# Grocery Delivery Data Generator

A lightweight Python service for generating **realistic, ML-ready** grocery delivery data, mimicking platforms like DoorDash or Instacart. Features **persona-based customer behavior**, **product bundles**, **weather/traffic patterns**, and **risk-based cancellations** for meaningful machine learning projects.

Made with help from Copilot and Claude Sonnet 4.5.

## Key Features

### 🤖 **ML Realism** (NEW!)
- **6 Customer Personas**: health_conscious, family_shopper, young_professional, budget_conscious, specialty_diet, convenience_seeker
- **20 Product Bundles**: Realistic meal patterns (pasta_night, taco_tuesday, breakfast_essentials, etc.)
- **Weather & Traffic**: City-specific patterns affecting delivery times and order volume
- **Smart Cancellation Risk**: Based on traffic, order value, customer history, premium status
- **Driver Performance**: Speed multipliers, reliability scores, experience levels
- **Repeat Purchases**: 30-70% items from customer history based on persona
- **Temporal Patterns**: Peak hours, weekends, preferred shopping times

### 🔄 **Continuous Generation**
All entities generate automatically with configurable intervals:
- Orders: Every 10 seconds (default)
- Customers: Every 2 minutes (default)
- Drivers: Every 5 minutes (default)
- Stores: Every 10 minutes (default)
- Bundles: Every 60 seconds (default)
- Predictions: Automatic on order confirmation (5s timeout)

### 🎲 **Deterministic Simulation** (NEW!)
Full replay-able simulation powered by seeded PRNG and statistical distributions:
- **Master Seed**: Single seed controls all randomness — same seed = identical output every run
- **Poisson Arrivals**: Order/customer/driver inter-arrival times follow exponential distribution
- **Gaussian Latency**: Confirmation delays, picking durations, and transit times use normal distributions (mean ± std)
- **Configurable Error Injection**: Simulate API 500 errors at a given rate with Gaussian response delays
- **Tunable Cancellation Rates**: Per-lifecycle-stage cancellation thresholds (pending/confirmed/picking/delivery)
- **Independent RNG Streams**: Each subsystem (orders, customers, drivers, etc.) gets its own derived seed so changes don't cascade

### ⚡ **Other Features**
- **Independent Control**: Start/stop each generator independently
- **Dynamic Configuration**: Update intervals without restarting
- **Store Hierarchy**: Stores with location-specific inventory and pricing
- **Geofencing**: 6 US cities with realistic boundaries
- **Real-time API**: Live data streaming for ML experimentation
- **100% Prediction Coverage**: Every confirmed order gets a delivery time estimate

## Quick Start

```bash
# Setup
python -m venv fake_grocery_venv
source fake_grocery_venv/bin/activate
pip install -r requirements.txt

# Test ML realism features (quick validation)
python scripts/test_ml_realism.py

# Generate complete historical dataset (100K orders, 60 days, with ML features)
python scripts/generate_complete_dataset.py --orders 100000 --days 60

# OR: For large datasets (1.2M orders) - faster bundling
python scripts/generate_complete_dataset.py --orders 1200000 --days 60 --bundle-hours 6

# OR: Deterministic mode (same seed = identical dataset every time)
python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42

# Verify geofencing (all data in 6 cities)
python scripts/verify_geofencing.py

# Start the API server
uvicorn api.main:app --reload --port 8000

# Open API docs
open http://localhost:8000/docs
```

### Deterministic Simulation (Quick Start)

```bash
# Full historical dataset: orders + customers + stores + drivers + bundles
# Same seed = identical database every time
python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42

# With simulated 5% error injection
python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42 --error-rate 0.05

# Custom Poisson arrival rate (~10 orders/min)
python scripts/generate_complete_dataset.py --orders 100000 --days 60 --deterministic --seed 42 --order-rate 10

# Skip bundling if you only need raw orders
python scripts/generate_complete_dataset.py --orders 5000 --deterministic --seed 42 --skip-bundling

# Or use main.py directly for quick tests (no bundling)
python main.py --deterministic --seed 42 --orders 5000
```

## ML Features Deep Dive

