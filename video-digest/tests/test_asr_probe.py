"""--check-asr: self-check of the transcription backends (no network, no model download)."""
import pytest
from ytdigest import asr_probe


def test_probe_reports_one_row_per_order_step(cfg):
    cfg["transcript_order"] = ["manual", "groq", "parakeet", "local", "auto"]
    rows = asr_probe.probe(cfg, ok_import)
    assert [r["step"] for r in rows] == ["manual", "groq", "parakeet", "local", "auto"]
    assert all(set(r) >= {"step", "status", "reason"} for r in rows)


def ok_import(name, path=None):
    return object()


def no_asr_import(name, path=None):
    raise ImportError(f"No module named '{name}'")


def test_local_available_when_faster_whisper_imports(cfg):
    cfg["transcript_order"] = ["local"]
    (row,) = asr_probe.probe(cfg, ok_import)
    assert row["status"] == "available" and "faster-whisper" in row["reason"]


def test_local_and_parakeet_missing_when_imports_fail(cfg):
    cfg["transcript_order"] = ["local", "parakeet"]
    rows = asr_probe.probe(cfg, no_asr_import)
    assert all(r["status"] == "missing" and "not installed" in r["reason"] for r in rows)


def test_groq_without_api_key_is_missing(cfg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg["transcript_order"] = ["groq"]
    (row,) = asr_probe.probe(cfg, ok_import)
    assert row["status"] == "missing" and "GROQ_API_KEY" in row["reason"]


def test_groq_with_api_key_is_available(cfg, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    cfg["transcript_order"] = ["groq"]
    (row,) = asr_probe.probe(cfg, ok_import)
    assert row["status"] == "available"


def test_unknown_step_is_reported_missing(cfg):
    cfg["transcript_order"] = ["manual", "bogus", "local"]
    rows = asr_probe.probe(cfg, ok_import)
    assert rows[1]["status"] == "missing" and "unknown" in rows[1]["reason"].lower()


def test_exit_true_only_with_a_working_asr_backend(cfg, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg["transcript_order"] = ["manual", "groq", "parakeet", "local", "auto"]
    assert asr_probe.check(cfg, ok_import) is True
    assert asr_probe.check(cfg, no_asr_import) is False


def test_run_prints_rows_and_exits_zero_when_local_works(cfg, monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg["transcript_order"] = ["manual", "groq", "parakeet", "local", "auto"]
    assert asr_probe.run(cfg, ok_import) == 0
    out = capsys.readouterr().out
    assert "local: available" in out and "parakeet: available" in out
    assert "groq: missing" in out


def test_run_exits_one_when_only_video_captions_are_possible(cfg, capsys):
    cfg["transcript_order"] = ["manual", "auto"]
    assert asr_probe.run(cfg, ok_import) == 1
    assert "no ASR backend" in capsys.readouterr().out


def test_cli_flag_runs_the_probe(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.yaml"))
    monkeypatch.setenv("YTDIGEST_DATA_DIR", str(tmp_path / "data"))
    from ytdigest import cli
    assert cli.main(["--check-asr"]) == 0
    assert "local: available" in capsys.readouterr().out


def test_this_venv_has_the_local_asr_backends(cfg):
    """The extra is installed here; if it disappears, --check-asr must say missing."""
    cfg["transcript_order"] = ["parakeet", "local"]
    rows = {r["step"]: r for r in asr_probe.probe(cfg)}
    assert rows["local"]["status"] == "available" and "faster-whisper" in rows["local"]["reason"]
    assert rows["parakeet"]["status"] == "available" and "onnx-asr" in rows["parakeet"]["reason"]


def test_config_pins_hf_cache_outside_the_backup_payload(monkeypatch, tmp_path):
    """Whisper/Parakeet weights (GBs) must never land under ~/.hermes (backup payload)."""
    import os
    from ytdigest import config
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("YTDIGEST_CONFIG", str(tmp_path / "none.yaml"))
    config.load(None)
    hf = os.environ["HF_HOME"]
    assert hf.endswith(".cache/huggingface") and ".hermes" not in hf