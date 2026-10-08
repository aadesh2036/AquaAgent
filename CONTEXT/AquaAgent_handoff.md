# AquaAgent --- Complete Build Handoff

> **Purpose:** Single handoff context for a fresh build-planning chat.
> It captures the decisions, architecture, scientific grounding, ML
> plan, AWS direction, UX direction, and implementation priorities
> agreed for AquaAgent.
>
> **Current status:** Architecture and theoretical design are
> substantially planned. The project is now moving into the actual
> build.

## 0. PROJECT IDENTITY

**Project:** AquaAgent\
**Tagline:** **Find the Water Nobody Can See.**

AquaAgent is a physics-grounded AI system for detecting and localising
hidden anomalies in municipal water-distribution networks from sparse
hydraulic observations.

Core thesis:

> **Physics generates reality. ML reconstructs the hidden state. Anomaly
> detection finds what does not fit. An agent explains the evidence and
> recommends action.**

The simulation is **not the final product**. It is a controlled
laboratory for generating physically consistent training/evaluation data
across many network configurations and operating conditions.

------------------------------------------------------------------------

## 1. THE PROBLEM

Municipal water networks are spatially distributed hydraulic systems.
Underground leakage can be difficult to observe directly because
utilities generally have incomplete sensing and cannot continuously
observe every pipe and junction.

AquaAgent focuses on:

> **Can a model reconstruct the hidden hydraulic state of a water
> network when only a small subset of nodes are observed, and can
> deviations from that reconstructed state be used to detect and
> localise anomalies?**

Do not claim that leakage is the only cause of urban water loss, that
AI-based leak detection itself is novel, or that AquaAgent solves an
entire city's water crisis. The research direction is the combination of
physics-grounded synthetic generation, sparse sensing,
graph/topology-aware state reconstruction, anomaly detection,
localisation, pressure-control experiments, and an agentic engineering
interface.

------------------------------------------------------------------------

## 2. SYSTEM VISION

``` text
Real Water Network
      │
      ▼
Pressure / Flow / Other Sensors
      │
      ▼
AWS IoT / telemetry ingestion
      │
      ▼
Sparse observations
      │
      ▼
Graph-based hydraulic state reconstruction
      │
      ▼
Expected hidden network state
      │
      ▼
Observed vs predicted residuals
      │
      ▼
Anomaly detection
      │
      ▼
Probable location / zone
      │
      ▼
AquaAgent
      ├── Explain
      ├── Diagnose
      ├── Simulate interventions
      └── Recommend actions
```

Prototype substitution:

``` text
EPANET/WNTR
      │
      ▼
Synthetic hydraulic network
      │
      ▼
Ground-truth states
      │
      ▼
Virtual sparse sensors
      │
      ▼
ML pipeline
```

------------------------------------------------------------------------

## 3. MOST IMPORTANT ARCHITECTURAL PRINCIPLE

### Simulation is a data-generation and experimentation environment

Do **not** build the project around continuously running a giant EPANET
simulation for every real sensor reading.

### During research/training

``` text
Many network configurations
        ↓
EPANET/WNTR
        ↓
Normal + abnormal scenarios
        ↓
Ground truth
        ↓
Training / validation / test datasets
        ↓
ML models
```

### During eventual deployment

``` text
Real network telemetry
        ↓
Sparse sensor observations
        ↓
Trained ML models
        ↓
Anomaly detection
        ↓
AquaAgent
```

The simulator remains useful for retraining, scenario testing,
counterfactual simulation, intervention evaluation, digital-twin
experiments, and generating additional labelled data.

------------------------------------------------------------------------

# 4. PHASE 1 --- PHYSICS SIMULATION

## Recommended engine

**EPANET + WNTR**

EPANET is the hydraulic simulation foundation. WNTR is the Python
modelling/control layer around it, providing network manipulation, leak
modelling, pressure-dependent demand, disruptions, scenario generation,
and extraction of hydraulic states.

