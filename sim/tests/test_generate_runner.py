"""Runner tests (module 02 §6 step 2) and validation exclusion (step 4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

import sim.generate.runner as runner
from shared.contracts.models import TABLE_COLUMNS, VALIDATION_CHECKS, ScenarioType
from sim.engine import network as net
from sim.generate.validation import validate_simulation
from sim.scenarios.sampler import plan_dataset

CFG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/generation/ds1.yaml").read_text())
NET = net.network_config()


@pytest.fixture(scope="module")
def results():
    plan = plan_dataset(CFG)
    out = {}
    for t in (ScenarioType.NORMAL, ScenarioType.MEDIUM_LEAK, ScenarioType.DEMAND_SHIFT, ScenarioType.PIPE_BURST):
        spec = next(s for s in plan if s.scenario_type == t)
        out[t] = (spec, runner.run_simulation(spec, NET))
    return out


def test_tables_have_exact_columns_and_289_steps(results):
    for _spec, res in results.values():
        assert res.ok, res.detail
        assert set(res.tables) == {"scenarios", "node_states", "link_states", "tank_states", "pump_states", "sensors", "context"}
        for name, df in res.tables.items():
            want = [c for c in TABLE_COLUMNS[name] if not (name == "scenarios" and c == "split")]
            assert list(df.columns) == want, name
        assert res.tables["context"]["sim_time_s"].nunique() == 289
        assert len(res.tables["node_states"]) == 289 * 8 and len(res.tables["link_states"]) == 289 * 9
        assert len(res.tables["sensors"]) == 289 * 5
        assert [r.check for r in res.validation_rows] == list(VALIDATION_CHECKS)
        assert all(r.passed for r in res.validation_rows)


def test_row_order_and_sensor_layout(results):
    _, res = results[ScenarioType.NORMAL]
    ns = res.tables["node_states"]
    assert ns.equals(ns.sort_values(["simulation_id", "sim_time_s", "node_id"], kind="stable").reset_index(drop=True))
    assert set(ns.loc[ns["is_sensor"], "node_id"]) == {"2", "4", "6"}
    hops = ns.drop_duplicates("node_id").set_index("node_id")["hop_to_nearest_sensor"].to_dict()
    assert hops == {"1": 1, "2": 0, "3": 1, "4": 0, "5": 1, "6": 0, "7": 1, "8": 2}
    se = res.tables["sensors"]
    assert set(se["sensor_id"]) == {"S1", "S2", "S3", "F1", "F2"}
    assert set(se.loc[se["measurement"] == "pressure_m", "source_id"]) == {"2", "4", "6"}
    assert set(se.loc[se["measurement"] == "flow_lps", "source_id"]) == {"3", "6"}
    assert se["sensor_fault_kind"].isna().all()


def test_noise_only_on_measured_value(results):
    _, res = results[ScenarioType.NORMAL]
    se, ns, lk = res.tables["sensors"], res.tables["node_states"], res.tables["link_states"]
    s1 = se[se["sensor_id"] == "S1"].reset_index(drop=True)
    truth = ns[ns["node_id"] == "2"].reset_index(drop=True)["pressure_m"]
    assert np.allclose(s1["true_value"], truth)  # untouched
    d = s1["measured_value"] - s1["true_value"]
    assert 0.02 < d.std() < 0.10 and abs(d.mean()) < 0.02
    f1 = se[se["sensor_id"] == "F1"].reset_index(drop=True)
    flow = lk[lk["link_id"] == "3"].reset_index(drop=True)["flow_m3s"] * 1000.0
    assert np.allclose(f1["true_value"], flow)
    assert 0.05 < (f1["measured_value"] - f1["true_value"]).std() < 0.2


@pytest.mark.parametrize("t", [ScenarioType.MEDIUM_LEAK, ScenarioType.PIPE_BURST])
def test_leak_sims_have_realised_leak(results, t):
    spec, res = results[t]
    row = res.tables["scenarios"].iloc[0]
    assert row["realised_leak_peak_m3s"] > 0 and row["severity_bucket"] in {"<5%", "5-15%", "15-25%", ">25%"}
    assert row["is_anomalous"] and row["fault_start_s"] == spec.faults[0].start_s
    ns = res.tables["node_states"]
    before = ns[ns["sim_time_s"] < row["fault_start_s"]]
    assert before["leak_m3s"].abs().max() == 0


def test_normal_has_no_leak_and_demand_shift_changes_demand(results):
    _, res = results[ScenarioType.NORMAL]
    row = res.tables["scenarios"].iloc[0]
    assert not row["is_anomalous"] and row["fault_type"] is None and row["realised_leak_peak_m3s"] is None
    assert res.tables["node_states"]["leak_m3s"].abs().max() == 0

    spec, res = results[ScenarioType.DEMAND_SHIFT]
    p, tf = spec.faults[0].params, spec.faults[0].start_s
    ns = res.tables["node_states"]
    d = ns[ns["node_id"] == p["node_up"]].set_index("sim_time_s")["base_demand_m3s"]
    ratio_before = d[tf - 300] / d[tf - 600]
    ratio_after = d[tf] / d[tf - 300]
    assert ratio_after > 1.3 * ratio_before  # x1.5..2.5 step at t_f
    assert res.tables["scenarios"].iloc[0]["fault_type"] == "DEMAND_SHIFT"


def test_reproducible_in_process(results):
    spec, res = results[ScenarioType.MEDIUM_LEAK]
    again = runner.run_simulation(spec, NET)
    for name in res.tables:
        assert res.tables[name].equals(again.tables[name]), name


def test_nan_injection_excludes_sim(results, monkeypatch):
    spec, res = results[ScenarioType.NORMAL]
    bad = {k: v.copy() for k, v in res.tables.items()}
    bad["node_states"].loc[10, "pressure_m"] = np.nan
    rows = validate_simulation(spec, bad)
    failed = {r.check for r in rows if not r.passed}
    assert "no_nan" in failed and len(rows) == len(VALIDATION_CHECKS)

    real = runner.build_tables

    def poisoned(*a, **k):
        t = real(*a, **k)
        t["tank_states"].loc[3, "level_m"] = np.nan
        return t

    monkeypatch.setattr(runner, "build_tables", poisoned)
    r = runner.run_simulation(spec, NET)
    assert not r.ok and r.tables == {}
    assert any((not x.passed) and x.check == "no_nan" for x in r.validation_rows)


def test_solver_exception_becomes_failed_result(results, monkeypatch):
    spec, _ = results[ScenarioType.NORMAL]

    def boom(*a, **k):
        raise RuntimeError("did not converge")

    monkeypatch.setattr(runner, "simulate", boom)
    r = runner.run_simulation(spec, NET)
    assert not r.ok and r.tables == {}
    assert [x.check for x in r.validation_rows] == list(VALIDATION_CHECKS)
    assert not next(x for x in r.validation_rows if x.check == "converged").passed
