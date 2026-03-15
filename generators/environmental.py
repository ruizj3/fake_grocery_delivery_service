"""
Traffic Patterns and Environmental Factors

Defines traffic multipliers, weather conditions, and other environmental factors
that affect delivery times and order patterns.

Noise is modeled using Gaussian distributions (via SimulationRNG) for realistic
jitter that clusters around the mean rather than uniform noise.
"""

import random
from datetime import datetime
from typing import Dict, Tuple, Optional

from simulation.rng import SimulationRNG


# Traffic patterns by city and time of day (hour)
# Multiplier applied to base delivery time
TRAFFIC_PATTERNS = {
    # New York - Heavy traffic patterns
    ("New York", "weekday"): {
        range(7, 10): 1.8,    # Morning rush
        range(10, 16): 1.3,   # Midday moderate
        range(16, 20): 2.0,   # Evening rush (worst)
        range(20, 23): 1.4,   # Late evening
        range(23, 24): 1.0,   # Late night
        range(0, 7): 0.9,     # Early morning
    },
    ("New York", "weekend"): {
        range(10, 14): 1.4,   # Weekend brunch/lunch
        range(14, 20): 1.3,   # Afternoon/evening
        range(20, 24): 1.2,   # Night
        range(0, 10): 0.95,   # Morning
    },
    
    # Seattle - Moderate traffic
    ("Seattle", "weekday"): {
        range(7, 9): 1.5,     # Morning rush
        range(9, 16): 1.2,    # Midday
        range(16, 19): 1.7,   # Evening rush
        range(19, 24): 1.1,   # Evening
        range(0, 7): 0.9,     # Early morning
    },
    ("Seattle", "weekend"): {
        range(10, 18): 1.3,   # Daytime
        range(18, 24): 1.1,   # Evening
        range(0, 10): 0.95,   # Morning
    },
    
    # San Francisco - Heavy traffic
    ("San Francisco", "weekday"): {
        range(7, 10): 1.9,    # Morning rush (hills + traffic)
        range(10, 16): 1.4,   # Midday
        range(16, 20): 2.1,   # Evening rush
        range(20, 24): 1.3,   # Evening
        range(0, 7): 0.9,     # Early morning
    },
    ("San Francisco", "weekend"): {
        range(9, 19): 1.5,    # Busy all day (tourism)
        range(19, 24): 1.2,   # Evening
        range(0, 9): 0.95,    # Morning
    },
    
    # Dallas - Car-centric, moderate traffic
    ("Dallas", "weekday"): {
        range(7, 9): 1.6,     # Morning commute
        range(9, 16): 1.2,    # Midday
        range(16, 19): 1.8,   # Evening rush
        range(19, 24): 1.1,   # Evening
        range(0, 7): 0.85,    # Early morning (spread out city)
    },
    ("Dallas", "weekend"): {
        range(10, 18): 1.2,   # Daytime
        range(18, 24): 1.0,   # Evening
        range(0, 10): 0.9,    # Morning
    },
    
    # Cincinnati - Light traffic
    ("Cincinnati", "weekday"): {
        range(7, 9): 1.3,     # Morning rush
        range(9, 16): 1.1,    # Midday
        range(16, 19): 1.5,   # Evening rush
        range(19, 24): 1.0,   # Evening
        range(0, 7): 0.85,    # Early morning
    },
    ("Cincinnati", "weekend"): {
        range(10, 18): 1.1,   # Daytime
        range(18, 24): 1.0,   # Evening
        range(0, 10): 0.9,    # Morning
    },
    
    # San Jose - Tech hub traffic
    ("San Jose", "weekday"): {
        range(7, 10): 1.7,    # Morning tech commute
        range(10, 16): 1.3,   # Midday
        range(16, 19): 1.9,   # Evening rush
        range(19, 24): 1.2,   # Evening
        range(0, 7): 0.9,     # Early morning
    },
    ("San Jose", "weekend"): {
        range(10, 18): 1.2,   # Daytime
        range(18, 24): 1.1,   # Evening
        range(0, 10): 0.95,   # Morning
    },
}


# Weather conditions and their impact on delivery time
WEATHER_CONDITIONS = {
    "clear": {
        "weight": 0.65,
        "delivery_multiplier": 1.0,
        "order_boost": 1.0,  # No change in order volume
    },
    "cloudy": {
        "weight": 0.15,
        "delivery_multiplier": 1.0,
        "order_boost": 1.0,
    },
    "rain": {
        "weight": 0.15,
        "delivery_multiplier": 1.25,
        "order_boost": 1.15,  # 15% more orders when raining
    },
    "heavy_rain": {
        "weight": 0.03,
        "delivery_multiplier": 1.5,
        "order_boost": 1.25,
    },
    "snow": {
        "weight": 0.015,  # Varies by city/season
        "delivery_multiplier": 1.8,
        "order_boost": 1.3,
    },
    "storm": {
        "weight": 0.005,
        "delivery_multiplier": 2.0,
        "order_boost": 1.4,
    },
}


