# 📋 Changelog

All notable changes to the **AIOps Root Cause Correlator** platform are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-10-24

### Added
- Verified 16-stage pipeline telemetry, documentation annotations, and latency tracking headers.
- **Linux eBPF CO-RE Kernel Telemetry (`EbpfKernelProbeEngine`):** Zero-instrumentation kernel kprobe and tracepoint inspection (`syscalls:sys_enter_futex`, `tcp:tcp_retransmit_skb`, `sched:sched_switch`, `inet_csk_accept`) over `GET /api/v1/diagnostics/ebpf/{service_id}`.
- **OpenTelemetry OTLP/HTTP `/v1/traces` Receiver (`OtlpTraceReceiver`):** Standards-compliant OpenTelemetry JSON trace receiver (`POST /api/v1/diagnostics/otlp/v1/traces`) with nanosecond-to-millisecond span normalization and interval-merged critical-path decomposition.
- **Progressive Trust & Remote Admin Investigation Mode:**
  - HMAC-SHA256 signed Magic-Link Incident Dossiers.
  - Zero-setup scannable QR Code (`?mode=mobile-admin`) for instant smartphone approval.
  - Multi-channel phone push dispatch (Discord & Slack incoming webhooks + SMTP email).
  - 15-minute investigation hold timer (`👀 Acknowledge & Pause Timer`).
  - 1% shadow dry-run execution sandbox.
  - Unreachable-admin 5% canary break-glass fallback.
- **Principal SRE Interview Playbook (`docs/PRINCIPAL_SRE_INTERVIEW_PLAYBOOK.md`):** Complete 90-second demo script, resume bullets, and system design winning answers.
- **AIOps End-to-End Sequence Diagram:** Real-time triage lifecycle visual added to `README.md`.

---

## [1.1.0] - 2026-10-12

### Added
- **24-Hour Fourier Harmonic Diurnal EWMA Baseline (`DiurnalSeasonalBaseline`):** 2-harmonic Fourier series modeling predictable diurnal traffic peaks to eliminate morning false alarms.
- **MicroRCA++ Edge-Weighted Personalized PageRank (`CorrelationEngine`):** Log-scaled RPS and empirical metric covariance edge weighting to eliminate ingress hub bias.
- **Online Thompson Sampling Bandit (`ThompsonSamplingRunbookBandit`):** Beta-Bernoulli multi-armed bandit for online runbook ranking and MTTR reduction.
- **Automated Chaos GameDay Scenario Runner (`ChaosGameDayEngine`):** 4-stage crisis drill orchestration measuring live MTTD, MTTI, and MTTR.
- **5% Canary Safety Circuit-Breaker:** High-risk remediation gating with automated gRPC rollback on health degradation.

---

## [1.0.0] - 2026-10-04

### Added
- Initial release of **AIOps Root Cause Correlator**.
- 8-microservice directed acyclic dependency topology.
- Real-time Winsorized EWMA statistical anomaly detector.
- Apache Kafka event streaming backbone in KRaft mode.
- Sub-millisecond gRPC diagnostic mesh (`:50051`) with Protocol Buffers.
- Strawberry GraphQL control plane (`/graphql`).
- Interactive React 18 dashboard with Three.js 3D WebGL neural topology mesh.
- 30-scenario ground-truth synthetic benchmark suite with 100% Top-1 causal accuracy.
