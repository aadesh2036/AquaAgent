# AquaAgent frontend design system

Visual language: an engineering blueprint. Chalk-white linework on deep blue, mono labels, CAD marks. Owner reference: `design/blueprint_template_reference.html` (visual system only; its copy is not reused).

## Routes
- `/` Landing (`pages/Landing.tsx`): overview, how it works, architecture, honest limits. Marketing, but every claim is true or measured.
- `/simulate` Simulator (`pages/Simulate.tsx`): the product. Plan view of `net_epa_tutorial_v1` driven by the API (or recorded mock data). Modes EXPLORE, BREAK IT, TEST THE AI.
- `/city` City view, CONCEPT DEMO (`pages/City.tsx`, lazy-loaded): illustrative city-scale operator view. Not live data, not a real utility; carries a permanent banner. Nothing on it is measured.

## Tokens (`tailwind.config.js`, `src/styles/blueprint.css`)
| Token | Hex | Role |
|---|---|---|
| ground `blueprint` | #035a8c | page ground, text-on-white buttons (white on it >= 7:1) |
| panel | #0369a1 | cards, header strips, `.cad-panel` |
| well | #075985 | drawing wells, inputs, `.cad-panel-dark` |
| chalk | #ffffff | primary text, pipes, borders (borders at 25-40% alpha) |
| pale | #e0f2fe | secondary text |
| paler | #bae6fd | mono labels on panels only (not on the bare background; 4.2:1 worst case there) |
| alarm | #fbbf24 | the ONLY accent |
| ai | #f0abfc | **AI-estimated content only** (BY AI chips, AI-estimated area on the plan view); dark ink `ai-ink` #3b0764 on it (8.5:1). Marks 4.3:1 on `well` |
Single amber rule: amber is used only for leaks, bursts, low/critical pressure, anomaly states and the concept-demo stamp. Never decoration. **AI rule (owner, 2026-10-09):** the `ai` fuchsia marks only what the AI estimated, is always paired with a "BY AI" label and dashed strokes (never colour alone; its luminance is close to amber), and never replaces the simulator's own amber leak/burst visuals, which stay on top. `/city` uses red (#f87171) for exactly one "critical (example)" marker.
The WebGL background is kept dark: worst-case stacked brightness (wave + contour + cursor glow + grid line + grain) gives white 5.6:1 and #e0f2fe 4.9:1.

## Typography
Sora: headings (800/700, tight tracking). Inter: body and UI copy. JetBrains Mono: all CAD labels, data, buttons, status bar (uppercase, small, tracked). Caveat: ONE handwritten word in the hero ("where."), nowhere else. Icons: Material Symbols Outlined (decorative, `aria-hidden`).

## Spacing and borders
Square corners everywhere (no radius except pills/dialog on /city). 1px white borders at 25-40% alpha; `border-2 border-white` marks emphasis. 4 px base spacing, page gutter 16 px (24 px from `sm`), content max width `max-w-7xl`. Fixed header 56 px (`h-14`); content offsets with `pt-14/pt-20`.

## CAD motifs (classes in blueprint.css)
`crosshair-corner` (+ marks at two corners), `cad-corner-marks` (L brackets), `blueprint-hatch-subtle`, `blueprint-grid-subtle`, `cad-panel` / `cad-panel-dark` / `cad-well`, `cad-btn-primary|secondary|active|alarm`, `tag-chip`, `mono-label`. Captions read like drawing titles: `PLAN VIEW // net_epa_tutorial_v1 // SCALE N.T.S.`.

