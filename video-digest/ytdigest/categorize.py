"""Sort a big discovered list (80k+ videos) into topic categories, for free.

Per video: keyword scores over title (x3), tags and channel name. Per channel:
the dominant category of its scored videos is lent to its unscored videos, so
"Fireship" uploads with vague titles still land in Software. Shorts and the
YouTube Music category are labelled but kept apart. No model calls: 80k videos
in seconds, deterministic, and re-runnable after the keyword lists are tuned.

Input: JSONL or TSV rows with at least video_id (or id), title, channel; optional
seconds/duration, tags, category/categories, is_short, is_music, language.
Output dir: categories.json (counts), <category>.txt (ids, newest first),
categorized.jsonl (every row + category + secondary), ai_software.txt.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# Order matters for ties: more specific categories first.
CATEGORIES: dict[str, str] = {
    "AI": r"\bai\b|a\.i\.|\bsi\b|sztuczn\w* inteligencj|\bllms?\b|\bgpt[-\w]*|chatgpt|claude|anthropic|openai|gemini|"
          r"copilot|cursor ai|\bagent(s|y|ów|i|ic)?\b|\bmcp\b|\brag\b|prompt|machine learning|uczeni\w* maszynow|"
          r"deep learning|neural|transformer|ollama|hugging ?face|langchain|crewai|n8n|midjourney|stable diffusion|"
          r"sora|veo\b|perplexity|deepseek|mistral|llama|grok|notebooklm|automat\w* (z|with) ai|vibe ?cod",
    "Software": r"programow|programming|programist|developer|\bdevs?\b|coding|\bcode\b|\bkod\b|python|javascript|"
                r"typescript|\breact\b|node\.?js|\brust\b|golang|\bjava\b|c\+\+|c#|\.net|\bsql\b|\bapi\b|backend|"
                r"frontend|full ?stack|devops|docker|kubernetes|\bk8s\b|terraform|ansible|\blinux\b|\bgit(hub)?\b|"
                r"software|oprogramowani|open ?source|self-?host|homelab|serwer|server|cloud|aws|azure|gcp|"
                r"cyber|security|hack|database|framework|neovim|vs ?code|\bide\b|saas|no-?code|low-?code|excel|"
                r"power ?bi|automatyzacj|automation|raspberry|arduino|home assistant|proxmox|nas\b",
    "Psychology": r"psycholog|psychiatr|terapi|therapy|therapist|mental|anxiety|lęk|depresj|depression|trauma|adhd|"
                  r"autyzm|autism|narcy|emocj|emotion|relacj|relationship|związ|attachment|przywiązan|motywacj|"
                  r"motivation|nawyk|habit|mindset|samoocen|self-?esteem|stoic|stoicyzm|medytac|meditat|"
                  r"mindful|szczęści|happiness|osobowo|personality|introwert|dopamin|prokrastyn|procrastinat|"
                  r"rozwój osobisty|self-?improvement|self-?help|neuro",
    "Politics": r"polityk|politic|wybor|election|rząd|government|sejm|senat|prezydent|president|premier|minister|"
                r"partia|party\b|pis\b|\bpo\b|konfederacj|lewic|prawic|left-?wing|right-?wing|trump|biden|harris|"
                r"putin|zelensk|tusk|kaczyński|nawrocki|mentzen|brexit|\bue\b|\beu\b|european union|nato|ukrain|"
                r"rosj|russia|wojn|\bwar\b|geopolit|konflikt|izrael|israel|gaza|china|chiny|tariff|cło|"
                r"democra|demokra|propagand|sanctions|sankcj|immigra|imigra|debata|debate",
    "Business & Finance": r"biznes|business|firm[aey]|startup|przedsiębior|entrepreneur|marketing|sprzedaż|sales|"
                          r"finans|finance|inwest|invest|giełd|stock|akcj[ei]|etf|crypto|krypto|bitcoin|"
                          r"pieniąd|money|oszczędz|saving|budżet|budget|podatk|tax|nieruchomo|real estate|"
                          r"inflacj|inflation|ekonomi|economy|economic|kredyt|mortgage|hipotek|zarabia|income|"
                          r"praca zdalna|kariera|career|leadership|ceo|seo|e-?commerce|dropshipping|freelanc",
    "Science & Education": r"nauk[aiy]|science|fizyk|physics|chemi|biolog|astronom|kosmos|space|nasa|"
                           r"matematyk|math|wykład|lecture|explained|wyjaśnia|jak działa|how .* works|"
                           r"edukacj|education|kurs\b|course|tutorial|lekcj|lesson|ewolucj|evolution|"
                           r"klimat|climate|energi|energy|quantum|kwant",
    "Health & Fitness": r"zdrowi|health|dieta|diet|odżywia|nutrition|trening|workout|fitness|siłowni|gym|"
                        r"bieg|running|sen\b|sleep|post przerywany|fasting|suplement|supplement|lekarz|doctor|"
                        r"medycyn|medicine|cholester|cukrzyc|diabet|longevity|długowieczn|kalori|calorie|joga|yoga",
    "Tech & Making": r"druk 3d|3d print|drukark|printer|bambu|prusa|filament|cad\b|fusion 360|cnc|laser|"
                     r"elektronik|electronics|lutow|solder|diy|majsterk|warsztat|workshop|smartfon|smartphone|"
                     r"iphone|android|laptop|\bpc\b|gpu|nvidia|procesor|cpu|recenzja sprzętu|unboxing|gadżet|gadget",
    "History & Documentary": r"histori|history|dokument|documentary|ii wojn|wwii|world war|średniowiecz|medieval|"
                             r"starożyt|ancient|imperium|empire|cywilizacj|civilization|archeolog|"
                             r"zbrodni|crime|śledztw|investigation|katastrof|disaster",
    "Chess & Games": r"szach|chess|magnus|carlsen|gambit|debiut|opening|gra planszow|board game|"
                     r"gaming|gameplay|minecraft|let'?s play|speedrun|\bgra\b|\bgame\b",
    "Travel & Places": r"podróż|travel|wycieczk|trip|vlog z|zwiedza|kraj|country|miasto|city|backpack|"
                       r"nomad|camping|kamper|van ?life|góry|mountains|hiking|trekking",
    "Food": r"przepis|recipe|gotow|cooking|kuchni|kitchen|obiad|dinner|ciasto|cake|chleb|bread|kawa|coffee|"
            r"restauracj|restaurant|food\b|jedzeni",
    "Family & Parenting": r"dzieck|dzieci|child|kids|rodzic|parent|wychowa|ciąż|pregnan|niemowl|baby|"
                          r"macierzyń|ojcost|fatherhood|motherhood|szkoła|school",
    "Faith & Philosophy": r"filozof|philosoph|bóg|god\b|wiara|faith|kości|church|religi|biblia|bible|"
                          r"modlitw|prayer|duchow|spiritual|sens życia|meaning of life|etyk|ethic",
}
_RX = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
NON_TOPIC = ("Shorts", "Music & Art")


def _get(row: dict, *keys, default=None):
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return default


def load(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    if path.suffix == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("rows", [])
    return list(csv.DictReader(text.splitlines(), delimiter="\t"))


def scores(row: dict) -> Counter:
    title = str(_get(row, "title", default=""))
    tags = _get(row, "tags", default=[])
    tags = " ".join(tags) if isinstance(tags, list) else str(tags)
    channel = str(_get(row, "channel", "channel_title", default=""))
    desc = str(_get(row, "description", default=""))[:500]
    c = Counter()
    for cat, rx in _RX.items():
        n = 3 * len(rx.findall(title)) + len(rx.findall(tags)) + 2 * len(rx.findall(channel)) + len(rx.findall(desc))
        if n:
            c[cat] = n
    if c.get("AI") and c.get("Software"):  # AI coding is AI first
        c["AI"] += 1
    return c


def _flag(row: dict, *keys) -> bool:
    v = _get(row, *keys, default=False)
    return v is True or str(v).lower() in ("1", "true", "yes")


def run(in_path: Path, out_dir: Path, min_score: int = 3) -> dict:
    rows = load(in_path)
    by_channel: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        r["_scores"] = scores(r)
        top = r["_scores"].most_common(1)
        if top and top[0][1] >= min_score:
            by_channel[str(_get(r, "channel_id", "channel", default=""))][top[0][0]] += 1
    for r in rows:
        vid = str(_get(r, "video_id", "id"))
        r["video_id"] = vid
        secs = int(float(_get(r, "seconds", "duration", default=0) or 0))
        cats = str(_get(r, "category", "categories", default=""))
        sc = r.pop("_scores")
        ranked = [k for k, v in sc.most_common() if v >= min_score]
        chan = by_channel.get(str(_get(r, "channel_id", "channel", default="")))
        if _flag(r, "is_short", "short", "shorts") or 0 < secs <= 60:
            r["topic"] = "Shorts"
        elif _flag(r, "is_music", "music") or "Music" in cats or str(_get(r, "channel", default="")).endswith(" - Topic"):
            r["topic"] = "Music & Art"
        elif ranked:
            r["topic"] = ranked[0]
        elif chan and sum(chan.values()) >= 3 and chan.most_common(1)[0][1] / sum(chan.values()) >= 0.5:
            r["topic"] = chan.most_common(1)[0][0]  # channel's usual topic
            r["topic_from"] = "channel"
        else:
            r["topic"] = "Other"
        r["secondary"] = [k for k in ranked if k != r["topic"]][:2]
        r["_secs"] = secs

    out_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["topic"]].append(r)

    def newest(rs):
        return sorted(rs, key=lambda x: str(_get(x, "published", "date", "published_at", default="")), reverse=True)

    summary = {}
    for cat, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rs = newest(rs)
        slug = re.sub(r"[^a-z0-9]+", "_", cat.lower()).strip("_")
        (out_dir / f"{slug}.txt").write_text("\n".join(r["video_id"] for r in rs) + "\n", encoding="utf-8")
        chans = Counter(str(_get(r, "channel", default="")) for r in rs)
        summary[cat] = {"videos": len(rs), "hours": round(sum(r["_secs"] for r in rs) / 3600, 1),
                        "file": f"{slug}.txt", "top_channels": [c for c, _ in chans.most_common(5)]}
    ai_sw = newest([r for r in rows if r["topic"] in ("AI", "Software")])
    (out_dir / "ai_software.txt").write_text("\n".join(r["video_id"] for r in ai_sw) + "\n", encoding="utf-8")
    summary["_ai_software"] = {"videos": len(ai_sw), "hours": round(sum(r["_secs"] for r in ai_sw) / 3600, 1),
                               "file": "ai_software.txt"}
    with (out_dir / "categorized.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            r.pop("_secs", None)
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "categories.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
