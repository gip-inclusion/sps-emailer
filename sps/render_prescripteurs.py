"""Rendu des e-mails « Alerte fins de contrats IAE » (schéma docs/schema/alerte-contrats.schema.json).

Modèle centré **structure** : les `groupes` (une structure IAE chacun) sont au niveau du
document, chaque section regroupe des contrats arrivant à échéance. Renderer distinct du
moteur SPS (render.py, centré bénéficiaire) — aucun couplage, styles inline Outlook-safe.

Architecture de l'information
-----------------------------
1. Titre + intro, puis **repère chiffré Dares** (placement volontaire : juste sous l'intro).
2. **Résumé** : N contrats · N structures · fenêtre de dates.
3. **Sommaire** ancré dès 3 structures (structure · nombre · échéance la plus proche).
4. Une section par structure : nom, coordonnées, phrase de contexte, **tableau de contrats**
   (échéance · candidature · accompagnement) trié par échéance. Le mot « Candidature » porte
   le lien — pas de bouton par ligne.
5. « Le saviez-vous ? » reste **au contact du premier tableau** (placement volontaire).
6. Pied : avis, mentions.

Variantes de mise en forme (paramètre `variant`) — même IA, habillage différent :
    filets   séparation par filets horizontaux, fond blanc (défaut)
    zebre    filets + lignes de tableau alternées
    blocs    une carte blanche par structure sur fond bleu très clair
    bandes   sections pleine largeur alternées blanc / bleu très clair
    echeance IA alternative : regroupement **par échéance** (semaine), structure en colonne

Charte La Plateforme de l'inclusion : bleu France #000091, accent orange #e57200, Arial.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path
import markdown as _md
from sps.template import esc

# --- palette La Plateforme de l'inclusion ---
_BLUE = "#000091"    # bleu France : titres de structure, liens
_ORANGE = "#e57200"  # accent : titre de l'e-mail, chiffre mis en avant
_INK = "#161616"     # texte courant
_MUTE = "#666666"    # texte secondaire (méta, légendes de colonnes)
_RULE = "#dddddd"    # filets de séparation
_TINT = "#f0f5fb"    # fond bleu très clair (blocs, bandes, zébrures)
_FONT = "Arial, Helvetica, sans-serif"

_W = 640      # largeur du bloc central
_R_SM = "4px"  # arrondi des blocs (Outlook l'ignore : angles droits, dégradation propre)
_R_XS = "2px"  # arrondi des petits éléments (bouton)

# Logo La Plateforme de l'inclusion (image hébergée)
_LOGO_URL = "https://img.mailinblue.com/3949075/images/content_library/original/680e18d8b0af2987e384efae.png"

# Encart avis. L'URL contient le tag de fusion Brevo {{ params.EMAIL }} (substitué à l'envoi
# via le champ `params` de l'API — fonctionne même si le destinataire n'est pas un contact Brevo).
# Inséré littéralement, jamais échappé.
_AVIS_URL = "https://tally.so/r/Y5Bkrv?email={{ params.EMAIL }}"

_SAVIEZ_VOUS = (
    "À partir de la candidature, vous pouvez retrouver les contrats déclarés à "
    "l’Agence de services et de paiement : cliquez sur « Afficher le PASS IAE » puis "
    "« Suivi des contrats IAE »."
)

_DARES_URL = ("https://dares.travail-emploi.gouv.fr/publication/quelle-situation-"
              "professionnelle-apres-un-parcours-en-insertion-par-lactivite")

# La source parle encore d'un bouton « Voir la candidature » qui n'existe plus : le lien est
# désormais porté par le mot « Candidature » dans le tableau. Corrigé au rendu pour que les
# mentions décrivent l'e-mail réellement envoyé (l'amont peut rattraper le texte plus tard).
_REMARQUE_OBSOLETE = re.compile(
    r"Cliquez sur\s*[«\"']?\s*Voir la candidature\s*[»\"']?\s*pour acc[ée]der",
    re.I)
_REMARQUE_CORRIGEE = "Cliquez sur « Candidature » pour accéder"

_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"]
_JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]

# e-mail nu (hors attribut/mailto déjà posé) → mailto cliquable dans les blocs riches
_EMAIL_RE = re.compile(r'(?<![\w.@+"=>-])([\w.+-]+@[\w-]+\.[\w.-]+\w)')
# téléphone FR national (« 04 72 76 94 00 ») ou international (« +33 3 74 64 26 90 ») → tel:
_TEL_RE = re.compile(r'(?<![\d>+])(\+33[ .]?\d(?:[ .]?\d\d){4}|0\d(?:[ .]?\d\d){4})(?!\d)')

# « Fin de contrat : 14/08/2026 » → date (tri + rendu)
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
# « Candidat orienté par REITH Marion » → prescripteur
_PRESC_RE = re.compile(r"orient[ée]?e?\s+par\s+(.+)$", re.I)


# --- variantes d'habillage ----------------------------------------------------------
# page      fond de page
# card      fond d'une section structure (None = transparent)
# alt       fond d'une section structure sur deux (None = pas d'alternance)
# gap       espace vertical entre structures (px)
# pad       marge interne d'une section structure (px) — 0 = pleine largeur du bloc
# rule      filet de séparation entre structures
# zebra     fond d'une ligne de tableau sur deux (None = pas de zébrure)
# bar       fond du bandeau de titre d'un bloc (None = pas de bandeau)
# border    filet de contour d'un bloc (None = pas de contour)
# inset     retrait horizontal du texte **porté par les cellules**, pas par le conteneur :
#           les fonds (zébrure, bandeau) touchent ainsi les bords du bloc qui les contient
_VARIANTS = {
    "filets": dict(page="#ffffff", card=None, alt=None, gap=0, pad=0, rule=True, zebra=None,
                   inset=0),
    "zebre":  dict(page="#ffffff", card=None, alt=None, gap=0, pad=0, rule=True, zebra=_TINT,
                   inset=0),
    "blocs":  dict(page=_TINT, card="#ffffff", alt=None, gap=16, pad=24, rule=False, zebra=None,
                   inset=24),
    "bandes": dict(page="#ffffff", card="#ffffff", alt=_TINT, gap=0, pad=20, rule=False,
                   zebra=None, inset=20),
    "echeance": dict(page="#ffffff", card=None, alt=None, gap=0, pad=0, rule=True, zebra=_TINT,
                     inset=0),
    # « best of » : lisibilité graphique de la v0 (bandeau bleu plein par bloc) posée sur
    # l'IA de la v2 (résumé, sommaire, dates lisibles, tri par urgence). En-tête de l'e-mail
    # sur fond blanc, sans encadré — seuls les blocs de contenu sont matérialisés.
    "cartes-siae": dict(page="#ffffff", card="#ffffff", alt=None, gap=18, pad=0,
                        rule=False, zebra=_TINT, bar=_BLUE, border="#dfe3ea", inset=20),
    "cartes-echeance": dict(page="#ffffff", card="#ffffff", alt=None, gap=18, pad=0,
                            rule=False, zebra=_TINT, bar=_BLUE, border="#dfe3ea", inset=20),
}
DEFAULT_VARIANT = "cartes-siae"


# --- typographie française ----------------------------------------------------------

def _typo_html(html):
    """Espaces insécables avant : ; ! ? » et après « — appliqué aux seuls nœuds texte.

    Corrige les retours à la ligne fautifs (« … de l’ASP \\n : cliquez … »).
    """
    parts = re.split(r"(<[^>]+>)", html)
    skip = False  # contenu de <style>/<script> : c'est du code, pas de la typographie
    for i, p in enumerate(parts):
        if p.startswith("<"):
            m = re.match(r"</?([a-zA-Z]+)", p)
            if m and m.group(1).lower() in ("style", "script"):
                skip = not p.startswith("</")
            continue
        if skip:
            continue
        p = re.sub(r"[ \t]+([:;!?»])", r"&nbsp;\1", p)
        p = re.sub(r"(«)[ \t]+", r"\1&nbsp;", p)
        parts[i] = p
    return "".join(parts)


def _nowrap(s):
    """Empêche la coupure d'un nom propre entre prénom et patronyme.

    Utile en colonnes (desktop) ; nuisible empilé, où un nom long déborderait du bloc au
    lieu de passer à la ligne — la media query relâche `.nw` sous 520px.
    """
    return f'<span class="nw" style="white-space:nowrap;">{s}</span>'


def _fmt_date(d, with_year=False, weekday=True):
    """14/08/2026 → « ven. 14 août » (année seulement si le document chevauche 2 années).

    Le jour de la semaine n'est utile que dans le tableau (repérer un vendredi, une fin de
    mois) : ailleurs — résumé, sommaire, titres de semaine — il encombre.
    """
    base = f"{'1er' if d.day == 1 else d.day} {_MOIS[d.month]}"
    if weekday:
        base = f"{_JOURS[d.weekday()]} {base}"
    return f"{base} {d.year}" if with_year else base


def _fmt_range(a, b, with_year=False):
    """« du 14 août au 18 septembre » — mois écrit une seule fois s'il est commun."""
    if a == b:
        return f"le {_fmt_date(a, with_year, weekday=False)}"
    if (a.month, a.year) == (b.month, b.year):
        fin = _fmt_date(b, with_year, weekday=False)
        return f"du {'1er' if a.day == 1 else a.day} au {fin}"
    return (f"du {_fmt_date(a, with_year, weekday=False)} "
            f"au {_fmt_date(b, with_year, weekday=False)}")


