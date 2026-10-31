import copy
import json
import socket
import subprocess

import pytest

from ytdigest import config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Hermetic config: pure DEFAULTS, no operator files.

    YTDIGEST_CONFIG points at an empty file inside tmp_path, so config_path()
    stops there instead of falling through to ~/.hermes (that silent fallthrough
    used to leak Filip's real config into every test).
    HERMES_REAL_HOME is redirected so nothing reads the operator's ~/.hermes.
    """
    monkeypatch.setenv("YTDIGEST_DATA_DIR", str(tmp_path / "data"))
    # Merge resolution #46 x #47: #47's guard tests require YTDIGEST_CONFIG to name a
    # real file (they assert config_path() resolves inside tmp_path), while #46 wants
    # pure DEFAULTS without reading operator state. An empty YAML file satisfies both:
    # config_path() stops here and load() only merges DEFAULTS.
    pinned = tmp_path / "config.yaml"
    pinned.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(pinned))
    monkeypatch.setenv("HERMES_REAL_HOME", str(tmp_path / "home"))
    c = config.load(None)
    assert set(c) == set(config.DEFAULTS), "cfg fixture must yield pure defaults"
    # Neutralise the two defaults that reach outside the sandbox (same intent as master):
    # topic overrides have their own tests, and the "Przetworzone przez Hermesa" playlist
    # step must never run — it would call googleapis with Filip's real token.
    c["topic_routes"] = {}
    c["processed_playlist"] = {"enabled": False}
    # DEFAULTS bakes HERMES_HOME at import time, so pointing HERMES_REAL_HOME at tmp_path
    # is not enough: name the operator's account/cookie directories away explicitly.
    # `cookies_file` is a template ({account}) that pipeline/tests format themselves.
    c["google_accounts_dir"] = str(tmp_path / "google-accounts")
    c["cookies_file"] = str(tmp_path / "cookies" / "{account}.txt")
    # routing.load() falls back to the sibling vbench/routing.json when routing_file
    # is empty. That table only landed on master after these test branches were cut,
    # and it would silently swap the default vision model (gemma4:31b) for a vbench
    # pick, so keep the fixture on DEFAULT_ROUTING. A missing path is enough — no
    # operator file is read.
    c["routing_file"] = str(tmp_path / "no-routing.json")
    return c


@pytest.fixture(scope="session")
def synthetic_video(tmp_path_factory):
    """40 s video: four 10 s scenes in different colours with text, plus a tone."""
    d = tmp_path_factory.mktemp("vid")
    out = d / "video.mp4"
    parts = []
    for i, colour in enumerate(["red", "blue", "green", "blue"]):
        p = d / f"p{i}.mp4"
        subprocess.run([
            "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=320x240:d=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-vf", f"drawbox=x={20 + i * 60}:y=60:w=80:h=80:color=white:t=fill",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)], check=True)
        parts.append(p)
    lst = d / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


@pytest.fixture(autouse=True)
def _no_live_model_list(monkeypatch):
    """Tests never ask a provider which models exist."""
    from ytdigest import llm
    monkeypatch.setattr(llm, "_MODEL_CACHE", {"ollama-cloud": None})


# --- suite-wide network fence -------------------------------------------------
# Hermetic `cfg` is not enough on its own: `backlog.token_for()` prefers the
# GOOGLE_<ALIAS>_TOKEN_JSON environment variables over the file in
# google_accounts_dir, so a test that reaches the YouTube playlist step would spend
# Filip's real credentials and write to his real "Przetworzone przez Hermesa" playlist.
# This fence is the backstop for the whole suite: any DNS lookup or connection aimed at
# a non-loopback host fails *the test that attempted it*. Loopback stays available
# because tests/test_server.py runs a real HTTP server on 127.0.0.1.
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "localhost.localdomain", "ip6-localhost"}


def _loopback_target(address) -> bool:
    """True for AF_UNIX paths, wildcard binds and IPv4/IPv6 loopback literals."""
    if isinstance(address, (str, bytes)):
        return True                     # AF_UNIX: a path, not a host
    if not isinstance(address, tuple) or not address:
        return True
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not host:
        return True                     # bind(("", port)) / getaddrinfo(None, ...)
    return host in LOOPBACK_HOSTS or str(host).startswith("127.")


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch):
    """No DNS, no TCP/UDP to anything but loopback: a leak fails loudly, not silently.

    Attempts are both raised (so no real traffic leaves the box) and collected, because
    production code legitimately swallows network errors (`pipeline.process` treats a
    playlist hiccup as non-fatal). The collected list is asserted at teardown so a
    swallowed leak still fails the test that caused it.
    """
    attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def deny(what, address):
        attempts.append(f"{what} -> {address!r}")
        raise AssertionError(
            f"network access attempted in a hermetic test: {what} -> {address!r}; "
            "fake the transport instead of letting a test reach a real service"
        )

    def connect(self, address, *args, **kwargs):
        if not _loopback_target(address):
            deny("socket.connect", address)
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if not _loopback_target(address):
            deny("socket.connect_ex", address)
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, port, *args, **kwargs):
        if not _loopback_target((host, port)):
            deny("socket.getaddrinfo", (host, port))
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
    if attempts:
        pytest.fail("non-loopback network access attempted: " + "; ".join(attempts), pytrace=False)



# --- fake provider transport (ytdigest.llm contract tests) -------------------
# llm.py reaches OpenAI-compatible providers through `requests`; these helpers hand
# every call a queued response instead of opening a socket, and record the request
# so a test can assert on URL, headers and body.


class FakeResponse:
    """Minimal `requests.Response` stand-in: status_code, .text, .ok and .json()."""

    def __init__(self, status_code=200, payload=None, text=None, ok=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.ok = (200 <= status_code < 400) if ok is None else ok

    def json(self):
        if self._payload is None:
            raise ValueError("response has no JSON body")
        return copy.deepcopy(self._payload)


def chat_ok(content="answer", prompt_tokens=10, completion_tokens=5):
    """A successful /chat/completions body with the OpenAI usage block."""
    return FakeResponse(payload={
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    })


class FakeTransport:
    """Queues for requests.post/get; every call is recorded for assertions."""

    def __init__(self):
        self.posts = []
        self.gets = []
        self.post_queue = []
        self.get_queue = []

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002 - mirrors requests
        self.posts.append({"url": url, "headers": dict(headers or {}),
                           "json": copy.deepcopy(json), "timeout": timeout})
        return self._next(self.post_queue, "post")

    def get(self, url, headers=None, timeout=None):
        self.gets.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        return self._next(self.get_queue, "get")

    @staticmethod
    def _next(queue, kind):
        if not queue:
            raise AssertionError(f"unexpected requests.{kind} call (nothing queued)")
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def transport(monkeypatch):
    """requests.post/get served from queues: no socket, no retries in real time."""
    import requests
    t = FakeTransport()
    monkeypatch.setattr(requests, "post", t.post)
    monkeypatch.setattr(requests, "get", t.get)
    return t
