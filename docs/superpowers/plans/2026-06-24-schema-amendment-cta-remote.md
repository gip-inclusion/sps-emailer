# Schema Amendment Plan — `cta_label`, `remote`, and contract/renderer alignment

> **Status (mis à jour 2026-06-24) : A/B/C appliqués.** `remote` + `cta_label` ajoutés au schéma et au bloc miroir du prompt-doc ; rendu mis à jour (`cta_label`, « À distance ») ; idiome lien-agrégat (C) documenté. **Décision E** : `item.structure` → documenté « contexte amont, non affiché » (pas de rendu). **Réconciliation post-réécriture visuelle** : Mismatch **F est caduc** (le panneau affiche désormais `profil`/`axes`/`rome` + chips de `freins`) ; Mismatch **D a évolué** (`section.type` pilote l'emoji de légende + le gabarit `best_service`, pas « aucun effet »). Les n° de ligne et `_TENSION_LABEL` de ce doc datent d'avant la réécriture du rendu. La couche contrat (schéma + prompt-doc + test schéma) est commitée ; les changements de rendu A/B vivent avec la réécriture visuelle **non encore commitée** (en attente de validation visuelle).

**Date:** 2026-06-24
**Touches:** `docs/schema/email.schema.json`, the mirrored block in `docs/upstream-agent-prompt.md`, `sps/render.py`, `sps/template.py`, `tests/test_schema.py`, `tests/test_render.py`
**Reference:** `docs/superpowers/specs/2026-06-24-sps-emails-pipeline-design.md`, `docs/upstream-agent-prompt.md`

---

## 1. Why this doc exists

The schema (`docs/schema/email.schema.json`) is the **contract handed to the upstream LLM agent** that produces recommendations. We compared it against a real upstream agent's actual JSON output (a recommendation engine: per-référent batches with tension scoring, DI services by constraint, IAE/GEIQ by ROME, DORA fallbacks, N1/N2 eligibility). The question was **not** "are the shapes identical" (they aren't — and shouldn't be) but: **given the project's goal, can the agent express everything the email must display?**

This plan records that comparison's conclusions and the minimal edits they justify.

## 2. The goal — and why most "losses" are intentional

`sps-emails` is a **deterministic render + send pipeline**: agent JSON (one per conseiller) → `deanon` (names by `de_id`) → `render` (one HTML email) → `brevo`. The schema sits at the **email-presentation** layer. Its job is to let the agent say what the conseiller must *see*, not to mirror the agent's analytics.

So the analytics the schema drops are **out of scope by design**, and we explicitly do **not** want to add them:

- **Tension metrics** (score, `candidatures_30j`, `etp_disponibles`, `taux_acceptation`) → the email shows a single coloured pastille (`template.py:_TENSION_LABEL`, lines 4–9) plus an optional free-text rationale in `item.note`. The upstream-agent example already does exactly this: `"note": "1175 candidatures sur ce métier (30 derniers jours)"`. Correct for a presentation contract.
- **`score_qualite`, multi-ROME/`projets`, `contrainte.impact`, N1/N2 booleans** → not displayed, so not in the contract. Eligibility surfaces as text via `section.legende` (e.g. `"… [critère(s) N1: RSA]"`).

**Non-goal:** do not introduce structured tension/quality/eligibility fields. That would turn a presentation contract into a data contract and is not what the pipeline consumes.

## 3. The genuine gaps (where + why)

Reading `sps/render.py` against the agent's real output surfaced three places where the contract **cannot faithfully express something the email needs to show**, plus three places where the **contract misleads the agent** about what renders.

### Gap A — CTA button text is guessed from the URL domain
**Where:** `sps/render.py:_cta_label` (lines 6–17). A 4-needle domain match (`emplois.inclusion`, `dora.inclusion`, `agefiph.fr`, `societenumerique`), else the generic `"Voir la solution"`.
**Why it matters:** The design principle in `CLAUDE.md` is *"CTA bleus libellés par domaine"* — intent is per-domain labels, but the mechanism silently degrades for any new domain (Tally avis link, France Travail, a PLIE/EPIDE/Mission Locale site, an Agefiph subdomain). The agent has the right label in hand and can't pass it.
**Fix:** add optional `item.cta_label`; renderer uses it, falls back to current inference when `null`. Backward-compatible.

### Gap B — "à distance" services render a misleading distance
**Where:** `sps/render.py:_render_item` (lines 36–40) prints `[type_struct] adresse (distance_km km)`.
**Why it matters:** data·inclusion services can be remote/visio (the agent computes `a_distance`). For the **mobility-constrained** DEs this product targets, "à distance" is a feature, not a 0 km. There's no way to render "À distance" instead of a distance.
**Fix:** add optional `item.remote` (boolean). Renderer shows "À distance" when true (and suppresses the `(x km)`).

### Gap C — aggregate/search-link recommendations have no documented idiom
**Where:** Schema `item` (lines 31–46) requires `nom` and models a single named structure. The agent's `services_par_contrainte` also emits **DORA fallbacks** = a count + a filtered search URL (`{type:"dora", dora_count, url}`), not a structure.
**Why it matters:** This already *fits* the schema via nullable fields, but nothing tells the agent how, so it will improvise or fake a structure. The email wants: "Plusieurs services « mobilité » à proximité — Voir sur Dora (12 résultats)".
**Fix:** **documentation only, no schema change.** Pin the idiom: `nom` = human label, `url` = filtered search, `note` = "N résultats", `type_struct`/`adresse`/`distance_km`/`tension` = `null`, `cta_label` = "Voir sur Dora". (Depends on Gap A's `cta_label`.)

### Mismatch D — `section.type` is advisory but documented as if it drives rendering
**Where:** `sps/render.py:_render_section` (lines 56–70) **never reads `s["type"]`**. The upstream prompt (rule 5) implies known types render specially.
**Why it matters:** The agent may agonize over picking the "right" type expecting different layouts; there are none today.
**Fix:** doc clarification — "`type` sert au tri/lecture amont, sans effet de rendu aujourd'hui."

### Mismatch E — `item.structure` is in the contract but never rendered
**Where:** Schema `item.structure` (line 38) vs `_render_item` (lines 30–54), which ignores it.
**Why it matters:** Dead field in the contract. The agent fills it; it vanishes.
**Decision needed:** either render it (under the structure name) or document it as non-rendu. Product call — see §6.

### Mismatch F — bénéficiaire context fields are carried but not displayed
**Where:** Schema `beneficiaire` declares `profil`, `axes`, `rome`, `freins`, `objectif` (lines 86–92). `_render_beneficiary` (lines 82–107) renders only `nom`, `age·commune`, `convocation`, `groupes`, `avis_url`.
**Why it matters:** The agent is told (and the example shows) to fill these, but they never reach the email. Either wasted agent effort, or a missed opportunity: a compact profil-tag row would give the conseiller scannable context (the design's "scan rapide" principle).
**Decision needed:** document as "contexte amont, non affiché" **or** render a profil row. Product call — see §6.

## 4. Net verdict

Against the goal, the schema is **well-fitted**: open `section.type`, nullable structure fields, free-text `note`/`legende`, rich blocks, and a tension enum whose four values map exactly to `compute_tension`'s 🟢🟡🟠🔴. The only true *functional* gaps are **A (`cta_label`)** and **B (`remote`)**; **C** is a doc idiom; **D/E/F** are contract↔renderer drift to document (and optionally act on). Everything analytics-shaped is intentionally and correctly left out.

## 5. Proposed edits (apply together — A & B are inert without the renderer change)

### Schema — `docs/schema/email.schema.json` (and the mirrored block in `docs/upstream-agent-prompt.md`)
Add two optional, additive properties to `$defs.item`:

```jsonc
"item": {
  "type": "object",
  "required": ["nom"],
  "properties": {
    "tension": {"type": ["string", "null"], "enum": ["vert","jaune","orange","rouge",null]},
    "type_struct": {"type": ["string", "null"]},
    "nom": {"type": "string"},
    "structure": {"type": ["string", "null"]},
    "adresse": {"type": ["string", "null"]},
    "distance_km": {"type": ["number", "null"]},
    "remote": {"type": ["boolean", "null"]},        // NEW (Gap B): true → afficher « À distance »
    "telephone": {"type": ["string", "null"]},
    "email": {"type": ["string", "null"]},
    "note": {"type": ["string", "null"]},
    "url": {"type": ["string", "null"]},
    "cta_label": {"type": ["string", "null"]}        // NEW (Gap A): texte du bouton ; null → déduit de l'URL
  }
}
```
> Keep the two copies in sync — the schema is duplicated verbatim in `upstream-agent-prompt.md`.

### Renderer — `sps/render.py`
- `_cta_label`: return `it.get("cta_label") or <current domain inference>`. Change `_render_item` (line ~50) to call `_cta_label(it)` instead of `_cta_label(it["url"])`.
- `_render_item` distance line (lines 36–40): when `it.get("remote")`, render `À distance` instead of `(distance_km km)`.

### Documentation — `docs/upstream-agent-prompt.md`
- New rule: `cta_label` controls button text (optional; null → pipeline infers from URL).
- New rule: `remote: true` for services à distance.
- New idiom (Gap C): how to express an aggregate/search-link item.
- Clarify (Gap D): `section.type` is advisory, no render branching today.
- Clarify (Gap F): which bénéficiaire fields render vs. are contexte amont (pending §6 decision).

### Tests
- `tests/test_schema.py`: a valid doc using `cta_label` + `remote`; confirm omission still validates (additive).
- `tests/test_render.py`: `cta_label` overrides the inferred label; `remote: true` renders "À distance" and suppresses the km.

### Task checklist
- [ ] Add `remote` + `cta_label` to `$defs.item` in `docs/schema/email.schema.json`
- [ ] Mirror the same two properties in the schema block of `docs/upstream-agent-prompt.md`
- [ ] `sps/render.py`: `_cta_label` honours `item.cta_label`; `_render_item` renders `remote`
- [ ] `docs/upstream-agent-prompt.md`: add rules for `cta_label`, `remote`, the aggregate-link idiom, and the `section.type`/bénéficiaire-fields clarifications
- [ ] Tests for both new fields (schema + render)
- [ ] Resolve §6 decisions before touching `item.structure` / profil-row

## 6. Open product decisions (resolve before coding the optional parts)

1. **`item.structure` (Mismatch E):** render it under the structure name, or document as non-rendu and let the agent stop filling it?
2. **Bénéficiaire profil row (Mismatch F):** add a compact `profil`/`freins` tag row to the bénéficiaire panel header (more scannable context), or formally mark those fields "contexte amont, non affiché"?

Both are presentation/product calls, not mechanical fixes — they shouldn't be bundled into the A/B/C/D mechanical pass.

## 7. Explicit non-goals

- No structured tension/quality/eligibility fields. Analytics stay in `note`/`legende` by design.
- No change to `de_id` semantics, the anonymity guarantee, or the one-JSON-per-conseiller rule.
- No new required fields — every amendment is additive and backward-compatible so existing valid documents keep validating.
