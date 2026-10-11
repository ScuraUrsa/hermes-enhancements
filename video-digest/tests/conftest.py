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
