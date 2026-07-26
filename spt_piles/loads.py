"""Esforços (cargas) de fundação por elemento (pilar, bloco ou estaca isolada).

IMPORTANTE: a carga informada deve ser a carga CARACTERÍSTICA (de serviço,
Nk - combinação quase-permanente/ELS), não a carga de cálculo majorada
(Nd/ELU). Os métodos semi-empíricos usados neste software (Décourt-Quaresma,
Aoki-Velloso) calculam Qadm já aplicando um fator de segurança global sobre a
capacidade última do solo, e essa comparação pressupõe carga característica.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FoundationLoad:
    element_id: str
    characteristic_load_kn: float
    n_piles: int = 1

    def __post_init__(self) -> None:
        if not self.element_id:
            raise ValueError("Identificação do elemento não pode ser vazia.")
        if self.characteristic_load_kn <= 0:
            raise ValueError("Carga característica deve ser maior que zero.")
        if self.n_piles <= 0:
            raise ValueError("Número de estacas do bloco deve ser maior que zero.")

    @property
    def load_per_pile_kn(self) -> float:
        return self.characteristic_load_kn / self.n_piles


@dataclass
class LoadSet:
    items: list[FoundationLoad] = field(default_factory=list)

    def add(self, element_id: str, characteristic_load_kn: float, n_piles: int = 1) -> None:
        self.items.append(FoundationLoad(element_id, characteristic_load_kn, n_piles))

    def clear(self) -> None:
        self.items.clear()

    def is_valid(self) -> bool:
        return len(self.items) > 0
