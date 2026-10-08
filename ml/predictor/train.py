"""Training script — runs IDENTICALLY locally and in SageMaker script mode (BACKBONE §9.1, §3.2).

Reads SM_CHANNEL_TRAIN / SM_CHANNEL_VAL / SM_MODEL_DIR / SM_OUTPUT_DATA_DIR with local defaults.

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations

import argparse
import os


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--arch", default="mlp", choices=["baseline", "mlp", "gnn"])
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=20261008)
    p.add_argument("--dataset-version", default="ds1")
    p.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "data/features/ds1"))
    p.add_argument("--val", default=os.environ.get("SM_CHANNEL_VAL", "data/features/ds1"))
    p.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "data/models/predictor/local"))
    p.add_argument("--output-dir", default=os.environ.get("SM_OUTPUT_DATA_DIR", "data/experiments/local"))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Train on NORMAL-only samples with random sensor masking (§9.1); write model + scalers + metrics."""
    args = parse_args(argv)  # noqa: F841 — used once implemented
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")


if __name__ == "__main__":
    raise SystemExit(main())
