"""FastAPI entrypoint (BACKBONE §7.14.1). Adds `X-Aqua-Contract` header, CORS (BI-12), `X-Api-Key` in aws mode.

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from shared.contracts.models import CONTRACT_VERSION  # noqa: F401


def create_app():  # -> fastapi.FastAPI
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


app = None  # replaced by create_app() in module 08
