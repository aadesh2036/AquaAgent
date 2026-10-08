# AquaAgent — BACKBONE.md

> **Find the Water Nobody Can See.**
> Physics generates reality. ML reconstructs the hidden state. Anomaly detection finds what does not fit. An agent explains the evidence and recommends action.

| Field | Value |
|---|---|
| Document | BACKBONE.md — master PRD + contract spec |
| Contract version | `backbone/1.1.0` |
| Status | FROZEN for hackathon (8–11 Oct 2026) unless changed via §17. v1.1.0 resolves `docs/BACKBONE_ISSUES.md` BI-01…BI-21 and re-tiers scope to the **MVP detection loop** (§2) |
| Owner | Aadesh Deshmukh |
| Applies to | Every module MD in `docs/modules/` and every coding agent |

---

## 0. How to Use This Document (READ FIRST — agents included)

1. **Every agent reads:** `INSTRUCTIONS.md` (process rules, no contracts), this `BACKBONE.md`, **and** the one module MD it is assigned (e.g. `docs/modules/01_SIMULATION_ENGINE.md`). `TILL_NOW.md` is read for status only. Nothing else is required context.
2. **BACKBONE owns the contracts.** Module MDs own the implementation. A module MD may *add* internal detail but may **never redefine** a schema, ID, unit, endpoint, S3 path or env var defined here.
3. **If a contract is wrong or missing:** stop, propose the change in the module MD under `## Proposed Backbone Changes`, and the owner bumps `backbone/x.y.z` (§17). Do not silently diverge.
4. **Every schema here has a Pydantic (Python) and a TypeScript twin.** They live in `shared/contracts/` and are the only place schemas are coded. Modules import them; they do not re-declare them.
5. **Precedence when documents disagree:** BACKBONE.md > module MD > `CONTEXT/AquaAgent_handoff.md` > Simulation Spec v1 > Prototype Guide > README_FOR_SIM.md.
6. Every module ends with an **acceptance gate** (§12). A module is not "done" until its gate passes.

---

## 1. Mission and Demo Promise

### 1.1 What we are proving

> In a simulated pressurised water network observed by only **3 pressure sensors + 2 flow sensors**, can a trained model reconstruct the hidden hydraulic state well enough that **deviations from it detect and localise** a hidden leak — and can an agent explain that evidence **without inventing a single number**?

### 1.2 The 60-second demo (the thing judges must see)

```
Healthy network (live WNTR physics, animated)
  → judge opens a tap → pressures/flows change for real
  → judge presses TEST THE AI → backend secretly injects a real WNTR leak
  → only S1/S2/S3 + F1/F2 readings go to the ML pipeline
  → predictor (MLP) reconstructs the expected state            [T2: served by SageMaker endpoint]
  → residuals cross dual threshold → anomaly detected
  → AquaAgent explains WHAT / WHY / EVIDENCE / ACTION from the Incident
       [T1: deterministic TemplateReporter · T2: Bedrock agent, grounded]
  → REVEAL: ground truth vs AI answer, detected?, detection delay
       [T2: + localisation rank of the true location / probable zone]
```

### 1.3 Non-negotiable principles

| # | Principle | Enforced by |
|---|---|---|
| P1 | Frontend never computes or fakes hydraulic values | §7.15, gate G9 |
| P2 | ML inference sees only `SensorWindow` (§7.8) — never ground truth, never fault labels | §11 firewall, type signatures |
| P3 | LLM never invents a number; every number in its output must exist in a tool result | §9.6 grounding check |
| P4 | Every simulation is reproducible from `(network_config, scenario_spec, seed)` | §7.2, gate G2 |
| P5 | Datasets are split by **simulation**, never by timestep | §8.5 |
| P6 | Every demo claim must be backed by a measured number from our own evaluation | §16 |

---

## 2. Frozen Scope

### 2.1 In scope (hackathon build) — v1.1.0 re-tier: "one small feature that works"

**T1 = the MVP detection loop, fully working locally (`docker compose up`).** Everything in T1 must work before any T2 item starts. The simulation is the core of everything.

| Tier | Item | Owner MD |
|---|---|---|
| **T1 — must work** | WNTR simulation engine: EPA tutorial network, PDD, real leaks, stepwise interactive session, sim server, container | 01 |
| T1 | Synthetic dataset `ds1` (1,200 sims, 8 scenario types §8.1), generated **locally**, split by simulation | 02 |
| T1 | Hydraulic state predictor: nearest-sensor baseline + **MLP** with leave-one-out over all 5 sensors | 04 |
| T1 | Residual-based RTCA dual-threshold anomaly detector (thresholds tuned on val, frozen) | 05 |
| T1 | Orchestrator API: session, challenge (hidden leak), SensorWindow firewall, predictor (in-process), detector, `Incident`, reveal | 08 |
| T1 | `TemplateReporter`: deterministic WHAT/WHY/EVIDENCE/ACTION from the `Incident` (no LLM) | 07 |
| T1 | React SVG interactive network (Explore · Break it · Test the AI), challenge + reveal UI | 09 |
| T1 | Demo script + fallback video + honest metrics | 10 |
| **T2 — high value, in this order** | T2a: AWS deploy of the T1 stack — S3 (dataset/models) + ECR + ECS (api+sim task, predictor in-process) + ALB + API Gateway + Amplify | 03 |
| T2 | T2b: SageMaker training job (same `train.py`) → real-time endpoint (`AQUA_MODE=aws` predictor) | 06 |
| T2 | T2c: signature-based localisation (top-k pipes, probable zone) | 05 |
| T2 | T2d: Bedrock AquaAgent (Converse tool use, grounding check, template fallback) | 07 |
| **T3 — only if T1+T2 green** | GNN predictor; ds2 scenario types (valve, pump, reservoir, demand spike, sensor faults); sensor-fault status; fault-type classifier; what-if counterfactual; ECS RunTask batch datagen; alternative sensor layouts; topology family | 02, 04, 05, 07 |
| T3 (future, pitch only) | RL / pressure optimisation, Step Functions, IoT Core, MLOps | — |

### 2.2 Explicitly OUT of scope

Real sensors / IoT hardware · Pune map or city-scale network · water quality · 3D/CFD · RL training · MLOps automation · multi-user sessions · authentication beyond an API key.

> **Rule:** Never sacrifice a T1 item to build a T2/T3 item. A T2 item is started only after the T1 loop runs end-to-end locally (gate **MVP**, §12).

---

## 3. System Architecture

### 3.1 Logical architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ FRONTEND  (React + TS + Vite + native SVG)        — AWS Amplify      │
│  NetworkCanvas · Inspector · Controls · ChallengePanel · AgentReport │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS, JSON, polling (§7.14)
┌───────────────────────────────▼──────────────────────────────────────┐
│ ORCHESTRATOR API  (FastAPI)                       "aquaagent-api"    │
│  session · event log · challenge state · ML pipeline · agent loop   │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐             │
│  │ SimClient    │  │ PredictorClient│ │ AgentRunner   │             │
│  └──────┬───────┘  └──────┬────────┘  └──────┬────────┘             │
│         │                 │   Detector + Localiser (in-process numpy)│
└─────────┼─────────────────┼──────────────────┼──────────────────────┘
          │ localhost HTTP  │ boto3            │ boto3 (Converse API)
┌─────────▼─────────┐ ┌─────▼──────────────┐ ┌─▼────────────────────────┐
│ SIM ENGINE        │ │ SageMaker real-time│ │ Amazon Bedrock            │
│ "aquaagent-sim"   │ │ endpoint           │ │ (Claude model, tool use)  │
│ FastAPI + WNTR    │ │ predictor model    │ └───────────────────────────┘
│ mode: serve|generate└────────▲───────────┘
└─────────┬─────────┘          │ model.tar.gz
          │ generate mode       │
          ▼                     │
┌─────────────────────┐  ┌──────┴─────────────────┐
│ S3  aquaagent-*      │─▶│ SageMaker Training Job │
│ raw/processed/models │  │ (PyTorch container)    │
└─────────────────────┘  └────────────────────────┘
```

### 3.2 Physical AWS deployment

| Component | AWS service | Notes |
|---|---|---|
| Frontend | **Amplify Hosting** (GitHub-connected, branch `main`) | env `VITE_API_BASE_URL` |
| Public HTTPS entry | **API Gateway HTTP API** → HTTP proxy to ALB | Solves mixed-content: Amplify is HTTPS, a raw ALB is HTTP. Integration timeout is a hard **30 s** (not adjustable for HTTP APIs) → every request must finish < 25 s. **CORS is owned by FastAPI** (APIGW CORS unset). Stage throttling on (the API key is visible in the browser). |
| Orchestrator + Sim engine | **ECS Fargate**, ONE task definition, TWO containers (`api` :8080, `sim` :8000) talking over `localhost` | One task = one in-memory session. `desiredCount = 1`. |
| Load balancer | **ALB** → target group on `api:8080`, health `/api/health` | |
| Batch data generation | **Local** `aquaagent-sim generate` (≈0.2 s per 24-h sim → minutes for ds1), then `aws s3 sync` | ECS RunTask of the same image = T3 (script exists, not on the critical path) |
| Images | **ECR** repos `aquaagent-sim`, `aquaagent-api` | tag = git short SHA |
| Data / models | **S3** bucket `aquaagent-<accountid>-<region>` | layout §10.2 |
| Training | **SageMaker Training Job** (PyTorch framework container, script mode) | CPU instance is sufficient for an 8-node graph |
| Inference | **SageMaker real-time endpoint**, 1 instance | Delete after the event (§10.5) |
| Agent LLM (T2d) | **Bedrock Converse API** with `toolConfig`; model id may be an **inference-profile id** | Bedrock Agents/AgentCore = pitch "next step", not required |
| Logs | **CloudWatch Logs** for ECS, SageMaker | |

> **Why not separate ECS services for sim and api?** The interactive session lives in memory. Two containers in one task share a lifecycle and `localhost`, which removes service discovery and state-sync work we do not have time for. The boundary between them is still a clean HTTP contract (§7.14.2), so they can be split later.

### 3.3 Local-first rule

Every component must run locally with `docker compose up` **before** it is deployed. AWS-only behaviour is hidden behind clients with a local fallback:

| Client | `AQUA_MODE=local` | `AQUA_MODE=aws` |
|---|---|---|
| `PredictorClient` | loads `model.tar.gz` content in-process (**T1 default, also used on ECS in T2a**) | invokes SageMaker endpoint (T2b) |
| `AgentRunner` | Bedrock via local AWS creds, or `TemplateReporter` if `AQUA_AGENT=template` | Bedrock |
| `DatasetStore` | `./data/` | `s3://…` |

