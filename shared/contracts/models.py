"""AquaAgent data contracts — Pydantic v2 twins of BACKBONE.md §6.4 and §7.1–7.15.

This file is the ONLY place schemas are coded in Python (BACKBONE §0.4). Modules import
from here; they never re-declare a schema. Field names are canonical and carry their unit
suffix (BACKBONE §5.2). Any change here requires a BACKBONE version bump (§17).

Conventions
-----------
* ``extra="forbid"`` everywhere: an unknown field is a contract violation, not a feature.
* Closed sets are ``StrEnum`` so they serialise as plain strings in JSON.
* Dict-keyed maps (node_id → state) mirror BACKBONE exactly; keys are EPANET ids as strings.
* Fields that are present in BACKBONE examples but legitimately absent in some messages
  (e.g. ``hidden`` after the visibility filter) are Optional with ``None`` default.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "backbone/1.1.0"
"""Value of the ``X-Aqua-Contract`` header on every API response (§5.5)."""

SCHEMA_VERSION = "1.0"
"""Default ``schema_version`` for persisted JSON / manifests (§5.5)."""

WINDOW_STEPS = 12
"""SensorWindow length in steps (§7.8). See BACKBONE_ISSUES BI-01 for cadence."""

DATASET_TIMESTEP_S = 300
INTERACTIVE_TIMESTEP_S = 300
"""Single cadence everywhere since backbone/1.1.0 (§5.3, D6)."""
EPISODE_DURATION_S = 86_400


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=False)


# ---------------------------------------------------------------------------
# Closed sets (enums)
# ---------------------------------------------------------------------------


class NodeType(StrEnum):
    JUNCTION = "junction"
    RESERVOIR = "reservoir"
    TANK = "tank"


class LinkType(StrEnum):
    PIPE = "pipe"
    PUMP = "pump"
    VALVE = "valve"


class LinkStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ACTIVE = "ACTIVE"


class LocationKind(StrEnum):
    """Fault / candidate location kind (§7.2, §7.11, §8.2)."""

    PIPE = "pipe"
    JUNCTION = "junction"


class ScenarioType(StrEnum):
    """§8.1 scenario catalogue (14 types)."""

    NORMAL = "NORMAL"
    HIGH_DEMAND = "HIGH_DEMAND"
    LOW_DEMAND = "LOW_DEMAND"
    DEMAND_SHIFT = "DEMAND_SHIFT"
    DEMAND_SPIKE = "DEMAND_SPIKE"
    VALVE_CLOSURE = "VALVE_CLOSURE"
    PARTIAL_VALVE = "PARTIAL_VALVE"
    PUMP_DEGRADE = "PUMP_DEGRADE"
    LOW_RESERVOIR = "LOW_RESERVOIR"
    SMALL_LEAK = "SMALL_LEAK"
    MEDIUM_LEAK = "MEDIUM_LEAK"
    LARGE_LEAK = "LARGE_LEAK"
    PIPE_BURST = "PIPE_BURST"
    SENSOR_FAULT = "SENSOR_FAULT"


class FaultType(StrEnum):
    """§7.2 hydraulic fault types."""

    LEAK = "LEAK"
    BURST = "BURST"
    VALVE_CLOSURE = "VALVE_CLOSURE"
    PARTIAL_VALVE = "PARTIAL_VALVE"
    PUMP_DEGRADE = "PUMP_DEGRADE"
    PUMP_TRIP = "PUMP_TRIP"
    LOW_RESERVOIR = "LOW_RESERVOIR"
    DEMAND_SPIKE = "DEMAND_SPIKE"
    DEMAND_SHIFT = "DEMAND_SHIFT"


class SensorFaultKind(StrEnum):
    """§7.2 sensor_faults[].kind."""

    SPIKE = "SPIKE"
    BIAS = "BIAS"
    DRIFT = "DRIFT"
    STUCK = "STUCK"
    MISSING = "MISSING"


# Scenario → primary hydraulic fault type (BACKBONE_ISSUES BI-16 interim rule).
SCENARIO_TO_FAULT: dict[ScenarioType, FaultType | None] = {
    ScenarioType.NORMAL: None,
    ScenarioType.HIGH_DEMAND: None,
    ScenarioType.LOW_DEMAND: None,
    ScenarioType.DEMAND_SHIFT: FaultType.DEMAND_SHIFT,
    ScenarioType.DEMAND_SPIKE: FaultType.DEMAND_SPIKE,
    ScenarioType.VALVE_CLOSURE: FaultType.VALVE_CLOSURE,
    ScenarioType.PARTIAL_VALVE: FaultType.PARTIAL_VALVE,
    ScenarioType.PUMP_DEGRADE: FaultType.PUMP_DEGRADE,
    ScenarioType.LOW_RESERVOIR: FaultType.LOW_RESERVOIR,
    ScenarioType.SMALL_LEAK: FaultType.LEAK,
    ScenarioType.MEDIUM_LEAK: FaultType.LEAK,
    ScenarioType.LARGE_LEAK: FaultType.LEAK,
    ScenarioType.PIPE_BURST: FaultType.BURST,
    ScenarioType.SENSOR_FAULT: None,
}

# §8.1 is_anomalous column. Operational variation (*) is NOT anomalous.
SCENARIO_IS_ANOMALOUS: dict[ScenarioType, bool] = {
    s: s
    not in {
        ScenarioType.NORMAL,
        ScenarioType.HIGH_DEMAND,
        ScenarioType.LOW_DEMAND,
        ScenarioType.DEMAND_SHIFT,
        ScenarioType.SENSOR_FAULT,
    }
    for s in ScenarioType
}

# §8.1 requested counts for ds1 (backbone/1.1.0: 8 types, sum = 1200, decision D7).
DS1_SCENARIO_COUNTS: dict[ScenarioType, int] = {
    ScenarioType.NORMAL: 320,
    ScenarioType.HIGH_DEMAND: 100,
    ScenarioType.LOW_DEMAND: 80,
    ScenarioType.DEMAND_SHIFT: 100,
    ScenarioType.SMALL_LEAK: 150,
    ScenarioType.MEDIUM_LEAK: 200,
    ScenarioType.LARGE_LEAK: 150,
    ScenarioType.PIPE_BURST: 100,
}

# §8.1 ds2 (T3) scenario types — defined now so ds2 needs no contract change.
DS2_SCENARIO_TYPES: frozenset[ScenarioType] = frozenset(set(ScenarioType) - set(DS1_SCENARIO_COUNTS))

# Operational variation: the detector must NOT fire; defines the false-alarm rate (§9.5).
OPERATIONAL_SCENARIOS: frozenset[ScenarioType] = frozenset(
    {ScenarioType.NORMAL, ScenarioType.HIGH_DEMAND, ScenarioType.LOW_DEMAND, ScenarioType.DEMAND_SHIFT}
)

# Pressure/flow sensors of the default layout (§6.4) — LOO runs over all five (§7.9).
PRESSURE_SENSORS: tuple[str, ...] = ("S1", "S2", "S3")
FLOW_SENSORS: tuple[str, ...] = ("F1", "F2")

# Scenarios whose normal (pre-fault + whole-episode) states the predictor may train on (§9.1).
PREDICTOR_TRAIN_SCENARIOS: frozenset[ScenarioType] = frozenset(
    {
        ScenarioType.NORMAL,
        ScenarioType.HIGH_DEMAND,
        ScenarioType.LOW_DEMAND,
        ScenarioType.DEMAND_SHIFT,
    }
)


class SeverityBucket(StrEnum):
    LT5 = "<5%"
    B5_15 = "5-15%"
    B15_25 = "15-25%"
    GT25 = ">25%"


class Split(StrEnum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


class EventSource(StrEnum):
    USER = "user"
    CHALLENGE = "challenge"
    SYSTEM = "system"


class EventKind(StrEnum):
    TAP_SET = "TAP_SET"
    PIPE_FAULT = "PIPE_FAULT"
    PIPE_RESET = "PIPE_RESET"
    VALVE_SET = "VALVE_SET"
    SPEED = "SPEED"
    RESET = "RESET"


class PredictorMode(StrEnum):
    RECONSTRUCT = "reconstruct"
    LEAVE_ONE_OUT = "leave_one_out"


class AnomalyStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ANOMALY = "ANOMALY"
    SENSOR_FAULT = "SENSOR_FAULT"


class NetworkStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ANOMALY = "ANOMALY"


class NodeUiStatus(StrEnum):
    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"


class VisualFault(StrEnum):
    NONE = "NONE"
    LEAK = "LEAK"
    BURST = "BURST"


class PumpUiStatus(StrEnum):
    ON = "ON"
    OFF = "OFF"


class PipeFaultKind(StrEnum):
    LEAK = "LEAK"
    BURST = "BURST"
    CLOSE = "CLOSE"
    RESET = "RESET"


class Difficulty(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ChallengeState(StrEnum):
    """Server-side `/challenge/status` state (§7.14.1)."""

    RUNNING = "RUNNING"
    DETECTED = "DETECTED"
    TIMEOUT = "TIMEOUT"


class UiChallengeState(StrEnum):
    """Frontend store challenge state (§7.15)."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    DETECTED = "DETECTED"
    REVEALED = "REVEALED"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class WhatIfAction(StrEnum):
    ISOLATE_PIPE = "isolate_pipe"
    CLOSE_VALVE = "close_valve"
    REDUCE_PUMP_SPEED = "reduce_pump_speed"


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    TEMPLATE = "template"


