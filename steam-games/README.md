# steam-games — Steam library and 2-player board games for Hermes

Asked by Filip on 2026-10-13: give Hermes access to his Steam (to learn what he likes, for gamification and
memory-palace themes) and let it always propose a two-person board game in **Tabletop Simulator** with its rules,
ideally a YouTube tutorial, so they can play without owning the physical copy.

| File | Deployed to (prod) |
|---|---|
| `steam_games.py` | `~/.hermes/scripts/steam-games/steam_games.py` (mode 755) |
| `boardgames.json` | `~/.hermes/scripts/steam-games/boardgames.json` |
| `steam_break.sh`, `steam_achievements.sh` | `~/.hermes/scripts/` (mode 755), no-agent cron wrappers |
| `SKILL.md` | `~/.hermes/skills/leisure/steam-games/SKILL.md` |
| state | `~/.hermes/autonomy/steam-games/` (`interests.json`, `played.json`, caches; in the nightly backup) |

Standard library only (Python ≥ 3.9). Commands: `status`, `biblioteka`, `ostatnio`, `zainteresowania`,
`planszowka`, `zasady`, `zagrane`, `historia`, `osiagniecia`, `przerwa`; all take `--json`. See the docstring in `steam_games.py`.

## Configuration

Read from the environment, then `~/.hermes/.env` (real home via `pwd`, so worker profiles work too):

| Name | What | Where it comes from |
|---|---|---|
| `STEAM_API_KEY` | Steam Web API key (secret) | Filip: <https://steamcommunity.com/dev/apikey>, stored in Bitwarden as `STEAM_API_KEY` |
| `STEAM_ID` | SteamID64 or profile vanity name / URL (not secret) | Filip's profile URL |
| `BGG_API_TOKEN` | optional BoardGameGeek XML API token | only adds direct BGG game/rulebook links |

Steam only returns the game list when the profile's **Game details** are Public
(<https://steamcommunity.com/my/edit/settings>); `GetOwnedGames` returns `{}` otherwise (exit code 2).

## Achievements → XP and break reminder (added 2026-10-15, Filip: "Tak")

- `osiagniecia`: `ISteamUserStats/GetPlayerAchievements` for recently played games (or the 50 most played with
  `--wszystkie`) + `GetGlobalAchievementPercentagesForApp` for rarity. Points: < 1 % = 100, < 5 % = 50,
  < 20 % = 25, else 10. The first sync is a baseline (no XP for old unlocks); later unlocks are appended to
  `xp.jsonl`, the feed for the gamification work in the project thread "Medytacja i grywalizacja przy ADHD".
- `przerwa`: reads "currently playing" (`gameextrainfo`) from `GetPlayerSummaries`; one reminder after
  `STEAM_BREAK_MINUTES` (120) of continuous play, repeated every `STEAM_BREAK_REPEAT` (60). A session ends after
  20 min without a game and is logged to `sessions.jsonl` (weekly play time).
- Both have `--cron`: output only when there is news; config or network errors go to stderr with exit 0, so a
  missing key never spams Filip (`status` shows it). Cron on prod (active only):

```bash
hermes cron create "every 10m" --name steam-break --script steam_break.sh --no-agent --deliver matrix
hermes cron create "0 21 * * *" --name steam-achievements --script steam_achievements.sh --no-agent --deliver matrix
```

## Data sources

- Steam Web API: `GetOwnedGames`, `GetRecentlyPlayedGames`, `GetPlayerSummaries`, `ResolveVanityURL`,
  `IWishlistService/GetWishlist`, `IPublishedFileService/QueryFiles` (Tabletop Simulator Workshop, app 286160).
- Store `appdetails` (genres) + SteamSpy `appdetails` (user tags such as Fantasy, Sci-fi), cached 30 days.
  Interests = tags/genres of the 25 most played games weighted by playtime (capped at 200 h) + wishlist,
  mapped to themes; Filip's own "fantasy + sci-fi" always stays at weight ≥ 1.
- YouTube tutorials: `yt-dlp ytsearch` (no API key), English "how to play" + Polish "zasady gry"; known rules
  channels (Watch It Played, Gaming Rules!, …) rank first. Without yt-dlp only search links are given.
- `boardgames.json`: 35 curated games playable by two (fantasy/sci-fi first), with mode, time, weight and a
  Polish one-line pitch. Rules themselves come from the tutorial video, not from this file.

## Decisions

- **Curated list + live search, not BGG scraping**: BGG's XML API needs a registered token since 2025, and a
  short list tuned to Filip's taste gives better picks than BGG rankings. BGG is optional.
- **Read-only Steam**: only the Web API key (read scope). No Steam login, no OpenID, nothing that can buy or
  change his account. Subscribing to a Workshop mod stays a click for Filip (the API has no user-auth path).
- **Suggestion scoring**: 1 + interest weights of the game's themes, +0.5 for games built for two, ×0.2 if
  played in the last 14 days, × (0.6 + avg rating / 5) when rated. Weighted random so it is not the same list
  every time.
- **Not done yet**: controlling Tabletop Simulator itself (its External Editor API listens on the PC at
  localhost:39999; the VM can't reach it, would need `hermes-gui-automation` or a PC-side bridge); films
  (Steam has none; Trakt or Letterboxd would be the source).

## Test

```bash
python3 -m pytest -q steam-games/tests      # offline, Steam/YouTube faked
```

## Deploy

```bash
scp steam_games.py boardgames.json steam_break.sh steam_achievements.sh SKILL.md ubuntu@<vm>:/tmp/
ssh ubuntu@<vm> 'install -Dm 755 /tmp/steam_games.py ~/.hermes/scripts/steam-games/steam_games.py \
  && install -m 644 /tmp/boardgames.json ~/.hermes/scripts/steam-games/ \
  && install -m 755 /tmp/steam_break.sh /tmp/steam_achievements.sh ~/.hermes/scripts/ \
  && install -Dm 644 /tmp/SKILL.md ~/.hermes/skills/leisure/steam-games/SKILL.md'
# then add STEAM_API_KEY (from Bitwarden) and STEAM_ID to ~/.hermes/.env, and run:
ssh ubuntu@<vm> 'python3 ~/.hermes/scripts/steam-games/steam_games.py status && python3 ~/.hermes/scripts/steam-games/steam_games.py zainteresowania --odswiez'
```
