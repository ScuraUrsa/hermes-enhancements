"""Contract tests for the MCP stdio bridge (`ytdigest/mcp_bridge.py`).

The bridge is what Claude Desktop / Hermes on Filip's laptop actually talks to:
it turns JSON-RPC lines on stdin into HTTP calls against `ytdigest serve` over
Tailscale.  Nothing here touches the network -- `urllib.request.urlopen` is
replaced by a recorder, `time` by a fake clock and `socket` is hard-blocked in
the hermeticity test -- so the suite proves the contract (default base URL,
token placement, GET vs POST, 4xx/5xx/URLError propagation, polling and the
JSON-RPC envelope) without a server.
"""

from __future__ import annotations

import io
import json
import runpy
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from ytdigest import mcp_bridge

MODULE_PATH = Path(mcp_bridge.__file__)

STILL_WORKING = "Hermes is still working on it; ask again with get_youtube_report in a few minutes."


# --------------------------------------------------------------------------- #
# fakes: HTTP transport, response, clock
# --------------------------------------------------------------------------- #

class FakeResponse:
    """Just enough of `http.client.HTTPResponse` for `_http()`."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":  # noqa: PYI034,UP037 -- py3.9-era tests, no typing.Self
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


class Transport:
    """Records every `Request` handed to `urlopen` and replays canned bodies.

    Items may be `bytes` (returned as the response body) or `Exception`
    instances (raised instead of returning, like a real transport failure).
    The last item is reused once the plan is exhausted.
    """

    def __init__(self, *plan: object):
        assert plan, "the transport needs at least one response"
        self._plan = list(plan)
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[object] = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        self.timeouts.append(timeout)
        item = self._plan.pop(0) if len(self._plan) > 1 else self._plan[0]
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    # -- assertions helpers ------------------------------------------------- #
    def urls(self) -> list[str]:
        return [r.full_url for r in self.requests]

    def paths(self) -> list[str]:
        return [urllib.parse.urlsplit(r.full_url).path for r in self.requests]

    def methods(self) -> list[str]:
        return [r.get_method() for r in self.requests]


class Clock:
    """Fake `time` module: `sleep()` moves the clock forward instead of waiting."""

    def __init__(self, start: float = 1000.0, advance_on_sleep: bool = True):
        self.now = start
        self.sleeps: list[float] = []
        self._advance = advance_on_sleep

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self._advance:
            self.now += seconds


def body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


QUEUED = body({"status": "queued"})
DONE = body({"status": "done", "report_md": "# Report", "notion_url": "https://notion.so/x"})


@pytest.fixture
def install(monkeypatch):
    """`install(payload, ...)` -> Transport patched in, env cleared by default."""

    def _install(*plan, clock: Clock | None = None) -> Transport:
        transport = Transport(*plan)
        monkeypatch.setattr(mcp_bridge.urllib.request, "urlopen", transport)
        if clock is not None:
            monkeypatch.setattr(mcp_bridge, "time", clock)
        return transport

    monkeypatch.delenv("YTDIGEST_URL", raising=False)
    monkeypatch.delenv("YTDIGEST_TOKEN", raising=False)
    return _install


def read_rpc(capsys) -> list[dict]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def run_main(monkeypatch, *lines: str | dict) -> None:
    text = "".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in lines)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    mcp_bridge.main()


# --------------------------------------------------------------------------- #
# _http(): base URL, token, GET vs POST, timeouts, empty body
# --------------------------------------------------------------------------- #

def test_get_uses_default_base_url_when_env_is_unset(install):
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert transport.urls() == [
        "http://127.0.0.1:8765/report?url=abc&token="
    ]


def test_get_uses_env_base_url_and_strips_trailing_slash(install, monkeypatch):
    monkeypatch.setenv("YTDIGEST_URL", "http://100.66.185.39:8765/")
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert transport.urls() == ["http://100.66.185.39:8765/report?url=abc&token="]


def test_get_appends_token_from_env_to_query(install, monkeypatch):
    monkeypatch.setenv("YTDIGEST_TOKEN", "s3cret")
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "abc"})

    query = transport.requests[0].full_url.split("?", 1)[1]
    assert "token=s3cret" in query
    # the token is a query parameter next to the caller's params, not a header
    assert transport.requests[0].get_header("Authorization") is None


def test_get_sends_empty_token_when_env_is_unset(install):
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert "token=" in transport.requests[0].full_url
    assert transport.methods() == ["GET"]


def test_get_url_encodes_caller_params(install):
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "https://youtu.be/a b?t=1&x=2"})

    query = transport.requests[0].full_url.split("?", 1)[1]
    assert "url=https%3A%2F%2Fyoutu.be%2Fa+b%3Ft%3D1%26x%3D2" in query


def test_post_sends_json_body_with_content_type(install, monkeypatch):
    monkeypatch.setenv("YTDIGEST_URL", "http://vm:8765")
    transport = install(body({"status": "queued"}))

    mcp_bridge._http("POST", "/digest", {"url": "abc"})

    req = transport.requests[0]
    assert req.full_url == "http://vm:8765/digest"   # no query string on POST
    assert req.get_method() == "POST"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {"url": "abc", "token": ""}


def test_post_puts_token_in_json_body(install, monkeypatch):
    monkeypatch.setenv("YTDIGEST_TOKEN", "s3cret")
    transport = install(body({"status": "queued"}))

    mcp_bridge._http("POST", "/digest", {"url": "abc"})

    req = transport.requests[0]
    assert json.loads(req.data)["token"] == "s3cret"
    assert "token" not in req.full_url


def test_urlopen_is_called_with_a_30_second_timeout(install):
    transport = install(DONE)

    mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert transport.timeouts == [30]


def test_empty_response_body_is_parsed_as_empty_dict(install):
    install(b"")

    assert mcp_bridge._http("GET", "/report", {"url": "abc"}) == {}


def test_response_body_is_returned_as_dict(install):
    install(body({"status": "done", "report_md": "# x"}))

    assert mcp_bridge._http("GET", "/report", {"url": "abc"}) == {"status": "done", "report_md": "# x"}


# --------------------------------------------------------------------------- #
# _http(): HTTP and transport failures surface to the caller
# --------------------------------------------------------------------------- #

def test_http_404_propagates_as_http_error(install):
    err = urllib.error.HTTPError("http://vm/report", 404, "Not Found", {}, io.BytesIO(b"nope"))
    install(err)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert excinfo.value.code == 404
    assert excinfo.value.read() == b"nope"


def test_http_500_propagates_as_http_error(install):
    err = urllib.error.HTTPError("http://vm/report", 500, "Server Error", {}, io.BytesIO(b"boom"))
    install(err)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        mcp_bridge._http("POST", "/digest", {"url": "abc"})

    assert excinfo.value.code == 500


def test_url_error_propagates_when_the_vm_is_unreachable(install):
    install(urllib.error.URLError("Connection refused"))

    with pytest.raises(urllib.error.URLError) as excinfo:
        mcp_bridge._http("GET", "/report", {"url": "abc"})

    assert "Connection refused" in str(excinfo.value.reason)


# --------------------------------------------------------------------------- #
# _text(): what the model sees
# --------------------------------------------------------------------------- #

def test_text_prefers_report_markdown_and_appends_notion_link():
    out = mcp_bridge._text({"status": "done", "report_md": "# Report",
                            "notion_url": "https://notion.so/x"})

    assert out == "# Report\n\nNotion: https://notion.so/x"


def test_text_returns_bare_markdown_without_notion_link():
    assert mcp_bridge._text({"status": "done", "report_md": "# Report"}) == "# Report"


def test_text_reports_status_when_there_is_no_markdown():
    assert mcp_bridge._text({"status": "queued"}) == "status: queued"


def test_text_reports_error_next_to_status():
    assert mcp_bridge._text({"status": "failed", "error": "no captions"}) == "status: failed, error: no captions"


def test_text_ignores_empty_report_markdown():
    assert mcp_bridge._text({"status": "failed", "report_md": "", "error": "x"}) == "status: failed, error: x"


# --------------------------------------------------------------------------- #
# TOOLS: the schemas Claude Desktop shows to the model
# --------------------------------------------------------------------------- #

def test_tools_exposes_exactly_the_two_public_tools():
    assert [t["name"] for t in mcp_bridge.TOOLS] == ["digest_youtube_video", "get_youtube_report"]


def test_digest_tool_schema_requires_url_and_defaults_wait_seconds_to_600():
    digest = next(t for t in mcp_bridge.TOOLS if t["name"] == "digest_youtube_video")

    schema = digest["inputSchema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["url"]
    assert schema["properties"]["url"]["type"] == "string"
    assert schema["properties"]["wait_seconds"] == {"type": "integer", "default": 600}
    assert digest["description"].strip()


def test_report_tool_schema_only_takes_a_url():
    report = next(t for t in mcp_bridge.TOOLS if t["name"] == "get_youtube_report")

    assert report["inputSchema"] == {
        "type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    assert report["description"].strip()


# --------------------------------------------------------------------------- #
# call(): get_youtube_report
# --------------------------------------------------------------------------- #

def test_get_youtube_report_does_one_get_and_no_post(install, monkeypatch):
    monkeypatch.setenv("YTDIGEST_TOKEN", "s3cret")
    transport = install(DONE)

    out = mcp_bridge.call("get_youtube_report", {"url": "abc"})

    assert out == "# Report\n\nNotion: https://notion.so/x"
    assert transport.methods() == ["GET"]
    assert transport.paths() == ["/report"]
    assert transport.requests[0].full_url.endswith("/report?url=abc&token=s3cret")


def test_get_youtube_report_does_not_start_a_digest_for_a_missing_report(install):
    transport = install(body({"status": "missing"}))

    assert mcp_bridge.call("get_youtube_report", {"url": "abc"}) == "status: missing"
    assert transport.methods() == ["GET"]


# --------------------------------------------------------------------------- #
# call(): digest_youtube_video
# --------------------------------------------------------------------------- #

def test_digest_returns_an_existing_report_without_queueing_or_polling(install):
    clock = Clock()
    transport = install(DONE, clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 60})

    assert out == "# Report\n\nNotion: https://notion.so/x"
    assert transport.methods() == ["GET"]
    assert clock.sleeps == []


def test_digest_accepts_artistic_as_a_finished_report(install):
    clock = Clock()
    transport = install(body({"status": "artistic", "report_md": "# Poem"}), clock=clock)

    assert mcp_bridge.call("digest_youtube_video", {"url": "abc"}) == "# Poem"
    assert transport.methods() == ["GET"]
    assert clock.sleeps == []


def test_digest_queues_then_polls_until_done(install):
    clock = Clock()
    transport = install(QUEUED, body({"ok": True}), QUEUED,
                        body({"status": "done", "report_md": "# Late"}), clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 600})

    assert out == "# Late"
    assert transport.methods() == ["GET", "POST", "GET", "GET"]
    assert transport.paths() == ["/report", "/digest", "/report", "/report"]
    assert json.loads(transport.requests[1].data) == {"url": "abc", "token": ""}
    assert clock.sleeps == [15, 15]


def test_digest_stops_polling_on_failed_and_reports_the_error(install):
    clock = Clock()
    install(QUEUED, b"{}", body({"status": "failed", "error": "no captions"}), clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 600})

    assert out == "status: failed, error: no captions"
    assert clock.sleeps == [15]


def test_digest_returns_still_working_when_the_deadline_is_exhausted(install):
    clock = Clock()
    transport = install(QUEUED, b"{}", QUEUED, clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 1})

    assert out == STILL_WORKING
    assert transport.methods() == ["GET", "POST", "GET"]
    assert clock.sleeps == [15]


def test_digest_wait_seconds_zero_returns_immediately_without_polling(install):
    """wait_seconds=0 means "do not wait": queue the digest and answer at once."""
    clock = Clock()
    transport = install(QUEUED, b"{}", QUEUED, clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 0})

    assert out == STILL_WORKING
    assert transport.methods() == ["GET", "POST"]       # queued, never polled
    assert clock.sleeps == []


def test_digest_negative_wait_seconds_is_treated_as_no_wait(install):
    clock = Clock()
    transport = install(QUEUED, b"{}", QUEUED, clock=clock)

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": -5})

    assert out == STILL_WORKING
    assert transport.methods() == ["GET", "POST"]
    assert clock.sleeps == []


def test_digest_defaults_to_a_600_second_budget_when_wait_seconds_is_absent(install):
    clock = Clock()
    transport = install(QUEUED, clock=clock)   # every poll keeps saying "queued"

    out = mcp_bridge.call("digest_youtube_video", {"url": "abc"})

    assert out == STILL_WORKING
    # 600 s budget, one poll every 15 s -> 40 polls, then the deadline is reached
    assert len(clock.sleeps) == 40
    assert set(clock.sleeps) == {15}
    assert transport.methods() == ["GET", "POST"] + ["GET"] * 40


def test_digest_explicit_none_wait_seconds_falls_back_to_the_default(install):
    clock = Clock()
    install(QUEUED, clock=clock)

    assert mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": None}) == STILL_WORKING
    assert len(clock.sleeps) == 40


def test_digest_polls_every_fifteen_seconds(install):
    clock = Clock()
    install(QUEUED, b"{}", QUEUED, QUEUED, QUEUED, DONE, clock=clock)

    mcp_bridge.call("digest_youtube_video", {"url": "abc", "wait_seconds": 600})

    assert clock.sleeps == [15, 15, 15, 15]   # one sleep per poll, 15 s each, never a busy loop


def test_missing_url_raises_key_error(install):
    install(DONE)

    with pytest.raises(KeyError):
        mcp_bridge.call("digest_youtube_video", {})


def test_unknown_tool_name_is_treated_as_a_digest(install):
    """Dispatcher contract: anything that is not get_youtube_report goes the digest route."""
    clock = Clock()
    transport = install(DONE, clock=clock)

    assert mcp_bridge.call("no_such_tool", {"url": "abc"}) == "# Report\n\nNotion: https://notion.so/x"
    assert transport.methods() == ["GET"]


# --------------------------------------------------------------------------- #
# main(): the JSON-RPC stdio envelope
# --------------------------------------------------------------------------- #

def test_main_initialize_echoes_the_client_protocol_version(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-03-26"}})

    reply = read_rpc(capsys)[0]
    assert reply["jsonrpc"] == "2.0"
    assert reply["id"] == 1
    assert reply["result"]["protocolVersion"] == "2025-03-26"
    assert reply["result"]["capabilities"] == {"tools": {}}
    assert reply["result"]["serverInfo"] == {"name": "youtube-digest", "version": "0.1"}


def test_main_initialize_defaults_the_protocol_version(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert read_rpc(capsys)[0]["result"]["protocolVersion"] == "2025-06-18"


def test_main_tools_list_returns_the_tool_schemas(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    reply = read_rpc(capsys)[0]
    assert reply["id"] == 2
    assert reply["result"] == {"tools": mcp_bridge.TOOLS}


def test_main_ping_returns_an_empty_result(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 3, "method": "ping"})

    assert read_rpc(capsys)[0] == {"jsonrpc": "2.0", "id": 3, "result": {}}


def test_main_unknown_method_returns_jsonrpc_error(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 4, "method": "resources/list"})

    reply = read_rpc(capsys)[0]
    assert "result" not in reply
    assert reply["id"] == 4
    assert reply["error"] == {"code": -32601, "message": "method not found"}


def test_main_ignores_notifications_without_an_id(monkeypatch, capsys):
    run_main(monkeypatch, {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 5, "method": "ping"})

    replies = read_rpc(capsys)
    assert [r["id"] for r in replies] == [5]


def test_main_skips_malformed_json_lines(monkeypatch, capsys):
    run_main(monkeypatch, "{not json", "", '{"jsonrpc": "2.0", "id": 6, "method": "ping"}')

    assert [r["id"] for r in read_rpc(capsys)] == [6]


def test_main_tools_call_wraps_the_result_as_text_content(install, monkeypatch, capsys):
    install(DONE)
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                           "params": {"name": "get_youtube_report", "arguments": {"url": "abc"}}})

    result = read_rpc(capsys)[0]["result"]
    assert result == {"content": [{"type": "text", "text": "# Report\n\nNotion: https://notion.so/x"}]}


def test_main_tools_call_without_params_returns_is_error(install, monkeypatch, capsys):
    install(DONE)
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 8, "method": "tools/call"})

    result = read_rpc(capsys)[0]["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("error: ")
    assert "url" in result["content"][0]["text"]


def test_main_tools_call_turns_unreachable_vm_into_is_error(install, monkeypatch, capsys):
    install(urllib.error.URLError("Connection refused"))
    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                           "params": {"name": "get_youtube_report", "arguments": {"url": "abc"}}})

    result = read_rpc(capsys)[0]["result"]
    assert result["isError"] is True
    assert "Connection refused" in result["content"][0]["text"]


def test_main_answers_every_request_in_order(monkeypatch, capsys):
    run_main(monkeypatch,
             {"jsonrpc": "2.0", "id": 10, "method": "ping"},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 11, "method": "tools/list"},
             {"jsonrpc": "2.0", "id": 12, "method": "bogus"})

    replies = read_rpc(capsys)
    assert [r.get("id") for r in replies] == [10, 11, 12]
    assert "tools" in replies[1]["result"]
    assert replies[2]["error"]["code"] == -32601


def test_module_entrypoint_runs_main(monkeypatch, capsys):
    """`python mcp_bridge.py` is how Claude Desktop launches it: the __main__ guard must fire."""
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"jsonrpc": "2.0", "id": 13, "method": "ping"}\n'))

    runpy.run_path(str(MODULE_PATH), run_name="__main__")

    assert read_rpc(capsys)[0] == {"jsonrpc": "2.0", "id": 13, "result": {}}


# --------------------------------------------------------------------------- #
# hermeticity: no socket may be opened while the bridge serves a request
# --------------------------------------------------------------------------- #

def test_bridge_opens_no_sockets_during_a_full_digest(install, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("the bridge must not open a socket under test")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    clock = Clock()
    install(QUEUED, b"{}", DONE, clock=clock)

    run_main(monkeypatch, {"jsonrpc": "2.0", "id": 14, "method": "tools/call",
                           "params": {"name": "digest_youtube_video",
                                      "arguments": {"url": "abc", "wait_seconds": 60}}})

    result = read_rpc(capsys)[0]["result"]
    assert "isError" not in result          # blocked socket is never reached: urlopen stayed faked
    assert "# Report" in result["content"][0]["text"]
    assert clock.sleeps == [15]        # the real 15 s wait was recorded, not slept through
