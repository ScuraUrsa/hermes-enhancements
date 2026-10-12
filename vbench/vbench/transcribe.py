"""Transcription track: when a video has no captions, which speech-to-text is good enough?

Yardstick: human (manual) YouTube captions of the same video. Score = 100 x (1 - WER) on the first
``window_sec`` seconds (default 10 minutes), which keeps the word alignment cheap and the comparison
fair across candidates.

Candidate refs:
  groq:whisper-large-v3-turbo / groq:whisper-large-v3   Groq API (GROQ_API_KEY), audio cut in 10-min mp3s
  youtube:auto                                          YouTube's automatic captions, if in the bundle
  local:faster-whisper-<size>                           faster-whisper on the VM's CPU (pip install faster-whisper)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .bundle import Segment, VideoBundle
from .providers import split_ref
from .stages import Call, StageResult

PRICE_PER_AUDIO_HOUR = {"groq:whisper-large-v3-turbo": 0.04, "groq:whisper-large-v3": 0.111, "youtube:auto": 0.0}


def normalize_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\[[^\]]*\]", " ", text)  # [Music], [Applause]
    text = re.sub(r"[^\w\s']", " ", text)
    return text.split()


def wer(ref: list[str], hyp: list[str]) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def window_text(segs: list[Segment], window_sec: float) -> str:
    return " ".join(s.text for s in segs if s.start < window_sec)


def _cut_audio(src: Path, tmp: Path, window_sec: float, chunk_sec: int = 600) -> list[tuple[float, Path]]:
    out = []
    for i, start in enumerate(range(0, int(window_sec), chunk_sec)):
        dst = tmp / f"chunk{i:03d}.mp3"
        dur = min(chunk_sec, window_sec - start)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
                        "-ac", "1", "-ar", "16000", "-b:a", "48k", str(dst)], check=True)
        if dst.exists() and dst.stat().st_size > 1000:
            out.append((float(start), dst))
    return out


def _groq(model: str, audio: Path, language: str | None) -> dict:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    boundary = uuid.uuid4().hex
    fields = {"model": model, "response_format": "verbose_json", "temperature": "0"}
    if language:
        fields["language"] = language
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{audio.name}\"\r\n"
             "Content-Type: audio/mpeg\r\n\r\n").encode() + audio.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/audio/transcriptions", data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < 3:
                time.sleep(10 * 2**i)
                continue
            raise RuntimeError(f"Groq HTTP {e.code}: {e.read()[:300]!r}") from e
    raise RuntimeError("unreachable")


def _faster_whisper(size: str, audio: Path, language: str | None) -> list[dict]:
    from faster_whisper import WhisperModel  # optional dependency

    model = WhisperModel(size, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(audio), language=language, vad_filter=True)
    return [{"start": s.start, "end": s.end, "text": s.text} for s in segs]


def transcribe(ref: str, b: VideoBundle, window_sec: float = 600.0) -> StageResult:
    res = StageResult("transcribe", ref)
    gold = b.reference_transcript()
    if not gold:
        res.error = "no manual captions to compare against"
        return res
    window = min(window_sec, b.duration_sec or window_sec)
    provider, model = split_ref(ref)
    lang = b.language or b.transcript.language
    t0 = time.monotonic()
    try:
        if provider == "youtube":
            hyp = b.alt_transcripts.get(f"youtube_{model}") or (b.transcript.segments if b.transcript.source ==
                                                                f"youtube_{model}" else None)
            if hyp is None:
                raise RuntimeError(f"bundle has no youtube_{model} transcript")
        else:
            audio = b.audio_path()
            if not audio or not audio.exists():
                raise RuntimeError("bundle has no audio file (audio.path)")
            hyp = []
            with tempfile.TemporaryDirectory(prefix="vbench-asr-") as tmp:
                for offset, chunk in _cut_audio(audio, Path(tmp), window):
                    if provider == "groq":
                        segs = _groq(model, chunk, lang).get("segments") or []
                    elif provider == "local" and model.startswith("faster-whisper-"):
                        segs = _faster_whisper(model.removeprefix("faster-whisper-"), chunk, lang)
                    else:
                        raise RuntimeError(f"unknown transcription candidate {ref}")
                    hyp += [Segment(offset + float(s["start"]), offset + float(s["end"]), s["text"]) for s in segs]
    except Exception as e:  # noqa: BLE001 - every failure is a scored failure
        res.error = str(e)
        return res
    dt = time.monotonic() - t0
    w = wer(normalize_words(window_text(gold, window)), normalize_words(window_text(hyp, window)))
    hours = (b.duration_sec or window) / 3600  # cost of transcribing the whole video
    price = PRICE_PER_AUDIO_HOUR.get(ref, 0.0)
    res.output = {"wer": round(w, 4), "window_sec": window, "text": window_text(hyp, window)[:5000]}
    res.calls.append(Call(ref, None, None, round(dt, 2), round(price * hours, 5),
                          0.0 if provider in ("youtube", "local") else round(price * hours, 5)))
    return res


def score_transcribe(res: StageResult) -> dict:
    if not res.output:
        return {"score": 0.0, "gate": res.error or "no output"}
    return {"score": round(100 * max(0.0, 1 - res.output["wer"]), 1), "wer": res.output["wer"]}
