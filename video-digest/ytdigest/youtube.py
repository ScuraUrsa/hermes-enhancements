"""Write side of YouTube: put processed videos into a playlist on Filip's channel.

YouTube's API cannot remove anything from Watch Later (it does not expose that
list at all), so "moved" means: added to the processed playlist. The playlist id
and the videos already added are remembered in data_dir, so a re-run never adds
a video twice (YouTube itself allows duplicates). Each insert costs 50 of the
10,000 daily API units, so at most ~190 videos a day.
"""

from __future__ import annotations

import json
from pathlib import Path

from .backlog import YT, token_for


def _state(cfg: dict) -> tuple[Path, dict]:
    path = Path(cfg["data_dir"]) / "youtube_playlist.json"
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return path, {}


def _call(method: str, path: str, token: str, **kw):
    import requests

    r = requests.request(method, f"{YT}/{path}", headers={"Authorization": f"Bearer {token}"}, timeout=30, **kw)
    if r.status_code == 403 and "insufficient" in r.text.lower():
        raise PermissionError("the Google token has read-only YouTube access; re-authorize with the youtube scope")
    if r.status_code >= 400:
        raise RuntimeError(f"YouTube {path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def playlist_id(cfg: dict, account: str, title: str, token: str) -> str:
    path, st = _state(cfg)
    key = f"{account}/{title}"
    if st.get("ids", {}).get(key):
        return st["ids"][key]
    pid = None
    page = None
    while pid is None:
        body = _call("GET", "playlists", token, params={"part": "snippet", "mine": "true", "maxResults": 50,
                                                          **({"pageToken": page} if page else {})})
        pid = next((p["id"] for p in body.get("items", []) if p["snippet"]["title"] == title), None)
        page = body.get("nextPageToken")
        if not page:
            break
    if pid is None:
        created = _call("POST", "playlists", token, params={"part": "snippet,status"},
                        json={"snippet": {"title": title, "description": "Filmy, z których Hermes zrobił raport w Notion."},
                              "status": {"privacyStatus": "private"}})
        pid = created["id"]
    st.setdefault("ids", {})[key] = pid
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1), encoding="utf-8")
    return pid


def add_to_playlist(cfg: dict, account: str, title: str, video_id: str) -> bool:
    """True when the video was added now, False when it was already there."""
    path, st = _state(cfg)
    done = set(st.get("added", {}).get(f"{account}/{title}", []))
    if video_id in done:
        return False
    token = token_for(cfg, account)
    pid = playlist_id(cfg, account, title, token)
    _call("POST", "playlistItems", token, params={"part": "snippet"},
          json={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
    path, st = _state(cfg)  # playlist_id() may have written it
    st.setdefault("added", {}).setdefault(f"{account}/{title}", []).append(video_id)
    path.write_text(json.dumps(st, indent=1), encoding="utf-8")
    return True
