"""Merge shards, split by simulation, apply hard holdout, write manifest (BACKBONE §7.6, §8.5).

Reads `<raw>/shard=*/<table>/part-*.parquet`, writes
`<out>/split=<s>/<table>/part-000.parquet` (scenarios, node_states, link_states, tank_states,
pump_states, sensors, context), `<out>/graph/part-000.parquet`, `<out>/validation_log/part-000.parquet`
and `<out>/manifest.json`. `raw`/`out` may be local paths or s3:// URIs (same code path).

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

import pandas as pd
import wntr

from shared.contracts.models import (
    TABLE_COLUMNS,
    DatasetManifest,
    FaultType,
    Holdout,
    NetworkConfig,
)
from shared.units import m3s_to_lps
from sim.engine import network as net
from sim.generate import writer
from sim.generate.runner import load_config
from sim.scenarios.sampler import GENERATOR_VERSION, derive_seed, make_rng

SPLIT_TABLES = ("scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context")
SPLITS = ("train", "val", "test")
_LEAK_FAULTS = {FaultType.LEAK.value, FaultType.BURST.value}


def holdout_mask(scenarios_df: pd.DataFrame, holdout: list[str]) -> pd.Series:
    """True for sims with a LEAK/BURST fault at a held-out location, e.g. 'pipe:5' (§8.5, D9)."""
    loc = scenarios_df["location_kind"].astype(str) + ":" + scenarios_df["location_id"].astype(str)
    return scenarios_df["fault_type"].isin(_LEAK_FAULTS) & loc.isin(set(holdout))


def assign_splits(
    scenarios_df: pd.DataFrame, seed: int, holdout: list[str], fractions: dict[str, float] | None = None
) -> pd.Series:
    """70/15/15 by simulation_id, stratified by scenario_type; holdout locations -> test only.

    Returns a Series of 'train'/'val'/'test' aligned to `scenarios_df.index`. Holdout sims count
    toward their type's test quota first; remaining test/val sims are drawn at random.
    """
    fr = fractions or {"train": 0.70, "val": 0.15, "test": 0.15}
    held = holdout_mask(scenarios_df, holdout)
    out = pd.Series("train", index=scenarios_df.index, dtype=object)
    for stype, grp in scenarios_df.groupby("scenario_type", sort=True):
        grp = grp.sort_values("simulation_id")
        n = len(grp)
        n_test, n_val = round(fr["test"] * n), round(fr["val"] * n)
        forced = grp.index[held.loc[grp.index].to_numpy()]
        free = grp.index[~held.loc[grp.index].to_numpy()]
        order = make_rng(derive_seed(seed, f"split:{stype}")).permutation(len(free))
        free = free[order]
        need_test = max(0, n_test - len(forced))
        out.loc[forced] = "test"
        out.loc[free[:need_test]] = "test"
        out.loc[free[need_test : need_test + n_val]] = "val"
    return out


def graph_table(cfg: NetworkConfig) -> pd.DataFrame:
    """Static graph rows (§7.5 `graph`): public network facts only (no hidden/leak info)."""
    rows = []
    for n in cfg.nodes:
        feats = {
            "node_type": n.node_type.value,
            "elevation_m": n.elevation_m,
            "base_demand_lps": m3s_to_lps(n.base_demand_m3s) if n.base_demand_m3s is not None else 0.0,
            "zone_id": n.zone_id,
            "x": n.x,
            "y": n.y,
        }
        rows.append((cfg.network_id, "node", n.node_id, None, None, json.dumps(feats, sort_keys=True)))
    for k in cfg.links:
        feats = {
            "link_type": k.link_type.value,
            "length_m": k.length_m,
            "diameter_m": k.diameter_m,
            "roughness_hw": k.roughness_hw,
            "is_pump": k.link_type.value == "pump",
            "is_open": k.initial_status.value != "CLOSED",
            "zone_id": k.zone_id,
        }
        rows.append((cfg.network_id, "edge", k.link_id, k.start_node, k.end_node, json.dumps(feats, sort_keys=True)))
    return pd.DataFrame(rows, columns=list(TABLE_COLUMNS["graph"]))


def git_sha() -> str:
    if os.environ.get("GIT_SHA"):
        return os.environ["GIT_SHA"]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _read_all(raw_uri: str, table: str) -> pd.DataFrame:
    parts = writer.list_parts(raw_uri, f"shard=*/{table}/part-*.parquet")
    if not parts:
        raise FileNotFoundError(f"no shard files for table {table!r} under {raw_uri}")
    return writer.concat([writer.read_table(p) for p in parts])


def _sorted(df: pd.DataFrame, table: str) -> pd.DataFrame:
    keys = [c for c in ("simulation_id", "sim_time_s", "node_id", "link_id", "tank_id", "pump_id", "sensor_id", "check") if c in df.columns]
    return df.sort_values(keys, kind="stable").reset_index(drop=True)


def merge(config_path: str, raw_uri: str, out_uri: str) -> DatasetManifest:
    cfg = load_config(config_path)
    holdout = list(cfg["holdout_test_only"])
    version = cfg["dataset_version"]

    scen = _sorted(_read_all(raw_uri, "scenarios"), "scenarios")
    if scen["simulation_id"].duplicated().any():
        raise ValueError("duplicate simulation_id across shards")
    vlog = _sorted(_read_all(raw_uri, "validation_log"), "validation_log")
    n_requested = int(vlog["simulation_id"].nunique())

    split = assign_splits(scen, cfg["dataset_seed"], holdout, cfg.get("splits"))
    scen.insert(list(TABLE_COLUMNS["scenarios"]).index("split"), "split", split)
    sim_split = dict(zip(scen["simulation_id"], scen["split"], strict=True))

    files: dict[str, str] = {}
    for table in SPLIT_TABLES:
        df = scen if table == "scenarios" else _sorted(_read_all(raw_uri, table), table)
        df = df[list(TABLE_COLUMNS[table])]
        spl = df["simulation_id"].map(sim_split)
        for s in SPLITS:
            writer.write_table(
                df[spl == s].reset_index(drop=True), table, writer.join(out_uri, f"split={s}", table, "part-000.parquet")
            )
        files[table] = f"split=<train|val|test>/{table}/"
    graph = graph_table(net.network_config(cfg["network_id"]))
    writer.write_table(graph, "graph", writer.join(out_uri, "graph", "part-000.parquet"))
    files["graph"] = "graph/"
    writer.write_table(vlog, "validation_log", writer.join(out_uri, "validation_log", "part-000.parquet"))
    files["validation_log"] = "validation_log/"

    n_valid = len(scen)
    manifest = DatasetManifest(
        dataset_version=version,
        created_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_sha=git_sha(),
        generator_version=GENERATOR_VERSION,
        wntr_version=wntr.__version__,
        network_ids=[cfg["network_id"]],
        sensor_layout_ids=[cfg["sensor_layout_id"]],
        dataset_seed=cfg["dataset_seed"],
        n_requested=n_requested,
        n_valid=n_valid,
        n_failed=n_requested - n_valid,
        counts_by_split={s: int((scen["split"] == s).sum()) for s in SPLITS},
        counts_by_scenario_type={k: int(v) for k, v in scen["scenario_type"].value_counts().sort_index().items()},
        holdout=Holdout(fault_locations_test_only=holdout),
        timestep_s=cfg["timestep_s"],
        duration_s=cfg["duration_s"],
        files=files,
    )
    writer.write_text(manifest.model_dump_json(indent=2) + "\n", writer.join(out_uri, "manifest.json"))
    return manifest
