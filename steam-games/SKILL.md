---
name: steam-games
description: "Steam Filipa (biblioteka gier, co ostatnio grał, jego zainteresowania) i propozycje planszówek dla 2 osób do Tabletop Simulatora z zasadami i filmami. Uruchom ~/.hermes/scripts/steam-games/steam_games.py zamiast zgadywać."
version: 1.0.0
author: Claude Code (for Filip), 2026-10-15
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [steam, gry, biblioteka gier, tabletop simulator, tts, planszówka, planszówki, gra planszowa, w co zagramy, zasady gry, board game, zainteresowania]
    related_skills: [hermes-operations]
---

# steam-games — Steam i planszówki (Filip, 2026-10-15)

Filip has ADHD and likes fantasy and science fiction. He owns **Tabletop Simulator** on Steam and wants Hermes to
suggest a board game for two people (him + one person), with the rules ready, even if they don't own the physical
game. Steam also tells Hermes what Filip likes, for gamification and memory-palace themes.

## When to use

- "w co zagramy?", "zaproponuj planszówkę na dwie osoby", "coś kooperacyjnego na pół godziny", "planszówka fantasy"
- "jak się gra w X?", "przygotuj mnie do X", "zasady X"
- "co mam na Steamie?", "w co ostatnio grałem?", "jakie gry lubię?"
- "zagraliśmy w X, było super" → log it (`zagrane`, rating 1–5 if he gives one)
- "jakie mam nowe osiągnięcia?", "ile mam XP?" → `osiagniecia`
- "jak długo dziś grałem?", "przypominaj mi o przerwie" → `przerwa` (the cron job `steam-break` reminds by itself)
- Before designing anything themed for Filip (gamification, rewards, mind maps, memory palace): read
  `~/.hermes/autonomy/steam-games/interests.json` (`themes`, `top_games`, `wishlist`).

## When not to use

- Buying games, adding to the wishlist, writing to his Steam account or friends: Steam access is read-only;
  anything that spends money needs Filip's OK and he does it himself.
- Films: Steam has none; say so instead of guessing.

## Run

`python3 ~/.hermes/scripts/steam-games/steam_games.py <command> [--json]`

| Filip asks | Command |
|---|---|
| suggest a board game | `planszowka --live` (+ `--czas 30`, `--tryb coop` / `rywalizacja`, `--motyw fantasy` / `scifi` / `horror`, `--ile 3`) |
| rules / prepare a game | `zasady "<English title>"` |
| we played X | `zagrane "<title>" [--ocena 1-5] [--notatka "..."]` |
| what we played | `historia` |
| what's on Steam | `biblioteka [--sort czas\|ostatnio\|nazwa] [--limit 20]` |
| what he played lately | `ostatnio` |
| what he likes | `zainteresowania` (`--odswiez` re-reads Steam; do it at most once a week) |
| new achievements, XP | `osiagniecia` (`--wszystkie` scans his 50 most played games, `--dni 30` for the summary window) |
| current game session | `przerwa` |
| is it set up | `status` |

- Exit 2 = Steam not configured or game details private: board-game suggestions still work (they don't need Steam).
  Tell Filip once and point to the setup task in timeplane; don't repeat it every time.
- Exit 3 = nothing matches: relax the time or mode and run again.
- Use English titles for `zasady` (Workshop and YouTube search work best in English).

## Achievements as XP

New Steam achievements are worth XP by rarity (share of all players who have it): legendarne < 1 % = 100,
epickie < 5 % = 50, rzadkie < 20 % = 25, zwykłe = 10. Each one is appended to
`~/.hermes/autonomy/steam-games/xp.jsonl` (`source: steam-achievement`); the gamification system reads that file.
Achievements unlocked before the first sync are history and give no XP. Cron `steam-achievements` (21:00)
reports new ones; celebrate them briefly, fantasy-style, without exaggerating.

## Break reminder

Cron `steam-break` (every 10 min) sends one reminder after `STEAM_BREAK_MINUTES` (120) of continuous play,
then every `STEAM_BREAK_REPEAT` (60) minutes. If Filip says it was planned play or asks to stop the reminders
today, don't argue; if he wants a different limit, set `STEAM_BREAK_MINUTES` in `~/.hermes/.env`.
Never shame him for playing; the reminder is support for hyperfocus, not a ban.

## Answer

Polish, short. For a suggestion: 2–3 games, one line why each fits (mode, time, theme), the tutorial video link and
the Tabletop Simulator mod link. Ask which one they pick. Then for the chosen game:

1. Give the best tutorial video (prefer Watch It Played / Gaming Rules! or a Polish one if Filip prefers Polish).
2. Give the TTS mod link: Filip clicks **Subskrybuj** on the Workshop page, then in Tabletop Simulator
   **Create → Singleplayer/Multiplayer → Workshop** and loads it; the other person joins his server (both need TTS).
3. If `ytdigest` is installed, offer a Polish rules summary: `ytdigest run <video url>`, then write a short
   "jak grać w 2 osoby" (setup, turn, how to win, 2-player changes) from the report, max 10 lines.

Never say the game is "ready" in TTS: Hermes cannot subscribe or load mods for him.
