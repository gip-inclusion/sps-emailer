"""Rendu des e-mails « Alerte fins de contrats IAE » (schéma docs/schema/alerte-contrats.schema.json).

Modèle centré **structure** : les `groupes` (une structure IAE chacun) sont au niveau du
document, chaque section regroupe des contrats arrivant à échéance. Renderer distinct du
moteur SPS (render.py, centré bénéficiaire) — aucun couplage, styles inline Outlook-safe.

Mise en forme : charte **La Plateforme de l'inclusion** — bleu France #000091, accent
orange #e57200, fonds bleu clair #f0f8ff, police Arial.
"""
import json
import re
from pathlib import Path
import markdown as _md
from sps.template import esc

# --- palette La Plateforme de l'inclusion ---
_BLUE = "#000091"    # bleu France : titres, en-têtes, boutons
_ORANGE = "#e57200"  # accent
_INK = "#000638"     # texte foncé
_MUTE = "#3b3f44"    # texte secondaire
_LIGHT = "#f0f8ff"   # fond bleu très clair
_LINK = "#000091"    # liens
_FONT = "Arial, Helvetica, sans-serif"

_SPACER = '<tr><td style="font-size:0;line-height:0;height:22px;">&nbsp;</td></tr>'

# Logo La Plateforme de l'inclusion (image hébergée)
_LOGO_URL = "https://img.mailinblue.com/3949075/images/content_library/original/680e18d8b0af2987e384efae.png"

# Encart avis. L'URL contient le tag de fusion Brevo {{ params.EMAIL }} (substitué à l'envoi
# via le champ `params` de l'API — fonctionne même si le destinataire n'est pas un contact Brevo).
# Inséré littéralement, jamais échappé.
_AVIS_URL = "https://tally.so/r/Y5Bkrv?email={{ params.EMAIL }}"

# Encart pédagogique affiché une seule fois, après le 1er demandeur d'emploi (encadré orange).
_SAVIEZ_VOUS = (
    '<div style="margin:16px 0 4px;padding:16px 18px;background:#ffffff;'
    'border:2px solid #e57200;border-radius:12px;color:#000638;font-size:14px;line-height:1.6;">'
    '💡 <strong style="color:#e57200;">Le saviez-vous ?</strong> À partir de la candidature, '
    'vous pouvez retrouver les contrats déclarés dans l’extranet IAE 2.0 de l’ASP. Il suffit de '
    'cliquer sur « Afficher le PASS IAE » puis « Suivi des contrats IAE ».</div>'
)

# Encart avis mis en avant, en haut de l'e-mail : fond bleu clair, titre bleu, bouton bleu plein.
_AVIS_ENCART = (
    '<tr><td><div style="background:#f0f8ff;border:1px solid #d3e2f5;border-radius:12px;'
    'padding:26px;text-align:center;">'
    '<div style="font-size:19px;font-weight:800;color:#000091;margin:0 0 6px;'
    'font-family:Arial,Helvetica,sans-serif;">💬 Votre avis nous intéresse</div>'
    '<div style="font-size:14px;color:#3b3f44;line-height:1.55;margin:0 0 18px;'
    'font-family:Arial,Helvetica,sans-serif;">En 2 minutes, aidez-nous à améliorer ces alertes.</div>'
    f'<a href="{_AVIS_URL}" style="display:inline-block;padding:13px 30px;background:#000091;'
    'color:#ffffff;text-decoration:none;border-radius:5px;font-size:15px;font-weight:700;'
    'font-family:Arial,Helvetica,sans-serif;">Donner mon avis</a></div></td></tr>'
)

# Encart « preuve par les chiffres » (statistique Dares), placé sous l'intro.
_STAT_ENCART = (
    '<tr><td><div style="background:#f0f8ff;border:1px solid #d3e2f5;border-radius:12px;'
    'padding:18px 20px;color:#000638;font-size:15px;line-height:1.6;'
    'font-family:Arial,Helvetica,sans-serif;">'
    '📊 L’aide dans les démarches (logement, recherche d’emploi, santé…) augmente de '
    '<strong style="color:#e57200;">30&nbsp;%</strong> les chances d’être en emploi 6 mois après la sortie.'
    '<div style="font-size:12px;color:#3b3f44;line-height:1.5;margin-top:10px;">'
    'Source : Julien Blasco, Dares — <a href="https://dares.travail-emploi.gouv.fr/publication/'
    'quelle-situation-professionnelle-apres-un-parcours-en-insertion-par-lactivite" '
    'style="color:#000091;text-decoration:underline;"><em>Quelle situation professionnelle '
    'après un parcours en insertion par l’activité économique ?</em></a> '
    '(Dares Analyses n° 9, janvier 2024, graphique 3)'
    '</div></div></td></tr>'
)

