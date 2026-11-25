# Carnet de bord — Factures Local
### Comment une facture est devenue un agent IA local

> Journal du projet, novembre 2026. Écrit pour ceux qui veulent comprendre
> **pourquoi** le projet est conçu ainsi — pas seulement ce qu'il fait.

---

## Page 1 — Le point de départ : « je m'étais lassé de faire ça à la main »

Partons du réel. Pendant des années, chaque facture a suivi le même rituel : rédiger le PDF à la main, le copier sur un deuxième ordinateur pour avoir une sauvegarde, puis rouvrir le livre des comptes et retaper les lignes une par une. Trois fois le même travail, pour un document qui ne change jamais de forme.

À force, la question s'est imposée d'elle-même : **tout ce que je refais à la main, une machine peut le faire — et mieux.** La réponse est devenue ce petit agent spécialisé : vous dictez la facture en une phrase, il rédige le PDF, il l'archive, il porte la ligne dans le livre des comptes. Et parce qu'il tourne *chez vous*, avec son modèle d'IA local, aucune donnée ne quitte la maison.

Ce carnet de bord raconte les décisions qui ont transformé cette irritation quotidienne en produit pour tout le monde — et pourquoi c'est exactement ce qu'une machine « Agent Computer » est censée faire.

---

## Page 2 — Les grandes décisions (et pourquoi)

### 1. Le local d'abord, le cloud ensuite — et jamais sans garde-fous
Un agent IA a besoin d'un cerveau. Deux options : une API cloud (puissante, mais chaque mot part de la machine) ou un modèle local via Ollama (gratuit, privé, disponible 24 h/24).

Nous avons choisi les deux — avec une règle non négociable : **en mode cloud, aucune donnée personnelle ne part**. Concrètement, avant tout envoi externe, chaque valeur sensible (nom, adresse, montant, RIB) est remplacée par un code anonyme (`[[C1]]`, `[[A2]]`…). La table de correspondance reste sur la machine. Le modèle ne voit que la structure d'une facture et des jetons ; au retour, tout est reconstitué localement.

> C'est l'idée centrale du projet : la confidentialité ne doit pas être un mode optionnel, c'est l'architecture.

### 2. Un modèle qui tient dans 6 Go de VRAM
Pour que « Monsieur Tout-le-Monde » puisse s'en servir, le cerveau doit tenir sur une carte graphique courante. Nous avons cherché le modèle le plus léger qui fasse correctement le travail — pas le plus petit possible, et pas le plus gros.

Le verdict de la recherche : **Qwen3.5 4B** (~4 Go). Il score 97,5 % sur les évaluations de « tool calling » 2026 — devant des modèles cinq fois plus lourds. Et sans GPU du tout ? Il tourne aussi en RAM normale, à ~8 tokens/s : une facture met alors une minute au lieu de cinq secondes. Utilisable partout, confortable sur un Agent PC.

> Le message est simple : la même application s'adapte au matériel que vous avez déjà.

### 3. Arrêter de prier le modèle — et le contraindre
Les petits modèles font des erreurs de forme (JSON mal fermé, texte autour du JSON). La solution élégante existe depuis peu : Ollama permet d'imposer un **schéma JSON** au décodeur lui-même — le modèle est *mécaniquement incapable* de sortir un format invalide. La qualité du contenu reste à mesurer (c'est notre benchmark), mais la forme est garantie.

> Détail qui compte : cette fonction n'existe que pour l'inférence **locale**. Le cloud d'Ollama ne la propose pas. Encore un point pour l'Agent PC.

### 4. Ne jamais verrouiller sur « mon » fichier
Le livre des comptes pose une question piège : chacun gère ses comptes dans son propre fichier — Excel local, Google Sheets, autre logiciel. Adapter l'appli à *un* format, c'est l'exclure de tous les autres.

Notre choix : un **format universel propre à l'application** (colonnes simples et stables) + un **mapping configurable** dans les réglages. Chacun relie le format de l'appli à *son* fichier, sans que personne n'ait à changer ses habitudes.

---

## Page 3 — Les problèmes rencontrés en route (le vrai travail)

Un projet local, c'est aussi une série d'obstacles concrets. En voici quatre qui ont façonné le design :

**Le modèle qui « pense » trop.** Notre premier modèle de test était un modèle « reasoning » : avec un budget de 800 tokens, la réponse arrivait *vide* — tout le budget partait dans son raisonnement interne, invisible. Augmenter à 2048 tokens a fait apparaître un JSON parfait. Leçon : les modèles ne sont pas interchangeables ; il faut connaître leurs mécanismes internes avant de les brancher.

