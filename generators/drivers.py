import uuid
import random
from datetime import datetime, timedelta
from .base import BaseGenerator
from models import Driver
from db import get_cursor


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
        # Drivers spread across the same metro areas as customers
        self.metro_centers = [
            {"lat": 37.7749, "lon": -122.4194},   # SF
            {"lat": 37.8044, "lon": -122.2712},   # Oakland
            {"lat": 37.3382, "lon": -121.8863},   # San Jose
            {"lat": 37.8716, "lon": -122.2727},   # Berkeley
            {"lat": 37.4419, "lon": -122.1430},   # Palo Alto
        ]
    
    def _weighted_choice(self, choices: list[tuple]) -> str:
        items, weights = zip(*choices)
        return random.choices(items, weights=weights)[0]
    
    def _generate_license_plate(self) -> str:
        return f"{random.randint(1, 9)}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter}{random.randint(100, 999)}"
    
    def generate_one(self) -> Driver:
        metro = random.choice(self.metro_centers)
        
        # Drivers have wider spread than customers (they travel)
        lat = metro["lat"] + random.uniform(-0.1, 0.1)
        lon = metro["lon"] + random.uniform(-0.1, 0.1)
        
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
        
        return Driver(
            driver_id=str(uuid.uuid4()),
            first_name=self.fake.first_name(),
            last_name=self.fake.last_name(),
            email=self.fake.unique.email(),
            phone=self.fake.phone_number(),
            vehicle_type=self._weighted_choice(self.VEHICLE_TYPES),
            license_plate=f"{random.randint(1,9)}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{self.fake.random_uppercase_letter()}{random.randint(100,999)}",
            rating=rating,
            total_deliveries=total_deliveries,
            home_latitude=lat,
            home_longitude=lon,
            is_active=random.random() < 0.85,  # 85% active rate
            created_at=created_at,
        )
    
    def generate_batch(self, count: int) -> list[Driver]:
        return [self.generate_one() for _ in range(count)]
    
    def save_to_db(self, records: list[Driver]):
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO drivers 
                (driver_id, first_name, last_name, email, phone, vehicle_type,
                 license_plate, rating, total_deliveries, home_latitude, 
                 home_longitude, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (d.driver_id, d.first_name, d.last_name, d.email, d.phone,
                     d.vehicle_type, d.license_plate, d.rating, d.total_deliveries,
                     d.home_latitude, d.home_longitude, d.is_active, d.created_at.isoformat())
                    for d in records
                ]
            )
        print(f"Saved {len(records)} drivers")
    
    def get_active_ids(self) -> list[str]:
        with get_cursor() as cursor:
            cursor.execute("SELECT driver_id FROM drivers WHERE is_active = 1")
            return [row[0] for row in cursor.fetchall()]
