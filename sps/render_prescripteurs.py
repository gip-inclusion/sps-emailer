"""Rendu de l'e-mail « fins de contrats — vue PRESCRIPTEUR ».

Reproduit le gabarit de référence fourni (sps-emailer-preview-prescripteur.html) : un e-mail par
**conseiller prescripteur**, ses candidatures regroupées par **structure IAE employeuse** (groupe),
puis par **accompagnateur** (section) et par **légende** (1ers contrats / renouvelés).

Schéma d'entrée = LISTE de conseillers ; chaque élément :
  conseiller {ref, nom, email, agence}, objet, intro, remarques, footer_questionnaire,
  autres_destinataires[], groupes[] où chaque groupe = { titre ("NOM (TYPE) — N contrats —
  adresse"), structure_email, before_block (alerte PASS, markdown|null), admin_emails_siae[],
  sections[] { type, accompagnateur_nom/email, contact_url, contact_label, sub_sections[]
  { legende, items[] { nom, pass_note, prescripteur_nom/email, url, cta_label } } } }.

Lancer :
  uv run python -m sps.render_prescripteurs                 # aperçu du 1er conseiller -> preview.html
  uv run python -m sps.render_prescripteurs <in.json> --preview [i]
  uv run python -m sps.render_prescripteurs <in.json> --all [out_dir]   # 1 HTML par conseiller
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from sps.charte import esc

# webhook n8n de contact groupé (même format que les contact_url pré-calculés du JSON)
_WEBHOOK_SUBJECT = "Contrats%20IAE%20arrivant%20%C3%A0%20%C3%A9ch%C3%A9ance"

_DEFAULT_IN = "/Users/elodiedelaisement/Desktop/sps-emailer-prescripteurs-sept2026.json"
# Sous-dossier dédié à CETTE campagne (isolé de l'ancienne campagne 579 dans le dossier parent).
_OUT_DIR = "out/Prescripteurs-fins-contrats/sept2026"

_STYLE = """  body { font-family: 'Marianne', Arial, sans-serif; margin: 0; padding: 0; background: #f5f5fe; color: #161616; }
  .wrapper { max-width: 680px; margin: 0 auto; background: #fff; }
  .body { padding: 24px 32px; }
  .intro { font-size: 15px; line-height: 1.6; margin-bottom: 24px; color: #3a3a3a; }
  .groupe { margin-bottom: 28px; border: 1px solid #e5e5e5; border-radius: 8px; overflow: hidden; }
  .groupe-header { background: #f5f5fe; padding: 14px 18px; border-bottom: 1px solid #e5e5e5; }
  .groupe-header h2 { font-size: 14px; font-weight: 700; margin: 0; color: #000091; }
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
  .item-pass.warn { color: #c45f00; font-weight: 500; }
  .item-presc { font-size: 11px; color: #aaa; margin-top: 2px; font-style: italic; }
  .item-cta { margin-top: 6px; }
  .item-cta a { display: inline-block; font-size: 12px; font-weight: 600; color: #000091; border: 1px solid #000091; padding: 4px 14px; border-radius: 4px; text-decoration: none; }
  .item-cta a:hover { background: #000091; color: #fff; }
  .footer { background: #FFF0E5; padding: 20px 32px; text-align: center; border-top: 1px solid #e5e5e5; }
  .footer p { font-size: 14px; color: #3a3a3a; font-weight: 600; margin: 0 0 12px; }
  .footer .btn { display: inline-block; background: #E57200; color: #fff; text-decoration: none; padding: 10px 24px; border-radius: 4px; font-size: 14px; font-weight: 600; }
  .footer .btn:hover { background: #c45f00; }
  .legal { padding: 16px 32px; font-size: 11px; color: #999; text-align: center; background: #f9f9f9; }"""


def _md_bold(text):
    """Échappe puis convertit le gras markdown **…** en <strong> (seul markdown utilisé ici)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


def _split_titre(titre):
    """'NOM (TYPE) — N contrats — adresse' -> (h2, meta) ; robuste si l'adresse manque."""
    parts = [p.strip() for p in (titre or "").split(" — ")]
    h2 = parts[0] if parts else ""
    if len(parts) >= 3:
        count, adresse = parts[1], " — ".join(parts[2:])
        meta = f"📍 {adresse} — {count}"
    elif len(parts) == 2:
        meta = parts[1]
    else:
        meta = ""
    return h2, meta


def _alert(g):
    bb = g.get("before_block")
    if not bb or not bb.get("content"):
        return ""
    content = _md_bold(bb["content"]) if bb.get("format") == "markdown" else esc(bb["content"])
    return f'      <div class="alert-block">⚠️ {content}</div>\n'


def _item(it):
    pn = it.get("pass_note") or ""
    urgent = " urgent" if "🔴" in pn else (" warn" if "🟠" in pn else "")
    presc = ""
    if it.get("prescripteur_nom"):
        presc = f'          <div class="item-presc">Prescripteur : {esc(it["prescripteur_nom"])}</div>\n'
    cta = ""
    if it.get("url"):
        cta = (f'          <div class="item-cta"><a href="{esc(it["url"])}">'
               f'{esc(it.get("cta_label") or "Voir la candidature")}</a></div>\n')
    return (
        f'        <div class="item">\n'
        f'          <div class="item-date">{esc(it.get("nom"))}</div>\n'
        f'          <div class="item-pass{urgent}">{esc(pn)}</div>\n'
        f'{presc}{cta}'
        f'        </div>\n')


def _structure_emails(g):
    """Tous les e-mails connus du groupe (accompagnateurs des sections, admins SIAE, e-mail
    structure), dédupliqués — pour le repli « Contacter la structure » quand une section n'a
    pas de contact_url (accompagnateur inconnu)."""
    em = [s.get("accompagnateur_email") for s in g.get("sections", []) if s.get("accompagnateur_email")]
    em += g.get("admin_emails_siae") or []
    if g.get("structure_email"):
        em.append(g["structure_email"])
    return list(dict.fromkeys(em))


def _webhook(emails):
    mail = quote(",".join(emails), safe="")
    return f"https://n8n.inclusion.beta.gouv.fr/webhook/mailto?mail={mail}&subject={_WEBHOOK_SUBJECT}&type=presc"


def _acc_block(sec, g):
    nom = sec.get("accompagnateur_nom")
    if nom:
        name_html = f'<span class="acc-name">👤 {esc(nom)}</span>'
    else:
        name_html = '<span class="acc-name" style="color:#888;">Non identifié</span>'
    url = sec.get("contact_url")
    label = sec.get("contact_label")
    if not url:  # repli : contacter la structure via ses e-mails connus (comme l'exemple ITER)
        se = _structure_emails(g)
        if se:
            url, label = _webhook(se), (label or "Contacter la structure")
    cta = ""
    if url:
        cta = (f'          <div class="acc-cta"><a href="{esc(url)}">'
               f'{esc(label or "Contacter la structure")}</a></div>\n')
    subs = []
    for ss in sec.get("sub_sections", []):
        subs.append(f'        <div class="sub-title">{esc(ss.get("legende"))}</div>\n')
        subs.extend(_item(it) for it in ss.get("items", []))
    return (
        f'      <div class="acc-block">\n'
        f'        <div class="acc-header">\n'
        f'          <div class="acc-left">\n'
        f'            <div class="acc-label">Accompagnateur</div>\n'
        f'            {name_html}\n'
        f'          </div>\n'
        f'{cta}'
        f'        </div>\n'
        f'{"".join(subs)}'
        f'      </div>\n')


def _groupe(g):
    h2, meta = _split_titre(g.get("titre"))
    accs = "".join(_acc_block(s, g) for s in g.get("sections", []))
    return (
        f'    <div class="groupe">\n'
        f'      <div class="groupe-header">\n'
        f'        <h2>{esc(h2)}</h2>\n'
        f'        <div class="meta">{esc(meta)}</div>\n'
        f'      </div>\n'
        f'{_alert(g)}'
        f'{accs}'
        f'    </div>\n')


def _avis_link(lien):
    """Force le paramètre email du lien avis à {{ params.EMAIL }} (substitué par Brevo au vrai
    destinataire de chaque copie) au lieu de l'e-mail pré-calculé du conseiller principal."""
    lien = lien or "https://tally.so/r/Y5Bkrv"
    if "email=" in lien:
        return re.sub(r"([?&]email=)[^&]*", r"\1{{ params.EMAIL }}", lien)
    return lien + ("&" if "?" in lien else "?") + "email={{ params.EMAIL }}"


def render(e):
    intro = esc(e.get("intro") or "").replace("\n\n", "<br><br>").replace("\n", "<br>")
    groupes = "".join(_groupe(g) for g in e.get("groupes", []))
    foot = e.get("footer_questionnaire") or {}
    tos = [e["conseiller"]["email"]] if e.get("conseiller", {}).get("email") else []
    tos += [d["email"] for d in e.get("autres_destinataires", []) if d.get("email")]
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

{groupes}  </div>

  <div class="footer">
    <p>{esc(foot.get('texte') or 'Cet email vous a été utile ? Donnez-nous votre avis en 2 minutes.')}</p>
    <a class="btn" href="{esc(_avis_link(foot.get('lien')))}">{esc(foot.get('label_bouton') or 'Donner mon avis')}</a>
  </div>

  <div class="legal">
    Cet email a été envoyé automatiquement par les emplois de l'inclusion.<br>
    Vous le recevez car vous êtes prescripteur habilité sur la plateforme.
  </div>

</div>
</body>
</html>"""


def _load(in_path):
    return json.loads(Path(in_path).read_text(encoding="utf-8"))


def run_preview(in_path=_DEFAULT_IN, idx=0, out_path=f"{_OUT_DIR}/preview.html"):
    e = _load(in_path)[int(idx)]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(render(e), encoding="utf-8")
    c = e.get("conseiller", {})
    print(f"aperçu : {out_path}  (conseiller {c.get('agence')} — {c.get('nom')}, {len(e.get('groupes',[]))} structures)")


def run_all(in_path=_DEFAULT_IN, out_dir=f"{_OUT_DIR}/html"):
    data = _load(in_path)
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    for i, e in enumerate(data):
        ref = (e.get("conseiller") or {}).get("ref") or "sans-ref"
        (d / f"{i:04d}_{ref}.html").write_text(render(e), encoding="utf-8")  # index = nom unique
    print(f"écrit : {len(data)} e-mails dans {out_dir}/")


if __name__ == "__main__":
    a = sys.argv[1:]
    in_path = a[0] if a and not a[0].startswith("--") else _DEFAULT_IN
    if "--all" in a:
        i = a.index("--all")
        run_all(in_path, a[i + 1] if len(a) > i + 1 else f"{_OUT_DIR}/html")
    elif "--preview" in a:
        i = a.index("--preview")
        run_preview(in_path, a[i + 1] if len(a) > i + 1 else 0)
    else:
        run_preview(in_path)
