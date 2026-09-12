"""Contextos pseudoaleatórios isolados por componente."""

from dataclasses import dataclass
from hashlib import sha256
from random import Random

from faker import Faker


def derive_component_seed(global_seed: int, component: str) -> int:
    """Derive uma seed estável sem depender de ``hash()`` do Python."""
    material = f"banking-data-generator:v1:{global_seed}:{component}".encode()
    return int.from_bytes(sha256(material).digest(), byteorder="big")


@dataclass(frozen=True, slots=True)
class GenerationContext:
    """Estado pseudoaleatório exclusivo de um componente de geração."""

    random: Random
    faker: Faker

    @classmethod
    def create(cls, global_seed: int, component: str) -> "GenerationContext":
        component_seed = derive_component_seed(global_seed, component)
        faker = Faker("pt_BR")
        faker.seed_instance(component_seed)
        return cls(random=Random(component_seed), faker=faker)
