"""Agent routes (BACKBONE §7.14.1). Not implemented until module 07 / 08 step 5."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.api_route("/agent/{path:path}", methods=["GET", "POST"], include_in_schema=False)
def agent_not_implemented(path: str) -> JSONResponse:
    return JSONResponse({"detail": "NOT IMPLEMENTED — module 08 step 5 / module 07"}, status_code=501)
