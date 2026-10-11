import json
import shutil
from pathlib import Path

import pytest

from sitedigest import config as sconfig
from sitedigest import course, crawl, docs, lesson, media, notion_out, session

from fake_course_site import Site, docx_bytes, pdf_bytes


@pytest.fixture
def scfg(cfg, tmp_path):
    cfg["site"] = {**sconfig.DEFAULTS, "root": str(tmp_path / "sites"), "delay_sec": [0, 0], "page_timeout_sec": 15}
    Path(cfg["site"]["root"]).mkdir(parents=True)
    return cfg


# -- pure helpers --------------------------------------------------------------------

def test_cookies_round_trip(scfg, tmp_path):
    txt = "# Netscape HTTP Cookie File\n#HttpOnly_.kurs.pl\tTRUE\t/\tTRUE\t1999999999\tsid\tabc\nkurs.pl\tFALSE\t/\tFALSE\t0\tlang\tpl\n"
    f = tmp_path / "c.txt"
    f.write_text(txt)
    assert session.import_cookies(scfg, "kurs", f) == 2
    state = session.load_state(scfg, "kurs")
    sid = next(c for c in state["cookies"] if c["name"] == "sid")
    assert sid["httpOnly"] and sid["secure"] and sid["domain"] == ".kurs.pl"
    assert oct(session.state_path(scfg, "kurs").stat().st_mode)[-3:] == "600"
    back = session.parse_netscape(session.cookies_path(scfg, "kurs").read_text())
    assert {c["name"] for c in back} == {"sid", "lang"}


def test_site_name_and_logged_out():
    assert session.site_name("https://academy.example.com/courses/x") == "example-com"
    assert session.site_name("https://kurs.pl/") == "kurs-pl"
    assert session.looks_logged_out("https://x.com/courses/1", "https://x.com/users/sign_in")
    assert not session.looks_logged_out("https://x.com/login", "https://x.com/login")
    assert not session.looks_logged_out("https://x.com/courses/1", "https://x.com/courses/1/lessons/2")


def test_media_classify_and_pick():
    assert media.classify("https://player.vimeo.com/video/1?h=2") == "video"
    assert media.classify("https://fast.wistia.net/embed/iframe/abc") == "video"
    assert media.classify("https://cdn.x.com/a/master.m3u8") == "video"
    assert media.classify("https://cdn.x.com/a/seg-12.ts") is None
    assert media.classify("https://x.com/files/handout.pdf?sig=1") == "doc"
    assert media.classify("https://x.com/img/a.png") == "image"
    assert media.classify("https://x.com/courses/1") is None
    assert media.classify("https://docs.google.com/presentation/d/AbC_1/edit#slide=1") == "doc"
    assert media.download_url("https://docs.google.com/presentation/d/AbC_1/edit") == "https://docs.google.com/presentation/d/AbC_1/export/pptx"
    assert media.download_url("https://drive.google.com/file/d/XyZ/view?usp=sharing") == "https://drive.google.com/uc?export=download&id=XyZ"
    assert media.download_url("https://www.dropbox.com/s/a/b.pdf?dl=0").endswith("dl=1")
    found = {"iframes": ["https://player.vimeo.com/video/9"], "videos": ["blob:https://x"], "embeds": [],
             "network": ["https://cdn.x.com/master.m3u8"]}
    assert media.page_videos(found, "https://x.com/l") == ["https://player.vimeo.com/video/9"]
    only_net = {"iframes": [], "videos": [], "embeds": [],
                "network": ["https://cdn.x.com/v/master.m3u8", "https://cdn.x.com/v/720p_1.m3u8", "https://cdn.x.com/v/seg-1.ts"]}
    assert media.page_videos(only_net, "https://x.com/l") == ["https://cdn.x.com/v/master.m3u8"]


def test_scope_never_opens_dangerous_links():
    s = crawl.Scope("https://k.pl/courses/demo")
    assert s("https://k.pl/courses/demo/lessons/1")
    for bad in ["https://k.pl/logout", "https://k.pl/cart", "https://k.pl/courses/demo/lessons/3/mark_complete",
                "https://k.pl/users/sign_out", "https://k.pl/files/a.pdf", "https://other.pl/courses/demo", "mailto:a@b.pl"]:
        assert not s(bad), bad
    assert crawl.normalise("https://K.pl/a//b/?utm_source=x&b=2&a=1#top") == "https://k.pl/a/b?a=1&b=2"


