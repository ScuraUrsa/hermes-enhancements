"""Which model does what, per video type.

The model-benchmark thread owns the real table (hermes-enhancements
vbench/routing.json). Until it lands, DEFAULT_ROUTING keeps everything on cheap
Ollama Cloud models that are already paid for by Filip's Pro plan.
"""

from __future__ import annotations

import json
from pathlib import Path

VIDEO_TYPES = [
    "podcast_talk", "interview", "tutorial_screen", "lecture_slides", "explainer_visual",
    "vlog_travel", "news_commentary", "documentary", "review_product", "music_artistic",
    "short", "other",
]

CHEAP_TEXT = "ollama-cloud:deepseek-v4.1-flash"
CHEAP_CLASSIFY = "ollama-cloud:gpt-oss:120b"
CHEAP_VISION = "ollama-cloud:gemma3:27b"
# Tried when the main vision model is gone or failing (Ollama retires models; 410/404).
VISION_FALLBACK = "ollama-cloud:gemma3:12b"
URL_MODEL = "gemini:gemini-flash-lite-latest"

# analyzer "gemini_url": one Gemini call reads the YouTube URL (speech + frames).
# analyzer "frames": local path (transcript + keyframes + vision + text model);
# also the automatic fallback when the URL path fails (private video, no key).
_base = {
    "analyzer": "gemini_url", "url_model": URL_MODEL, "url_fps": 0.2,
    "classify": CHEAP_CLASSIFY, "vision": CHEAP_VISION, "vision_fallback": VISION_FALLBACK, "report": CHEAP_TEXT,
    "frames_per_min": 1.0, "skip": False,
}

DEFAULT_ROUTING: dict[str, dict] = {
    "default": dict(_base),
    # Talking heads: the picture adds little, so few frames.
    "podcast_talk": {**_base, "frames_per_min": 0.2},
    "interview": {**_base, "frames_per_min": 0.3},
    "news_commentary": {**_base, "frames_per_min": 0.5},
    # The screen carries the content: more frames.
    "tutorial_screen": {**_base, "frames_per_min": 3.0, "url_fps": 1.0},
    "lecture_slides": {**_base, "frames_per_min": 2.0, "url_fps": 0.5},
    "explainer_visual": {**_base, "frames_per_min": 2.0, "url_fps": 0.5},
    "documentary": {**_base, "frames_per_min": 1.0},
    "vlog_travel": {**_base, "frames_per_min": 1.5},
    "review_product": {**_base, "frames_per_min": 1.5},
    "short": {**_base, "frames_per_min": 6.0, "url_fps": 1.0},
    "other": dict(_base),
    "music_artistic": {**_base, "skip": True, "frames_per_min": 0},
}


def load(cfg: dict) -> dict[str, dict]:
    table = {k: dict(v) for k, v in DEFAULT_ROUTING.items()}
    path = cfg.get("routing_file")
    if not path:
        # vbench lives next to video-digest in the same repo
        sibling = Path(__file__).resolve().parents[2] / "vbench" / "routing.json"
        path = str(sibling) if sibling.is_file() else ""
    if path and Path(path).is_file():
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
        provisional = bool(loaded.get("provisional"))
        vb_default = loaded.get("default") if isinstance(loaded.get("default"), dict) else {}
        for vtype in ["default", *VIDEO_TYPES]:
            row = {**vb_default, **(loaded.get(vtype) if isinstance(loaded.get(vtype), dict) else {})}
            if row:  # types vbench doesn't list inherit its "default" row
                table[vtype] = _from_vbench(table.get(vtype, table["default"]), row, provisional)
        tr = (loaded.get("transcribe") or {}).get("default") or {}
        if str(tr.get("ref", "")).startswith("groq:"):
            table["_transcribe_groq_model"] = tr["ref"].split(":", 1)[1].split("@")[0]
    return table


def _from_vbench(base: dict, row: dict, provisional: bool) -> dict:
    """Merge one vbench routing row. A report ref "gemini-video:<model>@fps=x" means
    Gemini reads the URL. While the table is provisional (no benchmark data yet) the
    Gemini URL path stays the default and vbench's picks drive the fallback path."""
    out = {**base, **{k: v for k, v in row.items() if k in ("classify", "vision", "vision_fallback", "report", "frames_per_min", "skip") and v is not None}}
    rep = str(row.get("report") or "")
    if rep.startswith("gemini-video:"):
        model = rep.split(":", 1)[1].split("@")[0]
        opts = dict(kv.split("=", 1) for kv in rep.split("@")[1:] if "=" in kv)
        out.update(analyzer="gemini_url", url_model=f"gemini:{model}", url_fps=float(opts.get("fps", base.get("url_fps", 0.2))))
        out["report"] = base["report"]  # text model for the fallback path
    elif not provisional:
        out["analyzer"] = "frames"
    return out


def route(table: dict[str, dict], video_type: str) -> dict:
    return table.get(video_type) or table["default"]
