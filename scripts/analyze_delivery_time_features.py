#!/usr/bin/env python3
"""
Analyze all database features for predictive value on delivery times.

This script performs comprehensive feature analysis including:
- Correlation analysis for numeric features
- ANOVA/effect size for categorical features
- Mutual information scores
- Feature importance ranking

Usage:
    python scripts/analyze_delivery_time_features.py
"""

import sqlite3
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
from scipy import stats
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import RandomForestRegressor
import warnings
warnings.filterwarnings('ignore')

DATABASE_PATH = Path(__file__).parent.parent / "database" / "grocery_delivery.db"
EXPORTS_PATH = Path(__file__).parent.parent / "exports"


class TeeWriter:
    """Write output to both console and file simultaneously."""
    
    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.file = open(file_path, 'w', encoding='utf-8')
    
    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)
    
    def flush(self):
        self.terminal.flush()
        self.file.flush()
    
    def close(self):
        self.file.close()


def load_delivery_data():
    """Load all relevant data for delivery time analysis."""
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Main query: orders with delivery times and all features
    orders_query = """
    SELECT 
        o.order_id,
        o.customer_id,
        o.store_id,
        o.status,
        o.subtotal,
        o.tax,
        o.delivery_fee,
        o.tip,
        o.total,
        o.created_at,
        o.confirmed_at,
        o.picked_at,
        o.picking_completed_at,
        o.delivered_at,
        o.delivery_latitude,
        o.delivery_longitude,
        o.weather_condition,
        o.traffic_multiplier,
        o.is_peak_hour,
        o.is_weekend,
        o.customer_order_number,
        o.days_since_last_order,
        o.cancellation_risk
    FROM orders o
    WHERE o.status = 'delivered'
      AND o.delivered_at IS NOT NULL
      AND o.created_at IS NOT NULL
    """
    
    orders = pd.read_sql_query(orders_query, conn)
    
    # Get customer info
    customers_query = """
    SELECT 
        customer_id,
        city as customer_city,
        is_premium,
        persona,
        preferred_shopping_hour,
        routine_strength
    FROM customers
    """
    customers = pd.read_sql_query(customers_query, conn)
    
    # Get store info
    stores_query = """
    SELECT 
        store_id,
        city as store_city,
        latitude as store_latitude,
        longitude as store_longitude
    FROM stores
    """
    stores = pd.read_sql_query(stores_query, conn)
    
    # Get order item counts
    items_query = """
    SELECT 
        order_id,
        COUNT(*) as item_count,
        SUM(quantity) as total_quantity,
        COUNT(DISTINCT parent_product_id) as unique_products
    FROM order_items
    GROUP BY order_id
    """
    items = pd.read_sql_query(items_query, conn)
    
    # Get bundle info if available
    try:
        bundles_query = """
        SELECT 
            bs.order_id,
            b.bundle_id,
            b.driver_id,
            bs.stop_sequence,
            (SELECT COUNT(*) FROM bundle_stops WHERE bundle_id = b.bundle_id) as stops_in_bundle
        FROM bundle_stops bs
        JOIN bundles b ON bs.bundle_id = b.bundle_id
        """
        bundles = pd.read_sql_query(bundles_query, conn)
    except:
        bundles = pd.DataFrame()
    
    # Get driver info if bundles exist
    if not bundles.empty:
        drivers_query = """
        SELECT 
            driver_id,
            city as driver_city,
            total_deliveries,
            rating,
            experience_level,
            speed_multiplier,
            reliability_score
        FROM drivers
        """
        drivers = pd.read_sql_query(drivers_query, conn)
    else:
        drivers = pd.DataFrame()
    
    conn.close()
    
    return orders, customers, stores, items, bundles, drivers


