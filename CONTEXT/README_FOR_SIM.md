# AquaAgent — Interactive Physics Simulation Frontend

A minimalist, visually understandable 2D hydraulic digital twin designed for hackathon evaluation in **5 seconds**.

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────┐
│             Interactive Frontend (React + SVG)          │
│   • Native SVG P&ID Network Illustration               │
│   • Dynamic animated stroke-dasharray water flow       │
│   • Sparse sensor beacons (S1, S2, S3)                 │
│   • Contextual inspectors for Taps, Pipes, Nodes       │
└───────────────────────────┬────────────────────────────┘
                            │ REST API (JSON)
                            ▼
┌────────────────────────────────────────────────────────┐
│             FastAPI Simulation Server (Python)          │
│   • /api/network/state                                 │
│   • /api/tap, /api/pipe/fault, /api/valve              │
│   • /api/scenario, /api/ai/test, /api/reset            │
└───────────────────────────┬────────────────────────────┘
                            │ Python API
                            ▼
┌────────────────────────────────────────────────────────┐
│         WNTR (Water Network Tool for Resilience)        │
│   • Pressure-Dependent Demand (PDD) formulation        │
│   • Hazen-Williams head loss calculation               │
│   • Real orifice leak & burst hydraulics               │
│   • EPANET 2.2-compatible solver                       │
└────────────────────────────────────────────────────────┘
```

> **Physics Principle**: The frontend **NEVER** fakes or interpolates hydraulic values. Every pressure, flow rate, velocity, and tank elevation is computed directly by WNTR solving the hydraulic governing conservation equations.

---

## 2. Baseline Network Specifications

Built according to the official **EPA 2.2 Tutorial Benchmark Network**:

| Node | Type | Elevation | Base Demand | Role / Label |
|---|---|---|---|---|
| **1** | Reservoir | 213.4 m (700 ft) | 0 gpm | Municipal Deep Aquifer Water Source |
| **2** | Junction | 213.4 m (700 ft) | 0 gpm | Pump Discharge Header [**Sensor S1**] |
| **3** | Junction | 216.4 m (710 ft) | 9.46 L/s | Commercial District [**Tap 1**] |
| **4** | Junction | 213.4 m (700 ft) | 9.46 L/s | West Residential District [**Sensor S2**, **Tap 2**] |
| **5** | Junction | 198.1 m (650 ft) | 12.62 L/s | Valley Consumer Node |
| **6** | Junction | 213.4 m (700 ft) | 9.46 L/s | East Residential District [**Sensor S3**, **Tap 3**] |
| **7** | Junction | 213.4 m (700 ft) | 0 gpm | Upper Loop Return Tie Point |
| **8** | Tank | 253.0 m (830 ft) | 0 gpm | Elevated Balancing & Storage Tank (20 ft capacity) |
| **Link 9** | Pump | — | 37.8 L/s @ 45.7m | Main High-Lift Booster Pump |
| **Pipe 7** | Valve | — | — | Loop Isolation Control Valve V1 |

---

## 3. Four Core User Actions

1. **ACTION 1: TAP (Click Tap 1, Tap 2, or Tap 3)**
   - Open small contextual panel: `[ OPEN ]` / `[ CLOSE ]`.
   - Displays real-time demand in `L/min`.
   - Modifies demand in WNTR; network pressure and flow recalculate immediately.

2. **ACTION 2: PIPE (Click any pipe)**
   - Open small contextual panel:
     - `[ Leak ]`: Moderate physical orifice leak.
     - `[ Burst ]`: Catastrophic pipe rupture.
     - `[ Close ]`: Isolate section.
     - `[ Reset ]`: Restore normal pipe condition.

3. **ACTION 3: SPEED (Simulation Velocity)**
   - `1×`, `5×`, `20×` options controlling timeline progression speed and SVG particle dash velocity.

4. **ACTION 4: TEST THE AI (Hackathon Challenge Mode)**
   - Secretly introduces a real physical hydraulic disturbance on an unobserved branch.
   - Lets the disturbance propagate naturally through the network.
   - Sparse sensors (`S1`, `S2`, `S3`) observe pressure drops and flow shifts.
   - AquaAgent synthesizes the **Explainable AI Diagnosis**:
     > *"Pressure at Sensor 2 fell 18.2% while observed demand remained within normal range. The predicted hydraulic state diverges from the observed state, making a leak in Branch 4 the most likely explanation."*

---

## 4. How to Run Locally

### Start Backend (FastAPI + WNTR)
```bash
# In project root
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start Frontend (React + Vite)
```bash
# In frontend directory
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` in your browser.