### Customer Personas
Each customer assigned a persona affecting shopping behavior:
- **health_conscious** (15%): Organic produce, 75% organic preference, ±30% higher value
- **family_shopper** (25%): Large carts (25 items avg), bulk quantities, pantry staples
- **young_professional** (20%): Small frequent orders (8 items), convenience items, late hours
- **budget_conscious** (20%): Price-sensitive, avoids organic, off-peak shopping
- **specialty_diet** (10%): Vegan, organic, specialty items, ±40% higher value
- **convenience_seeker** (10%): Very frequent, 70% repeat purchases, tiny carts (5 items)

### Product Bundles
20 realistic meal patterns with 60-80% co-occurrence:
- `breakfast_essentials`, `pasta_night`, `taco_tuesday`, `salad_bowl`, `burger_night`
- `stir_fry`, `pizza_homemade`, `smoothie_ingredients`, `bbq_party`, etc.
- 40% of orders include 1-2 bundles aligned with persona

### Environmental Factors
- **Weather**: clear, rain, heavy_rain, snow, storm (city-specific, seasonal)
  - Rain: +15-25% order volume, 1.25x delivery time
  - Snow: +30% orders, 1.8x delivery time
- **Traffic**: Rush hours (7-10am, 4-8pm) with 1.5-2.0x multipliers
  - NYC peak: 2.0x, Seattle: 1.7x, Cincinnati: 1.5x
  - Weekend patterns differ from weekdays

### Cancellation Risk Model
Risk-based cancellations (not random):
- Base 5% + traffic delays (+10%) + order value (±2%) + premium (-3%) + history (+10%)
- Realistic 5-25% range vs previous uniform 20%

### Driver Performance
- **Speed**: 0.7-1.3x (normal distribution), +experience bonus up to +20%
- **Reliability**: Expert (95-99%), Advanced (90-96%), Intermediate (85-92%), Beginner (75-88%)
- Correlates with ratings and total deliveries

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
| POST | `/services/start-all` | Start all generators (orders, customers, drivers, stores, bundles, predictions) |
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
| POST | `/services/predictions/start` | Start automatic prediction sending |
| POST | `/services/predictions/stop` | Stop prediction sending |
| PATCH | `/services/config` | Update intervals |

### Simulation Config

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/simulation/config` | Get current simulation parameters |
| PATCH | `/simulation/config` | Update simulation parameters (seed, rates, error injection) |

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

### Prediction Service

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/predictions/send?batch_size=10` | Manually send confirmed orders to prediction service (fallback) |
| GET | `/predictions/status` | Get prediction coverage statistics |

**⚡ Automatic Predictions**: Every confirmed order automatically gets a delivery time prediction!
- Non-blocking async calls with 5-second timeout
- Results saved to `estimated_delivery_time` field
- Failed predictions tracked but don't crash system
- See [Automatic Predictions](#automatic-predictions) section below

See [PREDICTION_SERVICE.md](PREDICTION_SERVICE.md) for legacy batch prediction documentation.

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
# - Orders progressing through lifecycle (picking → delivery)
# - Random order cancellations at various stages
```

### Deterministic Simulation Mode

Enable seeded, replay-able simulation where the same seed produces the exact same sequence of events:

```bash
# Enable deterministic mode via API
curl -X PATCH http://localhost:8000/simulation/config \
  -H "Content-Type: application/json" \
  -d '{"master_seed": 1001, "deterministic_mode": true}'

# Enable with 5% simulated API errors (Gaussian delay, ~500ms ± 100ms)
curl -X PATCH http://localhost:8000/simulation/config \
  -H "Content-Type: application/json" \
  -d '{"master_seed": 1001, "deterministic_mode": true, "api_error_rate": 0.05}'

# Tune Poisson arrival rates (orders, customers, drivers per minute)
curl -X PATCH http://localhost:8000/simulation/config \
  -H "Content-Type: application/json" \
  -d '{
    "master_seed": 1001,
    "deterministic_mode": true,
    "order_arrival_rate_per_min": 10.0,
    "customer_arrival_rate_per_min": 1.0,
    "driver_arrival_rate_per_min": 0.5
  }'

# Tune Gaussian latency distributions
curl -X PATCH http://localhost:8000/simulation/config \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_delay_mean_sec": 90,
    "confirmation_delay_std_sec": 30,
    "picking_duration_mean_min": 12,
    "picking_duration_std_min": 4,
    "transit_speed_mean_kmh": 30,
    "transit_speed_std_kmh": 8
  }'

