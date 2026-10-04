# 📘 Project Master Guide — AIOps Root Cause Correlator

> **The Definitive End-to-End Master Manual for Operating, Developing, Deploying, and Defending the AIOps Platform.**

---

## 1. Production Ecosystem & Live Deployments

| Resource | URL | Hosting Provider | Purpose |
| :--- | :--- | :---: | :--- |
| **Production UI Console** | [https://ai-ops-root-cause-correlator.vercel.app](https://ai-ops-root-cause-correlator.vercel.app) | **Vercel** | Real-time SRE command center, 3D WebGL mesh & EWMA chart |
| **Production API Backend** | [https://aiops-root-cause-correlator.onrender.com](https://aiops-root-cause-correlator.onrender.com) | **Render** | FastAPI core, NetworkX engine, Kafka publisher |
| **Interactive OpenAPI Docs**| [https://aiops-root-cause-correlator.onrender.com/docs](https://aiops-root-cause-correlator.onrender.com/docs) | **Render** | Swagger UI testing all endpoints |
| **GraphQL Control Plane** | [https://aiops-root-cause-correlator.onrender.com/graphql](https://aiops-root-cause-correlator.onrender.com/graphql) | **Render** | Strawberry GraphQL IDE querying unified incident graphs |
| **GitHub Source Repository**| [https://github.com/kartik-012/AIOps---Root-Cause-Correlator](https://github.com/kartik-012/AIOps---Root-Cause-Correlator) | **GitHub** | CI/CD pipeline, automated test suites, Docker configs |

---

## 2. Visual System Walkthrough

### 2.1 Mission Control Dashboard
![Operations Dashboard](docs/images/01_operations_dashboard.png)

### 2.2 3D Spatial Neural Mesh
![3D Spatial Neural Topology](docs/images/02_3d_spatial_mesh.png)

### 2.3 Executive RCA Post-Mortem Generator
![Executive RCA Report](docs/images/03_executive_rca_report.png)

### 2.4 Multi-Channel Webhook Alerts
![Slack Integration](docs/images/04_slack_webhook_alerts.png)

### 2.5 gRPC Diagnostic Mesh & Kafka Event Bus
![gRPC Diagnostic Mesh](docs/images/05_grpc_diagnostic_mesh.png)
![Kafka Event Bus](docs/images/06_kafka_event_bus.png)

### 2.6 GraphQL Control Plane
![GraphQL Control Plane](docs/images/07_graphql_control_plane.png)

### 2.7 30-Scenario Ground-Truth Benchmark
![Benchmark Evaluation](docs/images/08_benchmark_evaluation.png)

---

## 3. The 8-Stage Causal Inference Pipeline

1. **Kafka KRaft Ingestion (`service.telemetry`)**: Decoupled, high-throughput metric ingestion.
2. **Online EWMA Anomaly Detection**: Per-service/metric baselines flagging statistical outliers at $Z > 2.5\sigma$.
3. **Directed Topology Graph (DAG)**: NetworkX represents service-to-service call dependencies.
4. **Weakly Connected Components (WCC)**: Partitions independent concurrent failures into isolated incidents.
5. **Causal In-Degree Analysis**: Pinpoints the topological source (zero anomalous parent edges) with temporal precedence tiebreaking.
6. **gRPC Protocol Buffer Diagnostics (`:50051`)**: Direct RPC query verifying internal thread pool and memory states to adjust confidence score to 94%–96%.
7. **Cosine Signature Memory**: Suppresses repetitive benign batch patterns via 7-dimensional vector comparison.
8. **Automated Runbook & Post-Mortem**: Surfaces human-in-the-loop remediation and Markdown executive reports.

---

## 4. Benchmark Validation (30 Scenarios)

> Every metric is verified by automated pytest suites running in GitHub Actions CI.

```
                    BENCHMARK ACCURACY RESULTS
                    ══════════════════════════

  Top-1 Root Cause Accuracy        ████████████████████  100.0%  (30/30)
  Top-3 Root Cause Accuracy        ████████████████████  100.0%  (30/30)
  Multi-Incident Separation        ████████████████████  100.0%  (12/12)
  False-Positive Suppression       ████████████████████  100.0%  (8/8)
  Blast Radius Prediction          ████████████████████  100.0%  (8/8)
  Mean Correlation Time            ████████████████████  0.78s   (< 2s target)
```

- **Unit & Integration Tests**: **30 / 30 Passed (100% Green)**
- **Test execution command**: `pytest backend/tests/ -v`

---

## 5. Local Development & Deployment Guide

### Local Running

#### Terminal 1 — Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
# or: source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### Terminal 2 — Frontend
```bash
cd aiops-frontend
npm install
npm run dev
```

### Production Deployment Strategy
1. **Frontend (Vercel)**:
   - Configured via [`vercel.json`](file:///d:/project/AIOps%20Root%20Cause%20Correlator/aiops-frontend/vercel.json) for Single Page Application client-side routing.
   - Set environment variable: `VITE_API_URL=https://aiops-root-cause-correlator.onrender.com` (Plaintext / Config).
2. **Backend (Render)**:
   - Containerized with [`backend/Dockerfile`](file:///d:/project/AIOps%20Root%20Cause%20Correlator/backend/Dockerfile).
   - Dynamic port binding: `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]`.
   - Automatic redeployment triggered on push to `origin/main`.
