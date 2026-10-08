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
    if args.cmd == "generate":
        from sim.generate.runner import VALID_FRACTION_MIN, run_shard

        stats = run_shard(args.config, args.shard, args.num_shards, args.out, args.limit)
        print(
            f"shard {stats['shard']}: {stats['n_valid']}/{stats['n_requested']} valid "
            f"({stats['valid_fraction']:.1%}), {stats['elapsed_s']:.1f}s, {stats['s_per_sim']:.2f}s/sim"
        )
        return 0 if stats["n_requested"] and stats["valid_fraction"] >= VALID_FRACTION_MIN else 1
    if args.cmd == "merge":
        from sim.generate.merge import merge

        m = merge(args.config, args.raw, args.out)
        print(
            f"merged {m.n_valid}/{m.n_requested} valid sims; splits {m.counts_by_split}; "
            f"{args.out.rstrip('/')}/manifest.json"
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
