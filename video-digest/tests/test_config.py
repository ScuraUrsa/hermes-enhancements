"""Hermetic tests for ytdigest/config.py.

Nothing here touches the operator's real tree. HERMES_HOME, DEFAULTS and the
working directory are redirected into tmp_path, every YTDIGEST_* variable is
cleared, and an autouse trip-wire fails the test if anything under the real
~/.hermes is opened or created (pytest's own tmp_path is the sole exception:
it lives under ~/.hermes/profiles and belongs to the harness, not to ytdigest).
"""

import copy
import importlib
import os
from pathlib import Path

import pytest
import yaml

from ytdigest import config

PRISTINE_DEFAULTS = copy.deepcopy(config.DEFAULTS)
REAL_HERMES = Path(os.path.expanduser("~")) / ".hermes"
ENV_VARS = (
    "YTDIGEST_CONFIG",
    "YTDIGEST_DATA_DIR",
    "YTDIGEST_NOTION_DATA_SOURCE",
    "YTDIGEST_ROUTING",
    "HERMES_REAL_HOME",
)


# --- hermetic harness -------------------------------------------------------
@pytest.fixture(autouse=True)
def _guard_real_home(tmp_path, monkeypatch):
    """Trip-wire: any read/mkdir under the real ~/.hermes fails the test."""
    touched = []

    def guard(path):
        path = Path(path)
        try:
            path.relative_to(tmp_path)  # pytest's own scratch is allowed
            return
        except ValueError:
            pass
        if path == REAL_HERMES or REAL_HERMES in path.parents:
            touched.append(str(path))

    real_read_text, real_mkdir = Path.read_text, Path.mkdir

    def read_text(self, *args, **kwargs):
        guard(self)
        return real_read_text(self, *args, **kwargs)

    def mkdir(self, *args, **kwargs):
        guard(self)
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    yield
    assert not touched, f"test touched the operator home: {touched}"


class Paths:
    def __init__(self, tmp_path):
        self.root = tmp_path
        self.home = tmp_path / "home"
        self.hermes = self.home / ".hermes"
        self.cwd = tmp_path / "cwd"
        self.data = tmp_path / "data"
        self.hermes_config = self.hermes / "ytdigest" / "config.yaml"


