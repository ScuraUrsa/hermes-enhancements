import subprocess

import pytest

from ytdigest import config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Hermetic config: pure DEFAULTS, no operator files.

    YTDIGEST_CONFIG points at a missing file, which config_path() treats as
    "no config file" instead of falling through to ~/.hermes (that silent
    fallthrough used to leak Filip's real config into every test).
    HERMES_REAL_HOME is redirected so nothing reads the operator's ~/.hermes.
    """
    monkeypatch.setenv("YTDIGEST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.yaml"))
    monkeypatch.setenv("HERMES_REAL_HOME", str(tmp_path / "home"))
    c = config.load(None)
    assert set(c) == set(config.DEFAULTS), "cfg fixture must yield pure defaults"
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
