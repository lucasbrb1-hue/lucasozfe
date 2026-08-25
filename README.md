# Cálculo de Estacas via SPT — Profundidade e Armação

Software desktop (Python + Tkinter) para apoiar o pré-dimensionamento de
estacas a partir de um perfil de sondagem SPT (Standard Penetration Test):

- Estima a **capacidade de carga admissível** por profundidade usando os
  métodos semi-empíricos **Décourt-Quaresma** e/ou **Aoki-Velloso**.
- Determina a **profundidade mínima** de estaca que atende a uma carga de
  projeto informada.
- Sugere a **armação** (barras longitudinais e estribos): por padrão, pela
  taxa mínima usual associada à NBR 6118/NBR 6122; quando o momento fletor
  (Mk) característico é informado, dimensiona de verdade por **interação
  N-M (flexo-compressão)** e, se o cortante (Hk) também for informado,
  dimensiona os estribos ao **cisalhamento** - ver "Dimensionamento
  estrutural" abaixo.
- Suporta os tipos de estaca: hélice contínua, escavada (broca), pré-moldada
  cravada e Strauss.
- **Interpreta laudos de sondagem SPT em PDF via IA** (API da Claude,
  Anthropic): extrai profundidade, N-SPT, tipo de solo e nível d'água
  automaticamente, sempre com revisão humana obrigatória antes de qualquer
  cálculo.
- **Sugere o tipo de estaca mais adequado** a partir do perfil de SPT (aba
  "💡 Sugestão de Fundação"): cruza a resistência do solo e o nível d'água
  com perguntas sobre restrições do local da obra (vizinhança sensível a
  vibração, acesso/espaço para equipamento, pé-direito, uso de fluido
  estabilizante, porte da obra) e mostra um ranking justificado dos 4 tipos
  suportados - ver `pile_type_advisor.py` para o método (uma triagem
  heurística de apoio à decisão, não um método normativo).
- Gera um **memorial de cálculo completo em .docx**, com metodologia,
  fórmulas e memória de cálculo (valores intermediários) de cada método e
  de cada profundidade analisada.
- **Importa os esforços (cargas) de fundação** gerados por softwares de
  dimensionamento estrutural (Eberick, TQS, CypeCad etc.) - manualmente,
  por planilha CSV, via IA a partir do PDF do relatório de cargas, ou por um
  leitor dedicado (sem IA) do relatório "Esforços nas Fundações por
  Elementos" exportado em `.xlsx` pelo Eberick - e calcula automaticamente a
  **profundidade e a armadura de cada estaca**, com opção de **uniformizar**
  (agrupar) as profundidades em um número escolhido de padrões, para
  simplificar a execução na obra.
- **Suporta envoltória completa de combinações de carregamento**: muitos
  relatórios (como o do Eberick citado acima) não dão um único Mk/Hk por
  elemento - dão dezenas de combinações (N, Mx, My, Vx, Vy concomitantes por
  combinação). Quando isso é importado, a armadura é verificada contra
  **todas** as combinações de cada estaca, e a mais exigente é reportada
  como governante - a combinação de maior N nem sempre é a mais crítica
  para a flexo-compressão, então escolher só uma "na mão" pode subestimar o
  momento real. Ver `loads.py` (`LoadCombination`) e `eberick_import.py`.

> ⚠️ **Aviso de engenharia**: esta ferramenta é um apoio ao
> pré-dimensionamento, com coeficientes de referência da literatura técnica.
> Ela **não substitui** a investigação geotécnica completa, a análise crítica
> de um engenheiro habilitado, nem a Anotação/Registro de Responsabilidade
> Técnica (ART/RRT). Sempre valide os resultados com as normas vigentes
> (NBR 6118, NBR 6122 e demais aplicáveis) antes de qualquer uso em projeto
> executivo ou execução de obra.

## Estrutura do projeto

```
spt_piles/
  soil_data.py         tabelas de solo (K, alpha) - Aoki-Velloso / Décourt-Quaresma
  pile_factors.py       fatores alpha/beta (DQ) e F1/F2 (AV) por tipo de estaca
  models.py              perfil de SPT e geometria da estaca
  decourt_quaresma.py    método de Décourt-Quaresma
  aoki_velloso.py         método de Aoki-Velloso
  depth_solver.py         busca da profundidade mínima que atende a carga
  pile_type_advisor.py     sugestão heurística do tipo de estaca (solo + restrições do local)
  reinforcement.py         dimensionamento da armação
  structural_design.py       flexo-compressão (N-M) e cisalhamento (V) da seção circular
  ai_extraction.py            interpretação de laudos SPT e relatórios de esforços (PDF) via API da Claude
  config.py                    configuração local do usuário (chave de API)
  memorial.py                   geração do memorial de cálculo completo (.docx) de uma estaca
  loads.py                       esforços de fundação por elemento (pilar/bloco/estaca), inclusive envoltória de combinações
  eberick_import.py               leitor (sem IA) do relatório de combinações .xlsx do Eberick
  pile_group.py                   cálculo em lote por estaca, uniformização e armação em lote
  batch_memorial.py                memorial de cálculo (.docx) do lote de estacas
  report.py                         geração de relatório resumido em texto
  gui.py                             interface gráfica (Tkinter)
main.py                      ponto de entrada
tests/                        testes unitários (unittest)
```