# ---------------------------------------------------------------------------
# §6.4 Sensor layout
# ---------------------------------------------------------------------------


class PressureSensorDef(_Model):
    sensor_id: str
    node_id: str


class FlowSensorDef(_Model):
    sensor_id: str
    link_id: str


CONTEXT_FIELDS: tuple[str, ...] = (
    "tank_level_m",
    "pump_status",
    "pump_flow_lps",
    "reservoir_head_m",
    "time_of_day_s",
)


class SensorLayout(_Model):
    sensor_layout_id: str
    pressure: list[PressureSensorDef]
    flow: list[FlowSensorDef]
    context: list[str]


# ---------------------------------------------------------------------------
# §7.1 NetworkConfig
# ---------------------------------------------------------------------------


class NodeConfig(_Model):
    node_id: str
    node_type: NodeType
    elevation_m: float
    base_demand_m3s: float | None = None
    x: float
    y: float
    ui_label: str | None = None
    zone_id: str | None = None


class LinkConfig(_Model):
    link_id: str
    link_type: LinkType
    start_node: str
    end_node: str
    length_m: float | None = None
    diameter_m: float | None = None
    roughness_hw: float | None = None
    initial_status: LinkStatus = LinkStatus.OPEN
    zone_id: str | None = None


class Zone(_Model):
    zone_id: str
    name: str


