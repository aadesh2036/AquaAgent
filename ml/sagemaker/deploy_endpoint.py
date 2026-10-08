"""Create Model + EndpointConfig + real-time Endpoint (BACKBONE §3.2, §10.5).

Implementation: docs/modules/06_SAGEMAKER.md
"""

from __future__ import annotations

import argparse
import os


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-version", required=True)
    p.add_argument(
        "--endpoint-name", default=os.environ.get("AQUA_PREDICTOR_ENDPOINT", "aquaagent-predictor")
    )
    p.add_argument("--instance-type", default=os.environ.get("AQUA_SM_INFER_INSTANCE"))
    args = p.parse_args(argv)  # noqa: F841 — used once implemented
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


if __name__ == "__main__":
    raise SystemExit(main())
