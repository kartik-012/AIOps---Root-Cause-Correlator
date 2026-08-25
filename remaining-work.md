# 📘 remaining-work.md

**Outstanding implementation work — AIOps Root Cause Correlator**
Everything below is currently unbuilt. This document specifies exactly what "done" looks like for each item, so execution can be tracked against a concrete definition rather than a vague to-do.

---

## 1. Working FastAPI Project (Installable, Runnable)

**Current state:** Code exists only as snippets inside `04-core-engine-code.md`. There is no project you can clone and run.

**Definition of done:**
- A real `backend/` directory exists matching `01-repo-structure.md`, with `app/main.py` actually importing and mounting the routers from `api/v1/`
- `requirements.txt` is a real, pinned dependency list, not a conceptual one
- Running `pip install -r requirements.txt` followed by `uvicorn app.main:app --reload` starts a server with no errors
- Hitting `GET /docs` shows the live Swagger UI with every endpoint from `03-api-spec.md` actually registered, not just planned
- At minimum, `POST /detection/ingest` accepts a payload and returns a real response using the `DetectionEngine` class already written — this is the smallest possible slice that proves the whole chain (request → engine → response) works end to end

**Engineering note:** this is the single highest-leverage task on this entire list — everything else depends on this existing first.

---

## 2. PostgreSQL Actually Created, Migrations Run

**Current state:** Full schema written in `02-postgres-schema.md` as raw SQL. No database instance has executed it.

**Definition of done:**
- A local Postgres instance is running (via `docker-compose up postgres`, using the `docker-compose.yml` referenced in the repo structure)
- Alembic is initialized (`alembic init alembic`), and a first migration is generated from SQLAlchemy models that mirror the schema in `02-postgres-schema.md`
- `alembic upgrade head` runs cleanly and creates every table: `services`, `service_dependencies`, `metrics_raw`, `anomalies`, `incidents`, `incident_affected_services`, `suppressions`, `blast_radius_predictions`, `runbook_suggestions`
- The `pgvector` extension is confirmed installed and the `anomaly_signature` column on `incidents` accepts a vector insert without error
- A basic connectivity test (`SELECT 1`) is confirmed from the FastAPI app via SQLAlchemy session

---

## 3. Unit Tests Against the 30 Scenarios → Real Accuracy Numbers

**Current state:** The 30 scenarios are fully specified in `05-evaluation-scenarios.md` with documented ground truth. No test harness exists to run them.

**Definition of done:**
- `tests/fixtures/synthetic_scenarios/` contains 30 actual data files (JSON or Python fixtures), one per scenario, encoding the anomaly sequence and expected ground truth exactly as tabulated
- `tests/unit/test_correlation_engine.py` loads each fixture, runs it through `CorrelationEngine.correlate()`, and asserts the output root cause matches ground truth
- A test runner script (or the `/eval/run-scenarios` endpoint from `03-api-spec.md`) executes all 30 and prints a summary: top-1 accuracy, top-3 accuracy, multi-incident separation accuracy, suppression precision/recall, blast radius accuracy
- These numbers are recorded in the README as real, reproducible output — not an estimate

**Engineering note:** this task cannot be shortcut or approximated — the resume-worthy claim ("94% root-cause accuracy") does not exist as a legitimate statement until this exists and has actually been run.

---

## 4. React Frontend

**Current state:** Not started. Component names exist only in the repo structure document.

**Definition of done:**
- `frontend/` initialized via Vite (`npm create vite@latest`)
- `DependencyGraph.jsx` renders a live graph using `react-flow`, fed by `GET /services/graph`
- `IncidentTimeline.jsx` renders the timeline for a given incident from `GET /correlation/incidents/{id}`
- `useIncidentSocket.js` connects to `WS /ws/incidents` and updates the graph/timeline live as events stream in
- `RootCausePanel.jsx` and `EvidencePanel.jsx` display the result of `POST /explain/{incident_id}`
- The app runs locally via `npm run dev` and successfully displays a live incident end-to-end against the running backend

---

## 5. Actual Kubernetes Cluster + Services Deployed

**Current state:** Manifests are referenced in the repo structure but do not exist as files, and no cluster has been started.

