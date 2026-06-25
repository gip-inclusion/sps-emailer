from pathlib import Path
from sps.convert import parse_md

FIX = Path(__file__).parent / "fixtures" / "one_block.md"

def test_parses_one_conseiller():
    docs = parse_md(FIX.read_text(encoding="utf-8"))
    assert len(docs) == 1
    c = docs[0]["conseiller"]
    assert c["ref"] == "PE0TEST"
    assert c["nom"] == "DOE Jane"
    assert c["email"] == "jane.doe@francetravail.fr"
    assert docs[0]["objet"].startswith("Recommandations structures IAE")

def test_parses_beneficiary_meta():
    b = parse_md(FIX.read_text(encoding="utf-8"))[0]["beneficiaires"][0]
    assert b["de_id"] == "78"
    assert b["index"] == 1
    assert b["nom"] is None
    assert b["age"] == 26
    assert b["cp"] == "59800"
    assert b["commune"] == "LILLE"
    assert b["dernier_entretien"] == "2025-03-20"
    assert b["convocation"] == {"date": "2026-07-02", "heure": "09:00"}
    assert b["profil"] == ["DELD", "N2(DELD)"]
    assert b["axes"] == ["Choisir un métier", "Se former"]
    assert b["rome"]["code"] == "K2205"
    assert b["freins"] == ["Développer sa mobilité", "Faire face à des contraintes familiales"]
    assert b["objectif"] is None
