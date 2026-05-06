"""Flow endpoint: POST /flows/{name}."""
from __future__ import annotations

from typing import Any


def build_router(*, current_user: Any):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    class FlowCallRequest(BaseModel):
        inputs: dict[str, Any]

    router = APIRouter()

    @router.post("/flows/{name}")
    def run_flow(name: str, req: FlowCallRequest, user=Depends(current_user)):
        from praxia.flows import get_flow

        try:
            flow_cls = get_flow(name)
        except KeyError:
            raise HTTPException(404, f"Unknown flow: {name}")
        flow = flow_cls()
        result = flow.run(req.inputs)
        return {
            "output": result.final_output,
            "step_outputs": result.step_outputs,
            "usage": result.total_usage,
        }

    return router
