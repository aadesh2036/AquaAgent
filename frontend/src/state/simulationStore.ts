// BACKBONE §7.15 — the store shape is a contract (SimStore in @contracts).
import type { SimStore } from "@contracts";

export type { SimStore };

/** Zustand store per §7.15. `view` is replaced wholesale on every API response. */
export function createSimulationStore(): never {
  throw new Error("NOT IMPLEMENTED — see docs/modules/09_FRONTEND.md");
}
