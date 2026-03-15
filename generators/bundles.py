"""
Product Affinity Bundles

Defines common product combinations that frequently appear together in orders.
Creates realistic basket patterns for market basket analysis and recommendation systems.
"""

from typing import List, Dict
from models import ProductCategory


# Product affinity bundles - items that commonly appear together
PRODUCT_BUNDLES = {
    "breakfast_essentials": {
        "description": "Classic breakfast items",
        "product_patterns": [
            "eggs", "bacon", "bread", "orange juice", "coffee"
        ],
        "categories": [ProductCategory.DAIRY, ProductCategory.MEAT, ProductCategory.BAKERY, ProductCategory.BEVERAGES],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,  # Usually 3-5 items from bundle
    },
    "pasta_night": {
        "description": "Pasta dinner ingredients",
        "product_patterns": [
            "pasta", "tomato", "garlic", "parmesan", "ground beef", "olive oil"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.PRODUCE, ProductCategory.MEAT],
        "co_occurrence_probability": 0.75,
        "avg_bundle_size": 5,
    },
    "taco_tuesday": {
        "description": "Taco ingredients",
        "product_patterns": [
            "tortilla", "ground beef", "cheese", "lettuce", "tomato", "avocado", "sour cream"
        ],
        "categories": [ProductCategory.BAKERY, ProductCategory.MEAT, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.80,
        "avg_bundle_size": 6,
    },
    "salad_bowl": {
        "description": "Salad ingredients",
        "product_patterns": [
            "lettuce", "tomato", "cucumber", "chicken breast", "cheese"
        ],
        "categories": [ProductCategory.PRODUCE, ProductCategory.MEAT, ProductCategory.DAIRY],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,
    },
    "sandwich_lunch": {
        "description": "Sandwich ingredients",
        "product_patterns": [
            "bread", "turkey", "ham", "cheese", "lettuce", "tomato", "mayo"
        ],
        "categories": [ProductCategory.BAKERY, ProductCategory.MEAT, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 5,
    },
    "stir_fry": {
        "description": "Stir fry ingredients",
        "product_patterns": [
            "rice", "chicken", "broccoli", "carrot", "soy sauce", "garlic", "ginger"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.MEAT, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 5,
    },
    "baking_basics": {
        "description": "Baking essentials",
        "product_patterns": [
            "flour", "sugar", "butter", "eggs", "vanilla", "baking"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.DAIRY],
        "co_occurrence_probability": 0.60,
        "avg_bundle_size": 4,
    },
    "smoothie_ingredients": {
        "description": "Smoothie items",
        "product_patterns": [
            "banana", "berries", "yogurt", "milk", "honey", "spinach"
        ],
        "categories": [ProductCategory.PRODUCE, ProductCategory.DAIRY, ProductCategory.FROZEN],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,
    },
    "burger_night": {
        "description": "Burger ingredients",
        "product_patterns": [
            "ground beef", "hamburger buns", "cheese", "lettuce", "tomato", "onion", "ketchup"
        ],
        "categories": [ProductCategory.MEAT, ProductCategory.BAKERY, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.75,
        "avg_bundle_size": 6,
    },
    "pizza_homemade": {
        "description": "Homemade pizza ingredients",
        "product_patterns": [
            "pizza", "mozzarella", "tomato sauce", "pepperoni", "mushroom", "bell pepper"
        ],
        "categories": [ProductCategory.FROZEN, ProductCategory.DAIRY, ProductCategory.PANTRY, ProductCategory.MEAT, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 5,
    },
    "coffee_and_snacks": {
        "description": "Coffee break items",
        "product_patterns": [
            "coffee", "milk", "sugar", "cookies", "muffin"
        ],
        "categories": [ProductCategory.BEVERAGES, ProductCategory.DAIRY, ProductCategory.PANTRY, ProductCategory.SNACKS, ProductCategory.BAKERY],
        "co_occurrence_probability": 0.60,
        "avg_bundle_size": 3,
    },
    "soup_and_sandwich": {
        "description": "Soup and sandwich combo",
        "product_patterns": [
            "bread", "soup", "cheese", "butter", "tomato"
        ],
        "categories": [ProductCategory.BAKERY, ProductCategory.PANTRY, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,
    },
    "bbq_party": {
        "description": "BBQ essentials",
        "product_patterns": [
            "steak", "chicken", "ribs", "bbq sauce", "corn", "potato", "beer"
        ],
        "categories": [ProductCategory.MEAT, ProductCategory.PANTRY, ProductCategory.PRODUCE, ProductCategory.BEVERAGES],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 5,
    },
    "healthy_snacking": {
        "description": "Healthy snack items",
        "product_patterns": [
            "almonds", "yogurt", "berries", "granola", "apple", "hummus"
        ],
        "categories": [ProductCategory.SNACKS, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.60,
        "avg_bundle_size": 4,
    },
    "breakfast_cereal": {
        "description": "Cereal breakfast",
        "product_patterns": [
            "cereal", "milk", "banana", "berries"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 3,
    },
    "fish_dinner": {
        "description": "Fish dinner ingredients",
        "product_patterns": [
            "salmon", "lemon", "asparagus", "rice", "olive oil"
        ],
        "categories": [ProductCategory.MEAT, ProductCategory.PRODUCE, ProductCategory.PANTRY],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,
    },
    "snack_party": {
        "description": "Party snacks",
        "product_patterns": [
            "chips", "salsa", "guacamole", "cheese", "crackers", "dip"
        ],
        "categories": [ProductCategory.SNACKS, ProductCategory.PRODUCE, ProductCategory.DAIRY],
        "co_occurrence_probability": 0.70,
        "avg_bundle_size": 5,
    },
    "oatmeal_breakfast": {
        "description": "Oatmeal breakfast",
        "product_patterns": [
            "oatmeal", "milk", "honey", "berries", "nuts"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.DAIRY, ProductCategory.PRODUCE, ProductCategory.SNACKS],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 4,
    },
    "mexican_fiesta": {
        "description": "Mexican meal ingredients",
        "product_patterns": [
            "rice", "beans", "tortilla", "cheese", "salsa", "avocado", "cilantro"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.BAKERY, ProductCategory.DAIRY, ProductCategory.PRODUCE],
        "co_occurrence_probability": 0.75,
        "avg_bundle_size": 6,
    },
    "kids_lunch": {
        "description": "Kid-friendly lunch items",
        "product_patterns": [
            "peanut butter", "jelly", "bread", "apple", "juice", "crackers"
        ],
        "categories": [ProductCategory.PANTRY, ProductCategory.BAKERY, ProductCategory.PRODUCE, ProductCategory.BEVERAGES, ProductCategory.SNACKS],
        "co_occurrence_probability": 0.65,
        "avg_bundle_size": 5,
    },
}


# Persona to bundle affinities (which personas prefer which bundles)
PERSONA_BUNDLE_AFFINITIES = {
    "health_conscious": {
        "salad_bowl": 2.5,
        "smoothie_ingredients": 2.5,
        "healthy_snacking": 2.0,
        "fish_dinner": 2.0,
        "oatmeal_breakfast": 1.8,
        "breakfast_essentials": 0.5,
        "bbq_party": 0.3,
    },
    "family_shopper": {
        "taco_tuesday": 2.0,
        "burger_night": 2.0,
        "pizza_homemade": 2.0,
        "pasta_night": 1.8,
        "kids_lunch": 2.5,
        "breakfast_essentials": 1.8,
        "mexican_fiesta": 1.7,
    },
    "young_professional": {
        "sandwich_lunch": 2.0,
        "soup_and_sandwich": 1.8,
        "coffee_and_snacks": 2.5,
        "pizza_homemade": 1.5,
        "stir_fry": 1.5,
        "pasta_night": 1.3,
    },
    "budget_conscious": {
        "pasta_night": 2.0,
        "rice_and_beans": 2.0,
        "oatmeal_breakfast": 1.8,
        "sandwich_lunch": 1.7,
        "breakfast_cereal": 1.8,
    },
    "specialty_diet": {
        "salad_bowl": 2.5,
        "smoothie_ingredients": 2.5,
        "healthy_snacking": 2.0,
        "stir_fry": 1.8,
        "fish_dinner": 1.5,
    },
    "convenience_seeker": {
        "coffee_and_snacks": 2.0,
        "sandwich_lunch": 1.8,
        "breakfast_cereal": 1.5,
    },
}


def get_bundle_names() -> List[str]:
    """Get list of all bundle names."""
    return list(PRODUCT_BUNDLES.keys())


def get_bundle_config(bundle_name: str) -> Dict:
    """Get configuration for a specific bundle."""
    return PRODUCT_BUNDLES.get(bundle_name, {})


def get_bundles_for_persona(persona_name: str) -> Dict[str, float]:
    """Get bundle preferences (with weights) for a persona."""
    return PERSONA_BUNDLE_AFFINITIES.get(persona_name, {})


def get_bundle_categories(bundle_name: str) -> List[ProductCategory]:
    """Get product categories involved in a bundle."""
    bundle = get_bundle_config(bundle_name)
    return bundle.get("categories", [])


def get_bundle_size(bundle_name: str) -> int:
    """Get average number of items in a bundle."""
    bundle = get_bundle_config(bundle_name)
    return bundle.get("avg_bundle_size", 3)


def get_co_occurrence_probability(bundle_name: str) -> float:
    """Get probability that items in bundle appear together."""
    bundle = get_bundle_config(bundle_name)
    return bundle.get("co_occurrence_probability", 0.6)
