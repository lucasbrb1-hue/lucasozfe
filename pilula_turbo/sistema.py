"""Acesso ao Windows (registro, energia, processos, medições).

Tudo que toca o sistema operacional fica aqui, atrás de classes pequenas.
O resto do programa recebe essas classes prontas, o que permite testá-lo com
as versões "Memoria" (falsas) em qualquer sistema, sem alterar nada de verdade.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time

EH_WINDOWS = sys.platform == "win32"

if EH_WINDOWS:
    import winreg
    from ctypes import wintypes

_GUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"


def rodar(args: list[str], timeout: float = 15.0) -> str:
    """Roda um comando sem abrir janela de console e devolve a saída."""
    flags = 0x08000000 if EH_WINDOWS else 0  # CREATE_NO_WINDOW
    r = subprocess.run(
        args, capture_output=True, timeout=timeout, creationflags=flags,
        stdin=subprocess.DEVNULL,
    )
    saida = r.stdout.decode("utf-8", errors="replace")
    if r.returncode != 0:
        erro = r.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{args[0]} falhou ({r.returncode}): {erro or saida.strip()}")
    return saida


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------

class RegistroMemoria:
    """Registro falso, em memória (testes e modo demonstração)."""

    def __init__(self):
        self.dados: dict[str, dict[str, tuple[object, str]]] = {}

    def ler(self, caminho: str, nome: str):
        return self.dados.get(caminho, {}).get(nome)

    def escrever(self, caminho: str, nome: str, valor, tipo: str) -> None:
        self.dados.setdefault(caminho, {})[nome] = (valor, tipo)

    def apagar(self, caminho: str, nome: str) -> None:
        self.dados.get(caminho, {}).pop(nome, None)

    def valores(self, caminho: str) -> dict[str, tuple[object, str]]:
        return dict(self.dados.get(caminho, {}))


class RegistroWindows:
    """Registro real. Caminhos no formato ``HKCU\\Software\\...``."""

    def __init__(self):
        self._raizes = {
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
        }
        self._tipos = {
            "dword": winreg.REG_DWORD,
            "qword": winreg.REG_QWORD,
            "sz": winreg.REG_SZ,
            "expand_sz": winreg.REG_EXPAND_SZ,
            "binary": winreg.REG_BINARY,
        }
        self._nomes = {v: k for k, v in self._tipos.items()}

    def _partes(self, caminho: str):
        raiz, _, sub = caminho.partition("\\")
        return self._raizes[raiz], sub

    def ler(self, caminho: str, nome: str):
        raiz, sub = self._partes(caminho)
        try:
            with winreg.OpenKey(raiz, sub) as chave:
                valor, tipo = winreg.QueryValueEx(chave, nome)
        except FileNotFoundError:
            return None
        return valor, self._nomes.get(tipo, "sz")

    def escrever(self, caminho: str, nome: str, valor, tipo: str) -> None:
        raiz, sub = self._partes(caminho)
        with winreg.CreateKeyEx(raiz, sub, 0, winreg.KEY_SET_VALUE) as chave:
            winreg.SetValueEx(chave, nome, 0, self._tipos[tipo], valor)

    def apagar(self, caminho: str, nome: str) -> None:
        raiz, sub = self._partes(caminho)
        try:
            with winreg.OpenKey(raiz, sub, 0, winreg.KEY_SET_VALUE) as chave:
                winreg.DeleteValue(chave, nome)
        except FileNotFoundError:
            pass

    def valores(self, caminho: str) -> dict[str, tuple[object, str]]:
        raiz, sub = self._partes(caminho)
        saida = {}
        try:
            with winreg.OpenKey(raiz, sub) as chave:
                i = 0
                while True:
                    try:
                        nome, valor, tipo = winreg.EnumValue(chave, i)
                    except OSError:
                        break
                    saida[nome] = (valor, self._nomes.get(tipo, "sz"))
                    i += 1
        except FileNotFoundError:
            pass
        return saida


# --------------------------------------------------------------------------
# Planos de energia
# --------------------------------------------------------------------------

class EnergiaMemoria:
    EQUILIBRADO = "381b4222-f694-41f0-9685-ff5bb260df2e"

    def __init__(self):
        self._planos = {self.EQUILIBRADO: "Equilibrado"}
        self._ativo = self.EQUILIBRADO
        self._n = 0

    def planos(self) -> dict[str, str]:
        return dict(self._planos)

    def ativo(self) -> str:
        return self._ativo

    def ativar(self, guid: str) -> None:
        if guid not in self._planos:
            raise RuntimeError("plano inexistente")
        self._ativo = guid

    def duplicar(self, guid: str) -> str:
        self._n += 1
        novo = f"00000000-0000-0000-0000-{self._n:012d}"
        self._planos[novo] = "Alto desempenho"
        return novo

    def apagar(self, guid: str) -> None:
        self._planos.pop(guid, None)


class EnergiaWindows:
    """Planos de energia via ``powercfg`` (não exige administrador)."""

    def planos(self) -> dict[str, str]:
        saida = rodar(["powercfg", "/list"])
        return {
            m.group(1).lower(): m.group(2)
            for m in re.finditer(rf"({_GUID})\s+\((.*?)\)", saida)
        }

    def ativo(self) -> str:
        m = re.search(_GUID, rodar(["powercfg", "/getactivescheme"]))
        if not m:
            raise RuntimeError("não foi possível ler o plano de energia ativo")
        return m.group(0).lower()

    def ativar(self, guid: str) -> None:
        rodar(["powercfg", "/setactive", guid])

    def duplicar(self, guid: str) -> str:
        m = re.search(_GUID, rodar(["powercfg", "/duplicatescheme", guid]))
        if not m:
            raise RuntimeError("o Windows não permitiu criar o plano de alto desempenho")
        return m.group(0).lower()

    def apagar(self, guid: str) -> None:
        rodar(["powercfg", "/delete", guid])


# --------------------------------------------------------------------------
# Processos (prioridades) - usado pela Dose de Foco
# --------------------------------------------------------------------------

NORMAL = 0x20
ACIMA_DO_NORMAL = 0x8000
ABAIXO_DO_NORMAL = 0x4000


class ProcessosWindows:
    _CONSULTAR = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
    _ALTERAR = 0x0200    # PROCESS_SET_INFORMATION

    def __init__(self):
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u = ctypes.WinDLL("user32", use_last_error=True)

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        self._Entrada = PROCESSENTRY32W
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for f in (k.Process32FirstW, k.Process32NextW):
            f.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
            f.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.GetPriorityClass.argtypes = [wintypes.HANDLE]
        k.GetPriorityClass.restype = wintypes.DWORD
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.SetPriorityClass.restype = wintypes.BOOL
        k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        k.GetProcessTimes.restype = wintypes.BOOL
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._k, self._u = k, u

    def _abrir(self, pid: int, acesso: int):
        return self._k.OpenProcess(acesso, False, pid) or None

    def listar(self) -> dict[int, str]:
        """{pid: nome do executável} de todos os processos."""
        foto = self._k.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not foto or foto == ctypes.c_void_p(-1).value:
            return {}
        saida = {}
        try:
            e = self._Entrada()
            e.dwSize = ctypes.sizeof(e)
            ok = self._k.Process32FirstW(foto, ctypes.byref(e))
            while ok:
                saida[int(e.th32ProcessID)] = e.szExeFile
                ok = self._k.Process32NextW(foto, ctypes.byref(e))
        finally:
            self._k.CloseHandle(foto)
        return saida

    def pid_primeiro_plano(self) -> int | None:
        janela = self._u.GetForegroundWindow()
        if not janela:
            return None
        pid = wintypes.DWORD(0)
        self._u.GetWindowThreadProcessId(janela, ctypes.byref(pid))
        return int(pid.value) or None

    def tempo_cpu(self, pid: int) -> float | None:
        """Segundos de CPU já consumidos pelo processo (None se inacessível)."""
        h = self._abrir(pid, self._CONSULTAR)
        if not h:
            return None
        try:
            t = [wintypes.FILETIME() for _ in range(4)]
            if not self._k.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
                return None
            total = sum((x.dwHighDateTime << 32) | x.dwLowDateTime for x in t[2:])
            return total / 1e7
        finally:
            self._k.CloseHandle(h)

    def prioridade(self, pid: int) -> int | None:
        h = self._abrir(pid, self._CONSULTAR)
        if not h:
            return None
        try:
            return int(self._k.GetPriorityClass(h)) or None
        finally:
            self._k.CloseHandle(h)

    def definir_prioridade(self, pid: int, classe: int) -> bool:
        h = self._abrir(pid, self._ALTERAR)
        if not h:
            return False
        try:
            return bool(self._k.SetPriorityClass(h, classe))
        finally:
            self._k.CloseHandle(h)


# --------------------------------------------------------------------------
# Medições para o exame
# --------------------------------------------------------------------------

def memoria() -> tuple[int, int] | None:
    """(total, livre) em bytes da memória RAM."""
    if not EH_WINDOWS:
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    if not ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return int(m.ullTotalPhys), int(m.ullAvailPhys)


def nome_cpu() -> str:
    if EH_WINDOWS:
        try:
            v = RegistroWindows().ler(
                r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                "ProcessorNameString",
            )
            if v:
                return str(v[0]).strip()
        except OSError:
            pass
    import platform
    return platform.processor() or "Processador"


def uso_cpu(intervalo: float = 0.5) -> float | None:
    """Uso total de CPU (%) medido durante ``intervalo`` segundos."""
    if not EH_WINDOWS:
        return None
    k = ctypes.WinDLL("kernel32")

    def ler():
        t = [wintypes.FILETIME() for _ in range(3)]
        if not k.GetSystemTimes(*[ctypes.byref(x) for x in t]):
            return None
        return [(x.dwHighDateTime << 32) | x.dwLowDateTime for x in t]

    a = ler()
    time.sleep(intervalo)
    b = ler()
    if not a or not b:
        return None
    ocioso = b[0] - a[0]
    total = (b[1] - a[1]) + (b[2] - a[2])  # núcleo (inclui ocioso) + usuário
    if total <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (total - ocioso) / total))


def tempo_ligado() -> float | None:
    """Segundos desde a última inicialização completa do Windows."""
    if not EH_WINDOWS:
        return None
    f = ctypes.WinDLL("kernel32").GetTickCount64
    f.restype = ctypes.c_ulonglong
    return f() / 1000.0


def tipo_disco_sistema() -> str | None:
    """"SSD" ou "HDD" para o disco onde o Windows está instalado."""
    if not EH_WINDOWS:
        return None
    letra = os.environ.get("SystemDrive", "C:")[0]
    comando = (
        f"(Get-Partition -DriveLetter {letra} | Get-Disk | Get-PhysicalDisk).MediaType"
    )
    try:
        saida = rodar(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            timeout=12,
        ).strip().upper()
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None
    if "SSD" in saida:
        return "SSD"
    if "HDD" in saida:
        return "HDD"
    return None


def pasta_dados() -> str:
    """Pasta onde a Pílula Turbo guarda o que alterou (para poder desfazer)."""
    base = os.environ.get("APPDATA") if EH_WINDOWS else None
    pasta = os.path.join(base, "PilulaTurbo") if base else os.path.expanduser("~/.pilula_turbo")
    os.makedirs(pasta, exist_ok=True)
    return pasta
