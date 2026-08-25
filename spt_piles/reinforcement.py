"""Dimensionamento de armação de estacas moldadas in loco (longitudinal e
transversal), com base em práticas usuais associadas à NBR 6118 (Projeto de
estruturas de concreto) e NBR 6122 (Projeto e execução de fundações).

Por padrão (sem informar momento/cortante), a armadura é dimensionada apenas
pela taxa mínima - válido quando a estaca trabalha essencialmente à
compressão axial (a resistência à compressão fica a cargo do concreto).

Quando o momento fletor característico (`moment_kn_m`) é informado, o
dimensionamento passa a ser estrutural de verdade: verificação de
flexo-compressão (interação N-M) via `structural_design.py`, escolhendo a
menor combinação de barras que atenda simultaneamente a taxa mínima E a
capacidade resistente da seção. Quando o cortante característico
(`shear_kn`) também é informado, os estribos são dimensionados ao
cisalhamento (Modelo de Cálculo I da NBR 6118), reduzindo o espaçamento
construtivo se necessário. Projeto executivo deve ser assinado por
engenheiro responsável (ART/RRT).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import PileGeometry
from .structural_design import (
    GAMMA_C_STRUCTURAL,
    FlexoCompressionCheck,
    ShearDesign,
    check_flexo_compression,
    design_shear,
)

BAR_DIAMETERS_MM = [8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]
STIRRUP_DIAMETERS_MM = [5.0, 6.3, 8.0, 10.0]

MIN_BARS = 6
MAX_BARS = 24
DEFAULT_MAX_AGGREGATE_CM = 1.9  # brita 1, valor usual

# NBR 6122:2022, 8.6.2 - cobrimento mínimo de armadura para estacas moldadas
# in loco enterradas: 5 cm (classe de agressividade II) a 7 cm (classes III/
# IV, ambientes mais agressivos). Como alternativa simplificada a um
# cobrimento maior, a norma permite reduzir 2 mm no diâmetro das barras
# longitudinais ("espessura de sacrifício") no cálculo - não implementado
# aqui; se optar por essa alternativa com cobrimento menor, desconte
# manualmente 2 mm da bitola informada.
MIN_COVER_CM_CLASS_II = 5.0
MIN_COVER_CM_CLASS_III_IV = 7.0
# NBR 6122:2022 - fck mínimo do concreto de estacas: 30 MPa (classes de
# agressividade I/II) ou 40 MPa (classes III/IV).
MIN_FCK_MPA_CLASS_I_II = 30.0
MIN_FCK_MPA_CLASS_III_IV = 40.0


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
class StructuralDesignInfo:
    """Resumo do dimensionamento estrutural (N-M-V) quando momento/cortante
    são informados - ver structural_design.py para o método e hipóteses."""

    n_design_kn: float
    m_design_knm: float
    v_design_kn: float | None
    load_factor: float
    fck_mpa: float
    fyk_mpa: float
    gamma_c: float
    flexo_check: FlexoCompressionCheck | None
    shear: ShearDesign | None


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
    requested_armor_length_m: float | None = None
    structural: StructuralDesignInfo | None = None
    warnings: list[str] = field(default_factory=list)


def effective_armor_length_m(result: ReinforcementResult, pile_depth_m: float) -> float:
    """Comprimento efetivo da armadura longitudinal para uma estaca de uma
    dada profundidade: se o usuário não pediu armadura parcial
    (requested_armor_length_m is None), a armadura corre por toda a
    profundidade da estaca; senão, é limitada ao menor valor entre o pedido
    e a profundidade real da estaca (não faz sentido armar além do fundo)."""

    if result.requested_armor_length_m is None:
        return pile_depth_m
    return min(result.requested_armor_length_m, pile_depth_m)


def _min_clear_spacing_cm(bar_diameter_mm: float) -> float:
    bar_cm = bar_diameter_mm / 10.0
    return max(2.0, bar_cm, 1.2 * DEFAULT_MAX_AGGREGATE_CM)


def _try_design(
    geometry: PileGeometry,
    cover_cm: float,
    stirrup_diameter_mm: float,
    as_min_cm2: float,
    bar_diameter_mm: float | None = None,
) -> LongitudinalDesign | None:
    """`bar_diameter_mm`: se informado, fixa a bitola longitudinal (só busca
    o número de barras) em vez de testar todas as bitolas de BAR_DIAMETERS_MM
    da menor para a maior."""

    radius_cm = geometry.diameter_cm / 2.0
    candidate_diameters = [bar_diameter_mm] if bar_diameter_mm is not None else BAR_DIAMETERS_MM

    for bar_diameter_mm in candidate_diameters:
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


def _try_design_with_structural_check(
    geometry: PileGeometry,
    cover_cm: float,
    stirrup_diameter_mm: float,
    as_min_cm2: float,
    fck_mpa: float,
    fyk_mpa: float,
    n_design_kn: float,
    m_design_knm: float,
    gamma_c: float = GAMMA_C_STRUCTURAL,
    bar_diameter_mm: float | None = None,
) -> tuple[LongitudinalDesign | None, FlexoCompressionCheck | None]:
    """Como `_try_design`, mas também exige que a combinação de barras resista
    à flexo-compressão (N-M) de cálculo, não só à taxa mínima. Retorna a
    menor combinação viável e a última verificação tentada (para diagnóstico
    quando nenhuma combinação for suficiente).

    `bar_diameter_mm`: se informado, fixa a bitola longitudinal (só busca o
    número de barras) em vez de testar todas as bitolas de BAR_DIAMETERS_MM
    da menor para a maior."""

    radius_cm = geometry.diameter_cm / 2.0
    last_check: FlexoCompressionCheck | None = None
    candidate_diameters = [bar_diameter_mm] if bar_diameter_mm is not None else BAR_DIAMETERS_MM

    for bar_diameter_mm in candidate_diameters:
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

            check = check_flexo_compression(
                geometry, cover_cm, stirrup_diameter_mm, bar_diameter_mm, n_bars,
                fck_mpa, fyk_mpa, n_design_kn, m_design_knm, gamma_c=gamma_c,
            )
            last_check = check
            if check.adequate:
                design = LongitudinalDesign(
                    bar_diameter_mm=bar_diameter_mm,
                    n_bars=n_bars,
                    as_provided_cm2=as_provided,
                    clear_spacing_cm=clear_spacing,
                    feasible=True,
                )
                return design, check
    return None, last_check


def design_reinforcement(
    geometry: PileGeometry,
    axial_load_kn: float,
    cover_cm: float = MIN_COVER_CM_CLASS_II,
    rho_min_pct: float | None = None,
    stirrup_diameter_mm: float = 6.3,
    stirrup_spacing_body_cm: float = 15.0,
    stirrup_spacing_top_cm: float = 10.0,
    confinement_length_factor: float = 3.0,
    armor_length_m: float | None = None,
    moment_kn_m: float | None = None,
    shear_kn: float | None = None,
    load_factor: float = 1.4,
    fck_mpa: float = MIN_FCK_MPA_CLASS_I_II,
    fyk_mpa: float = 500.0,
    gamma_c: float = GAMMA_C_STRUCTURAL,
    bar_diameter_mm: float | None = None,
) -> ReinforcementResult:
    """`armor_length_m`: comprimento desejado de armadura longitudinal a
    partir do topo da estaca. None (padrão) arma toda a extensão da estaca -
    a opção mais segura/conservadora. Um valor numérico arma apenas os
    primeiros `armor_length_m` metros a partir do topo (armadura parcial),
    prática usual quando a estaca trabalha essencialmente à compressão
    axial e não há esforços horizontais/momento relevantes na região não
    armada - essa adequação deve ser confirmada pelo engenheiro responsável
    (ver aviso emitido abaixo quando este parâmetro é usado).

    `moment_kn_m`/`shear_kn`: momento fletor e força cortante CARACTERÍSTICOS
    (de serviço, mesma base que `axial_load_kn`) na cabeça da estaca. Quando
    `moment_kn_m` é informado, a armadura longitudinal deixa de ser apenas a
    mínima e passa a ser dimensionada pela verificação de flexo-compressão
    (N-M) da seção circular (ver structural_design.py); se `shear_kn`
    também for informado, os estribos são dimensionados ao cisalhamento.
    `load_factor` (γf, padrão 1,4) converte os esforços característicos em
    esforços de cálculo (Nd, Md, Vd) para essa verificação estrutural -
    ajuste se seu software já fornecer valores majorados (nesse caso use
    load_factor=1.0). `gamma_c` (γc, padrão 1,4 - o mesmo valor geral da NBR
    6118) é o coeficiente de ponderação da resistência do concreto; a NBR
    6122:2022 8.6.3 exige um valor mais alto apenas para execuções de maior
    risco (ex.: escavação sem qualquer suporte de parede/fluido) - ver
    structural_design.py para a justificativa e ajuste manualmente se o seu
    caso se enquadrar nessa situação.

    `cover_cm` (padrão 5 cm) e `fck_mpa` (padrão 30 MPa) seguem os mínimos da
    NBR 6122:2022 8.6.2 para estacas moldadas in loco em ambiente de classe
    de agressividade II (a mais comum para estacas enterradas); ambientes
    mais agressivos (classes III/IV) exigem cobrimento >= 7 cm e fck >= 40
    MPa - ajuste conforme a classe do seu projeto (NBR 6118, tabela 7.2).

    `bar_diameter_mm`: None (padrão) deixa o software escolher automaticamente
    a menor bitola comercial (de BAR_DIAMETERS_MM) que atenda ao espaçamento
    mínimo e à taxa/verificação estrutural exigida. Informe um valor (ex:
    12.5) para FIXAR a bitola das barras longitudinais - o software então só
    busca o número de barras com essa bitola; se nenhuma quantidade (entre
    MIN_BARS e MAX_BARS) for suficiente com a bitola fixada, o resultado vem
    sem armadura (`longitudinal is None`) com aviso explicando o motivo -
    nesse caso, tente uma bitola maior ou volte para a escolha automática."""

    if geometry.diameter_cm <= 0:
        raise ValueError("Diâmetro da estaca deve ser maior que zero.")
    if cover_cm <= 0:
        raise ValueError("Cobrimento deve ser maior que zero.")
    if armor_length_m is not None and armor_length_m <= 0:
        raise ValueError("Profundidade de armação deve ser maior que zero.")
    if load_factor <= 0:
        raise ValueError("Fator de majoração (γf) deve ser maior que zero.")
    if bar_diameter_mm is not None and bar_diameter_mm <= 0:
        raise ValueError("Bitola das barras longitudinais deve ser maior que zero.")

    gross_area_cm2 = geometry.area_m2 * 1e4
    rho = rho_min_pct if rho_min_pct is not None else default_rho_min_pct(geometry.diameter_cm)
    as_min_cm2 = (rho / 100.0) * gross_area_cm2

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
    structural: StructuralDesignInfo | None = None
    adjusted_stirrup_spacing_body_cm = stirrup_spacing_body_cm

    if moment_kn_m is not None:
        n_design_kn = load_factor * max(axial_load_kn, 0.0)
        m_design_knm = load_factor * moment_kn_m
        longitudinal, flexo_check = _try_design_with_structural_check(
            geometry, cover_cm, stirrup_diameter_mm, as_min_cm2, fck_mpa, fyk_mpa,
            n_design_kn, m_design_knm, gamma_c=gamma_c, bar_diameter_mm=bar_diameter_mm,
        )
        bitola_txt = f" com a bitola fixada de φ{bar_diameter_mm:.1f} mm" if bar_diameter_mm is not None else ""
        if longitudinal is None:
            if flexo_check is None:
                warnings.append(
                    f"Não foi possível encontrar uma combinação de barras{bitola_txt} que respeite "
                    "o espaçamento mínimo com o cobrimento informado."
                    + (" Tente uma bitola menor." if bar_diameter_mm is not None else "")
                )
            elif flexo_check.m_capacity_knm is None:
                warnings.append(
                    f"Mesmo com a maior quantidade de barras testada{bitola_txt}, a força normal de "
                    f"cálculo (Nd={n_design_kn:.1f} kN) excede a capacidade última à compressão da "
                    "seção - aumente o diâmetro da estaca ou o fck do concreto."
                )
            else:
                warnings.append(
                    f"Nenhuma combinação de barras{bitola_txt} resiste à flexo-compressão de cálculo "
                    f"(Nd={n_design_kn:.1f} kN, Md={m_design_knm:.1f} kN·m; melhor capacidade "
                    f"encontrada Mrd={flexo_check.m_capacity_knm:.1f} kN·m). Aumente o diâmetro da "
                    "estaca, o fck do concreto, a bitola fixada, ou revise os esforços de cálculo."
                )
        else:
            warnings.append(
                f"Armadura longitudinal dimensionada pela verificação de flexo-compressão "
                f"(Nd={n_design_kn:.1f} kN, Md={m_design_knm:.1f} kN·m; utilização "
                f"{flexo_check.utilization * 100:.0f}% da capacidade Mrd={flexo_check.m_capacity_knm:.1f} "
                "kN·m) - ver structural_design.py para o método e as hipóteses adotadas. Resultado "
                "numérico de pré-dimensionamento: confira de forma independente antes de executar."
            )

        shear_result: ShearDesign | None = None
        if shear_kn is not None:
            v_design_kn = load_factor * shear_kn
            shear_bar_diameter_mm = longitudinal.bar_diameter_mm if longitudinal is not None else None
            shear_result = design_shear(
                geometry, v_design_kn, stirrup_diameter_mm, fck_mpa, fyk_mpa,
                cover_cm=cover_cm, bar_diameter_mm=shear_bar_diameter_mm, gamma_c=gamma_c,
            )
            warnings.extend(shear_result.warnings)
            if shear_result.required_spacing_cm is not None:
                if shear_result.required_spacing_cm < adjusted_stirrup_spacing_body_cm:
                    adjusted_stirrup_spacing_body_cm = shear_result.required_spacing_cm
                    warnings.append(
                        f"Espaçamento dos estribos no corpo da estaca reduzido para "
                        f"{adjusted_stirrup_spacing_body_cm:.1f} cm (era {stirrup_spacing_body_cm:.1f} cm) "
                        f"para resistir ao cortante de cálculo Vd={v_design_kn:.1f} kN."
                    )

        structural = StructuralDesignInfo(
            n_design_kn=n_design_kn,
            m_design_knm=m_design_knm,
            v_design_kn=(load_factor * shear_kn if shear_kn is not None else None),
            load_factor=load_factor,
            fck_mpa=fck_mpa,
            fyk_mpa=fyk_mpa,
            gamma_c=gamma_c,
            flexo_check=flexo_check,
            shear=shear_result,
        )
    else:
        longitudinal = _try_design(geometry, cover_cm, stirrup_diameter_mm, as_min_cm2, bar_diameter_mm=bar_diameter_mm)
        if longitudinal is None:
            bitola_txt = f" com a bitola fixada de φ{bar_diameter_mm:.1f} mm" if bar_diameter_mm is not None else ""
            warnings.append(
                f"Não foi possível encontrar uma combinação de barras{bitola_txt} que respeite o "
                "espaçamento mínimo com o cobrimento informado. Avalie aumentar o diâmetro "
                "da estaca, reduzir o cobrimento (respeitando o mínimo normativo)"
                + (", usar outra bitola" if bar_diameter_mm is not None else "")
                + " ou revisar manualmente a disposição das barras."
            )

    confinement_length_m = confinement_length_factor * geometry.diameter_m

    if axial_load_kn <= 0:
        warnings.append("Carga axial não informada/ inválida - armadura calculada apenas pela taxa mínima.")

    if armor_length_m is not None:
        if armor_length_m < confinement_length_m:
            warnings.append(
                f"A profundidade de armação informada ({armor_length_m:.2f} m) é menor que a "
                f"zona de confinamento recomendada ({confinement_length_m:.2f} m) - reavalie."
            )
        warnings.append(
            "Armadura parcial (não estendida por toda a profundidade da estaca) só é "
            "adequada quando a estaca trabalha essencialmente à compressão axial, sem "
            "esforços horizontais, momento fletor ou tração relevantes na região não "
            "armada. Confirme essa hipótese com o engenheiro responsável antes de adotar."
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
