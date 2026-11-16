"""Key frames: scene changes + a time-based floor + chapter starts, deduplicated.

ffmpeg does the scene detection (no extra dependency); Pillow does a small
perceptual hash so a talking head that never changes yields a handful of
frames instead of dozens. OCR is optional (tesseract binary); when it is
missing the vision model reads on-screen text itself.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

_PTS = re.compile(r"pts_time:([0-9.]+)")


def scene_times(video: Path, threshold: float) -> list[float]:
    """Timestamps where ffmpeg's scene score exceeds the threshold."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an",
        "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-", "-f", "null", "-",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return [float(m.group(1)) for m in _PTS.finditer(out.stdout)]


def plan(duration: float, scenes: list[float], chapters: list[dict], frames_per_min: float, max_frames: int) -> list[tuple[float, str]]:
    """Choose timestamps. Chapters always win, then scene changes spaced out,
    then an interval grid fills long static stretches."""
    if duration <= 0:
        return []
    budget = max(1, min(max_frames, int(round(duration / 60 * frames_per_min)) + len(chapters)))
    min_gap = max(4.0, duration / max(budget, 1) / 2)
    picked: list[tuple[float, str]] = []

    def free(t: float) -> bool:
        return all(abs(t - p) >= min_gap for p, _ in picked)

    for ch in chapters:
        t = min(float(ch.get("t", ch.get("start_time", 0))) + 2.0, max(0.0, duration - 1))
        if free(t):
            picked.append((t, "chapter"))
    for t in scenes:
        if len(picked) >= budget:
            break
        if 1.0 < t < duration - 1 and free(t):
            picked.append((t, "scene"))
    step = duration / (budget + 1)
    t = step
    while len(picked) < budget and t < duration - 1:
        if free(t):
            picked.append((t, "interval"))
        t += step
    return sorted(picked)[:max_frames]


def extract(video: Path, t: float, out: Path, width: int) -> bool:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out),
    ]
    return subprocess.run(cmd, check=False).returncode == 0 and out.is_file()


def dhash(path: Path, size: int = 8) -> int:
    from PIL import Image

    with Image.open(path) as im:
        g = im.convert("L").resize((size + 1, size))
        px = g.tobytes()
    bits = 0
    for row in range(size):
        for col in range(size):
            bits = (bits << 1) | (px[row * (size + 1) + col] > px[row * (size + 1) + col + 1])
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def ocr(path: Path) -> str | None:
    if not shutil.which("tesseract"):
        return None
    # tesseract's OpenMP threads, one set per parallel worker, oversubscribe a small VM:
    # 3 workers on 4 cores took ~10 min per frame instead of ~1 s
    env = {**os.environ, "OMP_THREAD_LIMIT": os.environ.get("OMP_THREAD_LIMIT", "1")}
    try:
        r = subprocess.run(["tesseract", str(path), "-", "-l", "pol+eng", "--psm", "3"], capture_output=True,
                           text=True, check=False, env=env, timeout=120)
    except subprocess.TimeoutExpired:
        return None
    text = " ".join(r.stdout.split())
    return text or None


def extract_frames(video: Path, bundle_dir: Path, duration: float, chapters: list[dict], cfg: dict) -> list[dict]:
    frames_dir = bundle_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scenes = scene_times(video, cfg["scene_threshold"])
    chosen = plan(duration, scenes, chapters, cfg["frames_per_min"], cfg["max_frames"])
    frames: list[dict] = []
    hashes: list[int] = []
    for t, reason in chosen:
        name = f"{int(t):06d}.jpg"
        out = frames_dir / name
        if not extract(video, t, out, cfg["frame_width"]):
            continue
        h = dhash(out)
        if reason != "chapter" and any(_hamming(h, o) <= 6 for o in hashes):
            out.unlink(missing_ok=True)  # near-duplicate of a frame we already have
            continue
        hashes.append(h)
        frames.append({"t": round(t, 2), "path": f"frames/{name}", "reason": reason, "ocr_text": ocr(out), "caption": None})
    return frames
