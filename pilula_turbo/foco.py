"""Dose de Foco: efeito temporário, como um remédio de verdade.

Enquanto a dose dura, o programa que você está usando (a janela em primeiro
plano) recebe prioridade de CPU acima do normal e os programas que estão
consumindo CPU ao fundo são rebaixados. Quando a dose acaba - ou você a
interrompe - todas as prioridades voltam ao que eram.
"""

from __future__ import annotations

import os
import time

from .sistema import ABAIXO_DO_NORMAL, ACIMA_DO_NORMAL, NORMAL

# Processos do próprio Windows: nunca mexer.
PROTEGIDOS = {
    "system", "[system process]", "idle", "registry", "memory compression",
    "csrss.exe", "smss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "dwm.exe", "explorer.exe", "audiodg.exe", "svchost.exe",
    "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "taskmgr.exe",
    "msmpeng.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe",
}

# Fração de um núcleo acima da qual um processo de fundo é rebaixado.
LIMITE_FUNDO = 0.10


class DoseFoco:
    def __init__(self, processos, meu_pid: int | None = None, relogio=time.monotonic):
        self.processos = processos
        self.meu_pid = os.getpid() if meu_pid is None else meu_pid
        self.relogio = relogio
        self.fim: float | None = None
        self.acelerado: int | None = None
        self.rebaixados: dict[int, str] = {}
        self._originais: dict[int, int] = {}
        self._cpu: dict[int, float] = {}
        self._ultimo: float | None = None

    @property
    def ativa(self) -> bool:
        return self.fim is not None

    def restante(self) -> float:
        return max(0.0, self.fim - self.relogio()) if self.ativa else 0.0

    def iniciar(self, minutos: float) -> None:
        self.parar()
        self.fim = self.relogio() + minutos * 60
        self._cpu, self._ultimo = {}, None

    def parar(self) -> None:
        """Encerra a dose e devolve todas as prioridades originais."""
        for pid, classe in list(self._originais.items()):
            self.processos.definir_prioridade(pid, classe)
        self._originais.clear()
        self.rebaixados.clear()
        self.acelerado = None
        self.fim = None

    def _mexivel(self, pid: int, nome: str | None) -> bool:
        return bool(
            nome and pid > 4 and pid != self.meu_pid and nome.lower() not in PROTEGIDOS
        )

    def _restaurar(self, pid: int) -> None:
        classe = self._originais.pop(pid, None)
        if classe is not None:
            self.processos.definir_prioridade(pid, classe)
        self.rebaixados.pop(pid, None)

    def pulso(self) -> bool:
        """Reavalia o sistema. Chamar a cada ~2 s. Devolve False ao expirar."""
        if not self.ativa:
            return False
        if self.relogio() >= self.fim:
            self.parar()
            return False

        vivos = self.processos.listar()
        # Processo encerrado: esquecer (o PID pode ser reutilizado por outro).
        for pid in [p for p in self._originais if p not in vivos]:
            self._originais.pop(pid)
            self.rebaixados.pop(pid, None)
            if self.acelerado == pid:
                self.acelerado = None

        frente = self.processos.pid_primeiro_plano()
        if frente is not None and self._mexivel(frente, vivos.get(frente)):
            if frente != self.acelerado:
                if self.acelerado is not None:
                    self._restaurar(self.acelerado)
                if frente in self.rebaixados:
                    self._restaurar(frente)
                self.acelerado = None
                if self.processos.prioridade(frente) == NORMAL and \
                        self.processos.definir_prioridade(frente, ACIMA_DO_NORMAL):
                    self._originais[frente] = NORMAL
                    self.acelerado = frente

        agora = self.relogio()
        decorrido = (agora - self._ultimo) if self._ultimo is not None else 0.0
        novos: dict[int, float] = {}
        for pid, nome in vivos.items():
            if pid == frente or pid == self.acelerado or not self._mexivel(pid, nome):
                continue
            t = self.processos.tempo_cpu(pid)
            if t is None:
                continue
            novos[pid] = t
            anterior = self._cpu.get(pid)
            if anterior is None or decorrido <= 0 or pid in self._originais:
                continue
            if (t - anterior) / decorrido >= LIMITE_FUNDO and \
                    self.processos.prioridade(pid) == NORMAL and \
                    self.processos.definir_prioridade(pid, ABAIXO_DO_NORMAL):
                self._originais[pid] = NORMAL
                self.rebaixados[pid] = nome
        self._cpu, self._ultimo = novos, agora
        return True
