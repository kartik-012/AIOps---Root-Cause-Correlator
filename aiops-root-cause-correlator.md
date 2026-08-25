# AIOps Root Cause Correlator

**AI-powered incident correlation and root-cause analysis for distributed systems**

---

## 1. Observability Data (Input Sources)

- Logs
- Metrics
- Distributed Traces
- Alerts
- Deployment Events
- Infrastructure Events

All sources feed into the ingestion layer in real time.

---

## 2. Event Ingestion & Normalization

- Real-time event ingestion
- Timestamp normalization
- Service/entity identification
- Deduplication
- Noise filtering

---

## 3. Correlation Engine (Core)

Correlates events using:

- Temporal correlation
- Service dependency graphs
- Semantic similarity
- Event patterns
- Causal relationships
- Anomaly signals

Multiple seemingly unrelated incidents are converged into a single correlated incident graph.

---

## 4. AI Root-Cause Engine (Intelligence Layer)

**LLM + ML + Graph-based reasoning**

Analyzes:

- Incident context
- Service dependencies
- Historical incidents
- Recent deployments
- Logs / traces / metrics
- Failure propagation paths

Produces a ranked root-cause hypothesis.

---

## 5. Root Cause + Impact Analysis (Sample Output)

| Field | Value |
|---|---|
| **Likely Root Cause** | Database connection pool exhaustion |
| **Affected Services** | API Gateway → Order Service → Payment Service |
| **Confidence** | 94% |
| **Impact** | Elevated request latency + failed transactions |

---

## 6. Actionable Incident Response (Final Output)

- Root-cause explanation
- Evidence / supporting signals
- Impacted services
- Incident timeline
- Recommended remediation
- Incident summary

---

## Why It Matters

**Before:** Hundreds of alerts → Manual investigation → Long MTTR

**After:** Correlated signals → Root-cause hypothesis → Faster incident resolution

**Key outcomes:**
- Reduce alert noise
- Improve MTTR
- Explain failures
- Accelerate incident response
