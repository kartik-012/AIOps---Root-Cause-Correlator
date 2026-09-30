# ADR 003: gRPC Diagnostic Microservice Mesh vs. HTTP REST for Real-Time Verification

## Status
**Accepted**

## Context
When the causal graph correlation engine flags a suspect service (e.g. `payment-service`) during a cascading incident, the system must perform an authoritative runtime health check to confirm container-level metrics (active DB connections, thread count, error rate, p95 latency).

Using standard HTTP/1.1 REST endpoints for internal microservice diagnostics has key drawbacks:
1. **Serialization Latency**: JSON serialization/deserialization creates CPU overhead during active outages.
2. **Lack of Strict Contracts**: Ad-hoc REST endpoints drift in schema across microservice teams.
3. **Connection Overhead**: HTTP/1.1 requires new TCP handshakes or inefficient keep-alives compared to multiplexed HTTP/2 streams.

## Decision
We implemented a dedicated **gRPC Diagnostic Service** using **Protocol Buffers (`diagnostics.proto`)**:
- **Strong Typing**: Strict contract defining `HealthRequest`, `HealthResponse`, `ResourceRequest`, and server-side streaming `StreamMetrics`.
- **Multiplexed HTTP/2 Transport**: Low-latency, binary-encoded RPCs operating over port `50051`.
- **Dynamic Verification Engine**: When the RCA engine isolates a suspect, it executes a gRPC `GetHealthStatus` query:
  - If gRPC confirms critical metrics: confidence boosted (`+0.10`)
  - If gRPC reports healthy state: confidence penalized (`-0.15`) as a false-positive check.
  - If gRPC is unreachable: confidence unchanged and flagged as `UNREACHABLE`.

## Consequences
### Positive
- **Sub-Millisecond Verification**: Fast binary wire format avoids JSON parsing overhead.
- **Contract Enforcement**: Protobuf definitions version-controlled and shared across backend teams.
- **Bi-directional Capability**: Supports real-time metric streaming via server-side streaming RPCs.

### Negative
- Requires generating Python client/server stubs with `grpcio-tools`.
