# Grocery Delivery Data Generator

A lightweight Python service for generating fake grocery delivery data, mimicking platforms like DoorDash or Instacart. Includes a **live FastAPI service** with automatic, continuous generation of all entities (orders, customers, drivers, stores) and periodic bundling.

Made with help from Copilot and Claude Sonnet 4.5.

## Key Features

🔄 **Continuous Generation**: All entities generate automatically with configurable intervals
- Orders: Every 10 seconds (default)
- Customers: Every 2 minutes (default)
- Drivers: Every 5 minutes (default)
- Stores: Every 10 minutes (default)
- Bundles: Every 60 seconds (default)

⚡ **Independent Control**: Start/stop each generator independently
🎛️ **Dynamic Configuration**: Update intervals without restarting
🏪 **Store Hierarchy**: Stores with location-specific inventory and pricing
📊 **Real-time API**: Live data streaming for ML experimentation

## Quick Start

```bash
# Setup
python -m venv fake_grocery_venv
source fake_grocery_venv/bin/activate
pip install -r requirements.txt

# Start the API server
uvicorn api.main:app --reload --port 8000

# Open API docs
open http://localhost:8000/docs
```

## API Endpoints

### Entity Generation (On-Demand)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/customers/generate?count=5` | Generate new customers |
| POST | `/drivers/generate?count=3` | Generate new drivers |
| POST | `/stores/generate?count=2` | Generate new stores with inventory |
| POST | `/products/generate?count=10` | Generate random products |
| POST | `/orders/generate` | Generate a single order |
| POST | `/orders/generate-batch?count=20` | Generate multiple orders |

### Background Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/services/start-all` | Start all generators (orders, customers, drivers, stores, bundles) |
| POST | `/services/stop-all` | Stop all background services |
| POST | `/services/orders/start` | Start automatic order generation |
| POST | `/services/orders/stop` | Stop order generation |
| POST | `/services/customers/start` | Start automatic customer generation |
| POST | `/services/customers/stop` | Stop customer generation |
| POST | `/services/drivers/start` | Start automatic driver generation |
| POST | `/services/drivers/stop` | Stop driver generation |
| POST | `/services/stores/start` | Start automatic store generation |
| POST | `/services/stores/stop` | Stop store generation |
| POST | `/services/bundles/start` | Start periodic bundling |
| POST | `/services/bundles/stop` | Stop bundling |
| PATCH | `/services/config` | Update intervals |

### Data Access

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers` | List customers |
| GET | `/drivers` | List drivers |
| GET | `/stores` | List stores |
| GET | `/products` | List products |
| GET | `/orders` | List orders |
| GET | `/orders/queue` | Orders waiting for bundling |
| GET | `/bundles` | List bundles |
| GET | `/stats` | Database statistics |
| GET | `/status` | Service status (all generators + intervals) |

### Bundle Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bundles/process` | Process pending orders now |
| GET | `/bundles/{id}` | Get bundle with stops |

## Usage Examples

### Start Live Data Generation

```bash
# Start the API
uvicorn api.main:app --reload --port 8000

# In another terminal, start all services
curl -X POST http://localhost:8000/services/start-all

# Watch the logs - you'll see:
# - Orders generated every ~10s
# - Customers generated every ~120s (2 min)
# - Drivers generated every ~300s (5 min)
# - Stores generated every ~600s (10 min)
# - Bundles processed every ~60s
```

### Configure Generation Speed

All entity generators have independent, configurable intervals:

```bash
# Faster orders (every 5 seconds)
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{"order_interval_seconds": 5}'

# Faster bundling (every 30 seconds)
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{"bundle_interval_seconds": 30}'

# Faster customers (every 60 seconds)
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{"customer_interval_seconds": 60}'

# Faster drivers (every 120 seconds)
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{"driver_interval_seconds": 120}'

# Faster stores (every 300 seconds)
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{"store_interval_seconds": 300}'

# Update multiple at once
curl -X PATCH http://localhost:8000/services/config \
  -H "Content-Type: application/json" \
  -d '{
    "order_interval_seconds": 5,
    "customer_interval_seconds": 60,
    "driver_interval_seconds": 120,
    "store_interval_seconds": 300,
    "bundle_interval_seconds": 30
  }'
```

### Control Individual Generators

```bash
# Start only order generation
curl -X POST http://localhost:8000/services/orders/start

# Start only customer generation
curl -X POST http://localhost:8000/services/customers/start

# Start only driver generation
curl -X POST http://localhost:8000/services/drivers/start

# Start only store generation
curl -X POST http://localhost:8000/services/stores/start

# Stop a specific generator
curl -X POST http://localhost:8000/services/customers/stop
```

### Check Service Status

