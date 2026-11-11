# Gastos em 3D

Controle financeiro pessoal em um ambiente 3D. Cada categoria de gasto (casa,
comida, transporte...) é um reservatório de vidro cuja altura representa o
limite mensal; o líquido sobe a cada gasto lançado.

## Como usar

Abra `index.html` no navegador (não precisa de servidor nem de instalação).

- **Girar / aproximar**: arraste a cena; use a roda do mouse ou o gesto de pinça.
- **Lançar gasto**: clique em um reservatório (ou no rótulo dele), informe o
  valor, a data e a descrição.
- **Limite e alerta**: no painel da categoria, abra "Limite e alerta" para
  definir o limite mensal e em que porcentagem o aviso dispara (padrão 80%).
- **Nova categoria**: botão "+ Nova categoria".
- **Meses**: as setas no topo trocam o mês exibido; cada mês tem seus gastos.

## Alertas

| Situação | O que acontece |
| --- | --- |
| Perto do limite (>= % de alerta) | anel âmbar pulsando, borda da tela âmbar, aviso e som |
| Limite atingido ou estourado | líquido vermelho transbordando, reservatório tremendo, borda da tela vermelha pulsando, aviso e alarme sonoro |

Os dados ficam salvos apenas no navegador (`localStorage`). Na primeira
abertura aparecem dados de exemplo; "Começar do zero" os apaga.

Usa [three.js](https://threejs.org) r160 (licença MIT, em `vendor/`).
