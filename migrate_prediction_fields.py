"""
Migration script to add prediction tracking fields to orders table
"""
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "database" / "grocery_delivery.db"

def migrate():
    """Add prediction_sent and prediction_sent_at fields to orders table"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "prediction_sent" not in columns:
            print("Adding prediction_sent column...")
            cursor.execute("""
                ALTER TABLE orders 
                ADD COLUMN prediction_sent BOOLEAN DEFAULT FALSE
            """)
            print("✓ Added prediction_sent column")
        else:
            print("✓ prediction_sent column already exists")
        
        if "prediction_sent_at" not in columns:
            print("Adding prediction_sent_at column...")
            cursor.execute("""
                ALTER TABLE orders 
                ADD COLUMN prediction_sent_at TIMESTAMP
            """)
            print("✓ Added prediction_sent_at column")
        else:
            print("✓ prediction_sent_at column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
