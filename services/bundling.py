"""
Order Bundling Service

Groups orders into delivery bundles based on:
1. Time windows (orders placed within configurable window)
2. Geographic proximity (using simple distance-based clustering)
3. Driver capacity constraints

This is a simplified implementation suitable for ML feature engineering
and experimentation. Production systems would use more sophisticated
routing algorithms (e.g., OR-Tools, VROOM).
"""

import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from db import get_cursor
import uuid


@dataclass
class DeliveryStop:
    order_id: str
    store_id: str
    latitude: float
    longitude: float
    created_at: datetime
    customer_id: str
    total: float


@dataclass 
class Bundle:
    bundle_id: str
    driver_id: str | None
    stops: list[DeliveryStop] = field(default_factory=list)
    total_distance_km: float = 0.0
    estimated_duration_min: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    
    @property
    def order_count(self) -> int:
        return len(self.stops)
    
    @property
    def total_value(self) -> float:
        return sum(s.total for s in self.stops)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers.
    Uses Haversine formula for accuracy on Earth's surface.
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def get_centroid(stops: list[DeliveryStop]) -> tuple[float, float]:
    """Calculate geographic centroid of delivery stops."""
    if not stops:
        return (0.0, 0.0)
    avg_lat = sum(s.latitude for s in stops) / len(stops)
    avg_lon = sum(s.longitude for s in stops) / len(stops)
    return (avg_lat, avg_lon)


def calculate_route_distance(stops: list[DeliveryStop], 
                             start_lat: float, 
                             start_lon: float) -> float:
    """
    Calculate total route distance using nearest-neighbor heuristic.
    Returns distance in kilometers.
    """
    if not stops:
        return 0.0
    
    remaining = stops.copy()
    total_distance = 0.0
    current_lat, current_lon = start_lat, start_lon
    
    while remaining:
        # Find nearest stop
        nearest_idx = 0
        nearest_dist = float('inf')
        
        for i, stop in enumerate(remaining):
            dist = haversine_distance(current_lat, current_lon, 
                                      stop.latitude, stop.longitude)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i
        
        total_distance += nearest_dist
        current_lat = remaining[nearest_idx].latitude
        current_lon = remaining[nearest_idx].longitude
        remaining.pop(nearest_idx)
    
    return total_distance


def optimize_stop_order(stops: list[DeliveryStop],
                        start_lat: float,
                        start_lon: float) -> list[DeliveryStop]:
    """
    Reorder stops using nearest-neighbor heuristic.
    Simple but effective for small bundles.
    """
    if len(stops) <= 1:
        return stops
    
    remaining = stops.copy()
    ordered = []
    current_lat, current_lon = start_lat, start_lon
    
    while remaining:
        nearest_idx = 0
        nearest_dist = float('inf')
        
        for i, stop in enumerate(remaining):
            dist = haversine_distance(current_lat, current_lon,
                                      stop.latitude, stop.longitude)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i
        
        next_stop = remaining.pop(nearest_idx)
        ordered.append(next_stop)
        current_lat = next_stop.latitude
        current_lon = next_stop.longitude
    
    return ordered