def _tel_href(tel):
    return "".join(ch for ch in tel if ch.isdigit() or ch == "+")


def _linkify(html, link_color=_BLUE):
    """Rend cliquables e-mails (mailto) et téléphones FR/international (tel:) dans un bloc."""
    html = _EMAIL_RE.sub(
        rf'<a href="mailto:\1" style="color:{link_color};text-decoration:underline;">\1</a>', html)
    html = _TEL_RE.sub(
        lambda m: f'<a href="tel:{_tel_href(m.group(1))}" '
                  f'style="color:{link_color};text-decoration:underline;">{m.group(1)}</a>', html)
    return html


def _richblock(block, link_color=_BLUE):
    """Bloc riche : markdown (sauts de ligne simples respectés via nl2br) ou HTML brut."""
    if not block:
        return ""
    if block.get("format") == "html":
        return block["content"]
    return _linkify(_md.markdown(block["content"], extensions=["nl2br"]), link_color)


def _meta_line(block, link_color=_BLUE):
    """Coordonnées de la structure sur une seule ligne discrète, sans émoji ni encadré."""
    html = _richblock(block, link_color)
    if not html:
        return ""
    html = re.sub(r"</?p>", "", html)
    html = re.sub(r"<br\s*/?>", " · ", html)
    html = html.replace("📞", "").replace("✉", "").replace("📧", "")
    html = re.sub(r"\s{2,}", " ", html).strip(" ·\n")
    return html


