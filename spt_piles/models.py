"""Estruturas de dados básicas: pontos de sondagem SPT e perfil."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .soil_data import get_soil


@dataclass
class SPTPoint:
    """Um golpe/leitura de SPT em uma determinada profundidade."""

    depth_m: float
    n_spt: int
    soil_key: str

    def __post_init__(self) -> None:
        if self.depth_m <= 0:
            raise ValueError("Profundidade deve ser maior que zero.")
        if self.n_spt < 0:
            raise ValueError("N-SPT não pode ser negativo.")
        get_soil(self.soil_key)  # valida existência do tipo de solo


@dataclass
class SPTProfile:
    """Conjunto ordenado de leituras de SPT de uma sondagem (furo)."""

    points: list[SPTPoint] = field(default_factory=list)

    def add(self, depth_m: float, n_spt: int, soil_key: str) -> None:
        self.points.append(SPTPoint(depth_m, n_spt, soil_key))
        self.points.sort(key=lambda p: p.depth_m)

    def clear(self) -> None:
        self.points.clear()

    @property
    def max_depth(self) -> float:
        return max((p.depth_m for p in self.points), default=0.0)

    def is_valid(self) -> bool:
        return len(self.points) >= 2

    def n_at_or_before(self, depth_m: float) -> SPTPoint | None:
        candidates = [p for p in self.points if p.depth_m <= depth_m + 1e-9]
        return candidates[-1] if candidates else None

    def points_up_to(self, depth_m: float) -> list[SPTPoint]:
        return [p for p in self.points if p.depth_m <= depth_m + 1e-9]

    def tip_reference(self, depth_m: float) -> tuple[SPTPoint, list[SPTPoint]]:
        """Retorna o ponto mais próximo da profundidade (ponta) e os até 3
        pontos usados na média de ponta (o próprio, o anterior e o
        seguinte), conforme prática usual do método Décourt-Quaresma."""

        if not self.points:
            raise ValueError("Perfil de SPT vazio.")
        idx_candidates = [(abs(p.depth_m - depth_m), i) for i, p in enumerate(self.points)]
        idx_candidates.sort()
        tip_idx = idx_candidates[0][1]
        tip_point = self.points[tip_idx]
        window = self.points[max(0, tip_idx - 1): tip_idx + 2]
        return tip_point, window


PILE_DIAMETERS_CM = [20, 25, 30, 35, 40, 50, 60, 70, 80, 100, 120]


@dataclass
class PileGeometry:
    diameter_cm: float

    @property
    def diameter_m(self) -> float:
        return self.diameter_cm / 100.0

    @property
    def area_m2(self) -> float:
        return math.pi * (self.diameter_m ** 2) / 4.0

    @property
    def perimeter_m(self) -> float:
        return math.pi * self.diameter_m
