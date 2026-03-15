from abc import ABC, abstractmethod
from faker import Faker
import random

from simulation.rng import SimulationRNG
from simulation.config import SimulationConfig


# Global simulation config (shared across all generators)
_simulation_config: SimulationConfig | None = None


def get_simulation_config() -> SimulationConfig:
    """Get the global simulation config, creating default if needed."""
    global _simulation_config
    if _simulation_config is None:
        _simulation_config = SimulationConfig()
    return _simulation_config


def set_simulation_config(config: SimulationConfig):
    """Set the global simulation config."""
    global _simulation_config
    _simulation_config = config


class BaseGenerator(ABC):
    def __init__(self, seed: int | None = 42):
        self.fake = Faker()
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)
        
        # Create a SimulationRNG for this generator using the class name as namespace
        namespace = self.__class__.__name__.lower()
        self.rng = SimulationRNG(seed=seed, namespace=namespace)
        
        # Also seed stdlib random for compatibility with existing code paths
        if seed is not None:
            self.rng.seed_stdlib()
    
    @property
    def sim_config(self) -> SimulationConfig:
        """Access the global simulation config."""
        return get_simulation_config()
    
    @abstractmethod
    def generate_one(self):
        pass
    
    @abstractmethod
    def generate_batch(self, count: int) -> list:
        pass
    
    @abstractmethod
    def save_to_db(self, records: list):
        pass
