import json
import re
from pathlib import Path
from sps.template import (render_richblock, tension_badge, default_intro,
                          DEFAULT_REMARQUES, esc)

_CTA_BY_DOMAIN = [
    ("emplois.inclusion", "Voir la structure (Les Emplois)"),
    ("dora.inclusion", "Voir le service sur Dora"),
    ("agefiph.fr", "Voir l'aide (Agefiph)"),
    ("societenumerique", "Voir le service"),
    ("tally.so", "Donner mon avis"),
]

# type de section -> emoji de tête (légende), reproduit le repère visuel du MD
_SECTION_EMOJI = {
    "best_service": "🏆", "structures_iae": "✅", "formation": "📚",
    "dispositif": "🎯", "eligibilite": "✅", "aucune_action": "⚠",
}

# couleurs récurrentes
_INK = "#0f172a"
_MUTE = "#5b6776"
_LINK = "#1d4ed8"

# espaceur vertical uniforme entre blocs de premier niveau
_SPACER = '<tr><td style="font-size:0;line-height:0;height:24px;">&nbsp;</td></tr>'

def _cta_label(url):
    for needle, label in _CTA_BY_DOMAIN:
        if needle in (url or ""):
            return label
    return "Voir la solution"

def _beneficiary_title(b):
    return esc(b["nom"]) if b.get("nom") else f"Bénéficiaire #{b['index']}"

def _avatar(b):
    if b.get("nom"):
        parts = [p for p in b["nom"].split() if p]
        txt = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
    else:
        txt = str(b.get("index", "?"))
    return esc(txt)

def _fr_date(iso):
    if not iso:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else iso

def _cta(it):
    url = it.get("url")
    label = it.get("cta_label") or _cta_label(url)
    return (f'<a href="{esc(url)}" style="display:inline-block;margin:10px 0 2px;'
            f'padding:8px 14px;background:#eff6ff;color:{_LINK};text-decoration:none;'
            f'border-radius:7px;font-size:14px;font-weight:600;border:1px solid #dbeafe;">'
            f'{esc(label)} ↗</a>')

def _detail(text):
    return (f'<div style="font-size:14px;color:{_MUTE};line-height:1.55;margin:2px 0;">'
            f'{text}</div>')

def _contacts(it):
    """tel + e-mail sur une seule ligne, séparés par « · », avec marge haut/bas."""
    bits = []
    if it.get("telephone"):
        bits.append(f'<a href="tel:{esc(it["telephone"])}" style="color:{_LINK};'
                    f'text-decoration:none;">{esc(it["telephone"])}</a>')
    if it.get("email"):
        bits.append(f'<a href="mailto:{esc(it["email"])}" style="color:{_LINK};'
                    f'text-decoration:none;">{esc(it["email"])}</a>')
    if not bits:
        return ""
    return (f'<div style="font-size:14px;color:{_MUTE};line-height:1.55;margin:6px 0;">'
            f'{" &nbsp;·&nbsp; ".join(bits)}</div>')

def _item_inner(it, stype):
    out = []
    if stype == "best_service":
        contrainte = esc(it.get("note")) if it.get("note") else ""
        service = esc(it.get("nom"))
        head = f'{contrainte} → {service}' if contrainte else service
        out.append(f'<div style="font-weight:700;color:{_INK};font-size:16px;'
                   f'margin:0 0 4px;line-height:1.45;">'
                   f'<span style="color:#94a3b8;">●</span> {head}</div>')
        if it.get("adresse"):
            out.append(_detail(esc(it["adresse"])))
        if it.get("remote"):
            out.append(_detail("À distance"))
    else:
        prefix = f'[{esc(it["type_struct"])}] ' if it.get("type_struct") else ""
        loc = ""
        if it.get("adresse"):
            loc += f' | {esc(it["adresse"])}'
        if it.get("remote"):
            loc += ' · À distance'
        elif it.get("distance_km") is not None:
            loc += f' ({it["distance_km"]} km)'
        out.append(f'<div style="font-weight:700;color:{_INK};font-size:16px;'
                   f'margin:0 0 3px;line-height:1.45;">{prefix}{esc(it.get("nom"))}{loc}</div>')
        badge = tension_badge(it.get("tension"))
        if badge:
            out.append(f'<div style="margin:0 0 5px;">{badge}</div>')
        if it.get("note"):
            out.append(_detail(esc(it["note"])))
    out.append(_contacts(it))
    if it.get("url"):
        out.append(_cta(it))
    return "".join(out)

def _render_items(items, stype):
    parts = []
    for i, it in enumerate(items):
        inner = _item_inner(it, stype)
        if i == 0:
            parts.append(f'<div>{inner}</div>')
        else:
            parts.append(f'<div style="margin-top:18px;padding-top:16px;'
                         f'border-top:1px solid #eef2f6;">{inner}</div>')
    return "".join(parts)

