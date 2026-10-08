// Mock API (module 09, Day 1): serves recorded/fixture NetworkViews. Never computes hydraulics —
// fixtures come from shared/contracts/generated/examples.json or recorded API responses.
import type { AquaApi } from "./client";

export function createMockApi(): AquaApi {
  throw new Error("NOT IMPLEMENTED — see docs/modules/09_FRONTEND.md");
}
