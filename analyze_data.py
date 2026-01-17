import sqlite3
import pandas as pd

conn = sqlite3.connect('database/grocery_delivery.db')

print("=" * 70)
print("DATABASE ANALYSIS - GROCERY DELIVERY SYSTEM")
print("=" * 70)

# 1. Overall Statistics
print("\n📊 OVERALL STATISTICS")
print("-" * 70)
stats_query = """
SELECT 
    (SELECT COUNT(*) FROM stores) as stores,
    (SELECT COUNT(*) FROM customers) as customers,
    (SELECT COUNT(*) FROM drivers) as drivers,
    (SELECT COUNT(*) FROM parent_products) as products,
    (SELECT COUNT(*) FROM orders) as orders,
    (SELECT COUNT(*) FROM bundles) as bundles
"""
stats = pd.read_sql(stats_query, conn).iloc[0]
print(f"Stores:     {stats['stores']:>6}")
print(f"Customers:  {stats['customers']:>6}")
print(f"Drivers:    {stats['drivers']:>6}")
print(f"Products:   {stats['products']:>6}")
print(f"Orders:     {stats['orders']:>6}")
print(f"Bundles:    {stats['bundles']:>6}")

# 2. Order Status Distribution
print("\n📦 ORDER STATUS DISTRIBUTION")
print("-" * 70)
status_df = pd.read_sql("""
    SELECT status, COUNT(*) as count,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM orders), 1) as pct
    FROM orders 
    GROUP BY status 
    ORDER BY count DESC
""", conn)
print(status_df.to_string(index=False))

# 3. Order Lifecycle Completeness
print("\n⏱️  ORDER LIFECYCLE COMPLETENESS")
print("-" * 70)
lifecycle_df = pd.read_sql("""
    SELECT 
        COUNT(*) as total_orders,
        SUM(CASE WHEN confirmed_at IS NOT NULL THEN 1 ELSE 0 END) as has_confirmed,
        SUM(CASE WHEN picked_at IS NOT NULL THEN 1 ELSE 0 END) as has_picked,
        SUM(CASE WHEN picking_completed_at IS NOT NULL THEN 1 ELSE 0 END) as has_completed,
        SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) as has_delivered,
        ROUND(100.0 * SUM(CASE WHEN confirmed_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as confirmed_pct,
        ROUND(100.0 * SUM(CASE WHEN picked_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as picked_pct,
        ROUND(100.0 * SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as delivered_pct
    FROM orders
""", conn)
row = lifecycle_df.iloc[0]
print(f"Total Orders:              {row['total_orders']:>6}")
print(f"With confirmed_at:         {row['has_confirmed']:>6} ({row['confirmed_pct']:>5.1f}%)")
print(f"With picked_at:            {row['has_picked']:>6} ({row['picked_pct']:>5.1f}%)")
print(f"With picking_completed_at: {row['has_completed']:>6}")
print(f"With delivered_at:         {row['has_delivered']:>6} ({row['delivered_pct']:>5.1f}%)")

# 4. Bundle Statistics
print("\n📦 BUNDLE STATISTICS")
print("-" * 70)
bundle_stats = pd.read_sql("""
    SELECT 
        COUNT(*) as total_bundles,
        SUM(order_count) as total_orders_in_bundles,
        ROUND(AVG(order_count), 1) as avg_orders_per_bundle,
        MIN(order_count) as min_orders,
        MAX(order_count) as max_orders,
        ROUND(AVG(total_distance_km), 1) as avg_distance_km,
        ROUND(AVG(estimated_duration_min), 1) as avg_duration_min,
        SUM(CASE WHEN driver_id IS NOT NULL THEN 1 ELSE 0 END) as bundles_with_driver,
        SUM(CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END) as completed_bundles
    FROM bundles
""", conn)
if len(bundle_stats) > 0 and bundle_stats.iloc[0]['total_bundles'] > 0:
    bs = bundle_stats.iloc[0]
    print(f"Total Bundles:           {bs['total_bundles']:>6}")
    print(f"Orders in Bundles:       {bs['total_orders_in_bundles']:>6}")
    print(f"Avg Orders/Bundle:       {bs['avg_orders_per_bundle']:>6.1f}")
    print(f"Min-Max Orders/Bundle:   {bs['min_orders']:>6} - {bs['max_orders']}")
    print(f"Avg Distance:            {bs['avg_distance_km']:>6.1f} km")
    print(f"Avg Duration:            {bs['avg_duration_min']:>6.1f} min")
    print(f"With Drivers Assigned:   {bs['bundles_with_driver']:>6}")
    print(f"Completed Bundles:       {bs['completed_bundles']:>6}")
else:
    print("No bundles found")

