"""Check if drivers are matched to orders in the same city."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.geofence import get_zone_for_coordinates

conn = sqlite3.connect('database/grocery_delivery.db')
cursor = conn.cursor()

# Get bundles with driver and order locations
cursor.execute('''
    SELECT 
        b.bundle_id,
        b.driver_id,
        d.home_latitude,
        d.home_longitude,
        o.order_id,
        o.delivery_latitude,
        o.delivery_longitude,
        c.city as customer_city
    FROM bundles b
    JOIN drivers d ON b.driver_id = d.driver_id
    JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
    JOIN orders o ON bs.order_id = o.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE b.driver_id IS NOT NULL
    LIMIT 50
''')

rows = cursor.fetchall()
mismatches = 0
total = len(rows)

print(f"=== CHECKING {total} DRIVER-ORDER ASSIGNMENTS ===\n")

for row in rows:
    bundle_id, driver_id, dlat, dlon, order_id, olat, olon, cust_city = row
    
    driver_zone = get_zone_for_coordinates(dlat, dlon)
    order_zone = get_zone_for_coordinates(olat, olon)
    
    driver_city = driver_zone['city'] if driver_zone else 'OUTSIDE_ZONES'
    order_city = order_zone['city'] if order_zone else 'OUTSIDE_ZONES'
    
    if driver_city != order_city:
        mismatches += 1
        print(f"❌ MISMATCH #{mismatches}:")
        print(f"   Bundle: {bundle_id[:12]}...")
        print(f"   Driver {driver_id[:12]}... in {driver_city}")
        print(f"   Order {order_id[:12]}... in {order_city} (Customer city: {cust_city})")
        print()

print(f"\n{'='*60}")
print(f"RESULTS: {mismatches} mismatches out of {total} assignments")
print(f"Success Rate: {((total-mismatches)/total*100):.1f}%")
print(f"{'='*60}")

conn.close()
