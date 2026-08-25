# 📘 phases.doc.md

**Breakdown of the AIOps platform into incremental engineering phases**
**Project: AIOps Root Cause Correlator**

---

## PHASE 1: OBSERVABILITY & DATA INGESTION 🔵

- Log ingestion
- Metrics ingestion (via Prometheus scraping live Kubernetes pods)
- Distributed traces (OpenTelemetry + Jaeger)
- Alerts & events
- OpenTelemetry integration for auto-generated service dependency data
- Real-time event pipeline
- Schema normalization
- Real Kubernetes cluster (Minikube/Kind) hosting 6–8 microservices as the live data source
- Chaos Mesh integration for controlled, real failure injection (pod kill, latency injection, CPU stress)

**Goal:** Establish reliable, structured telemetry entering the platform from a real distributed environment — not simulated data alone.

↓

## PHASE 2: EVENT PROCESSING & NORMALIZATION 🟢

- Event parsing
- Timestamp normalization
- Deduplication
- Noise reduction
- Service/entity extraction
- Feature extraction
- Event enrichment
- **Drift-aware thresholds** — EWMA-based adaptive baselines so legitimate gradual growth doesn't trigger false anomalies
- Statistical anomaly scoring per service/metric (z-score / control-chart methods)

**Goal:** Transform raw telemetry into clean, correlation-ready signals with thresholds that adapt rather than stay static.

↓

## PHASE 3: CORRELATION ENGINE 🟣

- Temporal correlation
- Semantic similarity
- Service dependency mapping (built from real trace data, not hardcoded)
- Event clustering
- Causal relationship detection
- Incident grouping
- Alert deduplication
- **Multi-root-cause detection** — connected-components analysis on the anomaly subgraph so independent, simultaneous failures are correctly separated instead of merged into one wrong guess
- **False-positive suppression via historical memory** — cosine-similarity matching against known benign patterns (e.g. recurring daily traffic surges) to suppress noise before it reaches root-cause analysis
- **Blast radius prediction** — forward graph walk + anomaly spread velocity to forecast which services are likely to be affected next, with confidence and estimated time

**Goal:** Connect thousands of noisy signals into meaningful, correctly-separated incidents — reactively and predictively.

↓

## PHASE 4: AI ROOT-CAUSE ANALYSIS 🟠

- Anomaly detection (already scored in Phase 2, consumed here)
- LLM-assisted reasoning — thin usage layer only, reads structured evidence, never raw logs
- Historical incident context (from stored past incidents in Postgres)
- Dependency-graph reasoning
- Evidence retrieval
- Root-cause hypothesis generation
- Confidence scoring
- **Counterfactual "what-if" simulator** — re-runs the correlation engine on a user-modified parameter (e.g. "what if payment latency stayed under 200ms") to test whether a cascade would still have occurred

**Goal:** Identify and rank the most probable root cause using multiple evidence sources, with the ability to test causal "what-if" scenarios.

↓

## PHASE 5: INCIDENT INTELLIGENCE & RESPONSE 🟦

- Root-cause explanation
- Evidence timeline
- Impacted service analysis
- Incident severity
- **Severity-weighted business impact score** — combines anomaly severity, service revenue weight, and downstream dependent count into a single impact number
- **Auto-generated runbook suggestions** — root-cause type matched against a curated remediation library (e.g. "DB connection pool exhaustion → scale pool, check for leaks")
- Human-in-the-loop approval — no automatic remediation execution, ever
- Incident summary
- **Live incident dashboard** — WebSocket-streamed, real-time view of the incident unfolding (dependency graph turning red, root-cause node highlighted, live timeline) built with React + react-flow

**Goal:** Turn technical signals into actionable incident intelligence that an on-call engineer can act on immediately — with the loop from detection to suggested action fully closed.

↓

## PHASE 6: PRODUCTION HARDENING & SCALE 🔴

- Unit & integration testing (every engine — detection, correlation, suppression, prediction, counterfactual — tested against known ground-truth scenarios)
- Load and reliability testing
- Fault injection (via Chaos Mesh, extended beyond dev into a repeatable test suite)
- Observability of the AIOps platform itself (the monitoring system is monitored too)
- Security & access control (least-privilege service accounts, input validation, secrets management)
- Kubernetes deployment (full platform running on the real cluster, not just the target services)
- Horizontal scaling considerations (Redis for real-time state, Celery for background jobs, message queue between engine layers)
- Monitoring & continuous improvement (evaluation suite re-run against 25–30 injected scenarios, metrics tracked over time)

**Goal:** Make the system reliable, scalable, and production-ready — proven with real metrics, not assumed.

---

## Engineering Progression

```
Telemetry → Processing → Correlation → AI Reasoning → Incident Intelligence → Production Scale
```

Each phase produces a working, testable artifact before the next begins. No phase depends on assuming a later phase will "just work" — reliability is built bottom-up, not bolted on at the end.