## Components
- `components/CityLink.tsx` link into `/city`: preloads the lazy chunk on hover/focus, then a View Transitions circular reveal from the click point (`html[data-transition="city"]` rules in blueprint.css); fallback `.city-enter` fade; none under reduced motion. Use it for every link to `/city`.
- `components/BlueprintBackground.tsx` raw-WebGL blueprint water background; static frame for reduced motion; CSS grid fallback; pauses in background tabs.
- `components/Header.tsx` fixed header (brand mark, tag, center and right slots).
- `components/NetworkCanvas.tsx` SVG plan view; per-node label offsets; flow dashes, tank fill, leak droplets, sensors, taps, V1.
- `components/Controls.tsx` run/pause, speed, reset. `Inspector.tsx` selection details and actions. `ChallengePanel.tsx` TEST THE AI (disabled until the detector exists). `AgentReport.tsx` evidence report (renders only when a report exists).
- `components/landing/HowItWorks.tsx` slider with progress conduit; `landing/Drawings.tsx` the five schematics; `landing/Sections.tsx` telemetry band, architecture deck, honest limits, footer.
- `components/AiMonitor.tsx` AI monitor panel (status, anomaly-probability sparkline, SIMULATED vs AI table for every node/flow sensor, BY AI probable area + candidates, acknowledge). `components/AiToast.tsx` sticky AI alert banner above the plan view (never floats over the controls). `Inspector.tsx` shows a SIMULATED vs AI side-by-side for the selected node / flow-sensor pipe. `NetworkCanvas.tsx` draws the BY AI area (zone wash, dashed candidate pipes/junctions, `AI #n` chips, legend) under the node glyphs.
- `state/simulationStore.ts` zustand store (SimStore from `@contracts` plus connection status). `api/client.ts` HTTP client; `api/mock.ts` fixture-backed mock; `lib/display.ts` formatting and display mappings.

## Motion
CSS keyframes in blueprint.css (`aq-flow`, `aq-drip`, `aq-spray`, `aq-pulse`, `aq-sonar`, `aq-flow-main`). `flowAnimationDuration(lps)` in `lib/display.ts` maps |flow| to 0.6-6 s for display only; zero flow or paused sim means no animation; direction -1 reverses. `prefers-reduced-motion` collapses all CSS animation and stops autoplay and the WebGL loop. Motion never encodes data that is not also shown as text. Route transitions: only the entry into `/city` animates (the one orchestrated moment); other route changes are instant.

## Accessibility floor
Text contrast >= 4.5:1 (check the amber and paler tokens against their backing). Visible focus: `:focus-visible` 2 px white outline, offset 2 px. Interactive SVG elements are `role="button"`, `tabIndex=0`, with `aria-label`, and respond to Enter/Space. Decorative SVG/icons carry `aria-hidden="true"`. Layout works at 390 px with no horizontal page scroll; node labels hide below 480 px, sensor ids stay.

## Data rules
Render API values only. No hydraulic arithmetic (only `@units` formatting and display mappings). Types come from `@contracts`, units from `@units`; never redeclare. Two guard scripts run inside `npm run lint`: `scripts/check-no-hydraulics.sh` and `scripts/check-no-truth-fields.sh` (fails on `.hidden`, `"hidden":`, `LK_`; the English word "hidden" in copy is fine). Mock mode (`VITE_MOCK_API=true` or the offline "use mock data" button) serves `src/api/fixtures/*.json`. Re-record against the live stack: `node scripts/record_fixtures.mjs [baseUrl]` (writes topology.json, view.json, views_sequence.json). Missing values render as an em dash, never a plausible number. Env: `VITE_API_BASE_URL` (default http://localhost:8080), `VITE_API_KEY`, `VITE_MOCK_API`.

AI data (BI-27): `GET /api/ai/state` after every view-changing call; types in `src/api/ai.ts` (not yet in `@contracts`). The AI values are estimates from sensors + SCADA only; the SIMULATED column is the physics truth the explore mode already shows. The only arithmetic is the display difference `fmtDelta`.

## Copy rules
BACKBONE section 16: only true or measured statements; numbers trace to our own runs. Say "probable leak zone" and "most likely pipe", never accuracy claims. The simulator is synthetic: say so. V1 is pipe 7's status, not an EPANET valve object. Unbuilt things are labelled LIVE / BUILDING / NEXT. Anything illustrative is tagged "illustrative" and `/city` is always labelled CONCEPT DEMO. Do not name real organisations or people.

## Adding a page
1. Create `src/pages/Name.tsx` (default to a named export). Reuse `Header` and the CAD classes; use tokens, not new hex values.
2. Register it in `src/App.tsx`; lazy-load with `React.lazy` unless it is core to the first paint.
3. Link it from the header or footer where it belongs. Decide its data source (store, mock, or none) and label any non-live content.
4. Add its guarantees to this file.

## Checks before finishing
`npm run lint` (tsc + both grep scripts), `npm run build`, then screenshots at 1366x768 and 390x844 into `design/screens/` (headless Chrome + playwright-core works) and look at them. Run `/simulate` against a live API when touching the store, client or canvas.
