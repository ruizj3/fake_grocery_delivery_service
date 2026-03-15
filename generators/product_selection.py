"""
Product Selection Logic

Handles persona-based product selection and bundle integration for orders.
Creates realistic shopping patterns based on customer personas.
"""

import random
from typing import List, Tuple, Dict
from models import ProductCategory
from .personas import (
    get_category_preference,
    get_organic_preference,
    should_prefer_bulk,
    get_repeat_purchase_rate,
    get_items_multiplier
)
from .bundles import (
    get_bundles_for_persona,
    get_bundle_categories,
    get_bundle_size,
    get_co_occurrence_probability
)


def select_products_for_order(
    persona: str,
    store_products: List[Tuple],  # (store_product_id, parent_product_id, price, category, is_organic)
    target_items: int,
    customer_id: str = None,
    db_cursor = None
) -> List[Tuple]:
    """
    Select products for an order based on customer persona.
    
    Args:
        persona: Customer persona name
        store_products: Available products at store
        target_items: Target number of items
        customer_id: Customer ID for repeat purchase lookup
        db_cursor: Database cursor for order history lookup
        
    Returns:
        List of selected products (store_product_id, parent_product_id, price)
    """
    selected_products = []
    items_from_bundles = []
    
    # Phase 1: Try to include meal bundles (40% chance)
    if random.random() < 0.40:
        persona_bundles = get_bundles_for_persona(persona)
        if persona_bundles:
            # Weighted selection of bundle
            bundle_names = list(persona_bundles.keys())
            bundle_weights = list(persona_bundles.values())
            
            # Select 1-2 bundles
            num_bundles = random.choices([1, 2], weights=[0.7, 0.3])[0]
            selected_bundle_names = random.choices(
                bundle_names,
                weights=bundle_weights,
                k=min(num_bundles, len(bundle_names))
            )
            
            for bundle_name in selected_bundle_names:
                bundle_items = _get_bundle_items(
                    bundle_name,
                    store_products,
                    persona
                )
                items_from_bundles.extend(bundle_items)
    
    # Phase 2: Add repeat purchases (if customer has history)
    repeat_rate = get_repeat_purchase_rate(persona)
    if customer_id and db_cursor and random.random() < repeat_rate:
        repeat_items = _get_repeat_purchases(
            customer_id,
            store_products,
            db_cursor,
            max_items=max(3, int(target_items * 0.4))  # Up to 40% repeats
        )
        items_from_bundles.extend(repeat_items)
    
    # Phase 3: Fill remaining with persona-weighted random selection
    items_needed = target_items - len(items_from_bundles)
    if items_needed > 0:
        random_items = _select_persona_weighted_products(
            persona,
            store_products,
            items_needed,
            exclude_products=set(p[0] for p in items_from_bundles)
        )
        selected_products = items_from_bundles + random_items
    else:
        # Trim if we have too many from bundles
        selected_products = items_from_bundles[:target_items]
    
    return selected_products


def _get_bundle_items(
    bundle_name: str,
    store_products: List[Tuple],
    persona: str
) -> List[Tuple]:
    """Get items for a specific meal bundle."""
    bundle_categories = get_bundle_categories(bundle_name)
    target_size = get_bundle_size(bundle_name)
    co_occurrence_prob = get_co_occurrence_probability(bundle_name)
    
    # Filter products to bundle categories
    category_products = [
        p for p in store_products
        if len(p) >= 4 and p[3] in bundle_categories
    ]
    
    if not category_products:
        return []
    
    # Select items from bundle categories
    actual_size = int(target_size * random.uniform(0.6, 1.0))  # Some variation
    selected = []
    
    # Ensure we get products from each category in bundle
    for category in bundle_categories:
        cat_products = [p for p in category_products if p[3] == category]
        if cat_products:
            # Apply organic preference
            organic_pref = get_organic_preference(persona)
            if random.random() < organic_pref:
                organic_products = [p for p in cat_products if len(p) >= 5 and p[4]]
                if organic_products:
                    cat_products = organic_products
            
            product = random.choice(cat_products)
            selected.append(product[:3])  # (store_product_id, parent_product_id, price)
    
    # Fill to target size with random from bundle categories
    while len(selected) < actual_size and category_products:
        available = [p for p in category_products if p[0] not in [s[0] for s in selected]]
        if not available:
            break
        product = random.choice(available)
        selected.append(product[:3])
    
    return selected