## Initial network

Start small:

-   1 reservoir
-   5--6 junctions
-   1 tank
-   approximately 8 pipes
-   pump if required by the chosen baseline
-   several demand nodes
-   at least one loop

A strong baseline is the small network from the official EPANET
tutorial. Do not start with a Pune-scale network.

------------------------------------------------------------------------

# 5. PHYSICS THAT MUST BE REAL

The frontend must **never manually fake hydraulic responses**.

Bad:

``` python
pressure -= 20
```

Good:

``` text
User changes network
      ↓
WNTR/EPANET
      ↓
Hydraulic solution
      ↓
pressure / head / flow / demand
      ↓
frontend
```

The UI visualises the hydraulic solution; it does not invent it.

## Core equations to understand

### Continuity

At a junction:

\[ `\sum `{=tex}Q\_{in} - `\sum `{=tex}Q\_{out} = D \]

### Energy / head loss

\[ H_i-H_j=h_L \]

Head loss depends on flow, length, diameter, roughness and hydraulic
resistance. EPANET supports established formulations including
Hazen-Williams, Darcy-Weisbach, and Chezy-Manning depending on
configuration.

### Pressure/head relationship

\[ h_p=H-z \]

and, conceptually,

\[ P=`\rho `{=tex}g h_p \]

### Leak discharge

A pressure-dependent leak can be represented conceptually by:

\[ Q_L=C_dA`\sqrt{2gh}`{=tex} \]

The implementation should follow WNTR/EPANET's supported formulation
rather than manually modifying final pressure values.

------------------------------------------------------------------------

# 6. SIMULATION OUTPUTS

For every timestep/scenario retain the full hydraulic ground truth.

## Node-level

``` text
node_id
node_type
elevation
base_demand
actual_demand
pressure
head
observed_mask
sensor_id if observed
```

Potentially:

``` text
pressure_change
head_change
demand_multiplier
fault association
```

## Edge/pipe-level

``` text
pipe_id
start_node
end_node
length
diameter
roughness
status
flow
velocity
headloss
```

Potentially:

``` text
flow_direction
absolute_flow
flow_change
pipe_anomaly_state
leak_magnitude
```

## Tank-level

``` text
tank_id
level
volume
head
inflow
outflow
```

## Simulation metadata

``` text
simulation_id
network_id
scenario_id
scenario_type
timestamp
random_seed
demand_profile_id
hydraulic_options
network_parameters
```

Reproducibility is mandatory.

------------------------------------------------------------------------

# 7. SCENARIO GENERATION

Do not train only on leaks. Otherwise the detector can learn "pressure
drop = leak".

## Normal

Vary:

-   baseline demand
-   time-of-day demand
-   spatial demand distribution
-   tank level
-   reservoir head
-   pump condition
-   normal valve states

## Abnormal

Include:

-   small/medium/large leakage
-   burst
-   partial valve closure
-   complete valve closure
-   sudden demand increase/decrease/redistribution
-   pump abnormalities
-   low reservoir head
-   sensor missingness
-   sensor spikes
-   sensor bias
-   sensor drift
-   stuck sensors

The detector must distinguish hydraulic anomalies from sensor anomalies.

------------------------------------------------------------------------

# 8. TIME-DOMAIN SIMULATION

Use extended-period simulations rather than only independent steady
states.

Example:

``` text
24–72 hour simulation
↓
time-varying demand
↓
fault introduced at selected time
↓
hydraulic response propagates
```

Start simpler if necessary:

1.  steady-state scenarios
2.  short extended-period scenarios
3.  temporal anomaly experiments

------------------------------------------------------------------------

# 9. VIRTUAL SENSOR MODEL

The simulator knows everything. The ML model must not.

``` text
FULL GROUND TRUTH
       │
       ├── observed nodes → ML input
       │
       └── hidden nodes → prediction target
```

Example:

``` text
10 nodes

Sensor nodes:
N1 N4 N7

Hidden:
N2 N3 N5 N6 N8 N9 N10
```

