import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
import httpx

_API = "https://api.brevo.com/v3/smtp/email"
_SCHEDULE_LOG = "out/schedules.jsonl"


def validate_scheduled_at(value):
    """Accept ISO-8601 'YYYY-MM-DDTHH:MM:SS' (Brevo scheduledAt). Raise ValueError otherwise."""
    datetime.fromisoformat(value)  # raises ValueError on bad format


def _title(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return m.group(1).strip() if m else "Recommandations structures IAE"


def _resolve_proxy(proxy=None):
    """Proxy explicite > BREVO_PROXY env > None. Ex. socks5h://127.0.0.1:1080."""
    return proxy or os.environ.get("BREVO_PROXY") or None


def _cancel_url(message_id):
    return f"{_API}/{message_id}"


def _log_schedule(path, run_id, scheduled_at, message_ids, src):
    """Trace méta d'un run programmé (runId + messageIds Brevo ; jamais d'adresse/nom)."""
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "runId": run_id,
           "scheduledAt": scheduled_at, "count": len(message_ids),
           "messageIds": message_ids, "src": str(src)}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _lookup_run(path, run_id):
    """messageIds d'un run programmé loggé, ou None si runId inconnu."""
    p = Path(path)
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("runId") == run_id:
            return rec.get("messageIds", [])
    return None


def recipients_for(conseiller_email, test):
    if test:
        raw = os.environ.get("TEST_RECIPIENTS", "")
        return [e.strip() for e in raw.split(",") if e.strip()]
    return [conseiller_email] if conseiller_email else []


def build_payload(html, to_email, sender, test, scheduled_at=None):
    subject = _title(html)
    if test:
        subject = f"[TEST] {subject}"
    payload = {
        "sender": {"email": sender},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html,
    }
    if scheduled_at:
        payload["scheduledAt"] = scheduled_at
    return payload


def _send_one(client, payload, api_key):
    r = client.post(_API, headers={"api-key": api_key,
                                   "content-type": "application/json"},
                    json=payload)
    r.raise_for_status()
    return r.json()


def run_send(in_dir, test=False, scheduled_at=None, proxy=None):
    if scheduled_at:
        validate_scheduled_at(scheduled_at)
    api_key = os.environ["BREVO_API_KEY"]
    sender = os.environ["BREVO_SENDER"]  # required: fail loud rather than send from a baked-in identity
    proxy = _resolve_proxy(proxy)  # egress via une IP fixe whitelistée Brevo (tunnel SOCKS)
    src = Path(in_dir)
    html_files = sorted(src.glob("*.html"))
    sent, skipped = 0, 0
    message_ids = []  # pour annuler un envoi programmé (cancel par messageId)
    with httpx.Client(timeout=30, proxy=proxy) as client:
        for fp in html_files:
            html = fp.read_text(encoding="utf-8")
            m = re.search(r"<!--\s*to:\s*([^\s>]+)\s*-->", html)
            conseiller_email = m.group(1) if m else None
            for to in recipients_for(conseiller_email, test):
                resp = _send_one(client, build_payload(html, to, sender, test, scheduled_at), api_key)
                mid = resp.get("messageId") if isinstance(resp, dict) else None
                if mid:
                    message_ids.append(mid)
                sent += 1
            if not recipients_for(conseiller_email, test):
                skipped += 1
    mode = "programmé" if scheduled_at else "immédiat"
    via = " via proxy" if proxy else " (direct)"
    print(f"send ({mode}{via}): {sent} envoi(s), {skipped} ignoré(s)")
    if scheduled_at:
        run_id = str(uuid.uuid4())
        _log_schedule(_SCHEDULE_LOG, run_id, scheduled_at, message_ids, src)
        print(f"runId = {run_id}  (annulable : uv run sps cancel {run_id})")


def run_cancel(handle, proxy=None):
    """Annule un envoi programmé : par runId (loggé → tous ses messageIds) ou messageId direct."""
    api_key = os.environ["BREVO_API_KEY"]
    proxy = _resolve_proxy(proxy)
    ids = _lookup_run(_SCHEDULE_LOG, handle)
    if ids is None:
        ids = [handle]  # pas un runId connu → traité comme un messageId Brevo direct
    ok = 0
    with httpx.Client(timeout=30, proxy=proxy) as client:
        for mid in ids:
            r = client.delete(_cancel_url(mid), headers={"api-key": api_key})
            if r.status_code in (200, 204):
                ok += 1
            else:
                print(f"  échec {mid[:18]}… HTTP {r.status_code}")
    print(f"cancel: {ok}/{len(ids)} message(s) annulé(s)")