# --- extraction des champs métier ---------------------------------------------------

def _fin_de_contrat(it):
    """(date, texte brut) tirés de la note « Fin de contrat : 14/08/2026 »."""
    note = (it.get("note") or "").strip()
    m = _DATE_RE.search(note)
    if not m:
        return None, note
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d), m.group(0)
    except ValueError:
        return None, m.group(0)


def _prescripteur(it):
    m = _PRESC_RE.search((it.get("nom") or "").strip())
    return m.group(1).strip() if m else ""


def _items(g):
    """Tous les contrats d'une structure, toutes sections confondues, triés par échéance."""
    out = []
    for s in g.get("sections", []):
        out.extend(s.get("items", []) or [])
    return sorted(out, key=lambda it: (_fin_de_contrat(it)[0] or date.max))


def _all_dates(doc):
    return [d for g in doc.get("groupes", []) for it in _items(g)
            for d in [_fin_de_contrat(it)[0]] if d]


# --- tableau de contrats ------------------------------------------------------------

_TH = (f"padding:0 12px 6px 0;text-align:left;vertical-align:bottom;font-family:{_FONT};"
       f"font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;"
       f"color:{_MUTE};border-bottom:1px solid {_RULE};")
_TD = (f"padding:12px 12px 12px 0;text-align:left;vertical-align:top;font-family:{_FONT};"
       f"font-size:15px;line-height:1.5;color:{_INK};border-bottom:1px solid {_RULE};"
       f"word-break:break-word;")

# Libellé de repli affiché **uniquement** quand les cellules s'empilent (petit écran) :
# masqué en inline (donc masqué aussi là où le <style> est strippé — mais là les colonnes
# et leur en-tête subsistent, donc rien n'est perdu).
_LBL = '<span class="lbl" style="display:none;font-size:13px;color:%s;">%s</span>'


def _cell_echeance(it, with_year):
    d, raw = _fin_de_contrat(it)
    if not (d or raw):
        return '<span style="color:#999;">—</span>'
    txt = _fmt_date(d, with_year) if d else raw
    return ((_LBL % (_MUTE, "Fin de contrat&nbsp;: ")) +
            f'<span style="font-weight:700;color:{_INK};white-space:nowrap;">{esc(txt)}</span>')


def _cell_candidature(it):
    """« Candidature envoyée par X » — le mot « Candidature » porte le lien.

    Empilé (petit écran), ce même mot devient le libellé de la ligne : il passe dans le
    `.lbl` (lien compris) et disparaît du corps via `.dsk`, pour éviter de l'écrire deux fois.
    """
    url = it.get("url")
    if url:
        mot = (f'<a href="{esc(url)}" style="color:{_BLUE};text-decoration:underline;'
               f'font-weight:700;">Candidature</a>')
    else:
        mot = '<span style="font-weight:700;">Candidature</span>'
    lbl = (f'<span class="lbl" style="display:none;font-size:13px;color:{_MUTE};">'
           f'{mot}&nbsp;: </span>')
    presc = _prescripteur(it)
    if not presc:
        return lbl + f'<span class="dsk">{mot}</span>'
    return lbl + f'<span class="dsk">{mot} </span>envoyée par {_nowrap(esc(presc))}'


