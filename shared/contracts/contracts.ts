/**
 * AquaAgent data contracts — TypeScript twin of shared/contracts/models.py (BACKBONE §7).
 *
 * Hand-mirrored. Closed sets are `as const` arrays (not TS `enum`) so this file runs
 * under Node's type-stripping and Vite alike. Parity with the Python enums is checked by
 * `make contracts-test` (shared/tests/contracts.test.ts vs generated/enums.json).
 * Any change here requires a BACKBONE version bump (§17).
 */

export const CONTRACT_VERSION = "backbone/1.1.0";
export const SCHEMA_VERSION = "1.0";
export const WINDOW_STEPS = 12;
export const DATASET_TIMESTEP_S = 300;
export const INTERACTIVE_TIMESTEP_S = 300; // single cadence since backbone/1.1.0

// ---------------------------------------------------------------------------
// Closed sets
// ---------------------------------------------------------------------------

export const NodeType = ["junction", "reservoir", "tank"] as const;
export type NodeType = (typeof NodeType)[number];

export const LinkType = ["pipe", "pump", "valve"] as const;
export type LinkType = (typeof LinkType)[number];

export const LinkStatus = ["OPEN", "CLOSED", "ACTIVE"] as const;
export type LinkStatus = (typeof LinkStatus)[number];

export const LocationKind = ["pipe", "junction"] as const;
export type LocationKind = (typeof LocationKind)[number];

export const ScenarioType = [
  "NORMAL", "HIGH_DEMAND", "LOW_DEMAND", "DEMAND_SHIFT", "DEMAND_SPIKE", "VALVE_CLOSURE",
  "PARTIAL_VALVE", "PUMP_DEGRADE", "LOW_RESERVOIR", "SMALL_LEAK", "MEDIUM_LEAK", "LARGE_LEAK",
  "PIPE_BURST", "SENSOR_FAULT",
] as const;
export type ScenarioType = (typeof ScenarioType)[number];

export const FaultType = [
  "LEAK", "BURST", "VALVE_CLOSURE", "PARTIAL_VALVE", "PUMP_DEGRADE", "PUMP_TRIP",
  "LOW_RESERVOIR", "DEMAND_SPIKE", "DEMAND_SHIFT",
] as const;
export type FaultType = (typeof FaultType)[number];

export const SensorFaultKind = ["SPIKE", "BIAS", "DRIFT", "STUCK", "MISSING"] as const;
export type SensorFaultKind = (typeof SensorFaultKind)[number];

export const SeverityBucket = ["<5%", "5-15%", "15-25%", ">25%"] as const;
export type SeverityBucket = (typeof SeverityBucket)[number];

export const Split = ["train", "val", "test"] as const;
export type Split = (typeof Split)[number];

export const EventSource = ["user", "challenge", "system"] as const;
export type EventSource = (typeof EventSource)[number];

export const EventKind = ["TAP_SET", "PIPE_FAULT", "PIPE_RESET", "VALVE_SET", "SPEED", "RESET"] as const;
export type EventKind = (typeof EventKind)[number];

export const PredictorMode = ["reconstruct", "leave_one_out"] as const;
export type PredictorMode = (typeof PredictorMode)[number];

export const AnomalyStatus = ["NORMAL", "WATCH", "ANOMALY", "SENSOR_FAULT"] as const;
export type AnomalyStatus = (typeof AnomalyStatus)[number];

export const NetworkStatus = ["NORMAL", "WATCH", "ANOMALY"] as const;
export type NetworkStatus = (typeof NetworkStatus)[number];

export const NodeUiStatus = ["ok", "low", "critical"] as const;
export type NodeUiStatus = (typeof NodeUiStatus)[number];

export const VisualFault = ["NONE", "LEAK", "BURST"] as const;
export type VisualFault = (typeof VisualFault)[number];

export const PumpUiStatus = ["ON", "OFF"] as const;
export type PumpUiStatus = (typeof PumpUiStatus)[number];

export const PipeFaultKind = ["LEAK", "BURST", "CLOSE", "RESET"] as const;
export type PipeFaultKind = (typeof PipeFaultKind)[number];

export const Difficulty = ["small", "medium", "large"] as const;
export type Difficulty = (typeof Difficulty)[number];

export const ChallengeState = ["RUNNING", "DETECTED", "TIMEOUT"] as const;
export type ChallengeState = (typeof ChallengeState)[number];

export const UiChallengeState = ["IDLE", "RUNNING", "DETECTED", "REVEALED"] as const;
export type UiChallengeState = (typeof UiChallengeState)[number];

export const Confidence = ["HIGH", "MEDIUM", "LOW"] as const;
export type Confidence = (typeof Confidence)[number];