class HydraulicsConfig(_Model):
    demand_model: Literal["PDD", "DD"]
    required_pressure_m: float
    minimum_pressure_m: float
    headloss: Literal["H-W", "D-W", "C-M"]
    tank_init_level_m: float


class TapDef(_Model):
    tap_id: str
    node_id: str


class ValveDef(_Model):
    valve_id: str
    link_id: str
    impl: Literal["pipe_status"]


class NetworkConfig(_Model):
    schema_version: str = SCHEMA_VERSION
    network_id: str
    source: str
    inp_path: str | None = None
    nodes: list[NodeConfig]
    links: list[LinkConfig]
    zones: list[Zone]
    hydraulics: HydraulicsConfig
    taps: list[TapDef]
    valves: list[ValveDef]


class NetworkTopology(_Model):
    """`GET /network/topology` (§7.14.1): NetworkConfig minus hydraulics internals."""

    schema_version: str = SCHEMA_VERSION
    network_id: str
    nodes: list[NodeConfig]
    links: list[LinkConfig]
    zones: list[Zone]
    taps: list[TapDef]
    valves: list[ValveDef]
    sensor_layout: SensorLayout | None = None


# ---------------------------------------------------------------------------
# §7.2 ScenarioSpec
# ---------------------------------------------------------------------------


class DemandProfile(_Model):
    profile_id: str
    night_min: float
    morning_peak_mult: float
    morning_peak_h: float
    evening_peak_mult: float
    evening_peak_h: float
    node_multipliers: dict[str, float] = Field(default_factory=dict)
    noise_sigma: float
    weekend: bool = False
    global_mult: float | None = None
    """HIGH/LOW_DEMAND global multiplier (§8.1); absent = 1.0."""


class Operations(_Model):
    reservoir_head_offset_m: float = 0.0
    pump_speed: float = 1.0
    tank_init_level_m: float


