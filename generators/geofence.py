"""
Geofence Configuration for City-Based Delivery Zones

Defines delivery zones for 6 major US cities. Each zone ensures:
- Stores are located within city boundaries
- Customers are located within city boundaries  
- Orders only happen within the same city
- Deliveries stay within reasonable distances (3-8 km typical)
"""

import math
from typing import Optional


# City delivery zones with geofence boundaries
DELIVERY_ZONES = [
    {
        "city": "San Francisco",
        "state": "CA",
        "lat": 37.7749,
        "lon": -122.4194,
        "radius_km": 8.0,  # ~5 miles - covers most of SF proper
        "weight": 0.20,
    },
    {
        "city": "Seattle", 
        "state": "WA",
        "lat": 47.6062,
        "lon": -122.3321,
        "radius_km": 10.0,  # ~6 miles - covers downtown to neighborhoods
        "weight": 0.18,
    },
    {
        "city": "New York",
        "state": "NY", 
        "lat": 40.7128,
        "lon": -74.0060,
        "radius_km": 12.0,  # ~7.5 miles - covers Manhattan + nearby boroughs
        "weight": 0.25,
    },
    {
        "city": "Cincinnati",
        "state": "OH",
        "lat": 39.1031,
        "lon": -84.5120,
        "radius_km": 9.0,  # ~5.5 miles - covers metro area
        "weight": 0.12,
    },
    {
        "city": "Dallas",
        "state": "TX",
        "lat": 32.7767,
        "lon": -96.7970,
        "radius_km": 15.0,  # ~9 miles - Dallas is more spread out
        "weight": 0.15,
    },
    {
        "city": "San Jose",
        "state": "CA",
        "lat": 37.3382,
        "lon": -121.8863,
        "radius_km": 10.0,  # ~6 miles - covers downtown to suburbs
        "weight": 0.10,
    },
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula."""
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


def get_zone_for_coordinates(lat: float, lon: float) -> Optional[dict]:
    """
    Find which delivery zone contains the given coordinates.
    Returns None if coordinates are outside all zones.
    """
    for zone in DELIVERY_ZONES:
        distance = haversine_distance(lat, lon, zone["lat"], zone["lon"])
        if distance <= zone["radius_km"]:
            return zone
    return None


def are_in_same_zone(lat1: float, lon1: float, lat2: float, lon2: float) -> bool:
    """Check if two coordinate pairs are in the same delivery zone."""
    zone1 = get_zone_for_coordinates(lat1, lon1)
    zone2 = get_zone_for_coordinates(lat2, lon2)
    
    if zone1 is None or zone2 is None:
        return False
    
    return zone1["city"] == zone2["city"]


def get_all_zones() -> list[dict]:
    """Get list of all delivery zones."""
    return DELIVERY_ZONES.copy()


def get_zone_weights() -> list[float]:
    """Get probability weights for zone selection."""
    return [zone["weight"] for zone in DELIVERY_ZONES]