def test_docs_text(tmp_path):
    d = tmp_path / "a.docx"
    d.write_bytes(docx_bytes("Krok 1: wypisz tematy."))
    assert "Krok 1" in docs.text_of(d) and "Krok 2" in docs.text_of(d)
    p = tmp_path / "h.pdf"
    p.write_bytes(pdf_bytes("Handout: trzy zasady notatek"))
    text = docs.text_of(p)
    if shutil.which("pdftotext") or _has("pypdf"):
        assert "trzy zasady" in text
    assert docs.needs_pictures(p, "") and not docs.needs_pictures(d, "")


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def test_notion_toggle_splits_at_100():
    kids = [notion_out.block("paragraph", notion_out.rt(str(i))) for i in range(250)]
    t = notion_out.toggle("Transkrypcja", kids)
    assert [len(x["toggle"]["children"]) for x in t] == [100, 100, 50]


# -- end to end on a fake course site (real Chromium) ---------------------------------

class FakeClient:
    """Stands in for llm.Client: answers vision and report calls, records them."""

    def __init__(self, *a, **k):
        from ytdigest.llm import Usage

        self.usage = Usage()
        self.calls = []

    def json(self, ref, system, user, images=None, max_tokens=4000):
        self.calls.append((ref, user, images))
        self.usage.add(ref, 100, 50, 0.001)
        if images:
            if "frames" in user or "Image 1 at" in user:
                return {"frames": [{"n": i + 1, "caption": f"slajd {i + 1}", "on_screen_text": "", "adds_information": True}
                                   for i in range(len(images))]}
            return {"images": [{"n": i + 1, "caption": f"obraz {i + 1}", "text": ""} for i in range(len(images))]}
        if "lesson reports in course order" in user:
            return {"one_line": "Kurs o notatkach.", "about": "a", "text_summary": "b", "key_points": ["k"], "tags": ["notatki"]}
        return {"one_line": "Jak robić notatki.", "about": "O notatkach.", "text_summary": "Uczy systemu.",
                "visual_summary": "Slajdy.", "key_points": ["jedna myśl"], "life_applications": ["notuj"],
                "action_items": ["zrób arkusz"], "tags": ["Notatki"], "resources": [{"title": "Arkusz", "url": "http://x"}],
                "prerequisites": [], "difficulty": "beginner", "lesson_kind": "video_lesson", "confidence": 0.9}

    def complete(self, ref, system, user, images=None, json_mode=False, max_tokens=4000):
        self.calls.append((ref, user, images))
        return "notatki"


def _browser_ok():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:
        return False


needs_browser = pytest.mark.skipif(not _browser_ok(), reason="playwright + chromium not available")


@needs_browser
def test_map_and_digest_fake_course(scfg, tmp_path, synthetic_video, monkeypatch):
    srv = Site(synthetic_video)
    try:
        _map_and_digest(scfg, tmp_path, srv, monkeypatch)
    finally:
        srv.close()


