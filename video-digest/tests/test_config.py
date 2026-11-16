"""Tests for ytdigest.config: precedence, path resolution, merging."""
import json

from ytdigest import config


def test_precedence_defaults_file_overrides(tmp_path):
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"report_language": "en", "frames_per_min": 3.0}), encoding="utf-8")
    cfg = config.load(path=f, overrides={"frames_per_min": 9.0})
    assert cfg["report_language"] == "en"   # file beat default
    assert cfg["frames_per_min"] == 9.0     # override beat file
    assert cfg["max_frames"] == 60          # untouched default


import sys

import pytest


class _FakeYaml:
    """Minimal stand-in for PyYAML: flat `key: value` lines only."""

    @staticmethod
    def safe_load(text):
        out = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
        return out


@pytest.fixture
def fake_yaml(monkeypatch):
    monkeypatch.setitem(sys.modules, "yaml", _FakeYaml)


def _default_home(tmp_path, value="en"):
    home = tmp_path / "home"
    d = home / ".hermes" / "ytdigest"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(f"report_language: {value}\n", encoding="utf-8")
    return home


def test_explicit_path_beats_env(tmp_path, monkeypatch):
    env_file = tmp_path / "env.json"
    env_file.write_text(json.dumps({"report_language": "en"}), encoding="utf-8")
    explicit = tmp_path / "explicit.json"
    explicit.write_text(json.dumps({"report_language": "de"}), encoding="utf-8")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(env_file))
    assert config.load(path=explicit)["report_language"] == "de"


def test_env_config_beats_default_file(tmp_path, monkeypatch, fake_yaml):
    home = _default_home(tmp_path, "en")
    monkeypatch.setenv("HERMES_REAL_HOME", str(home))
    env_file = tmp_path / "env.json"
    env_file.write_text(json.dumps({"report_language": "de"}), encoding="utf-8")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(env_file))
    assert config.load()["report_language"] == "de"


def test_ytdigest_home_fallback(tmp_path, monkeypatch, fake_yaml):
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.yaml").write_text("report_language: en\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_REAL_HOME", str(tmp_path / "nohome"))
    monkeypatch.setenv("YTDIGEST_HOME", str(base))
    monkeypatch.delenv("YTDIGEST_CONFIG", raising=False)
    assert config.load()["report_language"] == "en"


def test_env_config_set_but_missing_means_defaults(tmp_path, monkeypatch, fake_yaml):
    home = _default_home(tmp_path, "en")
    monkeypatch.setenv("HERMES_REAL_HOME", str(home))
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.json"))
    assert config.load()["report_language"] == "pl"  # no fallthrough to the default file


def test_env_read_at_call_time(tmp_path, monkeypatch):
    f = tmp_path / "c.json"
    f.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(f))  # set long after the module was imported
    assert config.config_path() == f
    monkeypatch.delenv("YTDIGEST_CONFIG")
    h = tmp_path / "h"
    h.mkdir()
    (h / "config.yaml").write_text("a: 1\n", encoding="utf-8")
    monkeypatch.setenv("YTDIGEST_HOME", str(h))
    assert config.config_path() == h / "config.yaml"


def _no_pyyaml(monkeypatch):
    # sys.modules["yaml"] = None makes any `import yaml` raise ImportError,
    # exactly like an interpreter without PyYAML installed.
    monkeypatch.setitem(sys.modules, "yaml", None)


def test_missing_pyyaml_with_yaml_file_means_clear_error_not_crash(tmp_path, monkeypatch):
    f = tmp_path / "config.yaml"
    f.write_text("report_language: en\n", encoding="utf-8")
    _no_pyyaml(monkeypatch)
    with pytest.raises(RuntimeError, match="PyYAML is needed"):
        config.load(path=f)


def test_missing_pyyaml_without_config_file_means_clean_defaults(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_REAL_HOME", str(home))  # no config file anywhere
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.json"))
    _no_pyyaml(monkeypatch)
    cfg = config.load()
    assert set(cfg) == set(config.DEFAULTS)  # load() itself does not import yaml
