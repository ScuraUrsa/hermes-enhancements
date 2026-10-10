import pytest

from ytdigest import fetch

VTT_AUTO = """WEBVTT
Kind: captions
Language: pl

00:00:00.000 --> 00:00:02.000 align:start position:0%
dzień<00:00:00.500><c> dobry</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
dzień dobry

00:00:02.010 --> 00:00:04.000 align:start position:0%
dzień dobry
dzisiaj<00:00:02.500><c> o</c><00:00:03.000><c> AI</c>

00:00:04.000 --> 00:00:06.000
dzisiaj o AI
&amp; robotach
"""


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=WL",
    "https://youtu.be/dQw4w9WgXcQ?t=10",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://m.youtube.com/live/dQw4w9WgXcQ",
    "dQw4w9WgXcQ",
])
def test_video_id(url):
    assert fetch.video_id(url) == "dQw4w9WgXcQ"


def test_video_id_rejects_other_links():
    with pytest.raises(ValueError):
        fetch.video_id("https://example.com/watch")


def test_parse_vtt_collapses_rolling_auto_captions():
    segs = fetch.parse_vtt(VTT_AUTO)
    text = " ".join(s["text"] for s in segs)
    assert text == "dzień dobry dzisiaj o AI & robotach"
    assert segs[0]["start"] == 0.0 and segs[-1]["end"] == 6.0


def test_pick_caption_prefers_original_language_manual():
    info = {"language": "pl", "subtitles": {"en": [{}], "pl": [{}]}, "automatic_captions": {}}
    assert fetch.pick_caption(info, "manual", ["en"]) == ("pl", "manual")


def test_pick_caption_auto_only_original_track():
    info = {"language": "pl", "subtitles": {}, "automatic_captions": {"en": [{}], "pl-orig": [{}], "pl": [{}]}}
    assert fetch.pick_caption(info, "auto", ["en"]) == ("pl-orig", "auto")
    info2 = {"language": "pl", "automatic_captions": {"en": [{}], "de": [{}]}}
    assert fetch.pick_caption(info2, "auto", ["en"]) is None


def test_download_retries_on_403(monkeypatch, tmp_path):
    from ytdigest import fetch as F

    calls = {"n": 0}

    class Y:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("ERROR: unable to download video data: HTTP Error 403: Forbidden")
            (tmp_path / "video.mp4").write_bytes(b"x")

    monkeypatch.setattr(F, "_ydl", lambda opts, cookies: Y())
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert F.download_video("u", tmp_path).name == "video.mp4" and calls["n"] == 3


def test_polish_video_prefers_polish_track_even_if_metadata_says_en():
    from ytdigest import fetch as F
    info = {"title": "Jak używać NotebookLM do nauki – poradnik krok po kroku", "description": "W tym filmie pokazuję, jak to działa.",
            "language": "en", "subtitles": {"en": [{}], "pl": [{}]}, "automatic_captions": {}}
    assert F.pick_caption(info, "manual", ["pl", "en"]) == ("pl", "manual")
    assert F.guess_language({"title": "How to build an MCP server", "description": "In this video"}) is None
