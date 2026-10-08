// Display-only helpers. Nothing here derives a hydraulic quantity (BACKBONE P1, §7.15).
import { fmt, lpsToLpm } from "@units";
import type { NetworkTopology, SensorLayout } from "@contracts";

/** sensors_default_v1 (BACKBONE §6.4): used when the topology response carries no sensor_layout. */
export const DEFAULT_SENSOR_LAYOUT: SensorLayout = {
  sensor_layout_id: "sensors_default_v1",
  pressure: [
    { sensor_id: "S1", node_id: "2" },
    { sensor_id: "S2", node_id: "4" },
    { sensor_id: "S3", node_id: "6" },
  ],
  flow: [
    { sensor_id: "F1", link_id: "3" },
    { sensor_id: "F2", link_id: "6" },
  ],
  context: ["tank_level_m", "pump_status", "pump_flow_lps", "reservoir_head_m", "time_of_day_s"],
};

export const layoutOf = (t: NetworkTopology | null): SensorLayout => t?.sensor_layout ?? DEFAULT_SENSOR_LAYOUT;

/** Animation period for the flow dashes: a display mapping of |flow| onto 0.6–6 s. null = no animation. */
export function flowAnimationDuration(lps: number | null | undefined): number | null {
  if (lps === null || lps === undefined || !Number.isFinite(lps) || lps === 0) return null;
  const REF_LPS = 40; // display reference only
  const t = Math.min(1, Math.abs(lps) / REF_LPS);
  const dur = 6 - t * 5.4;
  return Math.min(6, Math.max(0.6, dur));
}

export const fmtM = (v: number | undefined | null): string => fmt(v, "m", 1);
export const fmtLps = (v: number | undefined | null): string => fmt(v, "L/s", 1);
export const fmtLpm = (v: number | undefined | null): string =>
  v === undefined || v === null || !Number.isFinite(v) ? "— L/min" : fmt(lpsToLpm(v), "L/min", 0);
export const fmtMs = (v: number | undefined | null): string => fmt(v, "m/s", 2);
export const fmtPct = (v: number | undefined | null): string => fmt(v, "%", 0);
