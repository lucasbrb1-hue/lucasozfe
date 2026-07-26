"""Método de Décourt-Quaresma (1978) para capacidade de carga de estacas via SPT.

Convenções adotadas (referência usual na prática brasileira):
  - Resistência de ponta:  rp = alpha * K * Np          [kPa]
  - Resistência lateral:   rl = beta * 10 * (Nl/3 + 1)   [kPa]
  - Qp = rp * Ap
  - Ql = rl * U * L_fuste
  - Qu = Qp + Ql
  - Qadm = Qu / FS

Onde:
  - Np: média dos N-SPT na região da ponta (valor na cota, um acima e um
    abaixo, quando disponíveis).
  - Nl: média dos N-SPT ao longo do fuste, cada leitura limitada ao
    intervalo [3, 50] antes da média (prática usual do método).
  - K: coeficiente de solo (kPa), tabela de Décourt-Quaresma.
  - alpha, beta: fatores por tipo de estaca (ver pile_factors.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PileGeometry, SPTProfile
from .pile_factors import dq_factors
from .soil_data import dq_k_for_soil, get_soil

MIN_N_CLIP = 3
MAX_N_CLIP = 50


@dataclass
class DecourtQuaresmaResult:
    depth_m: float
    np_tip: float
    nl_shaft: float
    k_kpa: float
    alpha: float
    beta: float
    qp_kn: float
    ql_kn: float
    qu_kn: float
    qadm_kn: float


def _clip(n: float) -> float:
    return max(MIN_N_CLIP, min(MAX_N_CLIP, n))


def calc_at_depth(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    depth_m: float,
    safety_factor: float = 2.0,
) -> DecourtQuaresmaResult:
    if not profile.is_valid():
        raise ValueError("Perfil de SPT precisa de ao menos 2 leituras.")
    if safety_factor <= 0:
        raise ValueError("Fator de segurança deve ser positivo.")

    tip_point, tip_window = profile.tip_reference(depth_m)
    np_tip = sum(p.n_spt for p in tip_window) / len(tip_window)

    shaft_points = profile.points_up_to(depth_m)
    if not shaft_points:
        shaft_points = [tip_point]
    nl_values = [_clip(p.n_spt) for p in shaft_points]
    nl_shaft = sum(nl_values) / len(nl_values)

    k_kpa = dq_k_for_soil(tip_point.soil_key)
    dq_soil_group = get_soil(tip_point.soil_key).dq_group
    factors = dq_factors(pile_type, dq_soil_group)

    rp = factors.alpha * k_kpa * np_tip
    rl = factors.beta * 10.0 * (nl_shaft / 3.0 + 1.0)

    qp_kn = rp * geometry.area_m2
    ql_kn = rl * geometry.perimeter_m * depth_m
    qu_kn = qp_kn + ql_kn
    qadm_kn = qu_kn / safety_factor

    return DecourtQuaresmaResult(
        depth_m=depth_m,
        np_tip=np_tip,
        nl_shaft=nl_shaft,
        k_kpa=k_kpa,
        alpha=factors.alpha,
        beta=factors.beta,
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
) -> list[DecourtQuaresmaResult]:
    """Calcula Qadm para cada profundidade candidata do perfil (>= min_depth_m)."""

    depths = sorted({p.depth_m for p in profile.points if p.depth_m >= min_depth_m})
    return [calc_at_depth(profile, geometry, pile_type, d, safety_factor) for d in depths]
