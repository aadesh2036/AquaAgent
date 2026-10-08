"""End-to-end challenge run against a base URL (G8 local + AWS, G10 three clean runs).

Usage: python -m api.scripts.e2e_challenge --base http://localhost:8080 [--api-key ...] [--runs 3]
Implementation: docs/modules/08_ORCHESTRATOR_API.md
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--api-key", default=None)
    p.add_argument("--runs", type=int, default=1)
    args = p.parse_args(argv)  # noqa: F841 — used once implemented
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/08_ORCHESTRATOR_API.md")


if __name__ == "__main__":
    raise SystemExit(main())
