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
  ai_extraction.py          interpretação de laudos SPT (PDF) via API da Claude
  memorial.py                geração do memorial de cálculo completo (.docx)
  report.py                   geração de relatório resumido em texto
  gui.py                       interface gráfica (Tkinter)
main.py                      ponto de entrada
tests/                        testes unitários (unittest)
```

## Rodando a partir do código-fonte

Requer apenas Python 3.10+ com Tkinter (já incluso na maioria das
instalações; no Ubuntu/Debian, se necessário: `sudo apt install python3-tk`).

```bash
python3 main.py
```

Para usar a **interpretação de laudos SPT via IA** e a **geração do memorial
em .docx**, instale as dependências opcionais e configure sua chave de API:

```bash
pip install -r requirements.txt

# Linux/macOS
export ANTHROPIC_API_KEY="sua-chave-aqui"
# Windows (PowerShell)
setx ANTHROPIC_API_KEY "sua-chave-aqui"
```

A chave é obtida em https://console.anthropic.com/ e **nunca** deve ser
commitada no repositório - ela só é lida em tempo de execução, a partir da
variável de ambiente. Sem `ANTHROPIC_API_KEY` definida, o resto do software
funciona normalmente; apenas a aba "2. Importar Laudo (IA)" mostrará uma
mensagem pedindo para configurar a chave.

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

## Rodando os testes

```bash
python3 -m unittest discover -s tests -v
```

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
- O módulo de armação calcula apenas a **armadura mínima** para estacas
  moldadas em concreto trabalhando essencialmente à compressão axial. Não
  contempla flexão composta, esforços horizontais, sismo, verificação ao
  cisalhamento por carregamento lateral, nem efeitos de grupo de estacas.
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

## Licença de uso

Ferramenta de apoio técnico fornecida "como está", sem garantia de adequação
a um projeto específico. O uso profissional dos resultados é de
responsabilidade do engenheiro que assina o projeto.
