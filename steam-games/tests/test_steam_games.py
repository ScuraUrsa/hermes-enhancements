"""Offline tests for steam_games.py (no network: Steam/YouTube calls are faked)."""
import datetime as dt
import json
import os
import random
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import steam_games as sg  # noqa: E402

OWNED = {"response": {"game_count": 3, "games": [
    {"appid": 286160, "name": "Tabletop Simulator", "playtime_forever": 1260, "rtime_last_played": 1760000000},
    {"appid": 292030, "name": "The Witcher 3", "playtime_forever": 9000, "rtime_last_played": 1750000000},
    {"appid": 105600, "name": "Terraria", "playtime_forever": 0},
]}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STEAM_GAMES_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("STEAM_API_KEY", "k")
    monkeypatch.setenv("STEAM_ID", "76561198000000001")
    monkeypatch.setattr(sg, "find_ytdlp", lambda: None)
    return tmp_path


def fake_http(routes):
    def http_json(url, params=None, headers=None):
        for frag, payload in routes.items():
            if frag in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload(params) if callable(payload) else payload
        raise AssertionError(f"unexpected URL {url}")
    return http_json


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    f = tmp_path / ".env"
    f.write_text('# c\nexport STEAM_API_KEY="abc"\nOTHER=1\n')
    assert sg.setting("STEAM_API_KEY", str(f)) == "abc"


def test_vanity_resolves_and_caches(env, monkeypatch):
    calls = []
    monkeypatch.setenv("STEAM_ID", "https://steamcommunity.com/id/filip/")
    monkeypatch.setattr(sg, "http_json", fake_http(
        {"ResolveVanityURL": lambda p: calls.append(p) or {"response": {"success": 1, "steamid": "76561198000000002"}}}))
    assert sg.steam_id() == "76561198000000002"
    assert sg.steam_id() == "76561198000000002"
    assert len(calls) == 1 and calls[0]["vanityurl"] == "filip"


def test_missing_key_is_config_error(env, monkeypatch, tmp_path):
    monkeypatch.delenv("STEAM_API_KEY")
    monkeypatch.setattr(sg, "real_home", lambda: str(tmp_path))
    with pytest.raises(sg.ConfigError):
        sg.steam_api("x")


def test_private_profile(env, monkeypatch):
    monkeypatch.setattr(sg, "http_json", fake_http({"GetOwnedGames": {"response": {}}}))
    with pytest.raises(sg.PrivateProfile):
        sg.owned_games("1")
    assert sg.main(["biblioteka"]) == 2


def test_library_output(env, monkeypatch, capsys):
    monkeypatch.setattr(sg, "http_json", fake_http({"GetOwnedGames": OWNED}))
    assert sg.main(["biblioteka", "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "3 gier" in out and out.index("Witcher") < out.index("Tabletop")


def test_interests_weights_themes(env, monkeypatch):
    routes = {
        "GetOwnedGames": OWNED,
        "GetWishlist": {"response": {"items": [{"appid": 1}]}},
        "appdetails": lambda p: {str(p["appids"]): {"success": True, "data": {"name": "G", "genres": [{"description": "RPG"}]}}},
        "steamspy": lambda p: {"name": "G", "tags": {"Fantasy": 900, "Open World": 500}
                               if p["appid"] != 1 else {"Sci-fi": 100}},
    }
    monkeypatch.setattr(sg, "http_json", fake_http(routes))
    data = sg.build_interests("1")
    assert data["tabletop_simulator"] == {"owned": True, "hours": 21.0}
    assert data["themes"]["fantasy"] > data["themes"]["scifi"] >= 1.0
    assert "Fantasy" in data["top_genres_tags"]
    assert os.path.exists(os.path.join(sg.state_dir(), "interests.json"))


def test_interests_survive_store_outage(env, monkeypatch):
    import urllib.error
    routes = {"GetOwnedGames": OWNED, "GetWishlist": {"response": {}},
              "appdetails": urllib.error.URLError("down"), "steamspy": urllib.error.URLError("down")}
    monkeypatch.setattr(sg, "http_json", fake_http(routes))
    data = sg.build_interests("1")
    assert data["themes"] == {"fantasy": 1.0, "scifi": 1.0}


def test_catalogue_is_valid():
    games = sg.load_catalogue()
    assert len(games) >= 30
    for g in games:
        assert g["players"][0] <= 2 <= g["players"][1], g["name"]
        assert g["mode"] in sg.MODE_PL and 1 <= g["weight"] <= 5 and g["pitch_pl"]
    assert len({g["name"] for g in games}) == len(games)


def test_suggest_filters():
    games = sg.load_catalogue()
    picks = sg.suggest(games, max_time=30, mode="coop", count=10, rng=random.Random(1))
    assert picks and all(g["time"] <= 30 and g["mode"] in ("coop", "both") for g in picks)
    picks = sg.suggest(games, theme="fantasy", count=50, rng=random.Random(1))
    assert picks and all("fantasy" in g["themes"] for g in picks)
    assert sg.suggest(games, players=7) == []


def test_suggest_prefers_interests_and_skips_recent():
    games = [{"name": n, "players": [2, 2], "time": 30, "weight": 2, "mode": "versus", "themes": [t], "pitch_pl": "x"}
             for n, t in (("A", "fantasy"), ("B", "handel"))]
    rng = random.Random(0)
    wins = sum(sg.suggest(games, count=1, interests={"fantasy": 5}, rng=rng)[0]["name"] == "A" for _ in range(300))
    assert wins > 220
    today = dt.date(2026, 10, 15)
    hist = [{"name": "A", "date": "2026-10-14"}]
    wins = sum(sg.suggest(games, count=1, interests={"fantasy": 1}, history=hist, today=today, rng=rng)[0]["name"] == "A"
               for _ in range(300))
    assert wins < 150


def test_suggest_cli_offline(env, capsys):
    assert sg.main(["planszowka", "--seed", "3", "--ile", "2"]) == 0
    out = capsys.readouterr().out
    assert out.count("TTS Workshop") == 2 and "youtube.com/results" in out
    assert sg.main(["planszowka", "--czas", "5"]) == 3


def test_youtube_ranking(monkeypatch):
    monkeypatch.setattr(sg, "find_ytdlp", lambda: "/bin/yt-dlp")

    def runner(cmd, **kw):
        q = cmd[-1]
        entries = [{"id": "aaa", "title": "Patchwork review", "channel": "Someone", "duration": 600},
                   {"id": "bbb", "title": "How to Play Patchwork", "channel": "Watch It Played", "duration": 480}]
        if "zasady" in q:
            entries = [{"id": "ccc", "title": "Patchwork - zasady gry", "channel": "Planszówki", "duration": 300}]
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"entries": entries}), "")

    vids = sg.youtube_tutorials("Patchwork", runner=runner)
    assert vids[0]["url"].endswith("bbb") and vids[0]["minutes"] == 8
    assert {v["lang"] for v in vids} == {"en", "pl"}


