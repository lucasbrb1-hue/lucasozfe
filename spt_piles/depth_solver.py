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
