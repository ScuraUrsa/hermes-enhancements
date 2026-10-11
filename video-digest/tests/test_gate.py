import json
import sqlite3
import time

from ytdigest import gate


def _home(tmp_path, monkeypatch):
    h = tmp_path / ".hermes"
    (h / "autonomy").mkdir(parents=True)
    monkeypatch.setattr(gate, "H", h)
    monkeypatch.setattr(gate, "_machine", lambda cfg: (True, "machine ok"))
    return h


def _state(h, source, ts):
    c = sqlite3.connect(h / "state.db")
    c.execute("create table if not exists sessions(id text, source text)")
    c.execute("create table if not exists messages(session_id text, timestamp real)")
    c.execute("insert into sessions values('s1', ?)", (source,))
    c.execute("insert into messages values('s1', ?)", (ts,))
    c.commit()


def test_gate_open_when_nothing_happens(tmp_path, monkeypatch, cfg):
    h = _home(tmp_path, monkeypatch)
    (h / "autonomy" / "quota.json").write_text(json.dumps({"mode": "non_coding"}))
    _state(h, "cron", time.time())  # Hermes' own cron does not count as Filip
    ok, why = gate.check(cfg)
    assert ok, why


def test_gate_closed_when_filip_is_chatting(tmp_path, monkeypatch, cfg):
    h = _home(tmp_path, monkeypatch)
    _state(h, "cli", time.time() - 60)
    ok, why = gate.check(cfg)
    assert not ok and any("active" in w for w in why)


def test_gate_closed_when_quota_idle_or_cap_spent(tmp_path, monkeypatch, cfg):
    h = _home(tmp_path, monkeypatch)
    (h / "autonomy" / "quota.json").write_text(json.dumps({"mode": "idle"}))
    assert not gate.check(cfg)[0]
    (h / "autonomy" / "quota.json").write_text(json.dumps({"mode": "coding"}))
    from ytdigest import llm
    c = llm.Client(cfg, ledger=gate.Path(cfg["data_dir"]) / "spend.jsonl", tag="backlog")
    c._ledger("x:y", 5.0)
    ok, why = gate.check(cfg)
    assert not ok and any("backlog spend" in w for w in why)


def test_gate_closed_when_filips_task_runs(tmp_path, monkeypatch, cfg):
    h = _home(tmp_path, monkeypatch)
    c = sqlite3.connect(h / "kanban.db")
    c.execute("create table tasks(id text, status text, priority int)")
    c.execute("insert into tasks values('t', 'running', 100)")
    c.commit()
    assert not gate.check(cfg)[0]
