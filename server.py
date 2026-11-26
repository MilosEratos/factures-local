#!/usr/bin/env python3
"""Serveur standalone de l'app Factures Local.

Lance par start.bat (qui demarre aussi llama-server en arriere-plan).
Fermer la console arrete tout (meme console).

Endpoints :
  GET  /                 page web (static/index.html)
  POST /api/generate     génère la facture PDF + aperçu PNG dans data/
  GET  /files/<name>     sert un fichier de data/ (PDF ou aperçu PNG)
  DELETE /api/files/<n>  supprime un fichier de data/
  GET  /api/state        état local : compteur, historique, clients (data/state.json)
  POST /api/state        sauvegarde l'état
  POST /api/assistant    LLM local via llama-server → JSON facture
  GET  /api/models       liste des modèles disponibles
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import webbrowser

from flask import Flask, jsonify, request, send_from_directory, abort

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

sys.path.insert(0, ROOT)
from core.gen import build, make_preview, invoice_filename, load_config  # noqa: E402

app = Flask(__name__, static_folder="static")
LLAMA_HOST = "http://127.0.0.1:8081"


def _port_open(port):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=1)
        s.close()
        return True
    except OSError:
        return False


def _kill_port_8081():
    """Tue un éventuel llama-server orphelin sur le port 8081."""
    if not _port_open(8081):
        return
    print("Un ancien moteur IA tourne encore sur le port 8081 — arret...")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetTCPConnection -LocalPort 8081 -State Listen "
             "-ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
            timeout=15,
        )
        time.sleep(1)
    except Exception:
        pass


def _wait_llama():
    """Attend que llama-server (demarre par start.bat) reponde sur 8081."""
    print("Attente du chargement du modele (cela peut prendre un moment)...")
    deadline = time.time() + 300
    while time.time() < deadline:
        if _port_open(8081):
            print("Moteur IA pret.")
            return
        time.sleep(1)
    print("[ERREUR] Le moteur IA ne repond pas apres 5 minutes.")
    print("Voir le fichier llama.log dans le dossier de l'application.")
    sys.exit(1)


# ── Routes ───────────────────────────────────────────────────────────


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    d = request.get_json(force=True)
    try:
        cfg = load_config()
        pdf_bytes, preview_bytes, fname = build(d, cfg)
        with open(os.path.join(DATA_DIR, fname), "wb") as f:
            f.write(pdf_bytes)
        prev = fname.replace(".pdf", "_preview.png")
        with open(os.path.join(DATA_DIR, prev), "wb") as f:
            f.write(preview_bytes)
        return jsonify({"ok": True, "file": fname, "preview": prev})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/files/<name>")
def files(name):
    return send_from_directory(DATA_DIR, name)


@app.route("/api/files/<name>", methods=["DELETE"])
def delete_file(name):
    p = os.path.join(DATA_DIR, name)
    if os.path.exists(p):
        os.remove(p)
    return jsonify({"ok": True})


@app.route("/api/state", methods=["GET", "POST"])
def api_state():
    sf = os.path.join(DATA_DIR, "state.json")
    if request.method == "POST":
        with open(sf, "w", encoding="utf-8") as f:
            json.dump(request.get_json(force=True), f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    if os.path.exists(sf):
        with open(sf, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({"counter": 1, "history": [], "clients": []})


@app.route("/api/assistant", methods=["POST"])
def api_assistant():
    d = request.get_json(force=True)
    messages = d.get("messages", [])
    today = d.get("today", "")
    system = (
        "Tu es un assistant de facturation. L'utilisateur décrit une prestation "
        "en langage naturel. Renvoie UNIQUEMENT un objet JSON valide, sans texte "
        "autour, avec ces clés : number (string, ex \"N-1\"), date (string YYYY-MM-DD), "
        "client (string), addr (array de string, une ligne par adresse), "
        "lines (array d'objets {desc, note, qty, amount}), "
        "title (array de string, titres de section, peut être vide). "
        "Si une info manque, mets une valeur vide ou raisonnable. "
        "Date du jour : " + today
    )
    payload = {
        "model": "local",
        "messages": [{"role": "system", "content": system}] +
                    [{"role": "user", "content": m} for m in messages],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    try:
        req = urllib.request.Request(
            LLAMA_HOST + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read().decode("utf-8"))
        text = out["choices"][0]["message"]["content"]
        return jsonify({"ok": True, "text": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/models")
def api_models():
    try:
        with urllib.request.urlopen(LLAMA_HOST + "/v1/models", timeout=10) as r:
            out = json.loads(r.read().decode("utf-8"))
        return jsonify({"ok": True, "models": [m.get("id") for m in out.get("data", [])]})
    except Exception as e:
        return jsonify({"ok": False, "models": [], "error": str(e)})


# ── Démarrage ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = int(os.environ.get("PORT", 5000))
    _kill_port_8081()
    _wait_llama()
    print("Factures Local -> http://localhost:%d" % port)
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:%d" % port)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
