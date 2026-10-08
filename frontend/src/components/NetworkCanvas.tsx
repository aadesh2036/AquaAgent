// NetworkCanvas — native SVG plan view of the topology. Renders API values only; no hydraulic math (P1).
import { useMemo } from "react";
import type { KeyboardEvent } from "react";
import type { LinkConfig, NetworkTopology, NetworkView, NodeConfig, SimStore } from "@contracts";
import { flowAnimationDuration, fmtLps, fmtM, fmtPct, layoutOf } from "../lib/display";

const W = "#fff";
const AMBER = "#fbbf24";
const WELL = "#075985";
const PAD = 30;

type Sel = SimStore["selection"];
interface Props {
  topology: NetworkTopology;
  view: NetworkView;
  running: boolean;
  selection: Sel;
  onSelect: (s: Sel) => void;
}

const key = (e: KeyboardEvent, fn: () => void): void => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); }
};

export function NetworkCanvas({ topology, view, running, selection, onSelect }: Props): JSX.Element {
  const layout = layoutOf(topology);
  const nodeById = useMemo(() => new Map(topology.nodes.map((n) => [n.node_id, n])), [topology]);

  const { vb, widthOf } = useMemo(() => {
    const xs = topology.nodes.map((n) => n.x), ys = topology.nodes.map((n) => n.y);
    const minX = Math.min(...xs) - PAD, minY = Math.min(...ys) - PAD;
    const maxX = Math.max(...xs) + PAD, maxY = Math.max(...ys) + PAD + 12;
    const diams = [...new Set(topology.links.filter((l) => l.diameter_m != null).map((l) => l.diameter_m as number))].sort((a, b) => a - b);
    return {
      vb: `${minX} ${minY} ${maxX - minX} ${maxY - minY}`,
      widthOf: (l: LinkConfig): number => (l.diameter_m == null ? 3 : 1.6 + diams.indexOf(l.diameter_m) * 0.7), // diameter rank → stroke width
    };
  }, [topology]);

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
  const tapOffset: Record<string, [number, number]> = { "3": [0, -17], "4": [-19, 0], "6": [19, 0] };
  const tank = topology.nodes.find((n) => n.node_type === "tank");
  const TH = 28, TW = 20;
  const pct = view.tank.level_pct;
  const fillH = Number.isFinite(pct) ? (TH * Math.min(100, Math.max(0, pct))) / 100 : 0;

  return (
    <svg viewBox={vb} className="w-full h-auto block" role="group" aria-label="Plan view of the water network">
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

      {/* flow-sensor tags */}
      {topology.links.map((l) => {
        const sid = sensorOfLink.get(l.link_id);
        if (!sid) return null;
        const { mx, my } = linkGeom(l);
        return (
          <g key={`ft${l.link_id}`} transform={`translate(${mx} ${my})`} role="presentation">
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
            <text y="15" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="5" fill={W} fillOpacity="0.8">PUMP {view.pump.status}</text>
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
              <g role="presentation">
                <path d="M-11 -8 H11 L8 8 H-8 Z" fill={WELL} stroke={W} strokeWidth="1.5" />
                <path d="M-9 -2 q3 -3 6 0 t6 0 t6 0" fill="none" stroke={W} strokeWidth="1" />
              </g>
            )}
            {n.node_type === "tank" && (
              <g role="presentation">
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
              <text x="9" y="-8" fontFamily="JetBrains Mono" fontSize="7" fontWeight="700" fill={W}>{vn.sensor_id}</text>
            )}
            {n.ui_label && n.node_type !== "reservoir" && (
              <text className="aq-node-label" y={n.node_type === "tank" ? TH / 2 + 16 : 14} textAnchor="middle" fontFamily="Inter" fontSize="4.6" fill={W} stroke={WELL} strokeWidth="2" paintOrder="stroke">{n.ui_label}</text>
            )}
            {n.node_type === "reservoir" && n.ui_label && <text className="aq-node-label" y="17" textAnchor="middle" fontFamily="Inter" fontSize="4.6" fill={W} stroke={WELL} strokeWidth="2" paintOrder="stroke">{n.ui_label}</text>}
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
  );
}
