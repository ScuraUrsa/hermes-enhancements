"""Main analysis path: Gemini reads the YouTube URL itself (speech + frames) and
returns the Report JSON in one call.

Google fetches the video, so the VM downloads nothing and YouTube's IP blocking
does not apply. Works for public videos only; anything else falls back to the
local frames path. Docs: https://ai.google.dev/gemini-api/docs/video-understanding
"""

from __future__ import annotations

import os
import time

from .llm import LLMError, parse_json
from .report import FIELDS, _instructions, _meta, normalise
from .routing import VIDEO_TYPES

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "You watch and listen to a YouTube video and write a report so its owner can skip watching it "
    "and still get everything useful. Use both what is said and what is shown. Only state what the "
    "video supports. Answer with one JSON object only."
)


def _prompt(bundle: dict, lang: str, transcript_hint: str) -> str:
    return (
        f"{_meta(bundle)}\n\n"
        + (f"A transcript is available (start shown for orientation):\n{transcript_hint[:3000]}\n\n" if transcript_hint else "")
        + "First decide video_type from: " + ", ".join(VIDEO_TYPES)
        + ". If the video is mainly a song, music video, concert or other artistic piece a summary "
        "cannot replace, set is_artistic true and keep the other fields short.\n"
        + _instructions(lang, "<your video_type>")
        + "\nAlso return frames_described: [{\"t\": seconds, \"caption\": \"what is on screen\"}] for 3-8 visually "
        "important moments (slides, code, charts, demos, places)."
    )


def analyse(client, model: str, bundle: dict, cfg: dict, fps: float, transcript_hint: str = "") -> tuple[dict, list[dict]]:
    """Return (report, frames_described)."""
    import requests

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY not set")
    lang = cfg["report_language"]
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"file_data": {"file_uri": bundle["url"], "mime_type": "video/*"},
                 "video_metadata": {"fps": max(0.05, float(fps))}},
                {"text": _prompt(bundle, lang, transcript_hint)},
            ],
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "mediaResolution": "MEDIA_RESOLUTION_LOW",
            "maxOutputTokens": 8192,
        },
    }
    last = ""
    for attempt in range(4):
        r = requests.post(API.format(model=model), params={"key": key}, json=body, timeout=900)
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"{r.status_code}: {r.text[:200]}"
            time.sleep(min(90, 10 * 2**attempt))
            continue
        if r.status_code >= 400:
            raise LLMError(f"gemini:{model} -> {r.status_code}: {r.text[:300]}")
        data = r.json()
        u = data.get("usageMetadata") or {}
        client._record(f"gemini-url:{model}", model, int(u.get("promptTokenCount") or 0),
                       int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0))
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"gemini returned no candidates: {str(data.get('promptFeedback'))[:200]}")
        text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
        out = parse_json(text)
        vtype = out.get("video_type") if out.get("video_type") in VIDEO_TYPES else "other"
        frames = [f for f in out.get("frames_described") or [] if isinstance(f, dict) and "t" in f]
        if out.get("is_artistic") or vtype == "music_artistic":
            rep = normalise(out, "music_artistic", bundle, lang)
            rep["is_artistic"] = True
            return rep, frames
        return normalise(out, vtype, bundle, lang), frames
    raise LLMError(f"gemini:{model} kept failing: {last}")


__all__ = ["analyse", "FIELDS"]
