"""Auth endpoints: POST /auth/login + GET /me."""
from __future__ import annotations

from typing import Any


def build_router(*, auth: Any, current_user: Any):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    class LoginRequest(BaseModel):
        api_key: str

    router = APIRouter()

    @router.post("/auth/login")
    def login(req: LoginRequest):
        user = auth.authenticate(api_key=req.api_key)
        if user is None:
            raise HTTPException(401, "Invalid API key")
        token = auth.issue_token(user.id)
        return {"token": token, "user_id": user.id, "role": user.role}

    @router.get("/me")
    def me(user=Depends(current_user)):
        return {"id": user.id, "username": user.username, "role": user.role}

    return router
