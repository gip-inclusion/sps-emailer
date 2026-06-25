import json
from pathlib import Path
from sps.deanon import load_name_map, deanonymize_doc, run_deanon

CSV = Path(__file__).parent / "fixtures" / "fake_names.csv"

def test_load_map():
    m = load_name_map(str(CSV))
    assert m["78"] == "Jane DOE"
    assert m["8"] == "Richard ROE"

def test_by_key_no_prefix_collision():
    # '#4' must never match '#41' — by-key lookup, not regex
    m = {"4": "Aa BB"}
    doc = {"beneficiaires": [{"de_id": "41", "nom": None},
                             {"de_id": "4", "nom": None}]}
    n = deanonymize_doc(doc, m)
    assert doc["beneficiaires"][0]["nom"] is None   # 41 unresolved
    assert doc["beneficiaires"][1]["nom"] == "Aa BB"
    assert n == 1

def test_run_deanon_counts(tmp_path, capsys):
    src = tmp_path / "in"; src.mkdir()
    (src / "PE0TEST.json").write_text(json.dumps(
        {"conseiller": {"ref": "PE0TEST", "nom": "C", "email": "c@x.fr"},
         "objet": "o",
         "beneficiaires": [{"de_id": "78", "index": 1, "nom": None, "groupes": []}]},
        ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    run_deanon(str(src), str(CSV), str(out))
    captured = capsys.readouterr().out
    assert "1 résolu" in captured or "1 b" in captured
    # The agent never reads out content; assert via counters only.
