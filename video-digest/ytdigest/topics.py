"""Topic overrides on top of the per-type routing table.

Filip wants AI and software videos (and anything he sends himself) processed in
full by Claude Sonnet through his subscription. Detection is a keyword score
over title, tags, channel, description and the start of the transcript: free,
deterministic, and good enough to pick the expensive path.
"""

from __future__ import annotations

import re

_AI_SOFTWARE = re.compile(
    r"\b(ai|a\.i\.|sztuczn\w* inteligencj\w*|llm\w*|gpt[-\w]*|chatgpt|claude|anthropic|openai|gemini|"
    r"copilot|cursor|agent(s|y|ów|i)?|agentic|mcp|rag|prompt\w*|machine learning|uczeni\w* maszynow\w*|"
    r"deep learning|neural|transformer\w*|ollama|hugging ?face|langchain|crewai|n8n|automation|automatyzacj\w*|"
    r"programowa\w*|programming|programist\w*|developer\w*|coding|code|kod\w*|python|javascript|typescript|"
    r"react|node\.?js|rust|golang|java|c\+\+|sql|api|backend|frontend|devops|docker|kubernetes|k8s|"
    r"terraform|ansible|linux|git(hub)?|software|oprogramowani\w*|open ?source|homelab|self-?host\w*|"
    r"vibe ?coding|saas|startup tech|openclaw|hermes agent)\b",
    re.I,
)


def score_ai_software(info: dict, transcript_head: str = "") -> int:
    """Weighted keyword hits: title/tags count triple, the rest once."""
    strong = " ".join([info.get("title") or "", " ".join(info.get("tags") or []), info.get("channel") or ""])
    weak = " ".join([(info.get("description") or "")[:1500], transcript_head[:3000]])
    return 3 * len(_AI_SOFTWARE.findall(strong)) + len(_AI_SOFTWARE.findall(weak))


def is_ai_software(info: dict, transcript_head: str = "", threshold: int = 6) -> bool:
    return score_ai_software(info, transcript_head) >= threshold


def apply(route: dict, cfg: dict, info: dict, transcript_head: str, tag: str) -> tuple[dict, str | None]:
    """Return (route with overrides, reason or None)."""
    over = {k: {kk: vv for kk, vv in v.items() if kk != "off"}
            for k, v in (cfg.get("topic_routes") or {}).items() if isinstance(v, dict) and v and not v.get("off")}
    if tag == "manual" and over.get("manual"):
        return {**route, **over["manual"]}, "your own link"
    ai = over.get("ai_software")
    if ai and is_ai_software(info, transcript_head, int(cfg.get("ai_software_threshold", 6))):
        return {**route, **ai}, "AI/software topic"
    return route, None
