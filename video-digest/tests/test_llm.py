import pytest

from ytdigest import llm


def test_parse_json_from_fenced_prose():
    assert llm.parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('x {"b": {"c": 2}} y') == {"b": {"c": 2}}
    with pytest.raises(llm.LLMError):
        llm.parse_json("nothing here")


def test_ledger_and_spend(tmp_path, cfg):
    c = llm.Client(cfg, ledger=tmp_path / "s.jsonl", tag="backlog")
    c._record("ollama-cloud:gpt-oss:120b", "gpt-oss:120b", 1_000_000, 1_000_000)
    assert abs(c.usage.cost_usd - 0.75) < 1e-9
    assert llm.spent_today(tmp_path / "s.jsonl", "backlog") == 0.75
    assert llm.spent_today(tmp_path / "s.jsonl", "manual") == 0.0


def test_live_refs_drops_retired_models(cfg, monkeypatch):
    from ytdigest import llm as L
    monkeypatch.setattr(L, "_MODEL_CACHE", {"ollama-cloud": {"gemma4:31b", "glm-5.3-flash"}})
    refs = L.live_refs(cfg, ["ollama-cloud:gemma3:27b", "ollama-cloud:gemma3:12b"],
                       ["ollama-cloud:gemma4:31b", "ollama-cloud:glm-5.3-flash"])
    assert refs == ["ollama-cloud:gemma4:31b", "ollama-cloud:glm-5.3-flash"]
    # unknown list (fetch failed) keeps refs as given; other providers are never filtered
    monkeypatch.setattr(L, "_MODEL_CACHE", {"ollama-cloud": None})
    assert L.live_refs(cfg, ["ollama-cloud:x", "claude-code:sonnet"]) == ["ollama-cloud:x", "claude-code:sonnet"]
