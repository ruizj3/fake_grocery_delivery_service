#!/usr/bin/env python3
"""
Test that delivery times are based on distance from store to customer.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_cursor
from generators.orders import haversine_distance
from datetime import datetime


def test_delivery_distance_correlation():
    """
    Verify that delivery times correlate with distance from store to customer.
    
    This tests the ML realism improvement where delivery duration should
    be calculated based on actual distance rather than random values.
    """
    print("\n" + "="*80)
    print("Testing Distance-Based Delivery Times")
    print("="*80)
    
    with get_cursor() as cursor:
        # Get sample of delivered orders with timestamps
        cursor.execute("""
            SELECT 
                o.order_id,
                o.store_id,
                o.delivery_latitude,
                o.delivery_longitude,
                o.picking_completed_at,
                o.delivered_at,
                o.traffic_multiplier,
                s.latitude as store_lat,
                s.longitude as store_lon
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE o.status = 'delivered' 
                AND o.delivered_at IS NOT NULL 
                AND o.picking_completed_at IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 20
        """)
        
        orders = cursor.fetchall()
    
    if not orders:
        print("⚠️  No delivered orders found. Generate historical orders first.")
        return
    
    print(f"\nAnalyzing {len(orders)} delivered orders:")
    print("-" * 80)
    
    results = []
    for order in orders:
        (order_id, store_id, cust_lat, cust_lon, picking_completed, delivered, 
         traffic_mult, store_lat, store_lon) = order
        
        # Calculate distance
        distance_km = haversine_distance(store_lat, store_lon, cust_lat, cust_lon)
        
        # Calculate delivery time
        picking_dt = datetime.fromisoformat(picking_completed)
        delivered_dt = datetime.fromisoformat(delivered)
        delivery_minutes = (delivered_dt - picking_dt).total_seconds() / 60
        
        # Expected base time: ~2.5 min/km + 5-8 min base
        expected_base = (distance_km * 2.5) + 6.5  # Using 6.5 as middle of 5-8 range
        
        # Account for traffic multiplier
        traffic_mult = traffic_mult if traffic_mult else 1.0
        expected_with_traffic = expected_base * traffic_mult
        
        results.append({
            'distance_km': distance_km,
            'delivery_minutes': delivery_minutes,
            'traffic_multiplier': traffic_mult,
            'expected_minutes': expected_with_traffic
        })
        
        print(f"Distance: {distance_km:5.2f} km | "
              f"Delivery Time: {delivery_minutes:5.1f} min | "
              f"Traffic: {traffic_mult:.2f}x | "
              f"Expected: ~{expected_with_traffic:.1f} min")
    
    print("-" * 80)
    
    # Statistical analysis
    distances = [r['distance_km'] for r in results]
    times = [r['delivery_minutes'] for r in results]
    
    avg_distance = sum(distances) / len(distances)
    avg_time = sum(times) / len(times)
    
    # Check correlation: longer distances should have longer times
    # Simple correlation check: count how many pairs follow the pattern
    correlation_count = 0
    total_pairs = 0
    
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            total_pairs += 1
            # If distance[i] > distance[j], then time[i] should also be > time[j]
            if (distances[i] > distances[j] and times[i] > times[j]) or \
               (distances[i] < distances[j] and times[i] < times[j]):
                correlation_count += 1
    
    correlation_pct = (correlation_count / total_pairs * 100) if total_pairs > 0 else 0
    
    print(f"\n📊 Statistics:")
    print(f"  • Average Distance: {avg_distance:.2f} km")
    print(f"  • Average Delivery Time: {avg_time:.1f} minutes")
    print(f"  • Minutes per km: {avg_time / avg_distance:.2f} min/km")
    print(f"  • Distance-Time Correlation: {correlation_pct:.1f}%")
    
    print(f"\n✅ Expected Behavior:")
    print(f"  • Base formula: (distance * 2.5 min/km) + 5-8 min")
    print(f"  • Modified by: traffic multiplier (1.0x-2.1x)")
    print(f"  • Modified by: driver speed (0.7x-1.3x slower/faster)")
    print(f"  • Modified by: ±10% random variation")
    print(f"  • Minimum: 8 minutes (even for very close deliveries)")
    
    if correlation_pct > 60:
        print(f"\n✅ SUCCESS: Delivery times show {correlation_pct:.1f}% correlation with distance!")
        print(f"   This is good - times are based on distance, not purely random.")
    else:
        print(f"\n⚠️  WARNING: Correlation is only {correlation_pct:.1f}%")
        print(f"   Expected >60% correlation between distance and delivery time.")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    test_delivery_distance_correlation()
