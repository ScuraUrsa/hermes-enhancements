"""Link triage without opening anything: what the link really points at and why it may be a trap."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlsplit

from .domains import find_lookalike, is_punycode, protected_domains, registrable, scripts, to_unicode
from .sanitize import Link

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
    "rb.gy", "t.ly", "tiny.cc", "s.id", "lnkd.in", "bl.ink", "short.io", "v.gd", "qr.ae", "trib.al", "urlz.fr",
}
# TLDs that are cheap and heavily abused (Spamhaus / Interisle reports); a weak signal on its own.
ABUSED_TLDS = {
    "zip", "mov", "top", "xyz", "click", "link", "work", "rest", "cfd", "sbs", "buzz", "monster", "quest", "icu",
    "cyou", "lol", "bond", "online", "site", "store", "live", "shop", "support", "tk", "ml", "ga", "cf", "gq", "su",
}
# Click-tracking domains of mail service providers: a link whose text shows the brand but goes through one of
# these is normal newsletter plumbing, not deception (measured on Filip's inboxes 06.11).
ESP_TRACKING = {
    "awstrack.me", "snrs.it", "sendgrid.net", "mailgun.org", "mailgun.net", "list-manage.com", "mlsend.com",
    "mailchi.mp", "hubspotlinks.com", "hs-sites.com", "exacttarget.com", "mktomail.com", "mkt.com", "smgrid.eu",
    "rs6.net", "ctctcdn.com", "sparkpostmail.com", "mandrillapp.com", "postmarkapp.com", "beehiiv.com",
    "substack.com", "convertkit-mail.com", "ck.page", "klclick.com", "klclick1.com", "klaviyomail.com",
    "freshmail.pl", "getresponse.com", "gr8.com", "salesmanago.pl", "c.gle", "mailerlite.com", "mlsend2.com",
    "sendinblue.com", "brevo.com", "sib.com", "r.sib", "email-od.com", "cmail19.com", "cmail20.com",
    "createsend1.com", "trk.klclick.com", "linkedin.com", "lnkd.in", "t.co", "app.link", "branch.io",
}
# Redirectors whose real target is in a query parameter.
_REDIRECT_PARAMS = ("url", "u", "q", "redirect", "redirect_uri", "target", "dest", "destination", "goto", "link", "r")


@dataclass
class LinkReport:
    id: str
    url: str                 # as written in the mail
    host: str                # Unicode host
    domain: str              # registrable domain
    shown_text: str
    flags: list[tuple[int, str, str]] = field(default_factory=list)   # (weight, code, Polish explanation)
    embedded_target: str = ""

    @property
    def score(self) -> int:
        return sum(w for w, _, _ in self.flags)

    @property
    def defanged(self) -> str:
        return defang(self.url)


def defang(url: str) -> str:
    """``https://evil.com/x`` -> ``hxxps://evil[.]com/x``: readable, not clickable, not auto-fetched."""
    u = re.sub(r"^http", "hxxp", url, flags=re.I)
    try:
        host = urlsplit(url if "://" in url else "http://" + url).hostname or ""
    except ValueError:
        host = ""
    return u.replace(host, host.replace(".", "[.]"), 1) if host else u.replace(".", "[.]")


def _host_of(url: str) -> str:
    try:
        parts = urlsplit(url if "://" in url else "http://" + url)
        return (parts.hostname or "").lower()
    except ValueError:
        return ""


