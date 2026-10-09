import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CityLink } from "../CityLink";

export function Telemetry(): JSX.Element {
  const wells = [
    ["// NETWORK", "EPA EPANET 2.2 tutorial", "|-- 8 nodes · 9 links · 2 loops --|"],
    ["// SENSING", "3 pressure + 2 flow", "|-- every other node stays hidden --|"],
    ["// PHYSICS", "WNTR 1.5, pressure-driven", "|-- 5-minute steps, real orifice leaks --|"],
    ["// EXPLANATION", "Evidence-only reports", "|-- every number comes from a reading --|"],
  ];
  return (
    <section aria-label="Telemetry summary" className="bg-panel blueprint-hatch-subtle border-y border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {wells.map(([l, v, f]) => (
          <div key={l} className="cad-corner-marks border-l-2 border-white pl-4 py-1">
            <div className="font-mono-cad text-[10px] text-paler">{l}</div>
            <div className="text-sm font-bold mt-1">{v}</div>
            <div className="font-mono-cad text-[9px] text-pale/70 mt-1">{f}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

type Status = "LIVE" | "BUILDING" | "NEXT";
interface Layer {
  n: string; tag: string; title: string; sub: string; body: string; status: Status; icon: string; wells: [string, string][];
}
const LAYERS: Layer[] = [
  { n: "01", tag: "SIMULATOR", title: "WNTR engine", sub: "aquaagent-sim", icon: "water", status: "LIVE",
    body: "The aquaagent-sim container runs the EPA tutorial network in 5-minute steps and answers the orchestrator over HTTP.",
    wells: [["STEP", "≈5 ms"], ["NETWORK", "8 nodes"], ["STATUS", "LIVE"]] },
  { n: "02", tag: "ORCHESTRATOR", title: "FastAPI service", sub: "session + firewall", icon: "hub", status: "LIVE",
    body: "Owns the session, applies taps, faults and valves, and strips hidden truth before anything reaches the browser.",
    wells: [["ROLE", "Session owner"], ["FIREWALL", "Truth stripped"], ["STATUS", "LIVE"]] },
  { n: "03", tag: "PREDICTOR", title: "Graph neural network", sub: "edge-aware GATv2", icon: "neurology", status: "LIVE",
    body: "Reconstructs the pressure at every node from five sensors and SCADA context. It reads the pipe graph, not node IDs, so it is not tied to one sensor layout.",
    wells: [["MODEL", "GNN · 160k"], ["TRAINED ON", "Normal days"], ["STATUS", "LIVE"]] },
  { n: "04", tag: "DETECTOR", title: "Detector + localiser", sub: "sensor-set net · network signatures", icon: "radar", status: "LIVE",
    body: "Listens to every 5-minute step for gaps between readings and the GNN's expectation, then matches the pattern against leaks simulated on the network map.",
    wells: [["OUTPUT", "3 states + area"], ["TUNED ON", "Validation only"], ["STATUS", "LIVE"]] },
  { n: "05", tag: "EXPLAINER", title: "Evidence report", sub: "grounded text", icon: "description", status: "NEXT",
    body: "A deterministic report from measured values today; an Amazon Bedrock agent with a grounding check next.",
    wells: [["TODAY", "Deterministic"], ["NEXT", "Bedrock agent"], ["STATUS", "NEXT"]] },
];

export function ArchitectureDeck(): JSX.Element {
  const [idx, setIdx] = useState(0);
  const [auto, setAuto] = useState(false);
  useEffect(() => { setAuto(!window.matchMedia("(prefers-reduced-motion: reduce)").matches); }, []);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % LAYERS.length), 3200);
    return () => clearInterval(t);
  }, [auto]);
  const L = LAYERS[idx];
  const statusClass = (s: Status): string => (s === "LIVE" ? "bg-white text-blueprint" : s === "BUILDING" ? "border border-white text-white" : "border border-dashed border-white/70 text-paler");

  return (
    <section id="architecture" className="py-16 sm:py-24 border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/30 pb-4 mb-8">
          <div>
            <div className="mono-label text-paler">[03] ARCHITECTURE</div>
            <h2 className="font-heading font-bold text-3xl sm:text-4xl mt-1">Five layers, honestly labelled</h2>
          </div>
          <button className="cad-btn-secondary h-10 px-3 flex items-center gap-2 mono-label" onClick={() => setAuto((a) => !a)} aria-pressed={auto}>
            <span aria-hidden="true" className="material-symbols-outlined">{auto ? "pause" : "play_arrow"}</span>{auto ? "AUTO-ADVANCE ON" : "AUTO-ADVANCE OFF"}
          </button>
        </div>

        <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label="Architecture layers">
          {LAYERS.map((l, i) => (
            <button key={l.n} role="tab" aria-selected={i === idx} onClick={() => { setIdx(i); setAuto(false); }}
              className={`px-3 py-2 font-mono-cad text-[11px] ${i === idx ? "cad-btn-active" : "cad-btn-secondary"}`}>[{l.n}] {l.tag}</button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {LAYERS.map((l, i) => (
            <button key={l.n} onClick={() => { setIdx(i); setAuto(false); }} aria-pressed={i === idx}
              className={`cad-panel blueprint-grid-subtle crosshair-corner text-left p-4 flex flex-col gap-3 transition-opacity ${i === idx ? "border-white" : "opacity-70"}`}>
              <div className="flex items-center justify-between">
                <span className="font-mono-cad text-[10px] text-paler">// LAYER {l.n}</span>
                <span className={`font-mono-cad text-[9px] px-2 py-0.5 ${statusClass(l.status)}`}>{l.status}</span>
              </div>
              <div className="w-10 h-10 border border-white/60 bg-well flex items-center justify-center"><span aria-hidden="true" className="material-symbols-outlined">{l.icon}</span></div>
              <div className="font-heading font-bold">{l.title}</div>
              <div className="font-mono-cad text-[10px] text-paler">{l.tag} · {l.sub}</div>
              <p className="text-xs text-pale leading-relaxed">{l.body}</p>
            </button>
          ))}
        </div>

        <div className="mt-6 border-2 border-white blueprint-hatch-subtle bg-panel p-5 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5" aria-live="polite">
          <div className="lg:col-span-7 flex gap-4">
            <div className="w-12 h-12 shrink-0 border border-white bg-well flex items-center justify-center"><span aria-hidden="true" className="material-symbols-outlined">{L.icon}</span></div>
            <div>
              <div className="font-mono-cad text-[10px] text-paler">// LAYER {L.n} · {L.tag}</div>
              <h3 className="font-heading font-bold text-xl">{L.title}</h3>
              <p className="text-pale text-sm mt-1">{L.body}</p>
            </div>
          </div>
          <div className="lg:col-span-5 grid grid-cols-3 gap-3">
            {L.wells.map(([k, v]) => (
              <div key={k} className="cad-well p-3">
                <div className="font-mono-cad text-[9px] text-paler">{k}</div>
                <div className="text-sm font-bold mt-1">{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

const MODELS: { tag: string; icon: string; name: string; what: string; how: string[]; result: [string, string][]; note: string }[] = [
  { tag: "PREDICTOR", icon: "hub", name: "Edge-aware graph attention network",
    what: "Estimates the pressure at every node — including the ones with no sensor — from 3 pressure sensors, 2 flow sensors and SCADA context.",
    how: ["GATv2 layers over the pipe graph (4 layers × 4 heads, residual, 160k parameters)", "Pipe length, diameter, roughness as edge features; no node IDs", "Trained on 181,851 normal 5-minute steps, random sensor placements"],
    result: [["Hidden-node error", "0.16 m MAE"], ["Nearest-sensor baseline", "1.93 m MAE"]],
    note: "Test split: 184 held-out simulations, normal states." },
  { tag: "DETECTOR", icon: "sensors", name: "Sensor-set temporal network",
    what: "Watches the last 2 hours of each sensor's residual (reading minus the GNN's leave-one-out estimate) and raises WATCH / ANOMALY.",
    how: ["Shared dilated temporal CNN per sensor + attention pooling over the sensor set (11k parameters)", "Knows sensor type, not identity — works if a sensor drops out", "Threshold chosen on validation data, frozen before test"],
    result: [["Caught: burst / large / medium", "94% / 45% / 30%"], ["False alarms on normal-operation sims", "4.4%"]],
    note: "Test split: 68 medium/large/burst faults, 90 operational sims. Small leaks mostly go unseen." },
  { tag: "LOCALISER", icon: "my_location", name: "Network-map signatures",
    what: "When the detector fires, simulates what a leak at every pipe and junction would look like on the known network, and finds the closest match.",
    how: ["168 physics signatures (14 locations × 3 sizes × 4 times of day)", "Same sensors, predictor and residuals as live", "No labelled leaks needed — any network with a map works"],
    result: [["Right pipe in top 3", "85%"], ["At locations never seen in training", "86%"]],
    note: "Test split, 68 medium/large/burst faults, measured with the true leak start; live estimates use the detector's start." },
];

export function Models(): JSX.Element {
  return (
    <section id="models" className="py-16 sm:py-24 border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="border-b border-white/30 pb-4 mb-8">
          <div className="mono-label text-paler">[04] THE MODELS</div>
          <h2 className="font-heading font-bold text-3xl sm:text-4xl mt-1">Three models, all measured</h2>
          <p className="text-pale text-sm mt-2 max-w-3xl">Every number below comes from our own held-out test simulations — synthetic data from the WNTR physics engine, never shown to the models during training or tuning.</p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {MODELS.map((m) => (
            <article key={m.tag} className="cad-panel crosshair-corner p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 border border-white/60 bg-well flex items-center justify-center"><span aria-hidden="true" className="material-symbols-outlined">{m.icon}</span></div>
                <div>
                  <div className="font-mono-cad text-[10px] text-paler">// {m.tag}</div>
                  <h3 className="font-heading font-bold text-lg leading-tight">{m.name}</h3>
                </div>
              </div>
              <p className="text-sm text-pale leading-relaxed">{m.what}</p>
              <ul className="flex flex-col gap-1.5">
                {m.how.map((h) => <li key={h} className="text-xs text-pale flex gap-2"><span aria-hidden="true" className="text-paler">—</span>{h}</li>)}
              </ul>
              <div className="grid grid-cols-2 gap-3 mt-auto">
                {m.result.map(([k, v]) => (
                  <div key={k} className="cad-well p-3">
                    <div className="font-mono-cad text-[9px] text-paler">{k.toUpperCase()}</div>
                    <div className="text-lg font-bold mt-1 font-mono-cad">{v}</div>
                  </div>
                ))}
              </div>
              <p className="font-mono-cad text-[10px] text-paler leading-snug">{m.note}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HonestLimits(): JSX.Element {
  const pods = [
    ["WHAT WE SHOW", "In our simulated network, five sensors plus a learned model of normal behaviour can flag hidden leaks — measured on held-out simulations.", "verified"],
    ["WHAT WE DON'T CLAIM", "This is not a real city. With five sensors it catches nearly every burst but misses about half of medium-to-large leaks and most small ones, and it names a probable area, not an exact pipe.", "gpp_maybe"],
    ["WHAT COMES NEXT", "Where to add the next sensor, a Bedrock explainer, larger networks, then real telemetry.", "arrow_circle_right"],
  ];
  return (
    <section id="limits" className="py-16 sm:py-24 border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="border-b border-white/30 pb-4 mb-8">
          <div className="mono-label text-paler">[05] HONEST LIMITS</div>
          <h2 className="font-heading font-bold text-3xl sm:text-4xl mt-1">What this is, and what it isn't</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {pods.map(([t, b, icon], i) => (
            <div key={t} className={`cad-panel crosshair-corner blueprint-hatch-subtle p-6 flex flex-col gap-3 ${i === 1 ? "border-2 border-white" : ""}`}>
              <span aria-hidden="true" className="material-symbols-outlined">{icon}</span>
              <div className="mono-label text-paler">// {t}</div>
              <p className={`${i === 1 ? "font-heading text-lg font-semibold" : "text-pale"} leading-relaxed`}>{b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Footer(): JSX.Element {
  return (
    <footer className="bg-panel blueprint-hatch-subtle border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex flex-col md:flex-row md:justify-between gap-2 font-mono-cad text-[10px] text-pale">
        <span>AQUAAGENT // FIND THE WATER NOBODY CAN SEE</span>
        <span>SIMULATED NETWORK · SYNTHETIC DATA // WNTR + EPANET 2.2</span>
        <CityLink className="underline">CITY VIEW (CONCEPT DEMO)</CityLink>
      </div>
    </footer>
  );
}
