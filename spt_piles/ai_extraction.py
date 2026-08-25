"""Interpretação automática de documentos de engenharia (PDF) via API da Claude:
laudos de sondagem SPT e relatórios de esforços (cargas) de fundação.

Este módulo é opcional: só é usado quando o usuário aciona uma das abas de
importação por IA na interface gráfica. Ele NUNCA grava dados diretamente nos
dados de cálculo - sempre retorna uma proposta de leitura que deve ser
revisada e confirmada manualmente na interface antes de ser usada em
qualquer cálculo (ver gui.py).

Configuração da chave de API: cada usuário pode colar sua própria chave da
Anthropic (https://console.anthropic.com/) na aba "Configurações" da
interface (salva localmente em config.py) ou, alternativamente, definir a
variável de ambiente ANTHROPIC_API_KEY (que tem prioridade quando presente).
Opcionalmente, ANTHROPIC_MODEL pode sobrescrever o modelo padrão.
"""

from __future__ import annotations

import base64
import math
import os
from dataclasses import dataclass, field

from .soil_data import SOIL_TABLE

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_SOIL_KEYS = list(SOIL_TABLE.keys())


class AIExtractionError(RuntimeError):
    """Erro amigável para qualquer falha ao interpretar um documento via IA."""


def _read_pdf_base64(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


def _call_pdf_tool(
    pdf_path: str,
    system_prompt: str,
    tool_schema: dict,
    user_instruction: str,
    model: str | None = None,
) -> tuple[dict, str]:
    """Envia um PDF para a API da Claude forçando a chamada de `tool_schema` e
    retorna o dicionário de entrada (`input`) que o modelo preencheu.

    Levanta AIExtractionError com uma mensagem amigável em caso de falha
    (biblioteca ausente, chave ausente, PDF inválido, erro de rede, resposta
    inesperada etc.). Compartilhado por todas as extrações via IA deste app.
    """

    try:
        import anthropic
    except ImportError as exc:
        raise AIExtractionError(
            "Biblioteca 'anthropic' não está instalada. Rode: pip install anthropic"
        ) from exc

    from .config import resolve_api_key

    api_key = resolve_api_key()
    if not api_key:
        raise AIExtractionError(
            "Nenhuma chave de API configurada. Cole sua chave da Anthropic "
            "(https://console.anthropic.com/) na aba \"Configurações\" e clique em "
            "Salvar, ou defina a variável de ambiente ANTHROPIC_API_KEY, e tente "
            "novamente."
        )

    try:
        pdf_b64 = _read_pdf_base64(pdf_path)
    except OSError as exc:
        raise AIExtractionError(f"Não foi possível ler o arquivo PDF: {exc}") from exc

    model_name = model or DEFAULT_MODEL
    client = anthropic.Anthropic(api_key=api_key)
    tool_name = tool_schema["name"]

    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=8000,
            system=system_prompt,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": user_instruction},
                    ],
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001 - qualquer erro de API deve virar mensagem amigável
        raise AIExtractionError(f"Falha ao chamar a API da Claude: {exc}") from exc

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        raise AIExtractionError(
            "A IA não retornou dados estruturados. Verifique se o PDF contém um "
            "documento legível do tipo esperado e tente novamente."
        )

    return tool_block.input, model_name


# =====================================================================
# Laudo de sondagem SPT
# =====================================================================


@dataclass
class ExtractedReading:
    depth_m: float
    n_spt: int
    soil_key: str
    soil_description_original: str


@dataclass
class ExtractedSPTReport:
    readings: list[ExtractedReading] = field(default_factory=list)
    water_table_depth_m: float | None = None
    water_table_found: bool = False
    borehole_id: str = ""
    notes: str = ""
    source_pdf_path: str = ""
    model_used: str = ""


_SPT_TOOL_NAME = "submit_spt_report"


