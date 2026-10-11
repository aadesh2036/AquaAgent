# AquaAgent — AI and ML

> Everything about the data, models, training, evaluation and explainable AI in AquaAgent, with the measured results.
> Every number traces to a file under `data/experiments/` (mirrored in `s3://<bucket>/experiments/`) or to a logged run in [TILL_NOW.md](../TILL_NOW.md). Contracts live in [BACKBONE.md](../BACKBONE.md). AWS and system architecture: [AWS_ARCHITECTURE.md](AWS_ARCHITECTURE.md).
> Status: 2026-10-11. **Deployed set: `gnn_ds3_202610101549` + `thr_ds3_202610101655` + `sig_ds3_202610101738`, explainer Amazon Nova Lite.**

---

## 1. The problem in one paragraph

A water network has thousands of pipes but only a handful of sensors. AquaAgent watches **3 pressure sensors (S1–S3) and 2 flow sensors (F1–F2)** plus normal SCADA context (tank level, pump status/flow, reservoir head, time of day) on the EPA tutorial network, and answers three questions every 5 simulated minutes:

1. **What should every node read right now?** → *predictor* (graph neural network)
2. **Is something wrong?** → *detector* (sensor-set temporal network on the predictor's residuals)
3. **Where is it?** → *localiser* (physics signatures from the network map)

When the detector raises an alarm, an **Amazon Bedrock agent** writes a grounded incident report (EXPLAIN WHY). All data is synthetic — produced by the WNTR (EPANET) physics engine — and every test number below is measured on held-out simulations the models never saw.

```
  sensors S1–S3, F1–F2 + SCADA context (a SensorWindow — the only thing models ever see)
                 │
                 ▼
  ┌──────────────────────────────┐   expected reading at every node + leave-one-out (LOO) estimate per sensor
  │ PREDICTOR  edge-aware GATv2   │──────────────────────────────────────────────┐
  └──────────────────────────────┘                                               │
                 │ residual r = observed − LOO estimate,  z = r / σ                │
                 ▼                                                                │
  ┌──────────────────────────────┐   P(anomaly) per step → NORMAL / WATCH / ANOMALY
  │ DETECTOR   SensorSetNet       │──────────────────┐                            │
  └──────────────────────────────┘                   │ on ANOMALY                  │
                 │ z-pattern over the first hour      ▼                            ▼
  ┌──────────────────────────────┐   ranked pipes/junctions + probable zone   Incident (frozen evidence)
  │ LOCALISER  physics signatures │──────────────────────────────────────────────►│
  └──────────────────────────────┘                                               ▼
                                                     ┌────────────────────────────────────────┐
                                                     │ EXPLAINER  Bedrock Nova Lite tool loop  │
                                                     │ + grounding check + template fallback   │
                                                     └────────────────────────────────────────┘
```

---

## 2. Design principles (binding)

| Principle | What it means in practice |
|---|---|
| **Firewall** (BACKBONE §11) | Inference code only ever receives a `SensorWindow`. Ground truth (`hidden.*`, `LK_*`, hidden node states, scenario specs) never reaches a model, the agent's tools or the frontend. Firewall tests exist in modules 02, 04 and 08 and stay green; the predictor service returns **422** on any ground-truth field. |
| **Generalised models only** (owner decision 2026-10-09) | Shipped models are topology/layout-agnostic: the GNN reads pipe physics, not node IDs; the detector reads a *set* of sensors by type, not identity; the localiser comes from the network map. A fixed-layout gradient-boosted model (R2) was better on val but is kept only as a reference. |
| **Test once** | Hyper-parameters, thresholds and model choices use **val only**. Each test split is opened once per frozen artifact. |
| **Claims discipline** (BACKBONE §16) | Only measured numbers; "probable zone", "most likely pipe" — never accuracy claims beyond what was measured. |
| **Reproducibility** | Seeded `numpy.random.Generator(PCG64)` everywhere; dataset generation is bit-for-bit reproducible (identical SHA-256); frozen artifacts carry a content SHA-256 checked on load. |

---

## 3. Data

### 3.1 Simulation engine
- **WNTR 1.5.0** (EPANET 2.2 solver), pressure-driven demand, **single 300-s cadence** for datasets and the interactive simulator (≈ 5–18 ms per step).
- Network `net_epa_tutorial_v1`: reservoir → pump → 8 nodes / 9 links, elevated tank, 3 zones; connectivity from EPANET 2.2 Fig. 2.1 (BACKBONE §6.2).
- **Pre-split pipes**: every pipe is split at the leak point in advance, so a leak never changes topology mid-run (ΔP ≤ 1.7e-5 m vs unsplit). Stop/restart stepping equals a full run (≤ 1e-6 m).
- Mass balance < 1e-8 m³/s per step.

### 3.2 Scenario catalogue (8 types)
| Type | Fault | Leak area (m²) | Realised leak (% of system demand, calibrated) |
|---|---|---|---|
| NORMAL, HIGH_DEMAND, LOW_DEMAND, DEMAND_SHIFT | none (operational) | — | — |
| SMALL_LEAK | leak | 2e-5 – 8e-5 | median 2.6 % |
| MEDIUM_LEAK | leak | 8e-5 – 2.5e-4 | median 9.1 % |
| LARGE_LEAK | leak | 2.5e-4 – 6e-4 | median 24.5 % |
| PIPE_BURST | burst | 1e-3 – 3e-3 | median 99.9 % |

Faults start between 06:00 and 18:00 at one of 14 locations (junctions 2–7, pipes 1–8 at 0.2–0.8 of their length); 30 % of leaks end after 2–6 h. Sensor noise: pressure σ 0.05 m, flow σ 0.10 L/s.
**Holdout locations `pipe:5` and `junction:6` appear only in test**, so test measures generalisation to never-seen leak positions.

### 3.3 Datasets
| Dataset | Sims | Split train/val/test | Where generated | Normal training rows (predictor) |
|---|---|---|---|---|
| **ds1** | 1,200 | 837 / 179 / 184 | local + ECS Fargate Spot (4 shards, ≈ 8.5 min) | 181,851 |
| **ds3** (scaled, deployed) | **12,000** (same mix ×10, seed 20261010) | 8,391 / 1,800 / 1,809 | **ECS Fargate Spot, 24 shards + merge (4 vCPU / 16 GB)** | **1,820,911** |

Both: 0 failed simulations, 24 h per sim, 289 steps. ds2 is reserved for the T3 scenario types (valves, pumps, sensor faults). Config: `config/generation/ds{1,3}.yaml`.

### 3.4 Features (`ml/features/`)
- Per step: observed pressure at instrumented nodes + 300-s and 900-s lags, F1/F2 flow, context (sin/cos time, tank level, pump status, pump flow, reservoir head) and static graph attributes (elevation, base demand, node type; pipe length, diameter, roughness, pump/open flags).
- Node features (15) and edge features (7) are built by **one function** (`tensorize`) shared by training, evaluation and online inference → offline == online by construction (tested ±1e-6).
- Scalers fitted on **train only**, copied into every `model.tar.gz`; inference reads only the artifact copy.
- Targets: hydraulic **head** at all scored nodes (pressure = head − elevation) and F1/F2 flow. Targets are never inputs.

---

## 4. Predictor — edge-aware graph attention network

### 4.1 Model
- **Edge-aware GATv2** in pure PyTorch (no torch_geometric, so the same artifact runs in the training container, the API and SageMaker): node encoder + edge encoder → L × GATv2 layers with edge features in the attention, residual + LayerNorm + FFN → head decoder per node + flow decoder per flow-sensor link.
- No node identity anywhere — only physical attributes, observations and the placement mask, so the model works on any `edge_index`.
- **Training on normal behaviour only** (operational sims + pre-fault steps); post-fault rows are asserted absent.
- **Random sensor masking per sample**: 50 % contract layout with one of {none, S1, S2, S3, F1, F2} hidden (exactly what inference runs), 50 % random k = 1…5 pressure sensors anywhere. Placements `3-5-7` and `2-5-7` are never sampled (held out for evaluation).
- Loss: masked MSE on standardised head at **unobserved** scored nodes + 0.5 × MSE on masked flows. Observed inputs never contribute to the loss.
- Online `predict()` returns, in one call, the reconstruction and the 5-sensor leave-one-out estimates (§7.9).

### 4.2 Versions
| Version | Params | Config | Trained on | Where | Time |
|---|---|---|---|---|---|
| `mlp_ds1_202610090559` (reference) | 144k | 3 × 256 | ds1 | laptop CPU | 396 s |
| `gnn_ds1_202610090559` | 160k | hidden 64 × 4 layers × 4 heads | ds1 | laptop CPU | 1,370 s (best epoch 38) |
| **`gnn_ds3_202610101549` (deployed)** | **897k** | **hidden 128 × 6 layers × 4 heads**, batch 2048, AdamW + OneCycle peak lr 7e-4, 40 epochs | ds3 | **SageMaker ml.g4dn.xlarge Spot (T4 GPU)** | 3,047 s wall, **1,118 billable s**; best epoch 40 |

Training note (ds3): a first run at peak lr 2e-3 was unstable (val MAE 0.154 m at epoch 5 → 0.31 m, train-loss spike at epoch 8); it was stopped and retrained at 7e-4, which converged smoothly to val 0.101 m (selection masks).

### 4.3 Results
**Contract layout (S1–S3 + F1/F2 observed), error at the hidden junctions 3/5/7, normal states:**

| Test split | Nearest-sensor baseline | MLP ds1 | GNN ds1 | **GNN ds3** |
|---|---|---|---|---|
| ds1 test (184 sims) | 1.932 m | 0.165 m | 0.162 m | — |
| ds3 test (1,809 sims) | 1.946 m | — | 0.131 m | **0.109 m** (−17 % vs GNN ds1) |

**Sensor coverage (ds3 test, every placement of k pressure sensors over the 6 junctions, F1/F2 present):**

| k sensors | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Baseline MAE (m) | 2.78 | 2.11 | 1.62 | 1.27 | 1.00 |
| **GNN ds3 MAE (m)** | **0.080** | **0.078** | **0.076** | **0.073** | **0.070** |

**Hops to the nearest pressure sensor (ds3 test):** GNN 0.075 / 0.081 / 0.091 m at 1 / 2 / 3 hops (baseline 1.48 / 3.33 / 4.46 m).
**Latency:** `predict()` (reconstruct + 5 LOO) p50 4.7 ms on one CPU thread for the 897k model (2.3 ms for the 160k model). End to end on ECS, a 20-step simulator tick including predictor + detector calls takes p50 0.58 s (ds3 models, via API Gateway).

**Finding.** With SCADA context the hydraulic state of this small network is nearly determined, so the GNN is almost flat across coverage and hops. The coverage research question needs a larger network or node-level demand variability.

---

## 5. Detector — SensorSetNet

### 5.1 Residuals
For each sensor s, the predictor estimates s with s itself hidden (leave-one-out): **r_s = observed_s − LOO_s** (m for S1–S3, L/s for F1–F2), **z_s = r_s / σ_s**, with σ_s the std of r_s on train-split normal rows (fixed, no adaptation). Offline (batched) and online (`residual_frame`) residuals are identical within 1e-4 (tested).

### 5.2 Model selection (val only)
| Candidate | Type | Val recall MLB* | Notes |
|---|---|---|---|
| R1 RTCA | dual threshold on z, σ in pump-flow bins | 0.43 | no learning; kept as fallback `thr_ds1_202610091559` |
| R2 gradient-boosted trees | fixed sensor slots | 0.60 | **not generalisable** → reference only |
| **R3 SensorSetNet** | set model over sensors | 0.54 | **shipped** (generalised) |
*MLB = MEDIUM + LARGE leaks + BURSTs, at FAR ≤ 5 % on each operational type.

### 5.3 Model
- Input per sensor: last **24 steps (2 h)** of its z, a sensor-**type** one-hot (pressure/flow — identity is never input) and context (pump flow, tank level).
- **Shared dilated temporal CNN** per sensor → **attention pooling over the sensor set** → P(anomaly). Random sensor dropout (20 %) in training, so it still works if a sensor goes missing (val with S3 removed: 0.55).
- Supervised on the train split (label: a leak/burst is active, fault_start ≤ t < fault_end), balanced sampling; **τ (probability threshold) and T (consecutive steps) chosen on val**; alarm = P > τ for T steps → ANOMALY; it keeps scoring and clears after 6 calm steps; a pipe repair re-arms it.

### 5.4 Versions and results
| | `thr_ds1_202610091624` (ds1) | **`thr_ds3_202610101655` (deployed)** |
|---|---|---|
| Size | hidden 32, 11k params | hidden 64, **43k params** |
| Training | 12 epochs × 120k samples, laptop CPU | 20 epochs × 400k samples, **SageMaker ml.g4dn.xlarge Spot** |
| Alarm rule (val) | τ 0.99, T 6 | τ 0.99997, T 1 |

**Same test split (ds3 test, 1,809 sims; 684 medium/large/burst faults, 900 operational sims), each detector with its own predictor:**

| Metric | ds1 detector + ds1 GNN | **ds3 detector + ds3 GNN** |
|---|---|---|
| Recall MEDIUM / LARGE / BURST | 0.37 / 0.49 / 0.97 | 0.31 / 0.45 / 0.80 |
| Recall MLB | 0.545 | 0.471 |
| Recall SMALL | 0.04 | 0.04 |
| False-alarm rate DEMAND_SHIFT / HIGH_DEMAND / LOW / NORMAL | 12.0 % / 4.0 % / 0 % / 0.2 % | **0.7 % / 0.7 % / 0 % / 0 %** |
| False alarms, all 900 operational sims | — | **2 (0.2 %)** |
| Median delay LARGE / BURST (5-min steps) | 17 / 6 | **6.5 / 2** |
| Holdout-location leaks (891), recall MLB | 0.54 | 0.47 |

On ds1 test the ds1 detector measured: recall MEDIUM 0.30, LARGE 0.45, BURST 0.94, SMALL 0.12; FAR 4.4 % (4/90 operational sims).

**Reading it.** The ds3 detector is much quieter and faster on bursts; the ds1 pair catches more leaks but violates the ≤ 5 % per-type false-alarm rule on ds3 (12 % on demand-shift days). The owner chose the ds3 set. With 3 pressure + 2 flow sensors, small leaks are below the observability limit for both.

---

## 6. Localiser — physics signatures from the network map

- For every candidate location (6 junctions + 8 pipes at mid-pipe) × 3 sizes (MEDIUM, LARGE, BURST at calibrated midpoints) × onset time, **simulate the leak on the known network**, convert snapshots to sensor readings with the same code as the live API, run the same predictor + LOO residuals, normalise by the detector's σ and store the **mean z-vector over the first hour**.
- Live: mean z over the detection window → **cosine similarity** with every signature → best per location → softmax (τ 0.05) → ranked candidates; zone score = sum of its candidates.
- **No labelled field leaks needed** — a new network only needs its map, and never-trained locations are covered by construction.

| Version | Signatures | Built with |
|---|---|---|
| `sig_ds1_202610091648` | 168 (14 × 3 × 4 onset hours) | GNN ds1, laptop |
| **`sig_ds3_202610101738` (deployed)** | **336 (14 × 3 × 8 onset hours)** | GNN ds3, **SageMaker ml.c5.2xlarge Spot** |

**Protocol (onset known):** mean z over steps onset+1 … onset+12, matched against the signatures (`ml/localisation/evaluate.py`; reproduces the ds1 figures exactly).

| Split | Old pair (ds1 GNN + 168 sig) top-1 / top-3 / zone | **New pair (ds3 GNN + 336 sig)** top-1 / top-3 / zone |
|---|---|---|
| ds1 test (68 faults) | 0.71 / 0.85 / 0.81 | — |
| ds3 val (675 faults, no holdout locations) | 0.48 / 0.78 / 0.63 | 0.43 / 0.76 / **0.75** |
| ds3 test (684 faults, 98 % at holdout locations) | **0.60 / 0.86 / 0.80** | 0.47 / 0.84 / 0.61 |

Using 4 instead of 8 onset hours did not help on val (top-3 0.74–0.77). Old signatures with the new predictor's residuals were worst (val top-3 0.73), so signatures must be rebuilt with the predictor they serve. Live, the onset is estimated by the detector, so live accuracy can be lower.

---

## 7. Explainable AI — Amazon Bedrock agent

- **Trigger:** every AI alarm freezes an `Incident` (observed vs AI-expected at each sensor, detector result, localisation, context). `POST /api/agent/diagnose {incident_id}`; the UI's **EXPLAIN WHY** shows the report.
- **Model:** **Amazon Nova Lite** via the APAC inference profile (`AQUA_BEDROCK_MODEL_ID` in SSM), Converse API.
- **Tool loop:** `get_incident`, `get_sensor_history`, `get_reconstruction`, `get_candidate_locations`, `get_network_element`, forced `submit_report`; ≤ 6 tool turns, temperature 0.2, 1,500 max tokens, 20-s wall-clock budget (API Gateway limit 30 s), adaptive retries.
- **Grounding check:** every number in the report must match a value in the evidence (with unit conversions and HH:MM labels); one retry, then the deterministic **TemplateReporter** fallback. Confidence is a fixed policy, not the model's opinion. Tools see only the frozen `SensorWindow`-derived context, never ground truth. Reports are cached per incident.

| Model (7 recorded incidents) | Grounded | Calls | Latency | Tokens in / out |
|---|---|---|---|---|
| **Nova Lite (shipped)** | **7/7** | 1 | ~3 s | ~2.6k / ~0.5k (≈ $0.0003 per report) |
| Nova Micro | 6/7 | — | — | — |
| Nova 2 Lite / Nova Pro | 7/7 | 3–6 | 6–18 s | 8–20k |
| Claude Haiku 4.5 | blocked (`INVALID_PAYMENT_INSTRUMENT`, account payment method) | — | — | — |

Live (2026-10-11, ds3 models): burst on pipe 5 → report in 3.2 s, confidence HIGH, "Probable leak in zone Z3 (most likely pipe 5)".

---

## 8. Training pipeline on Amazon SageMaker (ds3)

All three models were trained as **SageMaker Training Jobs** in script mode on the AWS PyTorch 2.8 containers (image resolved by the SDK, never hard-coded), with **managed Spot**. One launcher: `python -m ml.sagemaker.launch_training --task predictor|features|detector|signatures`.

| # | Job | Instance (Spot) | Inputs → outputs | Billable |
|---|---|---|---|---|
| 1 | `aquaagent-features-ds3-…1518` | ml.r6i.2xlarge | processed/ds3 → features/ds3 (npz + scalers + graph) | 61 s |
| 2 | `aquaagent-gnn-ds3-…1549` | ml.g4dn.xlarge (GPU) | features/ds3 → models/predictor/gnn_ds3_202610101549/model.tar.gz | 1,118 s |
| 3 | `aquaagent-detector-ds3-…1641` | ml.g4dn.xlarge (GPU) | LOO residual cache (GPU: 2.42M rows in 155 s) → SensorSetNet train → τ/T on val → freeze → one test eval (+ ds1 baseline on the same test, predictor sweep) → models/anomaly/thr_ds3_202610101655 | — |
| 4 | `aquaagent-signatures-ds3-…1732` | ml.c5.2xlarge | sim engine (WNTR in the container) + predictor + detector σ → 336 signatures + val/test eval → models/localisation/sig_ds3_202610101738 | — |

The same `train.py` runs locally and in SageMaker (reads `SM_CHANNEL_*`, `SM_MODEL_DIR`); GPU support is device-agnostic (`GraphStatic.to(device)`), masks are sampled on CPU so CPU and GPU see the same placements.

---

## 9. Where things are

| What | Path |
|---|---|
| Features, scalers, tensorize | `ml/features/` |
| Predictor (GNN, MLP, baseline, training, masking, packaging, eval) | `ml/predictor/` |
| Detector (residuals, RTCA, SensorSetNet, selection, freeze/eval) | `ml/anomaly/` |
| Localiser (signatures, matcher, eval) | `ml/localisation/` |
| Serving (predictor `:8001`, detector + localiser `:8002`) | `ml/serve/` |
| SageMaker launcher + in-container tasks | `ml/sagemaker/` |
| Explainer (Bedrock loop, tools, grounding, template, prompt) | `api/agent/` |
| Experiments / metrics | `data/experiments/<version>/`, `s3://<bucket>/experiments/` |
| Artifacts | `s3://<bucket>/models/{predictor,anomaly,localisation}/<version>/` |

**Reproduce (local):** `make setup && make setup-ml`, `make datagen-local`, `make features`, `make train-local ARCH=gnn`, `python -m ml.anomaly.select …`, `python -m ml.anomaly.sensorset freeze|evaluate …`, `python -m ml.localisation.signatures …`, `python -m ml.localisation.evaluate …`. Tests: `pytest ml/tests api/tests -m 'not bedrock'` (90 passed).

## 10. Honest limits
- Synthetic data from one small network (8 nodes); not a real city, no real telemetry.
- Five sensors: bursts are caught 4 in 5 times, about half of large leaks and a third of medium leaks; small leaks go unseen.
- Localisation names a probable area and ranked pipes, not an exact position; it is weaker at never-trained locations with the ds3 pair.
- Sensor faults, valve/pump faults (ds2) and a fault-type classifier are out of scope (T3).
