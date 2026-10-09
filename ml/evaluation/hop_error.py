"""MAE by hop distance from nearest sensor (BACKBONE §9.1).

Hop = pipe hops from a node to the nearest *pressure sensor of the evaluated placement* (pump link
excluded; the tank's SCADA level is not counted as a sensor — same definition as
``node_states.hop_to_nearest_sensor``). On net_epa_tutorial_v1 the junction graph diameter is 3, so
hops > 3 cannot occur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch


def hops_to_placement(hop_matrix: torch.Tensor, p_mask: torch.Tensor) -> torch.Tensor:
    """[B, N] hop distance of every node to the nearest observed node (inf if none)."""
    d = torch.where(p_mask.unsqueeze(1), hop_matrix.unsqueeze(0), torch.tensor(float("inf")))
    return d.min(dim=2).values


def hop_error_table(
    abs_err: np.ndarray, hops: np.ndarray, groups: dict[str, np.ndarray] | None = None
) -> pd.DataFrame:
    """MAE/RMSE/n per hop (optionally per extra grouping column, e.g. model)."""
    df = pd.DataFrame({"abs_err_m": abs_err, "hop": hops.astype(int), **(groups or {})})
    keys = [*(groups or {}), "hop"]
    out = df.groupby(keys).abs_err_m.agg(
        mae_m="mean",
        rmse_m=lambda x: float(np.sqrt(np.mean(np.square(x)))),
        p95_m=lambda x: float(np.quantile(x, 0.95)),
        n="size",
    )
    return out.reset_index()