Use an explicit observation mask:

``` text
pressure = [42.1, 0, 39.4, 41.7, 0, 0, 37.8]
mask     = [1,    0, 1,    1,    0, 0, 1]
```

Do not treat zero as "missing" without a mask.

------------------------------------------------------------------------

# 10. GRAPH DATA MODEL

Represent every network as a graph.

## Node features

Start with:

``` text
elevation
base_demand
current_demand
observed_pressure
pressure_mask
head_mask
node_type
sensor_mask
previous_pressure
demand_multiplier
```

Do not include future target values in the predictor input.

## Edge features

``` text
length
diameter
roughness
status
flow if legitimately available
direction if legitimately available
```

Avoid fields that directly reveal the answer at inference time.

------------------------------------------------------------------------

# 11. MODEL 1 --- HYDRAULIC STATE PREDICTOR

## Goal

Given network topology, node/edge attributes, sparse observations, and
optionally temporal history, predict pressure/head at unobserved nodes.

## Candidate progression

``` text
Simple interpolation / nearest baseline
        ↓
MLP baseline
        ↓
GCN / GraphSAGE
        ↓
GAT
        ↓
Heterogeneous GNN
        ↓
Residual / physics-informed variant
```

Do not jump directly to the most complicated architecture.

## Input

``` text
Graph G=(V,E)

Node:
elevation
demand
observed pressure
sensor mask
node type
temporal features

Edge:
length
diameter
roughness
status
```

## Output

Start with:

``` text
predicted_pressure[node]
```

for hidden nodes. Add head and uncertainty later if useful.

## Ground truth

``` text
y_true = EPANET/WNTR pressure
```

## Loss

Start with MAE/MSE:

\[ MAE=`\frac{1}{N}`{=tex}`\sum`{=tex}\_i\|y_i-`\hat `{=tex}y_i\| \]

\[ MSE=`\frac{1}{N}`{=tex}`\sum`{=tex}\_i(y_i-`\hat `{=tex}y_i)\^2 \]

Potential later objective:

\[
L=L\_{pressure}+`\lambda `{=tex}L\_{smooth}+`\beta `{=tex}L\_{physics}
\]

Only add physics-informed terms after the baseline works.

------------------------------------------------------------------------

# 12. PREDICTOR EVALUATION

Use:

-   MAE
-   RMSE
-   R²
-   relative error
-   error by graph distance

Especially report:

``` text
1 hop from sensor → MAE
2 hops            → MAE
3 hops            → MAE
4 hops            → MAE
```

Research question:

> **How far can hydraulic state be reconstructed from sparse
> observations before prediction error becomes unacceptable?**

------------------------------------------------------------------------

# 13. MODEL 2 --- ANOMALY DETECTOR

The predictor produces (`\hat `{=tex}P_i). Observed telemetry provides
(P_i).

Residual:

\[ r_i=P_i-`\hat `{=tex}P_i \]

Normalised residual:

\[ z_i=`\frac{P_i-\hat P_i}{\sigma_i+\epsilon}`{=tex} \]

The anomaly detector learns normal residual behaviour and identifies
abnormal patterns.

## Inputs

``` text
pressure residual
absolute residual
residual trend
flow residual if available
temporal features
node embedding
graph location
sensor health
prediction uncertainty
```

## Outputs

Minimum:

``` text
normal / anomaly
anomaly_score
```

Later:

``` text
fault class
probable zone
probable pipe
confidence
```

------------------------------------------------------------------------

# 14. LOCALISATION

Build in stages:

### Stage 1

Normal vs anomaly.

### Stage 2

Anomalous zone.

### Stage 3

Rank candidate pipes/nodes.

Example:

``` text
Pipe 4  0.91
Pipe 5  0.67
Pipe 8  0.21
Pipe 2  0.14
```

Ranking is preferable to prematurely forcing exact-pipe classification.

