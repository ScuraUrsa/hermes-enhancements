---
name: home-inventory
description: "Spis rzeczy w domu i mapa mieszkania: co mamy (spożywka, chemia, ubrania), gdzie leży (pokój, szafa, półka, sektor), do kiedy ważne. Użyj ~/.hermes/scripts/dom.py zamiast pamięci."
version: 0.3.0
author: Claude Code (for Filip), 2026-10-16
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [spiżarnia, lodówka, zakupy, przywiozłem, termin ważności, przydatność, przeterminowane, gdzie jest, gdzie mam, szafa, szafka, półka, mapa mieszkania, posiłek, obiad, chemia, inventory, pantry, expiry]
    related_skills: [hermes-timeplane, weather]
---

# home-inventory: spiżarnia i mapa mieszkania

What is at home, where it lies, until when it is good. Run `python3 ~/.hermes/scripts/dom.py ...` (below `dom`)
with the terminal tool. Reply in Polish, short; voice: 1–2 sentences, no `#id`s.

## Procedure (every request)

1. **Split** Filip's message into single items (one product, one piece of furniture, one move).
2. **Write one `dom` line per item.** One item → run it. Two or more → run them together in ONE call:
   `dom batch 'add masło --exp 30.10 --where "lodówka > półka 3"' 'add kefir --qty 2 --exp 19.10'`
   dom runs every line and checks it in the database.
3. **Read the output.** Say only what has ✅ / exit=0. For each ❌ say it was NOT saved and why.
   Never say „dodałem / zapisałem” without that output. Never print a command instead of running it.
4. Questions („gdzie”, „co jest”, „co się kończy”, meals) are answered only from `dom` output.

## Commands

| Filip says | Line |
|---|---|
| „przywiozłem mleko 2 l, ważne do 20.10, na górną półkę lodówki” | `add mleko --qty 2 --unit l --exp 20.10 --where "lodówka > półka 1"` |
| „płyn do naczyń pod zlewem” | `add "płyn do naczyń" --cat chemia --where "szafka pod zlewem"` |
| „body Teosia, szafa, 2. półka od dołu, z lewej z przodu, 3 sztuki” | `add "body Teosia" --qty 3 --cat ubrania --where "pokój Teosia > szafa 1 > półka 2 od dołu" --side lewo --depth przód` |
| „ważny do 22.10” / „to były 3 sztuki” (correction) | `set "jogurt grecki" --exp 22.10` / `--qty 3` (never a second add) |
| „otworzyłem śmietanę, 3 dni po otwarciu” | `set śmietana --opened --days-after-opening 3` |
| „zużyłem litr mleka” / „skończyło się” | `use mleko --qty 1` / `use mleko --all` |
| „wyrzuciłem przeterminowany ser” | `throw ser --expired-only --all` |
| „przełożyłem body do komody, 2. szuflada” | `move body --where "pokój Teosia > komoda > szuflada 2"` |
| „gdzie jest X?” | `where X` |
| „co jest w lodówce?” | `list --where lodówka` |
| „co się kończy w tym tygodniu?” | `expiring --days 7` |
| „co na obiad?” (any meal planning) | `plan --days 5` (always 5), then meals using that food + where it lies |
| „szafa z 5 półkami w sypialni”, „komoda z 4 szufladami” | `map add "Sypialnia > Szafa" --shelves 5` / `map add "Pokój Teosia > Komoda" --drawers 4` |
| „lodówka ma półki na drzwiach” | `map add "Kuchnia > Lodówka > Drzwi lodówki"` |
| „zmień nazwę szafy na Szafa biała” | `map rename "pokój Teosia > szafa 1" "Szafa biała"` |
| „wynieśliśmy komodę” | `map rm "pokój Teosia > komoda"` |
| „pokaż mapę (pokoju Teosia)” | `map show ["pokój Teosia"]` |

- Names: plain Polish nominative („mleko”, „ser żółty”). `--exp` takes Filip's words (`20.10`, `10.2026`,
  „20 października”, „za 5 dni”, `jutro`). Fresh food without a date: ask once for it.
- No `--where`: the item goes where it usually lies. Shelves count from the top (`półka 1`); `półka 2 od dołu` works.
- Paths go room → furniture → shelf with `>`; any unique part is enough. Missing levels are created by `map add`.
- `dom <command> --help` shows exact arguments.

## Exit codes

0 ok · 2 bad date/sector: ask again · 3 not found · 4 several matches: ask which · 5 unknown place: `map add` it only
if Filip described it, else ask · 6 batch: some lines failed (see ❌).

## Not here

The shopping list is timeplane (🛒 Zakupy): after „przywiozłem … z listy” add here, then tick them off there.
When `use` says „ostatnia sztuka”, ask whether to put it on the list. Buying/paying needs Filip's OK.
