# sps-emails

Mise en forme HTML d'e-mails de recommandations **« structures IAE »** (SPS — Solutions de Parcours Structurées) à destination des **conseillers France Travail**, et envoi via l'**API Brevo**.

## Contexte métier

IAE = insertion par l'activité économique. Chaque e-mail est adressé à **un conseiller** et liste, **par bénéficiaire** (demandeur d'emploi de son portefeuille convoqué cette semaine), des **solutions de parcours** : structures IAE (les-emplois), formations, dispositifs (EPIDE, PLIE, SEVE), et services data·inclusion par contrainte (mobilité, santé, famille, logement, numérique…). Les recommandations sont auto-générées et doivent être validées en entretien.

⚠️ Les données source contiennent des infos personnelles. Le flux par défaut reste **anonyme** (`Bénéficiaire #N`, `DE #x`) ; les vrais noms ne sont injectés que par `deanon` (substitution déterministe — voir « Contrainte cardinale »).

## Contrainte cardinale

Les vrais noms n'existent que dans le **CSV réel non-anonymisé** (fourni par lot — p. ex. `data/Lille.csv`, c'est un exemple, pas un nom fixe ; non versionné) et les sorties désanonymisées. `deanon`/`render`/`send` sont du Python déterministe : **aucun LLM ne lit noms ni diagnostics réels**. Un agent peut exécuter les scripts (stdout = compteurs only) mais ne doit jamais `Read` `out/json-nom/**` ni `out/html/**`.

## Fichiers