**L'encodage qui mange les accents.** Sur Windows, l'entrée standard du terminal n'est pas en UTF-8 : « Lumière » devenait « LumiA re » dans les noms de fichiers. Un correctif d'une ligne, mais invisible tant qu'on ne teste pas avec de vrais noms français.

**Le benchmark honnête.** Les classements publics ne disent pas tout : un modèle n°1 sur un leaderboard peut faire 15 % chez vous, selon le serveur et le format de sortie. Notre règle : **on ne croit qu'un modèle testé dans *notre* pipeline exact**, avec *nos* prompts français. D'où le script de benchmark dédié, qui mesure la complétude des champs sur des factures réalistes (avec accents, « demain », calculs tarif × quantité).

**La machine de test.** Tester de gros modèles sur la machine de travail, c'est la paralyser pendant les tests. Solution : une seconde machine dédiée (GTX Titan 12 Go) joignable en réseau — l'application elle-même ne change rien, seul l'hôte du modèle bouge. C'est aussi ça, le local : l'IA est un service de la maison, pas un locataire dans votre PC principal.

*Note : tout ce logiciel a été développé et testé en local, sur une carte ASUS TUF Gaming RTX 4090.*

---

## Page 4 — Où on va (et ce que ça raconte sur le local)

**La route du produit :**
1. **v1.0** — base standalone : serveur, interface, moteur PDF calibré au pixel, assistant local. ✅
2. **Configuration en 5 minutes** — à la première ouverture, un assistant de configuration : identité, SIRET, TVA, logo glisser-déposer, choix du dossier de sortie, choix du moteur (local ou clé API).
3. **Le modèle glissé** — on dépose *n'importe quel* PDF de facture existant ; l'agent le lit (positions, couleurs, polices) et reproduit ce modèle. Votre charte graphique ne quitte jamais votre machine.
4. **TVA complète** — taux par ligne, récapitulatif HT/TVA/TTC.
5. **Livre des comptes** — format universel + mapping vers le fichier de chacun.

**Et au-delà — un modèle qui apprend le métier.** La tâche « comprendre une phrase et remplir une facture » est étroite. On peut donc *enseigner* cette tâche à un petit modèle : un modèle généraliste génère d'abord des milliers d'exemples (c'est la distillation), puis un fine-tuning QLoRA spécialise un 4B sur ces exemples — avec, dans la littérature récente, des gains mesurables d'exactitude par champ et un modèle final plus rapide qui tient dans encore moins de mémoire. Deux cerveaux au lieu d'un : le généraliste pour la configuration, le spécialiste pour la facture au quotidien. C'est la prochaine étape du projet, hors de ce concours — mais c'est elle qui montre où va le local : **des IA qui apprennent votre métier, chez vous.**

**Et un horizon qui n'est pas de la spéculation.** La France impose la facturation électronique : depuis le 1er septembre 2026, toute entreprise doit *recevoir* des factures électroniques via une plateforme agréée ; au **1er septembre 2027**, les TPE, PME et micro-entreprises devront aussi les *émettre*. Des millions de petites entreprises et d'indépendants vont donc devoir changer d'outil dans les dix-huit mois qui viennent — et la plupart des logiciels qui arrivent sont pensés pour les comptables, pas pour la personne qui veut juste être rapide, chez elle, sans que ses données partent nulle part.

C'est là que ce projet prend un autre sens : **un agent de facturation local pourrait devenir l'un de ces logiciels de référence** — plus intelligent que les autres (il comprend une phrase, il retrouve votre modèle, il tient le livre des comptes), plus rapide (l'IA tourne sur la machine, pas dans un data center), et plus privé (rien ne quitte la maison). La route vers une agrément officiel est longue et réglementaire ; l'idée n'est pas de la courir en dix-sept jours, mais de montrer qu'elle existe — et qu'une machine « Agent » est le bon terrain pour la parcourir.

Une facture, c'est un document banal. Un agent qui la fabrique chez vous, dans votre langue, avec votre modèle, sans rien envoyer nulle part — c'est ce qu'une machine « Agent » change au quotidien. Et en 2027, ce ne sera plus une option : ce sera l'usage.

*Un logiciel qui tourne en local — développé en local.*

---

*Projet soumis à l'ASUS Agent Computer Challenge — catégorie Developer.*
*\#ASUSAgentComputer \#AgenticAI \#LocalAI \#AgentPC*
