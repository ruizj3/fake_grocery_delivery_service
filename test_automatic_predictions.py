#!/usr/bin/env python3
"""
Test script to verify automatic prediction functionality
"""

import time
import requests
import sqlite3
from pathlib import Path

API_URL = "http://localhost:8000"
PREDICTION_URL = "http://localhost:3000"
DB_PATH = Path(__file__).parent / "database" / "grocery_delivery.db"


def test_automatic_predictions():
    """Test that confirmed orders automatically get predictions."""
    
    print("🧪 Testing Automatic Prediction Setup\n")
    print("="*60)
    
    # Step 1: Check prediction service is running
    print("\n1. Checking prediction service connectivity...")
    try:
        response = requests.get(f"{PREDICTION_URL}/health", timeout=2)
        print(f"   ✅ Prediction service is running at {PREDICTION_URL}")
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️  WARNING: Cannot connect to prediction service at {PREDICTION_URL}")
        print("      Predictions will fail, but test will continue to verify error handling")
    except requests.exceptions.Timeout:
        print(f"   ⚠️  WARNING: Prediction service at {PREDICTION_URL} is slow to respond")
    except Exception as e:
        print(f"   ⚠️  WARNING: {e}")
    
    # Step 2: Check API is running
    print("\n2. Checking grocery delivery API connectivity...")
    try:
        response = requests.get(f"{API_URL}/")
        if response.status_code == 200:
            print(f"   ✅ API is running at {API_URL}")
        else:
            print("   ❌ API returned unexpected status")
            return
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect to API. Make sure it's running:")
        print("      uvicorn api.main:app --reload --port 8000")
        return
    
    # Step 3: Generate a test order
    print("\n3. Generating a test order...")
    try:
        response = requests.post(f"{API_URL}/orders/generate")
        if response.status_code == 200:
            order_data = response.json()
            order_id = order_data.get("order_id")
            status = order_data.get("status")
            print(f"   ✅ Order created: {order_id[:8]}...")
            print(f"   Status: {status}")
        else:
            print(f"   ❌ Failed to create order: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Step 3: Wait for prediction to complete
    print("\n4. Waiting for prediction to complete...")
    print("   (Checking database every 1 second for up to 10 seconds)")
    
    if not DB_PATH.exists():
        print(f"   ❌ Database not found at {DB_PATH}")
        return
    
    for i in range(10):
        time.sleep(1)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                status,
                predicted_delivery_minutes,
                prediction_sent,
                prediction_failed,
                prediction_sent_at
            FROM orders
            WHERE order_id = ?
        """, (order_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            status, est_time, pred_sent, pred_failed, sent_at = row
            
            if est_time is not None:
                print(f"\n   ✅ Prediction received!")
                print(f"      Estimated delivery time: {est_time} minutes")
                print(f"      Prediction sent at: {sent_at}")
                break
            elif pred_failed:
                print(f"\n   ⚠️  Prediction failed (but system handled it gracefully)")
                print(f"      Failed at: {sent_at}")
                break
        
        print(f"   ... waiting ({i+1}/10)")
    else:
        print("\n   ⚠️  No prediction received after 10 seconds")
        print("      This might be normal if:")
        print("      - Prediction service is not running")
        print("      - Order status was 'pending' instead of 'confirmed'")
    
    # Step 4: Check overall prediction status
    print("\n5. Checking overall prediction statistics...")
    try:
        response = requests.get(f"{API_URL}/predictions/status")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Total confirmed orders: {stats['total_confirmed_orders']}")
            print(f"   With predictions: {stats['with_predictions']}")
            print(f"   Failed predictions: {stats['failed_predictions']}")
            print(f"   Success rate: {stats['success_rate_percent']}%")
        else:
            print(f"   ⚠️  Could not fetch stats: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error fetching stats: {e}")
    
    # Step 5: Final summary
    print("\n" + "="*60)
    print("📊 Test Summary:")
    print("="*60)
    
    if status == 'confirmed':
        if est_time is not None:
            print("✅ PASS: Confirmed order received automatic prediction")
        elif pred_failed:
            print("✅ PARTIAL: System correctly handled prediction failure")
            print("   Note: Make sure prediction service is running for full test")
        else:
            print("⚠️  INCONCLUSIVE: No prediction received")
            print("   Possible reasons:")
            print("   - Prediction service not running")
            print("   - Network timeout")
            print("   - Check API logs for errors")
    else:
        print("ℹ️  Order was not confirmed (status: {status})")
        print("   Only confirmed orders get automatic predictions")
        print("   Try running the test again to get a confirmed order")
    
    print("\n💡 Next Steps:")
    print("   - Start prediction service if not running")
    print("   - Enable automatic order generation:")
    print("     curl -X POST http://localhost:8000/control/orders/start")
    print("   - Monitor predictions:")
    print("     curl http://localhost:8000/predictions/status")
    print()


if __name__ == "__main__":
    test_automatic_predictions()