def _map_and_digest(scfg, tmp_path, srv, monkeypatch):
    start = f"{srv.url}/courses/demo"
    # not logged in yet: the map stops with a clear message instead of mapping the login page
    with pytest.raises(session.SessionExpired):
        crawl.run(scfg, "demo", start, sleep=lambda s: None, log=lambda m: None)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("127.0.0.1\tFALSE\t/\tFALSE\t0\tsess\tok\n")
    session.import_cookies(scfg, "demo", cookies)
    m = crawl.run(scfg, "demo", start, sleep=lambda s: None, log=lambda m: None)

    mapped = {p["url"].split("/")[-1]: p for p in m["pages"] if p["status"] == "mapped"}
    assert set(mapped) == {"demo", "1-wstep", "2-zasady", "3-cwiczenie"}
    assert not any(h for h in srv.hits if "logout" in h or "cart" in h or "mark_complete" in h)
    l1, l2, l3 = mapped["1-wstep"], mapped["2-zasady"], mapped["3-cwiczenie"]
    assert mapped["demo"]["kind"] == "index"  # the course home is a table of contents
    assert l1["section"] == "Moduł 1: Podstawy" and l3["section"] == "Moduł 2: Praktyka"
    assert l1["videos"] == [f"{srv.url}/media/l1.mp4"]
    assert l2["videos"] == ["https://player.vimeo.com/video/123456789?h=abc"]
    assert [d["url"].rsplit("/", 1)[-1] for d in l1["docs"]] == ["handout.pdf"]
    assert l1["order"] < l2["order"] < l3["order"]
    assert "utm_source" not in l2["url"]
    assert (crawl.page_dir(scfg, "demo", l1["key"]) / "shot.jpg").is_file()
    text = (crawl.page_dir(scfg, "demo", l2["key"]) / "text.md").read_text()
    assert "Trzy zasady" in text and "Linkuj" in text
    outline = crawl.outline(m)
    assert "Moduł 2: Praktyka" in outline and "1 wideo" in outline
    assert {p["key"] for p in course.pending(m)} == {l1["key"], l2["key"], l3["key"]}

    # fetch first (as on the PC that holds the login): pages re-opened, video and PDF saved, no models
    res = crawl.fetch_pages(scfg, "demo", [l1], lambda r: lesson.fetch_media(scfg, "demo", r, log=lambda m: None),
                            sleep=lambda s: None, log=lambda m: None)
    assert res[0]["videos_ok"] == 1 and res[0]["docs_ok"] == 1
    assert list((crawl.page_dir(scfg, "demo", l1["key"]) / "media").glob("v01.*"))
    monkeypatch.setattr(lesson.media, "download_video", lambda *a, **k: pytest.fail("digest must reuse the fetched video"))

    # digest lesson 1 (fetched video and PDF, frames) with fake models and a fake transcript
    fake = FakeClient()
    monkeypatch.setattr(lesson.llm, "Client", lambda *a, **k: fake)
    monkeypatch.setattr(lesson.transcript, "get", lambda info, cfg, work, cookies, getter: {
        "source": "whisper_groq", "language": "pl", "segments": [{"start": 0, "end": 5, "text": "Witaj w kursie."}]})
    monkeypatch.setattr(lesson.pipeline.vision.shared, "vbench_prompts", lambda: None)
    res = course.digest_site(scfg, "demo", keys=[l1["key"]], write_notion=False, log=lambda m: None)
    assert res[0]["status"] == "done", res
    pdir = crawl.page_dir(scfg, "demo", l1["key"])
    les = json.loads((pdir / "lesson.json").read_text())
    assert les["videos"][0]["transcript"]["segments"][0]["text"] == "Witaj w kursie."
    assert les["videos"][0]["frames"] and les["videos"][0]["frames"][0]["caption"]
    assert les["docs"][0]["name"] == "handout.pdf" and les["docs"][0]["path"]
    assert les["screens"] and les["screens"][0]["caption"]
    md = (pdir / "report.md").read_text()
    assert "Jak robić notatki." in md and "Witaj w kursie." in md
    report_call = fake.calls[-1][1]
    assert "PAGE TEXT" in report_call and "VIDEO 1" in report_call and "FILE handout.pdf" in report_call
    after = {p["key"]: p for p in crawl.load_map(scfg, "demo")["pages"]}
    assert after[l1["key"]]["digest"]["status"] == "done"
    assert l1["key"] not in {p["key"] for p in course.pending(crawl.load_map(scfg, "demo"))}

    c = course.overview(scfg, "demo", write_notion=False, log=lambda m: None)
    assert c["report"]["one_line"] == "Kurs o notatkach."


