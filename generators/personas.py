"""
Customer Persona Configurations

Defines shopping behavior patterns for different customer segments.
Each persona affects product selection, order frequency, cart sizes, and timing preferences.
"""

import random
from typing import Dict, List
from models import ProductCategory


# Customer persona definitions with probabilistic behaviors
CUSTOMER_PERSONAS = {
    "health_conscious": {
        "weight": 0.15,
        "description": "Focuses on organic, fresh produce, and healthy options",
        "category_preferences": {
            ProductCategory.PRODUCE: 2.5,
            ProductCategory.DAIRY: 1.2,
            ProductCategory.MEAT: 0.6,
            ProductCategory.FROZEN: 0.5,
            ProductCategory.SNACKS: 0.4,
            ProductCategory.BEVERAGES: 1.3,
            ProductCategory.PANTRY: 1.0,
        },
        "organic_preference": 0.75,  # 75% likely to choose organic when available
        "avg_order_value_multiplier": 1.3,
        "avg_items_multiplier": 0.9,  # Slightly fewer items but higher quality
        "preferred_hours": [8, 9, 10, 18, 19],  # Morning and early evening
        "routine_strength": 0.75,  # Highly routine-driven
    },
    "family_shopper": {
        "weight": 0.25,
        "description": "Large cart, bulk purchases, pantry staples, and kid-friendly items",
        "category_preferences": {
            ProductCategory.PANTRY: 2.0,
            ProductCategory.FROZEN: 1.8,
            ProductCategory.BEVERAGES: 1.5,
            ProductCategory.SNACKS: 1.7,
            ProductCategory.DAIRY: 1.6,
            ProductCategory.PRODUCE: 1.4,
            ProductCategory.MEAT: 1.5,
            ProductCategory.BAKERY: 1.4,
        },
        "organic_preference": 0.3,
        "avg_order_value_multiplier": 1.3,
        "avg_items_multiplier": 1.8,  # Large carts ~18 items
        "bulk_purchases": True,  # Higher quantities
        "preferred_hours": [10, 11, 14, 15, 19, 20],  # Avoid rush hours
        "preferred_days": [6, 0],  # Sunday, Monday (weekly shop)
        "routine_strength": 0.8,  # Very routine-driven
    },
    "young_professional": {
        "weight": 0.20,
        "description": "Small frequent orders, convenience items, prepared foods",
        "category_preferences": {
            ProductCategory.FROZEN: 1.8,  # Prepared meals
            ProductCategory.BEVERAGES: 1.8,
            ProductCategory.SNACKS: 1.5,
            ProductCategory.DAIRY: 1.2,
            ProductCategory.BAKERY: 1.3,
            ProductCategory.PRODUCE: 0.8,  # Less fresh cooking
            ProductCategory.MEAT: 0.7,
        },
        "organic_preference": 0.4,
        "avg_order_value_multiplier": 0.7,
        "avg_items_multiplier": 0.6,  # Small, frequent orders ~6 items
        "preferred_hours": [18, 19, 20, 21, 22],  # After work, late
        "routine_strength": 0.6,  # Moderately routine
    },
    "budget_conscious": {
        "weight": 0.20,
        "description": "Price-sensitive, staples, less organic, smart shopping",
        "category_preferences": {
            ProductCategory.PANTRY: 1.5,
            ProductCategory.PRODUCE: 1.3,
            ProductCategory.FROZEN: 1.2,
            ProductCategory.DAIRY: 1.1,
            ProductCategory.MEAT: 0.9,
            ProductCategory.SNACKS: 0.8,
        },
        "organic_preference": 0.15,  # Avoid expensive organic
        "avg_order_value_multiplier": 0.7,
        "avg_items_multiplier": 1.0,
        "price_sensitivity": True,  # Prefer lower-priced items
        "preferred_hours": [6, 7, 8, 14, 15, 22, 23],  # Off-peak to avoid fees
        "routine_strength": 0.7,
    },
    "specialty_diet": {
        "weight": 0.10,
        "description": "Organic, vegan, specialty items, health-focused",
        "category_preferences": {
            ProductCategory.PRODUCE: 2.8,
            ProductCategory.PANTRY: 1.5,
            ProductCategory.BEVERAGES: 1.4,
            ProductCategory.SNACKS: 1.2,
            ProductCategory.DAIRY: 0.6,  # Alternative milks
            ProductCategory.MEAT: 0.2,  # Mostly plant-based
        },
        "organic_preference": 0.85,  # Strong organic preference
        "avg_order_value_multiplier": 1.4,
        "avg_items_multiplier": 0.9,
        "preferred_hours": [9, 10, 11, 17, 18],
        "routine_strength": 0.75,
    },
    "convenience_seeker": {
        "weight": 0.10,
        "description": "Very frequent small orders, repeat purchases, quick needs",
        "category_preferences": {
            ProductCategory.BEVERAGES: 1.5,
            ProductCategory.SNACKS: 1.4,
            ProductCategory.DAIRY: 1.3,
            ProductCategory.BAKERY: 1.2,
            ProductCategory.FROZEN: 1.3,
        },
        "organic_preference": 0.4,
        "avg_order_value_multiplier": 0.5,
        "avg_items_multiplier": 0.5,  # Very small carts ~5 items
        "repeat_purchase_rate": 0.7,  # 70% of items from previous orders
        "preferred_hours": list(range(8, 23)),  # Any time
        "routine_strength": 0.5,  # Less routine, more opportunistic
    },
}


