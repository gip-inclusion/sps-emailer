import os
import time
from sps.purge import _candidates, run_purge


def _touch(p, age_days):
    p.write_text("x", encoding="utf-8")
    t = time.time() - age_days * 86400
    os.utime(p, (t, t))


def test_candidates_only_old(tmp_path):
    d = tmp_path / "json-nom"; d.mkdir()
    old = d / "old.json"; new = d / "new.json"
    _touch(old, 10); _touch(new, 1)
    files = _candidates([str(d)], older_than_days=7)
    assert old in files and new not in files


def test_candidates_missing_dir():
    assert _candidates(["n/a/nope"], 7) == []


def test_run_purge_deletes_old_keeps_recent(tmp_path, capsys):
    d = tmp_path / "html"; d.mkdir()
    old = d / "old.html"; new = d / "new.html"
    _touch(old, 10); _touch(new, 1)
    run_purge([str(d)], older_than_days=7, assume_yes=True)
    assert not old.exists() and new.exists()
    assert "effacé" in capsys.readouterr().out


def test_run_purge_nothing(tmp_path, capsys):
    d = tmp_path / "html"; d.mkdir()
    run_purge([str(d)], older_than_days=7, assume_yes=True)
    assert "rien à effacer" in capsys.readouterr().out
