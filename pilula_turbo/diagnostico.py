"""Exame: olha o computador e diz o que o está segurando (e o que não tem cura
por software)."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass

from . import sistema
from .pilulas import (
    Ambiente, PilulaEnergia, PilulaInicializacao, formatar_bytes,
    tamanho_temporarios,
)


@dataclass
class Achado:
    gravidade: str  # "ok", "atencao" ou "critico"
    titulo: str
    detalhe: str
    pilula: str | None = None  # ident da pílula que trata


def examinar(amb: Ambiente) -> tuple[list[str], list[Achado]]:
    """Devolve (ficha do computador, achados)."""
    ficha = [
        f"Sistema: {platform.system()} {platform.release()} ({platform.version()})",
        f"Processador: {sistema.nome_cpu()} - {os.cpu_count()} núcleos lógicos",
    ]
    achados: list[Achado] = []

    mem = sistema.memoria()
    if mem:
        total, livre = mem
        usado = 100 * (total - livre) / total
        ficha.append(f"Memória: {formatar_bytes(total)} ({usado:.0f}% em uso)")
        if total < 7.5 * 1024**3:
            achados.append(Achado(
                "critico", "Pouca memória RAM instalada",
                f"{formatar_bytes(total)} é pouco para o Windows atual. Nenhum "
                "programa cria memória: a cura de verdade é instalar mais RAM. "
                "'Partida limpa' ajuda a sobrar mais do que existe.",
                "inicializacao"))
        elif usado > 85:
            achados.append(Achado(
                "atencao", "Memória quase cheia agora",
                f"{usado:.0f}% em uso. Feche abas e programas que não está usando; "
                "'Partida limpa' evita que voltem sozinhos.", "inicializacao"))

    unidade = os.environ.get("SystemDrive", "C:") + "\\" if sistema.EH_WINDOWS else "/"
    try:
        disco = shutil.disk_usage(unidade)
        livre_pct = 100 * disco.free / disco.total
        tipo = sistema.tipo_disco_sistema()
        ficha.append(
            f"Disco do sistema: {tipo or 'tipo não identificado'}, "
            f"{formatar_bytes(disco.free)} livres de {formatar_bytes(disco.total)}")
        if tipo == "HDD":
            achados.append(Achado(
                "critico", "Windows instalado em disco rígido (HDD)",
                "Este é o maior freio do seu PC e não tem cura por software: "
                "trocar por um SSD é, de longe, a melhora que mais se sente."))
        if livre_pct < 10:
            achados.append(Achado(
                "critico", "Disco quase cheio",
                f"Só {livre_pct:.0f}% livre. O Windows precisa de espaço para "
                "trabalhar; abaixo de 10% ele fica lento.", "limpeza"))
    except OSError:
        pass

    temporarios = tamanho_temporarios(amb.pasta_temp)
    if temporarios > 500 * 1024**2:
        achados.append(Achado(
            "atencao", "Arquivos temporários acumulados",
            f"{formatar_bytes(temporarios)} em temporários antigos.", "limpeza"))

    try:
        if not PilulaEnergia().ativa(amb):
            nome = amb.energia.planos().get(amb.energia.ativo().lower(), "atual")
            achados.append(Achado(
                "atencao", "Processador em modo de economia",
                f"Plano de energia '{nome}': o processador reduz a velocidade para "
                "economizar energia.", "energia"))
    except (RuntimeError, OSError):
        pass

    partida = [n for n, _, ligado in PilulaInicializacao().itens(amb) if ligado]
    if len(partida) >= 4:
        achados.append(Achado(
            "atencao", f"{len(partida)} programas iniciam com o Windows",
            "Ex.: " + ", ".join(partida[:4]) + ". Cada um gasta memória e "
            "atrasa a partida.", "inicializacao"))

    ligado = sistema.tempo_ligado()
    if ligado and ligado > 7 * 86400:
        achados.append(Achado(
            "atencao", f"Windows sem reiniciar há {ligado / 86400:.0f} dias",
            "Reiniciar (não 'Desligar': com a Inicialização Rápida, desligar "
            "não zera o sistema) limpa memória e processos presos."))

    uso = sistema.uso_cpu()
    if uso is not None:
        ficha.append(f"Uso de CPU neste momento: {uso:.0f}%")
        if uso > 60:
            achados.append(Achado(
                "atencao", "Processador ocupado mesmo em repouso",
                f"{uso:.0f}% de uso sem você fazer nada: algo está trabalhando "
                "ao fundo. A Dose de Foco tira esses programas do caminho."))

    if not achados:
        achados.append(Achado(
            "ok", "Nada segurando o seu hardware",
            "Não encontrei nenhum dos freios comuns. O desempenho atual é "
            "essencialmente o limite do hardware."))
    return ficha, achados
