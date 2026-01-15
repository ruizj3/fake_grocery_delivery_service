from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PICKING = "picking"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELED = "canceled"


class ProductCategory(str, Enum):
    PRODUCE = "produce"
    DAIRY = "dairy"
    MEAT = "meat"
    BAKERY = "bakery"
    FROZEN = "frozen"
    BEVERAGES = "beverages"
    SNACKS = "snacks"
    PANTRY = "pantry"
    HOUSEHOLD = "household"
    PERSONAL_CARE = "personal_care"


class Customer(BaseModel):
    customer_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    created_at: datetime
    is_premium: bool = False


class Driver(BaseModel):
    driver_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    vehicle_type: str
    license_plate: str
    rating: float = Field(ge=1.0, le=5.0)
    total_deliveries: int = 0
    home_latitude: float
    home_longitude: float
    is_active: bool = True
    created_at: datetime


class Product(BaseModel):
    product_id: str
    name: str
    category: ProductCategory
    brand: str
    price: float = Field(ge=0.01)
    unit: str  # e.g., "lb", "oz", "each", "gallon"
    weight_oz: Optional[float] = None
    is_organic: bool = False
    is_available: bool = True


class Order(BaseModel):
    order_id: str
    customer_id: str
    driver_id: Optional[str] = None
    status: OrderStatus
    subtotal: float
    tax: float
    delivery_fee: float
    tip: float
    total: float
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    picked_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    delivery_latitude: float
    delivery_longitude: float
    delivery_notes: Optional[str] = None


class OrderItem(BaseModel):
    order_item_id: str
    order_id: str
    product_id: str
    quantity: int = Field(ge=1)
    unit_price: float
    total_price: float
