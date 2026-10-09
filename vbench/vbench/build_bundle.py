"""Build a VideoBundle from a YouTube URL with yt-dlp + ffmpeg (for the benchmark sample).

The YouTube pipeline (video-digest) builds production bundles in the same format; this builder exists
so the benchmark can run on its own, and it additionally keeps the audio file and every caption track
for the transcription track.

Needs: yt-dlp (``pip install "yt-dlp[default]"``, plus Deno and the bgutil PO-token plugin in 2026)
and ffmpeg. For a signed-in account (Watch Later, private playlists) pass ``--cookies``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .bundle import Frame, Segment, Transcript, VideoBundle

SCENE_SELECT = ("isnan(prev_selected_t)+gte(t-prev_selected_t\\,{min_gap})*"
                "(gt(scene\\,{scene})+gte(t-prev_selected_t\\,{max_gap}))")


def _run(argv: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, **kw)


def _ytdlp() -> list[str]:
    exe = shutil.which("yt-dlp")
    return [exe] if exe else ["python3", "-m", "yt_dlp"]


def parse_json3(path: Path) -> list[Segment]:
    data = json.loads(path.read_text())
    segs = []
    for ev in data.get("events") or []:
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).replace("\n", " ").strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        segs.append(Segment(start, start + ev.get("dDurationMs", 0) / 1000, text))
    return segs


def extract_frames(video: Path, out_dir: Path, scene: float = 0.3, min_gap: float = 2.0, max_gap: float = 30.0,
                   width: int = 768, max_frames: int = 150) -> list[Frame]:
    """Scene cuts (at least ``min_gap`` s apart) plus a frame at least every ``max_gap`` s."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sel = SCENE_SELECT.format(scene=scene, min_gap=min_gap, max_gap=max_gap)
    cp = _run(["ffmpeg", "-hide_banner", "-y", "-i", str(video), "-vf",
               f"select='{sel}',scale={width}:-2,showinfo", "-vsync", "vfr", "-q:v", "4",
               str(out_dir / "%06d.jpg")])
    if cp.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {cp.stderr[-400:]}")
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", cp.stderr)]
    files = sorted(out_dir.glob("*.jpg"))
    frames = []
    prev_t = None
    for f, t in zip(files, times):
        reason = "scene" if prev_t is not None and t - prev_t < max_gap - 0.5 else "interval"
        frames.append(Frame(t=round(t, 2), path=f"frames/{f.name}", reason=reason))
        prev_t = t
    for f in files[len(frames):]:
        f.unlink()
    if len(frames) > max_frames:  # thin evenly, delete the rest
        keep = {int(i * len(frames) / max_frames) for i in range(max_frames)}
        for i, fr in enumerate(frames):
            if i not in keep:
                (out_dir / Path(fr.path).name).unlink(missing_ok=True)
        frames = [fr for i, fr in enumerate(frames) if i in keep]
    return frames


def music_hint(info: dict[str, Any]) -> bool:
    """Cheap metadata rule from the research: Music category, track/artist fields, '- Topic' or VEVO."""
    ch = (info.get("channel") or info.get("uploader") or "")
    return bool("Music" in (info.get("categories") or []) or info.get("track") or info.get("artist")
                or ch.endswith(" - Topic") or "VEVO" in ch)


def build(url: str, root: Path, langs: str = "pl.*,en.*", cookies: Path | None = None, keep_video: bool = False,
          account: str | None = None) -> VideoBundle:
    base = _ytdlp() + (["--cookies", str(cookies)] if cookies else [])
    cp = _run(base + ["-J", "--no-playlist", url])
    if cp.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {cp.stderr[-400:]}")
    info = json.loads(cp.stdout)
    vid = info["id"]
    d = Path(root) / vid
    d.mkdir(parents=True, exist_ok=True)
    (d / "ytdlp_info.json").write_text(json.dumps({k: info.get(k) for k in (
        "id", "title", "channel", "duration", "upload_date", "categories", "tags", "language", "track", "artist",
        "chapters", "description", "automatic_captions", "subtitles")}, ensure_ascii=False, default=str)[:2_000_000])

    # captions: manual and automatic, as json3
    _run(base + ["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", langs,
                 "--sub-format", "json3", "-o", str(d / "subs" / "%(id)s.%(ext)s"), url])
    manual_langs = set((info.get("subtitles") or {}).keys())
    manual: dict[str, list[Segment]] = {}
    auto: dict[str, list[Segment]] = {}
    for f in sorted((d / "subs").glob("*.json3")):
        lang = f.name.split(".")[-2]
        (manual if lang in manual_langs else auto)[lang] = parse_json3(f)
    lang = info.get("language") or next(iter(manual or auto), None)

    def pick(tracks: dict[str, list[Segment]]) -> tuple[str | None, list[Segment] | None]:
        if not tracks:
            return None, None
        for k in tracks:
            if lang and k.split("-")[0] == lang.split("-")[0]:
                return k, tracks[k]
        k = next(iter(tracks))
        return k, tracks[k]

    m_lang, m_segs = pick(manual)
    a_lang, a_segs = pick(auto)
    if m_segs:
        transcript = Transcript("youtube_manual", m_lang, m_segs)
    elif a_segs:
        transcript = Transcript("youtube_auto", a_lang, a_segs)
    else:
        transcript = Transcript("none", lang, [])
    alt = {}
    if m_segs:
        alt["youtube_manual"] = m_segs
    if a_segs:
        alt["youtube_auto"] = a_segs

    # low-res video for frames, audio for the transcription track
    vid_path = d / "video.mp4"
    cp = _run(base + ["-f", "bv*[height<=480]+ba/b[height<=480]/b", "--merge-output-format", "mp4",
                      "-o", str(vid_path), url])
    if cp.returncode != 0 or not vid_path.exists():
        raise RuntimeError(f"yt-dlp download failed: {cp.stderr[-400:]}")
    _run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(vid_path), "-vn", "-ac", "1", "-ar", "16000",
          "-b:a", "48k", str(d / "audio.mp3")])
    frames = extract_frames(vid_path, d / "frames")
    if not keep_video:
        vid_path.unlink(missing_ok=True)

    b = VideoBundle(
        video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=info.get("title") or "",
        channel=info.get("channel") or info.get("uploader") or "", duration_sec=float(info.get("duration") or 0),
        published_at=info.get("upload_date"), language=lang, description=info.get("description") or "",
        yt_tags=list(info.get("tags") or []),
        yt_chapters=[{"t": c.get("start_time"), "title": c.get("title")} for c in info.get("chapters") or []],
        account=account, transcript=transcript, frames=frames,
        audio={"path": "audio.mp3" if (d / "audio.mp3").exists() else None, "music_ratio": None,
               "music_hint": music_hint(info)},
        prep={"builder": "vbench.build_bundle", "scene_threshold": 0.3, "max_gap_sec": 30, "frame_width": 768},
        alt_transcripts=alt,
    )
    b.save(d)
    return b
