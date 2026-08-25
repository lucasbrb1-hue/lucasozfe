"""Determina a profundidade mínima de estaca que atende a uma carga de projeto,
com base no(s) método(s) de capacidade de carga via SPT selecionados."""

from __future__ import annotations

from dataclasses import dataclass

from . import aoki_velloso, decourt_quaresma
from .models import PileGeometry, SPTProfile

METHOD_DQ = "decourt_quaresma"
METHOD_AV = "aoki_velloso"
METHOD_BOTH = "ambos"


@dataclass
class DepthSolverRow:
    depth_m: float
    qadm_dq_kn: float | None
    qadm_av_kn: float | None
    qadm_governing_kn: float


@dataclass
class DepthSolverResult:
    rows: list[DepthSolverRow]
    required_depth_m: float | None
    load_kn: float
    method: str


def solve(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    load_kn: float,
    method: str = METHOD_BOTH,
    safety_factor: float = 2.0,
    min_depth_m: float = 1.0,
) -> DepthSolverResult:
    if load_kn <= 0:
        raise ValueError("Carga de projeto deve ser maior que zero.")
    if not profile.is_valid():
        raise ValueError("Perfil de SPT precisa de ao menos 2 leituras.")

    depths = sorted({p.depth_m for p in profile.points if p.depth_m >= min_depth_m})
    if not depths:
        raise ValueError(
            "Nenhuma leitura de SPT respeita a profundidade mínima de embutimento informada."
        )

    dq_results = {
        r.depth_m: r
        for r in (
            decourt_quaresma.calc_profile(profile, geometry, pile_type, safety_factor, min_depth_m)
            if method in (METHOD_DQ, METHOD_BOTH)
            else []
        )
    }
    av_results = {
        r.depth_m: r
        for r in (
            aoki_velloso.calc_profile(profile, geometry, pile_type, safety_factor, min_depth_m)
            if method in (METHOD_AV, METHOD_BOTH)
            else []
        )
    }

    rows: list[DepthSolverRow] = []
    required_depth_m: float | None = None
    for depth in depths:
        qadm_dq = dq_results[depth].qadm_kn if depth in dq_results else None
        qadm_av = av_results[depth].qadm_kn if depth in av_results else None

        candidates = [v for v in (qadm_dq, qadm_av) if v is not None]
        if not candidates:
            continue
        # quando ambos os métodos são usados, adota-se o mais conservador (menor Qadm)
        qadm_governing = min(candidates)

        rows.append(
            DepthSolverRow(
                depth_m=depth,
                qadm_dq_kn=qadm_dq,
                qadm_av_kn=qadm_av,
                qadm_governing_kn=qadm_governing,
            )
        )

        if required_depth_m is None and qadm_governing >= load_kn:
            required_depth_m = depth

    return DepthSolverResult(
        rows=rows,
        required_depth_m=required_depth_m,
        load_kn=load_kn,
        method=method,
    )


