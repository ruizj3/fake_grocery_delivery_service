import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('database/grocery_delivery.db')

print("=" * 80)
print("ORDER STATUS FLOW & TIMESTAMP ANALYSIS")
print("=" * 80)

# 1. Status Transition Analysis
print("\n📊 STATUS DISTRIBUTION")
print("-" * 80)
status_query = """
SELECT 
    status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM orders), 1) as pct,
    COUNT(CASE WHEN confirmed_at IS NOT NULL THEN 1 END) as has_confirmed,
    COUNT(CASE WHEN picked_at IS NOT NULL THEN 1 END) as has_picked,
    COUNT(CASE WHEN picking_completed_at IS NOT NULL THEN 1 END) as has_completed,
    COUNT(CASE WHEN delivered_at IS NOT NULL THEN 1 END) as has_delivered
FROM orders
GROUP BY status
ORDER BY count DESC
"""
print(pd.read_sql(status_query, conn).to_string(index=False))

# 2. Timestamp Progression for Out-for-Delivery Orders
print("\n⏱️  OUT-FOR-DELIVERY ORDERS - TIMESTAMP CHECK")
print("-" * 80)
ofd_sample = pd.read_sql("""
    SELECT 
        order_id,
        status,
        datetime(created_at) as created,
        datetime(confirmed_at) as confirmed,
        datetime(picked_at) as picked,
        datetime(picking_completed_at) as completed,
        datetime(delivered_at) as delivered,
        ROUND(julianday('now') - julianday(created_at), 2) as days_since_created,
        ROUND((julianday('now') - julianday(created_at)) * 24 * 60, 1) as mins_since_created
    FROM orders
    WHERE status = 'out_for_delivery'
    ORDER BY created_at DESC
    LIMIT 10
""", conn)
print(ofd_sample[['order_id', 'status', 'mins_since_created', 'picked', 'completed', 'delivered']].to_string(index=False))

# 3. Check Time Gaps Between Timestamps
print("\n⏳ TIMESTAMP GAPS (Out-for-Delivery Orders)")
print("-" * 80)
gaps = pd.read_sql("""
    SELECT 
        COUNT(*) as total,
        ROUND(AVG(julianday(confirmed_at) - julianday(created_at)) * 24 * 60, 1) as avg_create_to_confirm_mins,
        ROUND(AVG(julianday(picked_at) - julianday(confirmed_at)) * 24 * 60, 1) as avg_confirm_to_pick_mins,
        ROUND(AVG(julianday(picking_completed_at) - julianday(picked_at)) * 24 * 60, 1) as avg_pick_to_complete_mins,
        ROUND(AVG(julianday('now') - julianday(picking_completed_at)) * 24 * 60, 1) as avg_mins_since_completed
    FROM orders
    WHERE status = 'out_for_delivery'
    AND picked_at IS NOT NULL
    AND picking_completed_at IS NOT NULL
""", conn)
print(gaps.to_string(index=False))

# 4. Check if delivered_at timestamp exists but status not updated
print("\n🔍 MISMATCHED STATUS (has delivered_at but status != delivered)")
print("-" * 80)
mismatch = pd.read_sql("""
    SELECT 
        COUNT(*) as count,
        GROUP_CONCAT(DISTINCT status) as statuses_with_delivered_timestamp
    FROM orders
    WHERE delivered_at IS NOT NULL AND status != 'delivered'
""", conn)
print(mismatch.to_string(index=False))

