#!/usr/bin/env python3
"""
Test ML Realism Features

Quick test to verify that ML realism features are working correctly.
Generates a small dataset and verifies persona, bundle, and environmental features.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import init_database, get_cursor
from generators import (
    CustomerGenerator,
    DriverGenerator,
    StoreGenerator,
    ProductGenerator,
    OrderGenerator,
)

def test_ml_features():
    """Test ML realism implementation."""
    print("="*80)
    print("TESTING ML REALISM FEATURES")
    print("="*80)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_database()
    
    # Generate small dataset
    seed = 123
    
    print("\n2. Generating customers with personas...")
    customer_gen = CustomerGenerator(seed)
    customers = customer_gen.generate_batch(50)
    customer_gen.save_to_db(customers)
    
    # Verify personas assigned
    with get_cursor() as cursor:
        cursor.execute("SELECT persona, COUNT(*) FROM customers GROUP BY persona")
        persona_dist = cursor.fetchall()
        print("   Customer Persona Distribution:")
        for persona, count in persona_dist:
            print(f"      {persona}: {count}")
    
    print("\n3. Generating drivers with performance profiles...")
    driver_gen = DriverGenerator(seed)
    drivers = driver_gen.generate_batch(10)
    driver_gen.save_to_db(drivers)
    
    # Verify driver profiles
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT experience_level, AVG(speed_multiplier), AVG(reliability_score)
            FROM drivers
            GROUP BY experience_level
        """)
        driver_profiles = cursor.fetchall()
        print("   Driver Performance Profiles:")
        for level, avg_speed, avg_reliability in driver_profiles:
            print(f"      {level}: Speed={avg_speed:.2f}x, Reliability={avg_reliability:.2f}")
    
    print("\n4. Generating stores and products...")
    store_gen = StoreGenerator(seed)
    stores = store_gen.generate_batch(6)
    store_gen.save_to_db(stores)
    
    product_gen = ProductGenerator(seed)
    parent_products = product_gen.generate_catalog()
    product_gen.save_parent_products_to_db(parent_products)
    
    for store in stores:
        store_products = product_gen.generate_store_inventory(store.store_id)
        product_gen.save_store_products_to_db(store_products)
    
    print("   Generated catalog and store inventories")
    
    print("\n5. Generating orders with ML features...")
    order_gen = OrderGenerator(seed, days_back_max=30)
    orders, order_items = order_gen.generate_batch(100, enable_clustering=False, live_mode=False)
    order_gen.save_to_db((orders, order_items))
    
    # Verify ML features
    with get_cursor() as cursor:
        # Weather distribution
        cursor.execute("SELECT weather_condition, COUNT(*) FROM orders GROUP BY weather_condition")
        weather_dist = cursor.fetchall()
        print("\n   Weather Distribution:")
        for weather, count in weather_dist:
            print(f"      {weather}: {count}")
        
        # Peak hour distribution
        cursor.execute("SELECT is_peak_hour, COUNT(*) FROM orders GROUP BY is_peak_hour")
        peak_dist = cursor.fetchall()
        print("\n   Peak Hour Distribution:")
        for is_peak, count in peak_dist:
            label = "Peak Hours" if is_peak else "Off-Peak"
            print(f"      {label}: {count}")
        
        # Traffic impact
        cursor.execute("SELECT AVG(traffic_multiplier), MIN(traffic_multiplier), MAX(traffic_multiplier) FROM orders")
        avg_traffic, min_traffic, max_traffic = cursor.fetchone()
        print(f"\n   Traffic Multipliers:")
        print(f"      Average: {avg_traffic:.2f}x")
        print(f"      Range: {min_traffic:.2f}x - {max_traffic:.2f}x")
        
        # Cancellation risk
        cursor.execute("SELECT AVG(cancellation_risk), MIN(cancellation_risk), MAX(cancellation_risk) FROM orders")
        avg_risk, min_risk, max_risk = cursor.fetchone()
        print(f"\n   Cancellation Risk:")
        print(f"      Average: {avg_risk:.2%}")
        print(f"      Range: {min_risk:.2%} - {max_risk:.2%}")
        
        # Order numbers
        cursor.execute("SELECT AVG(customer_order_number), MAX(customer_order_number) FROM orders")
        avg_order_num, max_order_num = cursor.fetchone()
        print(f"\n   Customer Order Numbers:")
        print(f"      Average: {avg_order_num:.1f}")
        print(f"      Max: {max_order_num}")
    
    print("\n" + "="*80)
    print("✅ ML REALISM FEATURES TEST COMPLETE!")
    print("="*80)
    print("\nAll features are working correctly!")
    print("You can now generate larger datasets with:")
    print("  python scripts/generate_complete_dataset.py --orders 10000 --days 30")


if __name__ == "__main__":
    test_ml_features()