def _cell_accompagnement(it):
    """Accompagnateur : le nom porte le mailto (pas d'adresse brute — évite les débords)."""
    acc = it.get("accompagnateur") or {}
    nom, email, tel = acc.get("nom"), acc.get("email"), acc.get("telephone")
    if not (nom or email or tel):
        return '<span style="color:#999;">—</span>'
    lbl = _LBL % (_MUTE, "Accompagnement&nbsp;: ")
    if nom and email:
        main = _nowrap(f'<a href="mailto:{esc(email)}" style="color:{_BLUE};'
                       f'text-decoration:underline;">{esc(nom)}</a>')
    elif nom:
        main = _nowrap(esc(nom))
    else:
        main = (f'<a href="mailto:{esc(email)}" style="color:{_BLUE};'
                f'text-decoration:underline;">{esc(email)}</a>')
    if tel:
        main += (f'<br><a href="tel:{esc(_tel_href(tel))}" style="color:{_BLUE};'
                 f'text-decoration:underline;">{esc(tel)}</a>')
    return lbl + main


def _row(cells, widths, bg=None, last=False, inset=0):
    """Une ligne de tableau : cellules déjà rendues, largeurs en %, fond optionnel.

    Le fond de zébrure ne change **aucun** calage : mêmes marges internes sur toutes les
    lignes, sinon une ligne sur deux décale sa première colonne.
    """
    tds = []
    for i, (c, w) in enumerate(zip(cells, widths)):
        style = _TD + (f"background:{bg};" if bg else "")
        if i == 0 and inset:
            style += f"padding-left:{inset}px;"
        if i == len(cells) - 1:
            style += f"padding-right:{inset}px;" if inset else "padding-right:0;"
        if last:
            style = style.replace(f"border-bottom:1px solid {_RULE};", "border-bottom:0;")
        tds.append(f'<td class="c{i+1}" width="{w}%" style="{style}">{c}</td>')
    return f'<tr>{"".join(tds)}</tr>'


def _table(rows_html, headers, widths, inset=0):
    ths = []
    for i, (h, w) in enumerate(zip(headers, widths)):
        style = _TH
        if i == 0 and inset:
            style += f"padding-left:{inset}px;"
        if i == len(headers) - 1:
            style += f"padding-right:{inset}px;" if inset else "padding-right:0;"
        ths.append(f'<th class="c{i+1}" scope="col" width="{w}%" style="{style}">{h}</th>')
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="width:100%;border-collapse:collapse;margin:14px 0 0;">'
            f'<thead><tr>{"".join(ths)}</tr></thead>'
            f'<tbody>{rows_html}</tbody></table>')


_WIDTHS = (26, 42, 32)
_HEADERS = ("Fin de contrat", "Candidature", "Accompagnement")


def _table_structure(items, v, with_year):
    inset = v.get("inset", 0)
    rows = []
    for i, it in enumerate(items):
        bg = v["zebra"] if (v["zebra"] and i % 2 == 1) else None
        rows.append(_row((_cell_echeance(it, with_year), _cell_candidature(it),
                          _cell_accompagnement(it)), _WIDTHS, bg=bg,
                         last=(i == len(items) - 1), inset=inset))
    return _table("".join(rows), _HEADERS, _WIDTHS, inset)


def _phrase(n):
    if n <= 1:
        return ("1 ancien demandeur d’emploi de l’agence a un contrat qui arrive "
                "à échéance au sein de cette structure.")
    return (f"{n} anciens demandeurs d’emploi de l’agence ont un contrat qui arrive "
            f"à échéance au sein de cette structure.")


# --- blocs éditoriaux ---------------------------------------------------------------

def _dares_html(pad=0):
    """Repère chiffré Dares — placement volontaire : au contact immédiat de l'intro."""
    p = f"padding:16px {pad}px;" if pad else "padding:16px 18px;"
    return (f'<div style="background:{_TINT};{p}border-radius:{_R_SM};'
            f'margin:18px 0 0;font-family:{_FONT};'
            f'font-size:14px;line-height:1.6;color:{_INK};">'
            f'L’aide dans les démarches (logement, recherche d’emploi, santé…) augmente de '
            f'<strong style="color:{_ORANGE};">30&nbsp;%</strong> les chances d’être en emploi '
            f'6 mois après la sortie.'
            f'<span style="display:block;margin-top:8px;font-size:12px;color:{_MUTE};">'
            f'Source : Julien Blasco, Dares — '
            f'<a href="{_DARES_URL}" style="color:{_BLUE};text-decoration:underline;">'
            f'<em>Quelle situation professionnelle après un parcours en insertion par '
            f'l’activité économique ?</em></a> (Dares Analyses n°&nbsp;9, janvier 2024, '
            f'graphique 3)</span></div>')


