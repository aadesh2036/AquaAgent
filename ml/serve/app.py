"""Predictor service — the §7.9 contract over HTTP, as a container in the ECS serve task (BI-26).

Routes
  GET  /predictor/health         {status, model_version, arch, n_params}
  POST /predictor/predict        PredictorRequest → PredictorResponse (reconstruct + both LOO maps, one call)
  GET  /ping, POST /invocations  same, SageMaker-container compatible (lets this image become a SageMaker
                                 endpoint later without code changes)

The model is loaded once at start from ``AQUA_PREDICTOR_ARTIFACT`` (dir, model.tar.gz or s3:// URI, §10.4), or
from ``s3://$AQUA_BUCKET/models/predictor/$AQUA_PREDICTOR_VERSION/model.tar.gz`` when only those two are set.
Firewall (§11): the body must validate as ``PredictorRequest`` (``extra="forbid"``), so anything other than a
``SensorWindow`` is rejected with 422 before it reaches the model.
"""

from __future__ import annotations

import logging
import os
import threading

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ml.predictor.predict import Artifact, load_artifact, predict
from shared.contracts.models import CONTRACT_VERSION, PredictorRequest, PredictorResponse

log = logging.getLogger("aquaagent.predictor")


def create_app(artifact_uri: str | None = None) -> FastAPI:
    uri = artifact_uri or os.environ.get("AQUA_PREDICTOR_ARTIFACT")
    if not uri and os.environ.get("AQUA_BUCKET") and os.environ.get("AQUA_PREDICTOR_VERSION"):
        # canonical §10.2 layout: s3://<bucket>/models/predictor/<model_version>/model.tar.gz
        uri = f"s3://{os.environ['AQUA_BUCKET']}/models/predictor/{os.environ['AQUA_PREDICTOR_VERSION']}/model.tar.gz"
    if not uri:
        raise RuntimeError(
            "set AQUA_PREDICTOR_ARTIFACT (dir, model.tar.gz or s3:// URI) or AQUA_BUCKET + AQUA_PREDICTOR_VERSION"
        )
    torch.set_num_threads(int(os.environ.get("AQUA_PREDICTOR_THREADS", "1")))
    art: Artifact = load_artifact(uri)
    mv = art.meta["model_version"]
    expected = os.environ.get("AQUA_PREDICTOR_VERSION")
    if expected and expected != mv:
        raise RuntimeError(f"AQUA_PREDICTOR_VERSION={expected} but artifact is {mv}")
    lock = threading.Lock()  # torch modules are not guaranteed re-entrant; calls take ~2 ms
    log.info("loaded predictor %s from %s", mv, uri)

    app = FastAPI(title="AquaAgent predictor", version=CONTRACT_VERSION)

    @app.middleware("http")
    async def contract_header(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Aqua-Contract"] = CONTRACT_VERSION
        return response

    def _run(req: PredictorRequest) -> PredictorResponse:
        if req.model_version != mv:
            raise HTTPException(
                status_code=409, detail=f"model_version {req.model_version!r} not served; serving {mv!r}"
            )
        with lock:
            return predict(req.sensor_window, art, mv)

    @app.get("/predictor/health")
    def health() -> dict:
        return {
            "status": "ok",
            "model_version": mv,
            "arch": art.meta["arch"],
            "n_params": art.meta["n_params"],
        }

    @app.post("/predictor/predict", response_model=PredictorResponse)
    def predict_route(req: PredictorRequest) -> PredictorResponse:
        return _run(req)

    @app.get("/ping")
    def ping() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.post("/invocations", response_model=PredictorResponse)
    def invocations(req: PredictorRequest) -> PredictorResponse:
        return _run(req)

    return app


def main() -> None:
    import argparse

    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("AQUA_PREDICTOR_PORT", "8001")))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
