// NetworkCanvas — native SVG plan view of the topology. Renders API values only; no hydraulic math (P1).
import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent as RPointerEvent, WheelEvent as RWheelEvent } from "react";
import type { LinkConfig, NetworkTopology, NetworkView, NodeConfig, SimStore } from "@contracts";
import { flowAnimationDuration, fmtLps, fmtM, fmtPct, layoutOf } from "../lib/display";
import type { AiHighlight } from "../api/ai";

const W = "#fff";
const AMBER = "#fbbf24";
const WELL = "#075985";
const AI = "#f0abfc"; // tailwind `ai`: AI-estimated area only, always labelled BY AI (frontend/DESIGN.md)
const AI_INK = "#3b0764";
const PAD = 30;

type Sel = SimStore["selection"];
interface Props {
  topology: NetworkTopology;
  view: NetworkView;
  running: boolean;
  selection: Sel;
  onSelect: (s: Sel) => void;
  /** AI-estimated probable area (BI-27); drawn only when present and `showAi`. */
  aiHighlight?: AiHighlight | null;
  showAi?: boolean;
  /** Fill the parent's height (one-screen layout); keeps aspect ratio. */
  fit?: boolean;
}

const key = (e: KeyboardEvent, fn: () => void): void => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
};

export function NetworkCanvas({ topology, view, running, selection, onSelect, aiHighlight, showAi = true, fit = false }: Props): JSX.Element {
  const layout = layoutOf(topology);
  const nodeById = useMemo(() => new Map(topology.nodes.map((n) => [n.node_id, n])), [topology]);

  const { widthOf, minX, minY, w0, h0 } = useMemo(() => {
    const xs = topology.nodes.map((n) => n.x), ys = topology.nodes.map((n) => n.y);
    const minX = Math.min(...xs) - PAD, minY = Math.min(...ys) - PAD;
    const maxX = Math.max(...xs) + PAD, maxY = Math.max(...ys) + PAD + 12;
    const diams = [...new Set(topology.links.filter((l) => l.diameter_m != null).map((l) => l.diameter_m as number))].sort((a, b) => a - b);
    return {
      minX, minY, w0: maxX - minX, h0: maxY - minY,
      vb: `${minX} ${minY} ${maxX - minX} ${maxY - minY}`,
      widthOf: (l: LinkConfig): number => (l.diameter_m == null ? 3 : 1.6 + diams.indexOf(l.diameter_m) * 0.7), // diameter rank → stroke width
    };
  }, [topology]);

  // ---- zoom / pan (display only): the viewBox window over the drawing; scale 1 = fit
  const [cam, setCam] = useState({ s: 1, cx: 0.5, cy: 0.5 });
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; cx: number; cy: number; moved: boolean } | null>(null);
  const MAX_S = 5;
  const clampC = (c: number, s: number): number => Math.min(1 - 0.5 / s, Math.max(0.5 / s, c));
  const zoomTo = (s: number, cx = cam.cx, cy = cam.cy): void => {
    const ns = Math.min(MAX_S, Math.max(1, s));
    setCam({ s: ns, cx: clampC(cx, ns), cy: clampC(cy, ns) });
  };
  const vw = w0 / cam.s, vh = h0 / cam.s;
  const vb = `${minX + cam.cx * w0 - vw / 2} ${minY + cam.cy * h0 - vh / 2} ${vw} ${vh}`;
  /** client px → fraction of the full drawing (accounts for the meet letterbox) */
  const toFrac = (clientX: number, clientY: number): [number, number] => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return [cam.cx, cam.cy];
    const k = Math.max(vw / r.width, vh / r.height);
    const ox = (r.width - vw / k) / 2, oy = (r.height - vh / k) / 2;
    const x = minX + cam.cx * w0 - vw / 2 + (clientX - r.left - ox) * k;
    const y = minY + cam.cy * h0 - vh / 2 + (clientY - r.top - oy) * k;
    return [(x - minX) / w0, (y - minY) / h0];
  };
  const onWheel = (e: RWheelEvent<SVGSVGElement>): void => {
    const [fx, fy] = toFrac(e.clientX, e.clientY);
    const ns = Math.min(MAX_S, Math.max(1, cam.s * (e.deltaY < 0 ? 1.2 : 1 / 1.2)));
    // keep the point under the cursor fixed
    zoomTo(ns, fx - (fx - cam.cx) * (cam.s / ns), fy - (fy - cam.cy) * (cam.s / ns));
  };
  const onPointerDown = (e: RPointerEvent<SVGSVGElement>): void => {
    if (cam.s === 1) return;
    drag.current = { x: e.clientX, y: e.clientY, cx: cam.cx, cy: cam.cy, moved: false };
  };
  const onPointerMove = (e: RPointerEvent<SVGSVGElement>): void => {
    const d = drag.current;
    const r = svgRef.current?.getBoundingClientRect();
    if (!d || !r) return;
    const k = Math.max(vw / r.width, vh / r.height);
    if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 4) d.moved = true;
    if (!d.moved) return;
    setCam((c) => ({ ...c, cx: clampC(d.cx - ((e.clientX - d.x) * k) / w0, c.s), cy: clampC(d.cy - ((e.clientY - d.y) * k) / h0, c.s) }));
  };
  const suppressClick = useRef(false);
  const endDrag = (): void => {
    if (drag.current?.moved) { suppressClick.current = true; setTimeout(() => { suppressClick.current = false; }, 0); }
    drag.current = null;
  };

  const pt = (id: string): { x: number; y: number } => {
    const n = nodeById.get(id) as NodeConfig;
    return { x: n.x, y: n.y };
  };

  const linkGeom = (l: LinkConfig): { d: string; mx: number; my: number } => {
    const a = pt(l.start_node), b = pt(l.end_node);
    if (l.link_id === "8") { // drawn as a curve between nodes 5 and 6 (EPANET Fig 2.1)
      const c = { x: b.x, y: a.y };
      return { d: `M${a.x} ${a.y} Q${c.x} ${c.y} ${b.x} ${b.y}`, mx: 0.25 * a.x + 0.5 * c.x + 0.25 * b.x, my: 0.25 * a.y + 0.5 * c.y + 0.25 * b.y };
    }
    return { d: `M${a.x} ${a.y} L${b.x} ${b.y}`, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
  };

  const isSel = (kind: "node" | "link" | "tap" | "valve", id: string): boolean => selection?.kind === kind && selection.id === id;
  const sensorOfLink = new Map(layout.flow.map((f) => [f.link_id, f.sensor_id]));
  const tapAt = new Map(topology.taps.map((t) => [t.node_id, t.tap_id]));
  const tapOffset: Record<string, [number, number]> = { "3": [-12, -14], "4": [-18, -6], "6": [19, -6] };
  // Per-node label placement [dx, dy, anchor], chosen so labels do not cross pipes or each other.
  const labelAt: Record<string, [number, number, "start" | "middle" | "end"]> = {
    "1": [0, 17, "middle"], "2": [-4, 14, "start"], "3": [6, -9, "start"], "4": [-6, 14, "end"],
    "5": [0, 14, "middle"], "6": [7, 14, "start"], "7": [6, -9, "start"], "8": [0, 36, "middle"],
  };
  const tank = topology.nodes.find((n) => n.node_type === "tank");
  const TH = 28, TW = 20;
  const pct = view.tank.level_pct;
  const fillH = Number.isFinite(pct) ? (TH * Math.min(100, Math.max(0, pct))) / 100 : 0;

  return (
    <div className={`relative ${fit ? "lg:h-full" : ""}`}>
    <div className="absolute right-1 top-1 z-10 flex flex-col gap-1" role="group" aria-label="Zoom">
      <button className="cad-btn-secondary w-8 h-8 font-mono-cad text-sm font-bold bg-well" aria-label="Zoom in" onClick={() => zoomTo(cam.s * 1.4)}>+</button>
      <button className="cad-btn-secondary w-8 h-8 font-mono-cad text-sm font-bold bg-well" aria-label="Zoom out" onClick={() => zoomTo(cam.s / 1.4)} disabled={cam.s <= 1}>−</button>
      <button className="cad-btn-secondary w-8 h-8 bg-well flex items-center justify-center" aria-label="Fit drawing" onClick={() => zoomTo(1, 0.5, 0.5)} disabled={cam.s <= 1}>
        <span aria-hidden="true" className="material-symbols-outlined" style={{ fontSize: 16 }}>fit_screen</span>
      </button>
      {cam.s > 1 && <span className="font-mono-cad text-[9px] text-paler text-center">{Math.round(cam.s * 100)}%</span>}
    </div>
    <svg ref={svgRef} viewBox={vb} className={`${fit ? "w-full h-auto lg:h-full block" : "w-full h-auto block"} ${cam.s > 1 ? "cursor-grab touch-none" : ""}`}
      preserveAspectRatio="xMidYMid meet" overflow="hidden" style={{ overflow: "hidden" }} role="group" aria-label="Plan view of the water network — scroll to zoom, drag to pan"
      onWheel={onWheel} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endDrag} onPointerLeave={endDrag}
      onClickCapture={(e) => { if (suppressClick.current) { e.stopPropagation(); suppressClick.current = false; } }}>
      <defs>
        <clipPath id="tankclip">{tank && <rect x={tank.x - TW / 2} y={tank.y - TH / 2} width={TW} height={TH} />}</clipPath>
      </defs>

      {/* pipes */}
      {topology.links.map((l) => {
        const g = linkGeom(l);
        const v = view.links[l.link_id];
        const closed = v?.status === "CLOSED";
        const dur = running && !closed ? flowAnimationDuration(v?.flow_lps) : null;
        const w = l.link_type === "pump" ? 3 : widthOf(l);
        return (
          <g key={l.link_id}>
            <path d={g.d} fill="none" stroke={WELL} strokeWidth={w + 2.5} strokeLinecap="round" />
            <path d={g.d} fill="none" stroke={W} strokeOpacity={closed ? 0.35 : 0.95} strokeWidth={w} strokeDasharray={closed ? "3 3" : undefined} strokeLinecap="round" />
            {dur !== null && (
              <path d={g.d} fill="none" stroke={WELL} strokeWidth={Math.max(1, w * 0.45)}
                className={`aq-flow ${v.direction === -1 ? "rev" : ""}`} style={{ animationDuration: `${dur}s` }} />
            )}
          </g>
        );
      })}

      {/* leak / burst visuals */}
      {topology.links.map((l) => {
        const f = view.links[l.link_id]?.visual_fault;
        if (!f || f === "NONE") return null;
        const { mx, my } = linkGeom(l);
        return (
          <g key={`f${l.link_id}`} transform={`translate(${mx} ${my})`}>
            <title>{f === "BURST" ? "Burst" : "Leak"} on pipe {l.link_id}</title>
            <circle r="3" fill="none" stroke={AMBER} strokeWidth="1.2" className="aq-spray" />
            {f === "BURST" && <circle r="5" fill="none" stroke={AMBER} strokeWidth="1.5" className="aq-spray" style={{ animationDelay: ".25s" }} />}
            {(f === "BURST" ? [-6, -3, 0, 3, 6] : [-2, 0, 2]).map((dx, i) => (
              <circle key={dx} cx={dx} cy={2} r={f === "BURST" ? 1.5 : 1.1} fill={AMBER} className="aq-drip" style={{ animationDelay: `${i * 0.25}s` }} />
            ))}
          </g>
        );
      })}

      {/* AI-estimated area (BY AI) — under sensors and nodes so the simulator's own visuals stay on top */}
      {aiHighlight && showAi && (
        <g aria-label={`AI-estimated probable area: zone ${aiHighlight.probable_zone ?? "unknown"}`} role="img">
          <title>{`BY AI — probable zone ${aiHighlight.probable_zone}; most likely ${aiHighlight.candidates.map((c) => `${c.location_kind} ${c.location_id}`).join(", ")}`}</title>
          {topology.links.filter((l) => aiHighlight.zone_links.includes(l.link_id)).map((l) => (
            <path key={`az${l.link_id}`} d={linkGeom(l).d} fill="none" stroke={AI} strokeOpacity="0.16" strokeWidth={widthOf(l) + 12} strokeLinecap="round" pointerEvents="none" />
          ))}
          {topology.nodes.filter((n) => aiHighlight.zone_nodes.includes(n.node_id)).map((n) => (
            <circle key={`azn${n.node_id}`} cx={n.x} cy={n.y} r="13" fill={AI} fillOpacity="0.12" pointerEvents="none" />
          ))}
          {aiHighlight.candidates.map((c) => {
            const op = c.rank === 1 ? 0.95 : c.rank === 2 ? 0.7 : 0.5;
            const tag = (x: number, y: number): JSX.Element => (
              <g transform={`translate(${x} ${y})`} pointerEvents="none">
                <rect x="-11" y="-5" width="22" height="9" fill={AI} />
                <text textAnchor="middle" y="2.2" fontFamily="JetBrains Mono" fontSize="5.4" fontWeight="700" fill={AI_INK}>AI #{c.rank}</text>
              </g>
            );
            if (c.location_kind === "pipe") {
              const l = topology.links.find((q) => q.link_id === c.location_id);
              if (!l) return null;
              const g = linkGeom(l);
              const a = pt(l.start_node), b = pt(l.end_node);
              const horizontal = Math.abs(b.x - a.x) > Math.abs(b.y - a.y); // chip below horizontal pipes, clear of node labels
              return (
                <g key={`ac${c.rank}`}>
                  <path d={g.d} fill="none" stroke={AI} strokeOpacity={op} strokeWidth={widthOf(l) + 4} strokeDasharray="5 3" strokeLinecap="round" pointerEvents="none" />
                  {horizontal ? tag(g.mx, g.my + 11) : tag(g.mx, g.my - 9)}
                </g>
              );
            }
            const n = nodeById.get(c.location_id);
            if (!n) return null;
            return (
              <g key={`ac${c.rank}`}>
                <circle cx={n.x} cy={n.y} r="11" fill="none" stroke={AI} strokeOpacity={op} strokeWidth="2" strokeDasharray="3 2" pointerEvents="none" />
                {tag(n.x, n.y - 17)}
              </g>
            );
          })}
          <g transform={`translate(${minX + 4} ${minY + 4})`} pointerEvents="none">
            <rect width="24" height="10" fill={AI} />
            <text x="12" y="7" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="5.6" fontWeight="700" fill={AI_INK}>BY AI</text>
            <text x="28" y="7" fontFamily="JetBrains Mono" fontSize="5.4" fill={W}>AI-estimated area · zone {aiHighlight.probable_zone}</text>
          </g>
        </g>
      )}

      {/* flow-sensor tags */}
      {topology.links.map((l) => {
        const sid = sensorOfLink.get(l.link_id);
        if (!sid) return null;
        const { mx, my } = linkGeom(l);
        return (
          <g key={`ft${l.link_id}`} transform={`translate(${mx} ${my})`} aria-hidden="true">
            <rect x="-7" y="-4.5" width="14" height="9" fill={WELL} stroke={W} strokeWidth="1" />
            <text textAnchor="middle" y="2.4" fontFamily="JetBrains Mono" fontSize="6" fontWeight="700" fill={W}>{sid}</text>
          </g>
        );
      })}

      {/* pump glyph on the pump link */}
      {topology.links.filter((l) => l.link_type === "pump").map((l) => {
        const { mx, my } = linkGeom(l);
        const off = view.pump.status === "OFF";
        return (
          <g key={`p${l.link_id}`} transform={`translate(${mx} ${my})`}>
            <title>Pump {l.link_id}: {view.pump.status}, {fmtLps(view.pump.flow_lps)}</title>
            <circle r="7" fill={WELL} stroke={W} strokeWidth="1.5" strokeOpacity={off ? 0.4 : 1} />
            <path d="M-3 -4 L5 0 L-3 4 Z" fill={W} fillOpacity={off ? 0.4 : 1} />
            <text y="17" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="5" fill={W} fillOpacity="0.8">PUMP {view.pump.status}</text>
          </g>
        );
      })}

      {/* link hit targets */}
      {topology.links.map((l) => {
        const { d } = linkGeom(l);
        return (
          <path key={`h${l.link_id}`} d={d} fill="none" stroke="transparent" strokeWidth="11" className="aq-hit" tabIndex={0} role="button"
            aria-label={`${l.link_type === "pump" ? "Pump" : "Pipe"} ${l.link_id}`}
            onClick={() => onSelect({ kind: "link", id: l.link_id })} onKeyDown={(e) => key(e, () => onSelect({ kind: "link", id: l.link_id }))} />
        );
      })}
      {topology.links.filter((l) => isSel("link", l.link_id)).map((l) => (
        <path key={`s${l.link_id}`} d={linkGeom(l).d} fill="none" stroke={W} strokeWidth={widthOf(l) + 6} strokeOpacity="0.25" strokeLinecap="round" pointerEvents="none" />
      ))}

      {/* valve V1 */}
      {topology.valves.map((vd) => {
        const l = topology.links.find((q) => q.link_id === vd.link_id);
        if (!l) return null;
        const { mx, my } = linkGeom(l);
        const open = view.valves[vd.valve_id]?.open !== false;
        return (
          <g key={vd.valve_id} transform={`translate(${mx} ${my})`} className="aq-hit" tabIndex={0} role="button" aria-label={`Valve ${vd.valve_id}, ${open ? "open" : "closed"}`}
            onClick={() => onSelect({ kind: "valve", id: vd.valve_id })} onKeyDown={(e) => key(e, () => onSelect({ kind: "valve", id: vd.valve_id }))}>
            <rect x="-9" y="-9" width="18" height="18" fill="transparent" />
            <path d="M-6 -4 L0 0 L-6 4 Z M6 -4 L0 0 L6 4 Z" fill={open ? W : "none"} stroke={W} strokeWidth="1.2" fillOpacity={open ? 0.9 : 1} />
            {!open && <path d="M-7 -6 L7 6 M7 -6 L-7 6" stroke={W} strokeWidth="1.2" />}
            <text x="10" y="2" fontFamily="JetBrains Mono" fontSize="5.5" fontWeight="700" fill={W}>{vd.valve_id}</text>
            {isSel("valve", vd.valve_id) && <rect x="-10" y="-8" width="20" height="16" fill="none" stroke={W} strokeDasharray="2 2" />}
          </g>
        );
      })}

      {/* nodes */}
      {topology.nodes.map((n) => {
        const vn = view.nodes[n.node_id];
        const status = vn?.status ?? "ok";
        const sel = isSel("node", n.node_id);
        const tapId = tapAt.get(n.node_id);
        const off = tapOffset[n.node_id];
        return (
          <g key={n.node_id} transform={`translate(${n.x} ${n.y})`}>
            {n.node_type === "reservoir" && (
              <g aria-hidden="true">
                <path d="M-11 -8 H11 L8 8 H-8 Z" fill={WELL} stroke={W} strokeWidth="1.5" />
                <path d="M-9 -2 q3 -3 6 0 t6 0 t6 0" fill="none" stroke={W} strokeWidth="1" />
              </g>
            )}
            {n.node_type === "tank" && (
              <g aria-hidden="true">
                <rect x={-TW / 2} y={-TH / 2} width={TW} height={TH} fill={WELL} stroke={W} strokeWidth="1.5" />
                <g clipPath="url(#tankclip)" transform={`translate(${-n.x} ${-n.y})`}>
                  <rect x={n.x - TW / 2} y={n.y + TH / 2 - fillH} width={TW} height={fillH} fill={W} fillOpacity="0.75" />
                </g>
                <text y={TH / 2 + 8} textAnchor="middle" fontFamily="JetBrains Mono" fontSize="5.5" fill={W}>{fmtPct(pct)}</text>
              </g>
            )}
            {n.node_type === "junction" && (
              <>
                {(status === "low" || status === "critical") && (
                  <circle r={status === "critical" ? 10 : 8.5} fill="none" stroke={AMBER} strokeWidth={status === "critical" ? 2.5 : 1.6} className={status === "critical" ? "aq-pulse" : undefined} />
                )}
                {vn?.is_sensor && <circle r="7" fill="none" stroke={W} strokeWidth="1.2" />}
                <circle r="3.6" fill={WELL} stroke={W} strokeWidth="1.5" />
              </>
            )}
            {sel && <circle r="14" fill="none" stroke={W} strokeDasharray="2.5 2.5" strokeWidth="1" />}
            {vn?.is_sensor && vn.sensor_id && (
              <text x={n.node_id === "6" ? -9 : 9} y="-8" textAnchor={n.node_id === "6" ? "end" : "start"} fontFamily="JetBrains Mono" fontSize="8" fontWeight="700" fill={W}>{vn.sensor_id}</text>
            )}
            {n.ui_label && labelAt[n.node_id] && (
              <text className="aq-node-label" x={labelAt[n.node_id][0]} y={labelAt[n.node_id][1]} textAnchor={labelAt[n.node_id][2]} fontFamily="Inter" fontSize="4.6" fill={W} stroke={WELL} strokeWidth="2" paintOrder="stroke">{n.ui_label}</text>
            )}
            <title>{`Node ${n.node_id}${n.ui_label ? ` — ${n.ui_label}` : ""}${vn ? `, ${fmtM(vn.pressure_m)}` : ""}`}</title>
            <circle r="9" fill="transparent" className="aq-hit" tabIndex={0} role="button" aria-label={`Node ${n.node_id}${n.ui_label ? ` ${n.ui_label}` : ""}`}
              onClick={() => onSelect({ kind: "node", id: n.node_id })} onKeyDown={(e) => key(e, () => onSelect({ kind: "node", id: n.node_id }))} />
            {tapId && off && (() => {
              const open = view.taps[tapId]?.open !== false;
              return (
                <g transform={`translate(${off[0]} ${off[1]})`} className="aq-hit" tabIndex={0} role="button" aria-label={`Tap ${tapId}, ${open ? "open" : "closed"}`}
                  onClick={() => onSelect({ kind: "tap", id: tapId })} onKeyDown={(e) => key(e, () => onSelect({ kind: "tap", id: tapId }))}>
                  <rect x="-7" y="-7" width="14" height="14" fill="transparent" />
                  <path d="M-4 -3 h6 v-2 M2 -3 h3 v3 M0 -3 v6" fill="none" stroke={W} strokeWidth="1.2" strokeOpacity={open ? 1 : 0.4} />
                  {!open && <path d="M-5 -5 L5 5" stroke={W} strokeWidth="1.2" />}
                  <text y="10" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="5" fill={W}>{tapId}</text>
                  {isSel("tap", tapId) && <rect x="-8" y="-8" width="16" height="22" fill="none" stroke={W} strokeDasharray="2 2" />}
                </g>
              );
            })()}
          </g>
        );
      })}
    </svg>
    </div>
  );
}
