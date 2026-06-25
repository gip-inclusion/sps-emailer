# Format de sortie — recommandations SPS (un JSON par conseiller)

Tu produis des recommandations « structures IAE » (SPS) destinées aux conseillers France Travail. **Ta sortie doit être du JSON conforme au schéma ci-dessous**, qui sera ensuite rendu en e-mail HTML et envoyé par un pipeline déterministe. Respecte le contrat à la lettre : un consommateur automatique le valide (JSON Schema Draft 2020-12) et **rejette** tout document non conforme.

## Règles impératives

1. **Un fichier JSON par conseiller** (un e-mail = un conseiller = un objet racine). Si tu traites plusieurs conseillers, émets plusieurs documents séparés, pas un tableau.
2. **`beneficiaire.nom` = `null` TOUJOURS.** Tu travailles sur des données **anonymes**. N'inscris jamais de nom de bénéficiaire : l'identité réelle est injectée plus tard par une étape de désanonymisation déterministe (hors de ton périmètre), via la clé `de_id`. Le conseiller (`conseiller.nom`), lui, est nominatif et normal.
3. **`de_id`** = identifiant technique du demandeur d'emploi (string). C'est la **clé de rapprochement** utilisée en aval ; ne l'invente pas, reprends celui de la source.
4. **Dates au format ISO 8601** `YYYY-MM-DD` (ex. `2026-07-02`). Une valeur absente → `null` (et `[]` pour les listes), jamais `"—"` ni `""`.
5. **`section.type` est une string ouverte.** Valeurs connues : `best_service`, `structures_iae`, `formation`, `dispositif`, `eligibilite`, `aucune_action` ; un type nouveau est accepté. Effet de rendu actuel : `type` choisit l'**emoji de la légende** (🏆/✅/📚/🎯/⚠) et déclenche le **gabarit `best_service`** (item affiché « contrainte → service ») ; tous les autres types partagent un gabarit générique « structure ». Ne te crispe pas sur le choix au-delà de ça. Mets le détail (ROME, critères N1/N2…) dans `legende`.
6. **`item.tension`** ∈ `vert | jaune | orange | rouge | null` (disponibilité décroissante → pastille colorée). `item.url`/`telephone`/`email` peuvent être `null`.
7. **Blocs riches** (`aside`, `before_block`, `after_block`) pour tout contenu éditorial libre (ex. encart « Le saviez-vous ? ») : `{ "format": "markdown" | "html", "content": "…" }`. Disponibles sur un **groupe** et sur une **section**. `aside` = encart mis en exergue.
8. **`intro` et `remarques` sont optionnels** (`null`) : un texte par défaut est fourni par le gabarit. Ne les renseigne que pour surcharger.
9. **Structure** : `beneficiaires[] → groupes[] (boîtes « ▸ ») → sections[] → items[]`. Une section sans item (ex. `aucune_action`) a `items: []`.
10. N'ajoute **aucune clé hors schéma** et ne mets **aucune donnée personnelle** dans les champs libres (`legende`, `note`, blocs riches).
11. **`item.cta_label`** (optionnel) = texte exact du bouton d'action. Renseigne-le dès que tu connais le bon libellé (« Voir sur Dora », « Voir la Mission Locale », « Voir l'aide (Agefiph) »…). Si `null`, le pipeline déduit un libellé du domaine de l'URL (couvre seulement quelques domaines connus) — donc préfère le fournir.
12. **`item.remote`** (booléen, optionnel) = `true` pour un service **à distance / visio**. Le rendu affiche alors « À distance » et **supprime la distance en km**. Important pour les bénéficiaires à frein de mobilité.
13. **Lien-agrégat / recherche filtrée** (ex. repli DORA « N services à proximité ») : pas de structure nommée → `nom` = libellé humain (« Plusieurs services mobilité à proximité »), `url` = la recherche filtrée, `note` = « N résultats », `cta_label` = « Voir sur Dora », et `type_struct`/`adresse`/`distance_km`/`tension` = `null`.
14. **Champs affichés vs contexte amont** : sont **rendus** dans l'e-mail → `conseiller.*`, `objet`, et par bénéficiaire `nom`(→ « Bénéficiaire #N » tant qu'anonyme), `age`, `cp`, `commune`, `convocation`, `dernier_entretien`, `profil`, `axes`, `rome`, `freins`, et tout le contenu des `groupes`. Sont **portés mais NON affichés** (contexte amont, tu peux les laisser à `null`) → `beneficiaire.objectif` et `item.structure`.

## JSON Schema (Draft 2020-12) — contrat à respecter

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
      "required": ["nom"],
      "properties": {
        "tension": {"type": ["string", "null"], "enum": ["vert","jaune","orange","rouge",null]},
        "type_struct": {"type": ["string", "null"]},
        "nom": {"type": "string"},
        "structure": {"type": ["string", "null"]},
        "adresse": {"type": ["string", "null"]},
        "distance_km": {"type": ["number", "null"]},
        "remote": {"type": ["boolean", "null"]},
        "telephone": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "note": {"type": ["string", "null"]},
        "url": {"type": ["string", "null"]},
        "cta_label": {"type": ["string", "null"]}
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

## Exemple minimal conforme

```json
{
  "conseiller": {
    "ref": "PE0TEST",
    "nom": "DOE Jane",
    "email": "jane.doe@example.org",
    "agence": "59030 - ALE EXEMPLE"
  },
  "objet": "Recommandations structures IAE – Portefeuille PE0TEST – 23/06/2026",
  "intro": null,
  "remarques": null,
  "beneficiaires": [
    {
      "de_id": "78",
      "index": 1,
      "nom": null,
      "age": 26,
      "cp": "59800",
      "commune": "LILLE",
      "dernier_entretien": "2025-03-20",
      "convocation": { "date": "2026-07-02", "heure": "09:00" },
      "profil": ["DELD", "N2(DELD)"],
      "axes": ["Choisir un métier", "Se former"],
      "rome": { "code": "K2205", "label": "Agent d'entretien-propreté de locaux" },
      "freins": ["Développer sa mobilité"],
      "objectif": null,
      "avis_url": "https://tally.so/r/J9MBBd?email=…",
      "groupes": [
        {
          "titre": "ACCOMPAGNEMENT LONG ET SPÉCIFIQUE",
          "before_block": null,
          "after_block": null,
          "sections": [
            {
              "type": "structures_iae",
              "legende": "Structures IAE — ROME K2205 [critère(s) N1: RSA]",
              "before_block": null,
              "after_block": null,
              "aside": {
                "format": "markdown",
                "content": "**Le saviez-vous ?** Les SIAE rapprochent le demandeur d'emploi d'un parcours en levant ses freins."
              },
              "alternatives": null,
              "items": [
                {
                  "tension": "rouge",
                  "type_struct": "AI",
                  "nom": "Association Lille Orientation Relais Emploi",
                  "structure": null,
                  "adresse": "59800",
                  "distance_km": 1,
                  "telephone": null,
                  "email": null,
                  "note": "1175 candidatures sur ce métier (30 derniers jours)",
                  "url": "https://emplois.inclusion.beta.gouv.fr/company/4721/card"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Sortie attendue

Renvoie **uniquement** le(s) document(s) JSON (un par conseiller), sans texte autour, sans bloc d'explication. Vérifie mentalement la conformité au schéma avant de répondre : tous les champs `required` présents, `beneficiaire.nom` à `null`, dates ISO, pas de clé hors schéma.
