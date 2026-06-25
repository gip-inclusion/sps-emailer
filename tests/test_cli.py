import subprocess, sys

def run(*args):
    return subprocess.run([sys.executable, "-m", "sps", *args],
                          capture_output=True, text=True)

def test_help_lists_subcommands():
    r = run("--help")
    assert r.returncode == 0
    for cmd in ("convert", "deanon", "render", "send", "schedule"):
        assert cmd in r.stdout

def test_unknown_command_errors():
    r = run("frobnicate")
    assert r.returncode != 0


def test_send_help_has_via():
    r = run("send", "--help")
    assert r.returncode == 0 and "--via" in r.stdout

def test_schedule_help_has_via():
    r = run("schedule", "--help")
    assert r.returncode == 0 and "--via" in r.stdout


def test_cancel_in_subcommands():
    r = run("--help")
    assert r.returncode == 0 and "cancel" in r.stdout

def test_cancel_help_has_run_id():
    r = run("cancel", "--help")
    assert r.returncode == 0 and "run_id" in r.stdout


def test_purge_in_subcommands():
    r = run("--help")
    assert r.returncode == 0 and "purge" in r.stdout

def test_purge_help_has_older_than():
    r = run("purge", "--help")
    assert r.returncode == 0 and "older-than" in r.stdout
