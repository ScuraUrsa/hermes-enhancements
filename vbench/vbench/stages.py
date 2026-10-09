"""The pipeline stages as plain functions: classify -> vision -> report, plus the native-video
baseline. Each returns a StageResult with the parsed output and every model call's usage and cost."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import prompts as P
from .bundle import VIDEO_TYPES, VideoBundle
from .catalog import Catalog
from .providers import Completion, ProviderError

CHARS_PER_TOKEN = 3.5  # conservative for mixed Polish/English


@dataclass
class Call:
    ref: str
    input_tokens: int | None
    output_tokens: int | None
    latency_sec: float
    equiv_usd: float | None
    marginal_usd: float | None


@dataclass
class StageResult:
    stage: str
    ref: str
    output: Any = None
    error: str | None = None
    problems: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and not self.problems

    def totals(self) -> dict[str, Any]:
        def s(attr):
            vals = [getattr(c, attr) for c in self.calls]
            return None if any(v is None for v in vals) else sum(vals)
        return {"input_tokens": s("input_tokens"), "output_tokens": s("output_tokens"),
                "latency_sec": round(sum(c.latency_sec for c in self.calls), 2),
                "equiv_usd": s("equiv_usd"), "marginal_usd": s("marginal_usd"), "n_calls": len(self.calls)}

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "ref": self.ref, "ok": self.ok, "error": self.error,
                "problems": self.problems, "output": self.output, **self.totals()}


def _call(cat: Catalog, ref: str, res: StageResult, system: str, user: str, **kw) -> Completion:
    c = cat.model(ref).complete(system, user, **kw)
    cost = cat.cost(ref, c)
    res.calls.append(Call(ref, c.input_tokens, c.output_tokens, round(c.latency_sec, 2), cost.equiv_usd,
                          cost.marginal_usd))
    return c


def meta(b: VideoBundle) -> dict[str, Any]:
    return {"title": b.title, "channel": b.channel, "url": b.url, "duration_min": b.duration_min,
            "yt_tags": b.yt_tags, "description": b.description, "yt_chapters": b.yt_chapters,
            "transcript_source": b.transcript.source, "music_ratio": b.audio.get("music_ratio")}


# -- classify --------------------------------------------------------------------------------
def classify(cat: Catalog, ref: str, b: VideoBundle, head_chars: int = 3000) -> StageResult:
    res = StageResult("classify", ref)
    try:
        c = _call(cat, ref, res, P.CLASSIFY_SYSTEM, P.classify_user(meta(b), b.transcript.text(False)[:head_chars]),
                  json_mode=True, max_tokens=800)
        out = P.parse_json(c.text)
        if not isinstance(out, dict) or out.get("video_type") not in VIDEO_TYPES:
            res.problems.append(f"bad video_type {out.get('video_type') if isinstance(out, dict) else out!r}")
        res.output = out
    except (ProviderError, ValueError) as e:
        res.error = str(e)
    return res


# -- vision ----------------------------------------------------------------------------------
def speech_near(b: VideoBundle, t: float, window: float = 15.0) -> str:
    return " ".join(s.text for s in b.transcript.segments if s.end >= t - window and s.start <= t + window)


def frame_budget(b: VideoBundle, frames_per_min: float, max_frames: int) -> int:
    return max(1, min(max_frames, round(b.duration_min * frames_per_min) or 1))


def vision(cat: Catalog, ref: str, b: VideoBundle, frames_per_min: float = 2.0, max_frames: int = 40,
           per_call: int = 6) -> StageResult:
    res = StageResult("vision", ref, output=[])
    if cat.has_vision(ref) is False:
        res.error = f"{ref} has no image input"
        return res
    frames = b.select_frames(frame_budget(b, frames_per_min, max_frames))
    for i in range(0, len(frames), per_call):
        batch = frames[i:i + per_call]
        items = [(f.t, speech_near(b, f.t)) for f in batch]
        try:
            c = _call(cat, ref, res, P.VISION_SYSTEM, P.vision_user(b.title, items),
                      images=[b.frame_path(f) for f in batch], json_mode=True, max_tokens=300 * len(batch) + 200)
            out = P.parse_json(c.text)
            got = out.get("frames", []) if isinstance(out, dict) else out
            if not isinstance(got, list) or len(got) != len(batch):
                res.problems.append(f"batch {i // per_call}: {len(got) if isinstance(got, list) else '?'} "
                                    f"descriptions for {len(batch)} frames")
                got = got if isinstance(got, list) else []
            for f, g in zip(batch, got):  # trust our timestamps, not the model's
                if isinstance(g, dict):
                    res.output.append({**g, "t": f.t})
        except (ProviderError, ValueError) as e:
            res.problems.append(f"batch {i // per_call}: {e}")
    if not res.output:
        res.error = "; ".join(res.problems) or "no frames"
    return res


# -- report ----------------------------------------------------------------------------------
def _chunks(text: str, max_chars: int) -> list[str]:
    out, cur, n = [], [], 0
    for line in text.splitlines():
        if n + len(line) > max_chars and cur:
            out.append("\n".join(cur))
            cur, n = [], 0
        cur.append(line)
        n += len(line) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def report(cat: Catalog, ref: str, b: VideoBundle, video_type: str, frames: list[dict], language: str = "pl",
           context_share: float = 0.6) -> StageResult:
    res = StageResult("report", ref)
    transcript = b.transcript.text() or "(no transcript available)"
    budget_chars = int(cat.context_tokens(ref) * context_share * CHARS_PER_TOKEN)
    try:
        if len(transcript) > budget_chars:  # map-reduce: condense parts, then report from the notes
            parts = _chunks(transcript, budget_chars // 2)
            notes = []
            for i, part in enumerate(parts):
                c = _call(cat, ref, res, P.NOTES_SYSTEM, f"Part {i + 1} of {len(parts)} of '{b.title}':\n{part}",
                          max_tokens=4000)
                notes.append(c.text)
            transcript = "(condensed notes from a long transcript)\n" + "\n\n".join(notes)
        c = _call(cat, ref, res, P.report_system(language), P.report_user(meta(b), video_type, transcript, frames),
                  json_mode=True, max_tokens=6000)
        res.output = P.parse_json(c.text)
        res.problems = P.report_problems(res.output)
    except (ProviderError, ValueError) as e:
        res.error = str(e)
    return res


def video_url_report(cat: Catalog, ref: str, b: VideoBundle, language: str = "pl") -> StageResult:
    """Baseline: one multimodal call on the YouTube URL, no transcript and no frames."""
    res = StageResult("report", ref)
    try:
        c = _call(cat, ref, res, P.report_system(language), P.VIDEO_URL_USER.format(title=b.title),
                  video_url=b.url, json_mode=True, max_tokens=6000)
        res.output = P.parse_json(c.text)
        res.problems = P.report_problems(res.output)
    except (ProviderError, ValueError) as e:
        res.error = str(e)
    return res
