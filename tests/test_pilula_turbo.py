"""Testes da Pílula Turbo.

A lógica roda contra versões em memória do registro, da energia e dos
processos, então funciona em qualquer sistema. Os testes marcados como
"Windows" tocam o sistema real e só rodam lá (os que alteram o plano de
energia, apenas no CI).
"""

import os
import sys
import tempfile
import time
import unittest

from pilula_turbo import benchmark, sistema
from pilula_turbo.diagnostico import examinar
from pilula_turbo.foco import DoseFoco
from pilula_turbo.pilulas import (
    Ambiente, Estado, PilulaEnergia, PilulaInicializacao, PilulaJogos,
    PilulaLimpeza, PilulaVisual, antidoto, formatar_bytes, todas,
)
from pilula_turbo.sistema import (
    ABAIXO_DO_NORMAL, ACIMA_DO_NORMAL, NORMAL, EnergiaMemoria, RegistroMemoria,
)

NO_WINDOWS = sys.platform == "win32"
NO_CI = bool(os.environ.get("CI"))


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.arquivo = os.path.join(self.pasta.name, "estado.json")
        self.temp = os.path.join(self.pasta.name, "temp")
        os.mkdir(self.temp)
        self.amb = Ambiente(RegistroMemoria(), EnergiaMemoria(), Estado(self.arquivo), self.temp)


class TestPilulaRegistro(Base):
    def test_tomar_e_reverter_restaura_exatamente(self):
        reg = self.amb.registro
        caminho = r"HKCU\Control Panel\Desktop"
        reg.escrever(caminho, "MenuShowDelay", "400", "sz")
        antes = {k: dict(v) for k, v in reg.dados.items()}
        p = PilulaVisual()
        self.assertFalse(p.ativa(self.amb))
        p.tomar(self.amb)
        self.assertTrue(p.ativa(self.amb))
        self.assertEqual(reg.ler(caminho, "MenuShowDelay"), ("0", "sz"))
        p.reverter(self.amb)
        self.assertFalse(p.ativa(self.amb))
        # Valor que existia volta; valores que não existiam somem.
        self.assertEqual({k: v for k, v in reg.dados.items() if v}, antes)

    def test_tomar_duas_vezes_nao_perde_o_original(self):
        reg = self.amb.registro
        chave = r"HKCU\System\GameConfigStore"
        reg.escrever(chave, "GameDVR_Enabled", 1, "dword")
        p = PilulaJogos()
        p.tomar(self.amb)
        p.tomar(self.amb)
        p.reverter(self.amb)
        self.assertEqual(reg.ler(chave, "GameDVR_Enabled"), (1, "dword"))

    def test_estado_sobrevive_a_reabrir_o_programa(self):
        PilulaJogos().tomar(self.amb)
        outro = Ambiente(self.amb.registro, self.amb.energia, Estado(self.arquivo), self.temp)
        PilulaJogos().reverter(outro)
        self.assertFalse(PilulaJogos().ativa(outro))
        self.assertIsNone(Estado(self.arquivo).pilula("jogos"))

    def test_reverter_sem_ter_tomado_nao_altera_nada(self):
        mensagem = PilulaVisual().reverter(self.amb)
        self.assertIn("nada a desfazer", mensagem)
        self.assertEqual(self.amb.registro.dados, {})


class TestPilulaEnergia(Base):
    def test_cria_plano_ausente_e_reverte_apagando(self):
        energia = self.amb.energia
        original = energia.ativo()
        p = PilulaEnergia()
        self.assertFalse(p.ativa(self.amb))
        p.tomar(self.amb)
        self.assertTrue(p.ativa(self.amb))
        self.assertNotEqual(energia.ativo(), original)
        self.assertEqual(len(energia.planos()), 2)
        p.reverter(self.amb)
        self.assertEqual(energia.ativo(), original)
        self.assertEqual(len(energia.planos()), 1)

    def test_usa_plano_existente_sem_duplicar(self):
        energia = self.amb.energia
        energia._planos[PilulaEnergia.ALTO] = "Alto desempenho"
        PilulaEnergia().tomar(self.amb)
        self.assertEqual(energia.ativo(), PilulaEnergia.ALTO)
        PilulaEnergia().reverter(self.amb)
        self.assertIn(PilulaEnergia.ALTO, energia.planos())  # não apaga o que não criou

    def test_ja_em_alto_desempenho_nao_guarda_estado(self):
        energia = self.amb.energia
        energia._planos[PilulaEnergia.ALTO] = "Alto desempenho"
        energia.ativar(PilulaEnergia.ALTO)
        PilulaEnergia().tomar(self.amb)
        self.assertIsNone(self.amb.estado.pilula("energia"))