# e-mail nu (hors attribut/mailto déjà posé) → mailto cliquable dans les blocs contact
_EMAIL_RE = re.compile(r'(?<![\w.@+"=>-])([\w.+-]+@[\w-]+\.[\w.-]+\w)')
# téléphone FR national (« 04 72 76 94 00 ») ou international (« +33 3 74 64 26 90 ») → tel:
_TEL_RE = re.compile(r'(?<![\d>+])(\+33[ .]?\d(?:[ .]?\d\d){4}|0\d(?:[ .]?\d\d){4})(?!\d)')


def _tel_href(tel):
    return "".join(ch for ch in tel if ch.isdigit() or ch == "+")


def _linkify(html, link_color=_LINK):
    """Rend cliquables e-mails (mailto) et téléphones FR/international (tel:) dans un bloc."""
    html = _EMAIL_RE.sub(
        rf'<a href="mailto:\1" style="color:{link_color};text-decoration:none;">\1</a>', html)
    html = _TEL_RE.sub(
        lambda m: f'<a href="tel:{_tel_href(m.group(1))}" '
                  f'style="color:{link_color};text-decoration:none;">{m.group(1)}</a>', html)
    return html


def _richblock(block, link_color=_LINK):
    """Bloc riche : markdown (sauts de ligne simples respectés via nl2br) ou HTML brut."""
    if not block:
        return ""
    if block.get("format") == "html":
        return block["content"]
    return _linkify(_md.markdown(block["content"], extensions=["nl2br"]), link_color)


def _cta(it):
    url = it.get("url")
    label = it.get("cta_label") or "Voir la candidature"
    return (f'<a href="{esc(url)}" style="display:inline-block;margin:10px 0 2px;'
            f'padding:11px 20px;background:{_BLUE};color:#ffffff;text-decoration:none;'
            f'border-radius:5px;font-size:14px;font-weight:700;font-family:{_FONT};">'
            f'{esc(label)}</a>')


def _accompagnateur(acc):
    """Ligne « Accompagnateur : Nom — tél · e-mail » (tel/mailto cliquables)."""
    if not acc or not (acc.get("nom") or acc.get("email") or acc.get("telephone")):
        return ""
    bits = []
    if acc.get("telephone"):
        bits.append(f'<a href="tel:{esc(_tel_href(acc["telephone"]))}" '
                    f'style="color:{_LINK};text-decoration:none;">{esc(acc["telephone"])}</a>')
    if acc.get("email"):
        bits.append(f'<a href="mailto:{esc(acc["email"])}" '
                    f'style="color:{_LINK};text-decoration:none;">{esc(acc["email"])}</a>')
    label = (f'👤 Accompagnateur : {esc(acc["nom"])}' if acc.get("nom")
             else '👤 Accompagnateur')
    if bits:
        label += ' — ' + " &nbsp;·&nbsp; ".join(bits)
    return (f'<div style="font-size:14px;color:{_MUTE};line-height:1.55;margin:6px 0;">'
            f'{label}</div>')


def _numbered_title(it):
    """Titre « Demandeur d'emploi n°N — … » (numérotation continue via _num)."""
    nom = (it.get("nom") or "").strip()
    num = it.get("_num")
    # retire un préfixe « Candidat »/« Demandeur d'emploi » venant des données
    body = re.sub(r"^(?:Candidat|Demandeur d'emploi)\b[\s—–-]*", "", nom, flags=re.I)
    label = f"Demandeur d'emploi n°{num}" if num else "Demandeur d'emploi"
    if body:
        return esc(f"{label} — {body}")
    return esc(label if num else nom)


def _item(it):
    out = [f'<div style="font-weight:700;color:{_INK};font-size:16px;margin:0 0 3px;'
           f'line-height:1.45;">{_numbered_title(it)}</div>']
    if it.get("note"):
        out.append(f'<div style="font-size:14px;color:{_MUTE};line-height:1.55;'
                   f'margin:2px 0;">{esc(it["note"])}</div>')
    out.append(_accompagnateur(it.get("accompagnateur")))
    if it.get("url"):
        out.append(_cta(it))
    if it.get("_num") == 1:  # encart pédagogique, une seule fois, après le 1er demandeur
        out.append(_SAVIEZ_VOUS)
    return "".join(p for p in out if p)


def _render_items(items):
    parts = []
    for i, it in enumerate(items):
        inner = _item(it)
        if i == 0:
            parts.append(f'<div>{inner}</div>')
        else:
            parts.append(f'<div style="margin-top:16px;padding-top:14px;'
                         f'border-top:1px solid #e3e9f2;">{inner}</div>')
    return "".join(parts)


