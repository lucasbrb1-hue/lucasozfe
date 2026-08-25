# Tutorial — Cálculo de Estacas via SPT

Guia passo a passo para usar o `spt_estacas.exe`, do download até gerar o
memorial de cálculo. Para a lista completa de recursos e as hipóteses de
cálculo, veja o [README.md](README.md).

> ⚠️ Este software é um apoio ao pré-dimensionamento. Todo resultado deve
> ser conferido e assinado por um engenheiro habilitado (ART/RRT) antes de
> qualquer uso em projeto executivo ou execução de obra.

## 1. Baixar e abrir o programa

1. Baixe o executável:
   https://github.com/lucasbrb1-hue/lucasozfe/releases/download/windows-build-latest/spt_estacas.exe
2. Não é preciso instalar Python nem nada além disso - é um único arquivo.
3. Dê duplo clique em `spt_estacas.exe`.
   - O Windows SmartScreen pode avisar "O Windows protegeu o computador"
     (comum em executáveis não assinados digitalmente). Clique em **Mais
     informações** e depois em **Executar assim mesmo**.
4. A janela do programa abre com 8 abas: **Configurações**, **1. Perfil
   SPT**, **2. Importar Laudo (IA)**, **💡 Sugestão de Fundação**, **3.
   Estaca e Carga**, **4. Resultados**, **5. Armação** e **6. Esforços e
   Uniformização**.

Existem dois fluxos de uso, que podem ser combinados:

- **Fluxo A - uma estaca por vez** (abas 1 → 3 → 4 → 5): você digita o
  perfil de SPT e uma carga, e o programa calcula a profundidade e a
  armação daquela estaca.
- **Fluxo B - lote de estacas** (aba 6): você importa as cargas de vários
  pilares/blocos de uma vez (de uma planilha, digitando manualmente, ou via
  IA a partir do PDF do seu software estrutural) e o programa calcula a
  profundidade e a armação de todas de uma vez, com opção de uniformizar.

## 2. (Opcional) Configurar a chave de API para usar a IA

As abas **2. Importar Laudo (IA)** e a importação por IA na aba 6 usam a
API da Anthropic (Claude) para ler PDFs automaticamente. Isso é opcional -
sem chave configurada, você ainda pode preencher tudo manualmente.

1. Crie uma chave em https://console.anthropic.com/ (é uma conta paga por
   uso, separada da assinatura do Claude.ai).
2. Na aba **Configurações**, cole a chave no campo e clique em **Salvar
   chave**. Ela fica salva só neste computador (arquivo de configuração
   local, não é enviada a lugar nenhum além da própria Anthropic quando
   você usa a IA).
3. Cada pessoa que for usar o programa em outro computador precisa
   configurar sua própria chave.

## 3. Fluxo A — calcular uma estaca

### 3.1. Preencher o perfil de SPT (aba 1)

Para cada profundidade sondada, informe: profundidade (m), N-SPT (número de
golpes) e o tipo de solo. Clique em **Adicionar** para cada linha.

- Se você já tem o perfil em planilha, use **Carregar CSV...** (3 colunas:
  profundidade, N-SPT, tipo de solo - use **Salvar CSV...** uma vez para
  ver o formato esperado).
- Se você tem o laudo em PDF e configurou a chave de API, pule para a aba
  **2. Importar Laudo (IA)**: selecione o PDF, clique em **Interpretar com
  IA**, revise linha a linha os valores extraídos (a IA pode errar - **é
  obrigatório conferir** antes de importar) e clique em **Confirmar e
  importar para o Perfil SPT**. Isso preenche a aba 1 automaticamente.
- Se houver nível d'água, informe a profundidade no campo no fim da aba 1
  (ou deixe em branco se seco/não identificado).

### 3.2. (Opcional) Pedir uma sugestão de tipo de fundação (aba 💡)

Com o perfil de SPT preenchido (não importa se manualmente, por CSV ou via
IA), a aba **💡 Sugestão de Fundação** pode ajudar a escolher o tipo de
estaca antes de você preencher a aba 3:

