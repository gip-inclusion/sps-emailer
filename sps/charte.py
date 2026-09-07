"""Charte graphique « La Plateforme de l'inclusion » + helpers HTML partagés.

Un seul endroit pour les couleurs, la police, le logo, l'URL du formulaire d'avis et les
petits helpers d'échappement/formatage, réutilisés par les renderers d'e-mails
(`render_structure`, et à terme `render_prescripteurs`/`render`). Modifier le logo ou l'URL Tally
ici plutôt que dans chaque renderer.

Couleurs : bleu France #000091, accent orange #e57200 ; police Arial.
"""
import html as _html
import re

# Couleurs / typo charte
BLUE = "#000091"
ORANGE = "#e57200"
INK = "#161616"
MUTE = "#666666"
RULE = "#dddddd"
TINT = "#f0f5fb"
FONT = "Arial, Helvetica, sans-serif"
LOGO_URL = "https://img.mailinblue.com/3949075/images/content_library/original/680e18d8b0af2987e384efae.png"

# Encart avis — formulaire Tally. {{ params.EMAIL }} est substitué par Brevo à l'envoi
# (cf. sps/brevo.py build_payload → params.EMAIL) par l'adresse du destinataire de la copie.
AVIS_URL = "https://tally.so/r/2E6Q8L?email={{ params.EMAIL }}"

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

# CSS d'empilement des tableaux à colonnes sur mobile (< 480 px). Les cellules `.ct-td`
# passent en pleine largeur, l'en-tête `.ct-head` est masqué et les libellés `.ct-lbl`
# (cachés inline sur desktop) réapparaissent au-dessus de chaque cellule. Dégrade
# proprement là où le <style>/@media est strippé (Gmail mobile) : le tableau reste affiché.
STACK_TABLE_CSS = """@media only screen and (max-width:480px){
  .ct-head{display:none!important;}
  .ct-tr{display:block!important;}
  .ct-td{display:block!important;width:100%!important;box-sizing:border-box!important;border-left:none!important;}
  .ct-td + .ct-td{border-top:1px solid #eef2f7!important;}
  .ct-lbl{display:block!important;}
}"""


def esc(s):
    return _html.escape(str(s)) if s is not None else ""


def fr(iso):
    """Date ISO 'YYYY-MM-DD…' → '30 septembre 2026' (valeur brute si non parsable)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return f"{int(m.group(3))} {MOIS[int(m.group(2))]} {m.group(1)}" if m else (iso or "")


def clean_nom(nom):
    """Retire un suffixe SIRET '- 41197457900046' collé au nom de structure."""
    return re.sub(r"\s*-\s*\d{6,}$", "", nom or "").strip()


def link(url, txt, color=BLUE):
    return f'<a href="{esc(url)}" style="color:{color};text-decoration:underline;">{esc(txt)}</a>'


def mailto(email, color=BLUE):
    return f'<a href="mailto:{esc(email)}" style="color:{color};text-decoration:none;">{esc(email)}</a>'


def avis_encart(titre="Votre avis nous intéresse",
                texte="En 2 minutes, aidez-nous à améliorer ces alertes.",
                cta="Donner mon avis"):
    """Encart avis Tally (boîte orange centrée, CTA orange). À insérer dans une cellule."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>\n'
        f'<td style="border:2px solid {ORANGE};border-radius:6px;background:#fff7ef;padding:22px 24px;text-align:center;">\n'
        f'<p style="margin:0 0 4px;font-family:{FONT};font-size:17px;font-weight:700;color:{INK};">{esc(titre)}</p>\n'
        f'<p style="margin:0 0 16px;font-family:{FONT};font-size:15px;line-height:1.6;color:{INK};">{esc(texte)}</p>\n'
        f'<a href="{AVIS_URL}" style="display:inline-block;padding:13px 30px;background:{ORANGE};color:#ffffff;text-decoration:none;border-radius:4px;font-family:{FONT};font-size:15px;font-weight:700;">{esc(cta)}</a>\n'
        f'</td></tr></table>')