class TestPilulaInicializacao(Base):
    def setUp(self):
        super().setUp()
        reg = self.amb.registro
        for nome in ("Discord", "OneDrive", "Spotify"):
            reg.escrever(PilulaInicializacao.RUN, nome, f"C:\\{nome}.exe", "sz")
        # Spotify já estava desligado pelo usuário no Gerenciador de Tarefas.
        self.marca_spotify = bytes([3, 0, 0, 0]) + bytes(8)
        reg.escrever(PilulaInicializacao.APROVADO, "Spotify", self.marca_spotify, "binary")

    def test_lista_respeita_o_que_ja_estava_desligado(self):
        itens = {n: ligado for n, _, ligado in PilulaInicializacao().itens(self.amb)}
        self.assertEqual(itens, {"Discord": True, "OneDrive": True, "Spotify": False})

    def test_desliga_so_os_escolhidos_e_reverte(self):
        p = PilulaInicializacao()
        p.tomar(self.amb, nomes=["Discord"])
        itens = {n: ligado for n, _, ligado in p.itens(self.amb)}
        self.assertEqual(itens, {"Discord": False, "OneDrive": True, "Spotify": False})
        marca = self.amb.registro.ler(p.APROVADO, "Discord")[0]
        self.assertEqual((len(marca), marca[0]), (12, 3))
        self.assertTrue(p.ativa(self.amb))
        p.reverter(self.amb)
        itens = {n: ligado for n, _, ligado in p.itens(self.amb)}
        self.assertEqual(itens, {"Discord": True, "OneDrive": True, "Spotify": False})
        self.assertIsNone(self.amb.registro.ler(p.APROVADO, "Discord"))
        # O que o usuário já tinha desligado continua exatamente como estava.
        self.assertEqual(self.amb.registro.ler(p.APROVADO, "Spotify")[0], self.marca_spotify)


class TestPilulaLimpeza(Base):
    def _arquivo(self, *partes, idade_h=0.0, tamanho=10):
        caminho = os.path.join(self.temp, *partes)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "wb") as f:
            f.write(b"x" * tamanho)
        quando = time.time() - idade_h * 3600
        os.utime(caminho, (quando, quando))
        return caminho

    def test_apaga_so_antigos_e_poupa_programas_em_execucao(self):
        velho = self._arquivo("a", "velho.tmp", idade_h=48, tamanho=1000)
        novo = self._arquivo("novo.tmp", idade_h=1)
        empacotado = self._arquivo("_MEI123", "python.dll", idade_h=999)
        mensagem = PilulaLimpeza().tomar(self.amb)
        self.assertFalse(os.path.exists(velho))
        self.assertFalse(os.path.exists(os.path.dirname(velho)))  # pasta vazia sai
        self.assertTrue(os.path.exists(novo))
        self.assertTrue(os.path.exists(empacotado))
        self.assertIn("1 arquivo", mensagem)

    @unittest.skipIf(NO_WINDOWS, "links simbólicos exigem privilégio no Windows")
    def test_nunca_segue_links_para_fora_da_pasta(self):
        fora = os.path.join(self.pasta.name, "documentos")
        os.mkdir(fora)
        precioso = os.path.join(fora, "tese.docx")
        with open(precioso, "wb") as f:
            f.write(b"x")
        os.utime(precioso, (0, 0))
        os.symlink(fora, os.path.join(self.temp, "atalho"))
        PilulaLimpeza().tomar(self.amb)
        self.assertTrue(os.path.exists(precioso))


