"""Sender authentication (SPF, DKIM, DMARC) and sender-identity checks.

We do not re-verify DKIM or SPF ourselves: Gmail already did it at delivery time and wrote the result into
the topmost ``Authentication-Results`` header (authserv-id ``mx.google.com``). Re-verifying later gives
wrong answers (rotated DKIM keys, SPF evaluated from the wrong IP). What we must do is read only the
header our own provider wrote: anything below it was supplied by the sender and can be forged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.message import Message
from email.utils import getaddresses, parseaddr

from .domains import domain_shape, find_lookalike, protected_domains, registrable, to_unicode

TRUSTED_AUTHSERV = ("mx.google.com",)
# Free mailbox providers: a company mail that wants replies to one of these is classic invoice fraud (BEC).
FREEMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com",
            "proton.me", "protonmail.com", "wp.pl", "o2.pl", "onet.pl", "op.pl", "interia.pl", "interia.eu",
            "gazeta.pl", "tlen.pl", "poczta.fm", "vp.pl", "gmx.com", "gmx.net", "mail.ru", "yandex.ru",
            "aol.com", "zoho.com"}
# Brand names that are also everyday words; not used for the display-name check.
_COMMON_WORDS = {"orange", "office", "outlook"}

_RESULT_RE = re.compile(r"\b(spf|dkim|dmarc|arc)\s*=\s*([a-z]+)", re.I)
_HEADER_FROM_RE = re.compile(r"header\.from\s*=\s*([^\s;()]+)", re.I)
_DKIM_DOMAIN_RE = re.compile(r"dkim\s*=\s*pass[^;]*?header\.(?:i|d)\s*=\s*@?([^\s;()]+)", re.I)
_MAILFROM_RE = re.compile(r"smtp\.mailfrom\s*=\s*([^\s;()]+)", re.I)
_EMAIL_IN_TEXT_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass
class AuthResult:
    source: str = "none"            # authserv-id we trusted, or "none"
    spf: str = "none"
    dkim: str = "none"
    dmarc: str = "none"
    dkim_domains: list[str] = field(default_factory=list)
    mailfrom_domain: str = ""
    header_from_domain: str = ""
    forged_headers: int = 0         # Authentication-Results claiming our authserv-id below the real one


def _domain_of(addr: str) -> str:
    addr = addr.strip().strip("<>")
    return to_unicode(addr.rsplit("@", 1)[-1]).lower() if "@" in addr else to_unicode(addr).lower()


def parse_authentication_results(msg: Message, trusted: tuple[str, ...] = TRUSTED_AUTHSERV) -> AuthResult:
    res = AuthResult()
    headers = msg.get_all("Authentication-Results") or []
    seen_trusted = False
    for raw in headers:
        value = " ".join(str(raw).split())
        authserv = value.split(";", 1)[0].strip().split()[0].lower() if value else ""
        if authserv not in trusted:
            continue
        if seen_trusted:
            res.forged_headers += 1
            continue
        seen_trusted = True
        res.source = authserv
        for mech, result in _RESULT_RE.findall(value):
            mech = mech.lower()
            result = result.lower()
            if mech == "dkim":
                # several signatures: pass wins
                res.dkim = "pass" if "pass" in (res.dkim, result) else result
            elif mech in ("spf", "dmarc"):
                setattr(res, mech, result)
        res.dkim_domains = sorted({d.lower() for d in _DKIM_DOMAIN_RE.findall(value)})
        m = _MAILFROM_RE.search(value)
        res.mailfrom_domain = _domain_of(m.group(1)) if m else ""
        m = _HEADER_FROM_RE.search(value)
        res.header_from_domain = to_unicode(m.group(1)).lower() if m else ""
    return res


@dataclass
class SenderInfo:
    display_name: str
    address: str
    domain: str
    reply_to: list[str]
    return_path: str


def sender_info(msg: Message) -> SenderInfo:
    name, addr = parseaddr(str(msg.get("From", "")))
    reply_to = [a for _, a in getaddresses([str(x) for x in (msg.get_all("Reply-To") or [])]) if a]
    rp = parseaddr(str(msg.get("Return-Path", "")))[1]
    return SenderInfo(name.strip(), addr.lower(), _domain_of(addr) if addr else "", reply_to, rp.lower())


def sender_signals(msg: Message, protected: tuple[str, ...] | None = None) -> tuple[AuthResult, SenderInfo, list]:
    """Return (auth, sender, signals) where each signal is (weight, code, Polish explanation)."""
    protected = protected or protected_domains()
    auth = parse_authentication_results(msg)
    snd = sender_info(msg)
    sig: list[tuple[int, str, str]] = []

    if auth.source == "none":
        sig.append((10, "auth_missing", "Brak wyniku SPF/DKIM/DMARC od Gmaila (mail nie przeszedł przez mx.google.com "
                                        "albo nagłówek usunięto)."))
    else:
        if auth.dmarc == "fail":
            sig.append((45, "dmarc_fail",
                        f"DMARC nie przeszedł: domena {snd.domain} nie potwierdza, że wysłała ten mail."))
        elif auth.dmarc in ("none", "neutral", "temperror", "permerror"):
            if auth.spf != "pass" and auth.dkim != "pass":
                sig.append((30, "auth_none", "Ani SPF, ani DKIM nie potwierdzają nadawcy, a domena nie ma DMARC."))
            elif snd.domain and not _aligned(snd.domain, auth):
                sig.append((15, "auth_unaligned", "SPF/DKIM przechodzą, ale dla innej domeny niż ta w polu Od."))
            else:
                sig.append((10, "no_dmarc", f"Domena {snd.domain} nie publikuje DMARC (każdy może się pod nią podszyć; "
                                            "typowe dla jednorazowych domen spamerów)."))
            if auth.dkim != "pass":
                sig.append((10, "no_dkim", "Mail nie ma ważnego podpisu DKIM."))
        if auth.spf in ("fail", "softfail") and auth.dmarc != "pass":
            sig.append((10, "spf_fail", f"SPF: {auth.spf} (serwer nie jest uprawniony do wysyłki z tej domeny)."))
        if auth.forged_headers:
            sig.append((25, "forged_auth_header", "W mailu jest podrobiony nagłówek Authentication-Results "
                                                 "udający wynik Gmaila."))

    if snd.domain:
        la = find_lookalike(snd.domain, protected)
        if la:
            weight = 50 if la.how in ("homoglyph", "edit-distance") else 30
            sig.append((weight, "sender_lookalike",
                        f"Domena nadawcy {la.domain} podszywa się pod {la.imitates} ({la.how})."))

    # Display-name tricks: "PKO BP <x@gmail.com>", "noreply@mbank.pl <x@evil.io>"
    dn = snd.display_name.lower()
    for email_in_name in _EMAIL_IN_TEXT_RE.findall(snd.display_name):
        if registrable(_domain_of(email_in_name)) != registrable(snd.domain):
            sig.append((35, "display_name_email", f"Nazwa nadawcy zawiera inny adres ({email_in_name}) niż faktyczny "
                                                  f"({snd.address})."))
            break
    else:
        for p in protected:
            brand = p.split(".")[0]
            if len(brand) >= 5 and brand not in _COMMON_WORDS and re.search(rf"\b{re.escape(brand)}\b", dn) \
                    and registrable(snd.domain) != p and not find_lookalike(snd.domain, (p,)) \
                    and registrable(snd.domain) not in _related(p, protected) \
                    and brand not in registrable(snd.domain).split(".")[0]:   # bitwarden.eu, mail.notion.com
                sig.append((20, "display_name_brand", f"Nazwa nadawcy „{snd.display_name}” sugeruje {p}, a mail jest "
                                                      f"z {snd.domain}."))
                break

    for rt in snd.reply_to:
        if registrable(_domain_of(rt)) != registrable(snd.domain):
            free = registrable(_domain_of(rt)) in FREEMAIL and registrable(snd.domain) not in FREEMAIL
            sig.append((30 if free else 15, "reply_to_mismatch",
                        f"Odpowiedź pójdzie na inny adres ({rt}) niż nadawca ({snd.address})."))
            break
    if snd.domain:
        shape = domain_shape(snd.domain)
        if shape:
            sig.append(shape)
    if snd.domain and not snd.display_name and not snd.address:
        sig.append((10, "no_from", "Brak nadawcy w polu Od."))
    return auth, snd, sig


def _aligned(domain: str, auth: AuthResult) -> bool:
    org = registrable(domain)
    if auth.spf == "pass" and auth.mailfrom_domain and registrable(auth.mailfrom_domain) == org:
        return True
    return auth.dkim == "pass" and any(registrable(d) == org for d in auth.dkim_domains)


def _related(p: str, protected: tuple[str, ...]) -> set[str]:
    """Protected domains of the same brand (``ipko.pl`` and ``pkobp.pl`` are not, ``dhl.com``/``dhl.pl`` are)."""
    brand = p.split(".")[0]
    return {q for q in protected if q.split(".")[0] == brand}
