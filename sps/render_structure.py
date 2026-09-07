"""Rendu de l'e-mail « fins de contrats — vue STRUCTURE IAE ».

Adressé à la structure IAE (ses admins). Organisé par SEGMENT = type d'action à mener
(contacter un prescripteur, prolonger le PASS, faire le bilan…). Chaque contrat est une
carte-tableau : PASS IAE | Suivi interne | Prescripteur habilité, empilée sur mobile.

Charte et helpers communs : voir sps/charte.py.
Lancer :  uv run python -m sps.render_structure [in.json out.html]
          (défaut : out/structure/exemple.json → out/structure/exemple.html)
"""
import json
import re
import sys
from pathlib import Path

from sps.charte import (BLUE, ORANGE, INK, MUTE, RULE, TINT, FONT, LOGO_URL,
                        STACK_TABLE_CSS, esc, fr, clean_nom, mailto, avis_encart)

_W = 640  # largeur du conteneur (px)

# urgence -> (libellé, couleur texte/bordure, fond clair)
_URGENCE = {
    "critique": ("Urgence critique", "#b91c1c", "#fdecea"),
    "élevée":   ("Urgence élevée",   "#c2410c", "#fff3e6"),
    "normale":  ("À traiter",        BLUE,      TINT),
}
_RANK = {"critique": 0, "élevée": 1, "normale": 2}


def _admins_block(po):
    """Bloc « conseillers de l'agence prescriptrice » (hors le prescripteur habilité lui-même)."""
    admins = (po or {}).get("admins_org_prescriptrice") or []
    presc_email = (po or {}).get("presc_email")
    autres = [a for a in admins if a.get("email") and a.get("email") != presc_email]
    if not autres:
        return ""
    org = po.get("nom_org_prescripteur") or ""
    liens = " · ".join(
        f'<a href="mailto:{esc(a["email"])}" style="color:{BLUE};text-decoration:none;white-space:nowrap;">{esc(a["nom"])}</a>'
        for a in autres)
    return (f'<div style="margin-top:8px;padding:9px 12px;background:#f7f9fc;border-radius:4px;">'
            f'<div style="font-size:11px;font-weight:700;color:{MUTE};text-transform:uppercase;'
            f'letter-spacing:.04em;">Autres conseillers{(" — " + esc(org)) if org else ""}</div>'
            f'<div style="font-size:13px;color:{INK};margin-top:5px;line-height:1.9;">{liens}</div>'
            f'</div>')


def _pass_cell(c):
    val = c.get("pass_validite")
    if not val and not c.get("pass_date_fin"):
        return '<span style="color:#b91c1c;font-weight:700;">Expiré ou introuvable</span>'
    fin = fr(c.get("pass_date_fin"))
    j = c.get("jours_pass_restants_apres_fin_contrat")
    sub = ""
    if isinstance(j, int):
        if j < 0:
            sub = f'<div style="color:#b91c1c;margin-top:2px;">expire {abs(j)} j avant la fin du contrat</div>'
        elif j == 0:
            sub = '<div style="color:#c2410c;margin-top:2px;">expire le jour de la fin du contrat</div>'
        else:
            sub = f'<div style="color:{MUTE};margin-top:2px;">valide encore {j} j après la fin</div>'
    return f'Valide jusqu’au {fin}{sub}'


def _suivi_cell(c):
    acc = c.get("accompagnateur_siae") or []
    noms = [esc(a.get("nom")) for a in acc if a.get("nom")]
    if not noms:
        return f'<span style="color:{MUTE};">—</span>'
    return "<br>".join(noms)


def _presc_cell(c):
    cp = c.get("contact_prolongation") or {}
    po = c.get("prescripteur_origine")
    if cp.get("prescripteur_habilite") and po and po.get("presc_nom"):
        org = po.get("nom_org_prescripteur") or po.get("origine") or ""
        head = (f'<strong>{esc(po["presc_nom"])}</strong>'
                f'{("<br>" + esc(org)) if org else ""}'
                f'{("<br>" + mailto(po["presc_email"])) if po.get("presc_email") else ""}')
        return head + _admins_block(po)
    return f'<span style="color:{MUTE};">⚠ Aucun prescripteur habilité identifié</span>'