```bash
# See all active generators and their intervals
curl http://localhost:8000/status

# Response shows:
# {
#   "order_generation_active": true,
#   "bundle_processing_active": true,
#   "customer_generation_active": true,
#   "driver_generation_active": true,
#   "store_generation_active": true,
#   "order_interval_seconds": 10.0,
#   "bundle_interval_seconds": 60.0,
#   "customer_interval_seconds": 120.0,
#   "driver_interval_seconds": 300.0,
#   "store_interval_seconds": 600.0
# }
```

### Manual Generation

```bash
# Generate 10 customers
curl -X POST "http://localhost:8000/customers/generate?count=10"

# Generate 5 drivers
curl -X POST "http://localhost:8000/drivers/generate?count=5"

# Generate 50 orders
curl -X POST "http://localhost:8000/orders/generate-batch?count=50"

# Process bundles immediately
curl -X POST http://localhost:8000/bundles/process
```

### Check Queue Status

```bash
# See orders waiting to be bundled
curl http://localhost:8000/orders/queue

# Check service status
curl http://localhost:8000/status

# Database stats
curl http://localhost:8000/stats
```

## Data Model

### Entity Relationships

```
┌──────────────┐
│    stores    │
└──────┬───────┘
       │
       │ creates inventory
       ▼
┌──────────────────┐        ┌──────────────────┐
│ parent_products  │◄───────│ store_products   │
│  (176 items)     │  links │ (per-store inv)  │
└──────────────────┘        └────────┬─────────┘
                                     │
                                     │ references
                                     │
┌──────────────┐     ┌──────────────┐│
│   customers  │────►│    orders    │◄───
└──────────────┘     └──────┬───────┘
                            │       
                            │       
                     ┌──────▼───────────┐
                     │   order_items    │
                     └──────────────────┘
                            
┌──────────────┐     ┌──────────────┐
│   drivers    │◄────│   bundles    │
└──────────────┘     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │ bundle_stops │
                     └──────────────┘
```

**Key Relationships:**
- **customers → orders**: Customers place orders
- **stores → store_products**: Each store has inventory
- **store_products → parent_products**: Store inventory references canonical products
- **orders → order_items → store_products**: Order items reference store-specific products
- **bundles → drivers**: Drivers are assigned to bundles (not individual orders)
- **bundles → bundle_stops → orders**: Bundles group multiple orders for delivery

### Product Hierarchy

**Two-tier system:**
- **Parent Products** (176 items): Canonical product definitions with base prices
- **Store Products** (per store): Store-specific instances with local pricing (±15% variance)

### Order Flow

```
Customer → Selects Store (proximity-based)
    ↓
Places Order at specific Store
    ↓
Order Items reference Store Products (store-specific prices)
    ↓
Store Products link to Parent Products (canonical definition)
```

**Complete Join Path:**
```
orders → store_id → stores
orders → order_items → store_product_id → store_products
store_products → parent_product_id → parent_products
```

## Order Lifecycle

```
[pending] → [confirmed] → [picking] → [out_for_delivery] → [delivered]
```

**Bundling Process:**
1. Orders start in `pending` or `confirmed` status
2. The bundling service groups nearby orders from the same store
3. The bundling service assigns an available driver to each bundle
4. Orders are picked, delivered as a bundle, and marked `delivered`

**Key Point:** Drivers are assigned to bundles (groups of orders), not to individual orders. The bundling service finds the best available driver based on proximity to the bundle's centroid.

## CLI Commands (Still Available)

```bash
# Generate static data
python main.py --orders 1000

# Run bundling analysis
python main.py --bundle

# Export to CSV
python main.py --export

# Reset database
python main.py --reset
```

## Project Structure

```
grocery-delivery-data/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPI application with continuous generation
│   └── models.py        # API response models
├── generators/
│   ├── __init__.py
│   ├── base.py
│   ├── customers.py     # Customer generator
│   ├── drivers.py       # Driver generator
│   ├── products.py      # Parent & store product generators
│   ├── stores.py        # Store location generator
│   └── orders.py        # Order generator (with store selection)
├── services/
│   ├── __init__.py
│   └── bundling.py      # Bundle optimization service
├── models/
│   ├── __init__.py
│   └── schemas.py       # Pydantic models
├── database/
│   └── grocery_delivery.db
├── exports/             # CSV exports
│   ├── stores.csv
│   ├── parent_products.csv
│   ├── store_products.csv
│   ├── customers.csv
│   ├── drivers.csv
│   ├── orders.csv
│   └── order_items.csv
├── main.py              # CLI entry point
├── db.py                # Database initialization
├── requirements.txt
├── README.md
├── STORE_SYSTEM.md      # Store & product hierarchy documentation
└── verify_store_system.py  # Verification script
```

## Example Queries

### Get Order with Store and Product Details

```sql
SELECT 
    o.order_id,
    c.first_name || ' ' || c.last_name as customer_name,
    s.name as store_name,
    s.city as store_city,
    pp.name as product_name,
    pp.category,
    pp.base_price,
    sp.price as store_price,
    oi.quantity,
    oi.total_price
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN stores s ON o.store_id = s.store_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN store_products sp ON oi.store_product_id = sp.store_product_id
JOIN parent_products pp ON oi.parent_product_id = pp.parent_product_id
WHERE o.order_id = ?;
```

