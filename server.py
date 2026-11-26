#!/usr/bin/env python3
"""Serveur standalone de l'app Factures Local.

Lance :  python server.py   â†’  http://localhost:5000

Endpoints :
  GET  /                 page web (static/index.html)
  POST /api/generate     gÃ©nÃ¨re la facture PDF + aperÃ§u PNG dans data/
  GET  /files/<name>     sert un fichier de data/ (PDF ou aperÃ§u PNG)
  DELETE /api/files/<n>  supprime un fichier de data/
  GET  /api/state        Ã©tat local : compteur, historique, clients (data/state.json)
  POST /api/state        sauvegarde l'Ã©tat
  POST /api/assistant    LLM local via Ollama â†’ JSON facture
  GET  /api/models       liste des modÃ¨les Ollama installÃ©s
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error

from flask import Flask, jsonify, request, send_from_directory, abort

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

sys.path.insert(0, ROOT)
from core.gen import build, make_preview, invoice_filename, load_config  # noqa: E402

CONFIG = load_config()
LLAMA = CONFIG.get("llama", {})
LLAMA_HOST = LLAMA.get("host", "http://localhost:8081").rstrip("/")
LLAMA_MODEL = LLAMA.get("model", "models/qwen3.5-4b-q4_k_m.gguf")

app = Flask(__name__, static_folder=os.path.join(ROOT, "static"),
            static_url_path="/static")


def _state_path():
    return os.path.join(DATA_DIR, "state.json")


def load_state():
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"counter": "1", "history": [], "clients": []}


def save_state(state):
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return send_from_directory(os.path.join(ROOT, "static"), "index.html")


@app.route("/api/state", methods=["GET"])
def api_state_get():
    return jsonify(load_state())


@app.route("/api/state", methods=["POST"])
def api_state_set():
    state = request.get_json(force=True)
    if not isinstance(state, dict):
        abort(400)
    save_state(state)
    return jsonify({"ok": True})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    try:
        for k in ("number", "date", "client_name"):
            if not str(data.get(k, "")).strip():
                return jsonify({"ok": False, "error": "champ manquant : %s" % k}), 400
        lines = data.get("lines", [])
        if not lines:
            return jsonify({"ok": False, "error": "aucune ligne de prestation"}), 400
        for l in lines:
            if not (float(l.get("amount") or 0) > 0):
                return jsonify({"ok": False, "error": "chaque ligne doit avoir un montant"}), 400

        name = data.get("output") or invoice_filename(
            str(data["number"]), str(data["date"]),
            str(data["client_name"]), data.get("title", []))
        name = os.path.basename(name)
        for ch in '<>:"|?*':
            name = name.replace(ch, "-")
        out_path = os.path.join(DATA_DIR, name)
        total = build(data, out_path, CONFIG)
        preview = make_preview(out_path)
        return jsonify({
            "ok": True,
            "file": name,
            "preview": (os.path.basename(preview) if preview else None),
            "total": total,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/files/<path:name>")
def files(name):
    safe = os.path.basename(name)
    p = os.path.join(DATA_DIR, safe)
    if not os.path.exists(p):
        abort(404)
    return send_from_directory(DATA_DIR, safe)


@app.route("/api/files/<path:name>", methods=["DELETE"])
def api_files_delete(name):
    safe = os.path.basename(name)
    p = os.path.join(DATA_DIR, safe)
    if os.path.exists(p):
        os.remove(p)
    return jsonify({"ok": True})


SYSTEM_PROMPT = (
    "Tu remplis un formulaire de facture Ã  partir des messages de l'utilisateur. "
    "RÃ©ponds UNIQUEMENT avec un objet JSON valide, sans markdown ni texte autour, "
    "exactement au format : "
    '{"number":"","date":"JJ/MM/AAAA","client":"","addr":[],"title":[],'
    '"lines":[{"desc":"","note":"","qty":1,"amount":0}]}'
)


@app.route("/api/assistant", methods=["POST"])
def api_assistant():
    body = request.get_json(force=True)
    messages = body.get("messages", [])
    today = body.get("today", "")
    if not messages:
        return jsonify({"ok": False, "error": "aucun message"}), 400

    prompt = ("Aujourd'hui la date est %s (JJ/MM/AAAA).\n" % today +
              "\n".join("Message %d : %s" % (i + 1, m) for i, m in enumerate(messages)) +
              "\n\nRÃ¨gles : number = le numÃ©ro de facture demandÃ© (ex : Â« numÃ©ro 230300 Â»), "
              "vide sinon. date = la date de la facture en JJ/MM/AAAA ; si l'utilisateur dit "
              "Â« demain Â», calcule le lendemain d'aujourd'hui ; vide sinon. client = le nom du "
              "client seul, sans les mots de la phrase. addr = tableau d'au plus 2 Ã©lÃ©ments : "
              "[rue, \"code postal ville\"] ; le code postal et la ville sont TOUJOURS sur la "
              "mÃªme ligne (ex : \"75011 Paris\", \"69001 Lyon\") ; si l'utilisateur mentionne un "
              "arrondissement (ex : \"18e\"), le code postal est 750XX oÃ¹ XX = le numÃ©ro de "
              "l'arrondissement (ex : \"18e\" â†’ \"75018 Paris\") ; sinon, si la ville est une "
              "grande ville franÃ§aise bien connue et que le code postal n'est pas donnÃ©, ajoute "
              "le code postal usuel AVANT le nom de la ville ; ne devine JAMAIS un arrondissement "
              "diffÃ©rent de celui mentionnÃ© par l'utilisateur. "
              "title = la 1re ligne est le type de prestation, la 2e ligne le nom du projet UNIQUEMENT "
              "si un nom de projet est explicitement mentionné (sinon une seule ligne, ne mets JAMAIS "
              "'Projet non spécifié' ni rien d'autre). lines = une entrÃ©e par prestation : desc = nom de la prestation, "
              "note = le tarif au format Â« 500â‚¬/jour Â» s'il est mentionnÃ©, qty = quantité (jours, heures ou unités selon ce qui est dit), "
              "amount = total de la ligne (tarif Ã— qty, Ã  calculer). Ne mets que ce "
              "qui est rÃ©ellement dit, sinon vide (\"\" ou [] ou 0). Ne devine rien.")

    model = body.get("model") or LLAMA_MODEL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "max_tokens": int(LLAMA.get("max_tokens", 2048)),
        "temperature": 0,
    }
    try:
        req = urllib.request.Request(
            LLAMA_HOST + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.loads(r.read().decode("utf-8"))
        text = out["choices"][0]["message"]["content"]
        return jsonify({"ok": True, "text": text, "model": model})
    except urllib.error.URLError as e:
        return jsonify({"ok": False,
                        "error": "llama-server injoignable (%s) â€” vÃ©rifiez que le serveur tourne." % e}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/models", methods=["GET"])
def api_models():
    try:
        with urllib.request.urlopen(LLAMA_HOST + "/v1/models", timeout=10) as r:
            out = json.loads(r.read().decode("utf-8"))
        return jsonify({"ok": True, "models": [m.get("id") for m in out.get("data", [])]})
    except Exception as e:
        return jsonify({"ok": False, "models": [], "error": str(e)})


if __name__ == "__main__":
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = int(os.environ.get("PORT", 5000))
    print("Factures Local -> http://localhost:%d" % port)
    app.run(host="127.0.0.1", port=port, debug=False)