class BundlingService:
    """
    Groups orders into efficient delivery bundles.
    
    Parameters:
    -----------
    time_window_minutes : int
        Maximum time span for orders in a single bundle (default: 30)
    max_bundle_size : int
        Maximum orders per bundle (default: 5)
    max_radius_km : float
        Maximum distance from centroid for orders in bundle (default: 5.0)
    avg_speed_kmh : float
        Assumed average delivery speed for time estimates (default: 25)
    stop_time_minutes : float
        Time spent at each delivery stop (default: 5)
    """
    
    def __init__(
        self,
        time_window_minutes: int = 45,  # Reasonable bundling window
        max_bundle_size: int = 6,  # Realistic bundle size
        max_radius_km: float = 5.0,  # Tighter radius for city delivery
        avg_speed_kmh: float = 25.0,
        stop_time_minutes: float = 5.0,
    ):
        self.time_window_minutes = time_window_minutes
        self.max_bundle_size = max_bundle_size
        self.max_radius_km = max_radius_km
        self.avg_speed_kmh = avg_speed_kmh
        self.stop_time_minutes = stop_time_minutes
    
    def _get_store_location(self, store_id: str) -> tuple[float, float]:
        """Get store lat/lon from database."""
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude FROM stores WHERE store_id = ?",
                (store_id,)
            )
            row = cursor.fetchone()
            if row:
                return (row[0], row[1])
        # Fallback to SF center if store not found
        return (37.7749, -122.4194)
    
    def fetch_pending_orders(self, 
                             start_time: datetime | None = None,
                             end_time: datetime | None = None,
                             include_delivered: bool = False) -> list[DeliveryStop]:
        """Fetch orders ready for bundling.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
            include_delivered: If True, includes all order statuses for historical analysis.
                             If False (default), only fetches pending/confirmed orders.
                             
        Returns:
            List of DeliveryStop objects ready for bundling
            
        Note:
            For LIVE API usage, always use default (include_delivered=False) to avoid
            re-bundling already completed or canceled orders. Only set to True for
            historical/offline analysis of past deliveries.
        """
        
        if include_delivered:
            # For historical analysis, bundle all non-canceled orders
            status_clause = "status IN ('confirmed', 'pending', 'picking', 'out_for_delivery', 'delivered')"
        else:
            # For live bundling, only process pending/confirmed orders (excludes delivered/canceled)
            status_clause = "status IN ('confirmed', 'pending')"
        
        query = f"""
            SELECT order_id, store_id, delivery_latitude, delivery_longitude, 
                   created_at, customer_id, total
            FROM orders 
            WHERE {status_clause}
        """
        params = []
        
        if start_time:
            query += " AND created_at >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND created_at <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY created_at"
        
        with get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        return [
            DeliveryStop(
                order_id=row[0],
                store_id=row[1],
                latitude=row[2],
                longitude=row[3],
                created_at=datetime.fromisoformat(row[4]),
                customer_id=row[5],
                total=row[6],
            )
            for row in rows
        ]
    
    def fetch_all_delivered_orders(self) -> list[DeliveryStop]:
        """Fetch all delivered orders for historical bundling analysis."""
        
        query = """
            SELECT order_id, store_id, delivery_latitude, delivery_longitude,
                   created_at, customer_id, total
            FROM orders
            WHERE status = 'delivered'
            ORDER BY created_at
        """
        
        with get_cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
        
        return [
            DeliveryStop(
                order_id=row[0],
                store_id=row[1],
                latitude=row[2],
                longitude=row[3],
                created_at=datetime.fromisoformat(row[4]),
                customer_id=row[5],
                total=row[6],
            )
            for row in rows
        ]
    
    def _can_add_to_bundle(self, bundle: Bundle, stop: DeliveryStop) -> bool:
        """Check if a stop can be added to existing bundle."""
        
        # Check bundle size
        if bundle.order_count >= self.max_bundle_size:
            return False
        
        # Check same store (orders must be from same store to bundle)
        if bundle.stops:
            if bundle.stops[0].store_id != stop.store_id:
                return False
        
        # Check time window
        if bundle.stops:
            earliest = min(s.created_at for s in bundle.stops)
            latest = max(s.created_at for s in bundle.stops)
            window_start = earliest - timedelta(minutes=self.time_window_minutes)
            window_end = latest + timedelta(minutes=self.time_window_minutes)
            
            if not (window_start <= stop.created_at <= window_end):
                return False
        
        # Check geographic proximity
        if bundle.stops:
            centroid_lat, centroid_lon = get_centroid(bundle.stops)
            distance = haversine_distance(
                centroid_lat, centroid_lon,
                stop.latitude, stop.longitude
            )
            if distance > self.max_radius_km:
                return False
        
        return True
    
    def _estimate_duration(self, bundle: Bundle) -> float:
        """Estimate total delivery time in minutes."""
        if not bundle.stops:
            return 0.0
        
        # Time to drive the route
        drive_time = (bundle.total_distance_km / self.avg_speed_kmh) * 60
        
        # Time at each stop
        stop_time = len(bundle.stops) * self.stop_time_minutes
        
        return drive_time + stop_time
    
    def create_bundles(self, stops: list[DeliveryStop]) -> list[Bundle]:
        """
        Group stops into delivery bundles using greedy geographic clustering.
        
        Algorithm:
        1. Sort stops by time
        2. For each stop, try to add to existing bundle (same store only)
        3. If no compatible bundle, create new one
        4. Optimize stop order within each bundle using store as origin
        """
        
        if not stops:
            return []
        
        # Sort by creation time
        sorted_stops = sorted(stops, key=lambda s: s.created_at)
        
        bundles: list[Bundle] = []
        
        for stop in sorted_stops:
            added = False
            
            # Try to add to existing bundle (prefer closest centroid, same store)
            compatible_bundles = [
                (i, b) for i, b in enumerate(bundles)
                if self._can_add_to_bundle(b, stop)
            ]
            
            if compatible_bundles:
                # Find bundle with closest centroid
                best_idx = None
                best_dist = float('inf')
                
                for idx, bundle in compatible_bundles:
                    centroid_lat, centroid_lon = get_centroid(bundle.stops)
                    dist = haversine_distance(
                        centroid_lat, centroid_lon,
                        stop.latitude, stop.longitude
                    )
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = idx
                
                if best_idx is not None:
                    bundles[best_idx].stops.append(stop)
                    added = True
            
            # Create new bundle if needed
            if not added:
                new_bundle = Bundle(
                    bundle_id=str(uuid.uuid4()),
                    driver_id=None,
                    stops=[stop],
                    created_at=datetime.now(),  # Will be updated after all stops added
                )
                bundles.append(new_bundle)
        
        # Optimize each bundle using store location as origin
        for bundle in bundles:
            if bundle.stops:
                # Get store location for this bundle
                store_lat, store_lon = self._get_store_location(bundle.stops[0].store_id)
                
                # Reorder stops for efficiency
                bundle.stops = optimize_stop_order(
                    bundle.stops, 
                    store_lat, 
                    store_lon
                )
                
                # Calculate route metrics from store
                bundle.total_distance_km = calculate_route_distance(
                    bundle.stops,
                    store_lat,
                    store_lon
                )
                bundle.estimated_duration_min = self._estimate_duration(bundle)
                
                # Calculate and set centroid
                bundle.centroid_lat, bundle.centroid_lon = get_centroid(bundle.stops)
                
                # Set bundle created_at to be after the latest order in the bundle
                latest_order_time = max(stop.created_at for stop in bundle.stops)
                # Add 1-5 minutes after the latest order before bundling happens
                from datetime import timedelta
                import random
                bundle.created_at = latest_order_time + timedelta(minutes=random.randint(1, 5))
        
        return bundles
    
    def assign_drivers(self, bundles: list[Bundle]) -> list[Bundle]:
        """Assign available drivers to bundles based on proximity within the same city.
        
        Only assigns drivers who are not currently on a delivery.
        Enforces same-city constraint: drivers are only assigned to bundles in their city.
        """
        from generators.geofence import get_zone_for_coordinates
        
        with get_cursor() as cursor:
            # Get drivers who are NOT currently on active deliveries
            cursor.execute("""
                SELECT DISTINCT d.driver_id, d.home_latitude, d.home_longitude, d.rating
                FROM drivers d
                WHERE d.is_active = 1
                AND d.driver_id NOT IN (
                    SELECT DISTINCT b.driver_id
                    FROM bundles b
                    JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
                    JOIN orders o ON bs.order_id = o.order_id
                    WHERE b.driver_id IS NOT NULL
                    AND o.status IN ('picking', 'out_for_delivery')
                )
                ORDER BY d.rating DESC
            """)
            available_drivers = cursor.fetchall()
        
        if not available_drivers:
            print("Warning: No available drivers found. Using all active drivers.")
            # Fallback to all active drivers if none are available
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT driver_id, home_latitude, home_longitude, rating
                    FROM drivers 
                    WHERE is_active = 1
                    ORDER BY rating DESC
                """)
                available_drivers = cursor.fetchall()
        
        if not available_drivers:
            print("Warning: No drivers in system. Bundles created without driver assignment.")
            return bundles
        
        # Assign drivers to bundles (city-aware)
        for i, bundle in enumerate(bundles):
            # Find closest available driver to bundle centroid IN THE SAME CITY
            centroid_lat, centroid_lon = get_centroid(bundle.stops)
            bundle_zone = get_zone_for_coordinates(centroid_lat, centroid_lon)
            
            if bundle_zone is None:
                print(f"Warning: Bundle {bundle.bundle_id} outside all zones")
                continue
            
            # Filter drivers to same city as bundle
            same_city_drivers = []
            for idx, driver in enumerate(available_drivers):
                driver_zone = get_zone_for_coordinates(driver[1], driver[2])
                if driver_zone and driver_zone["city"] == bundle_zone["city"]:
                    same_city_drivers.append((idx, driver))
            
            if not same_city_drivers:
                print(f"Warning: No drivers in {bundle_zone['city']} for bundle {bundle.bundle_id[:8]}")
                # Fallback to nearest driver overall
                same_city_drivers = [(idx, driver) for idx, driver in enumerate(available_drivers)]
            
            # Find closest driver among same-city drivers
            best_driver_idx = None
            best_dist = float('inf')
            
            for idx, driver in same_city_drivers:
                dist = haversine_distance(
                    centroid_lat, centroid_lon,
                    driver[1], driver[2]
                )
                if dist < best_dist:
                    best_dist = dist
                    best_driver_idx = idx
            
            if best_driver_idx is not None:
                bundle.driver_id = available_drivers[best_driver_idx][0]
            # Don't remove driver from list - allow reuse if needed
        
        return bundles
    
    def save_bundles_to_db(self, bundles: list[Bundle]):
        """Save bundles and their assignments to database."""
        
        with get_cursor() as cursor:
            # Insert bundles
            for bundle in bundles:
                cursor.execute("""
                    INSERT INTO bundles 
                    (bundle_id, driver_id, order_count, total_value,
                     total_distance_km, estimated_duration_min, created_at, status,
                     centroid_latitude, centroid_longitude)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bundle.bundle_id,
                    bundle.driver_id,
                    bundle.order_count,
                    bundle.total_value,
                    bundle.total_distance_km,
                    bundle.estimated_duration_min,
                    bundle.created_at.isoformat(),
                    'pending',  # Initial status
                    bundle.centroid_lat,
                    bundle.centroid_lon,
                ))
                
                # Insert stops with sequence
                for seq, stop in enumerate(bundle.stops):
                    stop_id = str(uuid.uuid4())  # Generate unique ID for each stop
                    cursor.execute("""
                        INSERT INTO bundle_stops (id, bundle_id, order_id, stop_sequence)
                        VALUES (?, ?, ?, ?)
                    """, (stop_id, bundle.bundle_id, stop.order_id, seq))
        
        print(f"Saved {len(bundles)} bundles to database")
    
    def get_bundle_stats(self, bundles: list[Bundle]) -> dict:
        """Calculate summary statistics for bundles."""
        
        if not bundles:
            return {}
        
        order_counts = [b.order_count for b in bundles]
        distances = [b.total_distance_km for b in bundles]
        durations = [b.estimated_duration_min for b in bundles]
        values = [b.total_value for b in bundles]
        
        return {
            "total_bundles": len(bundles),
            "total_orders": sum(order_counts),
            "avg_orders_per_bundle": sum(order_counts) / len(bundles),
            "single_order_bundles": sum(1 for c in order_counts if c == 1),
            "multi_order_bundles": sum(1 for c in order_counts if c > 1),
            "avg_distance_km": sum(distances) / len(distances),
            "total_distance_km": sum(distances),
            "avg_duration_min": sum(durations) / len(durations),
            "avg_bundle_value": sum(values) / len(values),
            "total_value": sum(values),
        }


