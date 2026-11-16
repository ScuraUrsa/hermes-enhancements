"""Notion writer contract tests: request layer, row upsert, body rebuild, properties.

Hermetic on purpose: every HTTP call goes to ``FakeSession``, ``time.sleep`` is a
recorded no-op and any real socket connection fails the test. Nothing here needs
network, credentials or ffmpeg.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ytdigest import notion
from ytdigest.notion import API, VERSION, Notion, NotionError

BUNDLE = {
    "video_id": "abc123",
    "url": "https://www.youtube.com/watch?v=abc123",
    "title": "Jak działa inflacja",
    "channel": "Ekonomia",
    "duration_sec": 95,
    "language": "pl",
    "playlists": ["Makra, finanse"],
    "account": None,
    "transcript": {"source": "whisper_groq",
                   "segments": [{"start": 0.0, "end": 4.0, "text": "Inflacja to wzrost cen."}]},
    "frames": [],
}
REPORT = {
    "one_line": "Krótko o inflacji.",
    "about": "O inflacji.",
    "text_summary": "Ceny rosną.",
    "visual_summary": "Wykresy.",
    "key_points": ["a", "b"],
    "language": "pl",
    "video_type": "explainer_visual",
    "tags": ["Ekonomia", "#inflacja"],
    "confidence": 0.83,
    "is_artistic": False,
}
RUN = {"visual": True, "models": ["deepseek-v4.1-flash"], "tier": 2, "cost_usd": 0.0123}
CFG = {"report_language": "pl", "notion_upload_frames": True, "notion_max_frame_images": 6}


class Resp:
    """Just enough of ``requests.Response`` for the writer."""

    def __init__(self, status_code: int = 200, body=None, headers=None, content: bytes = b"{}"):
        self.status_code = status_code
        self._body = {} if body is None else body
        self.headers = headers or {}
        self.content = content
        self.text = json.dumps(self._body) if self._body else ""

    def json(self):
        return self._body


def echo_children(method, url, body):
    """Notion answers an append with the blocks it created, each with an id."""
    kids = (body or {}).get("children") or []
    return Resp(200, {"results": [{**b, "id": f"blk-{i}"} for i, b in enumerate(kids)]})


class FakeSession:
    """Scripted transport. Items are ``Resp``, ``None`` (empty 200) or callables."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[tuple] = []
        self.uploads: list[tuple] = []

    def _next(self, method, url, body):
        if not self.script:
            raise AssertionError(f"unexpected request {method} {url}")
        item = self.script.pop(0)
        if item is None:
            return Resp(200, {})
        if callable(item) and not isinstance(item, Resp):
            return item(method, url, body)
        return item

    def request(self, method, url, headers=None, json=None, timeout=None, **kw):
        self.calls.append((method, url, json, headers or {}, timeout))
        return self._next(method, url, json)

    def post(self, url, headers=None, files=None, timeout=None):  # file upload path
        self.uploads.append((url, headers, files))
        return self._next("POSTFILE", url, None)

    # -- assertions helpers ---------------------------------------------------
    def methods(self) -> list[str]:
        return [c[0] for c in self.calls]

    def urls(self) -> list[str]:
        return [c[1] for c in self.calls]

    def body(self, index: int = 0):
        return self.calls[index][2]

    def appends(self) -> list[tuple[str, list[dict]]]:
        """Every ``PATCH .../children`` as (parent url, children) - position independent."""
        return [(url, body["children"]) for method, url, body, _, _ in self.calls
                if method == "PATCH" and url.endswith("/children")]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("notion tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "connect_ex", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Record backoff instead of sleeping; keeps the suite fast and observable."""
    recorded: list[float] = []
    monkeypatch.setattr(notion, "time", type("T", (), {"sleep": staticmethod(recorded.append)}))
    return recorded


@pytest.fixture(autouse=True)
def _clean_notion_env(monkeypatch):
    """Hermeticity: notion.py reads NOTION_API_KEY before NOTION_TOKEN, so an
    ambient operator-env key would leak into tests that only set NOTION_TOKEN
    (or set neither). Clear both up front; tests that exercise env precedence
    setenv their variable after this fixture runs."""
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)


@pytest.fixture
def client():
    def make(*script, ds: str = "ds-1", token: str = "tok-1") -> tuple[Notion, FakeSession]:
        session = FakeSession(*script)
        return Notion(ds, token=token, session=session), session

    return make


# -- request layer ---------------------------------------------------------