def test_notion_blocks_and_markdown():
    les = {"site": "demo", "key": "k1", "url": "https://k.pl/l/1", "title": "Lekcja 1", "section": "Moduł 1", "order": 2,
           "page_text": "Tekst\n" * 10, "screens": [], "docs": [{"url": "https://k.pl/a.pdf", "name": "a.pdf", "text": "PDF", "error": None}],
           "videos": [{"n": 1, "url": "https://v", "title": "V", "status": "drm", "error": "DRM", "transcript": {"segments": []}, "frames": []}]}
    rep = lesson.normalise({"one_line": "x", "tags": ["A", "b"], "difficulty": "beginner", "key_points": ["p"]})
    blocks = notion_out.blocks(les, rep, {"models": ["m"], "cost_usd": 0.01}, "pl")
    kinds = [b["type"] for b in blocks]
    assert kinds[0] == "callout" and kinds[1] == "callout"  # partial warning because of the DRM video
    assert any(b["type"] == "toggle" for b in blocks)
    props = notion_out.properties(les, rep, {"models": ["m"], "cost_usd": 0.01}, "partial")
    assert props["Status"]["select"]["name"] == "Częściowo" and props["Kolejność"]["number"] == 2
    md = notion_out.markdown(les, rep, {"models": ["m"]})
    assert "Lekcja 1" in md and "drm" in md


def test_prefetched_local_video(scfg, tmp_path, synthetic_video, monkeypatch):
    """Videos harvested elsewhere (signed links) are referenced as local:<path> inside the page folder."""
    pdir = crawl.page_dir(scfg, "demo", "k1")
    (pdir / "media").mkdir()
    shutil.copy(synthetic_video, pdir / "media" / "l1.mp4")
    monkeypatch.setattr(lesson.media, "download_video", lambda *a, **k: pytest.fail("must not download"))
    monkeypatch.setattr(lesson.transcript, "get", lambda info, cfg, work, cookies, getter: {
        "source": "whisper_groq", "language": "pl", "segments": [{"start": 0, "end": 3, "text": "Cześć."}]})
    v = lesson.do_video(FakeClient(), scfg, {"frames_per_min": 0}, "local:media/l1.mp4", 1, pdir, "https://k.pl/l", None, {}, lambda m: None)
    assert v["status"] == "done" and v["duration_sec"] and v["transcript"]["segments"][0]["text"] == "Cześć."
    assert (pdir / "media" / "l1.mp4").is_file()  # the harvested file is kept
    (pdir / "media" / "l1.pl.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nZ napisów GPU.\n")
    monkeypatch.setattr(lesson.transcript, "get", lambda *a, **k: pytest.fail("the sibling VTT is the transcript"))
    v2 = lesson.do_video(FakeClient(), scfg, {"frames_per_min": 0}, "local:media/l1.mp4", 1, pdir, "https://k.pl/l", None, {}, lambda m: None)
    assert v2["transcript"]["source"] == "player_captions" and v2["transcript"]["segments"][0]["text"] == "Z napisów GPU."
    missing = lesson.do_video(FakeClient(), scfg, {"frames_per_min": 0}, "local:media/nope.mp4", 2, pdir, "https://k.pl/l", None, {}, lambda m: None)
    assert missing["status"] == "download_failed" and "nope.mp4" in missing["error"]
    assert lesson.fetch_media(scfg, "demo", {"key": "k1", "url": "https://k.pl/l", "videos": ["local:media/l1.mp4"]},
                              log=lambda m: None)["videos"] == 0


def _pool_map(scfg, n, with_vtt):
    pages = []
    for i in range(n):
        key = f"k{i:02d}"
        pdir = crawl.page_dir(scfg, "demo", key)
        (pdir / "media").mkdir(exist_ok=True)
        (pdir / "media" / "v01.mp4").write_bytes(b"x")
        if with_vtt(i):
            (pdir / "media" / "v01.pl.vtt").write_text("WEBVTT\n")
        pages.append({"key": key, "url": f"https://k.pl/l/{i}", "status": "mapped", "kind": "lesson", "order": i,
                      "videos": ["local:media/v01.mp4"], "text_chars": 500})
    crawl.save_map(scfg, "demo", {"site": "demo", "start_url": "https://k.pl", "pages": pages})


