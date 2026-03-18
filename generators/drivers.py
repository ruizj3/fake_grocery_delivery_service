import uuid
import random
import math
from datetime import datetime, timedelta
from .base import BaseGenerator
from .geofence import get_all_zones, get_zone_weights
from models import Driver
from database.db import get_cursor


class DriverGenerator(BaseGenerator):
    VEHICLE_TYPES = [
        ("sedan", 0.40),
        ("suv", 0.25),
        ("hatchback", 0.20),
        ("truck", 0.10),
        ("van", 0.05),
    ]
    
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        # Drivers distributed across delivery zones
        self.delivery_zones = get_all_zones()
    
    def _weighted_choice(self, choices: list[tuple]) -> str:
        items, weights = zip(*choices)
        return random.choices(items, weights=weights)[0]
    
    def _generate_license_plate(self) -> str:
        return f"{random.randint(1, 9)}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter}{random.randint(100, 999)}"
    
    def generate_one(self) -> Driver:
        # Select zone based on weights - ENSURES driver is in one of the 6 cities
        zone = random.choices(self.delivery_zones, weights=get_zone_weights())[0]
        
        # Drivers have wider spread within zone (they travel for deliveries)
        # Use up to 80% of zone radius
        r = zone["radius_km"] * 0.8 * math.sqrt(random.random())
        theta = random.uniform(0, 2 * math.pi)
        
        # Convert to lat/lon offset
        lat_offset = (r * math.cos(theta)) / 111.0
        lon_offset = (r * math.sin(theta)) / (111.0 * math.cos(math.radians(zone["lat"])))
        
        lat = zone["lat"] + lat_offset
        lon = zone["lon"] + lon_offset
        
        # Store city and state explicitly for reliable city-based matching
        city = zone["city"]
        state = zone["state"]
        
        # Random signup date within last 3 years
        days_ago = random.randint(0, 1095)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        # Rating distribution: most drivers between 4.0 and 5.0
        # Using beta distribution skewed toward higher ratings
        rating = round(4.0 + random.betavariate(5, 2), 2)
        rating = min(5.0, max(1.0, rating))
        
        # Deliveries correlate with tenure
        max_deliveries = (1095 - days_ago) * 3  # ~3 deliveries/day max
        total_deliveries = random.randint(0, max(1, max_deliveries))
        
        # Driver performance profile (for ML realism)
        # Speed: normally distributed around 1.0 (0.7-1.3x)
        speed_multiplier = max(0.7, min(1.3, random.normalvariate(1.0, 0.15)))
        
        # Experience effect: drivers get faster over time
        experience_bonus = min(0.2, total_deliveries / 5000)  # Up to 20% faster
        speed_multiplier += experience_bonus
        
        # Reliability: highly-rated drivers are more reliable
        if rating >= 4.8:
            reliability = random.uniform(0.95, 0.99)
            experience_level = "expert"
        elif rating >= 4.5:
            reliability = random.uniform(0.90, 0.96)
            experience_level = "advanced"
        elif rating >= 4.0:
            reliability = random.uniform(0.85, 0.92)
            experience_level = "intermediate"
        else:
            reliability = random.uniform(0.75, 0.88)
            experience_level = "beginner"
        
        return Driver(
            driver_id=str(uuid.uuid4()),
            first_name=self.fake.first_name(),
            last_name=self.fake.last_name(),
            email=self.fake.email(),
            phone=self.fake.phone_number(),
            vehicle_type=self._weighted_choice(self.VEHICLE_TYPES),
            license_plate=f"{random.randint(1,9)}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{random.randint(100,999)}",
            rating=rating,
            total_deliveries=total_deliveries,
            home_latitude=lat,
            home_longitude=lon,
            city=city,
            state=state,
            is_active=random.random() < 0.85,  # 85% active rate
            created_at=created_at,
        )
    
    def generate_batch(self, count: int) -> list[Driver]:
        return [self.generate_one() for _ in range(count)]
    
    def save_to_db(self, records: list[Driver]):
        import sqlite3
        from database.db import _is_postgres
        use_savepoints = _is_postgres()
        saved_count = 0
        with get_cursor() as cursor:
            for d in records:
                email = d.email
                max_retries = 5
                
                # Calculate performance metrics
                speed_multiplier = max(0.7, min(1.3, random.normalvariate(1.0, 0.15)))
                experience_bonus = min(0.2, d.total_deliveries / 5000)
                speed_multiplier += experience_bonus
                
                if d.rating >= 4.8:
                    reliability = random.uniform(0.95, 0.99)
                    experience_level = "expert"
                elif d.rating >= 4.5:
                    reliability = random.uniform(0.90, 0.96)
                    experience_level = "advanced"
                elif d.rating >= 4.0:
                    reliability = random.uniform(0.85, 0.92)
                    experience_level = "intermediate"
                else:
                    reliability = random.uniform(0.75, 0.88)
                    experience_level = "beginner"
                
                for attempt in range(max_retries):
                    try:
                        if use_savepoints:
                            cursor.savepoint("drv_insert")
                        cursor.execute(
                            """
                            INSERT INTO drivers 
                            (driver_id, first_name, last_name, email, phone, vehicle_type,
                             license_plate, rating, total_deliveries, home_latitude, 
                             home_longitude, city, state, is_active, created_at,
                             speed_multiplier, reliability_score, experience_level)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (d.driver_id, d.first_name, d.last_name, email, d.phone,
                             d.vehicle_type, d.license_plate, d.rating, d.total_deliveries,
                             d.home_latitude, d.home_longitude, d.city, d.state, d.is_active, d.created_at.isoformat(),
                             speed_multiplier, reliability, experience_level)
                        )
                        if use_savepoints:
                            cursor.release_savepoint("drv_insert")
                        saved_count += 1
                        break
                    except (sqlite3.IntegrityError, Exception) as e:
                        if "IntegrityError" in type(e).__name__ or "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                            if use_savepoints:
                                cursor.rollback_to("drv_insert")
                            # Email conflict - append random suffix
                            email = f"{d.email.split('@')[0]}{random.randint(1,9999)}@{d.email.split('@')[1]}"
                        else:
                            raise
        print(f"Saved {saved_count} drivers with performance profiles")
    
    def get_active_ids(self) -> list[str]:
        with get_cursor() as cursor:
            cursor.execute("SELECT driver_id FROM drivers WHERE is_active = 1")
            return [row[0] for row in cursor.fetchall()]