def _build_spt_tool_schema() -> dict:
    return {
        "name": _SPT_TOOL_NAME,
        "description": (
            "Registra os dados estruturados extraídos de um laudo/boletim de "
            "sondagem SPT (Standard Penetration Test) brasileiro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "borehole_id": {
                    "type": "string",
                    "description": "Identificação do furo de sondagem (ex: SP-01, FURO 1), se houver.",
                },
                "water_table_found": {
                    "type": "boolean",
                    "description": "true se o laudo indica presença de nível d'água (N.A.), false se indica solo seco ou não menciona.",
                },
                "water_table_depth_m": {
                    "type": ["number", "null"],
                    "description": "Profundidade do nível d'água em metros, se identificado. null se não encontrado.",
                },
                "readings": {
                    "type": "array",
                    "description": "Uma entrada para cada metro/leitura de SPT do furo, em ordem crescente de profundidade.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "depth_m": {"type": "number", "description": "Profundidade da leitura, em metros."},
                            "n_spt": {
                                "type": "integer",
                                "description": "Número de golpes do ensaio SPT (N-SPT) naquela profundidade.",
                            },
                            "soil_key": {
                                "type": "string",
                                "enum": _SOIL_KEYS,
                                "description": "Classificação do solo naquela profundidade, escolhida entre as chaves permitidas.",
                            },
                            "soil_description_original": {
                                "type": "string",
                                "description": "Texto original/literal da descrição do solo no laudo, para conferência humana.",
                            },
                        },
                        "required": ["depth_m", "n_spt", "soil_key", "soil_description_original"],
                    },
                },
                "notes": {
                    "type": "string",
                    "description": "Observações relevantes do laudo (nível d'água, cota do terreno, data do ensaio, impenetrável, etc).",
                },
            },
            "required": ["readings", "water_table_found"],
        },
    }


_SPT_SYSTEM_PROMPT = (
    "Você é um engenheiro geotécnico auxiliando na digitalização de laudos de "
    "sondagem SPT (boletins de sondagem à percussão) brasileiros. Leia todas as "
    "páginas do PDF fornecido, localize a tabela/perfil de sondagem e extraia, "
    "para CADA profundidade ensaiada, o número de golpes (N-SPT) e a "
    "classificação do solo. Classifique cada camada usando exclusivamente uma "
    "das chaves de solo permitidas no schema (categorias de areia/silte/argila "
    "e combinações, conforme a classificação de Aoki-Velloso) - escolha a mais "
    "próxima da descrição textual do laudo. Identifique também o nível d'água "
    "(N.A.), quando indicado. Sempre preencha soil_description_original com o "
    "texto literal do laudo para permitir conferência humana. Se um valor não "
    "for legível ou não existir, não invente - prefira omitir a leitura a "
    "adivinhar. Responda chamando a ferramenta fornecida."
)


def extract_spt_report(pdf_path: str, model: str | None = None) -> ExtractedSPTReport:
    """Envia o PDF do laudo SPT para a API da Claude e retorna os dados extraídos."""

    data, model_name = _call_pdf_tool(
        pdf_path,
        _SPT_SYSTEM_PROMPT,
        _build_spt_tool_schema(),
        "Extraia o perfil de sondagem SPT completo deste laudo, seguindo exatamente o schema da ferramenta fornecida.",
        model,
    )
    return _parse_spt_tool_output(data, pdf_path, model_name)


