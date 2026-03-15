#!/usr/bin/env python3
"""Simple test script for feature analysis."""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

DATABASE_PATH = Path(__file__).parent.parent / "database" / "grocery_delivery.db"

def main():
    print("="*60)
    print("SIMPLE FEATURE ANALYSIS TEST")
    print("="*60)
    
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Load orders
    print("\n1. Loading orders...")
    orders = pd.read_sql_query("""
        SELECT order_id, customer_id, total, traffic_multiplier, 
               created_at, delivered_at
        FROM orders WHERE status = 'delivered' 
          AND delivered_at IS NOT NULL
        LIMIT 10000
    """, conn)
    print(f"   Loaded {len(orders):,} orders")
    
    # Calculate delivery time
    orders['created_at'] = pd.to_datetime(orders['created_at'])
    orders['delivered_at'] = pd.to_datetime(orders['delivered_at'])
    orders['delivery_time_mins'] = (orders['delivered_at'] - orders['created_at']).dt.total_seconds() / 60
    
    print(f"   Delivery time: {orders['delivery_time_mins'].mean():.1f} mins (mean)")
    
    # Numeric correlation
    print("\n2. Testing numeric correlation...")
    r, p = stats.pearsonr(orders['total'], orders['delivery_time_mins'])
    print(f"   total vs delivery_time: r={r:.4f}, p={p:.4e}")
    
    r, p = stats.pearsonr(orders['traffic_multiplier'], orders['delivery_time_mins'])
    print(f"   traffic vs delivery_time: r={r:.4f}, p={p:.4e}")
    
    # Load customers for categorical test
    print("\n3. Loading customers...")
    customers = pd.read_sql_query("SELECT customer_id, persona FROM customers", conn)
    print(f"   Loaded {len(customers):,} customers")
    
    df = orders.merge(customers, on='customer_id', how='left')
    print(f"   Merged to {len(df):,} rows")
    
    # ANOVA on persona
    print("\n4. Testing ANOVA on persona...")
    persona_groups = df.groupby('persona')['delivery_time_mins']
    print(f"   Personas: {list(df['persona'].unique())}")
    
    groups = [g.values for _, g in persona_groups if len(g) >= 10]
    if len(groups) >= 2:
        f_stat, p_val = stats.f_oneway(*groups)
        print(f"   F={f_stat:.2f}, p={p_val:.4e}")
    
    print("\n" + "="*60)
    print("SUCCESS - All tests passed!")
    print("="*60)
    
    conn.close()

if __name__ == "__main__":
    main()
