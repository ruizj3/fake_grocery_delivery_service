"""
Verify that drivers and orders are matched within the same city.

This script creates sample bundles and verifies that:
1. All orders in a bundle are from the same city
2. The assigned driver is from the same city as the orders
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bundling import BundlingService

print('='*70)
print('TESTING BUNDLE CITY MATCHING')
print('='*70)

# Create bundling service
bundler = BundlingService()

# Fetch some pending/confirmed orders
print('\n📦 Fetching orders for bundling...')
stops = bundler.fetch_pending_orders(include_delivered=False)

if not stops:
    print('⚠️  No pending orders found. Generate some orders first:')
    print('   python main.py --orders 100')
else:
    print(f'✓ Found {len(stops)} orders ready for bundling')
    
    # Create bundles
    print(f'\n🔄 Creating bundles...')
    bundles = bundler.create_bundles(stops)
    print(f'✓ Created {len(bundles)} bundles')
    
    # Assign drivers
    print(f'\n🚗 Assigning drivers to bundles...')
    bundles = bundler.assign_drivers(bundles)
    
    # Verify city matching
    print(f'\n🔍 Verifying city matching...')
    
    conn = sqlite3.connect('database/grocery_delivery.db')
    cursor = conn.cursor()
    
    mismatches = 0
    total_bundles = len(bundles)
    
    for bundle in bundles:
        if not bundle.driver_id or not bundle.stops:
            continue
            
        # Get driver city
        cursor.execute('SELECT city FROM drivers WHERE driver_id = ?', (bundle.driver_id,))
        result = cursor.fetchone()
        if not result:
            print(f'⚠️  Driver {bundle.driver_id[:8]} not found')
            continue
        driver_city = result[0]
        
        # Get cities of all orders in bundle
        order_cities = set()
        for stop in bundle.stops:
            cursor.execute('''
                SELECT c.city FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_id = ?
            ''', (stop.order_id,))
            result = cursor.fetchone()
            if result:
                order_cities.add(result[0])
        
        # Check if all in same city
        if len(order_cities) > 1:
            print(f'❌ Bundle {bundle.bundle_id[:12]} has orders from multiple cities: {order_cities}')
            mismatches += 1
        elif order_cities and driver_city not in order_cities:
            print(f'❌ Bundle {bundle.bundle_id[:12]}: Driver in {driver_city}, Orders in {order_cities}')
            mismatches += 1
    
    conn.close()
    
    print('\n' + '='*70)
    if mismatches == 0:
        print(f'✅ SUCCESS: All {total_bundles} bundles have drivers matched to same city!')
    else:
        print(f'⚠️  MISMATCHES: {mismatches}/{total_bundles} bundles have city mismatches')
    print('='*70)
