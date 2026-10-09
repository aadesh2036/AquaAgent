"""Sensor-placement sampling for training and evaluation (BACKBONE §9.1; placement experiment §6.4 / P-04-1).

Two training modes, mixed per sample:

* **default** — the contract layout (S1–S3 at nodes 2/4/6 + F1/F2), with one of
  {none, S1, S2, S3, F1, F2} hidden uniformly. This is exactly what ``predict()`` runs at inference
  (reconstruct + 5-sensor leave-one-out), so the ship path is trained on its own distribution.
* **random** — k ~ U{k_min..k_max} pressure sensors placed uniformly over the candidate junctions,
  each flow sensor present with p = 0.5. Placements listed in ``holdout`` are never sampled, so
  evaluation can compare seen vs never-seen placements.
"""

from __future__ import annotations

import itertools

import torch

from ml.features.tensorize import GraphStatic


def parse_placements(spec: str, gs: GraphStatic) -> set[frozenset[int]]:
    """'3-5-7,2-5-7' → {frozenset(node indices)}."""
    out = set()
    for grp in filter(None, (s.strip() for s in spec.split(","))):
        out.add(frozenset(gs.node_order.index(n) for n in grp.split("-")))
    return out


def all_placements(gs: GraphStatic, k: int) -> list[frozenset[int]]:
    cand = torch.nonzero(gs.candidate).flatten().tolist()
    return [frozenset(c) for c in itertools.combinations(cand, k)]


def placement_mask(placement: frozenset[int], batch: int, gs: GraphStatic) -> torch.Tensor:
    m = torch.zeros(batch, gs.n_nodes, dtype=torch.bool)
    m[:, sorted(placement)] = True
    return m


def default_masks(batch: int, gs: GraphStatic, drop: str | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """Contract layout with optionally one sensor hidden ('S1'..'S3', 'F1', 'F2')."""
    p = placement_mask(frozenset(gs.default_sensor_idx), batch, gs)
    q = torch.ones(batch, len(gs.flow_edge_fwd), dtype=torch.bool)
    if drop is not None and drop.startswith("S"):
        p[:, gs.default_sensor_idx[int(drop[1:]) - 1]] = False
    elif drop is not None and drop.startswith("F"):
        q[:, int(drop[1:]) - 1] = False
    return p, q


def sample_masks(
    batch: int,
    gs: GraphStatic,
    g: torch.Generator,
    p_default: float = 0.5,
    k_range: tuple[int, int] = (1, 5),
    holdout: set[frozenset[int]] = frozenset(),
) -> tuple[torch.Tensor, torch.Tensor]:
    n_f = len(gs.flow_edge_fwd)
    cand = torch.nonzero(gs.candidate).flatten()
    use_default = torch.rand(batch, generator=g) < p_default

    # default mode: drop one of {none, S1..S3, F1..F2}
    p_def, q_def = default_masks(batch, gs)
    drop = torch.randint(0, 1 + len(gs.default_sensor_idx) + n_f, (batch,), generator=g)
    for i, node in enumerate(gs.default_sensor_idx):
        p_def[drop == 1 + i, node] = False
    for f in range(n_f):
        q_def[drop == 1 + len(gs.default_sensor_idx) + f, f] = False

    # random mode: k sensors over candidate junctions (rejection of held-out placements)
    p_rnd = torch.zeros(batch, gs.n_nodes, dtype=torch.bool)
    todo = torch.ones(batch, dtype=torch.bool)
    hold = [torch.tensor(sorted(h)) for h in holdout]
    while todo.any():
        idx = torch.nonzero(todo).flatten()
        k = torch.randint(k_range[0], k_range[1] + 1, (len(idx),), generator=g)
        ranks = torch.rand(len(idx), len(cand), generator=g).argsort(1).argsort(1)
        chosen = torch.zeros(len(idx), gs.n_nodes, dtype=torch.bool)
        chosen[:, cand] = ranks < k.unsqueeze(1)
        p_rnd[idx] = chosen
        todo[:] = False
        for h in hold:
            hm = torch.zeros(gs.n_nodes, dtype=torch.bool)
            hm[h] = True
            todo |= (p_rnd == hm).all(1)
    q_rnd = torch.rand(batch, n_f, generator=g) < 0.5

    p = torch.where(use_default.unsqueeze(1), p_def, p_rnd)
    q = torch.where(use_default.unsqueeze(1), q_def, q_rnd)
    return p, q
