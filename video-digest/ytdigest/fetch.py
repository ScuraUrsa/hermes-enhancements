"""Everything that talks to YouTube: metadata, captions, audio and low-res video.

Uses yt-dlp as a Python module (the VM's system python has no yt-dlp binary on
PATH; see crewai-orchestrator b536d6a). Cookies are optional and per account.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

_ID_RE = re.compile(r"(?:v=|/shorts/|youtu\.be/|/live/|/embed/)([A-Za-z0-9_-]{11})")


def video_id(url_or_id: str) -> str:
    s = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = _ID_RE.search(s)
    if not m:
        raise ValueError(f"not a YouTube video link: {url_or_id}")
    return m.group(1)


def watch_url(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


def _ydl(opts: dict[str, Any], cookies: str | None):
    import os

    import yt_dlp  # imported lazily so tests run without it

    # yt-dlp finds its JS runtime (deno) on PATH; cron and systemd start with a bare PATH.
    extra = [d for d in (Path.home() / ".local/bin", Path.home() / ".deno/bin") if (d / "deno").exists()]
    path = os.environ.get("PATH", "")
    for d in extra:
        if str(d) not in path.split(os.pathsep):
            path = f"{d}{os.pathsep}{path}"
    os.environ["PATH"] = path
    base = {"quiet": True, "no_warnings": True, "noprogress": True, "retries": 3}
    if cookies and Path(cookies).is_file():
        base["cookiefile"] = cookies
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def probe(url: str, cookies: str | None = None) -> dict:
    """Metadata only (title, channel, duration, category, captions list...)."""
    with _ydl({"skip_download": True}, cookies) as y:
        info = y.extract_info(url, download=False)
    return y.sanitize_info(info) if hasattr(y, "sanitize_info") else info


def flat_playlist(url: str, cookies: str | None = None) -> list[dict]:
    """Entries of a playlist without resolving each video (cheap)."""
    with _ydl({"skip_download": True, "extract_flat": "in_playlist"}, cookies) as y:
        info = y.extract_info(url, download=False)
    return [e for e in (info.get("entries") or []) if e and e.get("id")]


def pick_caption(info: dict, kind: str, langs: list[str]) -> tuple[str, str] | None:
    """Return (lang, kind) of the best caption track, or None.

    kind="manual" looks at uploaded subtitles, kind="auto" at auto-captions.
    The video's own language goes first, then the preferred list. For auto
    captions only the original-language track is real ASR; translated tracks
    are machine translations and are skipped.
    """
    tracks = info.get("subtitles" if kind == "manual" else "automatic_captions") or {}
    tracks = {k: v for k, v in tracks.items() if k != "live_chat"}
    if not tracks:
        return None
    original = (info.get("language") or "").split("-")[0]
    if kind == "auto":
        orig_keys = [k for k in tracks if k.endswith("-orig")]
        if orig_keys:
            return orig_keys[0], kind
        candidates = [original] if original else list(langs)
    else:
        candidates = ([original] if original else []) + [l for l in langs if l != original]
    for lang in candidates:
        for key in tracks:
            if key.split("-")[0] == lang:
                return key, kind
    if kind == "manual":
        return next(iter(tracks)), kind
    return None


def download_caption(url: str, lang_key: str, kind: str, out_dir: Path, cookies: str | None = None) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": kind == "manual",
        "writeautomaticsub": kind == "auto",
        "subtitleslangs": [lang_key],
        "subtitlesformat": "vtt/best",
        "outtmpl": str(out_dir / f"captions.{kind}.%(ext)s"),
    }
    with _ydl(opts, cookies) as y:
        y.download([url])
    found = sorted(out_dir.glob(f"captions.{kind}*.vtt"))
    return found[0] if found else None


_TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})|(\d{2}):(\d{2})[.,](\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _ts(s: str) -> float:
    m = _TS.search(s)
    if not m:
        return 0.0
    if m.group(1) is not None:
        h, mi, se, ms = (int(m.group(i)) for i in range(1, 5))
    else:
        h, (mi, se, ms) = 0, (int(m.group(i)) for i in range(5, 8))
    return h * 3600 + mi * 60 + se + ms / 1000


def parse_vtt(text: str) -> list[dict]:
    """WebVTT -> [{start, end, text}], collapsing the rolling duplicates that
    YouTube auto-captions repeat from one cue to the next."""
    segments: list[dict] = []
    last = ""
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = [l for l in block.strip().split("\n") if l.strip()]
        arrow = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if arrow is None:
            continue
        start_s, end_s = lines[arrow].split("-->", 1)
        start, end = _ts(start_s), _ts(end_s)
        new_parts = []
        for raw in lines[arrow + 1 :]:
            line = html.unescape(_TAG.sub("", raw)).strip()
            if not line or line == last or last.endswith(line):
                continue
            new_parts.append(line)
            last = line
        if new_parts:
            segments.append({"start": round(start, 2), "end": round(end, 2), "text": " ".join(new_parts)})
    return segments


def _download(opts: dict, url: str, cookies: str | None, attempts: int = 3, wait: float = 20.0) -> None:
    """yt-dlp download with retries: YouTube refuses streams intermittently (HTTP 403)
    and a fresh attempt a little later usually gets through."""
    import time

    for n in range(1, attempts + 1):
        try:
            with _ydl(opts, cookies) as y:
                y.download([url])
            return
        except Exception as exc:
            if n == attempts or not any(s in str(exc) for s in ("403", "Forbidden", "429", "timed out", "Connection")):
                raise
            time.sleep(wait * n)


def download_audio(url: str, out_dir: Path, cookies: str | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {"format": "bestaudio[ext=m4a]/bestaudio/best", "outtmpl": str(out_dir / "audio.%(ext)s")}
    _download(opts, url, cookies)
    found = sorted(p for p in out_dir.glob("audio.*") if p.suffix not in (".part", ".ytdl"))
    if not found:
        raise RuntimeError("audio download produced no file")
    return found[0]


def download_video(url: str, out_dir: Path, max_height: int = 480, cookies: str | None = None) -> Path:
    """Video-only stream at low resolution: enough for frames and OCR, small on disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = f"bv*[height<={max_height}][ext=mp4]/bv*[height<={max_height}]/b[height<={max_height}]/b"
    opts = {"format": fmt, "outtmpl": str(out_dir / "video.%(ext)s")}
    _download(opts, url, cookies)
    found = sorted(p for p in out_dir.glob("video.*") if p.suffix not in (".part", ".ytdl"))
    if not found:
        raise RuntimeError("video download produced no file")
    return found[0]
