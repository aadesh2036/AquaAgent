"""Metrics table of BACKBONE §9.5.

Implementation: docs/modules/05_ANOMALY_LOCALISATION.md
"""

from __future__ import annotations


def predictor_metrics(y_true, y_pred, mask) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")


def detection_metrics(results_by_sim) -> dict:
    """Recall by scenario type, FAR on operational sims (BI-06), delays."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")


def localisation_metrics(results_by_sim) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/05_ANOMALY_LOCALISATION.md")
