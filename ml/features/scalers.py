"""Standardisation fitted on the TRAIN split, normal rows only (BACKBONE §7.7, BI-09).

One global scaler per physical quantity (not per node), so standardisation never encodes node identity.
A zero-variance quantity (e.g. reservoir head, roughness in ds1) gets std = 1.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _ms(x) -> dict:
    x = np.asarray([v for v in np.ravel(x) if v is not None], dtype=np.float64)
    x = x[np.isfinite(x)]
    sd = float(x.std())
    return {"mean": float(x.mean()), "std": sd if sd > 1e-9 else 1.0}


def fit_scalers(train: dict[str, np.ndarray], graph: dict) -> dict:
    ok = train["train_ok"]
    order = graph["node_order"]
    cand = [order.index(n) for n in graph["candidate_sensor_nodes"]]
    scored = [order.index(n) for n in graph["scored_nodes"]]
    elev = np.asarray(graph["elevation_m"], np.float64)
    head = train["p_true"][ok][:, scored].astype(np.float64) + elev[scored]
    pipes = [i for i, p in enumerate(graph["is_pump"]) if not p]
    return {
        "schema_version": "1.0",
        "fitted_on": "train split, normal rows only (§9.1)",
        "pressure_m": _ms(train["p_obs"][ok][:, cand]),
        "head_m": _ms(head),
        "flow_lps": _ms(train["q_obs"][ok]),
        "tank_level_m": _ms(train["ctx"][ok, 1]),
        "pump_flow_lps": _ms(train["ctx"][ok, 3]),
        "reservoir_head_m": _ms(train["ctx"][ok, 4]),
        "elevation_m": _ms(graph["elevation_m"]),
        "base_demand_lps": _ms(graph["base_demand_lps"]),
        "length_m": _ms([graph["length_m"][i] for i in pipes]),
        "diameter_m": _ms([graph["diameter_m"][i] for i in pipes]),
        "roughness_hw": _ms([graph["roughness_hw"][i] for i in pipes]),
    }


def save_scalers(scalers: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(scalers, indent=1, sort_keys=True))


def load_scalers(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())
