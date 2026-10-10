"""Discover: every video from the last N days by every channel Filip follows or saves.

Channels come from
  - the authors of every video in the account's own playlists (API),
  - the authors of videos in extra id files (Watch Later export, which the API hides),
  - the account's subscriptions.
For each channel its uploads playlist is read newest-first until the cutoff date.
Output is one de-duplicated TSV (video_id, published, seconds, channel, title, source),
optionally queued at DISCOVER_PRIORITY, below every other backlog item.

YouTube API cost: ~1 unit per 50 items, so a few thousand units for hundreds of
channels (daily quota 10,000).
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import fetch
from .backlog import _paged, api_playlists, token_for

DISCOVER_PRIORITY = 5


def _get(token: str, path: str, params: dict) -> dict:
    import requests

    from .backlog import YT

    r = requests.get(f"{YT}/{path}", params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"{path} -> {r.status_code}: {r.text[:200]}")
    return r.json()


def _batches(xs: list, n: int = 50):
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def _seconds(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def video_channels(token: str, ids: list[str]) -> dict[str, str]:
    """{channel_id: channel_title} for the given video ids."""
    out = {}
    for b in _batches(list(dict.fromkeys(ids))):
        for it in _get(token, "videos", {"part": "snippet", "id": ",".join(b), "maxResults": 50}).get("items", []):
            out[it["snippet"]["channelId"]] = it["snippet"].get("channelTitle", "")
    return out


def subscriptions(token: str) -> dict[str, str]:
    subs = _paged(token, "subscriptions", {"part": "snippet", "mine": "true"})
    return {s["snippet"]["resourceId"]["channelId"]: s["snippet"].get("title", "") for s in subs}


def uploads_since(token: str, channel_ids: list[str], cutoff: datetime, log=print) -> list[dict]:
    """[{video_id, published, channel_id, channel, title}] newer than cutoff."""
    import requests

    from .backlog import YT

    uploads = {}
    for b in _batches(channel_ids):
        for it in _get(token, "channels", {"part": "contentDetails,snippet", "id": ",".join(b), "maxResults": 50}).get("items", []):
            uploads[it["id"]] = (it["contentDetails"]["relatedPlaylists"].get("uploads"), it["snippet"].get("title", ""))
    out = []
    for n, (cid, (pl, ctitle)) in enumerate(uploads.items(), 1):
        if not pl:
            continue
        page = None
        while True:
            r = requests.get(f"{YT}/playlistItems", headers={"Authorization": f"Bearer {token}"}, timeout=30,
                             params={"part": "contentDetails,snippet", "playlistId": pl, "maxResults": 50,
                                     **({"pageToken": page} if page else {})})
            if r.status_code == 404:  # channel without public uploads
                break
            if r.status_code >= 400:
                raise RuntimeError(f"uploads of {ctitle} -> {r.status_code}: {r.text[:200]}")
            body = r.json()
            old = False
            for it in body.get("items", []):
                pub = it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt")
                if not pub:
                    continue
                if datetime.fromisoformat(pub.replace("Z", "+00:00")) < cutoff:
                    old = True
                    continue
                out.append({"video_id": it["contentDetails"]["videoId"], "published": pub[:10], "channel_id": cid,
                            "channel": ctitle, "title": it["snippet"].get("title", "")})
            page = body.get("nextPageToken")
            if old or not page:  # uploads are newest-first
                break
        if n % 25 == 0:
            log(f"  {n}/{len(uploads)} channels read, {len(out)} videos so far")
    return out


def durations(token: str, ids: list[str]) -> dict[str, int]:
    out = {}
    for b in _batches(ids):
        for it in _get(token, "videos", {"part": "contentDetails", "id": ",".join(b), "maxResults": 50}).get("items", []):
            out[it["id"]] = _seconds(it["contentDetails"].get("duration"))
    return out


def run(cfg: dict, account: str, days: int, out_path: Path, id_files: list[str] = (), include_subs: bool = True,
        skip_shorts: bool = False, skip_topic_channels: bool = True, min_seconds: int = 0,
        max_per_channel: int = 0, log=print) -> dict:
    token = token_for(cfg, account)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    saved = []  # videos Filip saved: own playlists + id files
    for pid, ptitle in api_playlists(token, cfg.get("include_liked", True)):
        saved += [i["contentDetails"]["videoId"] for i in
                  _paged(token, "playlistItems", {"part": "contentDetails", "playlistId": pid}) if i.get("contentDetails")]
    for f in id_files:
        for ln in Path(f).read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.lstrip().startswith("#"):
                try:
                    saved.append(fetch.video_id(ln.split()[0]))
                except ValueError:
                    pass
    log(f"saved videos: {len(set(saved))}")
    channels = {cid: (t, "playlisty") for cid, t in video_channels(token, saved).items()}
    log(f"channels from saved videos: {len(channels)}")
    if include_subs:
        subs = subscriptions(token)
        log(f"subscriptions: {len(subs)}")
        for cid, t in subs.items():
            channels[cid] = (t, "subskrypcje+playlisty" if cid in channels else "subskrypcje")
    if skip_topic_channels:  # auto-generated music channels: all artistic anyway
        channels = {c: v for c, v in channels.items() if not v[0].endswith(" - Topic")}
    log(f"channels to read: {len(channels)}")

    vids = uploads_since(token, list(channels), cutoff, log=log)
    seen, rows = set(), []
    for v in vids:  # de-duplicate (a video can only appear once per channel, but be safe)
        if v["video_id"] not in seen:
            seen.add(v["video_id"])
            v["source"] = channels.get(v["channel_id"], ("", ""))[1]
            rows.append(v)
    secs = durations(token, [r["video_id"] for r in rows])
    for r in rows:
        r["seconds"] = secs.get(r["video_id"], 0)
    shorts = sum(1 for r in rows if 0 < r["seconds"] <= 60)
    if skip_shorts:
        rows = [r for r in rows if not (0 < r["seconds"] <= 60)]
    if min_seconds:
        rows = [r for r in rows if r["seconds"] >= min_seconds]
    rows.sort(key=lambda r: r["published"], reverse=True)
    if max_per_channel:  # mass uploaders (several videos a day) would bury everything else
        kept, per = [], {}
        for r in rows:
            per[r["channel_id"]] = per.get(r["channel_id"], 0) + 1
            if per[r["channel_id"]] <= max_per_channel:
                kept.append(r)
        rows = kept

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["video_id", "published", "seconds", "channel", "title", "source"])
        for r in rows:
            w.writerow([r["video_id"], r["published"], r["seconds"], r["channel"], r["title"].replace("\t", " "), r["source"]])
    hours = round(sum(r["seconds"] for r in rows) / 3600, 1)
    summary = {"channels": len(channels), "videos": len(rows), "shorts": shorts, "hours": hours,
               "already_saved": len(seen & set(saved)), "file": str(out_path)}
    log(f"discover: {summary}")
    return {"summary": summary, "rows": rows}
