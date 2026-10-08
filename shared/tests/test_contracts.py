"""Contract tests: every JSON example in BACKBONE.md round-trips through the Pydantic models."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.contracts import ids, models
from shared.contracts.backbone_examples import BACKBONE_PATH, EXPECTED_BLOCKS, load_examples

EXAMPLES = load_examples()


@pytest.mark.parametrize("key", [k for _, k in EXPECTED_BLOCKS])
def test_backbone_example_round_trips(key: str) -> None:
    model = models.SECTION_MODELS[key]
    data = EXAMPLES[key]
    obj = model.model_validate(data)
    dumped = obj.model_dump(mode="json", exclude_unset=True)
    assert json.loads(json.dumps(dumped)) == data
    # and back again
    assert model.model_validate(dumped) == obj


def test_backbone_contract_version_matches() -> None:
    text = BACKBONE_PATH.read_text(encoding="utf-8")
    assert f"`{models.CONTRACT_VERSION}`" in text


def test_extra_fields_are_rejected() -> None:
    data = dict(EXAMPLES["7.3"], unexpected_field=1)
    with pytest.raises(ValidationError):
        models.SimEvent.model_validate(data)


def test_ds1_counts_sum_to_d7() -> None:
    assert sum(models.DS1_SCENARIO_COUNTS.values()) == 1200
    assert set(models.DS1_SCENARIO_COUNTS) | models.DS2_SCENARIO_TYPES == set(models.ScenarioType)
    assert models.OPERATIONAL_SCENARIOS <= set(models.DS1_SCENARIO_COUNTS)
    assert not any(models.SCENARIO_IS_ANOMALOUS[s] for s in models.OPERATIONAL_SCENARIOS)


def test_every_scenario_has_fault_mapping_and_label() -> None:
    assert set(models.SCENARIO_TO_FAULT) == set(models.ScenarioType)
    assert set(models.SCENARIO_IS_ANOMALOUS) == set(models.ScenarioType)
    assert models.SCENARIO_IS_ANOMALOUS[models.ScenarioType.SMALL_LEAK]
    assert not models.SCENARIO_IS_ANOMALOUS[models.ScenarioType.HIGH_DEMAND]
    assert not models.SCENARIO_IS_ANOMALOUS[models.ScenarioType.SENSOR_FAULT]


def test_single_cadence() -> None:
    assert models.INTERACTIVE_TIMESTEP_S == models.DATASET_TIMESTEP_S == 300


def test_predictor_response_has_flow_loo() -> None:
    resp = models.PredictorResponse.model_validate(EXAMPLES["7.9.response"])
    assert set(resp.leave_one_out or {}) == set(models.PRESSURE_SENSORS)
    assert set(resp.leave_one_out_flow or {}) == set(models.FLOW_SENSORS)


def test_incident_localisation_optional_until_t2c() -> None:
    data = dict(EXAMPLES["7.12"], localisation=None)
    assert models.Incident.model_validate(data).localisation is None


def test_sensor_window_rejects_long_windows() -> None:
    sw = EXAMPLES["7.8"]
    too_long = dict(sw, window=sw["window"] * (models.WINDOW_STEPS + 1))
    with pytest.raises(ValidationError):
        models.SensorWindow.model_validate(too_long)


def test_feature_orders_are_frozen() -> None:
    assert len(models.NODE_FEATURES_V1) == 15
    assert len(models.EDGE_FEATURES_V1) == 7
    assert models.NODE_FEATURES_V1[0] == "elevation_m_z"
    assert models.EDGE_FEATURES_V1[-1] == "flow_obs_mask"


def test_firewall_tables_disjoint() -> None:
    assert not (models.MODEL_INPUT_TABLES & models.GROUND_TRUTH_TABLES)
    for table in models.MODEL_INPUT_TABLES - {"sensors"}:
        assert not (set(models.TABLE_COLUMNS[table]) & models.FORBIDDEN_INPUT_COLUMNS)


def test_incident_has_no_ground_truth_fields() -> None:
    forbidden = {"truth", "leak_area_m2", "scenario_type", "hidden", "fault_type"}
    schema_text = json.dumps(models.Incident.model_json_schema())
    for word in forbidden:
        assert f'"{word}"' not in schema_text


_SUFFIXES = ("_m", "_m3s", "_lps", "_lpm", "_ms", "_m2", "_mm", "_s", "_pct", "_m3", "_hw")
# Fields that are numeric but intentionally unit-less (counts, ratios, scores, ids, flags).
_UNITLESS_OK = {
    "seed",
    "dataset_seed",
    "n_requested",
    "n_valid",
    "n_failed",
    "x",
    "y",
    "position",
    "discharge_coeff",
    "score",
    "similarity",
    "anomaly_score",
    "rank",
    "priority",
    "speed",
    "direction",
    "pump_status",
    "detection_delay_steps",
    "night_min",
    "morning_peak_mult",
    "morning_peak_h",
    "evening_peak_mult",
    "evening_peak_h",
    "noise_sigma",
    "global_mult",
    "pump_speed",
    "missing_rate",
    "pct_change",
    "steps",
    "horizon_steps",
    "last_n_steps",
    "top_k",
    "true_location_rank",
    "magnitude",
    "customers_below_20m",
    "value",
    "n_nodes",
    "n_edges_directed",
    "latency_ms",
    "time_of_day_s",
}


def _numeric_fields(model: type) -> list[str]:
    out = []
    for name, field in model.model_fields.items():
        ann = str(field.annotation)
        if ("float" in ann or "int" in ann) and "dict" not in ann and "list" not in ann:
            out.append(name)
    return out


def test_numeric_fields_carry_unit_suffix() -> None:
    """BACKBONE §5.2: a numeric field without a unit suffix is a bug (allow-listed exceptions)."""
    offenders = []
    for name, obj in vars(models).items():
        if isinstance(obj, type) and issubclass(obj, models._Model) and obj is not models._Model:
            for f in _numeric_fields(obj):
                if not f.endswith(_SUFFIXES) and f not in _UNITLESS_OK:
                    offenders.append(f"{name}.{f}")
    assert offenders == []


def test_ids() -> None:
    assert ids.simulation_id("ds1", 417) == "sim_ds1_000417"
    assert ids.incident_id("sess_3f9a1c", 43200) == "inc_3f9a1c_43200"
    assert ids.canonical_link_id("4_B") == "4"
    assert ids.canonical_link_id("4") == "4"
    assert ids.is_hidden_element(ids.leak_node_id("4"))
    assert ids.SESSION_ID_RE.match(ids.new_session_id())
    assert ids.MODEL_VERSION_RE.match(ids.model_version("mlp", "ds1"))
    assert re.match(r"^thr_ds1_\d{12}$", ids.thresholds_version("ds1"))


def test_ts_mirror_mentions_every_enum() -> None:
    ts = (Path(models.__file__).parent / "contracts.ts").read_text(encoding="utf-8")
    from shared.contracts.export import enums

    for name in enums():
        assert f"export const {name} =" in ts, f"{name} missing from contracts.ts"
