"""Generates all 30 ground-truth synthetic test scenario fixtures.

Saves fixtures to tests/fixtures/synthetic_scenarios/
"""

import json
import os
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "synthetic_scenarios"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# Standard microservices topology
SERVICES = [
    {"id": "api-gateway", "name": "API Gateway", "revenue_weight": 10.0},
    {"id": "auth", "name": "Auth Service", "revenue_weight": 7.0},
    {"id": "product-catalog", "name": "Product Catalog", "revenue_weight": 6.0},
    {"id": "inventory", "name": "Inventory Service", "revenue_weight": 8.0},
    {"id": "order", "name": "Order Service", "revenue_weight": 9.0},
    {"id": "payment", "name": "Payment Service", "revenue_weight": 10.0},
    {"id": "notification", "name": "Notification Service", "revenue_weight": 3.0},
    {"id": "shipping", "name": "Shipping Service", "revenue_weight": 4.0},
]

DEPENDENCIES = [
    {"from": "api-gateway", "to": "auth"},
    {"from": "api-gateway", "to": "product-catalog"},
    {"from": "product-catalog", "to": "inventory"},
    {"from": "api-gateway", "to": "order"},
    {"from": "order", "to": "payment"},
    {"from": "order", "to": "inventory"},
    {"from": "order", "to": "notification"},
    {"from": "order", "to": "shipping"},
]

