import json
from pathlib import Path
from sps.render import render_doc, run_render

DOC = {
    "conseiller": {"ref": "PE0TEST", "nom": "DOE Jane", "email": "jane@x.fr", "agence": "AG"},
    "objet": "Recommandations IAE – PE0TEST",
    "intro": None, "remarques": None,
    "beneficiaires": [{
        "de_id": "78", "index": 1, "nom": None, "age": 26, "cp": "59800",
        "commune": "LILLE", "dernier_entretien": "2025-03-20",
        "convocation": {"date": "2026-07-02", "heure": "09:00"},
        "profil": ["DELD"], "axes": ["Se former"], "rome": {"code": "K2205", "label": "Agent"},
        "freins": [], "objectif": None, "avis_url": "https://tally.so/r/x",
        "groupes": [{"titre": "ACCOMPAGNEMENT LONG", "before_block": None, "after_block": None,
            "sections": [{"type": "structures_iae", "legende": "Structures IAE — K2205",
                "items": [{"tension": "rouge", "type_struct": "AI", "nom": "Assoc Test",
                    "structure": None, "adresse": "59800", "distance_km": 1,
                    "telephone": "+33800111009", "email": None,
                    "note": "1175 candidatures", "url": "https://emplois.inclusion/x"}],
                "aside": {"format": "markdown", "content": "**Le saviez-vous ?** ..."},
                "before_block": None, "after_block": None, "alternatives": None}]}],
    }],
}

def test_render_anonymous_uses_placeholder():
    html = render_doc(DOC)
    assert "Bénéficiaire #1" in html        # nom is None
    assert "Assoc Test" in html
    assert "Service très sollicité" in html
    assert "ACCOMPAGNEMENT LONG" in html
    assert "tel:+33800111009" in html
    assert "Le saviez-vous" in html
    assert "<title>" in html and "Recommandations IAE" in html

def test_render_with_name():
    doc = json.loads(json.dumps(DOC))
    doc["beneficiaires"][0]["nom"] = "Jane DOE"
    html = render_doc(doc)
    assert "Jane DOE" in html
    assert "Bénéficiaire #1" not in html

def test_render_embeds_conseiller_email():
    html = render_doc(DOC)
    assert "<!-- to: jane@x.fr -->" in html

def test_cta_label_overrides_inference():
    doc = json.loads(json.dumps(DOC))
    doc["beneficiaires"][0]["groupes"][0]["sections"][0]["items"][0]["cta_label"] = "Mon bouton"
    html = render_doc(doc)
    assert "Mon bouton ↗" in html
    assert "Voir la structure (Les Emplois)" not in html

def test_remote_renders_a_distance_and_hides_km():
    doc = json.loads(json.dumps(DOC))
    it = doc["beneficiaires"][0]["groupes"][0]["sections"][0]["items"][0]
    it["remote"] = True
    it["distance_km"] = 5
    html = render_doc(doc)
    assert "À distance" in html
    assert "(5 km)" not in html

def test_run_render_writes_one_html_per_conseiller(tmp_path):
    src = tmp_path / "json"; src.mkdir()
    (src / "PE0TEST.json").write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "html"
    run_render(str(src), str(out))
    files = list(out.glob("*.html"))
    assert len(files) == 1 and files[0].name == "PE0TEST.html"
