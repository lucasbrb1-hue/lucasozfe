"""Detecta candidatas a cachoeira com Google Earth Engine.

Critério: pixel de rio (área de drenagem MERIT Hydro >= --min-area km²) onde o
terreno SRTM cai pelo menos --queda metros dentro de um raio de 150 m.

Uso:
  earthengine authenticate
  python detectar.py --bbox -52 -29 -51 -28 --projeto SEU_PROJETO_GCP \
      --saida ../data/candidatas.json
"""
import argparse
import json
import math

import ee


def detectar(bbox, projeto, min_area, queda, limite):
    ee.Initialize(project=projeto)
    regiao = ee.Geometry.Rectangle(bbox)
    elev = ee.Image("USGS/SRTMGL1_003").select("elevation")
    upa = ee.Image("MERIT/Hydro/v1_0_1").select("upa")

    rio = upa.gte(min_area)
    # Desnível em relação ao ponto mais baixo num raio de 150 m.
    minimo = elev.focalMin(radius=150, units="meters")
    desnivel = elev.subtract(minimo).rename("queda_m")

    cand = rio.And(desnivel.gte(queda))
    img = ee.Image.cat([desnivel, upa.rename("area_km2")]).updateMask(cand)
    pontos = img.sample(region=regiao, scale=30, geometries=True, numPixels=limite)

    saida = []
    for f in pontos.getInfo()["features"]:
        lng, lat = f["geometry"]["coordinates"]
        p = f["properties"]
        saida.append({
            "lat": round(lat, 5), "lng": round(lng, 5),
            "queda_m": round(p["queda_m"]), "area_km2": round(p["area_km2"], 1),
        })
    saida = deduplicar(saida)
    for p in saida:
        p["probabilidade"] = pontuar(p)
    return sorted(saida, key=lambda p: -p["probabilidade"])


def pontuar(p):
    """Probabilidade heurística (0-100) de ser cachoeira real.

    Mais queda e mais água (área de drenagem) => mais provável.
    """
    f_queda = min(p["queda_m"] / 80.0, 1.0)
    f_agua = min(max(math.log10(max(p["area_km2"], 1.0) / 10.0), 0.0) / 2.0, 1.0)
    return round(100 * (0.6 * f_queda + 0.4 * f_agua))


def deduplicar(pontos, grau=0.003):
    """Mantém só a maior queda em cada célula de ~300 m."""
    melhor = {}
    for p in pontos:
        k = (round(p["lat"] / grau), round(p["lng"] / grau))
        if k not in melhor or p["queda_m"] > melhor[k]["queda_m"]:
            melhor[k] = p
    return sorted(melhor.values(), key=lambda p: -p["queda_m"])


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--bbox", nargs=4, type=float, required=True,
                   metavar=("OESTE", "SUL", "LESTE", "NORTE"))
    a.add_argument("--projeto", required=True, help="ID do projeto Google Cloud com Earth Engine")
    a.add_argument("--min-area", type=float, default=10.0)
    a.add_argument("--queda", type=float, default=30.0)
    a.add_argument("--limite", type=int, default=2000)
    a.add_argument("--saida", default="../data/candidatas.json")
    args = a.parse_args()
    res = detectar(args.bbox, args.projeto, args.min_area, args.queda, args.limite)
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"{len(res)} candidatas salvas em {args.saida}")