def _section_band(stype, legende, first=True):
    """Bandeau de sous-titre, autre couleur, séparé du corps. Gap avant si pas en tête de bloc."""
    emoji = _SECTION_EMOJI.get(stype, "")
    label = f'{emoji} {esc(legende)}'.strip()
    mt = "" if first else "margin-top:14px;"
    return (f'<div style="{mt}background:#eef4ff;border-top:1px solid #dbeafe;'
            f'border-bottom:1px solid #dbeafe;padding:9px 18px;font-size:13px;'
            f'font-weight:700;color:#1e3a8a;line-height:1.4;">{label}</div>')

def _render_section(s, first=True):
    """Retourne (bandeau de sous-titre) + (corps). Le corps vide est collapsé (pas de boîte vide)."""
    stype = s.get("type", "")
    band = _section_band(stype, s["legende"], first) if s.get("legende") else ""
    body = [render_richblock(s.get("before_block")),
            _render_items(s.get("items", []), stype)]
    if s.get("aside"):
        body.append(f'<div style="margin:16px 0 4px;padding:14px 16px;background:#eef2ff;'
                    f'border:1px solid #c7d2fe;border-radius:11px;color:#3730a3;'
                    f'font-size:14px;line-height:1.6;">{render_richblock(s["aside"])}</div>')
    if s.get("alternatives"):
        body.append('<div style="margin:16px 0 4px;font-weight:700;color:#334155;'
                    'font-size:15px;">Alternatives les moins sollicitées à proximité :</div>')
        body.append(_render_items(s["alternatives"], stype))
    body.append(render_richblock(s.get("after_block")))
    inner = "".join(p for p in body if p)
    body_html = f'<div style="padding:16px 18px;">{inner}</div>' if inner.strip() else ""
    return band + body_html

def _render_group(g):
    sections = "".join(_render_section(s, first=(i == 0))
                       for i, s in enumerate(g.get("sections", [])))
    pre = render_richblock(g.get("before_block"))
    post = render_richblock(g.get("after_block"))
    pre_html = f'<div style="padding:14px 18px 0;">{pre}</div>' if pre else ""
    post_html = f'<div style="padding:0 18px 14px;">{post}</div>' if post else ""
    return (f'<div style="margin:0 0 16px;border:1px solid #e2e8f0;border-radius:12px;'
            f'overflow:hidden;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,0.05);">'
            f'<div style="background:#1e3a8a;padding:13px 18px;">'
            f'<div style="color:#fff;font-weight:800;font-size:15px;text-transform:uppercase;'
            f'letter-spacing:0.05em;line-height:1.3;">{esc(g["titre"])}</div></div>'
            f'{pre_html}{sections}{post_html}</div>')

def _meta_line(label, value):
    return (f'<div style="font-size:14px;color:#334155;margin:4px 0;line-height:1.55;">'
            f'<strong style="color:#0f172a;">{label} :</strong> {value}</div>')

def _render_meta(b):
    rows = []
    if b.get("profil"):
        rows.append(_meta_line("Profil", esc(" · ".join(b["profil"]))))
    if b.get("axes"):
        rows.append(_meta_line("Axe", esc(" · ".join(b["axes"]))))
    if b.get("rome"):
        r = b["rome"]
        val = esc(r.get("code", "")) + (f' — {esc(r["label"])}' if r.get("label") else "")
        rows.append(_meta_line("ROME", val))
    if b.get("freins"):
        chips = "".join(
            f'<span style="display:inline-block;background:#eef2f6;color:#334155;'
            f'border-radius:6px;padding:2px 9px;font-size:13px;margin:2px 5px 2px 0;">'
            f'{esc(f)}</span>' for f in b["freins"])
        rows.append(f'<div style="font-size:14px;color:#334155;margin:5px 0;'
                    f'line-height:1.6;"><strong style="color:#0f172a;">Freins :</strong> '
                    f'{chips}</div>')
    if not rows:
        return ""
    return f'<div style="padding:14px 18px 2px;">{"".join(rows)}</div>'

