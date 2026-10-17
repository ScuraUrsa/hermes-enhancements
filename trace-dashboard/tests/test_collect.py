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
    rc = collect.main(["--hermes-home", f"prod={home}", "--kanban", f"dev={home / 'kanban-dev.db'}",
                       "--claude-runs", f"prod={home / 'autonomy' / 'claude_runs.jsonl'}",
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

    planner = tr["kb:t_bbbbbbbb"]  # planner task, worker matched by profile + run window
    assert planner["origin"] == "hermes_autonomy"
    assert "hs:w2" in planner["steps"]

    thread = tr["ct:cmsg_0123456789abcdefghijABCD"]
    assert thread["cost_usd"] == 3.25 and thread["status"] == "done"
    assert tr["coordinator"]["cost_usd"] == 1.0


def test_provider_of():
    assert collect.provider_of("qwen3.5-4b", "custom http://127.0.0.1:8083/v1") == "local"
    assert collect.provider_of("deepseek-v4.1-flash", "ollama-cloud") == "ollama"
    assert collect.provider_of("claude-opus-5-5") == "anthropic"
    assert collect.provider_of("gemini-3.6-flash", "gemini") == "gemini"


def test_redact():
    assert "ghp_" not in collect.redact("token ghp_abcdefghijklmnop123 here")
    assert "user:pass" not in collect.redact("https://user:pass@github.com/x")
