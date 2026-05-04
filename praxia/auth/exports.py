"""Admin data exports — for compliance, backups, SIEM forwarding.

Produces CSV or JSON dumps of:
    - audit log
    - user list
    - skill usage stats
    - personal memory entries (per user)
    - shared memory blocks
    - policies

Every export action is itself logged in the audit log so admins can prove
who downloaded what and when (chain of custody).
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

Format = Literal["csv", "json", "jsonl"]


class AdminExporter:
    """Bundle of read-only export operations for administrators.

    Args:
        storage_dir: the .praxia/ directory root
        audit_log: AuditLog to record export events
    """

    def __init__(
        self,
        *,
        storage_dir: Path | str = ".praxia",
        audit_log=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self.root = Path(storage_dir)
        self.audit = audit_log

    # --- Audit log ---------------------------------------------------------

    def export_audit(
        self,
        *,
        output_path: Path | str,
        format: Format = "csv",
        since: float | None = None,
        actor_id: str | None = None,
    ) -> Path:
        """Export the audit log. Filters by time / actor if specified."""
        src = self.root / "auth" / "audit.jsonl"
        records = self._read_jsonl(src)
        if since:
            records = [r for r in records if r.get("timestamp", 0.0) >= since]
        if actor_id:
            records = [r for r in records if r.get("actor_id") == actor_id]
        path = self._write(output_path, records, format)
        self._record_export("audit", path, count=len(records))
        return path

    # --- Users -------------------------------------------------------------

    def export_users(self, *, output_path: Path | str, format: Format = "csv") -> Path:
        """Export the user list (sensitive — admin only)."""
        src = self.root / "auth" / "users.jsonl"
        records = self._read_jsonl(src)
        # Strip sensitive fields
        for r in records:
            r.pop("api_key_hash", None)
            r.pop("password_hash", None)
        path = self._write(output_path, records, format)
        self._record_export("users", path, count=len(records))
        return path

    # --- Skill usage ------------------------------------------------------

    def export_skill_usage(
        self,
        *,
        output_path: Path | str,
        format: Format = "csv",
        skill_name: str | None = None,
    ) -> Path:
        src = self.root / "skills" / "usage.jsonl"
        records = self._read_jsonl(src)
        if skill_name:
            records = [r for r in records if r.get("skill_name") == skill_name]
        path = self._write(output_path, records, format)
        self._record_export("skill_usage", path, count=len(records))
        return path

    # --- Personal memories ------------------------------------------------

    def export_personal_memory(
        self,
        *,
        user_id: str,
        output_path: Path | str,
        format: Format = "jsonl",
    ) -> Path:
        src = self.root / "personal" / f"{user_id}.jsonl"
        records = self._read_jsonl(src)
        path = self._write(output_path, records, format)
        self._record_export(
            "personal_memory", path, count=len(records), metadata={"user_id": user_id}
        )
        return path

    def export_all_personal_memory(
        self, *, output_dir: Path | str, format: Format = "jsonl"
    ) -> list[Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        personal_dir = self.root / "personal"
        if not personal_dir.exists():
            return results
        for src in personal_dir.glob("*.jsonl"):
            user_id = src.stem
            results.append(
                self.export_personal_memory(
                    user_id=user_id,
                    output_path=out_dir / f"{user_id}.{format}",
                    format=format,
                )
            )
        return results

    # --- Shared memory ----------------------------------------------------

    def export_shared_memory(
        self, *, output_path: Path | str, format: Format = "jsonl"
    ) -> Path:
        src_dir = self.root / "shared"
        records: list[dict[str, Any]] = []
        if src_dir.exists():
            for f in src_dir.glob("*.jsonl"):
                records.extend(self._read_jsonl(f))
        path = self._write(output_path, records, format)
        self._record_export("shared_memory", path, count=len(records))
        return path

    # --- Policies ---------------------------------------------------------

    def export_policies(
        self, *, output_path: Path | str, format: Format = "json"
    ) -> Path:
        src = self.root / "auth" / "policies.jsonl"
        records = self._read_jsonl(src)
        path = self._write(output_path, records, format)
        self._record_export("policies", path, count=len(records))
        return path

    # --- Internals --------------------------------------------------------

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    @staticmethod
    def _write(
        output_path: Path | str, records: list[dict[str, Any]], format: Format
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            with path.open("w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        elif format == "jsonl":
            with path.open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        elif format == "csv":
            if not records:
                path.write_text("", encoding="utf-8")
            else:
                # Union of all keys, stable order
                keys: list[str] = []
                seen: set[str] = set()
                for r in records:
                    for k in r:
                        if k not in seen:
                            seen.add(k)
                            keys.append(k)
                with path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                    writer.writeheader()
                    for r in records:
                        # Stringify any nested structures
                        flat = {
                            k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                            for k, v in r.items()
                        }
                        writer.writerow(flat)
        else:
            raise ValueError(f"Unsupported format: {format}")
        return path

    def _record_export(
        self,
        kind: str,
        path: Path,
        *,
        count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.audit:
            return
        meta = {"path": str(path), "count": count, "ts": time.time()}
        if metadata:
            meta.update(metadata)
        self.audit.record(
            actor_id="admin",
            actor_role="admin",
            action=f"export.{kind}",
            resource=str(path),
            metadata={k: str(v) for k, v in meta.items()},
        )
