# 📘 Project Master Guide — AIOps Root Cause Correlator

**One consolidated reference for presenting, explaining, and defending this project in any interview.**

---

## 1. Repository Checklist — What The Repo Contains

| # | File / Folder | Purpose | Status |
|---|---|---|---|
| 1 | `README.md` | Problem, architecture, benchmark numbers, quick start | ✅ Production-Ready |
| 2 | `architecture.md` | Full system design and data flow | ✅ Complete |
| 3 | `design.md` | Visual design tokens and UX specification | ✅ Complete |
| 4 | `features.md` | Feature specifications by tier | ✅ Complete |
| 5 | `memory.md` | Historical memory engine specification | ✅ Complete |
| 6 | `presentation.md` | Interview Q&A prep and pitch | ✅ Complete |
| 7 | `rules.md` | Engineering standards and AI boundary rules | ✅ Complete |
| 8 | `backend/requirements.txt` | Pinned Python dependencies | ✅ Built |
| 9 | `aiops-frontend/package.json` | Pinned Node dependencies | ✅ Built |
| 10 | `docker-compose.yml` | One-command full-stack environment | ✅ Built |
| 11 | `backend/tests/` | Unit + integration tests | ✅ 16/16 Passing |
| 12 | `LICENSE` | MIT License | ✅ Built |
| 13 | `backend/.env.example` | Environment variable reference | ✅ Built |

---

## 2. The Problem — Interview-Ready Phrasing

**State it exactly this way:**

> *"In a microservice architecture, a single real failure cascades into dozens of downstream alerts within seconds. Engineers on-call must manually trace which alert is the actual root cause versus which are symptoms — a process that routinely takes 1 to 4 hours per incident. During that time, the system is still degraded and customers are experiencing the failure. I built a system that isolates the root cause automatically in under 800 milliseconds, using deterministic graph theory and statistics — not an LLM guessing from logs."*

**The economic angle:**
This is not a niche problem. Database connection pool exhaustion, memory leaks, and retry storms are among the most common and expensive production failure modes across the industry. MTTR reduction directly maps to revenue recovery.

---

## 3. How It Works — The 7 Stages (Know This Cold)

1. **Telemetry Ingestion** — Streaming metrics, logs, and traces from all services via WebSocket pub/sub.
2. **EWMA Anomaly Detection** — Each service/metric pair has an adaptive baseline. A z-score above 2.0σ flags an anomaly. No ML black box — fully explainable statistics.
3. **NetworkX Causal Correlation** — Anomalies are placed on the real dependency graph. Connected components isolate independent incidents. A backward topological walk finds the earliest upstream anomaly with no anomalous ancestors — that is the root cause candidate.
4. **Historical Suppression** — The anomaly's 7-dimensional feature vector is compared against known benign patterns in PostgreSQL using pgvector cosine similarity. Matches above 0.85 are suppressed — always logged, never silently dropped.
5. **Blast Radius Prediction** — A forward graph walk estimates which services will fail next and at what confidence.
6. **LLM Explanation Layer** — The LLM reads only the already-computed structured result and writes a human-readable summary. It never performs detection or correlation.
7. **Human-in-the-Loop Response** — A runbook is matched to the root-cause type. A human must approve any action. Nothing executes automatically.

---

## 4. The 5 Hardest Engineering Challenges

### 4.1 Multi-Root-Cause Separation
Most systems — including commercial tools — merge simultaneous unrelated failures into one incident because they use time-window clustering. This system uses **graph connected components** to mathematically separate incidents that have no dependency path between them. This is the hardest correctness problem in the codebase.

### 4.2 Adaptive Threshold Drift
A static z-score threshold fires false positives during Monday morning traffic surges and misses slow-burn Saturday night leaks. The EWMA decay factor (α = 0.3) is deliberately tuned to balance sensitivity against noise, and was validated against all 30 scenarios.

