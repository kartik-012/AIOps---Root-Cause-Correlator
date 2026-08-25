# 📘 rules.md

**Engineering standards, AI boundaries, reliability principles and development guidelines**
**Project: AIOps Root Cause Correlator**

---

## 1. WHAT TO USE ✅

> Approved technologies, architectural patterns and engineering practices for the platform.

### Backend & Language
- **Python 3.11+** as the primary backend language
- **FastAPI** for all API and WebSocket endpoints — async-native, auto-generates OpenAPI docs
- **Type hints everywhere** — every function signature must be fully typed, no bare `def foo(x):`
- **Pydantic models** for all request/response schemas and internal data contracts — no raw dicts passed between layers

### Observability
- **OpenTelemetry standards** for all trace instrumentation — don't invent a custom tracing format
- **Structured logging** (JSON logs) — every log line must be machine-parseable: `{"timestamp": ..., "service": ..., "level": ..., "event": ..., "context": {...}}`
- Every critical function logs entry, exit, and failure state

### Processing Model
- **Async/event-driven processing** for all I/O-bound work (DB calls, HTTP calls, websocket pushes)
- Background/periodic work (drift recalculation, suppression model updates) goes through a task queue (Celery), never inline in a request handler

### Infrastructure
- **Docker** for every service — one Dockerfile per microservice, multi-stage builds to keep images small
- **Kubernetes** (Minikube/Kind for local dev) for orchestration — no manually-managed processes
- **Helm charts** for repeatable installs (Prometheus, etc.)

### Testing
- **Automated testing required** for every engine (detection, correlation, suppression, prediction) — no engine ships without unit tests proving its core algorithm
- Test with known synthetic scenarios where the ground truth is known — this is how you get your accuracy metrics

### API Design
- **Secure API design** — authentication on every endpoint, input validation via Pydantic, rate limiting on public-facing routes
- Versioned API paths (`/api/v1/...`) from day one

---

## 2. WHAT TO AVOID ❌

> Patterns and practices that reduce reliability, explainability or maintainability.

| Anti-pattern | Why it's banned |
|---|---|
| **Hard-coded secrets** | API keys, DB passwords, tokens must never appear in source code — use environment variables / secrets manager |
| **Unstructured logs** | `print("error happened")` gives you nothing to correlate on. Every log must be structured JSON |
| **Silent exception handling** | `except: pass` hides real failures. Every caught exception must be logged with full context and re-raised or explicitly handled |
| **Unbounded retries** | A retry loop with no cap can hammer a failing service into total collapse. Every retry needs a max attempt count and backoff |
| **Blocking operations in async paths** | A synchronous DB call or `time.sleep()` inside an `async def` blocks the entire event loop — use async drivers everywhere |
| **Unvalidated AI output** | Never pass an LLM's output directly into a decision or action without checking it against structured evidence first |
| **Single points of failure** | No component (DB, message queue, detection engine) should be a hard dependency with no fallback path |
| **Unnecessary dependencies** | Every new library must be justified — don't import a whole framework for one utility function |

---

## 3. LIBRARIES & DEPENDENCIES 📦

> Keep dependencies minimal, pinned, reviewed and justified.

### Rules
- **Production-approved packages only** — stick to widely-adopted, actively-maintained libraries (FastAPI, NetworkX, Polars, Redis-py, SQLAlchemy) — avoid obscure or abandoned packages
- **Version pinning** — every dependency pinned to an exact version in `requirements.txt` / `pyproject.toml` (e.g. `fastapi==0.115.0`, not `fastapi>=0.100`)
- **Dependency vulnerability scanning** — run `pip-audit` or `safety` before every release
- **License checks** — confirm every dependency's license (MIT, Apache 2.0, BSD) is compatible with your intended use; flag GPL/AGPL dependencies for review
- **Regular updates** — schedule a monthly dependency review, don't let versions rot for a year
- **No unnecessary libraries** — before adding a package, ask: "can this be done in 20 lines of stdlib code instead?"

### This Project's Approved Core Dependencies
```
fastapi
uvicorn
pydantic
sqlalchemy
alembic
psycopg2-binary
redis
celery
networkx
polars
scikit-learn
python-dotenv
websockets
```

---

## 4. ERROR HANDLING & RELIABILITY ⚠️

> Failures must be observable, recoverable and safe.

