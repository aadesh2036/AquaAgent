# AquaAgent — BACKBONE.md

> **Find the Water Nobody Can See.**
> Physics generates reality. ML reconstructs the hidden state. Anomaly detection finds what does not fit. An agent explains the evidence and recommends action.

| Field | Value |
|---|---|
| Document | BACKBONE.md — master PRD + contract spec |
| Contract version | `backbone/1.0.0` |
| Status | FROZEN for hackathon (8–11 Oct 2026) unless changed via §17 |
| Owner | Aadesh Deshmukh |
| Applies to | Every module MD in `docs/modules/` and every coding agent |

---

## 0. How to Use This Document (READ FIRST — agents included)

1. **Every agent reads two files:** this `BACKBONE.md` **and** the one module MD it is assigned (e.g. `docs/modules/01_SIMULATION_ENGINE.md`). Nothing else is required context.
2. **BACKBONE owns the contracts.** Module MDs own the implementation. A module MD may *add* internal detail but may **never redefine** a schema, ID, unit, endpoint, S3 path or env var defined here.
3. **If a contract is wrong or missing:** stop, propose the change in the module MD under `## Proposed Backbone Changes`, and the owner bumps `backbone/x.y.z` (§17). Do not silently diverge.
4. **Every schema here has a Pydantic (Python) and a TypeScript twin.** They live in `shared/contracts/` and are the only place schemas are coded. Modules import them; they do not re-declare them.
5. **Precedence when documents disagree:** BACKBONE.md > module MD > `AquaAgent_handoff.md` > Simulation Spec v1 > Prototype Guide > README_FOR_SIM.md.
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
  → SageMaker endpoint reconstructs expected state
  → residuals cross dual threshold → anomaly detected
  → localisation ranks candidate pipes/zones
  → Bedrock AquaAgent explains WHAT / WHY / WHERE / EVIDENCE / ACTION
  → REVEAL: ground truth vs AI answer, detection delay, rank of true location
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

### 2.1 In scope (hackathon build)

| Tier | Item | Owner MD |
|---|---|---|
| **T1 — must work** | WNTR simulation engine (interactive + batch) in a container | 01, 02 |
| T1 | Synthetic dataset (≥2,000 simulations) in S3, ML-ready | 02, 03 |
| T1 | Hydraulic state predictor (baseline MLP; GNN if it beats it) trained on SageMaker | 04, 06 |
| T1 | SageMaker real-time endpoint serving the predictor | 06 |
| T1 | Residual-based dual-threshold anomaly detector | 05 |
| T1 | Signature-based localisation (top-k ranking) | 05 |
| T1 | Orchestrator API coordinating sim ↔ ML ↔ agent | 08 |
| T1 | React SVG interactive network on Amplify | 09 |
| T1 | Bedrock AquaAgent (tool-use, grounded, structured report) | 07 |
| **T2 — high value** | GNN predictor + hop-distance error report | 04 |
| T2 | Fault-type classifier (leak vs valve vs demand vs sensor fault) | 05 |
| T2 | Agent "what-if" counterfactual (isolate pipe → simulated impact) | 07, 01 |
| **T3 — only if T1/T2 green** | Topology family (5–10-node generated networks), unseen-topology test | 02, 04 |
| T3 | RL / pressure optimisation | — (future) |
| T3 | Step Functions, IoT Core, MLOps | — (future, pitch slide only) |

### 2.2 Explicitly OUT of scope

Real sensors / IoT hardware · Pune map or city-scale network · water quality · 3D/CFD · RL training · MLOps automation · multi-user sessions · authentication beyond an API key.

> **Rule:** Never sacrifice a T1 item to build a T2/T3 item.

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
| Public HTTPS entry | **API Gateway HTTP API** → HTTP proxy to ALB | Solves mixed-content: Amplify is HTTPS, a raw ALB is HTTP. (Alt: CloudFront in front of ALB.) |
| Orchestrator + Sim engine | **ECS Fargate**, ONE task definition, TWO containers (`api` :8080, `sim` :8000) talking over `localhost` | One task = one in-memory session. `desiredCount = 1`. |
| Load balancer | **ALB** → target group on `api:8080`, health `/api/health` | |
| Batch data generation | **ECS RunTask** of the `aquaagent-sim` image with command `generate …`, N parallel shards | Same image as serve mode |
| Images | **ECR** repos `aquaagent-sim`, `aquaagent-api` | tag = git short SHA |
| Data / models | **S3** bucket `aquaagent-<accountid>-<region>` | layout §10.2 |
| Training | **SageMaker Training Job** (PyTorch framework container, script mode) | CPU instance is sufficient for an 8-node graph |
| Inference | **SageMaker real-time endpoint**, 1 instance | Delete after the event (§10.5) |
| Agent LLM | **Bedrock Converse API** with `toolConfig` | Bedrock Agents/AgentCore = pitch "next step", not required |
| Logs | **CloudWatch Logs** for ECS, SageMaker | |

