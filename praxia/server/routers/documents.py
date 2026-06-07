"""Local-document ingestion endpoints.

A *folder* is a top-level directory the user registers with Praxia — typically
via the desktop app, which walks the directory recursively and uploads each
parseable file. Each uploaded file becomes a *document*: parsed via the
existing :mod:`praxia.io.parsers` pipeline, chunked, and persisted under the
calling user's namespace.

The resulting documents are searchable through the ``/documents/search``
endpoint and also surface to the agent's retriever (see
:class:`praxia.agent.commander.DefaultMemoryRetriever`).

Endpoints (all under ``/api/v1``):

  POST   /documents/folder                  register a folder (returns folder_id)
  GET    /documents/folders                 list user's registered folders
  GET    /documents/folder/{folder_id}      folder details + documents list
  DELETE /documents/folder/{folder_id}      remove a folder + all its documents
  POST   /documents/folder/{folder_id}/upload   upload one file (multipart)
  POST   /documents/search                  keyword search across documents

Storage layout (per user, all JSON for grep-ability + audit):

    <storage>/documents/<user_id>/
      folders.json                      registered folders index
      folder_<folder_id>/
        <doc_id>.json                   one document per file

Search is keyword-based for v1; embedding-aware retrieval comes when the
TiDB Vector / pgvector backend lands as a first-class memory backend.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Chunking — paragraphs up to this many chars stay as one chunk; longer
# paragraphs get split by sentence with a small overlap.
_TARGET_CHUNK_SIZE = 1200
_MIN_CHUNK_SIZE = 200
_CHUNK_OVERLAP = 100

# Hard upper bound — beyond this, skip the file. Tunable; covers most
# real-world documents while keeping memory pressure sensible.
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MiB


# ---------------------------------------------------------------------------
# Models (module-level for FastAPI introspection)
# ---------------------------------------------------------------------------


class Chunk(BaseModel):
    """A search-unit slice of a document's text content."""
    index: int                          # 0-based ordering within the document
    text: str
    start: int                          # character offset in original content
    end: int


class Document(BaseModel):
    """One file ingested into a folder."""
    id: str
    folder_id: str
    relative_path: str                  # path within the folder, forward-slashed
    filename: str
    size: int
    mtime: float
    content_hash: str                   # sha256 hex of file bytes
    indexed_at: float
    parser: str                         # extension that resolved the parser
    chunks: list[Chunk]
    metadata: dict[str, Any] = {}


