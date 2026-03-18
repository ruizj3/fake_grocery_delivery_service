"""
Grocery Delivery API

Live data generation service with:
- On-demand entity generation (customers, drivers, products)
- Random order placement
- Periodic bundle processing
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
import asyncio
import os
import random
from datetime import datetime

from database.db import init_database, get_table_counts
from generators import (
    CustomerGenerator,
    DriverGenerator,
    ProductGenerator,
    StoreGenerator,
    OrderGenerator,
)
from generators.base import get_simulation_config, set_simulation_config
from services import BundlingService
from services.predictions import PredictionService
from simulation import SimulationConfig, SimulationRNG
from api.models import (
    GenerationResponse,
    OrderResponse,
    BundleResponse,
    StatsResponse,
    ConfigUpdate,
    ServiceStatus,
    PredictionResponse,
    SimulationConfigUpdate,
)


# =============================================================================
# API Key Authentication
# =============================================================================

API_KEY = os.environ.get("API_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(_api_key_header)):
    """Dependency that protects write endpoints with an API key.
    If API_KEY is not set, all requests are allowed (local dev)."""
    if API_KEY is None:
        return  # No key configured — skip auth (local development)
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# Global state for background tasks
class AppState:
    def __init__(self):
        self.order_generation_active = False
        self.bundle_processing_active = False
        self.delivery_simulation_active = False
        self.customer_generation_active = False
        self.driver_generation_active = False
        self.store_generation_active = False
        self.prediction_sending_active = False
        
        # Simulation config (deterministic seeding)
        self.sim_config = SimulationConfig(deterministic_mode=False)  # API default: non-deterministic
        self.sim_rng = SimulationRNG(seed=None, namespace="api")
        
        # Generation intervals (will be overridden by Poisson arrivals when deterministic)
        self.order_interval_seconds = 10.0  # New order every N seconds
        self.bundle_interval_seconds = 60.0  # Process bundles every N seconds
        self.customer_interval_seconds = 120.0  # New customers every N seconds
        self.driver_interval_seconds = 300.0  # New drivers every N seconds
        self.store_interval_seconds = 600.0  # New stores every N seconds
        self.prediction_interval_seconds = 10.0  # Send predictions every N seconds
        
        # Background tasks
        self.order_task: asyncio.Task | None = None
        self.bundle_task: asyncio.Task | None = None
        self.delivery_task: asyncio.Task | None = None
        self.cancellation_task: asyncio.Task | None = None
        self.customer_task: asyncio.Task | None = None
        self.driver_task: asyncio.Task | None = None
        self.store_task: asyncio.Task | None = None
        self.prediction_task: asyncio.Task | None = None
        
        # Generators (lazy init after DB ready)
        self._customer_gen = None
        self._driver_gen = None
        self._product_gen = None
        self._store_gen = None
        self._order_gen = None
        self._bundle_service = None
    
    @property
    def customer_gen(self):
        if not self._customer_gen:
            seed = self.sim_config.derive_seed("customers") if self.sim_config.deterministic_mode else None
            self._customer_gen = CustomerGenerator(seed=seed)
        return self._customer_gen
    
    @property
    def driver_gen(self):
        if not self._driver_gen:
            seed = self.sim_config.derive_seed("drivers") if self.sim_config.deterministic_mode else None
            self._driver_gen = DriverGenerator(seed=seed)
        return self._driver_gen
    
    @property
    def product_gen(self):
        if not self._product_gen:
            seed = self.sim_config.derive_seed("products") if self.sim_config.deterministic_mode else None
            self._product_gen = ProductGenerator(seed=seed)
        return self._product_gen
    
    @property
    def store_gen(self):
        if not self._store_gen:
            seed = self.sim_config.derive_seed("stores") if self.sim_config.deterministic_mode else None
            self._store_gen = StoreGenerator(seed=seed)
        return self._store_gen
    
    @property
    def order_gen(self):
        if not self._order_gen:
            seed = self.sim_config.derive_seed("orders") if self.sim_config.deterministic_mode else None
            self._order_gen = OrderGenerator(seed=seed)
        return self._order_gen
    
    @property
    def bundle_service(self):
        if not self._bundle_service:
            self._bundle_service = BundlingService(
                time_window_minutes=60,  # Increased from 30 to allow more bundling
                max_bundle_size=10,
                max_radius_km=10.0,  # Increased from 5.0 to bundle wider area
            )
        return self._bundle_service
    
    @property
    def prediction_service(self):
        return PredictionService()


state = AppState()


async def request_prediction_for_orders(order_ids: list[str]):
    """Helper to request predictions for confirmed orders without blocking."""
    if not order_ids:
        return
    
    try:
        prediction_service = PredictionService()
        for order_id in order_ids:
            # Fire and forget - don't wait for response
            await prediction_service.get_prediction_for_order(order_id)
    except Exception as e:
        # Silent failure - don't crash the order generation
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Prediction request failed: {e}")


async def random_order_generator():
    """Background task: generates orders using Poisson process inter-arrival times.
    
    When deterministic_mode is enabled, uses exponential distribution (Poisson process)
    for realistic inter-arrival times controlled by the simulation seed.
    Otherwise falls back to uniform jitter around the configured interval.
    """
    while state.order_generation_active:
        try:
            # Poisson process: exponential inter-arrival time
            if state.sim_config.deterministic_mode:
                wait_seconds = state.sim_rng.exponential_wait(
                    rate_per_min=state.sim_config.order_arrival_rate_per_min
                )
            else:
                # Legacy behavior: uniform jitter around interval
                jitter = random.uniform(0.5, 1.5)
                wait_seconds = state.order_interval_seconds * jitter
            
            await asyncio.sleep(wait_seconds)
            
            if state.order_generation_active:
                # Simulated API error injection
                if state.sim_rng.should_trigger(state.sim_config.api_error_rate):
                    error_delay_ms = state.sim_rng.gaussian(
                        mean=state.sim_config.api_error_delay_mean_ms,
                        std=state.sim_config.api_error_delay_std_ms,
                        minimum=100.0
                    )
                    await asyncio.sleep(error_delay_ms / 1000.0)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Simulated order generation error (HTTP 500, {error_delay_ms:.0f}ms delay)")
                    continue
                
                order, items = state.order_gen.generate_one()
                confirmed_order_ids = state.order_gen.save_to_db(([order], items))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Generated order {order.order_id[:8]}... (${order.total:.2f})")
                
                # Immediately request prediction for confirmed orders
                if confirmed_order_ids:
                    asyncio.create_task(request_prediction_for_orders(confirmed_order_ids))
        except Exception as e:
            print(f"Error generating order: {e}")
            await asyncio.sleep(5)


async def periodic_bundle_processor():
    """Background task: processes pending orders into bundles."""
    while state.bundle_processing_active:
        try:
            await asyncio.sleep(state.bundle_interval_seconds)
            
            if state.bundle_processing_active:
                # Get pending/confirmed orders
                pending = state.bundle_service.fetch_pending_orders()
                
                if pending:
                    bundles = state.bundle_service.create_bundles(pending)
                    bundles = state.bundle_service.assign_drivers(bundles)
                    state.bundle_service.save_bundles_to_db(bundles)
                    
                    # Mark orders as "picking" with picked_at timestamp
                    # Also set assigned_at for bundles with drivers
                    from database.db import get_cursor
                    from datetime import timedelta
                    import random
                    with get_cursor() as cursor:
                        for bundle in bundles:
                            # Set assigned_at based on bundle.created_at (driver assigned right after bundle creation)
                            if bundle.driver_id:
                                # Assigned 0-2 minutes after bundle creation
                                assigned_time = bundle.created_at + timedelta(minutes=random.randint(0, 2))
                                cursor.execute(
                                    "UPDATE bundles SET assigned_at = ? WHERE bundle_id = ?",
                                    (assigned_time.isoformat(), bundle.bundle_id)
                                )
                            
                            # Picking starts 5-15 minutes after bundle creation (and after assignment)
                            picked_time = bundle.created_at + timedelta(minutes=random.randint(5, 15))
                            for stop in bundle.stops:
                                cursor.execute(
                                    "UPDATE orders SET status = 'picking', picked_at = ? WHERE order_id = ?",
                                    (picked_time.isoformat(), stop.order_id)
                                )
                    
                    stats = state.bundle_service.get_bundle_stats(bundles)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bundled {stats['total_orders']} orders into {stats['total_bundles']} bundles")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No pending orders to bundle")
        except Exception as e:
            print(f"Error processing bundles: {e}")
            await asyncio.sleep(10)


async def delivery_simulator():
    """Background task: simulates order delivery progression with realistic timestamps."""
    from database.db import get_cursor
    
    while state.delivery_simulation_active:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            if not state.delivery_simulation_active:
                break
            
            with get_cursor() as cursor:
                # Find bundles with orders in 'picking' status
                cursor.execute("""
                    SELECT DISTINCT b.bundle_id, b.estimated_duration_min, b.total_distance_km
                    FROM bundles b
                    JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
                    JOIN orders o ON bs.order_id = o.order_id
                    WHERE o.status = 'picking'
                    AND o.picked_at IS NOT NULL
                    AND datetime(o.picked_at, '+10 minutes') < datetime('now')
                """)
                picking_bundles = cursor.fetchall()
                
                # Progress picking → out_for_delivery
                for bundle_id, est_duration, total_distance in picking_bundles:
                    # Mark picking as completed - calculate relative to picked_at to ensure chronological order
                    cursor.execute("""
                        UPDATE orders
                        SET status = 'out_for_delivery',
                            picking_completed_at = datetime(picked_at, '+' || (15 + ABS(RANDOM()) % 31) || ' minutes')
                        WHERE order_id IN (
                            SELECT order_id FROM bundle_stops WHERE bundle_id = ?
                        )
                        AND picking_completed_at IS NULL
                    """, (bundle_id,))
                    
                    # Update bundle picked_up_at to match the earliest picked_at from orders
                    cursor.execute("""
                        UPDATE bundles
                        SET picked_up_at = (
                            SELECT MIN(o.picked_at)
                            FROM bundle_stops bs
                            JOIN orders o ON bs.order_id = o.order_id
                            WHERE bs.bundle_id = ?
                        )
                        WHERE bundle_id = ?
                    """, (bundle_id, bundle_id))
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bundle {bundle_id[:8]}... out for delivery")
                
                # Find bundles with orders in 'out_for_delivery' status for sequential delivery
                cursor.execute("""
                    SELECT DISTINCT b.bundle_id, b.estimated_duration_min
                    FROM bundles b
                    JOIN bundle_stops bs ON b.bundle_id = bs.bundle_id
                    JOIN orders o ON bs.order_id = o.order_id
                    WHERE o.status = 'out_for_delivery'
                    AND o.picked_at IS NOT NULL
                    AND datetime(o.picked_at, '+20 minutes') < datetime('now')
                """)
                delivery_bundles = cursor.fetchall()
                
                # Deliver orders sequentially within each bundle
                for bundle_id, est_duration in delivery_bundles:
                    # Get ordered stops for this bundle
                    cursor.execute("""
                        SELECT bs.order_id, bs.stop_sequence, o.picking_completed_at
                        FROM bundle_stops bs
                        JOIN orders o ON bs.order_id = o.order_id
                        WHERE bs.bundle_id = ?
                        AND o.status = 'out_for_delivery'
                        ORDER BY bs.stop_sequence
                    """, (bundle_id,))
                    stops = cursor.fetchall()
                    
                    if stops:
                        # Calculate time between stops based on total duration
                        time_per_stop = (est_duration or 30) / max(len(stops), 1)
                        
                        for order_id, sequence, picking_completed_at in stops:
                            # Each stop gets delivered at incremental times
                            from datetime import timedelta
                            completed_dt = datetime.fromisoformat(picking_completed_at) if picking_completed_at else datetime.now()
                            # Base delay (20 min to start delivery) + sequence-based increments
                            delivery_delay = timedelta(minutes=20 + (sequence * time_per_stop))
                            delivered_at = completed_dt + delivery_delay
                            
                            # Only mark as delivered if enough time has passed
                            if datetime.now() >= delivered_at:
                                cursor.execute("""
                                    UPDATE orders
                                    SET status = 'delivered', delivered_at = ?
                                    WHERE order_id = ?
                                """, (delivered_at.isoformat(), order_id))
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Delivered order {order_id[:8]}... (stop {sequence + 1})")
                        
                        # Check if all orders in this bundle are now delivered
                        cursor.execute("""
                            SELECT COUNT(*) as total,
                                   SUM(CASE WHEN o.status = 'delivered' THEN 1 ELSE 0 END) as delivered
                            FROM bundle_stops bs
                            JOIN orders o ON bs.order_id = o.order_id
                            WHERE bs.bundle_id = ?
                        """, (bundle_id,))
                        total, delivered = cursor.fetchone()
                        
                        # If all orders delivered, set bundle completed_at to last delivery time
                        if total > 0 and total == delivered:
                            cursor.execute("""
                                UPDATE bundles
                                SET completed_at = (
                                    SELECT MAX(o.delivered_at)
                                    FROM bundle_stops bs
                                    JOIN orders o ON bs.order_id = o.order_id
                                    WHERE bs.bundle_id = ?
                                )
                                WHERE bundle_id = ?
                            """, (bundle_id, bundle_id))
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Bundle {bundle_id[:8]}... completed!")
                
        except Exception as e:
            print(f"Error in delivery simulation: {e}")
            await asyncio.sleep(10)


async def order_cancellation_simulator():
    """Background task: randomly cancels orders at different lifecycle stages with decreasing probability.
    
    Cancellation rates are configurable via SimulationConfig and use the seeded
    RNG for deterministic replay when in deterministic_mode.
    """
    from database.db import get_cursor
    
    while state.delivery_simulation_active:  # Shares same activation flag as delivery
        try:
            await asyncio.sleep(15)  # Check every 15 seconds
            
            if not state.delivery_simulation_active:
                break
            
            with get_cursor() as cursor:
                # Pending orders: configurable cancellation rate (default 4%)
                cursor.execute("""
                    SELECT order_id FROM orders 
                    WHERE status = 'pending'
                    AND datetime(created_at, '+2 minutes') < datetime('now')
                """)
                pending_orders = cursor.fetchall()
                
                for (order_id,) in pending_orders:
                    if state.sim_rng.should_trigger(state.sim_config.cancellation_rate_pending):
                        cursor.execute(
                            "UPDATE orders SET status = 'canceled' WHERE order_id = ?",
                            (order_id,)
                        )
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Canceled order {order_id[:8]}... (pending stage)")
                
                # Confirmed orders: configurable cancellation rate (default 3%)
                cursor.execute("""
                    SELECT order_id FROM orders 
                    WHERE status = 'confirmed'
                    AND datetime(confirmed_at, '+5 minutes') < datetime('now')
                """)
                confirmed_orders = cursor.fetchall()
                
                for (order_id,) in confirmed_orders:
                    if state.sim_rng.should_trigger(state.sim_config.cancellation_rate_confirmed):
                        cursor.execute(
                            "UPDATE orders SET status = 'canceled' WHERE order_id = ?",
                            (order_id,)
                        )
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Canceled order {order_id[:8]}... (confirmed stage)")
                
                # Picking orders: configurable cancellation rate (default 2%)
                cursor.execute("""
                    SELECT order_id FROM orders 
                    WHERE status = 'picking'
                    AND datetime(picked_at, '+5 minutes') < datetime('now')
                """)
                picking_orders = cursor.fetchall()
                
                for (order_id,) in picking_orders:
                    if state.sim_rng.should_trigger(state.sim_config.cancellation_rate_picking):
                        cursor.execute(
                            "UPDATE orders SET status = 'canceled' WHERE order_id = ?",
                            (order_id,)
                        )
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Canceled order {order_id[:8]}... (picking stage)")
                
                # Out for delivery orders: configurable cancellation rate (default 1%)
                cursor.execute("""
                    SELECT order_id FROM orders 
                    WHERE status = 'out_for_delivery'
                    AND datetime(picked_at, '+15 minutes') < datetime('now')
                """)
                delivery_orders = cursor.fetchall()
                
                for (order_id,) in delivery_orders:
                    if state.sim_rng.should_trigger(state.sim_config.cancellation_rate_delivery):
                        cursor.execute(
                            "UPDATE orders SET status = 'canceled' WHERE order_id = ?",
                            (order_id,)
                        )
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Canceled order {order_id[:8]}... (out for delivery - rare!)")
                
        except Exception as e:
            print(f"Error in cancellation simulation: {e}")
            await asyncio.sleep(15)


async def automatic_prediction_sender():
    """Background task: sends confirmed orders to prediction service in batches."""
    while state.prediction_sending_active:
        try:
            await asyncio.sleep(state.prediction_interval_seconds)
            
            if state.prediction_sending_active:
                # Fetch and send confirmed orders
                result = await state.prediction_service.process_confirmed_orders(batch_size=10)
                
                if result["total_orders"] > 0:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Sent {result['total_orders']} confirmed orders for prediction "
                        f"({result['successful_batches']}/{result['batches_sent']} batches successful)"
                    )
        except Exception as e:
            print(f"Error sending predictions: {e}")
            await asyncio.sleep(10)


async def random_customer_generator():
    """Background task: generates customers using Poisson inter-arrival times."""
    while state.customer_generation_active:
        try:
            if state.sim_config.deterministic_mode:
                wait_seconds = state.sim_rng.exponential_wait(
                    rate_per_min=state.sim_config.customer_arrival_rate_per_min
                )
            else:
                jitter = random.uniform(0.8, 1.2)
                wait_seconds = state.customer_interval_seconds * jitter
            
            await asyncio.sleep(wait_seconds)
            
            if state.customer_generation_active:
                # Generate 1-3 customers at a time
                count = state.sim_rng.uniform_int(1, 3)
                customers = state.customer_gen.generate_batch(count)
                state.customer_gen.save_to_db(customers)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Generated {count} new customer(s)")
        except Exception as e:
            print(f"Error generating customers: {e}")
            await asyncio.sleep(10)


async def random_driver_generator():
    """Background task: generates drivers using Poisson inter-arrival times."""
    while state.driver_generation_active:
        try:
            if state.sim_config.deterministic_mode:
                wait_seconds = state.sim_rng.exponential_wait(
                    rate_per_min=state.sim_config.driver_arrival_rate_per_min
                )
            else:
                jitter = random.uniform(0.8, 1.2)
                wait_seconds = state.driver_interval_seconds * jitter
            
            await asyncio.sleep(wait_seconds)
            
            if state.driver_generation_active:
                # Generate 1-2 drivers at a time
                count = state.sim_rng.uniform_int(1, 2)
                drivers = state.driver_gen.generate_batch(count)
                state.driver_gen.save_to_db(drivers)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Generated {count} new driver(s)")
        except Exception as e:
            print(f"Error generating drivers: {e}")
            await asyncio.sleep(10)


async def random_store_generator():
    """Background task: generates stores at random intervals."""
    while state.store_generation_active:
        try:
            jitter = random.uniform(0.8, 1.2)
            await asyncio.sleep(state.store_interval_seconds * jitter)
            
            if state.store_generation_active:
                # Generate 1 store at a time
                stores = state.store_gen.generate_batch(1)
                state.store_gen.save_to_db(stores)
                
                # Generate inventory for the new store
                for store in stores:
                    inventory = state.product_gen.generate_store_inventory(store.store_id)
                    state.product_gen.save_store_products_to_db(inventory)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Generated 1 new store with inventory")
        except Exception as e:
            print(f"Error generating stores: {e}")
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    print("🚀 Starting Grocery Delivery API...")
    init_database(reset=False)
    
    # Ensure we have base data
    counts = get_table_counts()
    
    # Generate parent product catalog first
    if counts.get('parent_products', 0) == 0:
        print("📦 Generating parent product catalog...")
        products = state.product_gen.generate_parent_catalog()
        state.product_gen.save_parent_products_to_db(products)
    
    # Generate stores
    if counts.get('stores', 0) < 5:
        print("🏪 Generating stores...")
        stores = state.store_gen.generate_batch(15)  # Increased from 10
        state.store_gen.save_to_db(stores)
        
        # Generate inventory for each store
        print("📦 Generating store inventories...")
        store_ids = state.store_gen.get_all_ids()
        for store_id in store_ids:
            inventory = state.product_gen.generate_store_inventory(store_id)
            state.product_gen.save_store_products_to_db(inventory)
    
    if counts.get('customers', 0) < 10:
        print("👥 Generating initial customers...")
        customers = state.customer_gen.generate_batch(100)  # Increased from 50
        state.customer_gen.save_to_db(customers)
    
    if counts.get('drivers', 0) < 5:
        print("🚗 Generating initial drivers...")
        drivers = state.driver_gen.generate_batch(40)  # Increased from 20
        state.driver_gen.save_to_db(drivers)
    
    print("✅ API ready!")
    yield
    
    # Cleanup
    state.order_generation_active = False
    state.bundle_processing_active = False
    state.delivery_simulation_active = False
    state.prediction_sending_active = False
    state.customer_generation_active = False
    state.driver_generation_active = False
    state.store_generation_active = False
    
    for task in [state.order_task, state.bundle_task, state.delivery_task,
                 state.cancellation_task, state.prediction_task, state.customer_task, 
                 state.driver_task, state.store_task]:
        if task:
            task.cancel()
    
    print("👋 Shutting down...")


app = FastAPI(
    title="Grocery Delivery Data API",
    description="Live data generation service for ML experimentation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_middleware(request, call_next):
    """Require API key for all non-GET requests when API_KEY is set."""
    if API_KEY and request.method != "GET":
        key = request.headers.get("X-API-Key")
        if key != API_KEY:
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


# =============================================================================
# Health & Status
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "grocery-delivery-api"}


@app.get("/stats", response_model=StatsResponse, tags=["Health"])
async def get_stats():
    """Get current database statistics."""
    counts = get_table_counts()
    return StatsResponse(
        stores=counts.get("stores", 0),
        customers=counts.get("customers", 0),
        drivers=counts.get("drivers", 0),
        parent_products=counts.get("parent_products", 0),
        store_products=counts.get("store_products", 0),
        orders=counts.get("orders", 0),
        order_items=counts.get("order_items", 0),
        bundles=counts.get("bundles", 0),
    )


@app.get("/status", response_model=ServiceStatus, tags=["Health"])
async def get_service_status():
    """Get background service status."""
    return ServiceStatus(
        order_generation_active=state.order_generation_active,
        bundle_processing_active=state.bundle_processing_active,
        delivery_simulation_active=state.delivery_simulation_active,
        prediction_sending_active=state.prediction_sending_active,
        customer_generation_active=state.customer_generation_active,
        driver_generation_active=state.driver_generation_active,
        store_generation_active=state.store_generation_active,
        order_interval_seconds=state.order_interval_seconds,
        bundle_interval_seconds=state.bundle_interval_seconds,
        prediction_interval_seconds=state.prediction_interval_seconds,
        customer_interval_seconds=state.customer_interval_seconds,
        driver_interval_seconds=state.driver_interval_seconds,
        store_interval_seconds=state.store_interval_seconds,
    )


# =============================================================================
# Customer Endpoints
# =============================================================================

@app.post("/customers/generate", response_model=GenerationResponse, tags=["Customers"])
async def generate_customers(count: int = Query(default=1, ge=1, le=100)):
    """Generate new customers on demand."""
    customers = state.customer_gen.generate_batch(count)
    state.customer_gen.save_to_db(customers)
    return GenerationResponse(
        entity="customers",
        count=count,
        ids=[c.customer_id for c in customers],
    )


@app.get("/customers", tags=["Customers"])
async def list_customers(limit: int = 20, offset: int = 0):
    """List customers with pagination."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/customers/{customer_id}", tags=["Customers"])
