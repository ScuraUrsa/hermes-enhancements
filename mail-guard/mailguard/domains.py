"""Domain helpers: registrable domain, punycode, homoglyph skeleton and lookalike detection.

Stdlib only. The registrable-domain logic is a heuristic (no Public Suffix List download): it knows the
common two-level suffixes Filip meets (``com.pl``, ``gov.pl``, ``co.uk``...). That is enough to compare a
sender's domain with a protected one; it is not a general PSL replacement.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

# Second-level public suffixes that matter here. A domain under one of these keeps three labels.
_TWO_LEVEL_SUFFIXES = {
    "com.pl", "net.pl", "org.pl", "gov.pl", "edu.pl", "info.pl", "biz.pl", "waw.pl", "gda.pl", "poznan.pl",
    "krakow.pl", "wroc.pl", "lodz.pl", "szczecin.pl", "katowice.pl", "lublin.pl", "co.uk", "org.uk", "gov.uk",
    "ac.uk", "com.au", "co.jp", "com.br", "co.in", "com.cn", "com.tr", "co.za", "com.ua", "com.de",
}

# Visual confusables mapped to the ASCII letter they imitate. Not the full Unicode confusables table: the
# Latin-lookalike subset of Cyrillic and Greek plus digit tricks, which covers what phishing kits use.
_CONFUSABLES = {
    # Cyrillic
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "ѕ": "s", "і": "i", "ї": "i", "ј": "j", "ԁ": "d", "ɡ": "g", "ԛ": "q", "ԝ": "w", "һ": "h",
    "ӏ": "l", "ո": "n", "ս": "u",
    # Greek
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "χ": "x",
    "γ": "y", "ω": "w",
    # Latin look-alikes and accented letters often used to imitate plain ones
    "ı": "i", "ł": "l", "ŀ": "l", "ƚ": "l", "ǀ": "l", "ɑ": "a", "ɩ": "i", "ʟ": "l", "ꞁ": "l",
}
# Multi-character tricks applied after single characters. Digits are only folded when comparing, never
# when reporting, so "allegro2.pl" is still a different domain from "allegro.pl" for display.
_SEQUENCES = (("rn", "m"), ("vv", "w"), ("cl", "d"), ("0", "o"), ("1", "l"), ("3", "e"), ("5", "s"), ("|", "l"))


def to_unicode(host: str) -> str:
    """xn--... labels decoded to Unicode; anything undecodable is kept as is."""
    out = []
    for label in host.strip(".").lower().split("."):
        if label.startswith("xn--"):
            try:
                out.append(label.encode("ascii").decode("idna"))
                continue
            except UnicodeError:
                pass
        out.append(label)
    return ".".join(out)


def is_punycode(host: str) -> bool:
    return any(label.startswith("xn--") for label in host.lower().split("."))


def registrable(host: str) -> str:
    """``mail.allegro.pl`` -> ``allegro.pl``, ``a.b.pekao.com.pl`` -> ``pekao.com.pl``."""
    labels = [x for x in host.strip(".").lower().split(".") if x]
    if len(labels) <= 2:
        return ".".join(labels)
    if ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def scripts(text: str) -> set[str]:
    """Unicode scripts of the letters in ``text`` (LATIN, CYRILLIC, GREEK...)."""
    found = set()
    for ch in text:
        if ch.isalpha():
            try:
                found.add(unicodedata.name(ch).split(" ")[0])
            except ValueError:
                found.add("UNKNOWN")
    return found


def skeleton(host: str) -> str:
    """Fold a domain to what it looks like: confusables to ASCII, accents dropped, digit/sequence tricks."""
    s = to_unicode(host).lower()
    s = "".join(_CONFUSABLES.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for a, b in _SEQUENCES:
        s = s.replace(a, b)
    return s.replace("-", "")


def levenshtein(a: str, b: str, limit: int = 3) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@lru_cache(maxsize=1)
def _builtin_protected() -> tuple[str, ...]:
    text = resources.files("mailguard").joinpath("data/protected_domains.txt").read_text(encoding="utf-8")
    return tuple(_parse_list(text))


def _parse_list(text: str) -> list[str]:
    return [ln.strip().lower() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


@lru_cache(maxsize=1)
def known_good() -> frozenset[str]:
    text = resources.files("mailguard").joinpath("data/known_good.txt").read_text(encoding="utf-8")
    return frozenset(_parse_list(text))


def protected_domains(extra_file: str | None = None) -> tuple[str, ...]:
    """Built-in list + ``extra_file`` + file named in ``MAILGUARD_PROTECTED``."""
    out = list(_builtin_protected())
    for path in (extra_file, os.environ.get("MAILGUARD_PROTECTED")):
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out.extend(_parse_list(fh.read()))
    return tuple(dict.fromkeys(out))


@dataclass
class Lookalike:
    domain: str          # the domain that was checked (registrable)
    imitates: str        # the protected domain it resembles
    how: str             # "homoglyph", "edit-distance", "brand-in-subdomain", "brand-in-name"


def find_lookalike(host: str, protected: tuple[str, ...] | None = None) -> Lookalike | None:
    """Return the protected domain ``host`` imitates, or None if it is that domain or unrelated."""
    protected = protected or protected_domains()
    host_u = to_unicode(host)
    reg = registrable(host_u)
    if reg in protected or reg in known_good() or host_u in known_good():
        return None
    reg_skel = skeleton(reg)
    reg_name = reg.split(".")[0]
    for p in protected:
        p_skel = skeleton(p)
        p_name = p.split(".")[0]
        if reg_skel == p_skel:
            return Lookalike(reg, p, "homoglyph")
        if len(p_name) >= 5 and levenshtein(reg_skel, p_skel, 2) <= (1 if len(p_name) < 8 else 2):
            return Lookalike(reg, p, "edit-distance")
        # paypal.com.secure-login.io, allegro.pl-oferta.xyz
        sub = host_u[: -len(reg)] if host_u.endswith(reg) else ""
        if len(p_name) >= 4 and (p in sub or f"{p_name}." in sub or sub.startswith(f"{p_name}-")):
            return Lookalike(reg, p, "brand-in-subdomain")
        # allegro-oferta.pl, inpost-dostawa.com, mbank-logowanie.net
        if len(p_name) >= 5 and reg_name != p_name and (
            reg_name.startswith(p_name + "-") or reg_name.endswith("-" + p_name)
            or (reg_name.startswith(p_name) and len(reg_name) - len(p_name) >= 3)
        ):
            return Lookalike(reg, p, "brand-in-name")
    return None


# Throwaway-domain shape (measured 06.11 on Filip's spam: *.scannertool.me, pbjwfhtj.gbncbkqx.us, *.vexurin.biz).
CHEAP_SENDER_TLDS = {
    "me", "biz", "us", "id", "web.id", "xyz", "top", "click", "link", "icu", "cyou", "cfd", "sbs", "buzz", "rest",
    "monster", "quest", "lol", "bond", "online", "site", "store", "shop", "support", "live", "tk", "ml", "ga", "cf",
    "gq", "su", "info", "work", "pw", "ws", "cc", "vip", "fun", "space", "website", "life", "today", "world",
}
_VOWELS = set("aeiouy")


def random_label(label: str) -> bool:
    """A label that looks machine-generated: no pronounceable structure."""
    label = label.lower()
    letters = [c for c in label if c.isalpha()]
    if len(letters) < 6 or "-" in label:
        return False
    vowels = sum(c in _VOWELS for c in letters)
    run = longest = 0
    for c in letters:
        run = run + 1 if c not in _VOWELS else 0
        longest = max(longest, run)
    digits = sum(c.isdigit() for c in label)
    return vowels / len(letters) < 0.2 or longest >= 5 or (digits >= 3 and len(letters) >= 4)


def domain_shape(host: str) -> tuple[int, str, str] | None:
    """(weight, code, text) when the sender domain looks disposable, else None."""
    host = to_unicode(host).lower()
    reg = registrable(host)
    if reg in known_good() or reg in protected_domains():
        return None
    labels = host.split(".")
    tld = ".".join(labels[-2:]) if ".".join(labels[-2:]) in CHEAP_SENDER_TLDS else labels[-1]
    rnd = [lb for lb in labels[:-1] if random_label(lb)]
    w = (15 if rnd else 0) + (10 if tld in CHEAP_SENDER_TLDS else 0)
    if not w:
        return None
    parts = []
    if rnd:
        parts.append(f"losowo wyglądająca nazwa ({rnd[0]})")
    if tld in CHEAP_SENDER_TLDS:
        parts.append(f"tania, często nadużywana końcówka .{tld}")
    return w, "disposable_domain", f"Domena nadawcy {host} wygląda na jednorazową: " + ", ".join(parts) + "."