def _contract_block(c, first):
    top = "" if first else "margin-top:28px;"
    recond = c.get("num_reconduction") or 0
    recond_txt = f" · {recond}ᵉ reconduction" if recond else ""
    cid = c.get("emplois_candidat_id") or c.get("contrat_id_ctr")
    th = (f'font-size:11px;font-weight:700;color:{MUTE};text-transform:uppercase;'
          f'letter-spacing:.04em;text-align:left;padding:8px 12px;background:{TINT};'
          f'border-bottom:1px solid {RULE};')
    td = f'font-size:13px;color:{INK};line-height:1.5;padding:11px 12px;vertical-align:top;'
    sep = 'border-left:1px solid #eef2f7;'

    def lbl(t):  # libellé de colonne rappelé au-dessus de chaque cellule quand elles s'empilent (mobile)
        return (f'<span class="ct-lbl" style="display:none;font-size:11px;font-weight:700;color:{MUTE};'
                f'text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px;">{esc(t)}</span>')
    cp = c.get("contact_prolongation") or {}
    cand = ""
    if cp.get("lien_candidature"):
        cand = (f'<div style="margin:0 0 10px;">'
                f'<a href="{esc(cp["lien_candidature"])}" style="display:inline-block;padding:8px 15px;'
                f'background:#eff2fb;color:{BLUE};text-decoration:none;border:1px solid #cdd7ee;'
                f'border-radius:4px;font-size:13px;font-weight:700;">Voir la candidature</a></div>')
    return (
        f'<div style="{top}">'
        f'<div style="font-weight:700;color:{INK};font-size:15px;">'
        f'Contrat #{esc(c.get("contrat_id_ctr"))} — fin le {fr(c.get("date_fin_contrat"))}</div>'
        f'<div style="font-size:12px;color:{MUTE};margin:1px 0 8px;">'
        f'{int(c.get("duree_mois") or 0)} mois{recond_txt} · candidature #{esc(cid)}</div>'
        f'{cand}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;border:1px solid {RULE};table-layout:fixed;">'
        f'<tr class="ct-head">'
        f'<th style="{th}width:29%;">PASS IAE</th>'
        f'<th style="{th}{sep}width:23%;">Suivi interne</th>'
        f'<th style="{th}{sep}width:48%;">Prescripteur habilité</th>'
        f'</tr><tr class="ct-tr">'
        f'<td class="ct-td" style="{td}">{lbl("PASS IAE")}{_pass_cell(c)}</td>'
        f'<td class="ct-td" style="{td}{sep}">{lbl("Suivi interne")}{_suivi_cell(c)}</td>'
        f'<td class="ct-td" style="{td}{sep}">{lbl("Prescripteur habilité")}{_presc_cell(c)}</td>'
        f'</tr></table>'
        f'</div>')


def _segment_card(seg):
    label, color, bg = _URGENCE.get(seg.get("urgence"), _URGENCE["normale"])
    n = seg.get("nb_contrats", len(seg.get("contrats", [])))
    aide = ""
    if seg.get("lien_aide"):
        aide = (f'<div style="margin:2px 0 12px;">'
                f'<a href="{esc(seg["lien_aide"])}" style="display:inline-block;padding:9px 16px;'
                f'background:{BLUE};color:#fff;text-decoration:none;border-radius:4px;'
                f'font-size:14px;font-weight:700;">En savoir plus</a></div>')
    contrats = "".join(_contract_block(c, i == 0) for i, c in enumerate(seg.get("contrats", [])))
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 18px;border:1px solid {RULE};border-left:5px solid {color};">'
        f'<tr><td style="background:{bg};padding:12px 18px;">'
        f'<div style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase;'
        f'letter-spacing:.05em;">{esc(label)} · {n} contrat{"s" if n > 1 else ""}</div>'
        f'<div style="font-size:18px;font-weight:700;color:{INK};margin-top:3px;">'
        f'{esc(re.sub(r"^À traiter\s*—\s*", "", seg.get("action") or ""))}</div>'
        f'</td></tr>'
        f'<tr><td style="background:#ffffff;padding:14px 18px 16px;">'
        f'<p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:{MUTE};">{esc(seg.get("description"))}</p>'
        f'{aide}{contrats}</td></tr></table>')