def test_workshop_mods_parse(env, monkeypatch):
    payload = {"response": {"total": 1, "publishedfiledetails": [
        {"publishedfileid": "123", "title": "Patchwork (scripted)", "subscriptions": 4500}]}}
    seen = {}
    monkeypatch.setattr(sg, "http_json", fake_http({"QueryFiles": lambda p: seen.update(p) or payload}))
    mods = sg.workshop_mods("Patchwork")
    assert mods[0]["url"].endswith("id=123") and mods[0]["open_in_steam"] == "steam://url/CommunityFilePage/123"
    assert seen["appid"] == sg.TTS_APPID and seen["search_text"] == "Patchwork"


def test_played_log_and_history(env, capsys):
    assert sg.main(["zagrane", "Patchwork", "--ocena", "5", "--data", "2026-10-14"]) == 0
    assert sg.main(["historia"]) == 0
    assert "2026-10-14: Patchwork (5/5)" in capsys.readouterr().out


def test_api_key_never_in_errors(env, monkeypatch):
    import urllib.error

    def boom(url, params=None, headers=None):
        raise urllib.error.URLError(f"failed {url}?key={params['key']}")
    monkeypatch.setenv("STEAM_API_KEY", "SECRET123")
    monkeypatch.setattr(sg, "http_json", boom)
    with pytest.raises(RuntimeError) as e:
        sg.steam_api("IPlayerService/GetOwnedGames/v1/", steamid="1")
    assert "SECRET123" not in str(e.value)
