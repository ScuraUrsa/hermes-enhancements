"""Is the fast transcriber good enough for this course? Transcribes the first minutes of a few
lessons with large-v3-turbo (the default) and with large-v3 (3-4x slower), both with the
course's hotwords and corrections, and measures how much they disagree (WER between them).
Low disagreement: turbo is enough. High (> --threshold): use large-v3 for the course.
On Polish TEDx talks with human captions turbo had 2.5-7% WER (asr_bench.py).

  python asr_check.py --course od-developera-do-foundera-3.0 [--lessons 3] [--minutes 8]
Writes D:/courses/<site>/asr/<course>.check.json.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import asr_bench
import transcribe_pc

MODELS = Path(__file__).parent / "models"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--course", required=True)
    ap.add_argument("--lessons", type=int, default=3)
    ap.add_argument("--minutes", type=float, default=8)
    ap.add_argument("--threshold", type=float, default=0.10)
    a = ap.parse_args()
    transcribe_pc._add_cuda_dlls()
    import av

    _open = av.open
    av.open = lambda *x, **kw: _open(*x, **{k: v for k, v in kw.items() if k != "metadata_errors"})
    from faster_whisper import WhisperModel

    out = transcribe_pc.ROOT / a.site
    m = json.loads((out / "map.json").read_text(encoding="utf-8"))
    vids = []
    for p in m["pages"]:
        if a.course in p.get("course_url", ""):
            vids += [(p, out / "pages" / p["key"] / v[len("local:"):]) for v in p.get("videos") or [] if v.startswith("local:")]
    vids = [(p, f) for p, f in vids if f.is_file()]
    if not vids:
        raise SystemExit("no local videos for this course")
    step = max(1, len(vids) // a.lessons)
    sample = vids[step // 2::step][: a.lessons]  # spread over the course
    cfg = transcribe_pc.asr_settings(out, sample[0][0]["course_url"])
    clip = [0, a.minutes * 60]
    texts: dict[str, list[str]] = {}
    took: dict[str, float] = {}
    for name in ("faster-whisper-large-v3-turbo", "faster-whisper-large-v3"):
        model = WhisperModel(str(MODELS / name), device="cuda", compute_type="int8_float16")
        t0 = time.time()
        texts[name] = []
        for p, f in sample:
            segs, _ = model.transcribe(str(f), language="pl", vad_filter=True, beam_size=5, condition_on_previous_text=False,
                                       hotwords=cfg.get("hotwords") or None, clip_timestamps=clip)
            texts[name].append(transcribe_pc.apply_fixes(" ".join(s.text.strip() for s in segs), cfg))
        took[name] = round(time.time() - t0)
        del model
    rows = []
    for i, (p, f) in enumerate(sample):
        ref = asr_bench.words(texts["faster-whisper-large-v3"][i])
        hyp = asr_bench.words(texts["faster-whisper-large-v3-turbo"][i])
        rows.append({"title": p.get("title"), "disagreement": asr_bench.wer(ref, hyp)["wer"],
                     "examples": asr_bench.examples(ref, hyp, 8)})
    avg = round(sum(r["disagreement"] for r in rows) / len(rows), 4)
    res = {"course": a.course, "minutes_per_lesson": a.minutes, "seconds": took, "avg_disagreement": avg,
           "decision": "large-v3" if avg > a.threshold else "turbo", "lessons": rows}
    (out / "asr" / f"{a.course}.check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "lessons"}, ensure_ascii=False))
    for r in rows:
        print(f"  {r['disagreement']:.3f}  {r['title'][:60]}  | {'; '.join(r['examples'][:5])}")


if __name__ == "__main__":
    main()
