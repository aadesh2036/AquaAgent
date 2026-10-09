// AI monitor panel (BI-27): detector status, live score, Simulated vs AI comparison, BY AI area.
// Renders API values only; the only arithmetic is the display difference (fmtDelta).
import { clockLabel } from "@units";
import type { AiState, AiStatus } from "../api/ai";
import { useSimStore } from "../state/simulationStore";
import { fmtDelta, fmtLps, fmtM, fmtNum } from "../lib/display";

export function AiChip({ label = "BY AI" }: { label?: string }): JSX.Element {
  return <span className="font-mono-cad text-[9px] font-bold px-1.5 py-0.5 bg-ai text-ai-ink tracking-wider whitespace-nowrap">{label}</span>;
}

function StatusChip({ s }: { s: AiStatus }): JSX.Element {
  const cls = s === "ANOMALY" ? "bg-alarm text-blueprint" : s === "WATCH" ? "border border-alarm text-alarm" : "border border-white/60 text-white";
  return <span className={`font-mono-cad text-[10px] font-bold px-2 py-0.5 ${cls}`}>{s}</span>;
}

function Sparkline({ ai }: { ai: AiState }): JSX.Element {
  const h = ai.score_history.slice(-96);
  const W = 300, H = 46;
  if (h.length < 2) return <div className="font-mono-cad text-[10px] text-paler h-[46px] flex items-center">waiting for steps…</div>;
  const x = (i: number): number => (i / (h.length - 1)) * W;
  const y = (p: number): number => H - 3 - p * (H - 6);
  const pts = h.map(([, p], i) => `${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[46px] block" role="img"
      aria-label={`Anomaly probability over the last ${h.length} steps; latest ${fmtNum(h[h.length - 1][1], 2)}`}>
      <rect x="0" y="0" width={W} height={H} fill="#075985" />
      <line x1="0" x2={W} y1={y(0.5)} y2={y(0.5)} stroke="#fff" strokeOpacity="0.2" strokeDasharray="3 3" />
      <polyline points={pts} fill="none" stroke="#fff" strokeWidth="1.5" />
      {h.map(([t, p, s], i) => s !== "NORMAL" && <circle key={t} cx={x(i)} cy={y(p)} r="2" fill="#fbbf24" />)}
    </svg>
  );
}

export function AiMonitor(): JSX.Element {
  const { ai, view, topology, ackAi, showAiArea, setShowAiArea, select } = useSimStore();
  if (!ai) return <section className="cad-panel p-4"><div className="mono-label text-paler">// AI MONITOR</div><p className="text-sm text-pale mt-2">Connecting to the AI monitor…</p></section>;
  if (!ai.enabled) {
    return (
      <section className="cad-panel p-4" aria-label="AI monitor">
        <div className="mono-label text-paler">// AI MONITOR</div>
        <p className="text-sm text-pale mt-2">{ai.error ?? "The AI monitor is off."}</p>
      </section>
    );
  }
  const hl = ai.highlight;
  const nodes = (topology?.nodes ?? []).filter((n) => ai.nodes[n.node_id]);
  return (
    <section className="cad-panel p-3 lg:shrink-0" aria-label="AI monitor" aria-live="polite">
      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,1.25fr)] gap-4">
        {/* 1 — status + live probability */}
        <div className="flex flex-col gap-2 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="mono-label text-paler">// AI MONITOR</div>
            <StatusChip s={ai.status} />
          </div>
          <p className="text-[11px] text-pale leading-snug">
            Checks every 5-min step using only S1–S3, F1–F2 + SCADA context. {ai.steps_observed} steps{ai.sim_time_s !== null ? `, last ${clockLabel(ai.sim_time_s)}` : ""}.
          </p>
          <div>
            <div className="flex justify-between font-mono-cad text-[10px] text-paler mb-1"><span>ANOMALY PROBABILITY</span><span>{fmtNum(ai.anomaly_score, 2)}</span></div>
            <Sparkline ai={ai} />
            <div className="font-mono-cad text-[10px] mt-1 h-3">{ai.driving_sensors.length > 0 ? `DRIVEN BY ${ai.driving_sensors.join(", ")}` : ""}</div>
          </div>
          <div className="font-mono-cad text-[9px] text-paler leading-snug">
            {ai.models.predictor_arch?.toUpperCase()} PREDICTOR {ai.models.predictor} · DETECTOR {ai.models.detector}{ai.models.signatures ? ` · ${ai.models.signatures}` : ""}
          </div>
        </div>

        {/* 2 — BY AI probable area */}
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2"><AiChip /><span className="mono-label text-paler">PROBABLE AREA</span></div>
          {hl ? (
            <div className="border border-ai p-2 flex flex-col gap-1">
              <div className="font-mono-cad text-[12px] font-bold">ZONE {hl.probable_zone ?? "—"}</div>
              <ol className="font-mono-cad text-[11px] flex flex-col gap-0.5">
                {hl.candidates.map((c) => (
                  <li key={c.rank}>
                    <button className="underline decoration-dotted text-left" onClick={() => select({ kind: c.location_kind === "pipe" ? "link" : "node", id: c.location_id })}>
                      #{c.rank} {c.location_kind} {c.location_id}
                    </button>
                    <span className="text-paler"> · {c.zone_id} · match {fmtNum(c.similarity, 2)}</span>
                  </li>
                ))}
              </ol>
              <p className="text-[10px] text-paler leading-snug">Sensor pattern matched against leaks simulated on the network map. A probable area, not an exact location.</p>
              <div className="flex gap-2 mt-1">
                <button className="cad-btn-secondary px-2 py-1 font-mono-cad text-[10px]" aria-pressed={showAiArea} onClick={() => setShowAiArea(!showAiArea)}>{showAiArea ? "HIDE AREA" : "SHOW AREA"}</button>
                <button className="cad-btn-primary px-2 py-1 font-mono-cad text-[10px] font-bold" onClick={() => void ackAi()}>ACKNOWLEDGE</button>
              </div>
            </div>
          ) : (
            <p className="text-[11px] text-pale leading-snug border border-dashed border-white/30 p-2">
              No anomaly confirmed. When the detector confirms one, the AI marks the probable area on the plan view in this colour, labelled BY AI.
            </p>
          )}
        </div>

        {/* 3 — simulated vs AI, every node + flow sensor */}
        <div className="min-w-0">
          <div className="mono-label text-paler mb-1">SIMULATED vs AI</div>
          <table className="w-full font-mono-cad text-[11px] leading-tight">
            <thead><tr className="text-paler text-[10px]"><th className="text-left font-normal">NODE</th><th className="text-right font-normal">SIM</th><th className="text-right font-normal">AI</th><th className="text-right font-normal">Δ</th></tr></thead>
            <tbody>
              {nodes.map((n) => {
                const a = ai.nodes[n.node_id];
                const sim = view?.nodes[n.node_id]?.pressure_m;
                const aiv = a.kind === "sensor" ? a.ai_without_sensor_m : a.ai_pressure_m;
                return (
                  <tr key={n.node_id} className="border-t border-white/10">
                    <td className="py-px"><button className="underline decoration-dotted" onClick={() => select({ kind: "node", id: n.node_id })}>{n.node_id}{a.sensor_id ? ` ${a.sensor_id}` : ""}</button></td>
                    <td className="text-right">{fmtM(sim)}</td>
                    <td className="text-right">{fmtM(aiv)}{a.kind === "sensor" ? "*" : ""}</td>
                    <td className="text-right text-pale">{fmtDelta(aiv, sim, "m", 2)}</td>
                  </tr>
                );
              })}
              {Object.entries(ai.flows).map(([fid, f]) => (
                <tr key={fid} className="border-t border-white/10">
                  <td className="py-px">{fid} pipe {f.link_id}</td>
                  <td className="text-right">{fmtLps(f.link_id ? view?.links[f.link_id]?.flow_lps : null)}</td>
                  <td className="text-right">{fmtLps(Math.abs(f.ai_without_sensor_lps))}*</td>
                  <td className="text-right text-pale">z {fmtNum(f.z, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[9px] text-paler mt-1 leading-snug">* at a sensor: the AI estimate with that sensor hidden — the gap the detector listens for.</p>
        </div>
      </div>
    </section>
  );
}