1. Responda as perguntas de sim/não sobre o local da obra (vizinhança
   sensível a vibração, restrição de ruído, acesso/espaço para equipamento
   de grande porte, pé-direito restrito, se quer evitar fluido
   estabilizante, se é uma obra pequena/orçamento restrito). Deixe
   desmarcado o que não se aplica.
2. Clique em **Sugerir tipo de fundação**. O programa cruza a resistência
   do solo (N-SPT) e o nível d'água do perfil com suas respostas e mostra
   um ranking dos 4 tipos suportados, cada um com os pontos a favor e as
   restrições identificadas.
3. Se concordar com o tipo mais bem colocado, clique em **Aplicar tipo
   sugerido na aba '3. Estaca e Carga'** para já preenchê-lo lá.

> Esta sugestão é uma triagem heurística de apoio à decisão (regras de
> prática usual de fundações), não um cálculo normativo - ela não considera
> custo, disponibilidade local de equipamento/mão de obra nem licenciamento
> ambiental. A escolha final é sempre do engenheiro de fundações
> responsável.

### 3.3. Informar a estaca e a carga (aba 3)

- **Tipo de estaca**: hélice contínua, escavada (broca), pré-moldada
  cravada ou Strauss - os coeficientes de cálculo mudam por tipo.
- **Diâmetro** (cm) e **carga de projeto** (kN - lembrete: 1 tf ≈ 10 kN).
- **Fator de segurança global** (padrão 2,0, o usual para SPT).
- **Profundidade mínima de embutimento** e o **método de cálculo**
  (Décourt-Quaresma, Aoki-Velloso, ou ambos - o resultado usa sempre o mais
  conservador dos dois quando ambos estão marcados).
- Clique em **Calcular profundidade necessária**.

### 3.4. Conferir o resultado (aba 4)

A aba mostra a profundidade mínima encontrada, uma tabela de capacidade de
carga por profundidade e um gráfico. Dois botões de exportação:

- **Exportar relatório resumido (.txt)**: só o resultado, sem memória de
  cálculo.
- **Gerar memorial de cálculo completo (.docx)**: documento completo com
  metodologia, fórmulas e a memória de cálculo de cada profundidade
  analisada - normalmente é o que se anexa ao projeto.

### 3.5. Dimensionar a armação (aba 5)

Depois de calcular a profundidade (aba 3), vá à aba 5 para a armação:

- **Cobrimento** (padrão 5 cm, mínimo da NBR 6122:2022 para estacas em
  classe de agressividade II - ajuste para 7 cm ou mais em ambientes mais
  agressivos) e **taxa mínima de armadura** (deixe em branco para usar o
  padrão por diâmetro).
- **Bitola/espaçamento dos estribos** e o **comprimento de armação**: deixe
  em branco para armar a estaca inteira (mais seguro/conservador), ou
  informe um valor para armar só os primeiros metros a partir do topo
  (válido apenas quando a estaca trabalha essencialmente à compressão, sem
  momento/esforço horizontal relevante na região não armada).
- **Momento Mk e cortante Hk** (opcionais): se você não informar nada, a
  armadura é só pela taxa mínima. Se informar o momento (direto ou via
  componentes Mx/My), o programa faz o dimensionamento estrutural de
  verdade (flexo-compressão N-M); se também informar o cortante (direto ou
  via Hx/Hy), dimensiona os estribos ao cisalhamento.
- **fck, fyk, γf e γc**: valores padrão já seguem a NBR 6118/6122 (fck 30
  MPa, γc 1,4 - o mesmo valor geral usado na maioria das estacas). Só
  aumente o γc (ex.: para ~3,1) se a execução da sua estaca não tiver
  controle rigoroso de concretagem (ex.: escavada sem qualquer suporte de
  parede/fluido) - usar esse valor majorado sem necessidade mais que dobra
  a armadura calculada. Ajuste também conforme a classe de agressividade e
  o fator de majoração do seu software estrutural.
