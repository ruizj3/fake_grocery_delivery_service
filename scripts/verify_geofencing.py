"""Verify all data respects geofencing constraints."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

conn = sqlite3.connect('database/grocery_delivery.db')
cursor = conn.cursor()

print('='*70)
print('GEOFENCING VERIFICATION - All Data Should Be in These 6 Cities:')
print('San Francisco, Seattle, New York, Cincinnati, Dallas, San Jose')
print('='*70)

# Check stores
cursor.execute('SELECT city, COUNT(*) FROM stores GROUP BY city ORDER BY city')
stores = cursor.fetchall()
print('\n📍 STORES by City:')
for city, count in stores:
    print(f'   {city:20} {count:>6,}')

# Check customers
cursor.execute('SELECT city, COUNT(*) FROM customers GROUP BY city ORDER BY city')
customers = cursor.fetchall()
print('\n👥 CUSTOMERS by City:')
for city, count in customers:
    print(f'   {city:20} {count:>6,}')

# Check drivers
cursor.execute('SELECT city, COUNT(*) FROM drivers GROUP BY city ORDER BY city')
drivers = cursor.fetchall()
print('\n🚗 DRIVERS by City:')
for city, count in drivers:
    print(f'   {city:20} {count:>6,}')

# Check orders - join with customers to get city
cursor.execute('''
    SELECT c.city, COUNT(o.order_id) 
    FROM orders o 
    JOIN customers c ON o.customer_id = c.customer_id 
    GROUP BY c.city 
    ORDER BY c.city
''')
orders = cursor.fetchall()
print('\n📦 ORDERS by Customer City:')
for city, count in orders:
    print(f'   {city:20} {count:>6,}')

# Verify all entities are in expected cities
expected_cities = {'San Francisco', 'Seattle', 'New York', 'Cincinnati', 'Dallas', 'San Jose'}
all_cities = set()
for city, _ in stores + customers + drivers + orders:
    all_cities.add(city)

print('\n' + '='*70)
if all_cities == expected_cities:
    print('✅ SUCCESS: All data is within the 6 geofenced cities!')
else:
    print('⚠️  WARNING: Found unexpected cities!')
    unexpected = all_cities - expected_cities
    missing = expected_cities - all_cities
    if unexpected:
        print(f'   Unexpected cities: {unexpected}')
    if missing:
        print(f'   Missing cities: {missing}')
print('='*70)

conn.close()