def test_retry_exhaustion_makes_five_attempts_then_raises(client, sleeps):
    nt, session = client(*[Resp(500) for _ in range(5)])

    with pytest.raises(NotionError, match="gave up after retries"):
        nt._req("POST", "/x")

    assert len(session.calls) == 5
    # Four waits for five attempts: sleeping after the last one buys nothing
    # because the next action is to raise.
    assert sleeps == [2.0, 4.0, 6.0, 8.0]


def test_request_sends_auth_headers_version_and_timeout(client):
    nt, session = client(Resp(200, {"ok": True}))

    assert nt._req("POST", "/x", {"a": 1}) == {"ok": True}

    method, url, body, headers, timeout = session.calls[0]
    assert (method, url, body, timeout) == ("POST", f"{API}/x", {"a": 1}, 60)
    auth = headers["Authorization"]
    ok = auth == "Bearer tok-1"
    assert ok, f"expected Bearer <len 5>, got Bearer <len {len(auth) - 7}>, starts-with-ok: {auth.startswith('Bearer ')}"
    assert headers["Notion-Version"] == VERSION
    assert headers["Content-Type"] == "application/json"


def test_request_without_body_omits_content_type(client):
    nt, session = client(Resp(200, {"ok": True}))

    nt._req("GET", "/blocks/x/children?page_size=100")

    assert "Content-Type" not in session.calls[0][3]


def test_request_keeps_absolute_url_and_returns_empty_dict_on_empty_content(client):
    nt, session = client(Resp(200, {}, content=b""))

    assert nt._req("POST", "https://upload.example/put") == {}
    assert session.calls[0][1] == "https://upload.example/put"


def test_successful_request_paces_under_three_per_second(client, sleeps):
    nt, _ = client(Resp(200, {"ok": 1}))

    nt._req("GET", "/x")

    assert sleeps == [0.35]


def test_429_honours_retry_after_header(client, sleeps):
    nt, session = client(Resp(429, headers={"Retry-After": "1"}), Resp(200, {"ok": 1}))

    assert nt._req("POST", "/x", {}) == {"ok": 1}
    assert len(session.calls) == 2
    assert sleeps == [1.0, 0.35]


def test_5xx_uses_linear_backoff(client, sleeps):
    nt, session = client(Resp(502), Resp(503), Resp(200, {"ok": 1}))

    nt._req("POST", "/x", {})

    assert len(session.calls) == 3
    assert sleeps == [2.0, 4.0, 0.35]


def test_4xx_is_not_retried_and_carries_status_and_body(client, sleeps):
    nt, session = client(Resp(400, {"message": "bad property"}))

    with pytest.raises(NotionError) as err:
        nt._req("POST", "/pages", {"x": 1})

    assert "POST /pages -> 400" in str(err.value)
    assert "bad property" in str(err.value)
    assert len(session.calls) == 1
    assert sleeps == []


# -- rows ------------------------------------------------------------------

def test_find_queries_data_source_by_video_id(client):
    nt, session = client(Resp(200, {"results": [{"id": "page-7"}]}))

    assert nt.find("abc123") == "page-7"

    method, url, body = session.calls[0][:3]
    assert (method, url) == ("POST", f"{API}/data_sources/ds-1/query")
    assert body == {"filter": {"property": "Video ID", "rich_text": {"equals": "abc123"}},
                    "page_size": 1}


def test_find_returns_none_when_nothing_matches(client):
    nt, _ = client(Resp(200, {"results": []}))

    assert nt.find("nope") is None


def test_upsert_updates_existing_row_instead_of_creating(client):
    nt, session = client(Resp(200, {"results": [{"id": "page-7"}]}), Resp(200, {}))

    assert nt.upsert("abc123", {"Status": 1}) == "page-7"
    assert session.methods() == ["POST", "PATCH"]
    assert session.urls()[1] == f"{API}/pages/page-7"
    assert session.body(1) == {"properties": {"Status": 1}}


def test_upsert_creates_row_in_the_data_source_when_missing(client):
    nt, session = client(Resp(200, {"results": []}), Resp(200, {"id": "page-9"}))

    assert nt.upsert("abc123", {"Status": 1}) == "page-9"
    assert session.methods() == ["POST", "POST"]
    assert session.urls()[1] == f"{API}/pages"
    assert session.body(1) == {"parent": {"type": "data_source_id", "data_source_id": "ds-1"},
                               "properties": {"Status": 1}}


