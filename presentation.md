# 📘 presentation.md

**Pitch & Presentation Deck Content — AIOps Root Cause Correlator**

One honest flag before this: the "challenges faced" section below covers the genuine, inherent engineering difficulty of this architecture — the hard parts you *will* hit once building starts. It is not a list of specific bugs you've already debugged, because nothing has been built yet. Once you actually implement this, replace the generic difficulty descriptions with your real specific war stories — those are always more convincing in an interview than a generic one.

---

## 1. The One-Line Pitch

> "An AI-powered system that automatically finds the root cause of production incidents in distributed systems — using statistical anomaly detection and graph-based correlation, not just an LLM guessing from logs."

---

## 2. The Problem (30-second version)

- Modern applications run as dozens of interdependent microservices.
- When one service fails, the failure cascades — one real cause can trigger 50–200+ alerts across dependent services within seconds.
- Engineers spend 1–4 hours manually tracing which alert is the cause and which are symptoms. This is measurable, expensive, and universal — every company running microservices has this problem.
- Real-world cost example worth citing: Zillow's home-pricing model drift in 2021 cost the company over $500M because a production model issue went undetected for too long — the broader class of "we didn't catch it fast enough" production failures is not hypothetical, it's a recurring, expensive category of incident.

---

## 3. The Solution (60-second version)

A four-layer pipeline:

1. **Detection** — statistical anomaly scoring (z-score + adaptive EWMA baselines) per service, per metric. No ML black box here — deliberately deterministic and explainable.
2. **Correlation** — a graph-based engine that walks the real service dependency graph backward from symptoms to find the earliest anomaly with no anomalous upstream cause. Handles multiple simultaneous, unrelated incidents correctly using connected-component analysis.
3. **Intelligence** — historical memory (suppress known-benign recurring patterns), blast radius prediction (forecast what fails next), and a counterfactual simulator (test whether a fix would have prevented the cascade).
4. **Explanation** — a thin LLM layer that only narrates the structured result already produced by the layers above. It never performs detection or correlation itself.

**The one sentence that matters most in an interview:**
> "Detection and correlation are 100% deterministic statistics and graph algorithms. The LLM's only job is writing the final paragraph — that's the opposite of most AI-for-DevOps projects, which are just LLM wrappers around raw logs."

---

## 4. Why This Is Hard (Genuine Technical Difficulty)

### 4.1 Multi-root-cause separation is a real graph problem, not a formality
Deciding whether two failing services share a root cause or are coincidentally failing at the same time requires reasoning about the dependency graph's actual topology, not just clustering by time window. The hardest case — two independent failures that happen to cascade toward the same downstream service — genuinely can produce a wrong merge if the algorithm isn't careful about edge direction and upstream-anomaly checks. This is the single hardest correctness problem in the whole system.

### 4.2 Getting the anomaly threshold right is a moving target
A fixed threshold either drifts stale (too sensitive after organic traffic growth) or misses real incidents (too lenient after being loosened to reduce noise). An EWMA-based adaptive baseline solves this in principle, but tuning the decay factor (alpha) so it adapts to legitimate growth *without* becoming blind to genuinely gradual incidents (like a slow memory leak) is a real trade-off with no universally correct answer — it has to be validated against real injected scenarios, not picked arbitrarily.

### 4.3 False-positive suppression can silently hide real incidents if built carelessly
The suppression engine's entire value depends on precision — if the similarity threshold is too loose, it will suppress a real incident that merely resembles a past benign pattern. This is the one component in the system where a bug doesn't just produce a wrong answer, it produces silence, which is worse. This is why suppression precision/recall gets tracked as its own explicit metric rather than folded into overall accuracy.