def _section_band(legende, first):
    if not legende:
        return ""
    mt = "" if first else "margin-top:14px;"
    return (f'<div style="{mt}background:{_LIGHT};border-top:1px solid #d3e2f5;'
            f'border-bottom:1px solid #d3e2f5;padding:10px 20px;font-size:13px;'
            f'font-weight:700;color:{_BLUE};line-height:1.4;font-family:{_FONT};">{esc(legende)}</div>')


def _render_section(s, first):
    band = _section_band(s.get("legende"), first)
    items = _render_items(s.get("items", []))
    body = f'<div style="padding:16px 20px;">{items}</div>' if items.strip() else ""
    return band + body


def _render_group(g, idx):
    sections = "".join(_render_section(s, first=(i == 0))
                       for i, s in enumerate(g.get("sections", [])))
    # coordonnées de la structure : intégrées à l'en-tête bleu (liens en bleu clair, lisibles)
    coords = _richblock(g.get("before_block"), link_color="#c9d3ff")
    coords = coords.replace("<p>", "").replace("</p>", "").strip()
    coords = coords.replace("✉", "📧")  # emoji e-mail plus lisible
    coords_html = (f'<div style="color:#c9d3ff;font-size:13px;line-height:1.65;'
                   f'margin-top:7px;">{coords}</div>') if coords else ""
    anchor = f'<a name="grp-{idx}"></a><a id="grp-{idx}"></a>'
    return (f'{anchor}<div class="panel" style="margin:0;background:#fff;border-radius:12px;'
            f'overflow:hidden;border:1px solid #e3e9f2;box-shadow:0 4px 14px rgba(0,0,30,0.08);">'
            f'<div style="background:{_BLUE};padding:15px 20px;">'
            f'<div style="color:#fff;font-weight:800;font-size:17px;line-height:1.3;'
            f'font-family:{_FONT};">{esc(g["titre"])}</div>{coords_html}</div>'
            f'{sections}</div>')


def render_doc(doc):
    dests = doc.get("destinataires", [])
    to_comments = "\n".join(f'<!-- to: {esc(d["email"])} -->' for d in dests)
    intro = esc(doc["intro"]).replace("\n", "<br>") if doc.get("intro") else ""
    remarques = doc.get("remarques") or []
    rem_html = "<br>".join(esc(r) for r in remarques)
    groupes = doc.get("groupes", [])
    # numérotation continue des demandeurs d'emploi sur tout l'e-mail (n°1, n°2, …)
    n = 0
    for g in groupes:
        for s in g.get("sections", []):
            for it in s.get("items", []):
                n += 1
                it["_num"] = n

    rows = [
        f'<tr><td class="topcard" style="background:#ffffff;border-radius:12px;overflow:hidden;'
        f'box-shadow:0 4px 14px rgba(0,0,30,0.08);border-top:5px solid {_ORANGE};">'
        f'<div style="padding:26px 30px 2px;text-align:left;">'
        f'<img src="{_LOGO_URL}" alt="La Plateforme de l’inclusion" width="210" '
        f'style="display:inline-block;max-width:210px;height:auto;border:0;"></div>'
        f'<div style="padding:16px 30px 6px;"><div style="color:{_ORANGE};font-size:23px;'
        f'font-weight:800;line-height:1.3;font-family:{_FONT};">{esc(doc["objet"])}</div></div>'
        f'<div style="padding:6px 30px 22px;"><p style="font-size:15px;color:{_INK};'
        f'line-height:1.5;margin:0;">{intro}</p></div></td></tr>'
    ]
    rows.append(_STAT_ENCART)  # preuve par les chiffres (Dares), sous l'intro
    for i, g in enumerate(groupes):
        rows.append(f'<tr><td>{_render_group(g, i)}</td></tr>')
    rows.append(_AVIS_ENCART)  # encart avis en bas, juste au-dessus des mentions
    if rem_html:
        rows.append(f'<tr><td style="padding:4px 30px 8px;">'
                    f'<p style="font-size:13px;color:#667085;line-height:1.55;margin:0;'
                    f'text-align:center;">{rem_html}</p></td></tr>')
    body = _SPACER.join(rows)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(doc["objet"])}</title>
<style>
@media only screen and (max-width:600px) {{
  .gutter {{ padding-left:0 !important; padding-right:0 !important; padding-top:0 !important; }}
  .panel, .topcard {{ border-radius:0 !important; border-left:0 !important; border-right:0 !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#eaf1fb;font-family:{_FONT};-webkit-font-smoothing:antialiased;color:{_INK};">
{to_comments}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf1fb;">
<tr><td class="gutter" align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">
{body}
</table>
</td></tr>
</table>
</body>
</html>"""


def run_render(in_dir, out_dir):
    src, out = Path(in_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json"))
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        (out / f"{fp.stem}.html").write_text(render_doc(doc), encoding="utf-8")
    print(f"render-contrats: {len(files)} HTML écrit(s) → {out}")
