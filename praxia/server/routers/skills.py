"""Skill endpoint: POST /skills/{name}."""
from __future__ import annotations

from typing import Any


def build_router(*, current_user: Any):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    class SkillCallRequest(BaseModel):
        input: str
        kwargs: dict[str, Any] = {}

    router = APIRouter()

    @router.post("/skills/{name}")
    def run_skill(name: str, req: SkillCallRequest, user=Depends(current_user)):
        from praxia.skills import SKILLS

        if not SKILLS.has(name):
            raise HTTPException(404, f"Unknown skill: {name}")
        skill = SKILLS.get(name)()
        output = skill.run(req.input, **req.kwargs)
        return {"output": output, "skill": name}

    return router
