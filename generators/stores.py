import uuid
import random
import math
from datetime import datetime, timedelta
from dataclasses import dataclass
from .base import BaseGenerator
from .geofence import get_all_zones, get_zone_weights
from db import get_cursor


@dataclass
class Store:
    store_id: str
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    opens_at: str  # "HH:MM"
    closes_at: str  # "HH:MM"
    is_active: bool
    created_at: datetime


class StoreGenerator(BaseGenerator):
    # Store name patterns
    STORE_PREFIXES = [
        "Fresh", "Green", "Quick", "Daily", "Local", "Urban", 
        "Metro", "City", "Corner", "Village", "Market", "Prime",
        "Super", "Mega", "Express", "Smart", "Value", "Choice",
    ]
    
    STORE_SUFFIXES = [
        "Market", "Grocery", "Foods", "Mart", "Shop", "Store",
        "Provisions", "Pantry", "Basket", "Cart", "Goods", "Fare",
    ]
    
    # Delivery zones are defined in geofence.py
    
    OPERATING_HOURS = [
        ("06:00", "22:00"),  # Standard
        ("07:00", "23:00"),  # Late
        ("05:00", "21:00"),  # Early
        ("00:00", "23:59"),  # 24 hours (represented as full day)
        ("08:00", "20:00"),  # Short hours
    ]
    
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        self._used_names = set()
        self.delivery_zones = get_all_zones()
    
    def _generate_unique_name(self) -> str:
        """Generate a unique store name."""
        for _ in range(100):  # Max attempts
            prefix = random.choice(self.STORE_PREFIXES)
            suffix = random.choice(self.STORE_SUFFIXES)
            name = f"{prefix} {suffix}"
            if name not in self._used_names:
                self._used_names.add(name)
                return name
        # Fallback with number
        return f"{random.choice(self.STORE_PREFIXES)} {random.choice(self.STORE_SUFFIXES)} #{random.randint(1, 999)}"
    
    def _generate_address(self) -> str:
        """Generate a realistic street address."""
        number = random.randint(100, 9999)
        street_names = [
            "Main St", "Market St", "Broadway", "Mission St", "Valencia St",
            "Castro St", "Fillmore St", "Divisadero St", "Geary Blvd", "Clement St",
            "Irving St", "Judah St", "Taraval St", "Ocean Ave", "Geneva Ave",
            "San Pablo Ave", "Telegraph Ave", "Shattuck Ave", "College Ave", "Piedmont Ave",
            "El Camino Real", "University Ave", "California Ave", "Middlefield Rd", "Santa Cruz Ave",
        ]
        return f"{number} {random.choice(street_names)}"
    
    def generate_one(self) -> Store:
        # Select zone based on weights
        zone = random.choices(self.delivery_zones, weights=get_zone_weights())[0]
        
        # Stores are more centrally located (within 60% of zone radius)
        # Use polar coordinates for uniform distribution
        r = zone["radius_km"] * 0.6 * math.sqrt(random.random())
        theta = random.uniform(0, 2 * math.pi)
        
        # Convert to lat/lon offset
        lat_offset = (r * math.cos(theta)) / 111.0
        lon_offset = (r * math.sin(theta)) / (111.0 * math.cos(math.radians(zone["lat"])))
        
        lat = zone["lat"] + lat_offset
        lon = zone["lon"] + lon_offset
        
        # Operating hours
        opens, closes = random.choice(self.OPERATING_HOURS)
        
        # Store age (older stores more likely)
        days_ago = random.randint(30, 1825)  # 1 month to 5 years
        created_at = datetime.now() - timedelta(days=days_ago)
        
        return Store(
            store_id=str(uuid.uuid4()),
            name=self._generate_unique_name(),
            address=self._generate_address(),
            city=zone["city"],
            state=zone["state"],
            zip_code=self.fake.zipcode_in_state(zone["state"]),
            latitude=lat,
            longitude=lon,
            opens_at=opens,
            closes_at=closes,
            is_active=random.random() < 0.95,  # 95% active
            created_at=created_at,
        )
    
    def generate_batch(self, count: int) -> list[Store]:
        return [self.generate_one() for _ in range(count)]
    
    def save_to_db(self, records: list[Store]):
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO stores 
                (store_id, name, address, city, state, zip_code, 
                 latitude, longitude, opens_at, closes_at, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (s.store_id, s.name, s.address, s.city, s.state, s.zip_code,
                     s.latitude, s.longitude, s.opens_at, s.closes_at, 
                     s.is_active, s.created_at.isoformat())
                    for s in records
                ]
            )
        print(f"Saved {len(records)} stores")
    
    def get_all_ids(self) -> list[str]:
        with get_cursor() as cursor:
            cursor.execute("SELECT store_id FROM stores WHERE is_active = 1")
            return [row[0] for row in cursor.fetchall()]
    
    def get_store_location(self, store_id: str) -> tuple[float, float] | None:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT latitude, longitude FROM stores WHERE store_id = ?",
                (store_id,)
            )
            row = cursor.fetchone()
            return (row[0], row[1]) if row else None
