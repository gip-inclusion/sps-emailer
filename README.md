# sps-emails

Génération et envoi d'e-mails de recommandations « solutions structurées » (SPS) à des conseillers en insertio socio-pro.

## Pipeline

JSON (1 par conseiller) → `deanon` (optionnel, vrais noms, **sans LLM**) → `render` (HTML) → `send` / `schedule` (Brevo).

## 1. Installation (une fois)

```bash
uv sync
cp .env.example .env      # puis renseigner les variables ci-dessous
```

### Variables d'environnement (`.env`) à remplir

| Variable | Requise | Pour quoi |
|---|---|---|
| `BREVO_API_KEY` | oui (envoi) | clé API Brevo transactionnel |
| `BREVO_SENDER` | oui (envoi) | e-mail expéditeur, **validé** dans Brevo |
| `TEST_RECIPIENTS` | oui pour `--test` | destinataires de test (séparés par virgules) |
| `SPS_TUNNEL_HOST` / `SPS_TUNNEL_USER` | oui (envoi) | box du tunnel SOCKS (egress IP fixe whitelistée Brevo) |
| `BREVO_PROXY` | optionnel | proxy SOCKS (sinon utiliser `--via`) ; le tunnel doit être ouvert |

`convert` / `deanon` / `render` ne nécessitent **aucune** variable (étapes locales) ; elles ne servent qu'à partir de `send` / `schedule` / `cancel`.

## 2. Où mettre les JSON

Un fichier JSON **par conseiller**, au format `docs/schema/email.schema.json`, à déposer dans **`out/json/`** (dossier non versionné).
`nom` des bénéficiaires = `null` (anonyme) ; les vrais noms sont ajoutés à l'étape `deanon`.

## 3. Étapes (ce qu'on tape)

**a. (optionnel) Désanonymiser** — remplit les vrais noms depuis le CSV réel, par clé `de_id`, sans LLM :
```bash
uv run sps deanon out/json/ --csv <chemin/vers/le-vrai.csv> -o out/json-nom/
```
Sauter cette étape = rendu anonyme (« Bénéficiaire #N »), pratique pour tester.

**b. Générer les HTML** (un par conseiller) :
```bash
uv run sps render out/json-nom/ -o out/html/      # ou out/json/ si non désanonymisé
```

**c. Ouvrir le tunnel d'egress** (IP fixe whitelistée Brevo — détails dans CLAUDE.md) :
```bash
ssh -i ~/.ssh/sps-tunnel -D 1080 -N -f "$SPS_TUNNEL_USER@$SPS_TUNNEL_HOST"
export BREVO_PROXY=socks5h://127.0.0.1:1080
```

**d. Envoi de TEST** → vers `TEST_RECIPIENTS`, objet préfixé `[TEST]` :
```bash
uv run sps send out/html/ --test
```

**e. Envoi RÉEL** → destinataire = e-mail conseiller embarqué dans chaque HTML :
```bash
uv run sps send out/html/
```

**f. Envoi PROGRAMMÉ** (Brevo `scheduledAt`) → affiche un `runId` :
```bash
uv run sps schedule out/html/ --at 2026-06-29T07:00:00.000+02:00
```

**g. Annuler un envoi programmé** (par le `runId` affiché, aussi loggé dans `out/schedules.jsonl`) :
```bash
uv run sps cancel <runId>
```

## Données & secrets

- `out/` et `data/` : **non versionnés** (données personnelles) — y déposer JSON, CSV, sorties.
- `.env` : secrets (clé Brevo, expéditeur, destinataires de test, coordonnées du tunnel).
- Contrat JSON : `docs/schema/email.schema.json`.

> `sps convert <md.md> -o <dir>` existe encore (adaptateur **legacy** MD→JSON) mais n'est **plus le chemin nominal** : l'entrée attendue est directement du JSON.