## Metrics

Detection:

-   precision
-   recall
-   F1
-   ROC-AUC
-   PR-AUC

Localisation:

-   top-1 accuracy
-   top-k accuracy
-   distance to true fault
-   zone accuracy
-   mean localisation error
-   false-alarm rate

------------------------------------------------------------------------

# 15. CRITICAL DATA-SPLIT RULE

Never randomly split correlated timesteps from the same simulation
across train/test.

Use complete simulation/scenario splits:

``` text
70% train
15% validation
15% test
```

Create harder tests:

-   unseen fault locations
-   unseen network configurations
-   different demand profiles
-   different pipe parameters
-   different sensor placement
-   OOD topology

The target claim is generalisation, not memorisation of one topology.

------------------------------------------------------------------------

# 16. SENSOR EXPERIMENTS

Test:

``` text
1 sensor
2 sensors
3 sensors
5 sensors
10 sensors
```

and placement strategies:

-   random
-   high-degree
-   upstream/downstream
-   centrality-based
-   pressure-sensitive
-   optimisation-based

Measure:

``` text
sensor count
vs
prediction error
vs
anomaly detection
vs
localisation
```

This may become one of the strongest research experiments.

------------------------------------------------------------------------

# 17. SENSOR NOISE

Introduce progressively:

-   Gaussian noise
-   missing readings
-   spikes
-   bias
-   drift
-   stuck sensors

Measure model degradation and false alarms.

------------------------------------------------------------------------

# 18. RL --- PRESSURE OPTIMISATION

RL is a later stage. It is **not** the primary leak detector.

Question:

> **What control action should be taken after an anomaly is detected?**

Environment:

``` text
WNTR
```

State:

``` text
pressure
flow
tank level
demand
suspected anomaly
valve states
pump states
```

Actions:

``` text
adjust pressure
change pump setting
open/close valve
isolate branch
```

Reward should balance:

``` text
water loss reduction
+ service reliability
- energy cost
- pressure violations
- customer impact
- unnecessary interventions
```

Build a non-RL optimisation/controller baseline first, then compare RL
against it.

------------------------------------------------------------------------

# 19. AGENTIC AI --- AQUAAGENT

The LLM is **not** the hydraulic solver.

It consumes structured outputs from the scientific/ML layer.

Possible tools:

``` text
get_network_state()
get_sensor_readings()
get_predictions()
get_anomaly_score()
get_candidate_locations()
run_simulation()
run_intervention()
get_historical_events()
```

Example workflow:

``` text
User: Why is Zone 3 suspicious?
        ↓
get_sensor_readings()
        ↓
get_predictions()
        ↓
get residuals / anomaly score
        ↓
get candidate locations
        ↓
explain evidence
```

The agent must never invent pressure, flow, confidence, or hydraulic
results.

------------------------------------------------------------------------

# 20. AWS ARCHITECTURE

AWS is the infrastructure surrounding the scientific pipeline, not the
physics engine.

## S3

Store:

-   raw synthetic datasets
-   processed datasets
-   model artifacts
-   experiment outputs
-   simulation configs
-   evaluation results

Suggested layout:

``` text
s3://aquaagent/
    raw/
    processed/
    experiments/
    models/
    configs/
```

## SageMaker AI

Use for:

-   predictor training
-   anomaly-detector training
-   managed inference
-   model deployment
-   experiment/model lifecycle where useful

Develop locally first; move stable training pipelines to AWS.

## EC2 or ECS/Fargate

EC2 is acceptable for the prototype if simplicity/control are
priorities.

For production-style container deployment:

``` text
ECS Fargate
    ↓
FastAPI
    ↓
WNTR / EPANET
```

## Bedrock / AgentCore

Use for the agentic layer:

``` text
ML outputs
    ↓
AquaAgent
    ↓
explanation
recommendation
counterfactual simulation request
```

## AWS IoT Core --- future

