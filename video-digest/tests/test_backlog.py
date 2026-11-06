"""Contract tests for the backlog filler (``ytdigest.backlog``).

These tests pin *behaviour* of the module that feeds Filip's whole digest queue:
which YouTube API calls are made, how pagination is followed, what happens on a
missing playlist (404) versus a broken token (4xx), which playlist entries are
dropped, and — most important — that one broken account can never stop the
others from being queued.

Why this file exists: on 2026-10-25 ``ytdigest/backlog.py`` had 130 lines and
zero tests, while it is the only path that puts videos into the queue at all
(the run47 manifest of 259 videos was built through it). Every silent
regression below — ``404 -> []`` swallowed, ``nextPageToken`` ignored, entries
without ``contentDetails`` counted, per-account isolation removed — means
missing videos in the archive with no alarm at all.

Fully hermetic: an autouse fixture makes any socket use fail loudly, ``requests``
is replaced at the module the code imports it from, and every token/cookie file
lives under ``tmp_path``. Nothing here reads ``~/.hermes/google-accounts/**`` or
the real ``config.yaml``, and the suite passes on a host with no network.

The mutation table in the run48 card documents which named test goes RED for
each deliberate bug (see ``tests/`` history / kanban task t_6ba43622).
"""

from __future__ import annotations

import json
import socket

import pytest
import requests

import ytdigest.backlog as backlog
from ytdigest import fetch
from ytdigest.queue import BACKLOG_PRIORITY, Queue

# --------------------------------------------------------------------------- #
# hermeticity
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any attempt to open a socket fails the test loudly."""

    def boom(*args, **kwargs):
        raise AssertionError("backlog tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "connect_ex", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


@pytest.fixture(autouse=True)
def _no_live_requests(monkeypatch):
    """HTTP is opt-in per test: unpatched ``requests`` calls fail loudly too."""

    def boom(*args, **kwargs):
        raise AssertionError("backlog tests must not call requests for real")

    monkeypatch.setattr(requests, "get", boom, raising=True)
    monkeypatch.setattr(requests, "post", boom, raising=True)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


class Resp:
    """The little of ``requests.Response`` this module actually uses."""

    def __init__(self, status_code=200, body=None, text=None):
        self.status_code = status_code
        self._body = {} if body is None else body
        self.text = text if text is not None else json.dumps(self._body)

    def json(self):
        return self._body


class FakeQueue:
    """Records every ``add()`` and mimics ``Queue.add``'s "is this new?" answer.

    ``new="dedupe"`` returns True only the first time a video id is offered,
    exactly like the real queue (a video in two playlists counts once).
    """

    def __init__(self, new=True):
        self.calls = []
        self._new = new
        self._seen = set()

    def add(self, video_id, url, *, title=None, account=None, playlist=None, priority=None):
        self.calls.append(
            {
                "video_id": video_id,
                "url": url,
                "title": title,
                "account": account,
                "playlist": playlist,
                "priority": priority,
            }
        )
        if self._new == "dedupe":
            fresh = video_id not in self._seen
            self._seen.add(video_id)
            return fresh
        return bool(self._new)

    @property
    def ids(self):
        return [c["video_id"] for c in self.calls]

    @property
    def playlists(self):
        return [c["playlist"] for c in self.calls]


def _cfg(tmp_path, **over):
    """A config dict shaped like ``config.yaml`` but pointing at ``tmp_path``."""
    c = {
        "accounts": ["fjkazmierczak", "koalamis6"],
        "include_liked": False,
        "skip_playlists": [],
        "extra_playlists": [],
        "cookies_file": str(tmp_path / "cookies" / "{account}.txt"),
        "google_accounts_dir": str(tmp_path / "google-accounts"),
    }
    c.update(over)
    return c


def _token_json(**over):
    tok = {
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "access_token": "stale-access-token",
    }
    tok.update(over)
    return tok


def _forbid_flat_playlist(monkeypatch):
    """Watch Later / extra playlists must not be touched by API-only tests."""

    def boom(url, cookies=None):
        raise AssertionError(f"flat_playlist must not be called (url={url})")

    monkeypatch.setattr(fetch, "flat_playlist", boom)


def _install_get(monkeypatch, pages):
    """Patch ``requests.get`` with a queue of canned pages; returns the call log."""
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {}), "timeout": timeout})
        return Resp(200, pages[len(calls) - 1])

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


# --------------------------------------------------------------------------- #
# _paged: 404, hard errors, pagination, page size
# --------------------------------------------------------------------------- #


def test_paged_404_is_empty_not_an_error(monkeypatch):
    """A missing playlist (deleted, or never created) is a silent empty list."""
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp(404, text="Not Found"))

    assert backlog._paged("tok", "playlists", {"part": "snippet", "mine": "true"}) == []


@pytest.mark.parametrize("code", [400, 401, 403, 500])
def test_paged_hard_error_raises_runtime_error(monkeypatch, code):
    """Anything other than 404 must surface: 400 is an error, not a boundary."""
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Resp(code, text="quotaExceeded"))

    with pytest.raises(RuntimeError) as excinfo:
        backlog._paged("tok", "playlistItems", {"part": "snippet"})

    assert str(code) in str(excinfo.value)
    assert "quotaExceeded" in str(excinfo.value)


def test_paged_follows_next_page_token_and_keeps_order(monkeypatch):
    """Two pages are stitched in API order and the token is sent back."""
    pages = [
        {"items": [{"id": "a"}, {"id": "b"}], "nextPageToken": "PAGE-2"},
        {"items": [{"id": "c"}]},
    ]
    calls = _install_get(monkeypatch, pages)

    got = backlog._paged("tok", "playlistItems", {"part": "snippet", "playlistId": "PL1"})

    assert [i["id"] for i in got] == ["a", "b", "c"]
    assert len(calls) == 2
    assert "pageToken" not in calls[0]["params"], "first request must not carry a page token"
    assert calls[1]["params"]["pageToken"] == "PAGE-2"


def test_paged_always_sends_max_results_50(monkeypatch):
    """The page size is pinned: YouTube's maximum, on every page."""
    pages = [{"items": [], "nextPageToken": "P2"}, {"items": []}]
    calls = _install_get(monkeypatch, pages)

    backlog._paged("tok", "playlists", {"part": "snippet"})

    assert [c["params"]["maxResults"] for c in calls] == [50, 50]


