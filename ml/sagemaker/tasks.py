"""In-container pipeline steps for the scaled run (module 06, owner request 2026-10-10: ds3 + SageMaker).

Runs inside a SageMaker PyTorch training container (``sm_task.py --task <name> …``) or locally with the
same arguments. Every step reads its inputs from SageMaker channels (``SM_CHANNEL_<NAME>``) and writes
only to S3 prefixes the ``aqua-sagemaker-exec`` role may write (``models/``, ``experiments/``,
``sagemaker/``); the operator then copies run outputs that belong elsewhere (``features/<ds>/``).

* ``features``   processed/<ds> → features arrays + scalers (``ml.features.builder``)
                 → ``sagemaker/runs/<job>/features/``
* ``detector``   LOO residual cache (GPU) for the new predictor and the ds1 ship predictor → SensorSetNet
                 R3 training on train, τ/T on val → freeze → ONE test evaluation; also the ds1 ship detector on
                 the same test split, the predictor sweep on test and a contract-layout predictor comparison
                 → ``models/anomaly/<thr>/``, ``experiments/<thr>/``, residuals → ``sagemaker/runs/<job>/``
* ``signatures`` physics signatures from the new predictor + detector σ (sim engine) → test/val evaluation,
                 plus the ds1 ship signatures on the same split → ``models/localisation/<sig>/``,
                 ``experiments/<sig>/``
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np


def channel(name: str) -> Path:
    return Path(os.environ.get(f"SM_CHANNEL_{name.upper()}", f"/opt/ml/input/data/{name}"))


def s3_sync_up(local: Path, uri: str) -> None:
    """Upload a directory tree with boto3 (the training image has boto3; no aws cli needed).

    Bucket ``-`` = local dry run: list what would be uploaded, write nothing.
    """
    if uri.startswith("s3://-/"):
        print(f"[upload:dry] {sum(f.is_file() for f in local.rglob('*'))} files → {uri}", flush=True)
        return
    import boto3

    bucket, prefix = uri[5:].split("/", 1)
    s3 = boto3.client("s3")
    n = 0
    for f in sorted(local.rglob("*")):
        if f.is_file():
            s3.upload_file(str(f), bucket, f"{prefix.rstrip('/')}/{f.relative_to(local).as_posix()}")
            n += 1
    print(f"[upload] {n} files → {uri}", flush=True)


def artifact_path(d: Path) -> str:
    """A channel holding a predictor artifact: model.tar.gz or an extracted dir."""
    tgz = d / "model.tar.gz"
    return str(tgz if tgz.exists() else d)


def work_features(src: Path, dst: Path) -> Path:
    """Writable view of a read-only features channel (symlinks + an empty residuals/ dir)."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and not (dst / f.name).exists():
            (dst / f.name).symlink_to(f.resolve())
    (dst / "residuals").mkdir(exist_ok=True)
    if (src / "residuals").is_dir():
        for f in (src / "residuals").iterdir():
            if not (dst / "residuals" / f.name).exists():
                (dst / "residuals" / f.name).symlink_to(f.resolve())
    return dst


# ------------------------------------------------------------------------------------------- features
def task_features(a: argparse.Namespace) -> None:
    from ml.features import builder

    out = Path("/tmp/features") / a.dataset_version
    builder.main(["--processed", str(channel("processed")), "--out", str(out)])
    s3_sync_up(out, f"s3://{a.bucket}/{a.run_prefix}/features/")


# ------------------------------------------------------------------------------------------- detector
def cache_residuals(feat: Path, artifact: str, splits=("train", "val", "test"), device="cpu") -> str:
    from ml.anomaly.residuals import loo_residuals
    from ml.anomaly.tune import load_split
    from ml.predictor.predict import load_artifact

    art = load_artifact(artifact)
    mv = art.meta["model_version"]
    for s in splits:
        out = feat / "residuals" / f"{mv}_{s}.npy"
        if out.exists():
            continue
        t0 = time.time()
        r = loo_residuals(load_split(feat, s), art, bs=32768, device=device)
        np.save(out, r.astype(np.float32))
        print(f"[residuals] {mv} {s} rows={len(r)} {time.time() - t0:.0f}s", flush=True)
    return mv