# Tune cancellation rates per lifecycle stage
curl -X PATCH http://localhost:8000/simulation/config \
  -H "Content-Type: application/json" \
  -d '{
    "cancellation_rate_pending": 0.06,
    "cancellation_rate_confirmed": 0.04,
    "cancellation_rate_picking": 0.02,
    "cancellation_rate_delivery": 0.01
  }'

# Check current simulation config
curl http://localhost:8000/simulation/config
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
    ↓           ↓             ↓                ↓
    └───────────┴─────────────┴────────────────→ [canceled]
```

**Status Flow:**
1. **pending**: Order placed, awaiting confirmation (`created_at` set)
2. **confirmed**: Order confirmed, waiting to be bundled and picked (`confirmed_at` set)
3. **picking**: Shopper is gathering items from store (`picked_at` set)
4. **out_for_delivery**: All items picked, driver en route to customer (`picking_completed_at` set)
5. **delivered**: Order successfully delivered (`delivered_at` set)
6. **canceled**: Order canceled (can happen at any stage before delivery)

**Timestamps:**
- `created_at`: Order placed
- `confirmed_at`: Order confirmed (typically 1-5 minutes after creation)
- `picked_at`: Picking started (shopper begins gathering items)
- `picking_completed_at`: Picking finished (all items gathered, ready for delivery)
- `delivered_at`: Order delivered to customer

**Cancellation Behavior:**

Orders can be canceled at any point before delivery, with decreasing probability as they progress:
- **Pending stage** (40% of cancellations): Canceled before confirmation
- **Confirmed stage** (30%): Canceled after confirmation but before picking starts
- **Picking stage** (20%): Canceled while shopper is gathering items
- **Out for delivery stage** (10%): Rare late cancellation during delivery

Canceled orders have:
- Timestamps only up to their cancellation point
- $0.00 tip (no tip charged for canceled orders)
- Status set to `canceled`

**Bundling Process:**
1. Orders start in `pending` or `confirmed` status
2. The bundling service groups nearby orders from the same store
3. The bundling service assigns an available driver to each bundle
4. Orders transition through picking → out_for_delivery → delivered
5. Background simulator may randomly cancel orders at any stage

**Key Point:** Drivers are assigned to bundles (groups of orders), not to individual orders. The bundling service finds the best available driver based on proximity to the bundle's centroid.

## CLI Commands (Still Available)

```bash
# Generate static data
python main.py --orders 1000

# Generate large historical dataset (1.2M orders over 60 days)
python main.py --reset --orders 1200000 --days 60

# Deterministic mode: same seed = identical output every run
python main.py --deterministic --seed 42 --orders 5000

# Deterministic with 5% simulated errors and custom arrival rate
python main.py --deterministic --seed 42 --orders 5000 --error-rate 0.05 --order-rate 10

# Run bundling analysis
python main.py --bundle

# Export to CSV
python main.py --export

# Reset database
python main.py --reset
```

### CLI Options Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--orders, -n` | 500 | Number of orders to generate |
| `--seed, -s` | 42 | Random seed for reproducibility |
| `--days, -d` | 90 | Days of historical data |
| `--reset, -r` | — | Reset database before generating |
| `--deterministic` | — | Enable deterministic simulation mode |
| `--error-rate` | 0.0 | Simulated error injection rate (0.0–1.0) |
| `--order-rate` | 6.0 | Poisson arrival rate (orders per minute) |
| `--export, -e` | — | Export all tables to CSV |
| `--stats` | — | Show database statistics |
| `--bundle` | — | Run bundling analysis |

### Efficient Historical Bundling

For large datasets (100K+ orders), use the optimized batch bundling script:

```bash
# Bundle all historical orders in 12-hour batches (default)
python scripts/bundle_historical_orders.py

# Faster: Use 6-hour batches
python scripts/bundle_historical_orders.py --batch-hours 6

# Skip old delivered orders (only bundle active orders)
python scripts/bundle_historical_orders.py --skip-delivered

# Only bundle recent orders (last 30 days)
python scripts/bundle_historical_orders.py --limit-days 30
```

**Performance**: Processes ~1000-2000 orders/second, so 1.2M orders takes 10-20 minutes.