def calculate_delivery_metrics(orders, stores):
    """Calculate delivery time and related metrics."""
    df = orders.copy()
    
    # Convert timestamps (ISO8601 handles both with and without fractional seconds)
    for col in ['created_at', 'confirmed_at', 'picked_at', 'picking_completed_at', 'delivered_at']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format='ISO8601')
    
    # Calculate delivery time in minutes (total time from order to delivery)
    df['delivery_time_mins'] = (df['delivered_at'] - df['created_at']).dt.total_seconds() / 60
    
    # Calculate stage durations
    df['confirmation_time_mins'] = (df['confirmed_at'] - df['created_at']).dt.total_seconds() / 60
    df['picking_time_mins'] = (df['picking_completed_at'] - df['confirmed_at']).dt.total_seconds() / 60
    df['transit_time_mins'] = (df['delivered_at'] - df['picking_completed_at']).dt.total_seconds() / 60
    
    # Extract time features
    df['order_hour'] = df['created_at'].dt.hour
    df['order_day_of_week'] = df['created_at'].dt.dayofweek
    df['order_month'] = df['created_at'].dt.month
    
    # Merge store coordinates for distance calculation
    df = df.merge(stores[['store_id', 'store_latitude', 'store_longitude']], on='store_id', how='left')
    
    # Calculate delivery distance (Haversine)
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        return 2 * R * np.arcsin(np.sqrt(a))
    
    df['delivery_distance_km'] = haversine(
        df['store_latitude'], df['store_longitude'],
        df['delivery_latitude'], df['delivery_longitude']
    )
    
    return df


def analyze_numeric_correlations(df, target='delivery_time_mins'):
    """Analyze correlations between numeric features and delivery time."""
    print("\n" + "="*80)
    print("NUMERIC FEATURE CORRELATIONS")
    print("="*80)
    
    numeric_cols = [
        'subtotal', 'tax', 'delivery_fee', 'tip', 'total',
        'traffic_multiplier', 'customer_order_number', 'days_since_last_order',
        'cancellation_risk', 'order_hour', 'order_day_of_week',
        'delivery_distance_km', 'item_count', 'total_quantity', 'unique_products',
        'stops_in_bundle', 'stop_sequence', 'total_deliveries', 'rating',
        'speed_multiplier', 'reliability_score', 'preferred_shopping_hour', 
        'routine_strength'
    ]
    
    # Filter to columns that exist and are actually numeric
    available_cols = []
    for c in numeric_cols:
        if c in df.columns:
            try:
                col_data = pd.to_numeric(df[c], errors='coerce')
                if col_data.count() > 100:
                    available_cols.append(c)
            except Exception:
                pass
    
    results = []
    
    for col in available_cols:
        # Skip if too many NaNs
        valid_data = df[[col, target]].dropna()
        if len(valid_data) < 100:
            continue
        
        # Pearson correlation
        pearson_r, pearson_p = stats.pearsonr(valid_data[col], valid_data[target])
        
        # Spearman correlation (for non-linear relationships)
        spearman_r, spearman_p = stats.spearmanr(valid_data[col], valid_data[target])
        
        results.append({
            'feature': col,
            'pearson_r': pearson_r,
            'pearson_p': pearson_p,
            'spearman_r': spearman_r,
            'spearman_p': spearman_p,
            'abs_pearson': abs(pearson_r),
            'n_samples': len(valid_data)
        })
    
    results_df = pd.DataFrame(results).sort_values('abs_pearson', ascending=False)
    
    print(f"\n{'Feature':<30} {'Pearson r':>12} {'p-value':>12} {'Spearman r':>12} {'Samples':>10}")
    print("-" * 80)
    
    for _, row in results_df.iterrows():
        sig = "***" if row['pearson_p'] < 0.001 else "**" if row['pearson_p'] < 0.01 else "*" if row['pearson_p'] < 0.05 else ""
        print(f"{row['feature']:<30} {row['pearson_r']:>10.4f}{sig:<2} {row['pearson_p']:>12.2e} {row['spearman_r']:>12.4f} {row['n_samples']:>10,}")
    
    print("\nSignificance: *** p<0.001, ** p<0.01, * p<0.05")
    
    return results_df


