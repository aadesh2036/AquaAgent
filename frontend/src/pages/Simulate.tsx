import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { clockLabel } from "@units";
import { CONTRACT_VERSION } from "@contracts";
import { Header } from "../components/Header";
import { NetworkCanvas } from "../components/NetworkCanvas";
import { Controls } from "../components/Controls";
import { Inspector, type SimMode } from "../components/Inspector";
import { ChallengePanel } from "../components/ChallengePanel";
import { AgentReport } from "../components/AgentReport";
import { MOCK_HAS_FIXTURES } from "../api/mock";
import { API_BASE_URL, useSimStore, type Connection } from "../state/simulationStore";
import { fmtLps, fmtM, fmtPct, layoutOf } from "../lib/display";
import { CityLink } from "../components/CityLink";

const MODES: [SimMode, string][] = [["explore", "EXPLORE"], ["break", "BREAK IT"], ["challenge", "TEST THE AI"]];

function ModeTabs({ mode, onMode }: { mode: SimMode; onMode: (m: SimMode) => void }): JSX.Element {
  return (
    <div className="flex gap-1" role="tablist" aria-label="Mode">
      {MODES.map(([m, label]) => (
        <button key={m} role="tab" aria-selected={mode === m} onClick={() => onMode(m)}
          className={`px-3 py-1.5 font-mono-cad text-[11px] whitespace-nowrap ${mode === m ? "cad-btn-active" : "cad-btn-secondary"}`}>{label}</button>
      ))}
    </div>
  );
}

function ConnBadge({ c }: { c: Connection }): JSX.Element {
  const map: Record<Connection, [string, string]> = {
    live: ["LIVE API", "bg-white text-blueprint"],
    mock: ["MOCK DATA", "border border-dashed border-white text-white"],
    offline: ["API OFFLINE", "border border-alarm text-alarm"],
    unknown: ["CONNECTING…", "border border-white/50 text-pale"],
  };
  const [t, cls] = map[c];
  return <span className={`font-mono-cad text-[10px] font-bold px-2 py-1 whitespace-nowrap ${cls}`}>{t}</span>;
}

function StatusBar(): JSX.Element {
  const { view, topology } = useSimStore();
  const layout = layoutOf(topology);
  const parts: string[] = [`CLOCK ${view?.clock ?? "--:--"}`];
  for (const p of layout.pressure) parts.push(`${p.sensor_id} ${fmtM(view?.nodes[p.node_id]?.pressure_m)}`);
  for (const f of layout.flow) parts.push(`${f.sensor_id} ${fmtLps(view?.links[f.link_id]?.flow_lps)}`);
  parts.push(`TANK ${fmtPct(view?.tank.level_pct)}`);
  const status = view?.network_status ?? "—";
  return (
    <div className="fixed bottom-0 inset-x-0 z-40 bg-panel border-t border-white/40" role="status">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-9 flex items-center gap-3 overflow-x-auto whitespace-nowrap font-mono-cad text-[11px]">
        {parts.map((p) => <span key={p}>{p}<span className="text-white/40 ml-3">|</span></span>)}
        <span className={status === "NORMAL" ? "font-bold" : status === "—" ? "" : "font-bold text-alarm"}>NETWORK {status}</span>
      </div>
    </div>
  );
}

