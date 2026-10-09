"""Pick a small, stratified benchmark sample from Filip's playlists.

Input: any of
  * ``yt-dlp --flat-playlist -J <playlist url>`` output (one or many files),
  * the pipeline's queue export / archive_manifest-style JSON ({video_id: {...}}),
  * a JSON/JSONL list of {video_id|id, title, channel, duration, playlist}.
Titles are pre-sorted into video types by a cheap model in batches (about 1 call per 40 videos), then
``per_type`` videos are drawn per type, spreading durations. The answer keys later fix the real type.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from . import prompts as P
from .bundle import VIDEO_TYPES
from .catalog import Catalog

BATCH_SYSTEM = (P.CLASSIFY_SYSTEM.split("Answer with JSON only")[0]
                + 'You get a numbered list of videos (title, channel, minutes). Answer with JSON only: '
                  '{"items": [{"i": <number>, "video_type": "<type>"}]}')


def load_candidates(paths: list[Path]) -> list[dict[str, Any]]:
    out: dict[str, dict] = {}
    for p in paths:
        text = Path(p).read_text()
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        if isinstance(data, dict) and "entries" in data:  # yt-dlp playlist
            pl = data.get("title")
            items = [dict(e, playlist=pl) for e in data["entries"] or []]
        elif isinstance(data, dict):  # manifest
            items = [dict(v, video_id=k) for k, v in data.items() if isinstance(v, dict)]
        else:
            items = list(data)
        for e in items:
            vid = e.get("video_id") or e.get("id")
            if not vid or (e.get("title") or "") in ("[Private video]", "[Deleted video]"):
                continue
            out.setdefault(vid, {"video_id": vid, "title": e.get("title") or "", "channel": e.get("channel") or
                                 e.get("uploader") or "", "duration": e.get("duration") or 0,
                                 "playlist": e.get("playlist"), "url": f"https://www.youtube.com/watch?v={vid}"})
    return list(out.values())


def pre_classify(cat: Catalog, ref: str, items: list[dict], batch: int = 40) -> None:
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        lines = [f"{j}. {e['title']} | {e['channel']} | {float(e['duration'] or 0) / 60:.0f} min"
                 for j, e in enumerate(chunk)]
        try:
            c = cat.model(ref).complete(BATCH_SYSTEM, "\n".join(lines), json_mode=True, max_tokens=60 * len(chunk))
            for it in P.parse_json(c.text).get("items", []):
                j = int(it.get("i", -1))
                if 0 <= j < len(chunk) and it.get("video_type") in VIDEO_TYPES:
                    chunk[j]["guess_type"] = it["video_type"]
        except Exception as e:  # noqa: BLE001 - an unsorted batch just lands in "other"
            print(f"batch {i // batch}: {e}")
    for e in items:
        e.setdefault("guess_type", "other")


def stratify(items: list[dict], per_type: int = 3, artistic: int = 2, seed: int = 7,
             max_minutes: float = 120) -> list[dict]:
    rng = random.Random(seed)
    by_type: dict[str, list[dict]] = {}
    for e in items:
        if float(e.get("duration") or 0) / 60 <= max_minutes:
            by_type.setdefault(e["guess_type"], []).append(e)
    picked = []
    for vt, lst in sorted(by_type.items()):
        want = artistic if vt == "music_artistic" else per_type
        lst.sort(key=lambda e: float(e.get("duration") or 0))
        if len(lst) <= want:
            picked += lst
            continue
        # one from each duration band, so short and long videos are both represented
        bands = [lst[k * len(lst) // want:(k + 1) * len(lst) // want] for k in range(want)]
        picked += [rng.choice(b) for b in bands if b]
    return picked
