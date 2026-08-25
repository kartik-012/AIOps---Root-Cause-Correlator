# 📘 postgres-schema.md

**Database schema — AIOps Root Cause Correlator**

---

## 0. Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector; -- pgvector, for anomaly signature similarity search
```

---

## 1. `services` — Service Registry & Dependency Graph

```sql
CREATE TABLE services (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) UNIQUE NOT NULL,
    revenue_weight  FLOAT NOT NULL DEFAULT 1.0,   -- used by impact_engine
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE service_dependencies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    to_service_id   UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    UNIQUE (from_service_id, to_service_id)
);
```

---

## 2. `metrics_raw` — Time-Series Telemetry

```sql
CREATE TABLE metrics_raw (
    id              BIGSERIAL PRIMARY KEY,
    service_id      UUID NOT NULL REFERENCES services(id),
    metric_type     VARCHAR(50) NOT NULL,   -- 'latency_ms', 'error_rate', 'cpu_usage', 'memory_usage'
    value           FLOAT NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- If using TimescaleDB:
-- SELECT create_hypertable('metrics_raw', 'recorded_at');

CREATE INDEX idx_metrics_service_time ON metrics_raw (service_id, recorded_at DESC);
CREATE INDEX idx_metrics_type ON metrics_raw (metric_type);
```

---

## 3. `anomalies` — Detected Anomaly Events

```sql
CREATE TABLE anomalies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id      UUID NOT NULL REFERENCES services(id),
    metric_type     VARCHAR(50) NOT NULL,
    z_score         FLOAT NOT NULL,
    severity        VARCHAR(20) NOT NULL,   -- 'low', 'medium', 'high', 'critical'
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    incident_id     UUID REFERENCES incidents(id)   -- nullable until clustered into an incident
);

CREATE INDEX idx_anomalies_detected_at ON anomalies (detected_at DESC);
CREATE INDEX idx_anomalies_incident ON anomalies (incident_id);
```

---

## 4. `incidents` — Correlated Incident Records

```sql
CREATE TABLE incidents (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp_start         TIMESTAMPTZ NOT NULL,
    timestamp_end           TIMESTAMPTZ,
    root_cause_service_id   UUID REFERENCES services(id),
    root_cause_type         VARCHAR(100),      -- e.g. 'db_connection_exhaustion'
    confidence_at_detection FLOAT,
    is_multi_root_cause     BOOLEAN NOT NULL DEFAULT false,
    resolution_action       TEXT,
    was_false_positive      BOOLEAN NOT NULL DEFAULT false,
    learned_pattern_tag     VARCHAR(100),
    anomaly_signature       vector(7),          -- pgvector column, see memory.md Section 2
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidents_root_cause_type ON incidents (root_cause_type);
CREATE INDEX idx_incidents_false_positive ON incidents (was_false_positive);

-- Vector similarity index (build once incident volume grows)
CREATE INDEX idx_incidents_signature_cosine
    ON incidents USING ivfflat (anomaly_signature vector_cosine_ops)
    WITH (lists = 100);
```

**Note:** `anomalies.incident_id` references `incidents.id`, and `incidents.root_cause_service_id` references `services.id` — this creates the link between raw anomaly events and the incident they were clustered into.

---

## 5. `incident_affected_services` — Propagation Order (many-to-many with order)

```sql
CREATE TABLE incident_affected_services (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    service_id      UUID NOT NULL REFERENCES services(id),
    propagation_order INT NOT NULL,     -- 0 = root cause, 1 = first affected downstream, etc.
    affected_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_ias_incident ON incident_affected_services (incident_id, propagation_order);
```

---

## 6. `suppressions` — False-Positive Suppression Log

```sql
CREATE TABLE suppressions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    triggering_anomaly_id   UUID NOT NULL REFERENCES anomalies(id),
    matched_incident_id     UUID NOT NULL REFERENCES incidents(id),
    similarity_score        FLOAT NOT NULL,
    suppressed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Design note (per `rules.md` — no silent failures):** every suppression is logged here, never silently dropped. This table is what lets you compute suppression precision/recall in your evaluation.

---

## 7. `blast_radius_predictions` — Prediction Engine Output

```sql
CREATE TABLE blast_radius_predictions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id         UUID NOT NULL REFERENCES incidents(id),
    predicted_service_id UUID NOT NULL REFERENCES services(id),
    predicted_eta_seconds INT NOT NULL,
    confidence          FLOAT NOT NULL,
    was_correct         BOOLEAN,        -- filled in after the fact, for evaluation
    predicted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. `runbook_suggestions` — Remediation Library Lookup Log

```sql
CREATE TABLE runbook_suggestions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id),
    root_cause_type VARCHAR(100) NOT NULL,
    suggested_action TEXT NOT NULL,
    was_approved    BOOLEAN,       -- human-in-the-loop approval, per rules.md Section 5
    suggested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 9. Relationship Diagram (text form)

```
services ──< service_dependencies >── services
   │
   ├──< metrics_raw
   │
   ├──< anomalies >── incidents
   │                      │
   │                      ├──< incident_affected_services >── services
   │                      ├──< suppressions
   │                      ├──< blast_radius_predictions >── services
   │                      └──< runbook_suggestions
```

---

## 10. Sample Query — Retrieve Top-5 Similar Past Incidents (Memory Engine)

```sql
SELECT id, root_cause_type, resolution_action,
       anomaly_signature <=> :new_signature AS distance
FROM incidents
WHERE was_false_positive = false
ORDER BY distance ASC
LIMIT 5;
```

This is the exact query behind Section 3 of `memory.md` — the historical-context retrieval step.
