"""Tune k1,k2,W,T on VAL only, then freeze → thresholds.json (BACKBONE §9.3, G5).

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations


def tune_on_val(val_uri: str, predictor_artifact: str, far_target: float = 0.05) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
