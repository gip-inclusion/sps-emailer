import csv, json
from pathlib import Path

def load_name_map(csv_path):
    """Build {ID: 'Prénom NOM'} from the real CSV (cols id;identifiant;nom;prenom;…)."""
    mapping = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        for row in reader:
            if len(row) < 4 or not row[0].strip():
                continue
            _id, nom, prenom = row[0].strip(), row[2].strip(), row[3].strip()
            full = f"{prenom} {nom}".strip()
            if full:
                mapping[_id] = full
    return mapping

def deanonymize_doc(doc, name_map):
    """Fill beneficiary 'nom' by exact de_id key. Return count resolved."""
    resolved = 0
    for b in doc.get("beneficiaires", []):
        name = name_map.get(str(b.get("de_id")))
        if name:
            b["nom"] = name
            resolved += 1
    return resolved

def run_deanon(in_dir, csv_path, out_dir):
    name_map = load_name_map(csv_path)
    src, out = Path(in_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.json"))
    total, resolved, unresolved = 0, 0, 0
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        n = deanonymize_doc(doc, name_map)
        total += len(doc.get("beneficiaires", []))
        resolved += n
        unresolved += len(doc.get("beneficiaires", [])) - n
        (out / fp.name).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    # COUNTERS ONLY — never print names.
    print(f"deanon: {len(files)} fichier(s), {resolved} résolu(s), "
          f"{unresolved} non résolu(s) sur {total} bénéficiaire(s) → {out}")