# City-specific weather adjustments (some cities have more rain/snow)
CITY_WEATHER_ADJUSTMENTS = {
    "Seattle": {
        "rain": 1.8,          # Seattle has more rain
        "heavy_rain": 1.5,
        "snow": 0.3,          # Less snow
    },
    "San Francisco": {
        "rain": 0.8,          # Less rain
        "snow": 0.1,          # Rare snow
    },
    "New York": {
        "snow": 2.0,          # More snow in winter
        "heavy_rain": 1.2,
    },
    "Dallas": {
        "snow": 0.2,          # Rare snow
        "rain": 0.9,
    },
    "Cincinnati": {
        "snow": 1.5,          # Moderate snow
        "rain": 1.0,
    },
    "San Jose": {
        "rain": 0.7,          # Less rain
        "snow": 0.05,         # Very rare snow
    },
}


def get_traffic_multiplier(city: str, dt: datetime, rng: Optional[SimulationRNG] = None) -> float:
    """
    Get traffic multiplier for a given city and datetime.
    
    Uses Gaussian noise (mean=1.0, std=0.05) for realistic jitter that
    clusters around the base multiplier rather than uniform spread.
    
    Args:
        city: City name
        dt: DateTime of the order/delivery
        rng: Optional seeded RNG for deterministic noise. Falls back to stdlib random.
    
    Returns:
        Traffic multiplier (1.0 = normal, >1.0 = slower)
    """
    hour = dt.hour
    is_weekend = dt.weekday() >= 5
    day_type = "weekend" if is_weekend else "weekday"
    
    # Get traffic pattern for city and day type
    pattern_key = (city, day_type)
    if pattern_key not in TRAFFIC_PATTERNS:
        # Default pattern if city not found
        return 1.0
    
    pattern = TRAFFIC_PATTERNS[pattern_key]
    
    # Find matching hour range
    for hour_range, multiplier in pattern.items():
        if hour in hour_range:
            # Gaussian noise: clusters around multiplier with ±5% std deviation
            if rng:
                noise = rng.gaussian(mean=1.0, std=0.05, minimum=0.85, maximum=1.15)
            else:
                noise = random.uniform(0.9, 1.1)
            return multiplier * noise
    
    return 1.0


def generate_weather_condition(city: str, month: int = None, rng: Optional[SimulationRNG] = None) -> str:
    """
    Generate a random weather condition for a city.
    
    Args:
        city: City name
        month: Month (1-12), used for seasonal adjustments
        rng: Optional seeded RNG for deterministic selection.
    
    Returns:
        Weather condition name
    """
    # Base weather weights
    conditions = list(WEATHER_CONDITIONS.keys())
    weights = [WEATHER_CONDITIONS[c]["weight"] for c in conditions]
    
    # Adjust for city
    if city in CITY_WEATHER_ADJUSTMENTS:
        adjustments = CITY_WEATHER_ADJUSTMENTS[city]
        adjusted_weights = []
        for i, condition in enumerate(conditions):
            adjustment = adjustments.get(condition, 1.0)
            adjusted_weights.append(weights[i] * adjustment)
        weights = adjusted_weights
    
    # Seasonal adjustments (more snow in winter, etc.)
    if month is not None:
        # Winter months (Dec, Jan, Feb)
        if month in [12, 1, 2]:
            snow_idx = conditions.index("snow")
            weights[snow_idx] *= 3.0
        # Summer months (Jun, Jul, Aug)
        elif month in [6, 7, 8]:
            snow_idx = conditions.index("snow")
            weights[snow_idx] *= 0.1
    
    # Normalize weights
    total = sum(weights)
    weights = [w / total for w in weights]
    
    if rng:
        return rng.choice(conditions, weights=weights)
    return random.choices(conditions, weights=weights)[0]


def get_weather_multiplier(weather: str, rng: Optional[SimulationRNG] = None) -> float:
    """
    Get delivery time multiplier for weather condition.
    
    Uses Gaussian noise for realistic jitter around base multiplier.
    
    Args:
        weather: Weather condition name
        rng: Optional seeded RNG for deterministic noise.
    
    Returns:
        Delivery time multiplier
    """
    if weather not in WEATHER_CONDITIONS:
        return 1.0
    
    base_multiplier = WEATHER_CONDITIONS[weather]["delivery_multiplier"]
    # Gaussian noise: clusters around base with ±7% std deviation
    if rng:
        noise = rng.gaussian(mean=1.0, std=0.07, minimum=0.8, maximum=1.2)
    else:
        noise = random.uniform(0.85, 1.15)
    return base_multiplier * noise


def get_weather_order_boost(weather: str) -> float:
    """
    Get order volume boost for weather condition.
    Bad weather typically increases delivery orders.
    
    Args:
        weather: Weather condition name
    
    Returns:
        Order volume multiplier
    """
    if weather not in WEATHER_CONDITIONS:
        return 1.0
    
    return WEATHER_CONDITIONS[weather]["order_boost"]


def calculate_total_delivery_multiplier(city: str, dt: datetime, weather: str = None, 
                                         rng: Optional[SimulationRNG] = None) -> float:
    """
    Calculate combined delivery time multiplier from traffic and weather.
    
    Args:
        city: City name
        dt: DateTime of delivery
        weather: Weather condition (if None, generates random)
        rng: Optional seeded RNG for deterministic noise.
    
    Returns:
        Combined multiplier
    """
    traffic_mult = get_traffic_multiplier(city, dt, rng=rng)
    
    if weather is None:
        weather = generate_weather_condition(city, dt.month, rng=rng)
    
    weather_mult = get_weather_multiplier(weather, rng=rng)
    
    # Combine multiplicatively (traffic and weather compound)
    return traffic_mult * weather_mult
