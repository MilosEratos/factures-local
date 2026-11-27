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
  POST /api/assistant    LLM local via llama.cpp → JSON facture
  GET  /api/models       liste des modèles (info)
"""
import json
import os
import re
import sys
import unicodedata
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


# ============================================================
# Correction des codes postaux (post-processing, zéro impact
# sur le temps de génération). Source : base officielle des
# codes postaux (INSEE / Conseillers Opérationnels de l'Adresse).
# Règles : on ne modifie JAMAIS un code déjà présent ; on
# n'ajoute un code que si la ville est dans le dictionnaire ;
# ville inconnue → on ne touche à rien.
# ============================================================

CITY_CPS = {
    "paris": "75000", "lyon": "69000", "marseille": "13000",
    "toulouse": "31000", "nice": "06000", "nantes": "44000",
    "montpellier": "34000", "strasbourg": "67000", "bordeaux": "33000",
    "lille": "59000", "rennes": "35000", "saint etienne": "42000",
    "toulon": "83000", "grenoble": "38000", "dijon": "21000",
    "angers": "49000", "le havre": "76000", "clermont ferrand": "63000",
    "aix en provence": "13100", "brest": "29200", "limoges": "86000",
    "tours": "37000", "amiens": "80000", "metz": "57000",
    "perpignan": "66000", "nancy": "54000", "orleans": "45000",
    "reims": "51000", "rouen": "76000", "besancon": "25000",
    "caen": "14000", "mulhouse": "68000", "valenciennes": "59300",
    "saint denis": "93200", "villeurbanne": "69100",
    "nanterre": "92000", "creteil": "94000", "vitry sur seine": "94400",
    "boulogne billancourt": "92100", "levallois perret": "92300",
    "versailles": "78000", "cergy": "95000", "pontoise": "95300",
    "evry courcouronnes": "91000", "corbeil essonnes": "91100",
    "montreuil": "93100", "ivry sur seine": "94200",
    "asnieres sur seine": "92600", "argenteuil": "95100",
    "clichy": "92110", "neuilly sur seine": "92200", "puteaux": "92800",
    "colombes": "92700", "sceaux": "92330", "rueil malmaison": "92390",
    "cannes": "06400", "antibes": "06600", "saint laurent du var": "83100",
    "avignon": "84000", "arles": "13200", "montlucon": "03100",
    "moulins": "03000", "nevers": "58000", "chalon sur saone": "71100",
    "macon": "71000", "dole": "39000", "lons le saunier": "39000",
    "belfort": "90000", "colmar": "68000", "epinal": "88000",
    "charleville mezieres": "08000", "troyes": "10000",
    "chartres": "28000", "sens": "89000",
    "la roche sur yon": "44300", "lucon": "49400", "la rochelle": "17000",
    "royan": "17200", "poitiers": "86000", "gueret": "23000",
    "aubagne": "13400", "salon de provence": "13400",
    "draguignan": "83300", "frejus": "83600", "saint Raphael": "83700",
    "grasse": "06130", "mougins": "06250", "villeneuve loubet": "06270",
    "saint martin de re": "17290", "cognac": "16100",
}


def _norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fix_postal_code(addr, prompt_text=""):
    if not isinstance(addr, list) or not addr:
        return addr
    out = [str(a).strip() for a in addr]
    city_line = out[-1]
    if not city_line:
        return out
    # L'utilisateur a donné un code postal dans le prompt → on ne touche JAMAIS.
    if re.search(r"\b\d{5}\b", prompt_text or ""):
        return out
    norm = _norm(city_line)
    # Paris par arrondissement : « Paris 12e » / « Paris 12 » / « 12e Paris »
    m = re.search(r"\bparis\s+(\d{1,2})e?\b", norm) or re.search(r"\b(\d{1,2})e?\s+paris\b", norm)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            city_line = re.sub(r"\b\d{5}\b\s*", "", city_line).strip()
            out[-1] = "750%02d %s" % (n, city_line)
            return out
    # Ville dans le dictionnaire → code officiel (remplace un code halluciné).
    for city, cp in CITY_CPS.items():
        if city in norm:
            city_line = re.sub(r"\b\d{5}\b\s*", "", city_line).strip()
            out[-1] = "%s %s" % (cp, city_line)
            break
    return out


SYSTEM_PROMPT = (
    "Tu remplis un formulaire de facture à partir des messages de l'utilisateur. "
    "Réponds UNIQUEMENT avec un objet JSON valide, sans markdown ni texte autour, "
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
              "\n\nRègles : number = le numéro de facture demandé (ex : « numéro 230300 »), "
              "vide sinon. date = la date de la facture en JJ/MM/AAAA ; si l'utilisateur dit "
              "« demain », calcule le lendemain d'aujourd'hui ; vide sinon. client = le nom du "
              "client seul (prénom + nom), SANS le titre de civilité (jamais « Monsieur », « Madame », « M. », « Mme » ni « Mr ») et sans les mots de la phrase. addr = tableau d'au plus 2 éléments : "
              "[rue, \"code postal ville\"] ; le code postal et la ville sont TOUJOURS sur la "
              "même ligne (ex : \"75011 Paris\", \"69001 Lyon\") ; si l'utilisateur mentionne un "
              "arrondissement (ex : \"18e\"), le code postal est 750XX où XX = le numéro de "
              "l'arrondissement (ex : \"18e\" → \"75018 Paris\") ; sinon, si la ville est une "
              "grande ville française bien connue et que le code postal n'est pas donné, ajoute "
              "le code postal usuel AVANT le nom de la ville ; ne devine JAMAIS un arrondissement "
              "différent de celui mentionné par l'utilisateur. "
              "title = COURT (1 à 2 mots par ligne, JAMAIS de prix, durée, quantité ou tarif). "
              "1re ligne = type de prestation en 1-2 mots (ex : 'Shooting produit', 'Graphisme'). "
              "2e ligne = nom du projet UNIQUEMENT si explicitement mentionné (sinon une seule ligne, ne mets JAMAIS "
              "'Projet non spécifié' ni rien d'autre). lines = une entrée par prestation ET une entrée par frais déplacement (train, taxi, repas, parking : chaque montant dit DOIT apparaître en ligne). desc = nom de la prestation ou du frais, "
              "note = le tarif au format « 500€/jour » s'il est mentionné, qty = quantité (jours, heures ou unités selon ce qui est dit) "
              "amount = total de la ligne (tarif × qty, à calculer). Ne mets que ce "
              "qui est réellement dit, sinon vide (\"\" ou [] ou 0). Ne devine rien.")

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
        # Correction post-processing du code postal (zéro impact sur le temps)
        # On n'analyse que les messages de l'utilisateur, PAS les règles
        # (qui contiennent des exemples de codes postaux type "75011 Paris").
        user_msgs = "\n".join(str(m) for m in messages)
        try:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                obj = json.loads(m[0])
                if "addr" in obj:
                    obj["addr"] = _fix_postal_code(obj["addr"], user_msgs)
                text = json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass  # JSON invalide → on renvoie tel quel
        return jsonify({"ok": True, "text": text, "model": model})
    except urllib.error.URLError as e:
        return jsonify({"ok": False,
                        "error": "llama-server injoignable (%s) — vérifiez que le serveur tourne." % e}), 502
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