@pytest.fixture(autouse=True)
def _hermetic(_guard_real_home, tmp_path, monkeypatch):
    """Isolated env + isolated DEFAULTS + isolated cwd for every test."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    paths = Paths(tmp_path)
    paths.cwd.mkdir()
    monkeypatch.chdir(paths.cwd)
    monkeypatch.setattr(config, "HERMES_HOME", paths.hermes)
    defaults = copy.deepcopy(PRISTINE_DEFAULTS)
    defaults["data_dir"] = str(paths.data)
    defaults["cookies_file"] = str(paths.hermes / "ytdigest" / "cookies" / "{account}.txt")
    defaults["google_accounts_dir"] = str(paths.hermes / "google-accounts")
    monkeypatch.setattr(config, "DEFAULTS", defaults)
    return paths


def write_yaml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- _deep_merge ------------------------------------------------------------
def test_deep_merge_overrides_nested_keys_and_keeps_siblings():
    base = {"a": {"b": 1, "c": 2}, "top": "keep"}
    assert config._deep_merge(base, {"a": {"b": 9}}) == {"a": {"b": 9, "c": 2}, "top": "keep"}


def test_deep_merge_adds_new_keys_at_both_levels():
    assert config._deep_merge({"a": {"b": 1}}, {"a": {"new": 2}, "extra": 3}) == {
        "a": {"b": 1, "new": 2},
        "extra": 3,
    }


@pytest.mark.parametrize(
    "base, extra, expected",
    [
        ({"a": 1}, {"a": {"b": 1}}, {"a": {"b": 1}}),      # dict over scalar
        ({"a": {"b": 1}}, {"a": 1}, {"a": 1}),             # scalar over dict
        ({"a": [1, 2]}, {"a": [3]}, {"a": [3]}),           # list replaces, no concat
        ({"a": None}, {"a": {"b": 1}}, {"a": {"b": 1}}),   # dict over None
    ],
)
def test_deep_merge_conflicting_types_replace(base, extra, expected):
    assert config._deep_merge(base, extra) == expected


def test_deep_merge_with_none_extra_returns_a_copy():
    base = {"a": 1}
    assert config._deep_merge(base, None) == {"a": 1}  # type: ignore[arg-type]


def test_deep_merge_returns_an_independent_copy():
    base = {"a": {"b": [1, 2]}}
    merged = config._deep_merge(base, {})
    merged["a"]["b"].append(3)
    assert base == {"a": {"b": [1, 2]}}


# --- _read_file -------------------------------------------------------------
def test_read_file_parses_yaml(tmp_path):
    path = write_yaml(tmp_path / "c.yaml", "report_language: en\nnest:\n  x: 1\n")
    assert config._read_file(path) == {"report_language": "en", "nest": {"x": 1}}


@pytest.mark.parametrize("text", ["", "\n", "# only a comment\n"])
def test_read_file_empty_yaml_is_an_empty_mapping(tmp_path, text):
    path = write_yaml(tmp_path / "empty.yaml", text)
    assert config._read_file(path) == {}


def test_read_file_invalid_yaml_raises(tmp_path):
    path = write_yaml(tmp_path / "bad.yaml", "a: [1, 2\n")
    with pytest.raises(yaml.YAMLError):
        config._read_file(path)


def test_read_file_parses_json_with_tabs_by_suffix(tmp_path):
    """JSON is read with json.loads, not YAML: tab-indented JSON is valid for
    JSON but a ScannerError for PyYAML, which pins the suffix dispatch."""
    path = tmp_path / "c.json"
    path.write_text('{\n\t"a": {"b": 2}\n}', encoding="utf-8")
    assert config._read_file(path) == {"a": {"b": 2}}
    as_yaml = tmp_path / "c.yaml"
    as_yaml.write_text('{\n\t"a": {"b": 2}\n}', encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        config._read_file(as_yaml)


def test_read_file_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        config._read_file(tmp_path / "nope.yaml")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_read_file_permission_denied_raises(tmp_path):
    path = write_yaml(tmp_path / "locked.yaml", "a: 1\n")
    path.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            config._read_file(path)
    finally:
        path.chmod(0o600)


# --- config_path ------------------------------------------------------------
def test_config_path_prefers_ytdigest_config(tmp_path, monkeypatch):
    path = write_yaml(tmp_path / "explicit.yaml", "a: 1\n")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(path))
    assert config.config_path() == path


def test_config_path_falls_back_to_hermes_home(_hermetic, tmp_path, monkeypatch):
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "missing.yaml"))
    write_yaml(_hermetic.hermes_config, "report_language: en\n")
    assert config.config_path() == _hermetic.hermes_config


def test_config_path_empty_env_var_is_ignored(_hermetic, monkeypatch):
    monkeypatch.setenv("YTDIGEST_CONFIG", "")
    write_yaml(_hermetic.hermes_config, "report_language: en\n")
    assert config.config_path() == _hermetic.hermes_config


def test_config_path_falls_back_to_cwd(_hermetic):
    write_yaml(_hermetic.cwd / "config.yaml", "report_language: en\n")
    assert config.config_path() == Path("config.yaml")


def test_config_path_without_any_candidate_is_none(_hermetic):
    assert config.config_path() is None


def test_config_path_never_resolves_to_the_operator_config(_hermetic):
    assert _hermetic.hermes_config.parent.is_dir() is False  # isolated tree is empty
    resolved = config.config_path()
    assert resolved is None or REAL_HERMES not in Path(resolved).parents


# --- load: file precedence ---------------------------------------------------
def test_load_without_any_file_returns_the_defaults():
    assert config.load() == config.DEFAULTS


def test_load_without_any_file_does_not_use_the_operator_tree(_hermetic):
    cfg = config.load()
    assert cfg["data_dir"] == str(_hermetic.data)
    assert cfg["accounts"] == PRISTINE_DEFAULTS["accounts"]


def test_load_reads_the_isolated_hermes_home_not_the_operator_one(_hermetic):
    write_yaml(_hermetic.hermes_config, "marker: isolated-home\n")
    cfg = config.load()
    assert cfg["marker"] == "isolated-home"
    assert cfg["data_dir"] == str(_hermetic.data)


def test_load_uses_ytdigest_config_when_no_argument(tmp_path, monkeypatch):
    path = write_yaml(tmp_path / "env.yaml", "marker: from-env\n")
    monkeypatch.setenv("YTDIGEST_CONFIG", str(path))
    assert config.load()["marker"] == "from-env"


def test_load_explicit_path_wins_over_the_env(tmp_path, monkeypatch):
    monkeypatch.setenv("YTDIGEST_CONFIG", str(write_yaml(tmp_path / "env.yaml", "marker: from-env\n")))
    explicit = write_yaml(tmp_path / "explicit.yaml", "marker: explicit\n")
    assert config.load(explicit)["marker"] == "explicit"


def test_load_merges_a_partial_file_over_the_defaults(tmp_path):
    path = write_yaml(
        tmp_path / "c.yaml",
        "report_language: en\nproviders:\n  groq:\n    base_url: http://127.0.0.1:1\n",
    )
    cfg = config.load(path)
    assert cfg["report_language"] == "en"
    assert cfg["providers"]["groq"] == {"base_url": "http://127.0.0.1:1", "key_env": "GROQ_API_KEY"}
    assert cfg["providers"]["ollama-cloud"] == PRISTINE_DEFAULTS["providers"]["ollama-cloud"]
    assert cfg["max_frames"] == PRISTINE_DEFAULTS["max_frames"]


def test_load_missing_explicit_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        config.load(tmp_path / "nope.yaml")


# --- load: environment overrides beat the file ------------------------------
def test_load_env_data_dir_beats_the_file_and_is_created(tmp_path, monkeypatch):
    file_path = write_yaml(tmp_path / "c.yaml", f"data_dir: {tmp_path / 'from-file'}\n")
    target = tmp_path / "deep" / "from-env"
    monkeypatch.setenv("YTDIGEST_DATA_DIR", str(target))
    cfg = config.load(file_path)
    assert cfg["data_dir"] == str(target)
    assert target.is_dir()


def test_load_creates_the_default_data_dir(_hermetic):
    cfg = config.load()
    assert Path(cfg["data_dir"]).is_dir()


def test_load_env_notion_and_routing_beat_the_file(tmp_path, monkeypatch):
    file_path = write_yaml(
        tmp_path / "c.yaml",
        "notion_data_source_id: from-file\nrouting_file: /from/file.json\n",
    )
    monkeypatch.setenv("YTDIGEST_NOTION_DATA_SOURCE", "from-env")
    monkeypatch.setenv("YTDIGEST_ROUTING", "/from/env.json")
    cfg = config.load(file_path)
    assert cfg["notion_data_source_id"] == "from-env"
    assert cfg["routing_file"] == "/from/env.json"


def test_load_does_not_mutate_the_defaults():
    before = copy.deepcopy(config.DEFAULTS)
    cfg = config.load()
    cfg["accounts"].append("mutated")
    cfg["providers"]["groq"]["base_url"] = "http://mutated"
    cfg["topic_routes"]["ai_software"]["report"] = "mutated"
    assert config.DEFAULTS == before


# --- module-level home resolution -------------------------------------------
def test_defaults_follow_hermes_real_home(tmp_path, monkeypatch):
    real = tmp_path / "realhome"
    monkeypatch.setenv("HERMES_REAL_HOME", str(real))
    try:
        mod = importlib.reload(config)
        assert mod.HERMES_HOME == real / ".hermes"
        assert mod.DEFAULTS["data_dir"] == str(real / ".hermes" / "ytdigest")
        assert mod.DEFAULTS["cookies_file"] == str(real / ".hermes" / "ytdigest" / "cookies" / "{account}.txt")
        assert mod.DEFAULTS["google_accounts_dir"] == str(real / ".hermes" / "google-accounts")
    finally:
        monkeypatch.delenv("HERMES_REAL_HOME")
        importlib.reload(config)


def test_defaults_fall_back_to_home_when_hermes_real_home_is_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "userhome"))
    try:
        mod = importlib.reload(config)
        assert mod.HERMES_HOME == tmp_path / "userhome" / ".hermes"
        assert mod.DEFAULTS["data_dir"] == str(tmp_path / "userhome" / ".hermes" / "ytdigest")
    finally:
        monkeypatch.delenv("HOME")
        importlib.reload(config)