def test_page_url_drops_dashes(client):
    nt, _ = client()

    assert nt.page_url("1111-2222") == "https://www.notion.so/11112222"


# -- body ------------------------------------------------------------------

def test_clear_paginates_and_deletes_every_block(client):
    nt, session = client(
        Resp(200, {"results": [{"id": "b1"}, {"id": "b2"}], "has_more": True, "next_cursor": "c1"}),
        None, None,
        Resp(200, {"results": [{"id": "b3"}], "has_more": False}),
        None,
    )

    nt.clear("page-7")

    assert session.methods() == ["GET", "DELETE", "DELETE", "GET", "DELETE"]
    assert session.urls()[0] == f"{API}/blocks/page-7/children?page_size=100"
    assert session.urls()[3] == f"{API}/blocks/page-7/children?page_size=100&start_cursor=c1"
    assert session.urls()[1] == f"{API}/blocks/b1"
    assert session.urls()[4] == f"{API}/blocks/b3"


def test_clear_on_empty_page_makes_one_request(client):
    nt, session = client(Resp(200, {"results": [], "has_more": False}))

    nt.clear("page-7")

    assert session.methods() == ["GET"]


def test_append_chunks_children_in_hundreds(client):
    nt, session = client(*[echo_children for _ in range(3)])

    created = nt.append("page-7", [{"object": "block", "type": "paragraph"} for _ in range(250)])

    assert session.methods() == ["PATCH"] * 3
    assert [len(c[2]["children"]) for c in session.calls] == [100, 100, 50]
    assert session.urls() == [f"{API}/blocks/page-7/children"] * 3
    assert len(created) == 250


# -- properties ------------------------------------------------------------

def test_properties_cover_every_schema_column():
    props = notion.properties(BUNDLE, REPORT, RUN, "done")

    assert set(props) == {
        "Tytuł", "Video ID", "Link", "Kanał", "Status", "Typ wideo", "Tagi", "Jedno zdanie",
        "Język", "Czas trwania (min)", "Playlista", "Konto", "Źródło transkryptu",
        "Analiza obrazu", "Model", "Poziom modelu", "Koszt USD", "Pewność", "Przetworzono",
    }
    assert props["Tytuł"]["title"][0]["text"]["content"] == "Jak działa inflacja"
    assert props["Video ID"]["rich_text"][0]["text"]["content"] == "abc123"
    assert props["Link"]["url"] == BUNDLE["url"]
    assert props["Status"] == {"select": {"name": "Gotowe"}}
    assert props["Typ wideo"] == {"select": {"name": "explainer_visual"}}
    assert props["Tagi"] == {"multi_select": [{"name": "Ekonomia"}, {"name": "#inflacja"}]}
    assert props["Jedno zdanie"]["rich_text"][0]["text"]["content"] == "Krótko o inflacji."
    assert props["Język"] == {"select": {"name": "pl"}}
    assert props["Czas trwania (min)"] == {"number": 1.6}
    assert props["Playlista"] == {"multi_select": [{"name": "Makra  finanse"}]}
    assert props["Konto"] == {"select": {"name": "ręcznie"}}
    assert props["Źródło transkryptu"] == {"select": {"name": "Whisper Groq"}}
    assert props["Analiza obrazu"] == {"checkbox": True}
    assert props["Model"]["rich_text"][0]["text"]["content"] == "deepseek-v4.1-flash"
    assert props["Poziom modelu"] == {"select": {"name": "T2 średni"}}
    assert props["Koszt USD"] == {"number": 0.0123}
    assert props["Pewność"] == {"number": 0.83}
    assert "Opublikowano" not in props  # only added when the bundle has a date


def test_properties_map_status_source_and_tier_vocabularies():
    assert {k: v["select"]["name"] for k, v in
            ((s, notion.properties(BUNDLE, REPORT, RUN, s)["Status"]) for s in notion.STATUS)
            } == notion.STATUS
    for source, label in notion.SOURCE.items():
        props = notion.properties({**BUNDLE, "transcript": {"source": source}}, REPORT, RUN, "done")
        assert props["Źródło transkryptu"] == {"select": {"name": label}}
    for tier, label in notion.TIER.items():
        props = notion.properties(BUNDLE, REPORT, {**RUN, "tier": tier}, "done")
        assert props["Poziom modelu"] == {"select": {"name": label}}


def test_properties_keep_unknown_transcript_source_verbatim():
    props = notion.properties({**BUNDLE, "transcript": {"source": "brand_new_backend"}},
                              REPORT, RUN, "done")

    assert props["Źródło transkryptu"] == {"select": {"name": "brand_new_backend"}}


