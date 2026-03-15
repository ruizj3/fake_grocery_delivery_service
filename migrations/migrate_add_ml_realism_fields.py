"""
Migration: Add ML Realism Fields

Adds persona, environmental, and driver performance fields to support ML-ready dataset.
Run this before generating new data with persona/traffic/weather features.
"""

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "database" / "grocery_delivery.db"


def migrate():
    """Add new fields for ML realism features."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("Adding ML realism fields...")
    
    # Customers table - add persona and preference fields
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN persona TEXT")
        print("✓ Added customers.persona")
    except sqlite3.OperationalError:
        print("  customers.persona already exists")
    
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN preferred_shopping_hour INTEGER")
        print("✓ Added customers.preferred_shopping_hour")
    except sqlite3.OperationalError:
        print("  customers.preferred_shopping_hour already exists")
    
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN routine_strength REAL DEFAULT 0.5")
        print("✓ Added customers.routine_strength")
    except sqlite3.OperationalError:
        print("  customers.routine_strength already exists")
    
    # Orders table - add environmental and context fields
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN weather_condition TEXT")
        print("✓ Added orders.weather_condition")
    except sqlite3.OperationalError:
        print("  orders.weather_condition already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN traffic_multiplier REAL DEFAULT 1.0")
        print("✓ Added orders.traffic_multiplier")
    except sqlite3.OperationalError:
        print("  orders.traffic_multiplier already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_peak_hour BOOLEAN DEFAULT 0")
        print("✓ Added orders.is_peak_hour")
    except sqlite3.OperationalError:
        print("  orders.is_peak_hour already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_weekend BOOLEAN DEFAULT 0")
        print("✓ Added orders.is_weekend")
    except sqlite3.OperationalError:
        print("  orders.is_weekend already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN customer_order_number INTEGER DEFAULT 1")
        print("✓ Added orders.customer_order_number")
    except sqlite3.OperationalError:
        print("  orders.customer_order_number already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN days_since_last_order INTEGER")
        print("✓ Added orders.days_since_last_order")
    except sqlite3.OperationalError:
        print("  orders.days_since_last_order already exists")
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN cancellation_risk REAL")
        print("✓ Added orders.cancellation_risk")
    except sqlite3.OperationalError:
        print("  orders.cancellation_risk already exists")
    
    # Drivers table - add performance fields
    try:
        cursor.execute("ALTER TABLE drivers ADD COLUMN speed_multiplier REAL DEFAULT 1.0")
        print("✓ Added drivers.speed_multiplier")
    except sqlite3.OperationalError:
        print("  drivers.speed_multiplier already exists")
    
    try:
        cursor.execute("ALTER TABLE drivers ADD COLUMN reliability_score REAL DEFAULT 0.95")
        print("✓ Added drivers.reliability_score")
    except sqlite3.OperationalError:
        print("  drivers.reliability_score already exists")
    
    try:
        cursor.execute("ALTER TABLE drivers ADD COLUMN experience_level TEXT DEFAULT 'intermediate'")
        print("✓ Added drivers.experience_level")
    except sqlite3.OperationalError:
        print("  drivers.experience_level already exists")
    
    # Store products - add sales/promotion fields
    try:
        cursor.execute("ALTER TABLE store_products ADD COLUMN is_on_sale BOOLEAN DEFAULT 0")
        print("✓ Added store_products.is_on_sale")
    except sqlite3.OperationalError:
        print("  store_products.is_on_sale already exists")
    
    try:
        cursor.execute("ALTER TABLE store_products ADD COLUMN sale_price REAL")
        print("✓ Added store_products.sale_price")
    except sqlite3.OperationalError:
        print("  store_products.sale_price already exists")
    
    try:
        cursor.execute("ALTER TABLE store_products ADD COLUMN promotion_week INTEGER")
        print("✓ Added store_products.promotion_week")
    except sqlite3.OperationalError:
        print("  store_products.promotion_week already exists")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Migration complete!")
    print("You can now generate data with ML realism features.")


if __name__ == "__main__":
    migrate()
