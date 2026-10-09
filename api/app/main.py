"""FastAPI entrypoint (BACKBONE §7.14.1). Adds `X-Aqua-Contract`, CORS (BI-12), `X-Api-Key` in aws mode.

Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.app.settings import Settings
from api.clients.sim_client import SimClient, SimRejected, SimUnavailable
from api.pipeline.monitor import AIMonitor
from api.routes import agent, ai, challenge, health
from api.routes import sim as sim_routes
from api.session.store import SessionHolder
from shared.contracts.models import CONTRACT_VERSION

HEADER = "X-Aqua-Contract"


def create_app(settings: Settings | None = None, sim_client: SimClient | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="AquaAgent orchestrator API", version=CONTRACT_VERSION)
    app.state.settings = settings
    app.state.sim_client = sim_client or SimClient(settings.sim_url)  # lazy: no I/O until used
    app.state.holder = SessionHolder()
    app.state.topology, app.state.layout = sim_routes.load_topology(settings)
    app.state.monitor = AIMonitor(settings, app.state.topology, app.state.layout)

    @app.exception_handler(SimUnavailable)
    async def _unavailable(request: Request, exc: SimUnavailable) -> JSONResponse:
        return JSONResponse(
            {"detail": f"Simulation engine unreachable at {app.state.sim_client.base_url}"}, status_code=503
        )

    @app.exception_handler(SimRejected)
    async def _rejected(request: Request, exc: SimRejected) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=422)

    # Middleware order (innermost first): key check -> CORS -> contract header (outermost, so even
    # preflight and 401 responses carry X-Aqua-Contract and CORS headers).
    @app.middleware("http")
    async def api_key_check(request: Request, call_next):
        if (
            settings.mode == "aws"
            and request.method != "OPTIONS"
            and request.url.path != "/api/health"  # ALB health check cannot send the key (§3.2)
            and (settings.api_key is None or request.headers.get("X-Api-Key") != settings.api_key)
        ):
            return JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
        return await call_next(request)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[HEADER],
    )

    @app.middleware("http")
    async def contract_header(request: Request, call_next):
        response = await call_next(request)
        response.headers[HEADER] = CONTRACT_VERSION
        return response

    for r in (health.router, sim_routes.router, challenge.router, agent.router, ai.router):
        app.include_router(r, prefix="/api")
    return app


app = create_app()
