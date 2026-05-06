"""Memory endpoints: search / mode / show."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    from praxia.memory import (
        MemoryUserPreference,
        PersonalMemory,
        resolve_memory_config,
    )

    class MemorySearchRequest(BaseModel):
        query: str
        limit: int = 5

    class MemoryModeRequest(BaseModel):
        mode: str  # "accumulate" | "read_only"

    router = APIRouter()

    @router.post("/memory/search")
    def memory_search(req: MemorySearchRequest, user=Depends(current_user)):
        cfg = resolve_memory_config(
            user_id=user.id, storage_dir=storage, user_role=user.role
        )
        pm = PersonalMemory(
            user_id=user.id,
            backend=cfg.backend,
            storage_dir=storage / "personal",
            mode=cfg.mode,
        )
        return {"results": pm.search(req.query, limit=req.limit)}

    @router.put("/memory/mode")
    def memory_set_mode(req: MemoryModeRequest, user=Depends(current_user)):
        if req.mode not in ("accumulate", "read_only"):
            raise HTTPException(400, "mode must be 'accumulate' or 'read_only'")
        pref = MemoryUserPreference.load(storage, user.id)
        pref.mode = req.mode  # type: ignore[assignment]
        pref.save(storage)
        return {"ok": True, "mode": req.mode}

    @router.get("/memory/show")
    def memory_show(user=Depends(current_user)):
        cfg = resolve_memory_config(
            user_id=user.id, storage_dir=storage, user_role=user.role
        )
        return {
            "backend": cfg.backend,
            "mode": cfg.mode,
            "locked_by_admin": cfg.locked_by_admin,
            "reason": cfg.reason,
        }

    return router