def _get_repeat_purchases(
    customer_id: str,
    store_products: List[Tuple],
    db_cursor,
    max_items: int
) -> List[Tuple]:
    """Get products customer has purchased before."""
    try:
        # Get customer's most recent order items
        db_cursor.execute("""
            SELECT oi.parent_product_id, COUNT(*) as purchase_count
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.customer_id = ?
            AND o.status != 'canceled'
            GROUP BY oi.parent_product_id
            ORDER BY purchase_count DESC, MAX(o.created_at) DESC
            LIMIT 20
        """, (customer_id,))
        
        past_products = [row[0] for row in db_cursor.fetchall()]
        
        if not past_products:
            return []
        
        # Find these products in current store
        repeat_items = []
        for parent_id in past_products:
            matching = [p for p in store_products if p[1] == parent_id]
            if matching:
                product = random.choice(matching)
                repeat_items.append(product[:3])
                if len(repeat_items) >= max_items:
                    break
        
        return repeat_items
    except Exception:
        return []


def _select_persona_weighted_products(
    persona: str,
    store_products: List[Tuple],
    num_items: int,
    exclude_products: set = None
) -> List[Tuple]:
    """Select products using persona category preferences."""
    if exclude_products is None:
        exclude_products = set()
    
    available = [p for p in store_products if p[0] not in exclude_products]
    
    if not available:
        return []
    
    # Calculate weights based on persona preferences
    weights = []
    organic_pref = get_organic_preference(persona)
    
    for product in available:
        if len(product) < 4:
            # Missing category info, give default weight
            weights.append(1.0)
            continue
            
        category = product[3]
        category_weight = get_category_preference(persona, category)
        
        # Bonus for organic if persona prefers it
        organic_bonus = 1.0
        if len(product) >= 5 and product[4]:  # is_organic
            if random.random() < organic_pref:
                organic_bonus = 2.0
        
        # Price sensitivity for budget-conscious
        price_weight = 1.0
        if persona == "budget_conscious" and len(product) >= 3:
            # Prefer lower-priced items
            price = product[2]
            if price < 5.0:
                price_weight = 1.5
            elif price > 15.0:
                price_weight = 0.5
        
        total_weight = category_weight * organic_bonus * price_weight
        weights.append(total_weight)
    
    # Select products with weighted random selection
    num_to_select = min(num_items, len(available))
    
    if num_to_select == 0:
        return []
    
    # Prevent duplicate selection
    selected_indices = set()
    selected_products = []
    
    for _ in range(num_to_select):
        if not available:
            break
            
        # Weighted random choice
        idx = random.choices(range(len(available)), weights=weights)[0]
        
        # Skip if already selected
        if idx in selected_indices:
            continue
            
        selected_indices.add(idx)
        selected_products.append(available[idx][:3])  # (store_product_id, parent_product_id, price)
    
    return selected_products


def calculate_cart_size(persona: str, base_size: int = 10) -> int:
    """Calculate cart size based on persona.
    
    Real-world grocery delivery averages 10-15 items per order.
    Family shoppers may reach 20-25, convenience seekers 4-8.
    """
    multiplier = get_items_multiplier(persona)
    target_size = int(base_size * multiplier)
    
    # Add some randomness (±20%)
    variation = random.uniform(0.8, 1.2)
    final_size = int(target_size * variation)
    
    return max(2, min(30, final_size))  # Keep between 2-30 items