def _saviez_vous_html(inset=0):
    """« Le saviez-vous ? » — placement volontaire : au contact du premier tableau."""
    pad = f"padding:0 {inset}px;" if inset else ""
    return (f'<p style="margin:12px 0 0;{pad}font-family:{_FONT};font-size:14px;'
            f'line-height:1.6;color:{_MUTE};">'
            f'<strong style="color:{_ORANGE};">Le saviez-vous ?</strong> {_SAVIEZ_VOUS}</p>')


def _resume(doc, groupes):
    """« 24 contrats · 8 structures · du 14 août au 18 septembre » — repère de volume."""
    ds = _all_dates(doc)
    n = sum(len(_items(g)) for g in groupes)
    bits = [f"{n} contrat{'s' if n > 1 else ''}"]
    if len(groupes) > 1:
        bits.append(f"{len(groupes)} structures")
    if ds:
        with_year = min(ds).year != max(ds).year
        bits.append(_fmt_range(min(ds), max(ds), with_year))
    return " · ".join(bits)


def _sommaire(groupes, with_year, linked=True):
    """Sommaire — n'apparaît qu'au-delà de 2 structures (sinon il est du bruit).

    `linked=False` pour la variante `echeance`, où il n'existe pas de section par structure
    vers laquelle pointer : le sommaire y reste un simple inventaire.
    """
    if len(groupes) < 3:
        return ""
    lis = []
    for i, g in enumerate(groupes):
        items = _items(g)
        d = _fin_de_contrat(items[0])[0] if items else None
        droite = (f'<span style="color:{_MUTE};white-space:nowrap;">'
                  f'{len(items)} · dès le '
                  f'{esc(_fmt_date(d, with_year, weekday=False))}</span>') if d else ""
        titre = esc(g["titre"])
        if linked:
            titre = (f'<a href="#s-{i}" style="color:{_BLUE};'
                     f'text-decoration:underline;">{titre}</a>')
        else:
            titre = f'<span style="font-weight:700;">{titre}</span>'
        lis.append(
            f'<tr><td style="padding:5px 12px 5px 0;font-family:{_FONT};font-size:14px;'
            f'line-height:1.5;">{titre}</td>'
            f'<td style="padding:5px 0;text-align:right;font-family:{_FONT};font-size:13px;'
            f'line-height:1.5;">{droite}</td></tr>')
    return (f'<div style="margin:20px 0 0;">'
            f'<div style="font-family:{_FONT};font-size:11px;font-weight:700;'
            f'letter-spacing:.06em;text-transform:uppercase;color:{_MUTE};'
            f'padding-bottom:6px;border-bottom:1px solid {_RULE};">Les structures concernées</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="width:100%;border-collapse:collapse;">{"".join(lis)}</table></div>')


# --- sections structure -------------------------------------------------------------

def _group_inner(g, idx, items, v, with_year, first):
    # le retrait horizontal est porté par chaque élément (et par les cellules du tableau),
    # jamais par le conteneur : les fonds atteignent ainsi les bords du bloc
    inset = v.get("inset", 0)
    pad = f"padding-left:{inset}px;padding-right:{inset}px;" if inset else ""
    meta = _meta_line(g.get("before_block"))
    meta_html = (f'<div style="{pad}font-family:{_FONT};font-size:13px;line-height:1.6;'
                 f'color:{_MUTE};margin:4px 0 0;word-break:break-word;">{meta}</div>'
                 ) if meta else ""
    return (f'<a id="s-{idx}"></a><a name="s-{idx}"></a>'
            f'<h2 style="margin:0;{pad}font-family:{_FONT};font-size:18px;line-height:1.35;'
            f'font-weight:700;color:{_BLUE};">{esc(g["titre"])}</h2>'
            f'{meta_html}'
            f'<p style="margin:12px 0 0;{pad}font-family:{_FONT};font-size:15px;'
            f'line-height:1.55;color:{_INK};">{_phrase(len(items))}</p>'
            f'{_table_structure(items, v, with_year)}'
            f'{_saviez_vous_html(inset) if first else ""}')


