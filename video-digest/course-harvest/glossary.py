"""Candidate glossary for a course: the terms Whisper should spell right (passed to it as
hotwords) and suspicious spellings in the current transcripts (input for corrections).

  python glossary.py --course od-developera-do-foundera-3.0 [--site akademiasaas-pl]
Prints candidates; the curated result goes to D:\\courses\\<site>\\asr\\<course>.json:
  {"hotwords": ["SaaS", "churn", ...], "corrections": {"czern": "churn", ...}}
Only words that never occur in Polish go into corrections (they are replaced blindly).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(r"D:\courses")
WORD = re.compile(r"[A-Za-zÀ-ž0-9][\w\-+.]*[\w+]|[A-Za-z]")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="akademiasaas-pl")
    ap.add_argument("--course", required=True)
    ap.add_argument("--top", type=int, default=120)
    a = ap.parse_args()
    out = ROOT / a.site
    m = json.loads((out / "map.json").read_text(encoding="utf-8"))
    pages = [p for p in m["pages"] if a.course in p.get("course_url", "")]
    written, spoken = collections.Counter(), collections.Counter()
    for p in pages:
        d = out / "pages" / p["key"]
        txt = " ".join([p.get("title") or "", p.get("section") or ""])
        if (d / "text.md").is_file():
            txt += " " + (d / "text.md").read_text(encoding="utf-8")
        txt = re.sub(r"https?://\S+", " ", txt)
        written.update(w for w in WORD.findall(txt)
                       # acronyms, MixedCase brands, English-looking ASCII words
                       if re.fullmatch(r"[A-Z0-9]{2,6}|[A-Z][a-z]+[A-Z]\w*|[a-z]*[A-Z]{2,}\w*", w)
                       or (w.isascii() and len(w) > 3 and re.search(r"[qxv]|th|sh|ee|oo|ing\b|ck", w.lower())))
        for vtt in d.glob("prefetch/*.vtt"):
            spoken.update(w.lower() for w in WORD.findall(vtt.read_text(encoding="utf-8")) if not w[0].isdigit())
    print(f"{len(pages)} lessons")
    print("\nWRITTEN TERMS (titles + text under the videos):")
    print(", ".join(f"{w}:{n}" for w, n in written.most_common(a.top)))
    print("\nASCII-ONLY SPOKEN WORDS (English-looking words in transcripts):")
    eng = [(w, n) for w, n in spoken.most_common() if w.isascii() and len(w) > 3
           and re.search(r"[qxv]|th|sh|ee|oo|ing|ck|w[aeiou]{2}", w)]
    print(", ".join(f"{w}:{n}" for w, n in eng[: a.top]))


if __name__ == "__main__":
    main()
