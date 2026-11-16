"""local-extract: dostawca ``web_extract`` dla Hermesa bez kluczy i bez osobnej usługi (K136).

Pobiera stronę bezpośrednio z maszyny Hermesa (httpx z ochroną SSRF Hermesa) i wyciąga główny tekst
biblioteką trafilatura (Apache-2.0). Strony, których nie da się tak otworzyć (renderowane w JS, blokady,
błąd HTTP, za mało tekstu), przekazuje do pierścienia bez klucza Hermesa (Exa, Parallel, Firecrawl, Keenable),
chyba że ``web.keyless_fallback: false``. Wybór: ``web.extract_backend: local-extract``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

NAME = "local-extract"
MAX_BYTES = 5 * 1024 * 1024          # większych stron nie pobieramy w całości
MIN_CHARS = 200                      # mniej tekstu = najpewniej strona z JS albo blokada
TIMEOUT_S = 20.0
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36 hermes-local-extract/1.0")
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown", "application/xml", "text/xml")


def _page_error(url: str, error: str) -> dict[str, Any]:
    return {"url": url, "title": "", "content": "", "error": error}


def _client():
    """httpx.Client z ochroną SSRF Hermesa (adresy prywatne tylko przy security.allow_private_urls)."""
    try:
        from tools.url_safety import create_ssrf_safe_client
        return create_ssrf_safe_client(timeout=TIMEOUT_S, follow_redirects=True,
                                       headers={"User-Agent": USER_AGENT, "Accept-Language": "pl,en;q=0.8"})
    except ImportError:  # poza Hermesem (testy): zwykły klient
        import httpx
        return httpx.Client(timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _download(client, url: str) -> tuple[str, str, str]:
    """(tekst, content-type, końcowy URL); wyjątek przy błędzie HTTP, złym typie albo za dużej stronie."""
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype and not ctype.startswith(TEXT_TYPES):
            raise ValueError(f"typ {ctype} nie jest stroną tekstową")
        chunks, size = [], 0
        for chunk in resp.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError(f"strona większa niż {MAX_BYTES // 1024 // 1024} MB")
            chunks.append(chunk)
        body = b"".join(chunks)
        enc = resp.encoding or "utf-8"
        try:
            text = body.decode(enc, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        return text, ctype, str(resp.url)


def extract_html(html: str, url: str) -> tuple[str, str]:
    """(tytuł, tekst w markdown) z HTML; pusty tekst, gdy trafilatura nic nie znalazła."""
    import trafilatura
    text = trafilatura.extract(html, url=url, output_format="markdown", include_links=True,
                               include_tables=True, include_comments=False, favor_recall=True) or ""
    title = ""
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        title = (meta.title or "") if meta else ""
    except Exception:  # metadane są tylko dodatkiem
        pass
    return title, text.strip()


def fetch_one(client, url: str) -> dict[str, Any]:
    try:
        body, ctype, final_url = _download(client, url)
    except Exception as exc:
        return _page_error(url, f"local-extract: {type(exc).__name__}: {exc}"[:300])
    if ctype in ("text/plain", "text/markdown"):
        title, text = "", body.strip()
    else:
        title, text = extract_html(body, final_url)
    if len(text) < MIN_CHARS:
        return _page_error(url, f"local-extract: tylko {len(text)} znaków tekstu (strona z JS albo blokada)")
    meta = {"source": NAME}
    if final_url != url:
        meta["final_url"] = final_url
    return {"url": url, "title": title, "content": text, "raw_content": text, "metadata": meta}


def _keyless_on() -> bool:
    try:
        from plugins.web.keyless_mcp import keyless_enabled
        return bool(keyless_enabled())
    except Exception:
        return False


def _fallback(urls: list[str]) -> list[dict[str, Any]]:
    from plugins.web.keyless_mcp import extract_with_failover
    return extract_with_failover("firecrawl", list(urls))


def extract_urls(urls: list[str], *, fallback=None, client_factory=_client) -> list[dict[str, Any]]:
    with client_factory() as client:
        results = [fetch_one(client, u) for u in urls]
    failed = [i for i, r in enumerate(results) if r.get("error")]
    if failed and fallback is not None:
        try:
            rescued = fallback([urls[i] for i in failed])
        except Exception as exc:
            logger.warning("local-extract: zapas bez klucza padł: %s", exc)
            rescued = []
        by_url = {r.get("url"): r for r in rescued if isinstance(r, dict)}
        for i in failed:
            r = by_url.get(urls[i])
            if r and not r.get("error") and r.get("content"):
                meta = dict(r.get("metadata") or {})
                meta["rescued_from"] = NAME
                meta["local_error"] = results[i]["error"]
                results[i] = {**r, "url": urls[i], "metadata": meta}
    return results


try:  # nowsze Hermesy
    from plugins.web._common import BaseWebSearchProvider as _Base
except ImportError:
    try:  # starsze buildy (np. prod aaa1e08): rejestr wymaga podklasy WebSearchProvider
        from agent.web_search_provider import WebSearchProvider as _Base
    except ImportError:  # testy poza Hermesem
        _Base = object


class LocalExtractProvider(_Base):  # type: ignore[misc,valid-type]
    NAME = NAME
    DISPLAY_NAME = "Local extract (trafilatura)"
    KEY_ENV = ""
    EXTRACT = True
    KEYLESS = False

    name = property(lambda self: NAME)
    display_name = property(lambda self: "Local extract (trafilatura)")

    def is_available(self) -> bool:
        try:
            import trafilatura  # noqa: F401
            return True
        except ImportError:
            return False

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        if not self.is_available():
            return [_page_error(u, "local-extract: brak pakietu trafilatura w venv Hermesa") for u in urls]
        return extract_urls(list(urls), fallback=_fallback if _keyless_on() else None)


def register(ctx) -> None:
    ctx.register_web_search_provider(LocalExtractProvider())
