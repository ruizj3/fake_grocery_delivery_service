# Geofencing & City-Based Matching Summary

## Overview

All data generation now respects strict geofencing constraints. All entities (stores, customers, drivers, orders, bundles) are confined to **6 specific cities**:

- San Francisco, CA
- Seattle, WA
- New York, NY
- Cincinnati, OH
- Dallas, TX
- San Jose, CA

## Implementation Details

### 1. Geofence Configuration (`generators/geofence.py`)

Each city has a defined delivery zone:
- **Center coordinates** (lat/lon)
- **Radius** (3-15 km depending on city size)
- **Weight** (controls distribution of data across cities)

### 2. Entity Generation

#### Stores (`generators/stores.py`)
- ✅ Select city using weighted random choice
- ✅ Generate coordinates within 60% of zone radius (central locations)
- ✅ Store explicit `city` and `state` fields

#### Customers (`generators/customers.py`)
- ✅ Select city using weighted random choice
- ✅ Generate coordinates within 100% of zone radius (uniform distribution)
- ✅ Store explicit `city` and `state` fields

#### Drivers (`generators/drivers.py`)
- ✅ Select city using weighted random choice
- ✅ Generate coordinates within 80% of zone radius (wider travel area)
- ✅ **NEW**: Store explicit `city` and `state` fields in database
- ✅ **NEW**: Added migration to backfill city/state for existing drivers

#### Orders (`generators/orders.py`)
- ✅ Select customer from database (customer already has geofenced location)
- ✅ Select store from **same city** as customer (weighted by proximity)
- ✅ Fallback to any store if no same-city store exists
- ✅ Delivery address = customer address (always in same city)

### 3. Bundle & Driver Assignment (`services/bundling.py`)

#### Bundle Creation
- ✅ Groups orders from **same store only** (ensures same city)
- ✅ Uses geographic proximity within city
- ✅ Respects time windows and capacity constraints

#### Driver Assignment
- ✅ **NEW**: Queries drivers with explicit `city` field
- ✅ Filters drivers to **same city** as bundle's orders
- ✅ Selects closest available driver within that city
- ✅ Fallback to nearest driver overall if no same-city driver available
- ✅ No coordinate-based zone lookups needed (uses direct city comparison)

### 4. Database Schema Changes

Added to `drivers` table:
```sql
ALTER TABLE drivers ADD COLUMN city TEXT;
ALTER TABLE drivers ADD COLUMN state TEXT;
```

Migration script: `migrations/migrate_add_driver_city.py`
- Adds city/state columns
- Backfills existing drivers using coordinate lookup
- All future drivers generated with city/state

## Performance Optimizations

### Historical Bundling (`scripts/bundle_historical_orders.py`)

For large datasets (100K+ orders), use batch processing:

```bash
# Default: 12-hour batches
python scripts/bundle_historical_orders.py

# Faster: 6-hour batches
python scripts/bundle_historical_orders.py --batch-hours 6

# Only recent orders
python scripts/bundle_historical_orders.py --limit-days 30

# Skip delivered orders
python scripts/bundle_historical_orders.py --skip-delivered
```

**Performance**: ~1000-2000 orders/second
- 100K orders: 1-2 minutes
- 1.2M orders: 10-20 minutes

### Complete Workflow (`scripts/generate_complete_dataset.py`)

One-command dataset generation:

```bash
# 100K orders with bundles
python scripts/generate_complete_dataset.py --orders 100000 --days 60

# 1.2M orders with bundles (faster batching)
python scripts/generate_complete_dataset.py --orders 1200000 --days 60 --bundle-hours 6
```

## Verification Scripts

### Check Geofencing (`scripts/verify_geofencing.py`)
```bash
python scripts/verify_geofencing.py
```

Verifies:
- All stores are in the 6 cities
- All customers are in the 6 cities
- All drivers are in the 6 cities
- All orders are in the 6 cities

### Check Bundle Matching (`scripts/test_bundle_city_matching.py`)
```bash
python scripts/test_bundle_city_matching.py
```

Verifies:
- All orders in a bundle are from same city
- Assigned driver is from same city as orders

### Check City Matching (`scripts/check_city_matching.py`)
```bash
python scripts/check_city_matching.py
```

Analyzes existing bundles for city mismatches.

## Data Distribution

Example from 1.2M order dataset:

| City | Stores | Customers | Drivers | Orders |
|------|--------|-----------|---------|--------|
| New York | 27 | 59,669 | 5,944 | 299,111 |
| San Francisco | 19 | 47,833 | 4,780 | 238,649 |
| Seattle | 16 | 43,241 | 4,424 | 216,052 |
| Dallas | 21 | 36,073 | 3,526 | 180,100 |
| Cincinnati | 9 | 29,064 | 2,913 | 145,960 |
| San Jose | 8 | 24,120 | 2,413 | 120,128 |

Distribution follows city weights defined in `geofence.py`.

## Key Benefits

1. **Realistic**: Orders only happen within a single city (like real delivery services)
2. **Efficient**: Direct city field comparison (no coordinate calculations needed)
3. **Reliable**: Explicit city storage prevents drift or edge cases
4. **Scalable**: Batch processing handles millions of orders efficiently
5. **Verifiable**: Multiple scripts to validate data integrity

## Migration Path

For existing databases:
1. Run migration: `python migrations/migrate_add_driver_city.py`
2. Verify: `python scripts/verify_geofencing.py`
3. Bundle (if needed): `python scripts/bundle_historical_orders.py`

For new datasets:
1. Use complete workflow: `python scripts/generate_complete_dataset.py --orders 1200000 --days 60`
