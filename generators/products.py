import uuid
import random
from dataclasses import dataclass
from .base import BaseGenerator
from models import ProductCategory
from db import get_cursor


@dataclass
class ParentProduct:
    """Template product that can exist across multiple stores."""
    parent_product_id: str
    name: str
    category: ProductCategory
    brand: str
    base_price: float
    unit: str
    weight_oz: float | None
    is_organic: bool


@dataclass
class StoreProduct:
    """Actual product instance at a specific store."""
    store_product_id: str
    store_id: str
    parent_product_id: str
    price: float  # Store-specific price (may vary from base)
    is_available: bool
    stock_level: int


class ProductGenerator(BaseGenerator):
    """
    Two-tier product system:
    1. Parent products - the canonical product definitions
    2. Store products - instances at specific stores with local pricing/availability
    """
    
    # Base product catalog by category
    BASE_PRODUCTS = {
        ProductCategory.PRODUCE: [
            ("Bananas", "Dole", 0.59, "lb", 16, False),
            ("Avocados", "Hass", 1.49, "each", 6, False),
            ("Baby Spinach", "Earthbound", 4.99, "5oz", 5, False),
            ("Strawberries", "Driscoll's", 4.99, "lb", 16, False),
            ("Broccoli Crowns", "Local Farm", 2.49, "lb", 16, False),
            ("Russet Potatoes", "Idaho", 0.99, "lb", 16, False),
            ("Yellow Onions", "Local Farm", 1.29, "lb", 16, False),
            ("Roma Tomatoes", "Local Farm", 1.99, "lb", 16, False),
            ("Carrots", "Bolthouse", 1.49, "lb", 16, False),
            ("Lemons", "Sunkist", 0.69, "each", 4, False),
            ("Apples Honeycrisp", "Washington", 2.99, "lb", 16, False),
            ("Blueberries", "Driscoll's", 5.99, "6oz", 6, False),
            ("Garlic", "Christopher Ranch", 0.79, "each", 2, False),
            ("Cilantro", "Local Farm", 0.99, "bunch", 2, False),
            ("Bell Peppers", "Local Farm", 1.49, "each", 6, False),
            ("Grapes Red Seedless", "Farmer's Best", 3.49, "lb", 16, False),
            ("Cucumbers", "Local Farm", 1.29, "each", 8, False),
            ("Mushrooms White", "Monterey", 2.99, "8oz", 8, False),
            ("Lettuce Romaine", "Local Farm", 2.49, "head", 16, False),
            ("Sweet Potatoes", "Local Farm", 1.79, "lb", 16, False),
        ],
        ProductCategory.DAIRY: [
            ("2% Milk", "Horizon", 5.99, "gallon", 128, False),
            ("Whole Milk", "Organic Valley", 6.49, "gallon", 128, True),
            ("Large Eggs", "Happy Egg", 5.49, "dozen", 24, False),
            ("Greek Yogurt Plain", "Chobani", 1.29, "5.3oz", 5.3, False),
            ("Greek Yogurt Strawberry", "Chobani", 1.49, "5.3oz", 5.3, False),
            ("Greek Yogurt Vanilla", "Fage", 1.59, "5.3oz", 5.3, False),
            ("Cheddar Cheese Block", "Tillamook", 6.99, "8oz", 8, False),
            ("Cheddar Cheese Shredded", "Tillamook", 5.49, "8oz", 8, False),
            ("Mozzarella Fresh", "BelGioioso", 5.99, "8oz", 8, False),
            ("Butter Unsalted", "Kerrygold", 5.49, "8oz", 8, False),
            ("Butter Salted", "Land O Lakes", 4.99, "16oz", 16, False),
            ("Heavy Cream", "Organic Valley", 5.99, "16oz", 16, False),
            ("Sour Cream", "Daisy", 2.99, "16oz", 16, False),
            ("Cream Cheese", "Philadelphia", 3.49, "8oz", 8, False),
            ("Cottage Cheese", "Good Culture", 4.99, "16oz", 16, False),
            ("Parmesan Wedge", "Parmigiano Reggiano", 8.99, "5oz", 5, False),
            ("Oat Milk", "Oatly", 5.49, "64oz", 64, False),
            ("Almond Milk Unsweetened", "Califia", 4.99, "48oz", 48, False),
        ],
        ProductCategory.MEAT: [
            ("Chicken Breast Boneless", "Foster Farms", 8.99, "lb", 16, False),
            ("Chicken Thighs", "Foster Farms", 6.99, "lb", 16, False),
            ("Ground Beef 80/20", "Local Butcher", 6.99, "lb", 16, False),
            ("Ground Beef 90/10", "Local Butcher", 8.99, "lb", 16, False),
            ("Bacon Thick Cut", "Applegate", 8.99, "12oz", 12, False),
            ("Bacon Regular", "Oscar Mayer", 6.99, "16oz", 16, False),
            ("Salmon Fillet Wild", "Wild Caught", 12.99, "lb", 16, False),
            ("Salmon Fillet Farmed", "Atlantic", 9.99, "lb", 16, False),
            ("Pork Chops Bone-In", "Local Butcher", 5.99, "lb", 16, False),
            ("Italian Sausage Mild", "Johnsonville", 5.99, "16oz", 16, False),
            ("Italian Sausage Hot", "Johnsonville", 5.99, "16oz", 16, False),
            ("Ground Turkey 93/7", "Jennie-O", 6.49, "lb", 16, False),
            ("Ribeye Steak", "USDA Choice", 16.99, "lb", 16, False),
            ("NY Strip Steak", "USDA Choice", 14.99, "lb", 16, False),
            ("Shrimp Large 16-20", "Wild Caught", 11.99, "lb", 16, False),
            ("Shrimp Medium 31-40", "Frozen", 8.99, "lb", 16, False),
            ("Deli Turkey Smoked", "Boar's Head", 9.99, "lb", 16, False),
            ("Deli Ham Honey", "Boar's Head", 10.99, "lb", 16, False),
        ],
        ProductCategory.BAKERY: [
            ("Sourdough Bread", "Acme", 5.49, "loaf", 24, False),
            ("Whole Wheat Bread", "Dave's Killer", 5.99, "loaf", 24, False),
            ("White Bread", "Sara Lee", 3.99, "loaf", 20, False),
            ("Bagels Everything", "Thomas'", 4.99, "6ct", 18, False),
            ("Bagels Plain", "Thomas'", 4.99, "6ct", 18, False),
            ("Croissants Butter", "La Boulange", 6.99, "4ct", 8, False),
            ("Tortillas Flour 8in", "Mission", 3.49, "10ct", 16, False),
            ("Tortillas Corn", "Mission", 2.99, "30ct", 20, False),
            ("English Muffins", "Thomas'", 4.49, "6ct", 12, False),
            ("Hamburger Buns", "Sara Lee", 3.99, "8ct", 12, False),
            ("Hot Dog Buns", "Sara Lee", 3.99, "8ct", 12, False),
            ("Baguette French", "Local Bakery", 2.99, "each", 12, False),
            ("Ciabatta Rolls", "Local Bakery", 4.49, "4ct", 12, False),
            ("Pita Bread", "Joseph's", 3.99, "6ct", 10, False),
        ],
        ProductCategory.FROZEN: [
            ("Ice Cream Vanilla", "Häagen-Dazs", 5.99, "14oz", 14, False),
            ("Ice Cream Chocolate", "Häagen-Dazs", 5.99, "14oz", 14, False),
            ("Ice Cream Strawberry", "Ben & Jerry's", 5.99, "16oz", 16, False),
            ("Frozen Pizza Pepperoni", "DiGiorno", 7.99, "each", 28, False),
            ("Frozen Pizza Supreme", "DiGiorno", 8.49, "each", 30, False),
            ("Frozen Berries Mixed", "Cascadian Farm", 5.49, "10oz", 10, True),
            ("Frozen Blueberries", "Wyman's", 6.99, "15oz", 15, False),
            ("Chicken Nuggets", "Tyson", 8.99, "32oz", 32, False),
            ("Frozen Waffles Original", "Eggo", 4.49, "10ct", 12, False),
            ("Frozen Waffles Blueberry", "Eggo", 4.99, "10ct", 12, False),
            ("Frozen Vegetables Mixed", "Birds Eye", 2.99, "12oz", 12, False),
            ("Frozen Peas", "Birds Eye", 2.49, "10oz", 10, False),
            ("Frozen Burritos Bean", "Amy's", 3.49, "6oz", 6, True),
            ("Frozen Dumplings Pork", "Bibigo", 8.99, "24oz", 24, False),
            ("Fish Sticks", "Gorton's", 6.99, "19oz", 19, False),
        ],
        ProductCategory.BEVERAGES: [
            ("Orange Juice No Pulp", "Tropicana", 6.99, "52oz", 52, False),
            ("Orange Juice Pulp", "Tropicana", 6.99, "52oz", 52, False),
            ("Apple Juice", "Martinelli's", 3.99, "10oz", 10, False),
            ("Sparkling Water Lime", "LaCroix", 5.99, "12pk", 144, False),
            ("Sparkling Water Lemon", "LaCroix", 5.99, "12pk", 144, False),
            ("Sparkling Water Plain", "Topo Chico", 2.49, "12oz", 12, False),
            ("Coffee Beans Medium", "Peet's", 12.99, "12oz", 12, False),
            ("Coffee Beans Dark", "Starbucks", 11.99, "12oz", 12, False),
            ("Coffee Ground", "Folgers", 8.99, "30oz", 30, False),
            ("Cold Brew Coffee", "Stumptown", 4.99, "10.5oz", 10.5, False),
            ("Coconut Water", "Vita Coco", 2.49, "16.9oz", 16.9, False),
            ("Kombucha Ginger", "GT's", 3.99, "16oz", 16, False),
            ("Kombucha Original", "GT's", 3.99, "16oz", 16, False),
            ("Energy Drink Original", "Red Bull", 2.99, "8.4oz", 8.4, False),
            ("Sports Drink Lemon", "Gatorade", 1.99, "28oz", 28, False),
        ],
        ProductCategory.SNACKS: [
            ("Potato Chips Sea Salt", "Kettle Brand", 4.49, "8oz", 8, False),
            ("Potato Chips BBQ", "Lay's", 4.29, "8oz", 8, False),
            ("Potato Chips Sour Cream", "Ruffles", 4.49, "8.5oz", 8.5, False),
            ("Tortilla Chips", "Late July", 4.99, "11oz", 11, True),
            ("Tortilla Chips Lime", "Tostitos", 4.49, "13oz", 13, False),
            ("Mixed Nuts Deluxe", "Planters", 8.99, "10.3oz", 10.3, False),
            ("Almonds Roasted", "Blue Diamond", 7.99, "6oz", 6, False),
            ("Cashews Salted", "Planters", 9.99, "8oz", 8, False),
            ("Granola Bars Oat", "KIND", 5.99, "6ct", 8, False),
            ("Granola Bars Chocolate", "Nature Valley", 4.99, "6ct", 7.5, False),
            ("Pretzels Twists", "Snyder's", 3.99, "16oz", 16, False),
            ("Dark Chocolate 72%", "Ghirardelli", 4.49, "4.1oz", 4.1, False),
            ("Milk Chocolate", "Lindt", 3.99, "4.4oz", 4.4, False),
            ("Trail Mix Classic", "Kirkland", 12.99, "4lb", 64, False),
            ("Popcorn Sea Salt", "SkinnyPop", 4.99, "4.4oz", 4.4, False),
            ("Crackers Wheat", "Triscuit", 4.49, "9oz", 9, False),
            ("Crackers Cheese", "Cheez-It", 4.99, "12oz", 12, False),
        ],
        ProductCategory.PANTRY: [
            ("Olive Oil Extra Virgin", "California Olive Ranch", 12.99, "16.9oz", 16.9, False),
            ("Olive Oil Regular", "Bertolli", 8.99, "17oz", 17, False),
            ("Vegetable Oil", "Crisco", 4.99, "48oz", 48, False),
            ("Pasta Spaghetti", "Barilla", 1.99, "16oz", 16, False),
            ("Pasta Penne", "Barilla", 1.99, "16oz", 16, False),
            ("Pasta Fusilli", "De Cecco", 2.49, "16oz", 16, False),
            ("Rice Jasmine", "Mahatma", 4.99, "2lb", 32, False),
            ("Rice Brown", "Lundberg", 5.99, "2lb", 32, True),
            ("Rice Basmati", "Tilda", 6.99, "2lb", 32, False),
            ("Canned Tomatoes Diced", "Muir Glen", 2.99, "14.5oz", 14.5, True),
            ("Canned Tomatoes Crushed", "San Marzano", 3.99, "28oz", 28, False),
            ("Tomato Paste", "Hunt's", 1.49, "6oz", 6, False),
            ("Black Beans", "Bush's", 1.49, "15oz", 15, False),
            ("Chickpeas", "Goya", 1.69, "15.5oz", 15.5, False),
            ("Kidney Beans", "Bush's", 1.49, "16oz", 16, False),
            ("Peanut Butter Creamy", "Jif", 4.99, "16oz", 16, False),
            ("Peanut Butter Crunchy", "Skippy", 4.99, "16oz", 16, False),
            ("Almond Butter", "Justin's", 9.99, "12oz", 12, False),
            ("Honey Local", "Local Bees", 8.99, "12oz", 12, False),
            ("Maple Syrup Grade A", "Vermont", 11.99, "12oz", 12, False),
            ("Chicken Broth Low Sodium", "Pacific Foods", 3.99, "32oz", 32, False),
            ("Vegetable Broth", "Swanson", 2.99, "32oz", 32, False),
            ("Flour All Purpose", "King Arthur", 5.99, "5lb", 80, False),
            ("Sugar White", "Domino", 3.99, "4lb", 64, False),
            ("Brown Sugar", "C&H", 4.49, "2lb", 32, False),
        ],
        ProductCategory.HOUSEHOLD: [
            ("Paper Towels 6pk", "Bounty", 12.99, "6ct", None, False),
            ("Paper Towels 2pk", "Viva", 6.99, "2ct", None, False),
            ("Toilet Paper 12pk", "Charmin", 14.99, "12ct", None, False),
            ("Toilet Paper 6pk", "Cottonelle", 8.99, "6ct", None, False),
            ("Dish Soap Original", "Dawn", 4.49, "16oz", 16, False),
            ("Dish Soap Lavender", "Mrs. Meyer's", 4.99, "16oz", 16, False),
            ("Laundry Detergent Liquid", "Tide", 14.99, "64oz", 64, False),
            ("Laundry Detergent Pods", "Tide", 19.99, "42ct", None, False),
            ("Trash Bags 13gal", "Glad", 9.99, "45ct", None, False),
            ("Trash Bags 30gal", "Hefty", 12.99, "28ct", None, False),
            ("Aluminum Foil", "Reynolds", 6.99, "75ft", None, False),
            ("Plastic Wrap", "Glad", 3.99, "200ft", None, False),
            ("Sponges 6pk", "Scotch-Brite", 3.99, "6ct", None, False),
            ("Ziplock Bags Gallon", "Ziploc", 4.99, "38ct", None, False),
            ("Ziplock Bags Quart", "Ziploc", 3.99, "48ct", None, False),
            ("All Purpose Cleaner", "Method", 4.99, "28oz", 28, False),
            ("Glass Cleaner", "Windex", 4.49, "23oz", 23, False),
        ],
        ProductCategory.PERSONAL_CARE: [
            ("Toothpaste Mint", "Colgate", 4.99, "6oz", 6, False),
            ("Toothpaste Whitening", "Crest", 5.99, "4.1oz", 4.1, False),
            ("Shampoo Daily", "Pantene", 6.99, "12oz", 12, False),
            ("Shampoo Volumizing", "TRESemmé", 5.99, "28oz", 28, False),
            ("Conditioner Daily", "Pantene", 6.99, "12oz", 12, False),
            ("Body Wash Original", "Dove", 7.99, "22oz", 22, False),
            ("Body Wash Mens", "Old Spice", 6.99, "18oz", 18, False),
            ("Deodorant Mens", "Old Spice", 7.99, "2.6oz", 2.6, False),
            ("Deodorant Womens", "Native", 12.99, "2.65oz", 2.65, False),
            ("Hand Soap Lavender", "Mrs. Meyer's", 4.49, "12.5oz", 12.5, False),
            ("Hand Soap Unscented", "Method", 3.99, "12oz", 12, False),
            ("Lotion Daily", "Aveeno", 9.99, "18oz", 18, False),
            ("Lotion Intensive", "Eucerin", 12.99, "16.9oz", 16.9, False),
            ("Tissues 3pk", "Kleenex", 5.99, "480ct", None, False),
            ("Sunscreen SPF30", "Neutrogena", 11.99, "3oz", 3, False),
            ("Sunscreen SPF50", "Coppertone", 10.99, "8oz", 8, False),
            ("Lip Balm", "Burt's Bees", 3.49, "0.15oz", 0.15, False),
        ],
    }
    
    def __init__(self, seed: int | None = 42):
        super().__init__(seed)
        self._parent_products: list[ParentProduct] = []
    
    def generate_parent_catalog(self) -> list[ParentProduct]:
        """Generate the canonical parent product catalog."""
        products = []
        
        for category, product_list in self.BASE_PRODUCTS.items():
            for name, brand, base_price, unit, weight, is_organic in product_list:
                products.append(ParentProduct(
                    parent_product_id=str(uuid.uuid4()),
                    name=name,
                    category=category,
                    brand=brand,
                    base_price=base_price,
                    unit=unit,
                    weight_oz=weight,
                    is_organic=is_organic,
                ))
        
        self._parent_products = products
        return products
    
    def generate_store_inventory(
        self, 
        store_id: str, 
        coverage: float = 0.85,
        price_variance: float = 0.15,
    ) -> list[StoreProduct]:
        """
        Generate inventory for a specific store.
        
        Args:
            store_id: The store to generate inventory for
            coverage: Fraction of parent products this store carries (0-1)
            price_variance: Max price deviation from base (+/- percentage)
        """
        if not self._parent_products:
            # Load from DB if not in memory
            self._parent_products = self.get_all_parent_products()
        
        if not self._parent_products:
            # Still empty, generate catalog first
            self.generate_parent_catalog()
            self.save_parent_products_to_db(self._parent_products)
        
        # Randomly select which products this store carries
        num_products = int(len(self._parent_products) * coverage)
        selected = random.sample(self._parent_products, num_products)
        
        store_products = []
        for parent in selected:
            # Store-specific price variance
            price_mult = random.uniform(1 - price_variance, 1 + price_variance)
            price = round(parent.base_price * price_mult, 2)
            
            # Availability and stock
            is_available = random.random() < 0.92  # 92% in stock
            stock_level = random.randint(0, 50) if is_available else 0
            
            store_products.append(StoreProduct(
                store_product_id=str(uuid.uuid4()),
                store_id=store_id,
                parent_product_id=parent.parent_product_id,
                price=price,
                is_available=is_available,
                stock_level=stock_level,
            ))
        
        return store_products
    
    def generate_one(self) -> ParentProduct:
        """Generate a single random parent product."""
        category = random.choice(list(self.BASE_PRODUCTS.keys()))
        base_data = random.choice(self.BASE_PRODUCTS[category])
        name, brand, base_price, unit, weight, is_organic = base_data
        
        # Add some variation
        variant_suffix = random.choice(["", " Large", " Small", " Value Pack", " Family Size", ""])
        price_mult = random.uniform(0.9, 1.1)
        
        return ParentProduct(
            parent_product_id=str(uuid.uuid4()),
            name=f"{name}{variant_suffix}".strip(),
            category=category,
            brand=brand,
            base_price=round(base_price * price_mult, 2),
            unit=unit,
            weight_oz=weight,
            is_organic=is_organic or random.random() < 0.1,
        )
    
    def generate_catalog(self) -> list[ParentProduct]:
        """
        Generate the complete parent product catalog.
        This is the main method to generate all parent products.
        """
        return self.generate_parent_catalog()
    
    def generate_batch(self, count: int) -> list[ParentProduct]:
        """Generate random parent products."""
        return [self.generate_one() for _ in range(count)]
    
    def save_parent_products_to_db(self, records: list[ParentProduct]):
        """Save parent products to database."""
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO parent_products 
                (parent_product_id, name, category, brand, base_price, unit, 
                 weight_oz, is_organic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (p.parent_product_id, p.name, p.category.value, p.brand,
                     p.base_price, p.unit, p.weight_oz, p.is_organic)
                    for p in records
                ]
            )
        print(f"Saved {len(records)} parent products")
    
    def save_store_products_to_db(self, records: list[StoreProduct]):
        """Save store-specific products to database."""
        with get_cursor() as cursor:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO store_products 
                (store_product_id, store_id, parent_product_id, price, 
                 is_available, stock_level)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (sp.store_product_id, sp.store_id, sp.parent_product_id,
                     sp.price, sp.is_available, sp.stock_level)
                    for sp in records
                ]
            )
        print(f"Saved {len(records)} store products")
    
    def save_to_db(self, records: list[ParentProduct]):
        """Alias for save_parent_products_to_db for compatibility."""
        self.save_parent_products_to_db(records)
    
    def get_store_available_products(self, store_id: str) -> list[tuple]:
        """Returns (store_product_id, parent_product_id, price) for available products at store."""
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT store_product_id, parent_product_id, price 
                   FROM store_products 
                   WHERE store_id = ? AND is_available = 1""",
                (store_id,)
            )
            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    
    def get_all_parent_products(self) -> list[ParentProduct]:
        """Load all parent products from database."""
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM parent_products")
            rows = cursor.fetchall()
            return [
                ParentProduct(
                    parent_product_id=row[0],
                    name=row[1],
                    category=ProductCategory(row[2]),
                    brand=row[3],
                    base_price=row[4],
                    unit=row[5],
                    weight_oz=row[6],
                    is_organic=bool(row[7]),
                )
                for row in rows
            ]