async def get_customer(customer_id: str):
    """Get a specific customer."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        return dict(row)


# =============================================================================
# Driver Endpoints
# =============================================================================

@app.post("/drivers/generate", response_model=GenerationResponse, tags=["Drivers"])
async def generate_drivers(count: int = Query(default=1, ge=1, le=50)):
    """Generate new drivers on demand."""
    drivers = state.driver_gen.generate_batch(count)
    state.driver_gen.save_to_db(drivers)
    return GenerationResponse(
        entity="drivers",
        count=count,
        ids=[d.driver_id for d in drivers],
    )


@app.get("/drivers", tags=["Drivers"])
async def list_drivers(limit: int = 20, offset: int = 0, active_only: bool = False):
    """List drivers with pagination."""
    from database.db import get_cursor
    query = "SELECT * FROM drivers"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY rating DESC LIMIT ? OFFSET ?"
    
    with get_cursor() as cursor:
        cursor.execute(query, (limit, offset))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/drivers/{driver_id}", tags=["Drivers"])
async def get_driver(driver_id: str):
    """Get a specific driver."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Driver not found")
        return dict(row)


@app.patch("/drivers/{driver_id}/toggle", tags=["Drivers"])
async def toggle_driver_status(driver_id: str):
    """Toggle driver active status."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT is_active FROM drivers WHERE driver_id = ?", (driver_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        new_status = not row[0]
        cursor.execute(
            "UPDATE drivers SET is_active = ? WHERE driver_id = ?",
            (new_status, driver_id)
        )
        return {"driver_id": driver_id, "is_active": new_status}


# =============================================================================
# Store Endpoints
# =============================================================================

@app.post("/stores/generate", response_model=GenerationResponse, tags=["Stores"])
async def generate_stores(count: int = Query(default=1, ge=1, le=20)):
    """Generate new stores with inventory."""
    stores = state.store_gen.generate_batch(count)
    state.store_gen.save_to_db(stores)
    
    # Generate inventory for each new store
    for store in stores:
        inventory = state.product_gen.generate_store_inventory(store.store_id)
        state.product_gen.save_store_products_to_db(inventory)
    
    return GenerationResponse(
        entity="stores",
        count=count,
        ids=[s.store_id for s in stores],
    )


@app.get("/stores", tags=["Stores"])
async def list_stores(limit: int = 20, offset: int = 0, active_only: bool = False):
    """List stores with pagination."""
    from database.db import get_cursor
    query = "SELECT * FROM stores"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name LIMIT ? OFFSET ?"
    
    with get_cursor() as cursor:
        cursor.execute(query, (limit, offset))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/stores/{store_id}", tags=["Stores"])
async def get_store(store_id: str):
    """Get a specific store with product count."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Store not found")
        
        store = dict(row)
        
        # Get product count
        cursor.execute(
            "SELECT COUNT(*) FROM store_products WHERE store_id = ?",
            (store_id,)
        )
        store["product_count"] = cursor.fetchone()[0]
        
        return store


