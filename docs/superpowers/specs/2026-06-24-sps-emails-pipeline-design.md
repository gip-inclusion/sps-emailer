# sps-emails — pipeline JSON → HTML → Brevo

Design validé le 2026-06-24. Remplace le couple `render2.py` / `send.py` / `bin/replace_ids_by_names.sh` par une CLI unifiée (`uv run sps …`) organisée en étapes pures.

## 1. Objectif

Produire et envoyer, par conseiller France Travail, un e-mail HTML de recommandations « structures IAE » à partir de données **anonymes**, en n'injectant les vrais noms de bénéficiaires que par **substitution déterministe** (jamais via un LLM).

## 2. Contrainte cardinale : aucun LLM sur les données sensibles

- Les vrais noms n'existent que dans le CSV réel (`data/Lille.csv`, non versionné) et dans les sorties désanonymisées.
- `deanon`, `render` et `send` sont du **Python déterministe**. Aucun appel LLM dans le pipeline.
- **Discipline d'exécution de l'agent (Claude)** : l'agent peut *exécuter* n'importe quelle étape, car les scripts écrivent le contenu sensible dans des fichiers et n'impriment que des **compteurs** sur stdout (ex. `34 mails, 31 bénéficiaires désanonymisés, 0 ID non résolu`). L'agent ne doit **jamais** faire `Read`/`cat`/`head` sur `out/json-nom/**` ni `out/html/**`. Cette règle est la garantie « le LLM ne lit ni noms ni diagnostics réels ».
- **Débranchement** : la désanonymisation est optionnelle. Sur données anonymes (`nom: null`), `render` affiche `Bénéficiaire #N` (ou un faux nom de maquette). L'agent peut donc générer et envoyer des **tests anonymes** de bout en bout.

## 3. Architecture — pipeline 100 % données

```
.md (amont, format historique)
        │  convert
        ▼
out/json/        JSON anonyme, 1 fichier / conseiller   ← unité métier
        │  deanon  (Python pur + CSV réel)   [optionnel]
        ▼
out/json-nom/    JSON nominatif (sensible, gitignoré)
        │  render
        ▼
out/html/        HTML, 1 fichier / conseiller (sensible si nominatif)
        │  send / schedule
        ▼
API Brevo (transactionnel)
```

Chaque étape est une fonction pure dans son module (`sps/convert.py`, `sps/deanon.py`, `sps/render.py`, `sps/brevo.py`), orchestrée par `sps/__main__.py` (sous-commandes). Le JSON est l'unique format d'échange entre étapes.

**Unité de sortie** : un conseiller = un bloc `POUR :` du MD = un JSON = un HTML = un mail.

## 4. Le JSON (contrat fourni à l'agent amont)

L'agent amont qui génère les recommandations doit produire **un fichier JSON par conseiller**, conforme au schéma ci-dessous. C'est le contrat d'entrée du pipeline ; `convert` (MD→JSON) n'est qu'un adaptateur transitoire tant que l'amont émet encore du MD.

### 4.1 Exemple annoté

