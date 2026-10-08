// Inline SVG schematics for the "How it works" slides. Illustrative only: no hydraulic values drawn.
import netconfig from "@netconfig";
import type { NetworkTopology } from "@contracts";
import { DEFAULT_SENSOR_LAYOUT } from "../../lib/display";

const W = "#fff";
const AMBER = "#fbbf24";
const topo = netconfig as unknown as NetworkTopology;

function Defs(): JSX.Element {
  return (
    <defs>
      <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke={W} strokeOpacity="0.28" strokeWidth="1" />
      </pattern>
      <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0 0 L10 5 L0 10 z" fill={W} />
      </marker>
    </defs>
  );
}

const Box = ({ x, y, w, label }: { x: number; y: number; w: number; label: string }): JSX.Element => (
  <g>
    <rect x={x} y={y} width={w} height="22" fill="#0369a1" stroke={W} strokeOpacity="0.7" />
    <text x={x + w / 2} y={y + 15} textAnchor="middle" fontFamily="JetBrains Mono" fontSize="10" fill={W}>{label}</text>
  </g>
);

export function PhysicsDrawing(): JSX.Element {
  return (
    <svg viewBox="0 0 600 300" className="w-full h-full" role="img" aria-label="Pipe section with a pressure-driven leak and sensor S2">
      <Defs />
      <rect x="30" y="120" width="540" height="56" fill="url(#hatch)" stroke={W} strokeWidth="2" />
      <line x1="50" y1="148" x2="550" y2="148" stroke={W} strokeWidth="1.5" strokeDasharray="10 8" markerEnd="url(#arr)">
        <animate attributeName="stroke-dashoffset" from="36" to="0" dur="1.6s" repeatCount="indefinite" />
      </line>
      {/* leak: amber rings + jet */}
      <g>
        <circle cx="360" cy="176" r="4" fill={AMBER} />
        {[0, 0.6, 1.2].map((d) => (
          <circle key={d} cx="360" cy="176" r="6" fill="none" stroke={AMBER} strokeWidth="2">
            <animate attributeName="r" from="6" to="34" dur="1.8s" begin={`${d}s`} repeatCount="indefinite" />
            <animate attributeName="opacity" from="0.9" to="0" dur="1.8s" begin={`${d}s`} repeatCount="indefinite" />
          </circle>
        ))}
        <path d="M360 180 v26 M354 190 l-8 18 M366 190 l8 18" stroke={AMBER} strokeWidth="2" strokeLinecap="round" />
      </g>
      {/* sensor riser */}
      <line x1="170" y1="120" x2="170" y2="70" stroke={W} strokeDasharray="4 4" />
      <rect x="158" y="52" width="24" height="18" fill="#075985" stroke={W} strokeWidth="1.5" />
      <Box x={140} y={22} w={60} label="S2" />
      <Box x={320} y={222} w={80} label="LEAK ORIFICE" />
      <text x="30" y="205" fontFamily="JetBrains Mono" fontSize="10" fill={W} fillOpacity="0.7">PIPE // WNTR SOLVES EVERY STEP</text>
      <text x="570" y="205" textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill={W} fillOpacity="0.7">FLOW →</text>
    </svg>
  );
}

// Display scaling of topology x/y into the drawing box (layout only).
const SX = 2.0, SY = 1.1, OX = 40, OY = 70;
const P = (id: string): { x: number; y: number } => {
  const n = topo.nodes.find((q) => q.node_id === id)!;
  return { x: OX + n.x * SX, y: OY + n.y * SY };
};

export function SparseDrawing(): JSX.Element {
  const sensorNodes = new Map(DEFAULT_SENSOR_LAYOUT.pressure.map((p) => [p.node_id, p.sensor_id]));
  const flowLinks = new Map(DEFAULT_SENSOR_LAYOUT.flow.map((f) => [f.link_id, f.sensor_id]));
  return (
    <svg viewBox="0 0 600 300" className="w-full h-full" role="img" aria-label="Network with only five sensor marks highlighted">
      <Defs />
      {topo.links.map((l) => {
        const a = P(l.start_node), b = P(l.end_node);
        const fid = flowLinks.get(l.link_id);
        const curved = l.link_id === "8";
        const d = curved ? `M${a.x} ${a.y} Q ${a.x + 90} ${a.y + 60} ${b.x} ${b.y}` : `M${a.x} ${a.y} L${b.x} ${b.y}`;
        return (
          <g key={l.link_id}>
            <path d={d} fill="none" stroke={W} strokeOpacity={fid ? 0.9 : 0.3} strokeWidth="1.5" strokeDasharray={fid ? undefined : "4 4"} />
            {fid && (() => {
              const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
              return (<g><rect x={mx - 8} y={my - 8} width="16" height="16" fill="#075985" stroke={W} strokeWidth="1.5" />
                <text x={mx} y={my + 4} textAnchor="middle" fontFamily="JetBrains Mono" fontSize="9" fill={W}>{fid}</text></g>);
            })()}
          </g>
        );
      })}
      {topo.nodes.map((n) => {
        const p = P(n.node_id);
        const sid = sensorNodes.get(n.node_id);
        return sid ? (
          <g key={n.node_id}>
            <circle cx={p.x} cy={p.y} r="12" fill="#075985" stroke={W} strokeWidth="2" />
            <circle cx={p.x} cy={p.y} r="4" fill={W} />
            <text x={p.x + 16} y={p.y - 12} fontFamily="JetBrains Mono" fontSize="11" fontWeight="bold" fill={W}>{sid}</text>
          </g>
        ) : (
          <circle key={n.node_id} cx={p.x} cy={p.y} r="5" fill="none" stroke={W} strokeOpacity="0.3" strokeDasharray="2 2" />
        );
      })}
    </svg>
  );
}