def contract_layout_mae(feat: Path, artifact: str, split: str, stride: int = 2, device="cpu") -> dict:
    """Hidden-junction MAE (m) on normal rows, contract layout S1–S3 + F1/F2 (§9.5 headline metric)."""
    import torch

    from ml.features.tensorize import tensorize
    from ml.predictor.masking import default_masks
    from ml.predictor.predict import load_artifact
    from ml.predictor.train import ARRAY_KEYS, load_split

    art = load_artifact(artifact)
    gs = art.gs.to(device)
    model = art.model.to(device)
    a = load_split(feat, split)
    rows = np.flatnonzero(a["train_ok"])[::stride]
    junction = art.gs.node_static[:, 2].bool()
    ae = n = 0.0
    with torch.no_grad():
        for i in range(0, len(rows), 32768):
            sl = rows[i : i + 32768]
            b = {k: torch.from_numpy(np.ascontiguousarray(a[k][sl])).to(device) for k in ARRAY_KEYS}
            pm, qm = default_masks(len(sl), art.gs)
            hz, _ = model(*tensorize(b, pm.to(device), qm.to(device), gs), gs)
            err = (gs.head_z_to_pressure(hz) - b["p_true"]).abs().cpu()
            hid = (~pm) & junction
            ae += float((err * hid).sum())
            n += float(hid.sum())
    return {
        "model_version": art.meta["model_version"],
        "split": split,
        "normal_rows": int(len(rows)),
        "stride": stride,
        "hidden_junction_node_steps": int(n),
        "hidden_junction_mae_m": round(ae / max(n, 1), 4),
    }


def task_detector(a: argparse.Namespace) -> None:
    import torch

    from ml.anomaly import select, sensorset
    from ml.predictor import evaluate as pred_eval

    device = "cuda" if torch.cuda.is_available() else "cpu"
    feat = work_features(channel("features"), Path("/tmp/feat"))
    proc = channel("processed")
    new_pred = artifact_path(channel("predictor"))
    model_root, exp_root = Path("/tmp/models/anomaly"), Path("/tmp/experiments")

    mv = cache_residuals(feat, new_pred, device=device)
    base_pred = artifact_path(channel("basepredictor")) if channel("basepredictor").exists() else None
    base_mv = cache_residuals(feat, base_pred, splits=("test",), device=device) if base_pred else None

    sel = Path("/tmp/detsel")
    select.main(
        [
            "--predictor", mv, "--features", str(feat), "--processed", str(proc), "--only-r3",
            "--history", str(a.history), "--epochs", str(a.epochs), "--hidden", str(a.hidden),
            "--samples-per-class", str(a.samples_per_class), "--batch-size", str(a.batch_size),
            "--device", device, "--threads", str(os.cpu_count() or 4), "--out", str(sel),
        ]
    )  # fmt: skip
    sensorset.main(
        [
            "freeze", "--selection", str(sel), "--predictor", mv, "--features", str(feat),
            "--out-root", str(model_root), "--dataset-version", a.dataset_version,
        ]
    )  # fmt: skip
    thr = next(model_root.iterdir())
    exp = exp_root / thr.name
    sensorset.main(
        [
            "evaluate", "--detector", str(thr), "--features", str(feat), "--processed", str(proc),
            "--split", "test", "--experiments-root", str(exp_root),
        ]
    )  # fmt: skip
    shutil.copytree(sel, exp / "selection", dirs_exist_ok=True)

    compare = {"split": "test", "dataset_version": a.dataset_version}
    if base_pred and channel("basedetector").exists():
        base_exp = Path("/tmp/baseline_exp")
        sensorset.main(
            [
                "evaluate", "--detector", str(channel("basedetector")), "--features", str(feat),
                "--processed", str(proc), "--split", "test", "--experiments-root", str(base_exp),
            ]
        )  # fmt: skip
        b = next(base_exp.iterdir())
        shutil.copytree(b, exp / f"baseline_{b.name}", dirs_exist_ok=True)
    compare["predictor_contract_layout"] = [
        contract_layout_mae(feat, p, "test", device=device) for p in filter(None, (new_pred, base_pred))
    ]
    (exp / "compare_test.json").write_text(json.dumps(compare, indent=1))
    print(json.dumps(compare, indent=1), flush=True)

    # full predictor sweep (coverage / hop / placements) on test — new model only (scalers must match)
    pred_exp = exp_root / mv
    pred_eval.main(
        ["--features", str(feat), "--split", "test", "--models", new_pred, "--stride", str(a.eval_stride),
         "--out", str(pred_exp / "eval_test")]
    )  # fmt: skip

    s3_sync_up(thr, f"s3://{a.bucket}/models/anomaly/{thr.name}/")
    s3_sync_up(exp, f"s3://{a.bucket}/experiments/{thr.name}/")
    s3_sync_up(pred_exp, f"s3://{a.bucket}/experiments/{mv}/")
    res_dir = Path("/tmp/residuals_out")
    res_dir.mkdir(exist_ok=True)
    for f in (feat / "residuals").iterdir():
        if not f.is_symlink():
            shutil.copy(f, res_dir / f.name)
    s3_sync_up(res_dir, f"s3://{a.bucket}/{a.run_prefix}/residuals/")
    print(f"[detector] done thr={thr.name} predictor={mv} baseline_predictor={base_mv}", flush=True)


