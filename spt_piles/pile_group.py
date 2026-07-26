"""Cálculo em lote da profundidade de cada estaca a partir dos esforços
importados, com opção de uniformização (agrupamento) das profundidades.

A uniformização agrupa as estacas ordenadas pela profundidade individual
necessária em N grupos contíguos; cada grupo adota a maior profundidade
entre as estacas que o compõem, reduzindo a quantidade de profundidades
distintas usadas na obra (mais estacas ficam com folga, nunca com déficit).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import depth_solver as ds
from .loads import FoundationLoad
from .models import PileGeometry, SPTProfile


@dataclass
class PileDesign:
    element_id: str
    n_piles: int
    load_per_pile_kn: float
    individual_required_depth_m: float | None
    adopted_depth_m: float | None = None
    group_label: str | None = None


def compute_individual_designs(
    loads: list[FoundationLoad],
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    method: str = ds.METHOD_BOTH,
    safety_factor: float = 2.0,
    min_depth_m: float = 1.0,
) -> list[PileDesign]:
    """Calcula, para cada elemento importado, a profundidade mínima
    individual necessária para sua carga por estaca (carga do elemento
    dividida pelo número de estacas do bloco)."""

    if not loads:
        raise ValueError("Nenhum esforço de fundação foi informado.")

    designs: list[PileDesign] = []
    for load in loads:
        result = ds.solve(
            profile,
            geometry,
            pile_type,
            load.load_per_pile_kn,
            method=method,
            safety_factor=safety_factor,
            min_depth_m=min_depth_m,
        )
        designs.append(
            PileDesign(
                element_id=load.element_id,
                n_piles=load.n_piles,
                load_per_pile_kn=load.load_per_pile_kn,
                individual_required_depth_m=result.required_depth_m,
            )
        )
    return designs


def apply_no_uniformization(designs: list[PileDesign]) -> list[PileDesign]:
    """Cada estaca adota sua própria profundidade individual (sem agrupamento)."""

    for d in designs:
        d.adopted_depth_m = d.individual_required_depth_m
        d.group_label = None
    return designs


def apply_group_uniformization(designs: list[PileDesign], n_groups: int) -> list[PileDesign]:
    """Agrupa as estacas viáveis em `n_groups` grupos (ou menos, se houver menos
    estacas viáveis do que grupos pedidos), adotando a maior profundidade
    individual de cada grupo para todas as estacas daquele grupo."""

    if n_groups < 1:
        raise ValueError("Número de grupos deve ser ao menos 1.")

    for d in designs:
        if d.individual_required_depth_m is None:
            d.adopted_depth_m = None
            d.group_label = "Inviável"

    feasible = [d for d in designs if d.individual_required_depth_m is not None]
    feasible.sort(key=lambda d: d.individual_required_depth_m)

    n = len(feasible)
    groups = min(n_groups, n)
    for g in range(groups):
        start = g * n // groups
        end = (g + 1) * n // groups
        chunk = feasible[start:end]
        adopted = max(d.individual_required_depth_m for d in chunk)
        label = f"Grupo {g + 1} ({adopted:.2f} m)"
        for d in chunk:
            d.adopted_depth_m = adopted
            d.group_label = label

    return designs
