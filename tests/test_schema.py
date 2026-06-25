from sps.schema import validate_email

VALID = {
    "conseiller": {"ref": "PE1", "nom": "X Y", "email": "x@francetravail.fr"},
    "objet": "Objet", "beneficiaires": [
        {"de_id": "78", "index": 1, "groupes": []}
    ],
}

def test_valid_passes():
    validate_email(VALID)  # no exception

def test_open_section_type_allowed():
    doc = {**VALID, "beneficiaires": [{"de_id": "1", "index": 1, "groupes": [
        {"titre": "G", "sections": [{"type": "brand_new_type", "items": []}]}]}]}
    validate_email(doc)  # unknown type must NOT raise

def test_missing_required_raises():
    import pytest
    with pytest.raises(Exception):
        validate_email({"objet": "x"})

def test_cta_label_and_remote_validate():
    doc = {**VALID, "beneficiaires": [{"de_id": "1", "index": 1, "groupes": [
        {"titre": "G", "sections": [{"type": "best_service", "items": [
            {"nom": "Service X", "url": "https://x", "cta_label": "Voir sur Dora",
             "remote": True}]}]}]}]}
    validate_email(doc)  # new optional fields validate

def test_item_without_new_fields_still_valid():
    doc = {**VALID, "beneficiaires": [{"de_id": "1", "index": 1, "groupes": [
        {"titre": "G", "sections": [{"type": "x", "items": [{"nom": "S"}]}]}]}]}
    validate_email(doc)  # additive: omission still valid
