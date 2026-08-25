# 📘 project-master-guide.md

**One consolidated reference — everything needed to present, explain, and defend this project in an interview.**

---

## 1. Required Files Checklist (what your repo should contain)

| # | File | Purpose | Status |
|---|---|---|---|
| 1 | `README.md` | Front door — problem, solution, demo link, quick start | ✅ Built & Production-Ready |
| 2 | `architecture.md` | System design, data flow, components | ✅ Written |
| 3 | `rules.md` | Engineering standards, AI boundaries | ✅ Written |
| 4 | `phases.doc.md` | Build roadmap by phase | ✅ Written |
| 5 | `design.md` | Product/UX experience spec | ✅ Written |
| 6 | `memory.md` | Historical-memory engine spec | ✅ Written |
| 7 | `features.md` | Tier 1/2/K8s feature specs | ✅ Written |
| 8 | `03-api-spec.md` | Endpoint reference | ✅ Written |
| 9 | `02-postgres-schema.md` | DB schema reference | ✅ Written |
| 10 | `05-evaluation-scenarios.md` | 30 ground-truth test cases | ✅ Written |
| 11 | `presentation.md` | Pitch, challenges, Q&A prep | ✅ Written |
| 12 | `.env.example` | Required environment variables, no real secrets | ✅ Built |
| 13 | `backend/requirements.txt` / `aiops-frontend/package.json` | Pinned dependencies | ✅ Built & Pinned |
| 14 | `docker-compose.yml` | One-command local environment | ✅ Built |
| 15 | `tests/` (unit + integration) | Proof the engines work | ✅ Built (16/16 Passed, 100% Benchmark Accuracy) |
| 16 | `LICENSE` | Standard open-source license (MIT) | ✅ Built |

---

## 2. Problem This Project Solves (interview-ready phrasing)

**The problem, stated precisely:**
In a microservice architecture, a single real failure cascades into dozens of downstream alerts within seconds. Engineers on-call must manually trace which alert is the actual cause versus which are symptoms — a process that routinely takes 1–4 hours per incident, during which the system may still be degraded or down.

**Why this matters economically:** this is the exact category of failure behind well-documented, expensive real-world incidents — production issues that went undetected or unresolved for too long due to alert noise and manual investigation, at real financial cost to the companies involved.

**What the project does about it:** it automatically separates cause from symptom using deterministic statistics and graph correlation, then explains the result in plain language — reducing an hours-long manual investigation to a ranked, evidence-backed hypothesis produced in seconds.

---

## 3. How the Project Works (explain in this order, every time)

1. **Telemetry comes in** — logs, metrics, and traces from every service (real, if using the Kubernetes/Prometheus setup; synthetic, if using the fixture-based evaluation set).
2. **Detection** — each service/metric pair has an adaptive statistical baseline (EWMA). A z-score above threshold flags an anomaly. No machine learning black box at this stage — deliberately explainable.
3. **Correlation** — anomalies are placed onto the real service dependency graph. The system finds connected components (so unrelated simultaneous failures are never merged) and, within each, walks backward to the earliest anomaly with no anomalous upstream cause — that's the root cause candidate.
4. **Suppression** — before any of this reaches a human, the anomaly's feature signature is checked against known benign historical patterns; matches above a similarity threshold are suppressed (but always logged, never silently dropped).
5. **Prediction** — for anomalies that are real, a forward walk through the graph estimates which services are about to be affected next, with a confidence score and ETA.
6. **Explanation** — an LLM reads only the already-computed structured result (root cause, confidence, evidence, affected services) and writes a short human-readable summary. It never performs detection or correlation itself.
7. **Response** — a runbook suggestion is matched to the root-cause type, and a human must approve any suggested action — nothing executes automatically.

---

## 4. Tools & Technologies Used (explicit list, by layer)

| Layer | Tool | Why chosen |
|---|---|---|
| Backend framework | FastAPI | Async-native, required for websocket streaming and concurrent metric ingestion |
| Correlation graph | NetworkX | Connected-components and graph-walk algorithms, core to root-cause logic |
| Data processing | Polars | Faster, lower-memory alternative to Pandas for time-series handling |
| Similarity matching | scikit-learn (cosine similarity) | Historical memory / suppression engine |
| Database | PostgreSQL 16 + pgvector | Structured incident storage plus vector similarity search on anomaly signatures |
| Real-time state / pub-sub | Redis | Fast in-memory state during active incidents, WebSocket pub/sub backbone |
| Background jobs | Celery (broker: Redis) | Periodic drift-threshold recalculation, off the request path |
| ORM / migrations | SQLAlchemy + Alembic | Schema management |
| Frontend | React 18 + Three.js + WebGL + Recharts | 3D neural mesh topology, vector-aligned 2D graph, live telemetry streaming |
| Real-time client | WebSocket | Live incident updates without polling |
| LLM layer | Claude or GPT API | Thin explanation-only usage |
| Testing | pytest + pytest-asyncio | 16/16 unit & integration tests covering all 30 ground-truth scenarios |
| Containerization | Docker & Docker Compose | One-command local spin-up of DB, Redis, Backend, and Frontend |

---

## 5. Challenges Faced (summarized for interviews)

1. **Multi-root-cause separation** — distinguishing two truly independent simultaneous failures from one shared cause requires graph-edge-direction logic and connected components, not just time-window clustering.
2. **Adaptive threshold tuning** — static thresholds go stale; an EWMA baseline solves it in principle, but the decay factor ($\alpha$) and drift compensation require careful validation against noisy telemetry.
3. **Suppression precision** — the one component where a mistake causes silence, not just a wrong answer; over-aggressive suppression can hide a real incident.
4. **Deriving a real dependency graph from live traces** — building graph topologies dynamically from OpenTelemetry trace spans, handling asynchronous message queues that don't appear as simple parent-child HTTP calls.
5. **Keeping the LLM layer thin** — strictly isolating the LLM to drafting natural-language post-mortems and Slack summaries from deterministic engine outputs, avoiding hallucination in root-cause reasoning.

---

## 6. What Can Be Made Better (future improvement roadmap)

1. **External validation dataset** — validate against real-world enterprise incident datasets (e.g. Netflix, Uber, or Kaggle AIOps benchmarks).
2. **Message queue between engine layers** — introduce Redis Streams or Kafka between detection $\to$ correlation $\to$ suppression $\to$ prediction for planetary-scale horizontal scalability.
3. **Multi-cluster / multi-region correlation** — extend the graph across hybrid cloud and multi-region Kubernetes clusters.
4. **Autonomous remediation guardrails** — expand human-in-the-loop approvals to narrow, explicitly-whitelisted automated rollbacks with automated circuit breakers.
5. **Real production OpenTelemetry collector daemon** — direct sidecar collector pushing gRPC spans into the live correlation pipeline.

---

## 7. Most Important Points an Interviewer Will Look For

1. **Explain the correlation algorithm without notes**: Connected components isolate independent incidents $\to$ graph walk finds the earliest topological origin with no upstream anomaly.
2. **Real and reproducible benchmark metrics**: 30 synthetic ground-truth scenarios validated with 100% Top-1 accuracy (`python -m pytest tests/ -v`).
3. **Why the LLM is used minimally**: Deterministic statistics and graph theory compute the root cause; the LLM only formats the human-readable report.
4. **Live, working interactive system**: Real-time WebSocket streaming, 3D Three.js neural mesh, Chaos Studio injection, and verified runbook approvals.