# 5. Prediction Service Status
print("\n🤖 PREDICTION SERVICE STATUS")
print("-" * 70)
pred_stats = pd.read_sql("""
    SELECT 
        COUNT(*) as total_confirmed,
        SUM(CASE WHEN prediction_sent = 1 THEN 1 ELSE 0 END) as sent_for_prediction,
        ROUND(100.0 * SUM(CASE WHEN prediction_sent = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as sent_pct
    FROM orders
    WHERE status = 'confirmed'
""", conn)
ps = pred_stats.iloc[0]
sent = ps['sent_for_prediction'] if ps['sent_for_prediction'] else 0
pct = ps['sent_pct'] if ps['sent_pct'] else 0.0
print(f"Confirmed Orders:        {ps['total_confirmed']:>6}")
print(f"Sent for Prediction:     {sent:>6} ({pct:>5.1f}%)")

# 6. Recent Activity (last 30 minutes)
print("\n🕐 RECENT ACTIVITY (Last 30 minutes)")
print("-" * 70)
recent = pd.read_sql("""
    SELECT 
        COUNT(*) as recent_orders,
        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
        SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
        SUM(CASE WHEN status = 'picking' THEN 1 ELSE 0 END) as picking,
        SUM(CASE WHEN status = 'out_for_delivery' THEN 1 ELSE 0 END) as out_for_delivery,
        SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
        SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled
    FROM orders
    WHERE datetime(created_at) > datetime('now', '-30 minutes')
""", conn)
r = recent.iloc[0]
total = r['recent_orders']
if total > 0:
    print(f"Total Recent Orders:     {total:>6}")
    print(f"  Pending:               {r['pending']:>6}")
    print(f"  Confirmed:             {r['confirmed']:>6}")
    print(f"  Picking:               {r['picking']:>6}")
    print(f"  Out for Delivery:      {r['out_for_delivery']:>6}")
    print(f"  Delivered:             {r['delivered']:>6}")
    print(f"  Canceled:              {r['canceled']:>6}")
else:
    print("No orders created in last 30 minutes")
    print("Tip: Start live generation with POST /services/start-all")

# 7. Data Quality Checks
print("\n✅ DATA QUALITY CHECKS")
print("-" * 70)

orphan_orders = pd.read_sql("""
    SELECT COUNT(*) as count
    FROM orders o
    LEFT JOIN order_items oi ON o.order_id = oi.order_id
    WHERE oi.order_item_id IS NULL
""", conn).iloc[0]['count']
print(f"Orders without items:    {orphan_orders:>6} {'✓' if orphan_orders == 0 else '⚠️'}")

orphan_bundles = pd.read_sql("""
    SELECT COUNT(*) as count
    FROM bundles b
    LEFT JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
    WHERE bs.id IS NULL
""", conn).iloc[0]['count']
print(f"Bundles without stops:   {orphan_bundles:>6} {'✓' if orphan_bundles == 0 else '⚠️'}")

invalid_timestamps = pd.read_sql("""
    SELECT COUNT(*) as count
    FROM orders
    WHERE status = 'delivered'
    AND (
        delivered_at IS NULL 
        OR picked_at IS NULL
        OR confirmed_at IS NULL
        OR datetime(delivered_at) < datetime(picked_at)
        OR datetime(picked_at) < datetime(confirmed_at)
        OR datetime(confirmed_at) < datetime(created_at)
    )
""", conn).iloc[0]['count']
print(f"Invalid timestamps:      {invalid_timestamps:>6} {'✓' if invalid_timestamps == 0 else '⚠️'}")

# 8. Order Value Statistics
print("\n💰 ORDER VALUE STATISTICS")
print("-" * 70)
value_stats = pd.read_sql("""
    SELECT 
        ROUND(AVG(total), 2) as avg_total,
        ROUND(MIN(total), 2) as min_total,
        ROUND(MAX(total), 2) as max_total,
        ROUND(AVG(subtotal), 2) as avg_subtotal,
        ROUND(AVG(tip), 2) as avg_tip,
        ROUND(AVG(delivery_fee), 2) as avg_delivery_fee
    FROM orders
""", conn)
vs = value_stats.iloc[0]
print(f"Avg Order Total:         ${vs['avg_total']:>7.2f}")
print(f"Min-Max Total:           ${vs['min_total']:>7.2f} - ${vs['max_total']:>7.2f}")
print(f"Avg Subtotal:            ${vs['avg_subtotal']:>7.2f}")
print(f"Avg Tip:                 ${vs['avg_tip']:>7.2f}")
print(f"Avg Delivery Fee:        ${vs['avg_delivery_fee']:>7.2f}")

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE")
print("=" * 70)

conn.close()
