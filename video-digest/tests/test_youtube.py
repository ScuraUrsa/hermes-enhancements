"""Unit tests for the write side of YouTube (ytdigest.youtube).

No network: `requests` is replaced by a recording fake, sockets are blocked
outright, and every GOOGLE_* variable is stripped for the duration of a test,
so a passing run proves the module works with the token handed to it by
backlog.token_for() and never touches Google on its own.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from ytdigest import youtube


class Response:
    def __init__(self, payload: dict | None = None, status: int = 200, text: str | None = None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class FakeRequests:
    """Stands in for the `requests` module; records and answers every call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.handlers: dict[tuple[str, str], object] = {}

    def on(self, method: str, endpoint: str, handler) -> None:
        self.handlers[(method, endpoint)] = handler

    def request(self, method: str, url: str, **kw) -> Response:
        self.calls.append({"method": method, "url": url, **kw})
        endpoint = url.rsplit("/", 1)[-1]
        handler = self.handlers.get((method, endpoint))
        assert handler is not None, f"unexpected request {method} {url}"
        return handler(kw)

    def endpoints(self) -> list[tuple[str, str]]:
        return [(c["method"], c["url"].rsplit("/", 1)[-1]) for c in self.calls]


@pytest.fixture(autouse=True)
def no_network_no_google_env(monkeypatch):
    """DoD: a real HTTP call or a GOOGLE_* credential must never be reachable here."""
    for key in [k for k in os.environ if k.startswith("GOOGLE_")]:
        monkeypatch.delenv(key, raising=False)
    assert not [k for k in os.environ if k.startswith("GOOGLE_")]

    def blocked(*_args, **_kwargs):
        raise AssertionError("unit test tried to open a real network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked, raising=False)
    monkeypatch.setattr(socket, "create_connection", blocked, raising=False)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked, raising=False)
    yield


@pytest.fixture
def fake(monkeypatch):
    mod = FakeRequests()
    monkeypatch.setitem(sys.modules, "requests", mod)
    return mod


@pytest.fixture
def ytcfg(tmp_path):
    """Isolated data_dir: never the operator's ~/.hermes/ytdigest."""
    cfg = {"data_dir": str(tmp_path / "data")}
    assert cfg["data_dir"].startswith(str(tmp_path))
    return cfg


