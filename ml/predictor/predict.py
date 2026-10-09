"""Predict API: SensorWindow → PredictorResponse (BACKBONE §7.8, §7.9). Used by 06 inference.py and 08 local client.

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import torch

from ml.features.tensorize import GraphStatic, tensorize
from shared.contracts.models import (
    DATASET_TIMESTEP_S,
    LooEntry,
    LooFlowEntry,
    PredictorResponse,
    Reconstruction,
    SensorWindow,
)
from shared.units import time_of_day_s


@dataclass
class Artifact:
    model: torch.nn.Module
    gs: GraphStatic
    graph: dict
    meta: dict


def resolve_artifact(uri: str, cache_dir: str | None = None) -> Path:
    """``AQUA_PREDICTOR_ARTIFACT`` (§10.4) → local extracted dir. Accepts a dir, a model.tar.gz path or an
    ``s3://…/model.tar.gz`` URI (downloaded with the task role; scalers come from inside the tarball, BI-09)."""
    import tarfile
    import tempfile

    if Path(uri).is_dir():
        return Path(uri)
    cache = Path(cache_dir or tempfile.mkdtemp(prefix="aqua_predictor_"))
    cache.mkdir(parents=True, exist_ok=True)
    tgz = Path(uri)
    if uri.startswith("s3://"):
        import boto3

        bucket, key = uri[5:].split("/", 1)
        tgz = cache / "model.tar.gz"
        boto3.client("s3").download_file(bucket, key, str(tgz))
    out = cache / "model"
    out.mkdir(exist_ok=True)
    with tarfile.open(tgz, "r:gz") as tar:
        tar.extractall(out, filter="data")
    return out


def load_artifact(model_dir: str) -> Artifact:
    """Load model.pt + scalers.json + meta.json from an extracted model.tar.gz (BI-09).

    ``model_dir`` may also be a model.tar.gz path or an s3:// URI (see ``resolve_artifact``).
    """
    from ml.predictor.train import build_model

    d = resolve_artifact(str(model_dir))
    meta = json.loads((d / "meta.json").read_text())
    graph = json.loads((d / "graph.json").read_text())
    gs = GraphStatic.from_json(graph, json.loads((d / "scalers.json").read_text()))
    model = build_model(meta["model_config"], gs)
    model.load_state_dict(torch.load(d / "model.pt", map_location="cpu", weights_only=True))
    model.eval()
    return Artifact(model=model, gs=gs, graph=graph, meta=meta)


LOO_ROWS: tuple[str | None, ...] = (None, "S1", "S2", "S3", "F1", "F2")


def window_to_arrays(
    window: SensorWindow, gs: GraphStatic, graph: dict
) -> tuple[dict, torch.Tensor, torch.Tensor]:
    """Online twin of ``ml.features.builder``: last window step → arrays + base masks.

    Missing readings (``null``) are treated as uninstrumented (mask 0), never as 0. Lags (300 s / 900 s)
    come from earlier window steps; when absent the current value is used (same rule as offline).
    """
    if not isinstance(window, SensorWindow):
        raise TypeError("predict() accepts only a SensorWindow (BACKBONE §11)")
    if window.network_id != graph["network_id"] or window.sensor_layout_id != graph["sensor_layout_id"]:
        raise ValueError("SensorWindow network/layout does not match the artifact")
    steps = {s.sim_time_s: s for s in window.window}
    cur = window.window[-1]
    n = gs.n_nodes
    p_sensors = graph["pressure_sensors"]
    f_ids = sorted(graph["flow_sensors"])

    def pressures(step) -> list[float]:
        row = [float("nan")] * n
        for sid, node in p_sensors.items():
            v = step.pressure_m.get(sid) if step is not None else None
            row[gs.node_order.index(node)] = float("nan") if v is None else float(v)
        return row

    now = pressures(cur)
    lags = []
    for k in (1, 3):
        prev = pressures(steps.get(cur.sim_time_s - k * DATASET_TIMESTEP_S))
        lags.append([pv if pv == pv else nv for pv, nv in zip(prev, now, strict=True)])
    c = cur.context
    sc = gs.scalers

    def ctx_or_mean(v, key):
        return sc[key]["mean"] if v is None else float(v)

    arrays = {
        "p_obs": torch.tensor([now], dtype=torch.float32),
        "p_obs_lag1": torch.tensor([lags[0]], dtype=torch.float32),
        "p_obs_lag3": torch.tensor([lags[1]], dtype=torch.float32),
        "q_obs": torch.tensor(
            [[float("nan") if cur.flow_lps.get(f) is None else cur.flow_lps[f] for f in f_ids]]
        ),
        "ctx": torch.tensor(
            [
                [
                    float(time_of_day_s(c.time_of_day_s)),
                    ctx_or_mean(c.tank_level_m, "tank_level_m"),
                    1.0 if c.pump_status is None else float(c.pump_status),
                    ctx_or_mean(c.pump_flow_lps, "pump_flow_lps"),
                    ctx_or_mean(c.reservoir_head_m, "reservoir_head_m"),
                ]
            ],
            dtype=torch.float32,
        ),
    }
    p_mask = ~torch.isnan(arrays["p_obs"])
    q_mask = ~torch.isnan(arrays["q_obs"])
    return arrays, p_mask, q_mask