``` text
real sensors
    ↓
AWS IoT Core
    ↓
telemetry pipeline
    ↓
ML inference
```

Do not build physical IoT hardware solely for the first prototype.

## Step Functions --- optional

Potential workflow:

``` text
telemetry
 ↓
validation
 ↓
prediction
 ↓
anomaly detection
 ↓
localisation
 ↓
intervention simulation
 ↓
agent explanation
```

------------------------------------------------------------------------

# 21. MLOPS FUTURE

Long-term lifecycle:

``` text
New telemetry
     ↓
Data validation
     ↓
Data drift monitoring
     ↓
Model performance monitoring
     ↓
Retraining trigger
     ↓
SageMaker training
     ↓
Validation
     ↓
Model registry
     ↓
Deployment
     ↓
Monitoring
```

Unless actually implemented, describe this as future scope rather than
claiming it exists.

------------------------------------------------------------------------

# 22. FRONTEND / PROTOTYPE UX

The simulation should feel like an **interactive miniature water
network**, not a generic SCADA dashboard.

Visual direction:

-   light/white background
-   blue water
-   dark engineering lines
-   restrained accents
-   whitespace
-   network as hero
-   subtle technical/engineering language

The separate blog/marketing visual can use a **blueprint theme**:

-   sky-blue blueprint background
-   engineering grid
-   drafting lines and dimensions
-   geometric constructed AquaAgent lettering
-   schematic network diagrams
-   technical labels

The actual simulation UI should remain lighter and cleaner.

------------------------------------------------------------------------

# 23. SIMULATION INTERACTIONS

Only expose a few meaningful controls:

1.  Open/close tap
2.  Click pipe → Normal / Leak / Burst / Close
3.  Simulation speed → 1x / 5x / 20x
4.  **TEST THE AI** → hidden-anomaly challenge

------------------------------------------------------------------------

# 24. THREE SIMULATION MODES

## Explore

Open/close taps and observe hydraulic changes.

## Break It

Introduce:

-   leak
-   burst
-   valve closure
-   demand spike

## Test AquaAgent

The system secretly introduces a real hydraulic disturbance. The user
watches the response and then receives anomaly
detection/localisation/explanation.

------------------------------------------------------------------------

# 25. FRONTEND VISUALISATION

Use:

-   React
-   TypeScript
-   native SVG
-   CSS animations

Optional:

-   Framer Motion for UI transitions

Avoid:

-   Three.js
-   CFD rendering
-   complex 3D
-   generic chart dashboards
-   unnecessary graph editors

## Flow animation

``` text
flow magnitude → animation speed
flow direction → animation direction
zero flow → stop
```

This is a visual representation of hydraulic state, not particle-level
fluid physics.

## Tank

Use an SVG container with a clipped blue water region. Level should
follow simulation output. Optional subtle wave animation; no CFD.

## Leak

Small leak → a few drops.\
Large leak → stream.\
Burst → strong spray.

Visual intensity should be driven by scenario/simulation state.

------------------------------------------------------------------------

# 26. MAIN UI STATE

Example bottom status bar:

``` text
Pressure 38.4 m | Flow 24.8 L/s | Tank 72% | Network NORMAL
```

Selected node inspector:

``` text
Node J4
Pressure: 41.2 m
Demand: 150 gpm
Head: ...
Sensor: YES
```

Do not cover the network with cards.

------------------------------------------------------------------------

# 27. API CONTRACT

Frontend receives normalised state:

``` json
{
  "time": 12.5,
  "nodes": {
    "J1": {
      "pressure": 38.4,
      "head": 120.3,
      "demand": 10.2,
      "observed": true
    }
  },
  "pipes": {
    "P1": {
      "flow": 24.8,
      "status": "OPEN"
    }
  },
  "tank": {
    "level": 72
  }
}
```

Keep API representation independent of the exact visualisation.

------------------------------------------------------------------------

# 28. REPOSITORY STRUCTURE

Suggested:

