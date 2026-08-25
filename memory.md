# 📘 memory.md

**Incident Memory Engine — historical knowledge design**
**Project: AIOps Root Cause Correlator**

---

## 0. Why This Exists

A correlation engine with no memory re-solves the same incident from zero every single time. Real production AIOps value comes from **recognizing that "this looks like the incident from three weeks ago"** — cutting root-cause time down using precedent, not just fresh statistics. This document specifies how historical incidents are stored, matched, and used to both **suppress false positives** and **accelerate root-cause confidence** on new incidents.

This engine directly powers two features from `phases.doc.md`:
- Phase 3 — False-positive suppression via historical memory
- Phase 4 — Historical incident context feeding the AI Root-Cause Engine

---

## 1. What Gets Stored Per Incident

Every resolved incident is written to persistent storage as a structured record — never raw logs dumped wholesale.

| Field | Description |
|---|---|
| `incident_id` | Unique identifier |
| `timestamp_start` / `timestamp_end` | When the incident began and was resolved |
| `root_cause_service` | The service identified as the root cause |
| `root_cause_type` | Category (e.g. `db_connection_exhaustion`, `memory_leak`, `latency_cascade`) |
| `affected_services` | Ordered list of services impacted, in propagation order |
| `anomaly_signature` | Feature vector: which metrics spiked, magnitude, time-of-day, day-of-week |
| `confidence_at_detection` | The confidence score the AI engine assigned at the time |
| `resolution_action` | What actually fixed it (human-confirmed, not AI-guessed) |
| `was_false_positive` | Boolean — marked true if a human reviewer confirmed this was benign, not a real incident |
| `learned_pattern_tag` | Short label summarizing the pattern, for fast lookup |

---

## 2. The Anomaly Signature (core matching unit)

The anomaly signature is what makes two incidents comparable. It is a fixed-length feature vector, not free text:

```
[
  time_of_day_bucket,      # e.g. morning / afternoon / night
  day_of_week,
  primary_service_id,
  metric_type,             # latency / error_rate / cpu / memory
  severity_zscore,
  propagation_depth,       # how many services it cascaded through
  propagation_speed        # seconds between first and last affected service
]
```

This vector is what gets compared via cosine similarity — not raw logs, not free-text descriptions. Keeping it structured is what makes the matching fast and explainable.

---

## 3. Matching Pipeline — Step by Step

```
New anomaly detected
      ↓
Build anomaly signature for the new event
      ↓
Query historical incident store for signatures within similarity threshold
      ↓
   ┌─────────────┴─────────────┐
   ↓                           ↓
Match found                No match found
   ↓                           ↓
Check was_false_positive   Treat as novel incident,
   ↓                       proceed to full correlation
┌──┴──┐                    + root-cause analysis
↓     ↓
True  False
↓     ↓
Suppress   Attach matched incident's
(don't     root_cause_type as a
alert)     prior — boosts confidence
           if correlation engine
           independently agrees
```

**Key rule:** a historical match never overrides the correlation engine's own independent analysis — it only adds supporting evidence or suppresses known-benign noise. Memory assists reasoning; it does not replace it.

---

## 4. False-Positive Suppression Logic

1. During evaluation/operation, when a human reviewer marks a flagged anomaly as benign (e.g. the recurring 9am traffic surge), that incident's signature is stored with `was_false_positive = true`.
2. On every new anomaly, before running full correlation, check similarity against the false-positive store first.
3. If cosine similarity exceeds the suppression threshold (tune this — start at 0.9, evaluate against your test scenarios) → suppress the alert entirely, log it as suppressed (never silently dropped — always logged, per `rules.md` Section 4).
4. If similarity is below threshold → proceed to full detection/correlation pipeline as normal.

**This is the concrete mechanism behind the alert-fatigue-reduction claim** — it needs its own metric in your evaluation section (suppression precision/recall), not just an assumption that it works.

---

## 5. Historical Context Feeding the AI Root-Cause Engine

When a **real** (non-suppressed) incident is being analyzed:

1. Retrieve the top-k most similar past incidents (k=3–5) by anomaly signature similarity.
2. Pass their `root_cause_type` and `resolution_action` into the AI reasoning layer's input, alongside the current structured evidence.
3. The LLM explanation layer can then say something like: *"This anomaly signature closely matches 2 past incidents, both resolved as connection pool exhaustion — this raises confidence in the current hypothesis."*
4. This context **never determines the final root cause on its own** — it only adjusts the confidence score and provides explanatory grounding, staying consistent with the AI-boundaries principle: ground responses in evidence, never let history override present-moment analysis.

---

## 6. Storage & Retrieval Implementation

| Concern | Approach |
|---|---|
| Storage | PostgreSQL table `incidents` — structured fields as in Section 1 |
| Signature storage | Store as a fixed-length array column, or in a companion vector table if using a vector DB extension (e.g. `pgvector`) |
| Similarity search | Cosine similarity via `pgvector`'s `<=>` operator, or scikit-learn's `cosine_similarity` if kept in-process for small incident counts |
| Indexing | Vector index (IVFFlat or HNSW via `pgvector`) once incident count grows past a few thousand — not needed at portfolio scale, but document it as the production path |
| Retention | Keep all incidents; false-positive-marked ones especially should never expire, since they're what suppress recurring noise |

---

## 7. Visual Experience (from design.md, Section 8 — referenced here for completeness)

**Representation:** historical incidents as floating memory nodes, each showing:
```
Past Incident → Root Cause → Resolution → Learned Pattern → Future Detection
```

**Behavior on new incident:**
1. System visibly "searches" historical memory — a soft sweeping highlight passes across the memory node field
2. Relevant historical incidents visually move toward the current incident node
3. Reveal: **"Similar incident detected"**

This is the visual proof, in the product experience, of the matching pipeline described in Section 3 — the animation should map exactly to what the system is actually doing (querying signatures, ranking by similarity), not just look impressive.

---

## 8. What This Engine Must NOT Do

Consistent with `rules.md` Section 5 (Boundaries of AI):

- Must not treat a historical match as proof — it's supporting evidence only
- Must not suppress an alert silently — every suppression is logged with the matched historical incident ID for audit
- Must not let historical patterns grow stale unreviewed — a periodic review process (even manual, at portfolio scale) should re-check whether old false-positive patterns are still valid
- Must not store raw sensitive telemetry in the signature — only the abstracted feature vector, never raw request payloads or user data

---

## 9. Evaluation Metrics for This Engine

| Metric | What it proves |
|---|---|
| Suppression precision | Of alerts suppressed, % that were correctly benign (not a missed real incident) |
| Suppression recall | Of all truly benign recurring patterns, % actually caught and suppressed |
| Confidence boost accuracy | When historical context raised confidence, was the final root cause actually correct more often than without it? |
| Retrieval latency | Time to query and rank top-k similar incidents — should stay well under 1 second at portfolio scale |

Report these numbers in your evaluation section alongside the correlation engine's own metrics — this engine needs its own proof, not a free pass because it "sounds like it should help."
