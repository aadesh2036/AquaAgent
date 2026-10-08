# 09_FRONTEND.md
Backbone version: backbone/1.1.0 | Gate: **G9** | Tier: **T1** (local) / T2a (Amplify) | Est. effort: 10 h
Depends on: shared contracts (Day 1, mock mode) · 01 (exported topology) · 08 (real API) · 03 (Amplify, T2a) | Blocks: 10 | Schedule slot: Day 1 PM (static network + first vertical slice) · Day 2 PM (menus) · Day 3 PM (challenge + report + reveal) (BACKBONE §13)

## 1. Purpose
The judge-facing **interactive miniature water network**. It is a native-SVG P&ID of `net_epa_tutorial_v1` with animated flow, tank level, sensor beacons and leak droplets, and three modes: **Explore** (taps), **Break it** (pipe leak/burst/close, valve) and **Test the AI** (hidden challenge → detection → template explanation → reveal). It **renders API values only** and never computes hydraulics (P1).

## 2. Inputs — contracts consumed
- §7.14.1 public API (`NetworkView`, `NetworkTopology`, `ChallengeStartResponse`, `ChallengeStatusResponse`, `AgentReport`, `ChallengeReveal`, health), `X-Api-Key` (T2a), `X-Aqua-Contract`
- §7.15 `SimStore` shape + rendering rules; §6.2 coordinates and zones (via `/network/topology`)
- §7.13 `AgentReport.generated_by`, `grounding_check`; §7.11 language rule; §5.2/§5.3 formatting only via `@units` (speed 1×/5×/20× = 5/25/100 sim-min per second)
- `shared/contracts/contracts.ts` (`@contracts`), `shared/units.ts` (`@units`), `shared/contracts/generated/examples.json` (mock fixtures)
- Visual direction: `CONTEXT/AquaAgent_handoff.md` §22–§26 (precedence below BACKBONE)

## 3. Outputs — contracts produced
- T1: a local site at :5173 (`docker compose` / `npm run dev`). T2a: Amplify site.
- No new contracts.

## 4. Files owned
`frontend/` (all), `amplify.yml` (co-owned with 03).

## 5. Design decisions (binding)
- **React + TS + Vite + native SVG + CSS animations** (handoff §25). No Three.js, CFD, chart dashboards or graph editors. Zustand store with exactly the §7.15 shape. Positions come from topology x/y (scaled to the viewBox).
- **Visual direction (handoff §22, §26):** light/white background, blue water, dark engineering lines, restrained accents, whitespace, network as hero, no cards covering the network. Status bar: `Pressure … m | Flow … L/s | Tank …% | Network NORMAL`. Node inspector on selection.
- **Tick:** when running, every 1 s → `POST /sim/step {steps: speed}`; `view` replaced wholesale. No interpolation of values.
- **Flow animation:** `stroke-dasharray` + animated `stroke-dashoffset`. Duration *mapped* from `|flow_lps|` (a display mapping, not hydraulics), direction from `direction`, zero → stopped. **Tank:** clipped blue rect with height = `level_pct`. **Leak:** droplets/stream/spray intensity from `visual_fault` only (handoff §25).
- **Modes (handoff §24):** Explore (tap menu: open/close, demand in L/min via `@units`), Break it (pipe menu: Leak / Burst / Close / Reset; V1 tooltip "pipe 7 status", §6.2 honesty note), Test the AI (challenge panel).
- **Challenge flow:** TEST THE AI → `/challenge/start` (medium) → poll `/challenge/status` every 1 s → DETECTED → `/agent/diagnose` → report panel → REVEAL → `/challenge/reveal`: truth vs AI (detected?, delay; rank/zone from T2c when non-null).
- **Report panel:** headline, what/why/evidence/actions, confidence, caveats. **"template explanation" label** when `generated_by === "template"`. **Grounding badge**: green when passed, amber listing `unmatched_numbers` otherwise.
- **Mock-API mode from Day 1** (`VITE_MOCK_API=true`), serving recorded/fixture responses only.
- **No hydraulic math:** `scripts/check-no-hydraulics.sh` runs in CI and in the Amplify build.
- Language: "probable leak zone", "most likely pipe". No accuracy claims in the UI.

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `npm install`; app shell; aliases; mock API from `generated/examples.json`; static SVG network from topology (mock topology built from §6.2 until 01 exports the JSON). | `npm run dev` shows the network in mock mode; `npm run lint` passes. |
| 2 | Store (§7.15) + `client.ts` (fetch, contract-header check, `X-Api-Key` when set). | Switching `VITE_MOCK_API` swaps implementations; a header mismatch shows a banner. |
| 3 | Live view against local 08: run/pause, speed, 1-s tick; flow animation; tank; status bar. **First vertical slice (handoff §39) done.** | Time advances by speed × 5 min per second; flows animate only when ≠ 0. |
| 4 | Inspector + tap/pipe/valve menus; leak animation from `visual_fault`. | Opening T2 changes node-4 values on the next tick; a pipe leak shows droplets. |
| 5 | Challenge panel + report panel (label, badge) + reveal view. | Local E2E: start → DETECTED → report → reveal. |
| 6 | Responsive pass (1366×768, phone portrait); `check-no-hydraulics` green; `npm run build`. | Screenshots at both sizes noted in TILL_NOW. |
| 7 | (T2a) Amplify via `bash infra/scripts/15_amplify_app.sh` (+ MANUAL STEP), CORS refresh. | Amplify URL runs the demo against the AWS API. |

## 7. AWS steps
T1: none. T2a: `make deploy-frontend` (script 15, MANUAL STEP: GitHub OAuth), then `bash infra/scripts/11_ssm_params.sh && bash infra/scripts/09_ecs_service.sh` (CORS for the Amplify origin).

## 8. Tests
- Static: `tsc --noEmit`; `check-no-hydraulics.sh`.
- Contract: client asserts `X-Aqua-Contract`; mocks come from generated examples.
- Manual checklist (record in TILL_NOW): tick, pause, speeds, each menu, leak visuals, challenge flow, badge/label states.
- Firewall (UI): `grep -RIn "hidden\|LK_" frontend/src` → no hits.

## 9. Acceptance gate — G9
- [ ] no hydraulic math in frontend code (grep check)
- [ ] runs the full demo against the local API (T2a: deployed on Amplify against the AWS API)
- [ ] usable at 1366×768 and on a phone in portrait
- [ ] (module) template label + grounding badge render correctly; mock mode still works

## 10. Risks and fallbacks
- Animation jank at 20×: cap at 5× in the UI.
- Topology JSON not ready: mock topology from §6.2 coordinates (same numbers).
- Venue Wi-Fi: local `docker compose` stack + mock mode.

## 11. Handoff
- To **10**: demo flow timings, screenshots, mock mode for rehearsal.

## 12. Agent prompt
```
You are implementing module 09 (Frontend) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md, docs/modules/09_FRONTEND.md, TILL_NOW.md, and
CONTEXT/AquaAgent_handoff.md §22–§26 (visual direction only). Read nothing else.
Implement §6 in order (step 7 only after gate MVP); after each run its "done when" check plus
`cd frontend && npm run lint && bash scripts/check-no-hydraulics.sh`, update TILL_NOW.md, STOP.
Only edit files in §4. Import types from @contracts and formatting from @units. The frontend performs NO
hydraulic arithmetic. Start in mock mode. If a contract is wrong, write it under §13 and stop.
Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