class TestAntidoto(Base):
    def test_desfaz_todas_as_pilulas(self):
        self.amb.registro.escrever(PilulaInicializacao.RUN, "Discord", "x", "sz")
        original = self.amb.energia.ativo()
        for p in todas():
            p.tomar(self.amb)
        antidoto(self.amb)
        for p in todas():
            self.assertFalse(p.ativa(self.amb), p.ident)
        self.assertEqual(self.amb.energia.ativo(), original)
        self.assertEqual(self.amb.estado.dados.get("pilulas"), {})
        self.assertEqual(antidoto(self.amb), ["Nenhuma pílula ativa para reverter."])


class ProcessosFalsos:
    def __init__(self):
        self.nomes = {100: "jogo.exe", 200: "atualizador.exe", 300: "parado.exe",
                      400: "dwm.exe", 500: "renderizador.exe", 999: "pilula.exe"}
        self.classes = {pid: NORMAL for pid in self.nomes}
        self.classes[500] = ABAIXO_DO_NORMAL  # o próprio programa escolheu
        self.cpu = {pid: 0.0 for pid in self.nomes}
        self.frente = 100

    def listar(self):
        return dict(self.nomes)

    def pid_primeiro_plano(self):
        return self.frente

    def tempo_cpu(self, pid):
        return self.cpu.get(pid)

    def prioridade(self, pid):
        return self.classes.get(pid)

    def definir_prioridade(self, pid, classe):
        if pid not in self.classes:
            return False
        self.classes[pid] = classe
        return True


class TestDoseFoco(unittest.TestCase):
    def setUp(self):
        self.proc = ProcessosFalsos()
        self.agora = 0.0
        self.dose = DoseFoco(self.proc, meu_pid=999, relogio=lambda: self.agora)

    def _passar(self, segundos, **cpu):
        self.agora += segundos
        for pid, gasto in cpu.items():
            self.proc.cpu[int(pid[1:])] += gasto
        return self.dose.pulso()

    def test_acelera_a_frente_e_contem_o_fundo(self):
        self.dose.iniciar(10)
        self.dose.pulso()
        self.assertEqual(self.proc.classes[100], ACIMA_DO_NORMAL)
        # atualizador e dwm gastam CPU ao fundo; parado não gasta.
        self._passar(2, p200=1.5, p400=1.5, p999=1.5)
        self.assertEqual(self.proc.classes[200], ABAIXO_DO_NORMAL)
        self.assertEqual(self.proc.classes[300], NORMAL)
        self.assertEqual(self.proc.classes[400], NORMAL)   # do Windows: protegido
        self.assertEqual(self.proc.classes[999], NORMAL)   # a própria Pílula
        self.assertEqual(self.dose.rebaixados, {200: "atualizador.exe"})

    def test_segue_a_janela_em_uso(self):
        self.dose.iniciar(10)
        self.dose.pulso()
        self._passar(2, p200=1.5)
        self.proc.frente = 200  # usuário mudou para o programa que estava contido
        self._passar(2)
        self.assertEqual(self.proc.classes[200], ACIMA_DO_NORMAL)
        self.assertEqual(self.proc.classes[100], NORMAL)

    def test_ao_expirar_tudo_volta_ao_original(self):
        self.dose.iniciar(1)
        self.dose.pulso()
        self._passar(2, p200=1.5, p500=1.5)
        self.assertTrue(self.dose.ativa)
        self.assertFalse(self._passar(60))
        self.assertFalse(self.dose.ativa)
        self.assertEqual(self.proc.classes[100], NORMAL)
        self.assertEqual(self.proc.classes[200], NORMAL)
        # Prioridade escolhida pelo próprio programa nunca foi tocada.
        self.assertEqual(self.proc.classes[500], ABAIXO_DO_NORMAL)

    def test_processo_encerrado_e_esquecido(self):
        self.dose.iniciar(10)
        self.dose.pulso()
        del self.proc.nomes[100], self.proc.classes[100]
        self.proc.frente = None
        self._passar(2)
        self.assertIsNone(self.dose.acelerado)
        self.dose.parar()  # não tenta restaurar um PID que já não existe
        self.assertNotIn(100, self.proc.classes)


