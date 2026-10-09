"""Package a trained predictor into ``model.tar.gz`` + its experiment record (BACKBONE §10.2, module 04 §3).

Layout (also what SageMaker would produce from SM_MODEL_DIR)::

    model.tar.gz: model.pt, meta.json, scalers.json, graph.json
    data/models/predictor/<mv>/model.tar.gz
    data/experiments/<mv>/{train_metrics.json, curves.csv, metrics_{val,test}.json, coverage_*.csv,
                           hop_error_*.csv, placements_*.csv, plots_<split>/*.png}

``--upload`` copies both to ``s3://$AQUA_BUCKET/models/predictor/<mv>/`` and ``experiments/<mv>/``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ARTIFACT_FILES = ("model.pt", "meta.json", "scalers.json", "graph.json")
EVAL_FILES = ("metrics.json", "coverage.csv", "hop_error.csv", "placements.csv")


def build_tarball(model_dir: Path) -> Path:
    out = model_dir / "model.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for name in ARTIFACT_FILES:
            info = tar.gettarinfo(str(model_dir / name), arcname=name)
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""  # reproducible
            with open(model_dir / name, "rb") as f:
                tar.addfile(info, f)
    return out


def collect_experiment(mv: str, eval_dirs: list[Path], exp_root: Path) -> Path:
    exp = exp_root / mv
    exp.mkdir(parents=True, exist_ok=True)
    for ev in eval_dirs:
        split = json.loads((ev / "metrics.json").read_text())["split"]
        for name in EVAL_FILES:
            if (ev / name).exists():
                stem, ext = name.rsplit(".", 1)
                shutil.copy(ev / name, exp / f"{stem}_{split}.{ext}")
        if (ev / "plots").is_dir():
            shutil.copytree(ev / "plots", exp / f"plots_{split}", dirs_exist_ok=True)
    return exp


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-version", required=True)
    p.add_argument("--eval-dirs", nargs="*", default=[], help="evaluate.py output dirs to attach")
    p.add_argument("--models-root", default="data/models/predictor")
    p.add_argument("--experiments-root", default="data/experiments")
    p.add_argument("--upload", action="store_true")
    p.add_argument("--bucket", default=os.environ.get("AQUA_BUCKET"))
    args = p.parse_args(argv)

    model_dir = Path(args.models_root) / args.model_version
    meta = json.loads((model_dir / "meta.json").read_text())
    assert meta["model_version"] == args.model_version, "meta.json model_version mismatch"
    tgz = build_tarball(model_dir)
    exp = collect_experiment(
        args.model_version, [Path(d) for d in args.eval_dirs], Path(args.experiments_root)
    )
    print(f"[package] {tgz} ({tgz.stat().st_size} B); experiment record {exp}")

    if args.upload:
        if not args.bucket:
            raise SystemExit("--upload needs AQUA_BUCKET (source infra/env.sh)")
        base = f"s3://{args.bucket}"
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                str(tgz),
                f"{base}/models/predictor/{args.model_version}/model.tar.gz",
                "--only-show-errors",
            ],
            check=True,
        )
        subprocess.run(
            [
                "aws",
                "s3",
                "sync",
                str(exp),
                f"{base}/experiments/{args.model_version}/",
                "--only-show-errors",
            ],
            check=True,
        )
        print(f"[package] uploaded → {base}/models/predictor/{args.model_version}/model.tar.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
