#!/usr/bin/env python3
"""
Test script to verify distance-based delivery times with new orders.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.orders import OrderGenerator
from database.db import get_cursor


def test_new_orders_with_distance():
    """Generate a few new orders and verify distance-based delivery times."""
    print("\n" + "="*80)
    print("Testing NEW Orders with Distance-Based Delivery Times")
    print("="*80)
    
    # Generate 10 new historical orders
    print("\n🔨 Generating 10 new historical orders...")
    order_gen = OrderGenerator(seed=999)  # Different seed
    
    orders, items = order_gen.generate_batch(10, enable_clustering=False, live_mode=False)
    
    if not orders:
        print("⚠️  Failed to generate orders. Check if customers/drivers/stores exist.")
        return
    
    # Save to database (pass both orders and items)
    order_gen.save_to_db((orders, items))
    
    print(f"✅ Generated and saved {len(orders)} orders\n")
    
    # Analyze these specific orders
    print("📊 Analyzing new orders:")
    print("-" * 80)
    
    from generators.orders import haversine_distance
    from datetime import datetime
    
    order_ids = [o.order_id for o in orders]
    
    results = []
    for order in orders:
        if order.status.value != 'delivered':
            continue
            
        # Get store coordinates
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude FROM stores WHERE store_id = ?",
                (order.store_id,)
            )
            store_row = cursor.fetchone()
            if not store_row:
                continue
            store_lat, store_lon = store_row
        
        # Calculate distance
        distance_km = haversine_distance(
            store_lat, store_lon, 
            order.delivery_latitude, order.delivery_longitude
        )
        
        # Calculate delivery time
        if order.picking_completed_at and order.delivered_at:
            delivery_minutes = (order.delivered_at - order.picking_completed_at).total_seconds() / 60
        else:
            continue
        
        # Expected base time: ~2.5 min/km + 5-8 min base
        expected_base = (distance_km * 2.5) + 6.5
        
        # Account for traffic multiplier
        traffic_mult = order.traffic_multiplier if order.traffic_multiplier else 1.0
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
    
    if not results:
        print("⚠️  No delivered orders in this batch to analyze.")
        return
    
    print("-" * 80)
    
    # Statistical analysis
    distances = [r['distance_km'] for r in results]
    times = [r['delivery_minutes'] for r in results]
    
    avg_distance = sum(distances) / len(distances)
    avg_time = sum(times) / len(times)
    
    # Check correlation
    correlation_count = 0
    total_pairs = 0
    
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            total_pairs += 1
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
    print(f"  • Formula: (distance * 2.5 min/km) + 5-8 min base")
    print(f"  • Traffic multiplier: {min([r['traffic_multiplier'] for r in results]):.2f}x to {max([r['traffic_multiplier'] for r in results]):.2f}x")
    print(f"  • With ±10% random variation and driver speed differences")
    
    if correlation_pct > 70:
        print(f"\n✅ SUCCESS! Delivery times show {correlation_pct:.1f}% correlation with distance!")
        print(f"   New implementation is working correctly! 🎉")
    elif correlation_pct > 60:
        print(f"\n✅ GOOD: {correlation_pct:.1f}% correlation (above 60% threshold)")
    else:
        print(f"\n⚠️  WARNING: Correlation is only {correlation_pct:.1f}%")
        print(f"   Expected >60% correlation between distance and delivery time.")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    test_new_orders_with_distance()
