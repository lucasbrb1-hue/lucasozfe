"""Sugestão do tipo de estaca mais adequado a partir do perfil de SPT e de
restrições de execução do local da obra informadas pelo usuário.

MÉTODO E LIMITAÇÕES (leia antes de usar):

  Esta é uma TRIAGEM HEURÍSTICA de apoio à decisão - não é um método
  normativo nem um cálculo numérico. As regras abaixo cruzam características
  do perfil de solo (resistência N-SPT, presença/profundidade do nível
  d'água) com restrições práticas do local (vizinhança sensível a vibração,
  espaço/acesso para equipamento, pé-direito, uso de fluido estabilizante,
  porte da obra, restrição de ruído) e atribuem uma pontuação relativa a
  cada tipo de estaca suportado pelo software, com a justificativa de cada
  ponto somado/subtraído.

  O resultado é um RANKING relativo (não uma aprovação/reprovação
  definitiva) e NÃO considera fatores decisivos na prática que este
  software não tem como conhecer: custo local, disponibilidade de
  equipamento/mão de obra na região, prazo, licenciamento ambiental,
  interferências (redes enterradas, fundações vizinhas) e a experiência do
  engenheiro de fundações responsável. Use como ponto de partida para a
  conversa com o projetista/executor, nunca como decisão final.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import SPTProfile
from .pile_factors import PILE_TYPES

# Limiares de referência (prática usual/literatura de fundações) - ajustáveis
# conforme calibração local.
HIGH_NSPT_THRESHOLD = 30  # solo já bastante resistente
VERY_HIGH_NSPT_THRESHOLD = 45  # solo muito resistente / possível impenetrável a equip. convencional
SHALLOW_LAYER_DEPTH_M = 4.0  # profundidade considerada "rasa" p/ risco de nega em cravação
SHALLOW_WATER_TABLE_M = 3.0  # N.A. considerado raso

# (atributo em SiteConstraints, pergunta a exibir na interface)
SITE_QUESTIONS: list[tuple[str, str]] = [
    (
        "vibration_sensitive_neighbors",
        "Há edificações/estruturas vizinhas sensíveis a vibração (risco de dano ou "
        "incômodo com cravação por impacto)?",
    ),
    (
        "noise_restriction",
        "Há restrição legal/ambiental de ruído no horário ou local da obra?",
    ),
    (
        "limited_access_large_equipment",
        "O acesso/espaço no terreno é restrito para equipamento de grande porte "
        "(perfuratriz de hélice contínua, bate-estacas)?",
    ),
    (
        "limited_headroom",
        "Há pé-direito restrito (obra interna, reforço de fundação, subsolo)?",
    ),
    (
        "avoid_drilling_fluid",
        "Deseja evitar o uso de fluido estabilizante (lama bentonítica) na escavação?",
    ),
    (
        "small_scale_budget",
        "É uma obra de pequeno porte, com poucas estacas, ou de orçamento restrito?",
    ),
]


@dataclass
class SiteConstraints:
    """Respostas do usuário sobre restrições do local da obra. `None` =
    não informado (não pontua a favor nem contra de nenhum tipo)."""

    vibration_sensitive_neighbors: bool | None = None
    noise_restriction: bool | None = None
    limited_access_large_equipment: bool | None = None
    limited_headroom: bool | None = None
    avoid_drilling_fluid: bool | None = None
    small_scale_budget: bool | None = None


@dataclass
class PileTypeAssessment:
    pile_type: str
    label: str
    score: int
    reasons: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


@dataclass
class PileTypeRecommendation:
    assessments: list[PileTypeAssessment]  # ordenado do maior para o menor score
    profile_notes: list[str]

    @property
    def best(self) -> PileTypeAssessment | None:
        return self.assessments[0] if self.assessments else None


def _profile_signals(
    profile: SPTProfile, water_table_found: bool, water_table_depth_m: float | None
) -> tuple[int, int, bool]:
    max_nspt = max(p.n_spt for p in profile.points)
    shallow_points = [p for p in profile.points if p.depth_m <= SHALLOW_LAYER_DEPTH_M]
    max_nspt_shallow = max((p.n_spt for p in shallow_points), default=0)
    shallow_water = water_table_found and (
        water_table_depth_m is None or water_table_depth_m <= SHALLOW_WATER_TABLE_M
    )
    return max_nspt, max_nspt_shallow, shallow_water


def recommend_pile_types(
    profile: SPTProfile,
    water_table_found: bool = False,
    water_table_depth_m: float | None = None,
    constraints: SiteConstraints | None = None,
) -> PileTypeRecommendation:
    if not profile.is_valid():
        raise ValueError(
            "Perfil de SPT inválido - adicione ao menos 2 leituras antes de pedir a "
            "sugestão de tipo de estaca."
        )
    constraints = constraints or SiteConstraints()
    max_nspt, max_nspt_shallow, shallow_water = _profile_signals(
        profile, water_table_found, water_table_depth_m
    )

    profile_notes: list[str] = []
    if max_nspt_shallow >= HIGH_NSPT_THRESHOLD:
        profile_notes.append(
            f"Camada resistente (N-SPT >= {HIGH_NSPT_THRESHOLD}) já nos primeiros "
            f"{SHALLOW_LAYER_DEPTH_M:.0f} m de profundidade - risco de nega prematura em "
            "estacas cravadas."
        )
    if max_nspt >= VERY_HIGH_NSPT_THRESHOLD:
        profile_notes.append(
            f"N-SPT máximo do perfil ({max_nspt}) é muito alto - pode exceder a capacidade "
            "de perfuração de equipamentos convencionais de hélice contínua/estacas "
            "escavadas; avalie estaca cravada, estaca raiz, ou investigação complementar "
            "(possível rocha/matacão)."
        )
    if shallow_water:
        profile_notes.append(
            "Nível d'água raso identificado - favorece métodos executivos que dispensam "
            "escavação aberta sem suporte de parede."
        )

    assessments: list[PileTypeAssessment] = []
    for key, label in PILE_TYPES.items():
        score = 0
        reasons: list[str] = []
        concerns: list[str] = []

        if key == "helice_continua":
            if shallow_water:
                score += 2
                reasons.append(
                    "Bom desempenho abaixo do nível d'água sem uso de fluido estabilizante "
                    "(concretagem pelo tubo central durante a extração da hélice)."
                )
            if max_nspt_shallow >= HIGH_NSPT_THRESHOLD:
                score += 1
                reasons.append(
                    "Não sofre risco de nega por impacto em camada resistente rasa "
                    "(execução por rotação/escavação, não por cravação)."
                )
            if max_nspt >= VERY_HIGH_NSPT_THRESHOLD:
                score -= 2
                concerns.append(
                    "Solo muito resistente pode exceder o torque de equipamentos "
                    "convencionais de hélice contínua."
                )
            if constraints.limited_access_large_equipment:
                score -= 2
                concerns.append(
                    "Exige equipamento de grande porte (perfuratriz) - pode não caber no "
                    "acesso/espaço disponível."
                )
            if constraints.limited_headroom:
                score -= 2
                concerns.append(
                    "Equipamento de hélice contínua costuma exigir pé-direito alto para a torre."
                )
            if constraints.small_scale_budget:
                score -= 1
                concerns.append(
                    "Mobilização de equipamento costuma ser cara para poucas estacas - menos "
                    "econômico em obras pequenas."
                )
            if constraints.vibration_sensitive_neighbors:
                score += 1
                reasons.append("Execução sem cravação por impacto - baixo nível de vibração.")

        elif key == "escavada":
            if constraints.limited_access_large_equipment:
                score += 1
                reasons.append(
                    "Pode ser executada com equipamentos menores/adaptados que a hélice contínua."
                )
            if constraints.small_scale_budget:
                score += 1
                reasons.append("Mobilização geralmente mais barata para poucas estacas.")
            if constraints.vibration_sensitive_neighbors:
                score += 1
                reasons.append("Execução sem cravação por impacto - baixo nível de vibração.")
            if shallow_water and constraints.avoid_drilling_fluid:
                score -= 2
                concerns.append(
                    "N.A. raso sem uso de fluido estabilizante favorece desmoronamento das "
                    "paredes da escavação, especialmente em solos arenosos."
                )
            elif shallow_water:
                score -= 1
                concerns.append(
                    "N.A. raso pode exigir fluido estabilizante (lama bentonítica) ou "
                    "revestimento para evitar desmoronamento das paredes."
                )
            if max_nspt >= VERY_HIGH_NSPT_THRESHOLD:
                score -= 1
                concerns.append(
                    "Solo muito resistente pode dificultar a escavação com os equipamentos "
                    "usuais deste método."
                )

        elif key == "pre_moldada":
            if not shallow_water:
                score += 1
                reasons.append(
                    "Execução não é afetada pelo nível d'água (concreto pré-fabricado, sem "
                    "concretagem in loco)."
                )
            if constraints.vibration_sensitive_neighbors:
                score -= 3
                concerns.append(
                    "Cravação por impacto gera vibração significativa - risco de dano/incômodo "
                    "a edificações vizinhas sensíveis."
                )
            if constraints.noise_restriction:
                score -= 2
                concerns.append(
                    "Cravação gera ruído elevado - pode conflitar com restrições "
                    "ambientais/legais do entorno."
                )
            if constraints.limited_access_large_equipment:
                score -= 2
                concerns.append(
                    "Bate-estacas/guindaste exigem espaço de acesso e manobra consideráveis."
                )
            if constraints.limited_headroom:
                score -= 2
                concerns.append(
                    "Equipamento de cravação costuma exigir pé-direito alto para a torre."
                )
            if max_nspt_shallow >= HIGH_NSPT_THRESHOLD:
                score -= 2
                concerns.append(
                    "Camada resistente rasa aumenta o risco de nega prematura (não atingir a "
                    "profundidade de projeto)."
                )

        elif key == "strauss":
            if constraints.small_scale_budget:
                score += 2
                reasons.append(
                    "Método tradicionalmente econômico e adequado para obras pequenas/poucas "
                    "estacas."
                )
            if constraints.limited_access_large_equipment:
                score += 2
                reasons.append("Equipamento leve, bom para acessos restritos.")
            if constraints.limited_headroom:
                score += 1
                reasons.append(
                    "Equipamento compacto - tolera pé-direito reduzido melhor que hélice "
                    "contínua/cravada."
                )
            if constraints.vibration_sensitive_neighbors:
                score += 1
                reasons.append(
                    "Execução por percussão leve - vibração bem menor que a cravação de "
                    "pré-moldados."
                )
            if max_nspt >= HIGH_NSPT_THRESHOLD:
                score -= 2
                concerns.append(
                    "Método pouco adequado para solos muito resistentes ou com "
                    "pedregulhos/matacões."
                )
            if shallow_water:
                score -= 1
                concerns.append(
                    "N.A. raso exige revestimento (camisa metálica) acompanhando a escavação - "
                    "executável, mas aumenta o cuidado/custo."
                )
            concerns.append(
                "Diâmetro e profundidade tipicamente limitados - confirme se atende à carga "
                "de projeto."
            )

        assessments.append(
            PileTypeAssessment(pile_type=key, label=label, score=score, reasons=reasons, concerns=concerns)
        )

    assessments.sort(key=lambda a: a.score, reverse=True)
    return PileTypeRecommendation(assessments=assessments, profile_notes=profile_notes)
