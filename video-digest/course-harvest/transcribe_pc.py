"""Transcribe downloaded lesson videos on the PC's GPU (GTX 1650 Ti, 4 GB) with
faster-whisper and write a WebVTT file next to each video (prefetch/video.<lang>.vtt).
sitedigest on the VM uses that file as the lesson's captions instead of
transcribing on its CPU.

  python transcribe_pc.py [--site akademiasaas-pl] [--course od-developera-do-foundera-3.0] [--watch]
--watch keeps going while the harvester is still downloading.

Per-course ASR settings in D:/courses/<site>/asr/<course-slug>.json (made with glossary.py):
  "hotwords": course terms Whisper should spell right (halves jargon misspellings in our test),
  "corrections" / "corrections_from": whole-word replacements applied to the text afterwards, only
  for spellings that never occur in Polish ("czern" -> "churn", "sasa" -> "SaaS-a").
--redo re-transcribes lessons whose VTT predates the course's ASR settings (old VTT kept as *.vtt.v1);
--fix-only applies the corrections to existing VTTs without the GPU.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


ASR_VERSION = 2  # 2 = course hotwords + corrections


def asr_settings(site_dir: Path, course_url: str) -> dict:
    f = site_dir / "asr" / f"{course_url.rstrip('/').rsplit('/', 1)[-1]}.json"
    if not f.is_file():
        return {}
    cfg = json.loads(f.read_text(encoding="utf-8"))
    fixes: dict[str, str] = {}
    for extra in cfg.get("corrections_from") or []:
        fixes.update(json.loads((f.parent / extra).read_text(encoding="utf-8")))
    fixes.update(cfg.get("corrections") or {})
    cfg["fixes"] = {k.lower(): v for k, v in fixes.items()}
    if fixes:
        cfg["fix_re"] = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, cfg["fixes"]), key=len, reverse=True))
                                   + r")(?![\w-])", re.IGNORECASE)
    return cfg


def apply_fixes(text: str, cfg: dict) -> str:
    if not cfg.get("fix_re"):
        return text
    return cfg["fix_re"].sub(lambda m: cfg["fixes"][m.group(0).lower()], text)


def marker(vtt: Path) -> Path:
    return vtt.with_name(vtt.name + f".asr{ASR_VERSION}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--course", default="")
    # local copy: the Hugging Face cache download stalls on this PC (no symlinks, Xet bridge)
    ap.add_argument("--model", default=str(Path(__file__).parent / "models" / "faster-whisper-large-v3-turbo"))
    ap.add_argument("--lang", default="pl")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--redo", action="store_true", help="re-transcribe VTTs made before the course's ASR settings")
    ap.add_argument("--fix-only", action="store_true", help="only apply the corrections to existing VTTs")
    a = ap.parse_args()
    if a.fix_only:
        return fix_only(a)
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
        settings: dict[str, dict] = {}
        for p in m["pages"]:
            if a.course and a.course not in p["course_url"]:
                continue
            if p["course_url"] not in settings:
                settings[p["course_url"]] = asr_settings(out, p["course_url"])
            for v in p.get("videos") or []:
                if v.startswith("local:"):
                    f = out / "pages" / p["key"] / v[len("local:"):]
                    vtt = f.with_name(f"{f.stem}.{a.lang}.vtt")
                    stale = a.redo and settings[p["course_url"]] and vtt.is_file() and not marker(vtt).is_file()
                    if f.is_file() and (not vtt.is_file() or stale):
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
            cfg = settings[p["course_url"]]
            segs, info = model.transcribe(str(f), language=a.lang, vad_filter=True, beam_size=5,
                                          condition_on_previous_text=False, hotwords=cfg.get("hotwords") or None)
            lines = ["WEBVTT", ""]
            n = 0
            for s in segs:
                text = apply_fixes(s.text.strip(), cfg)
                if text:
                    n += 1
                    lines += [f"{ts(s.start)} --> {ts(s.end)}", text, ""]
            tmp = vtt.with_suffix(".tmp")
            tmp.write_text("\n".join(lines), encoding="utf-8")
            old = vtt.with_name(vtt.name + ".v1")
            if vtt.is_file() and not old.is_file():
                vtt.replace(old)  # keep the first transcript for comparison
            tmp.replace(vtt)
            if cfg:
                marker(vtt).write_text(json.dumps({"hotwords": cfg.get("hotwords"), "at": time.time()}), encoding="utf-8")
            took = time.time() - t0
            print(time.strftime("%H:%M:%S"), f"{p['title'][:50]} | {info.duration / 60:.1f} min audio, {n} segments, "
                  f"{took:.0f} s ({info.duration / max(took, 1):.1f}x)", flush=True)


def fix_only(a) -> int:
    out = ROOT / a.site
    m = json.loads((out / "map.json").read_text(encoding="utf-8"))
    changed = files = 0
    settings: dict[str, dict] = {}
    for p in m["pages"]:
        if a.course and a.course not in p["course_url"]:
            continue
        cfg = settings.setdefault(p["course_url"], asr_settings(out, p["course_url"]))
        for vtt in (out / "pages" / p["key"]).glob(f"prefetch/*.{a.lang}.vtt"):
            old = vtt.read_text(encoding="utf-8")
            new = apply_fixes(old, cfg)
            if new != old:
                vtt.write_text(new, encoding="utf-8")
                files += 1
                changed += sum(1 for x, y in zip(old.split(), new.split()) if x != y)
    print(f"corrected {changed} words in {files} VTT files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
