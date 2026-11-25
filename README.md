# Factures Local

**Un agent IA 100 % local qui transforme une phrase en facture PDF.**

Décrivez votre prestation en langage naturel — *« le client s'appelle Atelier Lumière, 3 jours de graphisme à 500 €/jour, plus 35 € de taxi »* — et l'agent remplit le formulaire, génère la facture PDF fidèle au modèle, et tout reste sur votre machine.

> Projet soumis au [ASUS Agent Computer Challenge](https://www.asus.com/microsite/agent-computer/fr/) — catégorie **Developer**.
> #ASUSAgentComputer #AgenticAI #LocalAI #AgentPC

---

## Pourquoi le local gagne ici

La facturation manipule des **données clients confidentielles** (adresses, montants, RIB). Un agent qui envoie ces données à une API cloud les expose ; un agent local ne les fait jamais quitter la machine. C'est exactement le message de l'Agent Computer :

| Pilier ASUS | Dans ce projet |
|---|---|
| **Contrôle flexible des données** | Les données clients + le RIB restent en local (`data/`, `config.json`). Zéro API cloud, zéro télémétrie. |
| **TCO optimisé** | Le LLM tourne via [Ollama](https://ollama.com) sur votre GPU : zéro coût par requête, contrairement aux API payantes au token. |
| **Performances sans limites** | Le serveur tourne 24 h/24 sur la machine ; pas de quota, pas de latence réseau, pas d'interruption du fournisseur. |

## Ce que fait l'agent

1. **Langage naturel → structure** : l'assistant (LLM local via Ollama) interprète vos messages et renvoie un objet JSON strict `{number, date, client, addr[], title[], lines[{desc, note, qty, amount}]}` — le modèle est contraint de ne rien inventer.
2. **Structure → PDF fidèle** : le moteur `core/gen.py` (ReportLab) génère une facture page 612×792 pt dont la mise en page est **calibrée au pixel** sur des PDF réels (baselines en points, colonnes, encadré total, RIB).
3. **Cycle complet** : aperçu PNG immédiat (PyMuPDF), téléchargement du PDF, compteur de numéros auto-incrémenté, historique et clients mémorisés dans `data/state.json`.

## Démarrage rapide

Prérequis : **Python 3.10+**, [Ollama](https://ollama.com) installé avec au moins un modèle (recommandé : `gemma4:12b-it-qat` — petit, rapide, très bon en JSON structuré ; tout modèle d'au moins ~8 GB fonctionne). ⚠️ Les modèles « thinking » (gemma4, qwen3…) réservent une partie du budget de tokens à leur raisonnement interne : `max_tokens` doit rester ≥ 2048 dans `config.json`, sinon la réponse arrive vide.

```bash
git clone <ce-repo> factures-local
cd factures-local
pip install -r requirements.txt

ollama pull gemma4:12b-it-qat   # si pas encore installé
python server.py                # → http://localhost:5000
```

Ouvrez `http://localhost:5000` :
- **Formulaire** → *Générer la facture* → aperçu + téléchargement PDF.
- **Assistant** (panneau de droite) → décrivez la facture en langage naturel → *Remplir le formulaire*.

Personnalisation : `config.json` contient l'identité du vendeur (en-tête, RIB, mention TVA, logo, modèle Ollama). Remplacez les valeurs de démo par les vôtres.

## Architecture

```
factures-local/
├── server.py            # serveur Flask : page web + endpoints (génération, fichiers, état, assistant)
├── config.json          # identité vendeur, RIB, logo, modèle Ollama (vos données, vos choix)
├── requirements.txt     # flask, reportlab, PyMuPDF
├── static/              # interface web (index.html, style.css, app.js) — appels fetch, aucune dépendance cloud
├── core/
│   └── gen.py           # moteur PDF : mise en page calibrée au pixel + aperçu PNG (PyMuPDF)
└── data/                # state.json + PDF générés (gitignored)
```

Flux de données : `app.js` ⇄ `server.py` (HTTP local) → `core/gen.py` (PDF/PNG) ; l'assistant appelle `Ollama /api/generate` **sur la même machine** (port 11434). Rien ne sort du réseau local.

## Moteur PDF — calibré au pixel

Les positions de `core/gen.py` sont des baselines mesurées en points sur des factures réelles (page 612×792 pt) : en-tête, bloc N°/date/client/adresse, titre centré multi-lignes, encadré « Coût total » auto-dimensionné, tableau à barre noire (Description / Unités / Coût), lignes avec description en gras + note auto-rétrécie, séparateurs, total, bloc RIB et mention TVA. Le format des montants est celui d'une vraie facture française (entier sans décimales, sinon 2 décimales, espace insécable avant « € »).

## Route

- **v1.0** (ici) — base standalone : serveur + web + moteur PDF nettoyé + assistant Ollama.
- **v1.1** — *adaptation au modèle glissé* : déposez un PDF de facture existant, l'agent le lit (PyMuPDF : positions, couleurs, polices ; LLM local : sémantique de chaque bloc) et génère la config du moteur. Vos modèles ne quittent jamais votre machine.
- **v1.2** — TVA : taux par ligne, bloc récap HT / TVA / TTC, pied de page adaptable.

## Licence

MIT — voir [LICENSE](LICENSE).

---

# English summary

**Factures Local is a 100 % local AI agent that turns plain sentences into invoice PDFs.** Describe your work in natural language and the agent fills the form, renders a pixel-calibrated invoice PDF, and keeps every byte on your machine — client data and bank details never leave it.

The LLM runs locally through [Ollama](https://ollama.com) (no cloud API, no per-token cost, available 24/7), the PDF engine is ReportLab with layout constants measured in points against real invoices, and the preview is rendered with PyMuPDF. State (counter, history, clients) lives in a local JSON file.

Run it: `pip install -r requirements.txt && python server.py` → `http://localhost:5000`.

Submitted to the [ASUS Agent Computer Challenge](https://www.asus.com/microsite/agent-computer/fr/) (Developer category). #ASUSAgentComputer #AgenticAI #LocalAI #AgentPC