**Why batch bundling?**
- Avoids loading all orders into memory at once
- Processes orders chronologically in time windows
- Provides progress tracking and performance metrics
- Commits to database in batches

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
│   ├── bundling.py      # Bundle optimization service
│   └── predictions.py   # Prediction service integration
├── simulation/
│   ├── __init__.py
│   ├── config.py        # SimulationConfig (seed, rates, distributions)
│   └── rng.py           # SimulationRNG (Poisson, Gaussian, uniform)
├── models/
│   ├── __init__.py
│   └── schemas.py       # Pydantic models
├── database/
│   ├── db.py            # Database initialization
│   └── grocery_delivery.db
├── scripts/             # Utility & analysis scripts
│   ├── analyze_data.py
│   ├── check_order_flow.py
│   └── verify_store_system.py
├── tests/               # Test scripts
│   ├── test_automatic_predictions.py
│   └── test_prediction_service.py
├── migrations/          # Database migrations
│   ├── migrate_add_prediction_fields.py
│   └── migrate_prediction_fields.py
├── exports/             # CSV exports
│   ├── stores.csv
│   ├── parent_products.csv
│   ├── store_products.csv
│   ├── customers.csv
│   ├── drivers.csv
│   ├── orders.csv
│   └── order_items.csv
├── main.py              # CLI entry point
├── requirements.txt
├── README.md
└── STORE_SYSTEM.md      # Store & product hierarchy documentation
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

- **[GEOFENCING.md](GEOFENCING.md)** - Complete guide to city-based geofencing and optimized bundling
- **[scripts/verify_store_system.py](scripts/verify_store_system.py)** - Script to verify store-product relationships and data integrity
- **[scripts/analyze_data.py](scripts/analyze_data.py)** - Database analysis and statistics
- **[scripts/check_order_flow.py](scripts/check_order_flow.py)** - Order status flow and timestamp analysis
- **[scripts/verify_geofencing.py](scripts/verify_geofencing.py)** - Verify all data is within 6 geofenced cities
- **[scripts/bundle_historical_orders.py](scripts/bundle_historical_orders.py)** - Efficiently bundle large historical datasets
- **[scripts/generate_complete_dataset.py](scripts/generate_complete_dataset.py)** - One-command complete dataset generation

---

## Store System Architecture

### Overview

The service uses a comprehensive **store location** and **product hierarchy** system. Each order is associated with a specific store, and products are managed through a two-tier system.

### Product Hierarchy

**Two-tier system:**
- **Parent Products** (176 items): Canonical product definitions with base prices
- **Store Products** (per store): Store-specific instances with local pricing (±15% variance)

**Categories** (176 products across 10 categories):
- Produce (20), Dairy (18), Meat (18), Bakery (14), Frozen (15)
- Beverages (15), Snacks (17), Pantry (25), Household (17), Personal Care (17)

### Store Coverage

- Each store carries ~85% of the catalog (149 products)
- 10 stores distributed across Bay Area cities
- Store-specific pricing with ±15% variance from base price
- Independent inventory tracking per store

### Example Queries

**Products at a specific store:**
```sql
SELECT pp.name, pp.category, sp.price, sp.stock_level
FROM store_products sp
JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
JOIN stores s ON sp.store_id = s.store_id
WHERE s.name = 'Daily Goods' AND sp.is_available = 1;
```

**Price variance across stores:**
```sql
SELECT 
    pp.name,
    s.name as store,
    pp.base_price,
    sp.price as store_price,
    ROUND(100.0 * (sp.price - pp.base_price) / pp.base_price, 1) as variance_pct
FROM parent_products pp
JOIN store_products sp ON pp.parent_product_id = sp.parent_product_id
JOIN stores s ON sp.store_id = s.store_id
WHERE pp.name = 'Bananas'
ORDER BY sp.price DESC;
```

---

## Automatic Predictions

### Overview

Every confirmed order **automatically** receives a delivery time prediction with zero manual intervention. The system maintains performance by using non-blocking async calls.

### How It Works

```
Order Created (status='confirmed')
         ↓
save_to_db() returns confirmed order IDs
         ↓
Async task fires for each order (non-blocking)
         ↓
┌────────────────────────────────────┐
│ For each order (5s timeout):      │
│ 1. Fetch order data                │
│ 2. POST to prediction service      │
│ 3. Save estimated_delivery_time    │
│ 4. Or mark prediction_failed       │
└────────────────────────────────────┘
         ↓
Main thread continues (NOT blocked)
```

### Database Fields

Two new fields in the `orders` table:
```sql
predicted_delivery_minutes INTEGER     -- Predicted delivery time in minutes
prediction_failed BOOLEAN DEFAULT FALSE -- Tracks failed prediction attempts
```

