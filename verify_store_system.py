#!/usr/bin/env python3
"""
Verification script to demonstrate store location and product relationships.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "database" / "grocery_delivery.db"


def main():
    conn = sqlite3.connect(DATABASE_PATH)
    
    print("=" * 80)
    print("STORE LOCATION AND PRODUCT SYSTEM VERIFICATION")
    print("=" * 80)
    
    # 1. Show stores
    print("\n1. STORE LOCATIONS")
    print("-" * 80)
    stores = pd.read_sql("""
        SELECT name, city, state, 
               ROUND(latitude, 4) as lat, 
               ROUND(longitude, 4) as lon,
               is_active
        FROM stores
    """, conn)
    print(stores.to_string(index=False))
    
    # 2. Show parent products distribution
    print("\n2. PARENT PRODUCT CATALOG BY CATEGORY")
    print("-" * 80)
    parent_stats = pd.read_sql("""
        SELECT category, COUNT(*) as product_count
        FROM parent_products
        GROUP BY category
        ORDER BY product_count DESC
    """, conn)
    print(parent_stats.to_string(index=False))
    
    # 3. Show store inventory coverage
    print("\n3. STORE INVENTORY COVERAGE")
    print("-" * 80)
    store_coverage = pd.read_sql("""
        SELECT 
            s.name as store_name,
            COUNT(DISTINCT sp.store_product_id) as products_carried,
            (SELECT COUNT(*) FROM parent_products) as total_products,
            ROUND(100.0 * COUNT(DISTINCT sp.store_product_id) / 
                  (SELECT COUNT(*) FROM parent_products), 1) as coverage_pct
        FROM stores s
        JOIN store_products sp ON s.store_id = sp.store_id
        GROUP BY s.store_id, s.name
        ORDER BY products_carried DESC
    """, conn)
    print(store_coverage.to_string(index=False))
    
    # 4. Show price variance example
    print("\n4. PRICE VARIANCE EXAMPLE (Same product at different stores)")
    print("-" * 80)
    price_variance = pd.read_sql("""
        SELECT 
            pp.name as product_name,
            pp.base_price,
            s.name as store_name,
            sp.price as store_price,
            ROUND(100.0 * (sp.price - pp.base_price) / pp.base_price, 1) as variance_pct
        FROM parent_products pp
        JOIN store_products sp ON pp.parent_product_id = sp.parent_product_id
        JOIN stores s ON sp.store_id = s.store_id
        WHERE pp.name = 'Bananas'
        ORDER BY sp.price DESC
    """, conn)
    print(price_variance.to_string(index=False))
    
    # 5. Show order-store-product relationships
    print("\n5. ORDER-STORE-PRODUCT RELATIONSHIPS (Sample)")
    print("-" * 80)
    order_relationships = pd.read_sql("""
        SELECT 
            o.order_id,
            c.first_name || ' ' || c.last_name as customer,
            s.name as store,
            pp.name as product,
            oi.quantity,
            oi.unit_price,
            oi.total_price
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN stores s ON o.store_id = s.store_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN parent_products pp ON oi.parent_product_id = pp.parent_product_id
        LIMIT 10
    """, conn)
    print(order_relationships.to_string(index=False))
    
    # 6. Show orders per store
    print("\n6. ORDERS PER STORE")
    print("-" * 80)
    orders_per_store = pd.read_sql("""
        SELECT 
            s.name as store_name,
            COUNT(o.order_id) as order_count,
            ROUND(AVG(o.total), 2) as avg_order_value,
            ROUND(SUM(o.total), 2) as total_revenue
        FROM stores s
        LEFT JOIN orders o ON s.store_id = o.store_id
        GROUP BY s.store_id, s.name
        ORDER BY order_count DESC
    """, conn)
    print(orders_per_store.to_string(index=False))
    
    # 7. Demonstrate complete join path
    print("\n7. COMPLETE JOIN PATH VERIFICATION")
    print("-" * 80)
    print("Order → Store → Store Product → Parent Product")
    print()
    complete_join = pd.read_sql("""
        SELECT 
            o.order_id,
            s.name as store,
            sp.store_product_id,
            pp.parent_product_id,
            pp.name as product,
            pp.base_price,
            sp.price as store_price,
            oi.unit_price as order_price,
            oi.quantity
        FROM orders o
        JOIN stores s ON o.store_id = s.store_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN store_products sp ON oi.store_product_id = sp.store_product_id
        JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
        LIMIT 5
    """, conn)
    for col in complete_join.columns:
        if 'id' in col:
            complete_join[col] = complete_join[col].str[:8] + '...'
    print(complete_join.to_string(index=False))
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 80)
    print("\nKey Features:")
    print("• Store locations generated with realistic addresses and coordinates")
    print("• Parent products define canonical product catalog")
    print("• Store products link parent products to specific stores")
    print("• Store-specific pricing with variance from base price")
    print("• Orders placed at specific stores")
    print("• Order items reference both store_product_id and parent_product_id")
    print("• Full join path: Order → Store → Store Product → Parent Product")
    print()


if __name__ == "__main__":
    main()
