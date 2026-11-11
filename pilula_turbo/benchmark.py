"""Teste de esforço: mede o computador antes e depois das pílulas.

Sem isto, qualquer "otimizador" é placebo. As medidas são simples e curtas
(cerca de 5 segundos no total) e variam alguns por cento de uma execução para
outra; diferenças abaixo de ~5% devem ser lidas como "sem efeito".
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time

# nome -> (rótulo, unidade, True se maior é melhor)
METRICAS = {
    "cpu": ("Processador", "MB/s", True),
    "memoria": ("Memória", "MB/s", True),
    "disco": ("Disco (gravação)", "MB/s", True),
    "resposta": ("Atraso de resposta", "ms", False),
}

RUIDO = 5.0  # variação (%) abaixo da qual não se afirma efeito


def medir_cpu(duracao: float = 1.2) -> float:
    bloco = b"\xa5" * (256 * 1024)
    n = 0
    inicio = time.perf_counter()
    while time.perf_counter() - inicio < duracao:
        hashlib.sha256(bloco).digest()
        n += 1
    return n * len(bloco) / (time.perf_counter() - inicio) / 1e6


def medir_memoria(duracao: float = 1.0) -> float:
    origem = bytearray(32 * 1024 * 1024)
    n = 0
    inicio = time.perf_counter()
    while time.perf_counter() - inicio < duracao:
        copia = bytes(origem)
        n += 1
    del copia
    return n * len(origem) / (time.perf_counter() - inicio) / 1e6


def medir_disco(tamanho_mb: int = 64, pasta: str | None = None) -> float:
    bloco = os.urandom(1024 * 1024)
    fd, caminho = tempfile.mkstemp(prefix="pilula_turbo_", suffix=".bin", dir=pasta)
    try:
        inicio = time.perf_counter()
        with os.fdopen(fd, "wb") as f:
            for _ in range(tamanho_mb):
                f.write(bloco)
            f.flush()
            os.fsync(f.fileno())
        return tamanho_mb / (time.perf_counter() - inicio)
    finally:
        try:
            os.remove(caminho)
        except OSError:
            pass


def medir_resposta(amostras: int = 150) -> float:
    """Quanto o sistema atrasa para acordar um programa (percentil 95, em ms).

    Pede pausas de 1 ms e mede o excesso. Com muita coisa disputando o
    processador, o atraso cresce - é o que se sente como "travadinhas".
    """
    excessos = []
    for _ in range(amostras):
        inicio = time.perf_counter()
        time.sleep(0.001)
        excessos.append((time.perf_counter() - inicio - 0.001) * 1000)
    excessos.sort()
    return max(0.0, excessos[int(len(excessos) * 0.95) - 1])


def medir_tudo(progresso=None) -> dict[str, float]:
    resultado = {}
    for nome, funcao in (
        ("cpu", medir_cpu), ("memoria", medir_memoria),
        ("disco", medir_disco), ("resposta", medir_resposta),
    ):
        if progresso:
            progresso(METRICAS[nome][0])
        resultado[nome] = round(funcao(), 2)
    return resultado


def comparar(antes: dict[str, float], depois: dict[str, float]) -> dict[str, float]:
    """Melhora percentual por métrica (positivo = ficou melhor)."""
    saida = {}
    for nome, (_, _, maior_melhor) in METRICAS.items():
        a, d = antes.get(nome), depois.get(nome)
        if not a or d is None:
            continue
        variacao = (d - a) / a * 100
        saida[nome] = round(variacao if maior_melhor else -variacao, 1)
    return saida


def veredito(melhoras: dict[str, float]) -> str:
    reais = {n: v for n, v in melhoras.items() if abs(v) >= RUIDO}
    if not reais:
        return ("Sem diferença mensurável (variações abaixo de 5% são ruído). "
                "Seu PC já estava perto do limite do hardware nessas medidas.")
    partes = [
        f"{METRICAS[n][0]} {'melhorou' if v > 0 else 'piorou'} {abs(v):.0f}%"
        for n, v in sorted(reais.items(), key=lambda x: -x[1])
    ]
    return "Efeito medido: " + "; ".join(partes) + "."