class FaultSpec(_Model):
    fault_id: str
    fault_type: FaultType
    location_kind: LocationKind | None = None
    location_id: str | None = None
    position: float | None = Field(default=None, ge=0.0, le=1.0)
    leak_area_m2: float | None = None
    discharge_coeff: float | None = None
    start_s: int
    end_s: int | None = None
    params: dict[str, Any] | None = None
    """Type-specific params (e.g. demand mult, HW C, pump speed, head offset)."""


class SensorFaultSpec(_Model):
    kind: SensorFaultKind
    sensor_id: str
    start_s: int
    end_s: int | None = None
    magnitude: float | None = None


class NoiseSpec(_Model):
    pressure_sigma_m: float
    flow_sigma_lps: float
    missing_rate: float = Field(ge=0.0, le=1.0)


class ScenarioSpec(_Model):
    schema_version: str = SCHEMA_VERSION
    simulation_id: str
    network_id: str
    sensor_layout_id: str
    seed: int
    duration_s: int = EPISODE_DURATION_S
    timestep_s: int = DATASET_TIMESTEP_S
    demand_profile: DemandProfile
    operations: Operations
    scenario_type: ScenarioType
    faults: list[FaultSpec] = Field(default_factory=list)
    sensor_faults: list[SensorFaultSpec] = Field(default_factory=list)
    noise: NoiseSpec
    config_hash: str
    generator_version: str


# ---------------------------------------------------------------------------
# §7.3 SimEvent
# ---------------------------------------------------------------------------


class SimEvent(_Model):
    event_id: str
    sim_time_s: int
    source: EventSource
    kind: EventKind
    target_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    hidden: bool = False


# ---------------------------------------------------------------------------
# §7.4 HydraulicSnapshot
# ---------------------------------------------------------------------------


class NodeState(_Model):
    pressure_m: float
    head_m: float
    demand_m3s: float
    base_demand_m3s: float
    leak_m3s: float = 0.0


class LinkState(_Model):
    flow_m3s: float
    velocity_ms: float
    headloss_m: float
    status: LinkStatus


class TankState(_Model):
    level_m: float
    head_m: float
    volume_m3: float
    net_inflow_m3s: float


class PumpState(_Model):
    flow_m3s: float
    head_gain_m: float
    status: LinkStatus


class LeakNodeState(_Model):
    leak_m3s: float


class HiddenState(_Model):
    leak_nodes: dict[str, LeakNodeState] = Field(default_factory=dict)


class HydraulicSnapshot(_Model):
    schema_version: str = SCHEMA_VERSION
    network_id: str
    sim_time_s: int
    converged: bool
    nodes: dict[str, NodeState]
    links: dict[str, LinkState]
    tanks: dict[str, TankState] = Field(default_factory=dict)
    pumps: dict[str, PumpState] = Field(default_factory=dict)
    hidden: HiddenState | None = None
    """Stripped by the orchestrator before any public response (§7.4, §11)."""


# ---------------------------------------------------------------------------
# §7.5 Dataset tables — column lists are contracts too
# ---------------------------------------------------------------------------

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "scenarios": (
        "simulation_id",
        "dataset_version",
        "network_id",
        "sensor_layout_id",
        "scenario_type",
        "is_anomalous",
        "has_sensor_fault",
        "fault_type",
        "location_kind",
        "location_id",
        "zone_id",
        "position",
        "leak_area_m2",
        "fault_start_s",
        "fault_end_s",
        "realised_leak_peak_m3s",
        "severity_bucket",
        "seed",
        "config_hash",
        "generator_version",
        "spec_json",
        "split",
        "valid",
    ),
    "node_states": (
        "simulation_id",
        "sim_time_s",
        "node_id",
        "node_type",
        "pressure_m",
        "head_m",
        "demand_m3s",
        "base_demand_m3s",
        "leak_m3s",
        "is_sensor",
        "hop_to_nearest_sensor",
    ),
    "link_states": (
        "simulation_id",
        "sim_time_s",
        "link_id",
        "link_type",
        "flow_m3s",
        "velocity_ms",
        "headloss_m",
        "status",
    ),
    "tank_states": (
        "simulation_id",
        "sim_time_s",
        "tank_id",
        "level_m",
        "head_m",
        "volume_m3",
        "net_inflow_m3s",
    ),
    "pump_states": (
        "simulation_id",
        "sim_time_s",
        "pump_id",
        "flow_m3s",
        "head_gain_m",
        "status",
    ),
    "sensors": (
        "simulation_id",
        "sim_time_s",
        "sensor_id",
        "source_kind",
        "source_id",
        "measurement",
        "true_value",
        "measured_value",
        "sensor_fault_kind",
    ),
    "context": (
        "simulation_id",
        "sim_time_s",
        "time_of_day_s",
        "tank_level_m",
        "pump_status",
        "pump_flow_lps",
        "reservoir_head_m",
    ),
    "graph": (
        "network_id",
        "element_kind",
        "element_id",
        "start_node",
        "end_node",
        "features_json",
    ),
    "validation_log": (
        "simulation_id",
        "seed",
        "check",
        "passed",
        "detail",
        "generator_version",
    ),
}

