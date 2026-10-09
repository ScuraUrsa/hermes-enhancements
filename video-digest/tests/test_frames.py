from ytdigest import frames


def test_plan_respects_budget_and_chapters():
    plan = frames.plan(600, scenes=[5, 6, 7, 100, 200, 300], chapters=[{"t": 0}, {"t": 300}], frames_per_min=0.5, max_frames=10)
    times = [t for t, _ in plan]
    assert len(plan) <= 7
    assert any(r == "chapter" for _, r in plan)
    assert times == sorted(times)
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert min(gaps) >= 4


def test_extract_frames_on_synthetic_video(tmp_path, synthetic_video, cfg):
    cfg = {**cfg, "frames_per_min": 12, "max_frames": 12}
    out = frames.extract_frames(synthetic_video, tmp_path, 40.0, [], cfg)
    assert out, "expected some frames"
    for f in out:
        assert (tmp_path / f["path"]).is_file()
    reasons = {f["reason"] for f in out}
    assert "scene" in reasons
    # scenes 2 and 4 are both blue with the box elsewhere; static stretches must be deduplicated
    assert len(out) < 12
