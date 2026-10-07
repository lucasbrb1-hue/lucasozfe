# Rastreador de Cachoeiras

Mapa de satélite com catálogo de cachoeiras e detecção de candidatas via Google Earth Engine.

## Rodar o mapa
```bash
cd cachoeiras
cp config.example.js config.js   # opcional: coloque sua GOOGLE_MAPS_API_KEY
python3 -m http.server 8000      # abra http://localhost:8000
```
Sem chave, usa imagens de satélite Esri. Com chave (Maps JavaScript API habilitada), usa Google Maps híbrido.

## Detectar novas cachoeiras
```bash
cd cachoeiras/detector
pip install -r requirements.txt
earthengine authenticate
python detectar.py --bbox -52 -29 -51 -28 --projeto SEU_PROJETO_GCP
```
Gera `data/candidatas.json` (laranja no mapa). O método combina rios (MERIT Hydro) com
desnível de terreno (SRTM 30 m): são **candidatas**, precisam de conferência visual
(inclui corredeiras, barragens e vertedouros).

## Catálogo
Edite `data/cachoeiras.json` (id, nome, lat, lng, estado, altura_m, descricao).
Alturas e coordenadas dos exemplos são aproximadas: confira antes de usar.
