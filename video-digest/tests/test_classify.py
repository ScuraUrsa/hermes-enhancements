from ytdigest import classify


def test_music_video_is_artistic_without_llm():
    info = {"title": "Artist - Song (Official Music Video)", "channel": "ArtistVEVO", "categories": ["Music"], "duration": 230}
    r = classify.rule_based(info)
    assert r["is_artistic"] and r["video_type"] == "music_artistic"


def test_topic_channel_is_artistic():
    r = classify.rule_based({"title": "Some track", "channel": "Band - Topic", "categories": ["Music"], "duration": 200})
    assert r["is_artistic"]


def test_podcast_in_music_category_is_not_decided_by_rules():
    info = {"title": "Podcast: jak produkować muzykę, wywiad", "channel": "Studio", "categories": ["Music"], "duration": 3600}
    assert classify.rule_based(info) is None


def test_podcast_episode_numbers_do_not_look_like_music():
    info = {"title": "Ep. 12 - rozmowa o finansach", "channel": "Pod", "categories": ["People & Blogs"], "duration": 3000}
    assert classify.rule_based(info) is None


class FakeClient:
    def __init__(self, out):
        self.out = out

    def json(self, *a, **k):
        return self.out


def test_with_model_normalises_unknown_type():
    r = classify.with_model(FakeClient({"video_type": "weird", "is_artistic": False, "confidence": 0.9}), "x:y", {}, "", 0.8)
    assert r["video_type"] == "other" and not r["is_artistic"]
    r = classify.with_model(FakeClient({"video_type": "documentary", "is_artistic": True}), "x:y", {}, "", 0.1)
    assert r["video_type"] == "music_artistic"
