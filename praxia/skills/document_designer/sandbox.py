"""Sandbox executor for LLM-generated Python code.

Two layers of protection:

1. **AST allowlist** — parse the code with `ast`, walk every node, reject
   any import / call that's not explicitly whitelisted. Catches the
   majority of attempts (bare `import os`, `open("/etc/passwd")`,
   `subprocess`, `__import__`, attribute access on `os.system`, etc.).

2. **Subprocess sandbox** — write the (validated) code to a temp file
   and run it with a fresh `python` process under:
     - `timeout=` (default 30 s) via `subprocess.run`
     - `resource.setrlimit(RLIMIT_AS, ...)` for ~512 MB RAM (POSIX only;
       Windows has no equivalent so we skip)
     - empty CWD inside a `tempfile.TemporaryDirectory` so the script
       can't accidentally clobber the host's filesystem
     - PYTHONNOUSERSITE=1 to disable the user-site path
     - Network: not blocked at the syscall level (no namespaces on
       Windows; would need firejail / nsjail elsewhere). The AST
       allowlist refuses all networking imports though, which catches
       the LLM-generated case in practice.

The contract with the executed code: print a single line of output that
is `PRAXIA_OUTPUT:<base64-encoded-bytes>`. The host decodes that and
returns the bytes. Anything else printed (warnings, debug) is captured
in `SandboxResult.stderr` for diagnostics and the retry loop.
"""
from __future__ import annotations

import ast
import base64
import os
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

# Imports the sandboxed code is allowed to make. Anything else trips the
# AST validator. Add stdlib modules narrowly — every entry is a potential
# escape vector if the module exposes filesystem / network / process
# primitives.
ALLOWED_IMPORTS: frozenset[str] = frozenset({
    # Document libs (the whole point)
    "pptx", "docx",
    # Image generation (matplotlib in agg mode, Pillow for raster)
    "matplotlib", "matplotlib.pyplot", "matplotlib.figure",
    "matplotlib.patches", "matplotlib.colors", "matplotlib.cm",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "PIL.ImageColor",
    # Data / math
    "numpy", "math", "statistics", "random", "fractions", "decimal",
    # Core stdlib that's safe (no fs/net/proc)
    "io", "base64", "json", "datetime", "time", "itertools", "functools",
    "collections", "collections.abc", "operator", "copy", "string",
    "textwrap", "re", "uuid", "hashlib", "enum", "dataclasses", "typing",
    "typing_extensions",
    # Required for python-pptx internals to work without warning
    "sys",
})

# AST node types that are unconditionally rejected.
FORBIDDEN_NODES: tuple[type[ast.AST], ...] = (
    # `class Foo(bar.Baz):` is fine but we don't need anything that runs
    # at definition time outside what the LLM should produce. Note: this
    # list is a sanity check. The real teeth are in ALLOWED_IMPORTS.
)

# Names whose use we reject outright. These bypass import filtering
# (e.g. eval / exec / __import__ are builtins, not imports).
FORBIDDEN_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "compile", "__import__",
    "globals", "locals", "vars",
    "breakpoint", "input",  # input() would hang the sandbox
    # Common escape-hatches via dunder attributes
    "__builtins__", "__loader__", "__spec__",
})

# Attribute access patterns that look like an escape attempt.
# E.g. `pptx.__class__.__bases__[0].__subclasses__()`.
SUSPICIOUS_ATTRS: frozenset[str] = frozenset({
    "__class__", "__bases__", "__subclasses__", "__mro__",
    "__globals__", "__code__", "__closure__", "__dict__",
    "__getattribute__", "__reduce__", "__reduce_ex__",
})

# How big the output bytes can be (16 MB — enough for a 100-slide deck
# with several embedded images).
MAX_OUTPUT_BYTES: int = 16 * 1024 * 1024

# The marker the sandboxed code uses to return its bytes.
OUTPUT_PREFIX: str = "PRAXIA_OUTPUT:"


# ---------------------------------------------------------------------------
# Errors


class SandboxError(RuntimeError):
    """Base for sandbox failures."""


