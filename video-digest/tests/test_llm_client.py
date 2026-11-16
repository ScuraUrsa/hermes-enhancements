"""Contract tests for `ytdigest.llm`: the provider boundary, retry loop, pricing and ledger.

Everything here is hermetic. Three things are replaced before a test body runs:

* `requests.post` / `requests.get`  -> `FakeTransport` queues (conftest helper),
* `time.sleep`                      -> a recorder, so backoff is asserted not waited,
* `subprocess.run`                  -> a recorder (the Claude Code CLI is never executed).

`_hermetic` also blocks `socket.socket.connect` / `socket.create_connection`, so a leaked
network call fails loudly instead of reaching a provider. Provider keys are read from the
environment by `llm.py`, so this module deletes every one of them first: no test can pass
because a real secret happened to be exported on the machine.
"""

import json
import os
import socket
import subprocess

import pytest

from conftest import FakeResponse, chat_ok
from ytdigest import llm

PROVIDER_KEYS = ("OLLAMA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


# --- hermeticity -------------------------------------------------------------

@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """No sockets, no subprocesses, no real sleeping, no inherited provider secrets."""
    for name in PROVIDER_KEYS:
        monkeypatch.delenv(name, raising=False)

    def _no_connect(self, *a, **k):
        raise AssertionError(f"network access attempted in a hermetic test: {self!r} {a}")

    monkeypatch.setattr(socket.socket, "connect", _no_connect)
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError(f"network access attempted: {a}")))

    slept = []
    monkeypatch.setattr(llm.time, "sleep", slept.append)

    # The suite-wide `_no_live_model_list` fixture pins ollama-cloud to None; here the
    # transport fake already makes a live call impossible, so start from an empty cache and
    # let each available_models test decide what the cache holds.
    monkeypatch.setattr(llm, "_MODEL_CACHE", {})

    def _no_subprocess(*a, **k):
        raise AssertionError(f"subprocess executed in a hermetic test: {a}")

    monkeypatch.setattr(subprocess, "run", _no_subprocess)
    return slept