@pytest.mark.parametrize("language, expected", [
    ("pl", {"select": {"name": "pl"}}),
    ("en-US", {"select": {"name": "en"}}),
    ("de", {"select": {"name": "inny"}}),
    ("", {"select": None}),
    (None, {"select": None}),
])
def test_properties_map_language_to_pl_en_or_inny(language, expected):
    props = notion.properties({**BUNDLE, "language": language}, {**REPORT, "language": None},
                              RUN, "done")

    assert props["Język"] == expected


def test_properties_flatten_missing_values_to_schema_safe_defaults():
    bundle = {"video_id": "vid-only", "url": "u", "title": None, "duration_sec": None,
              "transcript": {"source": "none"}}
    props = notion.properties(bundle, {"tags": []}, {}, "queued")

    assert props["Tytuł"]["title"][0]["text"]["content"] == "vid-only"
    assert props["Czas trwania (min)"] == {"number": 0.0}
    assert props["Pewność"] == {"number": 0.0}
    assert props["Poziom modelu"] == {"select": {"name": "T1 tani"}}  # tier defaults to 1
    assert props["Koszt USD"] == {"number": 0.0}
    assert props["Analiza obrazu"] == {"checkbox": False}
    assert props["Tagi"] == {"multi_select": []}
    assert props["Język"] == {"select": None}


def test_properties_truncate_to_notion_limits():
    long_bundle = {**BUNDLE, "title": "T" * 5000, "playlists": [f"p{i}," * 60 for i in range(15)]}
    long_report = {**REPORT, "tags": [f"t{i}" * 60 for i in range(30)], "one_line": "x" * 5000}

    props = notion.properties(long_bundle, long_report, RUN, "done")

    assert len(props["Tytuł"]["title"][0]["text"]["content"]) == 1900
    assert len(props["Jedno zdanie"]["rich_text"][0]["text"]["content"]) == 1900
    assert len(props["Tagi"]["multi_select"]) == 20
    assert all(len(t["name"]) == 100 for t in props["Tagi"]["multi_select"])
    assert len(props["Playlista"]["multi_select"]) == 10
    assert "," not in props["Playlista"]["multi_select"][0]["name"]


def test_properties_timestamp_is_iso_utc_now():
    props = notion.properties(BUNDLE, REPORT, RUN, "done")

    stamp = datetime.fromisoformat(props["Przetworzono"]["date"]["start"])
    offset = stamp.utcoffset()
    assert stamp.tzinfo is not None and offset is not None and offset.total_seconds() == 0
    assert abs((datetime.now(timezone.utc) - stamp).total_seconds()) < 60


def test_properties_include_publication_date_only_when_known():
    props = notion.properties({**BUNDLE, "published_at": "2026-01-02T03:04:05Z"}, REPORT, RUN, "done")

    assert props["Opublikowano"] == {"date": {"start": "2026-01-02T03:04:05Z"}}


# -- write_report ----------------------------------------------------------

@pytest.fixture
def bundle_dir(tmp_path) -> Path:
    for name in ("f1.jpg", "f2.jpg", "f3.jpg"):
        (tmp_path / name).write_bytes(b"\xff\xd8\xff" + name.encode())
    return tmp_path


def frame(name: str, t: float = 1.0, adds: bool = True) -> dict:
    return {"path": name, "t": t, "caption": f"kadr {name}", "adds_information": adds}


def test_write_report_replaces_body_and_returns_page_url(client, bundle_dir):
    nt, session = client(
        Resp(200, {"results": [{"id": "page-7"}]}),  # find
        None,                                        # upsert: patch properties
        None,                                        # clear
        echo_children,                               # append body
        echo_children,                               # append transcript under the toggle
    )
    bundle = {**BUNDLE, "frames": []}

    url = notion.write_report(nt, bundle_dir, bundle, REPORT, RUN, CFG)

    assert url == "https://www.notion.so/page7"
    assert session.methods() == ["POST", "PATCH", "GET", "PATCH", "PATCH"]
    assert session.urls()[2] == f"{API}/blocks/page-7/children?page_size=100"
    body = session.appends()[0][1]
    assert body[0]["type"] == "callout"
    toggles = [i for i, b in enumerate(body)
               if b["type"] == "heading_2" and b["heading_2"].get("is_toggleable")]
    assert len(toggles) == 1
    # echo_children() names the created block after its index in the request
    parent, transcript = session.appends()[1]
    assert parent == f"{API}/blocks/blk-{toggles[0]}/children"
    assert transcript[0]["paragraph"]["rich_text"][0]["text"]["content"].startswith("0:00")