## Rodando a partir do código-fonte

Requer apenas Python 3.10+ com Tkinter (já incluso na maioria das
instalações; no Ubuntu/Debian, se necessário: `sudo apt install python3-tk`).

```bash
python3 main.py
```

Para usar a **interpretação por IA** (laudo SPT e esforços de fundação) e a
**geração do memorial em .docx**, instale as dependências opcionais:

```bash
pip install -r requirements.txt
```

E configure sua chave de API de uma das duas formas:

- **Pela interface (recomendado para a maioria dos usuários)**: abra o
  programa, vá na aba **"⚙ Configurações"**, cole sua chave da Anthropic
  (obtida em https://console.anthropic.com/) e clique em "Salvar chave". Ela
  fica salva localmente neste computador (arquivo de configuração no
  diretório do usuário - `%APPDATA%\spt_estacas\config.json` no Windows,
  `~/.config/spt_estacas/config.json` no Linux/macOS), em texto simples.
  **Cada pessoa que usar o programa configura a sua própria chave**, direto
  na aba - não precisa editar nada por fora.
- **Por variável de ambiente** (uso avançado/CI - tem prioridade sobre a
  chave salva na aba Configurações, se ambas estiverem definidas):
  ```bash
  # Linux/macOS
  export ANTHROPIC_API_KEY="sua-chave-aqui"
  # Windows (PowerShell)
  setx ANTHROPIC_API_KEY "sua-chave-aqui"
  ```

A chave **nunca** deve ser commitada no repositório. Sem nenhuma chave
configurada, o resto do software funciona normalmente; apenas as abas de
importação por IA mostram uma mensagem pedindo para configurar a chave.

### Como funciona a importação por IA

1. Na aba **"2. Importar Laudo (IA)"**, selecione o PDF do laudo/boletim de
   sondagem SPT e clique em "Interpretar com IA".
2. O PDF é enviado para a API da Claude (Anthropic), que localiza a tabela de
   sondagem e retorna, para cada profundidade: N-SPT, classificação do solo
   (dentro do vocabulário usado pelos métodos Aoki-Velloso/Décourt-Quaresma)
   e a presença/profundidade do nível d'água, quando indicado no laudo.
3. **Os dados extraídos NUNCA entram direto no cálculo.** Eles aparecem numa
   tabela editável, junto com o texto original do laudo para cada linha, para
   você conferir e corrigir eventuais erros de leitura da IA.
4. Só depois de clicar em "Confirmar e importar" os dados substituem o perfil
   de SPT (aba 1), que então pode ser ajustado manualmente como qualquer
   outro perfil digitado à mão.

### Como funciona a importação de esforços e a uniformização (aba 6)

1. Importe os esforços de fundação por elemento (pilar, bloco ou estaca)
   digitando manualmente, carregando um CSV ou importando o PDF do relatório
   de cargas do seu software estrutural via IA (mesmo fluxo de revisão da
   aba 2 - os itens extraídos entram diretamente na tabela de esforços para
   você conferir/corrigir/remover antes de calcular). Momento (Mk) e
   cortante (Hk) são opcionais - sem eles, a armadura usa apenas a taxa
   mínima; com eles, veja "Dimensionamento estrutural" abaixo.
   O CSV aceita as colunas
   `elemento,carga_caracteristica_kn,n_estacas,momento_knm,cortante_kn` e,
   opcionalmente, mais quatro colunas `mx_knm,my_knm,hx_kn,hy_kn` - se
   preenchidas, o momento/cortante resultante é calculado automaticamente
   (√(Mx²+My²) e √(Hx²+Hy²)) e tem prioridade sobre as colunas diretas.
2. **Quando o relatório traz M e H como componentes ortogonais** (Mx e My,
   e/ou Fx e Fy) em vez de um valor resultante único, use os campos
   "...ou componentes Mx, My" / "...ou Hx, Hy" na aba 5 (uma estaca) ou aba 6
   (lote): o software calcula a resultante automaticamente
   (√(Mx²+My²)/√(Hx²+Hy²)) - prática padrão para seções circulares, já que a
   armadura distribuída uniformemente no perímetro resiste igual em qualquer
   direção de flexão. **Na importação por IA (PDF), essa mesma combinação é
   feita automaticamente**: a IA é instruída a extrair Mx/My e Fx/Fy
   exatamente como aparecem no relatório (não a calcular a resultante ela
   mesma), e o software soma os componentes de forma confiável em Python -
   os valores brutos extraídos ficam visíveis nas colunas "Mx / My" e
   "Hx / Hy" da tabela de esforços (aba 6), para você conferir contra o PDF
   original antes de calcular.
3. **Use sempre a carga característica (Nk, de serviço)**, nunca a carga
   majorada de cálculo (Nd/ELU) - a capacidade admissível (Qadm) já embute o
   fator de segurança geotécnico, então a comparação correta é sempre contra
   a carga característica.
4. Quando um bloco tiver mais de uma estaca, informe o número de estacas: o
   software divide a carga do bloco igualmente entre elas (não considera
   excentricidade/momento - para isso, informe a carga já dividida por
   estaca e deixe "Nº de estacas" = 1).
5. Escolha se quer **uniformizar** as profundidades. Sem uniformização, cada
   estaca recebe sua própria profundidade mínima necessária. Uniformizando,
   você escolhe quantos grupos/profundidades padrão deseja (ex: 3): o
   software ordena as estacas pela profundidade individual necessária,
   separa em grupos e adota, para todas as estacas de cada grupo, a maior
   profundidade individual daquele grupo - nunca uma profundidade menor do
   que a necessidade de qualquer estaca do grupo.
6. Gere o memorial de cálculo em lote (.docx), com os esforços importados, o
   resultado individual e adotado de cada estaca, e a armação comum adotada.

### Dimensionamento estrutural por N-M-V (flexo-compressão e cisalhamento)

Quando você informa o momento fletor característico (Mk, aba 5 ou 6), a
armadura longitudinal deixa de ser calculada apenas pela taxa mínima e passa
a ser dimensionada de verdade:

- **Flexo-compressão (N-M)**: o diagrama de interação da seção circular é
  construído numericamente (método das fibras, bloco retangular de tensões
  da NBR 6118), e o software busca a menor combinação de barras que resista
  à força normal e ao momento de cálculo (Nd, Md). No lote (aba 6), a mesma
  armadura é verificada contra o Nd/Md de **todas** as estacas importadas
  simultaneamente - a mais exigente é reportada como "estaca governante".
- **Cisalhamento (V)**: se você também informar o cortante característico
  (Hk), os estribos são dimensionados pelo Modelo de Cálculo I da NBR 6118
  (largura equivalente usual para seção circular: bw = D; a altura útil "d"
  é calculada de forma geométrica exata: d = D - cobrimento - φestribo -
  φlongitudinal/2), reduzindo o espaçamento construtivo se necessário.
- **Fator de majoração (γf)**: informe sempre esforços **característicos**
  (Nk, Mk, Hk) - o software aplica γf (padrão 1,4, ajustável) para obter os
  esforços de cálculo (Nd, Md, Vd) usados na verificação estrutural. Se seu
  software estrutural já fornecer valores majorados, ajuste γf para 1,0.
- **fck e fyk** são configuráveis na aba 5 (padrão **30 MPa** e 500 MPa/CA-50
  - o padrão de fck segue o mínimo da NBR 6122:2022 para estacas em classe
  de agressividade I/II; ambientes mais agressivos (classes III/IV) exigem
  fck >= 40 MPa, ajustável).
- **Cobrimento** é configurável na aba 5 (padrão **5 cm**, mínimo da NBR
  6122:2022 8.6.2 para estacas moldadas in loco em classe de agressividade
  II; classes III/IV exigem >= 7 cm). Se você usar um cobrimento menor que
  o mínimo (prática comum com a alternativa simplificada da norma, que
  permite descontar 2 mm da bitola longitudinal no cálculo como "espessura
  de sacrifício"), o software emite um aviso - essa alternativa não é
  aplicada automaticamente, ajuste a bitola manualmente se for o seu caso.
- **γc (coeficiente de ponderação do concreto)** é configurável na aba 5
  (padrão **1,4**, o mesmo valor geral da NBR 6118, aplicável à grande
  maioria das estacas). A NBR 6122:2022 item 8.6.3 prevê um γc majorado
  apenas para execuções de **maior risco** (ex.: concretagem sem controle
  rigoroso, ou escavação sem qualquer suporte de parede/fluido
  estabilizante) - nesses casos específicos, aumente manualmente o γc (um
  valor de referência de 3,1 para o caso mais crítico - estaca escavada
  sem fluido - foi conferido por retro-cálculo contra um memorial de
  cálculo profissional real, e fica disponível como `GAMMA_C_CONCRETE_PILE`
  em `structural_design.py`). **Não use esse valor majorado como padrão
  geral** - ele mais que dobra a armadura calculada para o mesmo caso e só
  se justifica quando a execução realmente carece de controle de
  concretagem. Confirme sempre com o engenheiro responsável.

> ⚠️ **Este é um cálculo numérico aproximado** (ver `structural_design.py`
> para o método completo e as simplificações assumidas, como o modelo de
> cisalhamento e a extrapolação do bloco retangular de tensões na região de
> compressão quase centrada). Ele foi validado contra limites teóricos
> conhecidos (ex: capacidade à compressão pura) e conferido por retro-cálculo
> contra um memorial de cálculo profissional real, mas **deve ser conferido
> de forma independente** (cálculo manual, ábacos ou software estrutural
> dedicado) por um engenheiro responsável antes de qualquer execução -
> especialmente para estacas fortemente solicitadas à flexão.
>
> ⚠️ **Limitação importante: o momento/cortante de cálculo usados aqui são
> os valores informados (Mk, Hk) apenas majorados por γf** - o software
> **não** executa uma análise de interação solo-estrutura para estacas
> curtas sob carregamento lateral (o chamado "Método Russo", baseado em
> viga sobre base elástica, usado em memoriais profissionais para obter o
> momento/deslocamento real amplificado pela reação do solo a partir das
> cargas na cabeça da estaca). Se o Mk/Hk que você informa já vier de uma
> análise desse tipo (ex: extraído de um memorial ou software que já fez
> essa verificação), o resultado aqui é consistente; se vier de um cálculo
> simplificado (só a carga na cabeça da estaca), o momento de cálculo real
> pode ser **maior** do que o considerado aqui. Confirme com o engenheiro
> responsável se essa análise é necessária para o seu caso.

## Rodando os testes

```bash
python3 -m unittest discover -s tests -v
```

## Baixar o `.exe` do Windows já pronto (sem instalar Python)

Não é necessário instalar Python nem rodar nenhum comando para obter o
executável do Windows: um workflow do GitHub Actions
(`.github/workflows/build-windows-exe.yml`) builda o `spt_estacas.exe`
automaticamente a cada alteração relevante nesta branch, roda a suíte de
testes, e publica o binário em uma **Release fixa** do repositório:

**https://github.com/lucasbrb1-hue/lucasozfe/releases/tag/windows-build-latest**

Baixe o `spt_estacas.exe` anexado a essa release (link direto, não exige
login no GitHub) e rode - é um binário standalone, não precisa de Python
instalado no computador que for executá-lo. Essa release é atualizada
automaticamente a cada novo build; o link acima permanece sempre o mesmo.

Veja o **[TUTORIAL.md](TUTORIAL.md)** para um passo a passo de uso do
programa (todas as abas, os dois fluxos de cálculo - estaca única e lote -
e erros comuns).

Se quiser gerar o executável você mesmo (por exemplo, para testar uma
alteração local antes de commitar), siga a seção abaixo.

## Gerando o executável (PyInstaller)

```bash
python3 -m venv .buildvenv
source .buildvenv/bin/activate        # Windows: .buildvenv\Scripts\activate
pip install -r requirements.txt

pyinstaller --noconfirm --onefile --windowed \
  --name spt_estacas \
  --add-data "spt_piles:spt_piles" \
  --collect-data docx \
  main.py
```

`--collect-data docx` é necessário para empacotar o template interno usado
pelo `python-docx` na geração do memorial de cálculo.

O executável é gerado em `dist/`. Um `spt_estacas.spec` já é criado
automaticamente após o primeiro build e pode ser reutilizado com
`pyinstaller spt_estacas.spec`.

**Importante sobre a plataforma do executável**: o PyInstaller empacota um
binário para o **sistema operacional em que é executado** (não faz build
cruzado). O executável incluso neste repositório (`dist/spt_estacas`, se
presente) é um binário **Linux**. Para gerar o `.exe` do Windows, rode o
comando acima em uma máquina Windows (com Python instalado); para gerar um
app `.app`/binário macOS, rode em um Mac. No Windows, use `--add-data
"spt_piles;spt_piles"` (ponto e vírgula em vez de dois-pontos).

## Metodologia e limitações conhecidas

- **Décourt-Quaresma**: `Qp = alpha·K·Np·Ap`, `Ql = beta·10·(Nl/3+1)·U·L`,
  com `Np` = média das leituras de N-SPT na região da ponta e `Nl` = média
  das leituras ao longo do fuste (cada uma limitada a `[3, 50]`).
- **Aoki-Velloso**: `Qp = (K·Np/F1)·Ap`, `Ql = U·Σ(alpha·K·Ni/F2·Δli)`,
  integrando camada a camada do perfil de SPT.
- Os fatores `alpha`/`beta` (Décourt-Quaresma) e `F1`/`F2` (Aoki-Velloso)
  variam entre autores/edições, especialmente para estacas hélice contínua e
  Strauss — os valores adotados são referências usuais de mercado e devem
  ser conferidos/calibrados pelo responsável técnico.
- **A capacidade de carga do solo (Qadm, aba 4) considera apenas o esforço
  axial** (carga vertical de compressão) - os métodos semi-empíricos
  (Décourt-Quaresma, Aoki-Velloso) não verificam capacidade geotécnica a
  esforços horizontais (empuxo, vento, desaprumo), tração/arrancamento,
  efeitos de grupo de estacas, flambagem em solos muito moles, nem ações
  sísmicas/dinâmicas - isso exige verificação geotécnica complementar por um
  engenheiro responsável (métodos de estaca horizontalmente carregada, como
  Broms ou p-y, não estão implementados).
- **A armadura (aba 5/6) pode considerar momento e cortante**, se
  informados (ver "Dimensionamento estrutural" acima) - nesse caso ela deixa
  de ser só a taxa mínima e passa a ser dimensionada por flexo-compressão
  (N-M) e cisalhamento (V). Sem momento informado, a armadura continua sendo
  apenas a taxa mínima (válida só para estacas essencialmente à compressão
  axial). Em nenhum dos dois casos há verificação de torção nem de efeitos
  de grupo entre estacas vizinhas.
- **Profundidade de armação**: por padrão, a armadura longitudinal é
  estendida por toda a profundidade da estaca (opção mais segura). É
  possível pedir uma armadura parcial (informando o comprimento em metros na
  aba 5 ou 6) - útil quando a estaca trabalha só à compressão axial e não há
  esforços horizontais/momento relevantes na região não armada; o software
  nunca deixa a armadura ultrapassar o fundo da estaca (usa sempre o menor
  valor entre o comprimento pedido e a profundidade real de cada estaca) e
  emite um aviso lembrando que essa hipótese deve ser confirmada pelo
  engenheiro responsável antes de adotar.
- Quando ambos os métodos SPT são selecionados, a profundidade necessária
  adota o **mais conservador** (menor capacidade admissível) entre os dois,
  por segurança.
- A **interpretação de laudos por IA** é uma ferramenta de digitalização, não
  um laudo geotécnico automatizado: a qualidade da extração depende da
  legibilidade do PDF (inclusive escaneados), e erros de leitura são
  possíveis. Por isso a importação exige sempre revisão/confirmação manual
  antes de qualquer cálculo, e o memorial registra que os dados vieram de
  extração por IA revisada pelo usuário, para rastreabilidade.
- O **memorial de cálculo (.docx)** reproduz a memória completa (valores
  intermediários por profundidade, para cada método usado) e a armação
  sugerida, mas continua sendo um documento de apoio - ele não substitui a
  formatação/assinatura de um memorial de cálculo oficial de projeto.
- O **cálculo em lote por esforços importados** assume diâmetro de estaca
  único para todo o conjunto (definido na aba 3); apenas a profundidade (e,
  portanto, o comprimento da armadura longitudinal) varia por estaca. Não
  há, no momento, suporte a diâmetros diferentes por estaca dentro do mesmo
  lote.
- A **divisão de carga em blocos com múltiplas estacas** presume
  distribuição igual entre as estacas do bloco - não considera excentricidade
  de carga nem momentos que gerem reação desigual entre estacas de um mesmo
  bloco; isso deve ser verificado separadamente pelo engenheiro responsável
  em blocos assimétricos ou com cargas excêntricas relevantes.
- A **uniformização** agrupa as estacas ordenadas por profundidade
  individual necessária em N grupos contíguos, adotando a maior profundidade
  de cada grupo para todas as estacas daquele grupo - portanto sempre igual
  ou mais conservadora do que o cálculo individual, nunca menos.

## Licença de uso

Ferramenta de apoio técnico fornecida "como está", sem garantia de adequação
a um projeto específico. O uso profissional dos resultados é de
responsabilidade do engenheiro que assina o projeto.
