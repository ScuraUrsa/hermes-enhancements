"""Fetch raw messages from Gmail with the tokens Hermes already has (``~/.hermes/google-accounts/<alias>``).

Stdlib only. The access token is refreshed in memory and never written back, so this never races with
``gacct`` / ``google_token_check.sh`` over the token file. Only ``gmail.readonly``-level calls are made.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://gmail.googleapis.com/gmail/v1/users/me"
ALIASES = {
    "praktyki": "praktyki", "praktyki.ftims@gmail.com": "praktyki",
    "koalamis6": "koalamis6", "koalamis6@gmail.com": "koalamis6",
    "fjkazmierczak": "fjkazmierczak", "f.j.kazmierczak@gmail.com": "fjkazmierczak",
    "kazmierczakfilipjan": "kazmierczakfilipjan", "kazmierczak.filip.jan@gmail.com": "kazmierczakfilipjan",
}
# Never touched, whatever the configuration says (Filip's rule 2026-10-24).
FORBIDDEN = ("hitachienergy.com",)


def _accounts_dir() -> Path:
    return Path(os.environ.get("MAILGUARD_ACCOUNTS_DIR", Path.home() / ".hermes" / "google-accounts"))


def access_token(account: str) -> str:
    if any(f in account.lower() for f in FORBIDDEN):
        raise PermissionError("konto służbowe jest wyłączone z przetwarzania")
    alias = ALIASES.get(account.lower(), account)
    path = _accounts_dir() / alias / "google_token.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({
        "client_id": data["client_id"], "client_secret": data["client_secret"],
        "refresh_token": data["refresh_token"], "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(data.get("token_uri", "https://oauth2.googleapis.com/token"), data=body)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed Google endpoint
        return json.loads(r.read())["access_token"]


def _get(token: str, url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed Google endpoint
        return json.loads(r.read())


def list_ids(token: str, query: str, limit: int = 20) -> list[str]:
    ids: list[str] = []
    page = ""
    while len(ids) < limit:
        q = {"q": query, "maxResults": min(100, limit - len(ids))}
        if page:
            q["pageToken"] = page
        res = _get(token, f"{API}/messages?{urllib.parse.urlencode(q)}")
        ids += [m["id"] for m in res.get("messages", [])]
        page = res.get("nextPageToken", "")
        if not page:
            break
    return ids[:limit]


def raw_message(token: str, msg_id: str) -> bytes:
    res = _get(token, f"{API}/messages/{urllib.parse.quote(msg_id)}?format=raw")
    return base64.urlsafe_b64decode(res["raw"] + "=" * (-len(res["raw"]) % 4))
