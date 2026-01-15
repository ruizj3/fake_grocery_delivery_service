# Grocery Delivery Data Generator

A lightweight Python service for generating fake grocery delivery data, mimicking platforms like DoorDash or Instacart. Includes a **live FastAPI service** with automatic, continuous generation of all entities (orders, customers, drivers, stores) and periodic bundling.

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

```
┌──────────────┐     ┌──────────────┐
│   customers  │     │   drivers    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └────────┬───────────┘
                │
         ┌──────▼───────┐      ┌──────────────┐
         │    orders    │──────│   products   │
         └──────┬───────┘      └──────────────┘
                │
         ┌──────▼───────┐
         │ order_items  │
         └──────────────┘
                │
         ┌──────▼───────┐      ┌──────────────┐
         │   bundles    │──────│ bundle_stops │
         └──────────────┘      └──────────────┘
```

## Order Lifecycle

```
[pending] → [confirmed] → [picking] → [out_for_delivery] → [delivered]
                ↓
           [bundled]
```

Orders in `pending` or `confirmed` status are picked up by the bundler.

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
│   ├── main.py          # FastAPI application
│   └── models.py        # API response models
├── generators/
│   ├── __init__.py
│   ├── base.py
│   ├── customers.py
│   ├── drivers.py
│   ├── products.py
│   └── orders.py
├── services/
│   ├── __init__.py
│   └── bundling.py
├── models/
│   ├── __init__.py
│   └── schemas.py
├── database/
│   └── grocery_delivery.db
├── main.py              # CLI entry point
├── db.py
├── requirements.txt
└── README.md
```
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
## ML Use Cases

With the live API, you can:

1. **Stream processing** - Connect to the API to get real-time order data
2. **Demand forecasting** - Predict order volume by time/location
3. **Bundle optimization** - Experiment with bundling parameters
4. **Driver assignment** - Build models for optimal driver matching
5. **ETA prediction** - Train models on bundle duration vs actual