```jsonc
{
  "conseiller": {
    "ref": "PE0TEST",                               // identifiant référent FT
    "nom": "DOE Jane",                              // déjà nominatif (pas anonymisé) — exemple fictif
    "email": "jane.doe@example.org",                // destinataire réel du mail
    "agence": "59030 - ALE EXEMPLE"
  },
  "objet": "Recommandations structures IAE – Portefeuille PE0TEST – 23/06/2026",
  // intro + remarques : voir §4.6 — gérées par le TEMPLATE, pas par la donnée
  // (override optionnel possible via "intro"/"remarques" si l'amont veut surcharger)
  "beneficiaires": [
    {
      "de_id": "78",            // CLÉ de désanonymisation (rapprochée à CSV.ID)
      "index": 1,               // numéro d'affichage « Bénéficiaire #1 »
      "nom": null,              // null = anonyme ; rempli par `deanon`
      "age": 26,
      "cp": "59800",
      "commune": "LILLE",
      "dernier_entretien": "2025-03-20",            // ISO 8601, ou null
      "convocation": { "date": "2026-07-02", "heure": "09:00" },  // null si absent
      "profil": ["DELD", "N2(DELD)"],
      "axes": ["Choisir un métier", "Se former"],
      "rome": { "code": "K2205", "label": "Agent d'entretien-propreté de locaux" },
      "freins": ["Développer sa mobilité", "Faire face à des contraintes familiales"],
      "objectif": null,
      "avis_url": "https://tally.so/r/J9MBBd?email=…&agence=…",
      "groupes": [                                  // les boîtes « ▸ … »
        {
          "titre": "ACCOMPAGNEMENT LONG ET SPÉCIFIQUE",
          "before_block": null,                    // bloc riche optionnel — voir §4.5
          "sections": [
            {
              "type": "structures_iae",            // string ouverte — voir §4.3
              "legende": "Structures IAE — ROME K2205 [critère(s) N1: RSA]",
              "before_block": null,                // bloc riche optionnel (§4.5)
              "items": [
                {
                  "tension": "rouge",              // vert|jaune|orange|rouge|null
                  "type_struct": "AI",             // AI|EI|ETTI|ACI|EITI|… ou null
                  "nom": "Association Lille Orientation Relais Emploi",
                  "structure": null,               // org. porteuse si distincte du nom
                  "adresse": "59800",
                  "distance_km": 1,
                  "telephone": null,
                  "email": null,
                  "note": "1175 candidatures sur ce métier (30 derniers jours)",
                  "url": "https://emplois.inclusion.beta.gouv.fr/company/4721/card?…"
                }
              ],
              "aside": {                           // ex-« 💡 Le saviez-vous ? » (§4.5)
                "format": "markdown",
                "content": "**Le saviez-vous ?** Les SIAE ne consistent pas à se former…"
              },
              "alternatives": [ /* mêmes items, sous-titre « Alternatives … » */ ],
              "after_block": null                  // bloc riche optionnel (§4.5)
            }
          ]
        }
      ]
    }
  ]
}
```

### 4.2 Règles de champs

- Dates : **ISO 8601** (`YYYY-MM-DD`). `convert` traduit le `JJ/MM/AAAA` du MD.
- Champ absent / vide (`—` dans le MD) → `null` (ou `[]` pour les listes).
- `nom` : **toujours `null` en sortie de l'amont et de `convert`**. Seul `deanon` le renseigne.
- `distance_km` : nombre ou `null`.
- Les URL conservent les paramètres `mtm_campaign`/`mtm_kwd` tels quels.
- Le `…` de troncature éventuel vient de la source : conservé tel quel.

### 4.3 `section.type` — enum **ouvert** (extensible)

`type` est une **string libre**, pas un enum fermé : de nouveaux types apparaîtront côté amont. Le rendu mappe les valeurs **connues** à un gabarit dédié et **dégrade proprement** toute valeur inconnue vers un gabarit générique (légende grise + `items` standard). Ajouter un type = ajouter une entrée de mapping dans `render`, sans casser l'existant.

Valeurs connues recensées dans `data/recos-*.md` (Lille, Epinay, HLS) :

| `type`            | Origine MD | Rendu |
|-------------------|-----------|-------|
| `best_service`    | 🏆 « Meilleur service (data·inclusion) par contrainte » | items `⚪ Contrainte → Service` ; légende grise |
| `structures_iae`  | ✅ « Structures IAE / les-emplois — ROME … » | items `• [TYPE] Nom \| CP (km)` + pastille de tension |
| `formation`       | 📚 « Accès à la formation (axe …) » | items service/structure/contact |
| `dispositif`      | 🎯 SEVE… | items dispositif |
| `eligibilite`     | ✅ PLIE / EPIDE / E2C / GEIQ / Apprentis d'Auteuil — « Éligible (…) » | structure unique + condition d'éligibilité dans la légende |
| `aucune_action`   | ⚠ « Aucune action recommandée dans un rayon de N km… » | message seul |
| *(inconnu)*       | — | gabarit générique : `legende` + `items` |

Le `convert` choisit le `type` d'après l'emoji + le libellé de tête ; il n'échoue jamais sur un en-tête non reconnu (→ `type` brut + gabarit générique).

Champs transverses d'une section : `type` (string), `legende` (string), `items` (array), `aside` (bloc riche|null, §4.5), `before_block`/`after_block` (bloc riche|null, §4.5), `alternatives` (array|null).

### 4.4 Schéma formel (JSON Schema, à livrer à l'agent amont)

Fichier `docs/schema/email.schema.json` (Draft 2020-12) à produire pendant l'implémentation, dérivé de §4.1–4.6. `type` y est `string` (pas `enum`) avec `examples` listant les valeurs connues. Sert de contrat validable (`jsonschema`) en tête de `render` et `deanon`.

### 4.5 Blocs riches (`aside`, `before_block`, `after_block`)

