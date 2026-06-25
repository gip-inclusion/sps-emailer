import json
from pathlib import Path
from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "schema" / "email.schema.json"

def _validator():
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))

def validate_email(doc):
    """Raise jsonschema.ValidationError if doc violates the contract."""
    _validator().validate(doc)
