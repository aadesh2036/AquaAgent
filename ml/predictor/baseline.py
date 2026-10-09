"""Nearest-sensor + elevation-corrected baseline (BACKBONE §9.1 rung 1). No training.

Hydraulic head (pressure + elevation) varies smoothly over a pipe network, so the baseline copies the
head of the nearest *known-head* location (by pipe hops) and converts back to pressure at the target
elevation. Known-head locations = observed pressure sensors in the placement + the tank (its level is
SCADA context, §6.4). Ties at equal hop distance are averaged. The reservoir is excluded (the pump
sits between it and the network). Flow sensors are ignored.
"""

from __future__ import annotations

import numpy as np
import torch

from ml.features.tensorize import GraphStatic


def pipe_hop_matrix(graph: dict) -> np.ndarray:
    """All-pairs hop distance over pipes only (pump excluded); inf if unreachable."""
    n = len(graph["node_order"])
    adj = [[] for _ in range(n)]
    for s, e, pump in zip(graph["edge_start"], graph["edge_end"], graph["is_pump"], strict=True):
        if not pump:
            adj[s].append(e)
            adj[e].append(s)
    d = np.full((n, n), np.inf)
    for src in range(n):
        d[src, src] = 0
        frontier = [src]
        while frontier:
            nxt = []
            for u in frontier:
                for v in adj[u]:
                    if d[src, v] == np.inf:
                        d[src, v] = d[src, u] + 1
                        nxt.append(v)
            frontier = nxt
    return d


class NearestSensorBaseline:
    def __init__(self, gs: GraphStatic, graph: dict) -> None:
        self.gs = gs
        self.hops = torch.tensor(pipe_hop_matrix(graph), dtype=torch.float32)
        self.tank = gs.node_static[:, 3].bool()

    def predict_pressure(self, batch: dict[str, torch.Tensor], p_mask: torch.Tensor) -> torch.Tensor:
        elev = self.gs.elevation_m
        b, n = p_mask.shape
        head_src = torch.nan_to_num(batch["p_obs"], nan=0.0) + elev
        head_src = torch.where(self.tank.expand(b, n), batch["ctx"][:, 1:2] + elev, head_src)
        src = p_mask | self.tank.expand(b, n)
        d = torch.where(src.unsqueeze(1), self.hops.unsqueeze(0), torch.tensor(float("inf")))  # [B, tgt, src]
        dmin = d.min(dim=2, keepdim=True).values
        w = ((d == dmin) & torch.isfinite(d)).float()
        head = (w * head_src.unsqueeze(1)).sum(2) / w.sum(2).clamp_min(1.0)
        return head - elev
