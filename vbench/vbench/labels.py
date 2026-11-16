"""Answer keys (``labels/<video_id>.json``): what a perfect report must contain.

A strong reference model drafts each key from the transcript and frames (``vbench label``); a
person then checks it (``vbench review`` renders it for reading) and sets ``"reviewed": true``.
Keys are lists of checkable facts rather than model prose, so a grader can't reward a candidate
for sounding like the reference model.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import prompts as P
from .bundle import VIDEO_TYPES, VideoBundle, fmt_t
from .catalog import Catalog
from .stages import frame_budget, speech_near


def label_path(labels: Path, video_id: str) -> Path:
    return Path(labels) / f"{video_id}.json"


def load_label(labels: Path, video_id: str) -> dict | None:
    p = label_path(labels, video_id)
    return json.loads(p.read_text()) if p.exists() else None


def problems(label: dict) -> list[str]:
    out = []
    if label.get("video_type") not in VIDEO_TYPES:
        out.append(f"video_type {label.get('video_type')!r} is not one of the known types")
    if not label.get("is_artistic"):
        if len(label.get("key_points") or []) < 3:
            out.append("fewer than 3 key points")
        ids = [k.get("id") for k in label.get("key_points") or []]
        if len(ids) != len(set(ids)):
            out.append("duplicate key point ids")
    return out


def draft(cat: Catalog, ref: str, b: VideoBundle, labels: Path, frames_per_min: float = 2.0,
          max_frames: int = 30, overwrite: bool = False) -> dict:
    p = label_path(labels, b.video_id)
    if p.exists() and not overwrite:
        return json.loads(p.read_text())
    frames = b.select_frames(frame_budget(b, frames_per_min, max_frames))
    frame_list = "\n".join(f"Frame {i + 1}: t={f.t:.1f}s; speech nearby: {speech_near(b, f.t)[:300]}"
                           for i, f in enumerate(frames))
    user = (f"Title: {b.title}\nChannel: {b.channel}\nDuration: {b.duration_min:.1f} min\n"
            f"Description:\n{b.description[:2000]}\n\n=== Frames ===\n{frame_list}\n\n"
            f"=== Transcript ({b.transcript.source}) ===\n{b.transcript.text()}")
    c = cat.model(ref).complete(P.LABEL_SYSTEM, user, images=[b.frame_path(f) for f in frames],
                                json_mode=True, max_tokens=12000)
    label = P.parse_json(c.text)
    for i, f in enumerate(frames):  # pin reference captions to the real frame times
        caps = label.get("frame_captions") or []
        if i < len(caps) and isinstance(caps[i], dict):
            caps[i]["t"] = f.t
    label.update({"video_id": b.video_id, "title": b.title, "url": b.url, "reviewed": False, "labeled_by": ref,
                  "labeled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "label_cost_equiv_usd": cat.cost(ref, c).equiv_usd})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(label, ensure_ascii=False, indent=1))
    return label


def render_markdown(label: dict) -> str:
    """A readable page for checking a key by hand."""
    lines = [f"# {label.get('title', label.get('video_id'))}", "",
             f"{label.get('url', '')}", "",
             f"Type: **{label.get('video_type')}**, artistic: **{label.get('is_artistic')}**, "
             f"language: {label.get('language')}, reviewed: {label.get('reviewed')}", ""]
    if label.get("notes"):
        lines += [f"Notes: {label['notes']}", ""]
    lines += ["## Key points (importance)", ""]
    lines += [f"{k.get('id')}. ({k.get('importance')}) {k.get('text')}" for k in label.get("key_points") or []]
    lines += ["", "## Visual facts", ""]
    lines += [f"{v.get('id')}. [{fmt_t(float(v.get('t') or 0))}] {v.get('text')}" for v in label.get("visual_facts") or []]
    lines += ["", "## Tags", "", ", ".join(label.get("tags") or []), ""]
    probs = problems(label)
    if probs:
        lines += ["## Problems", ""] + [f"- {p}" for p in probs]
    return "\n".join(lines) + "\n"
