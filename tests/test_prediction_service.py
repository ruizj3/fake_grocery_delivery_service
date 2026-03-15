"""
Test script to verify prediction service integration

This script:
1. Checks if the API is running
2. Generates some test orders
3. Manually triggers prediction sending
4. Shows the results
"""

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8000"

def test_prediction_service():
    print("🧪 Testing Prediction Service Integration")
    print("=" * 50)
    
    # Step 1: Check API is running
    print("\n1️⃣  Checking API status...")
    try:
        response = requests.get(f"{API_URL}/status")
        response.raise_for_status()
        status = response.json()
        print(f"   ✅ API is running")
        print(f"   Prediction sending active: {status.get('prediction_sending_active', False)}")
    except Exception as e:
        print(f"   ❌ API not responding: {e}")
        print(f"   Make sure to run: uvicorn api.main:app --reload --port 8000")
        return
    
    # Step 2: Generate test orders
    print("\n2️⃣  Generating test orders...")
    try:
        response = requests.post(f"{API_URL}/orders/generate?count=15")
        response.raise_for_status()
        result = response.json()
        print(f"   ✅ Generated {result['count']} orders")
        time.sleep(1)  # Give database a moment
    except Exception as e:
        print(f"   ⚠️  Error generating orders: {e}")
    
    # Step 3: Check confirmed orders
    print("\n3️⃣  Checking confirmed orders...")
    try:
        response = requests.get(f"{API_URL}/orders?status=confirmed&limit=100")
        response.raise_for_status()
        orders = response.json()
        confirmed_count = len(orders) if isinstance(orders, list) else 0
        print(f"   ✅ Found {confirmed_count} confirmed orders")
        
        if confirmed_count == 0:
            print("   ℹ️  No confirmed orders to send. Try generating more orders.")
            return
    except Exception as e:
        print(f"   ⚠️  Error checking orders: {e}")
    
    # Step 4: Send predictions manually
    print("\n4️⃣  Sending predictions (batch size: 10)...")
    try:
        response = requests.post(f"{API_URL}/predictions/send?batch_size=10")
        response.raise_for_status()
        result = response.json()
        
        print(f"   📊 Results:")
        print(f"      Total orders processed: {result['total_orders']}")
        print(f"      Batches sent: {result['batches_sent']}")
        print(f"      Successful: {result['successful_batches']}")
        print(f"      Failed: {result['failed_batches']}")
        
        if result['failed_batches'] > 0:
            print(f"\n   ⚠️  Some batches failed. Check if prediction service is running at http://localhost:3000")
            for i, batch_result in enumerate(result['results']):
                if not batch_result['success']:
                    print(f"      Batch {i+1} error: {batch_result.get('error', 'Unknown error')}")
        else:
            print(f"   ✅ All batches sent successfully!")
        
    except Exception as e:
        print(f"   ❌ Error sending predictions: {e}")
        print(f"   Make sure your prediction service is running at http://localhost:3000/predict/batch")
    
    # Step 5: Start automatic sending (optional)
    print("\n5️⃣  Testing automatic prediction service...")
    try:
        response = requests.post(f"{API_URL}/services/predictions/start")
        response.raise_for_status()
        result = response.json()
        
        if result['status'] == 'started':
            print(f"   ✅ Automatic prediction sending started")
            print(f"      Interval: {result['interval_seconds']} seconds")
            print(f"      Batch size: {result['batch_size']}")
            print(f"\n   💡 Watch the API logs to see automatic sending in action")
            print(f"      To stop: POST {API_URL}/services/predictions/stop")
        elif result['status'] == 'already_running':
            print(f"   ℹ️  Automatic sending was already running")
    except Exception as e:
        print(f"   ⚠️  Could not start automatic sending: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Test complete!")
    print("\nNext steps:")
    print("  • Check API logs for prediction sending messages")
    print("  • Verify your prediction service received the orders")
    print("  • Query database: SELECT * FROM orders WHERE prediction_sent = 1")

if __name__ == "__main__":
    test_prediction_service()
