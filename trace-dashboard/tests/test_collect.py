"""Linking and pricing of collect.py on a tiny synthetic Hermes home (no network)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect  # noqa: E402

T0 = 1792000000  # 2026-10-15 epoch


def make_home(tmp: Path) -> Path:
    home = tmp / ".hermes"
    (home / "profiles" / "coder").mkdir(parents=True)
    schema = ("CREATE TABLE sessions(id, source, title, model, billing_provider, billing_base_url, started_at, ended_at,"
              " parent_session_id, cwd, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,"
              " reasoning_tokens, estimated_cost_usd, profile_name);"
              "CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id, role, content);"
              "CREATE TABLE session_model_usage(session_id, model, billing_provider, base_url, mode, task,"
              " input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens,"
              " estimated_cost_usd, actual_cost_usd)")
    main = sqlite3.connect(home / "state.db")
    main.executescript(schema)
    main.execute("INSERT INTO sessions VALUES('chat1','cli','Zrób pogodę','deepseek-v4.1-flash','ollama-cloud','',"
                 "?,?,NULL,'/home/ubuntu',1000000,10000,500000,0,0,0,'main')", (T0, T0 + 600))
    main.execute("INSERT INTO messages(session_id,role,content) VALUES('chat1','user','Dodaj pogodę do Hermesa')")
    main.execute("INSERT INTO session_model_usage VALUES('chat1','deepseek-v4.1-flash','ollama-cloud','','', '',"
                 "1000000,10000,500000,0,0,0,0)")
    main.execute("INSERT INTO session_model_usage VALUES('chat1','qwen3.5-4b','custom','http://127.0.0.1:8083/v1','',"
                 "'cheap_route_router',2000,10,0,0,0,0,0)")
    main.commit()
    coder = sqlite3.connect(home / "profiles" / "coder" / "state.db")
    coder.executescript(schema)
    coder.execute("INSERT INTO sessions VALUES('w1','kanban','work kanban task t_aaaaaaaa','glm-5.3-flash',"
                  "'ollama-cloud','',?,?,NULL,'',2000000,20000,0,0,0,0,'coder')", (T0 + 700, T0 + 900))
    coder.execute("INSERT INTO sessions VALUES('w2','kanban','','glm-5.3-flash','ollama-cloud','',?,?,NULL,'',"
                  "1000000,0,0,0,0,0,'coder')", (T0 + 2000, T0 + 2100))
    coder.commit()
    kb = sqlite3.connect(home / "kanban-dev.db")
    kb.executescript("CREATE TABLE tasks(id,title,body,assignee,status,created_by,created_at,started_at,completed_at,"
                     "workspace_path,branch_name,result,session_id);"
                     "CREATE TABLE task_runs(id,task_id,profile,started_at,ended_at,metadata)")
    kb.execute("INSERT INTO tasks VALUES('t_aaaaaaaa','Weather skill','body','coder','done','filip-via-hermes',?,?,?,"
               "'','wt/t_aaaaaaaa','ok','chat1')", (T0 + 650, T0 + 700, T0 + 900))
    kb.execute("INSERT INTO tasks VALUES('t_bbbbbbbb','Planner chore','','coder','done','planner',?,?,?,'','','','')",
               (T0 + 1900, T0 + 2000, T0 + 2100))
    kb.execute("INSERT INTO task_runs VALUES(1,'t_bbbbbbbb','coder',?,?,'{}')", (T0 + 1990, T0 + 2200))
    kb.commit()
    (home / "autonomy").mkdir()
    (home / "autonomy" / "claude_runs.jsonl").write_text(json.dumps({
        "ts": "2026-10-15T06:00:00+00:00", "task_id": "t_aaaaaaaa", "session_id": "cc1", "model": "sonnet",
        "input_tokens": 10, "output_tokens": 100, "cache_read_tokens": 1000, "cost_usd_equiv": 0.5}) + "\n")
    return home


def test_build(tmp_path):
    home = make_home(tmp_path)
    threads = tmp_path / "threads.json"
    threads.write_text(json.dumps({"project_id": "chan_x", "threads": [{
        "thread_id": "cmsg_0123456789abcdefghijABCD", "session_id": "session_0123456789abcdefghijXYZ",
        "title": "Pogoda", "created_at": "2026-10-15T05:00:00Z", "resolved": True, "resolved_at": "2026-10-15T07:00:00Z",
        "root": {"author_name": "Filip", "text": "Chcę pogodę"},
        "session": {"branch": "claude/project-thread-abc", "usage": {"cost_usd": 3.25, "input_tokens": 5,
                                                                      "output_tokens": 7}}}],
        "coordinators": [{"id": "session_coord", "usage": {"cost_usd": 1.0}}]}))
    out = tmp_path / "trace.json"
    usage = tmp_path / "llm_usage.jsonl"
    usage.write_text("\n".join(json.dumps(r) for r in [
        {"ts": "2026-10-31T10:00:00+00:00", "caller": "timeplane/tp_state", "provider": "ollama",
         "model": "deepseek-v4.1-flash", "input_tokens": 1_000_000, "cache_read_tokens": 400_000, "output_tokens": 0},
        {"ts": "2026-10-31T10:10:00+00:00", "caller": "timeplane/tp_state", "provider": "ollama",
         "model": "deepseek-v4.1-flash", "input_tokens": 0, "cache_read_tokens": 0, "output_tokens": 100_000},
    ]) + "\nnot json\n")
    rc = collect.main(["--hermes-home", f"prod={home}", "--kanban", f"dev={home / 'kanban-dev.db'}",
                       "--claude-runs", f"prod={home / 'autonomy' / 'claude_runs.jsonl'}",
                       "--llm-usage", f"prod={usage}",
                       "--claude-threads", str(threads), "--budget", "/nonexistent", "--no-github",
                       "--days", "100000", "--github-cache", str(tmp_path / "c.json"), "--out", str(out)])
    assert rc == 0
    d = json.loads(out.read_text())
    tr = {t["id"]: t for t in d["traces"]}

    chat = tr["hs:chat1"]  # Filip's chat -> kanban task (tasks.session_id) -> worker (t_ id in title) -> Claude run
    assert chat["steps"] == ["hs:chat1", "kb:t_aaaaaaaa", "hs:w1", "cc:cc1"]
    assert d["steps"]["hs:w1"]["parent_step"] == "kb:t_aaaaaaaa"
    assert d["steps"]["cc:cc1"]["parent_step"] == "kb:t_aaaaaaaa"
    # deepseek 1M in * 0.3 + 0.5M cached * 0.006 + 10k out * 1.2 = 0.3 + 0.003 + 0.012; local qwen = 0
    assert abs(d["steps"]["hs:chat1"]["cost_usd"] - 0.315) < 1e-9
    assert set(chat["by_provider"]) == {"ollama", "anthropic", "local"}
    assert chat["by_provider"]["anthropic"]["cost_usd"] == 0.5
    # subscriptions (pricing.json): Ollama goes to the first key's plan, Claude to Max, llama.cpp to none
    assert set(chat["by_subscription"]) == {"ollama-main", "claude-max", "none"}
    assert abs(chat["by_subscription"]["ollama-main"]["sub_usd"] - chat["by_provider"]["ollama"]["cost_usd"] * 20 / 60) < 1e-4
    assert {s["id"] for s in d["subscriptions"]} >= {"ollama-main", "ollama-fj", "claude-max"}

    planner = tr["kb:t_bbbbbbbb"]  # planner task, worker matched by profile + run window
    assert planner["origin"] == "hermes_autonomy"
    assert "hs:w2" in planner["steps"]

    thread = tr["ct:cmsg_0123456789abcdefghijABCD"]
    assert thread["cost_usd"] == 3.25 and thread["status"] == "done"
    assert tr["coordinator"]["cost_usd"] == 1.0

    # direct calls: one step per script/day/model, input minus its cached part:
    # 0.6M * 0.3 + 0.4M * 0.006 + 0.1M * 1.2 = 0.18 + 0.0024 + 0.12
    direct = tr["direct:timeplane/tp_state:2026-10"]
    assert direct["origin"] == "hermes_autonomy" and set(direct["by_provider"]) == {"ollama"}
    assert abs(direct["cost_usd"] - 0.3024) < 1e-9
    assert d["steps"][direct["steps"][0]]["meta"]["calls"] == 2


def test_provider_of():
    assert collect.provider_of("qwen3.5-4b", "custom http://127.0.0.1:8083/v1") == "local"
    assert collect.provider_of("deepseek-v4.1-flash", "ollama-cloud") == "ollama"
    assert collect.provider_of("claude-opus-5-5") == "anthropic"
    assert collect.provider_of("gemini-3.6-flash", "gemini") == "gemini"


def test_redact():
    assert "ghp_" not in collect.redact("token ghp_abcdefghijklmnop123 here")
    assert "user:pass" not in collect.redact("https://user:pass@github.com/x")


def test_allocate_subscriptions():
    subs = [{"id": "a", "provider": "ollama", "keys": ["K1"], "monthly_price_usd": 20, "included_usd": 60, "period_start_day": 20},
            {"id": "b", "provider": "ollama", "keys": ["K2"], "monthly_price_usd": 20, "included_usd": 60, "period_start_day": 4},
            {"id": "c", "provider": "anthropic", "monthly_price_usd": 100, "included_usd": None, "period_start_day": 1}]
    spends = [
        {"ref": "s1", "at": "2026-10-21T10:00:00", "provider": "ollama", "key": None, "api_usd": 50.0, "tokens": 100},
        {"ref": "s2", "at": "2026-10-22T10:00:00", "provider": "ollama", "key": None, "api_usd": 30.0, "tokens": 60},
        {"ref": "s3", "at": "2026-10-23T10:00:00", "provider": "ollama", "key": "K2", "api_usd": 6.0, "tokens": 6},
        {"ref": "s4", "at": "2026-10-05T10:00:00", "provider": "anthropic", "key": None, "api_usd": 30.0, "tokens": 1},
        {"ref": "s5", "at": "2026-10-06T10:00:00", "provider": "anthropic", "key": None, "api_usd": 10.0, "tokens": 1},
        {"ref": "s6", "at": "2026-10-06T10:00:00", "provider": "local", "key": None, "api_usd": 0.0, "tokens": 5},
    ]
    alloc, out = collect.allocate_subscriptions(spends, subs)
    # s1 fits in a's $60; s2: $10 more on a (full), $20 overflows to b
    assert [(x["sub"], round(x["api_usd"], 6)) for x in alloc["s2"]] == [("a", 10.0), ("b", 20.0)]
    assert abs(alloc["s1"][0]["sub_usd"] - 50 * 20 / 60) < 1e-6
    assert alloc["s3"][0]["sub"] == "b" and alloc["s3"][0]["period"] == "2026-10-04"
    # Claude: fee split by share of the period's spend
    assert abs(alloc["s4"][0]["sub_usd"] - 75.0) < 1e-6 and abs(alloc["s5"][0]["sub_usd"] - 25.0) < 1e-6
    assert "s6" not in alloc
    per = {s["id"]: s["periods"] for s in out}
    assert per["a"] == [{"start": "2026-10-20", "end": "2026-11-20", "api_usd": 60.0, "sub_usd": 20.0, "used_pct": 100.0}]
    assert per["b"][0]["api_usd"] == 26.0 and per["b"][0]["start"] == "2026-10-04"


def test_elapsed_share():
    now = collect.dt.datetime(2026, 11, 16, tzinfo=collect.dt.timezone.utc)
    assert abs(collect.elapsed_share("2026-11-01", now) - 0.5) < 1e-9
    assert collect.elapsed_share("2026-10-01", now) == 1.0
    sub = [{"id": "c", "provider": "anthropic", "monthly_price_usd": 100, "included_usd": None, "period_start_day": 1}]
    alloc, out = collect.allocate_subscriptions(
        [{"ref": "x", "at": "2026-11-02T00:00:00", "provider": "anthropic", "api_usd": 1.0, "tokens": 1}], sub, now)
    assert abs(alloc["x"][0]["sub_usd"] - 50.0) < 1e-6 and abs(out[0]["periods"][0]["sub_usd"] - 50.0) < 1e-6


def test_period_start():
    assert collect.period_start("2026-11-03T23:00:00", 4) == "2026-10-04"
    assert collect.period_start("2026-11-04T00:00:00", 4) == "2026-11-04"
    assert collect.period_start("2026-01-10", 20) == "2025-12-20"