Pour laisser de la liberté éditoriale (ex-encart « 💡 Le saviez-vous ? », chapô, avertissement), on remplace `saviez_vous` par des **blocs riches** réutilisables :

```jsonc
{ "format": "markdown" | "html", "content": "…" }   // null si absent
```

- `format: "markdown"` → converti en HTML par `render` (lib markdown, output inline-safe pour e-mail).
- `format: "html"` → injecté tel quel (l'amont assume la responsabilité d'un HTML e-mail-safe).
- Emplacements autorisés : sur un **groupe** (`before_block`/`after_block`) et sur une **section** (`before_block`/`aside`/`after_block`). `aside` = encart mis en exergue (style indigo actuel du 💡). `before_block`/`after_block` = contenu libre avant/après le bloc.

### 4.6 Intro & remarques — gérées par le **template**, pas la donnée

L'intro (« Bonjour …, voici les solutions… ») et l'encart « Remarques importantes » (présents dans le 1ᵉʳ format, absents du 2ᵉ) sont du **texte de gabarit** porté par le template de mail, avec interpolation du prénom conseiller / portefeuille. Le JSON peut **surcharger** via des champs optionnels `intro` (string|bloc riche) et `remarques` (array de string|bloc riche) ; en leur absence, le template applique son texte par défaut. Le passage des `•` du MD vers ces remarques est géré par `convert` uniquement pour préserver l'existant.

## 5. Étapes / commandes

Toutes via `uv run sps <cmd>` (paquet `sps`, deps déclarées dans `pyproject.toml`).

| Commande | Entrée | Sortie | LLM-safe à exécuter par l'agent ? |
|----------|--------|--------|-----------------------------------|
| `convert <md> -o out/json/` | MD historique | N JSON anonymes | ✅ (anonyme) |
| `deanon out/json/ --csv data/Lille.csv -o out/json-nom/` | JSON anon + CSV réel | JSON nominatif | ✅ si stdout = compteurs only ; ne pas `Read` la sortie |
| `render <dir-json> -o out/html/` | JSON (anon ou nom) | N HTML | ✅ sur anonyme ; sortie nominative non lue |
| `send <dir-html> [--test]` | HTML | — (appels Brevo) | ✅ `--test` ; envoi réel = action sortante à confirmer |
| `schedule <dir-html> --at <ISO8601> [--test]` | HTML | — (Brevo `scheduledAt`) | idem `send` |

- `--test` : destinataires forcés = `TEST_RECIPIENTS` du `.env`. Sans `--test` : destinataire = `conseiller.email` du JSON correspondant (le HTML embarque ou référence cette adresse).
- Logs : **jamais de nom/diagnostic**, uniquement des compteurs et des IDs techniques.

### 5.1 `deanon` (remplacement par clé, sans LLM)

