"""Video type and the artistic/music check.

Step 1 runs on metadata alone and costs nothing: clear music videos, songs,
concerts and similar are listed as artistic before anything is downloaded.
Step 2 (only when step 1 is unsure) asks a cheap model with metadata plus the
start of the transcript.
"""

from __future__ import annotations

import re

from . import shared
from .routing import VIDEO_TYPES

_MUSIC_TITLE = re.compile(
    r"official\s+(music\s+)?video|official\s+audio|lyric(s)?\s+video|\blyrics?\b|\(audio\)|"
    r"teledysk|\bremix\b|\bft\.|\bfeat\.|live\s+(at|in|@)|koncert|concert|\bacoustic\b|"
    r"\bcover\b|\bOST\b|soundtrack|full\s+album|instrumental|\bkaraoke\b",
    re.I,
)
_ARTISTIC_CATEGORIES = {"Music"}
_TALK_HINTS = re.compile(r"podcast|wywiad|interview|rozmowa|explained|tutorial|jak |how to|review|recenzja|lecture|wykład", re.I)


def rule_based(info: dict) -> dict | None:
    """Return a classification when metadata alone is conclusive, else None."""
    title = info.get("title") or ""
    channel = info.get("channel") or info.get("uploader") or ""
    cats = set(info.get("categories") or [])
    duration = info.get("duration") or 0
    music_cat = bool(cats & _ARTISTIC_CATEGORIES)
    topic_channel = channel.endswith(" - Topic") or channel.upper().endswith("VEVO")
    music_title = bool(_MUSIC_TITLE.search(title))
    talky = bool(_TALK_HINTS.search(title))

    if topic_channel or (music_cat and music_title and not talky):
        return _result("music_artistic", True, 0.95, "metadata: music channel/category and song-like title")
    if music_cat and duration and duration < 12 * 60 and not talky:
        return _result("music_artistic", True, 0.75, "metadata: Music category, short, no talk hints")
    if duration and duration <= 70 and "/shorts/" in (info.get("webpage_url") or ""):
        return _result("short", False, 0.8, "metadata: YouTube Short")
    return None


def _result(video_type: str, is_artistic: bool, confidence: float, reason: str) -> dict:
    return {"video_type": video_type, "is_artistic": is_artistic, "confidence": confidence, "reason": reason}


SYSTEM = (
    "You classify YouTube videos for a personal assistant that writes summaries so its owner "
    "does not have to watch. Answer with one JSON object only."
)


def prompt(info: dict, transcript_head: str, speech_ratio: float | None) -> str:
    chapters = ", ".join(c.get("title", "") for c in (info.get("chapters") or [])[:15])
    return f"""Video metadata:
title: {info.get('title')}
channel: {info.get('channel') or info.get('uploader')}
duration_sec: {info.get('duration')}
youtube_categories: {info.get('categories')}
tags: {(info.get('tags') or [])[:20]}
chapters: {chapters}
speech_ratio (share of runtime with transcribed speech): {speech_ratio}
description (start): {(info.get('description') or '')[:1200]}
transcript (start): {transcript_head[:2500]}

Pick video_type from: {', '.join(VIDEO_TYPES)}.
is_artistic = true when the value is mainly artistic or cultural (songs, music videos,
concerts, poetry readings, short films, dance, ASMR, ambient) and a written summary would
not replace experiencing it. Talks ABOUT music or art are not artistic.
Return: {{"video_type": "...", "is_artistic": true|false, "confidence": 0.0-1.0, "reason": "one short sentence"}}"""


def with_model(client, ref: str, info: dict, transcript_head: str, speech_ratio: float | None,
               transcript_source: str = "none") -> dict:
    vp = shared.vbench_prompts()
    if vp:
        system, user = vp.CLASSIFY_SYSTEM, vp.classify_user(shared.meta(info, transcript_source), transcript_head[:2500])
    else:
        system, user = SYSTEM, prompt(info, transcript_head, speech_ratio)
    out = client.json(ref, system, user, max_tokens=400)
    vtype = out.get("video_type") if out.get("video_type") in VIDEO_TYPES else "other"
    artistic = bool(out.get("is_artistic")) or vtype == "music_artistic"
    if artistic:
        vtype = "music_artistic"
    return _result(vtype, artistic, float(out.get("confidence") or 0.5), str(out.get("reason") or ""))
