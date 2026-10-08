"""MLP on flattened features; outputs scored-node pressures + F1/F2 flows (BACKBONE §7.7, §9.1–9.2).

Implementation: docs/modules/04_ML_PREDICTOR.md
"""

from __future__ import annotations


class MLPPredictor:  # torch.nn.Module in implementation
    """One network; leave-one-out over all 5 sensors comes from input masking (§7.9 leave_one_out[_flow])."""

    def __init__(self, n_inputs: int, n_outputs: int, hidden: int = 128) -> None:
        raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/04_ML_PREDICTOR.md")