def solve_armor_length(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    adopted_depth_m: float,
    axial_load_kn: float,
    method: str = METHOD_BOTH,
    load_factor: float = 1.4,
    fck_mpa: float = 30.0,
    gamma_c: float | None = None,
    min_depth_m: float = 1.0,
) -> float | None:
    """Estima até que profundidade (a partir do topo) a armadura longitudinal
    é estruturalmente necessária numa estaca de profundidade adotada
    `adopted_depth_m` que trabalha essencialmente à compressão axial (sem
    momento/esforço horizontal relevante) - usado para sugerir automaticamente
    o campo antes preenchido manualmente ("profundidade de armação").

    MÉTODO: a capacidade última do(s) método(s) SPT selecionado(s) já separa
    a resistência em resistência de ponta (Qp) e de fuste/atrito lateral (Ql)
    - na profundidade adotada, adota-se o método mais conservador (menor
    Qadm), igual ao critério usado por `solve()`. Supondo que, à medida que a
    estaca é percorrida da cabeça até a ponta, a força axial remanescente
    N(z) é reduzida pelo atrito lateral já mobilizado no trecho [0, z] na
    mesma proporção da resistência última do método (Ql(z)/Qu), a força axial
    de cálculo remanescente numa profundidade z é aproximada por:

        Nd(z) = Nd_topo * (1 - Ql(z) / Qu(L))         [Qu(L) = Qp(L)+Ql(L)]

    A armadura deixa de ser necessária por resistência a partir da menor
    profundidade z em que essa força remanescente já é menor que a
    capacidade resistente do CONCRETO SIMPLES da seção (bloco retangular de
    tensões da NBR 6118 17.2.2, sem armadura): Nc = 0,85 * fcd * Ac. Retorna
    essa profundidade z, ou None se, mesmo na ponta (z = L), a força
    remanescente (o próprio Qp mobilizado) ainda excede a capacidade do
    concreto simples - nesse caso a armadura é necessária por toda a
    extensão da estaca.

    APROXIMAÇÃO de pré-dimensionamento: assume mobilização de atrito lateral
    proporcional ao longo da profundidade conforme a própria fórmula SPT
    usada, sem uma análise de transferência de carga/compatibilidade de
    deformações solo-estaca (t-z) nem verificação de tração/flexão residual.
    Só é válida para estacas trabalhando essencialmente à compressão axial;
    resultado de pré-dimensionamento - confirme com o engenheiro responsável
    antes de adotar."""

    from .structural_design import ALPHA_C, GAMMA_C_STRUCTURAL, KN_PER_CM2_MPA

    if axial_load_kn <= 0 or adopted_depth_m <= 0:
        return None
    if not profile.is_valid():
        raise ValueError("Perfil de SPT precisa de ao menos 2 leituras.")
    if load_factor <= 0:
        raise ValueError("Fator de majoração (γf) deve ser maior que zero.")
    gamma_c = gamma_c if gamma_c is not None else GAMMA_C_STRUCTURAL
    if gamma_c <= 0:
        raise ValueError("γc deve ser maior que zero.")

    depths = sorted(
        {p.depth_m for p in profile.points if min_depth_m <= p.depth_m <= adopted_depth_m}
    )
    if not depths or depths[-1] != adopted_depth_m:
        # a profundidade adotada precisa ser uma das cotas do perfil (é sempre
        # o caso quando `adopted_depth_m` vem de `solve()` com o mesmo perfil).
        return None

    dq_by_depth = {
        r.depth_m: r
        for r in (
            decourt_quaresma.calc_profile(profile, geometry, pile_type, 1.0, min_depth_m)
            if method in (METHOD_DQ, METHOD_BOTH)
            else []
        )
        if r.depth_m <= adopted_depth_m
    }
    av_by_depth = {
        r.depth_m: r
        for r in (
            aoki_velloso.calc_profile(profile, geometry, pile_type, 1.0, min_depth_m)
            if method in (METHOD_AV, METHOD_BOTH)
            else []
        )
        if r.depth_m <= adopted_depth_m
    }

    dq_at_l = dq_by_depth.get(adopted_depth_m)
    av_at_l = av_by_depth.get(adopted_depth_m)
    qu_dq_l = (dq_at_l.qp_kn + dq_at_l.ql_kn) if dq_at_l is not None else None
    qu_av_l = (av_at_l.qp_kn + av_at_l.ql_kn) if av_at_l is not None else None
    candidates_l = [v for v in (qu_dq_l, qu_av_l) if v is not None]
    if not candidates_l:
        return None
    governing_by_dq = (qu_dq_l is not None) and (qu_av_l is None or qu_dq_l <= qu_av_l)
    governing_map = dq_by_depth if governing_by_dq else av_by_depth
    qu_l = qu_dq_l if governing_by_dq else qu_av_l
    if qu_l <= 0:
        return None

    fcd_mpa = fck_mpa / gamma_c
    gross_area_cm2 = geometry.area_m2 * 1e4
    nc_bare_kn = ALPHA_C * fcd_mpa * gross_area_cm2 * KN_PER_CM2_MPA

    nd_head_kn = load_factor * axial_load_kn
    for depth in depths:
        entry = governing_map.get(depth)
        if entry is None:
            continue
        nd_z = nd_head_kn * (1.0 - entry.ql_kn / qu_l)
        if nd_z <= nc_bare_kn:
            return depth
    return None
