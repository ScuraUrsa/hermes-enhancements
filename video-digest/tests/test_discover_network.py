"""Hermetic contract tests for the network layer of ytdigest.discover.

Everything here talks to a fake YouTube Data API: `requests.get` is replaced with
a router that dispatches on the URL tail ("channels", "playlistItems", "videos",
"subscriptions") and hands back canned `Resp` objects. The autouse fixture below
additionally forbids real sockets, real sleeps and any un-stubbed HTTP call, so a
test that tries to reach the network fails loudly instead of hanging.

What is pinned here is the behaviour that decides which videos reach the archive
(C4): pagination, the cutoff break, 404/4xx handling, date precedence, batching
and the shape of the TSV + summary.
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone

import pytest

from ytdigest import discover

CUTOFF = datetime(2026, 10, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# hermeticity
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """No sockets, no sleeps, no unstubbed HTTP: every test here is offline."""

    def forbidden(*args, **kwargs):  # pragma: no cover - only on a broken test
        raise AssertionError("network access attempted from a hermetic test")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(time, "sleep", forbidden)
    monkeypatch.setattr("requests.get", forbidden)


# --------------------------------------------------------------------------
# fake API
# --------------------------------------------------------------------------
class Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else json.dumps(self._payload)

    def json(self):
        return self._payload


class Call:
    def __init__(self, url, params, headers, timeout):
        self.url, self.params, self.headers, self.timeout = url, params, headers, timeout

    @property
    def name(self):
        return self.url.rsplit("/", 1)[-1]

    def ids(self):
        return self.params.get("id", "").split(",")


class FakeApi:
    """Route -> list of responses; the last response repeats (page after page)."""

    # A route that keeps being asked after this many calls is a non-terminating
    # pagination loop (e.g. the cutoff break was dropped): fail, do not hang.
    CALL_LIMIT = 60

    def __init__(self, **routes):
        self.routes = {name: (r if isinstance(r, list) else [r]) for name, r in routes.items()}
        self.calls = []
        self._per_route = {}

    def __call__(self, url, params=None, headers=None, timeout=None):
        call = Call(url, dict(params or {}), dict(headers or {}), timeout)
        self.calls.append(call)
        assert call.name in self.routes, f"unexpected API call: {url} ({call.params})"
        self._per_route[call.name] = self._per_route.get(call.name, 0) + 1
        assert self._per_route[call.name] <= self.CALL_LIMIT, (
            f"pagination did not terminate: {self._per_route[call.name]} calls to {call.name}")
        queue = self.routes[call.name]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def of(self, name):
        return [c for c in self.calls if c.name == name]


def install(monkeypatch, **routes):
    api = FakeApi(**routes)
    monkeypatch.setattr("requests.get", api)
    return api


def channels_page(*rows):
    """rows: (channel_id, uploads_playlist_or_None, title)"""
    items = []
    for cid, uploads, title in rows:
        items.append({
            "id": cid,
            "contentDetails": {"relatedPlaylists": {"uploads": uploads} if uploads else {}},
            "snippet": {"title": title},
        })
    return Resp(200, {"items": items})


def uploads_item(video_id, video_published=None, snippet_published=None, title=None):
    snippet = {"title": title if title is not None else f"title {video_id}"}
    details = {"videoId": video_id}
    if video_published is not None:
        details["videoPublishedAt"] = video_published
    if snippet_published is not None:
        snippet["publishedAt"] = snippet_published
    return {"contentDetails": details, "snippet": snippet}


def uploads_page(*items, next_page=None):
    body = {"items": list(items)}
    if next_page:
        body["nextPageToken"] = next_page
    return Resp(200, body)


# --------------------------------------------------------------------------
# 1. _get: bearer auth, timeout, error translation
# --------------------------------------------------------------------------
def test_get_sends_bearer_header_and_thirty_second_timeout(monkeypatch):
    api = install(monkeypatch, videos=Resp(200, {"items": [{"id": "v1"}]}))

    body = discover._get("tok-123", "videos", {"part": "snippet", "id": "v1"})

    assert body == {"items": [{"id": "v1"}]}
    call = api.calls[0]
    assert call.url.endswith("/youtube/v3/videos")
    assert call.params == {"part": "snippet", "id": "v1"}
    assert call.headers["Authorization"] == "Bearer tok-123"
    assert call.timeout == 30


def test_get_raises_runtime_error_with_status_code_and_body(monkeypatch):
    install(monkeypatch, videos=Resp(404, text="playlist not found"))

    with pytest.raises(RuntimeError) as err:
        discover._get("tok", "videos", {"id": "v1"})

    assert str(err.value) == "videos -> 404: playlist not found"


def test_get_truncates_the_api_error_body_to_two_hundred_chars(monkeypatch):
    long_text = "E" * 300
    install(monkeypatch, videos=Resp(500, text=long_text))

    with pytest.raises(RuntimeError) as err:
        discover._get("tok", "videos", {"id": "v1"})

    message = str(err.value)
    assert message == f"videos -> 500: {'E' * 200}"
    assert "E" * 201 not in message


# --------------------------------------------------------------------------
# 2. _batches: groups of 50
# --------------------------------------------------------------------------
def test_batches_splits_ids_into_fifties_with_a_short_tail():
    assert [len(b) for b in discover._batches(list(range(120)))] == [50, 50, 20]
    assert [len(b) for b in discover._batches(list(range(50)))] == [50]
    assert [len(b) for b in discover._batches([1, 2, 3])] == [3]


def test_batches_yields_nothing_for_an_empty_list():
    assert list(discover._batches([])) == []


# --------------------------------------------------------------------------
# 3. video_channels: dedupe, batching, missing titles
# --------------------------------------------------------------------------
def test_video_channels_dedupes_ids_before_batching_and_merges_pages(monkeypatch):
    ids = [f"vid{i:08d}" for i in range(60)] + ["vid00000000"]  # 60 unique, one repeat
    api = install(monkeypatch, videos=[
        Resp(200, {"items": [
            {"snippet": {"channelId": "C1", "channelTitle": "Alpha"}},
            {"snippet": {"channelId": "C2", "channelTitle": "Beta"}},
        ]}),
        Resp(200, {"items": [{"snippet": {"channelId": "C3", "channelTitle": "Gamma"}}]}),
    ])

    out = discover.video_channels("tok", ids)

    assert out == {"C1": "Alpha", "C2": "Beta", "C3": "Gamma"}
    calls = api.of("videos")
    assert [len(c.ids()) for c in calls] == [50, 10]  # dedupe first, then batches of 50
    assert len(set(calls[0].ids())) == 50
    assert "vid00000000" not in calls[1].ids()  # the duplicate is gone, not re-sent


def test_video_channels_returns_blank_title_when_channel_title_is_missing(monkeypatch):
    install(monkeypatch, videos=Resp(200, {"items": [{"snippet": {"channelId": "C1"}}]}))

    assert discover.video_channels("tok", ["vid00000001"]) == {"C1": ""}


# --------------------------------------------------------------------------
# 4. durations: video_id -> seconds
# --------------------------------------------------------------------------
def test_durations_maps_video_id_to_seconds_and_omits_absent_ids(monkeypatch):
    install(monkeypatch, videos=Resp(200, {"items": [
        {"id": "v1", "contentDetails": {"duration": "PT1M"}},
        {"id": "v2", "contentDetails": {"duration": "PT1H"}},
        {"id": "v3", "contentDetails": {}},
    ]}))

    secs = discover.durations("tok", ["v1", "v2", "v9"])

    assert secs == {"v1": 60, "v2": 3600, "v3": 0}
    assert "v9" not in secs  # no API entry, no key


# --------------------------------------------------------------------------
# 5. _seconds: ISO 8601, garbage -> 0
# --------------------------------------------------------------------------
def test_seconds_parses_iso_durations_and_falls_back_to_zero():
    assert discover._seconds("PT1H2M3S") == 3723
    assert discover._seconds("P1DT1S") == 86401
    assert discover._seconds("PT59S") == 59
    assert discover._seconds("P2DT3H4M5S") == 183845
    assert discover._seconds("") == 0
    # Garbage from the API (null duration) must fall back to 0, not crash.
    assert discover._seconds(None) == 0  # type: ignore[arg-type]
    assert discover._seconds("not-a-duration") == 0


# --------------------------------------------------------------------------
# 6. uploads_since: the whole loop
# --------------------------------------------------------------------------
def test_uploads_since_pages_until_cutoff_and_stops_on_first_old_item(monkeypatch):
    api = install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "Chan One")),
        playlistItems=uploads_page(
            uploads_item("new00000001", video_published="2026-10-20T10:00:00Z"),
            uploads_item("old00000001", video_published="2020-01-01T00:00:00Z"),
            next_page="P2",
        ),
    )

    out = discover.uploads_since("tok", ["C1"], CUTOFF, log=lambda m: None)

    assert [v["video_id"] for v in out] == ["new00000001"]
    # uploads are newest-first: the first too-old item ends pagination for the channel
    assert len(api.of("playlistItems")) == 1
    assert out[0] == {"video_id": "new00000001", "published": "2026-10-20",
                      "channel_id": "C1", "channel": "Chan One", "title": "title new00000001"}


def test_uploads_since_treats_a_404_channel_as_empty_and_moves_on(monkeypatch):
    api = install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "No Uploads"), ("C2", "UU2", "Has Uploads")),
        playlistItems=[
            Resp(404, text="channel without public uploads"),
            uploads_page(uploads_item("vid00000001", video_published="2026-10-20T10:00:00Z")),
        ],
    )

    out = discover.uploads_since("tok", ["C1", "C2"], CUTOFF, log=lambda m: None)

    assert [v["video_id"] for v in out] == ["vid00000001"]  # 404 is silent, loop continues
    assert out[0]["channel"] == "Has Uploads"


def test_uploads_since_raises_with_the_channel_title_on_api_error(monkeypatch):
    install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "Chan One")),
        playlistItems=Resp(400, text="quota exceeded"),
    )

    with pytest.raises(RuntimeError) as err:
        discover.uploads_since("tok", ["C1"], CUTOFF, log=lambda m: None)

    assert str(err.value) == "uploads of Chan One -> 400: quota exceeded"


def test_uploads_since_reads_videoPublishedAt_and_falls_back_to_snippet_publishedAt(monkeypatch):
    install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "Chan One")),
        playlistItems=uploads_page(
            # videoPublishedAt wins over snippet.publishedAt
            uploads_item("vid00000001", video_published="2026-10-20T10:00:00Z",
                         snippet_published="2020-01-01T00:00:00Z"),
            # playlist-add date is the fallback when the video date is absent
            uploads_item("vid00000002", snippet_published="2026-10-21T10:00:00Z"),
        ),
    )

    out = discover.uploads_since("tok", ["C1"], CUTOFF, log=lambda m: None)

    assert [(v["video_id"], v["published"]) for v in out] == [
        ("vid00000001", "2026-10-20"), ("vid00000002", "2026-10-21")]


def test_uploads_since_skips_items_without_a_published_date_and_keeps_paging(monkeypatch):
    api = install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "Chan One")),
        playlistItems=[
            uploads_page(
                uploads_item("vid00000001", video_published="2026-10-20T10:00:00Z"),
                uploads_item("nodate00001"),  # neither date: skipped, and NOT counted as old
                next_page="P2",
            ),
            uploads_page(uploads_item("vid00000002", video_published="2026-10-19T10:00:00Z")),
        ],
    )

    out = discover.uploads_since("tok", ["C1"], CUTOFF, log=lambda m: None)

    assert [v["video_id"] for v in out] == ["vid00000001", "vid00000002"]
    assert len(api.of("playlistItems")) == 2  # a date-less item must not break pagination


def test_uploads_since_follows_next_page_token_with_fifty_results_per_page(monkeypatch):
    api = install(
        monkeypatch,
        channels=channels_page(("C1", "UU1", "Chan One")),
        playlistItems=[
            uploads_page(uploads_item("vid00000001", video_published="2026-10-20T10:00:00Z"), next_page="P2"),
            uploads_page(uploads_item("vid00000002", video_published="2026-10-19T10:00:00Z"), next_page="P3"),
            uploads_page(uploads_item("vid00000003", video_published="2026-10-18T10:00:00Z")),
        ],
    )

    out = discover.uploads_since("tok", ["C1"], CUTOFF, log=lambda m: None)

    assert [v["video_id"] for v in out] == ["vid00000001", "vid00000002", "vid00000003"]
    pages = api.of("playlistItems")
    assert [p.params.get("pageToken") for p in pages] == [None, "P2", "P3"]
    assert {p.params["maxResults"] for p in pages} == {50}
    assert {p.params["playlistId"] for p in pages} == {"UU1"}
    assert {p.headers["Authorization"] for p in pages} == {"Bearer tok"}


def test_uploads_since_skips_channel_without_an_uploads_playlist(monkeypatch):
    api = install(
        monkeypatch,
        channels=channels_page(("C1", None, "No Playlist"), ("C2", "UU2", "Chan Two")),
        playlistItems=uploads_page(uploads_item("vid00000002", video_published="2026-10-20T10:00:00Z")),
    )

    out = discover.uploads_since("tok", ["C1", "C2"], CUTOFF, log=lambda m: None)

    assert [v["video_id"] for v in out] == ["vid00000002"]
    assert len(api.of("playlistItems")) == 1  # the playlist-less channel is never read


def test_uploads_since_logs_progress_every_twenty_five_channels(monkeypatch):
    channels = [(f"C{i:02d}", f"UU{i:02d}", f"Chan {i:02d}") for i in range(25)]
    install(
        monkeypatch,
        channels=channels_page(*channels),
        playlistItems=uploads_page(),
    )
    logs = []

    discover.uploads_since("tok", [c[0] for c in channels], CUTOFF, log=logs.append)

    assert logs == ["  25/25 channels read, 0 videos so far"]


# --------------------------------------------------------------------------
# 7. run(): id files, min_seconds, max_per_channel, sorting, TSV, summary
# --------------------------------------------------------------------------
def _wire(monkeypatch, *, api_saved=(), subs=None, channel_map=None, videos=(), secs=None):
    monkeypatch.setattr(discover, "token_for", lambda c, a: "tok")
    monkeypatch.setattr(discover, "api_playlists", lambda t, liked: [("PL1", "Playlist")] if api_saved else [])
    monkeypatch.setattr(discover, "_paged", lambda t, path, p: [{"contentDetails": {"videoId": v}} for v in api_saved])
    monkeypatch.setattr(discover, "video_channels", lambda t, ids: dict(channel_map if channel_map is not None else {}))
    monkeypatch.setattr(discover, "subscriptions", lambda t: dict(subs or {}))
    monkeypatch.setattr(discover, "uploads_since", lambda t, cids, cutoff, log=print: [dict(v) for v in videos])
    monkeypatch.setattr(discover, "durations", lambda t, ids: dict(secs or {}))


def row(video_id, published, channel_id="C1", channel="Chan", title=None):
    return {"video_id": video_id, "published": published, "channel_id": channel_id,
            "channel": channel, "title": title if title is not None else f"t {video_id}"}


def test_run_reads_id_files_skipping_blanks_comments_and_unparsable_entries(cfg, monkeypatch, tmp_path):
    ids = tmp_path / "watch-later.txt"
    ids.write_text("\n".join([
        "",
        "   ",
        "# a comment",
        "   # an indented comment",
        "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "https://youtu.be/bbbbbbbbbbb",
        "ddddddddddd   # bare id with trailing junk",
        "not-a-valid-id",
        "",
    ]), encoding="utf-8")
    _wire(monkeypatch, channel_map={"C1": "Chan"})
    logs = []

    discover.run(cfg, "acct", 7, tmp_path / "d.tsv", id_files=[str(ids)], log=logs.append)

    assert "saved videos: 3" in logs  # three parsible ids, the rest skipped


def test_run_drops_videos_shorter_than_min_seconds(cfg, monkeypatch, tmp_path):
    _wire(monkeypatch, channel_map={"C1": "Chan"},
          videos=[row("vid00000001", "2026-10-20"), row("vid00000002", "2026-10-19")],
          secs={"vid00000001": 30, "vid00000002": 900})

    res = discover.run(cfg, "acct", 7, tmp_path / "d.tsv", min_seconds=120, log=lambda m: None)

    assert [r["video_id"] for r in res["rows"]] == ["vid00000002"]


def test_run_caps_videos_per_channel(cfg, monkeypatch, tmp_path):
    _wire(monkeypatch, channel_map={"C1": "Bulk", "C2": "Quiet"},
          videos=[row("bulk0000001", "2026-10-20", "C1", "Bulk"),
                  row("bulk0000002", "2026-10-19", "C1", "Bulk"),
                  row("bulk0000003", "2026-10-18", "C1", "Bulk"),
                  row("quiet000001", "2026-10-17", "C2", "Quiet")],
          secs={"bulk0000001": 600, "bulk0000002": 600, "bulk0000003": 600, "quiet000001": 600})

    res = discover.run(cfg, "acct", 7, tmp_path / "d.tsv", max_per_channel=1, log=lambda m: None)

    kept = [r["video_id"] for r in res["rows"]]
    assert kept == ["bulk0000001", "quiet000001"]  # newest of each channel survives


def test_run_sorts_newest_first_and_writes_sanitized_tsv(cfg, monkeypatch, tmp_path):
    _wire(monkeypatch, channel_map={"C1": "Chan"},
          videos=[row("vid00000001", "2026-10-10", title="first\twith tab"),
                  row("vid00000002", "2026-10-20", title="newest")],
          secs={"vid00000001": 60, "vid00000002": 120})
    out = tmp_path / "sub" / "d.tsv"

    res = discover.run(cfg, "acct", 7, out, log=lambda m: None)

    assert [r["video_id"] for r in res["rows"]] == ["vid00000002", "vid00000001"]
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "video_id\tpublished\tseconds\tchannel\ttitle\tsource"
    assert lines[1] == "vid00000002\t2026-10-20\t120\tChan\tnewest\tplaylisty"
    assert lines[2] == "vid00000001\t2026-10-10\t60\tChan\tfirst with tab\tplaylisty"  # \t -> space
    assert len(lines) == 3


def test_run_summary_counts_shorts_hours_and_already_saved(cfg, monkeypatch, tmp_path):
    _wire(monkeypatch, api_saved=["vid00000001", "not-returned-anywhere"],
          channel_map={"C1": "Chan"},
          videos=[row("vid00000001", "2026-10-20"), row("vid00000002", "2026-10-19")],
          secs={"vid00000001": 30, "vid00000002": 7200})

    res = discover.run(cfg, "acct", 7, tmp_path / "d.tsv", log=lambda m: None)

    summary = res["summary"]
    assert summary["videos"] == 2
    assert summary["shorts"] == 1
    assert summary["hours"] == 2.0
    assert summary["already_saved"] == 1  # intersection, not the size of `saved`
    assert summary["channels"] == 1
    assert summary["file"] == str(tmp_path / "d.tsv")