def analyze_categorical_features(df, target='delivery_time_mins'):
    """Analyze categorical features using ANOVA and effect sizes."""
    print("\n" + "="*80)
    print("CATEGORICAL FEATURE ANALYSIS (ANOVA)")
    print("="*80)
    
    categorical_cols = [
        'weather_condition', 'is_peak_hour', 'is_weekend', 'is_premium',
        'persona', 'customer_city', 'store_city', 'experience_level',
        'order_day_of_week'
    ]
    
    # Safely check which columns exist, have data, AND have 2+ unique values
    available_cols = []
    for c in categorical_cols:
        if c in df.columns:
            try:
                count = df[c].count()
                n_unique = df[c].nunique()
                if count > 100 and n_unique >= 2:
                    available_cols.append(c)
            except Exception:
                pass
    
    results = []
    
    for col in available_cols:
        try:
            valid_data = df[[col, target]].dropna()
            
            if len(valid_data) < 100:
                continue
            
            # Get groups with at least 10 samples
            groups = [group[target].values for name, group in valid_data.groupby(col) if len(group) >= 10]
            if len(groups) < 2:
                continue
            
            # ANOVA
            f_stat, p_value = stats.f_oneway(*groups)
            
            # Effect size (eta-squared) - calculate efficiently
            group_sizes = valid_data.groupby(col)[target].count()
            group_means = valid_data.groupby(col)[target].mean()
            grand_mean = valid_data[target].mean()
            
            ss_between = sum(group_sizes[g] * (group_means[g] - grand_mean)**2 for g in group_sizes.index)
            ss_total = ((valid_data[target] - grand_mean)**2).sum()
            eta_squared = ss_between / ss_total if ss_total > 0 else 0
            
            results.append({
                'feature': col,
                'f_statistic': f_stat,
                'p_value': p_value,
                'eta_squared': eta_squared,
                'n_groups': len(groups),
                'n_samples': len(valid_data)
            })
        except Exception as e:
            # Skip columns that cause errors
            continue
    
    results_df = pd.DataFrame(results).sort_values('eta_squared', ascending=False)
    
    print(f"\n{'Feature':<25} {'F-stat':>12} {'p-value':>12} {'η²':>10} {'Groups':>8} {'Samples':>10}")
    print("-" * 80)
    
    for _, row in results_df.iterrows():
        sig = "***" if row['p_value'] < 0.001 else "**" if row['p_value'] < 0.01 else "*" if row['p_value'] < 0.05 else ""
        effect = "large" if row['eta_squared'] > 0.14 else "medium" if row['eta_squared'] > 0.06 else "small"
        print(f"{row['feature']:<25} {row['f_statistic']:>10.2f}{sig:<2} {row['p_value']:>12.2e} {row['eta_squared']:>10.4f} {row['n_groups']:>8} {row['n_samples']:>10,}  ({effect})")
    
    print("\nEffect size: large (η²>0.14), medium (η²>0.06), small (η²<0.06)")
    
    return results_df


def analyze_mutual_information(df, target='delivery_time_mins'):
    """Calculate mutual information scores for all features."""
    print("\n" + "="*80)
    print("MUTUAL INFORMATION ANALYSIS")
    print("="*80)
    
    # Select ONLY numeric features - no booleans or categoricals
    feature_cols = [
        'subtotal', 'total', 'traffic_multiplier', 'customer_order_number',
        'cancellation_risk', 'order_hour', 'order_day_of_week',
        'delivery_distance_km', 'item_count', 'total_quantity',
        'stops_in_bundle', 'speed_multiplier', 'reliability_score'
    ]
    
    available_cols = [c for c in feature_cols if c in df.columns]
    
    # Prepare data - convert to numeric first
    valid_data = df[available_cols + [target]].copy()
    for col in available_cols:
        valid_data[col] = pd.to_numeric(valid_data[col], errors='coerce')
    
    valid_data = valid_data.dropna()
    
    if len(valid_data) < 100:
        print("Insufficient data for mutual information analysis")
        return pd.DataFrame()
    
    X = valid_data[available_cols].values
    y = valid_data[target].values
    
    # Calculate mutual information
    mi_scores = mutual_info_regression(X, y, random_state=42)
    
    results = pd.DataFrame({
        'feature': available_cols,
        'mi_score': mi_scores
    }).sort_values('mi_score', ascending=False)
    
    print(f"\n{'Feature':<30} {'MI Score':>12} {'Relative':>12}")
    print("-" * 55)
    
    max_mi = results['mi_score'].max()
    for _, row in results.iterrows():
        rel_score = row['mi_score'] / max_mi * 100 if max_mi > 0 else 0
        bar = '█' * int(rel_score / 5)
        print(f"{row['feature']:<30} {row['mi_score']:>12.4f} {rel_score:>10.1f}% {bar}")
    
    return results


