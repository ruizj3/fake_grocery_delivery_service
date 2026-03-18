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

    # 2. Set deterministic seed
    print(f"\nSetting deterministic seed={args.seed}...")
    r = client.patch("/simulation/config", json={
        "master_seed": args.seed,
        "deterministic_mode": True,
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

    # 4. Generate parent product catalog (needed for store inventory → order items)
    if stats.get("parent_products", 0) == 0:
        print("\nGenerating parent product catalog...")
        r = client.post("/products/generate-catalog")
        checked(r)
        data = r.json()
        print(f"  Created {data.get('count', '?')} parent products")
    else:
        print(f"\nParent products already exist ({stats['parent_products']}), skipping catalog generation")

    # 5. Generate stores (each store gets inventory from parent products → store_products)
    if stats.get("stores", 0) == 0:
        print(f"\nGenerating {args.stores} stores with inventory...")
        r = client.post(f"/stores/generate?count={args.stores}")
        checked(r)
        data = r.json()
        print(f"  Created {data.get('count', args.stores)} stores (each with store_products inventory)")
    else:
        print(f"\nStores already exist ({stats['stores']}), skipping store generation")

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

    # 8. Verify store_products exist before generating orders
    r = client.get("/stats")
    checked(r)
    stats = r.json()
    if stats.get("store_products", 0) == 0:
        print("\nERROR: No store_products found. Orders need store inventory to create items.")
        print("  Try regenerating the catalog: POST /products/generate-catalog")
        sys.exit(1)
    print(f"\nReady to generate orders ({stats['store_products']} store products available)")

    # 9. Generate orders in batches
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

    # 10. Bundle all orders
    print("\nProcessing bundles...")
    r = client.post("/bundles/process")
    checked(r)
    data = r.json()
    print(f"  Bundles created: {data}")

    # 11. Final stats
    print("\nFinal database stats:")
    r = client.get("/stats")
    checked(r)
    stats = r.json()
    for table, count in stats.items():
        print(f"  {table:20s} {count:>8,}")

    print("\nDone!")


if __name__ == "__main__":
    main()
