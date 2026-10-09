// BACKBONE §7.15 — the store shape is a contract (SimStore in @contracts).
import { create } from "zustand";
import type { SimStore } from "@contracts";
import { createHttpApi, DEFAULT_API_BASE_URL, type AquaApi } from "../api/client";
import { createMockApi } from "../api/mock";
import type { AiState } from "../api/ai";

export type { SimStore };

export type Connection = "unknown" | "live" | "mock" | "offline";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL;
const ENV_MOCK = import.meta.env.VITE_MOCK_API === "true";

export interface SimState extends SimStore {
  connection: Connection;
  error: string | null;
  contractMismatch: string | null;
  inFlight: boolean;
  api: AquaApi;
  loadTopology: () => Promise<void>;
  reset: () => Promise<void>;
  step: () => Promise<void>;
  setSpeed: (s: 1 | 5 | 20) => void;
  toggleRun: () => void;
  setRunning: (on: boolean) => void;
  select: (sel: SimStore["selection"]) => void;
  applyTap: (tapId: string, open: boolean) => Promise<void>;
  applyPipeFault: (linkId: string, kind: "LEAK" | "BURST" | "CLOSE" | "RESET") => Promise<void>;
  applyValve: (valveId: string, open: boolean) => Promise<void>;
  useMockData: (on: boolean) => void;
  /** AI monitor (BI-27): refreshed after every view-changing call. */
  ai: AiState | null;
  dismissed: string[];
  showAiArea: boolean;
  fetchAi: () => Promise<void>;
  ackAi: () => Promise<void>;
  dismissNotification: (id: string) => void;
  setShowAiArea: (on: boolean) => void;
}

export const useSimStore = create<SimState>((set, get) => {
  const makeHttp = (): AquaApi =>
    createHttpApi(API_BASE_URL, import.meta.env.VITE_API_KEY, {
      onContractMismatch: (v) => set({ contractMismatch: v }),
    });

  /** Run an API call that returns a NetworkView; replaces `view` wholesale. */
  async function viewCall(fn: (api: AquaApi) => Promise<SimStore["view"]>): Promise<void> {
    set({ inFlight: true });
    try {
      const view = await fn(get().api);
      set({ view, error: null, connection: get().connection === "mock" ? "mock" : "live" });
      await get().fetchAi();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "request failed", connection: get().connection === "mock" ? "mock" : "offline", running: false });
    } finally {
      set({ inFlight: false });
    }
  }

  return {
    topology: null, view: null, speed: 1, running: false, selection: null,
    challenge: { state: "IDLE" }, report: null,
    connection: ENV_MOCK ? "mock" : "unknown", error: null, contractMismatch: null, inFlight: false,
    api: ENV_MOCK ? createMockApi() : makeHttp(),

    loadTopology: async () => {
      set({ inFlight: true, error: null });
      try {
        const api = get().api;
        if (get().connection !== "mock") {
          await api.health();
        }
        const topology = await api.topology();
        const view = await api.state();
        set({ topology, view, connection: get().connection === "mock" ? "mock" : "live", error: null });
        await get().fetchAi();
      } catch (e) {
        set({ error: e instanceof Error ? e.message : "request failed", connection: get().connection === "mock" ? "mock" : "offline", running: false });
      } finally {
        set({ inFlight: false });
      }
    },
    ai: null, dismissed: [], showAiArea: true,
    fetchAi: async () => {
      try {
        set({ ai: await get().api.aiState() });
      } catch {
        // AI is optional: the simulator keeps working if the monitor endpoint is missing
      }
    },
    ackAi: async () => {
      try { set({ ai: await get().api.aiAck() }); } catch { /* ignore */ }
    },
    dismissNotification: (id) => set((s) => ({ dismissed: [...s.dismissed, id] })),
    setShowAiArea: (on) => set({ showAiArea: on }),
    reset: async () => {
      set({ running: false, selection: null, dismissed: [] });
      await viewCall((api) => api.sessionReset());
    },
    step: async () => {
      if (get().inFlight) return; // skip a tick while a request is outstanding
      const { speed } = get();
      await viewCall((api) => api.step(speed));
    },
    setSpeed: (speed) => set({ speed }),
    toggleRun: () => set((s) => ({ running: !s.running })),
    setRunning: (running) => set({ running }),
    select: (selection) => set({ selection }),
    applyTap: (id, open) => viewCall((api) => api.tap(id, open)),
    applyPipeFault: (id, kind) => viewCall((api) => api.pipeFault(id, kind)),
    applyValve: (id, open) => viewCall((api) => api.valve(id, open)),
    useMockData: (on) => {
      set({
        api: on ? createMockApi() : makeHttp(), connection: on ? "mock" : "unknown",
        topology: null, view: null, error: null, running: false, selection: null,
      });
      void get().loadTopology();
    },
  };
});