### 4.4 Building a real dependency graph from live traces is harder than hardcoding one
It's trivial to hand-write a dependency graph in code. It's a different problem to derive that graph correctly from live OpenTelemetry trace data, where request paths can be inconsistent, partially instrumented, or asynchronous (message-queue-based calls don't show up as simple parent-child trace spans the way synchronous HTTP calls do).

### 4.5 Keeping the LLM layer thin requires discipline, not just intention
It's easy to let the LLM layer creep into doing more — asking it to "also double check the root cause" or "suggest which one seems more likely" turns it back into the black-box wrapper this project is explicitly trying to avoid. Enforcing that boundary architecturally (the LLM prompt never receives raw anomaly data, only the already-computed structured result) is a discipline problem as much as a code problem.

### 4.6 Real Kubernetes + Chaos Mesh integration adds a full second skill domain
Everything above is an algorithms/backend problem. Getting a real cluster, Prometheus scraping, and Chaos Mesh fault injection actually working reliably is a separate infrastructure skill — YAML manifests, Helm chart configuration, and cluster networking debugging are a genuinely different kind of difficulty than the Python engine code, and usually the more time-consuming one in practice for someone newer to Kubernetes.

---

## 5. Anticipated "Issues Faced" — Fill These In With Real Specifics Once Built

Use this structure once you're actually building — each entry should end up with a real specific fix, not a generic description:

| Area | Likely issue category | What to document once it happens |
|---|---|---|
| Correlation engine | Adversarial multi-incident case incorrectly merged | Which scenario exposed it, what graph logic was wrong, what fixed it |
| Detection thresholds | False positives during initial EWMA warm-up period (no baseline yet) | How you handled the cold-start problem — e.g. a minimum warm-up window before flagging |
| Suppression engine | A real incident was suppressed because it resembled a benign pattern too closely | What threshold you had to raise, and the precision/recall trade-off you accepted |
| Kubernetes | A specific manifest, networking, or Helm chart issue that blocked cluster setup | The actual error and the actual fix — this is the most interview-relevant kind of detail |
| Chaos Mesh | A chaos experiment not behaving as expected (e.g. didn't actually reproduce the intended failure) | What you changed in the experiment definition |
| Evaluation | A specific scenario your system got wrong | Root cause of the miss, and whether you fixed it or documented it as a known limitation |

**Interview tip:** the most convincing answer to "what was the hardest part" is always a specific, technical, slightly self-critical story — not "everything was challenging." Fill this table in honestly as you build, and pick one entry to tell in depth during interviews.

---

## 6. What Makes This Stand Out (Differentiation Summary)

| Most student AI/DevOps projects | This project |
|---|---|
| LLM summarizes raw logs | Zero LLM calls in detection/correlation; LLM only narrates a pre-computed result |
| Single-incident assumption | Explicitly handles and tests multiple simultaneous independent incidents |
| Static thresholds | Adaptive, drift-aware baselines, validated against organic-growth scenarios |
| No suppression / high alert noise | Historical-memory-based suppression, measured with its own precision/recall |
| Reactive only | Predictive blast-radius forecasting, tested against an early-cascade checkpoint |
| Simulated data only | Real Kubernetes cluster, real Prometheus scraping, real Chaos Mesh fault injection |
| One accuracy number, unverified | 30 ground-truth scenarios, full metric breakdown, honest reporting of misses |

---

## 7. Suggested Pitch Structure (for a 5-minute presentation slot)

1. **Hook (30s):** the alert-storm problem, with the Zillow-style cost example
2. **Solution overview (60s):** the four-layer pipeline, emphasize the "zero LLM calls for detection" line
3. **Live or recorded demo (90s):** trigger a failure, show detection → correlation → root cause reveal
4. **The hard part (60s):** pick ONE of the technical difficulties from Section 4 and go deep — depth beats breadth here
5. **Evaluation numbers (45s):** state your real top-1/top-3 accuracy and suppression precision/recall, including any honest miss
6. **Close (15s):** what you'd build next (Kubernetes/Chaos Mesh integration, or the counterfactual simulator, depending on what's actually done) and the GitHub link

---

## 8. Anticipated Q&A — Prepare Answers For These

| Likely question | What to have ready |
|---|---|
| "Why not just use an LLM for everything?" | Cost, latency, and explainability — a deterministic algorithm can be audited and its accuracy measured; an LLM's reasoning cannot be verified the same way |
| "How do you know your accuracy numbers are real and not overfit to your own test scenarios?" | Be honest: these are your own injected scenarios, not an external benchmark — state this as a known limitation, and mention what an external validation would look like (real production traces, if you had access) |
| "What happens if two engines disagree?" | Explain the confidence-scoring approach and how the system communicates uncertainty rather than forcing a single answer |
| "Could this scale to hundreds of services?" | Acknowledge the graph algorithms are polynomial in service count and connected-components analysis remains efficient at scale, but note that real-time processing at very high event volume would need the Kafka/message-queue layer discussed in `features.md`, not the current in-process design |
| "What was the hardest bug you hit?" | Use your filled-in Section 5 table — a specific, real story |
