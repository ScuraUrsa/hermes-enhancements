"""Prompts for the three pipeline stages and the judge. The pipeline uses the same prompts
(video-digest imports them), so what is benchmarked is what runs."""

from __future__ import annotations

import json
import re
from typing import Any

from .bundle import VIDEO_TYPES

STAGE_MARK = {"classify": "[stage:classify]", "vision": "[stage:vision]", "report": "[stage:report]",
              "notes": "[stage:notes]", "judge_report": "[stage:judge_report]",
              "judge_vision": "[stage:judge_vision]", "label": "[stage:label]"}

LANG_NAMES = {"pl": "Polish", "en": "English"}

# -- classify --------------------------------------------------------------------------------
CLASSIFY_SYSTEM = f"""{STAGE_MARK['classify']}
You sort YouTube videos so a summarising pipeline can pick the right processing for each one.
Video types (pick exactly one):
- podcast_talk: people talking (podcast, talk, monologue); the picture adds little
- interview: host and guest, question and answer
- tutorial_screen: software, code or other screen recording where on-screen text matters
- lecture_slides: lecture, conference talk or course with slides
- explainer_visual: animation, diagrams, whiteboard; the picture carries the meaning
- vlog_travel: personal vlog, travel, outdoors, places
- news_commentary: news, opinion, reaction, commentary
- documentary: narrated documentary
- review_product: product review, unboxing, comparison
- music_artistic: song, music video, concert, live set, art film, poetry, anything valued mainly as
  culture or art rather than information. These are only listed, never summarised.
- short: under 3 minutes and none of the above fits better
- other
Answer with JSON only:
{{"video_type": "<one of: {', '.join(VIDEO_TYPES)}>", "is_artistic": true|false, "confidence": 0.0-1.0,
 "reason": "<one sentence>"}}"""


def classify_user(meta: dict[str, Any], transcript_head: str) -> str:
    return (f"Title: {meta['title']}\nChannel: {meta['channel']}\nDuration: {meta['duration_min']:.1f} min\n"
            f"YouTube tags: {', '.join(meta['yt_tags'][:30])}\nTranscript source: {meta['transcript_source']}\n"
            f"Music share of the audio (0-1, null if unknown): {meta['music_ratio']}\n"
            f"Description:\n{meta['description'][:1500]}\n\nStart of the transcript:\n{transcript_head}")


# -- vision ----------------------------------------------------------------------------------
VISION_SYSTEM = f"""{STAGE_MARK['vision']}
You describe frames sampled from a YouTube video for someone who will never watch it. For each frame,
say what is shown, copy any readable on-screen text (slides, code, captions, charts, labels) and note
information that is only visible, not spoken. Do not guess at what you cannot see.
Answer with JSON only:
{{"frames": [{{"t": <seconds, as given>, "caption": "<what is shown>", "on_screen_text": "<verbatim, or empty>",
  "visual_only": "<information the picture adds beyond the speech, or empty>"}}]}}"""


def vision_user(title: str, items: list[tuple[float, str]]) -> str:
    lines = [f"Video: {title}", "Frames in order, each with what is being said around it:"]
    for i, (t, speech) in enumerate(items):
        lines.append(f"Frame {i + 1}: t={t:.1f}s; speech nearby: {speech[:400] or '(none)'}")
    return "\n".join(lines)


# -- report ----------------------------------------------------------------------------------
REPORT_FIELDS = """{
 "one_line": "<one sentence: what this video is>",
 "about": "<3-5 sentences: what the video was about overall>",
 "text_summary": "<what was said: the argument, facts and conclusions, 150-400 words>",
 "visual_summary": "<what was shown that matters: slides, code, demos, places, charts; empty if the picture adds nothing>",
 "key_points": ["<5-12 specific takeaways, each one self-contained>"],
 "life_applications": ["<how the viewer can use this in their own life or work, concrete>"],
 "action_items": ["<concrete things to try, read, buy, set up; empty if none>"],
 "tags": ["<5-12 lowercase topic tags>"],
 "video_type": "<video type>",
 "is_artistic": false,
 "language": "<ISO code of the video's language>",
 "chapters": [{"t": <seconds>, "title": "<chapter>"}],
 "notable_quotes": [{"t": <seconds>, "quote": "<verbatim from the transcript>"}],
 "related_suggestions": ["<related topics, people, books or videos worth looking up>"],
 "confidence": 0.0-1.0
}"""

REPORT_SYSTEM_TMPL = STAGE_MARK["report"] + """
You turn one YouTube video into a report that replaces watching it. You get the transcript (with
timestamps) and descriptions of frames sampled from the video. Use only what they contain; if the
transcript is missing or poor, say so in "about" and lower "confidence". Be specific: names, numbers,
steps, tools, places. Write every text field in {language}; keep tags in {language} as well.
Answer with JSON only, exactly these keys:
""" + REPORT_FIELDS


def report_system(language: str = "pl") -> str:
    return REPORT_SYSTEM_TMPL.replace("{language}", LANG_NAMES.get(language, language))


