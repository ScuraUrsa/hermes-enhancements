"""Testy wtyczki local_extract (K136): bez sieci, httpx.MockTransport."""
import importlib.util
import pathlib

import httpx
import pytest

pytest.importorskip("trafilatura")

_P = pathlib.Path(__file__).resolve().parents[1] / "integracje" / "hermes" / "local_extract" / "__init__.py"
_spec = importlib.util.spec_from_file_location("local_extract", _P)
le = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(le)

ARTICLE = "<html><head><title>Artykuł testowy</title></head><body><nav>menu</nav><article><h1>Nagłówek</h1>" + \
    "".join(f"<p>Akapit {i}: Hermes otwiera strony lokalnie i wyciąga z nich główny tekst bez kluczy API.</p>" for i in range(8)) + \
    "</article><footer>stopka</footer></body></html>"
JS_PAGE = "<html><head><title>App</title></head><body><div id=root></div><script>app()</script></body></html>"


def _factory(routes):
    def handler(request):
        status, ctype, body = routes[str(request.url)]
        return httpx.Response(status, headers={"content-type": ctype}, content=body.encode())
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_article_extracted():
    f = _factory({"https://a.test/x": (200, "text/html; charset=utf-8", ARTICLE)})
    [r] = le.extract_urls(["https://a.test/x"], client_factory=f)
    assert "error" not in r
    assert "Akapit 3" in r["content"] and "stopka" not in r["content"]
    assert r["title"] in ("Artykuł testowy", "Nagłówek")  # trafilatura woli <h1> od <title>
    assert r["metadata"]["source"] == "local-extract"


def test_js_page_and_http_error_go_to_fallback():
    f = _factory({"https://a.test/js": (200, "text/html", JS_PAGE), "https://a.test/403": (403, "text/html", "no"),
                  "https://a.test/ok": (200, "text/html", ARTICLE)})
    asked = []

    def fallback(urls):
        asked.extend(urls)
        return [{"url": "https://a.test/js", "title": "App", "content": "tekst z zapasu", "raw_content": ""},
                {"url": "https://a.test/403", "title": "", "content": "", "error": "blocked"}]

    res = le.extract_urls(["https://a.test/js", "https://a.test/403", "https://a.test/ok"],
                          fallback=fallback, client_factory=f)
    assert asked == ["https://a.test/js", "https://a.test/403"]
    assert res[0]["content"] == "tekst z zapasu" and res[0]["metadata"]["rescued_from"] == "local-extract"
    assert "JS" in res[0]["metadata"]["local_error"]
    assert res[1]["error"].startswith("local-extract: HTTPStatusError")
    assert "Akapit" in res[2]["content"]


def test_no_fallback_when_disabled_and_binary_refused():
    f = _factory({"https://a.test/f.zip": (200, "application/zip", "PK")})
    [r] = le.extract_urls(["https://a.test/f.zip"], fallback=None, client_factory=f)
    assert "nie jest stroną tekstową" in r["error"]


def test_plain_text_passthrough():
    body = "linia tekstu " * 40
    f = _factory({"https://a.test/t.txt": (200, "text/plain", body)})
    [r] = le.extract_urls(["https://a.test/t.txt"], client_factory=f)
    assert r["content"] == body.strip()


def test_fallback_exception_keeps_local_error():
    f = _factory({"https://a.test/js": (200, "text/html", JS_PAGE)})

    def boom(urls):
        raise RuntimeError("ring down")

    [r] = le.extract_urls(["https://a.test/js"], fallback=boom, client_factory=f)
    assert "error" in r