class _Completed:
    """`subprocess.CompletedProcess` stand-in."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def cc(monkeypatch):
    """Replaces `subprocess.run`: records the call, pops a queued result."""
    rec = {"calls": [], "queue": []}

    def fake_run(cmd, **kwargs):
        rec["calls"].append({
            "cmd": list(cmd),
            "input": kwargs.get("input"),
            "env": dict(kwargs.get("env") or {}),
            "cwd": kwargs.get("cwd"),
            "cwd_existed": os.path.isdir(str(kwargs.get("cwd") or "")),
            "timeout": kwargs.get("timeout"),
        })
        if not rec["queue"]:
            raise AssertionError("unexpected subprocess.run (nothing queued)")
        item = rec["queue"].pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(subprocess, "run", fake_run)
    return rec


@pytest.fixture
def keyed(cfg, monkeypatch):
    """cfg with a fake ollama-cloud key, so the openai-compatible path can run."""
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key-not-a-secret")
    return cfg


# --- 1. split_ref ------------------------------------------------------------

def test_split_ref_drops_options_and_keeps_colons_in_model():
    assert llm.split_ref("ollama-cloud:gpt-oss:120b") == ("ollama-cloud", "gpt-oss:120b")
    assert llm.split_ref("gemini-video:gemini-2.5-flash-lite@fps=0.2") == (
        "gemini-video", "gemini-2.5-flash-lite")


def test_split_ref_without_model_raises():
    with pytest.raises(llm.LLMError, match="needs 'provider:model'"):
        llm.split_ref("ollama-cloud")
    with pytest.raises(llm.LLMError):
        llm.split_ref("ollama-cloud@fps=0.2")


# --- 2. price ----------------------------------------------------------------

def test_price_uses_per_model_table(cfg):
    # gpt-oss:120b is 0.15 / 0.60 USD per Mtok
    assert llm.price(cfg, "gpt-oss:120b", 1_000_000, 0) == pytest.approx(0.15)
    assert llm.price(cfg, "gpt-oss:120b", 0, 1_000_000) == pytest.approx(0.60)
    assert llm.price(cfg, "gpt-oss:120b", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_price_falls_back_to_default_table(cfg):
    cfg["prices_per_mtok"] = {"_default": [2.0, 4.0]}
    assert llm.price(cfg, "never-heard-of-it", 1_000_000, 0) == pytest.approx(2.0)
    # no config table at all: the built-in default is [0.5, 1.5]
    assert llm.price({}, "m", 1_000_000, 1_000_000) == pytest.approx(2.0)


# --- 3. _image_part ----------------------------------------------------------

def test_image_part_builds_base64_jpeg_data_uri(tmp_path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\xff\xd8\xff\x00binary")
    part = llm._image_part(img)
    assert part["type"] == "image_url"
    assert part["image_url"]["url"] == "data:image/jpeg;base64,/9j/AGJpbmFyeQ=="


# --- 4. ref_options ----------------------------------------------------------

def test_ref_options_parses_pairs_and_skips_garbage():
    assert llm.ref_options("gemini-video:gemini-2.5-flash-lite@fps=0.2") == {"fps": "0.2"}
    assert llm.ref_options("p:m@fps=0.5@scale=2@junk@k=v=w") == {"fps": "0.5", "scale": "2", "k": "v=w"}
    assert llm.ref_options("p:m") == {}
    assert llm.ref_options("p:m@fps=1@just-a-flag") == {"fps": "1"}


# --- 5. Client.json ----------------------------------------------------------

def test_json_returns_parsed_object_from_first_answer(keyed, transport):
    transport.post_queue.append(chat_ok('{"title": "hi", "n": 2}'))
    out = llm.Client(keyed).json("ollama-cloud:gpt-oss:120b", "sys", "user")
    assert out == {"title": "hi", "n": 2}
    assert len(transport.posts) == 1


def test_json_repairs_an_unparsable_first_answer(keyed, transport):
    transport.post_queue += [chat_ok("I cannot help with that."), chat_ok('{"ok": true}')]
    c = llm.Client(keyed)
    assert c.json("ollama-cloud:gpt-oss:120b", "sys", "user") == {"ok": True}
    first, second = transport.posts
    # the repair call asks for JSON only and feeds the broken text back
    assert second["json"]["messages"][0]["content"] == "Return only valid JSON. No prose."
    assert "I cannot help with that." in second["json"]["messages"][1]["content"]
    assert second["json"]["response_format"] == {"type": "json_object"}
    # both calls are billed
    assert c.usage.calls == 2


def test_json_propagates_when_the_repair_is_also_unparsable(keyed, transport):
    transport.post_queue += [chat_ok("nope"), chat_ok("still nope")]
    with pytest.raises(llm.LLMError, match="no JSON object"):
        llm.Client(keyed).json("ollama-cloud:gpt-oss:120b", "sys", "user")
    assert len(transport.posts) == 2


# --- 6. Client.complete dispatch --------------------------------------------

def test_complete_rejects_gemini_video_ref(cfg, transport):
    with pytest.raises(llm.LLMError, match="gemini_url analyzer"):
        llm.Client(cfg).complete("gemini-video:gemini-2.5-flash-lite", "s", "u")
    assert transport.posts == []


def test_complete_dispatches_claude_code_to_the_cli(cfg, cc):
    cc["queue"].append(_Completed(stdout=json.dumps({"result": "from cli", "usage": {}})))
    assert llm.Client(cfg).complete("claude-code:haiku", "s", "u") == "from cli"
    assert cc["calls"][0]["cmd"][:2] == ["claude", "-p"]
    assert cc["calls"][0]["cmd"][2:4] == ["--model", "haiku"]


def test_complete_dispatches_everything_else_to_openai_compat(keyed, transport):
    transport.post_queue.append(chat_ok("hi"))
    llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert transport.posts[0]["url"] == "https://ollama.com/v1/chat/completions"


# --- 7. _openai_compat -------------------------------------------------------

def test_openai_compat_rejects_unknown_provider(keyed, transport):
    with pytest.raises(llm.LLMError, match="unknown provider 'nope'"):
        llm.Client(keyed).complete("nope:m", "s", "u")
    assert transport.posts == []


def test_openai_compat_raises_when_key_env_is_set_but_empty(cfg, transport):
    # cfg declares OLLAMA_API_KEY for ollama-cloud and the autouse fixture deleted it
    assert "OLLAMA_API_KEY" not in os.environ
    with pytest.raises(llm.LLMError, match="OLLAMA_API_KEY not set"):
        llm.Client(cfg).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert transport.posts == []


def test_openai_compat_sends_no_authorization_without_key_env(keyed, transport):
    # ollama-local declares key_env: "" -> no key, and crucially no bearer header
    transport.post_queue.append(chat_ok())
    llm.Client(keyed).complete("ollama-local:llama3", "s", "u")
    assert "Authorization" not in transport.posts[0]["headers"]
    assert transport.posts[0]["headers"]["Content-Type"] == "application/json"


def test_openai_compat_sends_bearer_when_key_env_is_set(keyed, transport):
    transport.post_queue.append(chat_ok())
    llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert transport.posts[0]["headers"]["Authorization"] == "Bearer test-key-not-a-secret"


def test_openai_compat_json_mode_asks_for_a_json_object(keyed, transport):
    transport.post_queue.append(chat_ok("{}"))
    llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u", json_mode=True)
    assert transport.posts[0]["json"]["response_format"] == {"type": "json_object"}
    assert transport.posts[0]["json"]["temperature"] == 0.2
    assert transport.posts[0]["json"]["max_tokens"] == 4000


def test_openai_compat_400_on_response_format_retries_without_it(keyed, transport):
    transport.post_queue += [FakeResponse(status_code=400, text="response_format unsupported"),
                             chat_ok("{}")]
    out = llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u", json_mode=True)
    assert out == "{}"
    first, second = transport.posts
    assert first["json"]["response_format"] == {"type": "json_object"}
    assert "response_format" not in second["json"]
    assert len(transport.posts) == 2  # the 400 did not burn a retry attempt


def test_openai_compat_retries_429_then_succeeds_with_backoff(keyed, transport, _hermetic):
    transport.post_queue += [FakeResponse(status_code=429, text="slow down"), chat_ok("done")]
    out = llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert out == "done"
    assert len(transport.posts) == 2
    # min(60, 5 * 2**attempt) for attempt 0 -> 5s.
    assert _hermetic == [5]


def test_openai_compat_retries_5xx_and_collects_the_backoff_sequence(keyed, transport, _hermetic):
    transport.post_queue += [FakeResponse(status_code=503, text="a"),
                             FakeResponse(status_code=502, text="b"),
                             FakeResponse(status_code=500, text="c"),
                             chat_ok("finally")]
    c = llm.Client(keyed)
    assert c.complete("ollama-cloud:gpt-oss:120b", "s", "u") == "finally"
    assert _hermetic == [5, 10, 20]  # exponential, not a constant nap
    assert len(transport.posts) == 4
    assert c.usage.calls == 1  # only the successful call is billed


def test_openai_compat_gives_up_after_four_failing_attempts(keyed, transport, _hermetic):
    transport.post_queue += [FakeResponse(status_code=429, text="burst-%d" % n) for n in range(4)]
    with pytest.raises(llm.LLMError, match="kept failing: 429: burst-3"):
        llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert len(transport.posts) == 4
    # Four attempts, four naps: 5, 10, 20, then 40 before the loop falls through to the
    # raise -- that last nap buys nothing (finding, not asserted away: the 60s cap in
    # min(60, 5 * 2**attempt) is unreachable while the loop is range(4)).
    assert _hermetic == [5, 10, 20, 40]


def test_openai_compat_fails_fast_on_a_client_error(keyed, transport, _hermetic):
    transport.post_queue.append(FakeResponse(status_code=401, text="bad key"))
    with pytest.raises(llm.LLMError, match="-> 401: bad key"):
        llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert len(transport.posts) == 1
    assert _hermetic == []


def test_openai_compat_records_usage_and_strips_content(keyed, transport, tmp_path):
    ledger = tmp_path / "spend.jsonl"
    transport.post_queue.append(chat_ok("  padded  ", prompt_tokens=1_000_000,
                                        completion_tokens=1_000_000))
    c = llm.Client(keyed, ledger=ledger, tag="backlog")
    assert c.complete("ollama-cloud:gpt-oss:120b", "s", "u") == "padded"
    assert c.usage.calls == 1
    assert c.usage.input_tokens == 1_000_000
    assert c.usage.cost_usd == pytest.approx(0.75)  # price(): 1M*0.15 + 1M*0.60
    rec = json.loads(ledger.read_text().splitlines()[-1])
    assert rec["model"] == "ollama-cloud:gpt-oss:120b"
    assert rec["cost_usd"] == pytest.approx(0.75)
    assert rec["tag"] == "backlog"


def test_openai_compat_handles_a_missing_usage_block(keyed, transport):
    transport.post_queue.append(FakeResponse(payload={"choices": [{"message": {"content": "x"}}]}))
    c = llm.Client(keyed)
    assert c.complete("ollama-cloud:gpt-oss:120b", "s", "u") == "x"
    assert (c.usage.input_tokens, c.usage.output_tokens) == (0, 0)


def test_openai_compat_sends_images_as_data_uri_parts(keyed, transport, tmp_path):
    img = tmp_path / "frame.jpg"
    img.write_bytes(b"\xff\xd8\xff\x00img")
    transport.post_queue.append(chat_ok())
    llm.Client(keyed).complete("ollama-cloud:gpt-oss:120b", "s", "look", images=[img])
    content = transport.posts[0]["json"]["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "look"}
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# --- 8. _claude_code ---------------------------------------------------------

def test_claude_code_hides_anthropic_keys_and_runs_in_a_temp_cwd(cfg, cc, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-must-not-be-used")
    cc["queue"].append(_Completed(stdout=json.dumps({"result": "ok", "usage": {}})))
    llm.Client(cfg).complete("claude-code:haiku", "SYS", "USER")
    call = cc["calls"][0]
    assert "ANTHROPIC_API_KEY" not in call["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in call["env"]
    assert call["env"].get("PATH") == os.environ.get("PATH")  # the rest of the env survives
    assert call["cwd_existed"] is True
    assert os.path.basename(call["cwd"]).startswith("ytdigest-cc-")
    assert call["input"] == "SYS\n\nUSER"
    assert call["timeout"] == 1800


def test_claude_code_books_subscription_calls_at_zero_cost(keyed, cc, tmp_path):
    ledger = tmp_path / "spend.jsonl"
    cc["queue"].append(_Completed(stdout=json.dumps({
        "result": " hello ",
        "total_cost_usd": 0.0421,
        "usage": {"input_tokens": 7, "output_tokens": 3,
                  "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20},
    })))
    c = llm.Client(keyed, ledger=ledger, tag="manual")
    assert c.complete("claude-code:sonnet", "s", "u") == "hello"
    d = c.usage.by_model["claude-code:sonnet"]
    assert (d["input_tokens"], d["output_tokens"]) == (7, 3)
    assert (d["cache_read_tokens"], d["cache_write_tokens"]) == (100, 20)
    assert c.usage.cost_usd == 0.0  # subscription: not billed
    assert d["api_equiv_usd"] == pytest.approx(0.0421)
    rec = json.loads(ledger.read_text().splitlines()[-1])
    assert rec["cost_usd"] == 0.0
    assert rec["api_equiv_usd"] == pytest.approx(0.0421)
    assert rec["cache_read"] == 100


def test_claude_code_passes_images_as_readable_dirs(keyed, cc, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "1.jpg").write_bytes(b"x")
    (b / "2.jpg").write_bytes(b"y")
    cc["queue"].append(_Completed(stdout=json.dumps({"result": "seen", "usage": {}})))
    llm.Client(keyed).complete("claude-code:haiku", "s", "u", images=[a / "1.jpg", b / "2.jpg"])
    cmd, prompt = cc["calls"][0]["cmd"], cc["calls"][0]["input"]
    assert "--allowedTools" in cmd and cmd[cmd.index("--allowedTools") + 1] == "Read"
    assert cmd.count("--add-dir") == 2
    assert str(a.resolve()) in cmd and str(b.resolve()) in cmd
    assert "Images to look at" in prompt
    assert str((a / "1.jpg").resolve()) in prompt


def test_claude_code_limit_exit_raises_limit_error(keyed, cc):
    cc["queue"].append(_Completed(returncode=1, stdout=json.dumps(
        {"result": "Claude AI usage limit reached|1730000000"})))
    with pytest.raises(llm.LimitError, match="usage limit reached"):
        llm.Client(keyed).complete("claude-code:haiku", "s", "u")


def test_claude_code_other_exit_raises_plain_llm_error_with_raw_output(keyed, cc):
    # stdout is not JSON: the raw stdout/stderr is what reaches the operator
    cc["queue"].append(_Completed(returncode=2, stdout="CLI exploded", stderr="traceback here"))
    with pytest.raises(llm.LLMError) as err:
        llm.Client(keyed).complete("claude-code:haiku", "s", "u")
    assert not isinstance(err.value, llm.LimitError)
    assert "CLI exploded" in str(err.value)
    assert "traceback here" in str(err.value)


def test_claude_code_error_json_maps_limit_text_to_limit_error(keyed, cc):
    cc["queue"].append(_Completed(stdout=json.dumps(
        {"is_error": True, "result": "5-hour limit reached ∙ resets 3pm"})))
    with pytest.raises(llm.LimitError):
        llm.Client(keyed).complete("claude-code:haiku", "s", "u")


def test_claude_code_error_json_maps_other_text_to_llm_error(keyed, cc):
    cc["queue"].append(_Completed(stdout=json.dumps(
        {"is_error": True, "result": "context window exceeded"})))
    with pytest.raises(llm.LLMError) as err:
        llm.Client(keyed).complete("claude-code:haiku", "s", "u")
    assert not isinstance(err.value, llm.LimitError)
    assert "context window exceeded" in str(err.value)


# --- 9. _ledger --------------------------------------------------------------

def test_ledger_without_a_path_writes_nothing(keyed, transport, tmp_path):
    transport.post_queue.append(chat_ok())
    c = llm.Client(keyed)  # no ledger
    c.complete("ollama-cloud:gpt-oss:120b", "s", "u")
    assert c.ledger is None
    assert list(tmp_path.rglob("*.jsonl")) == []  # nothing hit the disk
    assert c.usage.calls == 1  # usage is still tracked in-memory


def test_ledger_appends_one_json_line_and_creates_parents(keyed, transport, tmp_path):
    ledger = tmp_path / "nested" / "deeper" / "spend.jsonl"
    transport.post_queue += [chat_ok(), chat_ok()]
    c = llm.Client(keyed, ledger=ledger, tag="backlog")
    c.complete("ollama-cloud:gpt-oss:120b", "s", "u")
    c.complete("ollama-cloud:gpt-oss:120b", "s", "u")
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # append, never overwrite
    rec = json.loads(lines[0])
    assert set(rec) == {"ts", "tag", "model", "input_tokens", "output_tokens", "cost_usd"}
    assert rec["tag"] == "backlog"


# --- 10. spent_today ---------------------------------------------------------

def test_spent_today_skips_unparsable_lines(tmp_path):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    ledger = tmp_path / "spend.jsonl"
    ledger.write_text("\n".join([
        "not json at all",
        json.dumps({"tag": "backlog", "ts": f"{today}T01:00:00+00:00", "cost_usd": 0.25}),
        json.dumps({"tag": "backlog", "ts": f"{today}T02:00:00+00:00", "cost_usd": 0.5}),
        json.dumps({"tag": "backlog", "ts": "2020-01-01T00:00:00+00:00", "cost_usd": 9.0}),
        json.dumps({"tag": "manual", "ts": f"{today}T03:00:00+00:00", "cost_usd": 7.0}),
        json.dumps({"tag": "backlog", "ts": f"{today}T04:00:00+00:00"}),  # no cost_usd
    ]) + "\n", encoding="utf-8")
    assert llm.spent_today(ledger, "backlog") == pytest.approx(0.75)


def test_spent_today_returns_zero_for_a_missing_ledger(tmp_path):
    assert llm.spent_today(tmp_path / "absent.jsonl", "backlog") == 0.0


# --- 11. available_models ----------------------------------------------------

def test_available_models_returns_the_provider_list(keyed, transport):
    transport.get_queue.append(FakeResponse(payload={"data": [{"id": "glm-5.3-flash"},
                                                             {"id": ""}, {"nope": 1}]}))
    assert llm.available_models(keyed, "ollama-cloud") == {"glm-5.3-flash"}
    assert transport.gets[0]["url"] == "https://ollama.com/v1/models"
    assert transport.gets[0]["headers"]["Authorization"] == "Bearer test-key-not-a-secret"
    assert transport.gets[0]["timeout"] == 20


def test_available_models_non_ok_returns_none_and_is_cached(keyed, transport):
    transport.get_queue.append(FakeResponse(status_code=500, payload={}))
    assert llm.available_models(keyed, "ollama-cloud") is None
    assert len(transport.gets) == 1
    # second call: no second request
    assert llm.available_models(keyed, "ollama-cloud") is None
    assert len(transport.gets) == 1


def test_available_models_empty_list_returns_none(keyed, transport):
    transport.get_queue.append(FakeResponse(payload={"data": []}))
    assert llm.available_models(keyed, "ollama-cloud") is None


def test_available_models_network_error_returns_none_and_is_cached(keyed, transport):
    transport.get_queue.append(OSError("connection refused"))
    assert llm.available_models(keyed, "ollama-cloud") is None
    assert llm.available_models(keyed, "ollama-cloud") is None
    assert len(transport.gets) == 1  # the failure is cached, no retry storm


def test_available_models_cache_hit_skips_the_network(keyed, transport):
    llm._MODEL_CACHE.update({"groq": {"llama-3.3-70b-versatile"}})
    assert llm.available_models(keyed, "groq") == {"llama-3.3-70b-versatile"}
    assert transport.gets == []


def test_available_models_unknown_provider_returns_none(keyed, transport):
    assert llm.available_models(keyed, "not-a-provider") is None
    assert transport.gets == []