def report_user(meta: dict[str, Any], video_type: str, transcript: str, frames: list[dict[str, Any]]) -> str:
    fr = "\n".join(
        f"[t={f.get('t')}] {f.get('caption', '')}"
        + (f" | on screen: {f['on_screen_text']}" if f.get("on_screen_text") else "")
        + (f" | visual only: {f['visual_only']}" if f.get("visual_only") else "")
        for f in frames) or "(no frames)"
    return (f"Title: {meta['title']}\nChannel: {meta['channel']}\nURL: {meta['url']}\n"
            f"Duration: {meta['duration_min']:.1f} min\nVideo type: {video_type}\n"
            f"YouTube chapters: {json.dumps(meta['yt_chapters'], ensure_ascii=False)}\n"
            f"Description:\n{meta['description'][:2000]}\n\n=== Frames ===\n{fr}\n\n=== Transcript ===\n{transcript}")


NOTES_SYSTEM = f"""{STAGE_MARK['notes']}
You condense one part of a long video transcript into dense notes that keep every fact, name, number,
step and argument, with the timestamps. Write in the transcript's language. Plain text, no preamble."""

# -- the native-video baseline (Gemini watches the URL) ------------------------------------------
VIDEO_URL_USER = "Watch the whole video (picture and sound) and write the report. Title: {title}"

# -- judge ------------------------------------------------------------------------------------
JUDGE_REPORT_SYSTEM = f"""{STAGE_MARK['judge_report']}
You grade a generated video report against a reference answer key written by a careful human-checked
annotator, and against the transcript. Be strict and literal; a point counts only if the report states
it (a paraphrase is fine, a vague gesture is not). Reports may be in a different language than the key.
Answer with JSON only:
{{"key_points": [{{"id": <id from key>, "verdict": "full"|"partial"|"missing"}}],
 "visual_facts": [{{"id": <id>, "verdict": "full"|"partial"|"missing"}}],
 "unsupported_claims": [{{"claim": "<text>", "severity": "major"|"minor"}}],
 "tag_matches": <how many of the report's tags match a key tag in meaning>,
 "usefulness": <1-5: would the life_applications and action_items actually help this viewer>,
 "comment": "<one sentence>"}}
A major unsupported claim is one that would mislead the reader about the video's content."""

JUDGE_VISION_SYSTEM = f"""{STAGE_MARK['judge_vision']}
You grade frame descriptions from a model against reference descriptions of the same frames.
For each reference visual fact, say whether the candidate descriptions convey it. List details in the
candidate that contradict the reference (hallucinations). Text copied from the screen counts only if it
is substantially correct. Answer with JSON only:
{{"visual_facts": [{{"id": <id>, "verdict": "full"|"partial"|"missing"}}],
 "hallucinations": [{{"t": <seconds>, "detail": "<text>", "severity": "major"|"minor"}}],
 "ocr_accuracy": <0.0-1.0, how faithfully on-screen text was copied; 1.0 if there was none>}}"""

LABEL_SYSTEM = f"""{STAGE_MARK['label']}
You are building an answer key for a benchmark of video-summarising models. From the transcript and
the frames, write what a perfect report must contain. Key points must be specific, checkable and
cover the whole video, most important first; importance 3 = core message, 1 = nice detail. Visual
facts are things only visible on screen (slide text, code, chart values, places, objects, demos),
each tied to a frame time. Answer with JSON only:
{{"video_type": "<type>", "is_artistic": false, "language": "<code>",
 "key_points": [{{"id": 1, "text": "<point>", "importance": 1|2|3}}],
 "visual_facts": [{{"id": 1, "t": <seconds>, "text": "<fact>"}}],
 "tags": ["<5-12 tags>"],
 "frame_captions": [{{"t": <seconds>, "caption": "<reference description>", "on_screen_text": "<verbatim>"}}],
 "notes": "<anything a grader should know, e.g. poor audio>"}}"""


def judge_report_user(label: dict, report: dict, transcript: str) -> str:
    return ("=== Answer key ===\n" + json.dumps({k: label.get(k) for k in ("key_points", "visual_facts", "tags")},
                                                 ensure_ascii=False, indent=1)
            + "\n\n=== Report to grade ===\n" + json.dumps(report, ensure_ascii=False, indent=1)
            + "\n\n=== Transcript (for checking unsupported claims) ===\n" + transcript)


def judge_vision_user(label: dict, frames: list[dict]) -> str:
    return ("=== Reference visual facts ===\n" + json.dumps(label.get("visual_facts", []), ensure_ascii=False)
            + "\n=== Reference frame descriptions ===\n" + json.dumps(label.get("frame_captions", []), ensure_ascii=False)
            + "\n\n=== Candidate frame descriptions ===\n" + json.dumps(frames, ensure_ascii=False))


# -- helpers ----------------------------------------------------------------------------------
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> Any:
    """Parse a model's JSON answer, tolerating code fences, preamble and <think> blocks."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    for cand in [text, *_FENCE.findall(text)]:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"no JSON in model output: {text[:200]!r}")


REPORT_REQUIRED = ("one_line", "about", "text_summary", "visual_summary", "key_points", "life_applications",
                   "tags", "video_type")


def report_problems(report: Any) -> list[str]:
    if not isinstance(report, dict):
        return ["not an object"]
    probs = [f"missing {k}" for k in REPORT_REQUIRED if k not in report]
    for k in ("key_points", "life_applications", "tags"):
        if k in report and not isinstance(report[k], list):
            probs.append(f"{k} is not a list")
    if isinstance(report.get("key_points"), list) and len(report["key_points"]) < 3:
        probs.append("fewer than 3 key points")
    return probs