def _parse_spt_tool_output(data: dict, pdf_path: str, model_name: str) -> ExtractedSPTReport:
    readings: list[ExtractedReading] = []
    for item in data.get("readings", []):
        try:
            soil_key = item["soil_key"]
            if soil_key not in SOIL_TABLE:
                continue
            readings.append(
                ExtractedReading(
                    depth_m=float(item["depth_m"]),
                    n_spt=int(item["n_spt"]),
                    soil_key=soil_key,
                    soil_description_original=str(item.get("soil_description_original", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    readings.sort(key=lambda r: r.depth_m)

    if not readings:
        raise AIExtractionError(
            "A IA não conseguiu identificar nenhuma leitura de SPT válida neste PDF. "
            "Confira se o arquivo corresponde a um laudo/boletim de sondagem SPT."
        )

    return ExtractedSPTReport(
        readings=readings,
        water_table_depth_m=data.get("water_table_depth_m"),
        water_table_found=bool(data.get("water_table_found", False)),
        borehole_id=str(data.get("borehole_id", "")),
        notes=str(data.get("notes", "")),
        source_pdf_path=pdf_path,
        model_used=model_name,
    )


# =====================================================================
# Relatório de esforços (cargas) de fundação
# =====================================================================


@dataclass
class ExtractedLoadItem:
    element_id: str
    characteristic_load_kn: float
    n_piles: int
    original_description: str
    moment_kn_m: float | None = None
    shear_kn: float | None = None
    # Componentes ortogonais originais, quando o relatório os traz separados
    # (em vez de já dar uma resultante única) - guardados para conferência.
    moment_x_knm: float | None = None
    moment_y_knm: float | None = None
    shear_x_kn: float | None = None
    shear_y_kn: float | None = None


@dataclass
class ExtractedLoadsReport:
    items: list[ExtractedLoadItem] = field(default_factory=list)
    notes: str = ""
    source_pdf_path: str = ""
    model_used: str = ""


_LOADS_TOOL_NAME = "submit_foundation_loads"


def _build_loads_tool_schema() -> dict:
    return {
        "name": _LOADS_TOOL_NAME,
        "description": (
            "Registra os esforços (cargas) de fundação extraídos de um relatório "
            "de cargas em pilares/blocos gerado por software de dimensionamento "
            "estrutural (ex: Eberick, TQS, CypeCad)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Uma entrada para cada pilar/bloco/estaca do relatório.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "element_id": {
                                "type": "string",
                                "description": "Identificação do pilar/bloco/estaca (ex: P12, B03, E01).",
                            },
                            "characteristic_load_kn": {
                                "type": "number",
                                "description": (
                                    "Carga vertical CARACTERÍSTICA (de serviço, Nk - combinação "
                                    "quase-permanente ou ELS; NUNCA a carga majorada/ELU), sempre "
                                    "convertida para kN (1 tf ≈ 10 kN)."
                                ),
                            },
                            "n_piles": {
                                "type": "integer",
                                "description": (
                                    "Número de estacas do bloco ao qual esta carga se refere. Use 1 "
                                    "se o relatório já fornece a carga por estaca individual, ou se "
                                    "não houver menção a um bloco com múltiplas estacas."
                                ),
                            },
                            "moment_x_knm": {
                                "type": ["number", "null"],
                                "description": (
                                    "Componente do momento fletor CARACTERÍSTICO na direção X (Mx) na "
                                    "cabeça do pilar/bloco/estaca, em kN·m (1 tf·m ≈ 10 kN·m). Preencha "
                                    "quando o relatório trouxer Mx e My separados. null se não existir."
                                ),
                            },
                            "moment_y_knm": {
                                "type": ["number", "null"],
                                "description": "Componente do momento fletor CARACTERÍSTICO na direção Y (My), em kN·m. null se não existir.",
                            },
                            "moment_kn_m": {
                                "type": ["number", "null"],
                                "description": (
                                    "Momento fletor CARACTERÍSTICO já como valor único/resultante (use "
                                    "isto SOMENTE quando o relatório já trouxer um único valor de momento, "
                                    "sem componentes Mx/My separados - nesse caso deixe moment_x_knm e "
                                    "moment_y_knm como null). Em kN·m. null se o relatório não trouxer "
                                    "momento para este elemento."
                                ),
                            },
                            "shear_x_kn": {
                                "type": ["number", "null"],
                                "description": (
                                    "Componente da força cortante/horizontal CARACTERÍSTICA na direção X "
                                    "(Fx) na cabeça do pilar/bloco/estaca, em kN. Preencha quando o "
                                    "relatório trouxer Fx e Fy separados. null se não existir."
                                ),
                            },
                            "shear_y_kn": {
                                "type": ["number", "null"],
                                "description": "Componente da força cortante/horizontal CARACTERÍSTICA na direção Y (Fy), em kN. null se não existir.",
                            },
                            "shear_kn": {
                                "type": ["number", "null"],
                                "description": (
                                    "Força cortante/horizontal CARACTERÍSTICA já como valor único/"
                                    "resultante (use isto SOMENTE quando o relatório já trouxer um único "
                                    "valor, sem componentes Fx/Fy separados - nesse caso deixe shear_x_kn "
                                    "e shear_y_kn como null). Em kN. null se não existir."
                                ),
                            },
                            "original_description": {
                                "type": "string",
                                "description": (
                                    "Texto/linha original do relatório (identificação, valor e unidade "
                                    "como aparecem no documento), para conferência humana."
                                ),
                            },
                        },
                        "required": ["element_id", "characteristic_load_kn", "n_piles", "original_description"],
                    },
                },
                "notes": {
                    "type": "string",
                    "description": (
                        "Observações relevantes (unidade original predominante, combinação de "
                        "carregamento usada, elementos ambíguos ou não identificados, etc)."
                    ),
                },
            },
            "required": ["items"],
        },
    }


