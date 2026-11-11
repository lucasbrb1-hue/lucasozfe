# Pílula Turbo

Aplicativo para Windows 10/11 que trata o computador como um paciente:
**examina**, **receita pílulas** e **mede o efeito**.

Um aviso honesto, que também aparece na tela do programa: nenhum software
cria hardware novo. O que a Pílula Turbo faz é tirar do caminho o que impede o
hardware que você já tem de render tudo o que pode. Quando o freio é o próprio
hardware (pouca RAM, Windows em disco rígido), o exame diz isso com todas as
letras em vez de prometer milagre.

## O que há de diferente

| Ideia | Como funciona |
|---|---|
| **Bula** | Cada pílula mostra o efeito esperado e os efeitos colaterais antes de ser tomada. |
| **Antídoto** | Antes de alterar qualquer coisa, o valor original é gravado em `%APPDATA%\PilulaTurbo\estado.json`. "Reverter" (uma pílula) ou "Antídoto" (todas) devolve exatamente o que estava lá, mesmo depois de fechar e reabrir o programa. |
| **Sem placebo** | Um teste de esforço de ~5 s mede processador, memória, disco e atraso de resposta antes e depois. Variações abaixo de 5% são tratadas como ruído, e o programa diz "sem diferença mensurável" quando for o caso. |
| **Dose de Foco** | Efeito temporário, com prazo: o programa em uso ganha prioridade de CPU e os que consomem CPU ao fundo são contidos. Acabou a dose, tudo volta ao normal. |
| **Sem administrador** | Só altera configurações do seu usuário. Não instala serviço nem driver e não fica rodando em segundo plano. |

## As pílulas

- **Energia máxima** - ativa o plano "Alto desempenho" (recria o plano quando
  o notebook o esconde). Colateral: mais consumo e calor.
- **Partida limpa** - você escolhe quais programas deixam de abrir junto com o
  Windows (o mesmo interruptor do Gerenciador de Tarefas).
- **Interface leve** - desliga transparência e animações.
- **Modo jogo** - liga o Modo de Jogo e desliga a gravação em segundo plano do
  Xbox Game Bar.
- **Faxina de temporários** - apaga temporários do usuário com mais de 24 h.
  É a única sem antídoto.
- **Dose de Foco** - descrita acima; de 5 a 480 minutos.

## Como usar

1. **Examinar o PC** - veja o que está segurando o computador.
2. **Medir** - grave a referência *antes* de tomar qualquer coisa.
3. Tome as pílulas indicadas (leia a bula).
4. **Medir de novo** - veja o efeito real, em números.

## Executar

Com Python 3.10+ instalado (não há dependências externas):

```
python -m pilula_turbo
```

Para gerar o `PilulaTurbo.exe`:

```
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name PilulaTurbo pilula_turbo_main.py
```

O workflow `.github/workflows/pilula-turbo-windows.yml` faz isso a cada push e
deixa o executável como artefato da execução, na aba *Actions* do GitHub.

Fora do Windows o programa abre em modo demonstração e não altera nada.

## Limites conhecidos

- **Partida limpa** só alcança programas registrados para o seu usuário
  (`HKCU\...\Run`). Os instalados para todos os usuários e os da pasta
  "Inicializar" continuam no Gerenciador de Tarefas.
- **Interface leve**: parte do efeito só aparece depois de sair e entrar de
  novo na conta do Windows.
- **Dose de Foco** não alcança processos de outros usuários nem do sistema. Se
  o programa for encerrado à força durante uma dose, os processos alterados
  ficam com a prioridade da dose até serem reabertos (fechar pela janela
  restaura tudo).
- O teste de esforço é curto e varia de uma execução para outra; feche outros
  programas ao medir e repita se o resultado parecer estranho.

## Testes

```
python -m unittest tests.test_pilula_turbo -v
```

A lógica é testada contra registro, energia e processos em memória. No
Windows, testes adicionais tocam o sistema real, sempre com ida e volta; os
que alteram o plano de energia e o registro do usuário só rodam no CI.
