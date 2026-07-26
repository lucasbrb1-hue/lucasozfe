"""Dimensionamento de armação de estacas moldadas in loco (longitudinal e
transversal), com base em práticas usuais associadas à NBR 6118 (Projeto de
estruturas de concreto) e NBR 6122 (Projeto e execução de fundações).

IMPORTANTE: estacas moldadas em concreto trabalhando à compressão axial são,
em geral, dimensionadas estruturalmente pela armadura mínima (a resistência
à compressão fica a cargo do concreto). Este módulo NÃO realiza verificação
de flexão composta, esforços horizontais, sismo ou choque - apenas o cálculo
de armadura mínima usual e uma sugestão construtiva de bitolas/estribos.
Projeto executivo deve ser assinado por engenheiro responsável (ART/RRT).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import PileGeometry

BAR_DIAMETERS_MM = [8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]
STIRRUP_DIAMETERS_MM = [5.0, 6.3, 8.0, 10.0]

MIN_BARS = 6
MAX_BARS = 24
DEFAULT_MAX_AGGREGATE_CM = 1.9  # brita 1, valor usual


def default_rho_min_pct(diameter_cm: float) -> float:
    """Taxa mínima de armadura longitudinal (% da área de concreto), valor
    de referência usual de mercado - confirmar com a norma vigente e o
    caderno de encargos do projeto específico."""

    if diameter_cm <= 25:
        return 0.8
    if diameter_cm <= 60:
        return 0.6
    return 0.5


def _bar_area_cm2(diameter_mm: float) -> float:
    d_cm = diameter_mm / 10.0
    return math.pi * (d_cm ** 2) / 4.0


@dataclass
class LongitudinalDesign:
    bar_diameter_mm: float
    n_bars: int
    as_provided_cm2: float
    clear_spacing_cm: float
    feasible: bool


@dataclass
class ReinforcementResult:
    diameter_cm: float
    gross_area_cm2: float
    rho_min_pct: float
    as_min_cm2: float
    longitudinal: LongitudinalDesign | None
    stirrup_diameter_mm: float
    stirrup_spacing_body_cm: float
    stirrup_spacing_top_cm: float
    confinement_length_m: float
    warnings: list[str] = field(default_factory=list)


def _min_clear_spacing_cm(bar_diameter_mm: float) -> float:
    bar_cm = bar_diameter_mm / 10.0
    return max(2.0, bar_cm, 1.2 * DEFAULT_MAX_AGGREGATE_CM)


def _try_design(
    geometry: PileGeometry,
    cover_cm: float,
    stirrup_diameter_mm: float,
    as_min_cm2: float,
) -> LongitudinalDesign | None:
    radius_cm = geometry.diameter_cm / 2.0

    for bar_diameter_mm in BAR_DIAMETERS_MM:
        bar_cm = bar_diameter_mm / 10.0
        bar_center_radius = radius_cm - cover_cm - (stirrup_diameter_mm / 10.0) - bar_cm / 2.0
        if bar_center_radius <= 0:
            continue
        min_spacing = _min_clear_spacing_cm(bar_diameter_mm)

        for n_bars in range(MIN_BARS, MAX_BARS + 1):
            as_provided = n_bars * _bar_area_cm2(bar_diameter_mm)
            if as_provided < as_min_cm2:
                continue
            circumference = 2 * math.pi * bar_center_radius
            clear_spacing = circumference / n_bars - bar_cm
            if clear_spacing >= min_spacing:
                return LongitudinalDesign(
                    bar_diameter_mm=bar_diameter_mm,
                    n_bars=n_bars,
                    as_provided_cm2=as_provided,
                    clear_spacing_cm=clear_spacing,
                    feasible=True,
                )
    return None


def design_reinforcement(
    geometry: PileGeometry,
    axial_load_kn: float,
    cover_cm: float = 4.0,
    rho_min_pct: float | None = None,
    stirrup_diameter_mm: float = 6.3,
    stirrup_spacing_body_cm: float = 15.0,
    stirrup_spacing_top_cm: float = 10.0,
    confinement_length_factor: float = 3.0,
) -> ReinforcementResult:
    if geometry.diameter_cm <= 0:
        raise ValueError("Diâmetro da estaca deve ser maior que zero.")
    if cover_cm <= 0:
        raise ValueError("Cobrimento deve ser maior que zero.")

    gross_area_cm2 = geometry.area_m2 * 1e4
    rho = rho_min_pct if rho_min_pct is not None else default_rho_min_pct(geometry.diameter_cm)
    as_min_cm2 = (rho / 100.0) * gross_area_cm2

    warnings: list[str] = []
    longitudinal = _try_design(geometry, cover_cm, stirrup_diameter_mm, as_min_cm2)
    if longitudinal is None:
        warnings.append(
            "Não foi possível encontrar uma combinação padrão de barras que respeite o "
            "espaçamento mínimo com o cobrimento informado. Avalie aumentar o diâmetro "
            "da estaca, reduzir o cobrimento (respeitando o mínimo normativo) ou revisar "
            "manualmente a disposição das barras."
        )

    confinement_length_m = confinement_length_factor * geometry.diameter_m

    if axial_load_kn <= 0:
        warnings.append("Carga axial não informada/ inválida - armadura calculada apenas pela taxa mínima.")

    return ReinforcementResult(
        diameter_cm=geometry.diameter_cm,
        gross_area_cm2=gross_area_cm2,
        rho_min_pct=rho,
        as_min_cm2=as_min_cm2,
        longitudinal=longitudinal,
        stirrup_diameter_mm=stirrup_diameter_mm,
        stirrup_spacing_body_cm=stirrup_spacing_body_cm,
        stirrup_spacing_top_cm=stirrup_spacing_top_cm,
        confinement_length_m=confinement_length_m,
        warnings=warnings,
    )
