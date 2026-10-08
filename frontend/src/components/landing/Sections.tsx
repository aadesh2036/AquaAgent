import { useEffect, useState } from "react";

export function Telemetry(): JSX.Element {
  const wells = [
    ["// NETWORK", "EPA EPANET 2.2 tutorial", "|-- 8 nodes · 9 links · 2 loops --|"],
    ["// SENSING", "3 pressure + 2 flow", "|-- every other node stays hiddden --|"],
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
    body: "Owns the session, applies taps, faults and valves, and strips hiddden truth before anything reaches the browser.",
    wells: [["ROLE", "Session owner"], ["FIREWALL", "Truth stripped"], ["STATUS", "LIVE"]] },
  { n: "03", tag: "PREDICTOR", title: "Healthy-state model", sub: "MLP", icon: "neurology", status: "BUILDING",
    body: "An MLP trained on normal days, locally first; SageMaker training and a real-time endpoint come next.",
    wells: [["MODEL", "MLP"], ["TRAINED ON", "Normal days"], ["STATUS", "BUILDING"]] },
  { n: "04", tag: "DETECTOR", title: "Residual dual threshold", sub: "NORMAL / WATCH / ANOMALY", icon: "radar", status: "BUILDING",
    body: "Turns reading-vs-expectation gaps into NORMAL, WATCH or ANOMALY, tuned on validation data only.",
    wells: [["OUTPUT", "3 states"], ["TUNED ON", "Validation only"], ["STATUS", "BUILDING"]] },
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
            <span className="material-symbols-outlined">{auto ? "pause" : "play_arrow"}</span>{auto ? "AUTO-ADVANCE ON" : "AUTO-ADVANCE OFF"}
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
              <div className="w-10 h-10 border border-white/60 bg-well flex items-center justify-center"><span className="material-symbols-outlined">{l.icon}</span></div>
              <div className="font-heading font-bold">{l.title}</div>
              <div className="font-mono-cad text-[10px] text-paler">{l.tag} · {l.sub}</div>
              <p className="text-xs text-pale leading-relaxed">{l.body}</p>
            </button>
          ))}
        </div>

        <div className="mt-6 border-2 border-white blueprint-hatch-subtle bg-panel p-5 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5" aria-live="polite">
          <div className="lg:col-span-7 flex gap-4">
            <div className="w-12 h-12 shrink-0 border border-white bg-well flex items-center justify-center"><span className="material-symbols-outlined">{L.icon}</span></div>
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

export function HonestLimits(): JSX.Element {
  const pods = [
    ["WHAT WE SHOW", "In our simulated network, five sensors plus a learned model of normal behaviour can flag hiddden leaks — measured on held-out simulations.", "verified"],
    ["WHAT WE DON'T CLAIM", "This is not a real city, it won't catch every leak, and three pressure sensors are not enough for every network.", "gpp_maybe"],
    ["WHAT COMES NEXT", "Model training on SageMaker, a Bedrock explainer, larger networks, then real telemetry.", "arrow_circle_right"],
  ];
  return (
    <section id="limits" className="py-16 sm:py-24 border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="border-b border-white/30 pb-4 mb-8">
          <div className="mono-label text-paler">[04] HONEST LIMITS</div>
          <h2 className="font-heading font-bold text-3xl sm:text-4xl mt-1">What this is, and what it isn't</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {pods.map(([t, b, icon], i) => (
            <div key={t} className={`cad-panel crosshair-corner blueprint-hatch-subtle p-6 flex flex-col gap-3 ${i === 1 ? "border-2 border-white" : ""}`}>
              <span className="material-symbols-outlined">{icon}</span>
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
      </div>
    </footer>
  );
}
