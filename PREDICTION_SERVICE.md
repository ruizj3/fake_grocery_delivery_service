# Prediction Service Integration

## Overview

The prediction service automatically sends confirmed orders to an external ML prediction service for processing. Orders are sent in batches of 10 to `http://localhost:3000/predict/batch`.

## How It Works

1. **Order Confirmation**: When orders are generated, they start with a status of `pending` or `confirmed`
2. **Automatic Sending**: A background service checks for confirmed orders every 30 seconds
3. **Batch Processing**: Orders are grouped into batches of 10 and sent to the prediction API
4. **Tracking**: Once sent, orders are marked with `prediction_sent = TRUE` to avoid duplicates

## Order Format

Orders are sent in the following JSON format:

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
      "created_at": "2026-01-16T19:30:00.123456"
    }
  ]
}
```

**Note**: The `total` field is in cents (multiply dollar amount by 100).

## API Endpoints

### Start Automatic Prediction Sending
```bash
POST http://localhost:8000/services/predictions/start
```

Starts the background service that automatically sends confirmed orders every 30 seconds.

**Response:**
```json
{
  "status": "started",
  "interval_seconds": 30.0,
  "batch_size": 10
}
```

### Stop Automatic Prediction Sending
```bash
POST http://localhost:8000/services/predictions/stop
```

Stops the automatic prediction sending service.

**Response:**
```json
{
  "status": "stopped"
}
```

### Manual Prediction Send
```bash
POST http://localhost:8000/predictions/send?batch_size=10
```

Manually triggers sending confirmed orders to the prediction service.

**Parameters:**
- `batch_size` (optional, default: 10): Number of orders per batch

**Response:**
```json
{
  "total_orders": 25,
  "batches_sent": 3,
  "successful_batches": 3,
  "failed_batches": 0,
  "results": [
    {
      "success": true,
      "status_code": 200,
      "data": {...},
      "orders_sent": 10
    }
  ]
}
```

### Start All Services (includes predictions)
```bash
POST http://localhost:8000/services/start-all
```

Starts all background services including:
- Order generation
- Bundle processing
- Delivery simulation
- **Prediction sending**
- Customer generation
- Driver generation
- Store generation

### Check Service Status
```bash
GET http://localhost:8000/status
```

Returns the status of all services including prediction sending:

```json
{
  "order_generation_active": true,
  "bundle_processing_active": true,
  "delivery_simulation_active": true,
  "prediction_sending_active": true,
  "customer_generation_active": true,
  "driver_generation_active": true,
  "store_generation_active": true,
  "order_interval_seconds": 10.0,
  "bundle_interval_seconds": 60.0,
  "prediction_interval_seconds": 30.0,
  "customer_interval_seconds": 120.0,
  "driver_interval_seconds": 300.0,
  "store_interval_seconds": 600.0
}
```

## Configuration

### Change Prediction Sending Interval
```bash
PATCH http://localhost:8000/services/config
Content-Type: application/json

{
  "prediction_interval_seconds": 60.0
}
```

This changes how often the service checks for and sends confirmed orders (default: 30 seconds).

### Change Batch Size

The batch size is currently hardcoded to 10 orders per batch in the automatic sending service. To use a different batch size, you can:

1. Call the manual endpoint with a custom `batch_size` parameter
2. Modify `batch_size=10` in the `automatic_prediction_sender()` function in `api/main.py`

## Database Schema

The `orders` table includes two tracking fields:

- `prediction_sent` (BOOLEAN): Whether the order has been sent to the prediction service
- `prediction_sent_at` (TIMESTAMP): When the order was sent to the prediction service

These fields ensure orders are only sent once, even if the service restarts or encounters errors.

## Testing

### 1. Start the API server
```bash
uvicorn api.main:app --reload --port 8000
```

### 2. Generate some orders
```bash
# Start order generation
POST http://localhost:8000/services/orders/start

# Or generate a batch manually
POST http://localhost:8000/orders/generate?count=50
```

### 3. Start prediction service
```bash
POST http://localhost:8000/services/predictions/start
```

### 4. Watch the logs
You should see messages like:
```
[19:30:15] Sent 25 confirmed orders for prediction (3/3 batches successful)
```

### 5. Check which orders were sent
```sql
SELECT order_id, status, prediction_sent, prediction_sent_at 
FROM orders 
WHERE status = 'confirmed' 
ORDER BY created_at DESC;
```

## Error Handling

- If the prediction service is unavailable, batches will fail but the service continues running
- Failed batches are logged with error details
- Orders that fail to send are NOT marked as sent, so they'll be retried on the next cycle
- The service sleeps for 10 seconds after any error before continuing

## Notes

- Only orders with `status = 'confirmed'` are sent
- Orders are only sent once (tracked via `prediction_sent` flag)
- The service fetches orders ordered by `created_at DESC` (newest first)
- Connection timeout is set to 30 seconds for the HTTP request
