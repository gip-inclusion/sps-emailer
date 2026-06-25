# sps-emails Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad-hoc `render2.py`/`send.py`/`bin/*.sh` scripts with a `uv`-managed `sps` CLI that converts upstream recommendation data to per-conseiller JSON, deanonymizes it deterministically (no LLM), renders one HTML email per conseiller, and sends/schedules via the Brevo API.

**Architecture:** A data-centric pipeline of pure stages — `convert` (MD→anon JSON), `deanon` (anon JSON + real CSV → nominative JSON), `render` (JSON→HTML), `send`/`schedule` (HTML→Brevo). JSON is the single interchange format; one file per conseiller is the unit of work. The "no LLM on sensitive data" guarantee is structural: every stage is deterministic Python that prints only counters, never names.

**Tech Stack:** Python 3.12, `uv` (deps in `pyproject.toml`), `httpx` (Brevo), `markdown` (rich blocks), `jsonschema` (contract validation), `pytest` (TDD). All tests use anonymized/synthetic fixtures only.

**Reference spec:** `docs/superpowers/specs/2026-06-24-sps-emails-pipeline-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | uv project + deps + `sps` console entry point |
| `sps/__init__.py` | package marker |
| `sps/__main__.py` | CLI dispatch (`convert`/`deanon`/`render`/`send`/`schedule`) |
| `sps/schema.py` | load + validate JSON against `docs/schema/email.schema.json` |
| `sps/convert.py` | parse MD → list of per-conseiller dicts |
| `sps/deanon.py` | CSV `ID→name` map + by-key substitution into JSON |
| `sps/render.py` | per-conseiller JSON dict → HTML string (ported from `render2.py`) |
| `sps/template.py` | shared HTML chrome: header, intro, remarques, mobile `@media`, rich-block→HTML |
| `sps/brevo.py` | build Brevo payload, send + schedule |
| `docs/schema/email.schema.json` | JSON Schema (Draft 2020-12) — the upstream contract |
| `tests/fixtures/*.md`, `tests/fixtures/*.csv` | anonymized/synthetic inputs |
| `tests/test_*.py` | pytest per module |

**Sensitive-data discipline (applies to every task):** Tests use only anonymized MD blocks and synthetic CSVs with fake names. Never `Read`/`cat` `out/json-nom/**` or `out/html/**`. Stage stdout is counters only.

---

## Task 1: Rewrite CLAUDE.md to the new architecture

**Files:**
- Modify: `CLAUDE.md` (replace "Fichiers", "Rendu / envoi", "Format d'entrée (parsing)" sections)

- [ ] **Step 1: Rewrite the "Fichiers" section** to describe the `sps/` package and stages instead of `render.py`/`render2.py`/`send.py`. Replace the bullet list with:

```markdown
## Fichiers

Pipeline `sps/` (CLI `uv run sps …`), une étape par module :
- `sps/convert.py` — MD historique → **un JSON anonyme par conseiller** (`out/json/`).
- `sps/deanon.py` — JSON anonyme + CSV réel → JSON nominatif (`out/json-nom/`). **Substitution déterministe par clé `de_id`, aucun LLM.**
- `sps/render.py` + `sps/template.py` — JSON → **un HTML par conseiller** (`out/html/`).
- `sps/brevo.py` — envoi / envoi programmé via l'API Brevo.
- `sps/schema.py` + `docs/schema/email.schema.json` — contrat JSON (donné à l'agent amont).
- `data/` — entrées **sensibles, non versionnées** (CSV réel + anonymes + .md). `out/` — sorties (gitignoré).
- `.env` — secrets (voir `.env.example`).
```

- [ ] **Step 2: Replace "Rendu / envoi"** with the `uv` commands:

```markdown
## Rendu / envoi

```bash
uv sync
uv run sps convert  data/recos-lille-23juin-2026.md -o out/json/
uv run sps deanon   out/json/ --csv data/Lille.csv   -o out/json-nom/   # optionnel
uv run sps render   out/json-nom/                    -o out/html/
uv run sps send     out/html/ --test                 # comptes de test (.env)
uv run sps send     out/html/                         # vrais conseillers
uv run sps schedule out/html/ --at 2026-06-29T07:00:00
```

Débranchement : sans `deanon`, `render out/json/` produit des HTML anonymes (`Bénéficiaire #N`) envoyables en test.
```

- [ ] **Step 3: Replace "Format d'entrée (parsing)"** with a pointer to the JSON contract:

```markdown
## Format d'entrée

Le contrat d'entrée est désormais **JSON** (un fichier par conseiller), défini dans `docs/schema/email.schema.json` et `docs/superpowers/specs/2026-06-24-sps-emails-pipeline-design.md` (§4). `convert` est l'adaptateur transitoire qui produit ce JSON depuis le MD historique. Points clés : `section.type` est une **string ouverte** (types inconnus → gabarit générique) ; contenus libres via blocs riches `aside`/`before_block`/`after_block` (`{format: markdown|html, content}`) ; intro + remarques portées par le template.
```

- [ ] **Step 4: Add the no-LLM constraint** near the top of CLAUDE.md, right after the "Contexte métier" section:

```markdown
## Contrainte cardinale

Les vrais noms n'existent que dans le CSV réel (`data/Lille.csv`, non versionné) et les sorties désanonymisées. `deanon`/`render`/`send` sont du Python déterministe : **aucun LLM ne lit noms ni diagnostics réels**. Un agent peut exécuter les scripts (stdout = compteurs only) mais ne doit jamais `Read` `out/json-nom/**` ni `out/html/**`.
```

- [ ] **Step 5: Update the "À garder en tête" section** — remove the obsolete `render.py`/git lines, since git is initialized in Task 3 and old scripts are dropped in Task 14. Replace the `render.py` bullet and the "Pas encore de dépôt git" bullet with:

```markdown
- Les anciens scripts (`render.py`, `render2.py`, `send.py`, `bin/replace_ids_by_names.sh`) sont remplacés par `sps/` et supprimés.
- Confirmer le layout exact des colonnes nom/prénom de `Lille.csv` avant de figer `deanon` (cf. `sps/deanon.py`).
```

(No commit yet — git is initialized in Task 3.)

---

## Task 2: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write a README** that mirrors CLAUDE.md but for a newcomer. Overwrite `README.md` with:

```markdown
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
```

(No commit yet — git is initialized in Task 3.)

---

## Task 3: Initialize git, gitignore, uv project; first commit

**Files:**
- Modify: `.gitignore`
- Create: `pyproject.toml`, `.env.example`, `sps/__init__.py`

- [ ] **Step 1: Extend `.gitignore`** to exclude sensitive data. Overwrite `.gitignore` with:

```
.env
data/
out/
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 2: Create `pyproject.toml`**:

```toml
[project]
name = "sps-emails"
version = "0.1.0"
description = "Génération et envoi d'e-mails de recommandations IAE (SPS) via Brevo"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "markdown>=3.6",
    "jsonschema>=4.21",
]

[project.scripts]
sps = "sps.__main__:main"

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create `.env.example`**:

```
BREVO_API_KEY=
BREVO_SENDER=expediteur-valide@example.org
TEST_RECIPIENTS=test1@example.org,test2@example.org
```

- [ ] **Step 4: Create `sps/__init__.py`** (empty file).

- [ ] **Step 5: Sync uv and verify it resolves**

Run: `uv sync --extra dev`
Expected: creates `.venv`, `uv.lock`; exit 0.

- [ ] **Step 6: git init + initial commit**

```bash
git init
git add .gitignore pyproject.toml uv.lock .env.example sps/ CLAUDE.md README.md docs/
git commit -m "chore: init sps pipeline project (uv, docs, gitignore)"
```

Expected: commit succeeds; `git status` shows `data/`, `out/`, `.env` untracked/ignored.

---

## Task 4: CLI dispatch skeleton

**Files:**
- Create: `sps/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import subprocess, sys

def run(*args):
    return subprocess.run([sys.executable, "-m", "sps", *args],
                          capture_output=True, text=True)

def test_help_lists_subcommands():
    r = run("--help")
    assert r.returncode == 0
    for cmd in ("convert", "deanon", "render", "send", "schedule"):
        assert cmd in r.stdout

def test_unknown_command_errors():
    r = run("frobnicate")
    assert r.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL (`No module named sps.__main__` / non-zero help).

- [ ] **Step 3: Write minimal implementation**

```python
# sps/__main__.py
import argparse, sys

def main(argv=None):
    parser = argparse.ArgumentParser(prog="sps", description="Pipeline e-mails SPS")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("convert", help="MD historique → JSON anonyme (1/conseiller)")
    p.add_argument("md"); p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("deanon", help="JSON anonyme + CSV réel → JSON nominatif")
    p.add_argument("indir"); p.add_argument("--csv", required=True)
    p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("render", help="JSON → HTML (1/conseiller)")
    p.add_argument("indir"); p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("send", help="Envoi via Brevo")
    p.add_argument("indir"); p.add_argument("--test", action="store_true")

    p = sub.add_parser("schedule", help="Envoi programmé via Brevo (scheduledAt)")
    p.add_argument("indir"); p.add_argument("--at", required=True)
    p.add_argument("--test", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "convert":
        from sps.convert import run_convert
        run_convert(args.md, args.out)
    elif args.cmd == "deanon":
        from sps.deanon import run_deanon
        run_deanon(args.indir, args.csv, args.out)
    elif args.cmd == "render":
        from sps.render import run_render
        run_render(args.indir, args.out)
    elif args.cmd in ("send", "schedule"):
        from sps.brevo import run_send
        run_send(args.indir, test=args.test,
                 scheduled_at=getattr(args, "at", None))

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sps/__main__.py tests/test_cli.py
git commit -m "feat: sps CLI dispatch skeleton"
```

---

## Task 5: JSON Schema + validator

**Files:**
- Create: `docs/schema/email.schema.json`, `sps/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write `docs/schema/email.schema.json`** (Draft 2020-12). `type` is `string` (open), not enum:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SPS conseiller email",
  "type": "object",
  "required": ["conseiller", "objet", "beneficiaires"],
  "properties": {
    "conseiller": {
      "type": "object",
      "required": ["ref", "nom", "email"],
      "properties": {
        "ref": {"type": "string"},
        "nom": {"type": "string"},
        "email": {"type": "string", "format": "email"},
        "agence": {"type": ["string", "null"]}
      }
    },
    "objet": {"type": "string"},
    "intro": {"type": ["string", "null"]},
    "remarques": {"type": ["array", "null"], "items": {"type": "string"}},
    "beneficiaires": {"type": "array", "items": {"$ref": "#/$defs/beneficiaire"}}
  },
  "$defs": {
    "richblock": {
      "type": ["object", "null"],
      "required": ["format", "content"],
      "properties": {
        "format": {"type": "string", "enum": ["markdown", "html"]},
        "content": {"type": "string"}
      }
    },
    "item": {
      "type": "object",
      "required": ["nom", "url"],
      "properties": {
        "tension": {"type": ["string", "null"], "enum": ["vert","jaune","orange","rouge",null]},
        "type_struct": {"type": ["string", "null"]},
        "nom": {"type": "string"},
        "structure": {"type": ["string", "null"]},
        "adresse": {"type": ["string", "null"]},
        "distance_km": {"type": ["number", "null"]},
        "telephone": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "note": {"type": ["string", "null"]},
        "url": {"type": "string"}
      }
    },
    "section": {
      "type": "object",
      "required": ["type", "items"],
      "properties": {
        "type": {"type": "string",
          "examples": ["best_service","structures_iae","formation","dispositif","eligibilite","aucune_action"]},
        "legende": {"type": ["string", "null"]},
        "items": {"type": "array", "items": {"$ref": "#/$defs/item"}},
        "aside": {"$ref": "#/$defs/richblock"},
        "before_block": {"$ref": "#/$defs/richblock"},
        "after_block": {"$ref": "#/$defs/richblock"},
        "alternatives": {"type": ["array", "null"], "items": {"$ref": "#/$defs/item"}}
      }
    },
    "groupe": {
      "type": "object",
      "required": ["titre", "sections"],
      "properties": {
        "titre": {"type": "string"},
        "before_block": {"$ref": "#/$defs/richblock"},
        "after_block": {"$ref": "#/$defs/richblock"},
        "sections": {"type": "array", "items": {"$ref": "#/$defs/section"}}
      }
    },
    "beneficiaire": {
      "type": "object",
      "required": ["de_id", "index", "groupes"],
      "properties": {
        "de_id": {"type": "string"},
        "index": {"type": "integer"},
        "nom": {"type": ["string", "null"]},
        "age": {"type": ["integer", "null"]},
        "cp": {"type": ["string", "null"]},
        "commune": {"type": ["string", "null"]},
        "dernier_entretien": {"type": ["string", "null"]},
        "convocation": {
          "type": ["object", "null"],
          "properties": {"date": {"type": ["string","null"]}, "heure": {"type": ["string","null"]}}
        },
        "profil": {"type": "array", "items": {"type": "string"}},
        "axes": {"type": "array", "items": {"type": "string"}},
        "rome": {"type": ["object", "null"],
          "properties": {"code": {"type": "string"}, "label": {"type": ["string","null"]}}},
        "freins": {"type": "array", "items": {"type": "string"}},
        "objectif": {"type": ["string", "null"]},
        "avis_url": {"type": ["string", "null"]},
        "groupes": {"type": "array", "items": {"$ref": "#/$defs/groupe"}}
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_schema.py
from sps.schema import validate_email

VALID = {
    "conseiller": {"ref": "PE1", "nom": "X Y", "email": "x@francetravail.fr"},
    "objet": "Objet", "beneficiaires": [
        {"de_id": "78", "index": 1, "groupes": []}
    ],
}

def test_valid_passes():
    validate_email(VALID)  # no exception

def test_open_section_type_allowed():
    doc = {**VALID, "beneficiaires": [{"de_id": "1", "index": 1, "groupes": [
        {"titre": "G", "sections": [{"type": "brand_new_type", "items": []}]}]}]}
    validate_email(doc)  # unknown type must NOT raise

def test_missing_required_raises():
    import pytest
    with pytest.raises(Exception):
        validate_email({"objet": "x"})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL (`No module named sps.schema`).

- [ ] **Step 4: Write `sps/schema.py`**

```python
# sps/schema.py
import json
from pathlib import Path
from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "schema" / "email.schema.json"

def _validator():
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))

def validate_email(doc):
    """Raise jsonschema.ValidationError if doc violates the contract."""
    _validator().validate(doc)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_schema.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/schema/email.schema.json sps/schema.py tests/test_schema.py
git commit -m "feat: JSON Schema contract + validator (open section type)"
```

---

## Task 6: convert — header + beneficiary metadata parsing

**Files:**
- Create: `sps/convert.py`
- Test: `tests/test_convert_header.py`, `tests/fixtures/one_block.md`

- [ ] **Step 1: Create the fixture** `tests/fixtures/one_block.md` (anonymized — fake conseiller, no real names):

```
POUR : PE0TEST - DOE Jane
EMAIL : jane.doe@francetravail.fr
======================================================================

Objet : Recommandations structures IAE – Portefeuille PE0TEST – 23/06/2026

Bonjour Jane,

Voici les solutions pour les 1 bénéficiaire(s).

REMARQUES IMPORTANTES :
  • Recommandations automatiques à valider en entretien.
  • Structures < 20 km.

─────────────────────────────────────────────────────────────────
Bénéficiaire #1 | DE #78 | 26 ans | 59800 LILLE | Dernier entretien : 20/03/2025 | Convocation : 02/07/2026 à 09:00
Profil :  DELD · N2(DELD)
Axe :     Choisir un métier · Se former
ROME :    K2205 — Agent d'entretien
Freins :  ⚪ Développer sa mobilité, ⚪ Faire face à des contraintes familiales
Objectif: —
─────────────────────────────────────────────────────────────────

▸ ACCOMPAGNEMENT LONG ET SPÉCIFIQUE

✅ Structures IAE — ROME K2205 (Agent d'entretien) [critère(s) N1: RSA]
   • 🔴 [AI] Assoc Test Emploi | 59800 (1 km)
     1175 candidatures sur ce métier (30 derniers jours)
     → https://emplois.inclusion.beta.gouv.fr/company/4721/card?mtm_campaign=xp-sps
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_convert_header.py
from pathlib import Path
from sps.convert import parse_md

FIX = Path(__file__).parent / "fixtures" / "one_block.md"

def test_parses_one_conseiller():
    docs = parse_md(FIX.read_text(encoding="utf-8"))
    assert len(docs) == 1
    c = docs[0]["conseiller"]
    assert c["ref"] == "PE0TEST"
    assert c["nom"] == "DOE Jane"
    assert c["email"] == "jane.doe@francetravail.fr"
    assert docs[0]["objet"].startswith("Recommandations structures IAE")

def test_parses_beneficiary_meta():
    b = parse_md(FIX.read_text(encoding="utf-8"))[0]["beneficiaires"][0]
    assert b["de_id"] == "78"
    assert b["index"] == 1
    assert b["nom"] is None
    assert b["age"] == 26
    assert b["cp"] == "59800"
    assert b["commune"] == "LILLE"
    assert b["dernier_entretien"] == "2025-03-20"
    assert b["convocation"] == {"date": "2026-07-02", "heure": "09:00"}
    assert b["profil"] == ["DELD", "N2(DELD)"]
    assert b["axes"] == ["Choisir un métier", "Se former"]
    assert b["rome"]["code"] == "K2205"
    assert b["freins"] == ["Développer sa mobilité", "Faire face à des contraintes familiales"]
    assert b["objectif"] is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_convert_header.py -v`
Expected: FAIL (`No module named sps.convert`).

- [ ] **Step 4: Write `sps/convert.py`** (header + meta; sections added in Task 7)

```python
# sps/convert.py
import re

_DASH = "─"

def _iso_date(fr):
    # "20/03/2025" -> "2025-03-20"; returns None for "" / "—"
    fr = fr.strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", fr)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None

def _split_list(value):
    # "A · B" or "A, B" -> ["A", "B"]; "—" -> []
    value = value.strip()
    if value in ("", "—"):
        return []
    parts = re.split(r"\s*·\s*|\s*,\s*", value)
    return [p.strip().lstrip("⚪").strip() for p in parts if p.strip()]

def _none_if_dash(value):
    value = value.strip()
    return None if value in ("", "—") else value

def split_conseiller_blocks(text):
    """Yield raw text per 'POUR :' block."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("POUR :")]
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        yield "\n".join(lines[start:end])

def parse_conseiller_header(block):
    lines = block.splitlines()
    pour = lines[0]
    m = re.match(r"POUR :\s*(\S+)\s*-\s*(.+?)\s*$", pour)
    ref, nom = (m.group(1), m.group(2)) if m else ("", "")
    email = ""
    objet = ""
    for l in lines[1:]:
        if l.startswith("EMAIL :"):
            email = l.split(":", 1)[1].strip()
        elif l.startswith("Objet :"):
            objet = l.split(":", 1)[1].strip()
            break
    return {"ref": ref, "nom": nom, "email": email, "agence": None}, objet

_BENEF_HEADER = re.compile(
    r"Bénéficiaire #(\d+)\s*\|\s*DE #(\S+)\s*\|\s*(\d+)\s*ans\s*\|\s*"
    r"(\d{5})\s+([^|]+?)\s*\|\s*Dernier entretien\s*:\s*([^|]+?)\s*\|\s*"
    r"Convocation\s*:\s*(\d{2}/\d{2}/\d{4})\s*à\s*(\d{2}:\d{2})")

def _parse_meta(meta_lines):
    meta = {"profil": [], "axes": [], "rome": None, "freins": [], "objectif": None}
    for l in meta_lines:
        if l.startswith("Profil"):
            meta["profil"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("Axe"):
            meta["axes"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("ROME"):
            v = _none_if_dash(l.split(":", 1)[1])
            if v and v != "PROJET À DÉFINIR":
                m = re.match(r"([A-Z]\d{4})\s*[—-]\s*(.+)", v)
                meta["rome"] = {"code": m.group(1), "label": m.group(2).strip()} if m \
                    else {"code": v, "label": None}
        elif l.startswith("Freins"):
            meta["freins"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("Objectif"):
            meta["objectif"] = _none_if_dash(l.split(":", 1)[1])
    return meta

def split_beneficiary_blocks(block):
    """Return list of (header_line, meta_lines, body_lines) per beneficiary."""
    lines = block.splitlines()
    # A beneficiary starts at a 'Bénéficiaire #' line (preceded by a ─ rule).
    idxs = [i for i, l in enumerate(lines) if l.lstrip().startswith("Bénéficiaire #")]
    result = []
    for k, start in enumerate(idxs):
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        seg = lines[start:end]
        # meta lines are the contiguous block until the closing ─ rule
        header = seg[0]
        meta, body, in_meta = [], [], True
        for l in seg[1:]:
            if in_meta and l.strip().startswith(_DASH):
                in_meta = False
                continue
            (meta if in_meta else body).append(l)
        result.append((header, meta, body))
    return result

def parse_beneficiary(header, meta_lines, body_lines):
    m = _BENEF_HEADER.search(header)
    b = {
        "de_id": m.group(2), "index": int(m.group(1)), "nom": None,
        "age": int(m.group(3)), "cp": m.group(4), "commune": m.group(5).strip(),
        "dernier_entretien": _iso_date(m.group(6)),
        "convocation": {"date": _iso_date(m.group(7)), "heure": m.group(8)},
        "avis_url": None, "groupes": [],
    }
    b.update(_parse_meta(meta_lines))
    from sps.convert_sections import parse_sections  # Task 7
    b["avis_url"], b["groupes"] = parse_sections(body_lines)
    return b

def parse_md(text):
    docs = []
    for block in split_conseiller_blocks(text):
        conseiller, objet = parse_conseiller_header(block)
        benefs = [parse_beneficiary(h, m, b)
                  for (h, m, b) in split_beneficiary_blocks(block)]
        docs.append({"conseiller": conseiller, "objet": objet,
                     "intro": None, "remarques": None, "beneficiaires": benefs})
    return docs
```

> Note: `parse_beneficiary` imports `parse_sections` from `sps.convert_sections`, created in Task 7. Until then, run only the header/meta tests by stubbing — see Step 5.

- [ ] **Step 5: Create a temporary stub so header tests run in isolation.** Create `sps/convert_sections.py` with a stub returning empty sections (replaced in Task 7):

```python
# sps/convert_sections.py  (stub — full implementation in Task 7)
def parse_sections(body_lines):
    return None, []
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_convert_header.py -v`
Expected: PASS (8 assertions across 2 tests).

- [ ] **Step 7: Commit**

```bash
git add sps/convert.py sps/convert_sections.py tests/test_convert_header.py tests/fixtures/one_block.md
git commit -m "feat: convert MD header + beneficiary metadata parsing"
```

---

## Task 7: convert — sections, items, tension, aside, alternatives

**Files:**
- Modify: `sps/convert_sections.py` (replace stub)
- Test: `tests/test_convert_sections.py`

- [ ] **Step 1: Write the failing test** (uses the same `one_block.md` body plus an aside/alternatives fixture inline):

```python
# tests/test_convert_sections.py
from sps.convert_sections import parse_sections, section_type_for

BODY = """
📋 Donnez votre avis sur les solutions en 1 minute !
   https://tally.so/r/J9MBBd?email=jane%40x

▸ SERVICES D'INSERTION PONCTUELS

🏆 Meilleur service par contrainte (< 10 km)
   ⚪ Mobilité → Aide prothèses auditives
     Agefiph Hauts-de-France | 27BIS Rue, Lille (1 km)
     +33800111009
     → https://www.agefiph.fr/aide?mtm_campaign=xp-sps

▸ ACCOMPAGNEMENT LONG ET SPÉCIFIQUE

✅ Structures IAE — ROME K2205 (Agent) [critère(s) N1: RSA]
   • 🔴 [AI] Assoc Test Emploi | 59800 (1 km)
     1175 candidatures sur ce métier (30 derniers jours)
     → https://emplois.inclusion.beta.gouv.fr/company/4721/card?mtm_campaign=xp-sps

   💡 Le saviez-vous ? Les SIAE ne forment pas
   à un métier précis :
   — elles lèvent les freins.

   Alternatives les moins sollicitées à proximité (< 10 km) :
   • 🟡 [EI] Metal Insertion | 59110 (3 km) — Métallier
     1 candidature sur H2911 (30 jours)
     → https://emplois.inclusion.beta.gouv.fr/company/4929/card?mtm_campaign=xp-sps
""".splitlines()

def test_type_mapping():
    assert section_type_for("✅", "Structures IAE — ROME K2205") == "structures_iae"
    assert section_type_for("✅", "PLIE — Éligible (DELD)") == "eligibilite"
    assert section_type_for("✅", "EPIDE — Éligible") == "eligibilite"
    assert section_type_for("🏆", "Meilleur service") == "best_service"
    assert section_type_for("📚", "Accès à la formation") == "formation"
    assert section_type_for("🎯", "SEVE") == "dispositif"
    assert section_type_for("⚠", "Aucune action") == "aucune_action"
    assert section_type_for("❓", "Nouveau truc") == "❓ Nouveau truc"  # unknown -> raw

def test_parse_sections():
    avis, groupes = parse_sections(BODY)
    assert avis.startswith("https://tally.so/")
    assert [g["titre"] for g in groupes] == [
        "SERVICES D'INSERTION PONCTUELS", "ACCOMPAGNEMENT LONG ET SPÉCIFIQUE"]

    best = groupes[0]["sections"][0]
    assert best["type"] == "best_service"
    assert best["items"][0]["nom"].startswith("Aide prothèses auditives") or \
           best["items"][0]["note"] == "Mobilité"  # contrainte captured

    iae = groupes[1]["sections"][0]
    assert iae["type"] == "structures_iae"
    it = iae["items"][0]
    assert it["tension"] == "rouge"
    assert it["type_struct"] == "AI"
    assert it["nom"] == "Assoc Test Emploi"
    assert it["adresse"] == "59800"
    assert it["distance_km"] == 1
    assert it["url"].startswith("https://emplois.inclusion")
    assert iae["aside"]["format"] == "markdown"
    assert "saviez-vous" in iae["aside"]["content"].lower()
    assert iae["alternatives"][0]["type_struct"] == "EI"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_convert_sections.py -v`
Expected: FAIL (stub returns empty).

- [ ] **Step 3: Replace `sps/convert_sections.py`** with the full parser:

```python
# sps/convert_sections.py
import re

_TENSION = {"🟢": "vert", "🟡": "jaune", "🟠": "orange", "🔴": "rouge"}

def section_type_for(emoji, legende):
    if emoji == "🏆":
        return "best_service"
    if emoji == "📚":
        return "formation"
    if emoji == "🎯":
        return "dispositif"
    if emoji == "⚠":
        return "aucune_action"
    if emoji == "✅":
        if legende.startswith("Structures IAE") or legende.startswith("Structures les-emplois"):
            return "structures_iae"
        return "eligibilite"
    return f"{emoji} {legende}".strip()  # unknown -> raw, generic rendering

_ITEM_IAE = re.compile(
    r"•\s*(?:([🟢🟡🟠🔴])\s*)?(?:\[([^\]]+)\]\s*)?(.+?)\s*\|\s*(.+?)\s*"
    r"(?:\((\d+)\s*km\))?\s*(?:—\s*(.+))?$")

def _emoji_head(line):
    """Return (emoji, rest) if line begins with a known section emoji."""
    for e in ("🏆", "✅", "📚", "🎯", "⚠", "💡", "📋"):
        if line.startswith(e):
            return e, line[len(e):].strip()
    return None, None

def _parse_item(lines, i):
    """Parse one '• …' item starting at lines[i]; return (item, next_i)."""
    m = _ITEM_IAE.search(lines[i].strip())
    item = {"tension": None, "type_struct": None, "nom": None, "structure": None,
            "adresse": None, "distance_km": None, "telephone": None,
            "email": None, "note": None, "url": None}
    if m:
        item["tension"] = _TENSION.get(m.group(1)) if m.group(1) else None
        item["type_struct"] = m.group(2)
        item["nom"] = (m.group(3) or "").strip()
        item["adresse"] = (m.group(4) or "").strip() or None
        item["distance_km"] = int(m.group(5)) if m.group(5) else None
        item["note"] = (m.group(6) or "").strip() or None
    else:
        item["nom"] = lines[i].strip().lstrip("•").strip()
    j = i + 1
    while j < len(lines):
        s = lines[j].strip()
        if s.startswith("→"):
            item["url"] = s[1:].strip()
        elif re.match(r"^(\+33|0)\d", s):
            item["telephone"] = s
        elif re.match(r"^[\w.+-]+@[\w.-]+$", s):
            item["email"] = s
        elif s == "" or s.startswith("•") or s.startswith("⚪") or _emoji_head(lines[j])[0] \
                or s.startswith("▸") or s.startswith("Alternatives"):
            break
        elif item["note"] is None:
            item["note"] = s
        j += 1
    return item, j

def _parse_best_item(lines, i):
    """'⚪ Contrainte → Service' + following detail lines."""
    s = lines[i].strip()
    m = re.match(r"⚪\s*(.+?)\s*→\s*(.+)", s)
    contrainte = m.group(1).strip() if m else None
    service = m.group(2).strip() if m else s.lstrip("⚪").strip()
    item = {"tension": None, "type_struct": None, "nom": service, "structure": None,
            "adresse": None, "distance_km": None, "telephone": None, "email": None,
            "note": contrainte, "url": None}
    j = i + 1
    while j < len(lines):
        t = lines[j].strip()
        if t.startswith("→"):
            item["url"] = t[1:].strip()
        elif re.match(r"^(\+33|0)\d", t):
            item["telephone"] = t
        elif re.match(r"^[\w.+-]+@[\w.-]+$", t):
            item["email"] = t
        elif t == "" or t.startswith("⚪") or t.startswith("▸") or _emoji_head(lines[j])[0]:
            break
        elif "|" in t and item["adresse"] is None:
            item["adresse"] = t
        j += 1
    return item, j

def parse_sections(body_lines):
    avis = None
    groupes = []
    cur_group = None
    cur_section = None
    i = 0
    n = len(body_lines)
    while i < n:
        raw = body_lines[i]
        line = raw.strip()
        if line.startswith("📋"):
            # avis: URL is on the next non-empty line
            j = i + 1
            while j < n and not body_lines[j].strip():
                j += 1
            if j < n:
                avis = body_lines[j].strip()
            i = j + 1
            continue
        if line.startswith("▸"):
            cur_group = {"titre": line[1:].strip(), "before_block": None,
                         "after_block": None, "sections": []}
            groupes.append(cur_group)
            cur_section = None
            i += 1
            continue
        emoji, rest = _emoji_head(line)
        if emoji in ("🏆", "✅", "📚", "🎯", "⚠"):
            cur_section = {"type": section_type_for(emoji, rest), "legende": rest,
                           "items": [], "aside": None, "before_block": None,
                           "after_block": None, "alternatives": None}
            if cur_group is None:  # safety: section before any ▸
                cur_group = {"titre": "", "before_block": None,
                             "after_block": None, "sections": []}
                groupes.append(cur_group)
            cur_group["sections"].append(cur_section)
            i += 1
            continue
        if emoji == "💡" and cur_section is not None:
            # multi-line aside until blank line
            content = [rest]
            j = i + 1
            while j < n and body_lines[j].strip():
                content.append(body_lines[j].strip())
                j += 1
            cur_section["aside"] = {"format": "markdown",
                                    "content": " ".join(content).strip()}
            i = j
            continue
        if line.startswith("Alternatives") and cur_section is not None:
            cur_section["alternatives"] = []
            i += 1
            continue
        if line.startswith("•") and cur_section is not None:
            item, i = _parse_item(body_lines, i)
            (cur_section["alternatives"] if cur_section["alternatives"] is not None
             else cur_section["items"]).append(item)
            continue
        if line.startswith("⚪") and cur_section is not None:
            item, i = _parse_best_item(body_lines, i)
            cur_section["items"].append(item)
            continue
        i += 1
    return avis, groupes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_convert_sections.py tests/test_convert_header.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sps/convert_sections.py tests/test_convert_sections.py
git commit -m "feat: convert sections/items/tension/aside/alternatives (open type)"
```

---

## Task 8: convert — intro/remarques + write per-conseiller JSON; validate against schema; run on real files

**Files:**
- Modify: `sps/convert.py` (add `run_convert`, intro/remarques)
- Test: `tests/test_convert_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_convert_run.py
import json
from pathlib import Path
from sps.convert import parse_md, run_convert
from sps.schema import validate_email

FIX = Path(__file__).parent / "fixtures" / "one_block.md"

def test_intro_and_remarques_extracted():
    doc = parse_md(FIX.read_text(encoding="utf-8"))[0]
    assert doc["intro"].startswith("Bonjour Jane")
    assert any("valider en entretien" in r for r in doc["remarques"])

def test_run_convert_writes_valid_json(tmp_path):
    out = tmp_path / "json"
    run_convert(str(FIX), str(out))
    files = list(out.glob("*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    validate_email(doc)            # conforms to contract
    assert files[0].name == "PE0TEST.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_convert_run.py -v`
Expected: FAIL (`run_convert` missing; intro/remarques None).

- [ ] **Step 3: Add intro/remarques parsing + `run_convert` to `sps/convert.py`.** Add these functions and extend `parse_md`:

```python
# --- append to sps/convert.py ---
import json
from pathlib import Path

def _parse_intro_remarques(block):
    lines = block.splitlines()
    intro_parts, remarques = [], []
    state = None
    for l in lines:
        if l.startswith("Objet :"):
            state = "intro"; continue
        if l.startswith("REMARQUES IMPORTANTES"):
            state = "remarques"; continue
        if l.strip().startswith(_DASH):  # reached first beneficiary rule
            break
        if state == "intro" and l.strip():
            intro_parts.append(l.strip())
        elif state == "remarques":
            s = l.strip().lstrip("•").strip()
            if s:
                remarques.append(s)
    intro = " ".join(intro_parts).strip() or None
    return intro, (remarques or None)

def run_convert(md_path, out_dir):
    text = Path(md_path).read_text(encoding="utf-8")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    docs = parse_md(text)
    written, total_benefs = 0, 0
    for doc in docs:
        ref = doc["conseiller"]["ref"] or f"conseiller-{written+1}"
        (out / f"{ref}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
        total_benefs += len(doc["beneficiaires"])
    print(f"convert: {written} conseiller(s), {total_benefs} bénéficiaire(s) → {out}")
```

Then in `parse_md`, replace the `"intro": None, "remarques": None` line with:

```python
        intro, remarques = _parse_intro_remarques(block)
        docs.append({"conseiller": conseiller, "objet": objet,
                     "intro": intro, "remarques": remarques,
                     "beneficiaires": benefs})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_convert_run.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke-test on the real MD files (counters only, no content printed)**

Run:
```bash
uv run sps convert data/recos-lille-23juin-2026.md  -o out/json-lille/
uv run sps convert data/recos-epinay-24juin-2026.md -o out/json-epinay/
```
Expected: prints e.g. `convert: 34 conseiller(s), N bénéficiaire(s)`; exit 0. **Do not open the output files** (anonymized but out/ is the sensitive sink by convention).

- [ ] **Step 6: Add a guard test that every produced JSON validates** (run against the anonymized Lille output already generated):

```python
# append to tests/test_convert_run.py
import glob, os, pytest

@pytest.mark.skipif(not os.path.isdir("out/json-lille"), reason="run convert first")
def test_all_lille_json_validate():
    files = glob.glob("out/json-lille/*.json")
    assert files
    for f in files:
        validate_email(json.loads(open(f, encoding="utf-8").read()))
```

Run: `uv run pytest tests/test_convert_run.py -v`
Expected: PASS (validation guard green on all real conseiller files).

- [ ] **Step 7: Commit**

```bash
git add sps/convert.py tests/test_convert_run.py
git commit -m "feat: convert intro/remarques + write validated per-conseiller JSON"
```

---

## Task 9: deanon — CSV ID→name map, by-key substitution, counters-only

**Files:**
- Create: `sps/deanon.py`
- Test: `tests/test_deanon.py`, `tests/fixtures/fake_names.csv`

- [ ] **Step 1: Create synthetic CSV fixture** `tests/fixtures/fake_names.csv` (fake names, mimics real layout `id;identifiant;nom;prenom;…`):

```
id;identifiant;nom;prenom;autre
78;X1;DOE;Jane;z
8;X2;ROE;Richard;z
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_deanon.py
import json
from pathlib import Path
from sps.deanon import load_name_map, deanonymize_doc, run_deanon

CSV = Path(__file__).parent / "fixtures" / "fake_names.csv"

def test_load_map():
    m = load_name_map(str(CSV))
    assert m["78"] == "Jane DOE"
    assert m["8"] == "Richard ROE"

def test_by_key_no_prefix_collision():
    # '#4' must never match '#41' — by-key lookup, not regex
    m = {"4": "Aa BB"}
    doc = {"beneficiaires": [{"de_id": "41", "nom": None},
                             {"de_id": "4", "nom": None}]}
    n = deanonymize_doc(doc, m)
    assert doc["beneficiaires"][0]["nom"] is None   # 41 unresolved
    assert doc["beneficiaires"][1]["nom"] == "Aa BB"
    assert n == 1

def test_run_deanon_counts(tmp_path, capsys):
    src = tmp_path / "in"; src.mkdir()
    (src / "PE0TEST.json").write_text(json.dumps(
        {"conseiller": {"ref": "PE0TEST", "nom": "C", "email": "c@x.fr"},
         "objet": "o",
         "beneficiaires": [{"de_id": "78", "index": 1, "nom": None, "groupes": []}]},
        ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    run_deanon(str(src), str(CSV), str(out))
    captured = capsys.readouterr().out
    assert "1 résolu" in captured or "1 b" in captured
    # The agent never reads out content; assert via counters only.
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_deanon.py -v`
Expected: FAIL (`No module named sps.deanon`).

- [ ] **Step 4: Write `sps/deanon.py`**

```python
# sps/deanon.py
import csv, json
from pathlib import Path

def load_name_map(csv_path):
    """Build {ID: 'Prénom NOM'} from the real CSV (cols id;identifiant;nom;prenom;…)."""
    mapping = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        for row in reader:
            if len(row) < 4 or not row[0].strip():
                continue
            _id, nom, prenom = row[0].strip(), row[2].strip(), row[3].strip()
            full = f"{prenom} {nom}".strip()
            if full:
                mapping[_id] = full
    return mapping

def deanonymize_doc(doc, name_map):
    """Fill beneficiary 'nom' by exact de_id key. Return count resolved."""
    resolved = 0
    for b in doc.get("beneficiaires", []):
        name = name_map.get(str(b.get("de_id")))
        if name:
            b["nom"] = name
            resolved += 1
    return resolved

def run_deanon(in_dir, csv_path, out_dir):
    name_map = load_name_map(csv_path)
    src, out = Path(in_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json"))
    total, resolved, unresolved = 0, 0, 0
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        n = deanonymize_doc(doc, name_map)
        total += len(doc.get("beneficiaires", []))
        resolved += n
        unresolved += len(doc.get("beneficiaires", [])) - n
        (out / fp.name).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    # COUNTERS ONLY — never print names.
    print(f"deanon: {len(files)} fichier(s), {resolved} résolu(s), "
          f"{unresolved} non résolu(s) sur {total} bénéficiaire(s) → {out}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_deanon.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sps/deanon.py tests/test_deanon.py tests/fixtures/fake_names.csv
git commit -m "feat: deanon by-key substitution, counters-only output"
```

> **Open item (do not block):** confirm `Lille.csv` real column order (`id;identifiant;nom;prenom`). If different, adjust the indices in `load_name_map` and update the test fixture accordingly.

---

## Task 10: template.py — chrome, rich blocks, type→template mapping

**Files:**
- Create: `sps/template.py`
- Test: `tests/test_template.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_template.py
from sps.template import render_richblock, tension_badge, default_intro

def test_richblock_markdown_to_html():
    html = render_richblock({"format": "markdown", "content": "**Hi** there"})
    assert "<strong>Hi</strong>" in html

def test_richblock_html_passthrough():
    html = render_richblock({"format": "html", "content": "<b>x</b>"})
    assert html == "<b>x</b>"

def test_richblock_none():
    assert render_richblock(None) == ""

def test_tension_badge_colors():
    assert "Service très sollicité" in tension_badge("rouge")
    assert "Places disponibles" in tension_badge("vert")
    assert tension_badge(None) == ""

def test_default_intro_interpolates_first_name():
    assert "Jane" in default_intro({"nom": "DOE Jane", "email": "j@x.fr"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_template.py -v`
Expected: FAIL (`No module named sps.template`).

- [ ] **Step 3: Write `sps/template.py`**

```python
# sps/template.py
import html as _html
import markdown as _md

_TENSION_LABEL = {
    "vert": ("Places disponibles", "#16a34a"),
    "jaune": ("Tension modérée", "#ca8a04"),
    "orange": ("Service sollicité", "#ea580c"),
    "rouge": ("Service très sollicité", "#dc2626"),
}

def render_richblock(block):
    if not block:
        return ""
    if block["format"] == "html":
        return block["content"]
    return _md.markdown(block["content"])

def tension_badge(tension):
    if not tension or tension not in _TENSION_LABEL:
        return ""
    label, color = _TENSION_LABEL[tension]
    return (f'<span style="font-size:11px;color:{color};">● {label}</span>')

def _first_name(nom):
    # "DOE Jane" -> "Jane" (heuristic: last token); "Jane DOE" handled by caller for deanon
    parts = (nom or "").split()
    return parts[-1] if parts else ""

def default_intro(conseiller):
    prenom = _first_name(conseiller.get("nom", ""))
    return (f"Bonjour {prenom},<br><br>Voici les solutions de parcours structurées "
            f"identifiées pour les bénéficiaires de votre portefeuille convoqués "
            f"cette semaine, sur la base de leurs critères d'éligibilité.")

DEFAULT_REMARQUES = [
    "Les recommandations sont établies automatiquement et nécessitent une validation en entretien.",
    "Structures géolocalisées sur le secteur (< 20 km pour l'IAE, < 10 km pour les services).",
]

def esc(s):
    return _html.escape(s or "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_template.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sps/template.py tests/test_template.py
git commit -m "feat: template helpers (rich blocks, tension badges, default intro)"
```

---

## Task 11: render — JSON → HTML, ported from render2.py, multi-conseiller

**Files:**
- Create: `sps/render.py`
- Test: `tests/test_render.py`

> **Porting note:** `render2.py` (still present on disk) holds the HTML/CSS for one beneficiary panel (dark header + initials avatar, blue group boxes `#1e3a8a`, tension badge under titles, `aside` indigo box, blue CTAs by domain, avis footer, `tel:`/`mailto:`, `@media` mobile, 700px width, `#e2e8f0` background). Port that markup, but drive it from the JSON model (`groupes`/`sections`/`items`) instead of re-parsing text. Replace fake-name generation with: real `nom` if present, else `Bénéficiaire #{index}`. Keep all maquette decisions documented in CLAUDE.md.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
import json
from pathlib import Path
from sps.render import render_doc, run_render

DOC = {
    "conseiller": {"ref": "PE0TEST", "nom": "DOE Jane", "email": "jane@x.fr", "agence": "AG"},
    "objet": "Recommandations IAE – PE0TEST",
    "intro": None, "remarques": None,
    "beneficiaires": [{
        "de_id": "78", "index": 1, "nom": None, "age": 26, "cp": "59800",
        "commune": "LILLE", "dernier_entretien": "2025-03-20",
        "convocation": {"date": "2026-07-02", "heure": "09:00"},
        "profil": ["DELD"], "axes": ["Se former"], "rome": {"code": "K2205", "label": "Agent"},
        "freins": [], "objectif": None, "avis_url": "https://tally.so/r/x",
        "groupes": [{"titre": "ACCOMPAGNEMENT LONG", "before_block": None, "after_block": None,
            "sections": [{"type": "structures_iae", "legende": "Structures IAE — K2205",
                "items": [{"tension": "rouge", "type_struct": "AI", "nom": "Assoc Test",
                    "structure": None, "adresse": "59800", "distance_km": 1,
                    "telephone": "+33800111009", "email": None,
                    "note": "1175 candidatures", "url": "https://emplois.inclusion/x"}],
                "aside": {"format": "markdown", "content": "**Le saviez-vous ?** ..."},
                "before_block": None, "after_block": None, "alternatives": None}]}],
    }],
}

def test_render_anonymous_uses_placeholder():
    html = render_doc(DOC)
    assert "Bénéficiaire #1" in html        # nom is None
    assert "Assoc Test" in html
    assert "Service très sollicité" in html
    assert "ACCOMPAGNEMENT LONG" in html
    assert "tel:+33800111009" in html
    assert "Le saviez-vous" in html
    assert "<title>" in html and "Recommandations IAE" in html

def test_render_with_name():
    doc = json.loads(json.dumps(DOC))
    doc["beneficiaires"][0]["nom"] = "Jane DOE"
    html = render_doc(doc)
    assert "Jane DOE" in html
    assert "Bénéficiaire #1" not in html

def test_run_render_writes_one_html_per_conseiller(tmp_path):
    src = tmp_path / "json"; src.mkdir()
    (src / "PE0TEST.json").write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "html"
    run_render(str(src), str(out))
    files = list(out.glob("*.html"))
    assert len(files) == 1 and files[0].name == "PE0TEST.html"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL (`No module named sps.render`).

- [ ] **Step 3: Write `sps/render.py`.** Implement `render_doc(doc)` returning a full HTML string and `run_render(in_dir, out_dir)`. Port the panel/box/CTA markup from `render2.py`, driven by the model. Skeleton with the contract the tests pin:

```python
# sps/render.py
import json
from pathlib import Path
from sps.template import (render_richblock, tension_badge, default_intro,
                          DEFAULT_REMARQUES, esc)

_CTA_BY_DOMAIN = [
    ("emplois.inclusion", "Voir la structure (Les Emplois)"),
    ("dora.inclusion", "Voir le service sur Dora"),
    ("agefiph.fr", "Voir l'aide (Agefiph)"),
    ("societenumerique", "Voir le service"),
]

def _cta_label(url):
    for needle, label in _CTA_BY_DOMAIN:
        if needle in (url or ""):
            return label
    return "Voir la solution"

def _beneficiary_title(b):
    return esc(b["nom"]) if b.get("nom") else f"Bénéficiaire #{b['index']}"

def _render_item(it):
    parts = [f'<div style="font-weight:bold;font-size:16px;color:#000;">'
             f'{esc(it.get("nom"))}</div>']
    badge = tension_badge(it.get("tension"))
    if badge:
        parts.append(f'<div>{badge}</div>')
    if it.get("type_struct"):
        parts.append(f'<div style="font-size:13px;color:#475569;">[{esc(it["type_struct"])}]'
                     f' {esc(it.get("adresse"))}'
                     + (f' ({it["distance_km"]} km)' if it.get("distance_km") is not None else "")
                     + '</div>')
    if it.get("note"):
        parts.append(f'<div style="font-size:13px;color:#64748b;">{esc(it["note"])}</div>')
    if it.get("telephone"):
        parts.append(f'<div><a href="tel:{esc(it["telephone"])}">{esc(it["telephone"])}</a></div>')
    if it.get("email"):
        parts.append(f'<div><a href="mailto:{esc(it["email"])}">{esc(it["email"])}</a></div>')
    if it.get("url"):
        parts.append(f'<a href="{esc(it["url"])}" style="display:inline-block;'
                     f'background:#1e3a8a;color:#fff;padding:8px 14px;border-radius:6px;'
                     f'text-decoration:none;font-size:14px;margin-top:6px;">'
                     f'{esc(_cta_label(it["url"]))}</a>')
    return f'<div style="margin:14px 0;">{"".join(parts)}</div>'

def _render_section(s):
    out = [render_richblock(s.get("before_block"))]
    if s.get("legende"):
        out.append(f'<div style="font-size:13px;color:#64748b;margin:8px 0;">'
                   f'{esc(s["legende"])}</div>')
    out += [_render_item(it) for it in s.get("items", [])]
    if s.get("aside"):
        out.append(f'<div style="background:#eef2ff;border-radius:8px;padding:12px;'
                   f'margin:12px 0;font-size:14px;">{render_richblock(s["aside"])}</div>')
    if s.get("alternatives"):
        out.append('<div style="font-size:13px;color:#64748b;margin-top:8px;">'
                   'Alternatives les moins sollicitées à proximité :</div>')
        out += [_render_item(it) for it in s["alternatives"]]
    out.append(render_richblock(s.get("after_block")))
    return "".join(out)

def _render_group(g):
    body = "".join(_render_section(s) for s in g.get("sections", []))
    return (f'<div style="margin:18px 0;">'
            f'<div style="background:#1e3a8a;color:#fff;font-weight:bold;'
            f'text-transform:uppercase;padding:10px 14px;border-radius:8px 8px 0 0;">'
            f'{esc(g["titre"])}</div>'
            f'<div style="background:#fff;padding:14px;border-radius:0 0 8px 8px;">'
            f'{render_richblock(g.get("before_block"))}{body}'
            f'{render_richblock(g.get("after_block"))}</div></div>')

def _render_beneficiary(b):
    title = _beneficiary_title(b)
    sub = " · ".join(x for x in [f'{b["age"]} ans' if b.get("age") else "",
                                 b.get("commune") or ""] if x)
    conv = b.get("convocation") or {}
    conv_str = f'📅 Convocation : {conv.get("date","")} à {conv.get("heure","")}' \
        if conv.get("date") else ""
    groups = "".join(_render_group(g) for g in b.get("groupes", []))
    avis = (f'<div style="font-size:13px;margin-top:14px;">'
            f'<a href="{esc(b["avis_url"])}" style="color:#334155;">'
            f'Donnez votre avis sur les solutions</a></div>') if b.get("avis_url") else ""
    return (f'<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px '
            f'rgba(0,0,0,0.1);margin:40px 0;overflow:hidden;">'
            f'<div style="background:#0f172a;color:#fff;padding:16px;">'
            f'<div style="font-size:18px;font-weight:bold;">{title}</div>'
            f'<div style="font-size:13px;color:#cbd5e1;">{esc(sub)}</div></div>'
            f'<div style="background:#1e40af;color:#fff;font-size:13px;padding:6px 16px;">'
            f'{esc(conv_str)}</div>'
            f'<div style="padding:16px;">{groups}{avis}</div></div>')

def render_doc(doc):
    c = doc["conseiller"]
    intro = doc.get("intro") or default_intro(c)
    remarques = doc.get("remarques") or DEFAULT_REMARQUES
    rem_html = "".join(f"<li>{esc(r)}</li>" for r in remarques)
    benefs = "".join(_render_beneficiary(b) for b in doc.get("beneficiaires", []))
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(doc["objet"])}</title>
<style>@media (max-width:600px){{.gutter{{padding:0!important}}}}</style></head>
<body style="margin:0;background:#e2e8f0;font-family:Arial,sans-serif;color:#0f172a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td align="center" class="gutter" style="padding:24px;">
<table role="presentation" width="700" style="max-width:700px;width:100%;">
<tr><td style="background:linear-gradient(135deg,#1e3a8a,#1e40af);color:#fff;
padding:24px;border-radius:12px;">
<div style="font-size:20px;font-weight:bold;">{esc(doc["objet"])}</div>
<div style="font-size:13px;color:#cbd5e1;">Portefeuille {esc(c["ref"])}</div></td></tr>
<tr><td style="padding:20px 4px;font-size:15px;">{intro}</td></tr>
<tr><td style="background:#fef3c7;border-radius:8px;padding:14px;font-size:13px;">
<strong>Remarques importantes</strong><ul style="margin:6px 0 0 0;padding-left:18px;">
{rem_html}</ul></td></tr>
<tr><td>{benefs}</td></tr>
</table></td></tr></table></body></html>"""

def run_render(in_dir, out_dir):
    src, out = Path(in_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json"))
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        (out / f'{fp.stem}.html').write_text(render_doc(doc), encoding="utf-8")
    print(f"render: {len(files)} HTML écrit(s) → {out}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 5: Visual smoke-test on anonymized JSON** (agent may open this one — it is anonymized):

```bash
uv run sps render out/json-lille/ -o out/html-anon/
```
Expected: `render: 34 HTML écrit(s)`. Open one `out/html-anon/*.html` in a browser to eyeball the layout against the maquette decisions in CLAUDE.md. (This output is anonymized — `nom` is null — so it is safe to view.)

- [ ] **Step 6: Commit**

```bash
git add sps/render.py tests/test_render.py
git commit -m "feat: render JSON→HTML (ported from render2), multi-conseiller"
```

---

## Task 12: brevo — send (immediate + test mode)

**Files:**
- Create: `sps/brevo.py`
- Test: `tests/test_brevo.py`

- [ ] **Step 1: Write the failing test** (no network — test payload building + recipient selection)

```python
# tests/test_brevo.py
import os
from sps.brevo import build_payload, recipients_for

HTML = "<html><head><title>Recommandations IAE – PE0TEST</title></head><body>x</body></html>"

def test_subject_from_title():
    p = build_payload(HTML, "to@x.fr", sender="elodie@x.fr", test=False)
    assert p["subject"] == "Recommandations IAE – PE0TEST"
    assert p["sender"]["email"] == "elodie@x.fr"
    assert p["to"] == [{"email": "to@x.fr"}]
    assert p["htmlContent"] == HTML
    assert "scheduledAt" not in p

def test_test_mode_prefixes_subject():
    p = build_payload(HTML, "to@x.fr", sender="e@x.fr", test=True)
    assert p["subject"].startswith("[TEST]")

def test_scheduled_at_included():
    p = build_payload(HTML, "to@x.fr", sender="e@x.fr", test=False,
                      scheduled_at="2026-06-29T07:00:00")
    assert p["scheduledAt"] == "2026-06-29T07:00:00"

def test_recipients_test_mode_from_env(monkeypatch):
    monkeypatch.setenv("TEST_RECIPIENTS", "a@x.fr, b@x.fr")
    assert recipients_for("real@ft.fr", test=True) == ["a@x.fr", "b@x.fr"]

def test_recipients_real_mode_uses_conseiller():
    assert recipients_for("real@ft.fr", test=False) == ["real@ft.fr"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_brevo.py -v`
Expected: FAIL (`No module named sps.brevo`).

- [ ] **Step 3: Write `sps/brevo.py`**

```python
# sps/brevo.py
import os, re, json
from pathlib import Path
import httpx

_API = "https://api.brevo.com/v3/smtp/email"

def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return m.group(1).strip() if m else "Recommandations structures IAE"

def _conseiller_email_for(html_path):
    """Sibling JSON not assumed; conseiller email is read from a .meta or the JSON dir.
    Convention: the HTML stem matches the conseiller ref; email comes from out/json*/<ref>.json
    if present, else None (caller must pass --test)."""
    return None  # resolved by run_send via the JSON dir; see below

def recipients_for(conseiller_email, test):
    if test:
        raw = os.environ.get("TEST_RECIPIENTS", "")
        return [e.strip() for e in raw.split(",") if e.strip()]
    return [conseiller_email] if conseiller_email else []

def build_payload(html, to_email, sender, test, scheduled_at=None):
    subject = _title(html)
    if test:
        subject = f"[TEST] {subject}"
    payload = {
        "sender": {"email": sender},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    if scheduled_at:
        payload["scheduledAt"] = scheduled_at
    return payload

def _send_one(client, payload, api_key):
    r = client.post(_API, headers={"api-key": api_key,
                                   "content-type": "application/json"},
                    json=payload)
    r.raise_for_status()
    return r.json()

def run_send(in_dir, test=False, scheduled_at=None):
    api_key = os.environ["BREVO_API_KEY"]
    sender = os.environ["BREVO_SENDER"]
    src = Path(in_dir)
    html_files = sorted(src.glob("*.html"))
    sent, skipped = 0, 0
    with httpx.Client(timeout=30) as client:
        for fp in html_files:
            html = fp.read_text(encoding="utf-8")
            # conseiller email: look for <ref>.json next to JSON outputs is out of scope here;
            # real-send requires the email embedded as a meta comment in the HTML.
            m = re.search(r"<!--\s*to:\s*([^\s>]+)\s*-->", html)
            conseiller_email = m.group(1) if m else None
            for to in recipients_for(conseiller_email, test):
                _send_one(client, build_payload(html, to, sender, test, scheduled_at), api_key)
                sent += 1
            if not recipients_for(conseiller_email, test):
                skipped += 1
    mode = "programmé" if scheduled_at else "immédiat"
    print(f"send ({mode}): {sent} envoi(s), {skipped} ignoré(s)")
```

> **Render dependency:** for real (`--test` absent) sends, the recipient must be embedded in the HTML. **Add to `render_doc` in `sps/render.py`** an HTML comment carrying the conseiller email, right after `<body...>`:
> ```python
> # in render_doc, immediately after the <body ...> tag string:
> f'<!-- to: {esc(c["email"])} -->'
> ```
> Add a render test asserting `f'<!-- to: {c["email"]} -->'` appears in output.

- [ ] **Step 4: Add the recipient-embedding to render + its test**

In `tests/test_render.py` add:

```python
def test_render_embeds_conseiller_email():
    html = render_doc(DOC)
    assert "<!-- to: jane@x.fr -->" in html
```

Update `render_doc` to include the comment after `<body...>` as noted above.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_brevo.py tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sps/brevo.py sps/render.py tests/test_brevo.py tests/test_render.py
git commit -m "feat: brevo send (test+real), recipient embedded in HTML"
```

---

## Task 13: brevo — schedule (scheduledAt) wiring + docs of IP constraint

**Files:**
- Modify: `sps/brevo.py` (already supports `scheduled_at`; add validation)
- Test: `tests/test_brevo.py`

- [ ] **Step 1: Write the failing test** (validate ISO-8601 `--at`)

```python
# append to tests/test_brevo.py
import pytest
from sps.brevo import validate_scheduled_at

def test_valid_iso():
    validate_scheduled_at("2026-06-29T07:00:00")  # no raise

def test_invalid_iso_raises():
    with pytest.raises(ValueError):
        validate_scheduled_at("29-06-2026 7h")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_brevo.py::test_valid_iso -v`
Expected: FAIL (`validate_scheduled_at` undefined).

- [ ] **Step 3: Add `validate_scheduled_at` to `sps/brevo.py` and call it in `run_send`**

```python
# add to sps/brevo.py
from datetime import datetime

def validate_scheduled_at(value):
    """Accept ISO-8601 'YYYY-MM-DDTHH:MM:SS' (Brevo scheduledAt). Raise ValueError otherwise."""
    datetime.fromisoformat(value)  # raises ValueError on bad format
```

And at the top of `run_send`, after computing `scheduled_at`:

```python
    if scheduled_at:
        validate_scheduled_at(scheduled_at)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_brevo.py -v`
Expected: PASS.

- [ ] **Step 5: Document the Brevo IP/scheduling caveat in CLAUDE.md** — append to the "Envoi Brevo" section:

```markdown
- **Envoi programmé** (`schedule --at <ISO8601>`) : `scheduledAt` met en file côté Brevo ; l'envoi part des serveurs Brevo, pas de votre IP. La restriction d'IP autorisée s'applique à **l'appel API** (401 si IP non listée au moment de programmer), **pas** à l'envoi différé → une seule fenêtre IP autorisée à la programmation suffit. Horizon limité (~72 h, à vérifier). Alternative : élargir/désactiver la restriction d'IP dans Brevo si l'IPv6 change trop.
```

- [ ] **Step 6: Commit**

```bash
git add sps/brevo.py tests/test_brevo.py CLAUDE.md
git commit -m "feat: schedule validation + document Brevo IP/scheduling caveat"
```

---

## Task 14: Remove legacy scripts; final cleanup

**Files:**
- Delete: `render.py`, `render2.py`, `send.py`, `bin/replace_ids_by_names.sh`, `block2.txt` (sample now covered by fixtures)

- [ ] **Step 1: Confirm the new CLI fully replaces the old scripts** by running the whole anon pipeline once:

```bash
uv run sps convert data/recos-lille-23juin-2026.md -o out/json-lille/
uv run sps render out/json-lille/ -o out/html-anon/
uv run pytest -q
```
Expected: convert/render counters print; all tests PASS.

- [ ] **Step 2: Delete legacy files**

```bash
git rm render.py render2.py send.py bin/replace_ids_by_names.sh
rm -f bin/.gitkeep 2>/dev/null || true
# block2.txt is untracked sample input; remove from disk:
rm -f block2.txt
```

- [ ] **Step 3: Run the full test suite again**

Run: `uv run pytest -q`
Expected: PASS (no import references to deleted modules).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove legacy render/send scripts, superseded by sps CLI"
```

---

## Self-Review

**Spec coverage:**
- §3 pipeline stages → Tasks 6–8 (convert), 9 (deanon), 11 (render), 12–13 (brevo). ✓
- §2 no-LLM / counters-only → Task 9 (counters), discipline noted in every stage, CLAUDE.md Task 1 Step 4. ✓
- §4 JSON contract (open type, rich blocks, intro/remarques template) → Task 5 (schema), Task 7 (open type + aside/alternatives), Task 8 (intro/remarques), Task 10 (rich blocks). ✓
- §5 commands via `uv run sps` → Task 4 (dispatch). ✓
- §5.3 Brevo send/schedule + IP caveat → Tasks 12–13. ✓
- §6 `.env` → Task 3 (`.env.example`). ✓
- §7bis CLAUDE.md first, README, git init after, gitignore data/, drop legacy, rename render2 → Tasks 1, 2, 3, 14. ✓
- §7 GUI explicitly out of scope → not planned (correct). ✓

**Placeholder scan:** No "TBD"/"add error handling" left. The render porting note points at concrete `render2.py` markup that exists on disk during implementation; the skeleton provided already satisfies all pinned tests, so the port is an enhancement, not a gap. ✓

**Type consistency:** `parse_md`→`run_convert`→JSON keys (`conseiller`, `beneficiaires`, `groupes`, `sections`, `items`, `aside`, `before_block`, `after_block`, `alternatives`) are identical across schema (Task 5), convert (Tasks 6–8), deanon (Task 9), render (Tasks 10–11). `section_type_for`, `parse_sections`, `render_doc`, `run_render`, `build_payload`, `recipients_for`, `validate_scheduled_at`, `load_name_map`, `deanonymize_doc`, `run_deanon` names are used consistently between definition and tests. ✓

**Open items (non-blocking, flagged in tasks):** real `Lille.csv` column order (Task 9); Brevo `scheduledAt` exact horizon (Task 13).
