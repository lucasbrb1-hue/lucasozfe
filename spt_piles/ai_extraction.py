"""Interpretação automática de laudos de sondagem SPT (PDF) via API da Claude.

Este módulo é opcional: só é usado quando o usuário aciona a aba de
importação por IA na interface gráfica. Ele NUNCA grava dados diretamente no
perfil de cálculo - sempre retorna uma proposta de leitura que deve ser
revisada e confirmada manualmente na interface antes de ser usada em
qualquer cálculo (ver gui.py).

Configuração: defina a variável de ambiente ANTHROPIC_API_KEY com uma chave
válida da API da Anthropic (https://console.anthropic.com/) antes de abrir o
programa. Opcionalmente, ANTHROPIC_MODEL pode sobrescrever o modelo padrão.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field

from .soil_data import SOIL_TABLE

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

TOOL_NAME = "submit_spt_report"

_SOIL_KEYS = list(SOIL_TABLE.keys())


class AIExtractionError(RuntimeError):
    """Erro amigável para qualquer falha ao interpretar o laudo via IA."""


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


def _build_tool_schema() -> dict:
    return {
        "name": TOOL_NAME,
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


_SYSTEM_PROMPT = (
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


def _read_pdf_base64(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


def extract_spt_report(pdf_path: str, model: str | None = None) -> ExtractedSPTReport:
    """Envia o PDF do laudo SPT para a API da Claude e retorna os dados extraídos.

    Levanta AIExtractionError com uma mensagem amigável em caso de falha
    (chave ausente, PDF inválido, erro de rede, resposta inesperada etc.).
    """

    try:
        import anthropic
    except ImportError as exc:
        raise AIExtractionError(
            "Biblioteca 'anthropic' não está instalada. Rode: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AIExtractionError(
            "Variável de ambiente ANTHROPIC_API_KEY não está definida. Defina sua "
            "chave da API da Anthropic (https://console.anthropic.com/) antes de "
            "abrir o programa e tente novamente."
        )

    try:
        pdf_b64 = _read_pdf_base64(pdf_path)
    except OSError as exc:
        raise AIExtractionError(f"Não foi possível ler o arquivo PDF: {exc}") from exc

    model_name = model or DEFAULT_MODEL
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=8000,
            system=_SYSTEM_PROMPT,
            tools=[_build_tool_schema()],
            tool_choice={"type": "tool", "name": TOOL_NAME},
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
                        {
                            "type": "text",
                            "text": (
                                "Extraia o perfil de sondagem SPT completo deste laudo, "
                                "seguindo exatamente o schema da ferramenta fornecida."
                            ),
                        },
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
            "laudo de sondagem SPT legível e tente novamente."
        )

    data = tool_block.input
    return _parse_tool_output(data, pdf_path, model_name)


def _parse_tool_output(data: dict, pdf_path: str, model_name: str) -> ExtractedSPTReport:
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
