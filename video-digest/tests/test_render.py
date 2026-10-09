from ytdigest import render

BUNDLE = {"video_id": "abcdefghijk", "url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "T", "channel": "C",
          "duration_sec": 3700, "published_at": "2026-01-01",
          "transcript": {"source": "youtube_manual", "segments": [{"start": i * 10.0, "end": i * 10.0 + 9, "text": "x" * 50} for i in range(30)]},
          "frames": [{"t": 65, "caption": "slajd", "path": None}]}
REPORT = {"one_line": "Jedno zdanie", "about": "A", "text_summary": "B\n\nC", "visual_summary": "D", "key_points": ["k"],
          "life_applications": ["l"], "action_items": ["zrób"], "tags": ["t1"], "video_type": "lecture_slides",
          "chapters": [{"t": 3661, "title": "koniec"}], "notable_quotes": [{"t": 5, "quote": "q"}],
          "related_suggestions": ["r"], "confidence": 0.9}
RUN = {"models": ["gemini-url:gemini-flash-lite-latest"], "cost_usd": 0.0123}


def test_mmss_and_timestamp_links():
    assert render.mmss(3661) == "1:01:01" and render.mmss(65) == "1:05"
    assert render.at(BUNDLE["url"], 65).endswith("&t=65s")


def test_notion_blocks_follow_template_order():
    blocks = render.notion_blocks(BUNDLE, REPORT, RUN, "pl")
    heads = [b[b["type"]]["rich_text"][0]["text"]["content"] for b in blocks if b["type"] == "heading_2"]
    assert heads == ["O czym jest ten film", "Co zostało powiedziane", "Co było widać", "Najważniejsze punkty",
                     "Jak możesz to wykorzystać w swoim życiu", "Propozycje działań", "Rozdziały", "Cytaty",
                     "Powiązane tematy do sprawdzenia", "Tagi i metadane", "Film", "Pełny transkrypt"]
    assert blocks[0]["type"] == "callout"
    assert any(b["type"] == "to_do" for b in blocks)
    assert any(b["type"] == "video" for b in blocks)
    assert blocks[-1]["heading_2"]["is_toggleable"]
    assert len(blocks) <= 100


def test_long_text_is_chunked_under_notion_limit():
    rich = render.rt("y" * 5000)
    assert len(rich) == 3 and all(len(r["text"]["content"]) <= 1900 for r in rich)


def test_transcript_paragraphs_per_minute_with_links():
    blocks = render.transcript_blocks(BUNDLE, "pl")
    assert len(blocks) == 5
    assert blocks[1]["paragraph"]["rich_text"][0]["text"]["link"]["url"].endswith("t=60s")


def test_artistic_page_is_minimal():
    blocks = render.notion_blocks(BUNDLE, {**REPORT, "is_artistic": True, "about": "piosenka"}, RUN, "pl")
    assert blocks[0]["type"] == "callout" and len(blocks) == 3


def test_markdown_template_en():
    md = render.markdown(BUNDLE, REPORT, RUN, "en", "https://notion.so/x")
    for h in ("What this video is about", "How you can use this in your life", "- [ ] zrób", "Notion: https://notion.so/x"):
        assert h in md
