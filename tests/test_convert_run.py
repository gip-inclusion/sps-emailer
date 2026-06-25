import glob
import json
import os
from pathlib import Path
import pytest
from sps.convert import parse_md, run_convert
from sps.schema import validate_email

FIX = Path(__file__).parent / "fixtures" / "one_block.md"

def test_intro_and_remarques_extracted():
    doc = parse_md(FIX.read_text(encoding="utf-8"))[0]
    assert doc["intro"].startswith("Bonjour Jane")
    assert any("valider en entretien" in r for r in doc["remarques"])

def test_run_convert_writes_valid_json(tmp_path):
    out = tmp_path / "json"
    run_convert(str(FIX), str(out))
    files = list(out.glob("*.json"))
    assert len(files) == 1
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    validate_email(doc)
    assert files[0].name == "PE0TEST.json"

def test_two_beneficiaries_and_avis_reset():
    docs = parse_md(FIX.read_text(encoding="utf-8"))
    assert len(docs) == 1
    benefs = docs[0]["beneficiaires"]
    assert len(benefs) == 2
    # avis_url is per-beneficiary, not leaked across
    b1, b2 = benefs
    assert b1["avis_url"].endswith("TEST1?email=jane%40x")
    assert b2["avis_url"].endswith("TEST2?email=jane%40x")

def test_best_service_urlless_item_and_multiline_note():
    b1 = parse_md(FIX.read_text(encoding="utf-8"))[0]["beneficiaires"][0]
    # find the best_service section
    best = [s for g in b1["groupes"] for s in g["sections"] if s["type"] == "best_service"][0]
    item = best["items"][0]
    assert item["note"] == "Mobilité"
    assert item["nom"] == "Atelier mobilité sans lien"
    assert item["url"] is None          # URL-less item is allowed
    # multi-line note on the IAE item is preserved, not truncated
    iae = [s for g in b1["groupes"] for s in g["sections"] if s["type"] == "structures_iae"][0]
    note = iae["items"][0]["note"]
    assert "1175 candidatures" in note and "plusieurs postes ouverts" in note

def test_aucune_action_section_validates():
    b2 = parse_md(FIX.read_text(encoding="utf-8"))[0]["beneficiaires"][1]
    sec = b2["groupes"][0]["sections"][0]
    assert sec["type"] == "aucune_action"
    assert sec["items"] == []

def test_end_to_end_convert_then_render():
    # the real producer output (parse_md) must render without contract drift
    from sps.render import render_doc
    doc = parse_md(FIX.read_text(encoding="utf-8"))[0]
    html = render_doc(doc)
    assert "<title>" in html
    assert "Bénéficiaire #1" in html  # anonymized (nom is null out of convert)
    assert "ACCOMPAGNEMENT LONG ET SPÉCIFIQUE" in html
    assert "<!-- to: jane.doe@francetravail.fr -->" in html

@pytest.mark.skipif(not os.path.isdir("out/json-lille"), reason="run convert first")
def test_all_lille_json_validate():
    files = glob.glob("out/json-lille/*.json")
    assert files
    for f in files:
        validate_email(json.loads(open(f, encoding="utf-8").read()))
