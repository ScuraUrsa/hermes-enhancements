"""Fill the queue from Filip's YouTube accounts.

Sources per account (config "accounts", fjkazmierczak first):
  - own playlists through the YouTube Data API, with the token Hermes already
    keeps at ~/.hermes/google-accounts/<alias>/google_token.json
  - Watch Later ("Do obejrzenia") through yt-dlp + that account's cookies,
    because the API returns nothing for Watch Later
  - any extra playlist URLs listed in config "extra_playlists"
Liked videos are left out unless config "include_liked" is true.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import fetch
from .queue import BACKLOG_PRIORITY, Queue

YT = "https://www.googleapis.com/youtube/v3"


class AuthError(RuntimeError):
    pass


def _access_token(token_file: Path) -> str:
    import requests

    if not token_file.is_file():
        raise AuthError(f"no token at {token_file}")
    tok = json.loads(token_file.read_text())
    r = requests.post(
        tok.get("token_uri") or "https://oauth2.googleapis.com/token",
        data={"client_id": tok["client_id"], "client_secret": tok["client_secret"],
              "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"},
        timeout=30,
    )
    if r.status_code >= 400:
        raise AuthError(f"refresh failed for {token_file.parent.name}: {r.text[:200]} (re-auth with google_auth_queue.sh)")
    return r.json()["access_token"]


def _paged(token: str, path: str, params: dict) -> list[dict]:
    import requests

    items, page = [], None
    while True:
        p = dict(params, maxResults=50, **({"pageToken": page} if page else {}))
        r = requests.get(f"{YT}/{path}", params=p, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code == 404:
            return items
        if r.status_code >= 400:
            raise RuntimeError(f"{path} -> {r.status_code}: {r.text[:200]}")
        body = r.json()
        items += body.get("items", [])
        page = body.get("nextPageToken")
        if not page:
            return items


def api_playlists(token: str, include_liked: bool) -> list[tuple[str, str]]:
    """[(playlist_id, title)] for the channel the token was granted for."""
    out = [(p["id"], p["snippet"]["title"]) for p in _paged(token, "playlists", {"part": "snippet", "mine": "true"})]
    if include_liked:
        out.append(("LL", "Polubione"))
    return out


def api_items(token: str, playlist_id: str) -> list[tuple[str, str]]:
    items = _paged(token, "playlistItems", {"part": "snippet,contentDetails", "playlistId": playlist_id})
    return [(i["contentDetails"]["videoId"], i["snippet"].get("title", "")) for i in items if i.get("contentDetails")]


def _skip(title: str, cfg: dict) -> bool:
    return any(s.lower() in (title or "").lower() for s in cfg.get("skip_playlists") or [])


def sync(cfg: dict, q: Queue, accounts: list[str] | None = None, log=print) -> dict:
    added: dict[str, int] = {}
    for alias in accounts or cfg["accounts"]:
        n = 0
        # 1. API playlists
        try:
            token = _access_token(Path(cfg["google_accounts_dir"]) / alias / "google_token.json")
            for pid, ptitle in api_playlists(token, cfg.get("include_liked", False)):
                if _skip(ptitle, cfg):
                    continue
                for vid, vtitle in api_items(token, pid):
                    n += q.add(vid, fetch.watch_url(vid), title=vtitle, account=alias, playlist=ptitle, priority=BACKLOG_PRIORITY)
        except Exception as exc:
            log(f"[{alias}] API playlists: {exc}")
        # 2. Watch Later through cookies
        cookies = (cfg.get("cookies_file") or "").format(account=alias)
        if cookies and Path(cookies).is_file():
            try:
                for e in fetch.flat_playlist(":ytwatchlater", cookies):
                    n += q.add(e["id"], fetch.watch_url(e["id"]), title=e.get("title"), account=alias,
                               playlist="Do obejrzenia", priority=BACKLOG_PRIORITY + 5)
            except Exception as exc:
                log(f"[{alias}] Watch Later: {exc}")
        else:
            log(f"[{alias}] Watch Later skipped: no cookies at {cookies}")
        added[alias] = n
    # 3. explicit playlist URLs
    for extra in cfg.get("extra_playlists") or []:
        alias = extra.get("account")
        cookies = (cfg.get("cookies_file") or "").format(account=alias or "default")
        try:
            for e in fetch.flat_playlist(extra["url"], cookies if Path(cookies).is_file() else None):
                added[alias or "extra"] = added.get(alias or "extra", 0) + q.add(
                    e["id"], fetch.watch_url(e["id"]), title=e.get("title"), account=alias,
                    playlist=extra.get("name") or "playlista", priority=extra.get("priority", BACKLOG_PRIORITY))
        except Exception as exc:
            log(f"[extra] {extra.get('url')}: {exc}")
    log(f"new videos queued: {added}")
    return added