def test_paged_sends_bearer_token_to_the_v3_endpoint(monkeypatch):
    calls = _install_get(monkeypatch, [{"items": []}])

    backlog._paged("tok-abc", "playlists", {"part": "snippet", "mine": "true"})

    assert calls[0]["url"] == "https://www.googleapis.com/youtube/v3/playlists"
    assert calls[0]["headers"]["Authorization"] == "Bearer tok-abc"
    assert calls[0]["params"]["part"] == "snippet"
    assert calls[0]["params"]["mine"] == "true"
    assert calls[0]["timeout"] == 30


# --------------------------------------------------------------------------- #
# api_playlists / api_items
# --------------------------------------------------------------------------- #


def test_playlists_without_liked_has_no_magic_entry(monkeypatch):
    monkeypatch.setattr(
        backlog, "_paged", lambda token, path, params: [{"id": "PL1", "snippet": {"title": "Nauka"}}]
    )

    assert backlog.api_playlists("tok", False) == [("PL1", "Nauka")]


def test_playlists_with_liked_appends_magic_LL_entry(monkeypatch):
    """``include_liked`` is the only way "Polubione" reaches the queue."""
    monkeypatch.setattr(
        backlog, "_paged", lambda token, path, params: [{"id": "PL1", "snippet": {"title": "Nauka"}}]
    )

    assert backlog.api_playlists("tok", True) == [("PL1", "Nauka"), ("LL", "Polubione")]


def test_playlists_asks_for_the_authenticated_channel(monkeypatch):
    seen = {}

    def fake_paged(token, path, params):
        seen.update({"token": token, "path": path, "params": params})
        return []

    monkeypatch.setattr(backlog, "_paged", fake_paged)

    backlog.api_playlists("tok", False)

    assert seen["path"] == "playlists"
    assert seen["params"] == {"part": "snippet", "mine": "true"}


def test_items_skips_entries_without_content_details(monkeypatch):
    """A deleted/private entry has no ``contentDetails`` and must not be counted."""
    rows = [
        {"contentDetails": {"videoId": "aaaaaaaaaaa"}, "snippet": {"title": "jeden"}},
        {"snippet": {"title": "wpis bez contentDetails"}},
        {"contentDetails": {"videoId": "bbbbbbbbbbb"}, "snippet": {}},
    ]
    monkeypatch.setattr(backlog, "_paged", lambda token, path, params: rows)

    assert backlog.api_items("tok", "PL1") == [("aaaaaaaaaaa", "jeden"), ("bbbbbbbbbbb", "")]