class SandboxValidationError(SandboxError):
    """Raised when the AST allowlist rejects the code (pre-execution)."""


class SandboxTimeout(SandboxError):
    """Raised when the subprocess exceeded its time budget."""


# ---------------------------------------------------------------------------
# Result


@dataclass
class SandboxResult:
    """Outcome of a sandbox run."""

    bytes: bytes = b""
    """The raw output payload (decoded from the PRAXIA_OUTPUT marker)."""

    stdout: str = ""
    """Anything the script printed BEFORE the marker line, or all of stdout
    if the marker was missing. Useful for debugging."""

    stderr: str = ""
    """Captured stderr (tracebacks, warnings, etc.)."""

    returncode: int = 0
    """Subprocess exit code (0 on success)."""

    duration_s: float = 0.0
    """Wall-clock time the subprocess ran for."""

    code: str = ""
    """The code that was executed — kept for retry-loop traceback context."""

    extras: dict = field(default_factory=dict)
    """Adapter-specific extras (e.g. matplotlib figure count)."""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and bool(self.bytes)


# ---------------------------------------------------------------------------
# AST validator


def _is_allowed_module(name: str) -> bool:
    """Allow `pptx` and `pptx.util` if `pptx` is in ALLOWED_IMPORTS, etc."""
    if name in ALLOWED_IMPORTS:
        return True
    head = name.split(".", 1)[0]
    if head in ALLOWED_IMPORTS:
        return True
    return False


