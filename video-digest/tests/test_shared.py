"""Unit tests for ytdigest.shared: the vbench prompt bridge and the metadata dict.

The bridge is tested against real import machinery: one case with a vbench
already importable, one with the sibling checkout next to video-digest, one
with neither, and one where the sibling package exists but blows up on import.
The three cases that need vbench *absent* pin sys.path to a sandbox instead of
skipping when the machine has one: earlier tests in the full suite can leave
the repo root on sys.path, and a skip there would hide the branch under test.
"""

from __future__ import annotations

import importlib.util
import sys
import sysconfig
import types

import pytest

from ytdigest import shared


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(shared, "_cache", {})


@pytest.fixture
def clean_vbench(monkeypatch):
    """Start and end without any vbench module in sys.modules."""
    for name in [n for n in sys.modules if n == "vbench" or n.startswith("vbench.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield
    for name in [n for n in list(sys.modules) if n == "vbench" or n.startswith("vbench.")]:
        del sys.modules[name]


def write_sibling(tmp_path, source: str):
    """Lay out <root>/video-digest/ytdigest/shared.py + <root>/vbench/vbench/prompts.py."""
    root = tmp_path / "repo"
    (root / "video-digest" / "ytdigest").mkdir(parents=True)
    pkg = root / "vbench" / "vbench"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "prompts.py").write_text(source, encoding="utf-8")
    return root


def sandbox_import_path(monkeypatch):
    """Pin sys.path to the stdlib, so no vbench is importable from outside.

    The production code decides vbench availability with a real ``import``, so
    the only way to test the "no package" branches hermetically is to own
    sys.path for the duration of the test. That also keeps these cases running
    inside the full suite, where other tests may already have put the repo root
    -- and with it this checkout's ``vbench/`` -- on sys.path. The temp root is
    deliberately NOT added: the sibling checkout is found through
    ``shared.__file__``, and an outer directory holding ``vbench/`` would make
    the first import succeed as a namespace package and shadow the retry.
    """
    stdlib = {sysconfig.get_paths()[key] for key in ("stdlib", "platstdlib")}
    monkeypatch.setattr(sys, "path", sorted(stdlib))

    # Prove the precondition instead of skipping on it: nothing importable as
    # vbench.prompts may come from the sandbox, whatever is installed here.
    saved_modules = sys.modules.copy()
    try:
        importlib.import_module("vbench.prompts")
    except ImportError:
        pass
    else:
        raise AssertionError("the sandbox path exposes a real vbench; it is not hermetic")
    finally:
        sys.modules.clear()
        sys.modules.update(saved_modules)


def test_meta_from_bundle_is_passed_through():
    bundle = {
        "title": "Jak działa Gdańsk",
        "channel": "Kanał",
        "url": "https://youtu.be/x",
        "duration_sec": 600,
        "yt_tags": ["miasto", "port"],
        "yt_chapters": [{"t": 5, "title": "Wstęp"}],
        "description": "opis",
    }

    meta = shared.meta(bundle, "whisper", 0.25)

    assert meta == {
        "title": "Jak działa Gdańsk",
        "channel": "Kanał",
        "url": "https://youtu.be/x",
        "duration_min": 10.0,
        "yt_tags": ["miasto", "port"],
        "yt_chapters": [{"t": 5, "title": "Wstęp"}],
        "transcript_source": "whisper",
        "music_ratio": 0.25,
        "description": "opis",
    }


def test_meta_from_yt_dlp_info_uses_fallbacks():
    info = {
        "title": "Tytuł",
        "uploader": "Uploader",
        "webpage_url": "https://youtube.com/watch?v=x",
        "duration": 90,
        "tags": ["a", "b"],
        "chapters": [{"start_time": 12, "title": "Intro"}, {"title": "Bez czasu"}],
        "description": "opis",
    }

    meta = shared.meta(info)

    assert meta["channel"] == "Uploader"
    assert meta["url"] == "https://youtube.com/watch?v=x"
    assert meta["duration_min"] == 1.5
    assert meta["yt_tags"] == ["a", "b"]
    assert meta["yt_chapters"] == [{"t": 12, "title": "Intro"}, {"t": 0, "title": "Bez czasu"}]
    assert meta["transcript_source"] == "none"
    assert meta["music_ratio"] is None


def test_meta_defaults_for_missing_fields():
    meta = shared.meta({})

    assert meta["title"] == ""
    assert meta["channel"] == ""
    assert meta["url"] == ""
    assert meta["duration_min"] == 0.0
    assert meta["yt_tags"] == []
    assert meta["yt_chapters"] == []
    assert meta["description"] == ""


def test_meta_prefers_bundle_fields_over_info_fields():
    bundle = {
        "title": "Bundle",
        "channel": "Kanał",
        "uploader": "Uploader",
        "url": "bundle-url",
        "webpage_url": "info-url",
        "yt_tags": ["bundle"],
        "tags": ["info"],
        "yt_chapters": [],
        "chapters": [{"start_time": 1, "title": "Ignored"}],
        "duration_sec": 60,
    }

    meta = shared.meta(bundle, "groq", 0.0)

    assert meta["channel"] == "Kanał"
    assert meta["url"] == "bundle-url"
    assert meta["yt_tags"] == ["bundle"]
    assert meta["yt_chapters"] == [{"t": 1, "title": "Ignored"}]  # an empty yt_chapters counts as missing
    assert meta["music_ratio"] == 0.0  # a measured zero stays zero


def test_meta_converts_stringy_duration_and_zero_duration_sec():
    assert shared.meta({"duration_sec": "120"})["duration_min"] == 2.0
    assert shared.meta({"duration_sec": 0, "duration": 60})["duration_min"] == 1.0


def test_vbench_prompts_uses_importable_package(monkeypatch, clean_vbench):
    pkg = types.ModuleType("vbench")
    prompts = types.ModuleType("vbench.prompts")
    prompts.STAGE_PROMPTS = {"summary": "z vbench"}
    pkg.prompts = prompts
    monkeypatch.setitem(sys.modules, "vbench", pkg)
    monkeypatch.setitem(sys.modules, "vbench.prompts", prompts)

    assert shared.vbench_prompts() is prompts

    monkeypatch.delitem(sys.modules, "vbench.prompts")
    monkeypatch.delitem(sys.modules, "vbench")
    assert shared.vbench_prompts() is prompts  # cached, no second import
    assert "vbench.prompts" not in sys.modules


def test_vbench_prompts_imports_the_sibling_checkout(monkeypatch, tmp_path, clean_vbench):
    root = write_sibling(tmp_path, "STAGE_PROMPTS = {'summary': 'z sąsiada'}\n")
    monkeypatch.setattr(shared, "__file__", str(root / "video-digest" / "ytdigest" / "shared.py"))
    sandbox_import_path(monkeypatch)

    prompts = shared.vbench_prompts()

    assert prompts is not None
    assert prompts.STAGE_PROMPTS == {"summary": "z sąsiada"}
    assert sys.path[0] == str(root / "vbench")


def test_vbench_prompts_returns_none_without_package_or_sibling(monkeypatch, tmp_path, clean_vbench):
    root = tmp_path / "repo"
    (root / "video-digest" / "ytdigest").mkdir(parents=True)
    monkeypatch.setattr(shared, "__file__", str(root / "video-digest" / "ytdigest" / "shared.py"))
    sandbox_import_path(monkeypatch)

    assert shared.vbench_prompts() is None
    assert shared._cache["p"] is None
    assert sys.path[0] not in {str(root / "vbench"), str(root)}  # nothing was injected


def test_vbench_prompts_survives_a_broken_sibling_package(monkeypatch, tmp_path, clean_vbench):
    root = write_sibling(tmp_path, "raise ImportError('vbench is broken here')\n")
    monkeypatch.setattr(shared, "__file__", str(root / "video-digest" / "ytdigest" / "shared.py"))
    sandbox_import_path(monkeypatch)

    assert shared.vbench_prompts() is None


def test_vbench_prompts_cache_wins_over_import(monkeypatch, clean_vbench):
    sentinel = object()
    shared._cache["p"] = sentinel

    assert shared.vbench_prompts() is sentinel
    assert "vbench" not in sys.modules
