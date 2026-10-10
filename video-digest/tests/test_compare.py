import json

from ytdigest import compare, pipeline


def test_compare_runs_each_model_strictly(cfg, monkeypatch, tmp_path):
    seen = []

    def fake(url, c, **kw):
        ref = kw["route_override"]["report"]
        seen.append((ref, kw["route_override"].get("vision_strict"), c["topic_routes"], kw["write_notion"]))
        return {"status": "done", "title": "T", "video_type": "tutorial_screen", "seconds": 12.0, "cost_usd": 0.001,
                "report_md": "# T\nabc", "usage": {ref: {"calls": 3, "input_tokens": 100, "output_tokens": 900,
                                                          "cache_read_tokens": 5000, "api_equiv_usd": 0.02}}}

    monkeypatch.setattr(pipeline, "safe_process", fake)
    res = compare.run(cfg, ["dQw4w9WgXcQ"], ["claude-code:sonnet", "claude-code:haiku"], log=lambda m: None,
                      out_dir=tmp_path / "cmp")
    assert [s[0] for s in seen] == ["claude-code:sonnet", "claude-code:haiku"]
    assert all(s[1] and s[2] == {} and s[3] is False for s in seen)
    data = json.loads((tmp_path / "cmp" / "results.json").read_text())
    assert data["totals"]["claude-code:haiku"]["output_tokens"] == 900
    assert "sonnet" in (tmp_path / "cmp" / "comparison.md").read_text()
