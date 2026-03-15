#!/usr/bin/env python3
"""
Analyze CSV exports to identify realism issues in simulated grocery delivery data.
Checks for patterns, anomalies, and areas where the data may not reflect real-world behavior.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import numpy as np

# Path to exports directory
EXPORTS_DIR = Path("/Users/josephruiz/Documents/GitHub/fake_grocery_delivery_service/exports")

def load_data():
    """Load all CSV files."""
    print("Loading CSV files...")
    data = {}
    files = {
        'stores': 'stores.csv',
        'customers': 'customers.csv',
        'drivers': 'drivers.csv',
        'parent_products': 'parent_products.csv',
        'store_products': 'store_products.csv',
        'orders': 'orders.csv',
        'order_items': 'order_items.csv',
        'bundles': 'bundles.csv',
        'bundle_stops': 'bundle_stops.csv'
    }
    
    for key, filename in files.items():
        filepath = EXPORTS_DIR / filename
        if filepath.exists():
            data[key] = pd.read_csv(filepath)
            print(f"  ✓ {key}: {len(data[key]):,} rows")
        else:
            print(f"  ✗ {key}: FILE NOT FOUND")
            data[key] = pd.DataFrame()
    
    return data

def analyze_basic_stats(data):
    """Basic dataset overview."""
    print("\n" + "="*80)
    print("DATASET OVERVIEW")
    print("="*80)
    
    for name, df in data.items():
        print(f"{name:20s}: {len(df):,} rows")

def analyze_order_distribution(data):
    """Analyze order status, values, and temporal patterns."""
    print("\n" + "="*80)
    print("ORDER ANALYSIS")
    print("="*80)
    
    orders = data['orders']
    if orders.empty:
        print("No orders data available")
        return
    
    # Status distribution
    print("\n📊 Order Status Distribution:")
    status_dist = orders['status'].value_counts()
    for status, count in status_dist.items():
        pct = 100 * count / len(orders)
        print(f"  {status:20s}: {count:6,} ({pct:5.1f}%)")
    
    # ISSUE CHECK: Unrealistic status ratios
    delivered_pct = (orders['status'] == 'delivered').sum() / len(orders) * 100
    canceled_pct = (orders['status'] == 'canceled').sum() / len(orders) * 100
    
    print(f"\n⚠️  REALISM CHECK - Order Completion:")
    if delivered_pct > 85:
        print(f"  ⚠️  {delivered_pct:.1f}% delivered - Too high? Real-world: 70-80%")
    elif delivered_pct < 60:
        print(f"  ⚠️  {delivered_pct:.1f}% delivered - Too low? Real-world: 70-80%")
    else:
        print(f"  ✓ {delivered_pct:.1f}% delivered - Realistic")
    
    if canceled_pct > 15:
        print(f"  ⚠️  {canceled_pct:.1f}% canceled - Too high? Real-world: 5-10%")
    elif canceled_pct < 2:
        print(f"  ⚠️  {canceled_pct:.1f}% canceled - Too low? Real-world: 5-10%")
    else:
        print(f"  ✓ {canceled_pct:.1f}% canceled - Realistic")
    
    # Order values
    non_canceled = orders[orders['status'] != 'canceled']
    print(f"\n💰 Order Values (non-canceled):")
    print(f"  Min:     ${non_canceled['total'].min():8.2f}")
    print(f"  Avg:     ${non_canceled['total'].mean():8.2f}")
    print(f"  Median:  ${non_canceled['total'].median():8.2f}")
    print(f"  Max:     ${non_canceled['total'].max():8.2f}")
    
    # ISSUE CHECK: Unrealistic order values
    avg_order = non_canceled['total'].mean()
    print(f"\n⚠️  REALISM CHECK - Order Values:")
    if avg_order > 100:
        print(f"  ⚠️  Avg ${avg_order:.2f} - Too high? Real-world grocery avg: $35-$65")
    elif avg_order < 20:
        print(f"  ⚠️  Avg ${avg_order:.2f} - Too low? Real-world grocery avg: $35-$65")
    else:
        print(f"  ✓ Avg ${avg_order:.2f} - Realistic range")
    
    # Tip analysis
    print(f"\n💵 Tip Analysis:")
    print(f"  Avg tip:     ${non_canceled['tip'].mean():6.2f}")
    avg_tip_pct = 100 * non_canceled['tip'].mean() / non_canceled['total'].mean()
    print(f"  Avg tip %:   {avg_tip_pct:6.1f}%")
    
    print(f"\n⚠️  REALISM CHECK - Tips:")
    if avg_tip_pct > 20:
        print(f"  ⚠️  {avg_tip_pct:.1f}% - Too generous? Real-world: 10-15%")
    elif avg_tip_pct < 8:
        print(f"  ⚠️  {avg_tip_pct:.1f}% - Too low? Real-world: 10-15%")
    else:
        print(f"  ✓ {avg_tip_pct:.1f}% - Realistic")

def analyze_temporal_patterns(data):
    """Check for unrealistic temporal patterns."""
    print("\n" + "="*80)
    print("TEMPORAL PATTERNS")
    print("="*80)
    
    orders = data['orders']
    if orders.empty or 'created_at' not in orders.columns:
        print("No temporal data available")
        return
    
    # Convert to datetime
    orders['created_at'] = pd.to_datetime(orders['created_at'])
    
    # Hour distribution
    orders['hour'] = orders['created_at'].dt.hour
    hour_dist = orders['hour'].value_counts().sort_index()
    
    print("\n🕐 Orders by Hour of Day (Top 10):")
    top_hours = hour_dist.sort_values(ascending=False).head(10)
    for hour, count in top_hours.items():
        pct = 100 * count / len(orders)
        print(f"  {hour:02d}:00 - {count:5,} orders ({pct:4.1f}%)")
    
    # ISSUE CHECK: Unrealistic temporal distribution
    print(f"\n⚠️  REALISM CHECK - Time Distribution:")
    
    # Check if too uniform (all hours similar)
    hour_std = hour_dist.std()
    hour_mean = hour_dist.mean()
    cv = hour_std / hour_mean  # Coefficient of variation
    
    if cv < 0.3:
        print(f"  ⚠️  Too uniform across hours (CV={cv:.2f})")
        print(f"     Real-world shows clear peak hours (lunch, dinner)")
    else:
        print(f"  ✓ Shows variation across hours (CV={cv:.2f})")
    
    # Check for overnight orders (midnight-6am)
    overnight = orders[orders['hour'].between(0, 5)]
    overnight_pct = 100 * len(overnight) / len(orders)
    
    if overnight_pct > 10:
        print(f"  ⚠️  {overnight_pct:.1f}% overnight (0-6am) - Too high?")
    else:
        print(f"  ✓ {overnight_pct:.1f}% overnight orders - Reasonable")
    
    # Day of week
    orders['dow'] = orders['created_at'].dt.dayofweek
    dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    print(f"\n📅 Orders by Day of Week:")
    for day_num in range(7):
        count = (orders['dow'] == day_num).sum()
        pct = 100 * count / len(orders)
        print(f"  {dow_names[day_num]}: {count:5,} ({pct:4.1f}%)")
    
    # Check weekend vs weekday
    weekend = orders[orders['dow'].isin([5, 6])]
    weekend_pct = 100 * len(weekend) / len(orders)
    
    print(f"\n⚠️  REALISM CHECK - Weekend Orders:")
    if abs(weekend_pct - 28.6) > 5:  # 2/7 days = 28.6%
        print(f"  ⚠️  {weekend_pct:.1f}% on weekends - Expected ~28-30% (2 days)")
        print(f"     Real patterns may show slight weekend increase")
    else:
        print(f"  ✓ {weekend_pct:.1f}% on weekends - Reasonable distribution")

def analyze_order_items(data):
    """Analyze items per order and product patterns."""
    print("\n" + "="*80)
    print("ORDER ITEMS ANALYSIS")
    print("="*80)
    
    items = data['order_items']
    if items.empty:
        print("No order items data available")
        return
    
    # Items per order
    items_per_order = items.groupby('order_id')['quantity'].sum()
    
    print(f"\n🛒 Items per Order:")
    print(f"  Min:     {items_per_order.min()}")
    print(f"  Avg:     {items_per_order.mean():.1f}")
    print(f"  Median:  {items_per_order.median():.1f}")
    print(f"  Max:     {items_per_order.max()}")
    
    # ISSUE CHECK
    avg_items = items_per_order.mean()
    print(f"\n⚠️  REALISM CHECK - Cart Size:")
    if avg_items > 20:
        print(f"  ⚠️  Avg {avg_items:.1f} items - Large for delivery")
        print(f"     Real-world delivery: 10-15 items typical")
    elif avg_items < 3:
        print(f"  ⚠️  Avg {avg_items:.1f} items - Too small")
        print(f"     Real-world delivery: 10-15 items typical")
    else:
        print(f"  ✓ Avg {avg_items:.1f} items - Realistic")
    
    # Category distribution
    if not data['parent_products'].empty:
        items_with_products = items.merge(
            data['parent_products'][['parent_product_id', 'category']], 
            on='parent_product_id', 
            how='left'
        )
        
        print(f"\n📦 Product Categories (by items sold):")
        category_sales = items_with_products.groupby('category')['quantity'].sum().sort_values(ascending=False)
        
        for category, qty in category_sales.head(10).items():
            pct = 100 * qty / category_sales.sum()
            print(f"  {category:20s}: {qty:6,} items ({pct:4.1f}%)")

def analyze_geography(data):
    """Check geographic distribution and geofencing."""
    print("\n" + "="*80)
    print("GEOGRAPHIC DISTRIBUTION")
    print("="*80)
    
    customers = data['customers']
    drivers = data['drivers']
    stores = data['stores']
    orders = data['orders']
    
    # City distribution
    print("\n🌆 Entity Distribution by City:")
    
    for entity_name, df in [('Customers', customers), ('Drivers', drivers), ('Stores', stores)]:
        if not df.empty and 'city' in df.columns:
            city_dist = df['city'].value_counts()
            print(f"\n  {entity_name}:")
            for city, count in city_dist.items():
                pct = 100 * count / len(df)
                print(f"    {city:20s}: {count:4,} ({pct:5.1f}%)")
    
    # Check for cross-city orders
    if not orders.empty and not customers.empty and not stores.empty:
        orders_with_cities = orders.merge(
            customers[['customer_id', 'city']], 
            on='customer_id', 
            suffixes=('', '_customer')
        ).merge(
            stores[['store_id', 'city']], 
            on='store_id', 
            suffixes=('', '_store')
        )
        
        cross_city = orders_with_cities[
            orders_with_cities['city'] != orders_with_cities['city_store']
        ]
        
        cross_city_pct = 100 * len(cross_city) / len(orders_with_cities)
        
        print(f"\n⚠️  REALISM CHECK - Geofencing:")
        if cross_city_pct > 5:
            print(f"  ⚠️  {cross_city_pct:.1f}% cross-city orders - Breaks geofencing!")
            print(f"     Top violations:")
            violations = cross_city.groupby(['city', 'city_store']).size().sort_values(ascending=False).head(5)
            for (cust_city, store_city), count in violations.items():
                print(f"       {cust_city} → {store_city}: {count} orders")
        else:
            print(f"  ✓ {cross_city_pct:.1f}% cross-city orders - Good geofencing")

def analyze_bundles(data):
    """Analyze bundle efficiency and driver assignment."""
    print("\n" + "="*80)
    print("BUNDLE & DRIVER ANALYSIS")
    print("="*80)
    
    bundles = data['bundles']
    bundle_stops = data['bundle_stops']
    
    if bundles.empty:
        print("No bundles data available")
        return
    
    # Stops per bundle
    if not bundle_stops.empty:
        stops_per_bundle = bundle_stops.groupby('bundle_id').size()
        
        print(f"\n📦 Bundle Efficiency:")
        print(f"  Total bundles:     {len(bundles):,}")
        print(f"  Avg stops/bundle:  {stops_per_bundle.mean():.1f}")
        print(f"  Min stops:         {stops_per_bundle.min()}")
        print(f"  Max stops:         {stops_per_bundle.max()}")
        
        # ISSUE CHECK
        avg_stops = stops_per_bundle.mean()
        print(f"\n⚠️  REALISM CHECK - Bundle Size:")
        if avg_stops < 2:
            print(f"  ⚠️  Avg {avg_stops:.1f} stops - Too small, inefficient")
            print(f"     Real-world batching: 3-5 orders per bundle typical")
        elif avg_stops > 8:
            print(f"  ⚠️  Avg {avg_stops:.1f} stops - Too large, delays")
            print(f"     Real-world batching: 3-5 orders per bundle typical")
        else:
            print(f"  ✓ Avg {avg_stops:.1f} stops - Realistic bundling")
    
    # Driver workload
    if not data['drivers'].empty:
        driver_bundles = bundles.groupby('driver_id').size().sort_values(ascending=False)
        
        print(f"\n🚗 Driver Workload Distribution:")
        print(f"  Drivers with bundles: {len(driver_bundles)}")
        print(f"  Avg bundles/driver:   {driver_bundles.mean():.1f}")
        print(f"  Max bundles:          {driver_bundles.max()}")
        print(f"  Min bundles:          {driver_bundles.min()}")
        
        # Check for idle drivers
        total_drivers = len(data['drivers'])
        active_drivers = len(driver_bundles)
        idle_drivers = total_drivers - active_drivers
        
        print(f"\n⚠️  REALISM CHECK - Driver Utilization:")
        if idle_drivers > 0:
            idle_pct = 100 * idle_drivers / total_drivers
            print(f"  ⚠️  {idle_drivers} drivers ({idle_pct:.1f}%) with no bundles")
            if idle_pct > 30:
                print(f"     High idle rate - overstaffed or bundling issue?")
        else:
            print(f"  ✓ All drivers have assignments")

def analyze_pricing(data):
    """Check for pricing anomalies."""
    print("\n" + "="*80)
    print("PRICING ANALYSIS")
    print("="*80)
    
    parent_products = data['parent_products']
    store_products = data['store_products']
    
    if parent_products.empty or store_products.empty:
        print("No pricing data available")
        return
    
    # Merge to compare prices
    price_comparison = store_products.merge(
        parent_products[['parent_product_id', 'base_price']], 
        on='parent_product_id'
    )
    
    price_comparison['variance_pct'] = 100 * (
        price_comparison['price'] - price_comparison['base_price']
    ) / price_comparison['base_price']
    
    print(f"\n💲 Store vs Base Price Variance:")
    print(f"  Avg variance:  {price_comparison['variance_pct'].mean():+.1f}%")
    print(f"  Min variance:  {price_comparison['variance_pct'].min():+.1f}%")
    print(f"  Max variance:  {price_comparison['variance_pct'].max():+.1f}%")
    
    # ISSUE CHECK
    print(f"\n⚠️  REALISM CHECK - Price Variance:")
    
    # Check if variance is too uniform
    variance_std = price_comparison['variance_pct'].std()
    if variance_std < 2:
        print(f"  ⚠️  Low variance spread (σ={variance_std:.1f}%)")
        print(f"     Real stores have more varied pricing strategies")
    else:
        print(f"  ✓ Reasonable variance spread (σ={variance_std:.1f}%)")
    
    # Check for outliers
    extreme_high = (price_comparison['variance_pct'] > 20).sum()
    extreme_low = (price_comparison['variance_pct'] < -20).sum()
    
    if extreme_high > 0 or extreme_low > 0:
        print(f"  ⚠️  {extreme_high} products >20% above base")
        print(f"  ⚠️  {extreme_low} products >20% below base")
        print(f"     Check if variance range is realistic")

def analyze_customer_behavior(data):
    """Analyze customer ordering patterns."""
    print("\n" + "="*80)
    print("CUSTOMER BEHAVIOR")
    print("="*80)
    
    orders = data['orders']
    customers = data['customers']
    
    if orders.empty or customers.empty:
        print("No customer data available")
        return
    
    # Orders per customer
    orders_per_customer = orders.groupby('customer_id').size()
    
    print(f"\n👥 Customer Activity:")
    print(f"  Total customers:        {len(customers):,}")
    print(f"  Customers with orders:  {len(orders_per_customer):,}")
    print(f"  Avg orders/customer:    {orders_per_customer.mean():.1f}")
    print(f"  Max orders:             {orders_per_customer.max()}")
    
    # Distribution
    print(f"\n📊 Order Frequency Distribution:")
    order_freq_dist = orders_per_customer.value_counts().sort_index().head(10)
    for num_orders, num_customers in order_freq_dist.items():
        pct = 100 * num_customers / len(orders_per_customer)
        print(f"  {num_orders:2d} orders: {num_customers:5,} customers ({pct:5.1f}%)")
    
    # ISSUE CHECK
    print(f"\n⚠️  REALISM CHECK - Customer Retention:")
    
    one_time = (orders_per_customer == 1).sum()
    one_time_pct = 100 * one_time / len(orders_per_customer)
    
    if one_time_pct > 70:
        print(f"  ⚠️  {one_time_pct:.1f}% one-time customers - Very high churn")
    elif one_time_pct < 30:
        print(f"  ⚠️  {one_time_pct:.1f}% one-time customers - Too loyal?")
        print(f"     Real-world grocery delivery: 40-60% try once")
    else:
        print(f"  ✓ {one_time_pct:.1f}% one-time customers - Realistic")
    
    # Check for inactive customers
    customers_with_orders = set(orders['customer_id'])
    inactive = len(customers) - len(customers_with_orders)
    
    if inactive > 0:
        inactive_pct = 100 * inactive / len(customers)
        print(f"  ⚠️  {inactive} customers ({inactive_pct:.1f}%) never ordered")

def analyze_order_lifecycle(data):
    """Analyze order timing and lifecycle."""
    print("\n" + "="*80)
    print("ORDER LIFECYCLE TIMING")
    print("="*80)
    
    orders = data['orders']
    if orders.empty:
        print("No orders data available")
        return
    
    # Filter delivered orders with complete timestamps
    delivered = orders[orders['status'] == 'delivered'].copy()
    
    if delivered.empty:
        print("No delivered orders to analyze")
        return
    
    # Convert timestamps
    for col in ['created_at', 'confirmed_at', 'picked_at', 'delivered_at']:
        if col in delivered.columns:
            delivered[col] = pd.to_datetime(delivered[col])
    
    # Calculate durations
    if 'confirmed_at' in delivered.columns and 'created_at' in delivered.columns:
        delivered['mins_to_confirm'] = (
            delivered['confirmed_at'] - delivered['created_at']
        ).dt.total_seconds() / 60
    
    if 'picked_at' in delivered.columns and 'confirmed_at' in delivered.columns:
        delivered['mins_to_pick'] = (
            delivered['picked_at'] - delivered['confirmed_at']
        ).dt.total_seconds() / 60
    
    if 'delivered_at' in delivered.columns and 'picked_at' in delivered.columns:
        delivered['mins_to_deliver'] = (
            delivered['delivered_at'] - delivered['picked_at']
        ).dt.total_seconds() / 60
    
    if 'delivered_at' in delivered.columns and 'created_at' in delivered.columns:
        delivered['total_mins'] = (
            delivered['delivered_at'] - delivered['created_at']
        ).dt.total_seconds() / 60
    
    print(f"\n⏱️  Delivery Timeline (n={len(delivered):,} delivered orders):")
    
    if 'mins_to_confirm' in delivered.columns:
        print(f"  Order → Confirmed:  {delivered['mins_to_confirm'].mean():.1f} min avg")
    
    if 'mins_to_pick' in delivered.columns:
        print(f"  Confirmed → Picked: {delivered['mins_to_pick'].mean():.1f} min avg")
    
    if 'mins_to_deliver' in delivered.columns:
        print(f"  Picked → Delivered: {delivered['mins_to_deliver'].mean():.1f} min avg")
    
    if 'total_mins' in delivered.columns:
        print(f"  Total time:         {delivered['total_mins'].mean():.1f} min avg")
        
        # ISSUE CHECK
        avg_total = delivered['total_mins'].mean()
        print(f"\n⚠️  REALISM CHECK - Delivery Time:")
        if avg_total < 30:
            print(f"  ⚠️  Avg {avg_total:.1f} min - Too fast!")
            print(f"     Real-world delivery: 45-90 minutes typical")
        elif avg_total > 120:
            print(f"  ⚠️  Avg {avg_total:.1f} min - Too slow")
            print(f"     Real-world delivery: 45-90 minutes typical")
        else:
            print(f"  ✓ Avg {avg_total:.1f} min - Realistic window")


def analyze_ml_features(data):
    """Analyze ML-relevant features for model training quality."""
    print("\n" + "="*80)
    print("ML FEATURE ANALYSIS")
    print("="*80)
    
    orders = data['orders']
    customers = data['customers']
    order_items = data['order_items']
    
    if orders.empty:
        print("No orders data available")
        return
    
    # Check for ML feature columns
    ml_columns = ['weather_condition', 'traffic_multiplier', 'is_peak_hour', 
                  'is_weekend', 'customer_order_number', 'days_since_last_order', 
                  'cancellation_risk']
    
    available_ml_cols = [col for col in ml_columns if col in orders.columns]
    
    print(f"\n🤖 ML Feature Availability:")
    for col in ml_columns:
        if col in orders.columns:
            non_null = orders[col].notna().sum()
            pct = 100 * non_null / len(orders)
            print(f"  ✓ {col}: {pct:.1f}% populated")
        else:
            print(f"  ✗ {col}: NOT AVAILABLE")
    
    # Weather distribution
    if 'weather_condition' in orders.columns:
        print(f"\n🌤️  Weather Distribution:")
        weather_dist = orders['weather_condition'].value_counts()
        for weather, count in weather_dist.head(6).items():
            pct = 100 * count / len(orders)
            print(f"  {weather:15s}: {count:6,} ({pct:5.1f}%)")
    
    # Traffic multiplier distribution
    if 'traffic_multiplier' in orders.columns:
        print(f"\n🚗 Traffic Multiplier Stats:")
        traffic = orders['traffic_multiplier']
        print(f"  Min: {traffic.min():.2f}x")
        print(f"  Avg: {traffic.mean():.2f}x")
        print(f"  Max: {traffic.max():.2f}x")
        
        # Check for realistic distribution
        high_traffic_pct = (traffic > 1.3).sum() / len(traffic) * 100
        print(f"  High traffic (>1.3x): {high_traffic_pct:.1f}%")
    
    # Customer order sequence analysis (CLV potential)
    if 'customer_order_number' in orders.columns:
        print(f"\n📈 Customer Order Sequence (CLV Feature):")
        seq = orders['customer_order_number']
        print(f"  First-time orders (seq=1): {(seq == 1).sum():,} ({100*(seq==1).sum()/len(seq):.1f}%)")
        print(f"  Repeat orders (seq>1): {(seq > 1).sum():,} ({100*(seq>1).sum()/len(seq):.1f}%)")
        print(f"  Max order sequence: {seq.max()}")
    
    # Cancellation risk distribution
    if 'cancellation_risk' in orders.columns:
        print(f"\n⚡ Cancellation Risk Distribution:")
        risk = orders['cancellation_risk']
        print(f"  Avg risk: {risk.mean():.1%}")
        print(f"  Low risk (<5%): {(risk < 0.05).sum():,} orders")
        print(f"  Med risk (5-15%): {((risk >= 0.05) & (risk < 0.15)).sum():,} orders")
        print(f"  High risk (>15%): {(risk >= 0.15).sum():,} orders")
        
        # Validate risk vs actual cancellations
        canceled = orders[orders['status'] == 'canceled']
        delivered = orders[orders['status'] == 'delivered']
        if len(canceled) > 0 and len(delivered) > 0:
            avg_risk_canceled = canceled['cancellation_risk'].mean()
            avg_risk_delivered = delivered['cancellation_risk'].mean()
            print(f"\n  Risk vs Outcome Correlation:")
            print(f"    Avg risk for canceled: {avg_risk_canceled:.1%}")
            print(f"    Avg risk for delivered: {avg_risk_delivered:.1%}")
            if avg_risk_canceled > avg_risk_delivered:
                print(f"  ✓ Risk correlates with cancellation - good for ML!")
            else:
                print(f"  ⚠️  Risk does NOT correlate with cancellation - review logic")
    
    # Market basket analysis readiness
    print(f"\n🛒 Market Basket Analysis Readiness:")
    if not order_items.empty:
        items_per_order = order_items.groupby('order_id').size()
        multi_item_orders = (items_per_order > 1).sum()
        pct_multi = 100 * multi_item_orders / len(items_per_order)
        print(f"  Multi-item orders: {multi_item_orders:,} ({pct_multi:.1f}%)")
        print(f"  Suitable for association rules: {'✓ Yes' if pct_multi > 50 else '⚠️  Limited'}")
    
    # Check persona distribution if available
    if 'persona' in customers.columns:
        print(f"\n👤 Customer Persona Distribution:")
        persona_dist = customers['persona'].value_counts()
        for persona, count in persona_dist.items():
            pct = 100 * count / len(customers)
            print(f"  {persona:20s}: {count:6,} ({pct:5.1f}%)")


def analyze_seasonality(data):
    """Analyze seasonal patterns for time series modeling."""
    print("\n" + "="*80)
    print("SEASONALITY ANALYSIS (Time Series Features)")
    print("="*80)
    
    orders = data['orders']
    if orders.empty:
        print("No orders data available")
        return
    
    orders = orders.copy()
    orders['created_at'] = pd.to_datetime(orders['created_at'])
    orders['month'] = orders['created_at'].dt.month
    orders['week'] = orders['created_at'].dt.isocalendar().week
    orders['day_of_year'] = orders['created_at'].dt.dayofyear
    orders['date'] = orders['created_at'].dt.date
    
    # Monthly trends
    print(f"\n📅 Monthly Order Distribution:")
    month_dist = orders.groupby('month').size()
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month in sorted(month_dist.index):
        count = month_dist[month]
        pct = 100 * count / len(orders)
        bar = '█' * int(pct / 2)
        print(f"  {month_names[month-1]}: {count:6,} ({pct:5.1f}%) {bar}")
    
    # Check for realistic seasonality
    if len(month_dist) >= 3:
        cv = month_dist.std() / month_dist.mean()
        print(f"\n⚠️  REALISM CHECK - Seasonality:")
        if cv < 0.05:
            print(f"  ⚠️  Very uniform monthly distribution (CV={cv:.2f})")
            print(f"     Real-world: expect 10-30% seasonal variation")
            print(f"     Suggestion: Add holiday spikes, summer dips")
        elif cv > 0.5:
            print(f"  ⚠️  Highly variable monthly distribution (CV={cv:.2f})")
            print(f"     May indicate data generation artifacts")
        else:
            print(f"  ✓ Reasonable monthly variation (CV={cv:.2f})")
    
    # Recency bias check - are recent days getting more orders?
    print(f"\n📈 Recency Bias Check (Business Growth Simulation):")
    daily_orders = orders.groupby('date').size().sort_index()
    if len(daily_orders) >= 14:
        # Compare first half vs second half of time window
        midpoint = len(daily_orders) // 2
        first_half_avg = daily_orders.iloc[:midpoint].mean()
        second_half_avg = daily_orders.iloc[midpoint:].mean()
        growth_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1.0
        
        print(f"  Older half avg: {first_half_avg:.1f} orders/day")
        print(f"  Recent half avg: {second_half_avg:.1f} orders/day")
        print(f"  Growth ratio: {growth_ratio:.2f}x")
        
        if 0.95 <= growth_ratio <= 1.05:
            print(f"  ⚠️  Very uniform distribution over time (ratio={growth_ratio:.2f})")
            print(f"     Real-world: expect recent data to have 20-50% more volume")
        elif growth_ratio > 1.1:
            print(f"  ✓ Shows recency bias - good for ML time series!")
        else:
            print(f"  ⚠️  Declining volume over time? (ratio={growth_ratio:.2f})")
    
    # Daily uniformity check
    print(f"\n📊 Daily Order Volume Variance:")
    if len(daily_orders) >= 7:
        daily_cv = daily_orders.std() / daily_orders.mean()
        print(f"  Min orders/day: {daily_orders.min()}")
        print(f"  Max orders/day: {daily_orders.max()}")
        print(f"  Avg orders/day: {daily_orders.mean():.1f}")
        print(f"  Coefficient of variation: {daily_cv:.2f}")
        
        if daily_cv < 0.10:
            print(f"  ⚠️  Very uniform daily volume (CV={daily_cv:.2f})")
            print(f"     Real-world: expect 15-40% daily variation")
        elif daily_cv > 0.5:
            print(f"  ⚠️  High daily variance (CV={daily_cv:.2f}) - may be realistic for small datasets")
        else:
            print(f"  ✓ Reasonable daily variation (CV={daily_cv:.2f})")


def main():
    """Run all analyses."""
    print("\n" + "="*80)
    print("GROCERY DELIVERY DATA REALISM ANALYSIS")
    print("Analyzing CSV exports for potential issues")
    print("="*80)
    
    # Load data
    data = load_data()
    
    # Run analyses
    analyze_basic_stats(data)
    analyze_order_distribution(data)
    analyze_temporal_patterns(data)
    analyze_order_items(data)
    analyze_geography(data)
    analyze_bundles(data)
    analyze_pricing(data)
    analyze_customer_behavior(data)
    analyze_order_lifecycle(data)
    analyze_ml_features(data)
    analyze_seasonality(data)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\n✓ Review warnings above to identify realism issues")
    print("✓ Compare patterns to real-world grocery delivery metrics")
    print("✓ Consider adjusting generators for more realistic distributions\n")

if __name__ == "__main__":
    main()
