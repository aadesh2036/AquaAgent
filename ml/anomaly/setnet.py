"""Topology-agnostic supervised anomaly detector over a SET of sensors (module 05, P-05-2).

Input  : for each available sensor, its last L residual z-scores (LOO residual / σ, BACKBONE §9.2) + sensor
         TYPE (pressure | flow, never identity) + per-step SCADA context (tod sin/cos, pump flow, tank level).
Model  : shared dilated temporal CNN per sensor → attention + max pooling over sensors → P(anomaly now).
         Per-sensor attention weights give ``driving_sensors``. Any number of sensors, any network.
Alarm  : P > τ for T consecutive 300-s steps → ANOMALY (latched), τ and T tuned on val (FAR ≤ 5 %/type).

Training uses labelled train-split simulations (anomalous = fault_start ≤ t < fault_end for LEAK/BURST);
the predictor that produces the residuals stays normal-only (§9.1).
"""

from __future__ import annotations

import math

import numpy as np
import torch
from torch import nn

N_CTX = 4  # tod_sin, tod_cos, pump_flow_z, tank_level_z
SENSOR_TYPES = ("pressure", "flow")


class SensorSetNet(nn.Module):
    def __init__(self, hidden: int = 32, history: int = 24, n_signal: int = 1) -> None:
        """n_signal = per-sensor signal channels: 1 = residual z; 2 = residual z + type-normalised raw reading."""
        super().__init__()
        self.history = history
        f_in = n_signal + len(SENSOR_TYPES) + N_CTX
        self.tcn = nn.Sequential(
            nn.Conv1d(f_in, hidden, 3, padding=2, dilation=1),
            nn.GELU(),
            nn.Conv1d(hidden, hidden, 3, padding=4, dilation=2),
            nn.GELU(),
            nn.Conv1d(hidden, hidden, 3, padding=8, dilation=4),
            nn.GELU(),
        )
        self.att = nn.Linear(2 * hidden, 1)
        self.head = nn.Sequential(nn.Linear(4 * hidden, hidden), nn.GELU(), nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor, sensor_mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """x [B, S, L, F]; sensor_mask [B, S] bool → (logit [B], attention [B, S])."""
        b, s, n_t, f = x.shape
        h = self.tcn(x.reshape(b * s, n_t, f).transpose(1, 2))[..., :n_t]  # causal crop
        emb = torch.cat([h[..., -1], h.mean(-1)], dim=1).view(b, s, -1)  # last step + history summary
        a = self.att(emb).squeeze(-1).masked_fill(~sensor_mask, float("-inf"))
        w = torch.softmax(a, dim=1)
        pooled = torch.cat(
            [
                (w.unsqueeze(-1) * emb).sum(1),
                emb.masked_fill(~sensor_mask.unsqueeze(-1), float("-inf")).max(1).values,
            ],
            dim=1,
        )
        return self.head(pooled).squeeze(-1), w


def build_inputs(z: np.ndarray, ctx: np.ndarray, sensor_types: list[str], history: int) -> np.ndarray:
    """Episode arrays → model inputs for EVERY step.

    z [E, T, S] z-scores; ctx [E, T, N_CTX]; returns [E, T, S, history, F] (zero-padded before t=0).
    """
    e, t, s = z.shape
    typ = np.zeros((s, len(SENSOR_TYPES)), np.float32)
    for i, st in enumerate(sensor_types):
        typ[i, SENSOR_TYPES.index(st)] = 1.0
    zp = np.concatenate([np.zeros((e, history - 1, s), np.float32), z.astype(np.float32)], axis=1)
    cp = np.concatenate(
        [np.zeros((e, history - 1, ctx.shape[-1]), np.float32), ctx.astype(np.float32)], axis=1
    )
    idx = np.arange(t)[:, None] + np.arange(history)[None, :]  # [T, H]
    zw = zp[:, idx]  # [E, T, H, S]
    cw = cp[:, idx]  # [E, T, H, C]
    zw = np.transpose(zw, (0, 1, 3, 2))[..., None]  # [E, T, S, H, 1]
    cw = np.broadcast_to(cw[:, :, None], (e, t, s, history, cw.shape[-1]))
    tw = np.broadcast_to(typ[None, None, :, None, :], (e, t, s, history, typ.shape[1]))
    return np.concatenate([zw, tw, cw], axis=-1)


def context_features(ctx: np.ndarray, scalers: dict) -> np.ndarray:
    """[..., 5] raw ctx (tod, tank, pump_status, pump_flow, res_head) → [..., N_CTX]."""
    ang = 2 * math.pi * ctx[..., 0] / 86400.0
    pf = (ctx[..., 3] - scalers["pump_flow_lps"]["mean"]) / scalers["pump_flow_lps"]["std"]
    tl = (ctx[..., 1] - scalers["tank_level_m"]["mean"]) / scalers["tank_level_m"]["std"]
    return np.stack([np.sin(ang), np.cos(ang), pf, tl], axis=-1).astype(np.float32)
