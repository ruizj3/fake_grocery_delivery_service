#!/usr/bin/env python3
"""
Migration: Add estimated_delivery_time and prediction_failed fields to orders table
"""

import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "database" / "grocery_delivery.db"


def migrate():
    """Add new prediction fields to existing database."""
    if not DATABASE_PATH.exists():
        print(f"Database not found at {DATABASE_PATH}")
        print("Run the API or main.py first to create the database.")
        return
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check if fields already exist
    cursor.execute("PRAGMA table_info(orders)")
    columns = [col[1] for col in cursor.fetchall()]
    
    migrations_needed = []
    
    if "predicted_delivery_minutes" not in columns:
        migrations_needed.append("predicted_delivery_minutes INTEGER")
    
    if "prediction_failed" not in columns:
        migrations_needed.append("prediction_failed BOOLEAN DEFAULT FALSE")
    
    if not migrations_needed:
        print("✅ All fields already exist. No migration needed.")
        conn.close()
        return
    
    # Add missing fields
    for field in migrations_needed:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {field}")
            print(f"✅ Added field: {field}")
        except sqlite3.OperationalError as e:
            print(f"⚠️  Could not add {field}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Migration complete!")
    print("   - Orders can now store predicted_delivery_minutes from predictions")
    print("   - Failed predictions are tracked with prediction_failed flag")


if __name__ == "__main__":
    migrate()
