"""Junction leaks and pipe leaks via split_pipe (BACKBONE §6.3, §5.1 `LK_<pipe>`, `<pipe>_B`).

Implementation: docs/modules/01_SIMULATION_ENGINE.md
"""

from __future__ import annotations


def add_junction_leak(
    wn, node_id: str, area_m2: float, start_s: int, end_s: int | None, discharge_coeff: float = 0.75
) -> None:
    """WNTR `add_leak` on a junction (§6.3)."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")


def add_pipe_leak(
    wn,
    pipe_id: str,
    position: float,
    area_m2: float,
    start_s: int,
    end_s: int | None,
    discharge_coeff: float = 0.75,
) -> str:
    """`wntr.morph.split_pipe` at `position` creating `<pipe>_B` + leak node `LK_<pipe>`; returns leak node id."""
    raise NotImplementedError("NOT IMPLEMENTED — see docs/modules/01_SIMULATION_ENGINE.md")
