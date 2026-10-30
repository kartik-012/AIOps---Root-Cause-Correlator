# 🏆 Principal SRE Portfolio & System Design Interview Playbook

This guide is designed to help you present **AIOps Root Cause Correlator** in Staff/Principal/Senior Backend & SRE interviews at companies like **Datadog, Cloudflare, Stripe, Netflix, Uber, Google, and Anthropic**.

---

## 🎬 1. The 90-Second "Two-Screen + Real Smartphone" Demo Script

Hiring managers and Staff Engineers spend ~60–90 seconds reviewing a live demo. Follow this exact sequence when recording your Loom/OBS video or presenting live on Zoom:

| Timestamp | Action on Screen | What You Say Out Loud |
| :--- | :--- | :--- |
| **0:00 – 0:20** | Click **🔥 Run Full 4-Stage GameDay** in the top Chaos Studio toolbar. | *"During a microservice outage, 50+ dependent services page on-call engineers simultaneously. Watch my deterministic engine inject a database connection pool saturation into `payment-service`, detect the deviation via a 24-hour Fourier harmonic EWMA baseline, and isolate the root cause in 41 milliseconds."* |
| **0:20 – 0:45** | In **Evidence & Kernel Attribution**, click **OTel Spans**, click **⚡ Push OTLP /v1/traces**, then switch to **🐧 eBPF**. | *"Rather than passing raw logs to an LLM that can hallucinate, my `/v1/traces` OTLP receiver computes interval-merged exclusive span duration—pinpointing the exact `SELECT ... FOR UPDATE` query taking 865ms—and correlates it with Linux eBPF `sys_enter_futex` kernel probes to prove threads are blocked on DB sockets while CPU run-queue latency is a healthy 58 microseconds."* |
| **0:45 – 1:15** | Click **🛡️ Remote Admin Investigation & Governance** in the Runbook Panel. Hold your **real phone** up, scan the **QR Code**, and tap **👀 Acknowledge & Pause Timer** $\to$ **🧪 Run 1% Shadow Dry-Run** $\to$ **✅ Approve 5% Safe Canary**. | *"For high-risk production remediations when the Principal SRE is away from their laptop, the engine generates an HMAC-SHA256 signed Mobile Incident Dossier. Scanning this QR code or clicking the Discord/Slack push opens the standalone mobile view on my phone—allowing me to pause the escalation timer while investigating, run a 1% shadow dry-run, and approve a 5% canary rollout with automatic gRPC rollback—all syncing back to the command center over WebSockets in real time."* |
| **1:15 – 1:30** | Click **30-Scenario Benchmark 📊** in the top nav. | *"Every algorithm is backed by a 30-scenario ground-truth benchmark achieving 100% Top-1 root-cause accuracy with 95% Wilson confidence intervals and 118 automated unit tests."* |

---

## 📄 2. High-Impact Resume Bullets (Copy-Paste Ready)

**AIOps Root Cause Correlator — Autonomous Causal Inference & eBPF/OTel Observability Platform**
- **Deterministic Causal Isolation & eBPF/OTLP Telemetry:** Engineered a distributed root-cause correlator combining **24-hour Fourier harmonic EWMA anomaly detection**, **MicroRCA++ edge-weighted Personalized PageRank**, **OpenTelemetry OTLP `/v1/traces` critical-path exclusive span attribution**, and **Linux eBPF CO-RE kernel probes (`sys_enter_futex`, `tcp_retransmit_skb`)**, achieving **100% Top-1 accuracy** across 30 cascading failure benchmarks with **$<45\text{ms}$ $p_{99}$ latency** on 100-node DAGs.
- **High-Throughput Multi-Protocol Streaming Backbone:** Built a lock-free **10K-event ring buffer with 80% high-watermark adaptive backpressure**, orchestrating real-time telemetry across **Apache Kafka (KRaft)**, **gRPC/Protobuf health probes (`:50051`)**, **Strawberry GraphQL**, and **WebSockets**.
- **Closed-Loop Canary Remediation & Cryptographic Mobile Governance:** Designed an **Online Thompson Sampling Beta-Bernoulli Bandit** for runbook ranking paired with an **HMAC-SHA256 out-of-band mobile approval workflow** (scannable QR/Webhook dossier, **Investigation Hold Timer**, **1% Shadow Dry-Run**, and **5% Canary Circuit-Breaker** with automatic rollback).

---

## 🧠 3. Top 4 Staff/Principal System Design Interview Questions & Winning Answers

