import uuid
import random
from datetime import datetime, timedelta
from .base import BaseGenerator
from models import Customer
from db import get_cursor


class CustomerGenerator(BaseGenerator):
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        # Simulate customers clustered around a few metro areas
        self.metro_centers = [
            {"city": "San Francisco", "state": "CA", "lat": 37.7749, "lon": -122.4194},
            {"city": "Oakland", "state": "CA", "lat": 37.8044, "lon": -122.2712},
            {"city": "San Jose", "state": "CA", "lat": 37.3382, "lon": -121.8863},
            {"city": "Berkeley", "state": "CA", "lat": 37.8716, "lon": -122.2727},
            {"city": "Palo Alto", "state": "CA", "lat": 37.4419, "lon": -122.1430},
        ]
    
    def generate_one(self) -> Customer:
        metro = random.choice(self.metro_centers)
        
        # Add some variance to location within metro area
        lat = metro["lat"] + random.uniform(-0.05, 0.05)
        lon = metro["lon"] + random.uniform(-0.05, 0.05)
        
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
            city=metro["city"],
            state=metro["state"],
            zip_code=self.fake.zipcode_in_state(metro["state"]),
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
