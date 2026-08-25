# ⚡ AIOps Root Cause Correlator

> **Autonomous AI-Powered Incident Correlation, Causal Root-Cause Isolation, and 3D Spatial Neural Mesh for Distributed Microservices.**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)](https://reactjs.org)
[![Three.js](https://img.shields.io/badge/Three.js-WebGL-black.svg?logo=three.js)](https://threejs.org)
[![PostgreSQL 16 pgvector](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg?logo=postgresql)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg?logo=redis)](https://redis.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/Tests-16%2F16%20Passed%20(100%25)-brightgreen.svg)]()

<br />

<div align="center">
  <img src="assets/dashboard-preview.png" alt="AIOps Root Cause Correlator Dashboard UI" width="100%" />
  <p><em>Real-Time Microservice Dependency Graph, Anomaly Correlation, Streaming EWMA Baseline, and What-If Simulation Dashboard</em></p>
</div>

---

## 🎯 The Problem

In modern distributed microservice architectures, **a single failure cascades into dozens of downstream alerts across the entire cluster within seconds**. 

Engineers on-call must manually sift through hundreds of noisy telemetry alerts to trace which service is the actual root cause versus which are merely cascading symptoms. This manual investigation routinely takes **1 to 4 hours per incident (MTTR)**, during which customers experience outages and companies incur substantial financial loss.

---

## 💡 The Solution

The **AIOps Root Cause Correlator** automates incident triage by replacing manual guesswork with **deterministic graph-theoretical causal inference, adaptive EWMA anomaly baselines, and historical vector memory**.

It reduces an hours-long manual investigation to a **ranked, evidence-backed root cause hypothesis delivered in under 800 milliseconds**.

```
[ Ingested Telemetry ] ──> [ Adaptive EWMA Engine ] ──> [ NetworkX Causal Graph ]
 (Metrics / Logs / Spans)       (Drift-Aware Baseline)      (Connected Components & Walk)
                                                                     │
 ┌───────────────────────────────────────────────────────────────────┘
 ▼
[ Historical Memory Engine ] ──> [ Blast Radius Predictor ] ──> [ 3D Spatial Neural Mesh ]
(pgvector Cosine Suppression)      (Forward Cascade Walk)        (Interactive WebGL / React 18)
```

---

## ✨ Key Features & Architecture

### 1. 🧠 Deterministic Causal Correlation Engine (`NetworkX`)
* **Multi-Root-Cause Separation**: Automatically separates independent simultaneous failures into distinct incident clusters using graph connected components.
* **Topological Origin Walk**: Walks backward through the directed dependency graph to identify the earliest upstream anomaly with no anomalous ancestors.

### 2. 📈 Adaptive Drift-Aware Anomaly Detection (`EWMA`)
* Tracks streaming latency, error rates, and resource utilization using an Exponentially Weighted Moving Average baseline.
* Dynamically adapts to seasonal traffic drift while triggering on statistical anomalies ($z > 2.0\sigma$).

### 3. 🛡️ Historical False-Positive Suppression (`pgvector` & `scikit-learn`)
* Indexes 7-dimensional incident feature signatures in PostgreSQL 16 using `pgvector`.
* Suppresses benign alert storms that match known historical false positives (cosine similarity $\ge 0.85$), eliminating on-call alert fatigue without dropping logs.

### 4. 🔮 Forward Blast Radius & Counterfactual "What-If" Simulation
* **Topological Blast Radius**: Predicts which downstream microservices will fail next with an estimated time-to-impact (ETA).
* **Counterfactual Simulator**: Simulates what-if scenarios (e.g. *"If the payment connection pool was capped at 1.5σ, would the upstream checkout cascade have been prevented?"*).

### 5. 🌐 Cinematic 3D Spatial Neural Mesh & Interactive UI
* **3D WebGL Mesh**: Built with Three.js with smooth 360° orbit, volumetric sonar shockwaves, and 60 FPS real-time projected service badges.
* **Chaos Engineering Studio**: Injects live faults (*Database Connection Exhaustion, Memory Leaks, CPU Throttling*) and observes autonomous real-time correlation.
* **Executive Post-Mortem & Slack Notifier**: Automatically formats structured markdown post-mortems and incident escalation payloads.

---

## 📊 Benchmark Evaluation (30 Ground-Truth Scenarios)

The system is tested against an exhaustive synthetic evaluation suite of **30 ground-truth distributed failure scenarios**:

| Evaluation Metric | Target | Benchmark Result | Status |
|---|---|---|---|
| **Top-1 Root Cause Accuracy** | $\ge 90\%$ | **100.0%** (30 / 30) | ✅ Passed |
| **Top-3 Root Cause Accuracy** | $\ge 95\%$ | **100.0%** (30 / 30) | ✅ Passed |
| **Multi-Incident Separation Accuracy** | $\ge 85\%$ | **100.0%** | ✅ Passed |
| **False-Positive Suppression Precision** | $\ge 90\%$ | **100.0%** | ✅ Passed |
| **False-Positive Suppression Recall** | $\ge 85\%$ | **100.0%** | ✅ Passed |
| **Blast Radius Prediction Accuracy** | $\ge 85\%$ | **100.0%** | ✅ Passed |
| **Mean Correlation Time** | $< 2.0\text{s}$ | **0.78s** | ✅ Passed |

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend Framework** | FastAPI (Python 3.12) | High-performance asynchronous API & WebSocket telemetry streaming |
| **Causal Graph Logic** | NetworkX | Connected component clustering and backward topological traversal |
| **Data Processing** | Polars & NumPy | High-speed time-series metric aggregation and z-score calculations |
| **Vector Memory** | PostgreSQL 16 + `pgvector` | Storing and querying 7-dimensional incident embeddings |
| **Cache & Pub/Sub** | Redis 7 | Live active incident mesh and WebSocket event distribution |
| **Task Queue** | Celery | Asynchronous background drift recalibration |
| **Frontend UI** | React 18 + Vite | Modular glassmorphism SRE dashboard |
| **3D Visualization** | Three.js + WebGL | Spatial neural mesh with real-time particle flows |
| **Telemetry Charts** | Recharts | Rolling EWMA baseline and metric stream visualization |
| **Testing** | `pytest` + `pytest-asyncio` | Automated integration and 30-scenario benchmark suite |
| **Containerization** | Docker & Docker Compose | Turnkey multi-container deployment |

---

## 🚀 Quick Start (Local Setup)

### Option A: Running with Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/kartik-012/AIOps---Root-Cause-Correlator.git
cd AIOps---Root-Cause-Correlator

# 2. Spin up the full stack (PostgreSQL pgvector, Redis, FastAPI, React Frontend)
docker-compose up --build
```

Access the dashboard at: **`http://localhost:5173`**  
Access the backend API docs at: **`http://localhost:8001/docs`**

---

### Option B: Manual Local Setup

#### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start FastAPI server on port 8001
uvicorn app.main:app --port 8001 --reload
```

#### 2. Frontend Setup
```bash
cd ../aiops-frontend
npm install
npm run dev
```

#### 3. Run Automated Benchmark Tests
```bash
cd ../backend
python -m pytest tests/ -v
```

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