_BAR_LINK = "#c9d3ff"  # liens sur bandeau bleu : contraste suffisant, reste lisible


def _card(anchor, titre, sous_titre, corps, v, last=False, pad_bottom=0):
    """Bloc « v0 » remis à plat : bandeau bleu plein + corps blanc **encadré**, léger arrondi.

    Le bandeau donne le point d'entrée, le contour tient le bloc : sur un e-mail qui en
    aligne huit, le corps a besoin d'un bord gauche/droit pour se lire comme un ensemble.
    Contour **ou** filet de séparation, jamais les deux — ici le contour.
    """
    # `bar` : sur fond bleu, Apple Mail transforme adresses / téléphones / dates en liens et
    # leur impose SA couleur (bleu foncé souligné) — illisible ici. La classe permet au
    # <style> de rendre au bandeau ses couleurs claires ; la couleur est aussi posée sur un
    # <span> interne, certains clients ignorant `color` porté par le <h2> lui-même.
    sub = (f'<div class="bar" style="color:{_BAR_LINK};font-family:{_FONT};font-size:13px;'
           f'line-height:1.6;margin:5px 0 0;word-break:break-word;">{sous_titre}</div>'
           ) if sous_titre else ""
    return (
        f'<tr><td style="padding:0 0 {v["gap"]}px;">{anchor}'
        f'<div style="background:{v["card"]};border:1px solid {v["border"]};'
        f'border-radius:{_R_SM};overflow:hidden;">'
        f'<div style="background:{v["bar"]};padding:14px 20px;'
        f'border-radius:{_R_SM} {_R_SM} 0 0;">'
        f'<h2 class="bartitle" style="margin:0;font-family:{_FONT};font-size:17px;'
        f'line-height:1.35;font-weight:700;color:#ffffff;">'
        f'<span style="color:#ffffff;">{titre}</span></h2>{sub}</div>'
        # Aucune marge interne horizontale : ce sont les cellules qui écartent le texte, de
        # sorte que les fonds de zébrure aillent d'un bord à l'autre du bloc. Ni en haut :
        # le premier paragraphe porte sa propre marge. En bas, seulement si un contenu suit
        # le tableau (« Le saviez-vous ? ») — sinon la dernière ligne ferme déjà le bloc.
        f'<div style="padding:0 0 {pad_bottom}px;">{corps}</div></div></td></tr>')


def _render_group_carte(g, idx, v, with_year, first, last=False):
    items = _items(g)
    inset = v.get("inset", 0)
    corps = (f'<p style="margin:14px 0 0;padding:0 {inset}px;font-family:{_FONT};'
             f'font-size:15px;line-height:1.55;color:{_INK};">{_phrase(len(items))}</p>'
             f'{_table_structure(items, v, with_year)}'
             f'{_saviez_vous_html(inset) if first else ""}')
    return _card(f'<a id="s-{idx}"></a><a name="s-{idx}"></a>',
                 esc(g["titre"]), _meta_line(g.get("before_block"), _BAR_LINK), corps, v, last,
                 pad_bottom=18 if first else 0)


def _render_group(g, idx, v, with_year, first, last=False):
    if v.get("bar"):
        return _render_group_carte(g, idx, v, with_year, first, last)
    inner = _group_inner(g, idx, _items(g), v, with_year, first)
    bg = v["alt"] if (v["alt"] and idx % 2 == 1) else v["card"]
    if bg:
        # carte (blocs) ou bande alternée : fond plein, léger arrondi, aucun contour
        return (f'<tr><td style="padding:0 0 {v["gap"]}px;">'
                f'<div style="background:{bg};padding:{v["pad"]}px 0;'
                f'border-radius:{_R_SM};">{inner}</div>'
                f'</td></tr>')
    sep = "" if first else f"border-top:1px solid {_RULE};"
    return f'<tr><td style="{sep}padding:26px 0 6px;">{inner}</td></tr>'


# --- IA alternative : regroupement par échéance -------------------------------------

def _semaine(d):
    lundi = d - timedelta(days=d.weekday())
    return lundi


