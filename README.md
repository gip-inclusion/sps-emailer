# sps-emails

Génération et envoi d'e-mails de recommandations « structures IAE » (SPS) aux conseillers France Travail, via l'API Brevo.

## Pipeline

`convert` (MD→JSON anonyme) → `deanon` (JSON+CSV→JSON nominatif, **sans LLM**) → `render` (JSON→HTML) → `send`/`schedule` (Brevo).

## Installation

```bash
uv sync
cp .env.example .env   # puis renseigner BREVO_API_KEY, BREVO_SENDER, TEST_RECIPIENTS
```

## Usage

```bash
uv run sps convert  data/recos-lille-23juin-2026.md -o out/json/
uv run sps deanon   out/json/ --csv data/Lille.csv   -o out/json-nom/
uv run sps render   out/json-nom/                    -o out/html/
uv run sps send     out/html/ --test
uv run sps schedule out/html/ --at 2026-06-29T07:00:00
```

`data/` et `out/` ne sont pas versionnés (données personnelles). Voir `docs/superpowers/specs/` pour la conception et `docs/schema/email.schema.json` pour le contrat JSON.