Pipeline `sps/` (CLI `uv run sps …`), une étape par module :
- `sps/deanon.py` — JSON anonyme + CSV réel → JSON nominatif (`out/json-nom/`). **Substitution déterministe par clé `de_id`, aucun LLM.**
- `sps/render.py` + `sps/template.py` — JSON → **un HTML par conseiller** (`out/html/`).
- `sps/brevo.py` — envoi / envoi programmé / annulation via l'API Brevo.
- `sps/schema.py` + `docs/schema/email.schema.json` — contrat JSON (donné à l'agent amont).
- `sps/convert.py` — **adaptateur legacy** MD→JSON, **plus le chemin nominal** (l'entrée attendue est du JSON).
- `data/` — entrées **sensibles, non versionnées**. `out/` — entrées JSON + sorties (gitignoré).
- `.env` — secrets (voir `.env.example`).

## Rendu / envoi

Entrée nominale = **JSON** (un par conseiller, format `docs/schema/email.schema.json`) déposé dans `out/json/`. Procédure pas-à-pas : voir `README.md`. En bref :

```bash
uv sync
uv run sps deanon   out/json/ --csv <le-vrai.csv> -o out/json-nom/   # optionnel (vrais noms)
uv run sps render   out/json-nom/                  -o out/html/      # ou out/json/ pour l'anonyme
# tunnel SOCKS ouvert + BREVO_PROXY exporté (cf. ci-dessous), puis :
uv run sps send     out/html/ --test                                  # comptes de test (.env)
uv run sps send     out/html/                                         # vrais conseillers (e-mail embarqué)
uv run sps schedule out/html/ --at 2026-06-29T07:00:00.000+02:00      # → runId
uv run sps cancel   <runId>                                           # annule un programmé
```

Débranchement : sans `deanon`, `render out/json/` produit des HTML anonymes (`Bénéficiaire #N`) envoyables en test.

## Format d'entrée

Le contrat d'entrée est **JSON** (un fichier par conseiller), défini dans `docs/schema/email.schema.json` et `docs/superpowers/specs/2026-06-24-sps-emails-pipeline-design.md` (§4). Points clés : `section.type` est une **string ouverte** (types inconnus → gabarit générique) ; contenus libres via blocs riches `aside`/`before_block`/`after_block` (`{format: markdown|html, content}`) ; intro + remarques portées par le template. (`sps convert` reste un adaptateur legacy MD→JSON, hors chemin nominal.)

## Design des e-mails

Voici les **principes** (le QUOI). Le COMMENT — couleurs, tailles, structure HTML exacte, espacements — vit dans `sps/render.py` + `sps/template.py`, **qui font foi** : modifier la mise en forme = modifier ces deux modules, pas dupliquer un pixel-spec ici.

- **Lisible desktop ET mobile**, sans dépendre d'une media query (cf. Outlook/Gmail ci-dessous).
- **Anticiper Outlook** comme client cible : table wrapper + styles **100 % inline**, pas de CSS hostile (fl/grid/positionnement), largeur fixe (~700px).
- **Valoriser l'espace vertical sans excès** : assez d'air pour scanner rapidement, mais pas de blancs gratuits.
- **Mobile : éviter les doubles marges horizontales** (gouttière du wrapper + padding interne) → bord à bord propre. ⚠️ Le `<style>`/`@media` du `<head>` est strippé par Gmail mobile : ne pas en dépendre pour la lisibilité de base, c'est un bonus.
- **Hiérarchie visuelle claire** : panneau bénéficiaire > boîte de groupe (`▸`) > nom de structure/contrainte > légende de section discrète.
- **Un panneau par bénéficiaire**, séparés par l'**élévation** (ombre) plutôt que des bordures ; **sommaire** « Accès rapide » avec ancres `#de-N` (dégrade en simple liste là où l'ancre ne saute pas — Gmail/Outlook).
- **Pastille de tension** sous le nom de la structure ; **CTA bleus libellés par domaine** (Dora, Les Emplois, formation, Agefiph…) ; **avis** en pied = lien méta discret, **pas** un CTA solution.
- **Blocs riches** `aside`/`before_block`/`after_block` (markdown/HTML) pour le contenu éditorial libre (ex- « 💡 Le saviez-vous ? »).
- **Liens** : téléphones → `tel:`, e-mails → `mailto:`. **Données échappées** (`esc`) partout, sauf les blocs riches (HTML assumé par l'amont).

## Envoi Brevo

- Sender : variable d'env **`BREVO_SENDER`** (requise, définie dans `.env`) — doit être un expéditeur/domaine **validé** dans Brevo.
- Objet préfixé **`[TEST]`** en mode `--test` (l'objet vient du `<title>`).
- **IP autorisées** : l'IP appelante doit être ajoutée dans Brevo (Réglages > IP autorisées) sinon **401** (IPv6, change selon le réseau).
- Destinataires de test : variable d'env **`TEST_RECIPIENTS`** (liste séparée par des virgules), forcés quand `--test` est passé.
- **Envoi programmé** (`schedule --at <ISO8601>`) : `scheduledAt` met en file côté Brevo ; l'envoi part des serveurs Brevo, pas de votre IP. La restriction d'IP autorisée s'applique à **l'appel API** (401 si IP non listée au moment de programmer), **pas** à l'envoi différé → une seule fenêtre IP autorisée à la programmation suffit. Horizon limité (~72 h, à vérifier). Alternative : élargir/désactiver la restriction d'IP dans Brevo si l'IPv6 change trop. Format `scheduledAt` accepté : `2026-06-29T07:00:00.000+02:00`.
- **Annulation** : pas d'annulation via la **GUI** Brevo → seulement par API (`DELETE /v3/smtp/email/{messageId}`). `schedule` génère un **`runId`** (affiché + loggé dans `out/schedules.jsonl` avec les `messageId`, sans aucune adresse/nom) ; `uv run sps cancel <runId>` supprime tout le lot. ⚠️ l'annulation passe aussi par le tunnel (IP autorisée requise au moment du `cancel`).

### Egress à IP fixe (tunnel SOCKS)

L'IPv6 résidentielle change → on route les appels Brevo via une **box à IP fixe whitelistée**, par un **tunnel SSH SOCKS** (TLS de bout en bout : la box ne voit ni la clé ni le HTML nominatif). **Les coordonnées réelles de la box (hôte, IP, users) ne sont PAS versionnées** : elles vivent dans `.env` (gitignoré) et la mémoire projet privée `sps-brevo-egress-tunnel`. Renseigner dans `.env` : `SPS_TUNNEL_HOST`, `SPS_TUNNEL_USER`.

```bash
ssh -i ~/.ssh/sps-tunnel -D 1080 -N -f "$SPS_TUNNEL_USER@$SPS_TUNNEL_HOST"   # ouvre le SOCKS
BREVO_PROXY=socks5h://127.0.0.1:1080 uv run sps send out/html/ --test         # ou: --via socks5h://127.0.0.1:1080
```
⚠️ Utiliser **`socks5h`** (DNS résolu côté box) — requis pour le `PermitOpen api.brevo.com:443` du tunnel. L'IP de la box est une **IP flexible** (réattachable à une future box).

## À garder en tête

- Le `…` de troncature présent dans certaines lignes vient de la **source**, conservé tel quel.
- Les anciens scripts (`render.py`, `render2.py`, `send.py`, `bin/replace_ids_by_names.sh`) sont remplacés par `sps/` et supprimés.
- Confirmer le layout exact des colonnes nom/prénom du CSV réel (p. ex. `Lille.csv` — un exemple parmi d'autres) avant de figer `deanon` (cf. `sps/deanon.py`).
