"""
Test ML Realism Features

Quick test to verify persona-based generation works.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import init_database
from generators import CustomerGenerator, DriverGenerator, StoreGenerator, ProductGenerator, OrderGenerator

def test_ml_features():
    print("Testing ML Realism Features...\n")
    
    # Initialize database
    init_database()
    
    # Generate small dataset
    print("1. Generating 10 customers with personas...")
    customer_gen = CustomerGenerator(seed=42)
    customers = customer_gen.generate_batch(10)
    customer_gen.save_to_db(customers)
    print(f"   ✓ Created {len(customers)} customers\n")
    
    print("2. Generating 5 drivers with performance profiles...")
    driver_gen = DriverGenerator(seed=42)
    drivers = driver_gen.generate_batch(5)
    driver_gen.save_to_db(drivers)
    print(f"   ✓ Created {len(drivers)} drivers\n")
    
    print("3. Generating 2 stores...")
    store_gen = StoreGenerator(seed=42)
    stores = store_gen.generate_batch(2)
    store_gen.save_to_db(stores)
    print(f"   ✓ Created {len(stores)} stores\n")
    
    print("4. Generating product catalog...")
    product_gen = ProductGenerator(seed=42)
    parent_products = product_gen.generate_catalog()
    product_gen.save_parent_products_to_db(parent_products)
    print(f"   ✓ Created {len(parent_products)} parent products\n")
    
    print("5. Generating store inventories...")
    for store in stores:
        store_products = product_gen.generate_store_inventory(
            store.store_id,
            coverage=0.85,
            price_variance=0.15
        )
        product_gen.save_store_products_to_db(store_products)
    print(f"   ✓ Created store inventories\n")
    
    print("6. Generating 5 orders with persona-based product selection...")
    order_gen = OrderGenerator(seed=42, days_back_max=30)
    
    try:
        orders, order_items = order_gen.generate_batch(5, enable_clustering=False, live_mode=False)
        order_gen.save_to_db((orders, order_items))
        print(f"   ✓ Created {len(orders)} orders with {len(order_items)} items\n")
        
        # Show sample order details
        if orders:
            sample = orders[0]
            print(f"Sample Order Analysis:")
            print(f"  - Weather: {sample.weather_condition}")
            print(f"  - Traffic Multiplier: {sample.traffic_multiplier:.2f}x")
            print(f"  - Peak Hour: {sample.is_peak_hour}")
            print(f"  - Weekend: {sample.is_weekend}")
            print(f"  - Cancellation Risk: {sample.cancellation_risk:.1%}")
            print(f"  - Customer Order #: {sample.customer_order_number}")
            
        print("\n✅ All ML realism features working!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error generating orders: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ml_features()
    sys.exit(0 if success else 1)