export const WhatIfAction = ["isolate_pipe", "close_valve", "reduce_pump_speed"] as const;
export type WhatIfAction = (typeof WhatIfAction)[number];

export const HealthStatus = ["ok", "degraded", "template"] as const;
export type HealthStatus = (typeof HealthStatus)[number];

export const NODE_FEATURES_V1 = [
  "elevation_m_z", "base_demand_lps_z", "is_junction", "is_tank", "is_reservoir", "obs_mask",
  "observed_pressure_m_z", "observed_pressure_lag1_z", "observed_pressure_lag3_z", "tod_sin",
  "tod_cos", "tank_level_m_z", "pump_on", "pump_flow_lps_z", "reservoir_head_m_z",
] as const;

export const EDGE_FEATURES_V1 = [
  "length_m_z", "diameter_m_z", "roughness_hw_z", "is_pump", "is_open", "observed_flow_lps_z",
  "flow_obs_mask",
] as const;

export const AGENT_TOOL_NAMES = [
  "get_incident", "get_sensor_history", "get_reconstruction", "get_candidate_locations",
  "get_network_element", "run_what_if", "submit_report",
] as const;

// ---------------------------------------------------------------------------
// §6.4 Sensor layout
// ---------------------------------------------------------------------------

export interface SensorLayout {
  sensor_layout_id: string;
  pressure: { sensor_id: string; node_id: string }[];
  flow: { sensor_id: string; link_id: string }[];
  context: string[];
}

// ---------------------------------------------------------------------------
// §7.1 NetworkConfig
// ---------------------------------------------------------------------------

export interface NodeConfig {
  node_id: string;
  node_type: NodeType;
  elevation_m: number;
  base_demand_m3s?: number | null;
  x: number;
  y: number;
  ui_label?: string | null;
  zone_id?: string | null;
}

export interface LinkConfig {
  link_id: string;
  link_type: LinkType;
  start_node: string;
  end_node: string;
  length_m?: number | null;
  diameter_m?: number | null;
  roughness_hw?: number | null;
  initial_status?: LinkStatus;
  zone_id?: string | null;
}

export interface Zone { zone_id: string; name: string }

export interface HydraulicsConfig {
  demand_model: "PDD" | "DD";
  required_pressure_m: number;
  minimum_pressure_m: number;
  headloss: "H-W" | "D-W" | "C-M";
  tank_init_level_m: number;
}

export interface TapDef { tap_id: string; node_id: string }
export interface ValveDef { valve_id: string; link_id: string; impl: "pipe_status" }

export interface NetworkConfig {
  schema_version: string;
  network_id: string;
  source: string;
  inp_path?: string | null;
  nodes: NodeConfig[];
  links: LinkConfig[];
  zones: Zone[];
  hydraulics: HydraulicsConfig;
  taps: TapDef[];
  valves: ValveDef[];
}

/** GET /network/topology — NetworkConfig minus hydraulics internals (§7.14.1). */
export interface NetworkTopology {
  schema_version: string;
  network_id: string;
  nodes: NodeConfig[];
  links: LinkConfig[];
  zones: Zone[];
  taps: TapDef[];
  valves: ValveDef[];
  sensor_layout?: SensorLayout | null;
}

// ---------------------------------------------------------------------------
// §7.2 ScenarioSpec
// ---------------------------------------------------------------------------

export interface DemandProfile {
  profile_id: string;
  night_min: number;
  morning_peak_mult: number;
  morning_peak_h: number;
  evening_peak_mult: number;
  evening_peak_h: number;
  node_multipliers?: Record<string, number>;
  noise_sigma: number;
  weekend?: boolean;
  global_mult?: number | null;
}

export interface Operations {
  reservoir_head_offset_m?: number;
  pump_speed?: number;
  tank_init_level_m: number;
}

export interface FaultSpec {
  fault_id: string;
  fault_type: FaultType;
  location_kind?: LocationKind | null;
  location_id?: string | null;
  position?: number | null;
  leak_area_m2?: number | null;
  discharge_coeff?: number | null;
  start_s: number;
  end_s?: number | null;
  params?: Record<string, unknown> | null;
}

export interface SensorFaultSpec {
  kind: SensorFaultKind;
  sensor_id: string;
  start_s: number;
  end_s?: number | null;
  magnitude?: number | null;
}

export interface NoiseSpec { pressure_sigma_m: number; flow_sigma_lps: number; missing_rate: number }

export interface ScenarioSpec {
  schema_version: string;
  simulation_id: string;
  network_id: string;
  sensor_layout_id: string;
  seed: number;
  duration_s: number;
  timestep_s: number;
  demand_profile: DemandProfile;
  operations: Operations;
  scenario_type: ScenarioType;
  faults: FaultSpec[];
  sensor_faults: SensorFaultSpec[];
  noise: NoiseSpec;
  config_hash: string;
  generator_version: string;
}