``` text
frontend/
  src/
    components/
      NetworkCanvas/
      Tank/
      Pipe/
      Junction/
      Pump/
      Valve/
      Tap/
      Sensor/
      LeakAnimation/
      FlowAnimation/
      NodeInspector/
      StatusBar/
      SimulationControls/
      EventToast/
    pages/
      SimulationPage/
    api/
      simulation.ts
    types/
      hydraulic.ts
    state/
      simulationStore.ts

backend/
  app/
    main.py
    api/
      simulation.py
      scenarios.py
    simulation/
      network.py
      solver.py
      scenarios.py
      state.py
    data/
      exporters.py
      schemas.py
    ml/
      predictor.py
      anomaly.py
    config/

ml/
  data_generation/
  preprocessing/
  baselines/
  predictor/
  anomaly/
  localisation/
  rl/
  evaluation/
  experiments/
```

Keep research/training code separate from production API code where
practical.

------------------------------------------------------------------------

# 29. BUILD ORDER

## Phase 0 --- Repository/environment

Set up Git, frontend, backend, Python environment, WNTR, EPANET, and
basic API.

**No ML yet.**

## Phase 1 --- Static network

Render reservoir/tank, junctions, pipes, labels.

Goal: visually correct network.

## Phase 2 --- Real hydraulic backend

``` text
FastAPI
  ↓
WNTR
  ↓
EPANET
  ↓
hydraulic state
```

## Phase 3 --- Live visualisation

Connect frontend. Animate flow, pressure indicators and tank level.

## Phase 4 --- User interactions

Implement taps, pipe context menu, valve closure, leak, burst, reset.
Every interaction modifies the hydraulic model and reruns the solver.

## Phase 5 --- Scenario generator

Generate thousands of simulations with configuration, ground truth,
metadata, topology and random seed.

## Phase 6 --- Data schema

Freeze schema before serious model training. Check target leakage,
reproducibility and split boundaries.

## Phase 7 --- Predictor baseline

Start with interpolation/nearest-neighbour and MLP, then
GCN/GraphSAGE/GAT.

## Phase 8 --- Predictor experiments

Sensor count, placement, graph distance, noise, unseen topology, unseen
faults.

## Phase 9 --- Anomaly detector

Residual-based detection across normal demand changes, sensor faults,
leaks, bursts, and valve events.

## Phase 10 --- Localisation

Rank zone/node/pipe and evaluate top-k/distance metrics.

## Phase 11 --- RL

WNTR environment → baseline controller → RL controller → comparison.

## Phase 12 --- AWS

Move stable pieces to S3, SageMaker, EC2/ECS and Bedrock/AgentCore.

## Phase 13 --- Agent

Expose scientific tools and test grounding/no hallucination/tool use.

## Phase 14 --- Final demo

Healthy network → interaction → hidden leak → sparse sensors →
reconstruction → anomaly → localisation → agent explanation → optional
intervention.

------------------------------------------------------------------------

# 30. DEMO STORY

Do not start with AWS.

### Scene 1 --- Healthy network

"This network has only a few pressure sensors."

### Scene 2 --- Interaction

Open a tap; pressure/flow change physically.

### Scene 3 --- Break it

Introduce a leak.

### Scene 4 --- Hide the fault

Run the AI challenge.

### Scene 5 --- Sparse observations

Only selected sensors are visible to ML.

### Scene 6 --- Reconstruction

Predict hidden state.

### Scene 7 --- Detection

Residual pattern indicates abnormal behaviour.

### Scene 8 --- Localisation

Rank likely region/pipe.

### Scene 9 --- Agent

Explain what changed, why it is suspicious, where it is likely
happening, and what action could be considered.

### Scene 10 --- Architecture

Only now reveal WNTR, S3, SageMaker and Bedrock/AgentCore.

------------------------------------------------------------------------

# 31. BLOG / RESEARCH STORY

Central question:

> **Can sparse observations reveal the hidden state of a water
> network?**

