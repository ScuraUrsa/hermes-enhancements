"""How good are our local transcripts? Word error rate of the PC pipeline (faster-whisper
large-v3-turbo, same settings as transcribe_pc.py) against human-made YouTube captions,
with YouTube's own auto-captions as a baseline.

  python asr_bench.py VIDEO_ID [VIDEO_ID ...] [--lang pl]
Results: D:\\courses\\asr-bench\\<id>\\ and results.json.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import transcribe_pc

OUT = Path(r"D:\courses\asr-bench")
YTDLP = str(Path(sys.executable).with_name("yt-dlp.exe"))


def vtt_text(path: Path) -> str:
    """Caption text without timings, tags and the rolling duplicates of auto-captions."""
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if out and line == out[-1]:
            continue
        out.append(line)
    return " ".join(out)


def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)  # [muzyka], (oklaski)
    return re.findall(r"[^\W_]+", text)


def wer(ref: list[str], hyp: list[str]) -> dict:
    """Levenshtein over words: substitutions + deletions + insertions over reference length."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return {"wer": round(prev[-1] / max(len(ref), 1), 4), "ref_words": len(ref), "hyp_words": len(hyp)}


def examples(ref: list[str], hyp: list[str], n: int = 12) -> list[str]:
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    res = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "replace" and a2 - a1 <= 4:
            res.append(f"{' '.join(ref[a1:a2])} -> {' '.join(hyp[b1:b2])}")
    return res[:: max(1, len(res) // n)][:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--lang", default="pl")
    ap.add_argument("--model", default=str(Path(__file__).parent / "models" / "faster-whisper-large-v3-turbo"))
    a = ap.parse_args()
    transcribe_pc._add_cuda_dlls()
    import av

    _open = av.open
    av.open = lambda *x, **kw: _open(*x, **{k: v for k, v in kw.items() if k != "metadata_errors"})
    from faster_whisper import WhisperModel

    model = WhisperModel(a.model, device="cuda", compute_type="int8_float16")
    results = []
    for vid in a.ids:
        d = OUT / vid
        (d / "human").mkdir(parents=True, exist_ok=True)
        (d / "auto").mkdir(exist_ok=True)
        url = f"https://www.youtube.com/watch?v={vid}"
        for _ in range(3):  # YouTube answers 403 now and then
            if [f for f in d.glob("audio.*") if f.suffix != ".part"]:
                break
            subprocess.run([YTDLP, "-q", "-f", "bestaudio/best", "-o", str(d / "audio.%(ext)s"), url], check=False)
        if not [f for f in d.glob("audio.*") if f.suffix != ".part"]:
            print(f"{vid}: audio download failed, skipped", flush=True)
            continue
        if not list((d / "human").glob("*.vtt")):
            subprocess.run([YTDLP, "-q", "--skip-download", "--write-subs", "--sub-langs", a.lang, "--sub-format", "vtt",
                            "-o", str(d / "human" / "s"), url], check=True)
        if not list((d / "auto").glob("*.vtt")):
            subprocess.run([YTDLP, "-q", "--skip-download", "--write-auto-subs", "--sub-langs", a.lang, "--sub-format", "vtt",
                            "-o", str(d / "auto" / "s"), url], check=False)
        audio = next(f for f in d.glob("audio.*") if f.suffix != ".part")
        t0 = time.time()
        segs, info = model.transcribe(str(audio), language=a.lang, vad_filter=True, beam_size=5,
                                      condition_on_previous_text=False)
        segs = list(segs)
        took = time.time() - t0
        ours = " ".join(s.text.strip() for s in segs)
        (d / "ours.txt").write_text(ours, encoding="utf-8")
        ref = words(vtt_text(next((d / "human").glob("*.vtt"))))
        hyp = words(ours)
        r = {"id": vid, "minutes": round(info.duration / 60, 1), "seconds_on_gpu": round(took),
             "ours": wer(ref, hyp), "examples": examples(ref, hyp),
             # Whisper's own confidence: share of speech in low-confidence segments
             "low_conf_share": round(sum(s.end - s.start for s in segs if s.avg_logprob < -0.6)
                                     / max(sum(s.end - s.start for s in segs), 1), 3)}
        auto = list((d / "auto").glob("*.vtt"))
        if auto:
            r["youtube_auto"] = wer(ref, words(vtt_text(auto[0])))
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "examples"}, ensure_ascii=False), flush=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
