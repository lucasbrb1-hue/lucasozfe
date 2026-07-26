"""Fatores empíricos por tipo de estaca para os métodos SPT.

Fontes de referência:
  - Décourt & Quaresma (1978), revisão Décourt (1996): fatores alpha (ponta)
    e beta (fuste).
  - Aoki & Velloso (1975), revisão de fatores F1/F2 por Laprovitera (1988)
    e Monteiro, amplamente reproduzida em bibliografia de fundações.

Os valores para "estaca Strauss" e, em menor grau, "hélice contínua" variam
entre autores/edições. Os valores aqui adotados são referências usuais de
mercado e DEVEM ser confirmados/calibrados pelo engenheiro responsável antes
do uso em projeto executivo.
"""

from __future__ import annotations

from typing import NamedTuple

PILE_TYPES: dict[str, str] = {
    "helice_continua": "Hélice contínua",
    "escavada": "Escavada (broca)",
    "pre_moldada": "Pré-moldada cravada",
    "strauss": "Strauss",
}


class DQFactors(NamedTuple):
    alpha: float  # fator de ponta
    beta: float   # fator de fuste


# alpha/beta por tipo de estaca, diferenciando solo argiloso x demais solos.
DQ_FACTORS: dict[str, dict[str, DQFactors]] = {
    "escavada": {
        "argila": DQFactors(0.85, 0.80),
        "outros": DQFactors(0.85, 0.80),
    },
    "helice_continua": {
        "argila": DQFactors(0.30, 1.00),
        "outros": DQFactors(0.30, 1.00),
    },
    "pre_moldada": {
        "argila": DQFactors(1.00, 1.00),
        "outros": DQFactors(1.00, 1.00),
    },
    # Strauss: sem tabela oficial amplamente publicada; aproximado por
    # escavada com revestimento recuperável (valor de referência - validar).
    "strauss": {
        "argila": DQFactors(0.85, 0.90),
        "outros": DQFactors(0.85, 1.00),
    },
}


class AVFactors(NamedTuple):
    f1: float
    f2: float


AV_FACTORS: dict[str, AVFactors] = {
    "pre_moldada": AVFactors(2.5, 5.0),
    "escavada": AVFactors(3.0, 6.0),
    "helice_continua": AVFactors(2.0, 4.0),
    # Valor de referência (Laprovitera) - validar com literatura/calibração local.
    "strauss": AVFactors(4.2, 3.9),
}


def dq_factors(pile_type: str, dq_soil_group: str) -> DQFactors:
    group_key = "argila" if dq_soil_group == "argila" else "outros"
    return DQ_FACTORS[pile_type][group_key]


def av_factors(pile_type: str) -> AVFactors:
    return AV_FACTORS[pile_type]
