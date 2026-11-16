"""Turn judge verdicts into 0-100 scores, with weights that depend on the kind of video:
in a podcast the picture hardly matters, in a coding tutorial it carries half the content."""

from __future__ import annotations

from typing import Any

from . import prompts as P
from .catalog import Catalog
from .providers import ProviderError

VISUAL_HEAVY = {"tutorial_screen", "lecture_slides", "explainer_visual", "vlog_travel", "review_product",
                "documentary"}
TALK = {"podcast_talk", "interview", "news_commentary"}

WEIGHTS = {
    "default": {"key_points": 0.40, "visual": 0.20, "faithfulness": 0.20, "tags": 0.10, "usefulness": 0.10},
    "visual": {"key_points": 0.35, "visual": 0.30, "faithfulness": 0.15, "tags": 0.10, "usefulness": 0.10},
    "talk": {"key_points": 0.50, "visual": 0.05, "faithfulness": 0.25, "tags": 0.10, "usefulness": 0.10},
}

VERDICT = {"full": 1.0, "partial": 0.5, "missing": 0.0}


def weights_for(video_type: str) -> dict[str, float]:
    if video_type in VISUAL_HEAVY:
        return WEIGHTS["visual"]
    if video_type in TALK:
        return WEIGHTS["talk"]
    return WEIGHTS["default"]


def recall(items: list[dict], verdicts: list[dict], weight_key: str | None = None) -> float | None:
    if not items:
        return None
    by_id = {v.get("id"): VERDICT.get(str(v.get("verdict")).lower(), 0.0) for v in verdicts or [] if isinstance(v, dict)}
    num = den = 0.0
    for it in items:
        w = float(it.get(weight_key, 1)) if weight_key else 1.0
        den += w
        num += w * by_id.get(it.get("id"), 0.0)
    return num / den if den else None


def penalty(issues: list[dict], major: float = 0.3, minor: float = 0.1) -> float:
    p = sum(major if str(i.get("severity")).lower() == "major" else minor for i in issues or [] if isinstance(i, dict))
    return min(1.0, p)


def score_report(label: dict, report: dict | None, verdict: dict | None, problems: list[str]) -> dict[str, Any]:
    if report is None or verdict is None or problems:
        return {"score": 0.0, "gate": "invalid output" if problems or report is None else "judge failed"}
    vt = label.get("video_type", "other")
    w = dict(weights_for(vt))
    kp = recall(label.get("key_points", []), verdict.get("key_points", []), "importance") or 0.0
    vis = recall(label.get("visual_facts", []), verdict.get("visual_facts", []))
    if vis is None:  # nothing visual to find: that weight goes to key points
        w["key_points"] += w.pop("visual")
    faith = 1.0 - penalty(verdict.get("unsupported_claims", []))
    rt, gt = report.get("tags") or [], label.get("tags") or []
    m = min(int(verdict.get("tag_matches") or 0), len(rt))
    prec, rec = (m / len(rt) if rt else 0.0), (min(1.0, m / len(gt)) if gt else 0.0)
    tags = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    useful = (min(5, max(1, float(verdict.get("usefulness") or 1))) - 1) / 4
    parts = {"key_points": kp, "visual": vis, "faithfulness": faith, "tags": tags, "usefulness": useful}
    total = sum(w[k] * (parts[k] or 0.0) for k in w)
    return {"score": round(100 * total, 1), **{k: (None if v is None else round(v, 3)) for k, v in parts.items()},
            "major_errors": sum(1 for c in verdict.get("unsupported_claims", []) or []
                                if isinstance(c, dict) and str(c.get("severity")).lower() == "major")}


def score_vision(label: dict, frames: list[dict] | None, verdict: dict | None) -> dict[str, Any]:
    if not frames or verdict is None:
        return {"score": 0.0, "gate": "no output" if not frames else "judge failed"}
    vis = recall(label.get("visual_facts", []), verdict.get("visual_facts", []))
    ocr = float(verdict.get("ocr_accuracy") if verdict.get("ocr_accuracy") is not None else 1.0)
    hall = penalty(verdict.get("hallucinations", []))
    vis_v = 1.0 if vis is None else vis
    total = 0.6 * vis_v + 0.25 * ocr + 0.15 * (1 - hall)
    return {"score": round(100 * total, 1), "visual": None if vis is None else round(vis, 3),
            "ocr": round(ocr, 3), "hallucination_penalty": round(hall, 3)}


def score_classify(label: dict, out: dict | None) -> dict[str, Any]:
    if not isinstance(out, dict):
        return {"score": 0.0, "type_ok": False, "artistic_ok": False}
    type_ok = out.get("video_type") == label.get("video_type")
    art_ok = bool(out.get("is_artistic")) == bool(label.get("is_artistic"))
    # Calling a lecture "artistic" loses a whole report; a wrong type only shifts weights.
    score = 100.0 if type_ok and art_ok else 60.0 if art_ok else 0.0
    return {"score": score, "type_ok": type_ok, "artistic_ok": art_ok}


# -- judge calls -----------------------------------------------------------------------------
def judge_report(cat: Catalog, judge_ref: str, label: dict, report: dict, transcript: str,
                 max_transcript_chars: int = 400_000) -> tuple[dict | None, dict]:
    usage: dict[str, Any] = {}
    try:
        c = cat.model(judge_ref).complete(P.JUDGE_REPORT_SYSTEM,
                                          P.judge_report_user(label, report, transcript[:max_transcript_chars]),
                                          json_mode=True, max_tokens=4000)
        cost = cat.cost(judge_ref, c)
        usage = {"judge_equiv_usd": cost.equiv_usd, "judge_latency_sec": round(c.latency_sec, 2)}
        return P.parse_json(c.text), usage
    except (ProviderError, ValueError) as e:
        return None, {**usage, "judge_error": str(e)}


def judge_vision(cat: Catalog, judge_ref: str, label: dict, frames: list[dict]) -> tuple[dict | None, dict]:
    usage: dict[str, Any] = {}
    try:
        c = cat.model(judge_ref).complete(P.JUDGE_VISION_SYSTEM, P.judge_vision_user(label, frames),
                                          json_mode=True, max_tokens=3000)
        cost = cat.cost(judge_ref, c)
        usage = {"judge_equiv_usd": cost.equiv_usd, "judge_latency_sec": round(c.latency_sec, 2)}
        return P.parse_json(c.text), usage
    except (ProviderError, ValueError) as e:
        return None, {**usage, "judge_error": str(e)}