function Events(): JSX.Element {
  const events = useSimStore((s) => s.view?.events);
  const list = [...(events ?? [])].reverse().sort((a, b) => b.sim_time_s - a.sim_time_s);
  return (
    <section className="cad-panel p-4" aria-label="Events">
      <div className="mono-label text-paler mb-2">// EVENTS</div>
      {list.length === 0 ? <p className="text-sm text-pale">Nothing has happened yet. Run the simulation or change something on the drawing.</p> : (
        <ul className="flex flex-col gap-1 max-h-48 overflow-y-auto">
          {list.map((e, i) => (
            <li key={`${e.sim_time_s}-${i}`} className="text-xs flex gap-3"><span className="font-mono-cad text-paler shrink-0">{clockLabel(e.sim_time_s)}</span><span>{e.text}</span></li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Simulate(): JSX.Element {
  const { topology, view, running, selection, connection, error, contractMismatch, report, loadTopology, select, useMockData } = useSimStore();
  const [mode, setMode] = useState<SimMode>("explore");

  useEffect(() => { void loadTopology(); }, [loadTopology]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => {
      if (document.visibilityState !== "visible") return; // pause the tick while the tab is in the background
      void useSimStore.getState().step();
    }, 1000);
    return () => clearInterval(t);
  }, [running]);

  const offline = connection === "offline" && !topology;

  return (
    <div className="min-h-screen pb-14">
      <Header tag="SIM://WNTR-1.5" center={<ModeTabs mode={mode} onMode={setMode} />}
        right={<><ConnBadge c={connection} /><CityLink className="font-mono-cad text-[10px] text-pale underline whitespace-nowrap max-sm:hidden">City view (demo)</CityLink><Link to="/" className="cad-btn-secondary px-3 py-1.5 font-mono-cad text-[11px] whitespace-nowrap">← OVERVIEW</Link></>} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pt-20">
        <div className="md:hidden mb-4 overflow-x-auto"><ModeTabs mode={mode} onMode={setMode} /></div>

        {contractMismatch && (
          <div role="alert" className="mb-4 border border-alarm text-alarm bg-well px-4 py-2 font-mono-cad text-[11px]">
            CONTRACT MISMATCH: the API speaks {contractMismatch}, this frontend expects {CONTRACT_VERSION}. Values may be wrong.
          </div>
        )}
        {connection === "mock" && MOCK_HAS_FIXTURES && (
          <div role="status" className="mb-4 border border-dashed border-white bg-well px-4 py-2 font-mono-cad text-[11px]">MOCK DATA — recorded from the live API. Steps replay a recorded session.</div>
        )}
        {connection === "mock" && !MOCK_HAS_FIXTURES && (
          <div role="status" className="mb-4 border border-dashed border-white bg-well px-4 py-2 font-mono-cad text-[11px]">MOCK DATA — fixtures not recorded yet. Values show as "—".</div>
        )}
        {connection === "offline" && topology && (
          <div role="alert" className="mb-4 border border-alarm text-alarm bg-well px-4 py-2 font-mono-cad text-[11px] flex flex-wrap items-center gap-3">
            <span>API OFFLINE: {error}</span>
            <button className="cad-btn-alarm px-3 py-1" onClick={() => void loadTopology()}>RETRY</button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-6 items-start">
          <div className="cad-panel-dark blueprint-grid-subtle crosshair-corner relative p-3 sm:p-4">
            <div className="mono-label text-paler mb-2">PLAN VIEW // net_epa_tutorial_v1 // SCALE N.T.S.</div>
            {offline ? (
              <div className="py-16 px-4 text-center flex flex-col items-center gap-4 max-w-xl mx-auto">
                <span aria-hidden="true" className="material-symbols-outlined text-alarm" style={{ fontSize: 40 }}>cloud_off</span>
                <p className="text-sm">Can't reach the AquaAgent API at {API_BASE_URL}. Start it with <code className="font-mono-cad">make sim-serve</code> and <code className="font-mono-cad">make api-serve</code>, or switch to mock data.</p>
                <div className="flex gap-3">
                  <button className="cad-btn-primary px-4 py-2 font-mono-cad text-xs font-bold" onClick={() => void loadTopology()}>RETRY</button>
                  <button className="cad-btn-secondary px-4 py-2 font-mono-cad text-xs font-bold" onClick={() => useMockData(true)}>USE MOCK DATA</button>
                </div>
              </div>
            ) : topology && view ? (
              <div><NetworkCanvas topology={topology} view={view} running={running} selection={selection} onSelect={select} /></div>
            ) : (
              <div className="py-24 text-center font-mono-cad text-xs text-paler aq-pulse">LOADING NETWORK…</div>
            )}
          </div>

          <aside className="flex flex-col gap-4">
            <Controls />
            {mode === "challenge" ? <ChallengePanel onBreak={() => setMode("break")} /> : <Inspector mode={mode} onMode={setMode} />}
            <AgentReport report={report} />
            <Events />
          </aside>
        </div>
      </main>
      <StatusBar />
    </div>
  );
}
