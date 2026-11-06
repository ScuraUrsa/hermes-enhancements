"""Turn untrusted mail bodies into plain text an LLM can read with less risk.

What is removed, and counted so the score can use it:
- script/style/head/template/noscript/iframe/object content and HTML comments;
- text a person would not see: ``display:none``, ``visibility:hidden``, ``hidden`` / ``aria-hidden``,
  ``font-size`` 0–2px, ``opacity:0``, white text, ``max-height:0``/``overflow:hidden`` boxes;
- invisible Unicode: zero-width characters, bidi overrides, and the "tag" block (U+E0000–E007F) used for
  ASCII smuggling of instructions that a human never sees.

Hidden text is exactly where mail prompt injections live, so it is dropped from the text and reported.
Nothing here fetches anything: remote images and links are only listed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "head", "template", "noscript", "iframe", "object", "embed", "svg", "math", "title"}
_VOID = {"br", "img", "hr", "meta", "link", "input", "area", "base", "col", "source", "wbr", "track", "param"}
_BLOCK = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "article", "blockquote",
          "ul", "ol", "header", "footer", "center", "pre"}

_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$|!)|font-size\s*:\s*[0-2](?:\.\d+)?"
    r"(?:px|pt)?\s*(?:;|$|!)|max-height\s*:\s*0|(?<![-\w])height\s*:\s*0(?:px)?\s*(?:;|$|!)"
    r"|(?<![-\w])color\s*:\s*(?:#fff(?:fff)?|white|rgba?\(\s*255\s*,\s*255\s*,\s*255)\b"
    r"|(?:mso-hide|clip)\s*:\s*(?:all|rect\(0)", re.I)

# Zero-width, bidi controls, soft hyphen, word joiner, BOM, and the Unicode "tags" block.
_INVISIBLE = re.compile("[­᠎​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]")


@dataclass
class Link:
    href: str
    text: str


@dataclass
class CleanBody:
    text: str
    links: list[Link] = field(default_factory=list)
    remote_images: list[str] = field(default_factory=list)
    tracking_pixels: int = 0
    hidden_chars: int = 0          # characters of text inside hidden elements
    hidden_samples: list[str] = field(default_factory=list)
    invisible_chars: int = 0       # zero-width / bidi / tag characters removed
    tag_chars: int = 0             # of which Unicode tag block (ASCII smuggling)
    comments: int = 0
    forms: int = 0
    scripts: int = 0


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[tuple[str, bool]] = []    # (tag, hidden)
        self.skip = 0
        self.body = CleanBody(text="")
        self._a: list[str] | None = None
        self._a_href = ""

    @property
    def hidden(self) -> bool:
        return any(h for _, h in self.stack)

    def handle_starttag(self, tag, attrs):  # noqa: C901 - flat attribute checks
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in _SKIP_TAGS:
            if tag == "script":
                self.body.scripts += 1
            if tag not in _VOID:
                self.skip += 1
            return
        if tag == "form":
            self.body.forms += 1
        hidden = ("hidden" in a or a.get("aria-hidden", "").lower() == "true"
                  or bool(_HIDDEN_STYLE.search(a.get("style", ""))))
        if tag == "img":
            src = a.get("src", "")
            if src.lower().startswith(("http://", "https://", "//")):
                self.body.remote_images.append(src)
                w, h = a.get("width", "").strip("px "), a.get("height", "").strip("px ")
                if (w in ("0", "1") and h in ("0", "1")) or hidden:
                    self.body.tracking_pixels += 1
            alt = a.get("alt", "").strip()
            if alt and not hidden and not self.hidden and not self.skip:
                self.out.append(f"[obraz: {alt}]")
            return
        if tag in _VOID:
            if tag == "br" and not self.skip:
                self.out.append("\n")
            return
        if tag in _BLOCK and not self.skip:
            self.out.append("\n")
        if tag == "a" and a.get("href"):
            self._a, self._a_href = [], a["href"].strip()
        self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and tag not in _VOID:
            self.skip = max(0, self.skip - 1)
            return
        if tag == "a" and self._a is not None:
            self.body.links.append(Link(self._a_href, " ".join("".join(self._a).split())))
            self._a = None
        # pop to the matching tag (mail HTML is rarely well formed)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in _BLOCK and not self.skip:
            self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.hidden:
            txt = data.strip()
            if txt:
                self.body.hidden_chars += len(txt)
                if len(self.body.hidden_samples) < 3:
                    self.body.hidden_samples.append(txt[:120])
            return
        if self._a is not None:
            self._a.append(data)
        self.out.append(data)

    def handle_comment(self, data):
        self.body.comments += 1


def strip_invisible(text: str) -> tuple[str, int, int]:
    found = _INVISIBLE.findall(text)
    tags = sum(1 for ch in found if 0xE0000 <= ord(ch) <= 0xE007F)
    return _INVISIBLE.sub("", text), len(found), tags


def decode_tag_smuggling(text: str) -> str:
    """What a Unicode-tag-smuggled payload says (for the report only, never for the model)."""
    return "".join(chr(ord(ch) - 0xE0000) for ch in text if 0xE0020 <= ord(ch) <= 0xE007E)


def _tidy(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_URL_RE = re.compile(r"""(?i)\b(?:https?://|www\.)[^\s<>"'()\[\]{}]+""")


def clean_html(raw_html: str) -> CleanBody:
    p = _Parser()
    try:
        p.feed(raw_html)
        p.close()
    except Exception:  # noqa: BLE001 - malformed HTML must never crash ingestion
        pass
    body = p.body
    text, n, tags = strip_invisible("".join(p.out))
    body.text, body.invisible_chars, body.tag_chars = _tidy(text), n, tags
    return body


def clean_text(raw_text: str) -> CleanBody:
    text, n, tags = strip_invisible(raw_text)
    body = CleanBody(text=_tidy(text), invisible_chars=n, tag_chars=tags)
    body.links = [Link(u.rstrip(".,;:!?"), "") for u in _URL_RE.findall(body.text)]
    return body


# --- prompt-injection heuristics -------------------------------------------------------------------------
# Signals, not a filter: a match raises the score and tells the agent to be careful. The structural defences
# (no tools on mail content, approvals, the quarantined reader) do the real work; see the skill.
_INJECTION_PATTERNS = [
    (r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|your)\b.{0,30}"
     r"\b(instructions?|prompts?|rules|guidelines|messages?)\b", "ignore-instructions"),
    (r"\b(zignoruj|zapomnij|pomi[nń]|nie zwracaj uwagi na)\b.{0,40}\b(poprzedni\w*|wcze[sś]niejsz\w*|wszystki\w*|"
     r"swoje)\b.{0,30}\b(instrukcj\w*|polece[nń]\w*|zasad\w*|regu\w*)", "ignore-instructions-pl"),
    (r"\b(you are|act as|you're now|from now on you)\b.{0,40}\b(assistant|ai|agent|model|gpt|claude|hermes|"
     r"llm|developer mode|dan)\b", "role-override"),
    (r"\b(jeste[sś]|od teraz jeste[sś]|udawaj)\b.{0,40}\b(asystent\w*|agent\w*|model\w*|ai|hermes|claude)\b",
     "role-override-pl"),
    (r"\b(system prompt|system message|developer message|<\|?system\|?>|\[/?inst\]|<\|im_start\|>|###\s*instruction)",
     "chat-template"),
    (r"\b(assistant|ai agent|llm|language model|hermes|claude|chatgpt|copilot)\b.{0,60}\b(must|should|please|"
     r"need to|has to|powinien|musi)\b", "addresses-the-ai"),
    (r"\b(to the ai|for the ai|ai assistant reading this|if you are an ai|je[sś]li jeste[sś] (ai|modelem|asystentem))",
     "addresses-the-ai"),
    (r"\b(send|forward|email|e-mail|upload|post|exfiltrate|wy[sś]lij|prze[sś]lij|przeka[zż])\b.{0,60}\b(password|"
     r"token|api key|secret|credentials?|2fa|otp|code|has[lł]\w*|kod\w*|klucz\w*|dane logowania)\b", "exfiltration"),
    (r"\b(run|execute|uruchom|wykonaj)\b.{0,30}\b(command|script|terminal|shell|powershell|bash|curl|komend\w*|"
     r"skrypt\w*|polecen\w*)\b", "tool-use"),
    (r"\b(call|use|invoke|wywo[lł]aj|u[zż]yj)\b.{0,20}\b(tool|function|narz[eę]dzi\w*|funkcj\w*)\b", "tool-use"),
    (r"!\[[^\]]*\]\(https?://[^)]*\?[^)]*=", "markdown-image-exfil"),
]
_INJECTION_RES = [(re.compile(p, re.I | re.S), code) for p, code in _INJECTION_PATTERNS]


def injection_signals(text: str) -> list[tuple[str, str]]:
    """[(code, snippet)] for each heuristic that fires (first match per code)."""
    hits: dict[str, str] = {}
    for rx, code in _INJECTION_RES:
        if code in hits:
            continue
        m = rx.search(text)
        if m:
            hits[code] = " ".join(m.group(0).split())[:120]
    return list(hits.items())