def window_to_features(window: SensorWindow, artifact: Artifact, mask_sensor: str | None = None):
    """Online features for the last window step, optionally with one sensor hidden (§7.7)."""
    arrays, pm, qm = window_to_arrays(window, artifact.gs, artifact.graph)
    pm, qm = pm.clone(), qm.clone()
    _apply_drop(pm, qm, mask_sensor, artifact.gs)
    return tensorize(arrays, pm, qm, artifact.gs)


def _apply_drop(pm: torch.Tensor, qm: torch.Tensor, sid: str | None, gs: GraphStatic) -> None:
    if sid is None:
        return
    if sid.startswith("S"):
        pm[..., gs.default_sensor_idx[int(sid[1:]) - 1]] = False
    else:
        qm[..., int(sid[1:]) - 1] = False


@torch.no_grad()
def predict(window: SensorWindow, artifact: Artifact, model_version: str) -> PredictorResponse:
    """reconstruct + leave_one_out (S1–S3) + leave_one_out_flow (F1–F2) from one 6-row batch (§7.9)."""
    t0 = time.perf_counter()
    gs, graph = artifact.gs, artifact.graph
    arrays, pm1, qm1 = window_to_arrays(window, gs, graph)
    rows = len(LOO_ROWS)
    batch = {k: v.expand(rows, *v.shape[1:]).clone() for k, v in arrays.items()}
    pm, qm = pm1.expand(rows, -1).clone(), qm1.expand(rows, -1).clone()
    for i, sid in enumerate(LOO_ROWS):
        _apply_drop(pm[i], qm[i], sid, gs)
    x, e = tensorize(batch, pm, qm, gs)
    head_z, flow_z = artifact.model(x, e, gs)
    pres = gs.head_z_to_pressure(head_z)
    flow = gs.z_to_flow(flow_z)

    obs_p = arrays["p_obs"][0]
    recon = {}
    for j, node in enumerate(gs.node_order):
        if not bool(gs.scored[j]):
            continue
        val = obs_p[j] if bool(pm1[0, j]) else pres[0, j]  # observed sensors report their reading
        recon[node] = round(float(val), 4)
    loo = {}
    for i, sid in enumerate(("S1", "S2", "S3")):
        j = gs.default_sensor_idx[i]
        loo[sid] = LooEntry(
            predicted_m=round(float(pres[1 + i, j]), 4),
            observed_m=None if not bool(pm1[0, j]) else round(float(obs_p[j]), 4),
        )
    loo_f = {}
    for f, fid in enumerate(sorted(graph["flow_sensors"])):
        loo_f[fid] = LooFlowEntry(
            predicted_lps=round(float(flow[4 + f, f]), 4),
            observed_lps=None if not bool(qm1[0, f]) else round(float(arrays["q_obs"][0, f]), 4),
        )
    return PredictorResponse(
        model_version=model_version,
        sim_time_s=window.window[-1].sim_time_s,
        reconstruct=Reconstruction(pressure_m=recon),
        leave_one_out=loo,
        leave_one_out_flow=loo_f,
        latency_ms=round((time.perf_counter() - t0) * 1000, 3),
    )
