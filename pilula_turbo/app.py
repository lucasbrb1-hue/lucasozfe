"""Interface da Pílula Turbo (Tkinter, sem dependências externas)."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox

from . import __version__, benchmark, sistema
from .diagnostico import examinar
from .foco import DoseFoco
from .pilulas import Ambiente, Estado, PilulaInicializacao, antidoto, todas

FUNDO, CARTAO, BORDA = "#0f1420", "#182033", "#263149"
TEXTO, FRACO = "#e8ecf4", "#8b96ab"
VERDE, AMARELO, VERMELHO = "#35d0a5", "#ffb454", "#ff6b6b"
FONTE = "Segoe UI"
CORES_GRAVIDADE = {"ok": VERDE, "atencao": AMARELO, "critico": VERMELHO}


class ProcessosDemo:
    """Usado fora do Windows: a Dose de Foco não encontra nada para alterar."""

    def listar(self):
        return {}

    def pid_primeiro_plano(self):
        return None

    def tempo_cpu(self, pid):
        return None

    def prioridade(self, pid):
        return None

    def definir_prioridade(self, pid, classe):
        return False


def criar_ambiente() -> tuple[Ambiente, object]:
    if sistema.EH_WINDOWS:
        estado = Estado(os.path.join(sistema.pasta_dados(), "estado.json"))
        amb = Ambiente(sistema.RegistroWindows(), sistema.EnergiaWindows(), estado)
        return amb, sistema.ProcessosWindows()
    # Modo demonstração: nada do sistema é alterado.
    return Ambiente(sistema.RegistroMemoria(), sistema.EnergiaMemoria(), Estado()), ProcessosDemo()


class App:
    def __init__(self, raiz: tk.Tk, amb: Ambiente | None = None, processos=None):
        if amb is None:
            amb, processos = criar_ambiente()
        self.raiz, self.amb = raiz, amb
        self.pilulas = todas()
        self.foco = DoseFoco(processos or ProcessosDemo())
        self.fila: queue.Queue = queue.Queue()
        self.ocupado = False
        self.cartoes: dict[str, tuple[tk.Label, tk.Button]] = {}

        raiz.title("Pílula Turbo")
        raiz.configure(bg=FUNDO)
        raiz.geometry("1060x780")
        raiz.minsize(940, 700)
        raiz.protocol("WM_DELETE_WINDOW", self._fechar)

        self._montar()
        self._atualizar_pilulas()
        self._mostrar_medidas()
        self.raiz.after(100, self._drenar_fila)
        self.raiz.after(2000, self._pulso_foco)

    # ------------------------------------------------------------ montagem
    def _rotulo(self, pai, texto, tamanho=10, cor=TEXTO, negrito=False, **kw):
        fonte = (FONTE, tamanho, "bold" if negrito else "normal")
        return tk.Label(pai, text=texto, bg=pai["bg"], fg=cor, font=fonte,
                        anchor="w", justify="left", **kw)

    def _botao(self, pai, texto, comando, cor=VERDE, **kw):
        return tk.Button(
            pai, text=texto, command=comando, bg=cor, fg="#08110e",
            activebackground=TEXTO, relief="flat", bd=0, padx=12, pady=5,
            font=(FONTE, 9, "bold"), cursor="hand2", **kw)

    def _cartao(self, pai, **kw):
        return tk.Frame(pai, bg=CARTAO, highlightbackground=BORDA,
                        highlightthickness=1, padx=12, pady=10, **kw)

    def _montar(self):
        topo = tk.Frame(self.raiz, bg=FUNDO, padx=20, pady=14)
        topo.pack(fill="x")
        self._rotulo(topo, "Pílula Turbo", 20, VERDE, True).pack(side="left")
        self._rotulo(
            topo, "  Não cria hardware novo. Tira do caminho o que segura o seu.",
            10, FRACO).pack(side="left", pady=(8, 0))
        self._rotulo(topo, f"v{__version__}", 9, FRACO).pack(side="right")
        if not sistema.EH_WINDOWS:
            self._rotulo(
                self.raiz, "  Modo demonstração (fora do Windows): nada é alterado.",
                9, AMARELO).pack(fill="x", padx=20)

        rodape = tk.Frame(self.raiz, bg=FUNDO, padx=20, pady=12)
        rodape.pack(fill="x", side="bottom")
        self.rotulo_status = self._rotulo(rodape, "Pronto.", 9, FRACO)
        self.rotulo_status.pack(side="left", fill="x", expand=True)
        self._botao(rodape, "Antídoto: desfazer tudo", self._antidoto, VERMELHO).pack(side="right")

        corpo = tk.Frame(self.raiz, bg=FUNDO, padx=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1, uniform="c")
        corpo.columnconfigure(1, weight=1, uniform="c")
        corpo.rowconfigure(0, weight=1)
        esquerda = tk.Frame(corpo, bg=FUNDO)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        direita = tk.Frame(corpo, bg=FUNDO)
        direita.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # 1. Exame
        exame = self._cartao(esquerda)
        exame.pack(fill="both", expand=True)
        linha = tk.Frame(exame, bg=CARTAO)
        linha.pack(fill="x")
        self._rotulo(linha, "1. Exame", 12, negrito=True).pack(side="left")
        self._botao(linha, "Examinar o PC", self._examinar).pack(side="right")
        self.texto_exame = tk.Text(
            exame, bg=CARTAO, fg=TEXTO, relief="flat", wrap="word", height=10,
            font=(FONTE, 9), padx=0, pady=8, highlightthickness=0)
        self.texto_exame.pack(fill="both", expand=True)
        for nome, cor in CORES_GRAVIDADE.items():
            self.texto_exame.tag_configure(nome, foreground=cor, font=(FONTE, 10, "bold"))
        self.texto_exame.tag_configure("fraco", foreground=FRACO)
        self._escrever_exame([("Clique em 'Examinar o PC' para descobrir o que "
                               "está segurando o seu computador.\n", "fraco")])

        # 3. Efeito medido
        medida = self._cartao(esquerda)
        medida.pack(fill="x", pady=(12, 0))
        linha = tk.Frame(medida, bg=CARTAO)
        linha.pack(fill="x")
        self._rotulo(linha, "3. Efeito medido", 12, negrito=True).pack(side="left")
        zerar = self._botao(linha, "Nova referência", self._zerar_medidas, BORDA)
        zerar.configure(fg=TEXTO)
        zerar.pack(side="right")
        self.botao_medir = self._botao(linha, "Medir", self._medir)
        self.botao_medir.pack(side="right", padx=6)
        grade = tk.Frame(medida, bg=CARTAO)
        grade.pack(fill="x", pady=(8, 0))
        for c, t in enumerate(("", "Antes", "Depois", "Melhora")):
            self._rotulo(grade, t, 9, FRACO).grid(row=0, column=c, sticky="w", padx=(0, 18))
        self.celulas: dict[str, list[tk.Label]] = {}
        for r, (nome, (rotulo, unidade, _)) in enumerate(benchmark.METRICAS.items(), 1):
            self._rotulo(grade, f"{rotulo} ({unidade})", 9).grid(
                row=r, column=0, sticky="w", padx=(0, 18), pady=1)
            self.celulas[nome] = []
            for c in (1, 2, 3):
                cel = self._rotulo(grade, "-", 9)
                cel.grid(row=r, column=c, sticky="w", padx=(0, 18))
                self.celulas[nome].append(cel)
        self.rotulo_veredito = self._rotulo(medida, "", 9, FRACO, wraplength=440)
        self.rotulo_veredito.pack(fill="x", pady=(8, 0))

        # 2. Pílulas
        self._rotulo(direita, "2. Tratamento", 12, negrito=True).pack(fill="x", pady=(0, 6))
        for p in self.pilulas:
            c = self._cartao(direita)
            c.pack(fill="x", pady=(0, 8))
            linha = tk.Frame(c, bg=CARTAO)
            linha.pack(fill="x")
            self._rotulo(linha, p.nome, 11, negrito=True).pack(side="left")
            situacao = self._rotulo(linha, "", 9, FRACO)
            situacao.pack(side="left", padx=8)
            botao = self._botao(linha, "Tomar", lambda p=p: self._alternar(p))
            botao.pack(side="right")
            bula = self._botao(linha, "Bula", lambda p=p: self._bula(p), BORDA)
            bula.configure(fg=TEXTO)
            bula.pack(side="right", padx=6)
            self._rotulo(c, p.resumo, 9, FRACO, wraplength=440).pack(fill="x", pady=(4, 0))
            self.cartoes[p.ident] = (situacao, botao)

        # Dose de Foco
        c = self._cartao(direita)
        c.pack(fill="x", pady=(0, 8))
        linha = tk.Frame(c, bg=CARTAO)
        linha.pack(fill="x")
        self._rotulo(linha, "Dose de Foco", 11, negrito=True).pack(side="left")
        self.rotulo_foco = self._rotulo(linha, "", 9, FRACO)
        self.rotulo_foco.pack(side="left", padx=8)
        self.botao_foco = self._botao(linha, "Tomar", self._alternar_foco)
        self.botao_foco.pack(side="right")
        self._rotulo(linha, "min", 9, FRACO).pack(side="right", padx=(0, 6))
        self.minutos = tk.IntVar(value=60)
        tk.Spinbox(linha, from_=5, to=480, increment=5, width=4, textvariable=self.minutos,
                   bg=FUNDO, fg=TEXTO, buttonbackground=BORDA, relief="flat",
                   insertbackground=TEXTO, font=(FONTE, 9)).pack(side="right", padx=(6, 2))
        self._rotulo(
            c, "Efeito temporário: o programa que você estiver usando ganha "
               "prioridade de CPU e os que trabalham ao fundo são rebaixados. "
               "Ao acabar a dose, tudo volta ao normal.",
            9, FRACO, wraplength=440).pack(fill="x", pady=(4, 0))


    # ------------------------------------------------------- infraestrutura
    def _status(self, texto: str, cor: str = FRACO):
        self.rotulo_status.configure(text=texto, fg=cor)

    def _em_segundo_plano(self, trabalho, ao_terminar, aviso: str):
        """Roda ``trabalho`` fora da interface para a janela não congelar."""
        if self.ocupado:
            self._status("Aguarde a operação em andamento terminar.", AMARELO)
            return
        self.ocupado = True
        self._status(aviso)

        def alvo():
            try:
                self.fila.put((ao_terminar, trabalho(), None))
            except Exception as erro:  # mostrado ao usuário, nunca engolido
                self.fila.put((ao_terminar, None, erro))

        threading.Thread(target=alvo, daemon=True).start()

    def _drenar_fila(self):
        try:
            while True:
                item = self.fila.get_nowait()
                if isinstance(item, str):
                    self._status(item)
                    continue
                ao_terminar, resultado, erro = item
                self.ocupado = False
                if erro is not None:
                    self._status(f"Erro: {erro}", VERMELHO)
                else:
                    ao_terminar(resultado)
        except queue.Empty:
            pass
        self.raiz.after(100, self._drenar_fila)

    # ---------------------------------------------------------------- exame
    def _escrever_exame(self, trechos):
        self.texto_exame.configure(state="normal")
        self.texto_exame.delete("1.0", "end")
        for texto, marca in trechos:
            self.texto_exame.insert("end", texto, marca or ())
        self.texto_exame.configure(state="disabled")

    def _examinar(self):
        self._em_segundo_plano(lambda: examinar(self.amb), self._mostrar_exame,
                               "Examinando o computador...")

    def _mostrar_exame(self, resultado):
        ficha, achados = resultado
        nomes = {p.ident: p.nome for p in self.pilulas}
        trechos = [(linha + "\n", "fraco") for linha in ficha] + [("\n", None)]
        for a in achados:
            trechos.append((a.titulo + "\n", a.gravidade))
            trechos.append((a.detalhe + "\n", None))
            if a.pilula:
                trechos.append((f"Tratamento: {nomes[a.pilula]}\n", "fraco"))
            trechos.append(("\n", None))
        self._escrever_exame(trechos)
        self._status("Exame concluído.")

    # -------------------------------------------------------------- pílulas
    def _atualizar_pilulas(self):
        for p in self.pilulas:
            situacao, botao = self.cartoes[p.ident]
            try:
                ativa = p.ativa(self.amb)
            except Exception:
                ativa = False
            if not p.reversivel:
                situacao.configure(text="dose única", fg=FRACO)
                botao.configure(text="Tomar", bg=VERDE)
            elif ativa:
                situacao.configure(text="● fazendo efeito", fg=VERDE)
                botao.configure(text="Reverter", bg=AMARELO)
            else:
                situacao.configure(text="○ não tomada", fg=FRACO)
                botao.configure(text="Tomar", bg=VERDE)

    def _bula(self, p):
        messagebox.showinfo(f"Bula - {p.nome}", p.bula, parent=self.raiz)

    def _alternar(self, p):
        if p.reversivel and p.ativa(self.amb):
            trabalho = lambda: p.reverter(self.amb)
        else:
            opcoes = {}
            if isinstance(p, PilulaInicializacao):
                nomes = self._escolher_partida(p)
                if not nomes:
                    return
                opcoes["nomes"] = nomes
            elif not messagebox.askokcancel(
                    f"Tomar: {p.nome}", p.bula + "\n\nTomar esta pílula?", parent=self.raiz):
                return
            trabalho = lambda: p.tomar(self.amb, **opcoes)
        self._em_segundo_plano(trabalho, self._pilula_feita, f"{p.nome}...")

    def _pilula_feita(self, mensagem):
        self._atualizar_pilulas()
        self._status(mensagem, VERDE)

    def _escolher_partida(self, p) -> list[str] | None:
        """Janela para escolher quais programas deixam de iniciar sozinhos."""
        itens = [(n, cmd) for n, cmd, ligado in p.itens(self.amb) if ligado]
        if not itens:
            messagebox.showinfo(p.nome, "Nenhum programa do seu usuário inicia "
                                "junto com o Windows.", parent=self.raiz)
            return None
        janela = tk.Toplevel(self.raiz, bg=FUNDO, padx=16, pady=14)
        janela.title(p.nome)
        janela.transient(self.raiz)
        janela.grab_set()
        self._rotulo(janela, "Marque o que NÃO precisa abrir junto com o Windows:",
                     10, negrito=True).pack(fill="x")
        self._rotulo(janela, "Você continua podendo abrir cada programa normalmente.",
                     9, FRACO).pack(fill="x", pady=(0, 8))
        marcas = {}
        for nome, comando in itens:
            var = tk.BooleanVar(value=True)
            marcas[nome] = var
            tk.Checkbutton(
                janela, text=f"{nome}   ({comando[:60]})", variable=var, bg=FUNDO,
                fg=TEXTO, selectcolor=CARTAO, activebackground=FUNDO,
                activeforeground=TEXTO, anchor="w", font=(FONTE, 9)).pack(fill="x")
        escolha: list[str] = []

        def confirmar():
            escolha.extend(n for n, v in marcas.items() if v.get())
            janela.destroy()

        linha = tk.Frame(janela, bg=FUNDO)
        linha.pack(fill="x", pady=(12, 0))
        self._botao(linha, "Tomar a pílula", confirmar).pack(side="right")
        cancelar = self._botao(linha, "Cancelar", janela.destroy, BORDA)
        cancelar.configure(fg=TEXTO)
        cancelar.pack(side="right", padx=6)
        self.raiz.wait_window(janela)
        return escolha or None

    def _antidoto(self):
        if not messagebox.askokcancel(
                "Antídoto", "Desfazer todas as pílulas e devolver o Windows ao "
                "estado em que estava?", parent=self.raiz):
            return
        self.foco.parar()
        self._atualizar_foco()
        self._em_segundo_plano(lambda: " ".join(antidoto(self.amb)),
                               self._pilula_feita, "Aplicando o antídoto...")

    # ----------------------------------------------------------------- foco
    def _alternar_foco(self):
        if self.foco.ativa:
            self.foco.parar()
            self._status("Dose de Foco interrompida; prioridades restauradas.")
        else:
            try:
                minutos = max(1, int(self.minutos.get()))
            except (tk.TclError, ValueError):
                minutos = 60
            self.foco.iniciar(minutos)
            self.foco.pulso()
            self._status("Dose de Foco tomada. Vá para o programa que quer acelerar.", VERDE)
        self._atualizar_foco()

    def _atualizar_foco(self):
        if self.foco.ativa:
            m, s = divmod(int(self.foco.restante()), 60)
            self.rotulo_foco.configure(
                text=f"● {m:02d}:{s:02d} · {len(self.foco.rebaixados)} contidos",
                fg=VERDE)
            self.botao_foco.configure(text="Parar", bg=AMARELO)
        else:
            self.rotulo_foco.configure(text="○ não tomada", fg=FRACO)
            self.botao_foco.configure(text="Tomar", bg=VERDE)

    def _pulso_foco(self):
        if self.foco.ativa:
            try:
                if not self.foco.pulso():
                    self._status("A Dose de Foco acabou; prioridades restauradas.")
            except Exception as erro:
                self.foco.parar()
                self._status(f"Dose de Foco interrompida: {erro}", VERMELHO)
            self._atualizar_foco()
        self.raiz.after(2000, self._pulso_foco)

    # --------------------------------------------------------------- medida
    def _medir(self):
        self._em_segundo_plano(
            lambda: benchmark.medir_tudo(lambda nome: self.fila.put(f"Medindo: {nome}...")),
            self._medido, "Medindo (uns 5 segundos; não mexa no PC)...")

    def _medido(self, resultado):
        medidas = self.amb.estado.dados.setdefault("medidas", {})
        medidas["depois" if "antes" in medidas else "antes"] = resultado
        self.amb.estado.salvar()
        self._mostrar_medidas()
        self._status("Medição concluída.", VERDE)

    def _zerar_medidas(self):
        self.amb.estado.dados.pop("medidas", None)
        self.amb.estado.salvar()
        self._mostrar_medidas()

    def _mostrar_medidas(self):
        medidas = self.amb.estado.dados.get("medidas", {})
        antes, depois = medidas.get("antes"), medidas.get("depois")
        melhoras = benchmark.comparar(antes, depois) if antes and depois else {}
        for nome, (a, d, m) in self.celulas.items():
            a.configure(text=f"{antes[nome]:.1f}" if antes else "-")
            d.configure(text=f"{depois[nome]:.1f}" if depois else "-")
            v = melhoras.get(nome)
            if v is None:
                m.configure(text="-", fg=TEXTO)
            else:
                cor = FRACO if abs(v) < benchmark.RUIDO else (VERDE if v > 0 else VERMELHO)
                m.configure(text=f"{v:+.0f}%", fg=cor)
        if not antes:
            dica = "Meça agora, antes de tomar qualquer pílula, para ter a referência."
        elif not depois:
            dica = "Referência gravada. Tome as pílulas e clique em 'Medir' de novo."
        else:
            dica = benchmark.veredito(melhoras)
        self.rotulo_veredito.configure(text=dica)
        self.botao_medir.configure(text="Medir de novo" if antes else "Medir")

    def _fechar(self):
        # Prioridades alteradas pela Dose de Foco nunca ficam para trás.
        self.foco.parar()
        self.raiz.destroy()


def main():
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
