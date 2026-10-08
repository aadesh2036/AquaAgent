"""Sampler / demand tests (module 02 §6 step 1)."""

from __future__ import annotations

import collections
from pathlib import Path

import numpy as np
import pytest
import yaml

from shared.contracts import ids
from shared.contracts.models import (
    DS1_SCENARIO_COUNTS,
    SCENARIO_TO_FAULT,
    FaultType,
    ScenarioSpec,
    ScenarioType,
)
from sim.scenarios.demand import hourly_multipliers
from sim.scenarios.sampler import (
    derive_seed,
    make_rng,
    pipe_split_positions,
    plan_dataset,
    sample_scenario,
    sim_seed,
)

CFG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/generation/ds1.yaml").read_text())


@pytest.fixture(scope="module")
def plan():
    return plan_dataset(CFG)


def test_seed_is_63_bit_and_stable():
    assert sim_seed(20261008, 0) == sim_seed(20261008, 0)
    assert sim_seed(20261008, 0) != sim_seed(20261008, 1)
    assert 0 <= sim_seed(20261008, 123) < 2**63
    assert derive_seed(5, "a") != derive_seed(5, "b")


def test_counts_match_contract_and_ids(plan):
    assert len(plan) == 1200
    assert collections.Counter(s.scenario_type for s in plan) == collections.Counter(DS1_SCENARIO_COUNTS)
    assert [s.simulation_id for s in plan] == [ids.simulation_id("ds1", i) for i in range(1200)]
    assert all(ids.SIMULATION_ID_RE.match(s.simulation_id) for s in plan)


def test_every_shard_and_prefix_is_a_mix(plan):
    for shard in range(8):
        types = {s.scenario_type for s in plan[shard::8]}
        assert len(types) == 8
    assert len({s.scenario_type for s in plan[:40]}) == 8


def test_determinism_and_specs_validate(plan):
    again = plan_dataset(CFG)
    assert [s.model_dump_json() for s in plan] == [s.model_dump_json() for s in again]
    for s in plan[:200]:
        ScenarioSpec.model_validate_json(s.model_dump_json())
    assert len({s.config_hash for s in plan}) == 1200
    assert all(s.config_hash.startswith("sha256:") and s.generator_version == "sim-0.2.0" for s in plan)
    other = plan_dataset(CFG, dataset_seed=1)
    assert other[0].seed != plan[0].seed


def test_ranges_per_type(plan):
    for s in plan:
        p = s.demand_profile
        assert 0.30 <= p.night_min <= 0.45
        assert 1.30 <= p.morning_peak_mult <= 1.60 and 6.5 <= p.morning_peak_h <= 8.5
        assert 1.40 <= p.evening_peak_mult <= 1.80 and 18.0 <= p.evening_peak_h <= 20.5
        assert set(p.node_multipliers) == {"3", "4", "5", "6"}
        assert all(0.85 <= v <= 1.15 for v in p.node_multipliers.values())
        assert 0.6 <= s.operations.tank_init_level_m <= 2.5
        t = s.scenario_type
        if t == ScenarioType.HIGH_DEMAND:
            assert 1.3 <= p.global_mult <= 1.8
        elif t == ScenarioType.LOW_DEMAND:
            assert 0.4 <= p.global_mult <= 0.7
        else:
            assert p.global_mult is None
        want = SCENARIO_TO_FAULT[t]
        assert [f.fault_type for f in s.faults] == ([want] if want else [])
        for f in s.faults:
            assert 6 * 3600 <= f.start_s <= 18 * 3600 and f.start_s % 300 == 0
            if f.fault_type in (FaultType.LEAK, FaultType.BURST):
                lo, hi = CFG["leak_area_m2"][t.value]
                assert lo <= f.leak_area_m2 <= hi and f.discharge_coeff == 0.75
                assert f.location_kind.value in {"pipe", "junction"}
                if f.location_kind.value == "pipe":
                    assert f.location_id in CFG["fault_locations"]["pipes"]
                    assert 0.2 <= f.position <= 0.8
                    assert f.position == pipe_split_positions(s.seed)[f.location_id]
                else:
                    assert f.location_id in CFG["fault_locations"]["junctions"] and f.position is None
                if f.end_s is not None:
                    assert 2 * 3600 <= f.end_s - f.start_s <= 6 * 3600 and (f.end_s - f.start_s) % 300 == 0
            if f.fault_type == FaultType.DEMAND_SHIFT:
                q = f.params
                assert q["node_up"] != q["node_down"] and f.location_id == q["node_up"]
                assert 1.5 <= q["mult_up"] <= 2.5 and 0.3 <= q["mult_down"] <= 0.6
        assert (s.noise.pressure_sigma_m, s.noise.flow_sigma_lps, s.noise.missing_rate) == (0.05, 0.10, 0.0)


def test_leak_end_fraction_and_location_coverage(plan):
    leaks = [s.faults[0] for s in plan if s.faults and s.faults[0].fault_type in (FaultType.LEAK, FaultType.BURST)]
    ended = sum(f.end_s is not None for f in leaks) / len(leaks)
    assert 0.2 < ended < 0.4
    assert len({(f.location_kind, f.location_id) for f in leaks}) == 14


def test_ds2_types_rejected():
    with pytest.raises(ValueError):
        sample_scenario(ScenarioType.VALVE_CLOSURE, 0, "ds1", make_rng(1), CFG)


def test_demand_multipliers_noise_and_clip():
    p = plan_dataset(CFG)[0].demand_profile
    a = hourly_multipliers(p, make_rng(1))
    assert a.shape == (24,) and (a >= 0.05).all()
    assert np.array_equal(a, hourly_multipliers(p, make_rng(1)))
    assert not np.array_equal(a, hourly_multipliers(p, make_rng(2)))
    quiet = p.model_copy(update={"noise_sigma": 0.0, "night_min": 0.01, "global_mult": 0.1})
    assert hourly_multipliers(quiet, make_rng(1)).min() == pytest.approx(0.05)
