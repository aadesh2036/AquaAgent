"""Sample ScenarioSpecs for every ds1 scenario type (BACKBONE §5.4, §7.2, §8.1-8.3).

All randomness goes through `numpy.random.Generator(PCG64(seed))`; `seed = sim_seed(dataset_seed, i)`.
Auxiliary streams (pipe split positions, demand noise, sensor noise) derive their own seeds from the
simulation seed with `derive_seed`, so the runner can reproduce them without extra spec fields.

Implementation: docs/modules/02_DATA_GENERATION.md
"""

from __future__ import annotations

import functools
import hashlib
import json
import math

from numpy.random import PCG64, Generator

from shared.contracts import ids
from shared.contracts.models import (
    DS1_SCENARIO_COUNTS,
    DemandProfile,
    FaultSpec,
    FaultType,
    LocationKind,
    NoiseSpec,
    Operations,
    ScenarioSpec,
    ScenarioType,
)
from sim.engine import network as net

GENERATOR_VERSION = "sim-0.2.0"
DISCHARGE_COEFF = 0.75
DEMAND_JUNCTIONS = ("3", "4", "5", "6")
LEAK_TYPES = (
    ScenarioType.SMALL_LEAK,
    ScenarioType.MEDIUM_LEAK,
    ScenarioType.LARGE_LEAK,
    ScenarioType.PIPE_BURST,
)
DEFAULT_PIPE_POSITION = (0.2, 0.8)
_MASK63 = (1 << 63) - 1


