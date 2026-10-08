"""Smoke invoke + p95 latency + local-vs-endpoint parity (BACKBONE G6: p95 < 300 ms, parity ±1e-5).

Implementation: docs/modules/06_SAGEMAKER.md
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint-name", required=True)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--parity-artifact", default=None, help="local model.tar.gz for ±1e-5 parity check")
    args = p.parse_args(argv)  # noqa: F841 — used once implemented
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/06_SAGEMAKER.md")


if __name__ == "__main__":
    raise SystemExit(main())
