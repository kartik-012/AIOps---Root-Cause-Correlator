# 📘 evaluation-scenarios.md

**Ground-truth injected failure scenarios — the dataset that produces your real accuracy metrics.**

Dependency graph used across all scenarios:
```
api-gateway → auth
api-gateway → product-catalog → inventory
api-gateway → order → payment
order → inventory
order → notification
order → shipping
```

Each scenario below has a known, documented ground truth. Running your pipeline against all of these and comparing output to the `ground_truth` field is what generates `top1_accuracy`, `top3_accuracy`, etc.

---

## Single Root-Cause Scenarios (1–18)

| # | Scenario | Injected Fault | Ground Truth Root Cause | Expected Cascade |
|---|---|---|---|---|
| 1 | DB pool exhaustion | `payment` DB connection pool maxed out | `payment` | order → api-gateway |
| 2 | Memory leak | `auth` gradual memory growth over 5 min | `auth` | api-gateway |
| 3 | CPU spike | `inventory` CPU pegged at 100% | `inventory` | product-catalog → order → api-gateway |
| 4 | Network latency injection | Artificial 500ms delay on `payment` | `payment` | order → api-gateway |
| 5 | Pod crash loop | `notification` pod repeatedly crashing | `notification` | order (partial degradation only) |
| 6 | Disk I/O saturation | `order` service disk writes saturated | `order` | payment, inventory, notification, api-gateway |
| 7 | Cold start storm | `shipping` scaled to zero, cold-start delay on burst traffic | `shipping` | order → api-gateway |
| 8 | Config error | `auth` deployed with wrong DB connection string | `auth` | api-gateway |
| 9 | Dependency timeout misconfig | `inventory` client timeout set too low | `inventory` | product-catalog → order → api-gateway |
| 10 | Cascading retry storm | `payment` slow → `order` retries amplify load | `payment` | order → api-gateway |
| 11 | Certificate expiry | `auth` TLS cert expired, all calls failing | `auth` | api-gateway |
| 12 | Rate limiter misfire | `api-gateway` rate limiter incorrectly triggered | `api-gateway` | none downstream (isolated) |
| 13 | Queue backlog | `notification` message queue backlog growing unbounded | `notification` | order (partial) |
| 14 | Bad deploy — regression | `product-catalog` new deploy introduces slow query | `product-catalog` | order → api-gateway |
| 15 | Resource limit misconfig | `payment` pod OOM-killed repeatedly (memory limit too low) | `payment` | order → api-gateway |
| 16 | DNS resolution failure | `inventory` service DNS intermittently failing | `inventory` | product-catalog → order → api-gateway |
| 17 | Connection leak (non-DB) | `shipping` HTTP client connections not released | `shipping` | order (partial) |
| 18 | Autoscaler misconfig | `order` autoscaler fails to scale under load | `order` | payment, inventory, notification, api-gateway |

---

## Multi-Root-Cause Scenarios (19–24) — tests connected-components logic

| # | Scenario | Injected Faults | Ground Truth Root Causes | Notes |
|---|---|---|---|---|
| 19 | Two independent failures | `auth` memory leak AND `shipping` pod crash, unrelated timing | `auth`, `shipping` | No dependency path between them — must NOT be merged into one incident |
| 20 | Simultaneous unrelated latency | `notification` queue backlog AND `product-catalog` slow query, same time window | `notification`, `product-catalog` | Tests time-window overlap without a shared cause |
| 21 | Coincidental overlap | `payment` DB pool exhaustion AND `auth` cert expiry within same 60s window | `payment`, `auth` | Both cascade to `api-gateway` independently — tests that correlation doesn't falsely link them via a shared downstream node |
| 22 | Three simultaneous | `inventory` CPU spike, `shipping` cold start, `notification` queue backlog, all within 90s | `inventory`, `shipping`, `notification` | Stress test for 3-way component separation |
| 23 | Cascading + independent combo | `payment` DB exhaustion (cascades to order/gateway) AND unrelated `auth` cert expiry (cascades to gateway) | `payment`, `auth` | Both cascades converge on `api-gateway` — hardest separation case in the set |
| 24 | Near-simultaneous same service type | Two different metric types anomalous on `order` at once (latency AND error rate) from genuinely one cause | `order` (single) | Negative test: confirms the engine does NOT over-split one real incident into two just because two metrics fired |

---

## False-Positive / Benign Scenarios (25–28) — tests suppression engine

| # | Scenario | Pattern | Expected System Behavior |
|---|---|---|---|
| 25 | Daily traffic surge | `api-gateway` latency rises every day at 9:00 AM due to real legitimate load | After first occurrence marked benign, subsequent occurrences suppressed |
| 26 | Weekly batch job | `inventory` CPU spikes every Sunday during scheduled batch reconciliation | Suppressed after first labeled occurrence |
| 27 | Seasonal legitimate growth | `order` latency baseline gradually rising over 2 weeks due to real traffic growth | EWMA drift-aware threshold should NOT flag this as anomalous — tests Section 1's core purpose |
| 28 | One-off manual maintenance | `shipping` intentionally taken down for planned maintenance (tagged in advance) | Suppressed via explicit maintenance-window tag, not similarity matching |

---

## Blast Radius Prediction Test Cases (29–30)

| # | Scenario | Setup | Ground Truth |
|---|---|---|---|
| 29 | Early-stage cascade | Inject `payment` failure, capture system state at T+10s (before full cascade completes) | Correct prediction: `order` next at ~T+15s, `api-gateway` at ~T+25s |
| 30 | Contained failure (negative test) | Inject `notification` queue backlog which historically stays contained, does not cascade | Correct prediction: no further services predicted to be affected |

---

## How to Use This Set

1. Run all 30 scenarios through the pipeline, one at a time, with the historical memory store empty at the start (except scenarios 25–28, which need one "seed" occurrence marked benign before testing suppression).
2. Log actual system output vs. `ground_truth` for each.
3. Compute:
   - **Top-1 accuracy** = correct root cause in scenarios 1–24 / 24
   - **Multi-incident separation accuracy** = correctly separated incidents in 19–24 / 6
   - **Suppression precision/recall** = from scenarios 25–28
   - **Blast radius accuracy** = from scenarios 29–30
4. Report every number, including the weak ones — a system that gets 100% on this exact test set and nothing else is suspicious in an interview; a system that gets 78% with an honest explanation of the 3 misses is credible.