def test_items_requests_snippet_and_content_details(monkeypatch):
    seen = {}

    def fake_paged(token, path, params):
        seen.update({"path": path, "params": params})
        return []

    monkeypatch.setattr(backlog, "_paged", fake_paged)

    backlog.api_items("tok", "PL-xyz")

    assert seen["path"] == "playlistItems"
    assert seen["params"] == {"part": "snippet,contentDetails", "playlistId": "PL-xyz"}


# --------------------------------------------------------------------------- #
# _skip
# --------------------------------------------------------------------------- #


def test_skip_matches_titles_case_insensitively():
    cfg = {"skip_playlists": ["Shorts", "POLUBIONE"]}

    assert backlog._skip("Moje SHORTS", cfg) is True
    assert backlog._skip("shorts z AI", cfg) is True
    assert backlog._skip("moje polubione filmy", cfg) is True
    assert backlog._skip("Nauka i rozwój", cfg) is False
    assert backlog._skip(None, cfg) is False


def test_skip_with_empty_config_never_skips():
    assert backlog._skip("Shorts", {}) is False
    assert backlog._skip("Shorts", {"skip_playlists": None}) is False


# --------------------------------------------------------------------------- #
# token refresh / token_for
# --------------------------------------------------------------------------- #


def test_refresh_posts_refresh_grant_and_returns_access_token(monkeypatch):
    calls = []

    def fake_post(url, data=None, timeout=None, **kwargs):
        calls.append({"url": url, "data": data, "timeout": timeout})
        return Resp(200, {"access_token": "ya29.fresh"})

    monkeypatch.setattr(requests, "post", fake_post)

    assert backlog._refresh(_token_json(), "fjkazmierczak") == "ya29.fresh"

    assert calls[0]["url"] == "https://oauth2.googleapis.com/token"
    assert calls[0]["data"] == {
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "grant_type": "refresh_token",
    }
    assert calls[0]["timeout"] == 30


def test_refresh_uses_custom_token_uri_from_the_token_file(monkeypatch):
    calls = []
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, data=None, timeout=None, **kw: (calls.append(url), Resp(200, {"access_token": "t"}))[1],
    )

    backlog._refresh(_token_json(token_uri="https://oauth.example/token"), "praktyki")

    assert calls == ["https://oauth.example/token"]


@pytest.mark.parametrize("code", [400, 401, 403])
def test_refresh_4xx_raises_auth_error_naming_the_account(monkeypatch, code):
    monkeypatch.setattr(
        requests, "post", lambda *a, **kw: Resp(code, text="invalid_grant: Token has been expired or revoked")
    )

    with pytest.raises(backlog.AuthError) as excinfo:
        backlog._refresh(_token_json(), "koalamis6")

    message = str(excinfo.value)
    assert "koalamis6" in message
    assert "invalid_grant" in message
    assert "google_auth_queue.sh" in message, "the operator needs the re-auth hint"


def test_token_for_reads_env_json_without_touching_disk(monkeypatch, tmp_path):
    """Bitwarden hands the token through the environment; no file is needed."""
    monkeypatch.setenv("GOOGLE_FJKAZMIERCZAK_TOKEN_JSON", json.dumps(_token_json()))
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Resp(200, {"access_token": "ya29.env"}))

    assert backlog.token_for({"google_accounts_dir": str(tmp_path / "absent")}, "fjkazmierczak") == "ya29.env"


def test_token_for_reads_the_account_token_file(monkeypatch, tmp_path):
    account_dir = tmp_path / "google-accounts" / "praktyki"
    account_dir.mkdir(parents=True)
    (account_dir / "google_token.json").write_text(json.dumps(_token_json()))
    monkeypatch.delenv("GOOGLE_PRAKTYKI_TOKEN_JSON", raising=False)
    monkeypatch.setattr(requests, "post", lambda *a, **kw: Resp(200, {"access_token": "ya29.file"}))

    assert backlog.token_for({"google_accounts_dir": str(tmp_path / "google-accounts")}, "praktyki") == "ya29.file"


def test_token_for_missing_token_file_raises_auth_error(tmp_path):
    with pytest.raises(backlog.AuthError) as excinfo:
        backlog.token_for({"google_accounts_dir": str(tmp_path / "google-accounts")}, "kazmierczakfilipjan")

    assert "kazmierczakfilipjan" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# sync: per-account isolation, Watch Later, extra playlists, counters