def analyze_random_forest_importance(df, target='delivery_time_mins'):
    """Use Random Forest to estimate feature importance."""
    print("\n" + "="*80)
    print("RANDOM FOREST FEATURE IMPORTANCE")
    print("="*80)
    
    # Select ONLY numeric features - no booleans/categoricals
    feature_cols = [
        'subtotal', 'total', 'traffic_multiplier', 'customer_order_number',
        'cancellation_risk', 'order_hour', 'order_day_of_week',
        'delivery_distance_km', 'item_count', 'total_quantity',
        'stops_in_bundle', 'speed_multiplier', 'reliability_score'
    ]
    
    available_cols = [c for c in feature_cols if c in df.columns]
    
    # Prepare data - convert to numeric first
    valid_data = df[available_cols + [target]].copy()
    for col in available_cols:
        valid_data[col] = pd.to_numeric(valid_data[col], errors='coerce')
    
    valid_data = valid_data.dropna()
    
    if len(valid_data) < 500:
        print("Insufficient data for Random Forest analysis (need 500+ samples)")
        return pd.DataFrame()
    
    X = valid_data[available_cols].values
    y = valid_data[target].values
    
    # Sample if too large
    if len(X) > 50000:
        sample_idx = np.random.choice(len(X), 50000, replace=False)
        X = X[sample_idx]
        y = y[sample_idx]
    
    # Fit Random Forest
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    
    results = pd.DataFrame({
        'feature': available_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n{'Feature':<30} {'Importance':>12} {'Relative':>12}")
    print("-" * 55)
    
    max_imp = results['importance'].max()
    for _, row in results.iterrows():
        rel_score = row['importance'] / max_imp * 100 if max_imp > 0 else 0
        bar = '█' * int(rel_score / 5)
        print(f"{row['feature']:<30} {row['importance']:>12.4f} {rel_score:>10.1f}% {bar}")
    
    # Model performance
    from sklearn.model_selection import cross_val_score
    cv_scores = cross_val_score(rf, X, y, cv=5, scoring='r2')
    print(f"\n📊 Model Performance (5-fold CV):")
    print(f"   R² Score: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    
    return results


def analyze_by_delivery_stage(df):
    """Analyze which features affect each stage of delivery."""
    print("\n" + "="*80)
    print("FEATURE IMPORTANCE BY DELIVERY STAGE")
    print("="*80)
    
    stages = {
        'confirmation_time_mins': 'Order → Confirmed',
        'picking_time_mins': 'Confirmed → Picked',
        'transit_time_mins': 'Picked → Delivered'
    }
    
    key_features = ['traffic_multiplier', 'delivery_distance_km', 'item_count', 
                    'total', 'order_hour', 'is_peak_hour']
    available_features = [f for f in key_features if f in df.columns]
    
    for stage_col, stage_name in stages.items():
        if stage_col not in df.columns:
            continue
            
        print(f"\n📍 {stage_name}:")
        valid_data = df[[stage_col] + available_features].dropna()
        
        if len(valid_data) < 100:
            print("   Insufficient data")
            continue
        
        correlations = []
        for feat in available_features:
            r, p = stats.pearsonr(valid_data[feat], valid_data[stage_col])
            correlations.append((feat, r, p))
        
        correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        
        for feat, r, p in correlations[:5]:
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            direction = "↑" if r > 0 else "↓"
            print(f"   {feat:<25} r={r:>7.4f}{sig:<3} {direction}")


def print_summary(numeric_results, categorical_results, mi_results, rf_results):
    """Print overall summary of most predictive features."""
    print("\n" + "="*80)
    print("🏆 FEATURE IMPORTANCE SUMMARY")
    print("="*80)
    
    # Combine all rankings
    all_features = {}
    
    # Add numeric correlations (normalized 0-1)
    if not numeric_results.empty:
        max_corr = numeric_results['abs_pearson'].max()
        for _, row in numeric_results.iterrows():
            feat = row['feature']
            score = row['abs_pearson'] / max_corr if max_corr > 0 else 0
            all_features[feat] = all_features.get(feat, []) + [score]
    
    # Add categorical effect sizes
    if not categorical_results.empty:
        max_eta = categorical_results['eta_squared'].max()
        for _, row in categorical_results.iterrows():
            feat = row['feature']
            score = row['eta_squared'] / max_eta if max_eta > 0 else 0
            all_features[feat] = all_features.get(feat, []) + [score]
    
    # Add MI scores
    if not mi_results.empty:
        max_mi = mi_results['mi_score'].max()
        for _, row in mi_results.iterrows():
            feat = row['feature']
            score = row['mi_score'] / max_mi if max_mi > 0 else 0
            all_features[feat] = all_features.get(feat, []) + [score]
    
    # Add RF importance
    if not rf_results.empty:
        max_rf = rf_results['importance'].max()
        for _, row in rf_results.iterrows():
            feat = row['feature']
            score = row['importance'] / max_rf if max_rf > 0 else 0
            all_features[feat] = all_features.get(feat, []) + [score]
    
    # Calculate average score
    summary = []
    for feat, scores in all_features.items():
        avg_score = np.mean(scores)
        summary.append({
            'feature': feat,
            'avg_score': avg_score,
            'n_methods': len(scores)
        })
    
    summary_df = pd.DataFrame(summary).sort_values('avg_score', ascending=False)
    
    print(f"\n{'Rank':<6} {'Feature':<30} {'Avg Score':>12} {'Methods':>10}")
    print("-" * 60)
    
    for i, (_, row) in enumerate(summary_df.head(15).iterrows(), 1):
        stars = '⭐' * min(5, int(row['avg_score'] * 5) + 1)
        print(f"{i:<6} {row['feature']:<30} {row['avg_score']:>12.4f} {row['n_methods']:>10} {stars}")
    
    print("\n💡 Interpretation:")
    print("   - Features with high scores across multiple methods are most reliable")
    print("   - Consider these features first when building ML models")
    print("   - Low-scoring features may add noise rather than signal")


def main():
    # Set up output to both console and file
    EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORTS_PATH / f"delivery_time_analysis_{timestamp}.txt"
    
    tee = TeeWriter(output_file)
    sys.stdout = tee
    
    try:
        print("="*80)
        print("DELIVERY TIME FEATURE ANALYSIS")
        print("Analyzing predictive value of all database features")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Load data
        print("\n📥 Loading data from database...")
        orders, customers, stores, items, bundles, drivers = load_delivery_data()
        
        print(f"   Orders (delivered): {len(orders):,}")
        print(f"   Customers: {len(customers):,}")
        print(f"   Stores: {len(stores):,}")
        print(f"   Order items aggregated: {len(items):,}")
        print(f"   Bundles: {len(bundles):,}")
        print(f"   Drivers: {len(drivers):,}")
        
        # Calculate delivery metrics
        print("\n⏱️  Calculating delivery metrics...")
        df = calculate_delivery_metrics(orders, stores)
        
        # Merge additional data
        df = df.merge(customers, on='customer_id', how='left')
        df = df.merge(items, on='order_id', how='left')
        
        if not bundles.empty:
            df = df.merge(bundles, on='order_id', how='left')
        
        if not drivers.empty and 'driver_id' in df.columns:
            df = df.merge(drivers, on='driver_id', how='left')
        
        # Remove outliers (delivery times > 300 minutes or < 5 minutes)
        initial_count = len(df)
        df = df[(df['delivery_time_mins'] >= 5) & (df['delivery_time_mins'] <= 300)]
        print(f"   Removed {initial_count - len(df):,} outliers (delivery time <5 or >300 mins)")
        print(f"   Final sample size: {len(df):,}")
        
        # Summary stats
        print(f"\n📊 Delivery Time Summary:")
        print(f"   Mean:   {df['delivery_time_mins'].mean():.1f} minutes")
        print(f"   Median: {df['delivery_time_mins'].median():.1f} minutes")
        print(f"   Std:    {df['delivery_time_mins'].std():.1f} minutes")
        print(f"   Min:    {df['delivery_time_mins'].min():.1f} minutes")
        print(f"   Max:    {df['delivery_time_mins'].max():.1f} minutes")
        
        # Run analyses
        numeric_results = analyze_numeric_correlations(df)
        categorical_results = analyze_categorical_features(df)
        mi_results = analyze_mutual_information(df)
        rf_results = analyze_random_forest_importance(df)
        analyze_by_delivery_stage(df)
        
        # Summary
        print_summary(numeric_results, categorical_results, mi_results, rf_results)
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        
    finally:
        # Restore stdout and close file
        sys.stdout = tee.terminal
        tee.close()
    
    print(f"\n✅ Analysis exported to: {output_file}")


if __name__ == "__main__":
    main()