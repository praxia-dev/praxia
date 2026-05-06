"""Export endpoint: POST /export."""
from __future__ import annotations

from typing import Any


def build_router(*, current_user: Any):
    from fastapi import APIRouter, Depends
    from fastapi.responses import Response
    from pydantic import BaseModel

    from praxia.io.exporters import export_as

    class ExportRequest(BaseModel):
        content: str
        format: str
        title: str | None = None

    router = APIRouter()

    @router.post("/export")
    def export(req: ExportRequest, user=Depends(current_user)):
        kwargs = {"title": req.title} if req.title else {}
        result = export_as(req.content, format=req.format, **kwargs)
        media_type = {
            "html": "text/html",
            "md": "text/markdown",
            "json": "application/json",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(req.format, "application/octet-stream")
        return Response(content=result.bytes, media_type=media_type)

    return router