### Find Price Variance Across Stores

```sql
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
ORDER BY sp.price DESC;
```

### Store Performance Metrics

```sql
SELECT 
    s.name as store_name,
    s.city,
    COUNT(DISTINCT o.order_id) as total_orders,
    ROUND(AVG(o.total), 2) as avg_order_value,
    ROUND(SUM(o.total), 2) as total_revenue,
    COUNT(DISTINCT o.customer_id) as unique_customers
FROM stores s
LEFT JOIN orders o ON s.store_id = o.store_id
GROUP BY s.store_id, s.name, s.city
ORDER BY total_orders DESC;
```

### Products Available at a Store

```sql
SELECT 
    pp.category,
    pp.name as product_name,
    pp.brand,
    pp.base_price,
    sp.price as store_price,
    sp.stock_level,
    sp.is_available
FROM store_products sp
JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
JOIN stores s ON sp.store_id = s.store_id
WHERE s.name = 'Daily Goods'
  AND sp.is_available = 1
ORDER BY pp.category, pp.name;
```

## Database Statistics

### Typical Dataset (1000 Orders)

| Table | Row Count | Description |
|-------|-----------|-------------|
| stores | 10 | Store locations across Bay Area |
| customers | 200 | Customer accounts |
| drivers | 20 | Active delivery drivers |
| parent_products | 176 | Canonical product catalog |
| store_products | 1,490 | Store-specific inventory (10 stores × ~149 products) |
| orders | 1,000 | Customer orders |
| order_items | 6,547 | Individual items in orders (~6.5 per order) |
| bundles | 60+ | Optimized delivery routes |

### Entity Ratios

- **Orders per Store**: ~100 orders (proximity-based selection)
- **Orders per Customer**: ~5 orders
- **Orders per Bundle**: ~3-5 orders grouped together
- **Bundles per Driver**: Variable (drivers assigned to bundles as needed)
- **Items per Order**: ~6.5 items average
- **Store Inventory Coverage**: 85% of parent catalog
- **Product Price Variance**: ±15% from base price

## Data Review with SQL 
```
source fake_grocery_venv/bin/activate && python -c "
import sqlite3
import pandas as pd

conn = sqlite3.connect('database/grocery_delivery.db')

# Show sample store
print('=== SAMPLE STORES ===')
stores = pd.read_sql('SELECT * FROM stores LIMIT 3', conn)
print(stores[['store_id', 'name', 'city', 'state', 'is_active']].to_string(index=False))

print('\n=== SAMPLE PARENT PRODUCTS ===')
parent_products = pd.read_sql('SELECT * FROM parent_products LIMIT 3', conn)
print(parent_products[['parent_product_id', 'name', 'category', 'brand', 'base_price']].to_string(index=False))

print('\n=== SAMPLE STORE PRODUCTS (with parent product info) ===')
store_products = pd.read_sql('''
    SELECT sp.store_product_id, s.name as store_name, pp.name as product_name, 
           pp.base_price, sp.price, sp.is_available, sp.stock_level
    FROM store_products sp
    JOIN stores s ON sp.store_id = s.store_id
    JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
    LIMIT 5
''', conn)
print(store_products.to_string(index=False))

print('\n=== SAMPLE ORDER (with store info) ===')
orders = pd.read_sql('''
    SELECT o.order_id, c.first_name || \" \" || c.last_name as customer,
           s.name as store_name, o.status, o.total
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN stores s ON o.store_id = s.store_id
    LIMIT 3
''', conn)
print(orders.to_string(index=False))

print('\n=== SAMPLE ORDER ITEMS (with product lineage) ===')
order_items = pd.read_sql('''
    SELECT oi.order_item_id, pp.name as product_name, oi.quantity, 
           oi.unit_price, oi.total_price
    FROM order_items oi
    JOIN parent_products pp ON oi.parent_product_id = pp.parent_product_id
    LIMIT 5
''', conn)
print(order_items.to_string(index=False))

conn.close()
"
```

## Stream Processing Example

```python
import requests
import time

# Poll for new orders every 5 seconds
while True:
    response = requests.get('http://localhost:8000/orders?limit=10')
    orders = response.json()
    
    for order in orders:
        # Get full order details with store and products
        detail = requests.get(f'http://localhost:8000/orders/{order["order_id"]}')
        
        # Process for ML pipeline
        process_order_for_training(detail.json())
    
    time.sleep(5)
```

## Additional Documentation

- **[STORE_SYSTEM.md](STORE_SYSTEM.md)** - Complete documentation of the store location and product hierarchy system
- **[CONTINUOUS_GENERATION_TEST.md](CONTINUOUS_GENERATION_TEST.md)** - Test results for continuous entity generation
- **[verify_store_system.py](verify_store_system.py)** - Script to verify store-product relationships and data integrity
