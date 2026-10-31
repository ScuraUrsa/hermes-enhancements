import copy
import json
import subprocess
from pathlib import Path

import pytest

from ytdigest import config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("YTDIGEST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.yaml"))
    c = config.load(None)
    c["routing_file"] = str(tmp_path / "no-routing.json")
    c["topic_routes"] = {}  # topic overrides have their own tests
    c["processed_playlist"] = {"enabled": False}
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
