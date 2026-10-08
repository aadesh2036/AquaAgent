// /city — CONCEPT DEMO. Illustrative layout and values only; nothing here is live data or a real utility.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as RPointerEvent, WheelEvent as RWheelEvent } from "react";
import { Link } from "react-router-dom";
import { Header } from "../components/Header";

const MW = 1440, MH = 820;
const AMBER = "#fbbf24", CRIT = "#f87171", WELL = "#075985";
type Layer = "full" | "pipes" | "loss";
const LAYERS: [Layer, string][] = [["full", "FULL"], ["pipes", "PIPES ONLY"], ["loss", "PRESSURE LOSS"]];

const SPINE = "M70 330 L300 330 C420 330 470 270 600 270 L860 270 C960 270 1000 340 1100 340 L1370 340";
const FEEDERS = [
  "M460 303 L460 140 L760 140 L760 270",
  "M300 330 L300 500 L640 500 L640 430 L860 430 L860 270",
  "M1100 340 L1100 180 L1330 180 L1330 340",
  "M1000 340 L1000 560 L1250 560 L1250 340",
];
const SECTORS: { id: string; name: string; pts: string; lx: number; ly: number }[] = [
  { id: "A", name: "OLD TOWN", pts: "60,100 480,100 480,440 60,440", lx: 74, ly: 124 },
  { id: "B", name: "MARKET QUARTER", pts: "480,100 900,100 900,440 480,440", lx: 494, ly: 124 },
  { id: "C", name: "HILL DISTRICT", pts: "900,100 1380,100 1380,440 900,440", lx: 914, ly: 124 },
  { id: "D", name: "GARDEN ESTATE", pts: "60,440 480,440 480,600 60,600", lx: 74, ly: 464 },
  { id: "E", name: "RIVERSIDE", pts: "480,440 900,440 900,600 480,600", lx: 494, ly: 464 },
  { id: "F", name: "INDUSTRIAL PARK", pts: "900,440 1380,440 1380,600 900,600", lx: 914, ly: 464 },
];
const RIVER = "M0 610 C220 580 400 680 640 650 S1000 700 1440 630 L1440 780 C1000 820 760 740 600 770 S200 700 0 760 Z";
const DMA: [number, number][] = [[460, 200], [610, 140], [760, 205], [300, 420], [470, 500], [640, 465], [860, 350], [1100, 260], [1215, 180], [1330, 260], [1000, 450], [1120, 560], [1250, 450]];

interface Incident {
  id: string; x: number; y: number; px: number; py: number; color: string; tag: string; badge: string; title: string; zone: string;
  cells: [string, string][]; body: string;
}
const INCIDENTS: Incident[] = [
  { id: "A", x: 560, y: 500, px: 600, py: 540, color: AMBER, tag: "INCIDENT A · ANOMALY", badge: "ANOMALY (EXAMPLE)", title: "Pressure below expected on a southern feeder",
    zone: "Probable leak zone: Riverside (sample layout)",
    cells: [["PRESSURE BELOW EXPECTED", "≈2.4 m · illustrative"], ["EVIDENCE", "S-sensor residuals · illustrative"]],
    body: "Concept card. In the working simulator this card would list what changed, why it is suspicious and what to check, using only measured values. The numbers shown here are placeholders." },
  { id: "B", x: 1215, y: 180, px: 1244, py: 110, color: CRIT, tag: "INCIDENT B · CRITICAL", badge: "CRITICAL (EXAMPLE)", title: "Sustained shortfall on a northern loop",
    zone: "Probable leak zone: Hill District (sample layout)",
    cells: [["PRESSURE BELOW EXPECTED", "≈5.1 m · illustrative"], ["EVIDENCE", "S-sensor residuals · illustrative"]],
    body: "Concept card showing the one 'critical' example. Real incidents come from the detector, which is still being trained; none of this is live." },
];

