"""Rendu de l'e-mail « fins de contrats — vue SIAE » (adressé à la structure employeuse).

Décliné du gabarit prescripteur, mais groupé **par prescripteur** (orienteur / prescripteur
habilité / auto-prescription / candidature spontanée / autre) : chaque groupe = un prescripteur,
avec ses « positionné par » (personnes) et leurs contrats. Reproduit le gabarit de référence
sps-emailer-preview.html.

Schéma d'entrée = LISTE de structures ; chaque élément :
  structure {nom, type, …}, objet, nb_contrats_total, intro, destinataires[],
  show_accompagnateur (bool), footer_questionnaire, legal, groupes[] où chaque groupe =
  { type_label, nom_org, nb_contrats, has_cta, btn_label, urgent_count, positionne_par[]
  { nom, email, webhook_url, sous_sections[] { label, contrats[] { date_display, pass_display,
  pass_urgent, lien_candidature, accompagnateur?, positionne_par? } } } }.

Lancer :
  uv run python -m sps.render_siae                  # aperçu (ISCRA si présent) -> preview.html
  uv run python -m sps.render_siae <in.json> --preview [i]
  uv run python -m sps.render_siae <in.json> --all [out_dir]
"""
import json
import re
import sys
from pathlib import Path

from sps.charte import esc

_DEFAULT_IN = "/Users/elodiedelaisement/Desktop/sps-emailer-siae-final.json"
_OUT_DIR = "out/SIAE-fins-contrats/sept2026"

_STYLE = """  body { font-family: 'Marianne', Arial, sans-serif; margin: 0; padding: 0; background: #f5f5fe; color: #161616; }
  .wrapper { max-width: 680px; margin: 0 auto; background: #fff; }
  .body { padding: 24px 32px; }
  .intro { font-size: 15px; line-height: 1.6; margin-bottom: 24px; color: #3a3a3a; }
  .groupe { margin-bottom: 28px; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }
  .groupe-header { background: #f5f5fe; padding: 14px 18px; border-bottom: 1px solid #e5e5e5; }
  .groupe-header .gh-type { font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; color: #666; font-weight: 600; }
  .groupe-header h2 { font-size: 14px; font-weight: 700; margin: 2px 0 0; color: #000091; }
  .groupe-header .meta { font-size: 12px; color: #666; margin-top: 3px; }
  .alert-block { padding: 10px 18px; background: #ffe9e6; border-bottom: 1px solid #e5e5e5; font-size: 13px; color: #ce0500; font-weight: 600; }
  .acc-block { border-top: 1px solid #e5e5e5; }
  .acc-header { padding: 10px 18px; background: #f0f0fe; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px; }
  .acc-header .acc-left { }
  .acc-header .acc-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; color: #666; }
  .acc-header .acc-name { font-size: 14px; font-weight: 700; color: #000091; }
  .acc-header .acc-cta a { display: inline-block; font-size: 12px; font-weight: 600; color: #fff; background: #000091; padding: 5px 14px; border-radius: 4px; text-decoration: none; }
  .acc-header .acc-cta a:hover { background: #1212ff; }
  .sub-title { font-size: 11px; font-weight: 600; color: #666; padding: 8px 18px 0; text-transform: uppercase; letter-spacing: 0.4px; }
  .item { padding: 10px 18px; border-top: 1px solid #f3f3f3; }
  .item-date { font-size: 13px; font-weight: 600; color: #161616; }
  .item-pass { font-size: 12px; color: #666; margin-top: 2px; }
  .item-pass.urgent { color: #ce0500; font-weight: 500; }
  .item-accomp { font-size: 11px; color: #aaa; margin-top: 2px; font-style: italic; }
  .item-cta { margin-top: 6px; }
  .item-cta a { display: inline-block; font-size: 12px; font-weight: 600; color: #000091; border: 1px solid #000091; padding: 4px 14px; border-radius: 4px; text-decoration: none; }
  .item-cta a:hover { background: #000091; color: #fff; }
  .footer { background: #FFF0E5; padding: 20px 32px; text-align: center; border-top: 1px solid #e5e5e5; }
  .footer p { font-size: 14px; color: #3a3a3a; font-weight: 600; margin: 0 0 12px; }
  .footer .btn { display: inline-block; background: #E57200; color: #fff; text-decoration: none; padding: 10px 24px; border-radius: 4px; font-size: 14px; font-weight: 600; }
  .footer .btn:hover { background: #c45f00; }
  .legal { padding: 16px 32px; font-size: 11px; color: #999; text-align: center; background: #f9f9f9; }"""


def _clean_nom(nom):
    return (nom or "").strip().strip('"').strip()


def _avis_link(lien):
    """Force/ajoute email={{ params.EMAIL }} (substitué par Brevo au destinataire), en gardant
    les autres paramètres (ex. type=siae-ACI)."""
    lien = lien or "https://tally.so/r/2E6Q8L"
    if "email=" in lien:
        return re.sub(r"([?&]email=)[^&]*", r"\1{{ params.EMAIL }}", lien)
    return lien + ("&" if "?" in lien else "?") + "email={{ params.EMAIL }}"


def _item(c, show_accompagnateur):
    urgent = " urgent" if c.get("pass_urgent") else ""
    accomp = ""
    if show_accompagnateur and c.get("accompagnateur"):
        accomp += f'<div class="item-accomp">Suivi par {esc(c["accompagnateur"])}</div>\n'
    if c.get("positionne_par"):
        accomp += f'<div class="item-accomp">Positionné par {esc(c["positionne_par"])}</div>\n'
    cta = ""
    if c.get("lien_candidature"):
        cta = f'<div class="item-cta"><a href="{esc(c["lien_candidature"])}">Voir la candidature</a></div>\n'
    return (
        f'<div class="item">\n'
        f'<div class="item-date">{esc(c.get("date_display"))}</div>\n'
        f'<div class="item-pass{urgent}">{esc(c.get("pass_display"))}</div>\n'
        f'{accomp}{cta}'
        f'</div>\n')