const SENSORS = ["S1", "S2", "S3", "F1", "F2"];
const OBS = [0.62, 0.5, 0.58, 0.7, 0.45]; // illustrative bar heights, not data
const EXP = [0.66, 0.66, 0.62, 0.68, 0.5];

export function ReconstructionDrawing(): JSX.Element {
  return (
    <svg viewBox="0 0 600 300" className="w-full h-full" role="img" aria-label="Illustrative observed versus expected bars for five sensors">
      <Defs />
      <line x1="40" y1="250" x2="560" y2="250" stroke={W} strokeOpacity="0.7" />
      {SENSORS.map((s, i) => {
        const x = 70 + i * 100;
        const ho = OBS[i] * 190, he = EXP[i] * 190;
        return (
          <g key={s}>
            <rect x={x} y={250 - he} width="30" height={he} fill="url(#hatch)" stroke={W} strokeDasharray="3 3" />
            <rect x={x + 34} y={250 - ho} width="30" height={ho} fill={W} fillOpacity="0.85" />
            <text x={x + 32} y="270" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="11" fill={W}>{s}</text>
          </g>
        );
      })}
      <rect x="400" y="22" width="12" height="12" fill={W} fillOpacity="0.85" />
      <text x="418" y="32" fontFamily="JetBrains Mono" fontSize="10" fill={W}>OBSERVED</text>
      <rect x="400" y="42" width="12" height="12" fill="url(#hatch)" stroke={W} strokeDasharray="2 2" />
      <text x="418" y="52" fontFamily="JetBrains Mono" fontSize="10" fill={W}>EXPECTED</text>
      <text x="40" y="32" fontFamily="JetBrains Mono" fontSize="10" fill={W} fillOpacity="0.7">ILLUSTRATIVE // NO VALUES</text>
    </svg>
  );
}

export function DetectionDrawing(): JSX.Element {
  return (
    <div className="w-full h-full flex flex-col justify-center gap-5 p-6 sm:p-10">
      <div className="mono-label text-paler">// Measured in our simulation</div>
      <p className="font-heading text-lg sm:text-2xl leading-snug">
        A <span className="inline-flex items-center gap-1 text-alarm"><span aria-hidden="true" className="material-symbols-outlined" style={{ fontSize: 22 }}>water_drop</span>3.3 L/s leak on pipe 4</span> makes S2 and S3 read{" "}
        <strong>0.92 m below</strong> the same network without it.
      </p>
      <p className="font-mono-cad text-[11px] text-paler">SENSOR NOISE σ = 0.05 m // SAME NETWORK, SAME TIME OF DAY, LEAK ON vs OFF</p>
      <div className="grid grid-cols-2 gap-3 max-w-md">
        <div className="cad-well p-3"><div className="mono-label text-paler">INSTANT</div><div className="text-xs mt-1">one reading crosses its limit</div></div>
        <div className="cad-well p-3"><div className="mono-label text-paler">CUMULATIVE</div><div className="text-xs mt-1">small gaps add up over time</div></div>
      </div>
    </div>
  );
}

export function ReportDrawing(): JSX.Element {
  const rows = ["WHAT CHANGED", "WHY SUSPICIOUS", "WHAT TO CHECK"];
  return (
    <svg viewBox="0 0 600 300" className="w-full h-full" role="img" aria-label="Mock evidence report card with a reveal stamp">
      <Defs />
      <rect x="60" y="30" width="330" height="240" fill="#0369a1" stroke={W} strokeWidth="1.5" />
      <rect x="60" y="30" width="330" height="26" fill="url(#hatch)" stroke={W} />
      <text x="72" y="48" fontFamily="JetBrains Mono" fontSize="11" fontWeight="bold" fill={W}>EVIDENCE REPORT</text>
      {rows.map((r, i) => (
        <g key={r} transform={`translate(76 ${82 + i * 60})`}>
          <text fontFamily="JetBrains Mono" fontSize="10" fill="#bae6fd">{r}</text>
          <line x1="0" y1="14" x2="290" y2="14" stroke={W} strokeOpacity="0.5" />
          <line x1="0" y1="26" x2="230" y2="26" stroke={W} strokeOpacity="0.3" />
        </g>
      ))}
      <g transform="translate(470 150) rotate(-12)">
        <rect x="-70" y="-26" width="140" height="52" fill="none" stroke={W} strokeWidth="3" strokeDasharray="8 4" />
        <text textAnchor="middle" y="9" fontFamily="Sora" fontWeight="800" fontSize="26" fill={W}>REVEAL</text>
      </g>
    </svg>
  );
}
