// Inspector — selection details and actions. Renders API values only; no hydraulic math (P1).
import type { ReactNode } from "react";
import { useSimStore } from "../state/simulationStore";
import { fmtDelta, fmtLpm, fmtLps, fmtM, fmtMs, fmtNum, fmtPct } from "../lib/display";
import { AiChip } from "./AiMonitor";
import type { AiFlow, AiNode } from "../api/ai";

/** Side-by-side: what the simulator computed vs what the AI estimates from sparse sensors (BI-27). */
function Compare({ sim, ai, flow }: { sim: number | undefined; ai?: AiNode; flow?: AiFlow }): JSX.Element | null {
  if (!ai && !flow) return null;
  const isSensor = flow !== undefined || ai?.kind === "sensor";
  const aiVal = flow ? Math.abs(flow.ai_without_sensor_lps) : isSensor ? ai?.ai_without_sensor_m : ai?.ai_pressure_m;
  const fmtV = flow ? fmtLps : fmtM;
  const unit = flow ? "L/s" : "m";
  const z = flow ? flow.z : ai?.z;
  return (
    <div className="mt-2 border border-ai/70 p-2">
      <div className="flex items-center gap-2 mb-2"><span className="mono-label text-paler">SIMULATED vs AI</span><AiChip /></div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-well p-2">
          <div className="font-mono-cad text-[9px] text-paler">SIMULATION (PHYSICS)</div>
          <div className="font-mono-cad text-lg font-bold">{fmtV(sim)}</div>
        </div>
        <div className="bg-well p-2 border-l-2 border-ai">
          <div className="font-mono-cad text-[9px] text-paler">{isSensor ? "AI, THIS SENSOR HIDDEN" : "AI ESTIMATE"}</div>
          <div className="font-mono-cad text-lg font-bold">{fmtV(aiVal)}</div>
        </div>
      </div>
      <div className="flex justify-between font-mono-cad text-[10px] mt-1.5">
        <span className="text-paler">DIFFERENCE (AI − SIM)</span><span>{fmtDelta(aiVal, sim, unit, 2)}</span>
      </div>
      {isSensor && (
        <div className="flex justify-between font-mono-cad text-[10px]">
          <span className="text-paler">SENSOR READING · RESIDUAL z</span>
          <span>{flow ? fmtLps(flow.observed_lps === null ? null : Math.abs(flow.observed_lps)) : fmtM(ai?.observed_m)} · {fmtNum(z, 1)}</span>
        </div>
      )}
      <p className="text-[10px] text-paler leading-snug mt-1.5">
        {isSensor
          ? "The AI predicts this sensor from the other sensors only. A growing gap here is what the detector listens for."
          : "No sensor here. The AI reconstructs it from S1–S3, F1–F2 and SCADA context; it never sees this value."}
      </p>
    </div>
  );
}

export type SimMode = "explore" | "break" | "challenge";

const Row = ({ k, v }: { k: string; v: ReactNode }): JSX.Element => (
  <div className="flex justify-between gap-3 py-1 border-b border-white/15 text-sm">
    <span className="font-mono-cad text-[10px] text-paler uppercase self-center">{k}</span>
    <span className="font-mono-cad text-xs text-right">{v}</span>
  </div>
);