# §7.5 / §11 firewall in data form.
MODEL_INPUT_TABLES: frozenset[str] = frozenset({"sensors", "context", "graph"})
GROUND_TRUTH_TABLES: frozenset[str] = frozenset(
    {"scenarios", "node_states", "link_states", "tank_states", "pump_states"}
)
# Columns that must never be model inputs (§7.7 "Forbidden as input").
FORBIDDEN_INPUT_COLUMNS: frozenset[str] = frozenset(
    {
        "demand_m3s",
        "leak_m3s",
        "scenario_type",
        "is_anomalous",
        "fault_type",
        "location_id",
        "leak_area_m2",
        "true_value",
        "sensor_fault_kind",
        "realised_leak_peak_m3s",
    }
)

VALIDATION_CHECKS: tuple[str, ...] = (
    "converged",
    "no_negative_pressure_normal",
    "mass_balance",
    "tank_level_in_range",
    "all_canonical_elements_present",
    "no_nan",
    "pump_status_valid",
)


class ScenarioRow(_Model):
    """One row of the `scenarios` table (§7.5)."""

    simulation_id: str
    dataset_version: str
    network_id: str
    sensor_layout_id: str
    scenario_type: ScenarioType
    is_anomalous: bool
    has_sensor_fault: bool
    fault_type: FaultType | None = None
    location_kind: LocationKind | None = None
    location_id: str | None = None
    zone_id: str | None = None
    position: float | None = None
    leak_area_m2: float | None = None
    fault_start_s: int | None = None
    fault_end_s: int | None = None
    realised_leak_peak_m3s: float | None = None
    severity_bucket: SeverityBucket | None = None
    seed: int
    config_hash: str
    generator_version: str
    spec_json: str
    split: Split
    valid: bool = True


class ValidationLogRow(_Model):
    simulation_id: str
    seed: int
    check: str
    passed: bool
    detail: str = ""
    generator_version: str


# ---------------------------------------------------------------------------
# §7.6 Manifest
# ---------------------------------------------------------------------------


class Holdout(_Model):
    fault_locations_test_only: list[str]


class DatasetManifest(_Model):
    schema_version: str = SCHEMA_VERSION
    dataset_version: str
    created_utc: str
    git_sha: str
    generator_version: str
    wntr_version: str
    network_ids: list[str]
    sensor_layout_ids: list[str]
    dataset_seed: int
    n_requested: int
    n_valid: int
    n_failed: int
    counts_by_split: dict[str, int]
    counts_by_scenario_type: dict[str, int]
    holdout: Holdout
    timestep_s: int
    duration_s: int
    files: dict[str, str]


# ---------------------------------------------------------------------------
# §7.7 GraphSample — feature order is FROZEN (v1). Tensors live in ml/; this is the contract.
# ---------------------------------------------------------------------------

NODE_FEATURES_V1: tuple[str, ...] = (
    "elevation_m_z",
    "base_demand_lps_z",
    "is_junction",
    "is_tank",
    "is_reservoir",
    "obs_mask",
    "observed_pressure_m_z",
    "observed_pressure_lag1_z",
    "observed_pressure_lag3_z",
    "tod_sin",
    "tod_cos",
    "tank_level_m_z",
    "pump_on",
    "pump_flow_lps_z",
    "reservoir_head_m_z",
)

EDGE_FEATURES_V1: tuple[str, ...] = (
    "length_m_z",
    "diameter_m_z",
    "roughness_hw_z",
    "is_pump",
    "is_open",
    "observed_flow_lps_z",
    "flow_obs_mask",
)


class GraphSampleMeta(_Model):
    simulation_id: str
    sim_time_s: int
    hop_to_nearest_sensor: list[int]


