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
        time_window_minutes: int = 30,
        max_bundle_size: int = 5,
        max_radius_km: float = 5.0,
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
                             end_time: datetime | None = None) -> list[DeliveryStop]:
        """Fetch confirmed orders ready for bundling."""
        
        query = """
            SELECT order_id, store_id, delivery_latitude, delivery_longitude, 
                   created_at, customer_id, total
            FROM orders 
            WHERE status IN ('confirmed', 'pending')
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
                    created_at=stop.created_at,
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
        
        return bundles
    
    def assign_drivers(self, bundles: list[Bundle]) -> list[Bundle]:
        """Assign available drivers to bundles based on proximity."""
        
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT driver_id, home_latitude, home_longitude, rating
                FROM drivers 
                WHERE is_active = 1
                ORDER BY rating DESC
            """)
            drivers = cursor.fetchall()
        
        if not drivers:
            return bundles
        
        available_drivers = list(drivers)
        
        for bundle in bundles:
            if not available_drivers:
                break
            
            # Find closest available driver to bundle centroid
            centroid_lat, centroid_lon = get_centroid(bundle.stops)
            
            best_driver_idx = 0
            best_dist = float('inf')
            
            for i, driver in enumerate(available_drivers):
                dist = haversine_distance(
                    centroid_lat, centroid_lon,
                    driver[1], driver[2]
                )
                if dist < best_dist:
                    best_dist = dist
                    best_driver_idx = i
            
            bundle.driver_id = available_drivers[best_driver_idx][0]
            available_drivers.pop(best_driver_idx)
        
        return bundles
    
    def save_bundles_to_db(self, bundles: list[Bundle]):
        """Save bundles and their assignments to database."""
        
        with get_cursor() as cursor:
            # Create bundles table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bundles (
                    bundle_id TEXT PRIMARY KEY,
                    driver_id TEXT,
                    order_count INTEGER,
                    total_value REAL,
                    total_distance_km REAL,
                    estimated_duration_min REAL,
                    created_at TIMESTAMP,
                    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bundle_stops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bundle_id TEXT,
                    order_id TEXT,
                    stop_sequence INTEGER,
                    FOREIGN KEY (bundle_id) REFERENCES bundles(bundle_id),
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """)
            
            # Insert bundles
            for bundle in bundles:
                cursor.execute("""
                    INSERT INTO bundles 
                    (bundle_id, driver_id, order_count, total_value,
                     total_distance_km, estimated_duration_min, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    bundle.bundle_id,
                    bundle.driver_id,
                    bundle.order_count,
                    bundle.total_value,
                    bundle.total_distance_km,
                    bundle.estimated_duration_min,
                    bundle.created_at.isoformat(),
                ))
                
                # Insert stops with sequence
                for seq, stop in enumerate(bundle.stops):
                    cursor.execute("""
                        INSERT INTO bundle_stops (bundle_id, order_id, stop_sequence)
                        VALUES (?, ?, ?)
                    """, (bundle.bundle_id, stop.order_id, seq))
        
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
    """Run bundling on historical orders and print analysis."""
    
    print("\n🚚 Running Bundle Analysis...")
    print("=" * 50)
    
    service = BundlingService(
        time_window_minutes=30,
        max_bundle_size=5,
        max_radius_km=5.0,
    )
    
    # Get historical delivered orders
    orders = service.fetch_all_delivered_orders()
    print(f"\nFound {len(orders)} delivered orders")
    
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