class Folder(BaseModel):
    """A registered top-level directory + its bookkeeping."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    path: str                           # original absolute path on user's machine
    title: str = ""                     # human label (default = folder name)
    created_at: float = Field(default_factory=time.time)
    last_sync: float = Field(default_factory=time.time)
    doc_count: int = 0
    total_bytes: int = 0
    enabled: bool = True


class CreateFolderRequest(BaseModel):
    path: str
    title: str = ""


class UploadResult(BaseModel):
    doc_id: str
    folder_id: str
    chunks: int
    status: str                         # "indexed" | "unchanged" | "skipped"
    reason: str = ""


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    folder_ids: list[str] | None = None  # None = all enabled folders


class SearchHit(BaseModel):
    doc_id: str
    folder_id: str
    relative_path: str
    chunk_index: int
    text: str
    score: float


# ---------------------------------------------------------------------------
# Chunking + scoring helpers (pure functions, easy to unit test)
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。!?])\s+|(?<=[.!?。!?])(?=\S)")
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def chunk_text(text: str) -> list[Chunk]:
    """Split a long string into ~1200-char chunks with small overlap.

    Strategy:
      1. Split by blank-line paragraph boundary
      2. For paragraphs that fit, emit as one chunk
      3. For paragraphs that don't, split by sentence with overlap

    Char offsets refer to the original ``text``.
    """
    if not text.strip():
        return []

    out: list[Chunk] = []
    paragraphs: list[tuple[int, str]] = []  # (start, body)
    cursor = 0
    for raw in re.split(r"\n\s*\n+", text):
        if not raw:
            cursor += 1
            continue
        start = text.find(raw, cursor)
        if start < 0:
            start = cursor
        paragraphs.append((start, raw))
        cursor = start + len(raw)

    # Group adjacent short paragraphs together; split overly-long ones
    buf_start: int | None = None
    buf_end = 0
    buf_text = ""
    idx = 0

    def _flush():
        nonlocal buf_start, buf_end, buf_text, idx
        if buf_text:
            out.append(Chunk(
                index=idx,
                text=buf_text.strip(),
                start=buf_start or 0,
                end=buf_end,
            ))
            idx += 1
            buf_start = None
            buf_end = 0
            buf_text = ""

    for p_start, body in paragraphs:
        if len(body) > _TARGET_CHUNK_SIZE:
            # Flush whatever was being accumulated, then split this paragraph
            _flush()
            sentences = [s for s in _SENTENCE_SPLIT.split(body) if s.strip()]
            sent_buf = ""
            sent_buf_start = p_start
            offset = p_start
            for s in sentences:
                if len(sent_buf) + len(s) + 1 > _TARGET_CHUNK_SIZE and sent_buf:
                    out.append(Chunk(
                        index=idx,
                        text=sent_buf.strip(),
                        start=sent_buf_start,
                        end=offset,
                    ))
                    idx += 1
                    # Overlap: keep tail of sent_buf as seed for next chunk
                    overlap_text = sent_buf[-_CHUNK_OVERLAP:] if len(sent_buf) > _CHUNK_OVERLAP else ""
                    sent_buf = overlap_text + " " + s if overlap_text else s
                    sent_buf_start = max(sent_buf_start, offset - len(overlap_text))
                else:
                    sent_buf = (sent_buf + " " + s).strip() if sent_buf else s
                offset += len(s) + 1
            if sent_buf.strip():
                out.append(Chunk(
                    index=idx,
                    text=sent_buf.strip(),
                    start=sent_buf_start,
                    end=offset,
                ))
                idx += 1
        else:
            # Accumulate into buffer until we hit the target size
            if not buf_text:
                buf_start = p_start
            candidate = (buf_text + "\n\n" + body) if buf_text else body
            if len(candidate) > _TARGET_CHUNK_SIZE and buf_text:
                _flush()
                buf_start = p_start
                buf_text = body
                buf_end = p_start + len(body)
            else:
                buf_text = candidate
                buf_end = p_start + len(body)

    _flush()

    # Drop tiny chunks unless they're the only one
    if len(out) > 1:
        out = [c for c in out if len(c.text) >= _MIN_CHUNK_SIZE] or out

    # Re-index after any drops
    for new_idx, c in enumerate(out):
        if c.index != new_idx:
            out[new_idx] = Chunk(
                index=new_idx,
                text=c.text,
                start=c.start,
                end=c.end,
            )
    return out


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 2]


def score_chunk(query_tokens: list[str], chunk_text_lower: str, chunk_tokens: list[str]) -> float:
    """Simple BM25-ish scoring: token coverage × IDF-ish length penalty.

    No IDF table in v1 — we approximate by giving rarer terms (longer)
    proportionally more weight, and penalising long chunks lightly so a
    perfectly-matching short chunk wins over a long chunk that mentions
    the term once.
    """
    if not query_tokens or not chunk_tokens:
        return 0.0
    hits = 0
    weight = 0.0
    for qt in query_tokens:
        # Count term occurrences (caps capped to avoid runaway on repetition)
        c = min(chunk_text_lower.count(qt), 5)
        if c:
            hits += 1
            weight += c * (1 + min(len(qt), 12) / 12.0)
    if hits == 0:
        return 0.0
    # Coverage bonus when more distinct query tokens land
    coverage = hits / len(query_tokens)
    length_penalty = 1.0 / (1.0 + len(chunk_tokens) / 400.0)
    return weight * coverage * length_penalty


# ---------------------------------------------------------------------------
# Storage helpers — module-level so they can be reused outside the router
# (e.g. by the agent's retriever).
# ---------------------------------------------------------------------------


def _docs_root(storage: Path) -> Path:
    return Path(storage) / "documents"


def _user_root(storage: Path, user_id: str) -> Path:
    d = _docs_root(storage) / user_id
    return d


def _folders_file(storage: Path, user_id: str) -> Path:
    return _user_root(storage, user_id) / "folders.json"


def _folder_dir(storage: Path, user_id: str, folder_id: str) -> Path:
    return _user_root(storage, user_id) / f"folder_{folder_id}"


def load_user_folders(storage: Path, user_id: str) -> list[Folder]:
    """List the folders this user has registered (empty when none)."""
    p = _folders_file(storage, user_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [Folder.model_validate(f) for f in data]


def load_docs_in_folder(storage: Path, user_id: str, folder_id: str) -> list[Document]:
    """Load every document registered under one folder."""
    d = _folder_dir(storage, user_id, folder_id)
    if not d.exists():
        return []
    out: list[Document] = []
    for f in d.glob("*.json"):
        try:
            out.append(Document.model_validate(json.loads(f.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def search_for_user(
    storage: Path,
    user_id: str,
    query: str,
    *,
    limit: int = 5,
    folder_ids: list[str] | None = None,
    path_prefix: str | None = None,
    include_images: bool = False,
) -> list[dict[str, Any]]:
    """Keyword search across this user's documents.

    Re-usable by the agent's retriever — when ``CommandedAgent`` runs, it
    asks the default retriever for sources, which calls this function in
    addition to walking L1 / L3 / L4 memory.

    Args:
        storage: server storage root.
        user_id: scoping key — no cross-user leakage.
        query: free-text query.
        limit: max hits returned (top-scored).
        folder_ids: when set, restrict to these folder ids.
        path_prefix: when set, only consider documents whose
            ``relative_path`` starts with this prefix. Lets the agent
            answer "what does the file under contracts/2024/ say
            about X" without re-shaping the index. Matched
            case-sensitively against the stored relative_path.
        include_images: when True, each hit gets an additional
            ``"images"`` field containing the doc-side images the
            commander should attach to the vision LLM. For PDF the
            page image matching the chunk's page is picked; for
            DOCX/PPTX up to 2 embedded images are included. Off by
            default to keep the response small for callers that don't
            need vision context.

    Returns:
        list of dicts shaped like :class:`SearchHit` (for cheap
        JSON-serialisation). Empty list on any error / no results.
    """
    if not query.strip():
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    all_folders = load_user_folders(storage, user_id)
    if folder_ids:
        allowed = set(folder_ids)
        folders = [f for f in all_folders if f.id in allowed]
    else:
        folders = [f for f in all_folders if f.enabled]

    # Normalise path_prefix so callers can pass either "sub/" or "sub"
    # without surprises. We compare against relative_path which uses
    # forward slashes regardless of host OS.
    norm_prefix = None
    if path_prefix:
        norm_prefix = path_prefix.replace("\\", "/").strip("/")

    hits: list[SearchHit] = []
    for folder in folders:
        for doc in load_docs_in_folder(storage, user_id, folder.id):
            if norm_prefix is not None:
                rel = doc.relative_path.replace("\\", "/")
                # Match either "prefix/..." or exactly "prefix" as a file.
                if not (rel == norm_prefix or rel.startswith(norm_prefix + "/")):
                    continue
            for chunk in doc.chunks:
                lc = chunk.text.lower()
                chunk_tokens = _tokenize(chunk.text)
                score = score_chunk(query_tokens, lc, chunk_tokens)
                if score > 0:
                    hits.append(SearchHit(
                        doc_id=doc.id,
                        folder_id=doc.folder_id,
                        relative_path=doc.relative_path,
                        chunk_index=chunk.index,
                        text=chunk.text,
                        score=round(score, 4),
                    ))
    hits.sort(key=lambda h: h.score, reverse=True)
    top = hits[: max(1, int(limit))]

    if not include_images:
        return [h.model_dump() for h in top]

    # ── Vision-attach path (alpha20+) ───────────────────────────────
    # For each top hit, fetch the doc and pull the relevant image(s)
    # so the commander can pass them through to inner.run(images=...).
    #
    # We do this in a second pass to avoid loading every doc twice
    # during the initial scoring loop. Cap N images per hit + total
    # bytes per hit so a pathological 50-image DOCX doesn't blow up
    # the JSON response.
    _MAX_IMAGES_PER_HIT = 2
    _MAX_IMAGE_BYTES_PER_HIT = 4 * 1024 * 1024

    # Cache loaded docs across hits — multiple hits from the same doc
    # are common and we don't want to re-read the JSON for each one.
    doc_cache: dict[str, Document] = {}

    def _doc_for(folder_id: str, doc_id: str) -> Document | None:
        if doc_id in doc_cache:
            return doc_cache[doc_id]
        for d in load_docs_in_folder(storage, user_id, folder_id):
            if d.id == doc_id:
                doc_cache[doc_id] = d
                return d
        return None

    def _page_num_for_chunk(chunk_text: str) -> int | None:
        """PDF chunks contain `--- Page N ---` markers from the parser.
        Pull the first page number we can find inside the chunk."""
        m = re.search(r"---\s*Page\s+(\d+)\s*---", chunk_text)
        return int(m.group(1)) if m else None

    def _select_images(doc: Document, chunk_text: str) -> list[dict[str, Any]]:
        meta = doc.metadata or {}
        out: list[dict[str, Any]] = []
        total = 0

        # PDF: page-image matched to the chunk's page marker
        if doc.parser == "pdf":
            page_n = _page_num_for_chunk(chunk_text)
            page_images = meta.get("page_images") or []
            if page_n is not None:
                # Find image whose page_num equals this chunk's page
                for pi in page_images:
                    if pi.get("page_num") == page_n:
                        sz = int(pi.get("bytes_size") or 0)
                        if total + sz <= _MAX_IMAGE_BYTES_PER_HIT:
                            out.append({"mime": pi["mime"], "data": pi["data"]})
                            total += sz
                        break
            # If no page marker found, fall back to the first page image
            if not out and page_images:
                pi = page_images[0]
                sz = int(pi.get("bytes_size") or 0)
                if sz <= _MAX_IMAGE_BYTES_PER_HIT:
                    out.append({"mime": pi["mime"], "data": pi["data"]})

        # DOCX/PPTX: chunk-level association isn't reliable (the python-
        # docx / python-pptx parsers don't tell us which paragraph each
        # image is inline with), so just attach the first N embedded
        # images. The user's query already selected this doc — sending
        # 1-2 figures from it is more useful than sending none.
        elif doc.parser in ("docx", "pptx"):
            for img in (meta.get("embedded_images") or [])[:_MAX_IMAGES_PER_HIT]:
                sz = int(img.get("bytes_size") or 0)
                if total + sz > _MAX_IMAGE_BYTES_PER_HIT:
                    break
                out.append({"mime": img["mime"], "data": img["data"]})
                total += sz

        return out[:_MAX_IMAGES_PER_HIT]

    out: list[dict[str, Any]] = []
    for h in top:
        d = h.model_dump()
        doc = _doc_for(h.folder_id, h.doc_id)
        d["images"] = _select_images(doc, h.text) if doc else []
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_router(*, current_user: Any, storage: Path):
    # FastAPI types are required for the closure-defined route handlers
    # below — but importing them at module level would prevent
    # `praxia.server.routers.documents` from being importable by the
    # agent retriever (which calls `search_for_user`) on installs that
    # don't have the `[server]` extras. The agent's call path imports
    # this module before ever reaching `build_router`, so the FastAPI
    # import is gated here.
    from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

    # Pydantic ForwardRef gotcha: type annotations inside closure-defined
    # functions need their referenced names in the function's __globals__
    # at validate time. Inject the FastAPI types we use as parameter
    # annotations into this module's globals so Pydantic can resolve them.
    globals().update({
        "UploadFile": UploadFile,
        "File": File,
        "Form": Form,
    })

    docs_root = Path(storage) / "documents"

    # --- storage helpers ----------------------------------------------------

    def _user_root(user_id: str) -> Path:
        d = docs_root / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _folders_path(user_id: str) -> Path:
        return _user_root(user_id) / "folders.json"

    def _folder_dir(user_id: str, folder_id: str) -> Path:
        d = _user_root(user_id) / f"folder_{folder_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_folders(user_id: str) -> list[Folder]:
        p = _folders_path(user_id)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [Folder.model_validate(f) for f in data]

    def _save_folders(user_id: str, folders: list[Folder]) -> None:
        p = _folders_path(user_id)
        p.write_text(
            json.dumps([f.model_dump() for f in folders], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_folder(user_id: str, folder_id: str) -> Folder:
        for f in _load_folders(user_id):
            if f.id == folder_id:
                return f
        raise HTTPException(404, f"Folder not found: {folder_id}")

    def _save_doc(user_id: str, doc: Document) -> None:
        (_folder_dir(user_id, doc.folder_id) / f"{doc.id}.json").write_text(
            json.dumps(doc.model_dump(), ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_docs_in_folder(user_id: str, folder_id: str) -> list[Document]:
        d = _folder_dir(user_id, folder_id)
        out: list[Document] = []
        for f in d.glob("*.json"):
            try:
                out.append(Document.model_validate(json.loads(f.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def _find_doc_by_path(
        user_id: str, folder_id: str, relative_path: str,
    ) -> Document | None:
        rp = relative_path.replace("\\", "/")
        for d in _load_docs_in_folder(user_id, folder_id):
            if d.relative_path == rp:
                return d
        return None

    # --- routes -------------------------------------------------------------

    router = APIRouter()

    @router.post("/documents/folder")
    def create_folder(
        req: CreateFolderRequest,
        user=Depends(current_user),
    ) -> dict[str, Any]:
        if not req.path.strip():
            raise HTTPException(400, "path is required")
        folders = _load_folders(user.id)
        # Idempotent on path: if same user re-registers the same folder, return existing
        for f in folders:
            if f.user_id == user.id and f.path == req.path:
                return f.model_dump()
        folder = Folder(
            user_id=user.id,
            path=req.path,
            title=req.title or Path(req.path).name or req.path,
        )
        folders.append(folder)
        _save_folders(user.id, folders)
        return folder.model_dump()

    @router.get("/documents/folders")
    def list_folders(user=Depends(current_user)) -> list[dict[str, Any]]:
        return [f.model_dump() for f in _load_folders(user.id)]

    @router.get("/documents/folder/{folder_id}")
    def get_folder(folder_id: str, user=Depends(current_user)) -> dict[str, Any]:
        folder = _get_folder(user.id, folder_id)
        docs = _load_docs_in_folder(user.id, folder_id)
        data = folder.model_dump()
        data["documents"] = [
            {
                "id": d.id,
                "relative_path": d.relative_path,
                "filename": d.filename,
                "size": d.size,
                "indexed_at": d.indexed_at,
                "chunks": len(d.chunks),
            }
            for d in docs
        ]
        return data

    @router.delete("/documents/folder/{folder_id}")
    def delete_folder(folder_id: str, user=Depends(current_user)) -> dict[str, Any]:
        folders = _load_folders(user.id)
        if not any(f.id == folder_id for f in folders):
            raise HTTPException(404, f"Folder not found: {folder_id}")
        folders = [f for f in folders if f.id != folder_id]
        _save_folders(user.id, folders)
        d = _user_root(user.id) / f"folder_{folder_id}"
        if d.exists():
            try:
                shutil.rmtree(d)
            except OSError as e:
                _log.warning("Failed to remove %s: %s", d, e)
        return {"deleted": folder_id}

    @router.post("/documents/folder/{folder_id}/upload", response_model=UploadResult)
    async def upload_document(
        folder_id: str,
        file: UploadFile = File(...),
        relative_path: str = Form(...),
        mtime: float = Form(0.0),
        user=Depends(current_user),
    ) -> UploadResult:
        folder = _get_folder(user.id, folder_id)
        data = await file.read()
        size = len(data)

        if size == 0:
            return UploadResult(
                doc_id="", folder_id=folder_id, chunks=0,
                status="skipped", reason="empty file",
            )
        if size > _MAX_FILE_BYTES:
            return UploadResult(
                doc_id="", folder_id=folder_id, chunks=0,
                status="skipped",
                reason=f"file size {size} exceeds {_MAX_FILE_BYTES}",
            )

        content_hash = hashlib.sha256(data).hexdigest()
        rel = relative_path.replace("\\", "/")

        # Re-upload of unchanged file → short-circuit
        existing = _find_doc_by_path(user.id, folder_id, rel)
        if existing and existing.content_hash == content_hash:
            return UploadResult(
                doc_id=existing.id, folder_id=folder_id,
                chunks=len(existing.chunks),
                status="unchanged",
            )

        # Parse via the existing pluggable parser registry
        try:
            from praxia.io.parsers import parse_file, supported_extensions
        except ImportError as e:  # pragma: no cover
            raise HTTPException(500, f"Parsers not available: {e}")

        ext = Path(rel).suffix.lower().lstrip(".")
        if ext not in supported_extensions():
            return UploadResult(
                doc_id="", folder_id=folder_id, chunks=0,
                status="skipped",
                reason=f"no parser for .{ext}",
            )

        try:
            import io as _io
            parsed = parse_file(_io.BytesIO(data), filename=Path(rel).name)
        except Exception as e:
            _log.warning("Parse failed for %s: %s", rel, e)
            return UploadResult(
                doc_id="", folder_id=folder_id, chunks=0,
                status="skipped",
                reason=f"parse error: {str(e)[:120]}",
            )

        chunks = chunk_text(parsed.content)
        if not chunks:
            return UploadResult(
                doc_id="", folder_id=folder_id, chunks=0,
                status="skipped",
                reason="parsed content was empty",
            )

        # Re-use existing doc id if replacing, else mint a new one
        doc_id = existing.id if existing else uuid.uuid4().hex
        doc = Document(
            id=doc_id,
            folder_id=folder_id,
            relative_path=rel,
            filename=Path(rel).name,
            size=size,
            mtime=float(mtime or time.time()),
            content_hash=content_hash,
            indexed_at=time.time(),
            parser=ext,
            chunks=chunks,
            metadata=parsed.metadata,
        )
        _save_doc(user.id, doc)

        # Update folder stats (rough — full recalc on every upload would be
        # quadratic; this is "good enough" stats that converge after a sync)
        folder.last_sync = time.time()
        folder.doc_count = len(_load_docs_in_folder(user.id, folder_id))
        folder.total_bytes = sum(d.size for d in _load_docs_in_folder(user.id, folder_id))
        folders = [folder if f.id == folder.id else f for f in _load_folders(user.id)]
        _save_folders(user.id, folders)

        return UploadResult(
            doc_id=doc_id, folder_id=folder_id, chunks=len(chunks),
            status="indexed",
        )

    @router.post("/documents/search")
    def search_documents(
        req: SearchRequest,
        user=Depends(current_user),
    ) -> list[dict[str, Any]]:
        if not req.query.strip():
            return []
        query_tokens = _tokenize(req.query)
        if not query_tokens:
            return []

        # Collect candidate folders (enabled + filter, if any)
        all_folders = _load_folders(user.id)
        if req.folder_ids:
            allowed = set(req.folder_ids)
            folders = [f for f in all_folders if f.id in allowed]
        else:
            folders = [f for f in all_folders if f.enabled]

        hits: list[SearchHit] = []
        for folder in folders:
            for doc in _load_docs_in_folder(user.id, folder.id):
                for chunk in doc.chunks:
                    lc = chunk.text.lower()
                    chunk_tokens = _tokenize(chunk.text)
                    score = score_chunk(query_tokens, lc, chunk_tokens)
                    if score > 0:
                        hits.append(SearchHit(
                            doc_id=doc.id,
                            folder_id=doc.folder_id,
                            relative_path=doc.relative_path,
                            chunk_index=chunk.index,
                            text=chunk.text,
                            score=round(score, 4),
                        ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return [h.model_dump() for h in hits[: max(1, int(req.limit))]]

    @router.delete("/documents/folder/{folder_id}/file")
    def delete_file_by_path(
        folder_id: str,
        relative_path: str,
        user=Depends(current_user),
    ) -> dict[str, Any]:
        """Remove one indexed document by relative path.

        Used by the folder watcher when it sees a file vanish from disk
        — we don't want stale chunks pinned in retrieval results. Idempotent:
        deleting an already-missing file returns ``{"deleted": false}`` rather
        than 404, so a watcher replaying its journal doesn't error out.
        """
        _get_folder(user.id, folder_id)  # 404 if folder unknown
        doc = _find_doc_by_path(user.id, folder_id, relative_path)
        if doc is None:
            return {"deleted": False, "reason": "not indexed"}
        try:
            (_folder_dir(user.id, folder_id) / f"{doc.id}.json").unlink()
        except OSError as e:  # pragma: no cover
            _log.warning("Failed to remove doc %s: %s", doc.id, e)
            raise HTTPException(500, "Failed to remove document")
        # Refresh folder rollup counts so the UI reflects the new state.
        folders = _load_folders(user.id)
        for f in folders:
            if f.id == folder_id:
                remaining = _load_docs_in_folder(user.id, folder_id)
                f.doc_count = len(remaining)
                f.total_bytes = sum(d.size for d in remaining)
                f.last_sync = time.time()
                break
        _save_folders(user.id, folders)
        return {"deleted": True, "doc_id": doc.id, "relative_path": doc.relative_path}

    return router