class GraphSampleSpec(_Model):
    """Shape/metadata contract for a GraphSample (§7.7). Tensors are not serialised here."""

    n_nodes: int
    n_edges_directed: int
    node_features: tuple[str, ...] = NODE_FEATURES_V1
    edge_features: tuple[str, ...] = EDGE_FEATURES_V1
    node_order: list[str]
    meta: GraphSampleMeta | None = None


# ---------------------------------------------------------------------------
# §7.8 SensorWindow — the ONLY input type allowed into the inference pipeline
# ---------------------------------------------------------------------------


class WindowContext(_Model):
    tank_level_m: float | None
    pump_status: int | None = Field(ge=0, le=1)
    pump_flow_lps: float | None
    reservoir_head_m: float | None
    time_of_day_s: int


class WindowStep(_Model):
    sim_time_s: int
    pressure_m: dict[str, float | None]
    flow_lps: dict[str, float | None]
    context: WindowContext


class SensorWindow(_Model):
    schema_version: str = SCHEMA_VERSION
    network_id: str
    sensor_layout_id: str
    window: list[WindowStep] = Field(min_length=1, max_length=WINDOW_STEPS)


# ---------------------------------------------------------------------------
# §7.9 Predictor endpoint contract
# ---------------------------------------------------------------------------


class PredictorRequest(_Model):
    model_version: str
    mode: PredictorMode
    sensor_window: SensorWindow


class Reconstruction(_Model):
    pressure_m: dict[str, float]
    pressure_std_m: dict[str, float] = Field(default_factory=dict)


class LooEntry(_Model):
    predicted_m: float
    observed_m: float | None


class LooFlowEntry(_Model):
    """Leave-one-out for a flow sensor (backbone/1.1.0, §7.9)."""

    predicted_lps: float
    observed_lps: float | None


class PredictorResponse(_Model):
    model_version: str
    sim_time_s: int
    reconstruct: Reconstruction | None = None
    leave_one_out: dict[str, LooEntry] | None = None
    leave_one_out_flow: dict[str, LooFlowEntry] | None = None
    latency_ms: float


# ---------------------------------------------------------------------------
# §7.10 ResidualFrame and AnomalyResult
# ---------------------------------------------------------------------------


class ResidualFrame(_Model):
    sim_time_s: int
    residuals: dict[str, float]
    z: dict[str, float]
    instant_flags: list[str] = Field(default_factory=list)
    cumulative_flags: list[str] = Field(default_factory=list)


class AnomalyResult(_Model):
    status: AnomalyStatus
    anomaly_score: float
    first_flag_time_s: int | None = None
    confirmed_time_s: int | None = None
    detection_delay_steps: int | None = None
    suspected_class: str | None = None
    """T2 only; ``None`` in T1 (§7.10)."""
    class_probs: dict[str, float] | None = None
    driving_sensors: list[str] = Field(default_factory=list)
    residual_history_ref: str | None = None
    thresholds_version: str


# ---------------------------------------------------------------------------
# §7.11 LocalisationResult
# ---------------------------------------------------------------------------


class Candidate(_Model):
    rank: int = Field(ge=1)
    location_kind: LocationKind
    location_id: str
    zone_id: str
    score: float
    similarity: float


class ProbableZone(_Model):
    zone_id: str
    score: float


class LocalisationResult(_Model):
    method: str
    candidates: list[Candidate]
    probable_zone: ProbableZone
    signatures_version: str


# ---------------------------------------------------------------------------
# §7.12 Incident
# ---------------------------------------------------------------------------


class SensorDelta(_Model):
    sensor_id: str
    baseline_m: float
    observed_m: float
    pct_change: float


class FlowDelta(_Model):
    sensor_id: str
    baseline_lps: float
    observed_lps: float
    pct_change: float


class ContextSummary(_Model):
    time_of_day: str
    tank_level_m: float
    pump_status: PumpUiStatus


class Evidence(_Model):
    sensor_deltas: list[SensorDelta] = Field(default_factory=list)
    flow_deltas: list[FlowDelta] = Field(default_factory=list)
    context_summary: ContextSummary


class ModelVersions(_Model):
    predictor: str
    thresholds: str
    signatures: str