---

## 4. Module Map and Sub-MD Index

Create these files in `docs/modules/`. Each module MD must contain: **Purpose · Inputs (Backbone refs) · Outputs (Backbone refs) · Implementation plan · Tests · Acceptance gate · Proposed Backbone Changes**.

| # | Module MD | Owns code in | Consumes | Produces | Gate |
|---|---|---|---|---|---|
| 01 | `01_SIMULATION_ENGINE.md` | `sim/engine/`, `sim/server/` | §6, §7.1–7.4 | `HydraulicSnapshot`, sim HTTP API §7.14.2 | G1 |
| 02 | `02_DATA_GENERATION.md` | `sim/generate/`, `sim/scenarios/` | §7.1–7.2, §8 | Parquet tables §7.5, manifest §7.6 | G2 |
| 03 | `03_AWS_INFRA.md` (T2a) | `infra/` | §3.2, §10 | ECR, ECS, ALB, APIGW, S3, IAM | G3 |
| 04 | `04_ML_PREDICTOR.md` | `ml/predictor/`, `ml/features/` | §7.5, §7.7, §9.1–9.2 | `model.tar.gz`, eval report | G4 |
| 05 | `05_ANOMALY_LOCALISATION.md` | `ml/anomaly/`, `ml/localisation/` | §7.9–7.11, §9.3–9.4 | thresholds.json, signatures.parquet, eval report | G5 |
| 06 | `06_SAGEMAKER.md` (T2b) | `ml/sagemaker/` | §7.9, §10 | training job, endpoint | G6 |
| 07 | `07_AQUAAGENT_BEDROCK.md` (T1 template, T2d Bedrock) | `api/agent/` | §7.12–7.13, §9.6 | `AgentReport` | G7 |
| 08 | `08_ORCHESTRATOR_API.md` | `api/` | everything | public API §7.14.1 | G8 |
| 09 | `09_FRONTEND.md` | `frontend/` | §7.14.1, §7.15 | Amplify site | G9 |
| 10 | `10_DEMO_AND_PITCH.md` | `docs/demo/` | eval reports | script, slides, fallback video | G10 |

### Dependency graph (critical path in **bold**)

```
T1 critical path (local):
**01 Sim engine** ──▶ **02 Data gen** ──▶ **04 Predictor** ──▶ **05 Detector** ──▶ **08 Orchestrator** ──▶ 10 Demo
      │                                                         07 TemplateReporter ──▶ ▲
      └──▶ **09 Frontend** (mock §7.14.1 from Day 1; real sim API as soon as 01 serves) ─┘
T2 (after gate MVP): 03 AWS deploy (T2a) → 06 SageMaker (T2b) → 05 localisation (T2c) → 07 Bedrock (T2d)
```

---

## 5. Global Conventions

### 5.1 Identifiers

| Thing | Format | Example |
|---|---|---|
| Network config | `net_<slug>_v<n>` | `net_epa_tutorial_v1` |
| Node ID | EPANET name, string | `"2"`, `"8"` |
| Link ID | EPANET name, string; pump keeps its EPANET id | `"4"`, `"9"` |
| Leak node (pipe leaks only) | `LK_<pipeId>` — **never exposed to ML features or public API outside reveal** | `LK_4` |
| Split pipe halves | `<pipeId>` and `<pipeId>_B` — mapped back to canonical `<pipeId>` in every snapshot | `4`, `4_B` → `4` |
| Sensor | `S1..Sn` (pressure), `F1..Fn` (flow) | `S2`, `F1` |
| Tap | `T1..T3` | `T2` |
| Valve (UI) | `V1` | `V1` |
| Simulation | `sim_<datasetVersion>_<6-digit index>` | `sim_ds1_000417` |
| Dataset version | `ds<n>` | `ds1` |
| Model version | `<arch>_<dsVersion>_<yyyymmddhhmm>` | `mlp_ds1_202610091830` |
| Session | `sess_<uuid4 short>` | `sess_3f9a1c` |
| Incident | `inc_<sessionShort>_<simTimeS>` (`sessionShort` = session id without `sess_`) | `inc_3f9a1c_43200` |
| Challenge | `chl_<sessionShort>_<simTimeS>` | `chl_3f9a1c_42300` |
| Thresholds version | `thr_<dsVersion>_<yyyymmddhhmm>` | `thr_ds1_202610100900` |
| Signatures version (T2c) | `sig_<dsVersion>_<yyyymmddhhmm>` | `sig_ds1_202610101000` |

### 5.2 Units (the single biggest source of silent bugs)

| Quantity | Storage & internal (WNTR native, SI) | Public API & UI | Column suffix |
|---|---|---|---|
| Pressure | metres of head | metres (m) | `_m` |
| Head / elevation | m | m | `_m` |
| Flow, demand, leak flow | m³/s | **L/s** (UI may show L/min for taps) | `_m3s` / `_lps` |
| Velocity | m/s | m/s | `_ms` |
| Length / diameter | m | m / mm | `_m` / `_mm` |
| Leak area | m² | cm² (display only) | `_m2` |
| Time | seconds since sim start (int) | seconds + `HH:MM` label | `_s` |
| Percentage | 0–100 | 0–100 | `_pct` (also the field `pct_change`) |
| Tap flow (display only) | — | L/min | `_lpm` |

**Rule:** every numeric column and JSON field carries its unit suffix. A field without a suffix is a bug. Conversions happen in exactly one place: `shared/units.py` / `shared/units.ts`.

**Two layers (v1.1.0):** the **state layer** (`HydraulicSnapshot`, `node_states`, `link_states`, `tank_states`, `pump_states`) is SI (`_m3s`). The **observation layer** (`sensors`, `context`, `SensorWindow`, agent tool outputs) uses SCADA units: pressure m, flow **L/s**. Where a column holds either quantity (`sensors.true_value`, `sensors.measured_value`, `get_sensor_history.value`) the unit is carried by the `measurement`/`unit` column — the only allowed exception to the suffix rule. `pump_status`: state layer `OPEN|CLOSED` (link status), observation layer int `0|1`, UI/Incident `ON|OFF`; converted only via `shared/units`.

### 5.3 Time

- Dataset hydraulic timestep: **300 s (5 min)**, episode duration **24 h** → 289 snapshots per simulation.
- Interactive timestep: **300 s — the same as the dataset (v1.1.0, single cadence everywhere).** Speed `1×/5×/20×` = number of 300-s steps advanced per frontend tick (tick = 1 s wall clock), i.e. 5 / 25 / 100 simulated minutes per second. Backend never runs a background clock (§7.14.1 `POST /api/sim/step`). One cadence means lags, windows and detector constants mean the same thing in training, evaluation and the live demo (measured stepwise cost ≈ 19 ms/step, `docs/research/WNTR_FEASIBILITY.md`).
- Sim start = 00:00 of a nominal day. Demand pattern indexes by `sim_time_s mod 86400`.

### 5.4 Seeds and reproducibility

- Every random draw goes through `numpy.random.Generator(PCG64(seed))`. **No** `random`, **no** global `np.random`.
- `seed` for a simulation = `hash64(dataset_seed, sim_index)`, recorded in the scenario row.
- `config_hash` = SHA-256 of canonical JSON of `NetworkConfig` + `ScenarioSpec` + generator code version. Stored per simulation.

### 5.5 Versioning

- `backbone/x.y.z` — contract version; every API response carries header `X-Aqua-Contract: backbone/1.1.0`.
- `schema_version` field inside every persisted JSON/Parquet manifest.
- Library pins live in `sim/requirements.txt`, `api/requirements.txt`, `ml/requirements.txt`. **Pin the exact WNTR version validated in G1 and never float it** (feasibility-validated: `wntr==1.5.0`). **Python 3.12** for all Python code (WNTR wheels exist for cp310–cp313 only; 3.14 has none).

---

## 6. Canonical Network — `net_epa_tutorial_v1`

Baseline = official EPANET 2.2 tutorial example network (EPANET 2.2 manual, Quick Start, Fig. 2.1 + Table 2.2), built **programmatically** in WNTR. **No official `.inp` file exists** (the tutorial only saves a binary `tutorial.net`; verified 2026-10-08), so v1.1.0 states connectivity here once, transcribed from Fig. 2.1 (copy: `docs/research/epanet22_fig2_1_tutorial_network.jpeg`). Module 01 builds the network from these tables, exports `config/networks/net_epa_tutorial_v1.{inp,json}` in G1, and a unit test asserts the exported topology equals §6.2. Feasibility of this build (PDD, leaks, stepping) is recorded in `docs/research/WNTR_FEASIBILITY.md`.

### 6.1 Nodes (SI; source values in ft/gpm)

