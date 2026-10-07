"""Servidor: cidade -> região -> candidatas a cachoeira com probabilidade.

  export EE_PROJECT=seu-projeto-gcp      # obrigatório
  export ANTHROPIC_API_KEY=...           # opcional: IA confere a imagem de satélite
  python servidor.py                     # http://localhost:8000
"""
import base64
import json
import os
import sqlite3
import sys
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "detector"))
from detectar import detectar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)
UA = {"User-Agent": "rastreador-cachoeiras/0.1"}
DB = os.environ.get("BUSCAS_DB", os.path.join(AQUI, "dados", "buscas.db"))
MAX_GRAUS = 0.4  # limita o tamanho da área analisada


def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS buscas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, consulta TEXT, cidade TEXT,
        criado_em REAL, ia INTEGER, resultado TEXT)""")
    return con


def salvar_busca(consulta, resultado):
    with db() as con:
        cur = con.execute(
            "INSERT INTO buscas (consulta, cidade, criado_em, ia, resultado) VALUES (?,?,?,?,?)",
            (consulta, resultado["local"]["nome"], time.time(), int(resultado["ia"]),
             json.dumps(resultado, ensure_ascii=False)))
        return cur.lastrowid


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
    resultado = {"local": local, "ia": bool(os.environ.get("ANTHROPIC_API_KEY")), "candidatas": pontos}
    resultado["id"] = salvar_busca(cidade, resultado)
    return jsonify(resultado)


@app.get("/api/historico")
def historico():
    with db() as con:
        linhas = con.execute(
            "SELECT id, consulta, cidade, criado_em, ia, json_array_length(resultado, '$.candidatas') "
            "FROM buscas ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([{"id": i, "consulta": q, "cidade": c, "criado_em": t, "ia": bool(ia), "total": n}
                    for i, q, c, t, ia, n in linhas])


@app.get("/api/historico/<int:busca_id>")
def historico_item(busca_id):
    with db() as con:
        linha = con.execute("SELECT resultado FROM buscas WHERE id=?", (busca_id,)).fetchone()
    if not linha:
        return jsonify(erro="Busca não encontrada."), 404
    resultado = json.loads(linha[0])
    resultado["id"] = busca_id
    return jsonify(resultado)


@app.get("/")
def raiz():
    return send_from_directory(AQUI, "index.html")


@app.get("/<path:arq>")
def estatico(arq):
    if arq in ("servidor.py",) or arq.startswith(("detector", "dados")):
        return "", 404
    return send_from_directory(AQUI, arq)


if __name__ == "__main__":
    # HOST=0.0.0.0 libera acesso por outros aparelhos da mesma rede (ex.: celular).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))