def test_pool_claims_are_exclusive_and_wait_for_transcripts(scfg):
    from sitedigest import pool

    _pool_map(scfg, 6, with_vtt=lambda i: i != 5)
    db = pool.connect(scfg, "demo")
    assert pool.sync(scfg, "demo", db, require_vtt=True) == 5  # lesson 5 has no transcript yet
    got = [pool.claim(db, f"w{i}") for i in range(7)]
    assert sorted(k for k in got if k) == ["k00", "k01", "k02", "k03", "k04"] and got[5] is None
    # an expired lease goes back to the pool
    db.execute("UPDATE jobs SET lease_until=0 WHERE key='k02'")
    assert pool.claim(db, "w9") == "k02"
    assert pool.is_limit("claude-code:sonnet -> Claude AI usage limit reached|1760000000")
    # finished lessons stay out; one sent back on purpose ('requeued') comes back, once
    for k in ("k00", "k01"):
        pool.finish(db, k, "done")
    crawl.update_pages(scfg, "demo", {"k00": {"status": "done"}, "k01": {"status": "requeued"}})
    assert pool.sync(scfg, "demo", db, require_vtt=True) == 1
    assert pool.claim(db, "w10") == "k01"
    assert pool.sync(scfg, "demo", db, require_vtt=True) == 0


def test_pool_reads_limit_reset_time():
    import time

    from sitedigest import pool

    now = 1760000000.0
    assert pool.limit_wait("Claude AI usage limit reached|1760003600", 1800, now) == 3600 + 120
    assert pool.is_limit("claude-code exit 1: You've hit your limit · resets 3pm (Europe/Warsaw)")
    t = time.localtime(now + 2 * 3600)  # a clock time two hours ahead, local time
    at = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, 0, 0, 0, 0, -1))
    h12 = f"{t.tm_hour % 12 or 12}{'pm' if t.tm_hour >= 12 else 'am'}"
    assert pool.limit_wait(f"5-hour limit reached ∙ resets {h12}", 1800, now) == at - now + 120
    assert pool.limit_wait(f"resets {t.tm_hour}:00", 1800, now) == at - now + 120
    assert pool.limit_wait("overloaded", 1800, now) == 1800  # no reset time: the default


def test_pool_runs_parallel_workers(scfg, monkeypatch):
    import os

    from sitedigest import pool
    from ytdigest.llm import LimitError

    _pool_map(scfg, 8, with_vtt=lambda i: True)
    calls = []

    def fake_digest(cfg, site, rec, **kw):
        if rec["key"] == "k03" and not calls.count("k03-retry"):
            calls.append("k03-retry")
            raise LimitError("claude-code:sonnet -> Claude AI usage limit reached")
        if rec["key"] == "k05":  # an ordinary error mentioning limits is a failed lesson, not a pause
            raise RuntimeError("no JSON object in model output: 'this lesson is about API rate limits'")
        return {"key": rec["key"], "status": "done", "pid": os.getpid()}

    monkeypatch.setattr(lesson, "digest", fake_digest)
    res = pool.run(scfg, "demo", workers=3, write_notion=False, pause_minutes=0, max_minutes=1, log=lambda m: None)
    assert sum(r["done"] for r in res) == 7 and sum(r["failed"] for r in res) == 1 and len(res) == 3
    m = crawl.load_map(scfg, "demo")
    st = {p["key"]: (p.get("digest") or {}).get("status") for p in m["pages"]}
    assert st.pop("k05") == "failed" and set(st.values()) == {"done"}, st
    assert pool.stats(scfg, "demo").get("done") == 7


def test_claude_limit_is_told_apart_from_other_errors(cfg, monkeypatch, tmp_path):
    import subprocess

    from ytdigest import llm

    def fake_run(stdout, code):
        return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=stdout, stderr="")

    client = llm.Client(cfg, ledger=tmp_path / "spend.jsonl")
    monkeypatch.setattr(subprocess, "run", fake_run(json.dumps({"is_error": True, "result": "5-hour limit reached ∙ resets 3pm"}), 1))
    with pytest.raises(llm.LimitError):
        client.complete("claude-code:sonnet", "s", "u")
    monkeypatch.setattr(subprocess, "run", fake_run(json.dumps({"is_error": True, "result": "Invalid model name"}), 1))
    with pytest.raises(llm.LLMError) as e:
        client.complete("claude-code:sonnet", "s", "u")
    assert not isinstance(e.value, llm.LimitError)


