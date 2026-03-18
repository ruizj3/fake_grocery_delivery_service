import os
import re
import sqlite3
from pathlib import Path
from contextlib import contextmanager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")

# Render uses "postgres://" but psycopg2 requires "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DATABASE_PATH = Path(__file__).parent / "grocery_delivery.db"


def _is_postgres() -> bool:
    return DATABASE_URL is not None


class _PgCursorWrapper:
    """Wraps a psycopg2 cursor to accept sqlite3-style '?' placeholders
    and return dict-like rows (matching sqlite3.Row behavior)."""

    def __init__(self, cursor):
        self._cursor = cursor

    @staticmethod
    def _translate_sql(sql: str) -> str:
        # Replace ? with %s, but skip ?? and strings
        sql = re.sub(r"(?<!\?)\?(?!\?)", "%s", sql)
        # INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
        sql = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            sql,
            flags=re.IGNORECASE,
        )
        if re.search(r"INSERT\s+OR\s+REPLACE\s+INTO", sql, re.IGNORECASE):
            sql = re.sub(
                r"INSERT\s+OR\s+REPLACE\s+INTO",
                "INSERT INTO",
                sql,
                flags=re.IGNORECASE,
            )
        return sql

    @staticmethod
    def _add_conflict_clause(sql: str, original_sql: str) -> str:
        """Add ON CONFLICT clause for INSERT OR IGNORE/REPLACE translations."""
        if re.search(r"INSERT\s+OR\s+IGNORE", original_sql, re.IGNORECASE):
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        return sql

    def execute(self, sql, params=None):
        original = sql
        sql = self._translate_sql(sql)
        sql = self._add_conflict_clause(sql, original)
        if params:
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def executemany(self, sql, seq_of_params):
        original = sql
        sql = self._translate_sql(sql)
        sql = self._add_conflict_clause(sql, original)
        return self._cursor.executemany(sql, seq_of_params)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _DictRow(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_DictRow(r) for r in rows]

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class _DictRow:
    """A dict-like row that supports both index and key access,
    matching sqlite3.Row interface."""

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return repr(self._data)


def get_connection():
    if _is_postgres():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def get_cursor():
    conn = get_connection()
    if _is_postgres():
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        wrapped = _PgCursorWrapper(cursor)
    else:
        wrapped = conn.cursor()
    try:
        yield wrapped
        conn.commit()
    finally:
        conn.close()


def init_database(reset: bool = False):
    if reset:
        if _is_postgres():
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DO $$ DECLARE r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            conn.commit()
            conn.close()
        elif DATABASE_PATH.exists():
            DATABASE_PATH.unlink()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Stores table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            opens_at TEXT NOT NULL,
            closes_at TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL
        )
    """)
    
    # Customers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at TIMESTAMP NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE,
            persona TEXT,
            preferred_shopping_hour INTEGER,
            routine_strength REAL DEFAULT 0.5
        )
    """)
    
    # Drivers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            driver_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            license_plate TEXT NOT NULL,
            rating REAL DEFAULT 4.5,
            total_deliveries INTEGER DEFAULT 0,
            home_latitude REAL NOT NULL,
            home_longitude REAL NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            speed_multiplier REAL DEFAULT 1.0,
            reliability_score REAL DEFAULT 0.95,
            experience_level TEXT DEFAULT 'intermediate'
        )
    """)
    
    # Parent products table (canonical product definitions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_products (
            parent_product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            base_price REAL NOT NULL,
            unit TEXT NOT NULL,
            weight_oz REAL,
            is_organic BOOLEAN DEFAULT FALSE
        )
    """)
    
    # Store products table (store-specific inventory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS store_products (
            store_product_id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            parent_product_id TEXT NOT NULL,
            price REAL NOT NULL,
            is_available BOOLEAN DEFAULT TRUE,
            stock_level INTEGER DEFAULT 0,
            is_on_sale BOOLEAN DEFAULT FALSE,
            sale_price REAL,
            promotion_week INTEGER,
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (parent_product_id) REFERENCES parent_products(parent_product_id)
        )
    """)
    
    # Legacy products table (for backward compatibility)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            brand TEXT NOT NULL,
            price REAL NOT NULL,
            unit TEXT NOT NULL,
            weight_oz REAL,
            is_organic BOOLEAN DEFAULT FALSE,
            is_available BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Orders table (now includes store_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            store_id TEXT,
            status TEXT NOT NULL,
            subtotal REAL NOT NULL,
            tax REAL NOT NULL,
            delivery_fee REAL NOT NULL,
            tip REAL NOT NULL,
            total REAL NOT NULL,
            created_at TIMESTAMP NOT NULL,
            confirmed_at TIMESTAMP,
            picked_at TIMESTAMP,
            picking_completed_at TIMESTAMP,
            delivered_at TIMESTAMP,
            delivery_latitude REAL NOT NULL,
            delivery_longitude REAL NOT NULL,
            delivery_notes TEXT,
            prediction_sent BOOLEAN DEFAULT FALSE,
            prediction_sent_at TIMESTAMP,
            predicted_delivery_minutes INTEGER,
            prediction_failed BOOLEAN DEFAULT FALSE,
            weather_condition TEXT,
            traffic_multiplier REAL DEFAULT 1.0,
            is_peak_hour BOOLEAN DEFAULT FALSE,
            is_weekend BOOLEAN DEFAULT FALSE,
            customer_order_number INTEGER DEFAULT 1,
            days_since_last_order INTEGER,
            cancellation_risk REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        )
    """)
    
    # Order items table (now references store_product_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            store_product_id TEXT NOT NULL,
            parent_product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (store_product_id) REFERENCES store_products(store_product_id),
            FOREIGN KEY (parent_product_id) REFERENCES parent_products(parent_product_id)
        )
    """)
    
    # Bundles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bundles (
            bundle_id TEXT PRIMARY KEY,
            driver_id TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            assigned_at TIMESTAMP,
            picked_up_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_distance_km REAL,
            estimated_duration_min INTEGER,
            order_count INTEGER DEFAULT 0,
            total_value REAL DEFAULT 0,
            centroid_latitude REAL,
            centroid_longitude REAL,
            FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
        )
    """)
    
    # Bundle stops table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bundle_stops (
            id TEXT PRIMARY KEY,
            bundle_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            stop_sequence INTEGER NOT NULL,
            FOREIGN KEY (bundle_id) REFERENCES bundles(bundle_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    """)
    
    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_city ON stores(city)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stores_active ON stores(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_store ON orders(store_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(store_product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_store_products_store ON store_products(store_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_store_products_parent ON store_products(parent_product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_parent_products_category ON parent_products(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundles_driver ON bundles(driver_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundles_status ON bundles(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_stops_bundle ON bundle_stops(bundle_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_stops_order ON bundle_stops(order_id)")
    
    conn.commit()
    conn.close()
    if _is_postgres():
        print("Database initialized (PostgreSQL)")
    else:
        print(f"Database initialized at {DATABASE_PATH}")


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database (works for both SQLite and PostgreSQL)."""
    with get_cursor() as cursor:
        if _is_postgres():
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?)",
                (table_name,),
            )
            return cursor.fetchone()[0]
        else:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return cursor.fetchone() is not None


def get_table_counts() -> dict:
    with get_cursor() as cursor:
        counts = {}
        tables = [
            "stores", "customers", "drivers", "parent_products", 
            "store_products", "orders", "order_items", "bundles", "bundle_stops"
        ]
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            except:
                counts[table] = 0
        return counts