export function Inspector({ mode, onMode }: { mode: SimMode; onMode: (m: SimMode) => void }): JSX.Element {
  const { selection, view, topology, applyTap, applyPipeFault, applyValve, inFlight, ai } = useSimStore();
  const Shell = ({ children }: { children: ReactNode }): JSX.Element => (
    <section className="cad-panel p-4 flex flex-col gap-2" aria-label="Inspector" aria-live="polite">
      <div className="mono-label text-paler">// INSPECTOR{selection ? ` · ${selection.kind.toUpperCase()} ${selection.id}` : ""}</div>
      {children}
    </section>
  );
  if (!selection || !view || !topology) {
    return <Shell><p className="text-sm text-pale">Select a node, pipe, tap or valve on the drawing to inspect it.</p></Shell>;
  }
  const breakHint = (
    <button className="cad-btn-secondary px-3 py-2 font-mono-cad text-[11px] mt-2" onClick={() => onMode("break")}>SWITCH TO BREAK IT TO CHANGE THIS</button>
  );

  if (selection.kind === "node") {
    const n = view.nodes[selection.id];
    const cfg = topology.nodes.find((q) => q.node_id === selection.id);
    if (!n || !cfg) return <Shell><p className="text-sm text-pale">No data for node {selection.id}.</p></Shell>;
    return (
      <Shell>
        <div className="font-heading font-bold">{cfg.ui_label ?? `Node ${cfg.node_id}`}</div>
        <Row k="Type" v={cfg.node_type} />
        <Row k="Zone" v={cfg.zone_id ?? "—"} />
        <Row k="Pressure" v={fmtM(n.pressure_m)} />
        <Row k="Head" v={fmtM(n.head_m)} />
        <Row k="Demand" v={`${fmtLps(n.demand_lps)} · ${fmtLpm(n.demand_lps)}`} />
        <Row k="Status" v={<span className={n.status === "ok" ? "" : "text-alarm font-bold"}>{n.status.toUpperCase()}</span>} />
        <Row k="Sensor" v={n.is_sensor ? n.sensor_id ?? "yes" : "none"} />
        {cfg.node_type === "tank" && <Row k="Level" v={fmtPct(view.tank.level_pct)} />}
        {ai?.enabled && <Compare sim={n.pressure_m} ai={ai.nodes[selection.id]} />}
      </Shell>
    );
  }

  if (selection.kind === "link") {
    const l = view.links[selection.id];
    const cfg = topology.links.find((q) => q.link_id === selection.id);
    if (!l || !cfg) return <Shell><p className="text-sm text-pale">No data for link {selection.id}.</p></Shell>;
    const isPipe = cfg.link_type === "pipe";
    return (
      <Shell>
        <div className="font-heading font-bold">{isPipe ? "Pipe" : "Pump"} {cfg.link_id} <span className="font-mono-cad text-xs text-paler">{cfg.start_node} → {cfg.end_node}</span></div>
        <Row k="Flow" v={`${fmtLps(l.flow_lps)}`} />
        <Row k="Velocity" v={fmtMs(l.velocity_ms)} />
        <Row k="Status" v={l.status} />
        <Row k="Direction" v={l.direction === 1 ? "start → end" : l.direction === -1 ? "end → start" : "none"} />
        {l.visual_fault !== "NONE" && <Row k="Fault" v={<span className="text-alarm font-bold">{l.visual_fault}</span>} />}
        {ai?.enabled && (() => {
          const f = Object.values(ai.flows).find((q) => q.link_id === cfg.link_id);
          return f ? <Compare sim={l.flow_lps} flow={f} /> : null;
        })()}
        {isPipe && (mode === "break" ? (
          <div className="grid grid-cols-2 gap-2 mt-2">
            <button className="cad-btn-alarm py-2 font-mono-cad text-[11px] font-bold" disabled={inFlight} onClick={() => void applyPipeFault(cfg.link_id, "LEAK")}>LEAK</button>
            <button className="cad-btn-alarm py-2 font-mono-cad text-[11px] font-bold" disabled={inFlight} onClick={() => void applyPipeFault(cfg.link_id, "BURST")}>BURST</button>
            <button className="cad-btn-secondary py-2 font-mono-cad text-[11px] font-bold" disabled={inFlight} onClick={() => void applyPipeFault(cfg.link_id, "CLOSE")}>CLOSE</button>
            <button className="cad-btn-secondary py-2 font-mono-cad text-[11px] font-bold" disabled={inFlight} onClick={() => void applyPipeFault(cfg.link_id, "RESET")}>RESET</button>
          </div>
        ) : breakHint)}
      </Shell>
    );
  }

  if (selection.kind === "tap") {
    const t = view.taps[selection.id];
    const cfg = topology.taps.find((q) => q.tap_id === selection.id);
    if (!t || !cfg) return <Shell><p className="text-sm text-pale">No data for tap {selection.id}.</p></Shell>;
    return (
      <Shell>
        <div className="font-heading font-bold">Tap {cfg.tap_id} <span className="font-mono-cad text-xs text-paler">at node {cfg.node_id}</span></div>
        <Row k="State" v={t.open ? "OPEN" : "CLOSED"} />
        <Row k="Demand" v={`${fmtLps(t.demand_lps)} · ${fmtLpm(t.demand_lps)}`} />
        <button className="cad-btn-primary py-2 font-mono-cad text-[11px] font-bold mt-2" disabled={inFlight} onClick={() => void applyTap(cfg.tap_id, !t.open)}>{t.open ? "CLOSE TAP" : "OPEN TAP"}</button>
      </Shell>
    );
  }

  const v = view.valves[selection.id];
  const cfg = topology.valves.find((q) => q.valve_id === selection.id);
  if (!v || !cfg) return <Shell><p className="text-sm text-pale">No data for valve {selection.id}.</p></Shell>;
  return (
    <Shell>
      <div className="font-heading font-bold">Valve {cfg.valve_id} <span className="font-mono-cad text-xs text-paler">on pipe {cfg.link_id}</span></div>
      <Row k="State" v={v.open ? "OPEN" : "CLOSED"} />
      <p className="text-[11px] text-paler leading-snug">V1 is pipe 7's open/closed status, not an EPANET valve object.</p>
      {mode === "break"
        ? <button className="cad-btn-primary py-2 font-mono-cad text-[11px] font-bold mt-2" disabled={inFlight} onClick={() => void applyValve(cfg.valve_id, !v.open)}>{v.open ? "CLOSE VALVE" : "OPEN VALVE"}</button>
        : breakHint}
    </Shell>
  );
}