# --------------------------------------------------------------------------- #


def test_sync_one_account_failing_does_not_stop_the_others(monkeypatch, tmp_path):
    """Isolation per account: a dead token on account 1 must not touch account 2."""

    def fake_token_for(cfg, alias):
        if alias == "fjkazmierczak":
            raise backlog.AuthError("refresh failed for fjkazmierczak: invalid_grant")
        return f"tok-{alias}"

    monkeypatch.setattr(backlog, "token_for", fake_token_for)
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [(f"PL-{token}", "Nauka")])
    monkeypatch.setattr(backlog, "api_items", lambda token, pid: [(f"vid-{token}", "Tytuł")])
    _forbid_flat_playlist(monkeypatch)
    q, logs = FakeQueue(), []

    added = backlog.sync(_cfg(tmp_path), q, log=logs.append)

    assert q.ids == ["vid-tok-koalamis6"], "the second account must still be queued"
    assert [c["account"] for c in q.calls] == ["koalamis6"]
    assert added == {"fjkazmierczak": 0, "koalamis6": 1}
    assert any("fjkazmierczak" in line and "invalid_grant" in line for line in logs)


def test_sync_api_failure_on_every_account_still_returns_counters(monkeypatch, tmp_path):
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: (_ for _ in ()).throw(RuntimeError("boom")))
    _forbid_flat_playlist(monkeypatch)
    q, logs = FakeQueue(), []

    added = backlog.sync(_cfg(tmp_path), q, log=logs.append)

    assert added == {"fjkazmierczak": 0, "koalamis6": 0}
    assert q.calls == []
    assert len([line for line in logs if "API playlists: boom" in line]) == 2


def test_sync_skips_watch_later_without_cookies_but_keeps_account_counter(monkeypatch, tmp_path):
    """No cookies file: Watch Later is skipped loudly, never a crash, counter exists."""
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: "tok")
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [])
    _forbid_flat_playlist(monkeypatch)
    q, logs = FakeQueue(), []

    added = backlog.sync(_cfg(tmp_path), q, accounts=["praktyki"], log=logs.append)

    assert added == {"praktyki": 0}
    assert "praktyki" in added, "the per-account counter must exist even when nothing is added"
    assert q.calls == []
    assert any("Watch Later skipped" in line and "praktyki" in line for line in logs)


def test_sync_reads_watch_later_with_the_account_cookies(monkeypatch, tmp_path):
    cookie = tmp_path / "cookies" / "fjkazmierczak.txt"
    cookie.parent.mkdir(parents=True)
    cookie.write_text("# fake netscape cookie file\n")
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: "tok")
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [])
    seen = []

    def fake_flat(url, cookies=None):
        seen.append({"url": url, "cookies": cookies})
        return [{"id": "wl000000001", "title": "Do obejrzenia"}]

    monkeypatch.setattr(fetch, "flat_playlist", fake_flat)
    q, logs = FakeQueue(), []

    added = backlog.sync(_cfg(tmp_path), q, accounts=["fjkazmierczak"], log=logs.append)

    assert seen == [{"url": ":ytwatchlater", "cookies": str(cookie)}]
    assert q.calls[0]["video_id"] == "wl000000001"
    assert q.calls[0]["playlist"] == "Do obejrzenia"
    assert q.calls[0]["priority"] == BACKLOG_PRIORITY + 5
    assert q.calls[0]["url"] == "https://www.youtube.com/watch?v=wl000000001"
    assert added == {"fjkazmierczak": 1}


def test_sync_extra_playlist_uses_configured_priority_and_name(monkeypatch, tmp_path):
    cfg = _cfg(
        tmp_path,
        accounts=[],
        extra_playlists=[
            {
                "account": "koalamis6",
                "name": "Kanał marki",
                "url": "https://www.youtube.com/playlist?list=PLextra",
                "priority": 42,
            }
        ],
    )
    monkeypatch.setattr(fetch, "flat_playlist", lambda url, cookies=None: [{"id": "ex000000001", "title": "extra"}])
    q, logs = FakeQueue(), []

    added = backlog.sync(cfg, q, log=logs.append)

    assert q.calls == [
        {
            "video_id": "ex000000001",
            "url": "https://www.youtube.com/watch?v=ex000000001",
            "title": "extra",
            "account": "koalamis6",
            "playlist": "Kanał marki",
            "priority": 42,
        }
    ]
    assert added == {"koalamis6": 1}


