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
from .product_selection import select_products_for_order, calculate_cart_size
from .environmental import generate_weather_condition, calculate_total_delivery_multiplier
from models import OrderStatus
from database.db import get_cursor


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
    """Order with store association and ML features."""
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
    # ML realism fields
    weather_condition: str | None = None
    traffic_multiplier: float = 1.0
    is_peak_hour: bool = False
    is_weekend: bool = False
    customer_order_number: int = 1
    days_since_last_order: int | None = None
    cancellation_risk: float = 0.05


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
    
    def __init__(self, seed: int | None = 42, days_back_max: int = 90):
        super().__init__(seed)
        self.customer_gen = CustomerGenerator(seed)
        self.driver_gen = DriverGenerator(seed)
        self.product_gen = ProductGenerator(seed)
        self.store_gen = StoreGenerator(seed)
        self.days_back_max = days_back_max
        
        self._customer_ids = []
        self._driver_ids = []
        self._store_ids = []
        self._store_products_cache = {}
        self._customer_weights = {}  # Weighted selection for realistic ordering patterns
    
    def _load_dependencies(self):
        """Load existing IDs from database."""
        all_customer_ids = self.customer_gen.get_all_ids()
        self._driver_ids = self.driver_gen.get_active_ids()
        self._store_ids = self.store_gen.get_all_ids()
        
        if not all_customer_ids:
            raise ValueError("No customers found. Generate customers first.")
        if not self._driver_ids:
            raise ValueError("No active drivers found. Generate drivers first.")
        if not self._store_ids:
            raise ValueError("No stores found. Generate stores first.")
        
        # Only use customers in cities that have stores
        # Also verify they're within valid delivery zones
        from .geofence import get_zone_for_coordinates
        
        with get_cursor() as cursor:
            cursor.execute("SELECT DISTINCT city FROM stores WHERE is_active = 1")
            cities_with_stores = {row[0] for row in cursor.fetchall()}
            
            cursor.execute("SELECT customer_id, city, latitude, longitude FROM customers")
            eligible_customers = []
            for row in cursor.fetchall():
                cust_id, city, lat, lon = row
                # Check if customer's city has stores AND they're in a valid zone
                if city in cities_with_stores:
                    zone = get_zone_for_coordinates(lat, lon)
                    # Only include if in a valid zone (handles edge cases at zone boundaries)
                    if zone is not None:
                        eligible_customers.append(cust_id)
            
            self._customer_ids = eligible_customers
        
        if not self._customer_ids:
            print(f"⚠️  Warning: No eligible customers found in cities with stores.")
            print(f"   Cities with stores: {cities_with_stores}")
            print(f"   This may happen if customers are at zone boundaries or no stores exist yet.")
            # Don't fail - just use empty list and skip order generation
            self._customer_ids = []
        
        # Assign customer loyalty tiers for realistic ordering patterns
        # 50% one-time (weight 1), 25% occasional (weight 3-5), 15% regular (weight 8-12), 10% loyal (weight 15-25)
        self._customer_weights = {}
        for customer_id in self._customer_ids:
            tier = random.choices(
                ['one_time', 'occasional', 'regular', 'loyal'],
                weights=[0.50, 0.25, 0.15, 0.10]
            )[0]
            
            if tier == 'one_time':
                self._customer_weights[customer_id] = 1  # Single order
            elif tier == 'occasional':
                self._customer_weights[customer_id] = random.randint(3, 5)  # 2-4 orders per month
            elif tier == 'regular':
                self._customer_weights[customer_id] = random.randint(8, 12)  # 1-2 orders per week
            else:  # loyal
                self._customer_weights[customer_id] = random.randint(15, 25)  # 3+ orders per week
        
        self._store_products_cache = {}
    
    def _get_weighted_customer(self, city: str | None = None) -> str:
        """Get a customer using weighted selection based on loyalty tiers.
        
        Dynamically reloads customers to include newly generated ones.
        Assigns loyalty tiers on-the-fly for new customers.
        
        Args:
            city: Optional city filter. If provided, only returns customers from that city.
        
        Returns:
            customer_id of selected customer
        """
        from .geofence import get_zone_for_coordinates
        
        # Get fresh customer list from database (includes newly generated customers)
        with get_cursor() as cursor:
            if city:
                cursor.execute(
                    "SELECT customer_id, city, latitude, longitude FROM customers WHERE city = ?",
                    (city,)
                )
                customers = cursor.fetchall()
            else:
                # Get customers in cities with stores
                cursor.execute("SELECT DISTINCT city FROM stores WHERE is_active = 1")
                cities_with_stores = {row[0] for row in cursor.fetchall()}
                
                cursor.execute("SELECT customer_id, city, latitude, longitude FROM customers")
                all_customers = cursor.fetchall()
                
                # Filter to eligible customers (in cities with stores and valid zones)
                customers = []
                for row in all_customers:
                    cust_id, cust_city, lat, lon = row
                    if cust_city in cities_with_stores:
                        zone = get_zone_for_coordinates(lat, lon)
                        if zone is not None:
                            customers.append((cust_id, cust_city, lat, lon))
        
        if not customers:
            raise ValueError(f"No eligible customers found" + (f" in {city}" if city else ""))
        
        customer_ids = [row[0] for row in customers]
        
        # Assign loyalty tiers for new customers not in cache
        for customer_id in customer_ids:
            if customer_id not in self._customer_weights:
                tier = random.choices(
                    ['one_time', 'occasional', 'regular', 'loyal'],
                    weights=[0.50, 0.25, 0.15, 0.10]
                )[0]
                
                if tier == 'one_time':
                    self._customer_weights[customer_id] = 1
                elif tier == 'occasional':
                    self._customer_weights[customer_id] = random.randint(3, 5)
                elif tier == 'regular':
                    self._customer_weights[customer_id] = random.randint(8, 12)
                else:  # loyal
                    self._customer_weights[customer_id] = random.randint(15, 25)
        
        # Weighted selection
        weights = [self._customer_weights[cid] for cid in customer_ids]
        return random.choices(customer_ids, weights=weights)[0]
    
    def _get_store_products(self, store_id: str) -> list[tuple]:
        """Get available products for a store (with caching)."""
        if store_id not in self._store_products_cache:
            products = self.product_gen.get_store_available_products(store_id)
            self._store_products_cache[store_id] = products
        return self._store_products_cache[store_id]
    
    # Day-of-week order volume weights (Mon=0, Sun=6)
    # Weekdays slightly lower, Sat/Sun higher for grocery delivery
    DAY_OF_WEEK_WEIGHTS = [0.13, 0.12, 0.13, 0.13, 0.15, 0.17, 0.17]
    
    def _generate_order_time(self, days_back_max: int | None = None) -> datetime:
        """Generate realistic order timestamp with day-of-week and recency bias.
        
        Creates non-uniform distribution:
        - Recent days have more orders (simulates business growth)
        - Weekends have ~20% more orders than weekdays
        - Maintains hourly patterns from HOUR_WEIGHTS
        """
        if days_back_max is None:
            days_back_max = self.days_back_max
        
        # Recency bias: more recent days get more orders
        # Using exponential decay - 70% of orders in most recent half of time window
        # This simulates business growth over time
        recency_factor = random.random() ** 0.6  # Skew toward recent (0 = today, 1 = oldest)
        days_ago_base = int(recency_factor * days_back_max)
        
        # Generate candidate date
        candidate_date = datetime.now() - timedelta(days=days_ago_base)
        day_of_week = candidate_date.weekday()
        
        # Apply day-of-week acceptance (rejection sampling)
        # Normalize weight to max 1.0 for acceptance probability
        max_weight = max(self.DAY_OF_WEEK_WEIGHTS)
        acceptance_prob = self.DAY_OF_WEEK_WEIGHTS[day_of_week] / max_weight
        
        # Retry with different day if rejected (up to 5 attempts, then accept anyway)
        attempts = 0
        while random.random() > acceptance_prob and attempts < 5:
            recency_factor = random.random() ** 0.6
            days_ago_base = int(recency_factor * days_back_max)
            candidate_date = datetime.now() - timedelta(days=days_ago_base)
            day_of_week = candidate_date.weekday()
            acceptance_prob = self.DAY_OF_WEEK_WEIGHTS[day_of_week] / max_weight
            attempts += 1
        
        # Apply hourly distribution
        hour = random.choices(range(24), weights=self.HOUR_WEIGHTS)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        return candidate_date.replace(hour=hour, minute=minute, second=second)
    
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
    
    def _calculate_cancellation_risk(self, customer_id: str, total: float, 
                                     is_premium: bool, traffic_multiplier: float,
                                     db_cursor=None) -> float:
        """
        Calculate cancellation risk based on multiple factors.
        Returns probability (0-1) that order will be canceled.
        """
        base_risk = 0.05  # 5% base cancellation rate
        
        # Factor 1: Order value (large orders less likely to cancel)
        if total > 200:
            base_risk -= 0.02
        elif total < 30:
            base_risk += 0.03
        
        # Factor 2: Premium members cancel less
        if is_premium:
            base_risk -= 0.03
        
        # Factor 3: Traffic/delays increase cancellations
        if traffic_multiplier > 1.5:
            base_risk += 0.10
        elif traffic_multiplier > 1.3:
            base_risk += 0.05
        
        # Factor 4: Customer's past cancellation rate
        if db_cursor is None:
            with get_cursor() as cursor:
                db_cursor = cursor
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_orders,
                        SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_orders
                    FROM orders
                    WHERE customer_id = ?
                """, (customer_id,))
                row = cursor.fetchone()
        else:
            db_cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_orders
                FROM orders
                WHERE customer_id = ?
            """, (customer_id,))
            row = db_cursor.fetchone()
        
        if row and row[0] > 0:
            past_cancel_rate = row[1] / row[0]
            if past_cancel_rate > 0.3:
                base_risk += 0.10
            elif past_cancel_rate > 0.15:
                base_risk += 0.05
        
        # Ensure risk stays in valid range
        return max(0.0, min(0.5, base_risk))
    
    def _generate_order_status(self, created_at: datetime, is_historical: bool = True) -> OrderStatus:
        """Generate order status based on whether it's historical or live data.
        
        For historical data: Orders should be in final states (80% DELIVERED, 20% CANCELED)
        For live/recent data: Orders start as PENDING or CONFIRMED and progress via bundling service
        
        Args:
            created_at: When the order was created
            is_historical: If True, generates final states. If False, generates initial states.
        """
        if is_historical:
            # Historical orders are in final states
            # 92% successfully delivered, 8% canceled (realistic grocery delivery rate)
            return random.choices(
                [OrderStatus.DELIVERED, OrderStatus.CANCELED],
                weights=[0.92, 0.08]
            )[0]
        else:
            # Live/recent orders start as pending or confirmed
            # They progress through bundling service
            return random.choice([OrderStatus.PENDING, OrderStatus.CONFIRMED])
    
    def _generate_timestamps(self, status: OrderStatus, created_at: datetime, 
                            is_historical: bool = True, 
                            store_lat: float | None = None, 
                            store_lon: float | None = None,
                            customer_lat: float | None = None,
                            customer_lon: float | None = None,
                            driver_speed_multiplier: float = 1.0,
                            traffic_multiplier: float = 1.0) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None]:
        """Generate realistic timestamps based on order status.
        
        For live orders: Only creates confirmed_at. Bundling service handles the rest.
        For historical orders: Generates complete lifecycle timestamps for realism.
        
        Timestamps are guaranteed to be chronological:
        created_at < confirmed_at < picked_at < picking_completed_at < delivered_at
        
        Args:
            status: Current order status
            created_at: When order was created
            is_historical: If True, generates full lifecycle. If False, only initial timestamps.
            store_lat: Store latitude (for distance-based delivery time)
            store_lon: Store longitude (for distance-based delivery time)
            customer_lat: Customer delivery latitude (for distance-based delivery time)
            customer_lon: Customer delivery longitude (for distance-based delivery time)
            driver_speed_multiplier: Driver's speed multiplier (0.7-1.3x)
            traffic_multiplier: Traffic/weather delivery multiplier (1.0-2.1x)
        """
        confirmed_at = None
        picked_at = None
        picking_completed_at = None
        delivered_at = None
        
        if not is_historical:
            # Live orders: only set confirmed_at for CONFIRMED status
            if status == OrderStatus.CONFIRMED:
                confirmed_at = created_at + timedelta(minutes=random.randint(1, 5))
            return confirmed_at, None, None, None
        
        # Historical orders: generate complete lifecycle timestamps
        if status == OrderStatus.CANCELED:
            # Canceled orders: confirmed, then canceled at random stage
            # Gaussian confirmation delay: clusters around mean
            confirm_delay = self.rng.gaussian(
                mean=self.sim_config.confirmation_delay_mean_sec / 60.0,
                std=self.sim_config.confirmation_delay_std_sec / 60.0,
                minimum=1.0, maximum=10.0
            )
            confirmed_at = created_at + timedelta(minutes=confirm_delay)
            
            # 40% canceled before picking, 30% during confirmation, 20% during picking, 10% during delivery
            cancel_stage = random.choices(
                ['before_pick', 'during_pick', 'during_delivery'],
                weights=[0.30, 0.20, 0.10]
            )[0]
            
            if cancel_stage == 'before_pick':
                # Canceled after confirmation but before picking started
                # Just confirmed_at, rest are None
                pass
            elif cancel_stage == 'during_pick':
                # Canceled during picking - Gaussian picking wait
                pick_delay = self.rng.gaussian(mean=12.0, std=4.0, minimum=5.0, maximum=25.0)
                picked_at = confirmed_at + timedelta(minutes=pick_delay)
            else:  # during_delivery
                # Canceled during delivery (rare)
                pick_delay = self.rng.gaussian(mean=12.0, std=4.0, minimum=5.0, maximum=25.0)
                picked_at = confirmed_at + timedelta(minutes=pick_delay)
                picking_dur = self.rng.gaussian(
                    mean=self.sim_config.picking_duration_mean_min,
                    std=self.sim_config.picking_duration_std_min,
                    minimum=8.0, maximum=30.0
                )
                picking_completed_at = picked_at + timedelta(minutes=picking_dur)
        
        elif status == OrderStatus.DELIVERED:
            # Delivered orders: complete lifecycle with all timestamps
            # Gaussian confirmation delay
            confirm_delay = self.rng.gaussian(
                mean=self.sim_config.confirmation_delay_mean_sec / 60.0,
                std=self.sim_config.confirmation_delay_std_sec / 60.0,
                minimum=1.0, maximum=10.0
            )
            confirmed_at = created_at + timedelta(minutes=confirm_delay)
            
            # Gaussian pick start delay
            pick_delay = self.rng.gaussian(mean=12.0, std=4.0, minimum=5.0, maximum=25.0)
            picked_at = confirmed_at + timedelta(minutes=pick_delay)
            
            # Gaussian picking duration
            picking_dur = self.rng.gaussian(
                mean=self.sim_config.picking_duration_mean_min,
                std=self.sim_config.picking_duration_std_min,
                minimum=8.0, maximum=30.0
            )
            picking_completed_at = picked_at + timedelta(minutes=picking_dur)
            
            # Calculate delivery time based on distance from store to customer
            if (store_lat is not None and store_lon is not None and 
                customer_lat is not None and customer_lon is not None):
                # Calculate distance in kilometers
                distance_km = haversine_distance(store_lat, store_lon, customer_lat, customer_lon)
                
                # Gaussian transit speed from sim config (e.g., 24 km/h ± 6 km/h)
                transit_speed = self.rng.gaussian(
                    mean=self.sim_config.transit_speed_mean_kmh,
                    std=self.sim_config.transit_speed_std_kmh,
                    minimum=10.0, maximum=50.0
                )
                # Base delivery time = distance / speed (in minutes) + parking/walk time
                parking_walk_min = self.rng.gaussian(mean=6.5, std=1.0, minimum=3.0, maximum=10.0)
                base_delivery_minutes = (distance_km / transit_speed * 60.0) + parking_walk_min
                
                # Apply driver speed multiplier (0.7x = slower, 1.3x = faster)
                # Slower drivers take MORE time, so divide by speed multiplier
                base_delivery_minutes = base_delivery_minutes / driver_speed_multiplier
                
                # Apply traffic/weather multiplier (1.0x-2.1x, higher = longer delivery)
                base_delivery_minutes = base_delivery_minutes * traffic_multiplier
                
                # Gaussian variation (±10%) for realism instead of uniform
                variation = self.rng.gaussian(mean=1.0, std=0.05, minimum=0.85, maximum=1.15)
                final_delivery_minutes = base_delivery_minutes * variation
                
                # Ensure minimum delivery time of 8 minutes (even for very close deliveries)
                final_delivery_minutes = max(8, final_delivery_minutes)
                
                delivered_at = picking_completed_at + timedelta(minutes=final_delivery_minutes)
            else:
                # Fallback: Gaussian delivery time
                fallback_min = self.rng.gaussian(mean=20.0, std=5.0, minimum=10.0, maximum=35.0)
                delivered_at = picking_completed_at + timedelta(minutes=fallback_min)
        
        # Validate chronological order
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
            # Edge case: customer slightly outside zone boundaries
            # This shouldn't happen with proper filtering, but handle gracefully
            # Just use the nearest store
            stores = all_stores
        else:
            # Only consider stores in the same city
            stores = [s for s in all_stores if s[1] == customer_zone["city"]]
            if not stores:
                # No stores in customer's city yet - this shouldn't happen with proper filtering
                # Fall back to nearest store as safety measure
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
        # Weighted customer selection with dynamic reload (includes newly generated customers)
        customer_id = self._get_weighted_customer()
        
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude, is_premium, persona, city FROM customers WHERE customer_id = ?",
                (customer_id,)
            )
            row = cursor.fetchone()
            customer_lat, customer_lon, is_premium = row[0], row[1], bool(row[2])
            persona = row[3] if row[3] else "convenience_seeker"  # Default if NULL
            customer_city = row[4]
        
        store_id = self._select_store_for_customer(customer_lat, customer_lon)
        
        # Get store coordinates for distance-based delivery time calculation
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude FROM stores WHERE store_id = ?",
                (store_id,)
            )
            store_row = cursor.fetchone()
            store_lat, store_lon = store_row[0], store_row[1]
        
        store_products_raw = self._get_store_products(store_id)
        
        if not store_products_raw:
            raise ValueError(f"No products found for store {store_id}. Generate store inventory first.")
        
        # Get products with category and organic info for persona-based selection
        with get_cursor() as cursor:
            # Get enriched product info (category, is_organic)
            cursor.execute("""
                SELECT sp.store_product_id, sp.parent_product_id, sp.price, 
                       pp.category, pp.is_organic
                FROM store_products sp
                JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
                WHERE sp.store_id = ? AND sp.is_available = 1
            """, (store_id,))
            store_products_full = cursor.fetchall()
        
        # Calculate cart size based on persona
        num_items = calculate_cart_size(persona, base_size=15)
        
        # Select products using persona-based logic with bundles
        with get_cursor() as cursor:
            selected_products = select_products_for_order(
                persona=persona,
                store_products=store_products_full,
                target_items=num_items,
                customer_id=customer_id,
                db_cursor=cursor
            )
        
        if not selected_products:
            # Fallback to random if persona selection fails
            selected_products = random.sample(
                store_products_raw,
                min(num_items, len(store_products_raw))
            )
        
        order_items = []
        subtotal = 0.0
        
        # Quantity selection influenced by persona
        # Real-world: most items bought in quantity 1, bulk is rare
        bulk_persona = persona == "family_shopper"
        
        # Handle both 3-tuple and 5-tuple product formats
        for product in selected_products:
            if len(product) >= 3:
                store_product_id, parent_product_id, price = product[0], product[1], product[2]
            else:
                continue  # Skip invalid products
            if bulk_persona:
                # Family shoppers buy in slightly larger quantities
                quantity = random.choices([1, 2, 3, 4], weights=[40, 35, 18, 7])[0]
            else:
                # Most customers buy 1-2 of each item
                quantity = random.choices([1, 2, 3], weights=[70, 25, 5])[0]
            
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
        
        # Get a random driver's speed multiplier for delivery time calculation
        # (In production, driver is assigned during bundling, but we need speed for historical data)
        driver_speed_multiplier = 1.0  # Default
        if self._driver_ids:
            random_driver_id = random.choice(self._driver_ids)
            with get_cursor() as cursor:
                cursor.execute(
                    "SELECT speed_multiplier FROM drivers WHERE driver_id = ?",
                    (random_driver_id,)
                )
                driver_row = cursor.fetchone()
                if driver_row and driver_row[0] is not None:
                    driver_speed_multiplier = driver_row[0]
        
        if live_mode:
            # Live orders: created NOW with pending/confirmed status
            created_at = datetime.now()
            status = self._generate_order_status(created_at, is_historical=False)
            
            # For live orders, calculate current weather/traffic conditions
            weather_condition = generate_weather_condition(customer_city, created_at.month, rng=self.rng)
            traffic_multiplier = calculate_total_delivery_multiplier(
                customer_city, created_at, weather_condition, rng=self.rng
            )
            
            confirmed_at, picked_at, picking_completed_at, delivered_at = self._generate_timestamps(
                status, created_at, is_historical=False,
                store_lat=store_lat, store_lon=store_lon,
                customer_lat=customer_lat, customer_lon=customer_lon,
                driver_speed_multiplier=driver_speed_multiplier,
                traffic_multiplier=traffic_multiplier
            )
        else:
            # Historical orders: random past time with final statuses (80% delivered, 20% canceled)
            created_at = self._generate_order_time()
            status = self._generate_order_status(created_at, is_historical=True)
            
            # Calculate weather/traffic for historical orders (needed for delivery time and ML features)
            weather_condition = generate_weather_condition(customer_city, created_at.month, rng=self.rng)
            traffic_multiplier = calculate_total_delivery_multiplier(
                customer_city, 
                created_at,  # Use created_at for traffic calculation
                weather_condition,
                rng=self.rng
            )
            
            confirmed_at, picked_at, picking_completed_at, delivered_at = self._generate_timestamps(
                status, created_at, is_historical=True,
                store_lat=store_lat, store_lon=store_lon,
                customer_lat=customer_lat, customer_lon=customer_lon,
                driver_speed_multiplier=driver_speed_multiplier,
                traffic_multiplier=traffic_multiplier
            )
        
        tip = self._calculate_tip(subtotal, status)
        total = round(subtotal + tax + delivery_fee + tip, 2)
        
        # Calculate cancellation risk based on multiple factors
        cancellation_risk = self._calculate_cancellation_risk(
            customer_id=customer_id,
            total=total,
            is_premium=is_premium,
            traffic_multiplier=traffic_multiplier,
            db_cursor=None
        )
        
        # Temporal context
        is_peak_hour = created_at.hour in [11, 12, 17, 18, 19, 20]
        is_weekend = created_at.weekday() >= 5
        
        # Get customer order number
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE customer_id = ? AND status != 'canceled'
            """, (customer_id,))
            customer_order_number = cursor.fetchone()[0] + 1
            
            # Days since last order
            cursor.execute("""
                SELECT MAX(created_at) FROM orders 
                WHERE customer_id = ? AND order_id != ?
            """, (customer_id, order_id))
            last_order_date = cursor.fetchone()[0]
            
            if last_order_date:
                last_dt = last_order_date if isinstance(last_order_date, datetime) else datetime.fromisoformat(last_order_date)
                days_since_last = (created_at - last_dt).days
            else:
                days_since_last = None
        
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
            # ML realism fields
            weather_condition=weather_condition,
            traffic_multiplier=traffic_multiplier,
            is_peak_hour=is_peak_hour,
            is_weekend=is_weekend,
            customer_order_number=customer_order_number,
            days_since_last_order=days_since_last,
            cancellation_risk=cancellation_risk,
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
        
        # If no eligible customers (e.g., no stores exist yet), return empty
        if not self._customer_ids:
            print(f"⚠️  Skipping order generation - no eligible customers in cities with stores")
            return [], []
        
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
        simulating realistic lunch/dinner rush patterns while respecting geofencing.
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
            
            # Pick a random customer first to determine the city zone
            base_customer_id = random.choice(self._customer_ids)
            
            with get_cursor() as cursor:
                cursor.execute(
                    "SELECT city, latitude, longitude FROM customers WHERE customer_id = ?",
                    (base_customer_id,)
                )
                row = cursor.fetchone()
                cluster_city, base_cust_lat, base_cust_lon = row[0], row[1], row[2]
            
            # Select a store near the base customer (respects geofencing)
            base_store_id = self._select_store_for_customer(base_cust_lat, base_cust_lon)
            
            # Generate orders in this cluster
            for i in range(cluster_size):
                order_id = str(uuid.uuid4())
                # Weighted customer selection from same city (includes newly generated customers)
                customer_id = self._get_weighted_customer(city=cluster_city)
                
                with get_cursor() as cursor:
                    cursor.execute(
                        "SELECT latitude, longitude, is_premium FROM customers WHERE customer_id = ?",
                        (customer_id,)
                    )
                    row = cursor.fetchone()
                    customer_lat, customer_lon, is_premium = row[0], row[1], bool(row[2])
                
                # Use the cluster's store (same store for bundling, already geofenced)
                store_id = base_store_id
                store_products = self._get_store_products(store_id)
                
                if not store_products:
                    # Fallback to different store if no products
                    store_id = self._select_store_for_customer(customer_lat, customer_lon)
                    store_products = self._get_store_products(store_id)
                
                # Generate order items
                # Doubled item count: range now 1-45 with realistic distribution
                num_items = random.choices(
                    range(1, 46),
                    weights=[
                        1, 2, 3, 5, 7, 9, 11, 13, 15, 16,  # 1-10: building up
                        17, 18, 20, 22, 24, 25, 25, 24, 22, 20,  # 11-20: peak
                        18, 16, 14, 12, 10, 8, 7, 6, 5, 4,  # 21-30: declining
                        3, 3, 2, 2, 2, 1, 1, 1, 1, 1,  # 31-40: long tail
                        0.5, 0.5, 0.5, 0.5, 0.5  # 41-45: rare large orders
                    ]
                )[0]
                
                selected_products = random.sample(
                    store_products, 
                    min(num_items, len(store_products))
                )
                
                order_items = []
                subtotal = 0.0
                
                # Handle both 3-tuple and 5-tuple product formats
                for product in selected_products:
                    if len(product) >= 5:
                        store_product_id, parent_product_id, price = product[0], product[1], product[2]
                    else:
                        store_product_id, parent_product_id, price = product
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
                
                # Historical clustered orders: 80% delivered, 20% canceled (realistic final states)
                status = self._generate_order_status(created_at, is_historical=True)
                
                tip = self._calculate_tip(subtotal, status)
                total = round(subtotal + tax + delivery_fee + tip, 2)
                
                # Get store coordinates for distance-based delivery time
                with get_cursor() as cursor:
                    cursor.execute(
                        "SELECT latitude, longitude FROM stores WHERE store_id = ?",
                        (store_id,)
                    )
                    store_row = cursor.fetchone()
                    store_lat, store_lon = store_row[0], store_row[1]
                
                # Get a random driver's speed multiplier for delivery time calculation
                driver_speed_multiplier = 1.0
                if self._driver_ids:
                    random_driver_id = random.choice(self._driver_ids)
                    with get_cursor() as cursor:
                        cursor.execute(
                            "SELECT speed_multiplier FROM drivers WHERE driver_id = ?",
                            (random_driver_id,)
                        )
                        driver_row = cursor.fetchone()
                        if driver_row and driver_row[0] is not None:
                            driver_speed_multiplier = driver_row[0]
                
                # Calculate weather/traffic for historical orders (ML features + delivery time)
                weather_condition = generate_weather_condition(cluster_city, created_at.month, rng=self.rng)
                traffic_multiplier = calculate_total_delivery_multiplier(
                    cluster_city, created_at, weather_condition, rng=self.rng
                )
                
                confirmed_at, picked_at, picking_completed_at, delivered_at = self._generate_timestamps(
                    status, created_at, is_historical=True,
                    store_lat=store_lat, store_lon=store_lon,
                    customer_lat=customer_lat, customer_lon=customer_lon,
                    driver_speed_multiplier=driver_speed_multiplier,
                    traffic_multiplier=traffic_multiplier
                )
                
                # Cancellation risk
                cancellation_risk = self._calculate_cancellation_risk(
                    customer_id=customer_id, total=total,
                    is_premium=is_premium, traffic_multiplier=traffic_multiplier,
                    db_cursor=None
                )
                
                # Temporal context
                is_peak_hour = created_at.hour in [11, 12, 17, 18, 19, 20]
                is_weekend = created_at.weekday() >= 5
                
                # Customer order history
                with get_cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) FROM orders 
                        WHERE customer_id = ? AND status != 'canceled'
                    """, (customer_id,))
                    customer_order_number = cursor.fetchone()[0] + 1
                    
                    cursor.execute("""
                        SELECT MAX(created_at) FROM orders 
                        WHERE customer_id = ? AND order_id != ?
                    """, (customer_id, order_id))
                    last_order_date = cursor.fetchone()[0]
                    if last_order_date:
                        last_dt = last_order_date if isinstance(last_order_date, datetime) else datetime.fromisoformat(last_order_date)
                        days_since_last = (created_at - last_dt).days
                    else:
                        days_since_last = None
                
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
                    # ML realism fields
                    weather_condition=weather_condition,
                    traffic_multiplier=traffic_multiplier,
                    is_peak_hour=is_peak_hour,
                    is_weekend=is_weekend,
                    customer_order_number=customer_order_number,
                    days_since_last_order=days_since_last,
                    cancellation_risk=cancellation_risk,
                )
                
                orders.append(order)
                all_items.extend(order_items)
            
            remaining -= cluster_size
            
            if len(orders) % 100 == 0:
                print(f"Generated {len(orders)}/{count} orders (with clustering)...", end='\r')
        
        return orders, all_items
    
    def save_to_db(self, records: tuple[list[Order], list[OrderItem]]):
        orders, items = records
        
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO orders 
                (order_id, customer_id, store_id, status, subtotal, tax,
                 delivery_fee, tip, total, created_at, confirmed_at, picked_at,
                 picking_completed_at, delivered_at, delivery_latitude, delivery_longitude, delivery_notes,
                 weather_condition, traffic_multiplier, is_peak_hour, is_weekend,
                 customer_order_number, days_since_last_order, cancellation_risk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (o.order_id, o.customer_id, o.store_id, o.status.value,
                     o.subtotal, o.tax, o.delivery_fee, o.tip, o.total,
                     o.created_at.isoformat(),
                     o.confirmed_at.isoformat() if o.confirmed_at else None,
                     o.picked_at.isoformat() if o.picked_at else None,
                     o.picking_completed_at.isoformat() if o.picking_completed_at else None,
                     o.delivered_at.isoformat() if o.delivered_at else None,
                     o.delivery_latitude, o.delivery_longitude, o.delivery_notes,
                     o.weather_condition, o.traffic_multiplier, o.is_peak_hour, o.is_weekend,
                     o.customer_order_number, o.days_since_last_order, o.cancellation_risk)
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
        
        print(f"Saved {len(orders)} orders with ML features and {len(items)} order items")
        
        # Return list of confirmed order IDs for immediate prediction
        confirmed_order_ids = [o.order_id for o in orders if o.status == OrderStatus.CONFIRMED]
        return confirmed_order_ids