@app.get("/stores/{store_id}/products", tags=["Stores"])
async def get_store_products(
    store_id: str, 
    limit: int = 50, 
    offset: int = 0,
    category: str | None = None,
    available_only: bool = True,
):
    """Get products available at a specific store."""
    from database.db import get_cursor
    
    query = """
        SELECT sp.*, pp.name, pp.category, pp.brand, pp.unit, pp.weight_oz, pp.is_organic
        FROM store_products sp
        JOIN parent_products pp ON sp.parent_product_id = pp.parent_product_id
        WHERE sp.store_id = ?
    """
    params = [store_id]
    
    if available_only:
        query += " AND sp.is_available = 1"
    if category:
        query += " AND pp.category = ?"
        params.append(category)
    
    query += " ORDER BY pp.category, pp.name LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.post("/stores/{store_id}/restock", tags=["Stores"])
async def restock_store(store_id: str):
    """Regenerate inventory for a store (restock with different availability)."""
    from database.db import get_cursor
    
    # Verify store exists
    with get_cursor() as cursor:
        cursor.execute("SELECT store_id FROM stores WHERE store_id = ?", (store_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Store not found")
        
        # Delete existing inventory
        cursor.execute("DELETE FROM store_products WHERE store_id = ?", (store_id,))
    
    # Generate new inventory
    inventory = state.product_gen.generate_store_inventory(store_id)
    state.product_gen.save_store_products_to_db(inventory)
    
    return {"store_id": store_id, "products_added": len(inventory)}


# =============================================================================
# Product Endpoints
# =============================================================================

@app.post("/products/generate", response_model=GenerationResponse, tags=["Products"])
async def generate_products(count: int = Query(default=1, ge=1, le=50)):
    """Generate new random parent products."""
    products = state.product_gen.generate_batch(count)
    state.product_gen.save_parent_products_to_db(products)
    return GenerationResponse(
        entity="parent_products",
        count=count,
        ids=[p.parent_product_id for p in products],
    )


@app.post("/products/generate-catalog", response_model=GenerationResponse, tags=["Products"])
async def generate_product_catalog():
    """Generate full parent product catalog and distribute to all stores."""
    products = state.product_gen.generate_parent_catalog()
    state.product_gen.save_parent_products_to_db(products)
    
    # Regenerate inventory for all stores
    store_ids = state.store_gen.get_all_ids()
    for store_id in store_ids:
        from database.db import get_cursor
        with get_cursor() as cursor:
            cursor.execute("DELETE FROM store_products WHERE store_id = ?", (store_id,))
        inventory = state.product_gen.generate_store_inventory(store_id)
        state.product_gen.save_store_products_to_db(inventory)
    
    return GenerationResponse(
        entity="parent_products",
        count=len(products),
        ids=[p.parent_product_id for p in products],
    )


@app.get("/products", tags=["Products"])
async def list_products(
    limit: int = 20, 
    offset: int = 0, 
    category: str | None = None,
):
    """List parent products (canonical product catalog)."""
    from database.db import get_cursor
    query = "SELECT * FROM parent_products WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    query += " ORDER BY category, name LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/products/categories", tags=["Products"])
async def list_categories():
    """List all product categories with counts."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT category, COUNT(*) as count FROM parent_products GROUP BY category ORDER BY category"
        )
        return [{"category": row[0], "count": row[1]} for row in cursor.fetchall()]


# =============================================================================
# Order Endpoints
# =============================================================================

@app.post("/orders/generate", response_model=OrderResponse, tags=["Orders"])
async def generate_order():
    """Generate a single order immediately."""
    order, items = state.order_gen.generate_one()
    confirmed_order_ids = state.order_gen.save_to_db(([order], items))
    
    # Request prediction for confirmed orders
    if confirmed_order_ids:
        asyncio.create_task(request_prediction_for_orders(confirmed_order_ids))
    
    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status.value,
        total=order.total,
        item_count=len(items),
    )


@app.post("/orders/generate-batch", tags=["Orders"])
async def generate_orders_batch(count: int = Query(default=10, ge=1, le=100)):
    """Generate multiple orders at once."""
    orders, items = state.order_gen.generate_batch(count)
    confirmed_order_ids = state.order_gen.save_to_db((orders, items))
    
    # Request predictions for confirmed orders
    if confirmed_order_ids:
        asyncio.create_task(request_prediction_for_orders(confirmed_order_ids))
    
    return {
        "count": len(orders),
        "total_items": len(items),
        "order_ids": [o.order_id for o in orders],
    }


@app.get("/orders", tags=["Orders"])
async def list_orders(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
):
    """List orders with optional status filter."""
    from database.db import get_cursor
    query = "SELECT * FROM orders"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/orders/queue", tags=["Orders"])
async def get_order_queue():
    """Get orders waiting to be bundled (pending/confirmed)."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM orders 
               WHERE status IN ('pending', 'confirmed') 
               ORDER BY created_at"""
        )
        rows = cursor.fetchall()
        return {
            "queue_length": len(rows),
            "orders": [dict(row) for row in rows],
        }


@app.get("/orders/{order_id}", tags=["Orders"])
async def get_order(order_id: str):
    """Get order details with items."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        cursor.execute(
            """SELECT oi.*, p.name, p.category 
               FROM order_items oi 
               JOIN products p ON oi.product_id = p.product_id
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        items = cursor.fetchall()
        
        return {
            "order": dict(order),
            "items": [dict(item) for item in items],
        }


# =============================================================================
# Bundle Endpoints
# =============================================================================

@app.post("/predictions/send", response_model=PredictionResponse, tags=["Predictions"])
async def send_predictions(batch_size: int = Query(10, description="Number of orders per batch")):
    """Send confirmed orders to external prediction service in batches."""
    result = await state.prediction_service.process_confirmed_orders(batch_size=batch_size)
    return result


@app.get("/predictions/status", tags=["Predictions"])
async def get_prediction_status():
    """Get statistics about prediction coverage for confirmed orders."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_confirmed,
                SUM(CASE WHEN predicted_delivery_minutes IS NOT NULL THEN 1 ELSE 0 END) as with_predictions,
                SUM(CASE WHEN prediction_failed = 1 THEN 1 ELSE 0 END) as failed_predictions,
                SUM(CASE WHEN prediction_sent = 0 OR prediction_sent IS NULL THEN 1 ELSE 0 END) as not_sent
            FROM orders
            WHERE status = 'confirmed'
        """)
        
        row = cursor.fetchone()
        total = row[0] if row else 0
        with_pred = row[1] if row else 0
        failed = row[2] if row else 0
        not_sent = row[3] if row else 0
        
        success_rate = round(100.0 * with_pred / total, 2) if total > 0 else 0
        
        return {
            "total_confirmed_orders": total,
            "with_predictions": with_pred,
            "failed_predictions": failed,
            "not_sent": not_sent,
            "success_rate_percent": success_rate,
        }


@app.post("/bundles/process", response_model=BundleResponse, tags=["Bundles"])
async def process_bundles_now():
    """Process pending orders into bundles immediately."""
    pending = state.bundle_service.fetch_pending_orders()
    
    if not pending:
        return BundleResponse(
            bundles_created=0,
            orders_bundled=0,
            bundle_ids=[],
        )
    
    bundles = state.bundle_service.create_bundles(pending)
    bundles = state.bundle_service.assign_drivers(bundles)
    state.bundle_service.save_bundles_to_db(bundles)
    
    # Update order statuses
    from database.db import get_cursor
    with get_cursor() as cursor:
        for bundle in bundles:
            for stop in bundle.stops:
                cursor.execute(
                    "UPDATE orders SET status = 'picking', driver_id = ? WHERE order_id = ?",
                    (bundle.driver_id, stop.order_id)
                )
    
    stats = state.bundle_service.get_bundle_stats(bundles)
    
    return BundleResponse(
        bundles_created=stats["total_bundles"],
        orders_bundled=stats["total_orders"],
        bundle_ids=[b.bundle_id for b in bundles],
        avg_distance_km=stats.get("avg_distance_km"),
        avg_duration_min=stats.get("avg_duration_min"),
    )


@app.get("/bundles", tags=["Bundles"])
async def list_bundles(limit: int = 20, offset: int = 0):
    """List bundles with pagination."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM bundles ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/bundles/{bundle_id}", tags=["Bundles"])
async def get_bundle(bundle_id: str):
    """Get bundle details with stops."""
    from database.db import get_cursor
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM bundles WHERE bundle_id = ?", (bundle_id,))
        bundle = cursor.fetchone()
        if not bundle:
            raise HTTPException(status_code=404, detail="Bundle not found")
        
        cursor.execute(
            """SELECT bs.*, o.customer_id, o.total, o.delivery_latitude, o.delivery_longitude
               FROM bundle_stops bs
               JOIN orders o ON bs.order_id = o.order_id
               WHERE bs.bundle_id = ?
               ORDER BY bs.stop_sequence""",
            (bundle_id,)
        )
        stops = cursor.fetchall()
        
        return {
            "bundle": dict(bundle),
            "stops": [dict(stop) for stop in stops],
        }


# =============================================================================
# Background Service Control
# =============================================================================

@app.post("/services/orders/start", tags=["Services"])
async def start_order_generation(background_tasks: BackgroundTasks):
    """Start automatic order generation."""
    if state.order_generation_active:
        return {"status": "already_running"}
    
    state.order_generation_active = True
    state.order_task = asyncio.create_task(random_order_generator())
    return {
        "status": "started",
        "interval_seconds": state.order_interval_seconds,
    }


@app.post("/services/orders/stop", tags=["Services"])
async def stop_order_generation():
    """Stop automatic order generation."""
    state.order_generation_active = False
    if state.order_task:
        state.order_task.cancel()
        state.order_task = None
    return {"status": "stopped"}


@app.post("/services/bundles/start", tags=["Services"])
async def start_bundle_processing(background_tasks: BackgroundTasks):
    """Start periodic bundle processing."""
    if state.bundle_processing_active:
        return {"status": "already_running"}
    
    state.bundle_processing_active = True
    state.bundle_task = asyncio.create_task(periodic_bundle_processor())
    return {
        "status": "started",
        "interval_seconds": state.bundle_interval_seconds,
    }


@app.post("/services/bundles/stop", tags=["Services"])
async def stop_bundle_processing():
    """Stop periodic bundle processing."""
    state.bundle_processing_active = False
    if state.bundle_task:
        state.bundle_task.cancel()
        state.bundle_task = None
    return {"status": "stopped"}


@app.post("/services/customers/start", tags=["Services"])
async def start_customer_generation(background_tasks: BackgroundTasks):
    """Start automatic customer generation."""
    if state.customer_generation_active:
        return {"status": "already_running"}
    
    state.customer_generation_active = True
    state.customer_task = asyncio.create_task(random_customer_generator())
    return {
        "status": "started",
        "interval_seconds": state.customer_interval_seconds,
    }


@app.post("/services/customers/stop", tags=["Services"])
async def stop_customer_generation():
    """Stop automatic customer generation."""
    state.customer_generation_active = False
    if state.customer_task:
        state.customer_task.cancel()
        state.customer_task = None
    return {"status": "stopped"}


@app.post("/services/drivers/start", tags=["Services"])
async def start_driver_generation(background_tasks: BackgroundTasks):
    """Start automatic driver generation."""
    if state.driver_generation_active:
        return {"status": "already_running"}
    
    state.driver_generation_active = True
    state.driver_task = asyncio.create_task(random_driver_generator())
    return {
        "status": "started",
        "interval_seconds": state.driver_interval_seconds,
    }


@app.post("/services/drivers/stop", tags=["Services"])
async def stop_driver_generation():
    """Stop automatic driver generation."""
    state.driver_generation_active = False
    if state.driver_task:
        state.driver_task.cancel()
        state.driver_task = None
    return {"status": "stopped"}


@app.post("/services/stores/start", tags=["Services"])
async def start_store_generation(background_tasks: BackgroundTasks):
    """Start automatic store generation."""
    if state.store_generation_active:
        return {"status": "already_running"}
    
    state.store_generation_active = True
    state.store_task = asyncio.create_task(random_store_generator())
    return {
        "status": "started",
        "interval_seconds": state.store_interval_seconds,
    }


@app.post("/services/stores/stop", tags=["Services"])
async def stop_store_generation():
    """Stop automatic store generation."""
    state.store_generation_active = False
    if state.store_task:
        state.store_task.cancel()
        state.store_task = None
    return {"status": "stopped"}


@app.post("/services/predictions/start", tags=["Services"])
async def start_prediction_sending(background_tasks: BackgroundTasks):
    """Start automatic prediction sending for confirmed orders."""
    if state.prediction_sending_active:
        return {"status": "already_running"}
    
    state.prediction_sending_active = True
    state.prediction_task = asyncio.create_task(automatic_prediction_sender())
    return {
        "status": "started",
        "interval_seconds": state.prediction_interval_seconds,
        "batch_size": 10,
    }


@app.post("/services/predictions/stop", tags=["Services"])
async def stop_prediction_sending():
    """Stop automatic prediction sending."""
    state.prediction_sending_active = False
    if state.prediction_task:
        state.prediction_task.cancel()
        state.prediction_task = None
    return {"status": "stopped"}


@app.post("/services/start-all", tags=["Services"])
async def start_all_services(background_tasks: BackgroundTasks):
    """Start all background services (orders, bundles, predictions, customers, drivers, stores)."""
    results = {}
    
    if not state.order_generation_active:
        state.order_generation_active = True
        state.order_task = asyncio.create_task(random_order_generator())
        results["orders"] = "started"
    else:
        results["orders"] = "already_running"
    
    if not state.bundle_processing_active:
        state.bundle_processing_active = True
        state.bundle_task = asyncio.create_task(periodic_bundle_processor())
        results["bundles"] = "started"
    else:
        results["bundles"] = "already_running"
    
    if not state.delivery_simulation_active:
        state.delivery_simulation_active = True
        state.delivery_task = asyncio.create_task(delivery_simulator())
        state.cancellation_task = asyncio.create_task(order_cancellation_simulator())
        results["delivery_simulation"] = "started"
    else:
        results["delivery_simulation"] = "already_running"
    
    if not state.prediction_sending_active:
        state.prediction_sending_active = True
        state.prediction_task = asyncio.create_task(automatic_prediction_sender())
        results["predictions"] = "started"
    else:
        results["predictions"] = "already_running"
    
    if not state.customer_generation_active:
        state.customer_generation_active = True
        state.customer_task = asyncio.create_task(random_customer_generator())
        results["customers"] = "started"
    else:
        results["customers"] = "already_running"
    
    if not state.driver_generation_active:
        state.driver_generation_active = True
        state.driver_task = asyncio.create_task(random_driver_generator())
        results["drivers"] = "started"
    else:
        results["drivers"] = "already_running"
    
    if not state.store_generation_active:
        state.store_generation_active = True
        state.store_task = asyncio.create_task(random_store_generator())
        results["stores"] = "started"
    else:
        results["stores"] = "already_running"
    
    return results


@app.post("/services/stop-all", tags=["Services"])
async def stop_all_services():
    """Stop all background services."""
    state.order_generation_active = False
    state.bundle_processing_active = False
    state.delivery_simulation_active = False
    state.prediction_sending_active = False
    state.customer_generation_active = False
    state.driver_generation_active = False
    state.store_generation_active = False
    
    for task in [state.order_task, state.bundle_task, state.delivery_task,
                 state.cancellation_task, state.prediction_task, state.customer_task, 
                 state.driver_task, state.store_task]:
        if task:
            task.cancel()
    
    state.order_task = None
    state.bundle_task = None
    state.delivery_task = None
    state.cancellation_task = None
    state.prediction_task = None
    state.customer_task = None
    state.driver_task = None
    state.store_task = None
    
    return {"status": "all_stopped"}


@app.patch("/services/config", tags=["Services"])
async def update_service_config(config: ConfigUpdate):
    """Update service intervals."""
    if config.order_interval_seconds is not None:
        state.order_interval_seconds = config.order_interval_seconds
    if config.bundle_interval_seconds is not None:
        state.bundle_interval_seconds = config.bundle_interval_seconds
    if config.prediction_interval_seconds is not None:
        state.prediction_interval_seconds = config.prediction_interval_seconds
    if config.customer_interval_seconds is not None:
        state.customer_interval_seconds = config.customer_interval_seconds
    if config.driver_interval_seconds is not None:
        state.driver_interval_seconds = config.driver_interval_seconds
    if config.store_interval_seconds is not None:
        state.store_interval_seconds = config.store_interval_seconds
    
    return {
        "order_interval_seconds": state.order_interval_seconds,
        "bundle_interval_seconds": state.bundle_interval_seconds,
        "prediction_interval_seconds": state.prediction_interval_seconds,
        "customer_interval_seconds": state.customer_interval_seconds,
        "driver_interval_seconds": state.driver_interval_seconds,
        "store_interval_seconds": state.store_interval_seconds,
    }


# =============================================================================
# Simulation Configuration
# =============================================================================

@app.get("/simulation/config", tags=["Simulation"])
async def get_simulation_config():
    """Get current simulation configuration."""
    cfg = state.sim_config
    return {
        "master_seed": cfg.master_seed,
        "deterministic_mode": cfg.deterministic_mode,
        "arrival_rates": {
            "order_per_min": cfg.order_arrival_rate_per_min,
            "customer_per_min": cfg.customer_arrival_rate_per_min,
            "driver_per_min": cfg.driver_arrival_rate_per_min,
        },
        "latency": {
            "confirmation_delay_mean_sec": cfg.confirmation_delay_mean_sec,
            "confirmation_delay_std_sec": cfg.confirmation_delay_std_sec,
            "picking_duration_mean_min": cfg.picking_duration_mean_min,
            "picking_duration_std_min": cfg.picking_duration_std_min,
            "transit_speed_mean_kmh": cfg.transit_speed_mean_kmh,
            "transit_speed_std_kmh": cfg.transit_speed_std_kmh,
        },
        "error_rates": {
            "cancellation_pending": cfg.cancellation_rate_pending,
            "cancellation_confirmed": cfg.cancellation_rate_confirmed,
            "cancellation_picking": cfg.cancellation_rate_picking,
            "cancellation_delivery": cfg.cancellation_rate_delivery,
            "api_error_rate": cfg.api_error_rate,
            "api_error_delay_mean_ms": cfg.api_error_delay_mean_ms,
            "api_error_delay_std_ms": cfg.api_error_delay_std_ms,
        },
    }


@app.patch("/simulation/config", tags=["Simulation"])
async def update_simulation_config(config: SimulationConfigUpdate):
    """Update simulation configuration.
    
    Changes take effect immediately for running services.
    Setting master_seed + deterministic_mode=true enables full replay capability.
    """
    cfg = state.sim_config
    
    if config.master_seed is not None:
        cfg.master_seed = config.master_seed
    if config.deterministic_mode is not None:
        cfg.deterministic_mode = config.deterministic_mode
    if config.order_arrival_rate_per_min is not None:
        cfg.order_arrival_rate_per_min = config.order_arrival_rate_per_min
    if config.customer_arrival_rate_per_min is not None:
        cfg.customer_arrival_rate_per_min = config.customer_arrival_rate_per_min
    if config.driver_arrival_rate_per_min is not None:
        cfg.driver_arrival_rate_per_min = config.driver_arrival_rate_per_min
    if config.confirmation_delay_mean_sec is not None:
        cfg.confirmation_delay_mean_sec = config.confirmation_delay_mean_sec
    if config.confirmation_delay_std_sec is not None:
        cfg.confirmation_delay_std_sec = config.confirmation_delay_std_sec
    if config.picking_duration_mean_min is not None:
        cfg.picking_duration_mean_min = config.picking_duration_mean_min
    if config.picking_duration_std_min is not None:
        cfg.picking_duration_std_min = config.picking_duration_std_min
    if config.transit_speed_mean_kmh is not None:
        cfg.transit_speed_mean_kmh = config.transit_speed_mean_kmh
    if config.transit_speed_std_kmh is not None:
        cfg.transit_speed_std_kmh = config.transit_speed_std_kmh
    if config.cancellation_rate_pending is not None:
        cfg.cancellation_rate_pending = config.cancellation_rate_pending
    if config.cancellation_rate_confirmed is not None:
        cfg.cancellation_rate_confirmed = config.cancellation_rate_confirmed
    if config.cancellation_rate_picking is not None:
        cfg.cancellation_rate_picking = config.cancellation_rate_picking
    if config.cancellation_rate_delivery is not None:
        cfg.cancellation_rate_delivery = config.cancellation_rate_delivery
    if config.api_error_rate is not None:
        cfg.api_error_rate = config.api_error_rate
    if config.api_error_delay_mean_ms is not None:
        cfg.api_error_delay_mean_ms = config.api_error_delay_mean_ms
    if config.api_error_delay_std_ms is not None:
        cfg.api_error_delay_std_ms = config.api_error_delay_std_ms
    
    # Re-initialize seeded RNG and generators when seed or mode changes
    if config.master_seed is not None or config.deterministic_mode is not None:
        if cfg.deterministic_mode:
            state.sim_rng = SimulationRNG(seed=cfg.master_seed, namespace="api")
            # Reset generators so they re-init with new seeds
            state._customer_gen = None
            state._driver_gen = None
            state._product_gen = None
            state._store_gen = None
            state._order_gen = None
            # Also update the global config used by generators
            set_simulation_config(cfg)
            print(f"🔒 Deterministic mode enabled (seed={cfg.master_seed})")
        else:
            state.sim_rng = SimulationRNG(seed=None, namespace="api")
            state._customer_gen = None
            state._driver_gen = None
            state._product_gen = None
            state._store_gen = None
            state._order_gen = None
            set_simulation_config(cfg)
            print(f"🔓 Non-deterministic mode enabled")
    
    return await get_simulation_config()


# =============================================================================
# Database Management
# =============================================================================

@app.post("/admin/reset", tags=["Admin"])
async def reset_database(confirm: bool = Query(default=False)):
    """Reset the database (requires confirm=true)."""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Add ?confirm=true to reset the database"
        )
    
    # Stop services first
    state.order_generation_active = False
    state.bundle_processing_active = False
    
    init_database(reset=True)
    
    # Regenerate base data
    products = state.product_gen.generate_catalog()
    state.product_gen.save_to_db(products)
    
    customers = state.customer_gen.generate_batch(50)
    state.customer_gen.save_to_db(customers)
    
    drivers = state.driver_gen.generate_batch(20)
    state.driver_gen.save_to_db(drivers)
    
    return {"status": "reset_complete", "stats": get_table_counts()}
