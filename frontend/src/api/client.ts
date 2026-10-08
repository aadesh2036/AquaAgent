// Typed client for BACKBONE §7.14.1. Adds X-Api-Key; asserts X-Aqua-Contract == CONTRACT_VERSION.
import { CONTRACT_VERSION } from "@contracts";
import type {
  AgentReport, ChallengeReveal, ChallengeStartResponse, ChallengeStatusResponse, Difficulty,
  HealthResponse, NetworkTopology, NetworkView, PipeFaultKind,
} from "@contracts";

export interface AquaApi {
  health(): Promise<HealthResponse>;
  sessionReset(seed?: number): Promise<NetworkView>;
  topology(): Promise<NetworkTopology>;
  state(): Promise<NetworkView>;
  step(steps: number): Promise<NetworkView>;
  tap(tapId: string, open: boolean): Promise<NetworkView>;
  pipeFault(linkId: string, kind: PipeFaultKind): Promise<NetworkView>;
  valve(valveId: string, open: boolean): Promise<NetworkView>;
  challengeStart(difficulty?: Difficulty): Promise<ChallengeStartResponse>;
  challengeStatus(): Promise<ChallengeStatusResponse>;
  diagnose(incidentId: string): Promise<AgentReport>;
  reveal(): Promise<ChallengeReveal>;
}

export const DEFAULT_API_BASE_URL = "http://localhost:8080";

export interface HttpApiOptions {
  /** Called with the server's X-Aqua-Contract value whenever it differs from CONTRACT_VERSION. */
  onContractMismatch?: (serverVersion: string) => void;
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}

export function createHttpApi(baseUrl: string, apiKey?: string, opts: HttpApiOptions = {}): AquaApi {
  const root = baseUrl.replace(/\/+$/, "");

  async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (apiKey) headers["X-Api-Key"] = apiKey;
    let res: Response;
    try {
      res = await fetch(`${root}/api${path}`, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      throw new ApiError(e instanceof Error ? e.message : "network error");
    }
    const contract = res.headers.get("X-Aqua-Contract");
    if (contract && contract !== CONTRACT_VERSION) opts.onContractMismatch?.(contract);
    if (!res.ok) throw new ApiError(`${method} ${path} → HTTP ${res.status}`, res.status);
    return (await res.json()) as T;
  }

  const notYet = (what: string) => (): Promise<never> =>
    Promise.reject(new ApiError(`${what} is not available yet`));

  return {
    health: () => call<HealthResponse>("GET", "/health"),
    sessionReset: (seed) => call<NetworkView>("POST", "/session/reset", { seed: seed ?? null }),
    topology: () => call<NetworkTopology>("GET", "/network/topology"),
    state: () => call<NetworkView>("GET", "/network/state"),
    step: (steps) => call<NetworkView>("POST", "/sim/step", { steps }),
    tap: (tap_id, open) => call<NetworkView>("POST", "/tap", { tap_id, open }),
    pipeFault: (link_id, kind) => call<NetworkView>("POST", "/pipe/fault", { link_id, kind }),
    valve: (valve_id, open) => call<NetworkView>("POST", "/valve", { valve_id, open }),
    challengeStart: notYet("The leak challenge"),
    challengeStatus: notYet("The leak challenge"),
    diagnose: notYet("The evidence report"),
    reveal: notYet("The reveal"),
  };
}
