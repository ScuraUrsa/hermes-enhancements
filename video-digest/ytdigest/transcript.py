"""Transcript: uploaded captions, Whisper (Groq or local), or auto-captions.

Order comes from config["transcript_order"]. YouTube auto-captions are the
last resort by default because Filip doesn't want to rely on them; Whisper on
Groq costs about $0.04 per hour of audio and is much better.
Source names follow vbench's VideoBundle: youtube_manual, youtube_auto,
whisper_groq, whisper_local, none.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import fetch

SOURCE_NAMES = {
    "manual": "youtube_manual",
    "auto": "youtube_auto",
    "groq": "whisper_groq",
    "local": "whisper_local",
    "parakeet": "parakeet_local",
}


class TranscriptUnavailable(RuntimeError):
    pass


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def split_audio(audio: Path, out_dir: Path, chunk_sec: int = 1200) -> list[tuple[Path, float]]:
    """Re-encode to 16 kHz mono Opus (~3 MB per 20 min) and split, so every
    chunk stays far below Groq's 25 MB upload limit."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("chunk_*.ogg"):
        old.unlink()
    _ffmpeg(
        "-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k",
        "-f", "segment", "-segment_time", str(chunk_sec), "-reset_timestamps", "1",
        str(out_dir / "chunk_%03d.ogg"),
    )
    chunks = sorted(out_dir.glob("chunk_*.ogg"))
    return [(c, i * chunk_sec) for i, c in enumerate(chunks)]


def whisper_groq(audio: Path, work: Path, model: str, language: str | None = None) -> dict:
    import requests

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise TranscriptUnavailable("GROQ_API_KEY not set")
    segments, lang = [], language
    for chunk, offset in split_audio(audio, work / "chunks"):
        data = {"model": model, "response_format": "verbose_json", "temperature": "0"}
        if language:
            data["language"] = language
        with chunk.open("rb") as fh:
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data=data,
                files={"file": (chunk.name, fh, "audio/ogg")},
                timeout=600,
            )
        if r.status_code >= 400:
            raise TranscriptUnavailable(f"Groq {r.status_code}: {r.text[:300]}")
        body = r.json()
        lang = lang or body.get("language")
        for s in body.get("segments") or []:
            text = (s.get("text") or "").strip()
            if text:
                segments.append(
                    {"start": round(s["start"] + offset, 2), "end": round(s["end"] + offset, 2), "text": text}
                )
    return {"segments": segments, "language": _lang_code(lang)}


def whisper_local(audio: Path, model_size: str, language: str | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise TranscriptUnavailable("faster-whisper not installed") from exc
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # vad_filter stays off: VAD drops sung/music parts (crewai-orchestrator D2).
    segs, info = model.transcribe(str(audio), language=language, vad_filter=False, beam_size=1)
    segments = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segs
        if s.text.strip()
    ]
    return {"segments": segments, "language": info.language}


def parakeet(audio: Path, work: Path) -> dict:
    """NVIDIA Parakeet-TDT-0.6B-v3 through onnx-asr: free, CPU-only, much faster
    than Whisper on the VM, 25 languages including Polish."""
    try:
        import onnx_asr  # type: ignore
    except ImportError as exc:
        raise TranscriptUnavailable("onnx-asr not installed") from exc
    wav = work / "audio16k.wav"
    _ffmpeg("-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", str(wav))
    vad = onnx_asr.load_vad("silero")
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3").with_vad(vad)
    segments = []
    for res in model.recognize(str(wav)):
        text = (getattr(res, "text", "") or "").strip()
        if text:
            segments.append({"start": round(float(getattr(res, "start", 0)), 2),
                             "end": round(float(getattr(res, "end", 0)), 2), "text": text})
    wav.unlink(missing_ok=True)
    return {"segments": segments, "language": None}


_LANG_NAMES = {"polish": "pl", "english": "en", "german": "de", "russian": "ru", "ukrainian": "uk"}


def _lang_code(lang: str | None) -> str | None:
    if not lang:
        return None
    lang = lang.lower()
    return _LANG_NAMES.get(lang, lang[:2] if len(lang) > 3 else lang)


def get(info: dict, cfg: dict, work: Path, cookies: str | None = None, audio_getter=None) -> dict:
    """Return {source, language, segments}. `audio_getter()` downloads audio lazily
    (only when a Whisper step actually runs)."""
    url = info.get("webpage_url") or fetch.watch_url(info["id"])
    duration_min = (info.get("duration") or 0) / 60
    hint = (info.get("language") or "").split("-")[0] or None
    errors = []
    audio: Path | None = None
    for step in cfg["transcript_order"]:
        try:
            if step in ("manual", "auto"):
                track = fetch.pick_caption(info, step, cfg["caption_languages"])
                if not track:
                    errors.append(f"{step}: no track")
                    continue
                vtt = fetch.download_caption(url, track[0], step, work / "captions", cookies)
                segs = fetch.parse_vtt(vtt.read_text(encoding="utf-8")) if vtt else []
                if segs:
                    return {"source": SOURCE_NAMES[step], "language": track[0].split("-")[0], "segments": segs}
                errors.append(f"{step}: empty")
                continue
            if step == "local" and duration_min > cfg["whisper_local_max_minutes"]:
                errors.append(f"local: video longer than {cfg['whisper_local_max_minutes']} min")
                continue
            if audio is None:
                audio = audio_getter() if audio_getter else fetch.download_audio(url, work, cookies)
            if step == "groq":
                out = whisper_groq(audio, work, cfg["whisper_groq_model"], hint)
            elif step == "local":
                out = whisper_local(audio, cfg["whisper_local_model"], hint)
            elif step == "parakeet":
                out = parakeet(audio, work)
                out["language"] = out["language"] or hint
            else:
                errors.append(f"{step}: unknown step")
                continue
            if out["segments"]:
                return {"source": SOURCE_NAMES[step], **out}
            errors.append(f"{step}: empty")
        except TranscriptUnavailable as exc:
            errors.append(f"{step}: {exc}")
        except Exception as exc:  # network, ffmpeg, yt-dlp; try the next step
            errors.append(f"{step}: {type(exc).__name__}: {str(exc)[:200]}")
    return {"source": "none", "language": hint, "segments": [], "errors": errors}


def degradation_warning(tr: dict) -> str | None:
    """One loud line when every transcription step failed; None when a transcript
    exists. Pipeline prefixes the video id and logs it — a lost transcript must
    never be silent (the errors say which step killed it and why)."""
    if tr.get("source") not in (None, "", "none"):
        return None
    reason = "; ".join(str(err) for err in tr.get("errors") or []) or "no step recorded a reason"
    return f"WARNING: no transcript (source=none): {reason}"


def speech_ratio(segments: list[dict], duration: float) -> float | None:
    if not duration:
        return None
    covered = sum(max(0.0, s["end"] - s["start"]) for s in segments)
    return round(min(1.0, covered / duration), 3)


def plain_text(segments: list[dict]) -> str:
    return " ".join(s["text"] for s in segments)


def save(path: Path, transcript: dict) -> None:
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")
