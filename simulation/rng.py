"""
Seeded Random Number Generator (RNG) Provider

Wraps numpy's PRNG to provide reproducible random distributions:
- Poisson process (exponential inter-arrival times)
- Gaussian / Normal (latency jitter, speed variation)
- Uniform (error injection, weighted choices)
- Beta (ratings, skewed distributions)

Each SimulationRNG instance is independently seeded, so different subsystems
don't interfere with each other's random streams.
"""

import random as stdlib_random
import numpy as np
from typing import Sequence


class SimulationRNG:
    """Independently seeded random number generator for deterministic simulation.
    
    Uses numpy's Generator (PCG64 algorithm) for high-quality, reproducible
    random number generation with proper statistical distribution support.
    
    Also seeds Python's stdlib `random` and `Faker` for compatibility with
    existing code that uses those modules.
    
    Example:
        rng = SimulationRNG(seed=42, namespace="orders")
        
        # Poisson inter-arrival: average 6 orders/minute
        wait = rng.exponential_wait(rate_per_min=6.0)
        
        # Gaussian latency: 50ms ± 20ms
        delay = rng.gaussian(mean=50.0, std=20.0, minimum=10.0)
        
        # Error injection: 5% of the time
        if rng.should_trigger(probability=0.05):
            raise SimulatedError()
    """
    
    def __init__(self, seed: int | None = None, namespace: str = "default"):
        """Initialize with optional seed.
        
        Args:
            seed: If provided, creates deterministic RNG. If None, uses entropy.
            namespace: Label for this RNG stream (for debugging/logging).
        """
        self.namespace = namespace
        self.seed = seed
        
        if seed is not None:
            # Derive a unique seed per namespace so different subsystems
            # get independent streams from the same master seed
            derived = hash((seed, namespace)) % (2**31)
            self._rng = np.random.default_rng(derived)
            self._stdlib_seed = derived
        else:
            self._rng = np.random.default_rng()
            self._stdlib_seed = None
    
    def seed_stdlib(self):
        """Seed Python's stdlib random module for compatibility.
        
        Call this before using code that relies on `random.random()`,
        `random.choices()`, etc. (e.g., Faker, existing generators).
        """
        if self._stdlib_seed is not None:
            stdlib_random.seed(self._stdlib_seed)
    
    # -------------------------------------------------------------------------
    # Poisson Process / Exponential (Arrival Rates)
    # -------------------------------------------------------------------------
    
    def exponential_wait(self, rate_per_min: float) -> float:
        """Generate inter-arrival time from Poisson process.
        
        Models the time between events when events occur at a constant
        average rate (e.g., order arrivals, customer signups).
        
        Args:
            rate_per_min: Average events per minute (λ). 
                         E.g., 6.0 means ~6 events per minute.
        
        Returns:
            Wait time in seconds until next event.
        """
        if rate_per_min <= 0:
            return float('inf')
        # Exponential distribution: mean = 1/λ (converted to seconds)
        mean_interval_sec = 60.0 / rate_per_min
        return float(self._rng.exponential(mean_interval_sec))
    
    def poisson_count(self, rate: float) -> int:
        """Generate count of events in a time window.
        
        Args:
            rate: Expected number of events (λ) in the window.
        
        Returns:
            Number of events that occurred.
        """
        return int(self._rng.poisson(rate))
    
    # -------------------------------------------------------------------------
    # Gaussian / Normal (Latency, Speed, Duration)
    # -------------------------------------------------------------------------
    
    def gaussian(self, mean: float, std: float, minimum: float | None = None,
                 maximum: float | None = None) -> float:
        """Generate a value from normal distribution with optional clamping.
        
        Use for modeling variable latency, speed, duration, etc.
        
        Args:
            mean: Center of the distribution.
            std: Standard deviation (spread).
            minimum: Floor value (clamp). None = no floor.
            maximum: Ceiling value (clamp). None = no ceiling.
        
        Returns:
            Sampled value, clamped to [minimum, maximum].
        """
        value = float(self._rng.normal(mean, std))
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value
    
    def gaussian_int(self, mean: float, std: float, minimum: int = 0,
                     maximum: int | None = None) -> int:
        """Generate an integer from a rounded normal distribution."""
        return int(round(self.gaussian(mean, std, float(minimum),
                                        float(maximum) if maximum else None)))
    
    # -------------------------------------------------------------------------
    # Uniform (Error injection, probability checks)
    # -------------------------------------------------------------------------
    
    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """Generate a uniform random float in [low, high)."""
        return float(self._rng.uniform(low, high))
    
    def uniform_int(self, low: int, high: int) -> int:
        """Generate a uniform random integer in [low, high] (inclusive)."""
        return int(self._rng.integers(low, high + 1))
    
    def should_trigger(self, probability: float) -> bool:
        """Probabilistic check (coin flip with bias).
        
        Use for error injection, cancellation decisions, etc.
        
        Args:
            probability: Chance of returning True (0.0 to 1.0).
                        E.g., 0.05 = 5% chance.
        
        Returns:
            True with the given probability.
        """
        return self.uniform() < probability
    
    # -------------------------------------------------------------------------
    # Weighted / Categorical choices
    # -------------------------------------------------------------------------
    
    def choice(self, items: Sequence, weights: Sequence[float] | None = None):
        """Choose a single item, optionally weighted.
        
        Args:
            items: Sequence to choose from.
            weights: Optional probability weights (will be normalized).
        
        Returns:
            Selected item.
        """
        if weights is not None:
            weights_arr = np.array(weights, dtype=float)
            weights_arr /= weights_arr.sum()  # Normalize
            idx = self._rng.choice(len(items), p=weights_arr)
        else:
            idx = self._rng.integers(0, len(items))
        return items[idx]
    
    def choices(self, items: Sequence, weights: Sequence[float] | None = None,
                k: int = 1) -> list:
        """Choose k items with replacement, optionally weighted."""
        if weights is not None:
            weights_arr = np.array(weights, dtype=float)
            weights_arr /= weights_arr.sum()
            indices = self._rng.choice(len(items), size=k, replace=True, p=weights_arr)
        else:
            indices = self._rng.integers(0, len(items), size=k)
        return [items[i] for i in indices]
    
    def sample(self, items: Sequence, k: int) -> list:
        """Choose k items without replacement."""
        k = min(k, len(items))
        indices = self._rng.choice(len(items), size=k, replace=False)
        return [items[i] for i in indices]
    
    # -------------------------------------------------------------------------
    # Beta distribution (ratings, skewed proportions)
    # -------------------------------------------------------------------------
    
    def beta(self, a: float, b: float) -> float:
        """Generate from Beta distribution. Useful for ratings, proportions."""
        return float(self._rng.beta(a, b))
    
    # -------------------------------------------------------------------------
    # Convenience: random float (drop-in for random.random())
    # -------------------------------------------------------------------------
    
    def random(self) -> float:
        """Generate a random float in [0, 1). Drop-in for random.random()."""
        return float(self._rng.random())