def run_bundling_analysis():
    """Run bundling analysis on historical orders and print statistics.
    
    Note: This is for OFFLINE analysis only. It includes all order statuses
    (pending, confirmed, picking, out_for_delivery, delivered) to calculate
    bundle metrics for past deliveries. 
    
    The live API should NOT use this - it uses fetch_pending_orders() with
    default parameters to only bundle new pending/confirmed orders.
    """
    
    print("\n🚚 Running Bundle Analysis...")
    print("=" * 50)
    
    service = BundlingService(
        time_window_minutes=45,
        max_bundle_size=6,
        max_radius_km=5.0,
    )
    
    # Get all orders (including delivered) for historical bundling analysis
    # WARNING: Do NOT use include_delivered=True in live API - only for offline analysis
    orders = service.fetch_pending_orders(include_delivered=True)
    print(f"\nFound {len(orders)} orders for bundling analysis")
    
    if not orders:
        print("No orders to bundle.")
        return
    
    # Create bundles
    bundles = service.create_bundles(orders)
    
    # Assign drivers
    bundles = service.assign_drivers(bundles)
    
    # Save to database
    service.save_bundles_to_db(bundles)
    
    # Get stats
    stats = service.get_bundle_stats(bundles)
    
    print(f"\n📊 Bundling Results:")
    print("-" * 50)
    print(f"   Total bundles created:     {stats['total_bundles']:,}")
    print(f"   Total orders bundled:      {stats['total_orders']:,}")
    print(f"   Avg orders per bundle:     {stats['avg_orders_per_bundle']:.2f}")
    print(f"   Single-order bundles:      {stats['single_order_bundles']:,}")
    print(f"   Multi-order bundles:       {stats['multi_order_bundles']:,}")
    print("-" * 50)
    print(f"   Avg distance per bundle:   {stats['avg_distance_km']:.2f} km")
    print(f"   Total distance:            {stats['total_distance_km']:.2f} km")
    print(f"   Avg duration per bundle:   {stats['avg_duration_min']:.1f} min")
    print("-" * 50)
    print(f"   Avg bundle value:          ${stats['avg_bundle_value']:.2f}")
    print(f"   Total value:               ${stats['total_value']:,.2f}")
    
    # Show sample bundles
    print(f"\n📦 Sample Bundles (first 3):")
    for i, bundle in enumerate(bundles[:3]):
        print(f"\n   Bundle {i+1}: {bundle.bundle_id[:8]}...")
        print(f"      Orders: {bundle.order_count}")
        print(f"      Distance: {bundle.total_distance_km:.2f} km")
        print(f"      Duration: {bundle.estimated_duration_min:.1f} min")
        print(f"      Value: ${bundle.total_value:.2f}")
        print(f"      Driver: {bundle.driver_id[:8] if bundle.driver_id else 'Unassigned'}...")


if __name__ == "__main__":
    run_bundling_analysis()
