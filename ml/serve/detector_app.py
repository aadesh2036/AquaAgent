"""Detector + localiser service — the second model endpoint in the ECS serve task (BI-27).

Routes
  GET  /detector/health          {status, detector, signatures, sigmas, params}
  POST /detector/reset           {session_id}
  POST /detector/update          {session_id, frame: ResidualFrame, context: WindowContext} → AnomalyResult
  POST /localiser/rank           {z_mean: {S1..F2}, top_k} → LocalisationResult

Streaming state (2-h residual history) is kept per ``session_id`` in memory (LRU). Models are loaded once from
``AQUA_THRESHOLDS_URI`` (SensorSetNet artifact) and ``AQUA_SIGNATURES_URI`` (physics signatures): local dirs
or s3:// URIs. Firewall (§11): bodies must validate as ResidualFrame / WindowContext (extra="forbid").
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict

import torch
from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict

from ml.anomaly.sensorset import SensorSetDetector
from ml.localisation.matcher import SignatureMatcher
from shared.contracts.models import (
    CONTRACT_VERSION,
    AnomalyResult,
    LocalisationResult,
    ResidualFrame,
    WindowContext,
)

log = logging.getLogger("aquaagent.detector")
MAX_SESSIONS = 8


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResetBody(_Body):
    session_id: str


class UpdateBody(_Body):
    session_id: str
    frame: ResidualFrame
    context: WindowContext


class RankBody(_Body):
    z_mean: dict[str, float]
    top_k: int = 3


def create_app(detector_uri: str | None = None, signatures_uri: str | None = None) -> FastAPI:
    det_uri = detector_uri or os.environ.get("AQUA_THRESHOLDS_URI")
    sig_uri = signatures_uri or os.environ.get("AQUA_SIGNATURES_URI")
    if not det_uri:
        raise RuntimeError("AQUA_THRESHOLDS_URI (detector artifact) is not set")
    torch.set_num_threads(int(os.environ.get("AQUA_DETECTOR_THREADS", "1")))
    proto = SensorSetDetector.load(det_uri)  # verifies the content hash once
    matcher = SignatureMatcher.load(sig_uri) if sig_uri else None
    sessions: OrderedDict[str, SensorSetDetector] = OrderedDict()
    lock = threading.Lock()
    log.info("loaded detector %s, signatures %s", proto.version, matcher.version if matcher else None)

    def session(sid: str) -> SensorSetDetector:
        if sid not in sessions:
            sessions[sid] = SensorSetDetector(proto.model, proto.cfg)  # shared weights, own history
            while len(sessions) > MAX_SESSIONS:
                sessions.popitem(last=False)
        sessions.move_to_end(sid)
        return sessions[sid]

    app = FastAPI(title="AquaAgent detector", version=CONTRACT_VERSION)

    @app.middleware("http")
    async def contract_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Aqua-Contract"] = CONTRACT_VERSION
        return response

    @app.get("/detector/health")
    def health() -> dict:
        return {
            "status": "ok",
            "detector": proto.version,
            "detector_kind": proto.cfg.get("detector"),
            "predictor_model_version": proto.cfg.get("predictor_model_version"),
            "signatures": matcher.version if matcher else None,
            "sigmas": proto.cfg["sigmas"],
            "params": proto.cfg["params"],
        }

    @app.post("/detector/reset")
    def reset(body: ResetBody) -> dict:
        with lock:
            session(body.session_id).reset()
        return {"ok": True}

    @app.post("/detector/update", response_model=AnomalyResult)
    def update(body: UpdateBody) -> AnomalyResult:
        with lock:
            return session(body.session_id).update(body.frame, body.context)

    @app.post("/localiser/rank", response_model=LocalisationResult)
    def rank(body: RankBody) -> LocalisationResult:
        if matcher is None:
            from fastapi import HTTPException

            raise HTTPException(503, "no signatures loaded (AQUA_SIGNATURES_URI)")
        return matcher.rank(body.z_mean, top_k=body.top_k)

    return app


def main() -> None:
    import argparse

    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("AQUA_DETECTOR_PORT", "8002")))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