def get_persona_weights() -> List[float]:
    """Get weights for random persona selection."""
    return [p["weight"] for p in CUSTOMER_PERSONAS.values()]


def get_persona_names() -> List[str]:
    """Get list of persona names."""
    return list(CUSTOMER_PERSONAS.keys())


def select_random_persona() -> str:
    """Select a random persona based on weights."""
    personas = get_persona_names()
    weights = get_persona_weights()
    return random.choices(personas, weights=weights)[0]


def get_persona_config(persona_name: str) -> Dict:
    """Get configuration for a specific persona."""
    return CUSTOMER_PERSONAS.get(persona_name, CUSTOMER_PERSONAS["convenience_seeker"])


def get_category_preference(persona_name: str, category: ProductCategory) -> float:
    """Get preference multiplier for a category given a persona."""
    persona = get_persona_config(persona_name)
    return persona.get("category_preferences", {}).get(category, 1.0)


def get_organic_preference(persona_name: str) -> float:
    """Get organic preference (0-1) for a persona."""
    persona = get_persona_config(persona_name)
    return persona.get("organic_preference", 0.3)


def should_prefer_bulk(persona_name: str) -> bool:
    """Check if persona prefers bulk purchases."""
    persona = get_persona_config(persona_name)
    return persona.get("bulk_purchases", False)


def get_preferred_shopping_hours(persona_name: str) -> List[int]:
    """Get preferred shopping hours for persona."""
    persona = get_persona_config(persona_name)
    return persona.get("preferred_hours", list(range(9, 21)))


def get_preferred_shopping_days(persona_name: str) -> List[int]:
    """Get preferred shopping days (0=Monday, 6=Sunday) for persona."""
    persona = get_persona_config(persona_name)
    return persona.get("preferred_days", list(range(7)))


def get_routine_strength(persona_name: str) -> float:
    """Get routine strength (0-1) - how often they follow their preferred schedule."""
    persona = get_persona_config(persona_name)
    return persona.get("routine_strength", 0.5)


def get_order_value_multiplier(persona_name: str) -> float:
    """Get multiplier for average order value."""
    persona = get_persona_config(persona_name)
    return persona.get("avg_order_value_multiplier", 1.0)


def get_items_multiplier(persona_name: str) -> float:
    """Get multiplier for average items per order."""
    persona = get_persona_config(persona_name)
    return persona.get("avg_items_multiplier", 1.0)


def get_repeat_purchase_rate(persona_name: str) -> float:
    """Get rate of repeat purchases from order history."""
    persona = get_persona_config(persona_name)
    return persona.get("repeat_purchase_rate", 0.3)