class Incident(_Model):
    """Handed to the agent. Contains NO ground truth (§7.12, §11)."""

    incident_id: str
    session_id: str
    created_sim_time_s: int
    network_id: str
    sensor_layout_id: str
    anomaly: AnomalyResult
    localisation: LocalisationResult | None = None
    """``None`` until T2c localisation is enabled (§7.11)."""
    evidence: Evidence
    model_versions: ModelVersions


# ---------------------------------------------------------------------------
# §7.13 Agent tools and AgentReport
# ---------------------------------------------------------------------------


class GetIncidentInput(_Model):
    incident_id: str


class GetSensorHistoryInput(_Model):
    sensor_id: str
    last_n_steps: int = Field(ge=1, le=60)


class SensorHistoryPoint(_Model):
    sim_time_s: int
    value: float | None
    unit: Literal["m", "L/s"]


class GetReconstructionInput(_Model):
    incident_id: str


class GetCandidateLocationsInput(_Model):
    incident_id: str
    top_k: int = Field(ge=1, le=5)


class GetNetworkElementInput(_Model):
    element_id: str


class RunWhatIfInput(_Model):
    action: WhatIfAction
    target_id: str
    horizon_steps: int = Field(ge=1, le=30)


class AffectedNode(_Model):
    node_id: str
    pressure_before_m: float
    pressure_after_m: float


class WhatIfResult(_Model):
    affected_nodes: list[AffectedNode]
    customers_below_20m: int


AGENT_TOOL_NAMES: tuple[str, ...] = (
    "get_incident",
    "get_sensor_history",
    "get_reconstruction",
    "get_candidate_locations",
    "get_network_element",
    "run_what_if",
    "submit_report",
)

AGENT_TOOL_INPUTS: dict[str, type[BaseModel]] = {
    "get_incident": GetIncidentInput,
    "get_sensor_history": GetSensorHistoryInput,
    "get_reconstruction": GetReconstructionInput,
    "get_candidate_locations": GetCandidateLocationsInput,
    "get_network_element": GetNetworkElementInput,
    "run_what_if": RunWhatIfInput,
}


class EvidenceClaim(_Model):
    claim: str
    source_tool: str
    fields: list[str] = Field(default_factory=list)


class RecommendedAction(_Model):
    priority: int = Field(ge=1)
    action: str
    rationale: str


class GroundingCheck(_Model):
    passed: bool
    unmatched_numbers: list[str] = Field(default_factory=list)


class AgentReport(_Model):
    incident_id: str
    headline: str
    what_happened: str
    why_suspicious: str
    where: str
    evidence: list[EvidenceClaim]
    recommended_actions: list[RecommendedAction]
    confidence: Confidence
    caveats: list[str] = Field(default_factory=list)
    grounding_check: GroundingCheck | None = None
    """Filled by the orchestrator (§9.6), never by the model."""
    generated_by: Literal["bedrock", "template"] | None = None
    """UI label source (§9.6 'template explanation'). Optional, additive."""


class SubmitReportInput(_Model):
    """`submit_report` tool input: AgentReport minus orchestrator-owned fields."""

    incident_id: str
    headline: str
    what_happened: str
    why_suspicious: str
    where: str
    evidence: list[EvidenceClaim]
    recommended_actions: list[RecommendedAction]
    confidence: Confidence
    caveats: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §7.14.1 Public orchestrator API
# ---------------------------------------------------------------------------


class HealthResponse(_Model):
    status: str
    sim: str
    predictor: HealthStatus
    agent: HealthStatus


class SessionResetRequest(_Model):
    seed: int | None = None


class SimStepRequest(_Model):
    steps: int = Field(ge=1, le=20)


class TapRequest(_Model):
    tap_id: str
    open: bool


class PipeFaultRequest(_Model):
    link_id: str
    kind: PipeFaultKind


class ValveRequest(_Model):
    valve_id: str
    open: bool


class ChallengeStartRequest(_Model):
    difficulty: Difficulty | None = None


class ChallengeStartResponse(_Model):
    challenge_id: str
    started_sim_time_s: int


class ChallengeStatusResponse(_Model):
    state: ChallengeState
    anomaly: AnomalyResult
    incident_id: str | None = None


class DiagnoseRequest(_Model):
    incident_id: str


class AskRequest(_Model):
    incident_id: str
    question: str


class AskResponse(_Model):
    answer: str
    grounding_check: GroundingCheck