> **Why not separate ECS services for sim and api?** The interactive session lives in memory. Two containers in one task share a lifecycle and `localhost`, which removes service discovery and state-sync work we do not have time for. The boundary between them is still a clean HTTP contract (§7.14.2), so they can be split later.

### 3.3 Local-first rule

Every component must run locally with `docker compose up` **before** it is deployed. AWS-only behaviour is hidden behind clients with a local fallback:

| Client | `AQUA_MODE=local` | `AQUA_MODE=aws` |
|---|---|---|
| `PredictorClient` | loads `model.pt` from disk, in-process | invokes SageMaker endpoint |
| `AgentRunner` | Bedrock via local AWS creds, or `TemplateReporter` if `AQUA_AGENT=template` | Bedrock |
| `DatasetStore` | `./data/` | `s3://…` |

---

## 4. Module Map and Sub-MD Index

Create these files in `docs/modules/`. Each module MD must contain: **Purpose · Inputs (Backbone refs) · Outputs (Backbone refs) · Implementation plan · Tests · Acceptance gate · Proposed Backbone Changes**.

| # | Module MD | Owns code in | Consumes | Produces | Gate |
|---|---|---|---|---|---|
| 01 | `01_SIMULATION_ENGINE.md` | `sim/engine/`, `sim/server/` | §6, §7.1–7.4 | `HydraulicSnapshot`, sim HTTP API §7.14.2 | G1 |
| 02 | `02_DATA_GENERATION.md` | `sim/generate/`, `sim/scenarios/` | §7.1–7.2, §8 | Parquet tables §7.5, manifest §7.6 | G2 |
| 03 | `03_AWS_INFRA.md` | `infra/` | §3.2, §10 | ECR, ECS, ALB, APIGW, S3, IAM | G3 |
| 04 | `04_ML_PREDICTOR.md` | `ml/predictor/`, `ml/features/` | §7.5, §7.7, §9.1–9.2 | `model.tar.gz`, eval report | G4 |
| 05 | `05_ANOMALY_LOCALISATION.md` | `ml/anomaly/`, `ml/localisation/` | §7.9–7.11, §9.3–9.4 | thresholds.json, signatures.parquet, eval report | G5 |
| 06 | `06_SAGEMAKER.md` | `ml/sagemaker/` | §7.9, §10 | training job, endpoint | G6 |
| 07 | `07_AQUAAGENT_BEDROCK.md` | `api/agent/` | §7.12–7.13, §9.6 | `AgentReport` | G7 |
| 08 | `08_ORCHESTRATOR_API.md` | `api/` | everything | public API §7.14.1 | G8 |
| 09 | `09_FRONTEND.md` | `frontend/` | §7.14.1, §7.15 | Amplify site | G9 |
| 10 | `10_DEMO_AND_PITCH.md` | `docs/demo/` | eval reports | script, slides, fallback video | G10 |

### Dependency graph (critical path in **bold**)