_LOADS_SYSTEM_PROMPT = (
    "Você é um engenheiro de estruturas auxiliando na digitalização de relatórios "
    "de esforços (cargas) de fundação, gerados por softwares brasileiros de "
    "dimensionamento estrutural (Eberick, TQS, CypeCad ou similares). Leia todas "
    "as páginas do PDF e localize a tabela de cargas por pilar/bloco/estaca. Para "
    "CADA elemento, extraia sua identificação e a carga vertical CARACTERÍSTICA "
    "(de serviço - combinação quase-permanente ou ELS). Se o relatório apresentar "
    "várias combinações (por exemplo ELU/Nd majorada e ELS/Nk característica), "
    "escolha SEMPRE a característica/de serviço, nunca a majorada - isso é "
    "essencial, pois o cálculo geotécnico já aplica seu próprio fator de "
    "segurança sobre a carga característica. Converta sempre o valor para kN (1 "
    "tf ≈ 10 kN), registrando o valor e unidade originais em "
    "original_description. Quando o relatório indicar que um bloco tem mais de "
    "uma estaca, informe o número de estacas em n_piles; caso contrário, use "
    "n_piles = 1. Se o relatório também trouxer momento fletor e/ou força "
    "horizontal/cortante na cabeça do elemento, extraia-os também (sempre "
    "característicos, nunca majorados). IMPORTANTE: se o relatório traz Mx e My "
    "(ou Fx e Fy) como componentes SEPARADOS, preencha moment_x_knm/moment_y_knm "
    "(ou shear_x_kn/shear_y_kn) com os valores exatamente como aparecem - NÃO "
    "calcule a resultante você mesmo, isso será feito automaticamente depois; "
    "nesse caso deixe moment_kn_m/shear_kn como null. Se o relatório já traz um "
    "único valor de momento/cortante (sem componentes separados), preencha "
    "moment_kn_m/shear_kn diretamente e deixe os campos de componentes como "
    "null. Quando não houver momento/cortante algum para o elemento, deixe todos "
    "esses campos como null - não invente. Não invente valores não legíveis - "
    "prefira omitir a linha.\n\n"
    "ATENÇÃO A DOIS ERROS COMUNS NESTE TIPO DE RELATÓRIO:\n"
    "1) Softwares como o Eberick geram VÁRIOS relatórios diferentes no mesmo "
    "memorial: um lista cargas POR PAVIMENTO em cada pilar (não é o que "
    "queremos), e outro lista a REAÇÃO FINAL NA FUNDAÇÃO/BASE de cada "
    "pilar-bloco (geralmente chamado 'Cargas para fundação', 'Reações de "
    "apoio' ou similar) - é APENAS este último que deve ser usado. Se o PDF "
    "tiver as duas tabelas, ignore a de pavimento/pilar e use somente a da "
    "fundação/base. Se não tiver certeza de qual tabela é a correta, explique "
    "a ambiguidade no campo notes em vez de adivinhar.\n"
    "2) Alguns relatórios trazem uma ENVOLTÓRIA (envelope) por elemento, com o "
    "valor MÁXIMO de N numa linha/coluna e os valores MÁXIMOS de Mx, My, Hx, Hy "
    "em linhas/colunas SEPARADAS (de combinações diferentes, não concomitantes "
    "entre si). Nesse caso, NÃO combine o N máximo com o Mx/My máximo de outra "
    "combinação como se fossem do mesmo instante - isso gera um esforço "
    "fisicamente inconsistente. Prefira extrair N, Mx, My, Hx, Hy de UMA MESMA "
    "linha/combinação (a mais desfavorável, isto é, a de maior N, ou a indicada "
    "pelo relatório como governante/crítica para aquele elemento). Se o "
    "relatório só oferecer valores em envoltória sem concomitância clara, "
    "extraia mesmo assim o que for mais razoável mas registre isso "
    "explicitamente no campo notes, citando os elementos afetados, para que o "
    "usuário confira manualmente antes de calcular.\n\n"
    "Responda chamando a ferramenta fornecida."
)