Suggested structure:

1.  Find the Water Nobody Can See
2.  Why underground leaks are difficult to locate
3.  The sparse-observation problem
4.  Starting with physics
5.  Turning simulations into a dataset
6.  Hiding most of the network
7.  Teaching a graph to reconstruct pressure
8.  Turning prediction error into anomaly detection
9.  Localising the problem
10. Exploring pressure control with RL
11. Moving the pipeline to AWS
12. What failed
13. What simulation cannot capture
14. From simulation to real sensors
15. What's next

Use the rhythm:

``` text
Problem
↓
Constraint
↓
Decision
↓
Why
↓
Result
↓
Lesson
```

------------------------------------------------------------------------

# 32. RESEARCH CLAIMS TO AVOID

Do not claim:

-   "We solve water leakage."
-   "AI can see every underground leak."
-   "Three sensors are enough for any network."
-   "Our simulator represents a real city."
-   "RL automatically optimises municipal water."
-   "Synthetic data proves real-world performance."
-   "AWS makes the model accurate."

Prefer:

-   "We investigate..."
-   "We evaluate..."
-   "In our simulated networks..."
-   "Under these assumptions..."
-   "The prototype demonstrates..."
-   "Future real-world deployment would require..."

------------------------------------------------------------------------

# 33. SCIENTIFIC VALIDITY CHECKLIST

-   [ ] Ground truth comes from the hydraulic simulator.
-   [ ] Input features do not reveal the target.
-   [ ] Simulation IDs are split correctly.
-   [ ] Test networks/scenarios are unseen.
-   [ ] Normal demand variation is included.
-   [ ] Sensor faults are included.
-   [ ] Leak sizes vary.
-   [ ] Fault locations vary.
-   [ ] Sensor placement is tested.
-   [ ] Noise is tested.
-   [ ] Graph distance is evaluated.
-   [ ] Baselines exist.
-   [ ] False-positive behaviour is measured.
-   [ ] OOD generalisation is measured.
-   [ ] Results are reproducible from seeds/configs.

------------------------------------------------------------------------

# 34. ENGINEERING VALIDITY CHECKLIST

-   [ ] Frontend never manually changes pressure.
-   [ ] Backend is source of hydraulic state.
-   [ ] Simulation can be reset.
-   [ ] Scenario parameters are reproducible.
-   [ ] API has a stable schema.
-   [ ] Simulation and UI time are synchronised.
-   [ ] Flow direction is visually correct.
-   [ ] Leak animation corresponds to scenario.
-   [ ] No unnecessary 3D/CFD complexity.
-   [ ] ML code is separate from simulation code.
-   [ ] Cloud deployment can be reproduced.

------------------------------------------------------------------------

# 35. AWS VALIDITY CHECKLIST

-   [ ] S3 stores versioned datasets.
-   [ ] Training jobs are reproducible.
-   [ ] Model artifacts are versioned.
-   [ ] Inference interface is stable.
-   [ ] Secrets are not committed.
-   [ ] IAM follows least privilege.
-   [ ] Cloud resources are documented.
-   [ ] Costs are monitored.
-   [ ] Agent tools return structured scientific results.
-   [ ] LLM cannot invent hydraulic values.
-   [ ] MLOps is labelled future/next-stage unless implemented.

------------------------------------------------------------------------

# 36. PROJECT PRIORITY

If time is limited:

## Tier 1 --- MUST WORK

1.  Physics simulation
2.  Interactive network
3.  Real hydraulic response
4.  Synthetic data generator
5.  Predictor baseline
6.  Anomaly detector
7.  Working visual demo

## Tier 2 --- HIGH VALUE

8.  GNN predictor
9.  localisation
10. AWS S3
11. SageMaker deployment
12. Agent explanation

## Tier 3 --- ADVANCED

13. RL
14. Step Functions
15. IoT simulation
16. MLOps
17. unseen-topology research
18. uncertainty estimation

