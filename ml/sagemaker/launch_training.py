"""Launch a SageMaker Training Job running ml/predictor/train.py in script mode.

Instance type and framework version are read from env (<VERIFY>), never hard-coded.

Implementation: docs/modules/06_SAGEMAKER.md
"""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-version", default="ds1")
    p.add_argument("--arch", default="mlp")
    p.add_argument("--instance-type", default=os.environ.get("AQUA_SM_TRAIN_INSTANCE"))
    p.add_argument("--framework-version", default=os.environ.get("AQUA_SM_PT_VERSION"))
    p.add_argument("--py-version", default=os.environ.get("AQUA_SM_PY_VERSION"))
    p.add_argument("--local", action="store_true", help="SageMaker local mode (instance_type='local')")
    args = p.parse_args(argv)  # noqa: F841 — used once implemented
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


if __name__ == "__main__":
    raise SystemExit(main())
