"""Transcribe downloaded lesson videos on the PC's GPU (GTX 1650 Ti, 4 GB) with
faster-whisper and write a WebVTT file next to each video (prefetch/video.<lang>.vtt).
sitedigest on the VM uses that file as the lesson's captions instead of
transcribing on its CPU.

  python transcribe_pc.py [--site akademiasaas-pl] [--course od-developera-do-foundera-3.0] [--watch]
--watch keeps going while the harvester is still downloading.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\courses")


def _add_cuda_dlls() -> None:
    """The nvidia-* pip wheels ship cuBLAS/cuDNN DLLs; put them on the DLL path."""
    import site

    for sp in site.getsitepackages():
        for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
            d = Path(sp) / sub
            if d.is_dir():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]


def ts(t: float) -> str:
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--course", default="")
    # local copy: the Hugging Face cache download stalls on this PC (no symlinks, Xet bridge)
    ap.add_argument("--model", default=str(Path(__file__).parent / "models" / "faster-whisper-large-v3-turbo"))
    ap.add_argument("--lang", default="pl")
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    _add_cuda_dlls()
    import av

    _open = av.open

    def _av_open(*args, **kw):  # faster-whisper 1.2 passes metadata_errors, which PyAV 19 (py3.14) dropped
        kw.pop("metadata_errors", None)
        return _open(*args, **kw)

    av.open = _av_open
    from faster_whisper import WhisperModel

    model = WhisperModel(a.model, device="cuda", compute_type="int8_float16")
    out = ROOT / a.site
    idle = 0
    while True:
        m = json.loads((out / "map.json").read_text(encoding="utf-8"))
        todo = []
        for p in m["pages"]:
            if a.course and a.course not in p["course_url"]:
                continue
            for v in p.get("videos") or []:
                if v.startswith("local:"):
                    f = out / "pages" / p["key"] / v[len("local:"):]
                    vtt = f.with_name(f"{f.stem}.{a.lang}.vtt")
                    if f.is_file() and not vtt.is_file():
                        todo.append((p, f, vtt))
        if not todo:
            if not a.watch or idle > 40:  # ~20 min without new videos
                break
            idle += 1
            time.sleep(30)
            continue
        idle = 0
        for p, f, vtt in todo:
            t0 = time.time()
            segs, info = model.transcribe(str(f), language=a.lang, vad_filter=True, beam_size=5,
                                          condition_on_previous_text=False)
            lines = ["WEBVTT", ""]
            n = 0
            for s in segs:
                text = s.text.strip()
                if text:
                    n += 1
                    lines += [f"{ts(s.start)} --> {ts(s.end)}", text, ""]
            tmp = vtt.with_suffix(".tmp")
            tmp.write_text("\n".join(lines), encoding="utf-8")
            tmp.replace(vtt)
            took = time.time() - t0
            print(time.strftime("%H:%M:%S"), f"{p['title'][:50]} | {info.duration / 60:.1f} min audio, {n} segments, "
                  f"{took:.0f} s ({info.duration / max(took, 1):.1f}x)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
