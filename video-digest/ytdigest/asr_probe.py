"""Availability probe for the transcription backends (--check-asr).

Prints one line per step of transcript_order: `step: status (reason)`.
Statuses: "available" = installable backend ready, "missing" = not installed /
no API key; manual and auto captions depend on the video, so they always read
missing here. The process exits 0 when at least one ASR backend (groq,
parakeet, local) is available, 1 otherwise.
The probe is hermetic: package imports only, no network, no model download.
Run as: ytdigest --check-asr  |  python -m ytdigest.asr_probe
"""
from __future__ import annotations

import importlib
import os
from importlib import metadata

_IMPORT = importlib.import_module  # seam for tests: fake a broken install

ASR_STEPS = {"groq", "parakeet", "local"}  # the steps that can transcribe any audio
_PKG = {"local": "faster-whisper", "parakeet": "onnx-asr"}
_MOD = {"local": "faster_whisper", "parakeet": "onnx_asr"}
_MISSING = {"local": "faster-whisper not installed",
            "parakeet": "onnx-asr not installed",
            "groq": "GROQ_API_KEY not set"}


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except Exception:  # PackageNotFoundError / broken metadata
        return ""


def probe_step(step: str, importer=None) -> dict:
    """One row {step, status, reason}; importer is injectable for tests."""
    if importer is None:
        importer = _IMPORT
    if step == "groq":
        if os.environ.get("GROQ_API_KEY"):
            return {"step": step, "status": "available", "reason": "GROQ_API_KEY set"}
        return {"step": step, "status": "missing", "reason": _MISSING[step]}
    if step in _MOD:
        try:
            importer(_MOD[step])
        except Exception as exc:  # missing or broken install — say which and how
            return {"step": step, "status": "missing",
                    "reason": f"{_MISSING[step]} ({type(exc).__name__})"}
        return {"step": step, "status": "available", "reason": f"{_PKG[step]} {_version(_PKG[step])}"}
    if step in ("manual", "auto"):
        what = "uploaded captions" if step == "manual" else "YouTube auto-captions"
        return {"step": step, "status": "missing", "reason": f"{what}: depends on the video"}
    return {"step": step, "status": "missing", "reason": "unknown transcript step"}


def probe(cfg: dict, importer=None) -> list[dict]:
    """One row per step of cfg["transcript_order"], in the configured order."""
    return [probe_step(step, importer) for step in cfg["transcript_order"]]


def check(cfg: dict, importer=None) -> bool:
    """True when at least one ASR backend (groq/parakeet/local) is available."""
    return any(r["status"] == "available" for r in probe(cfg, importer) if r["step"] in ASR_STEPS)


def run(cfg: dict, importer=None) -> int:
    """Print the per-step state; return 0 iff an ASR backend is available."""
    rows = probe(cfg, importer)
    for r in rows:
        print(f"{r['step']}: {r['status']} ({r['reason']})")
    working = [r["step"] for r in rows if r["status"] == "available" and r["step"] in ASR_STEPS]
    if working:
        print(f"check-asr: ok, transcribers ready: {', '.join(working)}")
        return 0
    print("check-asr: no ASR backend available; videos without captions end with source=none")
    return 1


def main(cfg: dict | None = None) -> int:
    from . import config
    return run(cfg or config.load(None))


if __name__ == "__main__":
    import sys
    sys.exit(main())