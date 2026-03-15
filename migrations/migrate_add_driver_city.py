"""
Migration: Add city and state fields to drivers table

This ensures drivers have explicit city information stored,
making city-based matching more reliable.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.geofence import get_zone_for_coordinates

# Database path
DB_PATH = Path(__file__).parent.parent / "database" / "grocery_delivery.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(drivers)")
    columns = [col[1] for col in cursor.fetchall()]
    
    needs_migration = 'city' not in columns
    
    if not needs_migration:
        print("✓ Drivers table already has city and state columns")
        conn.close()
        return
    
    print("Adding city and state columns to drivers table...")
    
    # Add new columns
    cursor.execute("ALTER TABLE drivers ADD COLUMN city TEXT")
    cursor.execute("ALTER TABLE drivers ADD COLUMN state TEXT")
    
    # Backfill existing drivers with city/state based on their coordinates
    print("Backfilling city/state for existing drivers...")
    cursor.execute("SELECT driver_id, home_latitude, home_longitude FROM drivers")
    drivers = cursor.fetchall()
    
    updated = 0
    for driver_id, lat, lon in drivers:
        zone = get_zone_for_coordinates(lat, lon)
        if zone:
            cursor.execute(
                "UPDATE drivers SET city = ?, state = ? WHERE driver_id = ?",
                (zone['city'], zone['state'], driver_id)
            )
            updated += 1
        else:
            # Driver outside zones - set to NULL
            print(f"  Warning: Driver {driver_id[:8]}... outside all zones")
    
    conn.commit()
    conn.close()
    
    print(f"✓ Migration complete! Updated {updated}/{len(drivers)} drivers")
    print(f"  Added columns: city, state")

if __name__ == "__main__":
    migrate()