def _hash64(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big") & _MASK63


def sim_seed(dataset_seed: int, sim_index: int) -> int:
    """`hash64(dataset_seed, sim_index)`: first 8 bytes of SHA-256, masked to 63 bits (§5.4)."""
    return _hash64(f"{dataset_seed}:{sim_index}")


def derive_seed(seed: int, label: str) -> int:
    """Seed of an auxiliary stream of one simulation (e.g. 'pipe_pos', 'demand', 'noise')."""
    return _hash64(f"{seed}:{label}")


def make_rng(seed: int) -> Generator:
    return Generator(PCG64(seed))


def pipe_split_positions(seed: int, lo: float = DEFAULT_PIPE_POSITION[0], hi: float = DEFAULT_PIPE_POSITION[1]):
    """U(lo, hi) split position for EVERY leak pipe, reproducible from the sim seed alone (§6.3)."""
    rng = make_rng(derive_seed(seed, "pipe_pos"))
    return {p: float(rng.uniform(lo, hi)) for p in net.LEAK_PIPES}


@functools.cache
def _network_payload(network_id: str) -> str:
    return json.dumps(net.network_config(network_id).model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def config_hash(spec: ScenarioSpec) -> str:
    """sha256 of canonical JSON of NetworkConfig + spec (without config_hash) + generator version (§5.4)."""
    payload = {
        "network": json.loads(_network_payload(spec.network_id)),
        "spec": spec.model_dump(mode="json", exclude={"config_hash"}),
        "generator_version": spec.generator_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def _snap(t_s: float, step: int) -> int:
    return int(round(t_s / step) * step)


def _profile(rng: Generator, scenario_type: ScenarioType, idx: int) -> DemandProfile:
    night_min = rng.uniform(0.30, 0.45)
    morning_mult = rng.uniform(1.30, 1.60)
    morning_h = rng.uniform(6.5, 8.5)
    evening_mult = rng.uniform(1.40, 1.80)
    evening_h = rng.uniform(18.0, 20.5)
    node_mult = {j: float(rng.uniform(0.85, 1.15)) for j in DEMAND_JUNCTIONS}
    global_mult = None
    if scenario_type == ScenarioType.HIGH_DEMAND:
        global_mult = float(rng.uniform(1.3, 1.8))
    elif scenario_type == ScenarioType.LOW_DEMAND:
        global_mult = float(rng.uniform(0.4, 0.7))
    return DemandProfile(
        profile_id=f"diurnal_random_{idx:06d}",
        night_min=float(night_min),
        morning_peak_mult=float(morning_mult),
        morning_peak_h=float(morning_h),
        evening_peak_mult=float(evening_mult),
        evening_peak_h=float(evening_h),
        node_multipliers=node_mult,
        noise_sigma=0.03,
        global_mult=global_mult,
    )


def _locations(gen_cfg: dict) -> list[tuple[LocationKind, str]]:
    fl = gen_cfg["fault_locations"]
    return [(LocationKind.JUNCTION, j) for j in fl["junctions"]] + [(LocationKind.PIPE, p) for p in fl["pipes"]]


def sample_scenario(
    scenario_type: ScenarioType, sim_index: int, dataset_version: str, rng: Generator, gen_cfg: dict
) -> ScenarioSpec:
    """One spec. All randomness via `rng` = Generator(PCG64(sim_seed(...))) (§5.4). Raises on ds2 types."""
    if scenario_type not in DS1_SCENARIO_COUNTS:
        raise ValueError(f"{scenario_type} is not a ds1 scenario type (ds2 types are T3)")
    seed = sim_seed(gen_cfg["dataset_seed"], sim_index)
    step = int(gen_cfg.get("timestep_s", 300))
    duration = int(gen_cfg.get("duration_s", 86400))
    profile = _profile(rng, scenario_type, sim_index)
    tank_init = float(rng.uniform(0.6, 2.5))
    faults: list[FaultSpec] = []

    t_lo, t_hi = gen_cfg.get("fault_start_window_h", [6, 18])
    if scenario_type in LEAK_TYPES:
        start_s = _snap(rng.uniform(t_lo * 3600, t_hi * 3600), step)
        lo, hi = gen_cfg["leak_area_m2"][scenario_type.value]
        area = float(math.exp(rng.uniform(math.log(lo), math.log(hi))))
        locs = _locations(gen_cfg)
        kind, loc = locs[int(rng.integers(len(locs)))]
        position = None
        if kind == LocationKind.PIPE:
            p_lo, p_hi = gen_cfg["fault_locations"].get("pipe_position", DEFAULT_PIPE_POSITION)
            position = pipe_split_positions(seed, p_lo, p_hi)[loc]
        end_s = None
        if rng.random() < gen_cfg.get("leak_end_probability", 0.30):
            d_lo, d_hi = gen_cfg.get("leak_end_duration_h", [2, 6])
            end = start_s + _snap(rng.uniform(d_lo * 3600, d_hi * 3600), step)
            end_s = end if end < duration else None
        faults.append(
            FaultSpec(
                fault_id="f0",
                fault_type=FaultType.BURST if scenario_type == ScenarioType.PIPE_BURST else FaultType.LEAK,
                location_kind=kind,
                location_id=loc,
                position=position,
                leak_area_m2=area,
                discharge_coeff=DISCHARGE_COEFF,
                start_s=start_s,
                end_s=end_s,
            )
        )
    elif scenario_type == ScenarioType.DEMAND_SHIFT:
        start_s = _snap(rng.uniform(t_lo * 3600, t_hi * 3600), step)
        a, b = rng.choice(len(DEMAND_JUNCTIONS), size=2, replace=False)
        up, down = DEMAND_JUNCTIONS[int(a)], DEMAND_JUNCTIONS[int(b)]
        faults.append(
            FaultSpec(
                fault_id="f0",
                fault_type=FaultType.DEMAND_SHIFT,
                location_kind=LocationKind.JUNCTION,
                location_id=up,
                start_s=start_s,
                params={
                    "node_up": up,
                    "mult_up": float(rng.uniform(1.5, 2.5)),
                    "node_down": down,
                    "mult_down": float(rng.uniform(0.3, 0.6)),
                },
            )
        )

    n = gen_cfg["noise"]
    spec = ScenarioSpec(
        simulation_id=ids.simulation_id(dataset_version, sim_index),
        network_id=gen_cfg["network_id"],
        sensor_layout_id=gen_cfg["sensor_layout_id"],
        seed=seed,
        duration_s=duration,
        timestep_s=step,
        demand_profile=profile,
        operations=Operations(tank_init_level_m=tank_init),
        scenario_type=scenario_type,
        faults=faults,
        noise=NoiseSpec(
            pressure_sigma_m=n["pressure_sigma_m"], flow_sigma_lps=n["flow_sigma_lps"], missing_rate=n["missing_rate"]
        ),
        config_hash="sha256:" + "0" * 64,
        generator_version=GENERATOR_VERSION,
    )
    return spec.model_copy(update={"config_hash": config_hash(spec)})


def plan_dataset(gen_cfg: dict, dataset_seed: int | None = None) -> list[ScenarioSpec]:
    """Full ds plan, `sim_index` 0..N-1, deterministic from `dataset_seed`.

    Order = stratified-jitter interleave: the k-th sim of a type with count n gets the key
    (k + u) / n with u ~ U(0, 1) from a dedicated stream, then all sims are sorted by key. Every
    prefix and every `index % num_shards` slice is therefore a proportional mix of all types.
    """
    cfg = dict(gen_cfg)
    if dataset_seed is not None:
        cfg["dataset_seed"] = dataset_seed
    seed = cfg["dataset_seed"]
    counts = {ScenarioType(k): int(v) for k, v in cfg["counts"].items()}
    for t in counts:
        if t not in DS1_SCENARIO_COUNTS:
            raise ValueError(f"{t} is not a ds1 scenario type")
    order_rng = make_rng(derive_seed(seed, "plan_order"))
    keyed = []
    for t in ScenarioType:  # fixed enum order -> deterministic
        n = counts.get(t, 0)
        for k in range(n):
            keyed.append(((k + order_rng.random()) / n, t.value, k, t))
    keyed.sort()
    version = cfg["dataset_version"]
    specs = []
    for i, (_, _, _, t) in enumerate(keyed):
        specs.append(sample_scenario(t, i, version, make_rng(sim_seed(seed, i)), cfg))
    return specs
