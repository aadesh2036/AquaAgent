"""Arrays + sensor placement → frozen v1 node/edge feature tensors (BACKBONE §7.7).

The single feature path shared by training, evaluation and online inference (``predict.py``), so
offline == online by construction. torch + numpy only (runs unchanged in the SageMaker container).

Firewall: every observation feature is multiplied by its placement mask, so a node/link that is not
instrumented in the sampled placement contributes exactly 0 regardless of what the array holds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch

N_NODE_FEATURES = 15  # len(NODE_FEATURES_V1)
N_EDGE_FEATURES = 7  # len(EDGE_FEATURES_V1)


def _z(x, s: dict):
    return (x - s["mean"]) / s["std"]


@dataclass
class GraphStatic:
    node_order: list[str]
    n_nodes: int
    node_static: torch.Tensor  # [n, 5] elevation_z, base_demand_z, is_junction, is_tank, is_reservoir
    elevation_m: torch.Tensor  # [n]
    edge_index: torch.Tensor  # [2, 2E] directed: forward links then reversed links
    edge_static: torch.Tensor  # [2E, 5] length_z, diameter_z, roughness_z, is_pump, is_open
    flow_edge_fwd: torch.Tensor  # [n_flow] forward edge index of each flow sensor link (F1, F2)
    flow_edge_rev: torch.Tensor  # [n_flow]
    scored: torch.Tensor  # [n] bool, y_mask (§7.7)
    candidate: torch.Tensor  # [n] bool, junctions that may carry a pressure sensor
    default_sensor_idx: list[int]  # node index of S1..S3
    scalers: dict

    @classmethod
    def from_json(cls, graph: dict, scalers: dict) -> GraphStatic:
        order = graph["node_order"]
        types = graph["node_type"]
        elev = np.asarray(graph["elevation_m"], np.float64)
        node_static = np.stack(
            [
                _z(elev, scalers["elevation_m"]),
                _z(np.asarray(graph["base_demand_lps"]), scalers["base_demand_lps"]),
                [t == "junction" for t in types],
                [t == "tank" for t in types],
                [t == "reservoir" for t in types],
            ],
            axis=1,
        )
        s, e = graph["edge_start"], graph["edge_end"]
        n_links = len(s)

        def col(name, key):
            return [0.0 if v is None else _z(float(v), scalers[key]) for v in graph[name]]

        est = np.stack(
            [
                col("length_m", "length_m"),
                col("diameter_m", "diameter_m"),
                col("roughness_hw", "roughness_hw"),
                np.asarray(graph["is_pump"], float),
                np.asarray(graph["is_open"], float),
            ],
            axis=1,
        )
        links = graph["link_order"]
        fwd = [links.index(graph["flow_sensors"][f]) for f in sorted(graph["flow_sensors"])]
        f32 = torch.float32
        return cls(
            node_order=order,
            n_nodes=len(order),
            node_static=torch.tensor(node_static, dtype=f32),
            elevation_m=torch.tensor(elev, dtype=f32),
            edge_index=torch.tensor([s + e, e + s], dtype=torch.long),
            edge_static=torch.tensor(np.concatenate([est, est]), dtype=f32),
            flow_edge_fwd=torch.tensor(fwd, dtype=torch.long),
            flow_edge_rev=torch.tensor([i + n_links for i in fwd], dtype=torch.long),
            scored=torch.tensor([n in graph["scored_nodes"] for n in order]),
            candidate=torch.tensor([n in graph["candidate_sensor_nodes"] for n in order]),
            default_sensor_idx=[
                order.index(graph["pressure_sensors"][k]) for k in sorted(graph["pressure_sensors"])
            ],
            scalers=scalers,
        )

    # --- target scaling: models predict standardised hydraulic HEAD; pressure = head − elevation
    def pressure_to_head_z(self, p: torch.Tensor) -> torch.Tensor:
        return _z(p + self.elevation_m, self.scalers["head_m"])

    def head_z_to_pressure(self, hz: torch.Tensor) -> torch.Tensor:
        s = self.scalers["head_m"]
        return hz * s["std"] + s["mean"] - self.elevation_m

    def flow_to_z(self, q: torch.Tensor) -> torch.Tensor:
        return _z(q, self.scalers["flow_lps"])

    def z_to_flow(self, qz: torch.Tensor) -> torch.Tensor:
        s = self.scalers["flow_lps"]
        return qz * s["std"] + s["mean"]


def tensorize(
    batch: dict[str, torch.Tensor], p_mask: torch.Tensor, q_mask: torch.Tensor, gs: GraphStatic
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build ``x [bsz, n, 15]`` and ``edge_attr [bsz, 2E, 7]`` in NODE/EDGE_FEATURES_V1 order.

    batch: ``p_obs``, ``p_obs_lag1``, ``p_obs_lag3`` [bsz, n]; ``q_obs`` [bsz, F]; ``ctx`` [bsz, 5]
    (time_of_day_s, tank_level_m, pump_status, pump_flow_lps, reservoir_head_m).
    p_mask [bsz, n] bool (pressure observed at node), q_mask [bsz, F] bool (flow sensor present).
    """
    sc = gs.scalers
    bsz, n = p_mask.shape
    m = p_mask.float()

    def obs(key):  # standardised reading where observed, exactly 0 elsewhere (NaN-safe)
        v = torch.nan_to_num(batch[key], nan=0.0)
        return torch.where(p_mask, _z(v, sc["pressure_m"]), torch.zeros_like(v))

    ctx = batch["ctx"]
    ang = 2.0 * math.pi * ctx[:, 0] / 86400.0
    glob = torch.stack(
        [
            torch.sin(ang),
            torch.cos(ang),
            _z(ctx[:, 1], sc["tank_level_m"]),
            ctx[:, 2],
            _z(ctx[:, 3], sc["pump_flow_lps"]),
            _z(ctx[:, 4], sc["reservoir_head_m"]),
        ],
        dim=1,
    )  # [bsz, 6]
    x = torch.cat(
        [
            gs.node_static.expand(bsz, n, 5),
            m.unsqueeze(-1),
            obs("p_obs").unsqueeze(-1),
            obs("p_obs_lag1").unsqueeze(-1),
            obs("p_obs_lag3").unsqueeze(-1),
            glob.unsqueeze(1).expand(bsz, n, 6),
        ],
        dim=-1,
    )

    e2 = gs.edge_static.shape[0]
    qz = torch.where(
        q_mask,
        _z(torch.nan_to_num(batch["q_obs"], nan=0.0), sc["flow_lps"]),
        torch.zeros_like(batch["q_obs"]),
    )
    flow = torch.zeros(bsz, e2)
    fmask = torch.zeros(bsz, e2)
    # sign convention: forward edge carries +q (link start→end), reverse edge −q
    flow[:, gs.flow_edge_fwd] = qz
    flow[:, gs.flow_edge_rev] = -qz
    fmask[:, gs.flow_edge_fwd] = q_mask.float()
    fmask[:, gs.flow_edge_rev] = q_mask.float()
    e = torch.cat([gs.edge_static.expand(bsz, e2, 5), flow.unsqueeze(-1), fmask.unsqueeze(-1)], dim=-1)
    return x, e