Never sacrifice Tier 1 to build Tier 3.

------------------------------------------------------------------------

# 37. NORTH-STAR TECHNICAL PIPELINE

``` text
                 PHYSICS
                    │
                    ▼
             EPANET / WNTR
                    │
                    ▼
          Synthetic Ground Truth
                    │
              ┌─────┴─────┐
              │            │
              ▼            ▼
        Full Network    Sparse Sensors
              │            │
              │            ▼
              │       GNN Predictor
              │            │
              │            ▼
              │     Hidden State Estimate
              │            │
              └──────┬─────┘
                     ▼
                 Residuals
                     │
                     ▼
             Anomaly Detector
                     │
                     ▼
               Localisation
                     │
                     ▼
              AquaAgent AI
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Explain    Simulate   Recommend
                     │
                     ▼
                    RL
              (future control)
```

------------------------------------------------------------------------

# 38. BUILD PHILOSOPHY

> **Do the simplest scientifically defensible version first.**

Do not begin with a huge dashboard, fancy GNN, autonomous agent,
complicated RL controller, or giant AWS architecture.

Start with:

``` text
One network
+
real hydraulic physics
+
one leak
+
a few sensors
+
one baseline predictor
+
one anomaly detector
```

Then expand.

The strongest AquaAgent is not the version with the most components. It
is the version where every component has a clear reason to exist.

------------------------------------------------------------------------

# 39. FIRST TASK IN THE NEW BUILD CHAT

When this handoff is pasted into a fresh chat, the new chat should
**not** immediately generate a huge amount of code.

First:

1.  Read this handoff completely.
2.  Restate the architecture in its own words.
3.  Identify contradictions or missing decisions.
4.  Freeze the Phase-1 technical scope.
5.  Propose the repository structure.
6.  Define the first minimal vertical slice.
7.  Specify exact environment/setup requirements.
8.  Begin implementation one stage at a time.

## First vertical slice

``` text
React frontend
        ↓
FastAPI
        ↓
WNTR / EPANET
        ↓
Small network
        ↓
Hydraulic state
        ↓
React SVG visualisation
```

**No ML. No AWS. No agent.**

Once this works reliably, everything else has a solid foundation.

------------------------------------------------------------------------

# 40. FOUNDATIONAL REFERENCES

## EPANET

U.S. EPA EPANET:\
https://github.com/USEPA/EPANET

EPANET 2.2 documentation:\
https://usepa.github.io/EPANET2.2/

EPANET tutorial:\
https://github.com/USEPA/EPANET/blob/main/tutorial/tutorial.md

EPANET 2.2 User Manual:\
https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10113EM.TXT

## WNTR

U.S. EPA WNTR:\
https://usepa.github.io/WNTR/

WNTR GitHub:\
https://github.com/USEPA/WNTR

WNTR graphics:\
https://usepa.github.io/WNTR/graphics.html

## Visualisation

epanet-js:\
https://github.com/epanet-js/epanet-js-toolkit

React Flow:\
https://reactflow.dev/

Konva React animations:\
https://konvajs.org/docs/react/Simple_Animations.html

SVG stroke-dashoffset:\
https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/stroke-dashoffset

## AWS

Amazon S3:\
https://aws.amazon.com/s3/

Amazon SageMaker:\
https://aws.amazon.com/sagemaker/

Amazon ECS:\
https://aws.amazon.com/ecs/

Amazon Bedrock:\
https://aws.amazon.com/bedrock/

Amazon Bedrock AgentCore:\
https://aws.amazon.com/bedrock/agentcore/

AWS IoT Core:\
https://aws.amazon.com/iot-core/

AWS Step Functions:\
https://aws.amazon.com/step-functions/

------------------------------------------------------------------------

# END OF HANDOFF

**Project:** AquaAgent\
**Tagline:** Find the Water Nobody Can See.\
**Core principle:** Physics generates reality. ML interprets sparse
observations. The agent explains evidence and supports decisions.