```
**01 Sim engine** ──▶ **02 Data gen** ──▶ **04 Predictor** ──▶ **06 SageMaker** ──┐
      │                    │                    │                               │
      │                    └──▶ 05 Anomaly/Loc ◀┘                               ▼
      ├──▶ 03 AWS infra ──────────────────────────────────────────────▶ **08 Orchestrator** ──▶ 10 Demo
      └──▶ 09 Frontend (can start on mocked §7.14.1 from Day 1) ───────▶        ▲
                                                     07 Agent ─────────────────┘
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
| Incident | `inc_<sessionId>_<simTimeS>` | `inc_3f9a1c_43200` |

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

**Rule:** every numeric column and JSON field carries its unit suffix. A field without a suffix is a bug. Conversions happen in exactly one place: `shared/units.py` / `shared/units.ts`.

### 5.3 Time

- Dataset hydraulic timestep: **300 s (5 min)**, episode duration **24 h** → 289 snapshots per simulation.
- Interactive timestep: **60 s**. Speed `1×/5×/20×` = number of 60-s steps advanced per frontend tick (tick = 1 s wall clock). Backend never runs a background clock (§7.14.1 `POST /api/sim/step`).
- Sim start = 00:00 of a nominal day. Demand pattern indexes by `sim_time_s mod 86400`.

### 5.4 Seeds and reproducibility

- Every random draw goes through `numpy.random.Generator(PCG64(seed))`. **No** `random`, **no** global `np.random`.
- `seed` for a simulation = `hash64(dataset_seed, sim_index)`, recorded in the scenario row.
- `config_hash` = SHA-256 of canonical JSON of `NetworkConfig` + `ScenarioSpec` + generator code version. Stored per simulation.

### 5.5 Versioning

- `backbone/x.y.z` — contract version; every API response carries header `X-Aqua-Contract: backbone/1.0.0`.
- `schema_version` field inside every persisted JSON/Parquet manifest.
- Library pins live in `sim/requirements.txt`, `api/requirements.txt`, `ml/requirements.txt`. **Pin the exact WNTR version validated in G1 and never float it.**

---

## 6. Canonical Network — `net_epa_tutorial_v1`

Baseline = official EPANET 2.2 tutorial example network, built programmatically in WNTR (or loaded from the tutorial `.inp`). **Connectivity (start/end nodes) is taken from the official tutorial and exported to `config/networks/net_epa_tutorial_v1.json` in G1; that file is the source of truth for topology.** This document does not restate start/end nodes to avoid transcription error.

### 6.1 Nodes (SI; source values in ft/gpm)

| Node | Type | Elevation (m) | Base demand (L/s) | Role / UI label | Instruments |
|---|---|---|---|---|---|
| 1 | Reservoir | 213.36 (700 ft) | — | Source | context: `reservoir_head_m` (known) |
| 2 | Junction | 213.36 | 0 | Pump discharge header | **S1** |
| 3 | Junction | 216.41 (710 ft) | 9.46 (150 gpm) | Commercial district | **T1** |
| 4 | Junction | 213.36 | 9.46 | West residential | **S2**, **T2** |
| 5 | Junction | 198.12 (650 ft) | 12.62 (200 gpm) | Valley consumers | hidden |
| 6 | Junction | 213.36 | 9.46 | East residential | **S3**, **T3** |
| 7 | Junction | 213.36 | 0 | Loop tie point | hidden |
| 8 | Tank | 252.98 (830 ft) | — | Elevated storage, max depth 6.10 m (20 ft), Ø 18.29 m (60 ft) | context: `tank_level_m` (known) |

### 6.2 Links

| Link | Kind | Length (m) | Diameter (m) | HW C | Instruments / UI |
|---|---|---|---|---|---|
| 1 | Pipe | 914.4 | 0.3556 | 100 | |
| 2 | Pipe | 1524.0 | 0.3048 | 100 | |
| 3 | Pipe | 1524.0 | 0.2032 | 100 | **F1** |
| 4 | Pipe | 1524.0 | 0.2032 | 100 | |
| 5 | Pipe | 1524.0 | 0.2032 | 100 | |
| 6 | Pipe | 2133.6 | 0.2540 | 100 | **F2** |
| 7 | Pipe | 1524.0 | 0.1524 | 100 | **V1** (see note) |
| 8 | Pipe | 2133.6 | 0.1524 | 100 | |
| 9 | Pump | — | — | — | design point 37.85 L/s @ 45.72 m; context: `pump_status`, `pump_flow_lps` (SCADA-known) |

> **V1 honesty note:** the EPA tutorial network has no valve element. "Valve V1" is implemented as **pipe 7 status OPEN/CLOSED** (and, for partial closure, a reduced HW C / minor loss). The UI may call it a valve; the README and pitch must not claim it is an EPANET valve object.

### 6.3 Hydraulics configuration (frozen)

| Option | Value |
|---|---|
| Simulator | **`wntr.sim.WNTRSimulator` for everything** (leaks + PDD require it; one simulator = no cross-simulator discrepancy) |
| Head loss | Hazen-Williams |
| Demand model | `PDD`, `required_pressure_m = 20`, `minimum_pressure_m = 0` (tune in G1 so the healthy baseline is ≥ 20 m everywhere; record final values in network config) |
| Leak model | WNTR `add_leak(area, discharge_coeff=0.75, start_time, end_time)` on a junction; pipe leaks via `wntr.morph.split_pipe` at fraction `pos` then `add_leak` on `LK_<pipe>` |
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
{"event_id":"ev_0007","sim_time_s":43260,"source":"user|challenge|system",
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
- Mass-balance check (G1): `Σ reservoir outflow + Σ tank outflow ≈ Σ delivered demand + Σ leak`, tolerance 1e-4 m³/s.

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
  "dataset_seed":20261008,"n_requested":2400,"n_valid":2371,"n_failed":29,
  "counts_by_split":{"train":1660,"val":355,"test":356},
  "counts_by_scenario_type":{"NORMAL":720,"SMALL_LEAK":200},
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

`_z` = standardised with statistics computed **on train split only**, saved as `ml/artifacts/<model_version>/scalers.json`.

**Forbidden as input (leakage):** `demand_m3s` of hidden nodes, `leak_m3s`, any `hidden.*`, `scenario_type`, anything from timesteps after `sim_time_s`.

The MLP baseline uses the flattened equivalent: `[observed pressures (3), observed flows (2), lags, context] → hidden pressures`.

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

Window length: last **12 steps** (interactive: 12 min at 60 s; dataset: 1 h at 300 s). Missing readings = `null`, never 0.

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
  "latency_ms": 18
}
```

