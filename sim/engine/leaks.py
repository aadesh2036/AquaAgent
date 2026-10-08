"""Junction leaks and pipe leaks on pre-split pipes (BACKBONE §6.3, §5.1 `LK_<pipe>`, `<pipe>_B`).

Pipes are pre-split by `network.build_network`, so a pipe leak is a WNTR leak on the existing
zero-demand junction `LK_<pipe>`; topology never changes mid-run.

Stepwise sessions toggle leaks at a pause with `set_leak_now` / `clear_leak_now`, which set
WNTR's leak attributes directly (no time controls). A new `WNTRSimulator(wn)` run on the same
model honours these attribute changes (verified in tests against a scheduled-leak full run).
"""

from __future__ import annotations

from sim.engine.network import JUNCTIONS, LEAK_PIPES

MAX_LEAK_AREA_M2 = 5e-3
DEFAULT_DISCHARGE_COEFF = 0.75


def _check_area(area_m2: float) -> None:
    if not (0.0 < area_m2 <= MAX_LEAK_AREA_M2):
        raise ValueError(f"leak area must be in (0, {MAX_LEAK_AREA_M2}] m2, got {area_m2}")


def _check_junction(node_id: str) -> None:
    if node_id not in JUNCTIONS and not (node_id.startswith("LK_") and node_id[3:] in LEAK_PIPES):
        raise ValueError(f"leaks allowed only on junctions 2-7 or LK_<pipe> nodes, got {node_id!r}")


def add_junction_leak(
    wn,
    node_id: str,
    area_m2: float,
    start_s: int,
    end_s: int | None = None,
    discharge_coeff: float = DEFAULT_DISCHARGE_COEFF,
) -> None:
    """Scheduled WNTR `add_leak` on a junction 2-7 (§6.3)."""
    if node_id not in JUNCTIONS:
        raise ValueError(f"junction leaks allowed only on junctions 2-7, got {node_id!r}")
    _check_area(area_m2)
    wn.get_node(node_id).add_leak(
        wn, area=area_m2, discharge_coeff=discharge_coeff, start_time=start_s, end_time=end_s
    )


def add_pipe_leak(
    wn,
    pipe_id: str,
    area_m2: float,
    start_s: int,
    end_s: int | None = None,
    discharge_coeff: float = DEFAULT_DISCHARGE_COEFF,
) -> str:
    """Scheduled leak on the pre-split leak node `LK_<pipe_id>`; returns that node id."""
    if pipe_id not in LEAK_PIPES:
        raise ValueError(f"unknown pipe {pipe_id!r}")
    lk = f"LK_{pipe_id}"
    if lk not in wn.node_name_list:
        raise ValueError(f"{lk} missing: network must be built pre-split")
    _check_area(area_m2)
    wn.get_node(lk).add_leak(
        wn, area=area_m2, discharge_coeff=discharge_coeff, start_time=start_s, end_time=end_s
    )
    return lk


def set_leak_now(wn, node_id: str, area_m2: float, discharge_coeff: float = DEFAULT_DISCHARGE_COEFF) -> None:
    """Activate a leak immediately (no time controls) for stepwise sessions."""
    _check_junction(node_id)
    _check_area(area_m2)
    node = wn.get_node(node_id)
    node.add_leak(wn, area=area_m2, discharge_coeff=discharge_coeff)  # no start/end -> no controls
    node._leak_status = True  # no public setter in WNTR 1.5


def clear_leak_now(wn, node_id: str) -> None:
    """Deactivate a leak immediately (leak definition retained, status off)."""
    _check_junction(node_id)
    node = wn.get_node(node_id)
    node._leak_status = False
