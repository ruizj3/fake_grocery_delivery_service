import uuid
import random
import math
from datetime import datetime, timedelta
from .base import BaseGenerator
from .geofence import get_all_zones, get_zone_weights
from models import Customer
from db import get_cursor


class CustomerGenerator(BaseGenerator):
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        # Use geofenced delivery zones
        self.delivery_zones = get_all_zones()
    
    def generate_one(self) -> Customer:
        # Select zone based on weights
        zone = random.choices(self.delivery_zones, weights=get_zone_weights())[0]
        
        # Generate random point within zone's radius (using polar coordinates for uniform distribution)
        # This ensures customers are evenly distributed within the circular geofence
        r = zone["radius_km"] * math.sqrt(random.random())  # sqrt for uniform distribution
        theta = random.uniform(0, 2 * math.pi)
        
        # Convert to lat/lon offset (approximate for small distances)
        lat_offset = (r * math.cos(theta)) / 111.0  # 1 degree lat ≈ 111 km
        lon_offset = (r * math.sin(theta)) / (111.0 * math.cos(math.radians(zone["lat"])))
        
        lat = zone["lat"] + lat_offset
        lon = zone["lon"] + lon_offset
        
        # Random signup date within last 2 years
        days_ago = random.randint(0, 730)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        return Customer(
            customer_id=str(uuid.uuid4()),
            first_name=self.fake.first_name(),
            last_name=self.fake.last_name(),
            email=self.fake.unique.email(),
            phone=self.fake.phone_number(),
            address=self.fake.street_address(),
            city=zone["city"],
            state=zone["state"],
            zip_code=self.fake.zipcode_in_state(zone["state"]),
            latitude=lat,
            longitude=lon,
            created_at=created_at,
            is_premium=random.random() < 0.15,  # 15% premium rate
        )
    
    def generate_batch(self, count: int) -> list[Customer]:
        return [self.generate_one() for _ in range(count)]
    
    def save_to_db(self, records: list[Customer]):
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO customers 
                (customer_id, first_name, last_name, email, phone, address, 
                 city, state, zip_code, latitude, longitude, created_at, is_premium)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (c.customer_id, c.first_name, c.last_name, c.email, c.phone,
                     c.address, c.city, c.state, c.zip_code, c.latitude, c.longitude,
                     c.created_at.isoformat(), c.is_premium)
                    for c in records
                ]
            )
        print(f"Saved {len(records)} customers")
    
    def get_all_ids(self) -> list[str]:
        with get_cursor() as cursor:
            cursor.execute("SELECT customer_id FROM customers")
            return [row[0] for row in cursor.fetchall()]
