"""describe_frames: a vision model captions each key frame, in small batches,
with the transcript around that moment as context."""

from __future__ import annotations

from pathlib import Path

SYSTEM = (
    "You describe video frames for someone who will not watch the video. Be concrete: what is "
    "shown (people, setting, objects, charts, slides, code, UI, maps), and transcribe any "
    "readable on-screen text. Answer with one JSON object only."
)


def _context(segments: list[dict], t: float, window: float = 20.0) -> str:
    near = [s["text"] for s in segments if s["end"] >= t - window and s["start"] <= t + window]
    return " ".join(near)[:600]


def describe(client, ref: str, bundle_dir: Path, frames: list[dict], segments: list[dict], lang: str, batch: int = 6) -> None:
    """Fill frame["caption"] (and frame["ocr_text"] when OCR didn't run). Mutates frames."""
    language = "Polish" if lang == "pl" else "English"
    for i in range(0, len(frames), batch):
        group = frames[i : i + batch]
        lines = []
        for n, f in enumerate(group, 1):
            lines.append(f"Image {n} at {int(f['t'])}s. Speech around it: \"{_context(segments, f['t'])}\"")
        user = (
            "\n".join(lines)
            + f"\n\nFor each image, in {language}, return "
            '{"frames": [{"n": 1, "caption": "1-2 sentences", "on_screen_text": "verbatim or empty", '
            '"adds_information": true|false}]}. adds_information = the picture shows something the speech does not.'
        )
        paths = [bundle_dir / f["path"] for f in group]
        try:
            out = client.json(ref, SYSTEM, user, images=paths, max_tokens=1500)
        except Exception as exc:  # one bad batch shouldn't sink the report
            for f in group:
                f["caption"] = None
                f["error"] = str(exc)[:200]
            continue
        by_n = {int(x.get("n", 0)): x for x in out.get("frames", []) if isinstance(x, dict)}
        for n, f in enumerate(group, 1):
            x = by_n.get(n, {})
            f["caption"] = x.get("caption")
            f["adds_information"] = x.get("adds_information")
            if not f.get("ocr_text") and x.get("on_screen_text"):
                f["ocr_text"] = x["on_screen_text"]