// ---------------------------------------------------------------------------
// §7.3 SimEvent
// ---------------------------------------------------------------------------

export interface SimEvent {
  event_id: string;
  sim_time_s: number;
  source: EventSource;
  kind: EventKind;
  target_id?: string | null;
  params?: Record<string, unknown>;
  hidden?: boolean;
}

// ---------------------------------------------------------------------------
// §7.4 HydraulicSnapshot
// ---------------------------------------------------------------------------

export interface NodeState {
  pressure_m: number; head_m: number; demand_m3s: number; base_demand_m3s: number; leak_m3s?: number;
}
export interface LinkState { flow_m3s: number; velocity_ms: number; headloss_m: number; status: LinkStatus }
export interface TankState { level_m: number; head_m: number; volume_m3: number; net_inflow_m3s: number }
export interface PumpState { flow_m3s: number; head_gain_m: number; status: LinkStatus }

export interface HydraulicSnapshot {
  schema_version: string;
  network_id: string;
  sim_time_s: number;
  converged: boolean;
  nodes: Record<string, NodeState>;
  links: Record<string, LinkState>;
  tanks?: Record<string, TankState>;
  pumps?: Record<string, PumpState>;
  hidden?: { leak_nodes: Record<string, { leak_m3s: number }> } | null;
}

// ---------------------------------------------------------------------------
// §7.6 Manifest
// ---------------------------------------------------------------------------

export interface DatasetManifest {
  schema_version: string;
  dataset_version: string;
  created_utc: string;
  git_sha: string;
  generator_version: string;
  wntr_version: string;
  network_ids: string[];
  sensor_layout_ids: string[];
  dataset_seed: number;
  n_requested: number;
  n_valid: number;
  n_failed: number;
  counts_by_split: Record<string, number>;
  counts_by_scenario_type: Record<string, number>;
  holdout: { fault_locations_test_only: string[] };
  timestep_s: number;
  duration_s: number;
  files: Record<string, string>;
}

// ---------------------------------------------------------------------------
// §7.8 SensorWindow
// ---------------------------------------------------------------------------

export interface WindowContext {
  tank_level_m: number | null;
  pump_status: 0 | 1 | null;
  pump_flow_lps: number | null;
  reservoir_head_m: number | null;
  time_of_day_s: number;
}

export interface WindowStep {
  sim_time_s: number;
  pressure_m: Record<string, number | null>;
  flow_lps: Record<string, number | null>;
  context: WindowContext;
}

export interface SensorWindow {
  schema_version: string;
  network_id: string;
  sensor_layout_id: string;
  window: WindowStep[];
}

// ---------------------------------------------------------------------------
// §7.9 Predictor
// ---------------------------------------------------------------------------

export interface PredictorRequest { model_version: string; mode: PredictorMode; sensor_window: SensorWindow }

