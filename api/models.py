from pydantic import BaseModel


class GenerationResponse(BaseModel):
    entity: str
    count: int
    ids: list[str]


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    status: str
    total: float
    item_count: int


class BundleResponse(BaseModel):
    bundles_created: int
    orders_bundled: int
    bundle_ids: list[str]
    avg_distance_km: float | None = None
    avg_duration_min: float | None = None


class StatsResponse(BaseModel):
    stores: int = 0
    customers: int
    drivers: int
    parent_products: int = 0
    store_products: int = 0
    orders: int
    order_items: int
    bundles: int = 0


class ServiceStatus(BaseModel):
    order_generation_active: bool
    bundle_processing_active: bool
    customer_generation_active: bool
    driver_generation_active: bool
    store_generation_active: bool
    order_interval_seconds: float
    bundle_interval_seconds: float
    customer_interval_seconds: float
    driver_interval_seconds: float
    store_interval_seconds: float


class ConfigUpdate(BaseModel):
    order_interval_seconds: float | None = None
    bundle_interval_seconds: float | None = None
    customer_interval_seconds: float | None = None
    driver_interval_seconds: float | None = None
    store_interval_seconds: float | None = None
