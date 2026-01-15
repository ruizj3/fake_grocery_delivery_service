# Store Location and Product System

## Overview

This grocery delivery service now includes a comprehensive **store location** and **product hierarchy** system. Each order is associated with a specific store, and products are managed through a two-tier system:

1. **Parent Products** - The canonical product definitions (e.g., "Bananas" from "Dole")
2. **Store Products** - Store-specific instances with local pricing and availability

## Data Model

### Store Locations

Each store has:
- Unique location with address and coordinates
- Operating hours (opens_at, closes_at)
- Active status
- Geographic distribution across Bay Area cities

**Example Stores:**
- Daily Goods (San Jose)
- Choice Mart (San Francisco)
- Prime Cart (Berkeley)
- Metro Fare (Oakland)

### Product Hierarchy

#### Parent Products
- Define the canonical product catalog
- Include base price, category, brand, unit, weight
- 176 products across 10 categories:
  - Produce (20 items)
  - Dairy (18 items)
  - Meat (18 items)
  - Bakery (14 items)
  - Frozen (15 items)
  - Beverages (15 items)
  - Snacks (17 items)
  - Pantry (25 items)
  - Household (17 items)
  - Personal Care (17 items)

#### Store Products
- Link parent products to specific stores
- Store-specific pricing (±15% variance from base price)
- Availability status and stock levels
- Each store carries ~85% of the catalog (149 products)

### Order Flow

```
Customer → Places Order → At Specific Store
                ↓
          Order Items
                ↓
    Reference Store Products (with store-specific price)
                ↓
         Link to Parent Products (canonical definition)
```

## Database Schema

### Stores Table
```sql
CREATE TABLE stores (
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
```

### Parent Products Table
```sql
CREATE TABLE parent_products (
    parent_product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    base_price REAL NOT NULL,
    unit TEXT NOT NULL,
    weight_oz REAL,
    is_organic BOOLEAN DEFAULT FALSE
)
```

### Store Products Table
```sql
CREATE TABLE store_products (
    store_product_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    parent_product_id TEXT NOT NULL,
    price REAL NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    stock_level INTEGER DEFAULT 0,
    FOREIGN KEY (store_id) REFERENCES stores(store_id),
    FOREIGN KEY (parent_product_id) REFERENCES parent_products(parent_product_id)
)
```

### Orders Table (Updated)
```sql
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    store_id TEXT,  -- NEW: Links to specific store
    driver_id TEXT,
    status TEXT NOT NULL,
    subtotal REAL NOT NULL,
    tax REAL NOT NULL,
    delivery_fee REAL NOT NULL,
    tip REAL NOT NULL,
    total REAL NOT NULL,
    created_at TIMESTAMP NOT NULL,
    ...
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
)
```

### Order Items Table (Updated)
```sql
CREATE TABLE order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    store_product_id TEXT NOT NULL,  -- Links to store-specific product
    parent_product_id TEXT NOT NULL,  -- Links to canonical product
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (store_product_id) REFERENCES store_products(store_product_id),
    FOREIGN KEY (parent_product_id) REFERENCES parent_products(parent_product_id)
)
```

## Usage

### Generate Data

```bash
# Generate with default 500 orders
python main.py

# Generate with specific order count
python main.py --orders 1000

# Reset database and generate fresh data
python main.py --reset --orders 1000

# Export all tables to CSV
python main.py --export

# Show database statistics
python main.py --stats
```

### Verify Store System

```bash
python verify_store_system.py
```

This will show:
1. Store locations
2. Parent product catalog by category
3. Store inventory coverage
4. Price variance examples
5. Order-store-product relationships
6. Orders per store
7. Complete join path verification

## Example Queries

### Find all products at a specific store
```sql
SELECT pp.name, pp.category, sp.price, sp.stock_level
FROM store_products sp
JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
JOIN stores s ON sp.store_id = s.store_id
WHERE s.name = 'Daily Goods' AND sp.is_available = 1;
```

### Find price differences for same product across stores
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

### Get order details with store and product information
```sql
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
JOIN parent_products pp ON oi.parent_product_id = pp.parent_product_id;
```

### Store performance metrics
```sql
SELECT 
    s.name as store_name,
    COUNT(o.order_id) as order_count,
    ROUND(AVG(o.total), 2) as avg_order_value,
    ROUND(SUM(o.total), 2) as total_revenue
FROM stores s
LEFT JOIN orders o ON s.store_id = o.store_id
GROUP BY s.store_id, s.name
ORDER BY order_count DESC;
```

## Key Features

✅ **Store Locations**: Geographic distribution with realistic addresses and coordinates
✅ **Product Hierarchy**: Two-tier system with parent products and store-specific instances
✅ **Price Variance**: Store-specific pricing (±15% from base price)
✅ **Inventory Management**: Each store carries ~85% of catalog with availability tracking
✅ **Order-Store Association**: Orders placed at specific stores with proximity-based selection
✅ **Complete Traceability**: Full join path from order → store → store product → parent product
✅ **Scalability**: Automatically scales store count based on order volume (~100 orders per store)

## Exported CSV Files

When you run `python main.py --export`, the following files are created in `exports/`:

- `stores.csv` - Store locations and details
- `parent_products.csv` - Canonical product catalog
- `store_products.csv` - Store-specific product inventory
- `customers.csv` - Customer data
- `drivers.csv` - Driver data
- `orders.csv` - Orders with store associations
- `order_items.csv` - Order items with both store and parent product references

## Data Generation Flow

1. **Generate Customers** - Based on order count (5:1 ratio)
2. **Generate Drivers** - Based on order count (50:1 ratio)
3. **Generate Stores** - Based on order count (100:1 ratio)
4. **Generate Parent Products** - Full catalog of 176 products
5. **Generate Store Inventories** - For each store, create 85% coverage with price variance
6. **Generate Orders** - With proximity-based store selection
7. **Generate Order Items** - Referencing store-specific products

## Statistics (1000 Orders)

```
stores                10 rows
customers            200 rows
drivers               20 rows
parent_products      176 rows
store_products     1,490 rows  (10 stores × ~149 products each)
orders             1,000 rows
order_items        6,547 rows  (~6.5 items per order avg)
```

## Future Enhancements

Potential extensions to this system:
- Store-specific promotions and discounts
- Regional product availability (seasonal items)
- Multi-warehouse inventory management
- Store capacity and delivery radius limits
- Real-time inventory updates
- Store-specific delivery time windows
