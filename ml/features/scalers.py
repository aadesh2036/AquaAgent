"""Standardisation fitted on TRAIN split only (BACKBONE §7.7, BI-09).

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations


def fit_scalers(train_uri: str) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")


def save_scalers(scalers: dict, path: str) -> None:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")


def load_scalers(path: str) -> dict:
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")