- Lit le CSV réel, construit la map `ID → "Prénom Nom"` (colonnes du CSV réel : `id; identifiant; nom; prenom; …` — à confirmer sur `Lille.csv`).
- Pour chaque bénéficiaire : `nom = map[de_id]`. Substitution **par clé exacte** (corrige le piège regex du sed actuel où `#4` matche `#41`).
- Compte et signale les `de_id` non résolus (sans les afficher en clair s'ils contiennent du sensible — ici l'ID seul n'est pas sensible).

### 5.2 `render`

- Généralise la logique HTML de `render2.py` (boîtes ▸ principales, pastilles de tension 11px sous le titre, encart `aside`/indigo, CTA bleus par domaine, avis en pied, liens `tel:`/`mailto:`, `@media` mobile, largeur 700px, fond `#e2e8f0`) à : boucle bénéficiaires d'un conseiller, puis boucle conseillers d'un répertoire.
- **Mapping `section.type`** : table type-connu → gabarit, avec fallback générique pour tout type inconnu (§4.3). Aucune valeur de `type` ne fait planter le rendu.
- **Blocs riches** (§4.5) : `markdown` → HTML via une lib markdown (sortie e-mail-safe, styles inline) ; `html` injecté tel quel. Rendus aux emplacements `before_block`/`aside`/`after_block` du groupe et de la section.
- **Intro & remarques** (§4.6) : texte par défaut du template, interpolé (prénom conseiller, portefeuille) ; surchargé par les champs JSON optionnels s'ils existent.
- Si `nom == null` → affichage `Bénéficiaire #N` (+ faux nom de maquette optionnel) ; sinon → vrai nom + initiales calculées.

### 5.3 `send` / `schedule` (Brevo)

- Sender : `BREVO_SENDER` du `.env` (expéditeur/domaine **validé** dans Brevo).
- Objet tiré du JSON (`objet`) ; préfixe `[TEST]` en mode `--test`.
- `schedule` : champ `scheduledAt` (ISO 8601) de `POST /v3/smtp/email`. Horizon limité (~72 h, à vérifier au moment du code) ; supporte un `batchId` pour annulation groupée (`DELETE /v3/smtp/email/{batchId}`).
- **Contrainte IP** : la liste d'IP autorisées Brevo s'applique à **l'appel API** (dépôt du mail), pas à l'envoi différé. Programmer ne contourne pas la restriction au moment de l'appel (401 si IP non listée), **mais** l'envoi réel part des serveurs Brevo → une seule fenêtre « IP autorisée » à la programmation suffit, même machine éteinte ensuite. Alternative : désactiver/élargir la restriction d'IP dans les réglages Brevo si l'IPv6 changeante est trop pénible.

## 6. `.env`

```
BREVO_API_KEY=…
BREVO_SENDER=expediteur-valide@example.org
TEST_RECIPIENTS=test1@example.org,test2@example.org
```

## 7. GUI Mac (phase 2, optionnel — hors périmètre du premier lot)

Idéal évoqué : une petite GUI locale sur Mac. Approche recommandée la plus légère : **mini-serveur web local** (`uv run sps gui` → FastAPI/Flask + une page) qui :
1. liste les fichiers d'`out/`, 2. prévisualise le HTML, 3. déclenche `send --test` / `send` / `schedule`.
Tourne sans installation lourde via `uv`, s'ouvre dans le navigateur. Alternative plus « native » (menu-bar `rumps`) : plus de travail, repoussée. **Non incluse dans le premier lot** ; à spécifier séparément si retenue.

## 7bis. Ordre d'implémentation & dépôt git

1. **Réécrire `CLAUDE.md`** d'après ce design (architecture pipeline, contrat JSON, contrainte « pas de LLM », commandes `uv run sps …`). Les sections « Format d'entrée (parsing) » et « Rendu / envoi » existantes sont remplacées par leurs équivalents JSON/CLI.
2. **Mettre à jour `README.md`** (puis affiné avec le code).
3. **`git init`** seulement **après** 1 et 2, avec un `.gitignore` qui exclut les données sensibles :
   - **`data/`** — contient le CSV réel (`Lille.csv`) **et** les CSV anonymes **et** les `.md` (diagnostics réels) → **non versionné**.
   - **`out/`** — déjà ignoré (JSON anonymes/nominatifs + HTML).
   - Conserver `.env`, `__pycache__/`, `*.pyc`, `.venv/`.
   - Versionner : `sps/` (code), `pyproject.toml`, `docs/`, `CLAUDE.md`, `README.md`, `.gitignore`, `.env.example`.

### Nettoyage des anciens scripts

- `render.py` (vieux format, 1ᵉʳ conseiller seulement) : **jeté** (non porté, non versionné). Sa logique « intro + remarques + sommaire » utile est reprise dans le template (§4.6).
- `render2.py`, `send.py`, `bin/replace_ids_by_names.sh` : remplacés par le paquet `sps/`. **Le nom « render2 » ne survit pas** — le module s'appelle simplement `sps/render.py`. Les anciens fichiers sont supprimés une fois la CLI fonctionnelle.

## 8. Hors périmètre (YAGNI)

- Refonte de `render.py` (vieux gros fichier) : conservé tel quel, non utilisé par la nouvelle CLI.
- Désanonymisation du conseiller (déjà nominatif).
- Tracking ouverture/clic Brevo.
- GUI native (voir §7).

## 9. Risques / points ouverts

- **Layout réel du CSV `Lille.csv`** (positions exactes des colonnes nom/prénom) : à confirmer sur le vrai fichier avant de figer `deanon`.
- **Couverture du parseur `convert`** : le MD a des variantes (PLIE/Apprentis d'Auteuil en ✅ sans `[TYPE]`, sections sans tension, encarts 💡 multi-lignes, blocs `Alternatives`). Le parseur doit être testé sur les 3 fichiers MD présents (Lille, Epinay, HLS).
- **Git non initialisé** : ce repo n'est pas sous git (`.gitignore` prêt). Le commit du spec et des sorties est donc différé ; à décider si on `git init`.