### Setup Instructions

#### 1. Migrate Existing Database

```bash
python migrations/migrate_add_prediction_fields.py
```

#### 2. Start Your Prediction Service

```bash
# Must be running at: http://localhost:3000/predict/batch
# (configure in services/predictions.py if different)
```

#### 3. Start Grocery Delivery API

```bash
source fake_grocery_venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

#### 4. Test Automatic Predictions

```bash
# Run automated test
python tests/test_automatic_predictions.py

# Or manually create an order
curl -X POST "http://localhost:8000/orders/generate"

# Check prediction coverage
curl "http://localhost:8000/predictions/status"
```

### Monitoring

**Check Prediction Success Rate:**
```bash
curl http://localhost:8000/predictions/status
```

Response:
```json
{
  "total_confirmed_orders": 150,
  "with_predictions": 142,
  "failed_predictions": 8,
  "not_sent": 0,
  "success_rate_percent": 94.67
}
```

**SQL Query for Details:**
```sql
SELECT 
    order_id,
    status,
    total,
    predicted_delivery_minutes,
    prediction_sent,
    prediction_failed,
    prediction_sent_at
FROM orders 
WHERE status = 'confirmed'
ORDER BY created_at DESC
LIMIT 20;
```

**Success Rate Calculation:**
```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN predicted_delivery_minutes IS NOT NULL THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN prediction_failed = 1 THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN predicted_delivery_minutes IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM orders
WHERE status = 'confirmed';
```

### Configuration

**Change Prediction Timeout:**

Edit `services/predictions.py`:
```python
async def get_prediction_for_order(self, order_id: str, timeout: float = 5.0):
    # Increase to 10.0 for slower prediction services
```

**Change Prediction Service URL:**

Edit `services/predictions.py`:
```python
PREDICTION_URL = "http://your-service:3000/predict/batch"
```

### Performance Characteristics

✅ **Zero Impact on Order Generation** - Predictions run async, order creation returns immediately
✅ **Fast** - 5-second timeout prevents slow predictions from accumulating
✅ **Resilient** - Failed predictions logged but don't crash the system
✅ **Transparent** - Easy to monitor success/failure rates via `/predictions/status`
✅ **Automatic** - No manual triggering required
✅ **Fallback Available** - Manual batch endpoint `/predictions/send` still available for retries

### Troubleshooting

**Orders Not Getting Predictions:**

1. Check prediction service is running:
   ```bash
   curl http://localhost:3000/health
   ```

2. Check API logs for errors:
   ```
   [HH:MM:SS] Prediction request failed: Connection refused
   ```

3. Verify order status (only 'confirmed' orders get predictions):
   ```sql
   SELECT status, COUNT(*) FROM orders GROUP BY status;
   ```

**High Failure Rate:**

- Increase timeout if prediction service is slow
- Check prediction service logs for errors
- Verify network connectivity between services
- Confirm data format matches prediction service expectations

### Key Benefits vs Previous Batch System

| Feature | Before (Batch) | Now (Automatic) |
|---------|---------------|-----------------|
| Coverage | Manual trigger needed | 100% automatic |
| Timing | Periodic batches | Immediate on confirmation |
| Performance | Could delay if slow | Non-blocking, no impact |
| Monitoring | Manual checking | Built-in `/predictions/status` |
| Retry | Manual re-run | Batch endpoint still available |

### Legacy Batch Prediction (Fallback)

While automatic predictions handle 100% of confirmed orders, the batch endpoint is still available for manual retries or catching missed orders:

**Manual Send:**
```bash
curl -X POST "http://localhost:8000/predictions/send?batch_size=10"
```

**Response:**
```json
{
  "total_orders": 25,
  "batches_sent": 3,
  "successful_batches": 3,
  "failed_batches": 0
}
```

**Order Format** sent to prediction service:
```json
{
  "orders": [
    {
      "order_id": "order_001",
      "customer_id": "customer_123",
      "store_id": "store_456",
      "store_latitude": 47.6062,
      "store_longitude": -122.3321,
      "delivery_latitude": 47.6205,
      "delivery_longitude": -122.3493,
      "total": 4500,
      "quantity": 5,
      "created_at": "2026-01-16T19:30:00"
    }
  ]
}
```

**Note**: `total` is in cents (multiply dollars by 100).
