# Gastos em 3D

Controle financeiro pessoal em um ambiente 3D. Cada categoria de gasto aparece
como o próprio objeto do gasto (uma casa, um carro, um hambúrguer...). O objeto
inteiro representa o limite mensal e vai se enchendo de cor, de baixo para
cima, a cada gasto lançado.

O formato é escolhido pelo nome da categoria (por exemplo "Aluguel" vira casa,
"Combustível" vira carro, "Mercado" vira comida) e pode ser trocado em
"Limite e alerta" > "Formato". Formatos: casa, carro, comida, lazer (pipoca),
saúde (maleta), educação (livros) e moedas (para o que não se encaixa).

## Como usar

Abra `index.html` no navegador (não precisa de servidor nem de instalação).

- **Girar / aproximar**: arraste a cena; use a roda do mouse ou o gesto de pinça.
- **Lançar gasto**: clique em um objeto (ou no rótulo dele), informe o
  valor, a data e a descrição.
- **Limite e alerta**: no painel da categoria, abra "Limite e alerta" para
  definir o limite mensal e em que porcentagem o aviso dispara (padrão 80%).
- **Nova categoria**: botão "+ Nova categoria".
- **Meses**: as setas no topo trocam o mês exibido; cada mês tem seus gastos.

## Alertas

| Situação | O que acontece |
| --- | --- |
| Perto do limite (>= % de alerta) | anel âmbar pulsando, borda da tela âmbar, aviso e som |
| Limite atingido ou estourado | objeto vermelho transbordando e tremendo, borda da tela vermelha pulsando, aviso e alarme sonoro |

## O objetivo: a meta de economia

O centro da praça é a sua meta (uma viagem, um carro, a casa própria, uma
reserva de emergência...). Você informa quanto custa e em quantos meses quer
chegar lá. O monumento da meta se enche de ouro conforme o dinheiro guardado.

- **Como se guarda**: a sobra de cada mês é a soma dos limites menos os gastos.
  Meses fechados ficam garantidos (ouro); a sobra do mês atual fica "em jogo"
  (ouro claro) e diminui a cada gasto. Um mês no vermelho tira do cofre.
- **Só vale mês anotado**: um mês só entra no cofre se houver gastos lançados
  em pelo menos 8 dias dele. Deixar de anotar não ajuda a meta.
- **Ritmo**: o painel da meta mostra quanto precisa sobrar por mês e o teto de
  gasto por dia até o fim do mês para chegar lá no prazo.
- **Marcos**: 25%, 50% e 75% da meta rendem +50 XP cada; alcançar a meta rende
  +200 XP e uma conquista. Depois dá para concluir e escolher a próxima; o que
  passou do valor já conta para ela.

## O jogo

Lançar gastos rende XP, e o XP sobe de nível. Cada nível libera uma recompensa
que aparece na cena.

| Como ganhar XP | Valor |
| --- | --- |
| Lançar um gasto (5 primeiros de cada dia) | +10 |
| Primeiro gasto do dia | +15, mais um bônus que cresce com os dias seguidos |
| Abrir o dia com categorias dentro do limite | +5 por categoria |
| Aceitar a ajuda oferecida por um personagem | +20 |
| Missões do dia e da semana | +15 a +50 |
| Conquistas | +30 cada |

| Nível | XP | Recompensa |
| --- | --- | --- |
| 2 Anotador | 100 | Bonés para os personagens |
| 3 Organizado | 250 | Árvores na praça |
| 4 Poupador | 450 | Troféu de bronze na praça |
| 5 Estrategista | 700 | Coroas douradas |
| 6 Mestre do orçamento | 1000 | Troféu de ouro |
| 7 Lenda | 1400 | Fogos de artifício |

O botão de nível no topo abre "Sua jornada", com a sequência de dias, as
missões, as recompensas e as conquistas. Os dados de exemplo não rendem o
bônus diário.

## Personagens

Cada categoria tem um personagem (uma miniatura do objeto, com rosto), com humor
conforme a situação (tranquilo, preocupado ou bravo). De tempos em tempos — e
logo depois de um gasto que acende um alerta — eles interagem:

- **Lição**: quem está dentro do limite vai até quem está mal e ensina.
- **Briga**: se o aluno não aceita a bronca, ou se os dois estouraram, vira
  briga (com poeira e tudo) até fazerem as pazes.
- **Ajuda**: depois da lição, o professor pode oferecer parte do seu limite
  ao colega estourado; você decide em "Transferir" ou "Agora não".
- **Elogio**: com tudo em ordem, eles se parabenizam.

O botão "Conversas" liga ou pausa as interações.

Os dados ficam salvos apenas no navegador (`localStorage`). Na primeira
abertura aparecem dados de exemplo; "Começar do zero" os apaga.

Usa [three.js](https://threejs.org) r160 (licença MIT, em `vendor/`).