def _acc_block(p, g, show_accompagnateur):
    header = ""
    if g.get("has_cta"):
        cta = ""
        if p.get("webhook_url"):
            cta = (f'<div class="acc-cta"><a href="{esc(p["webhook_url"])}">'
                   f'{esc(g.get("btn_label") or "Contacter")}</a></div>\n')
        header = (
            f'<div class="acc-header">\n'
            f'<div class="acc-left">\n'
            f'<div class="acc-label">Positionné par</div>\n'
            f'<span class="acc-name">👤 {esc(p.get("nom"))}</span>\n'
            f'</div>\n'
            f'{cta}'
            f'</div>\n')
    body = []
    for ss in p.get("sous_sections", []):
        body.append(f'<div class="sub-title">{esc(ss.get("label"))}</div>\n')
        body.extend(_item(c, show_accompagnateur) for c in ss.get("contrats", []))
    return f'<div class="acc-block">\n{header}{"".join(body)}</div>\n'


def _alert(g):
    n = g.get("urgent_count") or 0
    if n <= 0:
        return ""
    s = "s" if n > 1 else ""
    return (f'<div class="alert-block">⚠️ {n} contrat{s} nécessitant une action '
            f'urgente sur le PASS IAE.</div>\n')


def _groupe(g, show_accompagnateur):
    n = g.get("nb_contrats", 0)
    meta = f'{n} contrat{"s" if n > 1 else ""}'
    accs = "".join(_acc_block(p, g, show_accompagnateur) for p in g.get("positionne_par", []))
    return (
        f'<div class="groupe">\n'
        f'<div class="groupe-header">\n'
        f'<div class="gh-type">{esc(g.get("type_label"))}</div>\n'
        f'<h2>{esc(g.get("nom_org"))}</h2>\n'
        f'<div class="meta">{meta}</div>\n'
        f'</div>\n'
        f'{_alert(g)}{accs}'
        f'</div>\n')


def render(e):
    st = e.get("structure") or {}
    nom = _clean_nom(st.get("nom"))
    nb = e.get("nb_contrats_total") or 0
    mot = "contrat" if nb == 1 else "contrats"
    verbe = "arrive" if nb == 1 else "arrivent"
    intro = (f"Bonjour,<br><br><strong>{nb} {mot} IAE</strong> {verbe} à échéance entre le 14 "
             f"et le 30 septembre 2026 au sein de votre structure <strong>{esc(nom)}</strong>.<br>"
             f"Retrouvez ci-dessous le détail par prescripteur, avec les actions à mener pour chaque situation.")
    groupes = "".join(_groupe(g, e.get("show_accompagnateur")) for g in e.get("groupes", []))
    foot = e.get("footer_questionnaire") or {}
    legal = esc(e.get("legal") or "").replace(" Vous le recevez", "<br>\nVous le recevez")
    tos = [d["email"] for d in e.get("destinataires", []) if d.get("email")]
    tos = list(dict.fromkeys(tos))
    to_comments = "".join(f'<!-- to: {esc(t)} -->\n' for t in tos)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(e.get('objet'))}</title>
<style>
{_STYLE}
</style>
</head>
<body>
{to_comments}<div class="wrapper">
<div class="body">
<p class="intro">{intro}</p>

{groupes}</div>
<div class="footer">
<p>{esc(foot.get('texte') or "Cet email vous a été utile ? Donnez-nous votre avis en 2 minutes pour nous aider à l'améliorer.")}</p>
<a class="btn" href="{esc(_avis_link(foot.get('lien')))}">{esc(foot.get('label_bouton') or 'Donner mon avis')}</a>
</div>
<div class="legal">
{legal}
</div>
</div></body></html>"""


def _load(in_path):
    return json.loads(Path(in_path).read_text(encoding="utf-8"))


def _find_iscra(data):
    for i, e in enumerate(data):
        if "ISCRA" in ((e.get("structure") or {}).get("nom") or ""):
            return i
    return 0


def run_preview(in_path=_DEFAULT_IN, idx=None, out_path=f"{_OUT_DIR}/preview.html"):
    data = _load(in_path)
    i = _find_iscra(data) if idx is None else int(idx)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(render(data[i]), encoding="utf-8")
    st = data[i].get("structure", {})
    print(f"aperçu : {out_path}  (idx {i} — {st.get('nom')}, {len(data[i].get('groupes',[]))} prescripteurs)")


def run_all(in_path=_DEFAULT_IN, out_dir=f"{_OUT_DIR}/html"):
    data = _load(in_path)
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    for i, e in enumerate(data):
        ref = (e.get("structure") or {}).get("id_structure_asp") or "sans-id"
        (d / f"{i:04d}_{ref}.html").write_text(render(e), encoding="utf-8")
    print(f"écrit : {len(data)} e-mails dans {out_dir}/")


if __name__ == "__main__":
    a = sys.argv[1:]
    in_path = a[0] if a and not a[0].startswith("--") else _DEFAULT_IN
    if "--all" in a:
        i = a.index("--all")
        run_all(in_path, a[i + 1] if len(a) > i + 1 else f"{_OUT_DIR}/html")
    elif "--preview" in a:
        i = a.index("--preview")
        run_preview(in_path, a[i + 1] if len(a) > i + 1 else None)
    else:
        run_preview(in_path)
