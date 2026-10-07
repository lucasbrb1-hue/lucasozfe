# Rastreador de Cachoeiras

Mapa de satélite com catálogo de cachoeiras e detecção de candidatas via Google Earth Engine.

## Como usar (cidade -> locais prováveis)
```bash
cd cachoeiras
pip install -r requirements.txt
pip install -r detector/requirements.txt
earthengine authenticate
export EE_PROJECT=seu-projeto-gcp        # projeto Google Cloud com Earth Engine
export ANTHROPIC_API_KEY=...             # opcional: IA confere a imagem de satélite
cp config.example.js config.js           # opcional: GOOGLE_MAPS_API_KEY
python servidor.py                       # abra http://localhost:8000
```
Digite uma cidade: o servidor define uma área ao redor (até ~0,4°), roda o Earth Engine
(rios MERIT Hydro + desnível SRTM) e devolve até 50 pontos com **probabilidade**.
Nota base = mais queda e mais água => mais provável. Com `ANTHROPIC_API_KEY`, os 10 melhores
têm a imagem de satélite avaliada por um modelo de visão e a nota final é a média das duas.
As buscas ficam salvas em `dados/buscas.db` (SQLite) e aparecem em "Buscas salvas" para reabrir sem refazer.
São candidatas: confirme visualmente (barragens e corredeiras podem passar).

## Só o mapa (sem busca)
`python3 -m http.server 8000` dentro de `cachoeiras/` mostra apenas o catálogo.

## Catálogo
Edite `data/cachoeiras.json` (id, nome, lat, lng, estado, altura_m, descricao).
Alturas e coordenadas dos exemplos são aproximadas: confira antes de usar.
