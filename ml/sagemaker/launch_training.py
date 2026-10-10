"""Launch a SageMaker Training Job running ml/predictor/train.py in script mode.

Instance type and framework version are read from env (<VERIFY>), never hard-coded. The image URI is
resolved by the SDK (``sagemaker.image_uris``) from those values and recorded in the experiment log.

* Source: a minimal staged copy of the torch-only training path (``ml/features/tensorize.py`` +
  ``ml/predictor/{masking,gnn,mlp,train}.py``) plus a 2-line entry point — the SAME ``train.py`` as
  ``make train-local``.
* Channels ``train`` and ``val`` → ``s3://$AQUA_BUCKET/features/<ds>/`` (BACKBONE §10.2).
* Output → ``s3://$AQUA_BUCKET/models/predictor/<job>/output/model.tar.gz``; ``--copy`` then places it at
  ``models/predictor/<model_version>/model.tar.gz`` once the job has completed.

``--task features|detector|signatures`` (scaled ds3 run) stages ``ml/ shared/ sim/ config/`` + a pinned
``requirements.txt`` and runs ``ml.sagemaker.tasks`` in the same container; inputs come from
``--channel name=s3://…`` and hyper-parameters from ``--hp key=value``. Job output (unused) goes to
``sagemaker/jobs/``; each task uploads its real outputs itself (see ``ml/sagemaker/tasks.py``).

Implementation: docs/modules/06_SAGEMAKER.md
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STAGED_FILES = (
    "ml/__init__.py",
    "ml/features/__init__.py",
    "ml/features/tensorize.py",
    "ml/predictor/__init__.py",
    "ml/predictor/masking.py",
    "ml/predictor/gnn.py",
    "ml/predictor/mlp.py",
    "ml/predictor/train.py",
)
ENTRY = "from ml.predictor.train import main\n\nraise SystemExit(main())\n"
TASK_ENTRY = "from ml.sagemaker.tasks import main\n\nraise SystemExit(main())\n"
TASK_PACKAGES = ("ml", "shared", "sim", "config")
# on top of the SageMaker PyTorch image (torch + numpy come from the image; never pinned here)
TASK_REQUIREMENTS = "pandas>=2.2,<3\npyarrow>=15\npydantic>=2.7,<3\nwntr==1.5.0\npyyaml>=6\nmatplotlib>=3.8\n"
PASSTHROUGH = (
    "epochs",
    "lr",
    "batch_size",
    "hidden",
    "layers",
    "heads",
    "dropout",
    "p_default",
    "patience",
    "holdout_placements",
    "flow_loss_weight",
    "seed",
    "weight_decay",
    "device",
)


def stage_source(dst: Path) -> Path:
    for rel in STAGED_FILES:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dst / rel)
    (dst / "sm_entry.py").write_text(ENTRY)
    return dst


def stage_task_source(dst: Path) -> Path:
    ignore = shutil.ignore_patterns("__pycache__", "tests", "*.pyc", "*.ts", "node_modules")
    for pkg in TASK_PACKAGES:
        shutil.copytree(REPO / pkg, dst / pkg, ignore=ignore)
    (dst / "sm_task.py").write_text(TASK_ENTRY)
    (dst / "requirements.txt").write_text(TASK_REQUIREMENTS)
    return dst


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-version", default="ds1")
    p.add_argument("--task", default="predictor", choices=["predictor", "features", "detector", "signatures"])
    p.add_argument("--channel", action="append", default=[], help="name=s3://… (non-predictor tasks)")
    p.add_argument(
        "--hp", action="append", default=[], help="key=value hyper-parameter (non-predictor tasks)"
    )
    p.add_argument("--volume-gb", type=int, default=30)
    p.add_argument("--arch", default="gnn", choices=["mlp", "gnn"])
    p.add_argument("--instance-type", default=os.environ.get("AQUA_SM_TRAIN_INSTANCE"))
    p.add_argument("--framework-version", default=os.environ.get("AQUA_SM_PT_VERSION"))
    p.add_argument("--py-version", default=os.environ.get("AQUA_SM_PY_VERSION"))
    p.add_argument("--bucket", default=os.environ.get("AQUA_BUCKET"))
    p.add_argument("--role-arn", default=os.environ.get("AQUA_SM_ROLE_ARN"))
    p.add_argument("--region", default=os.environ.get("AQUA_REGION") or os.environ.get("AWS_REGION"))
    p.add_argument("--on-demand", action="store_true", help="disable managed Spot training")
    p.add_argument("--max-run-s", type=int, default=3 * 3600)
    p.add_argument("--wait", action="store_true", help="stream logs until the job ends")
    p.add_argument("--local", action="store_true", help="SageMaker local mode (instance_type='local')")
    p.add_argument("--dry-run", action="store_true", help="resolve image + build estimator, do not submit")
    for hp in PASSTHROUGH:
        p.add_argument("--" + hp.replace("_", "-"), default=None)
    args = p.parse_args(argv)
    for name in ("instance_type", "framework_version", "py_version", "bucket", "role_arn", "region"):
        if not getattr(args, name) and not (args.local and name == "instance_type"):
            raise SystemExit(f"missing --{name.replace('_', '-')} (set it in infra/env.sh)")

    import boto3
    import sagemaker
    from sagemaker.pytorch import PyTorch

    ts = datetime.now(UTC).strftime("%Y%m%d%H%M")
    sha = git_sha()
    if args.task != "predictor":
        return launch_task(args, ts, sha, sagemaker, boto3, PyTorch)
    mv = f"{args.arch}_{args.dataset_version}_{ts}"
    job = f"aquaagent-{args.arch}-{args.dataset_version}-{ts}"
    features = f"s3://{args.bucket}/features/{args.dataset_version}/"

    sess = (
        sagemaker.local.LocalSession()
        if args.local
        else sagemaker.Session(boto3.Session(region_name=args.region), default_bucket=args.bucket)
    )
    hps = {"arch": args.arch, "dataset-version": args.dataset_version, "model-version": mv, "git-sha": sha}
    hps.update({k.replace("_", "-"): v for k in PASSTHROUGH if (v := getattr(args, k)) is not None})
    spot = not args.on_demand and not args.local

    with tempfile.TemporaryDirectory() as tmp:
        est = PyTorch(
            entry_point="sm_entry.py",
            source_dir=str(stage_source(Path(tmp))),
            role=args.role_arn,
            framework_version=args.framework_version,
            py_version=args.py_version,
            instance_count=1,
            instance_type="local" if args.local else args.instance_type,
            hyperparameters=hps,
            output_path=f"s3://{args.bucket}/models/predictor/",
            code_location=f"s3://{args.bucket}/sagemaker/code",
            use_spot_instances=spot,
            max_run=args.max_run_s,
            max_wait=2 * args.max_run_s if spot else None,
            volume_size=args.volume_gb,
            disable_profiler=True,
            debugger_hook_config=False,
            environment={"PYTHONUNBUFFERED": "1", "AQUA_GIT_SHA": sha},
            tags=[{"Key": "project", "Value": "aquaagent"}, {"Key": "model_version", "Value": mv}],
            sagemaker_session=sess,
        )
        print(f"[launch] job={job} model_version={mv} image={est.training_image_uri()} spot={spot}")
        if args.dry_run:
            return 0
        est.fit(
            {"train": features, "val": features},
            job_name=job,
            wait=args.wait,
            logs="All" if args.wait else "None",
        )

    record = {
        "job_name": job,
        "model_version": mv,
        "image_uri": est.training_image_uri(),
        "instance_type": args.instance_type,
        "spot": spot,
        "framework_version": args.framework_version,
        "py_version": args.py_version,
        "hyperparameters": hps,
        "features_s3": features,
        "model_s3": f"s3://{args.bucket}/models/predictor/{job}/output/model.tar.gz",
        "copy_to": f"s3://{args.bucket}/models/predictor/{mv}/model.tar.gz",
        "launched_utc": ts,
    }
    out = REPO / "data/experiments" / mv
    out.mkdir(parents=True, exist_ok=True)
    (out / "sagemaker.json").write_text(json.dumps(record, indent=1))
    print(json.dumps(record, indent=1))
    return 0


def launch_task(args, ts: str, sha: str, sagemaker, boto3, pytorch_cls) -> int:
    """features / detector / signatures: same container, ``ml.sagemaker.tasks`` entry, explicit channels."""
    job = f"aquaagent-{args.task}-{args.dataset_version}-{ts}"
    run_prefix = f"sagemaker/runs/{job}"
    channels = dict(c.split("=", 1) for c in args.channel)
    hps = {
        "task": args.task,
        "dataset-version": args.dataset_version,
        "bucket": args.bucket,
        "run-prefix": run_prefix,
        "git-sha": sha,
        **dict(h.split("=", 1) for h in args.hp),
    }
    spot = not args.on_demand
    sess = sagemaker.Session(boto3.Session(region_name=args.region), default_bucket=args.bucket)
    with tempfile.TemporaryDirectory() as tmp:
        est = pytorch_cls(
            entry_point="sm_task.py",
            source_dir=str(stage_task_source(Path(tmp))),
            role=args.role_arn,
            framework_version=args.framework_version,
            py_version=args.py_version,
            instance_count=1,
            instance_type=args.instance_type,
            hyperparameters=hps,
            output_path=f"s3://{args.bucket}/sagemaker/jobs/",
            code_location=f"s3://{args.bucket}/sagemaker/code",
            use_spot_instances=spot,
            max_run=args.max_run_s,
            max_wait=2 * args.max_run_s if spot else None,
            volume_size=args.volume_gb,
            disable_profiler=True,
            debugger_hook_config=False,
            environment={"PYTHONUNBUFFERED": "1", "AQUA_GIT_SHA": sha},
            tags=[{"Key": "project", "Value": "aquaagent"}, {"Key": "task", "Value": args.task}],
            sagemaker_session=sess,
        )
        print(
            f"[launch] job={job} task={args.task} image={est.training_image_uri()} spot={spot} channels={channels}"
        )
        if args.dry_run:
            return 0
        est.fit(channels, job_name=job, wait=args.wait, logs="All" if args.wait else "None")
    record = {
        "job_name": job,
        "task": args.task,
        "image_uri": est.training_image_uri(),
        "instance_type": args.instance_type,
        "spot": spot,
        "hyperparameters": hps,
        "channels": channels,
        "run_prefix": f"s3://{args.bucket}/{run_prefix}/",
        "launched_utc": ts,
    }
    out = REPO / "data/experiments/sagemaker_runs"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{job}.json").write_text(json.dumps(record, indent=1))
    print(json.dumps(record, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