### Required Practices
- **Structured error logging** — every exception logged with: timestamp, service name, stack trace, request context, correlation ID
- **Timeouts** — every external call (DB, API, LLM) has an explicit timeout; nothing waits forever
- **Retries with exponential backoff** — e.g. retry at 1s, 2s, 4s, 8s, max 4 attempts, then fail loud
- **Circuit breakers** — if a downstream dependency (e.g. LLM API) fails repeatedly, stop calling it for a cooldown period instead of retrying forever
- **Graceful degradation** — if the LLM explanation layer is down, the system still returns the structured root-cause result without the narrative summary — never let a non-critical layer take down the whole response
- **Dead-letter handling** — events that fail processing repeatedly go to a dead-letter queue for manual inspection, not silently dropped
- **Clear error propagation** — errors bubble up with context intact; don't catch-and-reraise a generic `Exception` that loses the original stack trace
- **No silent failures** — anywhere. If something fails, it is logged, and either recovered from or surfaced.

### Example Pattern (Python)
```python
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("correlation_engine")

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=8))
async def fetch_service_metrics(service_id: str):
    try:
        return await metrics_client.get(service_id, timeout=5)
    except TimeoutError as e:
        logger.error(
            "metrics_fetch_timeout",
            extra={"service_id": service_id, "error": str(e)}
        )
        raise
```

---

## 5. BOUNDARIES OF AI 🛡️

> AI assists investigation but must not blindly control production systems.

### Core Principles
- **Ground AI responses in observable evidence** — the LLM never generates a root-cause explanation from nothing; it only summarizes structured data your detection/correlation engines already produced
- **Never invent telemetry or incidents** — if the data doesn't show an anomaly, the AI layer must not hallucinate one
- **Provide supporting evidence for root-cause hypotheses** — every AI output must be traceable back to the specific anomaly events and graph correlation that produced it
- **Show confidence / uncertainty** — never present a root-cause guess as fact; always attach a confidence score, and communicate when confidence is low
- **Validate model outputs** — check that the LLM's structured output (if using function-calling/JSON mode) matches your expected schema before displaying it; reject and fall back if malformed
- **Human approval for high-impact remediation** — this system suggests runbook actions, it never auto-executes a rollback, restart, or scaling action without a human clicking "approve"
- **Protect sensitive telemetry** — logs/metrics may contain sensitive data (user IDs, request payloads); redact before sending anything to an external LLM API
- **Fail safely when evidence is insufficient** — if the correlation engine can't identify a root cause with reasonable confidence, the system says "insufficient evidence" — it does not force a guess to look complete

---

## 6. GENERAL ENGINEERING RULES 📋

- **Clean architecture & separation of concerns** — detection, correlation, suppression, prediction, and explanation are independent modules with clear interfaces; no engine directly reaches into another's internals
- **Strong typing and consistent formatting** — full type hints, enforced with `mypy`; formatting enforced with `black` + `ruff`, run in CI on every commit
- **Meaningful naming conventions** — `detect_latency_anomaly()` not `check1()`; `ServiceDependencyGraph` not `Graph2`
- **Unit + integration + end-to-end testing** — unit tests per engine, integration tests across the pipeline, end-to-end tests running full injected failure scenarios
- **Security-first development** — validate all inputs, sanitize all outputs, no trust boundaries skipped
- **Least-privilege access** — the API only has DB permissions it actually needs; service accounts scoped narrowly, not given admin-everywhere credentials
- **Observability for every critical component** — every engine emits its own health metrics (latency, error rate, throughput) — you should be able to monitor the monitoring system itself
- **Performance and scalability considerations** — document the expected scale (number of services, event volume) and design within that budget; don't prematurely over-engineer, but don't ignore it either
- **Backward-compatible API changes** — new fields are additive; breaking changes get a new API version
- **Clear documentation** — every module has a docstring explaining its responsibility; this `rules.md` and the `architecture.md` are kept up to date as the system evolves
- **Reproducible builds** — anyone should be able to clone the repo, run `docker-compose up`, and get a working local environment without tribal knowledge
- **Review before production deployment** — no direct pushes to the deployed branch; every change goes through review, even solo (self-review checklist counts)

---

## Why These Rules Exist

A project like this lives or dies on **trust in its output.** If the correlation engine gives a wrong root cause with false confidence, it's worse than no tool at all — it sends engineers chasing the wrong fire while the real one spreads. Every rule above exists to protect one thing: **the system's claims must always be traceable back to real evidence, and it must fail honestly when it doesn't have enough.**