| Node | Type | Elevation (m) | Base demand (L/s) | Role / UI label | Instruments |
|---|---|---|---|---|---|
| 1 | Reservoir | 213.36 (700 ft) = fixed head | — | Source | context: `reservoir_head_m` (known) |
| 2 | Junction | 213.36 | 0 | Pump discharge header | **S1** |
| 3 | Junction | 216.41 (710 ft) | 9.46 (150 gpm) | Commercial district | **T1** |
| 4 | Junction | 213.36 | 9.46 | West residential | **S2**, **T2** |
| 5 | Junction | 198.12 (650 ft) | 12.62 (200 gpm) | Valley consumers | hidden |
| 6 | Junction | 213.36 | 9.46 | East residential | **S3**, **T3** |
| 7 | Junction | 213.36 | 0 | Loop tie point | hidden |
| 8 | Tank | 252.98 (830 ft) | — | Elevated storage, max depth 6.10 m (20 ft), Ø 18.29 m (60 ft) | context: `tank_level_m` (known) |

### 6.2 Links

| Link | Kind | Start → End | Length (m) | Diameter (m) | HW C | Zone | Instruments / UI |
|---|---|---|---|---|---|---|---|
| 1 | Pipe | 2 → 3 | 914.4 (3000 ft) | 0.3556 (14 in) | 100 | Z1 | |
| 2 | Pipe | 3 → 7 | 1524.0 (5000 ft) | 0.3048 (12 in) | 100 | Z1 | |
| 3 | Pipe | 3 → 4 | 1524.0 | 0.2032 (8 in) | 100 | Z2 | **F1** |
| 4 | Pipe | 4 → 6 | 1524.0 | 0.2032 | 100 | Z2 | |
| 5 | Pipe | 7 → 6 | 1524.0 | 0.2032 | 100 | Z3 | |
| 6 | Pipe | 7 → 8 (tank) | 2133.6 (7000 ft) | 0.2540 (10 in) | 100 | Z3 | **F2** |
| 7 | Pipe | 4 → 5 | 1524.0 | 0.1524 (6 in) | 100 | Z2 | **V1** (see note) |
| 8 | Pipe | 5 → 6 (drawn curved) | 2133.6 | 0.1524 | 100 | Z2 | |
| 9 | Pump | 1 → 2 | — | — | — | Z1 | single-point curve 37.85 L/s (600 gpm) @ 45.72 m (150 ft); context: `pump_status`, `pump_flow_lps` (SCADA-known) |

Loops: 3–4–6–7 and 4–5–6. **Zones:** Z1 *Supply & Commercial* (nodes 1, 2, 3), Z2 *West & Valley* (nodes 4, 5), Z3 *East & Storage* (nodes 6, 7, 8). **UI coordinates** (Fig. 2.1 layout, x right / y down, arbitrary units; the frontend scales them): 1 (15, 35) · 2 (90, 35) · 3 (143, 35) · 7 (205, 35) · 8 (265, 35) · 4 (143, 100) · 6 (205, 100) · 5 (143, 165).

> **V1 honesty note:** the EPA tutorial network has no valve element. "Valve V1" is implemented as **pipe 7 status OPEN/CLOSED** (and, for partial closure, a reduced HW C / minor loss). The UI may call it a valve; the README and pitch must not claim it is an EPANET valve object.

### 6.3 Hydraulics configuration (frozen)

