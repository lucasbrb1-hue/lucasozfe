"""Cálculo em lote da profundidade de cada estaca a partir dos esforços
importados, com opção de uniformização (agrupamento) das profundidades.

A uniformização agrupa as estacas ordenadas pela profundidade individual
necessária em N grupos contíguos; cada grupo adota a maior profundidade
entre as estacas que o compõem, reduzindo a quantidade de profundidades
distintas usadas na obra (mais estacas ficam com folga, nunca com déficit).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import depth_solver as ds
from .loads import FoundationLoad
from .models import PileGeometry, SPTProfile
from .reinforcement import (
    BAR_DIAMETERS_MM,
    MAX_BARS,
    MIN_BARS,
    MIN_COVER_CM_CLASS_II,
    MIN_FCK_MPA_CLASS_I_II,
    LongitudinalDesign,
    ReinforcementResult,
    StructuralDesignInfo,
    _bar_area_cm2,
    _min_clear_spacing_cm,
    default_rho_min_pct,
    design_reinforcement,
)
from .structural_design import (
    GAMMA_C_CONCRETE_PILE,
    FlexoCompressionCheck,
    build_interaction_diagram,
    design_shear,
    moment_capacity_at_n,
)


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


def compute_batch_reinforcement(
    loads: list[FoundationLoad],
    geometry: PileGeometry,
    cover_cm: float = MIN_COVER_CM_CLASS_II,
    rho_min_pct: float | None = None,
    stirrup_diameter_mm: float = 6.3,
    stirrup_spacing_body_cm: float = 15.0,
    stirrup_spacing_top_cm: float = 10.0,
    confinement_length_factor: float = 3.0,
    armor_length_m: float | None = None,
    load_factor: float = 1.4,
    fck_mpa: float = MIN_FCK_MPA_CLASS_I_II,
    fyk_mpa: float = 500.0,
    gamma_c: float = GAMMA_C_CONCRETE_PILE,
) -> ReinforcementResult:
    """Dimensiona UMA armação comum a todo o lote (mesmo diâmetro para todas
    as estacas do conjunto). Se nenhum esforço do lote tiver momento
    informado, delega para `design_reinforcement` com a maior carga axial
    (armadura mínima). Se houver momento em pelo menos um elemento, busca a
    menor combinação de barras que resista à flexo-compressão de TODAS as
    estacas do lote simultaneamente (cada uma com seu próprio Nd, Md) - a
    estaca mais exigente (menor margem) é reportada como "governante"."""

    if not loads:
        raise ValueError("Nenhum esforço de fundação foi informado.")

    if not any(ld.moment_per_pile_knm is not None for ld in loads):
        max_load = max(ld.load_per_pile_kn for ld in loads)
        return design_reinforcement(
            geometry,
            axial_load_kn=max_load,
            cover_cm=cover_cm,
            rho_min_pct=rho_min_pct,
            stirrup_diameter_mm=stirrup_diameter_mm,
            stirrup_spacing_body_cm=stirrup_spacing_body_cm,
            stirrup_spacing_top_cm=stirrup_spacing_top_cm,
            confinement_length_factor=confinement_length_factor,
            armor_length_m=armor_length_m,
        )

    if geometry.diameter_cm <= 0:
        raise ValueError("Diâmetro da estaca deve ser maior que zero.")
    if cover_cm <= 0:
        raise ValueError("Cobrimento deve ser maior que zero.")
    if load_factor <= 0:
        raise ValueError("Fator de majoração (γf) deve ser maior que zero.")

    gross_area_cm2 = geometry.area_m2 * 1e4
    rho = rho_min_pct if rho_min_pct is not None else default_rho_min_pct(geometry.diameter_cm)
    as_min_cm2 = (rho / 100.0) * gross_area_cm2

    design_pairs = [
        (
            load_factor * max(ld.load_per_pile_kn, 0.0),
            load_factor * (ld.moment_per_pile_knm or 0.0),
            ld.element_id,
        )
        for ld in loads
    ]
    max_shear_kn: float | None = None
    for ld in loads:
        v_per_pile = ld.shear_per_pile_kn
        if v_per_pile is not None:
            v_d = load_factor * v_per_pile
            max_shear_kn = v_d if max_shear_kn is None else max(max_shear_kn, v_d)

    radius_cm = geometry.diameter_cm / 2.0
    longitudinal: LongitudinalDesign | None = None
    worst_check: FlexoCompressionCheck | None = None
    governing_id: str | None = None

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
            if clear_spacing < min_spacing:
                continue

            diagram = build_interaction_diagram(
                geometry, cover_cm, stirrup_diameter_mm, bar_diameter_mm, n_bars, fck_mpa, fyk_mpa,
                gamma_c=gamma_c,
            )
            all_ok = True
            worst_utilization = -1.0
            worst_pair: tuple[float, float, str, float | None] | None = None
            for n_d, m_d, eid in design_pairs:
                m_cap = moment_capacity_at_n(diagram, n_d)
                if m_cap is None:
                    all_ok = False
                    worst_pair = (n_d, m_d, eid, None)
                    break
                utilization = (m_d / m_cap) if m_cap > 1e-9 else float("inf")
                if utilization > worst_utilization:
                    worst_utilization = utilization
                    worst_pair = (n_d, m_d, eid, m_cap)
                if utilization > 1.0 + 1e-6:
                    all_ok = False
                    break

            if all_ok and worst_pair is not None:
                longitudinal = LongitudinalDesign(
                    bar_diameter_mm=bar_diameter_mm,
                    n_bars=n_bars,
                    as_provided_cm2=as_provided,
                    clear_spacing_cm=clear_spacing,
                    feasible=True,
                )
                worst_check = FlexoCompressionCheck(
                    n_design_kn=worst_pair[0],
                    m_design_knm=worst_pair[1],
                    m_capacity_knm=worst_pair[3],
                    adequate=True,
                    utilization=worst_utilization,
                )
                governing_id = worst_pair[2]
                break
        if longitudinal is not None:
            break

    warnings: list[str] = []
    if cover_cm < MIN_COVER_CM_CLASS_II:
        warnings.append(
            f"Cobrimento informado ({cover_cm:.1f} cm) é menor que o mínimo da NBR 6122:2022 "
            f"8.6.2 para estacas moldadas in loco em classe de agressividade II ({MIN_COVER_CM_CLASS_II:.0f} "
            "cm). A norma permite, como alternativa simplificada, descontar 2 mm da bitola "
            "longitudinal no cálculo (espessura de sacrifício) - não aplicado automaticamente "
            "aqui. Confirme com o engenheiro responsável."
        )
    if fck_mpa < MIN_FCK_MPA_CLASS_I_II:
        warnings.append(
            f"fck informado ({fck_mpa:.0f} MPa) é menor que o mínimo da NBR 6122:2022 para "
            f"concreto de estacas em classes de agressividade I/II ({MIN_FCK_MPA_CLASS_I_II:.0f} MPa)."
        )
    if longitudinal is None:
        warnings.append(
            "Nenhuma combinação padrão de barras resiste à flexo-compressão de todas as "
            f"estacas do lote (estaca mais exigente: {governing_id or '?'}). Aumente o "
            "diâmetro da estaca, o fck do concreto, ou revise os esforços de cálculo."
        )
    else:
        warnings.append(
            f"Armadura longitudinal dimensionada pela verificação de flexo-compressão de todas "
            f"as estacas do lote; estaca governante: {governing_id} (utilização "
            f"{worst_check.utilization * 100:.0f}% da capacidade Mrd={worst_check.m_capacity_knm:.1f} "
            "kN·m). Ver structural_design.py para o método e as hipóteses adotadas. Resultado "
            "numérico de pré-dimensionamento: confira de forma independente antes de executar."
        )

    adjusted_stirrup_spacing_body_cm = stirrup_spacing_body_cm
    shear_result = None
    if max_shear_kn is not None:
        shear_bar_diameter_mm = longitudinal.bar_diameter_mm if longitudinal is not None else None
        shear_result = design_shear(
            geometry, max_shear_kn, stirrup_diameter_mm, fck_mpa, fyk_mpa,
            cover_cm=cover_cm, bar_diameter_mm=shear_bar_diameter_mm, gamma_c=gamma_c,
        )
        warnings.extend(shear_result.warnings)
        if shear_result.required_spacing_cm is not None and shear_result.required_spacing_cm < adjusted_stirrup_spacing_body_cm:
            adjusted_stirrup_spacing_body_cm = shear_result.required_spacing_cm
            warnings.append(
                f"Espaçamento dos estribos no corpo da estaca reduzido para "
                f"{adjusted_stirrup_spacing_body_cm:.1f} cm (era {stirrup_spacing_body_cm:.1f} cm) "
                f"para resistir ao maior cortante de cálculo do lote (Vd={max_shear_kn:.1f} kN)."
            )

    confinement_length_m = confinement_length_factor * geometry.diameter_m

    structural = StructuralDesignInfo(
        n_design_kn=worst_check.n_design_kn if worst_check else 0.0,
        m_design_knm=worst_check.m_design_knm if worst_check else 0.0,
        v_design_kn=max_shear_kn,
        load_factor=load_factor,
        fck_mpa=fck_mpa,
        fyk_mpa=fyk_mpa,
        gamma_c=gamma_c,
        flexo_check=worst_check,
        shear=shear_result,
    )

    if armor_length_m is not None and armor_length_m <= 0:
        raise ValueError("Profundidade de armação deve ser maior que zero.")
    if armor_length_m is not None and armor_length_m < confinement_length_m:
        warnings.append(
            f"A profundidade de armação informada ({armor_length_m:.2f} m) é menor que a "
            f"zona de confinamento recomendada ({confinement_length_m:.2f} m) - reavalie."
        )

    return ReinforcementResult(
        diameter_cm=geometry.diameter_cm,
        gross_area_cm2=gross_area_cm2,
        rho_min_pct=rho,
        as_min_cm2=as_min_cm2,
        longitudinal=longitudinal,
        stirrup_diameter_mm=stirrup_diameter_mm,
        stirrup_spacing_body_cm=adjusted_stirrup_spacing_body_cm,
        stirrup_spacing_top_cm=stirrup_spacing_top_cm,
        confinement_length_m=confinement_length_m,
        structural=structural,
        requested_armor_length_m=armor_length_m,
        warnings=warnings,
    )
