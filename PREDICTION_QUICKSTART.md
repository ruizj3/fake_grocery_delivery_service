# Quick Start: Prediction Service

## Setup Complete! ✅

The prediction service has been integrated into your grocery delivery system. Here's what was added:

### New Features

1. **Database Schema Updates**
   - Added `prediction_sent` (BOOLEAN) field to track sent orders
   - Added `prediction_sent_at` (TIMESTAMP) field to track when orders were sent

2. **Background Service**
   - Automatic prediction sender runs every 30 seconds
   - Sends confirmed orders in batches of 10
   - Posts to `http://localhost:3000/predict/batch`

3. **API Endpoints**
   - `POST /services/predictions/start` - Start automatic sending
   - `POST /services/predictions/stop` - Stop automatic sending
   - `POST /predictions/send?batch_size=10` - Manual send

4. **Service Integration**
   - Prediction service included in `/services/start-all`
   - Status visible in `/status` endpoint
   - Configurable via `/services/config`

## Quick Test

### 1. Start your prediction service (port 3000)
Make sure your ML prediction service is running at `http://localhost:3000/predict/batch`

### 2. Start the API (if not already running)
```bash
uvicorn api.main:app --reload --port 8000
```

### 3. Generate some orders
```bash
curl -X POST "http://localhost:8000/orders/generate?count=20"
```

### 4. Start prediction sending
```bash
curl -X POST "http://localhost:8000/services/predictions/start"
```

### 5. Watch the logs
You should see output like:
```
[19:30:15] Sent 15 confirmed orders for prediction (2/2 batches successful)
```

## Order Format Example

Orders are sent to your prediction service in this format:

```json
{
  "orders": [
    {
      "order_id": "abc123...",
      "customer_id": "cust456...",
      "store_id": "store789...",
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

**Note**: `total` is in cents (multiply dollars by 100)

## Configuration

### Change batch size
Edit line in `api/main.py` (around line 420):
```python
result = await state.prediction_service.process_confirmed_orders(batch_size=10)
```
Change `batch_size=10` to your desired value.

### Change sending frequency
```bash
curl -X PATCH "http://localhost:8000/services/config" \
  -H "Content-Type: application/json" \
  -d '{"prediction_interval_seconds": 60}'
```

## Troubleshooting

### No orders being sent?
- Check that orders have `status = 'confirmed'`
- Run: `curl "http://localhost:8000/orders?status=confirmed"`

### Service not starting?
- Check `/status` endpoint to see current state
- Look for errors in the API logs

### Prediction service unavailable?
- Failed batches are logged but service continues
- Orders that fail are NOT marked as sent and will retry

## Next Steps

See [PREDICTION_SERVICE.md](PREDICTION_SERVICE.md) for complete documentation.