SCENARIOS = [
    # 1-18 Single root cause
    {
        "id": 1,
        "name": "db_pool_exhaustion",
        "description": "Payment DB connection pool maxed out, cascading to order and api-gateway",
        "category": "single_root_cause",
        "injected_fault": {"service": "payment", "metric": "connection_pool", "z_score": 5.4, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 3.6, "severity": "high", "t_offset": 10},
            {"service": "api-gateway", "metric": "error_rate", "z_score": 3.1, "severity": "medium", "t_offset": 20},
        ],
        "ground_truth": {
            "root_cause_service": "payment",
            "root_cause_type": "db_connection_exhaustion",
            "affected_services": ["order", "api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 2,
        "name": "memory_leak",
        "description": "Auth gradual memory growth over 5 min causing pod slowdown",
        "category": "single_root_cause",
        "injected_fault": {"service": "auth", "metric": "memory_usage", "z_score": 4.8, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.2, "severity": "high", "t_offset": 15},
        ],
        "ground_truth": {
            "root_cause_service": "auth",
            "root_cause_type": "memory_leak",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 3,
        "name": "cpu_spike",
        "description": "Inventory CPU pegged at 100% cascading to product-catalog and order",
        "category": "single_root_cause",
        "injected_fault": {"service": "inventory", "metric": "cpu_usage", "z_score": 5.2, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "product-catalog", "metric": "latency_ms", "z_score": 3.8, "severity": "high", "t_offset": 8},
            {"service": "order", "metric": "latency_ms", "z_score": 3.4, "severity": "high", "t_offset": 14},
            {"service": "api-gateway", "metric": "error_rate", "z_score": 2.9, "severity": "medium", "t_offset": 22},
        ],
        "ground_truth": {
            "root_cause_service": "inventory",
            "root_cause_type": "cpu_spike",
            "affected_services": ["product-catalog", "order", "api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 4,
        "name": "network_latency_injection",
        "description": "Artificial 500ms delay on payment service",
        "category": "single_root_cause",
        "injected_fault": {"service": "payment", "metric": "latency_ms", "z_score": 4.2, "severity": "high", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 3.5, "severity": "high", "t_offset": 12},
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.0, "severity": "medium", "t_offset": 25},
        ],
        "ground_truth": {
            "root_cause_service": "payment",
            "root_cause_type": "network_latency_injection",
            "affected_services": ["order", "api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 5,
        "name": "pod_crash_loop",
        "description": "Notification pod repeatedly crashing",
        "category": "single_root_cause",
        "injected_fault": {"service": "notification", "metric": "restart_count", "z_score": 4.9, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "error_rate", "z_score": 2.6, "severity": "medium", "t_offset": 10},
        ],
        "ground_truth": {
            "root_cause_service": "notification",
            "root_cause_type": "pod_crash_loop",
            "affected_services": ["order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 6,
        "name": "disk_io_saturation",
        "description": "Order service disk writes saturated",
        "category": "single_root_cause",
        "injected_fault": {"service": "order", "metric": "disk_io", "z_score": 5.0, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.7, "severity": "high", "t_offset": 10},
        ],
        "ground_truth": {
            "root_cause_service": "order",
            "root_cause_type": "disk_io_saturation",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 7,
        "name": "cold_start_storm",
        "description": "Shipping scaled to zero, cold-start latency spike",
        "category": "single_root_cause",
        "injected_fault": {"service": "shipping", "metric": "latency_ms", "z_score": 3.9, "severity": "high", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 2.8, "severity": "medium", "t_offset": 12},
        ],
        "ground_truth": {
            "root_cause_service": "shipping",
            "root_cause_type": "cold_start_storm",
            "affected_services": ["order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 8,
        "name": "config_error",
        "description": "Auth deployed with wrong DB connection string",
        "category": "single_root_cause",
        "injected_fault": {"service": "auth", "metric": "error_rate", "z_score": 5.7, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "error_rate", "z_score": 4.1, "severity": "critical", "t_offset": 5},
        ],
        "ground_truth": {
            "root_cause_service": "auth",
            "root_cause_type": "config_error",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 9,
        "name": "dependency_timeout_misconfig",
        "description": "Inventory client timeout set too low",
        "category": "single_root_cause",
        "injected_fault": {"service": "inventory", "metric": "error_rate", "z_score": 4.3, "severity": "high", "t_offset": 0},
        "cascade": [
            {"service": "product-catalog", "metric": "error_rate", "z_score": 3.4, "severity": "high", "t_offset": 6},
            {"service": "order", "metric": "error_rate", "z_score": 3.1, "severity": "high", "t_offset": 12},
        ],
        "ground_truth": {
            "root_cause_service": "inventory",
            "root_cause_type": "config_error",
            "affected_services": ["product-catalog", "order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 10,
        "name": "cascading_retry_storm",
        "description": "Payment slow, order retries amplify load",
        "category": "single_root_cause",
        "injected_fault": {"service": "payment", "metric": "latency_ms", "z_score": 4.6, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "cpu_usage", "z_score": 4.1, "severity": "critical", "t_offset": 8},
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.5, "severity": "high", "t_offset": 18},
        ],
        "ground_truth": {
            "root_cause_service": "payment",
            "root_cause_type": "network_latency_injection",
            "affected_services": ["order", "api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 11,
        "name": "certificate_expiry",
        "description": "Auth TLS certificate expired",
        "category": "single_root_cause",
        "injected_fault": {"service": "auth", "metric": "error_rate", "z_score": 5.9, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "error_rate", "z_score": 4.5, "severity": "critical", "t_offset": 4},
        ],
        "ground_truth": {
            "root_cause_service": "auth",
            "root_cause_type": "config_error",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 12,
        "name": "rate_limiter_misfire",
        "description": "API Gateway rate limiter incorrectly triggered",
        "category": "single_root_cause",
        "injected_fault": {"service": "api-gateway", "metric": "error_rate", "z_score": 4.0, "severity": "high", "t_offset": 0},
        "cascade": [],
        "ground_truth": {
            "root_cause_service": "api-gateway",
            "root_cause_type": "config_error",
            "affected_services": [],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 13,
        "name": "queue_backlog",
        "description": "Notification message queue backlog unbounded",
        "category": "single_root_cause",
        "injected_fault": {"service": "notification", "metric": "queue_backlog", "z_score": 4.4, "severity": "high", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 2.5, "severity": "medium", "t_offset": 15},
        ],
        "ground_truth": {
            "root_cause_service": "notification",
            "root_cause_type": "unknown_anomaly",
            "affected_services": ["order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 14,
        "name": "bad_deploy_regression",
        "description": "Product catalog slow query deployment",
        "category": "single_root_cause",
        "injected_fault": {"service": "product-catalog", "metric": "latency_ms", "z_score": 4.7, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.3, "severity": "high", "t_offset": 12},
        ],
        "ground_truth": {
            "root_cause_service": "product-catalog",
            "root_cause_type": "network_latency_injection",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 15,
        "name": "resource_limit_misconfig",
        "description": "Payment pod OOM-killed due to low memory limit",
        "category": "single_root_cause",
        "injected_fault": {"service": "payment", "metric": "restart_count", "z_score": 5.1, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "error_rate", "z_score": 3.9, "severity": "high", "t_offset": 6},
            {"service": "api-gateway", "metric": "error_rate", "z_score": 3.1, "severity": "medium", "t_offset": 15},
        ],
        "ground_truth": {
            "root_cause_service": "payment",
            "root_cause_type": "pod_crash_loop",
            "affected_services": ["order", "api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 16,
        "name": "dns_resolution_failure",
        "description": "Inventory DNS lookup failures",
        "category": "single_root_cause",
        "injected_fault": {"service": "inventory", "metric": "error_rate", "z_score": 5.0, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "product-catalog", "metric": "error_rate", "z_score": 3.7, "severity": "high", "t_offset": 8},
            {"service": "order", "metric": "error_rate", "z_score": 3.2, "severity": "high", "t_offset": 14},
        ],
        "ground_truth": {
            "root_cause_service": "inventory",
            "root_cause_type": "config_error",
            "affected_services": ["product-catalog", "order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 17,
        "name": "connection_leak",
        "description": "Shipping service HTTP connection leak",
        "category": "single_root_cause",
        "injected_fault": {"service": "shipping", "metric": "connection_pool", "z_score": 4.5, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 2.7, "severity": "medium", "t_offset": 15},
        ],
        "ground_truth": {
            "root_cause_service": "shipping",
            "root_cause_type": "db_connection_exhaustion",
            "affected_services": ["order"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    {
        "id": 18,
        "name": "autoscaler_misconfig",
        "description": "Order service autoscaler fails to scale under traffic",
        "category": "single_root_cause",
        "injected_fault": {"service": "order", "metric": "cpu_usage", "z_score": 5.3, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.8, "severity": "high", "t_offset": 10},
        ],
        "ground_truth": {
            "root_cause_service": "order",
            "root_cause_type": "cpu_spike",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    # 19-24 Multi-root cause
    {
        "id": 19,
        "name": "dual_independent_cpu_memory",
        "description": "Auth memory leak AND shipping pod crash simultaneously",
        "category": "multi_root_cause",
        "injected_faults": [
            {"service": "auth", "metric": "memory_usage", "z_score": 4.6, "severity": "critical", "t_offset": 0},
            {"service": "shipping", "metric": "restart_count", "z_score": 4.2, "severity": "high", "t_offset": 3},
        ],
        "cascade": [],
        "ground_truth": {
            "root_cause_services": ["auth", "shipping"],
            "expected_incidents": 2,
            "is_false_positive": False,
        }
    },
    {
        "id": 20,
        "name": "triple_independent_failures",
        "description": "Three unrelated services fail simultaneously",
        "category": "multi_root_cause",
        "injected_faults": [
            {"service": "auth", "metric": "memory_usage", "z_score": 4.1, "severity": "high", "t_offset": 0},
            {"service": "inventory", "metric": "cpu_usage", "z_score": 4.8, "severity": "critical", "t_offset": 5},
            {"service": "shipping", "metric": "restart_count", "z_score": 3.9, "severity": "high", "t_offset": 8},
        ],
        "cascade": [],
        "ground_truth": {
            "root_cause_services": ["auth", "inventory", "shipping"],
            "expected_incidents": 3,
            "is_false_positive": False,
        }
    },
    {
        "id": 21,
        "name": "dual_converge_downstream",
        "description": "Adversarial: Payment AND Auth fail independently, both cascading to api-gateway",
        "category": "multi_root_cause",
        "injected_faults": [
            {"service": "payment", "metric": "connection_pool", "z_score": 5.0, "severity": "critical", "t_offset": 0},
            {"service": "auth", "metric": "error_rate", "z_score": 4.9, "severity": "critical", "t_offset": 4},
        ],
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 3.4, "severity": "high", "t_offset": 10},
            {"service": "api-gateway", "metric": "error_rate", "z_score": 4.0, "severity": "critical", "t_offset": 16},
        ],
        "ground_truth": {
            "root_cause_services": ["payment", "auth"],
            "expected_incidents": 2,
            "is_false_positive": False,
        }
    },
    {
        "id": 22,
        "name": "split_cluster_failure",
        "description": "Network partition: Inventory and Shipping fail in separate failure zones",
        "category": "multi_root_cause",
        "injected_faults": [
            {"service": "inventory", "metric": "latency_ms", "z_score": 4.4, "severity": "high", "t_offset": 0},
            {"service": "shipping", "metric": "latency_ms", "z_score": 4.1, "severity": "high", "t_offset": 6},
        ],
        "cascade": [],
        "ground_truth": {
            "root_cause_services": ["inventory", "shipping"],
            "expected_incidents": 2,
            "is_false_positive": False,
        }
    },
    {
        "id": 23,
        "name": "dual_config_errors",
        "description": "Payment DB pool and Auth cert expiry both fail at once",
        "category": "multi_root_cause",
        "injected_faults": [
            {"service": "payment", "metric": "connection_pool", "z_score": 5.2, "severity": "critical", "t_offset": 0},
            {"service": "auth", "metric": "error_rate", "z_score": 4.8, "severity": "critical", "t_offset": 2},
        ],
        "cascade": [
            {"service": "order", "metric": "latency_ms", "z_score": 3.5, "severity": "high", "t_offset": 12},
        ],
        "ground_truth": {
            "root_cause_services": ["payment", "auth"],
            "expected_incidents": 2,
            "is_false_positive": False,
        }
    },
    {
        "id": 24,
        "name": "independent_cert_and_leak",
        "description": "Two metric anomalies on order from genuinely single cause (negative test: don't oversplit)",
        "category": "single_root_cause",
        "injected_fault": {"service": "order", "metric": "latency_ms", "z_score": 4.4, "severity": "critical", "t_offset": 0},
        "cascade": [
            {"service": "order", "metric": "error_rate", "z_score": 3.8, "severity": "high", "t_offset": 2},
            {"service": "api-gateway", "metric": "latency_ms", "z_score": 3.1, "severity": "medium", "t_offset": 10},
        ],
        "ground_truth": {
            "root_cause_service": "order",
            "root_cause_type": "network_latency_injection",
            "affected_services": ["api-gateway"],
            "expected_incidents": 1,
            "is_false_positive": False,
        }
    },
    # 25-28 Benign / False-positive
    {
        "id": 25,
        "name": "daily_traffic_surge",
        "description": "Daily 9 AM legitimate traffic surge on API gateway",
        "category": "false_positive",
        "signature": [1.0, 1.0, 4.0, 2.0, 2.5, 1.0, 10.0],
        "injected_fault": {"service": "api-gateway", "metric": "latency_ms", "z_score": 2.5, "severity": "medium", "t_offset": 0},
        "cascade": [],
        "ground_truth": {
            "is_false_positive": True,
            "expected_suppression": True,
            "pattern_tag": "daily_traffic_surge",
        }
    },
    {
        "id": 26,
        "name": "weekly_batch_job",
        "description": "Weekly Sunday batch reconciliation CPU surge on inventory",
        "category": "false_positive",
        "signature": [0.0, 6.0, 8.0, 1.0, 3.2, 1.0, 10.0],
        "injected_fault": {"service": "inventory", "metric": "cpu_usage", "z_score": 3.2, "severity": "high", "t_offset": 0},
        "cascade": [],
        "ground_truth": {
            "is_false_positive": True,
            "expected_suppression": True,
            "pattern_tag": "weekly_batch_job",
        }
    },
    {
        "id": 27,
        "name": "gradual_organic_growth",
        "description": "Gradual organic traffic growth on order service baseline",
        "category": "false_positive",
        "signature": [2.0, 3.0, 5.0, 2.0, 2.1, 1.0, 10.0],
        "injected_fault": {"service": "order", "metric": "latency_ms", "z_score": 2.1, "severity": "low", "t_offset": 0},
        "cascade": [],
        "ground_truth": {
            "is_false_positive": True,
            "expected_suppression": True,
            "pattern_tag": "gradual_organic_growth",
        }
    },
    {
        "id": 28,
        "name": "planned_maintenance_window",
        "description": "Scheduled shipping maintenance window",
        "category": "false_positive",
        "signature": [0.0, 5.0, 7.0, 4.0, 4.0, 1.0, 10.0],
        "injected_fault": {"service": "shipping", "metric": "restart_count", "z_score": 4.0, "severity": "high", "t_offset": 0},
        "cascade": [],
        "ground_truth": {
            "is_false_positive": True,
            "expected_suppression": True,
            "pattern_tag": "planned_maintenance_window",
        }
    },
    # 29-30 Blast radius predictions
    {
        "id": 29,
        "name": "early_stage_cascade",
        "description": "Early stage payment failure, predict order and api-gateway spread",
        "category": "blast_radius",
        "injected_fault": {"service": "payment", "metric": "connection_pool", "z_score": 5.0, "severity": "critical", "t_offset": 0},
        "ground_truth": {
            "root_cause_service": "payment",
            "expected_predictions": ["order", "api-gateway"],
            "is_contained": False,
        }
    },
    {
        "id": 30,
        "name": "contained_failure",
        "description": "Isolated notification queue backlog, predict no cascade",
        "category": "blast_radius",
        "injected_fault": {"service": "notification", "metric": "queue_backlog", "z_score": 4.1, "severity": "high", "t_offset": 0},
        "ground_truth": {
            "root_cause_service": "notification",
            "expected_predictions": [],
            "is_contained": True,
        }
    }
]


def generate_all_fixtures():
    """Write all 30 scenario files."""
    for s in SCENARIOS:
        fname = f"{s['id']:02d}_{s['name']}.json"
        data = {
            "scenario_id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "category": s["category"],
            "services": SERVICES,
            "dependencies": DEPENDENCIES,
            "injected_fault": s.get("injected_fault"),
            "injected_faults": s.get("injected_faults"),
            "cascade": s.get("cascade", []),
            "signature": s.get("signature"),
            "ground_truth": s["ground_truth"],
        }
        fpath = FIXTURES_DIR / fname
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    print(f"Successfully generated {len(SCENARIOS)} scenario fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all_fixtures()
