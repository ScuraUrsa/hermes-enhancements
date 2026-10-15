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


def test_rarity_tiers():
    assert sg.rarity(0.5) == ("legendarne", 100)
    assert sg.rarity(3) == ("epickie", 50)
    assert sg.rarity(12) == ("rzadkie", 25)
    assert sg.rarity(60) == ("zwykłe", 10)


def _ach_routes(unlocks):
    return {
        "GetPlayerAchievements": lambda p: {"playerstats": {"success": True, "achievements": unlocks.get(p["appid"], [])}}
        if p["appid"] in unlocks else (_ for _ in ()).throw(RuntimeError("HTTP 400")),
        "GetGlobalAchievementPercentages": {"achievementpercentages": {"achievements": [
            {"name": "DRAGON", "percent": "0.7"}, {"name": "START", "percent": 91.2}]}},
    }


def test_achievements_baseline_then_xp(env, monkeypatch):
    unlocks = {292030: [{"apiname": "START", "achieved": 1, "unlocktime": 1000, "name": "Początek"}]}
    monkeypatch.setattr(sg, "http_json", fake_http(_ach_routes(unlocks)))
    games = [{"appid": 292030, "name": "The Witcher 3"}, {"appid": 1, "name": "No stats"}]
    assert sg.sync_achievements("1", games, now=5000) == []  # first sync: history only
    unlocks[292030].append({"apiname": "DRAGON", "achieved": 1, "unlocktime": 6000, "name": "Smokobójca"})
    unlocks[292030].append({"apiname": "LOCKED", "achieved": 0, "unlocktime": 0})
    new = sg.sync_achievements("1", games, now=7000)
    assert [(e["achievement"], e["rarity"], e["points"]) for e in new] == [("Smokobójca", "legendarne", 100)]
    assert sg.sync_achievements("1", games, now=8000) == []  # no double counting
    assert sum(e["points"] for e in sg.xp_since(7, now=8000)) == 100


def test_achievements_cron_is_silent_without_news(env, monkeypatch, capsys):
    routes = {"GetRecentlyPlayedGames": {"response": {"games": [{"appid": 292030, "name": "W3"}]}},
              **_ach_routes({292030: []})}
    monkeypatch.setattr(sg, "http_json", fake_http(routes))
    assert sg.main(["osiagniecia", "--cron"]) == 0
    assert capsys.readouterr().out == ""


def test_cron_commands_silent_without_config(env, monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("STEAM_ID")
    monkeypatch.setattr(sg, "real_home", lambda: str(tmp_path))
    assert sg.main(["przerwa", "--cron"]) == 0
    assert sg.main(["osiagniecia", "--cron"]) == 0
    assert capsys.readouterr().out == ""
    assert sg.main(["przerwa"]) == 2  # interactive use still reports the problem


def test_break_reminder_cycle(env, monkeypatch):
    playing = {"v": "Baldur's Gate 3"}
    monkeypatch.setattr(sg, "player_summary",
                        lambda sid: {"gameextrainfo": playing["v"], "gameid": "1086940"} if playing["v"] else {})
    t0 = 1_000_000

    def at(minute, **kw):  # cron runs every 10 min; replay the ticks up to `minute`
        msg = ""
        for m in range(at.last + 10, minute + 1, 10):
            msg = sg.check_break("1", now=t0 + m * 60, limit_min=120, repeat_min=60, **kw)[0] or msg
        at.last = minute
        return sg.check_break("1", now=t0 + minute * 60, limit_min=120, repeat_min=60, **kw)[0] or msg
    at.last = 0

    assert sg.check_break("1", now=t0, limit_min=120, repeat_min=60)[0] == ""
    assert at(110) == ""
    msg = at(121)
    assert "2 h 0" in msg and "Baldur" in msg
    assert at(150) == ""  # not again yet
    assert at(181) != ""  # an hour later
    playing["v"] = None
    sg.check_break("1", now=t0 + 190 * 60)  # short pause: session kept
    _, st = sg.check_break("1", now=t0 + 205 * 60)  # gap > 20 min: session closed and logged
    assert st == {}
    with open(os.path.join(sg.state_dir(), "sessions.jsonl")) as f:
        log = [json.loads(line) for line in f]
    assert [(e["game"], e["minutes"]) for e in log] == [("Baldur's Gate 3", 181)]


def test_break_new_session_after_long_gap(env, monkeypatch):
    monkeypatch.setattr(sg, "player_summary", lambda sid: {"gameextrainfo": "Terraria"})
    t0 = 2_000_000
    sg.check_break("1", now=t0, limit_min=120)
    _, st = sg.check_break("1", now=t0 + 3 * 3600, limit_min=120)  # no runs in between = VM was off
    assert st["started"] == t0 + 3 * 3600