def extract_foundation_loads(pdf_path: str, model: str | None = None) -> ExtractedLoadsReport:
    """Envia o PDF do relatório de esforços para a API da Claude e retorna os dados extraídos."""

    data, model_name = _call_pdf_tool(
        pdf_path,
        _LOADS_SYSTEM_PROMPT,
        _build_loads_tool_schema(),
        "Extraia todos os esforços (cargas características) de fundação deste relatório, seguindo exatamente o schema da ferramenta fornecida.",
        model,
    )
    return _parse_loads_tool_output(data, pdf_path, model_name)


def _parse_loads_tool_output(data: dict, pdf_path: str, model_name: str) -> ExtractedLoadsReport:
    items: list[ExtractedLoadItem] = []
    for item in data.get("items", []):
        try:
            element_id = str(item["element_id"]).strip()
            if not element_id:
                continue
            load_kn = float(item["characteristic_load_kn"])
            if load_kn <= 0:
                continue
            n_piles = int(item.get("n_piles", 1) or 1)
            if n_piles <= 0:
                n_piles = 1

            moment_x_knm = item.get("moment_x_knm")
            moment_x_knm = float(moment_x_knm) if moment_x_knm is not None else None
            moment_y_knm = item.get("moment_y_knm")
            moment_y_knm = float(moment_y_knm) if moment_y_knm is not None else None

            shear_x_kn = item.get("shear_x_kn")
            shear_x_kn = float(shear_x_kn) if shear_x_kn is not None else None
            shear_y_kn = item.get("shear_y_kn")
            shear_y_kn = float(shear_y_kn) if shear_y_kn is not None else None

            if moment_x_knm is not None or moment_y_knm is not None:
                # a resultante é sempre calculada aqui (em Python), nunca confiada
                # à aritmética da IA - mais confiável e verificável.
                moment_kn_m = math.hypot(moment_x_knm or 0.0, moment_y_knm or 0.0)
            else:
                moment_direct = item.get("moment_kn_m")
                moment_kn_m = abs(float(moment_direct)) if moment_direct is not None else None

            if shear_x_kn is not None or shear_y_kn is not None:
                shear_kn = math.hypot(shear_x_kn or 0.0, shear_y_kn or 0.0)
            else:
                shear_direct = item.get("shear_kn")
                shear_kn = abs(float(shear_direct)) if shear_direct is not None else None

            items.append(
                ExtractedLoadItem(
                    element_id=element_id,
                    characteristic_load_kn=load_kn,
                    n_piles=n_piles,
                    original_description=str(item.get("original_description", "")),
                    moment_kn_m=moment_kn_m,
                    shear_kn=shear_kn,
                    moment_x_knm=moment_x_knm,
                    moment_y_knm=moment_y_knm,
                    shear_x_kn=shear_x_kn,
                    shear_y_kn=shear_y_kn,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    if not items:
        raise AIExtractionError(
            "A IA não conseguiu identificar nenhum esforço de fundação válido neste "
            "PDF. Confira se o arquivo corresponde a um relatório de cargas em "
            "pilares/blocos de um software de dimensionamento estrutural."
        )

    return ExtractedLoadsReport(
        items=items,
        notes=str(data.get("notes", "")),
        source_pdf_path=pdf_path,
        model_used=model_name,
    )
