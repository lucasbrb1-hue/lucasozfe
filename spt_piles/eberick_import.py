"""Leitor determinístico (sem IA) do relatório "Esforços nas Fundações por
Elementos" exportado pelo AltoQi Eberick em .xlsx.

Por que um leitor dedicado em vez da extração por IA: este relatório traz,
para cada fundação (pilar/bloco), uma tabela já ESTRUTURADA com ~18 casos de
carregamento individuais (peso próprio, sobrecarga, vento, desaprumo etc.) e
dezenas de COMBINAÇÕES já somadas (N, Mx, My, Vx, Vy, Mt concomitantes por
linha). Como os dados já vêm em formato tabular limpo, um parser determinístico
é mais confiável do que pedir a um modelo de IA para ler/copiar corretamente
centenas de linhas numéricas de um PDF - e permite importar a ENVOLTÓRIA
completa de combinações (ver loads.py) em vez de um único valor por elemento.

FORMATO ESPERADO DA PLANILHA (uma aba, colunas A-G):
  - Uma linha "Fundação <id>" inicia o bloco de um elemento.
  - A linha seguinte é o cabeçalho fixo: Combinação | N (kN) | Mx (kN.m) |
    My (kN.m) | Vx (kN) | Vy (kN) | Mt (kN/m).
  - Em seguida, linhas de casos de carregamento INDIVIDUAIS (rótulo com
    parênteses, ex: "Peso próprio (G1)", "Vento X+ (V1)") - são IGNORADAS,
    pois não representam uma combinação de projeto por si só.
  - Depois, linhas de COMBINAÇÕES (rótulo sem parênteses, ex:
    "G1+G2+0.5Q+0.6V1+0.93D1") - cada uma vira uma `LoadCombination`.
  - O arquivo termina com uma seção "Legenda" (ignorada).

LIMITAÇÃO: o relatório não informa quantas estacas compõem cada fundação -
todo elemento é importado com n_piles=1 (carga já "por elemento"); ajuste
manualmente na interface se algum bloco tiver mais de uma estaca.
"""

from __future__ import annotations

from .loads import FoundationLoad, LoadCombination

_EXPECTED_HEADER_PREFIX = "Combinação"


class EberickImportError(RuntimeError):
    """Erro amigável ao interpretar a planilha de combinações do Eberick."""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_eberick_combinations_xlsx(path: str) -> list[FoundationLoad]:
    try:
        import openpyxl
    except ImportError as exc:
        raise EberickImportError(
            "Biblioteca 'openpyxl' não está instalada. Rode: pip install openpyxl"
        ) from exc

    try:
        workbook = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:  # noqa: BLE001 - qualquer erro de leitura vira mensagem amigável
        raise EberickImportError(f"Não foi possível abrir a planilha: {exc}") from exc

    sheet = workbook.worksheets[0]

    loads: list[FoundationLoad] = []
    current_id: str | None = None
    current_combinations: list[LoadCombination] = []
    inside_table = False

    def _flush_current() -> None:
        if current_id is None:
            return
        if not current_combinations:
            return
        max_n_kn = max(abs(c.n_kn) for c in current_combinations)
        loads.append(
            FoundationLoad(
                element_id=current_id,
                characteristic_load_kn=max_n_kn,
                n_piles=1,
                combinations=list(current_combinations),
            )
        )

    for row in sheet.iter_rows(values_only=True):
        label = row[0]
        if isinstance(label, str) and label.strip().startswith("Fundação"):
            _flush_current()
            current_id = label.strip()[len("Fundação"):].strip()
            current_combinations = []
            inside_table = False
            continue

        if isinstance(label, str) and label.strip() == _EXPECTED_HEADER_PREFIX:
            inside_table = True
            continue

        if isinstance(label, str) and label.strip() == "Legenda":
            inside_table = False
            continue

        if not inside_table or current_id is None:
            continue
        if not isinstance(label, str) or not label.strip():
            continue
        if not _is_number(row[1]):
            continue
        if "(" in label:
            # Caso de carregamento individual (ex: "Peso próprio (G1)") - não
            # é uma combinação de projeto, ignorar.
            continue

        n_kn = float(row[1])
        mx = float(row[2]) if _is_number(row[2]) else 0.0
        my = float(row[3]) if _is_number(row[3]) else 0.0
        vx = float(row[4]) if _is_number(row[4]) else 0.0
        vy = float(row[5]) if _is_number(row[5]) else 0.0
        current_combinations.append(
            LoadCombination(label=label.strip(), n_kn=n_kn, moment_x_knm=mx, moment_y_knm=my, shear_x_kn=vx, shear_y_kn=vy)
        )

    _flush_current()

    if not loads:
        raise EberickImportError(
            "Nenhuma fundação com combinações foi encontrada na planilha. Confira se é o "
            "relatório 'Esforços nas Fundações por Elementos' exportado em .xlsx pelo Eberick."
        )
    return loads