def test_sync_extra_playlist_without_account_falls_back_to_defaults(monkeypatch, tmp_path):
    cfg = _cfg(
        tmp_path,
        accounts=[],
        extra_playlists=[{"url": "https://www.youtube.com/playlist?list=PLanon"}],
    )
    seen = []

    def fake_flat(url, cookies=None):
        seen.append({"url": url, "cookies": cookies})
        return [{"id": "an000000001", "title": "anon"}]

    monkeypatch.setattr(fetch, "flat_playlist", fake_flat)
    q = FakeQueue()

    added = backlog.sync(cfg, q, log=lambda *_: None)

    assert seen == [{"url": "https://www.youtube.com/playlist?list=PLanon", "cookies": None}]
    assert q.calls[0]["playlist"] == "playlista"
    assert q.calls[0]["priority"] == BACKLOG_PRIORITY
    assert q.calls[0]["account"] is None
    assert added == {"extra": 1}


def test_sync_skips_configured_playlists_and_passes_include_liked(monkeypatch, tmp_path):
    seen_liked = []

    def fake_playlists(token, include_liked):
        seen_liked.append(include_liked)
        return [("PL1", "Moje SHORTS"), ("PL2", "Nauka")]

    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: "tok")
    monkeypatch.setattr(backlog, "api_playlists", fake_playlists)
    monkeypatch.setattr(backlog, "api_items", lambda token, pid: [(f"vid-{pid}", "t")])
    _forbid_flat_playlist(monkeypatch)
    q = FakeQueue()

    backlog.sync(
        _cfg(tmp_path, include_liked=True, skip_playlists=["shorts"]),
        q,
        accounts=["fjkazmierczak"],
        log=lambda *_: None,
    )

    assert q.ids == ["vid-PL2"], "a skipped playlist must contribute no videos"
    assert seen_liked == [True], "include_liked from config reaches api_playlists"


def test_sync_counts_only_new_videos_and_sums_per_account(monkeypatch, tmp_path):
    """``q.add`` returning False (already queued) must not inflate the counters."""
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: alias)
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [("PL1", "Nauka"), ("PL2", "Technika")])
    monkeypatch.setattr(
        backlog, "api_items", lambda token, pid: [(f"{token}-{pid}-1", "a"), ("shared00001", "wspólny")]
    )
    _forbid_flat_playlist(monkeypatch)
    q = FakeQueue(new="dedupe")

    added = backlog.sync(_cfg(tmp_path), q, log=lambda *_: None)

    # 2 playlists x (1 unique + 1 shared) per account; the shared video is
    # already queued by the first account, exactly like the real queue's
    # video_id primary key, so it counts once overall.
    assert added == {"fjkazmierczak": 3, "koalamis6": 2}
    assert len(q.calls) == 8
    assert sum(added.values()) == 5


def test_sync_defaults_to_every_account_in_config(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: (seen.append(alias), "tok")[1])
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [])
    _forbid_flat_playlist(monkeypatch)

    added = backlog.sync(_cfg(tmp_path, accounts=["a1", "a2", "a3"]), FakeQueue(), log=lambda *_: None)

    assert seen == ["a1", "a2", "a3"]
    assert list(added) == ["a1", "a2", "a3"]


def test_sync_writes_into_a_real_queue_with_account_playlist_and_priority(monkeypatch, tmp_path):
    """End-to-end against the real SQLite queue: the row the pipeline will pick."""
    monkeypatch.setattr(backlog, "token_for", lambda cfg, alias: "tok")
    monkeypatch.setattr(backlog, "api_playlists", lambda token, liked: [("PL1", "Nauka")])
    monkeypatch.setattr(backlog, "api_items", lambda token, pid: [("abcdefghijk", "Wykład o AI")])
    _forbid_flat_playlist(monkeypatch)
    q = Queue(tmp_path / "queue.db")

    added = backlog.sync(_cfg(tmp_path), q, accounts=["fjkazmierczak"], log=lambda *_: None)

    row = q.db.execute("SELECT * FROM videos WHERE video_id='abcdefghijk'").fetchone()
    assert added == {"fjkazmierczak": 1}
    assert row["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert row["title"] == "Wykład o AI"
    assert row["account"] == "fjkazmierczak"
    assert json.loads(row["playlists"]) == ["Nauka"]
    assert row["priority"] == BACKLOG_PRIORITY
    assert row["status"] == "queued"
    assert q.next()["video_id"] == "abcdefghijk"