**Definition of done:**
- Minikube or Kind cluster starts successfully (`minikube start`)
- Six to eight dummy services (simple FastAPI containers returning mock responses with configurable latency/error behavior) are containerized and pushed as local images
- `simulator/k8s-manifests/deployments/` and `.../services/` contain real Deployment and Service YAML for each of: `auth`, `product-catalog`, `inventory`, `payment`, `order`, `notification`, `shipping`, `api-gateway`
- `kubectl get pods` shows all services running and healthy
- Basic inter-service calls (e.g. `order` calling `payment`) succeed over the cluster's internal networking, confirming the dependency graph in `architecture.md` is real, not just diagrammed

---

## 6. Prometheus / Chaos Mesh Actually Installed and Running

**Current state:** Referenced conceptually in `features.md` Section 3. No installation has occurred.

**Definition of done:**
- `helm install prometheus prometheus-community/kube-prometheus-stack` completes successfully in the cluster
- Prometheus targets page confirms all 6–8 services are being scraped
- A test query in the Prometheus UI (or via API) returns real latency/CPU metrics from at least one running service
- Chaos Mesh installed via its Helm chart
- One real chaos experiment YAML (e.g. pod-kill on `payment-service`) is applied and confirmed to actually terminate the target pod
- The FastAPI backend's `/detection/ingest` endpoint receives real scraped metrics (via a small adapter script polling Prometheus) rather than only synthetic-generator input

---

## 7. Blast Radius / Counterfactual / Suppression Engines — Actual Code

**Current state:** `DetectionEngine`, `CorrelationEngine`, and `SuppressionEngine` have real working code in `04-core-engine-code.md`. `PredictionEngine` (blast radius), `CounterfactualEngine`, `ImpactEngine`, and the runbook-matching logic have no code written yet — only described in prose in `phases.doc.md` and `features.md`.

**Definition of done:**
- `app/engines/prediction_engine.py` implements the forward graph walk with anomaly-spread velocity scoring described in `features.md` Section 1.3, returning ranked predictions with ETA and confidence
- `app/engines/counterfactual_engine.py` implements the re-simulation logic described in Section 1.4 — takes an incident + modified parameter, re-runs correlation on the adjusted trace, returns whether the cascade would still occur
- `app/engines/impact_engine.py` implements the severity × revenue-weight × downstream-dependent-count formula from Section 2.3
- Runbook matching logic (root-cause-type → `runbooks/runbook_library.json` lookup) is implemented as a small utility function, wired into the `/runbook/{root_cause_type}` endpoint
- Each of these has at least one unit test proving it produces the expected output on a known input

---

## 8. The Actual Three.js Interactive Site (`index.html`)

**Current state:** `06-threejs-site-build-guide.md` specifies the approach, file structure, and code patterns. No `frontend/showcase/index.html` file exists.

**Definition of done:**
- Following the build order specified in the guide (hero → scroll skeleton → telemetry → correlation graph → AI reasoning reveal), sections 1 through 5 exist as real, working code and render correctly in a browser
- The signature gold root-cause reveal moment (Section 3.5 of the build guide) is implemented and visually distinct from every other moment in the experience
- `prefers-reduced-motion` fallback is implemented and tested, not just planned
- The site loads and runs at an acceptable frame rate on a mid-range laptop — this should be manually verified, not assumed

---

## 9. Deployment (Render / Vercel / Live Links)

**Current state:** Configured for one-command Docker Compose & local deployment.

**Definition of done:**
- FastAPI backend deployed to Render or Railway, with environment variables (DB connection string, LLM API key) configured as secrets, not hardcoded
- React frontend deployed to Vercel, pointed at the deployed backend's live URL
- A live link exists that a recruiter or engineer can open and interact with directly.

---

## Build Order (do not attempt these in parallel)

```
1 → 2 → 3   (backend + DB + real evaluation numbers — this alone is a legitimate resume line)
      ↓
7           (remaining engines, once the core pipeline is proven)
      ↓
5 → 6       (K8s + Prometheus + Chaos Mesh — the production-realism layer)
      ↓
4           (frontend, once there's a real backend to point it at)
      ↓
10          (deploy backend + frontend)
      ↓
8           (3D showcase site — nice-to-have, does not block anything else)
      ↓
9           (video — recorded last, once everything above is real)
```

**Direct engineering note:** items 1–3 alone, fully working, are worth more on a resume than items 4–10 left undone. If time runs short before placement season, stop after item 3 and be able to say honestly: "backend live, database live, evaluated against 30 ground-truth scenarios, here are the real numbers." That sentence is already stronger than most student portfolios in this space.
