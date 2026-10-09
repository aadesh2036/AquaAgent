"""Build predictor feature arrays from processed ds1 (BACKBONE §7.5, §7.7, §9.1, §11).

Offline output per split = one ``<split>.npz`` of dense per-timestep arrays plus a shared
``graph.json`` and train-only ``scalers.json``. Node/edge feature tensors (§7.7, order frozen v1)
are assembled at batch time by ``ml.features.tensorize`` from these arrays, so the training loop,
the evaluation sweep and the online ``SensorWindow`` path all run the *same* maths.

Firewall (§11) — what each array is allowed to be used for:

* **Inputs** — ``sensors.measured_value`` (S1–S3 pressure at nodes 2/4/6, F1/F2 flow), ``context``
  (tank level, pump status/flow, reservoir head, time of day) and static ``graph`` attributes.
* **Targets / evaluation only** — ``node_states.pressure_m`` (all nodes) and ``sensors.true_value``
  of F1/F2. Read in ``_read_targets`` only.
* **Virtual sensors (placement experiment, docs/modules/04 §13 proposal P-04-1)** — for nodes that
  are *not* in the default layout, ``p_obs`` holds ``pressure_m + N(0, pressure_sigma_m)`` drawn
  with the dataset's own noise model. It is only ever fed to a model where the sampled sensor
  placement says that node is instrumented; ``tensorize`` zeroes it everywhere else.
* **Selection metadata** — ``train_ok`` (normal state, §9.1), ``post_fault``, ``scenario_code``
  choose rows; they are never model inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from shared.contracts.models import (
    EDGE_FEATURES_V1,
    FLOW_SENSORS,
    FORBIDDEN_INPUT_COLUMNS,
    NODE_FEATURES_V1,
    PREDICTOR_TRAIN_SCENARIOS,
    PRESSURE_SENSORS,
    ScenarioType,
)

SPLITS = ("train", "val", "test")
LAG_STEPS = (1, 3)  # 300 s and 900 s at the single 300-s cadence (§5.3)
SCENARIO_TYPES: tuple[str, ...] = tuple(s.value for s in ScenarioType)

# Columns the INPUT readers are allowed to touch (asserted by ml/tests/test_leakage.py).
SENSOR_INPUT_COLUMNS = ("simulation_id", "sim_time_s", "sensor_id", "source_id", "measured_value")
CONTEXT_INPUT_COLUMNS = (
    "simulation_id",
    "sim_time_s",
    "time_of_day_s",
    "tank_level_m",
    "pump_status",
    "pump_flow_lps",
    "reservoir_head_m",
)


def _hash_seed(*parts: object) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "little")


# ---------------------------------------------------------------------------- graph


def build_graph(processed_dir: str | Path) -> dict:
    """Static graph description from the ``graph`` table + default sensor layout (§6.4)."""
    g = pd.read_parquet(Path(processed_dir) / "graph")
    nodes = g[g.element_kind == "node"].copy()
    nodes["k"] = nodes.element_id.astype(int)
    nodes = nodes.sort_values("k")
    node_order = nodes.element_id.tolist()
    nf = [json.loads(s) for s in nodes.features_json]

    edges = g[g.element_kind == "edge"].copy()
    edges["k"] = edges.element_id.astype(int)
    edges = edges.sort_values("k")
    ef = [json.loads(s) for s in edges.features_json]

    layout = json.loads(
        (Path(__file__).resolve().parents[2] / "config/sensors/sensors_default_v1.json").read_text()
    )
    p_sensors = {d["sensor_id"]: d["node_id"] for d in layout["pressure"]}
    f_sensors = {d["sensor_id"]: d["link_id"] for d in layout["flow"]}
    assert tuple(p_sensors) == PRESSURE_SENSORS and tuple(f_sensors) == FLOW_SENSORS

    return {
        "network_id": str(g.network_id.iloc[0]),
        "sensor_layout_id": layout["sensor_layout_id"],
        "node_order": node_order,
        "node_type": [f["node_type"] for f in nf],
        "elevation_m": [float(f["elevation_m"]) for f in nf],
        "base_demand_lps": [float(f["base_demand_lps"]) for f in nf],
        "link_order": edges.element_id.tolist(),
        "edge_start": [node_order.index(s) for s in edges.start_node],
        "edge_end": [node_order.index(s) for s in edges.end_node],
        "length_m": [f["length_m"] for f in ef],
        "diameter_m": [f["diameter_m"] for f in ef],
        "roughness_hw": [f["roughness_hw"] for f in ef],
        "is_pump": [bool(f["is_pump"]) for f in ef],
        "is_open": [bool(f["is_open"]) for f in ef],
        "pressure_sensors": p_sensors,  # S1→"2", …
        "flow_sensors": f_sensors,  # F1→"3", …
        # junctions that may carry a (real or virtual) pressure sensor in the placement experiment
        "candidate_sensor_nodes": [
            n for n, t in zip(node_order, (f["node_type"] for f in nf), strict=True) if t == "junction"
        ],
        # scored = every non-reservoir node (§7.7 y_mask); tank pressure == context tank level
        "scored_nodes": [n for n, f in zip(node_order, nf, strict=True) if f["node_type"] != "reservoir"],
        "node_features": list(NODE_FEATURES_V1),
        "edge_features": list(EDGE_FEATURES_V1),
    }


# ---------------------------------------------------------------------------- readers


def _read_inputs(split_dir: Path, graph: dict) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Model-visible data only: sensors.measured_value + context (§11)."""
    sens = pd.read_parquet(split_dir / "sensors", columns=list(SENSOR_INPUT_COLUMNS))
    ctx = pd.read_parquet(split_dir / "context", columns=list(CONTEXT_INPUT_COLUMNS))
    ctx = ctx.sort_values(["simulation_id", "sim_time_s"], kind="stable").reset_index(drop=True)
    wide = sens.pivot_table(
        index=["simulation_id", "sim_time_s"], columns="sensor_id", values="measured_value", dropna=False
    )
    wide = wide.reindex(pd.MultiIndex.from_frame(ctx[["simulation_id", "sim_time_s"]]))
    p_sensor = wide[list(PRESSURE_SENSORS)].to_numpy(np.float64)
    q_sensor = wide[list(FLOW_SENSORS)].to_numpy(np.float64)
    return ctx, p_sensor, q_sensor