class TestBenchmark(unittest.TestCase):
    def test_comparar_trata_menor_como_melhor_no_atraso(self):
        antes = {"cpu": 100, "memoria": 100, "disco": 100, "resposta": 10}
        depois = {"cpu": 120, "memoria": 101, "disco": 80, "resposta": 5}
        m = benchmark.comparar(antes, depois)
        self.assertEqual(m, {"cpu": 20.0, "memoria": 1.0, "disco": -20.0, "resposta": 50.0})
        texto = benchmark.veredito(m)
        self.assertIn("Atraso de resposta melhorou 50%", texto)
        self.assertIn("Disco (gravação) piorou 20%", texto)
        self.assertNotIn("Memória", texto)  # 1% é ruído

    def test_sem_efeito_e_dito_com_todas_as_letras(self):
        self.assertIn("Sem diferença", benchmark.veredito({"cpu": 2.0, "disco": -3.0}))

    def test_medidas_reais_dao_numeros_positivos(self):
        self.assertGreater(benchmark.medir_cpu(0.05), 0)
        self.assertGreater(benchmark.medir_memoria(0.05), 0)
        self.assertGreater(benchmark.medir_disco(2), 0)
        self.assertGreaterEqual(benchmark.medir_resposta(5), 0)


class TestDiversos(Base):
    def test_formatar_bytes(self):
        self.assertEqual(formatar_bytes(512), "512 B")
        self.assertEqual(formatar_bytes(1536), "1.5 KB")
        self.assertEqual(formatar_bytes(8 * 1024**3), "8.0 GB")

    def test_exame_aponta_o_tratamento(self):
        for n in range(5):
            self.amb.registro.escrever(PilulaInicializacao.RUN, f"App{n}", "x", "sz")
        ficha, achados = examinar(self.amb)
        self.assertTrue(ficha)
        tratamentos = {a.pilula for a in achados}
        self.assertIn("energia", tratamentos)
        self.assertIn("inicializacao", tratamentos)

    def test_estado_corrompido_nao_derruba_o_programa(self):
        with open(self.arquivo, "w") as f:
            f.write("{quebrado")
        self.assertEqual(Estado(self.arquivo).dados, {})