### Q1: *"Why didn't you just use an LLM Agent to read the logs and trigger the runbook?"*
> **Winning Answer:**
> *"Three reasons: **Latency, Determinism, and Blast-Radius Safety**. During an alert storm with 50,000 events/sec, calling an LLM takes 4–12 seconds per inference, costs thousands of dollars, and can hallucinate a destructive restart on a downstream victim service like `api-gateway`. Instead, I use deterministic math—Fourier Diurnal EWMA + Edge-Weighted Personalized PageRank + OTel Exclusive Span Attribution + eBPF Kernel Probes—to isolate the root cause in under 45 milliseconds. I only use the LLM at the end to synthesize a human-readable executive post-mortem guarded by a strict citation verifier, and high-risk remediations are gated by a Thompson Sampling bandit, a 1% shadow dry-run, and an HMAC-signed 5% canary circuit-breaker."*

### Q2: *"How do you prevent hub bias in PageRank so `api-gateway` isn't blamed for every outage?"*
> **Winning Answer:**
> *"Standard PageRank treats all edges uniformly, which causes high-degree ingress hubs like `api-gateway` to accumulate disproportionate probability mass. I implemented **MicroRCA++ dynamic edge weighting** where each directed edge $(u \to v)$ is weighted by $\log(1 + \text{RPS}_{u,v}) \times \text{Cov}(M_u, M_v)$ and the personalization vector biases random walks toward downstream leaf candidates with zero anomalous callees (`out_degree_anomalous == 0`) plus a temporal precedence decay factor $\exp(-\lambda \Delta t)$."*

### Q3: *"How does your anomaly detector avoid paging on-call engineers every morning at 9:00 AM when traffic naturally spikes?"*
> **Winning Answer:**
> *"A static threshold or plain EWMA triggers false positives during predictable daily traffic ramps. My `DiurnalSeasonalBaseline` models the 24-hour cycle using a 2-harmonic **Fourier series** ($\mu + \sum_{k=1}^2 [a_k \sin(k\omega t) + b_k \cos(k\omega t)]$) combined with Winsorized EWMA variance clamping. A 400 RPS surge at 9:00 AM matches the expected diurnal curve ($z < 1.2\sigma$), whereas the exact same 400 RPS surge at 3:00 AM deviates from the seasonal baseline ($z > 4.5\sigma$) and immediately triggers correlation."*

### Q4: *"What happens if a high-risk incident occurs while the Principal Admin is on an airplane or investigating?"*
> **Winning Answer:**
> *"I designed a **Progressive Trust & Admin Investigation State Machine**. First, the Admin receives an HMAC-SHA256 signed **Mobile Incident Dossier** on their phone via QR code, Slack/Discord webhook, or email. If they need time to inspect the evidence, tapping **Acknowledge & Pause Timer** transitions the session to `INVESTIGATING_HOLD` for 15 minutes and lets them run a **1% Shadow Dry-Run** from their phone. Second, if the Admin is completely unreachable (e.g., on a flight) and SLA burn exceeds critical thresholds after the 5-minute dead-man timer expires, the on-call engineer can invoke **Break-Glass**, which is strictly hardware-capped to a **5% Safe Canary** guarded by the automatic gRPC rollback circuit-breaker—never a blind 100% cluster mutation."*

---

## ⚡ 4. Rapid-Fire Technical Metric Cheat Sheet

| Engineering Dimension | Production Metric | Verification Method |
| :--- | :--- | :--- |
| **Top-1 Causal Accuracy** | `100.0%` (30 / 30) | Wilson score interval ($z=1.96$, 95% CI: `[88.6%, 100%]`) |
| **P99 Inference Latency** | `< 45ms` (100-node DAG) | Single-pass sparse matrix Laplacian vector walks |
| **Ingestion Throughput** | `10,000 events/sec` | Lock-free bounded ring buffer with 80% watermark backpressure |
| **Kernel Verification** | `Zero-instrumentation` | Linux eBPF CO-RE (`sys_enter_futex`, `tcp_retransmit_skb`) |
| **Automated Test Coverage** | `118 unit & e2e tests` | Pytest with async fixtures across all 4 tier services |



---

## 🚦 5. SRE Incident Severity & Escalation Matrix

| Severity Tier | Revenue Impact | Automated Action | Governance Approval |
| :--- | :--- | :--- | :--- |
| **P1 - Critical** | > $5,000 / min | 1% Shadow Dry-Run + Mobile Alert | Principal SRE QR / Break-Glass 5% Canary |
| **P2 - Degraded** | $500 - $5,000 / min | Fourier EWMA Anomaly Isolation | Thompson Sampling Ranked Runbook |
| **P3 - Warning** | < $500 / min | Telemetry Suppression (Cosine Memory) | SRE Auto-Resolution with Audit Log |

<!-- Revision 2026.10: Staff SRE System Design & Real-Time Incident Correlator -->
