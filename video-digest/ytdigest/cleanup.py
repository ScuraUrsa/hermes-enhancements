"""Readable transcript: YouTube auto captions have no punctuation or casing.

The transcript is cut into paragraphs of about a minute (the same cut Notion
shows), and a cheap model adds punctuation, casing and obvious word fixes in
batches. Each paragraph keeps its start time; if the model returns the wrong
number of paragraphs for a batch, that batch stays as it was.
"""

from __future__ import annotations

SYSTEM = (
    "You restore punctuation and capitalisation in raw speech-to-text. Keep the speaker's words and "
    "language; fix only obvious mis-hearings; do not summarise, translate or drop anything. "
    "Answer with one JSON object only."
)


def minute_paragraphs(segments: list[dict], every: float = 60.0) -> list[dict]:
    out, buf, start = [], [], segments[0]["start"] if segments else 0.0
    for s in segments:
        if buf and s["start"] - start >= every:
            out.append({"t": start, "text": " ".join(buf)})
            buf, start = [], s["start"]
        buf.append(s["text"].strip())
    if buf:
        out.append({"t": start, "text": " ".join(buf)})
    return out


def paragraphs(client, ref: str, segments: list[dict], lang: str, batch: int = 8) -> list[dict]:
    paras = minute_paragraphs(segments)
    for i in range(0, len(paras), batch):
        group = paras[i : i + batch]
        user = (
            f"Fix these {len(group)} transcript paragraphs. Return "
            '{"paragraphs": ["...", ...]} with exactly the same number of items, in order.\n\n'
            + "\n\n".join(f"[{n}] {p['text']}" for n, p in enumerate(group, 1))
        )
        try:
            out = client.json(ref, SYSTEM, user, max_tokens=min(8000, 400 + sum(len(p["text"]) for p in group) // 2))
        except Exception:
            continue
        fixed = out.get("paragraphs")
        if isinstance(fixed, list) and len(fixed) == len(group):
            for p, f in zip(group, fixed):
                if isinstance(f, str) and len(f) >= 0.6 * len(p["text"]):  # refuse truncation
                    p["text"] = f.strip()
                    p["clean"] = True
    return paras
