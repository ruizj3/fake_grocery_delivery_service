#!/usr/bin/env python3
"""
Seed a production database via the API.

Usage:
    python scripts/seed_production.py --url https://YOUR-APP.onrender.com --key YOUR_API_KEY
    python scripts/seed_production.py --url https://YOUR-APP.onrender.com --key YOUR_API_KEY --orders 5000
"""

import argparse
import httpx
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Seed production database via API")
    parser.add_argument("--url", required=True, help="Base URL of the API")
    parser.add_argument("--key", required=True, help="API key (X-API-Key)")
    parser.add_argument("--orders", type=int, default=1000, help="Number of orders to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic mode")
    parser.add_argument("--customers", type=int, default=200, help="Extra customers to generate")
    parser.add_argument("--drivers", type=int, default=40, help="Extra drivers to generate")
    parser.add_argument("--stores", type=int, default=15, help="Number of stores to generate")
    parser.add_argument("--no-reset", action="store_true", help="Skip database reset")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    headers = {"X-API-Key": args.key, "Content-Type": "application/json"}
    batch_size = 100

    client = httpx.Client(base_url=base, headers=headers, timeout=120)

    def checked(r):
        """Raise with response body on error."""
        if r.status_code >= 400:
            print(f"  ERROR {r.status_code}: {r.text}")
            r.raise_for_status()
        return r

    # 1. Health check
    print("Checking API health...")
    try:
        r = client.get("/")
        r.raise_for_status()
        print(f"  API is up: {r.json()}")
    except Exception as e:
        print(f"  ERROR: Cannot reach API: {e}")
        sys.exit(1)

    # 2. Reset database (drops all tables, recreates with base data)
    if not args.no_reset:
        print("\nResetting database...")
        r = client.post("/admin/reset?confirm=true")
        checked(r)
        data = r.json()
        print(f"  Reset complete: {data.get('stats', {})}")
    else:
        print("\nSkipping reset (--no-reset)")

    # 3. Set deterministic seed + fast arrival rates for bulk seeding
    print(f"\nSetting deterministic seed={args.seed} with 50x arrival rates...")
    r = client.patch("/simulation/config", json={
        "master_seed": args.seed,
        "deterministic_mode": True,
        "order_arrival_rate_per_min": 300.0,
        "customer_arrival_rate_per_min": 25.0,
        "driver_arrival_rate_per_min": 10.0,
        "confirmation_delay_mean_sec": 2.4,
        "confirmation_delay_std_sec": 0.9,
        "picking_duration_mean_min": 0.3,
        "picking_duration_std_min": 0.1,
        "transit_speed_mean_kmh": 1200.0,
        "transit_speed_std_kmh": 300.0,
    })
    checked(r)
    print(f"  Done: {r.json()}")

    # 3. Check what already exists
    print("\nChecking existing data...")
    r = client.get("/stats")
    checked(r)
    stats = r.json()
    for table, count in stats.items():
        if count > 0:
            print(f"  {table}: {count}")

    # 4. Generate parent product catalog + distribute to all stores
    #    This mirrors main.py: catalog → stores → store inventories
    #    The /products/generate-catalog endpoint creates parent_products AND
    #    regenerates store_products for every existing store.
    print("\nGenerating product catalog (parent_products + store inventories)...")
    r = client.post("/products/generate-catalog")
    checked(r)
    data = r.json()
    print(f"  Created {data.get('count', '?')} parent products")

    # 5. Generate stores with inventory (each store gets store_products)
    print(f"\nGenerating {args.stores} stores with inventory...")
    r = client.post(f"/stores/generate?count={args.stores}")
    checked(r)
    data = r.json()
    print(f"  Created {data.get('count', args.stores)} stores (each with store_products)")

    # 6. Generate customers
    print(f"\nGenerating {args.customers} customers...")
    remaining = args.customers
    while remaining > 0:
        count = min(remaining, 100)
        r = client.post(f"/customers/generate?count={count}")
        checked(r)
        data = r.json()
        print(f"  Created {data.get('count', count)} customers")
        remaining -= count

    # 7. Generate drivers
    print(f"\nGenerating {args.drivers} drivers...")
    remaining = args.drivers
    while remaining > 0:
        count = min(remaining, 100)
        r = client.post(f"/drivers/generate?count={count}")
        checked(r)
        data = r.json()
        print(f"  Created {data.get('count', count)} drivers")
        remaining -= count

    # 8. Generate orders in batches
    total_orders = 0
    total_items = 0
    num_batches = (args.orders + batch_size - 1) // batch_size
    print(f"\nGenerating {args.orders} orders in {num_batches} batches...")
    start = time.time()

    for i in range(num_batches):
        count = min(batch_size, args.orders - total_orders)
        r = client.post(f"/orders/generate-batch?count={count}")
        checked(r)
        data = r.json()
        total_orders += data["count"]
        total_items += data["total_items"]
        elapsed = time.time() - start
        print(f"  Batch {i + 1}/{num_batches}: {data['count']} orders, "
              f"{data['total_items']} items ({elapsed:.1f}s elapsed)")

    print(f"\n  Total: {total_orders} orders, {total_items} items")

    # 9. Bundle all orders
    print("\nProcessing bundles...")
    r = client.post("/bundles/process")
    checked(r)
    data = r.json()
    print(f"  Bundles created: {data}")

    # 10. Final stats
    print("\nFinal database stats:")
    r = client.get("/stats")
    checked(r)
    stats = r.json()
    for table, count in stats.items():
        print(f"  {table:20s} {count:>8,}")

    print("\nDone!")


if __name__ == "__main__":
    main()
