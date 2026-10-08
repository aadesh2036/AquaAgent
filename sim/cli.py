"""Container entrypoint: `serve | generate | merge` (BACKBONE §3.2, §8.6, Appendix A).

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aquaagent-sim")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run §7.14.2 server on :8000")
    s.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container entrypoint
    s.add_argument("--port", type=int, default=8000)
    g = sub.add_parser("generate", help="generate one shard of a dataset (§8.6)")
    g.add_argument("--config", required=True)
    g.add_argument("--shard", type=int, required=True)
    g.add_argument("--num-shards", type=int, required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=None, help="cap sims (smoke runs)")
    m = sub.add_parser("merge", help="merge shards → processed/ + manifest (§8.6)")
    m.add_argument("--config", required=True)
    m.add_argument("--raw", required=True)
    m.add_argument("--out", required=True)
    args = p.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        from sim.server.app import app

        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    print(
        f"NOT IMPLEMENTED — `{args.cmd}`: see docs/modules/01_SIMULATION_ENGINE.md / 02_DATA_GENERATION.md",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
