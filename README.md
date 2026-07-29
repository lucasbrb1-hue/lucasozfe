# Cálculo de Estacas via SPT — Profundidade e Armação

Software desktop (Python + Tkinter) para apoiar o pré-dimensionamento de
estacas a partir de um perfil de sondagem SPT (Standard Penetration Test):

- Estima a **capacidade de carga admissível** por profundidade usando os
  métodos semi-empíricos **Décourt-Quaresma** e/ou **Aoki-Velloso**.
- Determina a **profundidade mínima** de estaca que atende a uma carga de
  projeto informada.
- Sugere a **armação** (barras longitudinais e estribos) com base em taxas
  mínimas de armadura usuais associadas à NBR 6118 / NBR 6122.
- Suporta os tipos de estaca: hélice contínua, escavada (broca), pré-moldada
  cravada e Strauss.
- **Interpreta laudos de sondagem SPT em PDF via IA** (API da Claude,
  Anthropic): extrai profundidade, N-SPT, tipo de solo e nível d'água
  automaticamente, sempre com revisão humana obrigatória antes de qualquer
  cálculo.
- Gera um **memorial de cálculo completo em .docx**, com metodologia,
  fórmulas e memória de cálculo (valores intermediários) de cada método e
  de cada profundidade analisada.
- **Importa os esforços (cargas) de fundação** gerados por softwares de
  dimensionamento estrutural (Eberick, TQS, CypeCad etc.) - manualmente,
  por planilha CSV, ou via IA a partir do PDF do relatório de cargas - e
  calcula automaticamente a **profundidade e a armadura de cada estaca**,
  com opção de **uniformizar** (agrupar) as profundidades em um número
  escolhido de padrões, para simplificar a execução na obra.

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
  reinforcement.py         dimensionamento da armação
  ai_extraction.py          interpretação de laudos SPT e relatórios de esforços (PDF) via API da Claude
  memorial.py                geração do memorial de cálculo completo (.docx) de uma estaca
  loads.py                    esforços de fundação por elemento (pilar/bloco/estaca)
  pile_group.py                cálculo em lote por estaca e uniformização (agrupamento)
  batch_memorial.py             memorial de cálculo (.docx) do lote de estacas
  report.py                      geração de relatório resumido em texto
  gui.py                          interface gráfica (Tkinter)
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
   digitando manualmente, carregando um CSV (`elemento,carga_caracteristica_kn,n_estacas`)
   ou importando o PDF do relatório de cargas do seu software estrutural via
   IA (mesmo fluxo de revisão da aba 2 - os itens extraídos entram
   diretamente na tabela de esforços para você conferir/corrigir/remover
   antes de calcular).
2. **Use sempre a carga característica (Nk, de serviço)**, nunca a carga
   majorada de cálculo (Nd/ELU) - a capacidade admissível (Qadm) já embute o
   fator de segurança geotécnico, então a comparação correta é sempre contra
   a carga característica.
3. Quando um bloco tiver mais de uma estaca, informe o número de estacas: o
   software divide a carga do bloco igualmente entre elas (não considera
   excentricidade/momento - para isso, informe a carga já dividida por
   estaca e deixe "Nº de estacas" = 1).
4. Escolha se quer **uniformizar** as profundidades. Sem uniformização, cada
   estaca recebe sua própria profundidade mínima necessária. Uniformizando,
   você escolhe quantos grupos/profundidades padrão deseja (ex: 3): o
   software ordena as estacas pela profundidade individual necessária,
   separa em grupos e adota, para todas as estacas de cada grupo, a maior
   profundidade individual daquele grupo - nunca uma profundidade menor do
   que a necessidade de qualquer estaca do grupo.
5. Gere o memorial de cálculo em lote (.docx), com os esforços importados, o
   resultado individual e adotado de cada estaca, e a armação comum adotada.

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
- **O software analisa apenas o esforço axial (carga vertical de
  compressão)** transmitido à estaca. Ele NÃO verifica: esforços
  horizontais/cortante (empuxo, vento na base, desaprumo), momento fletor,
  tração/arrancamento, torção, efeitos de grupo de estacas (interação
  estaca-estaca), flambagem em solos muito moles, nem ações sísmicas ou
  dinâmicas. Qualquer estaca sujeita a esses esforços exige verificação
  estrutural/geotécnica complementar por um engenheiro responsável (métodos
  de estacas horizontalmente carregadas, como Broms ou p-y, não estão
  implementados aqui).
- O módulo de armação calcula a **armadura mínima** (longitudinal e
  estribos) para estacas moldadas em concreto trabalhando essencialmente à
  compressão axial - não dimensiona para flexão composta nem cisalhamento
  por carga lateral (ver item acima).
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
