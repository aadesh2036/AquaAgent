import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

/** First-visit guided tour of /simulate. Targets are elements with `data-tour="<id>"`; a step without a
 *  target is a centred card. Skip / Esc ends the tour; the choice is remembered per browser (best effort). */

type Step = { target?: string; title: string; body: string };

const STEPS: Step[] = [
  {
    title: "Welcome to the simulator",
    body: "This is a live physics simulation of a small water network (the EPA tutorial network, run by WNTR in 5-minute steps). You can break pipes and watch the AI try to find the problem. This tour takes about a minute.",
  },
  {
    target: "plan",
    title: "Plan view",
    body: "Reservoir, pump, tank, pipes and junctions. S1–S3 (pressure) and F1–F2 (flow) are the only sensors the AI can see. Click any pipe or junction to inspect it; scroll to zoom, drag to pan.",
  },
  {
    target: "controls",
    title: "Run the clock",
    body: "Run or pause, pick a speed (1×, 5× or 20× = steps per second; one step is 5 simulated minutes) and reset the day.",
  },
  {
    target: "modes",
    title: "Modes",
    body: "EXPLORE to look around. BREAK IT to cause trouble: leaks, bursts, closed pipes and opened taps.",
  },
  {
    target: "inspector",
    title: "Inspector",
    body: "Details of what you selected, with the simulated value next to the AI's estimate. In BREAK IT, choose LEAK or BURST on the selected pipe; RESET repairs it.",
  },
  {
    target: "ai",
    title: "AI monitor",
    body: "The AI compares every sensor with what it expected and shows its anomaly probability. On ANOMALY it marks a probable area BY AI (dashed pink) and offers EXPLAIN WHY — a report written by Amazon Bedrock from the measured values.",
  },
  {
    target: "status",
    title: "Status bar",
    body: "Clock, live sensor readings, tank level and the network status at a glance.",
  },
  {
    title: "Try it",
    body: "Switch to BREAK IT, click pipe 5, press BURST, then run at 20×. In our runs the AI raised the alarm about an hour of simulated time later and named pipe 5 first. Reopen this guide any time with GUIDE in the header.",
  },
];

const STORAGE_KEY = "aquaagent.simTour.v1";
const PAD = 6;

export function tourSeen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "done";
  } catch {
    return false;
  }
}

function markSeen(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, "done");
  } catch {
    /* storage blocked: the tour simply shows again next visit */
  }
}

function findTarget(id: string | undefined): HTMLElement | null {
  if (!id) return null;
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(`[data-tour="${id}"]`))) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
}

type Box = { top: number; left: number; width: number; height: number };

export function Tour({ open, onClose }: { open: boolean; onClose: () => void }): JSX.Element | null {
  const [i, setI] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const [vw, setVw] = useState(() => window.innerWidth);
  const [vh, setVh] = useState(() => window.innerHeight);
  const nextRef = useRef<HTMLButtonElement>(null);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  const finish = useCallback(() => {
    markSeen();
    setI(0);
    onClose();
  }, [onClose]);

  const measure = useCallback(() => {
    setVw(window.innerWidth);
    setVh(window.innerHeight);
    const el = findTarget(step?.target);
    if (!el) return setBox(null);
    const r = el.getBoundingClientRect();
    setBox({ top: r.top - PAD, left: r.left - PAD, width: r.width + 2 * PAD, height: r.height + 2 * PAD });
  }, [step]);

  useLayoutEffect(() => {
    if (!open) return;
    const el = findTarget(step?.target);
    el?.scrollIntoView({ block: "nearest", inline: "nearest" });
    measure();
  }, [open, i, step, measure]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, measure]);

  useEffect(() => {
    if (open) nextRef.current?.focus();
  }, [open, i]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      else if (e.key === "ArrowRight" && !last) setI((n) => n + 1);
      else if (e.key === "ArrowLeft") setI((n) => Math.max(0, n - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, last, finish]);

  if (!open || !step) return null;

  // Card placement: phones → docked at the bottom; otherwise below / above / beside the target, clamped.
  const CARD_W = Math.min(360, vw - 32);
  const mobile = vw < 640;
  let card: CSSProperties;
  if (mobile) {
    card = { left: 16, right: 16, bottom: 16 };
  } else if (!box) {
    card = { left: (vw - CARD_W) / 2, top: Math.max(80, vh / 2 - 140), width: CARD_W };
  } else {
    const below = vh - (box.top + box.height);
    const left = Math.min(Math.max(16, box.left), vw - CARD_W - 16);
    if (below > 240) card = { left, top: box.top + box.height + 12, width: CARD_W };
    else if (box.top > 240) card = { left, bottom: vh - box.top + 12, width: CARD_W };
    else if (box.left > CARD_W + 32) card = { left: box.left - CARD_W - 12, top: Math.max(72, box.top), width: CARD_W };
    else card = { left: Math.min(box.left + box.width + 12, vw - CARD_W - 16), top: Math.max(72, box.top), width: CARD_W };
  }

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body">
      {box ? (
        <div aria-hidden="true" className="absolute border-2 border-white pointer-events-none transition-all duration-200 motion-reduce:transition-none"
          style={{ ...box, boxShadow: "0 0 0 9999px rgba(2, 30, 52, 0.74)" }} />
      ) : (
        <div aria-hidden="true" className="absolute inset-0" style={{ background: "rgba(2, 30, 52, 0.74)" }} />
      )}
      <div className="absolute cad-panel crosshair-corner p-4 flex flex-col gap-3 shadow-xl" style={card}>
        <div className="flex items-center justify-between gap-3">
          <span className="mono-label text-paler">GUIDE // {i + 1} / {STEPS.length}</span>
          <button onClick={finish} className="font-mono-cad text-[11px] underline text-pale hover:text-white">SKIP TOUR</button>
        </div>
        <h2 id="tour-title" className="font-heading font-bold text-lg leading-tight">{step.title}</h2>
        <p id="tour-body" className="text-sm text-pale">{step.body}</p>
        <div className="flex items-center gap-1" aria-hidden="true">
          {STEPS.map((_, k) => <span key={k} className={`h-1 flex-1 ${k <= i ? "bg-white" : "bg-white/25"}`} />)}
        </div>
        <div className="flex justify-between gap-2">
          <button onClick={() => setI((n) => Math.max(0, n - 1))} disabled={i === 0}
            className="cad-btn-secondary px-3 py-1.5 font-mono-cad text-[11px] font-bold disabled:opacity-40">← BACK</button>
          <button ref={nextRef} onClick={() => (last ? finish() : setI((n) => n + 1))}
            className="cad-btn-primary px-4 py-1.5 font-mono-cad text-[11px] font-bold">{last ? "START EXPLORING" : i === 0 ? "START TOUR →" : "NEXT →"}</button>
        </div>
      </div>
    </div>
  );
}
