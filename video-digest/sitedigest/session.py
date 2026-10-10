"""Logged-in browser sessions, one per site.

A site's login lives in <root>/<site>/session.json (Playwright storage state:
cookies + local storage, file mode 600) and is mirrored to cookies.txt
(Netscape format) for yt-dlp and plain downloads. Three ways to get it:

  sitedigest login URL            a visible browser opens; log in, then press Enter
  sitedigest import-cookies FILE  cookies.txt exported from your own browser
  sitedigest login URL --auto     fill the login form from SITEDIGEST_<SITE>_USER / _PASSWORD
                                  (or SITEDIGEST_USER / SITEDIGEST_PASSWORD; e.g. from Bitwarden),
                                  for unattended refreshes

Cookie values are never printed or logged.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

LOGIN_URL = re.compile(r"/(log-?in|sign[-_]?in|signin|auth|sso|users/sign_in|account/login)(\b|/|\?|$)", re.I)


class SessionExpired(RuntimeError):
    """The site sent us to its login page: run `sitedigest login` again."""


def site_name(url: str) -> str:
    host = urlparse(url).hostname or "site"
    host = re.sub(r"^(www|app|members|courses?|learn|academy)\.", "", host)
    return re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")


def site_dir(cfg: dict, site: str) -> Path:
    d = Path(cfg["site"]["root"]) / site
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(cfg: dict, site: str) -> Path:
    return site_dir(cfg, site) / "session.json"


def cookies_path(cfg: dict, site: str) -> Path:
    return site_dir(cfg, site) / "cookies.txt"


def _private_write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, 0o600)


# -- cookies.txt <-> Playwright -------------------------------------------------

def parse_netscape(text: str) -> list[dict]:
    """cookies.txt lines -> Playwright cookie dicts."""
    out = []
    for line in text.splitlines():
        http_only = line.startswith("#HttpOnly_")
        if http_only:
            line = line[len("#HttpOnly_"):]
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, secure, expires, name, value = parts[:7]
        c = {"name": name, "value": value, "domain": domain, "path": path or "/",
             "secure": secure.upper() == "TRUE", "httpOnly": http_only, "sameSite": "Lax"}
        try:
            exp = int(float(expires))
            c["expires"] = exp if exp > 0 else -1
        except ValueError:
            c["expires"] = -1
        out.append(c)
    return out


def to_netscape(cookies: list[dict]) -> str:
    lines = ["# Netscape HTTP Cookie File", "# written by sitedigest; do not share"]
    for c in cookies:
        domain = c.get("domain") or ""
        prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        sub = "TRUE" if domain.startswith(".") else "FALSE"
        exp = c.get("expires")
        exp = int(exp) if exp and exp > 0 else 0
        lines.append("\t".join([prefix + domain, sub, c.get("path") or "/", "TRUE" if c.get("secure") else "FALSE",
                                str(exp), c["name"], c["value"]]))
    return "\n".join(lines) + "\n"


def save_state(cfg: dict, site: str, state: dict) -> None:
    _private_write(state_path(cfg, site), json.dumps(state))
    _private_write(cookies_path(cfg, site), to_netscape(state.get("cookies") or []))


def load_state(cfg: dict, site: str) -> dict | None:
    p = state_path(cfg, site)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def import_cookies(cfg: dict, site: str, cookies_txt: Path) -> int:
    cookies = parse_netscape(cookies_txt.read_text(encoding="utf-8", errors="replace"))
    if not cookies:
        raise ValueError(f"{cookies_txt}: no cookies found (expects the Netscape cookies.txt format)")
    old = load_state(cfg, site) or {"cookies": [], "origins": []}
    keep = {(c["name"], c["domain"], c["path"]): c for c in old.get("cookies") or []}
    for c in cookies:
        keep[(c["name"], c["domain"], c["path"])] = c
    save_state(cfg, site, {"cookies": list(keep.values()), "origins": old.get("origins") or []})
    return len(cookies)


def requests_session(cfg: dict, site: str):
    """A requests.Session carrying the site's cookies, for document downloads."""
    import requests

    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    for c in (load_state(cfg, site) or {}).get("cookies") or []:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", "").lstrip("."), path=c.get("path") or "/")
    return s


# -- browser --------------------------------------------------------------------

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/141.0.0.0 Safari/537.36")


def launch(pw, headless: bool = True):
    exe = os.environ.get("SITEDIGEST_CHROMIUM")
    kw = {"headless": headless, "args": ["--disable-blink-features=AutomationControlled"]}
    if exe:
        kw["executable_path"] = exe
    return pw.chromium.launch(**kw)


def new_context(browser, cfg: dict, site: str):
    state = load_state(cfg, site)
    ctx = browser.new_context(storage_state=state, user_agent=USER_AGENT, viewport={"width": 1366, "height": 900},
                              accept_downloads=True, locale="pl-PL")
    return ctx


def looks_logged_out(start_url: str, final_url: str) -> bool:
    return bool(LOGIN_URL.search(urlparse(final_url).path)) and not LOGIN_URL.search(urlparse(start_url).path)


def login(cfg: dict, url: str, site: str, *, auto: bool = False, wait_for=input, log=print) -> Path:
    """Open the site, let Filip (or the form filler) log in, save the session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = launch(pw, headless=auto)
        ctx = new_context(browser, cfg, site)
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=cfg["site"]["page_timeout_sec"] * 1000)
        if auto:
            user, password = credentials(site)
            _fill_login(page, user, password)
        else:
            log("Log in in the browser window (2FA included), open any course page, then press Enter here.")
            wait_for()
        save_state(cfg, site, ctx.storage_state())
        log(f"session saved for '{site}' ({len(ctx.cookies())} cookies) in {state_path(cfg, site)}")
        browser.close()
    return state_path(cfg, site)


def credentials(site: str) -> tuple[str, str]:
    env = "SITEDIGEST_" + re.sub(r"[^A-Z0-9]+", "_", site.upper())
    return (os.environ.get(f"{env}_USER") or os.environ.get("SITEDIGEST_USER", ""),
            os.environ.get(f"{env}_PASSWORD") or os.environ.get("SITEDIGEST_PASSWORD", ""))


def _fill_login(page, user: str, password: str) -> None:
    if not (user and password):
        raise SessionExpired("SITEDIGEST_USER / SITEDIGEST_PASSWORD not set for --auto login")
    page.fill("input[type=email], input[name*=email i], input[name*=user i], input[name*=login i]", user, timeout=15000)
    if not page.locator("input[type=password]").count():  # two-step forms: e-mail first, then password
        page.keyboard.press("Enter")
        page.wait_for_selector("input[type=password]", timeout=15000)
    page.fill("input[type=password]", password)
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)
    if LOGIN_URL.search(urlparse(page.url).path):
        raise SessionExpired("still on the login page after submitting (wrong password, captcha or 2FA)")
