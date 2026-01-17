"""
Prediction Service - Sends confirmed orders to external ML prediction service
"""
import sqlite3
from datetime import datetime
from typing import Optional
import httpx


PREDICTION_URL = "http://localhost:3000/predict/batch"
BATCH_SIZE = 10


class PredictionService:
    """Service to send confirmed orders to external prediction API"""
    
    def __init__(self, db_path: str = "database/grocery_delivery.db"):
        self.db_path = db_path
    
    def fetch_confirmed_orders_for_prediction(self, limit: Optional[int] = None) -> list[dict]:
        """
        Fetch confirmed orders that haven't been sent for prediction yet.
        
        Args:
            limit: Maximum number of orders to fetch. If None, fetches all.
        
        Returns:
            List of order dictionaries with all required fields for prediction
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch confirmed orders that haven't been sent yet
        query = """
            SELECT 
                o.order_id,
                o.customer_id,
                o.store_id,
                s.latitude as store_latitude,
                s.longitude as store_longitude,
                c.latitude as delivery_latitude,
                c.longitude as delivery_longitude,
                o.total,
                o.created_at,
                COUNT(oi.order_item_id) as quantity
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN stores s ON o.store_id = s.store_id
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'confirmed'
            AND (o.prediction_sent IS NULL OR o.prediction_sent = 0)
            GROUP BY o.order_id
            ORDER BY o.created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        orders = []
        for row in rows:
            orders.append({
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "store_id": row["store_id"],
                "store_latitude": row["store_latitude"],
                "store_longitude": row["store_longitude"],
                "delivery_latitude": row["delivery_latitude"],
                "delivery_longitude": row["delivery_longitude"],
                "total": int(row["total"] * 100),  # Convert to cents
                "quantity": row["quantity"],
                "created_at": row["created_at"]
            })
        
        return orders
    
    async def send_batch_prediction(self, orders: list[dict]) -> dict:
        """
        Send a batch of orders to the prediction service.
        
        Args:
            orders: List of order dictionaries
        
        Returns:
            Response from prediction service
        """
        payload = {"orders": orders}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(PREDICTION_URL, json=payload)
                response.raise_for_status()
                
                # Mark orders as sent
                self._mark_orders_as_sent([o["order_id"] for o in orders])
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json(),
                    "orders_sent": len(orders)
                }
        except httpx.HTTPError as e:
            return {
                "success": False,
                "error": str(e),
                "orders_sent": 0
            }
    
    def _mark_orders_as_sent(self, order_ids: list[str]):
        """
        Mark orders as sent to prediction service.
        
        Args:
            order_ids: List of order IDs to mark as sent
        """
        if not order_ids:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(order_ids))
        query = f"""
            UPDATE orders 
            SET prediction_sent = 1, 
                prediction_sent_at = datetime('now')
            WHERE order_id IN ({placeholders})
        """
        
        cursor.execute(query, order_ids)
        conn.commit()
        conn.close()
    
    async def process_confirmed_orders(self, batch_size: int = BATCH_SIZE) -> dict:
        """
        Fetch confirmed orders and send them in batches to prediction service.
        
        Args:
            batch_size: Number of orders per batch
        
        Returns:
            Summary of prediction processing
        """
        orders = self.fetch_confirmed_orders_for_prediction()
        
        if not orders:
            return {
                "total_orders": 0,
                "batches_sent": 0,
                "successful_batches": 0,
                "failed_batches": 0,
                "results": []
            }
        
        # Process in batches
        results = []
        successful_batches = 0
        failed_batches = 0
        
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            result = await self.send_batch_prediction(batch)
            results.append(result)
            
            if result["success"]:
                successful_batches += 1
            else:
                failed_batches += 1
        
        return {
            "total_orders": len(orders),
            "batches_sent": len(results),
            "successful_batches": successful_batches,
            "failed_batches": failed_batches,
            "results": results
        }
