from ytdigest import render

DESC = """W tym filmie buduję agenta.

GitHub repo: https://github.com/example/agent
Mój kurs:
https://kurs.example.com/ai?ref=yt.
Twitter - https://x.com/example
https://github.com/example/agent"""


def test_description_links():
    links = render.description_links(DESC)
    assert links == [("GitHub repo", "https://github.com/example/agent"),
                     ("Mój kurs", "https://kurs.example.com/ai?ref=yt"),
                     ("Twitter", "https://x.com/example")]


def test_page_and_markdown_show_description():
    bundle = {"url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "T", "description": DESC,
              "transcript": {"source": "youtube_manual", "segments": []}, "frames": []}
    rep = {"one_line": "x", "video_type": "tutorial_screen", "tags": []}
    blocks = render.notion_blocks(bundle, rep, {}, "pl")
    heads = [b["heading_2"]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "heading_2"]
    assert "Linki i opis od autora" in heads
    assert any(b["type"] == "toggle" for b in blocks)
    md = render.markdown(bundle, rep, {}, "pl")
    assert "GitHub repo: https://github.com/example/agent" in md and "W tym filmie buduję agenta." in md


def test_rerender_adds_description(cfg, tmp_path):
    import json
    from types import SimpleNamespace

    from ytdigest import cli

    d = tmp_path / "data" / "bundles" / "abcdefghijk"
    d.mkdir(parents=True)
    bundle = {"video_id": "abcdefghijk", "url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "T",
              "description": DESC, "transcript": {"source": "none", "segments": []}, "frames": []}
    (d / "bundle.json").write_text(json.dumps(bundle))
    (d / "report.json").write_text(json.dumps({"report": {"one_line": "x", "tags": []}, "run": {}}))
    (d / "report.md").write_text("# old")
    a = SimpleNamespace(data_dir=str(tmp_path / "data"), video=None, notion=False, refetch=False)
    assert cli.cmd_rerender(cfg, a) == 0
    assert "https://github.com/example/agent" in (d / "report.md").read_text()
