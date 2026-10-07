"""Servidor: cidade -> região -> candidatas a cachoeira com probabilidade.

  export EE_PROJECT=seu-projeto-gcp      # obrigatório
  export ANTHROPIC_API_KEY=...           # opcional: IA confere a imagem de satélite
  python servidor.py                     # http://localhost:8000
"""
import base64
import json
import os
import sys

import requests
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "detector"))
from detectar import detectar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)
UA = {"User-Agent": "rastreador-cachoeiras/0.1"}
MAX_GRAUS = 0.4  # limita o tamanho da área analisada


def geocodificar(cidade):
    r = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=20,
                     params={"q": cidade, "format": "json", "limit": 1, "countrycodes": "br"})
    r.raise_for_status()
    dados = r.json()
    if not dados:
        return None
    sul, norte, oeste, leste = map(float, dados[0]["boundingbox"])
    lat, lng = float(dados[0]["lat"]), float(dados[0]["lon"])
    # Cidade pequena: expande para pegar o entorno rural (onde ficam as cachoeiras).
    meio = max(norte - sul, leste - oeste, 0.15) / 2
    meio = min(meio, MAX_GRAUS / 2)
    return {"nome": dados[0]["display_name"], "lat": lat, "lng": lng,
            "bbox": [lng - meio, lat - meio, lng + meio, lat + meio]}


def imagem_satelite(lat, lng, d=0.004):
    r = requests.get(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export",
        headers=UA, timeout=30,
        params={"bbox": f"{lng-d},{lat-d},{lng+d},{lat+d}", "bboxSR": 4326, "imageSR": 4326,
                "size": "512,512", "format": "jpg", "f": "image"})
    r.raise_for_status()
    return r.content


def conferir_com_ia(pontos, limite=10):
    """Pede a um modelo de visão para avaliar a imagem de satélite dos melhores pontos."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    import anthropic
    cli = anthropic.Anthropic()
    for p in pontos[:limite]:
        try:
            img = base64.b64encode(imagem_satelite(p["lat"], p["lng"])).decode()
            msg = cli.messages.create(
                model="claude-sonnet-5-5", max_tokens=300,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
                    {"type": "text", "text":
                        "Imagem de satélite (~800 m) centrada num trecho de rio com forte desnível. "
                        "Estime a chance de haver uma cachoeira natural (não barragem, vertedouro ou "
                        "corredeira suave). Responda só JSON: "
                        '{"probabilidade": 0-100, "motivo": "uma frase em português"}'}]}])
            txt = msg.content[0].text
            ia = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
            p["ia_probabilidade"] = int(ia["probabilidade"])
            p["ia_motivo"] = ia["motivo"]
            p["probabilidade"] = round((p["probabilidade"] + p["ia_probabilidade"]) / 2)
        except Exception as e:  # uma falha não derruba a busca inteira
            p["ia_motivo"] = f"IA indisponível: {type(e).__name__}"
    pontos.sort(key=lambda p: -p["probabilidade"])


@app.get("/api/buscar")
def buscar():
    cidade = request.args.get("cidade", "").strip()
    if not cidade:
        return jsonify(erro="Informe uma cidade."), 400
    projeto = os.environ.get("EE_PROJECT")
    if not projeto:
        return jsonify(erro="Defina a variável EE_PROJECT (projeto Google Cloud com Earth Engine)."), 500
    local = geocodificar(cidade)
    if not local:
        return jsonify(erro=f"Cidade '{cidade}' não encontrada."), 404
    try:
        pontos = detectar(local["bbox"], projeto, min_area=10.0, queda=25.0, limite=3000)
    except Exception as e:
        return jsonify(erro=f"Falha no Earth Engine: {e}"), 502
    pontos = pontos[:50]
    conferir_com_ia(pontos)
    return jsonify(local=local, ia=bool(os.environ.get("ANTHROPIC_API_KEY")), candidatas=pontos)


@app.get("/")
def raiz():
    return send_from_directory(AQUI, "index.html")


@app.get("/<path:arq>")
def estatico(arq):
    if arq in ("servidor.py",) or arq.startswith("detector"):
        return "", 404
    return send_from_directory(AQUI, arq)


if __name__ == "__main__":
    app.run(port=8000)
