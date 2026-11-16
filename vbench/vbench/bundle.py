"""VideoBundle: the pipeline's per-video input, and what every benchmark stage reads.

A bundle is a directory ``<root>/<video_id>/`` holding ``bundle.json`` plus the frame JPGs it
references. The YouTube pipeline writes it; vbench only reads it (the vision stage writes
captions to the results directory, never back into the bundle).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_ID = "video_bundle/v1"

VIDEO_TYPES = (
    "podcast_talk",  # one or more people talking; picture adds little
    "interview",  # host + guest, Q&A
    "tutorial_screen",  # software / code / screen recording; screen text matters
    "lecture_slides",  # lecture or talk with slides; slide text matters
    "explainer_visual",  # animation, diagrams, whiteboard; picture carries meaning
    "vlog_travel",  # personal vlog, travel, outdoor; scenery and places
    "news_commentary",  # news, opinion, reaction
    "documentary",  # narrated documentary
    "review_product",  # product review / unboxing / comparison
    "music_artistic",  # song, music video, concert, art film: listed, not processed
    "short",  # under 3 minutes, any content
    "other",
)

TRANSCRIPT_SOURCES = ("youtube_manual", "youtube_auto", "whisper_local", "whisper_groq", "none")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Frame:
    t: float
    path: str
    reason: str = "interval"  # scene | interval | chapter
    ocr_text: str | None = None
    caption: str | None = None


@dataclass
class Transcript:
    source: str = "none"
    language: str | None = None
    segments: list[Segment] = field(default_factory=list)

    def text(self, with_times: bool = True) -> str:
        if not with_times:
            return " ".join(s.text.strip() for s in self.segments)
        return "\n".join(f"[{fmt_t(s.start)}] {s.text.strip()}" for s in self.segments)


@dataclass
class VideoBundle:
    video_id: str
    url: str
    title: str
    channel: str = ""
    duration_sec: float = 0.0
    published_at: str | None = None
    language: str | None = None
    description: str = ""
    yt_tags: list[str] = field(default_factory=list)
    yt_chapters: list[dict[str, Any]] = field(default_factory=list)
    playlists: list[str] = field(default_factory=list)
    account: str | None = None
    transcript: Transcript = field(default_factory=Transcript)
    frames: list[Frame] = field(default_factory=list)
    audio: dict[str, Any] = field(default_factory=dict)  # music_ratio, speech_ratio, path (benchmark only)
    prep: dict[str, Any] = field(default_factory=dict)
    # Benchmark only: other transcripts of the same video, e.g. {"youtube_auto": [...], "youtube_manual": [...]}
    alt_transcripts: dict[str, list[Segment]] = field(default_factory=dict)
    schema: str = SCHEMA_ID
    root: Path | None = field(default=None, repr=False, compare=False)

    # -- io ---------------------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "VideoBundle":
        path = Path(path)
        if path.is_dir():
            path = path / "bundle.json"
        data = json.loads(path.read_text())
        if data.get("schema", SCHEMA_ID) != SCHEMA_ID:
            raise ValueError(f"{path}: unsupported bundle schema {data.get('schema')!r}")
        tr = data.get("transcript") or {}
        b = cls(
            video_id=data["video_id"],
            url=data.get("url") or f"https://www.youtube.com/watch?v={data['video_id']}",
            title=data.get("title", ""),
            channel=data.get("channel", ""),
            duration_sec=float(data.get("duration_sec") or 0),
            published_at=data.get("published_at"),
            language=data.get("language"),
            description=data.get("description") or "",
            yt_tags=list(data.get("yt_tags") or []),
            yt_chapters=list(data.get("yt_chapters") or []),
            playlists=list(data.get("playlists") or []),
            account=data.get("account"),
            transcript=Transcript(
                source=tr.get("source", "none"),
                language=tr.get("language"),
                segments=[Segment(float(s["start"]), float(s["end"]), s["text"]) for s in tr.get("segments") or []],
            ),
            frames=[Frame(**{k: f.get(k) for k in ("t", "path", "reason", "ocr_text", "caption") if k in f})
                    for f in data.get("frames") or []],
            audio=dict(data.get("audio") or {}),
            prep=dict(data.get("prep") or {}),
            alt_transcripts={k: [Segment(float(s["start"]), float(s["end"]), s["text"]) for s in v]
                             for k, v in (data.get("alt_transcripts") or {}).items()},
        )
        b.root = path.parent
        return b

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("root", None)
        return d

    def save(self, directory: Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        out = directory / "bundle.json"
        out.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        self.root = directory
        return out

    def audio_path(self) -> Path | None:
        p = self.audio.get("path")
        if not p:
            return None
        p = Path(p)
        return p if p.is_absolute() or self.root is None else self.root / p

    def reference_transcript(self) -> list[Segment] | None:
        """Human captions, if any: the yardstick for transcription."""
        if self.transcript.source == "youtube_manual":
            return self.transcript.segments
        return self.alt_transcripts.get("youtube_manual")

    def frame_path(self, frame: Frame) -> Path:
        p = Path(frame.path)
        return p if p.is_absolute() or self.root is None else self.root / p

    # -- helpers ----------------------------------------------------------------------------
    @property
    def duration_min(self) -> float:
        return self.duration_sec / 60.0

    def duration_bucket(self) -> str:
        m = self.duration_min
        if m < 3:
            return "short"
        if m < 20:
            return "medium"
        if m < 60:
            return "long"
        return "very_long"

    def select_frames(self, max_frames: int) -> list[Frame]:
        """Evenly thin the frame list to at most ``max_frames``, keeping scene cuts first."""
        if max_frames <= 0:
            return []
        if len(self.frames) <= max_frames:
            return list(self.frames)
        step = len(self.frames) / max_frames
        return [self.frames[int(i * step)] for i in range(max_frames)]


def fmt_t(sec: float) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def iter_bundles(root: Path) -> list[VideoBundle]:
    root = Path(root)
    return [VideoBundle.load(p) for p in sorted(root.glob("*/bundle.json"))]
