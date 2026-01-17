import uuid
import random
import math
from datetime import datetime, timedelta
from dataclasses import dataclass
from .base import BaseGenerator
from .customers import CustomerGenerator
from .drivers import DriverGenerator
from .products import ProductGenerator
from .stores import StoreGenerator
from models import OrderStatus
from db import get_cursor


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@dataclass
class Order:
    """Order with store association."""
    order_id: str
    customer_id: str
    store_id: str
    status: OrderStatus
    subtotal: float
    tax: float
    delivery_fee: float
    tip: float
    total: float
    created_at: datetime
    confirmed_at: datetime | None
    picked_at: datetime | None
    picking_completed_at: datetime | None
    delivered_at: datetime | None
    delivery_latitude: float
    delivery_longitude: float
    delivery_notes: str | None


@dataclass
class OrderItem:
    """Order item linking to store-specific product."""
    order_item_id: str
    order_id: str
    store_product_id: str
    parent_product_id: str
    quantity: int
    unit_price: float
    total_price: float


class OrderGenerator(BaseGenerator):
    """Generates orders that are placed at specific stores."""
    
    DELIVERY_NOTES = [
        None, None, None, None, None,
        "Leave at door",
        "Ring doorbell",
        "Call when arriving",
        "Gate code: {code}",
        "Leave with doorman",
        "Back door please",
        "Dog in yard - be careful",
        "Apartment {apt}",
        "Leave on porch",
        "Text when delivered",
    ]
    
    HOUR_WEIGHTS = [
        0.01, 0.01, 0.01, 0.01, 0.01, 0.02,
        0.03, 0.04, 0.05, 0.06, 0.07, 0.08,
        0.08, 0.07, 0.06, 0.06, 0.07, 0.08,
        0.09, 0.08, 0.06, 0.04, 0.02, 0.01,
    ]
    
    TAX_RATE = 0.0875
    BASE_DELIVERY_FEE = 5.99
    
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        self.customer_gen = CustomerGenerator(seed)
        self.driver_gen = DriverGenerator(seed)
        self.product_gen = ProductGenerator(seed)
        self.store_gen = StoreGenerator(seed)
        
        self._customer_ids = []
        self._driver_ids = []
        self._store_ids = []
        self._store_products_cache = {}
    
    def _load_dependencies(self):
        """Load existing IDs from database."""
        self._customer_ids = self.customer_gen.get_all_ids()
        self._driver_ids = self.driver_gen.get_active_ids()
        self._store_ids = self.store_gen.get_all_ids()
        
        if not self._customer_ids:
            raise ValueError("No customers found. Generate customers first.")
        if not self._driver_ids:
            raise ValueError("No active drivers found. Generate drivers first.")
        if not self._store_ids:
            raise ValueError("No stores found. Generate stores first.")
        
        self._store_products_cache = {}
    
    def _get_store_products(self, store_id: str) -> list[tuple]:
        """Get available products for a store (with caching)."""
        if store_id not in self._store_products_cache:
            products = self.product_gen.get_store_available_products(store_id)
            self._store_products_cache[store_id] = products
        return self._store_products_cache[store_id]
    
    def _generate_order_time(self, days_back_max: int = 365) -> datetime:
        """Generate realistic order timestamp."""
        days_ago = random.randint(0, days_back_max)
        order_date = datetime.now() - timedelta(days=days_ago)
        hour = random.choices(range(24), weights=self.HOUR_WEIGHTS)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        return order_date.replace(hour=hour, minute=minute, second=second)
    
    def _generate_delivery_note(self) -> str | None:
        note = random.choice(self.DELIVERY_NOTES)
        if note and "{code}" in note:
            note = note.format(code=random.randint(1000, 9999))
        if note and "{apt}" in note:
            note = note.format(apt=random.randint(1, 500))
        return note
    
    def _calculate_tip(self, subtotal: float, status: OrderStatus) -> float:
        """Generate realistic tip based on subtotal."""
        if status == OrderStatus.CANCELED:
            return 0.0
        tip_pct = random.choices(
            [0, 0.10, 0.15, 0.18, 0.20, 0.25],
            weights=[0.05, 0.15, 0.30, 0.25, 0.20, 0.05]
        )[0]
        return round(subtotal * tip_pct, 2)
    
    def _generate_order_status(self, created_at: datetime) -> OrderStatus:
        """Generate initial order status.
        
        New orders start as PENDING or CONFIRMED.
        The background cancellation simulator service will cancel orders
        as they progress through the lifecycle based on their current status.
        
        For batch/historical generation, you can generate a mix of statuses
        to simulate orders at different stages.
        """
        # Orders start as pending or confirmed
        # They progress through the lifecycle naturally via the bundling/delivery services
        # Cancellations happen via the live cancellation simulator
        return random.choices(
            [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PICKING, 
             OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            weights=[0.10, 0.20, 0.05, 0.05, 0.60]  # Mix of statuses for historical data
        )[0]
    
    def _generate_timestamps(self, status: OrderStatus, created_at: datetime) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None]:
        """Generate realistic timestamps based on order status.
        
        Timestamps are guaranteed to be chronological:
        created_at < confirmed_at < picked_at < picking_completed_at < delivered_at
        
        Note: This generator does NOT create canceled orders.
        Cancellations happen via the live cancellation simulator service.
        """
        confirmed_at = None
        picked_at = None
        picking_completed_at = None
        delivered_at = None
        
        # Set timestamps progressively based on status
        # Each timestamp builds on the previous one, ensuring chronological order
        
        if status in [OrderStatus.CONFIRMED, OrderStatus.PICKING, OrderStatus.OUT_FOR_DELIVERY, 
                      OrderStatus.DELIVERED]:
            # Order confirmed 2-15 minutes after creation
            confirmed_at = created_at + timedelta(minutes=random.randint(2, 15))
        
        # Orders that reach picking stage
        if status in [OrderStatus.PICKING, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]:
            if confirmed_at:
                # Picking started 20-90 minutes after confirmation (includes bundling wait time)
                picked_at = confirmed_at + timedelta(minutes=random.randint(20, 90))
        
        # Orders that complete picking and go out for delivery
        if status in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]:
            if picked_at:
                # Picking completed 15-45 minutes after picking started (shopping time)
                picking_completed_at = picked_at + timedelta(minutes=random.randint(15, 45))
        
        # Only delivered orders get delivered_at timestamp
        if status == OrderStatus.DELIVERED:
            if picking_completed_at:
                # Delivered 30-90 minutes after picking completed (driving + multiple stops)
                delivered_at = picking_completed_at + timedelta(minutes=random.randint(30, 90))
        
        # Validate chronological order (defensive programming)
        if confirmed_at and confirmed_at <= created_at:
            raise ValueError(f"confirmed_at must be after created_at")
        if picked_at and confirmed_at and picked_at <= confirmed_at:
            raise ValueError(f"picked_at must be after confirmed_at")
        if picking_completed_at and picked_at and picking_completed_at <= picked_at:
            raise ValueError(f"picking_completed_at must be after picked_at")
        if delivered_at and picking_completed_at and delivered_at <= picking_completed_at:
            raise ValueError(f"delivered_at must be after picking_completed_at")
        
        return confirmed_at, picked_at, picking_completed_at, delivered_at
    
    def _get_delivery_fee(self, subtotal: float, is_premium: bool) -> float:
        """Calculate delivery fee."""
        if is_premium:
            return 0.0 if subtotal >= 35 else 2.99
        return self.BASE_DELIVERY_FEE if subtotal < 35 else 3.99
    
    def _select_store_for_customer(self, customer_lat: float, customer_lon: float) -> str:
        """Select a store for the customer within the same city zone, weighted by proximity."""
        with get_cursor() as cursor:
            # Get stores in the same city as customer
            cursor.execute(
                """SELECT store_id, city, latitude, longitude 
                   FROM stores 
                   WHERE is_active = 1"""
            )
            all_stores = cursor.fetchall()
        
        if not all_stores:
            raise ValueError("No active stores found")
        
        # Filter to stores in same city (based on geofence)
        from .geofence import get_zone_for_coordinates
        customer_zone = get_zone_for_coordinates(customer_lat, customer_lon)
        
        if customer_zone is None:
            # Customer outside all zones, fall back to nearest store
            stores = all_stores
        else:
            # Only consider stores in the same city
            stores = [s for s in all_stores if s[1] == customer_zone["city"]]
            if not stores:
                # No stores in customer's city, fall back to all stores
                stores = all_stores
        
        # Weight by distance (closer stores more likely)
        distances = []
        for store in stores:
            dist = haversine_distance(customer_lat, customer_lon, store[2], store[3])
            distances.append(max(0.1, dist))
        
        weights = [1.0 / (d ** 2) for d in distances]  # Square inverse for stronger proximity preference
        selected = random.choices(stores, weights=weights)[0]
        return selected[0]
    
    def generate_one(self, live_mode: bool = True) -> tuple[Order, list[OrderItem]]:
        """Generate a single order.
        
        Args:
            live_mode: If True, creates a fresh order with current timestamp and pending/confirmed status.
                      If False, creates historical order with random past timestamp and varied statuses.
        """
        if not self._customer_ids:
            self._load_dependencies()
        
        order_id = str(uuid.uuid4())
        customer_id = random.choice(self._customer_ids)
        
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, is_premium FROM customers WHERE customer_id = ?",
                (customer_id,)
            )
            row = cursor.fetchone()
            customer_lat, customer_lon, is_premium = row[0], row[1], bool(row[2])
        
        store_id = self._select_store_for_customer(customer_lat, customer_lon)
        store_products = self._get_store_products(store_id)
        
        if not store_products:
            raise ValueError(f"No products found for store {store_id}. Generate store inventory first.")
        
        num_items = random.choices(
            range(1, 16),
            weights=[1, 3, 8, 12, 15, 15, 12, 8, 5, 4, 3, 2, 2, 1, 1]
        )[0]
        
        selected_products = random.sample(
            store_products, 
            min(num_items, len(store_products))
        )
        
        order_items = []
        subtotal = 0.0
        
        for store_product_id, parent_product_id, price in selected_products:
            quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3])[0]
            item_total = round(price * quantity, 2)
            subtotal += item_total
            
            order_items.append(OrderItem(
                order_item_id=str(uuid.uuid4()),
                order_id=order_id,
                store_product_id=store_product_id,
                parent_product_id=parent_product_id,
                quantity=quantity,
                unit_price=price,
                total_price=item_total,
            ))
        
        subtotal = round(subtotal, 2)
        delivery_fee = self._get_delivery_fee(subtotal, is_premium)
        tax = round(subtotal * self.TAX_RATE, 2)
        
        if live_mode:
            # Live orders: created NOW with pending/confirmed status
            created_at = datetime.now()
            status = random.choice([OrderStatus.PENDING, OrderStatus.CONFIRMED])
            # Live orders start fresh - no historical timestamps
            confirmed_at = created_at + timedelta(minutes=random.randint(1, 3)) if status == OrderStatus.CONFIRMED else None
            picked_at = None
            picking_completed_at = None
            delivered_at = None
        else:
            # Historical orders: random past time with varied statuses and full lifecycle
            created_at = self._generate_order_time()
            status = self._generate_order_status(created_at)
            confirmed_at, picked_at, picking_completed_at, delivered_at = self._generate_timestamps(
                status, created_at
            )
        
        tip = self._calculate_tip(subtotal, status)
        total = round(subtotal + tax + delivery_fee + tip, 2)
        
        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            store_id=store_id,
            status=status,
            subtotal=subtotal,
            tax=tax,
            delivery_fee=delivery_fee,
            tip=tip,
            total=total,
            created_at=created_at,
            confirmed_at=confirmed_at,
            picked_at=picked_at,
            picking_completed_at=picking_completed_at,
            delivered_at=delivered_at,
            delivery_latitude=customer_lat,
            delivery_longitude=customer_lon,
            delivery_notes=self._generate_delivery_note(),
        )
        
        return order, order_items
    
    def generate_batch(self, count: int, enable_clustering: bool = True, live_mode: bool = False) -> tuple[list[Order], list[OrderItem]]:
        """Generate orders with optional temporal clustering for realistic bundling.
        
        Args:
            count: Number of orders to generate
            enable_clustering: If True, creates order bursts from same stores (better for bundling)
            live_mode: If True, creates fresh orders. If False (default), creates historical data.
        """
        self._load_dependencies()
        orders = []
        all_items = []
        
        if enable_clustering and not live_mode:
            # Generate orders in clusters for realistic bundling (historical data only)
            orders, all_items = self._generate_clustered_batch(count)
        else:
            # Generate individual orders (for live mode or non-clustered batch)
            for i in range(count):
                order, items = self.generate_one(live_mode=live_mode)
                orders.append(order)
                all_items.extend(items)
                
                if (i + 1) % 100 == 0:
                    print(f"Generated {i + 1}/{count} orders...")
        
        return orders, all_items
    
    def _generate_clustered_batch(self, count: int) -> tuple[list[Order], list[OrderItem]]:
        """Generate orders with temporal clustering for realistic bundling.
        
        Creates bursts of 2-6 orders from the same store within 15-30 minute windows,
        simulating realistic lunch/dinner rush patterns.
        """
        orders = []
        all_items = []
        remaining = count
        
        while remaining > 0:
            # Decide cluster size (40% single orders, 60% clustered)
            if random.random() < 0.4 or remaining == 1:
                cluster_size = 1
            else:
                cluster_size = min(random.choices([2, 3, 4, 5, 6], weights=[30, 25, 20, 15, 10])[0], remaining)
            
            # Generate base timestamp for this cluster
            base_time = self._generate_order_time()
            
            # Pick a random store for this cluster
            base_store_id = random.choice(self._store_ids)
            
            # Generate orders in this cluster
            for i in range(cluster_size):
                order_id = str(uuid.uuid4())
                customer_id = random.choice(self._customer_ids)
                
                with get_cursor() as cursor:
                    cursor.execute(
                        "SELECT latitude, longitude, is_premium FROM customers WHERE customer_id = ?",
                        (customer_id,)
                    )
                    row = cursor.fetchone()
                    customer_lat, customer_lon, is_premium = row[0], row[1], bool(row[2])
                
                # Use the cluster's store (same store for bundling)
                store_id = base_store_id
                store_products = self._get_store_products(store_id)
                
                if not store_products:
                    # Fallback to different store if no products
                    store_id = self._select_store_for_customer(customer_lat, customer_lon)
                    store_products = self._get_store_products(store_id)
                
                # Generate order items
                num_items = random.choices(
                    range(1, 16),
                    weights=[1, 3, 8, 12, 15, 15, 12, 8, 5, 4, 3, 2, 2, 1, 1]
                )[0]
                
                selected_products = random.sample(
                    store_products, 
                    min(num_items, len(store_products))
                )
                
                order_items = []
                subtotal = 0.0
                
                for store_product_id, parent_product_id, price in selected_products:
                    quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 30, 12, 5, 3])[0]
                    item_total = round(price * quantity, 2)
                    subtotal += item_total
                    
                    order_items.append(OrderItem(
                        order_item_id=str(uuid.uuid4()),
                        order_id=order_id,
                        store_product_id=store_product_id,
                        parent_product_id=parent_product_id,
                        quantity=quantity,
                        unit_price=price,
                        total_price=item_total,
                    ))
                
                subtotal = round(subtotal, 2)
                delivery_fee = self._get_delivery_fee(subtotal, is_premium)
                tax = round(subtotal * self.TAX_RATE, 2)
                
                # Add 0-30 minutes to base time for orders in same cluster
                created_at = base_time + timedelta(minutes=random.randint(0, 30))
                
                # For clustered orders, bias towards pending/confirmed status
                status = random.choices(
                    [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PICKING, 
                     OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
                    weights=[0.30, 0.40, 0.05, 0.05, 0.20]  # More pending/confirmed for bundling
                )[0]
                
                tip = self._calculate_tip(subtotal, status)
                total = round(subtotal + tax + delivery_fee + tip, 2)
                
                confirmed_at, picked_at, picking_completed_at, delivered_at = self._generate_timestamps(
                    status, created_at
                )
                
                order = Order(
                    order_id=order_id,
                    customer_id=customer_id,
                    store_id=store_id,
                    status=status,
                    subtotal=subtotal,
                    tax=tax,
                    delivery_fee=delivery_fee,
                    tip=tip,
                    total=total,
                    created_at=created_at,
                    confirmed_at=confirmed_at,
                    picked_at=picked_at,
                    picking_completed_at=picking_completed_at,
                    delivered_at=delivered_at,
                    delivery_latitude=customer_lat,
                    delivery_longitude=customer_lon,
                    delivery_notes=self._generate_delivery_note(),
                )
                
                orders.append(order)
                all_items.extend(order_items)
            
            remaining -= cluster_size
            
            if len(orders) % 100 == 0:
                print(f"Generated {len(orders)}/{count} orders (with clustering)...")
        
        return orders, all_items
    
    def save_to_db(self, records: tuple[list[Order], list[OrderItem]]):
        orders, items = records
        
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO orders 
                (order_id, customer_id, store_id, status, subtotal, tax,
                 delivery_fee, tip, total, created_at, confirmed_at, picked_at,
                 picking_completed_at, delivered_at, delivery_latitude, delivery_longitude, delivery_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (o.order_id, o.customer_id, o.store_id, o.status.value,
                     o.subtotal, o.tax, o.delivery_fee, o.tip, o.total,
                     o.created_at.isoformat(),
                     o.confirmed_at.isoformat() if o.confirmed_at else None,
                     o.picked_at.isoformat() if o.picked_at else None,
                     o.picking_completed_at.isoformat() if o.picking_completed_at else None,
                     o.delivered_at.isoformat() if o.delivered_at else None,
                     o.delivery_latitude, o.delivery_longitude, o.delivery_notes)
                    for o in orders
                ]
            )
            
            cursor.executemany(
                """
                INSERT INTO order_items 
                (order_item_id, order_id, store_product_id, parent_product_id,
                 quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (i.order_item_id, i.order_id, i.store_product_id, i.parent_product_id,
                     i.quantity, i.unit_price, i.total_price)
                    for i in items
                ]
            )
        
        print(f"Saved {len(orders)} orders and {len(items)} order items")
        
        # Return list of confirmed order IDs for immediate prediction
        confirmed_order_ids = [o.order_id for o in orders if o.status == OrderStatus.CONFIRMED]
        return confirmed_order_ids