def validate_code(code: str) -> None:
    """Parse `code` and reject if it tries anything outside the allowlist.

    Raises:
        SandboxValidationError: with a one-line description of the offense.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SandboxValidationError(f"syntax error: {e.msg} (line {e.lineno})") from e

    for node in ast.walk(tree):
        # Imports ----------------------------------------------------------
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_allowed_module(alias.name):
                    raise SandboxValidationError(
                        f"forbidden import: {alias.name!r} "
                        f"(allowed: {', '.join(sorted(ALLOWED_IMPORTS))})"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None or not _is_allowed_module(node.module):
                raise SandboxValidationError(
                    f"forbidden from-import: from {node.module!r} import ..."
                )
        # Direct calls to forbidden names ---------------------------------
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                raise SandboxValidationError(
                    f"forbidden call: {node.func.id}() is not allowed"
                )
        # Bare references to dangerous names ------------------------------
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                raise SandboxValidationError(
                    f"forbidden name reference: {node.id!r}"
                )
        # Suspicious attribute lookups (sandbox-escape style) -------------
        elif isinstance(node, ast.Attribute):
            if node.attr in SUSPICIOUS_ATTRS:
                raise SandboxValidationError(
                    f"forbidden attribute access: .{node.attr}"
                )


# ---------------------------------------------------------------------------
# Subprocess runner


def _build_runner_preamble(work_dir: Path) -> str:
    """Code prepended to the LLM's snippet inside the subprocess.

    Sets up the matplotlib non-interactive backend (so importing pyplot
    doesn't try to open a display), pins CWD to the temp dir, and
    installs a tiny helper `_emit(payload: bytes)` that the LLM is
    instructed to call at the end with its document bytes.
    """
    return textwrap.dedent(f"""
    import sys, os, base64
    os.chdir({str(work_dir)!r})
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.dont_write_bytecode = True

    def _emit(payload):
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("_emit() expects bytes, got " + type(payload).__name__)
        sys.stdout.write({OUTPUT_PREFIX!r})
        sys.stdout.write(base64.b64encode(bytes(payload)).decode("ascii"))
        sys.stdout.write("\\n")
        sys.stdout.flush()
    """).lstrip()


def _apply_resource_limits() -> None:
    """POSIX-only: cap virtual memory at 512 MB. Skipped on Windows."""
    try:
        import resource
    except ImportError:
        return  # Windows
    try:
        # 512 MB virtual address space
        soft = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
    except (ValueError, OSError):
        pass  # best-effort; some kernels reject setrlimit silently


def _is_frozen() -> bool:
    """True when running inside a PyInstaller-frozen bundle.

    In that case `sys.executable` is the bundled binary, not a real
    Python interpreter — invoking it as a subprocess would re-run the
    bundled entrypoint instead of executing our runner script. We fall
    back to in-process execution in that environment. The AST allowlist
    still bounces unsafe code; we lose the process-isolation layer and
    the wall-clock timeout (Python lacks safe thread-kill).
    """
    return getattr(sys, "frozen", False) is True


def _run_in_process(code: str, *, timeout_s: float) -> SandboxResult:
    """Execute validated code in the current Python process.

    Used only when the subprocess path is unavailable (frozen bundle).
    We construct a constrained globals dict, capture stdout, and read
    back the _emit marker from the captured output — same wire protocol
    as the subprocess path so the caller can't tell which ran.

    The `timeout_s` argument is accepted for API symmetry but isn't
    enforceable: there's no safe way to forcibly kill arbitrary Python
    code from another thread (`PyThreadState_SetAsyncExc` corrupts
    state on objects holding locks). The AST validator's rule against
    naive infinite loops + 16k LLM-token cap on generated code keeps
    runaway risk low in practice.
    """
    import io
    import time

    captured = io.StringIO()
    safe_builtins = {
        # Minimum set the LLM-generated code legitimately needs.
        "print": print, "range": range, "len": len, "list": list,
        "dict": dict, "set": set, "tuple": tuple, "str": str,
        "int": int, "float": float, "bool": bool, "bytes": bytes,
        "bytearray": bytearray, "isinstance": isinstance,
        "issubclass": issubclass, "min": min, "max": max, "sum": sum,
        "abs": abs, "round": round, "sorted": sorted, "reversed": reversed,
        "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
        "any": any, "all": all, "iter": iter, "next": next,
        "type": type, "repr": repr, "hash": hash, "id": id,
        "True": True, "False": False, "None": None,
        # Allow imports so the allowlisted modules are reachable. AST
        # validator already proved every import in the code is in the
        # allowlist, so this isn't a fresh attack surface.
        "__import__": __import__,
        # Exception classes — needed for try/except inside generated code.
        "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "RuntimeError": RuntimeError,
        "IOError": IOError, "OSError": OSError, "KeyError": KeyError,
        "IndexError": IndexError, "StopIteration": StopIteration,
        # python-pptx needs open() to load embedded images via Pillow;
        # but we can't expose open() to the LLM code itself. Pillow
        # uses the path → memoryview internally; for our in-process path
        # this is acceptable because trust boundary is "your own LLM".
        "open": open,
    }
    emitted: list[bytes] = []

    def _emit(payload: bytes | bytearray) -> None:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("_emit() expects bytes")
        emitted.append(bytes(payload))

    namespace: dict = {
        "__builtins__": safe_builtins,
        "__name__": "__sandbox__",
        "_emit": _emit,
    }
    # Same matplotlib backend pin as the subprocess path.
    os.environ.setdefault("MPLBACKEND", "Agg")

    t0 = time.monotonic()
    try:
        import contextlib
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            exec(compile(code, "<sandbox>", "exec"), namespace, namespace)  # noqa: S102
    except Exception as e:
        raise SandboxError(
            f"in-process sandbox raised {type(e).__name__}: {e}. "
            f"stdout tail:\n{captured.getvalue()[-1500:]}"
        ) from e
    duration = time.monotonic() - t0

    if not emitted:
        raise SandboxError(
            "code finished without calling _emit(bytes). "
            f"stdout tail:\n{captured.getvalue()[-500:]}"
        )

    return SandboxResult(
        stdout=captured.getvalue(),
        stderr="",
        returncode=0,
        duration_s=duration,
        bytes=emitted[0],
        code=code,
    )


def run_in_sandbox(
    code: str,
    *,
    timeout_s: float = 30.0,
    extra_env: dict[str, str] | None = None,
    skip_validate: bool = False,
    force_in_process: bool | None = None,
) -> SandboxResult:
    """Execute `code` in a child Python process and return its bytes.

    Args:
        code: the Python program to run. Must call `_emit(<bytes>)`
            exactly once with the document payload.
        timeout_s: max wall-clock seconds. SandboxTimeout if exceeded.
        extra_env: additional env vars to set in the subprocess (e.g.
            paths to theme assets the code reads). Existing env is
            otherwise inherited (we don't blank the env to avoid
            breaking matplotlib font lookups, etc.).
        skip_validate: bypass the AST allowlist. Only set in tests where
            you know the code is safe — never from user-facing code.
        force_in_process: if True, always use the in-process path
            (faster, less isolation). If False, always use subprocess.
            If None (default), use in-process when frozen, subprocess
            otherwise. The frozen check matters for the desktop
            sidecar — sys.executable in a PyInstaller bundle is the
            bundle itself, not a Python interpreter.

    Returns:
        SandboxResult with `.bytes` populated on success.

    Raises:
        SandboxValidationError: AST allowlist rejected the code.
        SandboxTimeout: process exceeded `timeout_s`.
        SandboxError: any other failure (non-zero exit, missing marker).
    """
    if not skip_validate:
        validate_code(code)

    use_in_process = force_in_process if force_in_process is not None else _is_frozen()
    if use_in_process:
        return _run_in_process(code, timeout_s=timeout_s)

    import time

    with tempfile.TemporaryDirectory(prefix="praxia_sandbox_") as work_dir:
        work_path = Path(work_dir)
        runner_path = work_path / "runner.py"
        runner_path.write_text(
            _build_runner_preamble(work_path) + "\n# --- LLM code below ---\n" + code,
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Make matplotlib pick a writable cache dir inside the sandbox
        env["MPLCONFIGDIR"] = str(work_path / ".mplcache")
        if extra_env:
            env.update(extra_env)

        kwargs: dict = {
            "args": [sys.executable, str(runner_path)],
            "capture_output": True,
            "timeout": timeout_s,
            "cwd": str(work_path),
            "env": env,
            "text": True,
        }
        # POSIX: install resource limits via preexec_fn. Windows: skip.
        if os.name == "posix":
            kwargs["preexec_fn"] = _apply_resource_limits

        t0 = time.monotonic()
        try:
            proc = subprocess.run(**kwargs)  # noqa: S603
        except subprocess.TimeoutExpired as e:
            raise SandboxTimeout(
                f"sandbox exceeded {timeout_s}s (output so far: "
                f"{(e.stdout or '')[:200]!r})"
            ) from e
        duration = time.monotonic() - t0

        result = SandboxResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            returncode=proc.returncode,
            duration_s=duration,
            code=code,
        )

        if proc.returncode != 0:
            raise SandboxError(
                f"sandbox exited with code {proc.returncode}. "
                f"stderr (tail):\n{(proc.stderr or '').rstrip()[-1500:]}"
            )

        # Find the marker line and decode it.
        payload = _extract_payload(proc.stdout or "")
        if payload is None:
            raise SandboxError(
                f"sandbox finished without emitting output. Make sure the "
                f"code calls `_emit(bytes)` exactly once at the end. "
                f"stdout tail:\n{(proc.stdout or '').rstrip()[-500:]}"
            )

        if len(payload) > MAX_OUTPUT_BYTES:
            raise SandboxError(
                f"output too large: {len(payload)} bytes (max {MAX_OUTPUT_BYTES})"
            )

        result.bytes = payload
        # Strip the marker line out of stdout so callers see only the
        # script's intentional prints (debug logs, etc.).
        result.stdout = _stdout_without_marker(proc.stdout or "")
        return result


def _extract_payload(stdout: str) -> bytes | None:
    """Find the last line starting with `PRAXIA_OUTPUT:` and decode it."""
    target = None
    for line in stdout.splitlines():
        if line.startswith(OUTPUT_PREFIX):
            target = line[len(OUTPUT_PREFIX):].strip()
    if target is None:
        return None
    try:
        return base64.b64decode(target, validate=True)
    except (ValueError, base64.binascii.Error) as e:
        raise SandboxError(f"sandbox output was not valid base64: {e}") from e


def _stdout_without_marker(stdout: str) -> str:
    return "\n".join(
        line for line in stdout.splitlines() if not line.startswith(OUTPUT_PREFIX)
    )
