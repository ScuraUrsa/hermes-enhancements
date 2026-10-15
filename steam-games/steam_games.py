#!/usr/bin/env python3
"""steam_games.py — Steam i planszówki dla Hermesa (Filip). Tylko biblioteka standardowa.

Użycie:
  steam_games.py status                         # konfiguracja: klucz, SteamID, publiczny profil, Tabletop Simulator
  steam_games.py biblioteka [--sort czas|ostatnio|nazwa] [--limit 20]
  steam_games.py ostatnio                       # gry z ostatnich 2 tygodni
  steam_games.py zainteresowania [--odswiez]    # gatunki i motywy z gier (czas gry) + lista życzeń -> interests.json
  steam_games.py planszowka [--czas 45] [--tryb coop|rywalizacja] [--motyw fantasy] [--ile 3] [--live]
  steam_games.py zasady "7 Wonders Duel"        # film z zasadami (YouTube) + mod do Tabletop Simulator
  steam_games.py zagrane "Patchwork" [--ocena 4] [--notatka "..."]
  steam_games.py historia                       # zagrane planszówki

Każda komenda ma --json. Konfiguracja (zmienne środowiskowe albo ~/.hermes/.env):
  STEAM_API_KEY   klucz Steam Web API (Bitwarden: STEAM_API_KEY), https://steamcommunity.com/dev/apikey
  STEAM_ID        SteamID64 (17 cyfr) albo własny adres profilu (vanity), np. "filip"
  BGG_API_TOKEN   opcjonalny token BoardGameGeek XML API (bez niego tylko linki)
  STEAM_GAMES_STATE  katalog stanu (domyślnie ~/.hermes/autonomy/steam-games)
Kody wyjścia: 0 ok, 1 błąd sieci/API, 2 brak konfiguracji albo prywatny profil, 3 nic nie pasuje.
"""
import argparse
import datetime as dt
import json
import os
import pwd
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TTS_APPID = 286160
UA = {"User-Agent": "hermes-steam-games/1.0"}
TIMEOUT = 15
API = "https://api.steampowered.com"
HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.environ.get("STEAM_GAMES_CATALOGUE", os.path.join(HERE, "boardgames.json"))
# Filip, 2026-10-13: interesuje się fantasy i science fiction. Steam data refines these weights.
DEFAULT_THEMES = {"fantasy": 1.0, "scifi": 1.0}
# Steam tags / genres -> catalogue themes.
TAG_THEMES = {
    "fantasy": "fantasy", "dark fantasy": "fantasy", "medieval": "fantasy", "magic": "fantasy",
    "dragons": "fantasy", "mythology": "mitologia", "lovecraftian": "lovecraft", "horror": "horror",
    "sci-fi": "scifi", "science fiction": "scifi", "space": "scifi", "cyberpunk": "cyberpunk",
    "futuristic": "scifi", "aliens": "scifi", "space sim": "scifi", "post-apocalyptic": "postapo",
    "superhero": "superbohaterowie", "historical": "historia", "world war ii": "wojenna", "war": "wojenna",
    "military": "wojenna", "trading": "handel", "exploration": "eksploracja", "adventure": "przygoda",
    "card game": "karty", "deckbuilding": "karty", "strategy": "strategia", "turn-based tactics": "strategia",
    "board game": "planszowka", "puzzle": "abstrakcyjna", "co-op": "coop", "online co-op": "coop",
}
TUTORIAL_CHANNELS = ("watch it played", "gaming rules!", "rules girl", "dice in a tower", "the rules girl",
                     "board game school", "how to play", "meeple university")
MODE_ALIASES = {"coop": "coop", "kooperacja": "coop", "kooperacyjna": "coop", "razem": "coop",
                "versus": "versus", "rywalizacja": "versus", "vs": "versus", "przeciwko": "versus"}


class ConfigError(Exception):
    pass


class PrivateProfile(Exception):
    pass


# ---------- environment ----------