def test_write_report_marks_artistic_videos_without_transcript_or_frames(client, bundle_dir):
    nt, session = client(
        Resp(200, {"results": []}),
        Resp(200, {"id": "page-9"}),  # create
        None,                          # clear
        echo_children,                 # append body
    )
    report = {**REPORT, "is_artistic": True, "video_type": "music"}
    bundle = {**BUNDLE, "frames": [frame("f1.jpg")]}

    notion.write_report(nt, bundle_dir, bundle, report, RUN, CFG)

    assert session.methods() == ["POST", "POST", "GET", "PATCH"]  # no file upload requests
    assert session.uploads == []
    assert session.body(1)["properties"]["Status"] == {"select": {"name": "Artystyczne"}}
    assert session.body(1)["properties"]["Analiza obrazu"] == {"checkbox": True}
    assert len(session.appends()) == 1  # artistic body has no transcript toggle


def test_write_report_uploads_only_useful_frames_up_to_the_cap(client, bundle_dir):
    nt, session = client(
        Resp(200, {"results": [{"id": "page-7"}]}),   # find
        None,                                          # upsert: patch properties
        Resp(200, {"id": "up1"}), Resp(200, {}),       # f1: create upload + send file
        Resp(200, {"id": "up2"}), Resp(200, {}),       # f2
        None,                                          # clear
        echo_children,                                 # append body
        echo_children,                                 # append transcript
    )
    bundle = {**BUNDLE, "frames": [
        frame("f1.jpg", 5),
        frame("f2.jpg", 10),
        frame("f3.jpg", 15),       # over the cap of 2
        frame("f3.jpg", 20, adds=False),  # filtered out by adds_information
    ]}

    notion.write_report(nt, bundle_dir, bundle, REPORT, RUN, {**CFG, "notion_max_frame_images": 2})

    assert [c[1] for c in session.calls].count(f"{API}/file_uploads") == 2
    assert len(session.uploads) == 2
    assert session.uploads[0][2]["file"][0] == "f1.jpg"
    images = [b for b in session.appends()[0][1] if b["type"] == "image"]
    assert [i["image"]["file_upload"]["id"] for i in images] == ["up1", "up2"]
    assert images[0]["image"]["caption"][0]["text"]["content"] == "0:05 kadr f1.jpg"


def test_write_report_skips_frames_when_uploading_is_disabled(client, bundle_dir):
    nt, session = client(
        Resp(200, {"results": [{"id": "page-7"}]}),
        None,            # upsert: patch properties
        None,            # clear
        echo_children,   # append body
        echo_children,   # append transcript
    )

    notion.write_report(nt, bundle_dir, {**BUNDLE, "frames": [frame("f1.jpg")]}, REPORT, RUN,
                        {**CFG, "notion_upload_frames": False})

    assert session.uploads == []
    assert f"{API}/file_uploads" not in session.urls()


def test_write_report_survives_a_failed_frame_upload(client, bundle_dir):
    nt, session = client(
        Resp(200, {"results": [{"id": "page-7"}]}),
        None,                                   # upsert: patch properties
        Resp(200, {"id": "up1"}),
        Resp(413, {"message": "too large"}),    # file send fails -> frame dropped
        None,                                   # clear
        echo_children,                          # append body
        echo_children,                          # append transcript
    )

    url = notion.write_report(nt, bundle_dir, {**BUNDLE, "frames": [frame("f1.jpg")]}, REPORT, RUN, CFG)

    assert url.endswith("page7")
    assert [b["type"] for b in session.appends()[0][1] if b["type"] == "image"] == []


# -- mark ------------------------------------------------------------------

def test_mark_writes_a_bare_row(client):
    nt, session = client(Resp(200, {"results": []}), Resp(200, {"id": "page-1"}))

    url = notion.mark(nt, "abc123", BUNDLE["url"], "", "queued")

    assert url == "https://www.notion.so/page1"
    assert session.body(1)["properties"] == {
        "Tytuł": {"title": [{"text": {"content": "abc123"}}]},
        "Video ID": {"rich_text": [{"text": {"content": "abc123"}}]},
        "Link": {"url": BUNDLE["url"]},
        "Status": {"select": {"name": "W kolejce"}},
    }


