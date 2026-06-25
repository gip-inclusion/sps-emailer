import os
from sps.brevo import build_payload, recipients_for

HTML = "<html><head><title>Recommandations IAE – PE0TEST</title></head><body>x</body></html>"

def test_subject_from_title():
    p = build_payload(HTML, "to@x.fr", sender="elodie@x.fr", test=False)
    assert p["subject"] == "Recommandations IAE – PE0TEST"
    assert p["sender"]["email"] == "elodie@x.fr"
    assert p["to"] == [{"email": "to@x.fr"}]
    assert p["htmlContent"] == HTML
    assert "scheduledAt" not in p

def test_test_mode_prefixes_subject():
    p = build_payload(HTML, "to@x.fr", sender="e@x.fr", test=True)
    assert p["subject"].startswith("[TEST]")

def test_scheduled_at_included():
    p = build_payload(HTML, "to@x.fr", sender="e@x.fr", test=False,
                      scheduled_at="2026-06-29T07:00:00")
    assert p["scheduledAt"] == "2026-06-29T07:00:00"

def test_recipients_test_mode_from_env(monkeypatch):
    monkeypatch.setenv("TEST_RECIPIENTS", "a@x.fr, b@x.fr")
    assert recipients_for("real@ft.fr", test=True) == ["a@x.fr", "b@x.fr"]

def test_recipients_real_mode_uses_conseiller():
    assert recipients_for("real@ft.fr", test=False) == ["real@ft.fr"]


import pytest
from sps.brevo import validate_scheduled_at

def test_valid_iso():
    validate_scheduled_at("2026-06-29T07:00:00")  # no raise

def test_invalid_iso_raises():
    with pytest.raises(ValueError):
        validate_scheduled_at("29-06-2026 7h")


from sps.brevo import _resolve_proxy

def test_resolve_proxy_arg_wins(monkeypatch):
    monkeypatch.setenv("BREVO_PROXY", "socks5h://env:1")
    assert _resolve_proxy("socks5h://arg:2") == "socks5h://arg:2"

def test_resolve_proxy_env_fallback(monkeypatch):
    monkeypatch.setenv("BREVO_PROXY", "socks5h://env:1")
    assert _resolve_proxy(None) == "socks5h://env:1"

def test_resolve_proxy_none(monkeypatch):
    monkeypatch.delenv("BREVO_PROXY", raising=False)
    assert _resolve_proxy(None) is None


from sps.brevo import _cancel_url, _log_schedule, _lookup_run

def test_cancel_url():
    assert _cancel_url("<abc@smtp-relay.mailin.fr>") == \
        "https://api.brevo.com/v3/smtp/email/<abc@smtp-relay.mailin.fr>"

def test_log_and_lookup_run(tmp_path):
    import json
    p = tmp_path / "sch.jsonl"
    _log_schedule(p, "run-1", "2026-06-29T07:00:00", ["<m1@x>", "<m2@x>"], "out/html")
    _log_schedule(p, "run-2", "2026-06-29T08:00:00", ["<m3@x>"], "out/html")
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["runId"] == "run-1" and rec["count"] == 2 and rec["scheduledAt"].startswith("2026")
    assert _lookup_run(p, "run-1") == ["<m1@x>", "<m2@x>"]
    assert _lookup_run(p, "run-2") == ["<m3@x>"]
    assert _lookup_run(p, "inconnu") is None
    # le log ne contient aucune adresse de destinataire / nom
    content = p.read_text(encoding="utf-8")
    assert "meidosem" not in content and "inclusion.gouv" not in content

def test_lookup_run_no_file(tmp_path):
    assert _lookup_run(tmp_path / "absent.jsonl", "x") is None
