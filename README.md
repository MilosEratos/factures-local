# Factures Local

**Un agent IA 100 % local qui transforme une phrase en facture PDF.**

Décrivez votre prestation en langage naturel — *« le client s'appelle Atelier Lumière, 3 jours de graphisme à 500 €/jour, plus 35 € de taxi »* — et l'agent remplit le formulaire, génère la facture PDF fidèle au modèle, et tout reste sur votre machine.

> Projet soumis au [ASUS Agent Computer Challenge](https://www.asus.com/microsite/agent-computer/fr/) — catégorie **High-End**.
> #ASUSAgentComputer #AgenticAI #LocalAI #AgentPC

---

## Pourquoi le local gagne ici

La facturation manipule des **données clients confidentielles** (adresses, montants, RIB). Un agent qui envoie ces données à une API cloud les expose ; un agent local ne les fait jamais quitter la machine. C'est exactement le message de l'Agent Computer :

| Pilier ASUS | Dans ce projet |
|---|---|
| **Contrôle flexible des données** | Les données clients + le RIB restent en local (`data/`, `config.json`). Zéro API cloud, zéro télémétrie. |
| **TCO optimisé** | Le LLM tourne via [llama.cpp](https://github.com/ggml-org/llama.cpp) sur votre GPU : zéro coût par requête, contrairement aux API payantes au token. |
| **Performances sans limites** | Un double-clic pour démarrer, fermer la fenêtre pour arrêter : le serveur vit le temps d'éditer votre facture, pas une seconde de plus. Pas de quota, pas de latence réseau, pas d'interruption du fournisseur. |

## Ce que fait l'agent

1. **Langage naturel → structure** : l'assistant (LLM local via llama.cpp) interprète vos messages et renvoie un objet JSON strict `{number, date, client, addr[], title[], lines[{desc, note, qty, amount}]}` — le modèle est contraint de ne rien inventer.
2. **Structure → PDF fidèle** : le moteur `core/gen.py` (ReportLab) génère une facture page 612×792 pt dont la mise en page est **calibrée au pixel** sur des PDF réels (baselines en points, colonnes, encadré total, RIB).
3. **Cycle complet** : aperçu PNG immédiat (PyMuPDF), téléchargement du PDF, compteur de numéros auto-incrémenté, historique et clients mémorisés dans `data/state.json`.

## Démarrage rapide

### Option 1 : Double-clic (Windows) — recommandé

Aucun prérequis. Le script d'installation détecte votre matériel et télécharge tout ce qu'il faut.

```
1. Cloner le repo (ou télécharger le zip)
2. Double-cliquer sur install.bat   ← une seule fois
3. Double-cliquer sur start.bat     ← à chaque utilisation
```

`install.bat` :
- Installe Python (embarqué, ~10 MB) si absent
- Installe les dépendances (flask, reportlab, PyMuPDF)
- Détecte votre GPU (NVIDIA → CUDA, AMD → Vulkan, sinon CPU)
- Télécharge le bon build de llama.cpp (~200 MB)
- Télécharge le modèle Qwen3.5 4B (~2.6 GB)

Le navigateur s'ouvre automatiquement sur `http://localhost:5000`.

### Option 2 : Manuel

Prérequis : **Python 3.10+** et un GPU (NVIDIA ou AMD) ou CPU.

```bash
git clone https://github.com/MilosEratos/factures-local.git
cd factures-local
pip install -r requirements.txt

# Télécharger llama.cpp (build CUDA, Vulkan ou CPU) :
# https://github.com/ggml-org/llama.cpp/releases → b12716
# Placer dans llama.cpp/

# Télécharger le modèle :
# https://huggingface.co/unsloth/Qwen3.5-4B-GGUF → Qwen3.5-4B-Q4_K_M.gguf
# Placer dans models/

# 1. Lancer le moteur IA (port 8081)
llama.cpp\llama-server.exe -m models\Qwen3.5-4B-Q4_K_M.gguf -ngl 99 --port 8081 --no-webui --reasoning off

# 2. Lancer l'application (port 5000) — dans un autre terminal
python server.py
```

Ouvrez `http://localhost:5000` :
- **Formulaire** → *Générer la facture* → aperçu + téléchargement PDF.
- **Assistant** (panneau de droite) → décrivez la facture en langage naturel → *Générer le formulaire*.

Personnalisation : `config.json` contient l'identité du vendeur (en-tête, RIB, mention TVA, logo, modèle). Remplacez les valeurs de démo par les vôtres.

## Architecture

```
factures-local/
├── install.bat          # installation automatique : Python + dépendances + llama.cpp + modèle
├── start.bat            # double-clic : lance llama-server + Flask + navigateur
├── server.py            # serveur Flask : page web + endpoints (génération, fichiers, état, assistant)
├── config.json          # identité vendeur, RIB, logo, modèle (vos données, vos choix)
├── requirements.txt     # flask, reportlab, PyMuPDF
├── static/              # interface web (index.html, style.css, app.js) — appels fetch, aucune dépendance cloud
├── core/
│   └── gen.py           # moteur PDF : mise en page calibrée au pixel + aperçu PNG (PyMuPDF)
├── llama.cpp/           # moteur IA portable (llama-server.exe + DLLs) — installé par install.bat
├── models/              # modèle GGUF (Qwen3.5 4B Q4_K_M) — installé par install.bat
└── data/                # state.json + PDF générés (gitignored)
```

Flux de données : `app.js` ⇄ `server.py` (HTTP local, port 5000) → `core/gen.py` (PDF/PNG) ; l'assistant appelle `llama-server /v1/chat/completions` **sur la même machine** (port 8081). Rien ne sort du réseau local.

## Moteur IA — llama.cpp

Le modèle **Qwen3.5 4B** (Q4_K_M, 2.6 GB) tourne via `llama-server.exe` en mode API OpenAI. L'option `--reasoning off` désactive le mode « thinking » du modèle : il répond directement en JSON sans phase de raisonnement interne.

Compatible **NVIDIA** (CUDA), **AMD** (Vulkan) et **CPU** (sans GPU).

## Moteur PDF — calibré au pixel

Les positions de `core/gen.py` sont des baselines mesurées en points sur des factures réelles (page 612×792 pt) : en-tête, bloc N°/date/client/adresse, titre centré multi-lignes avec word-wrap, encadré « Coût total » auto-dimensionné, tableau à barre noire (Description / Unités / Coût), lignes avec description en gras + note auto-rétrécie, séparateurs, total, bloc RIB et mention TVA. Le format des montants est celui d'une vraie facture française (entier sans décimales, sinon 2 décimales, espace insécable avant « € »).

## Route

- **v1.0** (ici) — base standalone : serveur + web + moteur PDF + assistant llama.cpp + start.bat.
- **v1.1** — *adaptation au modèle glissé* : déposez un PDF de facture existant, l'agent le lit (PyMuPDF : positions, couleurs, polices ; LLM local : sémantique de chaque bloc) et génère la config du moteur. Vos modèles ne quittent jamais votre machine.
- **v1.2** — TVA : taux par ligne, bloc récap HT / TVA / TTC, pied de page adaptable.

## Licence

MIT — voir [LICENSE](LICENSE).

---

# English summary

**Factures Local is a 100 % local AI agent that turns plain sentences into invoice PDFs.** Describe your work in natural language and the agent fills the form, renders a pixel-calibrated invoice PDF, and keeps every byte on your machine — client data and bank details never leave it.

The LLM runs locally through [llama.cpp](https://github.com/ggml-org/llama.cpp) (Qwen3.5 4B, no cloud API, no per-token cost), the PDF engine is ReportLab with layout constants measured in points against real invoices, and the preview is rendered with PyMuPDF. State (counter, history, clients) lives in a local JSON file.

**One folder, one double-click, zero external dependencies.** Works on NVIDIA (CUDA), AMD (Vulkan), and CPU.

Run it: `install.bat` (once) → `start.bat` (each use) → `http://localhost:5000`.

Submitted to the [ASUS Agent Computer Challenge](https://www.asus.com/microsite/agent-computer/fr/) (High-End category). #ASUSAgentComputer #AgenticAI #LocalAI #AgentPC