@pytest.fixture
def tokens(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_token_for(cfg, alias):
        seen.append((cfg, alias))
        return "tok"

    monkeypatch.setattr(youtube, "token_for", fake_token_for)
    return seen


def state_file(cfg) -> Path:
    return Path(cfg["data_dir"]) / "youtube_playlist.json"


def test_first_add_creates_private_playlist_and_remembers_it(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response({"items": []}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    assert tokens and tokens[0][1] == "acc"
    assert fake.endpoints() == [
        ("GET", "playlists"),
        ("POST", "playlists"),
        ("POST", "playlistItems"),
    ]
    listing, created, inserted = fake.calls
    assert listing["params"] == {"part": "snippet", "mine": "true", "maxResults": 50}
    assert created["json"]["snippet"]["title"] == "Przetworzone"
    assert created["json"]["status"]["privacyStatus"] == "private"
    assert inserted["json"]["snippet"] == {
        "playlistId": "PLnew",
        "resourceId": {"kind": "youtube#video", "videoId": "aaaaaaaaaaa"},
    }
    for call in fake.calls:
        assert call["headers"] == {"Authorization": "Bearer tok"}
        assert call["timeout"] == 30
        assert call["url"].startswith(youtube.YT + "/")

    saved = json.loads(state_file(ytcfg).read_text(encoding="utf-8"))
    assert saved["ids"] == {"acc/Przetworzone": "PLnew"}
    assert saved["added"] == {"acc/Przetworzone": ["aaaaaaaaaaa"]}


def test_second_add_of_same_video_makes_no_request(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response({"items": []}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))
    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    fake.calls.clear()
    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is False
    assert fake.calls == []
    assert json.loads(state_file(ytcfg).read_text())["added"] == {"acc/Przetworzone": ["aaaaaaaaaaa"]}


def test_new_video_reuses_cached_playlist_id(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response({"items": []}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))
    youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")

    fake.calls.clear()
    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "bbbbbbbbbbb") is True
    assert fake.endpoints() == [("POST", "playlistItems")]
    assert fake.calls[0]["json"]["snippet"]["playlistId"] == "PLnew"
    assert json.loads(state_file(ytcfg).read_text())["added"] == {
        "acc/Przetworzone": ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    }


def test_existing_playlist_on_first_page_is_not_duplicated(ytcfg, fake, tokens):
    fake.on(
        "GET",
        "playlists",
        lambda kw: Response({"items": [{"id": "PLexist", "snippet": {"title": "Przetworzone"}}]}),
    )
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    assert fake.endpoints() == [("GET", "playlists"), ("POST", "playlistItems")]
    assert fake.calls[1]["json"]["snippet"]["playlistId"] == "PLexist"
    assert "pageToken" not in fake.calls[0]["params"]


def test_existing_playlist_found_on_later_page(ytcfg, fake, tokens):
    pages = {
        None: {"items": [{"id": "PLother", "snippet": {"title": "Coś innego"}}], "nextPageToken": "P2"},
        "P2": {"items": [{"id": "PLexist", "snippet": {"title": "Przetworzone"}}]},
    }
    fake.on("GET", "playlists", lambda kw: Response(pages[kw["params"].get("pageToken")]))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    assert fake.endpoints() == [
        ("GET", "playlists"),
        ("GET", "playlists"),
        ("POST", "playlistItems"),
    ]
    assert "pageToken" not in fake.calls[0]["params"]
    assert fake.calls[1]["params"]["pageToken"] == "P2"
    assert fake.calls[2]["json"]["snippet"]["playlistId"] == "PLexist"


def test_match_on_a_page_that_advertises_more_pages_stops_there(ytcfg, fake, tokens):
    # The playlist is on this page, but the API also offers a nextPageToken:
    # the loop must fall out through its condition, not fetch page two.
    pages = {
        None: {
            "items": [{"id": "PLexist", "snippet": {"title": "Przetworzone"}}],
            "nextPageToken": "P2",
        },
    }
    fake.on("GET", "playlists", lambda kw: Response(pages[kw["params"].get("pageToken")]))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    assert fake.endpoints() == [("GET", "playlists"), ("POST", "playlistItems")]
    assert fake.calls[1]["json"]["snippet"]["playlistId"] == "PLexist"


def test_last_page_without_next_page_token_stops_looking(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response({"items": [], "nextPageToken": ""}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")

    assert fake.endpoints().count(("GET", "playlists")) == 1


def test_cached_playlist_id_skips_http_entirely(ytcfg, fake, tokens):
    path = state_file(ytcfg)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"ids": {"acc/Przetworzone": "PLcached"}}), encoding="utf-8")

    assert youtube.playlist_id(ytcfg, "acc", "Przetworzone", "tok") == "PLcached"
    assert fake.calls == []


def test_corrupt_state_file_is_ignored_and_rewritten(ytcfg, fake, tokens):
    path = state_file(ytcfg)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    fake.on("GET", "playlists", lambda kw: Response({"items": []}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    assert youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa") is True

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["ids"] == {"acc/Przetworzone": "PLnew"}
    assert saved["added"] == {"acc/Przetworzone": ["aaaaaaaaaaa"]}


def test_unreadable_state_path_is_ignored(ytcfg):
    path = state_file(ytcfg)
    path.mkdir(parents=True)  # a directory where the file should be -> OSError

    returned_path, state = youtube._state(ytcfg)

    assert returned_path == path
    assert state == {}


def test_missing_data_dir_is_created(ytcfg, fake, tokens):
    assert not Path(ytcfg["data_dir"]).exists()
    fake.on("GET", "playlists", lambda kw: Response({"items": []}))
    fake.on("POST", "playlists", lambda kw: Response({"id": "PLnew"}))
    fake.on("POST", "playlistItems", lambda kw: Response({"id": "item1"}))

    youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")

    assert state_file(ytcfg).is_file()


def test_insufficient_scope_is_a_permission_error(ytcfg, fake, tokens):
    body = '{"error":{"code":403,"errors":[{"reason":"insufficientPermissions"}]}}'
    fake.on("GET", "playlists", lambda kw: Response(status=403, text=body))

    with pytest.raises(PermissionError, match="read-only YouTube access"):
        youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")

    assert fake.endpoints() == [("GET", "playlists")]
    assert not state_file(ytcfg).exists()


def test_other_http_errors_carry_status_and_short_body(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response(status=500, text="x" * 500))

    with pytest.raises(RuntimeError) as err:
        youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")

    message = str(err.value)
    assert "playlists -> 500" in message
    assert message.endswith("x" * 200)
    assert len(message) < 260  # body truncated, not echoed whole
    assert fake.endpoints() == [("GET", "playlists")]  # no hidden retry


def test_403_without_insufficient_scope_is_a_normal_error(ytcfg, fake, tokens):
    fake.on("GET", "playlists", lambda kw: Response(status=403, text="quota exceeded"))

    with pytest.raises(RuntimeError, match="playlists -> 403: quota exceeded"):
        youtube.add_to_playlist(ytcfg, "acc", "Przetworzone", "aaaaaaaaaaa")
