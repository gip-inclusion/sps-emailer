import json
import re
from pathlib import Path

from sps.convert_sections import parse_sections
from sps.schema import validate_email

_DASH = "─"

def _iso_date(fr):
    fr = fr.strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", fr)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None

def _split_list(value):
    value = value.strip()
    if value in ("", "—"):
        return []
    parts = re.split(r"\s*·\s*|\s*,\s*", value)
    return [p.strip().lstrip("⚪").strip() for p in parts if p.strip()]

def _none_if_dash(value):
    value = value.strip()
    return None if value in ("", "—") else value

def split_conseiller_blocks(text):
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("POUR :")]
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        yield "\n".join(lines[start:end])

def parse_conseiller_header(block):
    lines = block.splitlines()
    pour = lines[0]
    m = re.match(r"POUR :\s*(\S+)\s*-\s*(.+?)\s*$", pour)
    ref, nom = (m.group(1), m.group(2)) if m else ("", "")
    email = ""
    objet = ""
    for l in lines[1:]:
        if l.startswith("EMAIL :"):
            email = l.split(":", 1)[1].strip()
        elif l.startswith("Objet :"):
            objet = l.split(":", 1)[1].strip()
            break
    return {"ref": ref, "nom": nom, "email": email, "agence": None}, objet

_BENEF_HEADER = re.compile(
    r"Bénéficiaire #(\d+)\s*\|\s*DE #(\S+)\s*\|\s*(\d+)\s*ans\s*\|\s*"
    r"(\d{5})\s+([^|]+?)\s*\|\s*Dernier entretien\s*:\s*([^|]+?)\s*\|\s*"
    r"Convocation\s*:\s*(\d{2}/\d{2}/\d{4})\s*à\s*(\d{2}:\d{2})")

def _parse_meta(meta_lines):
    meta = {"profil": [], "axes": [], "rome": None, "freins": [], "objectif": None}
    for l in meta_lines:
        if l.startswith("Profil"):
            meta["profil"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("Axe"):
            meta["axes"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("ROME"):
            v = _none_if_dash(l.split(":", 1)[1])
            if v and v != "PROJET À DÉFINIR":
                m = re.match(r"([A-Z]\d{4})\s*[—-]\s*(.+)", v)
                meta["rome"] = {"code": m.group(1), "label": m.group(2).strip()} if m \
                    else {"code": v, "label": None}
        elif l.startswith("Freins"):
            meta["freins"] = _split_list(l.split(":", 1)[1])
        elif l.startswith("Objectif"):
            meta["objectif"] = _none_if_dash(l.split(":", 1)[1])
    return meta

def split_beneficiary_blocks(block):
    lines = block.splitlines()
    idxs = [i for i, l in enumerate(lines) if l.lstrip().startswith("Bénéficiaire #")]
    result = []
    for k, start in enumerate(idxs):
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        seg = lines[start:end]
        header = seg[0]
        meta, body, in_meta = [], [], True
        for l in seg[1:]:
            if in_meta and l.strip().startswith(_DASH):
                in_meta = False
                continue
            (meta if in_meta else body).append(l)
        result.append((header, meta, body))
    return result

def parse_beneficiary(header, meta_lines, body_lines):
    m = _BENEF_HEADER.search(header)
    b = {
        "de_id": m.group(2), "index": int(m.group(1)), "nom": None,
        "age": int(m.group(3)), "cp": m.group(4), "commune": m.group(5).strip(),
        "dernier_entretien": _iso_date(m.group(6)),
        "convocation": {"date": _iso_date(m.group(7)), "heure": m.group(8)},
        "avis_url": None, "groupes": [],
    }
    b.update(_parse_meta(meta_lines))
    b["avis_url"], b["groupes"] = parse_sections(body_lines)
    return b

def parse_md(text):
    docs = []
    for block in split_conseiller_blocks(text):
        conseiller, objet = parse_conseiller_header(block)
        benefs = [parse_beneficiary(h, m, b)
                  for (h, m, b) in split_beneficiary_blocks(block)]
        intro, remarques = _parse_intro_remarques(block)
        docs.append({"conseiller": conseiller, "objet": objet,
                     "intro": intro, "remarques": remarques,
                     "beneficiaires": benefs})
    return docs

def _parse_intro_remarques(block):
    lines = block.splitlines()
    intro_parts, remarques = [], []
    state = None
    for l in lines:
        if l.startswith("Objet :"):
            state = "intro"; continue
        if l.startswith("REMARQUES IMPORTANTES"):
            state = "remarques"; continue
        if l.strip().startswith(_DASH):
            break
        if state == "intro" and l.strip():
            intro_parts.append(l.strip())
        elif state == "remarques":
            s = l.strip().lstrip("•").strip()
            if s:
                remarques.append(s)
    intro = " ".join(intro_parts).strip() or None
    return intro, (remarques or None)

def run_convert(md_path, out_dir):
    text = Path(md_path).read_text(encoding="utf-8")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    docs = parse_md(text)
    written, total_benefs = 0, 0
    for doc in docs:
        validate_email(doc)  # fail loudly on contract drift before writing
        ref = doc["conseiller"]["ref"] or f"conseiller-{written+1}"
        (out / f"{ref}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
        total_benefs += len(doc["beneficiaires"])
    print(f"convert: {written} conseiller(s), {total_benefs} bénéficiaire(s) → {out}")
