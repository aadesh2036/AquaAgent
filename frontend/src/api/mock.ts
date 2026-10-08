// Mock API (module 09): serves RECORDED fixtures only. Never computes hydraulics.
// With no fixtures recorded, values are NaN placeholders that render as "—" and the UI shows
// "MOCK DATA — fixtures not recorded yet". Record real ones with: node scripts/record_fixtures.mjs
import netconfig from "@netconfig";
import type { HealthResponse, NetworkTopology, NetworkView, PipeFaultKind } from "@contracts";
import type { AquaApi } from "./client";
import { DEFAULT_SENSOR_LAYOUT } from "../lib/display";

const fixtures = import.meta.glob("./fixtures/*.json", { eager: true, import: "default" }) as Record<string, unknown>;
const fixture = <T,>(name: string): T | null => (fixtures[`./fixtures/${name}.json`] as T | undefined) ?? null;

export const MOCK_HAS_FIXTURES = fixture<NetworkView>("view") !== null || fixture<NetworkView[]>("views_sequence") !== null;

function mockTopology(): NetworkTopology {
  const recorded = fixture<NetworkTopology>("topology");
  if (recorded) return recorded;
  const c = netconfig as unknown as NetworkTopology;
  return {
    schema_version: c.schema_version, network_id: c.network_id, nodes: c.nodes, links: c.links,
    zones: c.zones, taps: c.taps, valves: c.valves, sensor_layout: DEFAULT_SENSOR_LAYOUT,
  };
}

function placeholderView(topo: NetworkTopology): NetworkView {
  const tank = topo.nodes.find((n) => n.node_type === "tank");
  const pump = topo.links.find((l) => l.link_type === "pump");
  const sensorNode = new Map(DEFAULT_SENSOR_LAYOUT.pressure.map((p) => [p.node_id, p.sensor_id]));
  const nodes: NetworkView["nodes"] = {};
  for (const n of topo.nodes) {
    const sid = sensorNode.get(n.node_id) ?? null;
    nodes[n.node_id] = { pressure_m: NaN, head_m: NaN, demand_lps: NaN, is_sensor: sid !== null, sensor_id: sid, status: "ok" };
  }
  const links: NetworkView["links"] = {};
  for (const l of topo.links) {
    links[l.link_id] = { flow_lps: NaN, velocity_ms: NaN, status: l.initial_status ?? "OPEN", direction: 0, visual_fault: "NONE" };
  }
  const taps: NetworkView["taps"] = {};
  for (const t of topo.taps) taps[t.tap_id] = { open: true, demand_lps: NaN };
  const valves: NetworkView["valves"] = {};
  for (const v of topo.valves) valves[v.valve_id] = { open: true };
  return {
    session_id: "mock", sim_time_s: 0, clock: "--:--", speed: 1, nodes, links,
    tank: { tank_id: tank?.node_id ?? "8", level_m: NaN, level_pct: NaN },
    pump: { pump_id: pump?.link_id ?? "9", flow_lps: NaN, status: "ON" },
    taps, valves, network_status: "NORMAL", challenge: { active: false }, events: [],
  };
}

export function createMockApi(): AquaApi {
  const topo = mockTopology();
  // Recorded session (views_sequence.json): each step replays the next recorded frame, clamped at the end.
  const seq = fixture<NetworkView[]>("views_sequence");
  let idx = 0;
  const base = (): NetworkView => (seq ? seq[idx] : fixture<NetworkView>("view") ?? placeholderView(topo));
  let view: NetworkView = base();
  const fresh = (): NetworkView => structuredClone(view);
  const unavailable = (what: string) => (): Promise<never> => Promise.reject(new Error(`${what}: no recorded fixture`));
  const mockEvent = (text: string): void => {
    view = { ...view, events: [{ sim_time_s: view.sim_time_s, text: `(mock) ${text}` }, ...view.events] };
  };
  return {
    health: async (): Promise<HealthResponse> => ({ status: "mock", sim: "mock", predictor: "template", agent: "template" }),
    sessionReset: async () => { idx = 0; view = base(); return fresh(); },
    topology: async () => topo,
    state: async () => fresh(),
    step: async (steps) => {
      if (seq) { idx = Math.min(seq.length - 1, idx + steps); view = base(); }
      return fresh();
    },
    tap: async (id, open) => {
      view = { ...view, taps: { ...view.taps, [id]: { ...view.taps[id], open } } };
      mockEvent(`Tap ${id} ${open ? "opened" : "closed"}`);
      return fresh();
    },
    pipeFault: async (id, kind: PipeFaultKind) => {
      const link = view.links[id];
      const vf = kind === "LEAK" ? "LEAK" : kind === "BURST" ? "BURST" : "NONE";
      view = { ...view, links: { ...view.links, [id]: { ...link, visual_fault: vf, status: kind === "CLOSE" ? "CLOSED" : kind === "RESET" ? "OPEN" : link.status } } };
      mockEvent(`Pipe ${id}: ${kind}`);
      return fresh();
    },
    valve: async (id, open) => {
      view = { ...view, valves: { ...view.valves, [id]: { open } } };
      mockEvent(`Valve ${id} ${open ? "opened" : "closed"}`);
      return fresh();
    },
    challengeStart: unavailable("challenge"),
    challengeStatus: unavailable("challenge"),
    diagnose: unavailable("report"),
    reveal: unavailable("reveal"),
  };
}
