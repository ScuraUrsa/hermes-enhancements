---
name: home-inventory
description: "Spis rzeczy w domu i mapa mieszkania: co mamy (spożywka, chemia, ubrania), gdzie leży (pokój, szafa, półka, sektor), do kiedy ważne. Użyj ~/.hermes/scripts/dom.py zamiast pamięci."
version: 0.1.0
author: Claude Code (for Filip), 2026-10-15
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [spiżarnia, lodówka, zakupy, przywiozłem, termin ważności, przydatność, przeterminowane, gdzie jest, gdzie mam, szafa, szafka, półka, mapa mieszkania, posiłek, obiad, chemia, inventory, pantry, expiry]
    related_skills: [hermes-timeplane, weather]
---

# home-inventory — spiżarnia i mapa mieszkania (Filip, 2026-10-15)

The single source of truth for what is at home, where it lies and until when it is good. State is a SQLite file
in `~/.hermes/autonomy/home-inventory/dom.db` (nightly backup). Never answer "where is X" or "what expires" from
memory or Honcho: run the script. Talk to Filip in Polish, short; in voice replies one or two sentences, no tables,
no `#id`s.

Run: `python3 ~/.hermes/scripts/dom.py <command> ...` (below: `dom`). Add `--json` when you need to compute.
`dom <command> --help` shows the exact arguments.

## Hard rules

1. **Act, then confirm.** Every change (bought, used, moved, new furniture, rename) is a `dom` call run through the
   terminal tool. Never write „dodałem / zapisałem / zaktualizowałem” before you have seen `exit=0` from that call,
   and never print a command as text instead of running it.
2. **One call per thing.** Three products = three `dom add` calls; a fridge with three shelves = one `dom map add`
   per shelf (or one `dom map import`).
3. **Answers come from `dom` output**, never from memory: run `dom where` / `dom list` / `dom plan` first.

## When to use

| Filip says | Do |
|---|---|
| „gdzie mam body Teosia z długim rękawem?”, „gdzie jest płyn do naczyń?” | `dom where "body Teosia z długim rękawem"` |
| „co jest w lodówce?”, „co leży na drugiej półce w szafie Teosia?” | `dom list --where "lodówka"` / `dom list --where "pokój Teosia > szafa > półka 2"` |
| „przywiozłem mleko 2 litry, ważne do 20.10, i jogurt do jutra” | one `dom add` per product (see Adding), then tick them off the shopping list (below) |
| „włożyłem ser do lodówki na górną półkę z lewej” | `dom add "ser żółty" --where "lodówka > półka 1" --side lewo` |
| „zużyłem / zjedliśmy / skończyło się mleko” | `dom use "mleko"` (`--qty N`, or `--all` when it is gone) |
| „wyrzuciłem przeterminowany jogurt” | `dom throw "jogurt" --expired-only --all` |
| „przełożyłem body do komody, druga szuflada” | `dom move "body" --where "pokój Teosia > komoda > szuflada 2"` |
| „otworzyłem śmietanę, po otwarciu 3 dni” | `dom set "śmietana" --opened --days-after-opening 3` |
| „co się kończy?”, „co się przeterminuje w tym tygodniu?” | `dom expiring --days 7` |
| meal planning (the timeplane meal procedure, „co na obiad?”, „zaplanujmy posiłki”) | `dom plan --days 5` first (keep 5 days even for „jutro”), then propose meals that use the listed food, saying where each item is |
| describing the flat: „w kuchni mam lodówkę z 3 półkami…” | `dom map add "Kuchnia > Lodówka > Półka 1"` (one per shelf) or write an outline and `dom map import` |
| „pokaż mapę mieszkania”, „co jest w szafie Teosia” | `dom map show ["pokój Teosia > szafa 1"]` |
| „lodówka ma półki na drzwiach”, „w sypialni jest szafa z 5 półkami” | `dom map add "Sypialnia > Szafa > Półka 1"` … one per shelf (missing room/furniture levels are created) |
| „zmień nazwę szafy na Szafa biała” | `dom map rename "pokój Teosia > szafa 1" "Szafa biała"` (path first, then the new name) |
| „wynieśliśmy komodę” | `dom map rm "pokój Teosia > komoda"` |

## When not to use

- The shopping list itself („dopisz do listy zakupów masło”) lives in timeplane (🛒 Zakupy): use the timeplane skill.
  This skill only records what is already at home.
- Buying online or paying: not here, and paying needs Filip's OK.

## Adding

`dom add NAME [--qty N] [--unit l|kg|g|szt|op] [--exp DATE] [--where PLACE] [--side lewo|środek|prawo] [--depth przód|środek|tył] [--cat spożywcze|chemia|ubrania|inne] [--alias "inne nazwy"]`

- NAME: the plain Polish product name in the nominative („mleko”, „jogurt naturalny”, „płyn do naczyń”,
  „body Teosia z długim rękawem”). Reuse the existing name (check `dom where`) so batches stack up.
- `--exp` accepts what Filip says: `20.10`, `20.10.2026`, `10.2026` (end of month), `„20 października”`,
  `„za 5 dni”`, `jutro`. Pass his words; exit code 2 means ask him again.
- `--cat chemia` for cleaning/washing products, `ubrania` for clothes. With `--exp` and no `--cat`, food is assumed.
- No `--where`: the item goes where it usually lies (its last place). If the reply says „Nie wiem, gdzie to leży”,
  ask Filip and run `dom move`.
- Shelves are numbered from the top (`półka 1` = top). „Druga od dołu” → `półka 2 od dołu` also works.

After „przywiozłem … z listy zakupów”: add each product here, then tick the same products off the timeplane shopping
list. Ask once for missing expiry dates of fresh food („Jaki termin ma jogurt?”); chemicals and clothes need none.

## Places (apartment map)

Paths go from the room down: `"Pokój Teosia > Szafa 1 > Półka 3"`; `>` or `/` separate levels and any unique part
of the path is enough (`"lodówka > półka 2"`). The sector on a shelf is `--side` (lewo/środek/prawo) and `--depth`
(przód/środek/tył). Import an outline (2 spaces per level; shelves top to bottom; `| aliasy`, `# uwaga`):

```
Kuchnia
  Lodówka | lodowka
    Półka 1
    Półka 2
  Szafka pod zlewem | chemia  # środki czystości
Pokój Teosia | pokój syna
  Szafa 1
    Półka 1
```

`echo "<outline>" | dom map import -` (re-import is safe: existing places are kept). `dom map rename`, `dom map rm`
(only empty places).

## Exit codes

0 ok · 1 error · 2 bad date or sector: ask again · 3 nothing found (the message says where the item usually lies, if
known) · 4 several matches: ask Filip which one, or pass `#id` from the listing · 5 unknown place: create it with
`dom map add` only if Filip described it, otherwise ask.

## Answering

- „gdzie”: room → furniture → shelf (from the top/bottom) → sector, e.g. „W pokoju Teosia, szafa 1, druga półka od
  góry, po lewej z przodu.”
- Expiry: say the date and how many days are left; mention expired food first.
- When `use` reports the last piece („ostatnia sztuka”), ask whether to add it to the shopping list.

## Reminder

A no-agent cron job may run `dom remind --days 2` every morning; it prints nothing when nothing expires, otherwise
a short 🧺 list to deliver to Filip.
