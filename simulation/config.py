"""
Simulation Configuration

Central configuration for deterministic simulation parameters.
All random behavior flows from a single master seed, making the entire
simulation reproducible when the same seed is used.
"""

from dataclasses import dataclass, field


@dataclass
class SimulationConfig:
    """Master configuration controlling all simulation randomness and behavior.
    
    The core principle: given the same seed and the same config, the system
    produces the exact same sequence of events every time.
    
    Attributes:
        master_seed: The root seed from which all sub-seeds derive. Using the
            same master_seed guarantees identical simulation runs.
        
        # --- Arrival Rate (Poisson Process) ---
        order_arrival_rate_per_min: Average orders per minute (λ for Poisson process).
            Inter-arrival times follow Exponential(1/λ) distribution.
        customer_arrival_rate_per_min: Average new customers per minute.
        driver_arrival_rate_per_min: Average new drivers per minute.
        
        # --- Latency / Duration (Gaussian) ---
        confirmation_delay_mean_sec: Mean delay in seconds for order confirmation.
        confirmation_delay_std_sec: Std deviation of confirmation delay.
        picking_duration_mean_min: Mean picking duration in minutes.
        picking_duration_std_min: Std deviation of picking duration.
        transit_speed_mean_kmh: Mean transit speed in km/h.
        transit_speed_std_kmh: Std deviation of transit speed.
        
        # --- Error / Cancellation Rates (Uniform threshold) ---
        cancellation_rate_pending: Probability of canceling at pending stage.
        cancellation_rate_confirmed: Probability at confirmed stage.
        cancellation_rate_picking: Probability at picking stage.
        cancellation_rate_delivery: Probability at out-for-delivery stage.
        api_error_rate: Probability of simulated API 500 errors.
        api_error_delay_mean_ms: Mean delay in ms for error responses (Gaussian).
        api_error_delay_std_ms: Std deviation of error response delay.
        
        # --- Feature flags ---
        deterministic_mode: When True, all generators use seeded RNG. When False,
            generators use unseeded (truly random) RNG for live/demo mode.
    """
    
    # Master seed
    master_seed: int = 42
    
    # Arrival rates (Poisson process λ)
    order_arrival_rate_per_min: float = 6.0       # ~6 orders/min = 1 every 10s
    customer_arrival_rate_per_min: float = 0.5    # ~1 every 2 min
    driver_arrival_rate_per_min: float = 0.2      # ~1 every 5 min
    
    # Confirmation delay (Gaussian, in seconds)
    confirmation_delay_mean_sec: float = 120.0    # 2 min average
    confirmation_delay_std_sec: float = 45.0      # ±45s jitter
    
    # Picking duration (Gaussian, in minutes)
    picking_duration_mean_min: float = 15.0       # 15 min average
    picking_duration_std_min: float = 5.0         # ±5 min jitter
    
    # Transit speed (Gaussian, in km/h)
    transit_speed_mean_kmh: float = 24.0          # ~24 km/h city driving
    transit_speed_std_kmh: float = 6.0            # ±6 km/h variation
    
    # Cancellation rates (uniform threshold)
    cancellation_rate_pending: float = 0.04       # 4% at pending
    cancellation_rate_confirmed: float = 0.03     # 3% at confirmed
    cancellation_rate_picking: float = 0.02       # 2% at picking
    cancellation_rate_delivery: float = 0.01      # 1% at delivery
    
    # Simulated API error injection
    api_error_rate: float = 0.0                   # 0% by default, set >0 to inject
    api_error_delay_mean_ms: float = 500.0        # 500ms mean error latency
    api_error_delay_std_ms: float = 100.0         # ±100ms jitter
    
    # Mode
    deterministic_mode: bool = True
    
    def derive_seed(self, namespace: str) -> int:
        """Derive a deterministic sub-seed for a specific generator/subsystem.
        
        This ensures each subsystem gets its own independent but reproducible
        PRNG stream, so changes in one subsystem don't cascade to others.
        
        Args:
            namespace: Identifier like 'customers', 'orders', 'drivers', etc.
        
        Returns:
            A deterministic seed derived from master_seed + namespace.
        """
        return hash((self.master_seed, namespace)) % (2**31)
