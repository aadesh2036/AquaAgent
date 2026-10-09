"""PredictorClient: §7.9 predictor, in-process or over HTTP (BACKBONE §3.3; BI-26).

* ``AQUA_PREDICTOR_URL`` set  → POST {url}/predictor/predict (the ``predictor`` container in the ECS task).
* otherwise                   → loads ``AQUA_PREDICTOR_ARTIFACT`` (dir / model.tar.gz / s3://) in-process.

The ONLY accepted input is SensorWindow (§7.8, §11 firewall).
"""

from __future__ import annotations

import os

import httpx

from shared.contracts.models import PredictorMode, PredictorRequest, PredictorResponse, SensorWindow


class PredictorClient:
    def __init__(
        self, artifact: str | None = None, url: str | None = None, model_version: str | None = None
    ) -> None:
        self.url = (url or os.environ.get("AQUA_PREDICTOR_URL") or "").rstrip("/") or None
        self._art = None
        if self.url:
            self._http = httpx.Client(base_url=self.url, timeout=5.0)
            h = self._http.get("/predictor/health").json()
            self.model_version = model_version or h["model_version"]
            self._remote_arch = h.get("arch", "remote")
        else:
            from ml.predictor.predict import load_artifact

            if not artifact:
                raise RuntimeError("set AQUA_PREDICTOR_ARTIFACT (or AQUA_PREDICTOR_URL)")
            self._art = load_artifact(artifact)
            self.model_version = self._art.meta["model_version"]
        self.arch = self._art.meta["arch"] if self._art else self._remote_arch

    @property
    def node_order(self) -> list[str] | None:
        return self._art.gs.node_order if self._art else None

    def predict(self, window: SensorWindow) -> PredictorResponse:
        """Signature is the firewall: nothing but a SensorWindow may enter (§11)."""
        if not isinstance(window, SensorWindow):
            raise TypeError("PredictorClient.predict accepts only a SensorWindow (§11)")
        if self._art is not None:
            from ml.predictor.predict import predict

            return predict(window, self._art, self.model_version)
        req = PredictorRequest(
            model_version=self.model_version, mode=PredictorMode.LEAVE_ONE_OUT, sensor_window=window
        )
        r = self._http.post(
            "/predictor/predict", content=req.model_dump_json(), headers={"Content-Type": "application/json"}
        )
        r.raise_for_status()
        return PredictorResponse.model_validate(r.json())
