// AI anomaly notification (BI-27): sticky banner above the plan view (never covers the controls).
// Shows the newest undismissed AI notification; values come from the API.
import { useSimStore } from "../state/simulationStore";
import { AiChip } from "./AiMonitor";

export function AiToast(): JSX.Element | null {
  const { ai, dismissed, dismissNotification, setShowAiArea, setRunning, explain, explaining } = useSimStore();
  const n = [...(ai?.notifications ?? [])].reverse().find((x) => !dismissed.includes(x.id));
  if (!n) return null;
  const alarm = n.status === "ANOMALY";
  return (
    <div role={alarm ? "alert" : "status"} aria-live={alarm ? "assertive" : "polite"}
      className={`sticky top-16 z-30 mb-3 bg-panel shadow-lg p-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 ${alarm ? "border-2 border-alarm" : "border-2 border-white/70"}`}>
      <div className="flex items-center gap-2 shrink-0">
        <span aria-hidden="true" className={`material-symbols-outlined ${alarm ? "text-alarm aq-pulse" : "text-white"}`}>{alarm ? "warning" : "check_circle"}</span>
        <span className={`font-mono-cad text-[11px] font-bold ${alarm ? "text-alarm" : "text-white"}`}>{alarm ? "AI ALERT" : "AI ALL CLEAR"} · {n.clock}</span>
        <AiChip />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm leading-snug">{n.text}</p>
        {alarm && <p className="text-[10px] text-paler">Anomaly probability {n.anomaly_score.toFixed(2)} · driven by {n.driving_sensors.join(", ") || "—"}</p>}
      </div>
      <div className="flex gap-2 shrink-0">
        {alarm && (
          <button className="cad-btn-primary px-3 py-1.5 font-mono-cad text-[10px] font-bold"
            onClick={() => { setShowAiArea(true); setRunning(false); dismissNotification(n.id); }}>PAUSE + SHOW AREA</button>
        )}
        {alarm && n.incident_id && (
          <button className="cad-btn-secondary px-3 py-1.5 font-mono-cad text-[10px] font-bold" disabled={!!explaining}
            onClick={() => { setShowAiArea(true); setRunning(false); dismissNotification(n.id); void explain(n.incident_id!); }}>EXPLAIN WHY</button>
        )}
        <button className="cad-btn-secondary px-3 py-1.5 font-mono-cad text-[10px]" onClick={() => dismissNotification(n.id)}>DISMISS</button>
      </div>
    </div>
  );
}
