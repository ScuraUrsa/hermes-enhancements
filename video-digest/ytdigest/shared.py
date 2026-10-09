"""Use the benchmark's stage prompts when vbench is available, so what is
benchmarked is what runs. vbench lives next to video-digest in the same repo
(or is pip-installed); without it ytdigest falls back to its own prompts."""

from __future__ import annotations

import sys
from pathlib import Path

_cache: dict = {}


def vbench_prompts():
    if "p" in _cache:
        return _cache["p"]
    mod = None
    try:
        from vbench import prompts as mod  # type: ignore
    except ImportError:
        sibling = Path(__file__).resolve().parents[2] / "vbench"
        if (sibling / "vbench" / "prompts.py").is_file():
            sys.path.insert(0, str(sibling))
            try:
                from vbench import prompts as mod  # type: ignore
            except ImportError:
                mod = None
    _cache["p"] = mod
    return mod


def meta(bundle_or_info: dict, transcript_source: str = "none", music_ratio=None) -> dict:
    """The metadata dict vbench's prompt builders expect."""
    b = bundle_or_info
    return {
        "title": b.get("title") or "",
        "channel": b.get("channel") or b.get("uploader") or "",
        "url": b.get("url") or b.get("webpage_url") or "",
        "duration_min": float(b.get("duration_sec") or b.get("duration") or 0) / 60,
        "yt_tags": list(b.get("yt_tags") or b.get("tags") or []),
        "yt_chapters": b.get("yt_chapters") or [{"t": c.get("start_time", 0), "title": c.get("title", "")} for c in b.get("chapters") or []],
        "transcript_source": transcript_source,
        "music_ratio": music_ratio,
        "description": b.get("description") or "",
    }