def test_mark_adds_note_and_account_when_given(client):
    nt, session = client(Resp(200, {"results": [{"id": "page-1"}]}), None)

    notion.mark(nt, "abc123", BUNDLE["url"], "Tytuł", "failed", note="n" * 3000, account="konto-x")

    props = session.body(1)["properties"]
    assert len(props["Jedno zdanie"]["rich_text"][0]["text"]["content"]) == 1900
    assert props["Konto"] == {"select": {"name": "konto-x"}}
    assert props["Status"] == {"select": {"name": "Błąd"}}


# -- construction ----------------------------------------------------------

def test_missing_token_fails_before_any_request(monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)

    with pytest.raises(NotionError, match="NOTION_API_KEY"):
        Notion("ds-1")


def test_token_falls_back_to_environment(monkeypatch):
    """NOTION_TOKEN is the legacy fallback: with no explicit token and no
    NOTION_API_KEY, the writer must still authenticate. The assertion compares
    into a bool so a failure can never echo the captured Authorization header
    (which, on a misconfigured runner, could be a real credential)."""
    monkeypatch.setenv("NOTION_TOKEN", "env-token")
    session = FakeSession(Resp(200, {"ok": 1}))

    nt = Notion("ds-1", session=session)
    nt._req("GET", "/x")

    auth = session.calls[0][3]["Authorization"]
    ok = auth == "Bearer env-token"
    assert ok, f"expected Bearer <len 9>, got Bearer <len {len(auth) - 7}>, starts-with-ok: {auth.startswith('Bearer ')}"


def test_error_messages_never_embed_token(client):
    """The _req 4xx path interpolates the server response body into NotionError,
    and the upload path does the same — a hostile/misbehaving endpoint could
    echo the Authorization header back in r.text. Guard: with a fake
    'ntn_'-prefixed key on, no raised error message (str or repr) may contain
    the credential prefix. The missing-token path is safe by construction
    ('NOTION_API_KEY not set' is a constant), so the HTTP path is the one that
    genuinely risks echoing configuration."""
    fake = "ntn_" + "x" * 12
    nt, session = client(Resp(400, {"message": "bad property"}), token=fake)

    with pytest.raises(NotionError) as err:
        nt._req("POST", "/pages", {"x": 1})

    text, rep = str(err.value), repr(err.value)
    assert "ntn_" not in text and "ntn_" not in rep, (
        f"error message leaked credential prefix: len={len(text)}")
    assert "POST /pages -> 400" in text  # the useful part of the message survives


@pytest.mark.parametrize("ds", ["", "-"])
def test_data_source_id_is_not_validated_so_page_level_callers_work(ds):
    """compare.publish_notion() uses Notion("") and sitedigest.setup() uses Notion("-"):
    both are page-level clients, so __init__ must not reject an empty data source."""
    session = FakeSession(Resp(200, {"id": "p"}))

    nt = Notion(ds, token="tok", session=session)
    nt._req("POST", "/pages", {"parent": {"page_id": "p"}})

    assert nt.ds == ds
    assert session.calls[0][1] == f"{API}/pages"


def test_properties_treat_null_lists_as_empty_and_never_crash():
    """A model emitting "tags": null / "playlists": null must not kill the write path.

    Null and missing both mean "nothing to tag", so the payload carries empty
    multi_select arrays instead of raising TypeError.
    """
    bundle = {"video_id": "v1", "url": "u", "transcript": {"source": "none"}, "playlists": None}

    props = notion.properties(bundle, {"tags": None}, {}, "queued")

    assert props["Tagi"] == {"multi_select": []}
    assert props["Playlista"] == {"multi_select": []}


def test_unknown_status_is_a_notion_error_naming_the_vocabulary():
    """STATUS[status] used to escape as a bare KeyError; callers catch NotionError."""
    bundle = {"video_id": "v1", "url": "u", "transcript": {"source": "none"}}

    with pytest.raises(NotionError) as err:
        notion.properties(bundle, {}, {}, "bogus")

    message = str(err.value)
    assert "bogus" in message
    for known in ("queued", "done", "failed"):
        assert known in message


def test_unknown_status_in_mark_fails_before_any_request():
    session = FakeSession(Resp(200, {"id": "page-1"}))
    nt = Notion("ds-1", token="tok-1", session=session)

    with pytest.raises(NotionError, match="bogus"):
        notion.mark(nt, "abc123", BUNDLE["url"], "", "bogus")

    assert session.calls == []
