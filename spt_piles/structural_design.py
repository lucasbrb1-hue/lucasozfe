"""Dimensionamento estrutural da seção de concreto armado da estaca à
flexo-compressão reta (N + M) e ao cisalhamento (V), conforme a NBR 6118
(bloco retangular de tensões no concreto, aço elastoplástico perfeito).

MÉTODO E HIPÓTESES (leia antes de usar):

  - Flexo-compressão: o diagrama de interação Nrd x Mrd da seção circular é
    obtido numericamente pelo "método das fibras" - a seção é discretizada
    em faixas finas paralelas à linha neutra, varrendo-se a profundidade da
    linha neutra `x` e aplicando, em cada passo, o bloco retangular
    equivalente de tensões no concreto (NBR 6118, 17.2.2: tensão constante
    0,85·fcd ao longo de 0,8·x, medido a partir da fibra mais comprimida) e
    a lei tensão-deformação elastoplástica perfeita do aço (Es = 210 GPa,
    patamar em fyd). A seção circular é considerada simétrica em relação a
    qualquer eixo de flexão (armadura distribuída uniformemente no
    perímetro), por isso o momento resultante |M| = sqrt(Mx²+My²) pode ser
    tratado como flexão uniaxial equivalente.
  - Esta é uma APROXIMAÇÃO NUMÉRICA do diagrama de interação exato da NBR
    6118: não implementa o "domínio 5" com deformação de referência no
    ponto a 3/7 da altura (usado na norma para compressão quase centrada) -
    o bloco retangular é extrapolado de forma aproximada para grandes
    valores de x. Os resultados costumam ficar próximos aos de softwares
    dedicados no domínio 2-3-4 (flexão predominante) e podem apresentar
    pequenas diferenças na região de compressão quase centrada.
  - Cisalhamento: Modelo de Cálculo I da NBR 6118, com largura equivalente
    usual para seções circulares (bw = D). A altura útil "d" é calculada de
    forma geométrica exata quando cobrimento e bitola longitudinal são
    conhecidos (d = D - cobrimento - φestribo - φlongitudinal/2); quando
    essa informação não está disponível numa chamada específica, cai-se de
    volta na aproximação usual d = 0,8·D.
  - A contribuição do concreto ao cisalhamento (Vc) é calculada pela
    fórmula de elementos em flexão simples (sem o acréscimo permitido pela
    norma para compressão), o que é uma hipótese A FAVOR DA SEGURANÇA
    (subestima Vc).
  - γc (coeficiente de ponderação da resistência do concreto): o PADRÃO
    aqui é γc = 1,4 (GAMMA_C_STRUCTURAL), o mesmo valor geral da NBR 6118 -
    é o que se aplica à grande maioria das estacas (qualquer execução com
    controle de concretagem normal: hélice contínua, pré-moldada, estacas
    escavadas com controle usual etc.). A NBR 6122:2022 (item 8.6.3) prevê
    um γc majorado apenas para situações executivas específicas de MAIOR
    risco (por exemplo, concretagem sem controle rigoroso de consumo de
    cimento/abatimento, ou escavação sem qualquer suporte de parede/fluido
    estabilizante) - nesses casos, ajuste manualmente o parâmetro `gamma_c`
    para um valor mais alto (GAMMA_C_CONCRETE_PILE = 3,1 é oferecido aqui
    como referência para o caso mais crítico, conferido por retro-cálculo
    contra um memorial de cálculo profissional real de uma estaca escavada
    sem fluido - mas é EXCESSIVAMENTE CONSERVADOR se aplicado como padrão
    geral, já que não representa a execução típica da maioria das estacas).
    Confirme sempre com o engenheiro responsável qual γc se aplica ao seu
    caso específico, conforme o tipo de estaca e o controle de execução
    real da obra.

Este módulo produz uma ESTIMATIVA de pré-dimensionamento. Antes de qualquer
execução, o resultado deve ser conferido de forma independente (cálculo
manual, ábacos, ou software estrutural dedicado) por um engenheiro
responsável.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import PileGeometry

ES_MPA = 210_000.0  # módulo de elasticidade do aço (CA-50/CA-60), NBR 6118
ECU = 3.5e-3  # deformação última de encurtamento do concreto (fck <= 50 MPa)
GAMMA_C_STRUCTURAL = 1.4  # valor padrão NBR 6118 (estruturas em geral)
GAMMA_C_CONCRETE_PILE = 3.1  # NBR 6122:2022 8.6.3 - estacas moldadas in loco (ver módulo acima)
GAMMA_S = 1.15
ALPHA_C = 0.85  # coeficiente do bloco retangular de tensões (NBR 6118 17.2.2)
KN_PER_CM2_MPA = 0.1  # 1 MPa * 1 cm² = 0.1 kN

N_X_POINTS = 140
N_STRIPS = 150


def _bar_area_cm2(diameter_mm: float) -> float:
    d_cm = diameter_mm / 10.0
    return math.pi * (d_cm ** 2) / 4.0


def _chord_half_width_cm(radius_cm: float, y_cm: float) -> float:
    v = radius_cm ** 2 - y_cm ** 2
    return math.sqrt(v) if v > 0 else 0.0


def _bar_layer_ys_cm(n_bars: int, bar_circle_radius_cm: float) -> list[float]:
    return [bar_circle_radius_cm * math.cos(2 * math.pi * i / n_bars) for i in range(n_bars)]


def _concrete_capacity_curve(
    radius_cm: float, fcd_mpa: float, x_values_cm: list[float], n_strips: int = N_STRIPS
) -> tuple[list[float], list[float]]:
    """Retorna (Nc[kN], Mc[kN.cm]) do concreto para cada x do bloco retangular."""

    nc_values: list[float] = []
    mc_values: list[float] = []
    for x_cm in x_values_cm:
        a_cm = min(0.8 * x_cm, 2 * radius_cm)
        if a_cm <= 0:
            nc_values.append(0.0)
            mc_values.append(0.0)
            continue
        y_bottom = radius_cm - a_cm
        strip_h = a_cm / n_strips
        n_force = 0.0
        m_force = 0.0
        for i in range(n_strips):
            y_mid = y_bottom + (i + 0.5) * strip_h
            w = 2 * _chord_half_width_cm(radius_cm, y_mid)
            area_cm2 = w * strip_h
            force_kn = ALPHA_C * fcd_mpa * area_cm2 * KN_PER_CM2_MPA
            n_force += force_kn
            m_force += force_kn * y_mid
        nc_values.append(n_force)
        mc_values.append(m_force)
    return nc_values, mc_values


def _steel_capacity_at_x(
    x_cm: float,
    radius_cm: float,
    bar_ys_cm: list[float],
    bar_area_cm2: float,
    fyd_mpa: float,
    fcd_mpa: float,
) -> tuple[float, float]:
    """Retorna (Ns[kN], Ms[kN.cm]) do aço para a posição de linha neutra x_cm,
    descontando a área de concreto deslocada pelas barras dentro do bloco
    de tensões (evita contar a mesma área duas vezes)."""

    a_cm = min(0.8 * x_cm, 2 * radius_cm)
    y_bottom_block = radius_cm - a_cm
    y_na = radius_cm - x_cm

    n_force = 0.0
    m_force = 0.0
    for y_i in bar_ys_cm:
        if x_cm > 1e-9:
            strain = ECU * (y_i - y_na) / x_cm
        else:
            strain = ECU if y_i >= y_na else -ECU
        stress_mpa = max(-fyd_mpa, min(fyd_mpa, ES_MPA * strain))
        concrete_stress_here = ALPHA_C * fcd_mpa if (y_bottom_block <= y_i <= radius_cm) else 0.0
        net_stress_mpa = stress_mpa - concrete_stress_here
        force_kn = net_stress_mpa * bar_area_cm2 * KN_PER_CM2_MPA
        n_force += force_kn
        m_force += force_kn * y_i
    return n_force, m_force


@dataclass
class InteractionDiagram:
    x_values_cm: list[float]
    nrd_kn: list[float]
    mrd_knm: list[float]


def build_interaction_diagram(
    geometry: PileGeometry,
    cover_cm: float,
    stirrup_diameter_mm: float,
    bar_diameter_mm: float,
    n_bars: int,
    fck_mpa: float,
    fyk_mpa: float,
    gamma_c: float = GAMMA_C_STRUCTURAL,
) -> InteractionDiagram:
    radius_cm = geometry.diameter_cm / 2.0
    fcd = fck_mpa / gamma_c
    fyd = fyk_mpa / GAMMA_S

    bar_circle_radius_cm = radius_cm - cover_cm - (stirrup_diameter_mm / 10.0) - (bar_diameter_mm / 20.0)
    if bar_circle_radius_cm <= 0:
        raise ValueError("Cobrimento/estribo/bitola incompatíveis com o diâmetro da estaca.")
    bar_area_cm2 = _bar_area_cm2(bar_diameter_mm)
    bar_ys_cm = _bar_layer_ys_cm(n_bars, bar_circle_radius_cm)

    x_max_cm = 3.0 * geometry.diameter_cm
    x_values = [x_max_cm * (i + 1) / N_X_POINTS for i in range(N_X_POINTS)]

    nc_arr, mc_arr = _concrete_capacity_curve(radius_cm, fcd, x_values)

    nrd: list[float] = []
    mrd: list[float] = []
    for idx, x_cm in enumerate(x_values):
        ns, ms = _steel_capacity_at_x(x_cm, radius_cm, bar_ys_cm, bar_area_cm2, fyd, fcd)
        nrd.append(nc_arr[idx] + ns)
        mrd.append(abs(mc_arr[idx] + ms) / 100.0)  # kN.cm -> kN.m

    return InteractionDiagram(x_values_cm=x_values, nrd_kn=nrd, mrd_knm=mrd)


def moment_capacity_at_n(diagram: InteractionDiagram, n_design_kn: float) -> float | None:
    """Interpola no diagrama de interação a capacidade de momento (kN.m) para
    a força normal de cálculo informada. Retorna None se `n_design_kn`
    estiver fora da faixa coberta pelo diagrama (carga além da capacidade
    última à compressão centrada, ou negativa/tração)."""

    nrd = diagram.nrd_kn
    mrd = diagram.mrd_knm
    if n_design_kn < 0 or n_design_kn > nrd[-1]:
        return None

    lower_n, lower_m = 0.0, 0.0
    for n_i, m_i in zip(nrd, mrd):
        if n_i >= n_design_kn:
            if n_i == lower_n:
                return m_i
            frac = (n_design_kn - lower_n) / (n_i - lower_n) if (n_i - lower_n) > 1e-9 else 0.0
            return lower_m + frac * (m_i - lower_m)
        lower_n, lower_m = n_i, m_i
    return mrd[-1]


@dataclass
class FlexoCompressionCheck:
    n_design_kn: float
    m_design_knm: float
    m_capacity_knm: float | None
    adequate: bool
    utilization: float | None


def check_flexo_compression(
    geometry: PileGeometry,
    cover_cm: float,
    stirrup_diameter_mm: float,
    bar_diameter_mm: float,
    n_bars: int,
    fck_mpa: float,
    fyk_mpa: float,
    n_design_kn: float,
    m_design_knm: float,
    gamma_c: float = GAMMA_C_STRUCTURAL,
) -> FlexoCompressionCheck:
    diagram = build_interaction_diagram(
        geometry, cover_cm, stirrup_diameter_mm, bar_diameter_mm, n_bars, fck_mpa, fyk_mpa, gamma_c=gamma_c
    )
    m_cap = moment_capacity_at_n(diagram, n_design_kn)
    if m_cap is None:
        return FlexoCompressionCheck(n_design_kn, m_design_knm, None, False, None)
    utilization = (m_design_knm / m_cap) if m_cap > 1e-9 else float("inf")
    adequate = m_design_knm <= m_cap + 1e-6
    return FlexoCompressionCheck(n_design_kn, m_design_knm, m_cap, adequate, utilization)


# ---------------------------------------------------------------------
# Cisalhamento (Modelo de Cálculo I, NBR 6118), seção circular equivalente
# ---------------------------------------------------------------------

EQUIVALENT_BW_FACTOR = 1.0  # bw = fator * D
EQUIVALENT_D_FACTOR = 0.8  # d = fator * D


@dataclass
class ShearDesign:
    v_design_kn: float
    vrd2_kn: float
    vc_kn: float
    crushing_ok: bool
    required_spacing_cm: float | None
    warnings: list[str]


def design_shear(
    geometry: PileGeometry,
    v_design_kn: float,
    stirrup_diameter_mm: float,
    fck_mpa: float,
    fywk_mpa: float = 500.0,
    cover_cm: float | None = None,
    bar_diameter_mm: float | None = None,
    gamma_c: float = GAMMA_C_STRUCTURAL,
) -> ShearDesign:
    diameter_cm = geometry.diameter_cm
    bw_cm = EQUIVALENT_BW_FACTOR * diameter_cm
    if cover_cm is not None and bar_diameter_mm is not None:
        # d = D - cobrimento - φestribo - φlongitudinal/2 (geometria exata da seção circular).
        d_cm = diameter_cm - cover_cm - (stirrup_diameter_mm / 10.0) - (bar_diameter_mm / 20.0)
    else:
        d_cm = EQUIVALENT_D_FACTOR * diameter_cm

    fcd = fck_mpa / gamma_c
    fywd = fywk_mpa / GAMMA_S
    alpha_v2 = 1 - fck_mpa / 250.0
    vrd2_kn = 0.27 * alpha_v2 * fcd * bw_cm * d_cm * KN_PER_CM2_MPA

    fctm = 0.3 * (fck_mpa ** (2.0 / 3.0))
    fctk_inf = 0.7 * fctm
    fctd = fctk_inf / gamma_c
    vc_kn = 0.6 * fctd * bw_cm * d_cm * KN_PER_CM2_MPA

    warnings: list[str] = []
    crushing_ok = v_design_kn <= vrd2_kn
    if not crushing_ok:
        warnings.append(
            f"Vd ({v_design_kn:.1f} kN) excede Vrd2 ({vrd2_kn:.1f} kN) - a biela de concreto "
            "esmagaria antes do escoamento dos estribos. Aumente o diâmetro da estaca ou o fck; "
            "estribos sozinhos não resolvem este caso."
        )

    required_spacing_cm: float | None = None
    if v_design_kn > vc_kn and crushing_ok:
        vsw_needed_kn_per_cm = (v_design_kn - vc_kn) / (0.9 * d_cm)
        bar_area_cm2 = _bar_area_cm2(stirrup_diameter_mm)
        asw_effective_cm2 = 2 * bar_area_cm2  # estribo fechado, 2 ramos cortando a fissura
        if vsw_needed_kn_per_cm > 1e-9:
            required_spacing_cm = (asw_effective_cm2 * fywd * KN_PER_CM2_MPA) / vsw_needed_kn_per_cm

    return ShearDesign(
        v_design_kn=v_design_kn,
        vrd2_kn=vrd2_kn,
        vc_kn=vc_kn,
        crushing_ok=crushing_ok,
        required_spacing_cm=required_spacing_cm,
        warnings=warnings,
    )
