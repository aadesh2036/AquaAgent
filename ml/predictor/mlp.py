"""MLP on flattened features; outputs scored-node pressures + F1/F2 flows (BACKBONE §7.7, §9.1–9.2).

Same call signature as ``GNNPredictor`` (``x``, ``edge_attr`` from ``ml.features.tensorize``), so the
training loop, evaluation and ``predict()`` treat both identically. The flat layout is the §7.7 MLP
layout generalised to any placement: per non-reservoir node [obs_mask, pressure, lag1, lag3], then
[flow, flow_mask] per flow sensor, then the 6 global context features. Unlike the GNN, the MLP sees
node *positions* (slot order), i.e. it is tied to this topology — that is the comparison point.
"""

from __future__ import annotations

import torch
from torch import nn

from ml.features.tensorize import GraphStatic

OBS_SLICE = slice(5, 9)  # obs_mask, observed_pressure_m_z, lag1, lag3
CTX_SLICE = slice(9, 15)  # tod_sin, tod_cos, tank_level_z, pump_on, pump_flow_z, reservoir_head_z


class MLPPredictor(nn.Module):
    """One network; leave-one-out over all 5 sensors comes from input masking (§7.9 leave_one_out[_flow])."""

    def __init__(self, gs: GraphStatic, hidden: int = 256, layers: int = 3, dropout: float = 0.0) -> None:
        super().__init__()
        self.register_buffer("nodes", torch.nonzero(~gs.node_static[:, 4].bool()).flatten(), persistent=False)
        n_in = len(self.nodes) * 4 + len(gs.flow_edge_fwd) * 2 + 6
        n_out = gs.n_nodes + len(gs.flow_edge_fwd)
        mods: list[nn.Module] = []
        d = n_in
        for _ in range(layers):
            mods += [nn.Linear(d, hidden), nn.GELU(), nn.Dropout(dropout)]
            d = hidden
        mods.append(nn.Linear(d, n_out))
        self.net = nn.Sequential(*mods)
        self.n_nodes = gs.n_nodes

    def forward(self, x: torch.Tensor, e: torch.Tensor, gs: GraphStatic) -> tuple[torch.Tensor, torch.Tensor]:
        b = x.shape[0]
        flat = torch.cat(
            [
                x[:, self.nodes, OBS_SLICE].reshape(b, -1),
                e[:, gs.flow_edge_fwd, 5:7].reshape(b, -1),
                x[:, 0, CTX_SLICE],
            ],
            dim=1,
        )
        out = self.net(flat)
        return out[:, : self.n_nodes], out[:, self.n_nodes :]
