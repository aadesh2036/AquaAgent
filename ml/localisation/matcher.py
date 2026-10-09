"""Cosine signature matcher → ranked candidates + probable zone (BACKBONE §7.11, §9.4). numpy only.

Online: mean z over the detection window → cosine similarity with every physics signature → best per location
→ softmax (temperature τ) → ranked candidates; zone score = sum of its candidates' scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from shared.contracts.models import Candidate as LocalisationCandidate
from shared.contracts.models import LocalisationResult, ProbableZone

SENSORS = ("S1", "S2", "S3", "F1", "F2")


class SignatureMatcher:
    def __init__(self, doc: dict, temperature: float = 0.05) -> None:
        self.doc, self.temperature = doc, temperature
        self.version = doc["signatures_version"]
        sigs = doc["signatures"]
        self.keys = [(s["location_kind"], s["location_id"], s["zone_id"]) for s in sigs]
        m = np.array([s["z_mean"] for s in sigs], np.float64)
        self.mat = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)

    @classmethod
    def load(cls, uri: str) -> SignatureMatcher:
        if uri.startswith("s3://"):
            import boto3

            bucket, key = uri[5:].rstrip("/").split("/", 1)
            body = boto3.client("s3").get_object(Bucket=bucket, Key=f"{key}/signatures.json")["Body"].read()
            return cls(json.loads(body))
        p = Path(uri)
        return cls(json.loads((p / "signatures.json" if p.is_dir() else p).read_text()))

    def rank(self, z_mean: dict[str, float] | np.ndarray, top_k: int = 3) -> LocalisationResult:
        v = np.array([z_mean[s] for s in SENSORS] if isinstance(z_mean, dict) else z_mean, np.float64)
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        sim = self.mat @ v
        best: dict[tuple[str, str, str], float] = {}
        for k, s in zip(self.keys, sim, strict=True):
            best[k] = max(best.get(k, -1.0), float(s))
        keys = list(best)
        sims = np.array([best[k] for k in keys])
        w = np.exp((sims - sims.max()) / self.temperature)
        w /= w.sum()
        order = np.argsort(-w)
        zones: dict[str, float] = {}
        for k, s in zip(keys, w, strict=True):
            zones[k[2]] = zones.get(k[2], 0.0) + float(s)
        zbest = max(zones, key=zones.get)
        return LocalisationResult(
            method="signature_cosine_v1",
            candidates=[
                LocalisationCandidate(
                    rank=i + 1,
                    location_kind=keys[j][0],
                    location_id=keys[j][1],
                    zone_id=keys[j][2],
                    score=round(float(w[j]), 4),
                    similarity=round(float(sims[j]), 4),
                )
                for i, j in enumerate(order[:top_k])
            ],
            probable_zone=ProbableZone(zone_id=zbest, score=round(zones[zbest], 4)),
            signatures_version=self.version,
        )