def _render_beneficiary(b):
    title = _beneficiary_title(b)
    sub = " · ".join(x for x in [f'{b["age"]} ans' if b.get("age") else "",
                                 f'{esc(b.get("cp") or "")} {esc(b.get("commune") or "")}'.strip()]
                     if x)
    conv = b.get("convocation") or {}
    conv_bits = []
    if conv.get("date"):
        conv_bits.append(f'<span style="font-weight:700;color:#0369a1;">'
                         f'📅 Convocation : {_fr_date(conv.get("date"))}'
                         + (f' à {esc(conv.get("heure"))}' if conv.get("heure") else "") + '</span>')
    if b.get("dernier_entretien"):
        conv_bits.append(f'<span style="color:#64748b;">Dernier entretien : '
                         f'{_fr_date(b["dernier_entretien"])}</span>')
    conv_bar = ""
    if conv_bits:
        conv_bar = (f'<div style="padding:11px 18px;background:#f1f5f9;'
                    f'border-bottom:1px solid #e2e8f0;font-size:14px;">'
                    f'{" &nbsp;·&nbsp; ".join(conv_bits)}</div>')
    # avis : remonté sous les titres, centré
    avis = ""
    if b.get("avis_url"):
        avis = (f'<div style="padding:12px 18px 12px;text-align:center;">'
                f'<a href="{esc(b["avis_url"])}" style="color:{_LINK};font-size:14px;'
                f'font-weight:600;text-decoration:underline;">'
                f'📋 Donner votre avis sur ces solutions (1 min)</a></div>')
    groups = "".join(_render_group(g) for g in b.get("groupes", []))
    anchor = f'<a name="de-{b["index"]}"></a><a id="de-{b["index"]}"></a>'
    return (
        f'{anchor}<div class="panel" style="margin:0;background:#fff;border-radius:14px;'
        f'overflow:hidden;border:1px solid #e9eef3;box-shadow:0 4px 14px rgba(15,23,42,0.10);">'
        f'<div style="background:#0f172a;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="50" valign="middle" style="padding:16px 0 16px 18px;">'
        f'<div style="width:44px;height:44px;border-radius:50%;background:#1d4ed8;color:#fff;'
        f'font-weight:700;font-size:17px;text-align:center;line-height:44px;">{_avatar(b)}</div>'
        f'</td><td valign="middle" style="padding:14px 18px;">'
        f'<div style="color:#fff;font-weight:800;font-size:20px;line-height:1.2;">{title}</div>'
        f'<div style="color:#cbd5e1;font-size:14px;margin-top:3px;">{esc(sub)}</div>'
        f'</td></tr></table></div>'
        f'{conv_bar}{_render_meta(b)}{avis}'
        f'<div style="padding:2px 18px 4px;">{groups}</div></div>'
    )

def _toc(beneficiaires):
    if len(beneficiaires) <= 1:
        return ""
    items = "".join(
        f'<li style="margin:3px 0;"><a href="#de-{b["index"]}" style="color:#1d4ed8;'
        f'text-decoration:none;">{_beneficiary_title(b)}'
        + (f' — {esc(b.get("commune") or "")}' if b.get("commune") else "") + '</a></li>'
        for b in beneficiaires)
    return (f'<tr><td><div class="toccard" style="background:#fff;'
            f'border-radius:14px;border:1px solid #e9eef3;box-shadow:0 1px 3px rgba(15,23,42,0.06);'
            f'padding:16px 22px;">'
            f'<div style="font-size:14px;font-weight:700;color:#334155;margin-bottom:6px;">'
            f'Accès rapide</div>'
            f'<ul style="margin:0;padding-left:18px;font-size:15px;color:#334155;">{items}</ul>'
            f'</div></td></tr>')

def render_doc(doc):
    c = doc["conseiller"]
    intro = doc.get("intro") or default_intro(c)
    remarques = doc.get("remarques") or DEFAULT_REMARQUES
    rem_html = "<br>".join(esc(r) for r in remarques)
    benefs_list = doc.get("beneficiaires", [])
    toc = _toc(benefs_list)

    # blocs de premier niveau, espacés uniformément par des lignes-espaceuses 24px
    rows = [
        f'<tr><td class="topcard" style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 14px rgba(15,23,42,0.08);">'
        f'<div style="background:linear-gradient(135deg,#1e3a8a,#1d4ed8);padding:28px 30px;">'
        f'<div style="color:#bfdbfe;font-size:13px;font-weight:700;letter-spacing:0.04em;">Recommandations structures IAE · Portefeuille {esc(c["ref"])}</div>'
        f'<div style="color:#ffffff;font-size:23px;font-weight:800;margin-top:7px;line-height:1.3;">{esc(doc["objet"])}</div>'
        f'</div>'
        f'<div style="padding:22px 30px;"><p style="font-size:15px;color:#334155;line-height:1.65;margin:0;">{intro}</p></div>'
        f'</td></tr>'
    ]
    if toc:
        rows.append(toc)
    for b in benefs_list:
        rows.append(f'<tr><td>{_render_beneficiary(b)}</td></tr>')
    rows.append(
        f'<tr><td style="padding:4px 30px 8px;">'
        f'<p style="font-size:13px;color:#94a3b8;line-height:1.55;margin:0;text-align:center;">{rem_html}</p>'
        f'</td></tr>'
    )
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
  .panel, .topcard, .toccard {{ border-radius:0 !important; border-left:0 !important; border-right:0 !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;color:#1e293b;">
<!-- to: {esc(c["email"])} -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#e2e8f0;">
<tr><td class="gutter" align="center" style="padding:24px 12px;">
<table role="presentation" width="700" cellpadding="0" cellspacing="0" style="max-width:700px;width:100%;">
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
        (out / f'{fp.stem}.html').write_text(render_doc(doc), encoding="utf-8")
    print(f"render: {len(files)} HTML écrit(s) → {out}")