def test_pool_leases_are_owned_renewed_and_given_up(scfg):
    from sitedigest import pool

    _pool_map(scfg, 2, with_vtt=lambda i: True)
    db = pool.connect(scfg, "demo")
    pool.sync(scfg, "demo", db)
    k = pool.claim(db, "a", lease_sec=0)  # expired at once: someone else may take it
    assert pool.claim(db, "b") == k
    assert not pool.renew(db, k, "a") and pool.renew(db, k, "b")
    assert not pool.finish(db, k, "done", owner="a")  # the old holder can't close it
    assert pool.owns(db, k, "b") and pool.finish(db, k, "done", owner="b")
    # a lesson that kills its worker every time is given up after MAX_ATTEMPTS
    other = pool.claim(db, "c", lease_sec=0)
    for i in range(pool.MAX_ATTEMPTS - 1):
        assert pool.claim(db, f"d{i}", lease_sec=0) == other
    assert pool.claim(db, "e") is None
    assert dict(db.execute("SELECT key, status FROM jobs").fetchall())[other] == "failed"


def test_pool_parent_survives_a_killed_worker(scfg, monkeypatch):
    import os

    from sitedigest import pool

    _pool_map(scfg, 4, with_vtt=lambda i: True)

    def fake_digest(cfg, site, rec, **kw):
        if rec["key"] == "k00":
            os._exit(9)  # like an OOM kill: no report, no cleanup
        return {"key": rec["key"], "status": "done"}

    monkeypatch.setattr(lesson, "digest", fake_digest)
    res = pool.run(scfg, "demo", workers=2, write_notion=False, max_minutes=0.3, log=lambda m: None)
    assert len(res) == 2 and any("code 9" in (r.get("error") or "") for r in res)
    assert sum(r["done"] for r in res) == 3


def test_limit_wait_reads_zones_and_dates():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from sitedigest import pool

    waw = ZoneInfo("Europe/Warsaw")
    now = datetime(2026, 10, 11, 13, 0, tzinfo=waw).timestamp()
    assert pool.limit_wait("You've hit your limit · resets 3pm (Europe/Warsaw)", 60, now) == 2 * 3600 + 120
    weekly = datetime(2026, 10, 14, 15, 0, tzinfo=waw).timestamp() - now + 120
    assert pool.limit_wait("weekly limit reached · resets Oct 14, 3pm (Europe/Warsaw)", 60, now) == weekly
    assert pool.limit_wait("resets 25:00", 60, now) == 60


def test_captions_for_matches_only_this_video(tmp_path):
    v = tmp_path / "lesson1.mp4"
    for name in ("lesson1.vtt", "lesson1.pl.vtt", "lesson10.pl.vtt", "lesson1.en.vtt"):
        (tmp_path / name).write_text("WEBVTT\n")
    assert [f.name for f in media.captions_for(v, ["pl", "en"])] == ["lesson1.pl.vtt", "lesson1.en.vtt", "lesson1.vtt"]
    odd = tmp_path / "a[1].mp4"
    (tmp_path / "a[1].vtt").write_text("WEBVTT\n")
    assert media.captions_for(odd)


def test_long_runs_keep_results_written_meanwhile(scfg):
    _pool_map(scfg, 3, with_vtt=lambda i: True)
    stale = crawl.load_map(scfg, "demo")
    crawl.update_pages(scfg, "demo", {"k01": {"status": "done"}})
    stale["pages"][0]["title"] = "renamed by the mapper"
    crawl.save_map_merged(scfg, "demo", stale)
    m = crawl.load_map(scfg, "demo")
    assert m["pages"][1]["digest"] == {"status": "done"} and m["pages"][0]["title"] == "renamed by the mapper"


def test_digest_skips_lessons_whose_video_has_not_synced(scfg, monkeypatch):
    _pool_map(scfg, 2, with_vtt=lambda i: True)
    (crawl.page_dir(scfg, "demo", "k01") / "media" / "v01.mp4").unlink()
    seen = []
    monkeypatch.setattr(lesson, "digest", lambda cfg, site, rec, **kw: seen.append(rec["key"]) or {"key": rec["key"], "status": "done"})
    course.digest_site(scfg, "demo", write_notion=False, log=lambda m: None)
    assert seen == ["k00"]