def render(doc):
    st = doc["structure"]
    nom = clean_nom(st.get("nom"))
    segs = sorted(doc.get("sections", []), key=lambda s: (_RANK.get(s.get("urgence"), 9)))
    cards = "".join(_segment_card(s) for s in segs)
    intro = (f"Bonjour,<br>Votre structure <strong>{esc(nom)}</strong> ({esc(st.get('type'))}) compte "
             f"<strong>{doc.get('nb_contrats_total')} contrats IAE</strong> arrivant à échéance en "
             f"septembre 2026. Voici, <strong>par type d'action à mener</strong>, la marche à suivre "
             f"pour chacun — du plus urgent au moins urgent.")
    summ = " · ".join(f'{s.get("nb_contrats")} {_URGENCE.get(s.get("urgence"),["",""])[0].lower()}'
                      for s in segs)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(doc['objet'])}</title>
<style>
{STACK_TABLE_CSS}
</style></head>
<body style="margin:0;padding:0;background:#eaf1fb;font-family:{FONT};color:{INK};">
{"".join(f'<!-- to: {esc(d["email"])} -->' for d in doc.get("destinataires", []))}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf1fb;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="{_W}" cellpadding="0" cellspacing="0" style="max-width:{_W}px;width:100%;">
<tr><td style="background:#fff;border-top:5px solid {ORANGE};padding:26px 30px 4px;">
<img src="{LOGO_URL}" alt="La Plateforme de l’inclusion" width="210" style="display:block;max-width:210px;height:auto;border:0;">
</td></tr>
<tr><td style="background:#fff;padding:14px 30px 6px;">
<div style="color:{ORANGE};font-size:22px;font-weight:800;line-height:1.3;">{esc(doc['objet'])}</div>
<div style="color:{MUTE};font-size:13px;margin-top:6px;">{esc(st.get('adresse'))}</div>
</td></tr>
<tr><td style="background:#fff;padding:10px 30px 22px;">
<p style="margin:0;font-size:15px;line-height:1.55;color:{INK};">{intro}</p>
<div style="margin-top:12px;padding:10px 14px;background:{TINT};font-size:13px;color:{INK};">
<strong>{doc.get('nb_contrats_total')} contrats</strong> répartis en {len(segs)} actions : {esc(summ)}</div>
</td></tr>
<tr><td style="padding:20px 0 0;">{cards}</td></tr>
<tr><td style="padding:10px 0 4px;">
{avis_encart()}</td></tr>
<tr><td style="border-top:1px solid {RULE};padding:16px 0 0;">
<p style="margin:0;font-size:12px;line-height:1.55;color:{MUTE};">
Données issues des contrats déclarés (flux IAE / ASP) et des candidatures acceptées sur Les Emplois de l'inclusion.
Le statut du PASS IAE et le contact prescripteur sont donnés à titre indicatif — à vérifier avant toute démarche.</p>
</td></tr>
</table></td></tr></table></body></html>"""


def run_render(in_path="out/structure/exemple.json", out_path="out/structure/exemple.html"):
    doc = json.loads(Path(in_path).read_text(encoding="utf-8"))
    Path(out_path).write_text(render(doc), encoding="utf-8")
    print(f"écrit : {out_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    run_render(*args) if args else run_render()