| Option | Value |
|---|---|
| Simulator | **`wntr.sim.WNTRSimulator` for everything** (leaks + PDD require it; one simulator = no cross-simulator discrepancy) |
| Head loss | Hazen-Williams |
| Demand model | `PDD`, `required_pressure_m = 20`, `minimum_pressure_m = 0` (feasibility run: healthy junction pressures 34.9–58.0 m over 24 h, so the baseline is ≥ 20 m; record final values in network config) |
| Leak model | WNTR `add_leak(area, discharge_coeff=0.75, start_time, end_time)` on a junction. **Pipe leaks use pre-split pipes (v1.1.0):** when a network model is built, every candidate pipe is split once with `wntr.morph.split_pipe(wn, p, f"{p}_B", f"LK_{p}", split_at_point=pos)` (interactive sessions: `pos = 0.5`; dataset: `pos` drawn per simulation). `LK_<p>` is a zero-demand junction, so the healthy hydraulics are unchanged (measured max \|ΔP\| 1.7e-5 m). A leak is then just `add_leak` on an **existing** node, so the topology never changes mid-run. |
| Stepping | Stop/restart: increase `wn.options.time.duration` and run a new `WNTRSimulator(wn)` on the same model; results continue from the last time (measured: identical to a full run within 3e-14 m, ≈19 ms per 300-s step). Fallback: replay from t = 0 with the event log. |
| Demand pattern | Per-session/per-sim diurnal profile from §7.2 `demand_profile` (the tutorial's own 4-step pattern is not used) |
| Tank initial level | Open decision D3 (default 1.07 m ≈ 3.5 ft) |

### 6.4 Sensor layout `sensors_default_v1`

```json
{
  "sensor_layout_id": "sensors_default_v1",
  "pressure": [{"sensor_id":"S1","node_id":"2"},{"sensor_id":"S2","node_id":"4"},{"sensor_id":"S3","node_id":"6"}],
  "flow":     [{"sensor_id":"F1","link_id":"3"},{"sensor_id":"F2","link_id":"6"}],
  "context":  ["tank_level_m","pump_status","pump_flow_lps","reservoir_head_m","time_of_day_s"]
}
```

`context` = values a real utility's SCADA already knows. They are allowed ML inputs. Anything not listed in `pressure`, `flow` or `context` is **hidden** and may only appear as a training target.

Alternative layouts for the placement experiment (T2): `[3,5,7]`, `[2,5,8]` → `sensors_alt_a_v1`, `sensors_alt_b_v1`.

---

## 7. Data Contracts

All schemas live in `shared/contracts/` (Pydantic v2 + generated TS via `datamodel-code-generator` or hand-mirrored). Field names below are canonical.

### 7.1 `NetworkConfig`

```json
{
  "schema_version": "1.0",
  "network_id": "net_epa_tutorial_v1",
  "source": "epanet_tutorial",
  "inp_path": "config/networks/net_epa_tutorial_v1.inp",
  "nodes": [
    {"node_id":"3","node_type":"junction","elevation_m":216.41,"base_demand_m3s":0.00946,
     "x":300,"y":120,"ui_label":"Commercial District","zone_id":"Z1"}
  ],
  "links": [
    {"link_id":"4","link_type":"pipe","start_node":"4","end_node":"5",
     "length_m":1524.0,"diameter_m":0.2032,"roughness_hw":100,"initial_status":"OPEN","zone_id":"Z2"}
  ],
  "zones": [{"zone_id":"Z1","name":"Commercial"},{"zone_id":"Z2","name":"West"}],
  "hydraulics": {"demand_model":"PDD","required_pressure_m":20,"minimum_pressure_m":0,
                 "headloss":"H-W","tank_init_level_m":1.07},
  "taps": [{"tap_id":"T1","node_id":"3"},{"tap_id":"T2","node_id":"4"},{"tap_id":"T3","node_id":"6"}],
  "valves": [{"valve_id":"V1","link_id":"7","impl":"pipe_status"}]
}
```

(`start_node`/`end_node`/`x`/`y` in the example are illustrative; real values come from the exported file.) Zones exist so localisation can report a **probable zone** even when pipe-level ranking is uncertain.

### 7.2 `ScenarioSpec`

```json
{
  "schema_version": "1.0",
  "simulation_id": "sim_ds1_000417",
  "network_id": "net_epa_tutorial_v1",
  "sensor_layout_id": "sensors_default_v1",
  "seed": 8812736451,
  "duration_s": 86400,
  "timestep_s": 300,
  "demand_profile": {
    "profile_id": "diurnal_random",
    "night_min": 0.35, "morning_peak_mult": 1.45, "morning_peak_h": 7.5,
    "evening_peak_mult": 1.60, "evening_peak_h": 19.0,
    "node_multipliers": {"3":1.05,"4":0.92,"5":1.10,"6":0.98},
    "noise_sigma": 0.03, "weekend": false
  },
  "operations": {"reservoir_head_offset_m": 0.0, "pump_speed": 1.0, "tank_init_level_m": 1.07},
  "scenario_type": "MEDIUM_LEAK",
  "faults": [
    {"fault_id":"f0","fault_type":"LEAK","location_kind":"pipe","location_id":"4","position":0.4,
     "leak_area_m2":0.00015,"discharge_coeff":0.75,"start_s":39600,"end_s":86400}
  ],
  "sensor_faults": [],
  "noise": {"pressure_sigma_m":0.05,"flow_sigma_lps":0.10,"missing_rate":0.0},
  "config_hash": "sha256:…",
  "generator_version": "sim-0.3.1"
}
```

`fault_type ∈ {LEAK, BURST, VALVE_CLOSURE, PARTIAL_VALVE, PUMP_DEGRADE, PUMP_TRIP, LOW_RESERVOIR, DEMAND_SPIKE, DEMAND_SHIFT}`
`sensor_faults[].kind ∈ {SPIKE, BIAS, DRIFT, STUCK, MISSING}` with `sensor_id, start_s, end_s, magnitude`.

### 7.3 `SimEvent` (interactive mode event log)

```json
{"event_id":"ev_0007","sim_time_s":43500,"source":"user|challenge|system",
 "kind":"TAP_SET|PIPE_FAULT|PIPE_RESET|VALVE_SET|SPEED|RESET",
 "target_id":"T2","params":{"open":true},"hidden":false}
```

The session keeps an append-only event log. Challenge events have `hidden: true` and are stripped from every public response until reveal. The event log + seed must be sufficient to replay a session exactly.

### 7.4 `HydraulicSnapshot` (canonical full state at one instant — sim engine output)

```json
{
  "schema_version": "1.0",
  "network_id": "net_epa_tutorial_v1",
  "sim_time_s": 43200,
  "converged": true,
  "nodes": {
    "4": {"pressure_m":38.42,"head_m":251.78,"demand_m3s":0.00946,"base_demand_m3s":0.00946,
          "leak_m3s":0.0}
  },
  "links": {
    "4": {"flow_m3s":0.0121,"velocity_ms":0.37,"headloss_m":1.92,"status":"OPEN"}
  },
  "tanks": {"8": {"level_m":2.31,"head_m":255.29,"volume_m3":606.8,"net_inflow_m3s":0.0018}},
  "pumps": {"9": {"flow_m3s":0.0362,"head_gain_m":46.1,"status":"OPEN"}},
  "hidden": {"leak_nodes": {"LK_4": {"leak_m3s":0.0031}}}
}
```

Rules:
- Split-pipe halves are merged back: canonical link `4` reports the **upstream** half's flow; `hidden.leak_nodes` carries the leak node state.
- `hidden` is populated only inside the sim engine and the dataset writer. The orchestrator strips it before any public response unless `reveal=true`.
- Mass-balance check (G1): `Σ reservoir outflow + Σ tank outflow ≈ Σ delivered demand + Σ leak`, tolerance 1e-4 m³/s. In WNTR results this is `|Σ_nodes demand + Σ_nodes leak_demand| ≤ 1e-4` per timestep (reservoir/tank demands are negative; `leak_demand` is reported separately from `demand`).

### 7.5 Dataset tables (Parquet, partitioned by `split=`)

**`scenarios`** — one row per simulation

| column | type | note |
|---|---|---|
| simulation_id | str | PK |
| dataset_version | str | |
| network_id, sensor_layout_id | str | |
| scenario_type | str | §8.1 |
| is_anomalous | bool | hydraulic anomaly present (sensor faults → false, see `has_sensor_fault`) |
| has_sensor_fault | bool | |
| fault_type, location_kind, location_id, zone_id | str / null | first hydraulic fault |
| position | float / null | 0–1 along pipe |
| leak_area_m2 | float / null | |
| fault_start_s, fault_end_s | int / null | |
| realised_leak_peak_m3s | float / null | measured from results |
| severity_bucket | str / null | `<5%`, `5-15%`, `15-25%`, `>25%` of system demand (matches AquaSentinel buckets) |
| seed, config_hash, generator_version | | |
| spec_json | str | full `ScenarioSpec` |
| split | str | `train/val/test` |
| valid | bool | failed sims never reach this table — they go to `validation_log` |

**`node_states`** — `simulation_id, sim_time_s, node_id, node_type, pressure_m, head_m, demand_m3s, base_demand_m3s, leak_m3s, is_sensor (bool), hop_to_nearest_sensor (int)`

**`link_states`** — `simulation_id, sim_time_s, link_id, link_type, flow_m3s, velocity_ms, headloss_m, status`

**`tank_states`** — `simulation_id, sim_time_s, tank_id, level_m, head_m, volume_m3, net_inflow_m3s`

**`pump_states`** — `simulation_id, sim_time_s, pump_id, flow_m3s, head_gain_m, status`

**`sensors`** — `simulation_id, sim_time_s, sensor_id, source_kind (node|link), source_id, measurement (pressure_m|flow_lps), true_value, measured_value (nullable = missing), sensor_fault_kind (nullable)`

**`context`** — `simulation_id, sim_time_s, time_of_day_s, tank_level_m, pump_status, pump_flow_lps, reservoir_head_m`

**`graph`** — static per network: `network_id, element_kind (node|edge), element_id, start_node, end_node, features_json`

**`validation_log`** — `simulation_id, seed, check, passed, detail, generator_version` (every run, pass or fail)

> **The ML firewall in data form:** `sensors` + `context` = everything a deployed model may see. `node_states`, `link_states`, `scenarios` = ground truth for training targets and evaluation only.

### 7.6 Dataset `manifest.json`

```json
{
  "schema_version":"1.0","dataset_version":"ds1","created_utc":"2026-10-09T10:12:00Z",
  "git_sha":"a1b2c3d","generator_version":"sim-0.3.1","wntr_version":"<pinned>",
  "network_ids":["net_epa_tutorial_v1"],"sensor_layout_ids":["sensors_default_v1"],
  "dataset_seed":20261008,"n_requested":1200,"n_valid":1188,"n_failed":12,
  "counts_by_split":{"train":832,"val":178,"test":178},
  "counts_by_scenario_type":{"NORMAL":316,"SMALL_LEAK":148},
  "holdout":{"fault_locations_test_only":["pipe:5","junction:6"]},
  "timestep_s":300,"duration_s":86400,
  "files":{"node_states":"processed/ds1/node_states/","sensors":"processed/ds1/sensors/"}
}
```

### 7.7 ML sample (`GraphSample`) — produced by `ml/features/`

One sample = one `(simulation_id, sim_time_s)` on one network.

| Tensor | Shape | Content |
|---|---|---|
| `x` | `[N, F_node]` | node features, order frozen below |
| `edge_index` | `[2, 2E]` | undirected (both directions), canonical links incl. pump |
| `edge_attr` | `[2E, F_edge]` | edge features, order frozen below |
| `obs_mask` | `[N]` | 1 if node pressure observed in this sample |
| `y` | `[N]` | true `pressure_m` (target) |
| `y_mask` | `[N]` | 1 for junctions/tanks to score (reservoir excluded) |
| `meta` | dict | `simulation_id, sim_time_s, hop_to_nearest_sensor[N]` |

**Node features `F_node` (order frozen, v1):**
`[elevation_m_z, base_demand_lps_z, is_junction, is_tank, is_reservoir, obs_mask, observed_pressure_m_z (0 if unobserved), observed_pressure_lag1_z, observed_pressure_lag3_z, tod_sin, tod_cos, tank_level_m_z, pump_on, pump_flow_lps_z, reservoir_head_m_z]`
(global context features are broadcast to every node.)

**Edge features `F_edge` (order frozen, v1):**
`[length_m_z, diameter_m_z, roughness_hw_z, is_pump, is_open, observed_flow_lps_z (0 if unobserved), flow_obs_mask]`

`_z` = standardised with statistics computed **on train split only**, written to `features/ds1/scalers.json` and **copied into `model.tar.gz`** (inference reads only the artifact copy).

**Forbidden as input (leakage):** `demand_m3s` of hidden nodes, `leak_m3s`, any `hidden.*`, `scenario_type`, anything from timesteps after `sim_time_s`.

The MLP (T1 ship model) uses the flattened equivalent: `[observed pressures (3), observed flows (2), 5 observation-mask bits, lags (300 s and 900 s), context] → [pressure at every scored node, flow at F1, F2]`. Lags are at the single 300-s cadence (§5.3).

### 7.8 `SensorWindow` — the ONLY input type allowed into the inference pipeline

```json
{
  "schema_version":"1.0","network_id":"net_epa_tutorial_v1","sensor_layout_id":"sensors_default_v1",
  "window": [
    {"sim_time_s":42900,
     "pressure_m":{"S1":51.20,"S2":38.40,"S3":36.90},
     "flow_lps":{"F1":12.10,"F2":8.30},
     "context":{"tank_level_m":2.31,"pump_status":1,"pump_flow_lps":36.2,"reservoir_head_m":213.36,"time_of_day_s":42900}}
  ]
}
```

Window length: last **12 steps = 1 h** at the single 300-s cadence (interactive and dataset alike). Missing readings = `null`, never 0.

### 7.9 Predictor endpoint contract (SageMaker)

**Request** (`ContentType: application/json`):

```json
{"model_version":"mlp_ds1_202610091830","mode":"reconstruct|leave_one_out",
 "sensor_window": { "…": "SensorWindow §7.8" }}
```

**Response:**

```json
{
  "model_version":"mlp_ds1_202610091830","sim_time_s":43200,
  "reconstruct": {"pressure_m": {"2":51.18,"3":44.02,"4":38.47,"5":53.11,"6":36.95,"7":40.30,"8":42.20},
                  "pressure_std_m": {"5":0.41,"7":0.38}},
  "leave_one_out": {"S1":{"predicted_m":51.05,"observed_m":51.20},
                    "S2":{"predicted_m":41.10,"observed_m":38.40},
                    "S3":{"predicted_m":37.02,"observed_m":36.90}},
  "leave_one_out_flow": {"F1":{"predicted_lps":10.70,"observed_lps":12.10},
                         "F2":{"predicted_lps":8.25,"observed_lps":8.30}},
  "latency_ms": 18
}
```

`leave_one_out` / `leave_one_out_flow` (v1.1.0): for each of the **5 sensors** `s ∈ {S1,S2,S3,F1,F2}`, mask `s` and predict its value from the remaining sensors + context (pressures in m, flows in L/s). This is how we get a residual **at an observed location** (see §9.2 — the core anomaly signal). One call returns `reconstruct` + both LOO maps, to avoid 6 round trips. In T1 this is an in-process Python call with the same request/response; in T2b it is the SageMaker endpoint.

### 7.10 `ResidualFrame` and `AnomalyResult`

```json
{
  "sim_time_s":43200,
  "residuals": {"S1":0.15,"S2":-2.70,"S3":-0.12,"F1":1.40,"F2":0.05},
  "z": {"S1":0.6,"S2":-6.1,"S3":-0.4,"F1":3.2,"F2":0.1},
  "instant_flags": ["S2","F1"],
  "cumulative_flags": ["S2"]
}
```

```json
{
  "status":"NORMAL|WATCH|ANOMALY|SENSOR_FAULT",
  "anomaly_score":0.93,
  "first_flag_time_s":42600,"confirmed_time_s":43200,
  "detection_delay_steps":2,
  "suspected_class":"LEAK","class_probs":{"LEAK":0.81,"DEMAND_SPIKE":0.12,"VALVE_CLOSURE":0.07},
  "driving_sensors":["S2","F1"],
  "residual_history_ref":"session buffer last 12 frames",
  "thresholds_version":"thr_ds1_202610100900"
}
```

`suspected_class` / `class_probs` are T3; in T1/T2 they are `null`. Status `SENSOR_FAULT` is reserved for T3 (ds1 has no sensor-fault scenarios); T1 emits only `NORMAL|WATCH|ANOMALY`. `detection_delay_steps` = steps from `first_flag_time_s` to `confirmed_time_s`; the challenge's `detection_delay_s` (§7.14.1) is measured from the true fault start.

### 7.11 `LocalisationResult`

```json
{
  "method":"signature_cosine_v1",
  "candidates":[
    {"rank":1,"location_kind":"pipe","location_id":"4","zone_id":"Z2","score":0.81,"similarity":0.94},
    {"rank":2,"location_kind":"pipe","location_id":"5","zone_id":"Z2","score":0.13,"similarity":0.71},
    {"rank":3,"location_kind":"junction","location_id":"5","zone_id":"Z2","score":0.06,"similarity":0.55}
  ],
  "probable_zone":{"zone_id":"Z2","score":0.94},
  "signatures_version":"sig_ds1_202610101000"
}
```

Language rule: UI and agent say **"probable leak zone"** / **"most likely pipe"**, never "exact location". Localisation is **T2c**; until then `Incident.localisation` is `null` and the reveal's `true_location_rank`/`zone_correct` are `null`.

### 7.12 `Incident` (the object handed to the agent)

```json
{
  "incident_id":"inc_3f9a1c_43200","session_id":"sess_3f9a1c","created_sim_time_s":43200,
  "network_id":"net_epa_tutorial_v1","sensor_layout_id":"sensors_default_v1",
  "anomaly": { "…": "AnomalyResult §7.10" },
  "localisation": { "…": "LocalisationResult §7.11 (null until T2c)" },
  "evidence": {
    "sensor_deltas":[{"sensor_id":"S2","baseline_m":41.10,"observed_m":38.40,"pct_change":-6.6}],
    "flow_deltas":[{"sensor_id":"F1","baseline_lps":10.70,"observed_lps":12.10,"pct_change":13.1}],
    "context_summary":{"time_of_day":"12:00","tank_level_m":2.31,"pump_status":"ON"}
  },
  "model_versions":{"predictor":"mlp_ds1_202610091830","thresholds":"thr_ds1_…","signatures":"sig_ds1_…"}
}
```

No ground truth is ever placed inside an `Incident`.

### 7.13 Agent tools and `AgentReport`

**Tools exposed to Bedrock (Converse `toolConfig`)** — each returns JSON from §7 contracts, never prose:

| Tool | Input | Returns |
|---|---|---|
| `get_incident` | `{incident_id}` | `Incident` |
| `get_sensor_history` | `{sensor_id, last_n_steps ≤ 60}` | list of `{sim_time_s, value, unit}` |
| `get_reconstruction` | `{incident_id}` | predictor response §7.9 (`reconstruct` only) |
| `get_candidate_locations` | `{incident_id, top_k ≤ 5}` | `LocalisationResult` |
| `get_network_element` | `{element_id}` | node/link static attributes from `NetworkConfig` |
| `run_what_if` (T2) | `{action: "isolate_pipe"\|"close_valve"\|"reduce_pump_speed", target_id, horizon_steps ≤ 30}` | `{affected_nodes:[{node_id, pressure_before_m, pressure_after_m}], customers_below_20m: int}` — runs on a **forked copy** of the session network, never the live one |

**`AgentReport`** (model must answer by calling a final tool `submit_report` with this schema — forces structure):

```json
{
  "incident_id":"inc_3f9a1c_43200",
  "headline":"Probable leak in West Residential zone (pipe 4)",
  "what_happened":"…", "why_suspicious":"…", "where":"…",
  "evidence":[{"claim":"Pressure at S2 is 2.7 m below expected","source_tool":"get_incident","fields":["evidence.sensor_deltas[0]"]}],
  "recommended_actions":[{"priority":1,"action":"Dispatch acoustic survey to pipe 4","rationale":"…"}],
  "confidence":"HIGH|MEDIUM|LOW",
  "caveats":["Simulated network and synthetic sensor data"],
  "grounding_check":{"passed":true,"unmatched_numbers":[]}
}
```

`grounding_check` is filled by the orchestrator (§9.6), not by the model. Optional field `generated_by: "template"|"bedrock"` drives the UI label (v1.1.0). **T1 produces `AgentReport` with the deterministic `TemplateReporter` only**; the Bedrock tool loop is T2d and `run_what_if` is T3.

### 7.14 HTTP APIs

#### 7.14.1 Public orchestrator API (frontend ↔ `aquaagent-api`)

Base: `${VITE_API_BASE_URL}/api`. Header `X-Api-Key` required in `aws` mode (`OPTIONS` preflight exempt; the key is visible in the browser bundle — a deterrent, not a secret). All responses carry `X-Aqua-Contract`. CORS is set by FastAPI from `AQUA_CORS_ORIGINS`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{status, sim:"ok", predictor:"ok|degraded", agent:"ok|template"}` |
| POST | `/session/reset` | `{seed?}` | `NetworkView` |
| GET | `/network/topology` | — | `NetworkConfig` minus hydraulics internals (static; fetch once) |
| GET | `/network/state` | — | `NetworkView` |
| POST | `/sim/step` | `{steps: 1..20}` | `NetworkView` (advances sim; frontend calls once per second with `steps = speed`) |
| POST | `/tap` | `{tap_id, open: bool}` | `NetworkView` |
| POST | `/pipe/fault` | `{link_id, kind: "LEAK"\|"BURST"\|"CLOSE"\|"RESET"}` | `NetworkView` |
| POST | `/valve` | `{valve_id, open: bool}` | `NetworkView` |
| POST | `/challenge/start` | `{difficulty?: "small"\|"medium"\|"large"}` (default `medium`) | `{challenge_id, started_sim_time_s}` — fault is hidden. Difficulty → leak-area range of SMALL/MEDIUM/LARGE_LEAK in `config/generation/ds1.yaml`; location drawn (seeded) from the §8.2 candidates excluding sensor nodes; the fault starts 1–3 steps after the call |
| GET | `/challenge/status` | — | `{state: "RUNNING"\|"DETECTED"\|"TIMEOUT", anomaly: AnomalyResult, incident_id?}` |
| POST | `/agent/diagnose` | `{incident_id}` | `AgentReport` (T1: template, instant; T2d: Bedrock with a hard 20-s server budget, then template fallback — API Gateway cuts at 30 s) |
| POST | `/agent/ask` (T3) | `{incident_id, question}` | `{answer, grounding_check}` |
| POST | `/challenge/reveal` | — | `ChallengeReveal` (below) |

**`NetworkView`** (UI-shaped, units converted, hidden fields stripped):

```json
{
  "session_id":"sess_3f9a1c","sim_time_s":43200,"clock":"12:00","speed":5,
  "nodes":{"4":{"pressure_m":38.4,"head_m":251.8,"demand_lps":9.46,"is_sensor":true,"sensor_id":"S2","status":"ok|low|critical"}},
  "links":{"4":{"flow_lps":12.1,"velocity_ms":0.37,"status":"OPEN","direction":1,"visual_fault":"NONE|LEAK|BURST"}},
  "tank":{"tank_id":"8","level_m":2.31,"level_pct":37.9},
  "pump":{"pump_id":"9","flow_lps":36.2,"status":"ON"},
  "taps":{"T2":{"open":true,"demand_lps":9.46}},
  "valves":{"V1":{"open":true}},
  "network_status":"NORMAL|WATCH|ANOMALY",
  "challenge":{"active":false},
  "events":[{"sim_time_s":42900,"text":"Tap 2 opened"}]
}
```

During a challenge: `links[*].visual_fault` stays `NONE` for the hidden fault and challenge events are omitted; the physics (flows/pressures) still reflect it, because that is reality.

**`ChallengeReveal`:**

```json
{"truth":{"fault_type":"LEAK","location_kind":"pipe","location_id":"4","zone_id":"Z2","start_sim_time_s":42300,"leak_peak_lps":3.1,"severity_bucket":"5-15%"},
 "ai":{"detected":true,"detection_delay_s":900,"true_location_rank":1,"zone_correct":true,"report_incident_id":"inc_…"}}
```

#### 7.14.2 Internal sim engine API (`aquaagent-api` → `aquaagent-sim` on `localhost:8000`)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/sim/health` | — | `{status, wntr_version}` |
| POST | `/sim/session` | `{network_id, seed, timestep_s:60}` | `{session_id}` |
| POST | `/sim/session/{id}/event` | `SimEvent` | `{applied: true}` |
| POST | `/sim/session/{id}/advance` | `{steps}` | list of `HydraulicSnapshot` (one per step) |
| GET | `/sim/session/{id}/snapshot` | — | `HydraulicSnapshot` (with `hidden`) |
| POST | `/sim/session/{id}/fork_what_if` | `{events: SimEvent[], horizon_steps}` | list of `HydraulicSnapshot` |
| POST | `/sim/session/{id}/reset` | — | `HydraulicSnapshot` |

The sim engine never decides what is hidden from users — it returns full truth; the orchestrator enforces visibility.

### 7.15 Frontend state (`frontend/src/state/simulationStore.ts`)

```ts
type SimStore = {
  topology: NetworkTopology | null;   // GET /network/topology once
  view: NetworkView | null;           // replaced wholesale on every response
  speed: 1 | 5 | 20;
  running: boolean;                   // drives the 1-s tick → POST /sim/step {steps: speed}
  selection: {kind: 'node'|'link'|'tap'|'valve', id: string} | null;
  challenge: {state: 'IDLE'|'RUNNING'|'DETECTED'|'REVEALED', incidentId?: string, reveal?: ChallengeReveal};
  report: AgentReport | null;
};
```

Rendering rules: flow animation speed ∝ `|flow_lps|`, direction from `direction`, zero flow → stopped; tank fill = `level_pct`; leak droplet intensity from `visual_fault` only. The frontend performs **no** hydraulic arithmetic.

---

## 8. Scenario Catalogue and Generation Plan (`ds1`)

### 8.1 Scenario mix — `ds1` (T1): 1,200 requested

| scenario_type | count | is_anomalous | fault_type | parameters (uniform ranges unless stated) |
|---|---|---|---|---|
| NORMAL | 320 | no | — | demand profile randomised (§7.2), tank init 0.6–2.5 m |
| HIGH_DEMAND | 100 | no* | — | `demand_profile.global_mult` 1.3–1.8 for whole episode |
| LOW_DEMAND | 80 | no* | — | `global_mult` 0.4–0.7 |
| DEMAND_SHIFT | 100 | no* | DEMAND_SHIFT | one node ×1.5–2.5, another ×0.3–0.6 from t_f |
| SMALL_LEAK | 150 | yes | LEAK | area 2e-5–8e-5 m² |
| MEDIUM_LEAK | 200 | yes | LEAK | area 8e-5–2.5e-4 m² |
| LARGE_LEAK | 150 | yes | LEAK | area 2.5e-4–6e-4 m² |
| PIPE_BURST | 100 | yes | BURST | area 1e-3–3e-3 m² |

\* operational variation — the detector must **not** fire on these. They exist to kill the "pressure ↓ = leak" shortcut and they define the false-alarm rate (§9.5).

Fault start `t_f` ∈ [6 h, 18 h], snapped to timestep. Leaks run to episode end unless `end_s` drawn (30% of leaks end after 2–6 h).

**Leak area ranges** were checked in the feasibility run (pipe 4, mean demand 40.9 L/s): 2e-5 → 1.0%, 8e-5 → 4.0%, 2.5e-4 → 12.1%, 6e-4 → 25.7%, 3e-3 → 72.9% of mean system demand, i.e. the ranges already map onto the `<5% / 5–15% / 15–25% / >25%` severity buckets. G2 still runs the calibration over all 14 locations and records final ranges in `config/generation/ds1.yaml`.

**ds2 (T3, not built unless T1+T2 are green):** VALVE_CLOSURE, PARTIAL_VALVE, PUMP_DEGRADE, PUMP_TRIP, LOW_RESERVOIR, DEMAND_SPIKE, SENSOR_FAULT. Labelling rules are fixed now so ds2 needs no contract change: DEMAND_SPIKE is a hydraulic event (`is_anomalous=true`) reported in its own row, never in leak recall and never in FAR; SENSOR_FAULT sims have `is_anomalous=false, has_sensor_fault=true`; `PIPE_BURST→BURST`, `*_LEAK→LEAK` (`shared.contracts.models.SCENARIO_TO_FAULT`).

### 8.2 Fault locations

Candidate set (14): junctions `2–7` + pipes `1–8` (pipe leaks at `position ~ U(0.2, 0.8)` in the dataset; `0.5` in interactive sessions, §6.3). Pump link `9` is not a leak location. Challenge leaks (§7.14.1) exclude sensor junctions 2, 4, 6.

### 8.3 Sensor noise (applied to `sensors.measured_value` only)

Default: pressure σ = 0.05 m, flow σ = 0.10 L/s, missing 0%. The orchestrator applies the **same** noise to live sensor readings (seeded per session). Robustness variants (T3): σ ×{2, 5}, missing 5%.

### 8.4 Validation per simulation (all logged to `validation_log`)

`converged` · `no negative pressure at non-leak junctions in NORMAL` · `mass balance` (§7.4) · `tank level within [0, max]` · `all canonical nodes/links present` · `no NaN` · `pump status valid`. Any failure → excluded from tables, kept in log.

### 8.5 Splits

- Split **by `simulation_id`**, stratified by `scenario_type`: 70 / 15 / 15.
- **Hard holdout:** leaks at `pipe:5` and `junction:6` appear **only in test** (recorded in manifest). Localisation is physics-signature based (§9.4) so it can still rank them — that is the generalisation claim we test.
- Predictor training uses only **non-anomalous** train sims (§9.1).

### 8.6 Batch execution

T1 (local): `python -m sim.cli generate --config config/generation/ds1.yaml --shard i --num-shards N --out data/raw/ds1/shard=i/` for i in 0..N−1 (parallel processes on the laptop), then `python -m sim.cli merge … --out data/processed/ds1/`. A 24-h simulation takes ≈0.2 s, so ds1 takes minutes. Upload with `aws s3 sync data/processed/ds1 s3://…/processed/ds1/` (T2a). ECS RunTask of the same `generate` command (`infra/scripts/07_run_datagen.sh`) is T3.

---

## 9. ML Design (binding decisions)

### 9.1 Predictor — "what should the network look like right now?"

- **Train only on hydraulically normal simulations** (NORMAL, HIGH/LOW_DEMAND, DEMAND_SHIFT, and pre-fault timesteps of anomalous sims). If the predictor learns from leak states it learns to *reconstruct* leaks, and residuals collapse. This is the most important ML rule in the project.
- **Random sensor masking during training:** each sample randomly hides 0–1 of the **5 sensors** (S1–S3, F1–F2) in addition to all hidden nodes, so one model handles `reconstruct`, `leave_one_out` and `leave_one_out_flow` (v1.1.0).
- **Model ladder (stop at the first that meets G4 targets, then try the next only if time allows):**
  1. Nearest-sensor + elevation-corrected baseline (no training; sanity floor)
  2. **MLP** on flattened features (§7.7) — the T1 ship model
  3. GraphSAGE / GAT (PyTorch Geometric) — T3
- Loss: MSE on `y_mask` nodes; report MAE/RMSE/R², and **MAE by hop distance** (1/2/3+ hops from nearest sensor).
- Honest framing: on a fixed 8-node graph an MLP may match a GNN; the GNN earns its place only on unseen topologies (T3). Report whichever wins — do not ship a GNN just for the slide.

### 9.2 Residuals — where the anomaly signal comes from

You cannot get a residual at a node you do not observe, and a sensor fed into the model as input has a trivial residual. Therefore:

- **Pressure residual** at sensor `s`: `r_s = observed_s − LOO_prediction_s` (prediction with `s` masked).
- **Flow residual** at `F1`, `F2`: `r_f = observed_f − LOO_prediction_f` from `leave_one_out_flow` (same masking mechanism as pressure; v1.1.0).
- Normalise: `z_s = r_s / σ_s`, `σ_s` = std of `r_s` on **validation normal** data. Stored in `thresholds.json`.

### 9.3 Detector — RTCA-style dual threshold (T1) + classifier (T3)

Following the AquaSentinel pattern from the briefing document:
- instant flag if `|z_s| > k1` (default 2.5), cumulative flag if mean `|z_s|` over window `W` (default 6 steps) `> k2` (default 3.0);
- **ANOMALY** when ≥1 sensor has both flags for `T` consecutive steps (default 3); **WATCH** on instant-only;
- **SENSOR_FAULT** (T3, needs ds2): when one sensor's |z| is extreme, other sensors' LOO residuals are consistent with each other, and the jump is physically implausible.
- Tune `k1, k2, W, T` on validation to hit the false-alarm target on non-anomalous sims, **then freeze** before touching test. `W`, `T` are counted in 300-s steps everywhere (§5.3). σ is fixed from val (no adaptive EMA — it can absorb a slow leak).
- T3: gradient-boosted classifier on residual features → `suspected_class`.

### 9.4 Localisation — signature matching (T2c)

- Offline: for each of the 14 candidate locations × 3 leak sizes × 4 times-of-day, simulate the leak, run the resulting `SensorWindow`s **through the same predictor + residual pipeline as online**, and record the averaged `z` vector over the detection window as the signature (v1.1.0: one signal space for offline and online). Save `signatures.parquet` with the predictor version it was built with.
- Online: average `z` vector over the detection window → cosine similarity with every signature → softmax over max-similarity per location → ranked `candidates`; aggregate by `zone_id` for `probable_zone`.
- Because signatures are generated from physics (not learned from labelled training leaks), the hard-holdout locations remain rankable.

### 9.5 Evaluation targets (report actuals honestly even if missed)

| Metric | Target (ds1 test) |
|---|---|
| Predictor MAE, hidden junctions, normal | < 1.0 m |
| Detection recall, MEDIUM/LARGE/BURST | ≥ 95% |
| Detection recall, SMALL | report (expect lower) |
| False-alarm rate on operational sims (NORMAL, HIGH/LOW_DEMAND, DEMAND_SHIFT) | ≤ 5% of sims, reported per type |
| Median detection delay (medium leak) | ≤ 6 steps |
| Localisation top-1 / top-3 (pipe) — T2c | report / ≥ 80% top-3 |
| Zone accuracy — T2c | ≥ 85% |
| Hard-holdout locations top-3 — T2c | report separately |

### 9.6 Agent grounding

- **T1:** `TemplateReporter` only (deterministic, always grounded, labelled "template explanation").
- **T2d:** Converse API loop, max 6 tool turns, temperature low (≤ 0.2), 20-s wall-clock budget, system prompt forbids numbers not returned by tools.
- **Grounding check (orchestrator):** extract every number in the report text; each must match a value in the turn's tool results within ±0.5% or ±0.05 absolute, after unit normalisation (L/s↔L/min, m³/s↔L/s, `%`). Exempt: element IDs present in the tool results, `HH:MM` labels present in the tool results, ranks/priorities 1–5. Failures → `grounding_check.passed=false`, list `unmatched_numbers`, and the UI shows a warning badge. One automatic retry with the unmatched list fed back; then fall back to `TemplateReporter`.
- `TemplateReporter` builds the same `AgentReport` deterministically from the `Incident`. It is the fallback if Bedrock is unavailable and must be **labelled** "template explanation" in the UI.
- The README sample sentence ("Pressure at Sensor 2 fell 18.2%…") must be **generated** from real values, never hard-coded.

---

## 10. AWS Resources

### 10.1 Region

Single region for everything. Default **`us-east-1`** unless the chosen Bedrock Claude model is confirmed enabled in `ap-south-1` for this account (decision D1, verified with `infra/scripts/14_bedrock_check.sh`). Never split S3/SageMaker/ECS across regions. Exception: a Bedrock *cross-region inference profile* may route a call to other regions of the same geography — this is required for newer Claude models (on-demand calls by bare model id are rejected).

### 10.2 S3 layout — `s3://aquaagent-<accountid>-<region>/`

```
configs/        networks/*.json, generation/ds1.yaml, sensors/*.json
raw/ds1/        shard=0..7/{scenarios,node_states,link_states,tank_states,pump_states,sensors,context,validation_log}/*.parquet
processed/ds1/  split=train|val|test/<table>/*.parquet, graph/, manifest.json
features/ds1/   train.pt, val.pt, test.pt (or .npz), scalers.json
models/         predictor/<model_version>/model.tar.gz
                anomaly/<thresholds_version>/thresholds.json
                localisation/<signatures_version>/signatures.parquet
experiments/    <model_version>/{metrics.json, hop_error.csv, plots/}
demo/           fallback_recording.mp4, reveal_logs/
```

Enable bucket versioning. Block public access.

### 10.3 IAM (least privilege, one role per actor)

| Role | Trusted by | Permissions |
|---|---|---|
| `aqua-ecs-exec` | ECS tasks | pull ECR, write CloudWatch Logs, `ssm:GetParameters` on `/aquaagent/*` (+ `kms:Decrypt` via SSM) for injected secrets |
| `aqua-sim-task` | ECS (generate mode) | `s3:PutObject/GetObject/ListBucket` on bucket |
| `aqua-api-task` | ECS (serve; shared by the `api` and `sim` containers of the one task — accepted, the sim never calls AWS) | `sagemaker:InvokeEndpoint` on our endpoint (T2b); `bedrock:InvokeModel*` on the chosen **inference-profile ARN and the foundation-model ARNs in every region it routes to** (T2d); `s3:GetObject` on `models/` |
| `aqua-sagemaker-exec` | SageMaker | S3 read `features/`, write `models/`, `experiments/`; ECR pull; logs |
| Amplify service role | Amplify | not needed for static hosting (not created) |
| `aqua-codebuild` (optional) | CodeBuild | push our two ECR repos, read `codebuild/` source zip, logs — only for the no-docker fallback |

No long-lived keys in code or images. Secrets (API key) in SSM Parameter Store → injected as ECS env.

### 10.4 Environment variables (canonical names)

| Var | Used by | Example |
|---|---|---|
| `AQUA_MODE` | api, sim | `local` / `aws` |
| `AQUA_REGION` | all | `us-east-1` |
| `AQUA_BUCKET` | all | `aquaagent-1234…-us-east-1` |
| `AQUA_NETWORK_ID` | api, sim | `net_epa_tutorial_v1` |
| `AQUA_SENSOR_LAYOUT_ID` | api | `sensors_default_v1` |
| `AQUA_SIM_URL` | api | `http://localhost:8000` |
| `AQUA_PREDICTOR_ENDPOINT` | api | `aquaagent-predictor` |
| `AQUA_PREDICTOR_VERSION` | api | `mlp_ds1_…` |
| `AQUA_PREDICTOR_ARTIFACT` | api | local dir or `s3://…/model.tar.gz` of the predictor for the in-process client (T1 default; v1.1.0) |
| `AQUA_THRESHOLDS_URI`, `AQUA_SIGNATURES_URI` | api | `s3://…` |
| `AQUA_AGENT` | api | `bedrock` / `template` |
| `AQUA_BEDROCK_MODEL_ID` | api | model id **or inference-profile id**, discovered by `14_bedrock_check.sh`; **not hard-coded** |
| `AQUA_API_KEY` | api | SSM |
| `AQUA_CORS_ORIGINS` | api | Amplify domain |
| `VITE_API_BASE_URL` | frontend | API Gateway URL |

### 10.5 Cost guardrails

- AWS Budget alert at a low threshold on Day 1.
- SageMaker endpoint (T2b): smallest instance that passes G6 latency (< 300 ms p95). **Delete the endpoint after judging**; keep `model.tar.gz`. Scalers live inside `model.tar.gz` (the copy in `features/` is the build source).
- API Gateway stage throttling on (the API key is public in the browser).
- ECS `desiredCount = 0` outside demo windows after the event.
- Tag every resource `project=aquaagent`.

---

## 11. Information-Leakage Firewall (scientific integrity)

| Boundary | Allowed through | Never allowed through |
|---|---|---|
| Sim engine → dataset | everything (truth) | — |
| Dataset → model **inputs** | `sensors.measured_value`, `context`, static `graph` features | `node_states` of hidden nodes, `link_states` (except observed flows), `scenarios.*`, `hidden.*` |
| Orchestrator → predictor/detector/localiser | `SensorWindow` only (enforced by function signature + type) | `HydraulicSnapshot`, `SimEvent` with `hidden=true` |
| Orchestrator → agent tools | `Incident`, predictor outputs, `NetworkConfig` static | ground truth, challenge spec |
| Orchestrator → frontend | `NetworkView` | `hidden.*`, hidden events (until reveal) |

Unit test (G8): construct a session with a hidden leak, call every public endpoint and every agent tool, and assert that neither the leak location ID, `LK_*`, nor the leak area appears anywhere in the serialized output before `/challenge/reveal`.

---

## 12. Acceptance Gates

| Gate | Tier | Module | Pass criteria |
|---|---|---|---|
| **G1** | T1 | Sim engine | EPA network built from §6 tables, exported `.inp`/`.json` topology == §6.2 (test); 24 h EPS at 300 s; PDD on, healthy baseline ≥ 20 m; junction leak and pre-split pipe leak both change pressures/flows; mass balance ≤ 1e-4 m³/s every step; stepwise advance == full run (or documented replay fallback); WNTR version pinned; container runs `serve`. |
| **G2** | T1 | Data gen | 20-sim local smoke run reproducible bit-for-bit from seeds; leak-size calibration recorded; full `ds1` (1,200) in `data/processed/ds1/` with manifest (T2a: also in S3); ≥ 95% valid; split integrity test; holdout locations absent from train/val; firewall data test. |
| **G4** | T1 | Predictor | MLP beats nearest-sensor baseline on hidden-node MAE; hop-distance table produced; scalers fitted on train only; leakage test passes (shuffling hidden-node targets destroys performance; removing a forbidden column changes nothing); LOO residual on LARGE_LEAK val sims > 3σ. |
| **G5** | T1 (T2c: localisation rows) | Detector (+ localisation) | Thresholds tuned on val only and frozen (hash recorded) before test; §9.5 detection rows produced on test; FAR on each operational scenario type reported separately. T2c adds the localisation rows. |
| **G7** | T1 (T2d: Bedrock) | Explanation | T1: `TemplateReporter` produces a schema-valid, grounded `AgentReport` for 10 recorded incidents. T2d: the same 10 incidents → 10 Bedrock reports with `grounding_check.passed=true`; template fallback works with Bedrock disabled. |
| **G8** | T1 | Orchestrator | All §7.14.1 endpoints conform to schema; firewall test (§11) passes; full challenge loop (start → DETECTED → report → reveal) runs end-to-end locally. T2a: also on AWS. |
| **G9** | T1 | Frontend | No hydraulic math in frontend code (grep check); runs the full demo against the local API; usable at 1366×768 and on a phone in portrait. T2a: deployed on Amplify against the AWS API. |
| **MVP** | T1 | all T1 | `docker compose up` on a clean machine → 3 consecutive clean challenge runs (detected, reveal correct, report shown). **No T2 work starts before this passes.** |
| **G3** | T2a | AWS infra | `curl https://<apigw>/api/health` returns ok from the public internet; ECS task healthy; ds1 + model artifacts in S3; budget alert active. |
| **G6** | T2b | SageMaker | Training job reproducible from S3 inputs; endpoint returns §7.9 schema; p95 latency < 300 ms; in-process predictor produces identical outputs (±1e-5) from the same artifact. |
| **G10** | T1 (+T2 if deployed) | Demo | 3 consecutive clean challenge runs on the stack being demoed; recorded fallback video; every number on slides traced to `experiments/`. |

---

## 13. Build Schedule — 8 → 11 Oct 2026 (v1.1.0: MVP first)

Assumes hackathon ends evening of 11 Oct. Adjust the times, not the order. **T1 is the plan; T2 is the bonus.**

### Day 1 — Thu 8 Oct: Physics is real (first vertical slice: React → FastAPI → WNTR → SVG)
| Block | Work | Gate |
|---|---|---|
| AM | Repo skeleton, contracts (done); Python 3.12 env; budget alert + Bedrock D1 check only if time (5 min each) | — |
| AM–PM | Sim engine: build network from §6, EPS, PDD, junction + pre-split pipe leaks, mass balance, stepwise advance | G1 (local) |
| PM | Sim server (§7.14.2) + Dockerfile; orchestrator skeleton (`/session/reset`, `/network/*`, `/sim/step`, taps/pipes/valve via the visibility filter); frontend renders the real topology and live flow | — |
| Night | Scenario sampler + 20-sim smoke run + leak calibration | G2 (smoke) |

### Day 2 — Fri 9 Oct: Data and the first model
| Block | Work | Gate |
|---|---|---|
| AM | Full ds1 locally (parallel shards) + merge + split + firewall test | G2 |
| AM–PM | Feature builder; baseline + MLP with 5-sensor LOO; leakage tests; hop table | G4 |
| PM | Residuals + RTCA detector tuned on val, frozen; test metrics | G5 (T1 rows) |
| PM | Frontend: tap/pipe/valve menus, speed, inspector, status bar | — |

### Day 3 — Sat 10 Oct: Close the loop → MVP
| Block | Work | Gate |
|---|---|---|
| AM | Orchestrator: window buffer, in-process predictor, detector, `Incident`, challenge start/status/reveal, firewall test | G8 (local) |
| AM | `TemplateReporter` + 10 recorded incidents | G7 (T1) |
| PM | Frontend challenge panel + report + reveal; responsive pass | G9 (local) |
| Evening | `docker compose up` on a clean checkout → 3 clean runs | **MVP** |
| Night | T2a only if MVP passed: S3 upload, ECR, ECS, ALB, API Gateway, Amplify | G3 |

### Day 4 — Sun 11 Oct: Make it unbreakable
| Block | Work | Gate |
|---|---|---|
| AM | Record fallback video of the working stack (local or AWS); slides with measured numbers only | G10 |
| AM | T2b SageMaker training job + endpoint → T2c localisation → T2d Bedrock, strictly in that order, each only if the previous is green | G6 / G5 loc / G7 Bedrock |
| PM | Feature freeze 3 h before judging; rehearsal ×3 | — |

### Cut lines (decide at these checkpoints, not later)
- **End of Day 1:** if pre-split pipe leaks misbehave → junction leaks only for ds1 and the challenge.
- **End of Day 2:** if the MLP does not beat the baseline → ship the baseline predictor; residual detection still works on top of it (report honestly).
- **Evening Day 3:** if the MVP loop is not clean → no T2 work; Day 4 AM goes to fixing the MVP.
- **Day 4 midday:** stop starting new T2 items; whatever is green ships, anything else becomes a "next steps" slide.

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| WNTRSimulator stepwise advance behaves unexpectedly after mid-run leak changes | Low (feasibility run: restart == full run, 19 ms/step) | High | Pre-split pipes (no mid-run topology change); G1 test stepwise == full run; fallback = replay from t=0 with event log |
| PDD/leak convergence failures at bursts | Med | Med | Log + exclude; clamp burst area; record failure rate in manifest |
| Predictor learns to reconstruct leaks → no residual | Med | **Critical** | §9.1 normal-only training; unit test: LOO residual on a large leak must exceed 3σ |
| Python 3.14 has no WNTR wheels | High (dev laptop is 3.14) | High | Python 3.12 via `uv` (`make setup`); containers use `python:3.12-slim` |
| Scope creep into T2/T3 before the loop works | High | **Critical** | Gate MVP (§12) blocks all T2 work |
| Detector fires on demand changes | High | High | Operational scenarios (HIGH/LOW_DEMAND, DEMAND_SHIFT) in train/val; FAR per type; T3 classifier |
| Mixed-content / CORS between Amplify and API (T2a) | High | High | API Gateway HTTPS front door; FastAPI sole CORS owner; `AQUA_CORS_ORIGINS` |
| Bedrock model not enabled / needs inference profile | Med | Med (T2d only) | `14_bedrock_check.sh`; inference-profile id + IAM for all routed regions; template fallback is T1 anyway |
| Endpoint cold start / latency in live demo | Low | Med | Real-time endpoint (not serverless); warm with health call before demo |
| Wi-Fi at venue fails | Med | **Critical** | Recorded fallback video; `docker compose` local mode on laptop |
| Overclaiming in pitch | Med | High | §16 claims discipline; every number traced to `experiments/` |

---

## 15. Open Decisions (defaults apply until changed)

| ID | Decision | Default |
|---|---|---|
| D1 | AWS region | `us-east-1` unless Bedrock model confirmed in `ap-south-1` (T2) |
| D2 | Bedrock model (T2d) | a current Claude model available to the account; model **or inference-profile** ID in `AQUA_BEDROCK_MODEL_ID` |
| D3 | Tank initial level | 1.07 m (3.5 ft; the tutorial text says both 3.5 ft and 4 ft) |
| D4 | Ship model | MLP (baseline if MLP fails G4); GNN is T3 |
| D5 | Window W / consecutive T | 6 / 3 steps (tuned on val) |
| D6 | Interactive timestep | **300 s** (single cadence, v1.1.0) |
| D7 | ds1 size | **1,200 requested, 8 scenario types** (v1.1.0) |
| D8 | Auth | single `X-Api-Key` header |
| D9 | Hard holdout locations | `pipe:5`, `junction:6` |
| D10 | ECS sizing | 1 vCPU / 2 GB per task (raise if WNTR stepping is slow) |
| D11 | Python | 3.12 everywhere (local via `uv`, containers `python:3.12-slim`) |
| D12 | WNTR | `1.5.0` (feasibility-validated; pin confirmed in G1) |

---

## 16. Claims Discipline (pitch, blog, README)

Say: "in our simulated network", "we evaluate", "under these assumptions", "probable zone", "the prototype demonstrates".
Never say: "we solve leakage", "detects every leak", "three sensors are enough for any network", "represents Pune", "real-time city telemetry", "AWS makes it accurate", "100% accuracy" (unless our own test table says so, with its n).

Cite external context correctly: the AquaSentinel / Heter-GATRes numbers in the briefing document are **their** results on **their** benchmarks — use them as motivation, never as our results.

Always show alongside our numbers: dataset size, number of test sims, holdout definition, false-alarm rate.

---

## 17. Change Control

1. Propose in the module MD under `## Proposed Backbone Changes` (what, why, which contracts).
2. Owner edits BACKBONE.md, bumps `backbone/x.y.z` (patch = clarification, minor = additive field, major = breaking), and updates `shared/contracts/`.
3. Append to the changelog below.

### Changelog
| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-10-08 | Initial frozen backbone for hackathon build |
| 1.1.0 | 2026-10-08 | Resolves BI-01…BI-21 (`docs/BACKBONE_ISSUES.md`). Scope re-tiered to the MVP detection loop (§2, gate MVP §12, schedule §13). Single 300-s cadence (§5.3, D6). Connectivity + zones + UI coordinates stated in §6.2 (no official `.inp` exists). Pre-split pipe leaks + verified stepping (§6.3). Observation-layer units, `_pct`/`_lpm` (§5.2). New ids (§5.1). `leave_one_out_flow` over 5 sensors (§7.9, §9.1–9.2). `Incident.localisation` nullable until T2c; `AgentReport.generated_by`. ds1 = 1,200 sims / 8 types, generated locally (§8). IAM: exec-role SSM, inference profiles, CodeBuild role (§10.3). Grounding exemptions (§9.6). Python 3.12, WNTR 1.5.0 (D11, D12). |

---

## Appendix A — Repository Layout

```
aquaagent/
├── BACKBONE.md
├── INSTRUCTIONS.md · TILL_NOW.md
├── docs/modules/01_SIMULATION_ENGINE.md … 10_DEMO_AND_PITCH.md · docs/research/ · docs/aws/ · docs/RUNBOOK.md
├── shared/
│   ├── contracts/        # Pydantic models (python) + contracts.ts
│   └── units.py / units.ts
├── config/
│   ├── networks/net_epa_tutorial_v1.{inp,json}
│   ├── sensors/sensors_default_v1.json
│   └── generation/ds1.yaml
├── sim/                  # image: aquaagent-sim
│   ├── engine/           # network build, session, stepping, leaks, snapshot mapping
│   ├── scenarios/        # ScenarioSpec sampling
│   ├── generate/         # batch runner, writers, validation, merge
│   ├── server/           # FastAPI §7.14.2
│   ├── Dockerfile        # ENTRYPOINT: serve | generate | merge
│   └── tests/
├── ml/
│   ├── features/         # GraphSample builder, scalers
│   ├── predictor/        # baseline, mlp, gnn, train.py (same script local + SageMaker)
│   ├── anomaly/          # residuals, RTCA thresholds, classifier (T2)
│   ├── localisation/     # signature generation + matcher
│   ├── sagemaker/        # launch_training.py, deploy_endpoint.py, inference.py
│   └── evaluation/       # metrics, hop-error, reports
├── api/                  # image: aquaagent-api
│   ├── app/main.py
│   ├── routes/           # §7.14.1
│   ├── session/          # event log, challenge, visibility filter
│   ├── clients/          # SimClient, PredictorClient, AgentRunner
│   ├── pipeline/         # SensorWindow buffer → detector → localiser → Incident
│   ├── agent/            # tools, prompt, grounding, template reporter
│   └── tests/            # firewall test, schema conformance
├── frontend/             # React + TS + Vite + SVG (Amplify)
├── infra/                # scripts or CDK/Terraform for §10
└── docker-compose.yml    # sim + api + frontend locally
```

## Appendix B — Module MD Template

```markdown
# <NN>_<NAME>.md
Backbone version: backbone/1.1.0

## Purpose
## Inputs  (cite Backbone §)
## Outputs (cite Backbone §)
## Implementation plan (ordered steps, each ≤ 2 h)
## Tests
## Acceptance gate (copy Gx from Backbone §12, add module-specific checks)
## Risks / fallbacks
## Proposed Backbone Changes
```

## Appendix C — Glossary

**Snapshot** full hydraulic state at one instant · **EPS** extended-period simulation · **PDD** pressure-dependent demand · **LOO** leave-one-sensor-out prediction · **Residual** observed − expected · **Signature** sensor residual pattern produced by a known simulated fault · **Firewall** rules in §11 separating truth from what models see · **Challenge** hidden-fault demo mode.

---
*End of BACKBONE.md (backbone/1.1.0) — Physics generates reality. ML interprets sparse observations. The agent explains evidence and supports decisions.*