# 5. Check Delivered Orders
print("\n✅ SUCCESSFULLY DELIVERED ORDERS")
print("-" * 80)
delivered = pd.read_sql("""
    SELECT 
        COUNT(*) as total_delivered,
        ROUND(AVG(julianday(delivered_at) - julianday(created_at)) * 24 * 60, 1) as avg_total_time_mins,
        ROUND(AVG(julianday(confirmed_at) - julianday(created_at)) * 24 * 60, 1) as avg_create_to_confirm,
        ROUND(AVG(julianday(picked_at) - julianday(confirmed_at)) * 24 * 60, 1) as avg_confirm_to_pick,
        ROUND(AVG(julianday(picking_completed_at) - julianday(picked_at)) * 24 * 60, 1) as avg_pick_to_complete,
        ROUND(AVG(julianday(delivered_at) - julianday(picking_completed_at)) * 24 * 60, 1) as avg_complete_to_deliver
    FROM orders
    WHERE status = 'delivered'
""", conn)
print(delivered.to_string(index=False))

# 6. Sample Out-for-Delivery with calculated delivery time
print("\n🚚 SAMPLE OUT-FOR-DELIVERY - EXPECTED vs ACTUAL")
print("-" * 80)
sample_detail = pd.read_sql("""
    SELECT 
        SUBSTR(o.order_id, 1, 8) as order_id,
        datetime(o.picking_completed_at) as completed_at,
        datetime(o.picking_completed_at, '+20 minutes') as expected_delivery_start,
        datetime('now') as now,
        CASE 
            WHEN datetime('now') >= datetime(o.picking_completed_at, '+20 minutes') 
            THEN 'READY' 
            ELSE 'WAITING'
        END as should_deliver
    FROM orders o
    WHERE o.status = 'out_for_delivery'
    AND o.picking_completed_at IS NOT NULL
    LIMIT 5
""", conn)
print(sample_detail.to_string(index=False))

# 7. Bundle Completion Status
print("\n📦 BUNDLE COMPLETION ANALYSIS")
print("-" * 80)
bundle_analysis = pd.read_sql("""
    SELECT 
        b.bundle_id,
        b.order_count,
        COUNT(bs.order_id) as actual_stops,
        SUM(CASE WHEN o.status = 'delivered' THEN 1 ELSE 0 END) as delivered_count,
        SUM(CASE WHEN o.status = 'out_for_delivery' THEN 1 ELSE 0 END) as ofd_count,
        SUM(CASE WHEN o.status = 'picking' THEN 1 ELSE 0 END) as picking_count,
        b.completed_at
    FROM bundles b
    LEFT JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
    LEFT JOIN orders o ON bs.order_id = o.order_id
    GROUP BY b.bundle_id
    HAVING ofd_count > 0
    LIMIT 10
""", conn)
if len(bundle_analysis) > 0:
    print(bundle_analysis[['bundle_id', 'order_count', 'delivered_count', 'ofd_count', 'picking_count', 'completed_at']].to_string(index=False))
else:
    print("No bundles with out-for-delivery orders found")

# 8. Check for Timestamp Chronology Issues
print("\n❌ TIMESTAMP CHRONOLOGY ERRORS")
print("-" * 80)
chrono_errors = pd.read_sql("""
    SELECT 
        'confirmed < created' as error_type,
        COUNT(*) as count
    FROM orders
    WHERE confirmed_at IS NOT NULL 
    AND datetime(confirmed_at) < datetime(created_at)
    
    UNION ALL
    
    SELECT 
        'picked < confirmed' as error_type,
        COUNT(*) as count
    FROM orders
    WHERE picked_at IS NOT NULL AND confirmed_at IS NOT NULL
    AND datetime(picked_at) < datetime(confirmed_at)
    
    UNION ALL
    
    SELECT 
        'completed < picked' as error_type,
        COUNT(*) as count
    FROM orders
    WHERE picking_completed_at IS NOT NULL AND picked_at IS NOT NULL
    AND datetime(picking_completed_at) < datetime(picked_at)
    
    UNION ALL
    
    SELECT 
        'delivered < completed' as error_type,
        COUNT(*) as count
    FROM orders
    WHERE delivered_at IS NOT NULL AND picking_completed_at IS NOT NULL
    AND datetime(delivered_at) < datetime(picking_completed_at)
""", conn)
print(chrono_errors.to_string(index=False))

print("\n" + "=" * 80)

conn.close()
