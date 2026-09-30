# ADR 002: Apache Kafka (KRaft Mode) as Event Backbone vs. Synchronous REST Ingestion

## Status
**Accepted**

## Context
High-velocity telemetry streams (CPU, memory, latency, database connection pools) produce thousands of data points per second across production clusters. Directly pushing telemetry over synchronous HTTP REST to the correlation engine introduces severe architectural risks:
1. **API Thread Starvation**: An alert storm overwhelms FastAPI worker threads, causing dropped metrics and connection timeouts.
2. **Coupling**: If the analysis engine undergoes maintenance or restarts, telemetry data is lost.
3. **Audit Immutability**: Compliance requires an unalterable event log of every incident detected and remediation action approved.

## Decision
We adopted **Apache Kafka in KRaft mode (ZooKeeper-free)** as the central event backbone:
- **Decoupled Telemetry Topic (`service.telemetry`)**: Microservices publish metric samples asynchronously; our `aiokafka` consumer reads at its own rate with backpressure tolerance.
- **Incident Lifecycle Topics**: `incident.detected` and `incident.updated` publish structured incident states to downstream subscribers (Slack notifiers, PagerDuty, dashboards).
- **Dead Letter Queue (`service.telemetry.dlq`)**: Malformed or poisoned payloads are diverted to a dedicated DLQ topic without crashing consumer loops.
- **Audit Stream (`audit.events`)**: All human approval decisions are committed to an append-only Kafka topic.

## Consequences
### Positive
- **Zero Ingestion Loss**: Buffered partition log handles traffic surges without dropping data.
- **Event Replayability**: Engineers can replay historical Kafka topic offsets to debug algorithms against historical production outages.
- **Sub-Millisecond Producer Overhead**: Asynchronous non-blocking message emission for monitored microservices.

### Negative
- Requires maintaining a Kafka cluster (mitigated by lightweight KRaft single-node mode in development and Docker Compose).