@unittest.skipUnless(NO_WINDOWS, "toca o Windows de verdade")
class TestWindowsReal(unittest.TestCase):
    CHAVE = r"HKCU\Software\PilulaTurboTeste"

    def test_registro_real_ida_e_volta(self):
        reg = sistema.RegistroWindows()
        self.assertIsNone(reg.ler(self.CHAVE, "inexistente"))
        casos = [("n", 7, "dword"), ("t", "0", "sz"), ("b", bytes(range(12)), "binary")]
        try:
            for nome, valor, tipo in casos:
                reg.escrever(self.CHAVE, nome, valor, tipo)
                self.assertEqual(reg.ler(self.CHAVE, nome), (valor, tipo))
            self.assertEqual(len(reg.valores(self.CHAVE)), 3)
        finally:
            for nome, _, _ in casos:
                reg.apagar(self.CHAVE, nome)
            import winreg
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.CHAVE.split("\\", 1)[1])
        self.assertEqual(reg.valores(self.CHAVE), {})

    def test_processos_e_prioridade_do_proprio_processo(self):
        proc = sistema.ProcessosWindows()
        eu = os.getpid()
        self.assertIn(eu, proc.listar())
        self.assertGreater(len(proc.listar()), 5)
        self.assertGreaterEqual(proc.tempo_cpu(eu), 0)
        original = proc.prioridade(eu)
        self.assertIsNotNone(original)
        try:
            self.assertTrue(proc.definir_prioridade(eu, ABAIXO_DO_NORMAL))
            self.assertEqual(proc.prioridade(eu), ABAIXO_DO_NORMAL)
        finally:
            proc.definir_prioridade(eu, original)
        self.assertEqual(proc.prioridade(eu), original)
        proc.pid_primeiro_plano()  # pode ser None em sessão sem janelas; não pode falhar

    def test_dose_de_foco_real_restaura_prioridades(self):
        proc = sistema.ProcessosWindows()
        antes = {pid: proc.prioridade(pid) for pid in proc.listar()}
        dose = DoseFoco(proc)
        dose.iniciar(1)
        dose.pulso()
        time.sleep(0.3)
        dose.pulso()
        dose.parar()
        for pid, classe in antes.items():
            atual = proc.prioridade(pid)
            if classe is not None and atual is not None:
                self.assertEqual(atual, classe, pid)

    def test_medicoes_do_sistema(self):
        total, livre = sistema.memoria()
        self.assertGreater(total, livre)
        self.assertGreater(livre, 0)
        self.assertTrue(sistema.nome_cpu())
        self.assertTrue(0 <= sistema.uso_cpu(0.2) <= 100)
        self.assertGreater(sistema.tempo_ligado(), 0)
        self.assertIn(sistema.tipo_disco_sistema(), ("SSD", "HDD", None))

    def test_exame_real_so_leitura(self):
        with tempfile.TemporaryDirectory() as pasta:
            amb = Ambiente(sistema.RegistroWindows(), sistema.EnergiaWindows(), Estado(), pasta)
            ficha, achados = examinar(amb)
        self.assertGreaterEqual(len(ficha), 4)
        self.assertTrue(achados)

    @unittest.skipUnless(NO_CI, "altera o plano de energia: só no CI")
    def test_plano_de_energia_real_ida_e_volta(self):
        energia = sistema.EnergiaWindows()
        original = energia.ativo()
        planos = energia.planos()
        self.assertIn(original, planos)
        amb = Ambiente(RegistroMemoria(), energia, Estado())
        p = PilulaEnergia()
        ja_ativa = p.ativa(amb)
        p.tomar(amb)
        self.assertTrue(p.ativa(amb))
        p.reverter(amb)
        self.assertEqual(energia.ativo(), original)
        self.assertEqual(energia.planos().keys(), planos.keys())
        self.assertEqual(p.ativa(amb), ja_ativa)

    @unittest.skipUnless(NO_CI, "altera o registro do usuário: só no CI")
    def test_pilulas_de_registro_reais_ida_e_volta(self):
        reg = sistema.RegistroWindows()
        amb = Ambiente(reg, EnergiaMemoria(), Estado())
        for p in (PilulaVisual(), PilulaJogos()):
            antes = [reg.ler(c, n) for c, n, _, _ in p.ajustes]
            p.tomar(amb)
            self.assertTrue(p.ativa(amb))
            p.reverter(amb)
            self.assertEqual([reg.ler(c, n) for c, n, _, _ in p.ajustes], antes)


class TestInterface(unittest.TestCase):
    def test_janela_abre_e_fluxo_basico_funciona(self):
        try:
            import tkinter as tk
            raiz = tk.Tk()
        except Exception as erro:  # sem Tk ou sem tela
            self.skipTest(f"sem interface gráfica: {erro}")
        from pilula_turbo.app import App, ProcessosDemo
        amb = Ambiente(RegistroMemoria(), EnergiaMemoria(), Estado())
        try:
            app = App(raiz, amb, ProcessosDemo())
            raiz.update()
            app._mostrar_exame(examinar(amb))
            app._medido({"cpu": 100.0, "memoria": 100.0, "disco": 100.0, "resposta": 4.0})
            app._medido({"cpu": 130.0, "memoria": 100.0, "disco": 100.0, "resposta": 2.0})
            self.assertIn("Processador melhorou 30%", app.rotulo_veredito["text"])
            todas()[2].tomar(amb)
            app._atualizar_pilulas()
            self.assertEqual(app.cartoes["visual"][1]["text"], "Reverter")
            app._alternar_foco()
            self.assertTrue(app.foco.ativa)
            app._alternar_foco()
            self.assertFalse(app.foco.ativa)
            raiz.update()
        finally:
            raiz.destroy()


if __name__ == "__main__":
    unittest.main()
