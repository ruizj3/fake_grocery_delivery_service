"""
Efficiently bundle historical orders in time-based batches.

This script processes orders day-by-day to avoid memory issues and provides
realistic bundle assignments for historical data.

Usage:
    python scripts/bundle_historical_orders.py --days 60
    python scripts/bundle_historical_orders.py --days 60 --batch-hours 6
    python scripts/bundle_historical_orders.py --skip-delivered  # Only bundle active orders
"""

import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.bundling import BundlingService


def get_date_range(conn):
    """Get the min/max order dates from database."""
    cursor = conn.cursor()
    cursor.execute('SELECT MIN(created_at), MAX(created_at) FROM orders')
    min_date, max_date = cursor.fetchone()
    if not min_date:
        return None, None
    return (min_date if isinstance(min_date, datetime) else datetime.fromisoformat(min_date),
            max_date if isinstance(max_date, datetime) else datetime.fromisoformat(max_date))


def count_orders_to_bundle(conn, skip_delivered=False):
    """Count how many orders need bundling."""
    cursor = conn.cursor()
    
    if skip_delivered:
        # Only count non-delivered orders
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE status IN ('confirmed', 'picking', 'out_for_delivery')
            AND order_id NOT IN (SELECT order_id FROM bundle_stops)
        """)
    else:
        # Count all non-canceled, non-pending orders
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE status IN ('confirmed', 'picking', 'out_for_delivery', 'delivered')
            AND order_id NOT IN (SELECT order_id FROM bundle_stops)
        """)
    
    return cursor.fetchone()[0]


def bundle_time_window(bundler, start_time, end_time, skip_delivered=False):
    """Bundle all orders within a specific time window."""
    
    # Fetch orders in this time window
    stops = bundler.fetch_pending_orders(
        start_time=start_time,
        end_time=end_time,
        include_delivered=not skip_delivered
    )
    
    if not stops:
        return 0, 0
    
    # Create bundles
    bundles = bundler.create_bundles(stops)
    
    if not bundles:
        return len(stops), 0
    
    # Assign drivers
    bundles = bundler.assign_drivers(bundles)
    
    # Save to database
    bundler.save_bundles_to_db(bundles)
    
    return len(stops), len(bundles)


def main():
    parser = argparse.ArgumentParser(description='Bundle historical orders efficiently')
    parser.add_argument('--batch-hours', type=int, default=12,
                       help='Process orders in batches of this many hours (default: 12)')
    parser.add_argument('--skip-delivered', action='store_true',
                       help='Skip bundling delivered orders (only bundle active orders)')
    parser.add_argument('--limit-days', type=int,
                       help='Only bundle orders from the most recent N days')
    
    args = parser.parse_args()
    
    conn = sqlite3.connect('database/grocery_delivery.db')
    bundler = BundlingService()
    
    print('='*80)
    print('HISTORICAL ORDER BUNDLING')
    print('='*80)
    
    # Get date range
    min_date, max_date = get_date_range(conn)
    if not min_date:
        print('❌ No orders found in database')
        conn.close()
        return
    
    print(f'\n📅 Order Date Range:')
    print(f'   Earliest: {min_date.strftime("%Y-%m-%d %H:%M")}')
    print(f'   Latest:   {max_date.strftime("%Y-%m-%d %H:%M")}')
    print(f'   Span:     {(max_date - min_date).days} days')
    
    # Apply limit if specified
    if args.limit_days:
        min_date = max_date - timedelta(days=args.limit_days)
        print(f'\n⚠️  Limiting to most recent {args.limit_days} days')
        print(f'   Processing from: {min_date.strftime("%Y-%m-%d %H:%M")}')
    
    # Count orders to process
    total_orders = count_orders_to_bundle(conn, args.skip_delivered)
    print(f'\n📦 Orders to Bundle: {total_orders:,}')
    
    if args.skip_delivered:
        print(f'   (Skipping delivered orders)')
    
    if total_orders == 0:
        print('✅ All orders are already bundled!')
        conn.close()
        return
    
    # Calculate time windows
    batch_delta = timedelta(hours=args.batch_hours)
    current_time = min_date
    batch_num = 0
    total_processed = 0
    total_bundles = 0
    
    print(f'\n🔄 Processing in {args.batch_hours}-hour batches...\n')
    
    start_overall = datetime.now()
    
    while current_time < max_date:
        batch_num += 1
        batch_end = min(current_time + batch_delta, max_date)
        
        batch_start_time = datetime.now()
        orders_bundled, bundles_created = bundle_time_window(
            bundler, current_time, batch_end, args.skip_delivered
        )
        batch_elapsed = (datetime.now() - batch_start_time).total_seconds()
        
        total_processed += orders_bundled
        total_bundles += bundles_created
        
        if orders_bundled > 0:
            orders_per_sec = orders_bundled / batch_elapsed if batch_elapsed > 0 else 0
            print(f'Batch {batch_num:3d}: {current_time.strftime("%Y-%m-%d %H:%M")} → '
                  f'{orders_bundled:5,} orders → {bundles_created:4,} bundles '
                  f'({batch_elapsed:.1f}s, {orders_per_sec:.0f} orders/sec)')
        
        current_time = batch_end
    
    elapsed = (datetime.now() - start_overall).total_seconds()
    
    conn.close()
    
    print('\n' + '='*80)
    print(f'✅ BUNDLING COMPLETE')
    print(f'   Processed: {total_processed:,} orders')
    print(f'   Created:   {total_bundles:,} bundles')
    print(f'   Time:      {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)')
    if elapsed > 0:
        print(f'   Rate:      {total_processed/elapsed:.0f} orders/second')
    print('='*80)


if __name__ == '__main__':
    main()