def _render_par_echeance(doc, groupes, v, with_year):
    """Variante `echeance` : ce qui compte est *quand*, pas *où*. Une section par semaine,
    la structure devient une colonne. Contre-proposition à l'IA centrée structure."""
    widths = (24, 34, 42)
    # la colonne porte le nom de la structure **et** l'accompagnateur : le titre le dit
    headers = ("Fin de contrat", "Structure et accompagnement", "Candidature")

    lignes = []
    for g in groupes:
        for it in _items(g):
            d = _fin_de_contrat(it)[0]
            lignes.append((d or date.max, g, it))
    lignes.sort(key=lambda t: (t[0], t[1]["titre"]))

    # regroupement par semaine, ordre conservé
    semaines = []
    for d, g, it in lignes:
        sem = _semaine(d) if d != date.max else None
        if not semaines or semaines[-1][0] != sem:
            semaines.append((sem, []))
        semaines[-1][1].append((g, it))

    def _titre(sem):
        if not sem:
            return "Sans date"
        return f"Semaine {_fmt_range(sem, sem + timedelta(days=6), with_year)}"

    inset = v.get("inset", 0)

    def _corps(paires):
        rows = []
        for i, (g, it) in enumerate(paires):
            struct = ((_LBL % (_MUTE, "Structure&nbsp;: ")) +
                      f'<span style="font-weight:700;">{esc(g["titre"])}</span>'
                      f'<span class="sub" style="display:block;font-size:13px;'
                      f'color:{_MUTE};">{_cell_accompagnement(it)}</span>')
            bg = v["zebra"] if (v["zebra"] and i % 2 == 1) else None
            rows.append(_row((_cell_echeance(it, with_year), struct, _cell_candidature(it)),
                             widths, bg=bg, last=(i == len(paires) - 1), inset=inset))
        return _table("".join(rows), headers, widths, inset)

    if v.get("bar"):  # une carte par semaine, bandeau bleu
        out = []
        for i, (sem, paires) in enumerate(semaines):
            n = len(paires)
            sous = f"{n} contrat{'s' if n > 1 else ''}"
            corps = _corps(paires) + (_saviez_vous_html(inset) if i == 0 else "")
            out.append(_card("", esc(_titre(sem)), sous, corps, v,
                             last=(i == len(semaines) - 1),
                             pad_bottom=18 if i == 0 else 0))
        return "".join(out)

    out = []
    for sem, paires in semaines:
        out.append(f'<h2 style="margin:26px 0 0;font-family:{_FONT};font-size:16px;'
                   f'line-height:1.35;font-weight:700;color:{_BLUE};">'
                   f'{esc(_titre(sem))}</h2>')
        out.append(_corps(paires))
    return (f'<tr><td style="padding:20px 0 6px;">{"".join(out)}'
            f'{_saviez_vous_html()}</td></tr>')


# --- document -----------------------------------------------------------------------

def render_doc(doc, variant=DEFAULT_VARIANT):
    v = _VARIANTS[variant]
    par_echeance = variant.endswith("echeance")
    dests = doc.get("destinataires", [])
    to_comments = "\n".join(f'<!-- to: {esc(d["email"])} -->' for d in dests)
    intro = esc(doc["intro"]).replace("\n", "<br>") if doc.get("intro") else ""
    remarques = [_REMARQUE_OBSOLETE.sub(_REMARQUE_CORRIGEE, r)
                 for r in (doc.get("remarques") or [])]
    # mentions : un seul paragraphe au fil du texte, sans retour forcé entre les phrases
    rem_html = " ".join(esc(r) for r in remarques)

    ds = _all_dates(doc)
    with_year = bool(ds) and min(ds).year != max(ds).year
    # structures classées par échéance la plus proche
    groupes = sorted(doc.get("groupes", []),
                     key=lambda g: min((_fin_de_contrat(it)[0] or date.max)
                                       for it in _items(g)) if _items(g) else date.max)

    rows = [
        # En-tête : logo et titre posés directement sur le blanc, sans encadré — seuls les
        # blocs de contenu sont matérialisés, l'e-mail « démarre » sur une page.
        f'<tr><td style="padding:0 0 26px;">'
        f'<img src="{_LOGO_URL}" alt="La Plateforme de l’inclusion" width="240" '
        f'style="display:block;width:240px;max-width:64%;height:auto;border:0;"></td></tr>',
        f'<tr><td style="border-top:1px solid {_RULE};padding:28px 0 0;">'
        f'<h1 style="margin:0;font-family:{_FONT};font-size:30px;line-height:1.22;'
        f'font-weight:700;color:{_ORANGE};letter-spacing:-.01em;">{esc(doc["objet"])}</h1>'
        f'<p style="margin:12px 0 0;font-family:{_FONT};font-size:13px;line-height:1.5;'
        f'font-weight:700;letter-spacing:.03em;color:{_MUTE};">{esc(_resume(doc, groupes))}</p>'
        f'<p style="margin:16px 0 0;font-family:{_FONT};font-size:16px;line-height:1.6;'
        f'color:{_INK};">{intro}</p>'
        f'{_dares_html()}'
        f'{_sommaire(groupes, with_year, linked=not par_echeance)}'
        f'<div style="height:26px;font-size:0;line-height:0;">&nbsp;</div>'
        f'</td></tr>',
    ]
    if par_echeance:
        rows.append(_render_par_echeance(doc, groupes, v, with_year))
    else:
        for i, g in enumerate(groupes):
            rows.append(_render_group(g, i, v, with_year, first=(i == 0),
                                      last=(i == len(groupes) - 1)))

    # bloc avis : encart encadré orange, mis en avant (bordure + fond orangé + CTA orange)
    rows.append(
        f'<tr><td style="padding:28px 0 12px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="border:2px solid {_ORANGE};border-radius:{_R_SM};background:#fff7ef;'
        f'padding:22px 24px;text-align:center;">'
        f'<p style="margin:0 0 4px;font-family:{_FONT};font-size:17px;font-weight:700;'
        f'color:{_INK};">Votre avis nous intéresse</p>'
        f'<p style="margin:0 0 16px;font-family:{_FONT};font-size:15px;line-height:1.6;'
        f'color:{_INK};">En 2 minutes, aidez-nous à améliorer ces alertes.</p>'
        f'<a href="{_AVIS_URL}" style="display:inline-block;padding:13px 30px;'
        f'background:{_ORANGE};color:#ffffff;text-decoration:none;border-radius:{_R_XS};'
        f'font-family:{_FONT};font-size:15px;font-weight:700;">Donner mon avis</a>'
        f'</td></tr></table></td></tr>')
    if rem_html:
        rows.append(
            f'<tr><td style="border-top:1px solid {_RULE};padding:22px 0 0;">'
            f'<p style="margin:0;font-family:{_FONT};font-size:13px;line-height:1.6;'
            f'color:{_MUTE};">{rem_html}</p></td></tr>')

    body = "\n".join(rows)
    ins = v.get("inset", 0)  # repris dans la media query : les cellules empilées gardent
    # le même retrait que le reste du bloc, sinon elles se recollent au bord

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
<meta name="x-apple-disable-message-reformatting">
<meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<title>{esc(doc["objet"])}</title>
<style>
/* Apple Mail « data detectors » : adresses, téléphones et dates sont convertis en liens
   auxquels le client impose sa propre couleur soulignée. On les remet au style du texte
   qui les porte — sur le bandeau bleu, ce bleu foncé souligné était illisible. */