# ------------------------------------------------------------------------------------------- signatures
def task_signatures(a: argparse.Namespace) -> None:
    from ml.localisation import evaluate as loc_eval
    from ml.localisation import signatures
    from ml.localisation.matcher import SignatureMatcher

    feat = work_features(channel("features"), Path("/tmp/feat"))
    proc = channel("processed")
    out = signatures.generate(
        artifact_path(channel("predictor")),
        str(channel("detector")),
        "/tmp/models/localisation",
        config=f"config/generation/{a.dataset_version}.yaml",
        dataset_version=a.dataset_version,
        start_hours=tuple(int(h) for h in a.start_hours.split(",")),
    )
    exp = Path("/tmp/experiments") / out.name
    holdout = ["pipe:5", "junction:6"]
    exp.mkdir(parents=True, exist_ok=True)
    summary = {}
    for split in ("val", "test"):
        m = loc_eval.evaluate(SignatureMatcher.load(str(out)), feat, proc, split, holdout)
        m.pop("_table").to_csv(exp / f"localisation_table_{split}.csv", index=False)
        (exp / f"localisation_{split}.json").write_text(json.dumps(m, indent=1))
        summary[split] = m
    if channel("basesignatures").exists():
        m = loc_eval.evaluate(
            SignatureMatcher.load(str(channel("basesignatures"))), feat, proc, "test", holdout
        )
        m.pop("_table")
        (exp / f"baseline_{m['signatures_version']}_localisation_test.json").write_text(
            json.dumps(m, indent=1)
        )
        summary["baseline_test"] = m
    print(json.dumps(summary, indent=1), flush=True)
    s3_sync_up(out, f"s3://{a.bucket}/models/localisation/{out.name}/")
    s3_sync_up(exp, f"s3://{a.bucket}/experiments/{out.name}/")


TASKS = {"features": task_features, "detector": task_detector, "signatures": task_signatures}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=sorted(TASKS))
    p.add_argument("--dataset-version", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--run-prefix", required=True, help="sagemaker/runs/<job> — scratch outputs")
    p.add_argument("--history", type=int, default=24)
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--hidden", type=int, default=32)
    p.add_argument("--samples-per-class", type=int, default=60000)
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--eval-stride", type=int, default=4)
    p.add_argument("--start-hours", default="3,9,15,21")
    p.add_argument("--git-sha", default="unknown")
    a, _ = p.parse_known_args(argv)
    os.environ.setdefault("AQUA_GIT_SHA", a.git_sha)
    TASKS[a.task](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
