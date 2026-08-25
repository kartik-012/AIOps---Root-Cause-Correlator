# 📘 features.md

**Advanced Feature Specification — AIOps Root Cause Correlator**
**Scope: Tier 1 (core differentiators), Tier 2 (extended capabilities), and Kubernetes/Prometheus integration**



## Overview

The base system performs statistical anomaly detection and graph-based root-cause correlation. The features below extend it from a detection tool into a predictive, self-improving incident intelligence platform. Each feature is scoped with its engineering rationale, functional behavior, and the production concern it addresses — written as it would appear in an internal design document ahead of implementation sign-off.



## TIER 1 — Core Differentiating Features

### 1.1 Multi-Root-Cause Detection

**Problem statement:** Production incidents are not always singular. Two or more services can fail independently and concurrently, with no causal relationship between them. A correlation engine that assumes a single root cause will either merge unrelated failures into one incorrect hypothesis, or arbitrarily pick one failure and ignore the other.

**Engineering approach:** The anomaly subgraph — the set of currently-anomalous services and their real dependency edges — is decomposed using connected-component analysis. Each connected component is treated as an independent incident and receives its own root-cause analysis. This guarantees that unrelated failures are never conflated, regardless of how close together they occur in time.

**Why this matters for evaluation:** This is validated directly against six dedicated multi-incident scenarios (see `evaluation-scenarios.md`, items 19–24), including a deliberately adversarial case where two independent failures cascade toward the same downstream service — the hardest separation case in the set.



### 1.2 False-Positive Suppression via Historical Memory

**Problem statement:** Alert fatigue is not solved by detecting more anomalies — it is solved by correctly ignoring the ones that don't matter. Recurring benign patterns (scheduled batch jobs, daily traffic peaks) will otherwise generate the same false alarm indefinitely.

**Engineering approach:** Every resolved incident is stored with a fixed-length anomaly signature (time-of-day, service, metric type, severity, propagation depth and speed). When a new anomaly is detected, its signature is compared via cosine similarity against the store of signatures previously marked as false positives by a human reviewer. A similarity above threshold results in suppression; the event is still logged, never silently dropped, satisfying the platform's no-silent-failure principle.

**Why this matters for evaluation:** Suppression precision and recall are tracked as first-class metrics, not assumed. A suppression engine that hides a real incident is worse than no suppression at all — this is measured explicitly, not asserted.



### 1.3 Blast Radius Prediction

**Problem statement:** By the time a cascade has fully propagated, the incident is already at its worst. There is measurable value in predicting which services are about to be affected before that happens, giving on-call engineers a head start.

**Engineering approach:** Given the currently-anomalous services and the rate at which anomalies are appearing across the dependency graph, the engine performs a forward walk from each anomalous node, scoring downstream services by graph distance and current anomaly-spread velocity. Output is a ranked list of predicted next-affected services with an estimated time-to-impact and a confidence score — not a binary yes/no.

**Why this matters for evaluation:** Prediction accuracy is tested at an early cascade checkpoint (evaluation scenario 29) and against a deliberately contained, non-cascading failure (scenario 30) to confirm the engine does not over-predict spread where none will occur.



### 1.4 Counterfactual "What-If" Simulator

**Problem statement:** Root-cause analysis explains what happened. It does not, by default, explain what would have prevented it. Without a causal counterfactual capability, remediation recommendations remain guesswork.

