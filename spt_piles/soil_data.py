"""Tabelas de solo usadas pelos métodos de Aoki-Velloso e Décourt-Quaresma.

Os coeficientes K e alpha (Aoki-Velloso, 1975) são os classicamente publicados
na literatura técnica brasileira. Valores de referência - a calibração local
do solo (ensaios complementares, experiência regional) sempre prevalece sobre
valores tabelados genéricos.
"""

from __future__ import annotations

from typing import NamedTuple


class SoilInfo(NamedTuple):
    label: str      # rótulo em português para a interface
    k_mpa: float     # coeficiente K (Aoki-Velloso), em MPa
    alpha_pct: float  # razão de atrito alpha (Aoki-Velloso), em %
    dq_group: str    # grupo equivalente para Décourt-Quaresma: "argila" | "silte" | "silte_arenoso" | "areia"


# Tabela clássica de Aoki & Velloso (1975), K em MPa e alpha em %.
SOIL_TABLE: dict[str, SoilInfo] = {
    "areia": SoilInfo("Areia", 1.00, 1.4, "areia"),
    "areia_siltosa": SoilInfo("Areia siltosa", 0.80, 2.0, "areia"),
    "areia_silto_argilosa": SoilInfo("Areia silto-argilosa", 0.70, 2.4, "areia"),
    "areia_argilosa": SoilInfo("Areia argilosa", 0.60, 3.0, "areia"),
    "areia_argilo_siltosa": SoilInfo("Areia argilo-siltosa", 0.50, 2.8, "areia"),
    "silte": SoilInfo("Silte", 0.40, 3.0, "silte"),
    "silte_arenoso": SoilInfo("Silte arenoso", 0.55, 2.2, "silte_arenoso"),
    "silte_areno_argiloso": SoilInfo("Silte areno-argiloso", 0.45, 2.8, "silte_arenoso"),
    "silte_argiloso": SoilInfo("Silte argiloso", 0.23, 3.4, "silte"),
    "silte_argilo_arenoso": SoilInfo("Silte argilo-arenoso", 0.25, 3.0, "silte"),
    "argila": SoilInfo("Argila", 0.20, 6.0, "argila"),
    "argila_arenosa": SoilInfo("Argila arenosa", 0.35, 2.4, "argila"),
    "argila_areno_siltosa": SoilInfo("Argila areno-siltosa", 0.30, 2.8, "argila"),
    "argila_siltosa": SoilInfo("Argila siltosa", 0.22, 4.0, "argila"),
    "argila_silto_arenosa": SoilInfo("Argila silto-arenosa", 0.25, 3.0, "argila"),
}

# Coeficiente K (kPa) para Décourt-Quaresma por grupo de solo.
DQ_K_KPA: dict[str, float] = {
    "argila": 120.0,
    "silte": 200.0,
    "silte_arenoso": 250.0,
    "areia": 400.0,
}


def soil_options() -> list[tuple[str, str]]:
    """Retorna lista (chave, rótulo) para preencher combobox da interface."""
    return [(key, info.label) for key, info in SOIL_TABLE.items()]


def get_soil(key: str) -> SoilInfo:
    try:
        return SOIL_TABLE[key]
    except KeyError as exc:
        raise ValueError(f"Tipo de solo desconhecido: {key!r}") from exc


def dq_k_for_soil(key: str) -> float:
    return DQ_K_KPA[get_soil(key).dq_group]
