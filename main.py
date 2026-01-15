#!/usr/bin/env python3
"""
Grocery Delivery Data Generator

Generate realistic fake data for a grocery delivery platform.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from db import init_database, get_table_counts, DATABASE_PATH
from generators import (
    CustomerGenerator,
    DriverGenerator,
    ProductGenerator,
    StoreGenerator,
    OrderGenerator,
)
from services import run_bundling_analysis


def generate_data(num_orders: int, seed: int = 42):
    """Generate all data based on target order count"""
    
    # Scale other entities relative to orders
    num_customers = max(100, num_orders // 5)   # ~5 orders per customer avg
    num_drivers = max(20, num_orders // 50)     # ~50 orders per driver avg
    num_stores = max(5, num_orders // 100)      # ~100 orders per store avg
    
    print(f"\n📊 Generating data for {num_orders} orders...")
    print(f"   - {num_customers} customers")
    print(f"   - {num_drivers} drivers")
    print(f"   - {num_stores} store locations")
    print(f"   - Full product catalog\n")
    
    # Generate customers
    print("👥 Generating customers...")
    customer_gen = CustomerGenerator(seed)
    customers = customer_gen.generate_batch(num_customers)
    customer_gen.save_to_db(customers)
    
    # Generate drivers
    print("🚗 Generating drivers...")
    driver_gen = DriverGenerator(seed)
    drivers = driver_gen.generate_batch(num_drivers)
    driver_gen.save_to_db(drivers)
    
    # Generate stores
    print("🏪 Generating store locations...")
    store_gen = StoreGenerator(seed)
    stores = store_gen.generate_batch(num_stores)
    store_gen.save_to_db(stores)
    
    # Generate parent product catalog
    print("🛒 Generating parent product catalog...")
    product_gen = ProductGenerator(seed)
    parent_products = product_gen.generate_catalog()
    product_gen.save_parent_products_to_db(parent_products)
    
    # Generate store-specific inventories
    print("📦 Generating store inventories...")
    for i, store in enumerate(stores, 1):
        store_products = product_gen.generate_store_inventory(
            store.store_id,
            coverage=0.85,  # Each store carries 85% of catalog
            price_variance=0.15,  # Prices vary +/- 15%
        )
        product_gen.save_store_products_to_db(store_products)
        print(f"   Store {i}/{num_stores}: {len(store_products)} products")
    
    # Generate orders (this ties everything together)
    print("📝 Generating orders...")
    order_gen = OrderGenerator(seed)
    orders, order_items = order_gen.generate_batch(num_orders)
    order_gen.save_to_db((orders, order_items))
    
    print("\n✅ Data generation complete!")


def export_to_csv():
    """Export all tables to CSV files"""
    import sqlite3
    import pandas as pd
    
    export_dir = Path(__file__).parent / "exports"
    export_dir.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Core tables
    tables = [
        "stores", 
        "customers", 
        "drivers", 
        "parent_products",
        "store_products",
        "orders", 
        "order_items"
    ]
    
    # Check for bundle tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bundles'")
    if cursor.fetchone():
        tables.extend(["bundles", "bundle_stops"])
    
    print("\n📁 Exporting to CSV...")
    for table in tables:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        output_path = export_dir / f"{table}.csv"
        df.to_csv(output_path, index=False)
        print(f"   - {output_path} ({len(df)} rows)")
    
    conn.close()
    print("\n✅ Export complete!")


def show_stats():
    """Display current database statistics"""
    counts = get_table_counts()
    
    print("\n📈 Database Statistics:")
    print("-" * 30)
    for table, count in counts.items():
        print(f"   {table:15} {count:>8,} rows")
    print("-" * 30)
    print(f"   {'Total':15} {sum(counts.values()):>8,} rows")
    print(f"\n   Database: {DATABASE_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate fake grocery delivery data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Generate 500 orders (default)
  python main.py --orders 5000      # Generate 5000 orders
  python main.py --reset --orders 1000  # Reset DB and generate fresh
  python main.py --bundle           # Run bundling analysis
  python main.py --export           # Export tables to CSV
  python main.py --stats            # Show database statistics
        """
    )
    
    parser.add_argument(
        "--orders", "-n",
        type=int,
        default=500,
        help="Number of orders to generate (default: 500)"
    )
    
    parser.add_argument(
        "--reset", "-r",
        action="store_true",
        help="Reset database before generating"
    )
    
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    
    parser.add_argument(
        "--export", "-e",
        action="store_true",
        help="Export all tables to CSV files"
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics"
    )
    
    parser.add_argument(
        "--bundle",
        action="store_true",
        help="Run bundling analysis on existing orders"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    init_database(reset=args.reset)
    
    if args.stats:
        show_stats()
        return
    
    if args.bundle:
        run_bundling_analysis()
        return
    
    if args.export:
        export_to_csv()
        return
    
    # Generate data
    generate_data(num_orders=args.orders, seed=args.seed)
    
    # Show final stats
    show_stats()


if __name__ == "__main__":
    main()
