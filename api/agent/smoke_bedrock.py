"""Minimal Converse smoke call used by infra/scripts/14_bedrock_check.sh. Model id from env only.

Implementation: docs/modules/07_AQUAAGENT_BEDROCK.md
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    model_id = os.environ.get("AQUA_BEDROCK_MODEL_ID")
    region = os.environ.get("AQUA_REGION") or os.environ.get("AWS_REGION")
    if not model_id or not region:
        print("set AQUA_BEDROCK_MODEL_ID and AQUA_REGION", file=sys.stderr)
        return 2
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/07_AQUAAGENT_BEDROCK.md")


if __name__ == "__main__":
    raise SystemExit(main())