export function City(): JSX.Element {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 560 });
  const [v, setV] = useState({ k: 1, tx: 0, ty: 0 });
  const [layer, setLayer] = useState<Layer>("full");
  const [open, setOpen] = useState<Incident | null>(null);
  const [cursor, setCursor] = useState<[number, number]>([0, 0]);
  const [measured, setMeasured] = useState(false);
  const [fitted, setFitted] = useState(false);
  const pts = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ moved: boolean; sx: number; sy: number } | null>(null);
  const pinch = useRef(0);

  const f = Math.min(size.w / MW, size.h / MH); // fit scale (layout only)
  const fit = useCallback((): { k: number; tx: number; ty: number } => {
    const k = size.w < 640 ? 2.2 : 1; // phones start zoomed in on the centre of the map
    return { k, tx: (size.w - MW * f * k) / 2, ty: (size.h - MH * f * k) / 2 };
  }, [size, f]);

  useEffect(() => {
    const el = box.current; if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el); setSize({ w: el.clientWidth, h: el.clientHeight }); setMeasured(true);
    return () => ro.disconnect();
  }, []);
  useEffect(() => { if (!fitted && measured) { setV(fit()); setFitted(true); } }, [fit, fitted, measured]);

  const zoomAt = useCallback((factor: number, cx: number, cy: number) => {
    setV((o) => {
      const k = Math.min(6, Math.max(0.6, o.k * factor));
      const r = k / o.k;
      return { k, tx: cx - (cx - o.tx) * r, ty: cy - (cy - o.ty) * r };
    });
  }, []);
  const zoomCenter = (factor: number): void => zoomAt(factor, size.w / 2, size.h / 2);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setOpen(null);
      else if (e.key === "+" || e.key === "=") zoomAt(1.25, size.w / 2, size.h / 2);
      else if (e.key === "-" || e.key === "_") zoomAt(0.8, size.w / 2, size.h / 2);
      else if (e.key === "0") setV(fit());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fit, size, zoomAt]);

  const onWheel = (e: RWheelEvent): void => {
    const r = box.current!.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top);
  };
  const onDown = (e: RPointerEvent): void => {
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    drag.current = { moved: false, sx: e.clientX, sy: e.clientY };
    if (pts.current.size === 2) { const [a, b] = [...pts.current.values()]; pinch.current = Math.hypot(a.x - b.x, a.y - b.y); }
  };
  const onMove = (e: RPointerEvent): void => {
    const r = box.current!.getBoundingClientRect();
    const mk = f * v.k;
    setCursor([Math.round((e.clientX - r.left - v.tx) / mk), Math.round((e.clientY - r.top - v.ty) / mk)]);
    const prev = pts.current.get(e.pointerId);
    if (!prev) return;
    pts.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.current.size === 2) {
      const [a, b] = [...pts.current.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinch.current > 0) zoomAt(d / pinch.current, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
      pinch.current = d;
      if (drag.current) drag.current.moved = true;
      return;
    }
    const dr = drag.current;
    if (!dr) return;
    if (!dr.moved && Math.hypot(e.clientX - dr.sx, e.clientY - dr.sy) < 5) return;
    if (!dr.moved) (e.currentTarget as Element).setPointerCapture(e.pointerId);
    dr.moved = true;
    setV((o) => ({ ...o, tx: o.tx + e.clientX - prev.x, ty: o.ty + e.clientY - prev.y }));
  };
  const onUp = (e: RPointerEvent): void => { pts.current.delete(e.pointerId); pinch.current = 0; if (pts.current.size === 0) setTimeout(() => { drag.current = null; }, 0); };

  const mk = f * v.k;
  const vis = { x: -v.tx / mk, y: -v.ty / mk, w: size.w / mk, h: size.h / mk };
  const showBase = layer !== "pipes";
  const haloOp = layer === "loss" ? 1 : layer === "full" ? 0.45 : 0;
  const pipeOp = layer === "loss" ? 0.45 : 1;
  const sel = useMemo(() => open, [open]);

  return (
    <div className="min-h-screen flex flex-col city-enter">
      <Header tag="CONCEPT://CITY" right={<>
        <Link to="/simulate" className="cad-btn-primary px-3 py-1.5 font-mono-cad text-[11px] font-bold whitespace-nowrap">OPEN SIMULATOR</Link>
        <Link to="/" className="cad-btn-secondary px-3 py-1.5 font-mono-cad text-[11px] whitespace-nowrap max-sm:hidden">← OVERVIEW</Link></>} />
      <div role="note" className="mt-14 bg-well border-b-2 border-alarm px-4 py-2 text-[11px] sm:text-xs font-mono-cad text-center">
        <strong className="text-alarm">CONCEPT DEMO</strong> — illustrative layout and values, not live data and not a real utility. The working simulator is at <Link to="/simulate" className="underline">/simulate</Link>.
      </div>

      <div ref={box} tabIndex={0} aria-label="Sample city map. Plus and minus zoom, zero resets, Escape closes a card."
        className="relative flex-1 min-h-[520px] h-[calc(100dvh-120px)] overflow-hidden bg-well blueprint-grid-subtle touch-none select-none cursor-grab"
        onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
        <svg width={size.w} height={size.h} className="block" role="img" aria-label="Sample city water network, illustrative">
          <defs>
            <pattern id="cityhatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="#fff" strokeOpacity=".18" /></pattern>
            <radialGradient id="haloA"><stop offset="0" stopColor={AMBER} stopOpacity=".7" /><stop offset="1" stopColor={AMBER} stopOpacity="0" /></radialGradient>
            <radialGradient id="haloB"><stop offset="0" stopColor={CRIT} stopOpacity=".7" /><stop offset="1" stopColor={CRIT} stopOpacity="0" /></radialGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4" /></filter>
          </defs>
          <g transform={`translate(${v.tx} ${v.ty}) scale(${mk})`}>
            {showBase && (<>
              <path d={RIVER} fill="url(#cityhatch)" stroke="#fff" strokeOpacity=".5" />
              <text x="620" y="722" fontFamily="JetBrains Mono" fontSize="14" letterSpacing="4" fill="#fff" fillOpacity=".6">RIVER (SAMPLE)</text>
              {SECTORS.map((s) => (
                <g key={s.id}>
                  <polygon points={s.pts} fill="#fff" fillOpacity=".02" stroke="#fff" strokeOpacity=".4" strokeDasharray="6 6" />
                  <text x={s.lx} y={s.ly} fontFamily="JetBrains Mono" fontSize="12" letterSpacing="2" fill="#fff" fillOpacity=".65">SECTOR {s.id} · {s.name}</text>
                </g>
              ))}
            </>)}
            {/* heatmap halos (illustrative pressure loss) */}
            <g opacity={haloOp} pointerEvents="none">
              <circle cx="560" cy="500" r="150" fill="url(#haloA)" />
              <circle cx="1215" cy="180" r="170" fill="url(#haloB)" />
            </g>
            <g opacity={pipeOp}>
              {FEEDERS.map((d) => (<g key={d}><path d={d} fill="none" stroke="#7bd0ff" strokeWidth="6" strokeOpacity=".35" filter="url(#glow)" /><path d={d} fill="none" stroke="#7bd0ff" strokeWidth="2.5" /><path d={d} fill="none" stroke={WELL} strokeWidth="1.5" className="aq-flow-feeder" /></g>))}
              <path d={SPINE} fill="none" stroke="#38bdf8" strokeWidth="12" strokeOpacity=".4" filter="url(#glow)" />
              <path d={SPINE} fill="none" stroke="#fff" strokeWidth="4" />
              <path d={SPINE} fill="none" stroke="#38bdf8" strokeWidth="2" className="aq-flow-main" />
              {/* fixtures */}
              <g fontFamily="JetBrains Mono" fontSize="11" fill="#fff">
                <g transform="translate(70 330)"><path d="M-22 -16 H22 L16 16 H-16 Z" fill={WELL} stroke="#fff" strokeWidth="2" /><text y="34" textAnchor="middle">SOURCE</text></g>
                <g transform="translate(300 330)"><rect x="-11" y="-11" width="22" height="22" fill={WELL} stroke="#fff" strokeWidth="2" /><text y="-18" textAnchor="middle">FLOW METER</text></g>
                <g transform="translate(600 270)"><path d="M-9 -8 L0 0 L-9 8 Z M9 -8 L0 0 L9 8 Z" fill="#fff" /><text y="-16" textAnchor="middle">GATE VALVE</text></g>
                <g transform="translate(1100 340)"><path d="M0 -11 L11 0 L0 11 L-11 0 Z" fill={WELL} stroke="#fff" strokeWidth="2" /><text y="26" textAnchor="middle">PRV</text></g>
                <g transform="translate(860 270)"><circle r="6" fill={WELL} stroke="#fff" strokeWidth="2" /><text y="-14" textAnchor="middle">JUNCTION</text></g>
              </g>
            </g>
            {showBase && DMA.map(([x, y]) => <circle key={`${x}${y}`} cx={x} cy={y} r="4.5" fill="#fff" fillOpacity=".85" stroke={WELL} strokeWidth="1.5" />)}
            {/* incidents */}
            {INCIDENTS.map((i) => (
              <g key={i.id}>
                <polyline points={`${i.x},${i.y} ${i.px - 6},${i.py} ${i.px},${i.py}`} fill="none" stroke={i.color} strokeWidth="1.2" />
                <circle cx={i.x} cy={i.y} r="46" fill="none" stroke={i.color} strokeWidth="2" className="aq-sonar" pointerEvents="none" />
                <circle cx={i.x} cy={i.y} r="46" fill="none" stroke={i.color} strokeWidth="2" className="aq-sonar" style={{ animationDelay: "1.2s" }} pointerEvents="none" />
                <path d={`M${i.x - 14} ${i.y} H${i.x + 14} M${i.x} ${i.y - 14} V${i.y + 14}`} stroke={i.color} strokeWidth="1.5" />
                <circle cx={i.x} cy={i.y} r="7" fill="none" stroke={i.color} strokeWidth="2" />
                <g transform={`translate(${i.px} ${i.py - 12})`} className="aq-hit" tabIndex={0} role="button" aria-label={`Open ${i.tag}`}
                  onClick={() => { if (!drag.current?.moved) setOpen(i); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(i); } }}>
                  <rect width="190" height="24" fill="#fff" rx="12" />
                  <circle cx="13" cy="12" r="4" fill={i.color} stroke={WELL} />
                  <text x="24" y="16" fontFamily="JetBrains Mono" fontSize="11" fontWeight="700" fill={WELL}>{i.tag}</text>
                </g>
              </g>
            ))}
          </g>
        </svg>

        {/* HUD */}
        <div className="absolute top-3 left-3 max-sm:hidden bg-panel/90 border border-white/40 px-3 py-2 font-mono-cad text-[10px] leading-relaxed pointer-events-none">
          <div className="font-bold">SAMPLE CITY LAYOUT // CONCEPT</div>
          <div className="text-paler">CURSOR {cursor[0]}, {cursor[1]} · SCALE N.T.S. · ZOOM {Math.round(v.k * 100)}%</div>
        </div>
        <div className="absolute top-3 right-3 max-sm:left-3 flex flex-wrap justify-end max-sm:justify-center gap-2" onPointerDown={(e) => e.stopPropagation()}>
          <div className="flex" role="group" aria-label="Layer">
            {LAYERS.map(([id, label]) => (
              <button key={id} onClick={() => setLayer(id)} aria-pressed={layer === id} className={`px-2.5 py-1.5 font-mono-cad text-[10px] ${layer === id ? "cad-btn-active" : "cad-btn-secondary"}`}>{label}</button>
            ))}
          </div>
          <button className="cad-btn-secondary px-2.5 py-1.5 font-mono-cad text-[10px]" onClick={() => setV(fit())}>RESET VIEW</button>
        </div>
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex flex-col gap-2 items-center" onPointerDown={(e) => e.stopPropagation()}>
          <div className="w-9 h-9 rounded-full border border-white/60 bg-panel flex items-center justify-center" title="North"><svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 2 L14 12 L10 10 L6 12 Z" fill="#fff" /><text x="10" y="19" textAnchor="middle" fontSize="6" fill="#fff" fontFamily="JetBrains Mono">N</text></svg></div>
          <button className="cad-btn-secondary w-9 h-9 font-mono-cad font-bold" onClick={() => zoomCenter(1.25)} aria-label="Zoom in">+</button>
          <button className="cad-btn-secondary w-9 h-9 font-mono-cad font-bold" onClick={() => zoomCenter(0.8)} aria-label="Zoom out">−</button>
          <button className="cad-btn-secondary w-9 h-9 flex items-center justify-center" onClick={() => setV(fit())} aria-label="Recenter"><svg aria-hidden="true" viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="#fff" strokeWidth="1.6"><circle cx="10" cy="10" r="4" /><path d="M10 1v4M10 15v4M1 10h4M15 10h4" /></svg></button>
        </div>

        <div className="absolute bottom-3 left-3 flex flex-col gap-2 pointer-events-none">
          <div className="bg-panel/90 border border-white/40 px-3 py-2 font-mono-cad text-[10px] flex flex-col gap-1">
            <span><span className="inline-block w-5 h-[3px] bg-white align-middle mr-2" />MAIN</span>
            <span><span className="inline-block w-5 h-[2px] align-middle mr-2" style={{ background: "#7bd0ff" }} />FEEDER</span>
            <span><span className="inline-block w-2 h-2 rounded-full align-middle mr-2" style={{ background: AMBER }} />ANOMALY (EXAMPLE)</span>
            <span><span className="inline-block w-2 h-2 rounded-full align-middle mr-2" style={{ background: CRIT }} />CRITICAL (EXAMPLE)</span>
          </div>
          <div className="font-mono-cad text-[10px] flex items-center gap-2"><span className="inline-block w-24 h-2 border-x border-b border-white" />N.T.S. · ILLUSTRATIVE</div>
        </div>

        <div className="absolute bottom-3 right-3 w-48 flex flex-col gap-1 items-end max-sm:hidden pointer-events-none">
          <div className="font-mono-cad text-[9px] text-paler">STATIC DEMO · NO LIVE FEED</div>
          <svg width="192" height="112" viewBox={`0 0 ${MW} ${MH}`} className="bg-panel/90 border border-white/50" role="img" aria-label="Minimap">
            <path d={RIVER} fill="#fff" fillOpacity=".15" />
            <path d={SPINE} fill="none" stroke="#fff" strokeWidth="14" />
            {FEEDERS.map((d) => <path key={d} d={d} fill="none" stroke="#7bd0ff" strokeWidth="8" />)}
            <rect x={vis.x} y={vis.y} width={vis.w} height={vis.h} fill="#fff" fillOpacity=".12" stroke="#fff" strokeWidth="10" />
          </svg>
        </div>
      </div>

      {sel && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50" onClick={() => setOpen(null)}>
          <div role="dialog" aria-modal="true" aria-label={sel.tag} onClick={(e) => e.stopPropagation()} className="bg-white text-well max-w-md w-full p-6 border-2 border-white flex flex-col gap-3 shadow-2xl">
            <span className="self-start font-mono-cad text-[10px] font-bold px-2 py-1 text-well" style={{ background: sel.color }}>{sel.badge}</span>
            <h2 className="font-heading font-bold text-xl text-[#0c4a6e]">{sel.title}</h2>
            <p className="font-mono-cad text-[11px]">{sel.zone}</p>
            <div className="grid grid-cols-2 gap-2">
              {sel.cells.map(([k, val]) => (<div key={k} className="border border-[#0c4a6e]/30 p-2"><div className="font-mono-cad text-[9px] text-[#075985]">{k}</div><div className="text-sm font-bold">{val}</div></div>))}
            </div>
            <p className="text-sm leading-relaxed text-[#0c4a6e]">{sel.body}</p>
            <div className="flex gap-2 mt-1">
              <Link to="/simulate" className="flex-1 text-center bg-[#075985] text-white py-2 font-mono-cad text-xs font-bold">INSPECT IN SIMULATOR</Link>
              <button autoFocus className="px-4 py-2 border border-[#075985] font-mono-cad text-xs font-bold" onClick={() => setOpen(null)}>DISMISS</button>
            </div>
            <p className="font-mono-cad text-[9px] text-[#075985]">CONCEPT DEMO · ALL VALUES ILLUSTRATIVE</p>
          </div>
        </div>
      )}
    </div>
  );
}