def real_home():
    """Workers run with HOME=~/.hermes/profiles/<p>/home, so resolve the account's real home."""
    try:
        return pwd.getpwuid(os.getuid()).pw_dir
    except KeyError:
        return os.path.expanduser("~")


def read_env_file(path):
    vals = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.removeprefix("export ").strip()
                vals[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return vals


def setting(name, env_file=None):
    if os.environ.get(name):
        return os.environ[name]
    path = env_file or os.path.join(real_home(), ".hermes", ".env")
    return read_env_file(path).get(name, "")


def state_dir():
    d = os.environ.get("STEAM_GAMES_STATE") or os.path.join(real_home(), ".hermes", "autonomy", "steam-games")
    os.makedirs(d, exist_ok=True)
    return d


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------- HTTP ----------

def http_json(url, params=None, headers=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def redact(text):
    return re.sub(r"key=[A-Za-z0-9]+", "key=***", str(text))


def steam_api(path, **params):
    key = setting("STEAM_API_KEY")
    if not key:
        raise ConfigError("brak STEAM_API_KEY (klucz Steam Web API)")
    try:
        return http_json(f"{API}/{path}", {"key": key, "format": "json", **params})
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ConfigError(f"Steam odrzucił klucz API (HTTP {e.code})") from None
        raise RuntimeError(redact(f"Steam API HTTP {e.code} dla {path}")) from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise RuntimeError(redact(f"Steam API niedostępne ({path}): {e}")) from None


# ---------- Steam ----------

def steam_id():
    raw = setting("STEAM_ID").strip()
    if not raw:
        raise ConfigError("brak STEAM_ID (SteamID64 albo nazwa z adresu profilu)")
    m = re.search(r"steamcommunity\.com/(id|profiles)/([^/?#]+)", raw)
    if m:
        raw = m.group(2)
    if re.fullmatch(r"7656\d{13}", raw):
        return raw
    cache = os.path.join(state_dir(), "steamid.json")
    cached = load_json(cache, {})
    if cached.get("vanity") == raw and cached.get("steamid"):
        return cached["steamid"]
    resp = steam_api("ISteamUser/ResolveVanityURL/v1/", vanityurl=raw).get("response", {})
    if resp.get("success") != 1:
        raise ConfigError(f"nie znam profilu Steam '{raw}' (ResolveVanityURL)")
    save_json(cache, {"vanity": raw, "steamid": resp["steamid"]})
    return resp["steamid"]


def player_summary(sid):
    players = steam_api("ISteamUser/GetPlayerSummaries/v2/", steamids=sid).get("response", {}).get("players", [])
    return players[0] if players else {}


def owned_games(sid):
    resp = steam_api("IPlayerService/GetOwnedGames/v1/", steamid=sid, include_appinfo=1,
                     include_played_free_games=1).get("response", {})
    if "games" not in resp:
        # Empty response = game details are private (Steam returns {} instead of an error).
        raise PrivateProfile("Steam nie pokazuje gier: ustaw 'Szczegóły gier' na Publiczne "
                             "(https://steamcommunity.com/my/edit/settings)")
    games = []
    for g in resp["games"]:
        games.append({
            "appid": g.get("appid"),
            "name": g.get("name") or f"app {g.get('appid')}",
            "hours": round(g.get("playtime_forever", 0) / 60, 1),
            "hours_2weeks": round(g.get("playtime_2weeks", 0) / 60, 1),
            "last_played": dt.datetime.fromtimestamp(g["rtime_last_played"]).date().isoformat()
            if g.get("rtime_last_played") else None,
        })
    return games


def recent_games(sid):
    resp = steam_api("IPlayerService/GetRecentlyPlayedGames/v1/", steamid=sid).get("response", {})
    return [{"appid": g.get("appid"), "name": g.get("name"), "hours_2weeks": round(g.get("playtime_2weeks", 0) / 60, 1),
             "hours": round(g.get("playtime_forever", 0) / 60, 1)} for g in resp.get("games", [])]


def wishlist(sid):
    try:
        resp = steam_api("IWishlistService/GetWishlist/v1/", steamid=sid).get("response", {})
    except RuntimeError:
        return []
    return [i.get("appid") for i in resp.get("items", []) if i.get("appid")]


def app_info(appid, cache):
    """Genres (Steam store) + user tags (SteamSpy), cached for 30 days. Missing data is not an error."""
    key = str(appid)
    hit = cache.get(key)
    if hit and time.time() - hit.get("ts", 0) < 30 * 86400:
        return hit
    info = {"ts": time.time(), "name": None, "genres": [], "tags": []}
    try:
        d = http_json("https://store.steampowered.com/api/appdetails", {"appids": appid, "l": "english"})
        data = (d.get(key) or {}).get("data") or {}
        info["name"] = data.get("name")
        info["genres"] = [g.get("description", "") for g in data.get("genres", [])]
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass
    try:
        d = http_json("https://steamspy.com/api.php", {"request": "appdetails", "appid": appid})
        tags = d.get("tags") or {}
        if isinstance(tags, dict):
            info["tags"] = [t for t, _ in sorted(tags.items(), key=lambda kv: -kv[1])][:12]
        info["name"] = info["name"] or d.get("name")
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass
    cache[key] = info
    return info


def build_interests(sid, top=25, wish_limit=15):
    games = sorted(owned_games(sid), key=lambda g: -g["hours"])
    cache_path = os.path.join(state_dir(), "appinfo-cache.json")
    cache = load_json(cache_path, {})
    weights, genres = {}, {}
    played = [g for g in games if g["hours"] > 0][:top]
    for g in played:
        info = app_info(g["appid"], cache)
        w = 1.0 + min(g["hours"], 200) / 20  # playtime counts, but one 2000 h game must not drown the rest
        for label in info["tags"] + info["genres"]:
            genres[label] = genres.get(label, 0) + w
            theme = TAG_THEMES.get(label.lower())
            if theme:
                weights[theme] = weights.get(theme, 0) + w
    wish_ids = wishlist(sid)[:wish_limit]
    wish_names = []
    for appid in wish_ids:
        info = app_info(appid, cache)
        wish_names.append(info.get("name") or f"app {appid}")
        for label in info["tags"] + info["genres"]:
            theme = TAG_THEMES.get(label.lower())
            if theme:
                weights[theme] = weights.get(theme, 0) + 2.0
    save_json(cache_path, cache)
    total = sum(weights.values()) or 1.0
    themes = {k: round(v / total * 10, 2) for k, v in sorted(weights.items(), key=lambda kv: -kv[1])}
    for k, v in DEFAULT_THEMES.items():  # what Filip said himself always stays in
        themes[k] = max(themes.get(k, 0), v)
    tts = next((g for g in games if g["appid"] == TTS_APPID), None)
    data = {
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
        "steamid": sid,
        "games_owned": len(games),
        "top_games": [{"name": g["name"], "hours": g["hours"]} for g in games[:15]],
        "top_genres_tags": [k for k, _ in sorted(genres.items(), key=lambda kv: -kv[1])][:20],
        "themes": themes,
        "wishlist": wish_names,
        "tabletop_simulator": {"owned": bool(tts), "hours": tts["hours"] if tts else 0},
    }
    save_json(os.path.join(state_dir(), "interests.json"), data)
    return data


def interests_or_default():
    data = load_json(os.path.join(state_dir(), "interests.json"), {})
    return data.get("themes") or dict(DEFAULT_THEMES)


# ---------- board games ----------

def load_catalogue(path=CATALOGUE):
    return load_json(path, {}).get("games", [])


def links(name):
    q = urllib.parse.quote_plus
    return {
        "tts_workshop": f"https://steamcommunity.com/workshop/browse/?appid={TTS_APPID}&searchtext={q(name)}&browsesort=textsearch",
        "youtube_en": f"https://www.youtube.com/results?search_query={q(name + ' how to play')}",
        "youtube_pl": f"https://www.youtube.com/results?search_query={q(name + ' zasady gry')}",
        "bgg": f"https://boardgamegeek.com/geeksearch.php?action=search&objecttype=boardgame&q={q(name)}",
    }


def played_log():
    return load_json(os.path.join(state_dir(), "played.json"), [])


def suggest(games, *, players=2, max_time=None, mode=None, theme=None, count=3, interests=None,
            history=None, today=None, rng=None):
    rng = rng or random.Random()
    interests = interests or dict(DEFAULT_THEMES)
    today = today or dt.date.today()
    recent, ratings = {}, {}
    for h in history or []:
        try:
            days = (today - dt.date.fromisoformat(h["date"])).days
        except (KeyError, ValueError):
            continue
        recent[h["name"].lower()] = min(recent.get(h["name"].lower(), 9999), days)
        if h.get("rating"):
            ratings.setdefault(h["name"].lower(), []).append(h["rating"])
    pool = []
    for g in games:
        lo, hi = g["players"]
        if not lo <= players <= hi:
            continue
        if max_time and g["time"] > max_time:
            continue
        if mode and g["mode"] not in (mode, "both"):
            continue
        if theme and theme not in g["themes"]:
            continue
        score = 1.0 + sum(interests.get(t, 0) for t in g["themes"])
        if hi == 2:
            score += 0.5  # built for two
        days = recent.get(g["name"].lower())
        if days is not None and days < 14:
            score *= 0.2  # played in the last two weeks: something else first
        r = ratings.get(g["name"].lower())
        if r:
            score *= 0.6 + sum(r) / len(r) / 5  # 1/5 -> 0.8, 5/5 -> 1.6
        pool.append((score, g))
    picks = []
    while pool and len(picks) < count:
        total = sum(s for s, _ in pool)
        x, acc = rng.uniform(0, total), 0.0
        for i, (s, g) in enumerate(pool):
            acc += s
            if acc >= x:
                picks.append(g)
                pool.pop(i)
                break
    return picks


def find_ytdlp():
    cands = [os.environ.get("YTDLP", ""), os.path.join(real_home(), ".hermes", "hermes-agent", "venv", "bin", "yt-dlp"),
             os.path.join(real_home(), ".local", "bin", "yt-dlp"), shutil.which("yt-dlp") or ""]
    return next((c for c in cands if c and os.access(c, os.X_OK)), None)


def youtube_tutorials(name, limit=5, runner=subprocess.run):
    """Top tutorial videos via yt-dlp search (no API key). Known rules channels rank first."""
    exe = find_ytdlp()
    if not exe:
        return []
    out = []
    for query, lang in ((f"{name} how to play", "en"), (f"{name} zasady gry", "pl")):
        try:
            p = runner([exe, "--flat-playlist", "--dump-single-json", "--no-warnings", f"ytsearch{limit}:{query}"],
                       capture_output=True, text=True, timeout=60)
            entries = json.loads(p.stdout or "{}").get("entries") or []
        except (subprocess.SubprocessError, ValueError, OSError):
            continue
        for e in entries:
            vid = e.get("id")
            if not vid:
                continue
            title = e.get("title") or ""
            channel = e.get("channel") or e.get("uploader") or ""
            rank = 0
            if any(c in channel.lower() for c in TUTORIAL_CHANNELS):
                rank += 3
            if re.search(r"how to play|zasady|rules|jak grać|instrukcja|tutorial", title, re.IGNORECASE):
                rank += 2
            if name.lower().split(":")[0] in title.lower():
                rank += 2
            out.append({"title": title, "channel": channel, "lang": lang, "rank": rank,
                        "minutes": round((e.get("duration") or 0) / 60),
                        "url": f"https://www.youtube.com/watch?v={vid}"})
    out.sort(key=lambda v: -v["rank"])
    return out[:limit]


def workshop_mods(name, limit=3):
    """Tabletop Simulator Workshop mods by text search (IPublishedFileService/QueryFiles)."""
    try:
        resp = steam_api("IPublishedFileService/QueryFiles/v1/", query_type=12, appid=TTS_APPID,
                         search_text=name, numperpage=limit, return_short_description="true",
                         return_vote_data="true").get("response", {})
    except (ConfigError, RuntimeError):
        return []
    mods = []
    for f in resp.get("publishedfiledetails", []) or []:
        fid = f.get("publishedfileid")
        if not fid:
            continue
        mods.append({"title": f.get("title", ""), "subscriptions": f.get("subscriptions", 0),
                     "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={fid}",
                     "open_in_steam": f"steam://url/CommunityFilePage/{fid}"})
    return mods


def bgg_rules_links(name):
    """BoardGameGeek id + files page when BGG_API_TOKEN is set (BGG XML API needs a token since 2025)."""
    token = setting("BGG_API_TOKEN")
    if not token:
        return {}
    url = "https://boardgamegeek.com/xmlapi2/search?" + urllib.parse.urlencode(
        {"query": name, "type": "boardgame", "exact": 1})
    try:
        req = urllib.request.Request(url, headers={**UA, "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            xml = r.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError):
        return {}
    m = re.search(r'<item type="boardgame" id="(\d+)"', xml)
    if not m:
        return {}
    gid = m.group(1)
    return {"bgg": f"https://boardgamegeek.com/boardgame/{gid}", "bgg_files": f"https://boardgamegeek.com/boardgame/{gid}/files"}


def enrich(game, live):
    g = dict(game)
    g["links"] = links(game["name"])
    if live:
        g["videos"] = youtube_tutorials(game["name"], limit=3)
        g["tts_mods"] = workshop_mods(game["name"])
        g["links"].update(bgg_rules_links(game["name"]))
    return g


# ---------- output ----------

MODE_PL = {"coop": "kooperacja", "versus": "rywalizacja", "both": "kooperacja lub rywalizacja"}


def fmt_game(g, idx=None):
    lo, hi = g["players"]
    head = f"{idx}. " if idx else ""
    who = f"{lo} os." if lo == hi else f"{lo}–{hi} os."
    lines = [f"{head}{g['name']} — {MODE_PL[g['mode']]}, {who}, ~{g['time']} min, trudność {g['weight']}/5",
             f"   {g['pitch_pl']}"]
    for v in g.get("videos", [])[:2]:
        lines.append(f"   ▶ {v['title']} ({v['channel']}, {v['minutes']} min): {v['url']}")
    if not g.get("videos"):
        lines.append(f"   ▶ zasady na YouTube: {g['links']['youtube_en']}")
    mods = g.get("tts_mods") or []
    if mods:
        m = mods[0]
        lines.append(f"   🎲 TTS: {m['title']} ({m['subscriptions']} subskrypcji): {m['url']}")
    else:
        lines.append(f"   🎲 TTS Workshop: {g['links']['tts_workshop']}")
    return "\n".join(lines)


def emit(args, data, text):
    print(json.dumps(data, ensure_ascii=False, indent=1) if args.json else text)


# ---------- commands ----------

def cmd_status(args):
    rep = {"api_key": bool(setting("STEAM_API_KEY")), "steam_id": None, "profile_public": None,
           "games_visible": None, "tabletop_simulator": None, "yt_dlp": bool(find_ytdlp()),
           "bgg_token": bool(setting("BGG_API_TOKEN"))}
    problems = []
    try:
        sid = steam_id()
        rep["steam_id"] = sid
        p = player_summary(sid)
        rep["persona"] = p.get("personaname")
        rep["profile_public"] = p.get("communityvisibilitystate") == 3
        try:
            games = owned_games(sid)
            rep["games_visible"] = True
            rep["games_owned"] = len(games)
            tts = next((g for g in games if g["appid"] == TTS_APPID), None)
            rep["tabletop_simulator"] = {"owned": bool(tts), "hours": tts["hours"] if tts else 0}
        except PrivateProfile as e:
            rep["games_visible"] = False
            problems.append(str(e))
    except ConfigError as e:
        problems.append(str(e))
    rep["problems"] = problems
    t = [f"Klucz API: {'jest' if rep['api_key'] else 'BRAK'}",
         f"SteamID: {rep['steam_id'] or 'BRAK'}" + (f" ({rep.get('persona')})" if rep.get("persona") else ""),
         f"Gry widoczne: {rep['games_visible']}" + (f", {rep.get('games_owned')} gier" if rep.get("games_owned") else "")]
    if rep["tabletop_simulator"]:
        tts = rep["tabletop_simulator"]
        t.append(f"Tabletop Simulator: {'tak' if tts['owned'] else 'nie'}, {tts['hours']} h")
    t.append(f"yt-dlp: {'jest' if rep['yt_dlp'] else 'brak (tylko linki do wyszukiwania)'}")
    t += [f"Problem: {p}" for p in problems]
    emit(args, rep, "\n".join(t))
    return 0 if not problems else 2


def cmd_library(args):
    games = owned_games(steam_id())
    key = {"czas": lambda g: -g["hours"], "ostatnio": lambda g: g["last_played"] or "",
           "nazwa": lambda g: g["name"].lower()}[args.sort]
    games.sort(key=key, reverse=args.sort == "ostatnio")
    shown = games[: args.limit] if args.limit else games
    text = [f"Biblioteka Steam: {len(games)} gier, łącznie {round(sum(g['hours'] for g in games))} h"]
    text += [f"- {g['name']}: {g['hours']} h" + (f", ostatnio {g['last_played']}" if g["last_played"] else "")
             for g in shown]
    emit(args, {"count": len(games), "games": shown}, "\n".join(text))
    return 0


def cmd_recent(args):
    games = recent_games(steam_id())
    text = "\n".join(f"- {g['name']}: {g['hours_2weeks']} h w 2 tygodnie" for g in games) or "Nic w ostatnich 2 tygodniach."
    emit(args, {"games": games}, text)
    return 0


def cmd_interests(args):
    path = os.path.join(state_dir(), "interests.json")
    data = load_json(path, {})
    if args.odswiez or not data:
        data = build_interests(steam_id())
    text = [f"Zainteresowania (Steam, {data.get('updated', '?')}):",
            "Motywy: " + ", ".join(f"{k} {v}" for k, v in list(data.get("themes", {}).items())[:8]),
            "Gatunki/tagi: " + ", ".join(data.get("top_genres_tags", [])[:12]),
            "Najwięcej grane: " + ", ".join(f"{g['name']} ({g['hours']} h)" for g in data.get("top_games", [])[:8])]
    if data.get("wishlist"):
        text.append("Lista życzeń: " + ", ".join(data["wishlist"][:10]))
    text.append(f"Plik: {path}")
    emit(args, data, "\n".join(text))
    return 0


def cmd_suggest(args):
    mode = MODE_ALIASES.get((args.tryb or "").lower()) if args.tryb else None
    theme = (args.motyw or "").lower().replace("-", "").replace("science fiction", "scifi") or None
    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    picks = suggest(load_catalogue(), players=args.graczy, max_time=args.czas, mode=mode, theme=theme,
                    count=args.ile, interests=interests_or_default(), history=played_log(), rng=rng)
    if not picks:
        emit(args, {"games": []}, "Nic nie pasuje do tych warunków; poluzuj czas, tryb albo motyw.")
        return 3
    out = [enrich(g, args.live) for g in picks]
    text = f"Propozycje na planszówkę dla {args.graczy} osób:\n" + "\n".join(fmt_game(g, i + 1) for i, g in enumerate(out))
    emit(args, {"games": out}, text)
    return 0


def cmd_rules(args):
    name = args.gra
    cat = {g["name"].lower(): g for g in load_catalogue()}
    base = cat.get(name.lower(), {"name": name})
    data = {"name": base["name"], "links": links(base["name"]), "videos": youtube_tutorials(base["name"]),
            "tts_mods": workshop_mods(base["name"])}
    data["links"].update(bgg_rules_links(base["name"]))
    text = [f"{data['name']}: przygotowanie do gry"]
    if base.get("pitch_pl"):
        text.append(base["pitch_pl"])
    if data["videos"]:
        text.append("Filmy z zasadami:")
        text += [f"- {v['title']} ({v['channel']}, {v['minutes']} min, {v['lang']}): {v['url']}" for v in data["videos"][:3]]
    else:
        text.append(f"Filmy z zasadami: {data['links']['youtube_en']} | po polsku: {data['links']['youtube_pl']}")
    if data["tts_mods"]:
        text.append("Mody do Tabletop Simulator (kliknij Subskrybuj, potem w TTS: Create → Workshop):")
        text += [f"- {m['title']} ({m['subscriptions']} subskrypcji): {m['url']}" for m in data["tts_mods"]]
    else:
        text.append(f"Mody do Tabletop Simulator: {data['links']['tts_workshop']}")
    text.append(f"Instrukcja (PDF) i FAQ: {data['links'].get('bgg_files', data['links']['bgg'])}")
    emit(args, data, "\n".join(text))
    return 0


def cmd_played(args):
    path = os.path.join(state_dir(), "played.json")
    log = played_log()
    entry = {"date": args.data or dt.date.today().isoformat(), "name": args.gra}
    if args.ocena:
        entry["rating"] = args.ocena
    if args.notatka:
        entry["note"] = args.notatka
    log.append(entry)
    save_json(path, log)
    emit(args, entry, f"Zapisane: {args.gra} ({entry['date']})" + (f", ocena {args.ocena}/5" if args.ocena else ""))
    return 0


def cmd_history(args):
    log = played_log()
    text = "\n".join(f"- {h['date']}: {h['name']}" + (f" ({h['rating']}/5)" if h.get("rating") else "")
                     + (f" — {h['note']}" if h.get("note") else "") for h in log[-20:]) or "Jeszcze nic nie zapisane."
    emit(args, {"played": log}, text)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Steam i planszówki dla Hermesa")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, func, aliases=()):
        p = sub.add_parser(name, aliases=list(aliases))
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=func)
        return p

    add("status", cmd_status)
    p = add("biblioteka", cmd_library, ["library"])
    p.add_argument("--sort", choices=["czas", "ostatnio", "nazwa"], default="czas")
    p.add_argument("--limit", type=int, default=20)
    add("ostatnio", cmd_recent, ["recent"])
    p = add("zainteresowania", cmd_interests, ["interests"])
    p.add_argument("--odswiez", "--refresh", action="store_true")
    p = add("planszowka", cmd_suggest, ["planszówka", "boardgame"])
    p.add_argument("--graczy", type=int, default=2)
    p.add_argument("--czas", type=int, help="maks. minut")
    p.add_argument("--tryb", help="coop | rywalizacja")
    p.add_argument("--motyw", help="np. fantasy, scifi, horror")
    p.add_argument("--ile", type=int, default=3)
    p.add_argument("--live", action="store_true", help="dociągnij filmy (yt-dlp) i mody TTS (Steam API)")
    p.add_argument("--seed", type=int)
    p = add("zasady", cmd_rules, ["rules"])
    p.add_argument("gra")
    p = add("zagrane", cmd_played, ["played"])
    p.add_argument("gra")
    p.add_argument("--ocena", type=int, choices=range(1, 6))
    p.add_argument("--notatka")
    p.add_argument("--data", help="YYYY-MM-DD, domyślnie dziś")
    add("historia", cmd_history, ["history"])

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, PrivateProfile) as e:
        print(f"Brak konfiguracji Steam: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"Błąd: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
