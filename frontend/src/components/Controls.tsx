// Controls — run/pause, speed, reset. Renders API values only; no hydraulic math (P1).
import { useSimStore } from "../state/simulationStore";

const SPEEDS: [1 | 5 | 20, string][] = [[1, "1×"], [5, "5×"], [20, "20×"]];

export function Controls(): JSX.Element {
  const { running, speed, view, connection, toggleRun, setSpeed, reset } = useSimStore();
  const disabled = !view || connection === "offline";
  return (
    <section className="cad-panel p-4 flex flex-col gap-3" aria-label="Simulation controls">
      <div className="mono-label text-paler">// CONTROLS</div>
      <div className="flex gap-2">
        <button className={`flex-1 py-2 font-mono-cad font-bold text-xs flex items-center justify-center gap-2 ${running ? "cad-btn-active" : "cad-btn-primary"}`} disabled={disabled} onClick={toggleRun} aria-pressed={running}>
          <span aria-hidden="true" className="material-symbols-outlined">{running ? "pause" : "play_arrow"}</span>{running ? "PAUSE" : "RUN"}
        </button>
        <button className="cad-btn-secondary px-4 py-2 font-mono-cad font-bold text-xs flex items-center gap-2" disabled={disabled} onClick={() => void reset()}>
          <span aria-hidden="true" className="material-symbols-outlined">restart_alt</span>RESET
        </button>
      </div>
      <div>
        <div className="flex gap-2" role="group" aria-label="Speed">
          {SPEEDS.map(([s, label]) => (
            <button key={s} className={`flex-1 py-1.5 font-mono-cad text-xs ${speed === s ? "cad-btn-active" : "cad-btn-secondary"}`} onClick={() => setSpeed(s)} aria-pressed={speed === s}>{label}</button>
          ))}
        </div>
        <div className="font-mono-cad text-[10px] text-paler mt-2">= 5 / 25 / 100 sim-min per second</div>
      </div>
    </section>
  );
}
