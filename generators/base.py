from abc import ABC, abstractmethod
from faker import Faker
import random

class BaseGenerator(ABC):
    def __init__(self, seed: int | None = 42):
        self.fake = Faker()
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)
    
    @abstractmethod
    def generate_one(self):
        pass
    
    @abstractmethod
    def generate_batch(self, count: int) -> list:
        pass
    
    @abstractmethod
    def save_to_db(self, records: list):
        pass