- Clique em **Calcular armação**. O resultado (bitola, nº de barras,
  estribos, avisos) aparece na caixa de texto abaixo, e passa a ser
  incluído automaticamente no memorial de cálculo (aba 4) se você gerar o
  .docx depois de calcular a armação.

## 4. Fluxo B — lote de estacas (aba 6)

Use quando você já tem as cargas de vários pilares/blocos vindas do seu
software estrutural (Eberick, TQS, CypeCad etc.) e quer calcular todas as
estacas de uma vez.

1. Preencha primeiro o **perfil de SPT** (aba 1) e o **tipo/diâmetro de
   estaca** (aba 3) - o lote usa esses mesmos dados para todas as estacas.
2. Na aba 6, adicione os esforços de cada elemento:
   - **Manualmente**: elemento, carga característica **Nk** (nunca a carga
     majorada/ELU), nº de estacas do bloco (a carga é dividida igualmente
     entre elas) e, se houver, momento/cortante (direto Mk/Hk, ou como
     componentes Mx/My e Hx/Hy - o programa calcula a resultante sozinho).
   - **Via planilha**: **Carregar CSV...**.
   - **Via IA**: **Importar PDF via IA...** + **Interpretar com IA**, e
     revise a tabela antes de calcular (mesma lógica de revisão obrigatória
     da aba 2).
3. Escolha se quer **uniformizar** as profundidades: "Sim" agrupa as
   estacas em N profundidades padrão (reduz a variedade de comprimentos na
   obra, sempre pela maior necessidade de cada grupo - nunca fica menor que
   o necessário); "Não" mantém a profundidade individual de cada estaca.
4. Clique em **Calcular profundidade de todas as estacas**. A tabela mostra
   elemento, carga por estaca, profundidade individual, grupo (se
   uniformizado), profundidade adotada e comprimento de armadura.
5. Se quiser a armação em lote (mesma bitola/nº de barras para todas as
   estacas do conjunto, verificada contra o Nd/Md da estaca mais exigente),
   preencha cobrimento/fck/γc/γf normalmente na aba 5 antes deste passo -
   os mesmos valores são usados no cálculo em lote.
6. Clique em **Gerar memorial de cálculo em lote (.docx)** para o documento
   completo: esforços importados, metodologia, resultado por estaca e a
   armação adotada.

## 5. Erros comuns

- **"A carga de projeto não é atingida dentro da profundidade sondada"**:
  o perfil de SPT não é fundo o suficiente para a carga pedida - acrescente
  leituras mais profundas ou revise a carga/diâmetro/tipo de estaca.
- **Aba de IA sem funcionar / botão "Interpretar com IA" dá erro**: confira
  se a chave de API foi salva na aba Configurações (ou defina a variável de
  ambiente `ANTHROPIC_API_KEY` antes de abrir o programa) e se há conexão
  com a internet.
- **"Não foi possível encontrar uma combinação padrão de barras..."** (aba
  5): o cobrimento informado é grande demais para o diâmetro da estaca, ou
  o momento de cálculo é maior do que a seção resiste - considere aumentar
  o diâmetro, o fck, ou revisar os esforços.
- **CSV não carrega**: confira se as colunas estão na ordem esperada
  (gere um CSV de exemplo pelo botão "Salvar CSV..." de cada aba e compare
  o formato).

## 6. Lembretes importantes

- Os esforços (Nk, Mk, Hk) informados nas abas 3/5/6 devem ser sempre
  **característicos** (de serviço) - o programa aplica o fator γf para
  obter os valores de cálculo. Não informe valores já majorados, a menos
  que ajuste γf para 1,0.
- O momento/cortante de cálculo usados no dimensionamento estrutural são
  apenas os valores informados majorados por γf - o programa **não** faz
  uma análise de interação solo-estrutura (tipo "Método Russo") para
  amplificar esse momento em estacas curtas sob carga lateral. Se o seu
  caso exige essa verificação, ela deve ser feita à parte.
- Todo resultado é numérico e aproximado (ver limitações detalhadas no
  README) - confira de forma independente antes de executar.