a[x-apple-data-detectors] {{
  color:inherit !important; text-decoration:none !important; font-size:inherit !important;
  font-family:inherit !important; font-weight:inherit !important; line-height:inherit !important;
}}
.bartitle, .bartitle span {{ color:#ffffff !important; }}
.bar, .bar a, .bar a[x-apple-data-detectors] {{ color:{_BAR_LINK} !important; }}
.bar a {{ text-decoration:underline !important; }}
/* Bonus progressif : les clients qui gardent le <style> (pas Gmail mobile) empilent
   les cellules sous 520px. La mise en page reste lisible sans, colonnes courtes. */
@media only screen and (max-width:520px) {{
  /* width:auto + border-box : avec `width:100%` la marge interne s'ajoute *hors* des 100 %
     (content-box par défaut) et le texte passe sous le bord droit du bloc. */
  .c1, .c2, .c3 {{
    display:block !important; width:auto !important; box-sizing:border-box !important;
  }}
  thead {{ display:none !important; }}
  .c1 {{ padding:18px {ins}px 0 !important; border-bottom:0 !important; }}
  .c2 {{ padding:4px {ins}px 0 !important; border-bottom:0 !important; }}
  .c3 {{ padding:4px {ins}px 18px !important; }}
  /* empilé, tout se lit à la même taille : les libellés cessent d'être une note de bas de
     ligne et les trois lignes forment un paragraphe régulier */
  .c1, .c2, .c3, .lbl, .sub {{ font-size:15px !important; line-height:1.55 !important; }}
  .lbl {{ display:inline !important; }}
  .dsk {{ display:none !important; }}
  .nw {{ white-space:normal !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:{v['page']};color:{_INK};font-family:{_FONT};-webkit-font-smoothing:antialiased;">
{to_comments}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{v['page']};">
<tr><td align="center" style="padding:28px 20px 40px;">
<table role="presentation" width="{_W}" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:{_W}px;text-align:left;">
{body}
</table>
</td></tr>
</table>
</body>
</html>"""
    return _typo_html(html)


def run_render(in_dir, out_dir, variant=DEFAULT_VARIANT):
    src, out = Path(in_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json"))
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        (out / f"{fp.stem}.html").write_text(render_doc(doc, variant), encoding="utf-8")
    print(f"render-contrats[{variant}]: {len(files)} HTML écrit(s) → {out}")