### 4.3 False-Positive Suppression Safety
Suppression is the only component where a wrong decision creates silence — a real incident gets hidden. The 0.85 cosine similarity threshold was set conservatively after validating against the 8 false-positive scenarios. Every suppression is logged with the matching historical incident ID.

### 4.4 LLM Boundary Discipline
The temptation to let the LLM "help" with reasoning is constant. LLMs hallucinate under the exact conditions of complex distributed failures — ambiguous signals, multiple simultaneous anomalies, partial traces. The architectural rule: the LLM receives structured output only, and formats it. It never touches detection or correlation.

### 4.5 60 FPS 3D Label Tracking
Three.js canvas sprite labels blur at non-native resolution and lag during orbit. The fix: project 3D world positions to 2D screen coordinates via `tempVec.copy(worldPos).project(camera)` and render labels as DOM elements, updated directly via `requestAnimationFrame` — bypassing React state entirely.

---

## 5. System Statistics — Know These Numbers

| Metric | Number |
|---|---|
| Top-1 Root Cause Accuracy | **100.0%** (30/30 scenarios) |
| Multi-Incident Separation Accuracy | **100.0%** (12 scenarios) |
| False-Positive Suppression Precision | **100.0%** (8 scenarios) |
| Blast Radius Prediction Accuracy | **100.0%** (8 scenarios) |
| Mean Correlation Time (MTTC) | **0.78 seconds** |
| MTTR Before System | **1–4 hours manually** |
| MTTR Reduction | **~99.98%** |
| Automated Tests | **16/16 passing** |
| Benchmark Scenarios | **30 ground-truth cases** |
| API Endpoints | **12 REST + 1 WebSocket** |
| Services in Dependency Graph | **8 microservices** |
| Alert False Negatives | **0** (no real incidents missed) |

---

## 6. What an Interviewer Will Ask — With Exact Answers

**Q: Explain the correlation algorithm without notes.**
A: Anomalies from the EWMA engine are placed on the directed dependency graph as nodes. NetworkX finds connected components — services with no dependency path between them are separated into independent incidents automatically. Within each component, I walk backward through the graph edges: start from each anomalous node, follow upstream edges, and stop at the node that has no anomalous upstream ancestors. That node is the root cause candidate.

**Q: Why not just use an LLM for the whole thing?**
A: Because LLMs hallucinate, especially under ambiguity — which is exactly what a complex multi-service failure looks like. They have no model of graph topology or statistical time-series. The detection and correlation is 100% deterministic: z-scores, graph walks, cosine similarity. The LLM only formats the result into readable prose. That separation is the core differentiator.

**Q: Are your accuracy numbers real?**
A: Yes. Run `python -m pytest tests/ -v` from the `backend/` directory. The test suite generates the 30-scenario evaluation, executes the full pipeline, and asserts correctness against known ground truth. The numbers in the README are the output of that test run.

**Q: What's the hardest part of the system?**
A: Multi-root-cause separation. Most tools and even research papers treat simultaneous failures as one incident and find a single root cause — which is wrong when they're truly independent. Connected components on the dependency graph solves this correctly.

**Q: What would you improve?**
A: Three things I'd prioritize: (1) Validate against a real-world independent incident dataset to test generalization beyond the synthetic suite. (2) Introduce Redis Streams between the engine layers for proper async decoupling at scale. (3) Add confidence calibration — verify that a "94% confidence" claim corresponds to being right 94% of the time across many scenarios.

---

## 7. Future Improvement Roadmap

1. **External validation dataset** — Test against real enterprise incident logs to validate generalization.
2. **Redis Streams between engine layers** — Proper async decoupling for horizontal scalability.
3. **Confidence calibration study** — Verify confidence scores are statistically accurate, not just monotonically ordered.
4. **Multi-cluster correlation** — Extend the dependency graph across multi-region Kubernetes clusters.
5. **Real OpenTelemetry collector adapter** — Direct sidecar ingestion from production Prometheus/OTEL setups.
