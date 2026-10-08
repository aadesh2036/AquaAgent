// Typed client for BACKBONE §7.14.1. Adds X-Api-Key; asserts X-Aqua-Contract == CONTRACT_VERSION.
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

export function createHttpApi(_baseUrl: string, _apiKey?: string): AquaApi {
  throw new Error("NOT IMPLEMENTED — see docs/modules/09_FRONTEND.md");
}
