# 📘 repo-structure.md

**Repository layout — AIOps Root Cause Correlator**

---

```
aiops-root-cause-correlator/
│
├── backend/
│   ├── app/
│   │   ├── main.py                      # FastAPI app entrypoint
│   │   ├── config.py                    # env vars, settings via Pydantic BaseSettings
│   │   ├── dependencies.py              # shared DB/Redis session dependencies
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── incidents.py         # /api/v1/incidents endpoints
│   │   │   │   ├── services.py          # /api/v1/services endpoints
│   │   │   │   ├── detection.py         # /api/v1/detection endpoints
│   │   │   │   ├── correlation.py       # /api/v1/correlation endpoints
│   │   │   │   ├── prediction.py        # /api/v1/blast-radius endpoints
│   │   │   │   ├── counterfactual.py    # /api/v1/whatif endpoints
│   │   │   │   ├── explain.py           # /api/v1/explain (LLM layer) endpoints
│   │   │   │   └── ws.py                # websocket streaming endpoint
│   │   │   │
│   │   ├── engines/
│   │   │   ├── __init__.py
│   │   │   ├── detection_engine.py      # z-score + EWMA drift-aware detection
│   │   │   ├── correlation_engine.py    # graph backward-walk, multi-root-cause
│   │   │   ├── suppression_engine.py    # historical memory + cosine similarity
│   │   │   ├── prediction_engine.py     # blast radius forward-walk
│   │   │   ├── counterfactual_engine.py # what-if re-simulation
│   │   │   ├── impact_engine.py         # business impact scoring
│   │   │   └── explanation_engine.py    # thin LLM wrapper
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── db_models.py             # SQLAlchemy ORM models
│   │   │   └── schemas.py               # Pydantic request/response schemas
│   │   │
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   └── dependency_graph.py      # NetworkX graph builder + queries
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py            # Celery config
│   │   │   └── periodic_tasks.py        # drift recalculation, suppression model refresh
│   │   │
│   │   └── runbooks/
│   │       └── runbook_library.json     # root-cause-type → suggested remediation
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_detection_engine.py
│   │   │   ├── test_correlation_engine.py
│   │   │   ├── test_suppression_engine.py
│   │   │   └── test_prediction_engine.py
│   │   ├── integration/
│   │   │   └── test_pipeline_end_to_end.py
│   │   └── fixtures/
│   │       └── synthetic_scenarios/     # the 25-30 injected failure scenarios
│   │
│   ├── alembic/
│   │   └── versions/                    # DB migrations
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml               # local Postgres + Redis + backend
│
├── simulator/
│   ├── services/                        # dummy microservice source (auth, payment, etc.)
│   │   ├── auth-service/
│   │   ├── payment-service/
│   │   ├── inventory-service/
│   │   ├── order-service/
│   │   ├── notification-service/
│   │   └── api-gateway/
│   ├── k8s-manifests/
│   │   ├── namespace.yaml
│   │   ├── deployments/                 # one per service
│   │   ├── services/                    # one per service
│   │   └── prometheus-values.yaml       # Helm values for kube-prometheus-stack
│   └── chaos/
│       └── chaos-experiments/           # Chaos Mesh experiment YAMLs, one per scenario
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DependencyGraph.jsx      # react-flow graph
│   │   │   ├── IncidentTimeline.jsx
│   │   │   ├── RootCausePanel.jsx
│   │   │   ├── CounterfactualPanel.jsx
│   │   │   └── EvidencePanel.jsx
│   │   ├── hooks/
│   │   │   └── useIncidentSocket.js     # websocket hook
│   │   ├── pages/
│   │   │   └── Dashboard.jsx
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   ├── architecture.md
│   ├── rules.md
│   ├── phases.doc.md
│   ├── design.md
│   ├── memory.md
│   ├── api-spec.md
│   └── evaluation-scenarios.md
│
├── .env.example
├── README.md
└── LICENSE
```

---

## Notes on Structure

- **`engines/` is the core IP** — each engine is a standalone, independently testable module. No engine imports another engine's internals directly; they communicate through the pipeline in `api/v1/`.
- **`simulator/` is separate from `backend/`** — the synthetic environment (or real K8s target services) is not part of the product, it's the test harness. Keep this distinction clear in your README so an interviewer understands what's "the product" vs "the test rig."
- **`tests/fixtures/synthetic_scenarios/`** holds your 25-30 ground-truth failure scenarios — this directory is what makes your evaluation numbers reproducible, not just claimed.
- **`docs/`** mirrors everything already built in this conversation — keep these in the actual repo, not just as chat output. Interviewers who check your GitHub will read these.
