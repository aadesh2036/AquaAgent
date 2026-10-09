import { useEffect, useState } from "react";
import { DetectionDrawing, PhysicsDrawing, ReconstructionDrawing, ReportDrawing, SparseDrawing } from "./Drawings";

interface Stage {
  n: string; layer: string; title: string; h3: string; body: string; chips: string[];
  caption: string; drawing: JSX.Element;
}

const STAGES: Stage[] = [
  { n: "01", layer: "PHYSICS LAYER", title: "Physics", h3: "A real hydraulic world",
    body: "WNTR solves pressure and flow across the network every five simulated minutes. Leaks are pressure-driven orifices, never edited numbers.",
    chips: ["MASS BALANCE CLOSED", "≈5 ms PER STEP"], caption: "FIG 01 // PIPE SECTION, SCHEMATIC", drawing: <PhysicsDrawing /> },
  { n: "02", layer: "SENSING LAYER", title: "Sparse sensing", h3: "Five readings, nothing else",
    body: "Only S1–S3 pressures, F1–F2 flows and what a utility already knows (tank level, pump state) leave the simulator. The leak's location never does.",
    chips: ["FIREWALL TESTED", "SENSOR NOISE σ 0.05 m"], caption: "FIG 02 // WHAT LEAVES THE SIMULATOR", drawing: <SparseDrawing /> },
  { n: "03", layer: "MODEL LAYER", title: "Reconstruction", h3: "What should it read right now?",
    body: "A model trained only on healthy days predicts each sensor from the other four, given the time of day, tank level and pump state.",
    chips: ["TRAINED ON NORMAL DAYS ONLY", "LEAVE-ONE-OUT"], caption: "FIG 03 // OBSERVED vs EXPECTED (ILLUSTRATIVE)", drawing: <ReconstructionDrawing /> },
  { n: "04", layer: "DECISION LAYER", title: "Detection", h3: "When reality stops fitting",
    body: "A small network watches the last two hours of every sensor's gap between reading and expectation. A sustained gap raises ANOMALY; the AI then matches the pattern against leaks simulated on the network map and marks the probable area.",
    chips: ["SENSOR-SET NETWORK", "FALSE ALARMS MEASURED", "AREA BY AI"], caption: "FIG 04 // ONE MEASURED FACT", drawing: <DetectionDrawing /> },
  { n: "05", layer: "REPORT LAYER", title: "Explanation & reveal", h3: "Evidence, then the answer",
    body: "AquaAgent writes what changed, why it is suspicious and what to check, using only measured values. Then the hidden fault is revealed next to the AI's answer.",
    chips: ["NO INVENTED NUMBERS", "GROUND TRUTH REVEAL"], caption: "FIG 05 // REPORT CARD, MOCK-UP", drawing: <ReportDrawing /> },
];

export function HowItWorks(): JSX.Element {
  const [idx, setIdx] = useState(0);
  const [auto, setAuto] = useState(false);

  useEffect(() => {
    // Autoplay is opt-in for users who prefer reduced motion.
    setAuto(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);
  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % STAGES.length), 6500);
    return () => clearInterval(t);
  }, [auto, idx]);

  const go = (i: number): void => setIdx((i + STAGES.length) % STAGES.length);

  return (
    <section id="how" className="py-16 sm:py-24 border-t border-white/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/30 pb-4 mb-8">
          <div>
            <div className="mono-label text-paler">[02] HOW IT WORKS</div>
            <h2 className="font-heading font-bold text-3xl sm:text-4xl mt-1">From pipe to proof, in five stages</h2>
          </div>
          <div className="flex items-center gap-2">
            <button className="cad-btn-secondary w-10 h-10 flex items-center justify-center" onClick={() => go(idx - 1)} aria-label="Previous stage"><span aria-hidden="true" className="material-symbols-outlined">arrow_back</span></button>
            <button className="cad-btn-secondary w-10 h-10 flex items-center justify-center" onClick={() => go(idx + 1)} aria-label="Next stage"><span aria-hidden="true" className="material-symbols-outlined">arrow_forward</span></button>
            <button className="cad-btn-secondary h-10 px-3 flex items-center gap-2 mono-label" onClick={() => setAuto((a) => !a)} aria-pressed={auto}>
              <span aria-hidden="true" className="material-symbols-outlined">{auto ? "pause" : "play_arrow"}</span>{auto ? "AUTOPLAY ON" : "AUTOPLAY OFF"}
            </button>
          </div>
        </div>

        <div className="relative mb-8 h-10 flex items-center" role="tablist" aria-label="Stages">
          <div className="absolute inset-x-4 top-1/2 h-1 bg-well border border-white/30">
            <div className="h-full bg-white transition-all duration-500" style={{ width: `${(idx / (STAGES.length - 1)) * 100}%` }} />
          </div>
          <div className="relative w-full flex justify-between">
            {STAGES.map((s, i) => (
              <button key={s.n} role="tab" aria-selected={i === idx} aria-label={`Stage ${s.n}: ${s.title}`} onClick={() => setIdx(i)}
                className={`w-8 h-8 font-mono-cad text-[11px] border ${i <= idx ? "bg-white text-blueprint border-white font-bold" : "bg-panel border-white/50"}`}>{s.n}</button>
            ))}
          </div>
        </div>

        <div className="overflow-hidden">
          <div className="timeline-slider" style={{ transform: `translateX(-${idx * 20}%)` }}>
            {STAGES.map((s, i) => (
              <div key={s.n} className={`timeline-slide-item px-1 ${i === idx ? "active-slide" : ""}`} {...(i === idx ? {} : { inert: "" })}>
                <div className="cad-panel crosshair-corner grid grid-cols-1 lg:grid-cols-12">
                  <div className="lg:col-span-4 p-5 sm:p-8 flex flex-col gap-4">
                    <div className="flex items-center gap-3">
                      <span className="bg-white text-blueprint font-mono-cad font-bold text-[11px] px-2 py-1">STAGE {s.n}</span>
                      <span className="mono-label text-paler">{s.layer}</span>
                    </div>
                    <div className="mono-label">{s.title}</div>
                    <h3 className="font-heading font-bold text-2xl">{s.h3}</h3>
                    <p className="text-pale text-sm leading-relaxed">{s.body}</p>
                    <div className="flex flex-wrap gap-2 mt-auto">{s.chips.map((c) => <span key={c} className="tag-chip">{c}</span>)}</div>
                  </div>
                  <div className="lg:col-span-8 p-3 sm:p-5">
                    <div className="cad-panel-dark blueprint-grid-subtle relative h-full min-h-[240px] sm:min-h-[320px] flex flex-col">
                      <div className="mono-label text-paler px-3 pt-2">{s.caption}</div>
                      <div className="flex-1 min-h-0 flex items-center">{s.drawing}</div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
