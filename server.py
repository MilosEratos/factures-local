#!/usr/bin/env python3
"""Serveur standalone de l'app Factures Local.

Lance :  python server.py   →  http://localhost:5000

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
import atexit
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

# ── Gestion de llama-server ──────────────────────────────────────────

_llama_proc = None


def _kill_port_8081():
    """Tue un éventuel llama-server orphelin sur le port 8081."""
    try:
        s = socket.create_connection(("127.0.0.1", 8081), timeout=1)
        s.close()
    except OSError:
        return  # port libre, rien à faire
    # Le port est occupé : on tue le processus
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetTCPConnection -LocalPort 8081 -State Listen "
             "-ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
            timeout=10,
        )
        time.sleep(1)
    except Exception:
        pass


def _start_llama():
    """Lance llama-server en fond (sans fenêtre) et attend qu'il soit prêt."""
    global _llama_proc
    exe = os.path.join(ROOT, "llama.cpp", "llama-server.exe")
    model = os.path.join(ROOT, "models", "Qwen3.5-4B-Q4_K_M.gguf")
    if not os.path.exists(exe):
        raise RuntimeError("llama-server.exe introuvable — lancez d'abord install.bat")

    # Nettoyer un éventuel orphelin
    _kill_port_8081()

    print("Chargement du modèle (cela peut prendre un moment)...")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    _llama_proc = subprocess.Popen(
        [exe, "-m", model, "-ngl", "99", "--port", "8081",
         "--no-webui", "--reasoning", "off"],
        creationflags=flags,
    )

    # Attendre que le port 8081 réponde
    deadline = time.time() + 300
    while time.time() < deadline:
        if _llama_proc.poll() is not None:
            raise RuntimeError(
                "llama-server s'est arrêté au démarrage (code %d)." % _llama_proc.returncode)
        try:
            s = socket.create_connection(("127.0.0.1", 8081), timeout=1)
            s.close()
            print("Moteur IA prêt.")
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("llama-server ne répond pas après 5 minutes")


def _stop_llama():
    """Tue llama-server (appelé par atexit)."""
    global _llama_proc
    if _llama_proc and _llama_proc.poll() is None:
        _llama_proc.kill()
        _llama_proc.wait(timeout=5)
        print("Moteur IA arrêté.")


atexit.register(_stop_llama)

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
    _start_llama()
    print("Factures Local -> http://localhost:%d" % port)
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:%d" % port)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
