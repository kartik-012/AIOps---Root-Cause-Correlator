"""Seeds the PostgreSQL database with the standard 8-microservice topology and dependency graph."""

import sys
from pathlib import Path
import httpx

BACKEND_URL = "http://127.0.0.1:8001"

SERVICES = [
    {"name": "api-gateway", "revenue_weight": 10.0},
    {"name": "auth-service", "revenue_weight": 7.0},
    {"name": "product-catalog", "revenue_weight": 6.0},
    {"name": "inventory-service", "revenue_weight": 8.0},
    {"name": "order-service", "revenue_weight": 9.0},
    {"name": "payment-service", "revenue_weight": 10.0},
    {"name": "notification-service", "revenue_weight": 3.0},
    {"name": "shipping-service", "revenue_weight": 4.0},
]

DEPENDENCIES = [
    ("api-gateway", "auth-service"),
    ("api-gateway", "product-catalog"),
    ("product-catalog", "inventory-service"),
    ("api-gateway", "order-service"),
    ("order-service", "payment-service"),
    ("order-service", "inventory-service"),
    ("order-service", "notification-service"),
    ("order-service", "shipping-service"),
]


def seed():
    print("=" * 60)
    print("   SEEDING AIOps 8-MICROSERVICE TOPOLOGY")
    print("=" * 60)

    with httpx.Client(base_url=BACKEND_URL, timeout=5.0) as client:
        # 1. Register Services
        name_to_id = {}
        for s in SERVICES:
            res = client.post("/api/v1/services", json=s)
            if res.status_code == 200:
                data = res.json()
                name_to_id[s["name"]] = data["id"]
                print(f"  [+] Service registered: {s['name']} (ID: {data['id']})")
            else:
                print(f"  [!] Failed to register {s['name']}: {res.text}")

        # 2. Register Dependencies
        print("-" * 60)
        for src, tgt in DEPENDENCIES:
            src_id = name_to_id.get(src)
            tgt_id = name_to_id.get(tgt)
            if src_id and tgt_id:
                res = client.post("/api/v1/services/dependencies", json={
                    "from_service_id": src_id,
                    "to_service_id": tgt_id,
                })
                if res.status_code == 200:
                    print(f"  [+] Dependency registered: {src} → {tgt}")
                else:
                    print(f"  [!] Failed dependency {src} → {tgt}: {res.text}")

        print("=" * 60)
        print("Topology successfully seeded into database!")


if __name__ == "__main__":
    seed()
