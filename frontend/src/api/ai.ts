// GET /api/ai/state, POST /api/ai/ack — AI monitor extension (BI-27, OPEN; not yet in @contracts).
// Everything here is derived server-side from the SensorWindow pipeline (BACKBONE §11): no ground truth.

export type AiStatus = "NORMAL" | "WATCH" | "ANOMALY";

export interface AiNode {
  ai_pressure_m: number;
  kind: "sensor" | "estimated";
  sensor_id: string | null;
  observed_m?: number | null;
  ai_without_sensor_m?: number;
  residual_m?: number | null;
  z?: number | null;
}

export interface AiFlow {
  link_id: string | null;
  observed_lps: number | null;
  ai_without_sensor_lps: number;
  residual_lps: number | null;
  z: number | null;
}

export interface AiNotification {
  id: string;
  sim_time_s: number;
  clock: string;
  status: AiStatus;
  anomaly_score: number;
  driving_sensors: string[];
  text: string;
  probable_zone: string | null;
}

export interface AiCandidate {
  rank: number;
  location_kind: "pipe" | "junction";
  location_id: string;
  zone_id: string;
  score: number;
  similarity: number;
  nodes: string[];
  links: string[];
}

export interface AiHighlight {
  label: string;
  method: string;
  signatures_version: string | null;
  probable_zone: string | null;
  zone_score: number | null;
  zone_nodes: string[];
  zone_links: string[];
  candidates: AiCandidate[];
  detected_at_s: number;
}

export interface AiState {
  enabled: boolean;
  error: string | null;
  label: string;
  models: { predictor: string | null; predictor_arch: string | null; detector: string | null; detector_kind: string | null; signatures: string | null };
  sim_time_s: number | null;
  steps_observed: number;
  status: AiStatus;
  anomaly_score: number;
  driving_sensors: string[];
  first_flag_time_s: number | null;
  confirmed_time_s: number | null;
  nodes: Record<string, AiNode>;
  flows: Record<string, AiFlow>;
  score_history: [number, number, AiStatus][];
  notifications: AiNotification[];
  highlight: AiHighlight | null;
}

export const AI_DISABLED: AiState = {
  enabled: false, error: "AI monitor is not available in mock mode", label: "BY AI",
  models: { predictor: null, predictor_arch: null, detector: null, detector_kind: null, signatures: null },
  sim_time_s: null, steps_observed: 0, status: "NORMAL", anomaly_score: 0, driving_sensors: [],
  first_flag_time_s: null, confirmed_time_s: null, nodes: {}, flows: {}, score_history: [], notifications: [], highlight: null,
};
