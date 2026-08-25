"""Esforços (cargas) de fundação por elemento (pilar, bloco ou estaca isolada).

IMPORTANTE: os valores informados devem ser os esforços CARACTERÍSTICOS (de
serviço, combinação quase-permanente/ELS), não os esforços de cálculo
majorados (Nd/Md/Vd, ELU):
  - A carga axial (Nk) é comparada com a capacidade admissível do solo
    (Qadm), que já aplica um fator de segurança geotécnico global sobre a
    capacidade última - essa comparação pressupõe carga característica.
  - O momento (Mk) e o cortante (Hk), quando informados, são majorados
    internamente por um fator γf (ver reinforcement.py/design_reinforcement)
    para o dimensionamento estrutural da armadura (flexo-compressão N-M e
    cisalhamento V) - não informe aqui valores já majorados.

Momento e cortante são OPCIONAIS: sem eles, a armadura da estaca é
dimensionada apenas pela taxa mínima (válido para estacas essencialmente à
compressão axial). Quando um bloco tem mais de uma estaca, a mesma premissa
de distribuição igual usada para a carga axial é aplicada a M e H.

ENVOLTÓRIA DE COMBINAÇÕES: softwares como o Eberick não fornecem um único
Mk/Hk por elemento - fornecem uma tabela com dezenas de COMBINAÇÕES de
carregamento (ex: "G1+G2+0.5Q+0.6V1+0.93D1"), cada uma com seu próprio N,
Mx, My, Vx, Vy CONCOMITANTES (do mesmo carregamento). A combinação com maior
N nem sempre é a mais crítica para a armadura (flexo-compressão), por isso
`FoundationLoad.combinations`, quando preenchido, guarda a envoltória
completa - o dimensionamento estrutural (pile_group.compute_batch_reinforcement)
verifica a armadura contra TODAS as combinações e reporta a mais exigente
como governante. NUNCA misture valores (N, Mx, My, Vx, Vy) de combinações
diferentes como se fossem concomitantes - isso gera um esforço fisicamente
inconsistente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class LoadCombination:
    """Uma linha da envoltória de combinações de um elemento: N, Mx, My, Vx,
    Vy CONCOMITANTES (todos do mesmo carregamento/combinação - nunca misturar
    com valores de outra combinação)."""

    label: str
    n_kn: float
    moment_x_knm: float = 0.0
    moment_y_knm: float = 0.0
    shear_x_kn: float = 0.0
    shear_y_kn: float = 0.0

    @property
    def moment_kn_m(self) -> float:
        return math.hypot(self.moment_x_knm, self.moment_y_knm)

    @property
    def shear_kn(self) -> float:
        return math.hypot(self.shear_x_kn, self.shear_y_kn)


@dataclass
class FoundationLoad:
    element_id: str
    characteristic_load_kn: float
    n_piles: int = 1
    moment_kn_m: float | None = None
    shear_kn: float | None = None
    # Componentes ortogonais originais (Mx, My, Fx, Fy), quando disponíveis -
    # guardados apenas para rastreabilidade/conferência; o cálculo usa sempre
    # moment_kn_m/shear_kn (a resultante já combinada).
    moment_x_knm: float | None = None
    moment_y_knm: float | None = None
    shear_x_kn: float | None = None
    shear_y_kn: float | None = None
    # Envoltória completa de combinações (opcional) - ver docstring do módulo.
    # Quando presente, o dimensionamento estrutural usa TODAS as combinações
    # (não apenas moment_kn_m/shear_kn acima) para achar a governante.
    combinations: list[LoadCombination] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.element_id:
            raise ValueError("Identificação do elemento não pode ser vazia.")
        if self.characteristic_load_kn <= 0:
            raise ValueError("Carga característica deve ser maior que zero.")
        if self.n_piles <= 0:
            raise ValueError("Número de estacas do bloco deve ser maior que zero.")
        if self.moment_kn_m is not None and self.moment_kn_m < 0:
            raise ValueError("Momento fletor não pode ser negativo (informe o valor absoluto).")
        if self.shear_kn is not None and self.shear_kn < 0:
            raise ValueError("Força cortante não pode ser negativa (informe o valor absoluto).")

    @property
    def load_per_pile_kn(self) -> float:
        return self.characteristic_load_kn / self.n_piles

    @property
    def moment_per_pile_knm(self) -> float | None:
        return self.moment_kn_m / self.n_piles if self.moment_kn_m is not None else None

    @property
    def shear_per_pile_kn(self) -> float | None:
        return self.shear_kn / self.n_piles if self.shear_kn is not None else None

    def combinations_per_pile(self) -> list[LoadCombination]:
        """Cada combinação da envoltória, com N/Mx/My/Vx/Vy divididos
        igualmente entre as estacas do bloco (mesma premissa simplificadora
        já usada para characteristic_load_kn/moment_kn_m/shear_kn)."""

        return [
            LoadCombination(
                label=c.label,
                n_kn=c.n_kn / self.n_piles,
                moment_x_knm=c.moment_x_knm / self.n_piles,
                moment_y_knm=c.moment_y_knm / self.n_piles,
                shear_x_kn=c.shear_x_kn / self.n_piles,
                shear_y_kn=c.shear_y_kn / self.n_piles,
            )
            for c in self.combinations
        ]


@dataclass
class LoadSet:
    items: list[FoundationLoad] = field(default_factory=list)

    def add(
        self,
        element_id: str,
        characteristic_load_kn: float,
        n_piles: int = 1,
        moment_kn_m: float | None = None,
        shear_kn: float | None = None,
        moment_x_knm: float | None = None,
        moment_y_knm: float | None = None,
        shear_x_kn: float | None = None,
        shear_y_kn: float | None = None,
        combinations: list[LoadCombination] | None = None,
    ) -> None:
        self.items.append(
            FoundationLoad(
                element_id, characteristic_load_kn, n_piles, moment_kn_m, shear_kn,
                moment_x_knm, moment_y_knm, shear_x_kn, shear_y_kn,
                combinations or [],
            )
        )

    def clear(self) -> None:
        self.items.clear()

    def is_valid(self) -> bool:
        return len(self.items) > 0

    def has_moment_data(self) -> bool:
        return any(item.moment_kn_m is not None or item.combinations for item in self.items)
