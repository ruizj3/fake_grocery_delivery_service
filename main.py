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

from database.db import init_database, get_table_counts, DATABASE_PATH, get_connection, table_exists
from generators import (
    CustomerGenerator,
    DriverGenerator,
    ProductGenerator,
    StoreGenerator,
    OrderGenerator,
)
from generators.base import set_simulation_config
from simulation import SimulationConfig
from services import run_bundling_analysis


def generate_data(num_orders: int, seed: int = 42, days_back: int = 90, 
                  sim_config: SimulationConfig | None = None):
    """Generate all data based on target order count.
    
    Args:
        num_orders: Number of orders to generate.
        seed: Random seed for reproducibility.
        days_back: Number of days of historical data to generate.
        sim_config: Optional SimulationConfig for deterministic simulation.
                   When provided, uses proper statistical distributions
                   (Gaussian, Poisson) and seeded RNG throughout.
    """
    
    # Apply simulation config globally if provided
    if sim_config is None:
        sim_config = SimulationConfig(master_seed=seed)
    set_simulation_config(sim_config)
    
    # Scale other entities relative to orders for realistic ratios
    # Increased by 50% for customers and drivers
    num_customers = max(150, int(num_orders // 5 * 1.5))   # ~3.3 orders per customer avg (50% more customers)
    num_drivers = max(30, int(num_orders // 50 * 1.5))     # ~33 orders per driver avg (50% more drivers)
    num_stores = min(100, max(12, num_orders // 10000))     # Cap stores at 100
    
    det_label = " [DETERMINISTIC]" if sim_config.deterministic_mode else ""
    print(f"\n📊 Generating data for {num_orders} orders...{det_label}")
    print(f"   - {num_customers} customers")
    print(f"   - {num_drivers} drivers")
    print(f"   - {num_stores} store locations (spread across 6 cities)")
    print(f"   - Full product catalog")
    print(f"   - Date range: last {days_back} days")
    if sim_config.deterministic_mode:
        print(f"   - Master seed: {sim_config.master_seed}")
    print()
    
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
    order_gen = OrderGenerator(seed, days_back_max=days_back)
    orders, order_items = order_gen.generate_batch(num_orders)
    order_gen.save_to_db((orders, order_items))
    
    print("\n✅ Data generation complete!")


def export_to_csv():
    """Export all tables to CSV files"""
    import pandas as pd
    
    export_dir = Path(__file__).parent / "exports"
    export_dir.mkdir(exist_ok=True)
    
    conn = get_connection()
    
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
    if table_exists("bundles"):
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
  python main.py --reset --orders 1200000 --days 60  # 1.2M orders over 60 days
  python main.py --bundle           # Run bundling analysis
  python main.py --export           # Export tables to CSV
  python main.py --stats            # Show database statistics

Deterministic Simulation:
  python main.py --deterministic --seed 42   # Reproducible output (same every run)
  python main.py --deterministic --seed 42 --error-rate 0.05  # 5% simulated errors
  python main.py --deterministic --order-rate 10  # ~10 orders/min Poisson arrival
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
        "--days", "-d",
        type=int,
        default=90,
        help="Number of days back for historical data (default: 90)"
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
    
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Enable deterministic simulation mode (same seed = same output)"
    )
    
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.0,
        help="Simulated error injection rate (0.0-1.0, default: 0.0)"
    )
    
    parser.add_argument(
        "--order-rate",
        type=float,
        default=6.0,
        help="Order arrival rate per minute for Poisson process (default: 6.0)"
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
    sim_config = SimulationConfig(
        master_seed=args.seed,
        deterministic_mode=args.deterministic,
        api_error_rate=args.error_rate,
        order_arrival_rate_per_min=args.order_rate,
    )
    generate_data(
        num_orders=args.orders, 
        seed=args.seed, 
        days_back=args.days,
        sim_config=sim_config,
    )
    
    # Show final stats
    show_stats()


if __name__ == "__main__":
    main()