def _read_targets(split_dir: Path, graph: dict, keys: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Ground truth for targets/evaluation ONLY: node pressures and true F1/F2 flows."""
    ns = pd.read_parquet(
        split_dir / "node_states", columns=["simulation_id", "sim_time_s", "node_id", "pressure_m"]
    )
    pw = ns.pivot_table(index=["simulation_id", "sim_time_s"], columns="node_id", values="pressure_m")
    pw = pw.reindex(pd.MultiIndex.from_frame(keys))[graph["node_order"]]
    se = pd.read_parquet(
        split_dir / "sensors", columns=["simulation_id", "sim_time_s", "sensor_id", "true_value"]
    )
    qw = se.pivot_table(index=["simulation_id", "sim_time_s"], columns="sensor_id", values="true_value")
    qw = qw.reindex(pd.MultiIndex.from_frame(keys))[list(FLOW_SENSORS)]
    return pw.to_numpy(np.float64), qw.to_numpy(np.float64)


def _read_selection(split_dir: Path) -> pd.DataFrame:
    """Per-sim labels used to SELECT rows (normal-only training, eval slices). Never inputs."""
    sc = pd.read_parquet(
        split_dir / "scenarios", columns=["simulation_id", "scenario_type", "fault_start_s", "spec_json"]
    )
    sc["pressure_sigma_m"] = [json.loads(s)["noise"]["pressure_sigma_m"] for s in sc.spec_json]
    return sc.drop(columns="spec_json").set_index("simulation_id")


def _lag(arr: np.ndarray, sim_codes: np.ndarray, k: int) -> np.ndarray:
    """Value k steps earlier in the same simulation; persistence (current value) when unavailable."""
    out = arr.copy()
    same = np.zeros(len(arr), bool)
    same[k:] = sim_codes[k:] == sim_codes[:-k]
    out[k:][same[k:]] = arr[:-k][same[k:]]
    return out


# ---------------------------------------------------------------------------- build


def build_split(
    processed_dir: str | Path, split: str, graph: dict, dataset_seed: int
) -> dict[str, np.ndarray]:
    split_dir = Path(processed_dir) / f"split={split}"
    ctx, p_sensor, q_sensor = _read_inputs(split_dir, graph)
    keys = ctx[["simulation_id", "sim_time_s"]]
    p_true, q_true = _read_targets(split_dir, graph, keys)
    sel = _read_selection(split_dir)

    sim_ids = keys.simulation_id.to_numpy()
    uniq, sim_code = np.unique(sim_ids, return_inverse=True)
    t = keys.sim_time_s.to_numpy(np.int64)
    n_rows, n_nodes = p_true.shape
    node_order = graph["node_order"]

    # Observation layer per node: real sensors use recorded measured_value; other junctions get a
    # virtual reading with the dataset noise model (placement experiment only; masked unless placed).
    rng = np.random.Generator(np.random.PCG64(_hash_seed(dataset_seed, "virtual_sensors", split)))
    sigma = sel.loc[uniq, "pressure_sigma_m"].to_numpy()[sim_code]
    p_obs = np.full((n_rows, n_nodes), np.nan)
    for j, n in enumerate(node_order):
        if n in graph["candidate_sensor_nodes"]:
            p_obs[:, j] = p_true[:, j] + rng.normal(0.0, 1.0, n_rows) * sigma
    for k, sid in enumerate(PRESSURE_SENSORS):
        p_obs[:, node_order.index(graph["pressure_sensors"][sid])] = p_sensor[:, k]

    stype = sel.loc[uniq, "scenario_type"].to_numpy()[sim_code]
    fstart = sel.loc[uniq, "fault_start_s"].to_numpy(np.float64)[sim_code]
    operational = np.isin(stype, [s.value for s in PREDICTOR_TRAIN_SCENARIOS])
    pre_fault = np.isnan(fstart) | (t < fstart)
    train_ok = operational | pre_fault
    post_fault = ~operational & ~pre_fault

    tod = ctx.time_of_day_s.to_numpy(np.float64)
    out = {
        "sim_code": sim_code.astype(np.int32),
        "sim_ids": uniq.astype(str),
        "sim_time_s": t.astype(np.int32),
        "p_obs": p_obs.astype(np.float32),
        "p_obs_lag1": _lag(p_obs, sim_code, LAG_STEPS[0]).astype(np.float32),
        "p_obs_lag3": _lag(p_obs, sim_code, LAG_STEPS[1]).astype(np.float32),
        "q_obs": q_sensor.astype(np.float32),
        "ctx": np.stack(
            [
                tod,
                ctx.tank_level_m.to_numpy(np.float64),
                ctx.pump_status.to_numpy(np.float64),
                ctx.pump_flow_lps.to_numpy(np.float64),
                ctx.reservoir_head_m.to_numpy(np.float64),
            ],
            axis=1,
        ).astype(np.float32),
        "p_true": p_true.astype(np.float32),
        "q_true": q_true.astype(np.float32),
        "train_ok": train_ok,
        "post_fault": post_fault,
        "scenario_code": np.array([SCENARIO_TYPES.index(s) for s in stype], np.int8),
    }
    assert not np.isnan(out["p_true"]).any() and not np.isnan(out["ctx"]).any()
    return out


def main(argv: list[str] | None = None) -> int:
    from ml.features.scalers import fit_scalers, save_scalers

    p = argparse.ArgumentParser(description="Build predictor features (module 04 step 1)")
    p.add_argument("--processed", default="data/processed/ds1")
    p.add_argument("--out", default="data/features/ds1")
    args = p.parse_args(argv)

    manifest = json.loads((Path(args.processed) / "manifest.json").read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    graph = build_graph(args.processed)
    graph["dataset_version"] = manifest["dataset_version"]
    graph["dataset_git_sha"] = manifest["git_sha"]
    (out / "graph.json").write_text(json.dumps(graph, indent=1))

    arrays = {}
    for split in SPLITS:
        arrays[split] = build_split(args.processed, split, graph, manifest["dataset_seed"])
        np.savez_compressed(out / f"{split}.npz", **arrays[split])
        a = arrays[split]
        print(
            f"{split}: rows={len(a['sim_code'])} sims={len(a['sim_ids'])} train_ok={int(a['train_ok'].sum())}"
        )
    save_scalers(fit_scalers(arrays["train"], graph), out / "scalers.json")
    print(f"wrote {out}/{{train,val,test}}.npz, graph.json, scalers.json")
    return 0


assert not set(SENSOR_INPUT_COLUMNS + CONTEXT_INPUT_COLUMNS) & FORBIDDEN_INPUT_COLUMNS

if __name__ == "__main__":
    raise SystemExit(main())
