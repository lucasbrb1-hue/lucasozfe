"""Método de Aoki & Velloso (1975) para capacidade de carga de estacas via SPT.

Convenções adotadas:
  - Resistência de ponta:  rp = (K * Np) / F1                    [kPa]
  - Resistência lateral:   rl_i = (alpha_i/100 * K_i * N_i) / F2  [kPa] (por camada i)
  - Qp = rp * Ap
  - Ql = U * sum(rl_i * comprimento_i)
  - Qu = Qp + Ql
  - Qadm = Qu / FS

Cada leitura de SPT é tratada como representativa de uma camada cuja
espessura é a metade da distância até a leitura anterior mais a metade da
distância até a leitura seguinte (integração trapezoidal simples), prática
usual quando as sondagens são feitas de metro em metro.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PileGeometry, SPTProfile
from .pile_factors import av_factors
from .soil_data import get_soil


@dataclass
class AokiVellosoResult:
    depth_m: float
    n_tip: float
    k_tip_mpa: float
    f1: float
    f2: float
    qp_kn: float
    ql_kn: float
    qu_kn: float
    qadm_kn: float


def _layer_thickness(depths: list[float], i: int) -> float:
    n = len(depths)
    lower = depths[i - 1] if i > 0 else 0.0
    upper = depths[i]
    half_below = (upper - lower) / 2.0
    if i + 1 < n:
        half_above = (depths[i + 1] - upper) / 2.0
    else:
        half_above = (upper - lower) / 2.0
    return half_below + half_above


def calc_at_depth(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    depth_m: float,
    safety_factor: float = 2.0,
) -> AokiVellosoResult:
    if not profile.points:
        raise ValueError("Perfil de SPT está vazio.")
    if safety_factor <= 0:
        raise ValueError("Fator de segurança deve ser positivo.")

    shaft_points = profile.points_up_to(depth_m)
    if not shaft_points:
        raise ValueError("Não há leituras de SPT até a profundidade informada.")

    tip_point = shaft_points[-1]
    factors = av_factors(pile_type)
    tip_soil = get_soil(tip_point.soil_key)

    rp = (tip_soil.k_mpa * 1000.0 * tip_point.n_spt) / factors.f1
    qp_kn = rp * geometry.area_m2

    depths = [p.depth_m for p in shaft_points]
    ql_kn = 0.0
    for i, point in enumerate(shaft_points):
        thickness = _layer_thickness(depths, i)
        # limita a espessura da última camada para não ultrapassar a ponta
        remaining = depth_m - (depths[i - 1] if i > 0 else 0.0)
        thickness = min(thickness, remaining) if i == len(shaft_points) - 1 else thickness
        soil = get_soil(point.soil_key)
        rl_i = (soil.alpha_pct / 100.0) * soil.k_mpa * 1000.0 * point.n_spt / factors.f2
        ql_kn += rl_i * geometry.perimeter_m * thickness

    qu_kn = qp_kn + ql_kn
    qadm_kn = qu_kn / safety_factor

    return AokiVellosoResult(
        depth_m=depth_m,
        n_tip=tip_point.n_spt,
        k_tip_mpa=tip_soil.k_mpa,
        f1=factors.f1,
        f2=factors.f2,
        qp_kn=qp_kn,
        ql_kn=ql_kn,
        qu_kn=qu_kn,
        qadm_kn=qadm_kn,
    )


def calc_profile(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    safety_factor: float = 2.0,
    min_depth_m: float = 1.0,
) -> list[AokiVellosoResult]:
    depths = sorted({p.depth_m for p in profile.points if p.depth_m >= min_depth_m})
    return [calc_at_depth(profile, geometry, pile_type, d, safety_factor) for d in depths]