`leave_one_out`: for each sensor `s`, mask `s`, predict its pressure from the remaining sensors + context. This is how we get a residual **at an observed location** (see §9.2 — this is the core anomaly signal). One endpoint call returns both, to avoid 4 round trips.

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
  "detection_delay_steps":3,
  "suspected_class":"LEAK","class_probs":{"LEAK":0.81,"DEMAND_SPIKE":0.12,"VALVE_CLOSURE":0.07},
  "driving_sensors":["S2","F1"],
  "residual_history_ref":"session buffer last 12 frames",
  "thresholds_version":"thr_ds1_202610100900"
}
```

`suspected_class` is T2; in T1 it is `null`.

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

Language rule: UI and agent say **"probable leak zone"** / **"most likely pipe"**, never "exact location".

### 7.12 `Incident` (the object handed to the agent)

```json
{
  "incident_id":"inc_3f9a1c_43200","session_id":"sess_3f9a1c","created_sim_time_s":43200,
  "network_id":"net_epa_tutorial_v1","sensor_layout_id":"sensors_default_v1",
  "anomaly": { "…": "AnomalyResult §7.10" },
  "localisation": { "…": "LocalisationResult §7.11" },
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

`grounding_check` is filled by the orchestrator (§9.6), not by the model.

### 7.14 HTTP APIs

#### 7.14.1 Public orchestrator API (frontend ↔ `aquaagent-api`)

Base: `${VITE_API_BASE_URL}/api`. Header `X-Api-Key` required in `aws` mode. All responses carry `X-Aqua-Contract`.

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
| POST | `/challenge/start` | `{difficulty?: "small"\|"medium"\|"large"}` | `{challenge_id, started_sim_time_s}` — fault is hidden |
| GET | `/challenge/status` | — | `{state: "RUNNING"\|"DETECTED"\|"TIMEOUT", anomaly: AnomalyResult, incident_id?}` |
| POST | `/agent/diagnose` | `{incident_id}` | `AgentReport` |
| POST | `/agent/ask` (T2) | `{incident_id, question}` | `{answer, grounding_check}` |
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
  "events":[{"sim_time_s":43140,"text":"Tap 2 opened"}]
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

### 8.1 Scenario mix (target 2,400 requested → ≈2,350 valid)

| scenario_type | count | is_anomalous | parameters (uniform ranges unless stated) |
|---|---|---|---|
| NORMAL | 700 | no | demand profile randomised (§7.2), tank init 0.6–2.5 m |
| HIGH_DEMAND | 150 | no* | global mult 1.3–1.8 for whole episode |
| LOW_DEMAND | 100 | no* | global mult 0.4–0.7 |
| DEMAND_SHIFT | 150 | no* | one node ×1.5–2.5, another ×0.3–0.6 |
| DEMAND_SPIKE | 120 | yes | one node ×2–3 for 30–120 min |
| VALVE_CLOSURE | 100 | yes | pipe 7 (V1) or random pipe CLOSED at t_f |
| PARTIAL_VALVE | 80 | yes | HW C reduced to 20–40 on one pipe |
| PUMP_DEGRADE | 80 | yes | pump speed 0.75–0.9 at t_f |
| LOW_RESERVOIR | 80 | yes | reservoir head −3 to −8 m at t_f |
| SMALL_LEAK | 200 | yes | area 2e-5–8e-5 m² |
| MEDIUM_LEAK | 200 | yes | area 8e-5–2.5e-4 m² |
| LARGE_LEAK | 150 | yes | area 2.5e-4–6e-4 m² |
| PIPE_BURST | 120 | yes | area 1e-3–3e-3 m² |
| SENSOR_FAULT | 170 | no (has_sensor_fault) | one of SPIKE/BIAS/DRIFT/STUCK/MISSING on one sensor |

\* operational variation — the detector must **not** fire on these. They exist to kill the "pressure ↓ = leak" shortcut.

Fault start `t_f` ∈ [6 h, 18 h], snapped to timestep. Leaks run to episode end unless `end_s` drawn (30% of leaks end after 2–6 h).

**Leak area ranges are provisional.** In G2 calibration, measure realised leak flow at baseline pressure and adjust so the buckets roughly correspond to `<5% / 5–15% / 15–25% / >25%` of total system demand. Record final ranges in `config/generation/ds1.yaml`.

### 8.2 Fault locations

Candidate set (14): junctions `2–7` + pipes `1–8` (pipe leaks at `position ~ U(0.2, 0.8)`). Pump link `9` is not a leak location.

### 8.3 Sensor noise (applied to `sensors.measured_value` only)

Default: pressure σ = 0.05 m, flow σ = 0.10 L/s, missing 0%. Robustness variants (T2): σ ×{2, 5}, missing 5%.

### 8.4 Validation per simulation (all logged to `validation_log`)

`converged` · `no negative pressure at non-leak junctions in NORMAL` · `mass balance` (§7.4) · `tank level within [0, max]` · `all canonical nodes/links present` · `no NaN` · `pump status valid`. Any failure → excluded from tables, kept in log.

### 8.5 Splits

- Split **by `simulation_id`**, stratified by `scenario_type`: 70 / 15 / 15.
- **Hard holdout:** leaks at `pipe:5` and `junction:6` appear **only in test** (recorded in manifest). Localisation is physics-signature based (§9.4) so it can still rank them — that is the generalisation claim we test.
- Predictor training uses only **non-anomalous** train sims (§9.1).

### 8.6 Batch execution

`aquaagent-sim generate --config config/generation/ds1.yaml --shard i --num-shards 8 --out s3://…/raw/ds1/shard=i/`
Each shard writes its own Parquet files; a final `merge` step (local or one more RunTask) writes `processed/ds1/` + `manifest.json`. Expected runtime is small for an 8-node network; measure on 20 sims locally before launching.

---

## 9. ML Design (binding decisions)

### 9.1 Predictor — "what should the network look like right now?"

- **Train only on hydraulically normal simulations** (NORMAL, HIGH/LOW_DEMAND, DEMAND_SHIFT, and pre-fault timesteps of anomalous sims). If the predictor learns from leak states it learns to *reconstruct* leaks, and residuals collapse. This is the most important ML rule in the project.
- **Random sensor masking during training:** each sample randomly hides 0–1 of the 3 pressure sensors in addition to all hidden nodes, so one model handles both `reconstruct` and `leave_one_out`.
- **Model ladder (stop at the first that meets G4 targets, then try the next only if time allows):**
  1. Nearest-sensor + elevation-corrected baseline (no training; sanity floor)
  2. **MLP** on flattened features (§7.7) — expected T1 ship model
  3. GraphSAGE / GAT (PyTorch Geometric) — T2
- Loss: MSE on `y_mask` nodes; report MAE/RMSE/R², and **MAE by hop distance** (1/2/3+ hops from nearest sensor).
- Honest framing: on a fixed 8-node graph an MLP may match a GNN; the GNN earns its place only on unseen topologies (T3). Report whichever wins — do not ship a GNN just for the slide.

### 9.2 Residuals — where the anomaly signal comes from

You cannot get a residual at a node you do not observe, and a sensor fed into the model as input has a trivial residual. Therefore:

- **Pressure residual** at sensor `s`: `r_s = observed_s − LOO_prediction_s` (prediction with `s` masked).
- **Flow residual** at `F1`, `F2`: predictor also outputs expected observed flows from pressures + context (add as extra heads; trained on normal data).
- Normalise: `z_s = r_s / σ_s`, `σ_s` = std of `r_s` on **validation normal** data. Stored in `thresholds.json`.

### 9.3 Detector — RTCA-style dual threshold (T1) + classifier (T2)

Following the AquaSentinel pattern from the briefing document:
- instant flag if `|z_s| > k1` (default 2.5), cumulative flag if mean `|z_s|` over window `W` (default 6 steps) `> k2` (default 3.0);
- **ANOMALY** when ≥1 sensor has both flags for `T` consecutive steps (default 3); **WATCH** on instant-only;
- **SENSOR_FAULT** when one sensor's `|z|` is extreme, other sensors' LOO residuals are consistent with each other, and the jump is physically implausible (step change > configurable bound in one step, or variance ≈ 0 for STUCK).
- Tune `k1, k2, W, T` on validation to hit the false-alarm target on non-anomalous sims, **then freeze** before touching test.
- T2: gradient-boosted classifier on residual features → `suspected_class`.

### 9.4 Localisation — signature matching (T1)

- Offline: for each of the 14 candidate locations × 3 leak sizes × 4 times-of-day, simulate the leak and record the **sensor residual signature** (Δ observed vs no-leak twin, normalised). Save `signatures.parquet`.
- Online: average `z` vector over the detection window → cosine similarity with every signature → softmax over max-similarity per location → ranked `candidates`; aggregate by `zone_id` for `probable_zone`.
- Because signatures are generated from physics (not learned from labelled training leaks), the hard-holdout locations remain rankable.

### 9.5 Evaluation targets (report actuals honestly even if missed)

| Metric | Target (ds1 test) |
|---|---|
| Predictor MAE, hidden junctions, normal | < 1.0 m |
| Detection recall, MEDIUM/LARGE/BURST | ≥ 95% |
| Detection recall, SMALL | report (expect lower) |
| False-alarm rate on non-anomalous sims | ≤ 5% of sims |
| Median detection delay (medium leak) | ≤ 6 steps |
| Localisation top-1 / top-3 (pipe) | report / ≥ 80% top-3 |
| Zone accuracy | ≥ 85% |
| Hard-holdout locations top-3 | report separately |

### 9.6 Agent grounding

- Converse API loop, max 6 tool turns, temperature low (≤ 0.2), system prompt forbids numbers not returned by tools.
- **Grounding check (orchestrator):** extract every number in the report text; each must match a value in the turn's tool results within ±0.5% or ±0.05 absolute, after unit normalisation. Failures → `grounding_check.passed=false`, list `unmatched_numbers`, and the UI shows a warning badge. One automatic retry with the unmatched list fed back; then fall back to `TemplateReporter`.
- `TemplateReporter` builds the same `AgentReport` deterministically from the `Incident`. It is the fallback if Bedrock is unavailable and must be **labelled** "template explanation" in the UI.
- The README sample sentence ("Pressure at Sensor 2 fell 18.2%…") must be **generated** from real values, never hard-coded.

---

## 10. AWS Resources

### 10.1 Region

Single region for everything. Default **`us-east-1`** unless the chosen Bedrock Claude model is confirmed enabled in `ap-south-1` for this account (decision D1, verify on Day 1 in the Bedrock console → Model access). Never split S3/SageMaker/Bedrock across regions.

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
| `aqua-ecs-exec` | ECS tasks | pull ECR, write CloudWatch Logs |
| `aqua-sim-task` | ECS (generate mode) | `s3:PutObject/GetObject/ListBucket` on bucket |
| `aqua-api-task` | ECS (serve) | `sagemaker:InvokeEndpoint` on our endpoint; `bedrock:InvokeModel`/`Converse` on the chosen model; `s3:GetObject` on `models/` |
| `aqua-sagemaker-exec` | SageMaker | S3 read `features/`, write `models/`, `experiments/`; ECR pull; logs |
| Amplify service role | Amplify | default |

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
| `AQUA_THRESHOLDS_URI`, `AQUA_SIGNATURES_URI` | api | `s3://…` |
| `AQUA_AGENT` | api | `bedrock` / `template` |
| `AQUA_BEDROCK_MODEL_ID` | api | set from Bedrock console; **not hard-coded** |
| `AQUA_API_KEY` | api | SSM |
| `AQUA_CORS_ORIGINS` | api | Amplify domain |
| `VITE_API_BASE_URL` | frontend | API Gateway URL |

### 10.5 Cost guardrails

- AWS Budget alert at a low threshold on Day 1.
- SageMaker endpoint: smallest instance that passes G6 latency (< 300 ms p95). **Delete the endpoint after judging**; keep `model.tar.gz`.
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

| Gate | Module | Pass criteria |
|---|---|---|
| **G1** | Sim engine | EPA network builds; snapshot + 24 h EPS run; PDD on; junction leak and pipe leak (split) both change pressures/flows; mass balance within tolerance; stepwise advance works (or documented replay fallback); network JSON exported; WNTR version pinned; container runs `serve`. |
| **G2** | Data gen | 20-sim local smoke run reproducible bit-for-bit from seeds; leak-size calibration recorded; full `ds1` in S3 with manifest; ≥ 95% valid; split integrity test (no `simulation_id` in two splits); holdout locations absent from train/val. |
| **G3** | AWS infra | `curl https://<apigw>/api/health` returns ok from the public internet; ECS task healthy; generate RunTask writes to S3; budget alert active. |
| **G4** | Predictor | Beats nearest-sensor baseline on hidden-node MAE; hop-distance table produced; scalers fitted on train only; leakage test passes (shuffling hidden-node targets destroys performance; removing a forbidden column changes nothing because it was never there). |
| **G5** | Anomaly + loc | Thresholds tuned on val only; test metrics table (§9.5) produced; false-alarm rate on operational-variation scenarios reported separately. |
| **G6** | SageMaker | Training job reproducible from S3 inputs; endpoint returns §7.9 schema; p95 latency < 300 ms; `AQUA_MODE=local` produces identical outputs (±1e-5) from the same artifact. |
| **G7** | Agent | 10 recorded incidents → 10 reports with `grounding_check.passed=true`; template fallback works with Bedrock disabled. |
| **G8** | Orchestrator | All §7.14.1 endpoints conform to schema; firewall test (§11) passes; full challenge loop runs end-to-end locally and on AWS. |
| **G9** | Frontend | Deployed on Amplify; no hydraulic math in frontend code (grep check); runs the full demo against the AWS API; usable at 1366×768 and on a phone in portrait. |
| **G10** | Demo | 3 consecutive clean challenge runs on the deployed stack; recorded fallback video in `s3://…/demo/`; every number on slides traced to `experiments/`. |

---

## 13. Build Schedule — 8 → 11 Oct 2026

Assumes hackathon ends evening of 11 Oct. Adjust the times, not the order.

### Day 1 — Thu 8 Oct: Physics is real
| Block | Work | Gate |
|---|---|---|
| AM | Repo skeleton, `shared/contracts`, units module; **Bedrock model access + region check (D1)**; budget alert | — |
| AM–PM | Sim engine: build EPA network, EPS, PDD, junction + pipe leaks, mass-balance check, stepwise advance | G1 (local) |
| PM | Sim server (§7.14.2) + Dockerfile (`serve`/`generate`) ; frontend starts on **mocked** `NetworkView` | — |
| Night | Scenario generator + 20-sim smoke run; leak-size calibration | G2 (local part) |

### Day 2 — Fri 9 Oct: Data in the cloud, first model
| Block | Work | Gate |
|---|---|---|
| AM | ECR push, S3 bucket, ECS cluster, sharded `generate` RunTasks → `ds1` | G2 |
| AM | ALB + API Gateway + ECS service with `sim` + stub `api` | G3 |
| PM | Feature builder; nearest-sensor baseline + MLP **locally**; LOO masking; hop-distance report | G4 (local) |
| PM | Frontend: real topology, live flow animation, taps/pipe menu wired to local API | — |
| Night | Signature dictionary generation; detector on val | G5 (draft) |

### Day 3 — Sat 10 Oct: SageMaker, detection, agent
| Block | Work | Gate |
|---|---|---|
| AM | SageMaker training job (same script as local) → endpoint | G6 |
| AM | Orchestrator: session, challenge, `SensorWindow` buffer, detector + localiser, reveal, firewall test | G8 (local) |
| PM | Bedrock agent: tools, `submit_report`, grounding check, template fallback | G7 |
| PM | Deploy api to ECS (aws mode); Amplify frontend live against API Gateway | G9 |
| Night | GNN attempt **only if** G4–G8 green; else harden | T2 |

### Day 4 — Sun 11 Oct: Make it unbreakable
| Block | Work | Gate |
|---|---|---|
| AM | End-to-end runs on AWS ×10; fix flakiness; freeze thresholds; final test-set metrics | G5 final |
| AM | Record fallback demo video; slides with measured numbers only | G10 |
| PM | Pitch rehearsal ×3; feature freeze 3 h before judging | — |

### Cut lines (decide at these checkpoints, not later)
- **End of Day 1:** if pipe-leak splitting is unstable → use junction leaks only for ds1; pipe leaks become T2.
- **End of Day 2:** if `ds1` is not in S3 → generate locally and upload; ECS RunTask becomes a slide, not a blocker.
- **Midday Day 3:** if the SageMaker endpoint is not serving → `AQUA_MODE=local` predictor inside the api container; keep the training job as the SageMaker story.
- **Evening Day 3:** if Bedrock is not grounded reliably → ship `TemplateReporter` labelled as such; agent becomes "live attempt with fallback".

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| WNTRSimulator stepwise advance behaves unexpectedly after mid-run topology/leak changes | Med | High | Test in G1 hour 1; fallback = replay from t=0 with event log (fine for an 8-node net at modest speeds; cap 20× if slow) |
| PDD/leak convergence failures at bursts | Med | Med | Log + exclude; clamp burst area; record failure rate in manifest |
| Predictor learns to reconstruct leaks → no residual | Med | **Critical** | §9.1 normal-only training; unit test: LOO residual on a large leak must exceed 3σ |
| Detector fires on demand spikes | High | High | Operational scenarios in val; report FAR separately; T2 classifier |
| Mixed-content / CORS between Amplify and API | High | High | API Gateway HTTPS front door from Day 2; CORS env |
| Bedrock model not enabled in region | Med | High | D1 check on Day 1 AM |
| Endpoint cold start / latency in live demo | Low | Med | Real-time endpoint (not serverless); warm with health call before demo |
| Wi-Fi at venue fails | Med | **Critical** | Recorded fallback video; `docker compose` local mode on laptop |
| Overclaiming in pitch | Med | High | §16 claims discipline; every number traced to `experiments/` |

---

## 15. Open Decisions (defaults apply until changed)

| ID | Decision | Default |
|---|---|---|
| D1 | AWS region | `us-east-1` unless Bedrock model confirmed in `ap-south-1` |
| D2 | Bedrock model | a current Claude model available to the account; ID in `AQUA_BEDROCK_MODEL_ID` |
| D3 | Tank initial level | 1.07 m (3.5 ft) |
| D4 | Ship model | whichever of MLP / GNN wins on val hidden-node MAE |
| D5 | Window W / consecutive T | 6 / 3 steps (tuned on val) |
| D6 | Interactive timestep | 60 s |
| D7 | ds1 size | 2,400 requested |
| D8 | Auth | single `X-Api-Key` header |
| D9 | Hard holdout locations | `pipe:5`, `junction:6` |
| D10 | ECS sizing | 1 vCPU / 2 GB per task (raise if WNTR stepping is slow) |

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

---

## Appendix A — Repository Layout

```
aquaagent/
├── BACKBONE.md
├── docs/modules/01_SIMULATION_ENGINE.md … 10_DEMO_AND_PITCH.md
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
Backbone version: backbone/1.0.0

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
*End of BACKBONE.md — Physics generates reality. ML interprets sparse observations. The agent explains evidence and supports decisions.*
