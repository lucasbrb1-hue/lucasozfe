"""Geração de relatório texto com o resumo dos cálculos."""

from __future__ import annotations

from datetime import datetime

from .depth_solver import DepthSolverResult
from .models import PileGeometry, SPTProfile
from .pile_factors import PILE_TYPES
from .reinforcement import ReinforcementResult

DISCLAIMER = (
    "AVISO: este relatório é gerado por uma ferramenta de apoio ao pré-dimensionamento\n"
    "geotécnico/estrutural, com base em métodos semi-empíricos (Décourt-Quaresma e/ou\n"
    "Aoki-Velloso) e coeficientes de referência da literatura técnica. Os resultados NÃO\n"
    "substituem a investigação geotécnica completa, a análise crítica e a Anotação de\n"
    "Responsabilidade Técnica (ART/RRT) de um engenheiro habilitado. Validar sempre com\n"
    "as normas vigentes (NBR 6118, NBR 6122 e demais aplicáveis) antes de qualquer uso\n"
    "em projeto executivo ou execução de obra."
)


def build_report(
    profile: SPTProfile,
    geometry: PileGeometry,
    pile_type: str,
    solver_result: DepthSolverResult,
    reinforcement: ReinforcementResult | None,
    safety_factor: float,
) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("RELATÓRIO - CÁLCULO DE ESTACA A PARTIR DE SONDAGEM SPT")
    lines.append("=" * 70)
    lines.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lines.append("")
    lines.append(f"Tipo de estaca: {PILE_TYPES.get(pile_type, pile_type)}")
    lines.append(f"Diâmetro: {geometry.diameter_cm:.1f} cm")
    lines.append(f"Fator de segurança global: {safety_factor:.2f}")
    lines.append(f"Carga de projeto: {solver_result.load_kn:.1f} kN")
    lines.append(f"Método de cálculo: {solver_result.method}")
    lines.append("")

    lines.append("-- Perfil de SPT --")
    for p in profile.points:
        lines.append(f"  {p.depth_m:6.2f} m | N-SPT = {p.n_spt:3d} | solo: {p.soil_key}")
    lines.append("")

    lines.append("-- Capacidade de carga admissível por profundidade --")
    lines.append(f"{'Prof.(m)':>10} {'Qadm DQ (kN)':>14} {'Qadm AV (kN)':>14} {'Qadm gov. (kN)':>16}")
    for row in solver_result.rows:
        dq_str = f"{row.qadm_dq_kn:14.1f}" if row.qadm_dq_kn is not None else f"{'--':>14}"
        av_str = f"{row.qadm_av_kn:14.1f}" if row.qadm_av_kn is not None else f"{'--':>14}"
        lines.append(f"{row.depth_m:10.2f} {dq_str} {av_str} {row.qadm_governing_kn:16.1f}")
    lines.append("")

    if solver_result.required_depth_m is not None:
        lines.append(
            f"PROFUNDIDADE MÍNIMA NECESSÁRIA: {solver_result.required_depth_m:.2f} m "
            f"(atende Qadm >= {solver_result.load_kn:.1f} kN)"
        )
    else:
        lines.append(
            "Nenhuma profundidade do perfil de SPT informado atinge a carga de projeto. "
            "Aumente o comprimento da sondagem, reavalie o diâmetro da estaca ou a carga."
        )
    lines.append("")

    if reinforcement is not None:
        lines.append("-- Armação sugerida --")
        lines.append(f"Área bruta da seção: {reinforcement.gross_area_cm2:.1f} cm²")
        lines.append(f"Taxa mínima de armadura: {reinforcement.rho_min_pct:.2f} %")
        lines.append(f"Área de aço mínima (As,min): {reinforcement.as_min_cm2:.2f} cm²")
        if reinforcement.longitudinal:
            lg = reinforcement.longitudinal
            lines.append(
                f"Armadura longitudinal sugerida: {lg.n_bars} x φ{lg.bar_diameter_mm:.1f} mm "
                f"(As fornecido = {lg.as_provided_cm2:.2f} cm², "
                f"espaçamento livre ≈ {lg.clear_spacing_cm:.1f} cm)"
            )
        else:
            lines.append("Armadura longitudinal: não foi possível obter combinação padrão viável.")
        lines.append(
            f"Estribos: φ{reinforcement.stirrup_diameter_mm:.1f} mm, espaçamento "
            f"{reinforcement.stirrup_spacing_body_cm:.0f} cm no fuste e "
            f"{reinforcement.stirrup_spacing_top_cm:.0f} cm na zona de confinamento "
            f"(primeiros {reinforcement.confinement_length_m:.2f} m a partir do topo)"
        )
        for w in reinforcement.warnings:
            lines.append(f"AVISO: {w}")
        lines.append("")

    lines.append(DISCLAIMER)
    return "\n".join(lines)
