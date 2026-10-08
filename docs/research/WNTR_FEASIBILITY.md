# Research notes behind backbone/1.1.0 (2026-10-08)

The research and measurements used to resolve `docs/BACKBONE_ISSUES.md`. Re-run the measurements with `make feasibility` (script: `docs/research/wntr_feasibility_spike.py`, Python 3.12, `wntr==1.5.0`).

## 1. The EPA tutorial network has no official `.inp` (→ BI-21)

- The EPANET 2.2 manual's Quick Start (https://usepa.github.io/EPANET2.2/2_quickstart.html) builds the network by hand in the GUI and saves `tutorial.net`, a binary project file. It does not provide an `.inp`. The GitHub tutorial (https://github.com/USEPA/EPANET/blob/main/tutorial/tutorial.md) doesn't either.
- The text states only pipe 1 (2→3), pipe 8 (5→6, curved) and pump 9 (1→2). Everything else comes from **Fig. 2.1** (copy: `epanet22_fig2_1_tutorial_network.jpeg`):

```
SOURCE 1 ─pump 9─ 2 ─1─ 3 ─2─ 7 ─6─ 8 TANK
                        │     │
                        3     5
                        │     │
                        4 ─4─ 6
                        │    ╱
                        7   8 (curved)
                        │ ╱
                        5
```
- Table 2.2: lengths 3000/5000/5000/5000/5000/7000/5000/7000 ft, diameters 14/12/8/8/8/10/6/6 in, C = 100. Tank: 830 ft, Ø 60 ft, max 20 ft. The initial level is given as **3.5 ft** in one place and **4 ft** in another. We keep D3 = 3.5 ft (1.07 m).
- **Decision:** BACKBONE §6.2 states the connectivity once. Module 01 builds the network from the tables and exports the `.inp`/`.json`, and a test checks the exported topology against §6.2.

## 2. WNTR facts that shaped the design

| Question | Finding | Source |
|---|---|---|
| Latest version / Python support | `wntr` **1.5.0** on PyPI. Wheels exist for **cp310–cp313 only**, so the laptop's Python 3.14 cannot install it (→ BI-22: Python 3.12 via `uv`) | https://pypi.org/project/wntr/ (JSON API, checked 2026-10-08) |
| Stop/restart | Only the WNTRSimulator can "pause a hydraulic simulation, change network operations, and then restart". You change `wn.options.time.duration` and run a new simulator. `wn.reset_initial_values()` returns the model to t=0 | https://usepa.github.io/WNTR/hydraulics.html |
| Leaks | The WNTRSimulator has a built-in leak model (C_d default 0.75; exponent fixed at 0.5). Leaks can go on junctions or tanks, and a pipe leak = split the pipe and add a node. The EpanetSimulator uses emitters instead | same page |
| PDD | Both simulators support it (EPANET 2.2). Per-node required/minimum pressure only in WNTRSimulator | same page |

## 3. Measurements (this repo's spike, 2026-10-08)

| Measurement | Result | Used for |
|---|---|---|
| 24-h EPS at 300 s | 289 steps in **0.22–0.27 s** | ds1 can be generated locally in minutes, so ECS RunTask moves to T3 (§8.6) |
| Healthy junction pressure range (PDD 20/0) | **34.9–58.0 m** (≥ 20 m) | G1 baseline criterion |
| Tank level over 24 h | 1.07–2.54 m (max 6.10 m) | sanity |
| Mass balance, healthy / with leak | 1.4e-17 / 1.4e-17 m³/s (Σ demand + Σ leak_demand) | §7.4 formula in WNTR terms |
| Pre-split every pipe at 0.5 vs plain network | max \|ΔP\| **1.7e-5 m** | §6.3: pre-split pipes (no topology change mid-run) |
| Pipe-4 leak 1.5e-4 m² (3.0 L/s), ΔP at S1/S2/S3 after 2 h | −0.19 / **−0.81 / −0.80 m** (16× the 0.05 m noise σ) | the core detection signal is real |
| Stop at 10 h, add leak, restart to 24 h vs full run | **identical** (max \|ΔP\| ≤ 3e-14 m) | stepwise interactive mode works; replay is only a fallback |
| One 300-s step advance | **≈18–19 ms** | 20× speed = 20 steps per 1-s tick ≈ 0.4 s, which fits the tick |
| Leak area → share of mean system demand (40.9 L/s), pipe 4 | 2e-5 → 1.0% · 8e-5 → 4.0% · 2.5e-4 → 12.1% · 6e-4 → 25.7% · 3e-3 → 72.9% | §8.1 provisional ranges already match the severity buckets |
| Large leak / burst pressure floor | 18.2 m at 6e-4 m², 6.7 m at 3e-3 m² | PDD reduces delivery under bursts, which is realistic |

## 4. AWS facts (affect T2 only)

| Topic | Finding | Source |
|---|---|---|
| API Gateway **HTTP API** integration timeout | **30 s, not adjustable**. REST APIs (Regional/private) can request more than 29 s, at the cost of throttle quota | https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html · https://repost.aws/knowledge-center/api-gateway-timeout-limit |
| Bedrock Claude on-demand calls | Newer Claude models reject bare model IDs for on-demand calls ("on-demand throughput isn't supported"). You must call an **inference profile** (`us.`/`global.` prefix). IAM must allow the `inference-profile` ARN **and** the `foundation-model` ARNs in every region the profile routes to | https://docs.aws.amazon.com/bedrock/latest/userguide/inference-how.html · https://braintrust.dev/docs/kb/bedrock-model-variations-for-on-demand-throughput |

## 5. Resulting design choices (see BACKBONE §17 changelog 1.1.0)

1. **Single 300-s cadence** for dataset and interactive mode. It is cheap (18 ms/step) and removes every train/serve cadence bug (BI-01).
2. **Pre-split pipes**, so a leak is `add_leak` on an existing `LK_<pipe>` node and topology never changes mid-run (BI-21 risk removed).
3. **Local datagen** (minutes), then `aws s3 sync`. ECS RunTask is T3.
4. **MVP first:** the T1 loop is sim → data → MLP (5-sensor LOO) → RTCA detector → orchestrator challenge → TemplateReporter → SVG UI, all local. AWS, SageMaker, localisation and Bedrock follow, in that order.