def analyse_link(link: Link, idx: int, protected: tuple[str, ...] | None = None) -> LinkReport:
    protected = protected or protected_domains()
    url = link.href.strip()
    rep = LinkReport(id=f"L{idx}", url=url, host="", domain="", shown_text=link.text[:200])
    low = url.lower()
    if low.startswith(("mailto:", "tel:", "#", "cid:")):
        return rep
    if low.startswith(("javascript:", "data:", "vbscript:", "file:")):
        rep.flags.append((60, "dangerous_scheme", f"Link typu {low.split(':', 1)[0]}: — przeglądarka wykona kod."))
        return rep
    if re.match(r"(?i)^[a-z][a-z0-9+.-]*:", url) and "://" not in url:
        rep.flags.append((20, "malformed", "Link jest zniekształcony (schemat bez „//”)."))
        return rep
    try:
        parts = urlsplit(url if "://" in url else "http://" + url)
    except ValueError:
        rep.flags.append((20, "malformed", "Link jest zniekształcony."))
        return rep
    host = (parts.hostname or "").lower()
    if not host:
        rep.flags.append((20, "malformed", "Link bez adresu serwera."))
        return rep
    rep.host, rep.domain = to_unicode(host), registrable(to_unicode(host))
    if parts.scheme == "http":
        rep.flags.append((5, "no_tls", "Link bez https."))
    if "@" in (parts.netloc or ""):
        rep.flags.append((40, "userinfo", "Adres zawiera „@”: prawdziwa domena jest za znakiem @, a część przed nim "
                                          "tylko udaje znany serwis."))
    try:
        ipaddress.ip_address(host.strip("[]"))
        rep.flags.append((35, "ip_host", "Link prowadzi na goły adres IP zamiast domeny."))
    except ValueError:
        pass
    if is_punycode(host):
        mixed = len(scripts(rep.host.replace(".", ""))) > 1
        rep.flags.append((30 if mixed else 15, "punycode",
                          f"Domena w punycode ({host} = {rep.host})" + (" z mieszanymi alfabetami." if mixed else ".")))
    la = find_lookalike(host, protected)
    if la:
        rep.flags.append((50 if la.how in ("homoglyph", "edit-distance") else 35, "lookalike",
                          f"Domena {la.domain} podszywa się pod {la.imitates} ({la.how})."))
    if rep.domain in SHORTENERS:
        rep.flags.append((15, "shortener", f"Skracacz linków ({rep.domain}): nie widać, dokąd prowadzi."))
    tld = rep.host.rsplit(".", 1)[-1] if "." in rep.host else ""
    if tld in ABUSED_TLDS:
        rep.flags.append((10, "abused_tld", f"Domena w często nadużywanej końcówce .{tld}."))
    if len(url) > 300:
        rep.flags.append((5, "long_url", "Bardzo długi link."))
    # Open redirectors: google.com/url?q=..., facebook l.php?u=..., or any ?redirect=
    qs = parse_qs(parts.query)
    for key in _REDIRECT_PARAMS:
        for val in qs.get(key, []):
            target = unquote(val)
            if target.lower().startswith(("http://", "https://")):
                t_host = _host_of(target)
                if t_host and registrable(t_host) != rep.domain:
                    rep.embedded_target = target
                    rep.flags.append((15, "redirector", f"Link przekierowuje dalej na {registrable(t_host)}."))
                    la2 = find_lookalike(t_host, protected)
                    if la2:
                        rep.flags.append((40, "lookalike_target", f"Cel przekierowania {la2.domain} podszywa się "
                                                                   f"pod {la2.imitates}."))
                break
    # Shown text looks like a URL/domain but points elsewhere: "https://mbank.pl" -> evil.io
    shown_host = _host_of(link.text) if re.search(r"\b[\w-]+\.[a-z]{2,}\b", link.text.lower()) else ""
    if shown_host and "." in shown_host and " " not in link.text.strip():
        if registrable(to_unicode(shown_host)) != rep.domain and rep.domain not in ESP_TRACKING \
                and not any(rep.host.endswith("." + t) for t in ESP_TRACKING):
            rep.flags.append((45, "text_mismatch",
                              f"Tekst linku pokazuje {shown_host}, a link prowadzi do {rep.host}."))
    return rep


def analyse_links(links: list[Link], protected: tuple[str, ...] | None = None, limit: int = 200) -> list[LinkReport]:
    seen: set[str] = set()
    out = []
    for link in links:
        if link.href in seen:
            continue
        seen.add(link.href)
        out.append(analyse_link(link, len(out) + 1, protected))
        if len(out) >= limit:
            break
    return out
