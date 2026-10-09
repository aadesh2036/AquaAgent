"""Detector + localiser clients (BI-27): HTTP to the ``detector`` container, or in-process for local dev/tests.

* ``AQUA_DETECTOR_URL`` set → the ECS task's detector endpoint (http://localhost:8002); the api needs no torch.
* otherwise → loads ``AQUA_THRESHOLDS_URI`` / ``AQUA_SIGNATURES_URI`` in-process (requires torch).
Both expose the same small interface the AI monitor uses.
"""

from __future__ import annotations

import os
import uuid

import httpx
import numpy as np

from shared.contracts.models import AnomalyResult, LocalisationResult, ResidualFrame, WindowContext

SENSORS = ("S1", "S2", "S3", "F1", "F2")


class RemoteDetector:
    def __init__(self, url: str) -> None:
        self._http = httpx.Client(base_url=url.rstrip("/"), timeout=5.0)
        h = self._http.get("/detector/health").json()
        self.version = h["detector"]
        self.cfg = {"sigmas": h["sigmas"], "detector": h["detector_kind"], "params": h["params"]}
        self.signatures = h.get("signatures")
        self.session_id = uuid.uuid4().hex[:12]

    def reset(self) -> None:
        self.session_id = uuid.uuid4().hex[:12]  # fresh server-side history
        self._http.post("/detector/reset", json={"session_id": self.session_id}).raise_for_status()

    def update(self, frame: ResidualFrame, context: WindowContext) -> AnomalyResult:
        body = {
            "session_id": self.session_id,
            "frame": frame.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
        }
        r = self._http.post("/detector/update", json=body)
        r.raise_for_status()
        return AnomalyResult.model_validate(r.json())


class RemoteLocaliser:
    def __init__(self, url: str, version: str) -> None:
        self._http = httpx.Client(base_url=url.rstrip("/"), timeout=5.0)
        self.version = version

    def rank(self, z_mean, top_k: int = 3) -> LocalisationResult:
        z = (
            {s: float(v) for s, v in zip(SENSORS, np.asarray(z_mean, float), strict=True)}
            if not isinstance(z_mean, dict)
            else z_mean
        )
        r = self._http.post("/localiser/rank", json={"z_mean": z, "top_k": top_k})
        r.raise_for_status()
        return LocalisationResult.model_validate(r.json())


def make_detector_and_localiser(thresholds_uri: str | None, signatures_uri: str | None):
    """→ (detector, localiser | None) following AQUA_DETECTOR_URL / in-process rules."""
    url = os.environ.get("AQUA_DETECTOR_URL")
    if url:
        det = RemoteDetector(url)
        return det, (RemoteLocaliser(url, det.signatures) if det.signatures else None)
    from ml.anomaly.sensorset import SensorSetDetector

    if not thresholds_uri:
        raise RuntimeError("AQUA_THRESHOLDS_URI (detector artifact) is not set (or set AQUA_DETECTOR_URL)")
    det = SensorSetDetector.load(thresholds_uri)
    loc = None
    if signatures_uri:
        from ml.localisation.matcher import SignatureMatcher

        loc = SignatureMatcher.load(signatures_uri)
    return det, loc