class ViewNode(_Model):
    pressure_m: float
    head_m: float
    demand_lps: float
    is_sensor: bool
    sensor_id: str | None = None
    status: NodeUiStatus


class ViewLink(_Model):
    flow_lps: float
    velocity_ms: float
    status: LinkStatus
    direction: Literal[-1, 0, 1]
    visual_fault: VisualFault = VisualFault.NONE


class ViewTank(_Model):
    tank_id: str
    level_m: float
    level_pct: float


class ViewPump(_Model):
    pump_id: str
    flow_lps: float
    status: PumpUiStatus


class ViewTap(_Model):
    open: bool
    demand_lps: float


class ViewValve(_Model):
    open: bool


class ViewChallenge(_Model):
    active: bool
    challenge_id: str | None = None
    state: ChallengeState | None = None


class ViewEvent(_Model):
    sim_time_s: int
    text: str


class NetworkView(_Model):
    """UI-shaped state: units converted, hidden fields stripped (§7.14.1)."""

    session_id: str
    sim_time_s: int
    clock: str
    speed: Literal[1, 5, 20]
    nodes: dict[str, ViewNode]
    links: dict[str, ViewLink]
    tank: ViewTank
    pump: ViewPump
    taps: dict[str, ViewTap]
    valves: dict[str, ViewValve]
    network_status: NetworkStatus
    challenge: ViewChallenge
    events: list[ViewEvent] = Field(default_factory=list)


class RevealTruth(_Model):
    fault_type: FaultType
    location_kind: LocationKind
    location_id: str
    zone_id: str
    start_sim_time_s: int
    leak_peak_lps: float | None = None
    severity_bucket: SeverityBucket | None = None


class RevealAI(_Model):
    detected: bool
    detection_delay_s: int | None = None
    true_location_rank: int | None = None
    zone_correct: bool | None = None
    report_incident_id: str | None = None


class ChallengeReveal(_Model):
    truth: RevealTruth
    ai: RevealAI


# ---------------------------------------------------------------------------
# §7.14.2 Internal sim engine API
# ---------------------------------------------------------------------------


class SimHealthResponse(_Model):
    status: str
    wntr_version: str


class SimSessionCreateRequest(_Model):
    network_id: str
    seed: int
    timestep_s: int = INTERACTIVE_TIMESTEP_S


class SimSessionCreateResponse(_Model):
    session_id: str


class SimEventApplied(_Model):
    applied: bool


class SimAdvanceRequest(_Model):
    steps: int = Field(ge=1, le=20)


class ForkWhatIfRequest(_Model):
    events: list[SimEvent]
    horizon_steps: int = Field(ge=1, le=30)


# ---------------------------------------------------------------------------
# §7.15 Frontend state (mirrored for completeness; the TS twin is authoritative for UI)
# ---------------------------------------------------------------------------


class Selection(_Model):
    kind: Literal["node", "link", "tap", "valve"]
    id: str


class StoreChallenge(_Model):
    state: UiChallengeState
    incidentId: str | None = None  # noqa: N815 — mirrors TS field name in §7.15
    reveal: ChallengeReveal | None = None


class SimStore(_Model):
    topology: NetworkTopology | None
    view: NetworkView | None
    speed: Literal[1, 5, 20]
    running: bool
    selection: Selection | None
    challenge: StoreChallenge
    report: AgentReport | None


# ---------------------------------------------------------------------------
# Registry: section → model, used by contract tests and the TS mirror check.
# ---------------------------------------------------------------------------

SECTION_MODELS: dict[str, type[BaseModel]] = {
    "6.4": SensorLayout,
    "7.1": NetworkConfig,
    "7.2": ScenarioSpec,
    "7.3": SimEvent,
    "7.4": HydraulicSnapshot,
    "7.5": ScenarioRow,
    "7.6": DatasetManifest,
    "7.7": GraphSampleSpec,
    "7.8": SensorWindow,
    "7.9.request": PredictorRequest,
    "7.9.response": PredictorResponse,
    "7.10.residual": ResidualFrame,
    "7.10.anomaly": AnomalyResult,
    "7.11": LocalisationResult,
    "7.12": Incident,
    "7.13": AgentReport,
    "7.14.1.view": NetworkView,
    "7.14.1.reveal": ChallengeReveal,
    "7.15": SimStore,
}