**Engineering approach:** Given a completed incident and a user-specified modification to one parameter (for example, capping a service's latency at a fixed value), the correlation engine is re-run against the modified synthetic trace. The system reports whether the original cascade would still have occurred under the modified condition. This operates on replay data, not live production traffic, to keep the blast radius of the feature itself contained.

**Why this matters for evaluation:** This is the feature most likely to be raised in an interview as evidence of causal, not merely correlational, reasoning — the distinction is worth being able to explain clearly.



## TIER 2 — Extended Platform Capabilities

### 2.1 Live Incident Streaming (WebSocket Dashboard)

**Problem statement:** A static, request-response dashboard cannot convey an incident as it unfolds. Engineers investigating a live outage need to see anomalies, correlation results, and predictions update in real time, not on a refresh cycle.

**Engineering approach:** A dedicated WebSocket endpoint streams three event types to connected clients — anomaly detection, incident correlation, and blast radius updates — as they are produced by the backend pipeline. The frontend subscribes once per session; no polling is used at any layer.



### 2.2 Auto-Generated Runbook Suggestions

**Problem statement:** Identifying a root cause is only half the operational value. Without a suggested next action, the system still leaves the engineer to independently determine remediation.

**Engineering approach:** Each root-cause type is mapped, via a curated and version-controlled JSON library, to a suggested remediation action. The suggestion is surfaced alongside the root-cause result but is explicitly advisory — no endpoint in the system executes a remediation action automatically. Every suggestion requires explicit human approval before being marked as actioned, consistent with the platform's human-in-the-loop principle for high-impact operations.



### 2.3 Severity-Weighted Business Impact Scoring

**Problem statement:** Not all incidents carry equal operational weight. A failure in a low-traffic notification service is not equivalent to a failure in the payment path, even if their raw anomaly severity scores are similar.

**Engineering approach:** Each service carries a configurable revenue-weight attribute. The impact score for an incident is computed as a function of anomaly severity, the affected service's revenue weight, and the number of downstream services depending on it. This produces a single, sortable impact number that can be used to triage multiple concurrent incidents by business consequence rather than raw technical severity alone.



### 2.4 Drift-Aware Detection Thresholds

**Problem statement:** A static anomaly threshold, tuned once, will either become too sensitive as legitimate traffic grows, or too lenient as it ages. Both outcomes degrade detection quality over time without any code change having occurred.

**Engineering approach:** Per-service, per-metric baselines are maintained using an exponentially weighted moving average rather than a fixed rolling window. The baseline continuously adapts to genuine, gradual shifts in normal behavior while still flagging sudden deviations. This is validated directly against a dedicated evaluation scenario (item 27) simulating two weeks of legitimate, gradual traffic growth, confirming the engine does not misclassify organic growth as an incident.



## KUBERNETES & PROMETHEUS INTEGRATION

### 3.1 Rationale

A synthetic, purely in-memory data generator demonstrates the algorithms in isolation but does not demonstrate operational familiarity with the environment these systems actually run in. Integrating with a real Kubernetes cluster and a real Prometheus metrics pipeline moves the project from an academic simulation to a system exercised against production-representative infrastructure.

### 3.2 Cluster & Deployment

- A local Kubernetes cluster (Minikube or Kind) hosts six to eight independently deployed microservices representing a realistic e-commerce topology: authentication, product catalog, inventory, payment, order orchestration, notification, shipping, and an API gateway.
- Each service is containerized individually and deployed via standard Kubernetes manifests, managed through Helm where appropriate.

### 3.3 Metrics Pipeline

- Prometheus is deployed via the community Helm chart (`kube-prometheus-stack`) and configured to scrape latency, error rate, CPU, and memory metrics from each service pod at a fixed interval.
- Where request-level dependency data is required rather than assumed, OpenTelemetry instrumentation combined with Jaeger provides real distributed tracing, from which the service dependency graph can be derived directly rather than hardcoded.

### 3.4 Failure Injection

- Chaos Mesh is used to inject real, controlled failures directly into the running cluster — pod termination, network latency injection, and CPU/memory stress — rather than simulating these conditions in application code. This is what allows the evaluation scenario set to be executed against genuine infrastructure behavior rather than a synthetic approximation of it.

### 3.5 Operational Boundary

- The Kubernetes and Prometheus integration constitutes the test environment and telemetry source. It is deliberately kept separate from the core product (the detection, correlation, suppression, and prediction engines), which remain infrastructure-agnostic and could equally be pointed at a different metrics source in a real deployment. This separation is reflected directly in the repository structure (`simulator/` versus `backend/`).

---

## Summary Table

| Feature | Tier | Primary Engineering Concern |
|---|---|---|
| Multi-root-cause detection | 1 | Correctness under concurrent independent failures |
| False-positive suppression | 1 | Alert fatigue reduction, measured not assumed |
| Blast radius prediction | 1 | Predictive, not purely reactive, detection |
| Counterfactual simulator | 1 | Causal reasoning beyond correlation |
| Live WebSocket streaming | 2 | Real-time operational usability |
| Runbook suggestions | 2 | Closing the loop from detection to action, safely |
| Business impact scoring | 2 | Triage by consequence, not raw severity |
| Drift-aware thresholds | 2 | Long-term detection stability |
| Kubernetes + Prometheus | Infra | Production-representative validation environment |