export interface PredictorResponse {
  model_version: string;
  sim_time_s: number;
  reconstruct?: {
    pressure_m: Record<string, number>;
    pressure_std_m?: Record<string, number>;
  } | null;
  leave_one_out?: Record<string, { predicted_m: number; observed_m: number | null }> | null;
  /** backbone/1.1.0: LOO for flow sensors F1/F2. */
  leave_one_out_flow?: Record<string, { predicted_lps: number; observed_lps: number | null }> | null;
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// §7.10 – §7.12
// ---------------------------------------------------------------------------

export interface ResidualFrame {
  sim_time_s: number;
  residuals: Record<string, number>;
  z: Record<string, number>;
  instant_flags: string[];
  cumulative_flags: string[];
}

export interface AnomalyResult {
  status: AnomalyStatus;
  anomaly_score: number;
  first_flag_time_s?: number | null;
  confirmed_time_s?: number | null;
  detection_delay_steps?: number | null;
  suspected_class?: string | null;
  class_probs?: Record<string, number> | null;
  driving_sensors: string[];
  residual_history_ref?: string | null;
  thresholds_version: string;
}

export interface Candidate {
  rank: number;
  location_kind: LocationKind;
  location_id: string;
  zone_id: string;
  score: number;
  similarity: number;
}

export interface LocalisationResult {
  method: string;
  candidates: Candidate[];
  probable_zone: { zone_id: string; score: number };
  signatures_version: string;
}

export interface Incident {
  incident_id: string;
  session_id: string;
  created_sim_time_s: number;
  network_id: string;
  sensor_layout_id: string;
  anomaly: AnomalyResult;
  /** null until T2c localisation is enabled. */
  localisation?: LocalisationResult | null;
  evidence: {
    sensor_deltas: { sensor_id: string; baseline_m: number; observed_m: number; pct_change: number }[];
    flow_deltas: { sensor_id: string; baseline_lps: number; observed_lps: number; pct_change: number }[];
    context_summary: { time_of_day: string; tank_level_m: number; pump_status: PumpUiStatus };
  };
  model_versions: { predictor: string; thresholds: string; signatures: string };
}

// ---------------------------------------------------------------------------
// §7.13 AgentReport
// ---------------------------------------------------------------------------

export interface GroundingCheck { passed: boolean; unmatched_numbers: string[] }

export interface AgentReport {
  incident_id: string;
  headline: string;
  what_happened: string;
  why_suspicious: string;
  where: string;
  evidence: { claim: string; source_tool: string; fields: string[] }[];
  recommended_actions: { priority: number; action: string; rationale: string }[];
  confidence: Confidence;
  caveats: string[];
  grounding_check?: GroundingCheck | null;
  generated_by?: "bedrock" | "template" | null;
}

export interface WhatIfResult {
  affected_nodes: { node_id: string; pressure_before_m: number; pressure_after_m: number }[];
  customers_below_20m: number;
}

// ---------------------------------------------------------------------------
// §7.14.1 Public API
// ---------------------------------------------------------------------------

export interface HealthResponse { status: string; sim: string; predictor: HealthStatus; agent: HealthStatus }
export interface SessionResetRequest { seed?: number | null }
export interface SimStepRequest { steps: number }
export interface TapRequest { tap_id: string; open: boolean }
export interface PipeFaultRequest { link_id: string; kind: PipeFaultKind }
export interface ValveRequest { valve_id: string; open: boolean }
export interface ChallengeStartRequest { difficulty?: Difficulty | null }
export interface ChallengeStartResponse { challenge_id: string; started_sim_time_s: number }
export interface ChallengeStatusResponse { state: ChallengeState; anomaly: AnomalyResult; incident_id?: string | null }
export interface DiagnoseRequest { incident_id: string }
export interface AskRequest { incident_id: string; question: string }
export interface AskResponse { answer: string; grounding_check: GroundingCheck }

export interface ViewNode {
  pressure_m: number;
  head_m: number;
  demand_lps: number;
  is_sensor: boolean;
  sensor_id?: string | null;
  status: NodeUiStatus;
}

export interface ViewLink {
  flow_lps: number;
  velocity_ms: number;
  status: LinkStatus;
  direction: -1 | 0 | 1;
  visual_fault: VisualFault;
}

export interface NetworkView {
  session_id: string;
  sim_time_s: number;
  clock: string;
  speed: 1 | 5 | 20;
  nodes: Record<string, ViewNode>;
  links: Record<string, ViewLink>;
  tank: { tank_id: string; level_m: number; level_pct: number };
  pump: { pump_id: string; flow_lps: number; status: PumpUiStatus };
  taps: Record<string, { open: boolean; demand_lps: number }>;
  valves: Record<string, { open: boolean }>;
  network_status: NetworkStatus;
  challenge: { active: boolean; challenge_id?: string | null; state?: ChallengeState | null };
  events: { sim_time_s: number; text: string }[];
}

export interface ChallengeReveal {
  truth: {
    fault_type: FaultType;
    location_kind: LocationKind;
    location_id: string;
    zone_id: string;
    start_sim_time_s: number;
    leak_peak_lps?: number | null;
    severity_bucket?: SeverityBucket | null;
  };
  ai: {
    detected: boolean;
    detection_delay_s?: number | null;
    true_location_rank?: number | null;
    zone_correct?: boolean | null;
    report_incident_id?: string | null;
  };
}

// ---------------------------------------------------------------------------
// §7.15 Frontend store
// ---------------------------------------------------------------------------

export type SimStore = {
  topology: NetworkTopology | null;
  view: NetworkView | null;
  speed: 1 | 5 | 20;
  running: boolean;
  selection: { kind: "node" | "link" | "tap" | "valve"; id: string } | null;
  challenge: { state: UiChallengeState; incidentId?: string; reveal?: ChallengeReveal };
  report: AgentReport | null;
};

/** Every closed set, keyed by the Python enum class name — used by the parity test. */
export const ENUMS: Record<string, readonly string[]> = {
  NodeType, LinkType, LinkStatus, LocationKind, ScenarioType, FaultType, SensorFaultKind,
  SeverityBucket, Split, EventSource, EventKind, PredictorMode, AnomalyStatus, NetworkStatus,
  NodeUiStatus, VisualFault, PumpUiStatus, PipeFaultKind, Difficulty, ChallengeState,
  UiChallengeState, Confidence, WhatIfAction, HealthStatus,
};
