"""As pílulas: ajustes reais do Windows, cada um com bula e antídoto.

Regra de ouro: antes de alterar qualquer coisa, o valor original é gravado em
disco (``Estado``). "Reverter" devolve exatamente o que estava lá.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
import time
from dataclasses import dataclass, field


class Estado:
    """Memória persistente do que foi alterado (arquivo JSON)."""

    def __init__(self, caminho: str | None = None):
        self.caminho = caminho
        self.dados: dict = {}
        if caminho and os.path.exists(caminho):
            try:
                with open(caminho, encoding="utf-8") as f:
                    self.dados = json.load(f)
            except (OSError, ValueError):
                self.dados = {}

    def salvar(self) -> None:
        if not self.caminho:
            return
        provisorio = self.caminho + ".tmp"
        with open(provisorio, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, indent=2, ensure_ascii=False)
        os.replace(provisorio, self.caminho)

    def pilula(self, ident: str) -> dict | None:
        return self.dados.get("pilulas", {}).get(ident)

    def gravar_pilula(self, ident: str, conteudo: dict | None) -> None:
        pilulas = self.dados.setdefault("pilulas", {})
        if conteudo is None:
            pilulas.pop(ident, None)
        else:
            pilulas[ident] = conteudo
        self.salvar()


@dataclass
class Ambiente:
    """Tudo de que uma pílula precisa para agir."""
    registro: object
    energia: object
    estado: Estado
    pasta_temp: str = field(default_factory=tempfile.gettempdir)


def _guardar(lido) -> dict | None:
    """Converte um valor lido do registro em algo que cabe no JSON."""
    if lido is None:
        return None
    valor, tipo = lido
    if isinstance(valor, (bytes, bytearray)):
        return {"tipo": tipo, "hex": bytes(valor).hex()}
    return {"tipo": tipo, "valor": valor}


def _restaurar(registro, caminho: str, nome: str, guardado: dict | None) -> None:
    if guardado is None:
        registro.apagar(caminho, nome)
    elif "hex" in guardado:
        registro.escrever(caminho, nome, bytes.fromhex(guardado["hex"]), guardado["tipo"])
    else:
        registro.escrever(caminho, nome, guardado["valor"], guardado["tipo"])


class Pilula:
    ident = ""
    nome = ""
    resumo = ""
    bula = ""
    reversivel = True

    def ativa(self, amb: Ambiente) -> bool:
        raise NotImplementedError

    def tomar(self, amb: Ambiente, **opcoes) -> str:
        raise NotImplementedError

    def reverter(self, amb: Ambiente) -> str:
        raise NotImplementedError


class PilulaRegistro(Pilula):
    """Pílula feita de valores do registro do usuário (HKCU, sem administrador)."""

    ajustes: list[tuple[str, str, object, str]] = []  # caminho, nome, valor, tipo

    def ativa(self, amb):
        for caminho, nome, valor, _ in self.ajustes:
            lido = amb.registro.ler(caminho, nome)
            if lido is None or lido[0] != valor:
                return False
        return True

    def tomar(self, amb, **opcoes):
        # Nunca sobrescreve originais já guardados (tomar duas vezes é seguro).
        guardado = amb.estado.pilula(self.ident) or {"originais": {}}
        for caminho, nome, _, _ in self.ajustes:
            chave = f"{caminho}|{nome}"
            if chave not in guardado["originais"]:
                guardado["originais"][chave] = _guardar(amb.registro.ler(caminho, nome))
        amb.estado.gravar_pilula(self.ident, guardado)
        for caminho, nome, valor, tipo in self.ajustes:
            amb.registro.escrever(caminho, nome, valor, tipo)
        return f"{self.nome}: aplicada."

    def reverter(self, amb):
        guardado = amb.estado.pilula(self.ident)
        if not guardado:
            return f"{self.nome}: o Windows já estava assim antes; nada a desfazer."
        for chave, original in guardado["originais"].items():
            caminho, nome = chave.split("|", 1)
            _restaurar(amb.registro, caminho, nome, original)
        amb.estado.gravar_pilula(self.ident, None)
        return f"{self.nome}: revertida, valores originais restaurados."


class PilulaVisual(PilulaRegistro):
    ident = "visual"
    nome = "Interface leve"
    resumo = "Desliga transparência e animações de janelas, menus e barra de tarefas."
    bula = (
        "Efeito: menos trabalho para a placa de vídeo e resposta mais seca ao "
        "abrir janelas e menus. Mais perceptível em PCs com vídeo integrado.\n"
        "Colateral: o Windows fica visualmente mais simples.\n"
        "Parte do efeito só aparece depois de sair e entrar de novo na conta."
    )
    ajustes = [
        (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
         "EnableTransparency", 0, "dword"),
        (r"HKCU\Control Panel\Desktop\WindowMetrics", "MinAnimate", "0", "sz"),
        (r"HKCU\Control Panel\Desktop", "MenuShowDelay", "0", "sz"),
        (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
         "TaskbarAnimations", 0, "dword"),
    ]


class PilulaJogos(PilulaRegistro):
    ident = "jogos"
    nome = "Modo jogo"
    resumo = "Liga o Modo de Jogo e desliga a gravação em segundo plano do Xbox Game Bar."
    bula = (
        "Efeito: o Windows prioriza o jogo em tela cheia e para de gravar "
        "vídeo o tempo todo (o que consome CPU, GPU e disco).\n"
        "Colateral: 'gravar os últimos 30 segundos' do Game Bar deixa de funcionar."
    )
    ajustes = [
        (r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, "dword"),
        (r"HKCU\System\GameConfigStore", "GameDVR_Enabled", 0, "dword"),
        (r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR",
         "AppCaptureEnabled", 0, "dword"),
    ]


class PilulaEnergia(Pilula):
    ident = "energia"
    nome = "Energia máxima"
    resumo = "Ativa o plano de energia 'Alto desempenho' (o processador para de economizar)."
    bula = (
        "Efeito: o processador mantém a frequência alta em vez de reduzir para "
        "economizar. É a pílula com maior efeito em notebooks.\n"
        "Colateral: mais consumo, mais calor e menos bateria. Use na tomada."
    )
    ALTO = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

    def ativa(self, amb):
        guardado = amb.estado.pilula(self.ident)
        ativo = amb.energia.ativo().lower()
        return ativo == self.ALTO or bool(guardado and guardado.get("alvo") == ativo)

    def tomar(self, amb, **opcoes):
        if self.ativa(amb):
            return f"{self.nome}: já está ativa."
        anterior = amb.energia.ativo().lower()
        criado = None
        alvo = self.ALTO
        if alvo not in {g.lower() for g in amb.energia.planos()}:
            # Muitos notebooks escondem o plano; o Windows permite recriá-lo.
            alvo = criado = amb.energia.duplicar(self.ALTO).lower()
        amb.estado.gravar_pilula(
            self.ident, {"anterior": anterior, "alvo": alvo, "criado": criado}
        )
        amb.energia.ativar(alvo)
        return f"{self.nome}: plano de alto desempenho ativado."

    def reverter(self, amb):
        guardado = amb.estado.pilula(self.ident)
        if not guardado:
            return f"{self.nome}: o Windows já estava assim antes; nada a desfazer."
        amb.energia.ativar(guardado["anterior"])
        if guardado.get("criado"):
            try:
                amb.energia.apagar(guardado["criado"])
            except (RuntimeError, OSError):
                pass  # plano extra sobrando não atrapalha nada
        amb.estado.gravar_pilula(self.ident, None)
        return f"{self.nome}: plano de energia anterior restaurado."


class PilulaInicializacao(Pilula):
    ident = "inicializacao"
    nome = "Partida limpa"
    resumo = "Impede programas de abrirem sozinhos junto com o Windows."
    bula = (
        "Efeito: o Windows liga mais rápido e sobra memória e CPU, porque menos "
        "programas ficam rodando escondidos.\n"
        "Colateral: os programas desmarcados só abrem quando você abrir. "
        "Sincronizadores (OneDrive, Drive) e mensageiros deixam de iniciar sozinhos.\n"
        "É o mesmo interruptor da aba 'Inicializar' do Gerenciador de Tarefas. "
        "Programas instalados para todos os usuários não são tocados."
    )
    RUN = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    APROVADO = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

    def itens(self, amb) -> list[tuple[str, str, bool]]:
        """(nome, comando, habilitado) dos programas que iniciam com o Windows."""
        saida = []
        for nome, (comando, _) in sorted(amb.registro.valores(self.RUN).items()):
            marca = amb.registro.ler(self.APROVADO, nome)
            # Primeiro byte ímpar = desabilitado (convenção do próprio Windows).
            desligado = bool(marca and marca[0] and bytes(marca[0])[0] % 2 == 1)
            saida.append((nome, str(comando), not desligado))
        return saida

    def ativa(self, amb):
        guardado = amb.estado.pilula(self.ident)
        return bool(guardado and guardado.get("originais"))

    def tomar(self, amb, nomes: list[str] | None = None, **opcoes):
        habilitados = [n for n, _, ligado in self.itens(amb) if ligado]
        alvos = [n for n in habilitados if nomes is None or n in nomes]
        if not alvos:
            return f"{self.nome}: nenhum programa para desligar."
        guardado = amb.estado.pilula(self.ident) or {"originais": {}}
        for nome in alvos:
            if nome not in guardado["originais"]:
                guardado["originais"][nome] = _guardar(amb.registro.ler(self.APROVADO, nome))
        amb.estado.gravar_pilula(self.ident, guardado)
        agora = int(time.time() * 1e7) + 116444736000000000  # FILETIME
        marca = struct.pack("<IQ", 3, agora)
        for nome in alvos:
            amb.registro.escrever(self.APROVADO, nome, marca, "binary")
        return f"{self.nome}: {len(alvos)} programa(s) não iniciam mais com o Windows."

    def reverter(self, amb):
        guardado = amb.estado.pilula(self.ident)
        if not guardado:
            return f"{self.nome}: nada a desfazer."
        for nome, original in guardado["originais"].items():
            _restaurar(amb.registro, self.APROVADO, nome, original)
        amb.estado.gravar_pilula(self.ident, None)
        return f"{self.nome}: inicialização automática restaurada."


def _eh_atalho(entrada) -> bool:
    """Links simbólicos e junções: nunca seguir, nunca apagar o destino."""
    if entrada.is_symlink():
        return True
    eh_juncao = getattr(entrada, "is_junction", None)
    return bool(eh_juncao and eh_juncao())


def tamanho_temporarios(pasta: str, idade_min_s: float = 24 * 3600) -> int:
    """Bytes de arquivos temporários antigos que a limpeza removeria."""
    return _varrer(pasta, idade_min_s, apagar=False)[0]


def _varrer(pasta: str, idade_min_s: float, apagar: bool) -> tuple[int, int]:
    limite = time.time() - idade_min_s
    total = arquivos = 0
    try:
        entradas = list(os.scandir(pasta))
    except OSError:
        return 0, 0
    for e in entradas:
        try:
            if _eh_atalho(e):
                continue
            if e.is_dir(follow_symlinks=False):
                # _MEI*: pasta de trabalho de programas empacotados em execução
                # (inclusive a própria Pílula Turbo quando roda como .exe).
                if e.name.startswith("_MEI"):
                    continue
                b, n = _varrer(e.path, idade_min_s, apagar)
                total += b
                arquivos += n
                if apagar:
                    try:
                        os.rmdir(e.path)  # só sai se ficou vazia
                    except OSError:
                        pass
            else:
                info = e.stat(follow_symlinks=False)
                if info.st_mtime > limite:
                    continue
                if apagar:
                    os.remove(e.path)  # em uso -> o Windows recusa; seguimos
                total += info.st_size
                arquivos += 1
        except OSError:
            continue
    return total, arquivos


class PilulaLimpeza(Pilula):
    ident = "limpeza"
    nome = "Faxina de temporários"
    resumo = "Apaga arquivos temporários do seu usuário com mais de 24 horas."
    bula = (
        "Efeito: libera espaço em disco. Disco quase cheio deixa o Windows "
        "lento; com espaço sobrando, o ganho de velocidade é pequeno.\n"
        "Colateral: nenhum conhecido. Arquivos em uso são pulados.\n"
        "Dose única: é a única pílula que não tem antídoto (o que foi apagado "
        "não volta)."
    )
    reversivel = False

    def ativa(self, amb):
        return False

    def tomar(self, amb, **opcoes):
        liberado, arquivos = _varrer(amb.pasta_temp, 24 * 3600, apagar=True)
        return f"{self.nome}: {arquivos} arquivo(s) apagados, {formatar_bytes(liberado)} liberados."

    def reverter(self, amb):
        return f"{self.nome}: não há o que reverter."


def formatar_bytes(n: float) -> str:
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidade == "TB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"


def todas() -> list[Pilula]:
    return [
        PilulaEnergia(),
        PilulaInicializacao(),
        PilulaVisual(),
        PilulaJogos(),
        PilulaLimpeza(),
    ]


def antidoto(amb: Ambiente) -> list[str]:
    """Desfaz tudo o que a Pílula Turbo alterou."""
    mensagens = []
    for p in todas():
        if p.reversivel and amb.estado.pilula(p.ident):
            mensagens.append(p.reverter(amb))
    return mensagens or ["Nenhuma pílula ativa para reverter."]
