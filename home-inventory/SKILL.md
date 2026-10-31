---
name: home-inventory
description: "Spis rzeczy w domu i mapa mieszkania: co mamy (spożywka, chemia, ubrania), gdzie leży (pokój, szafa, półka, sektor), do kiedy ważne. Użyj ~/.hermes/scripts/dom.py zamiast pamięci."
version: 0.4.0
author: Claude Code (for Filip), 2026-10-16
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [spiżarnia, pokaż gdzie, zdjęcie szafy, etykiety, kod QR, pojemnik, lodówka, zakupy, przywiozłem, termin ważności, przydatność, przeterminowane, gdzie jest, gdzie mam, szafa, szafka, półka, mapa mieszkania, posiłek, obiad, chemia, inventory, pantry, expiry]
    related_skills: [hermes-timeplane, weather]
---

# home-inventory: spiżarnia i mapa mieszkania

What is at home, where it lies, until when it is good. Use the terminal tool; every command starts with
`python3 ~/.hermes/scripts/dom.py` exactly as below (a bare `dom` does not exist). Reply in Polish, short; voice: 1–2 sentences, no `#id`s.

## Procedure (every request)

1. **Split** Filip's message into single items (one product, one piece of furniture, one move).
2. **Write one line per item.** One item → run it. Two or more → run them together in ONE call:
   `python3 ~/.hermes/scripts/dom.py batch 'add masło --exp 30.10 --where "lodówka > półka 3"' 'add kefir --qty 2 --exp 19.10'`
   It runs every line and checks it in the database. Multi-word names and paths always in "double quotes".
3. **Read the output.** Say only what has ✅ / exit=0. For each ❌ say it was NOT saved and why.
   Never say „dodałem / zapisałem” without that output. Never print a command instead of running it.
   After every command, always answer Filip in words (never an empty reply).
   Exit 5 (unknown place): ask Filip where that place is; do not paste commands to him.
4. Questions („gdzie”, „co jest”, „co się kończy”, meals) are answered only from its output.

## Commands

| Filip says | Command |
|---|---|
| „przywiozłem mleko 2 l, ważne do 20.10, na górną półkę lodówki” | `python3 ~/.hermes/scripts/dom.py add mleko --qty 2 --unit l --exp 20.10 --where "lodówka > półka 1"` |
| „płyn do naczyń pod zlewem” | `python3 ~/.hermes/scripts/dom.py add "płyn do naczyń" --cat chemia --where "szafka pod zlewem"` |
| „body Teosia, szafa, 2. półka od dołu, z lewej z przodu, 3 sztuki” | `python3 ~/.hermes/scripts/dom.py add "body Teosia" --qty 3 --cat ubrania --where "pokój Teosia > szafa 1 > półka 2 od dołu" --side lewo --depth przód` |
| „ważny do 22.10” / „to były 3 sztuki” (correction) | `python3 ~/.hermes/scripts/dom.py set "jogurt grecki" --exp 22.10` / `--qty 3` (never a second add) |
| „otworzyłem śmietanę, 3 dni po otwarciu” | `python3 ~/.hermes/scripts/dom.py set śmietana --opened --days-after-opening 3` |
| „zużyłem litr mleka” / „skończyło się” | `python3 ~/.hermes/scripts/dom.py use mleko --qty 1` / `python3 ~/.hermes/scripts/dom.py use mleko --all` |
| „płaszcz wełniany granatowy, ciepły, elegancki, do sypialni” (clothes) | `python3 ~/.hermes/scripts/dom.py add "płaszcz wełniany granatowy" --cat ubrania --where "Sypialnia > Szafa" --note "typ:płaszcz ciepło:4 styl:elegancki woda:nie kto:filip kolor:granat stan:czyste"` |
| „płaszcz w praniu” / „wyprany” | `python3 ~/.hermes/scripts/dom.py set "płaszcz wełniany granatowy" --tag stan:pranie` / `--tag stan:czyste` |
| „wyrzuciłem przeterminowany ser” | `python3 ~/.hermes/scripts/dom.py throw ser --expired-only --all` |
| „przełożyłem body do komody, 2. szuflada” | `python3 ~/.hermes/scripts/dom.py move body --where "pokój Teosia > komoda > szuflada 2"` |
| „gdzie jest X?” | `python3 ~/.hermes/scripts/dom.py where "X"` |
| „pokaż, gdzie jest X” / „gdzie dokładnie…” | `python3 ~/.hermes/scripts/dom.py show "X"`: copy its `MEDIA:/…` line unchanged into your reply (sends the photo with a circle); say the directions in 1–2 sentences |
| Filip sends a photo: „to szafa w pokoju Teosia” | `python3 ~/.hermes/scripts/dom.py photo add "pokój Teosia > szafa 1" --file /path/to/the/photo.jpg` (shelves are marked automatically, top to bottom) |
| „na zdjęciu półka 2 jest wyżej / tylko lewa połowa” | `python3 ~/.hermes/scripts/dom.py photo mark "pokój Teosia > szafa 1 > półka 2" --box 0,20,50,45` (left,top,right,bottom in % of the photo) |
| „wydrukuj etykiety na pojemniki” / „wizytówki szafy” | `python3 ~/.hermes/scripts/dom.py label` (all containers) / `python3 ~/.hermes/scripts/dom.py label "pokój Teosia > szafa 1" --format wizytowka --with-children`; send the `MEDIA:` file |
| a message with `[P12]` (scanned label) | `python3 ~/.hermes/scripts/dom.py where "<the whole message>"` (lists what is in that box/shelf) |
| „co jest w lodówce?” | `python3 ~/.hermes/scripts/dom.py list --where lodówka` |
| „co się kończy w tym tygodniu?” | `python3 ~/.hermes/scripts/dom.py expiring --days 7` |
| „co na obiad?” (any meal planning) | `python3 ~/.hermes/scripts/dom.py plan --days 5` (always 5), then meals using that food + where it lies |
| „szafa z 5 półkami w sypialni”, „komoda z 4 szufladami” | `python3 ~/.hermes/scripts/dom.py map add "Sypialnia > Szafa" --shelves 5` / `python3 ~/.hermes/scripts/dom.py map add "Pokój Teosia > Komoda" --drawers 4` |
| „lodówka ma półki na drzwiach” | `python3 ~/.hermes/scripts/dom.py map add "Kuchnia > Lodówka > Drzwi lodówki"` |
| „zmień nazwę szafy na Szafa biała” | `python3 ~/.hermes/scripts/dom.py map rename "pokój Teosia > szafa 1" "Szafa biała"` |
| „wynieśliśmy komodę” | `python3 ~/.hermes/scripts/dom.py map rm "pokój Teosia > komoda"` |
| „pokaż mapę (pokoju Teosia)” | `python3 ~/.hermes/scripts/dom.py map show ["pokój Teosia"]` |

- Names: plain Polish nominative („mleko”, „ser żółty”). `--exp` takes Filip's words (`20.10`, `10.2026`,
  „20 października”, „za 5 dni”, `jutro`). Fresh food without a date: ask once for it.
- No `--where`: the item goes where it usually lies (do not ask where or how much; qty defaults to 1). Shelves count from the top (`półka 1`); `półka 2 od dołu` works.
- Paths go room → furniture → shelf with `>`; any unique part is enough. Missing levels are created by `map add`.
  The side/depth on a shelf go in `--side`/`--depth`, not in `--where`.
- Clothes: always `--cat ubrania` and a note with `typ: ciepło:1–5 styl:sport|casual|smart|elegancki|formalny
  woda:tak|nie kto:filip|teos kolor: stan:czyste|pranie` (only keys Filip's words give; the `wyjscie` skill reads them).
  Change one attribute with `set … --tag key:value`, never by rewriting `--note`.
- `python3 ~/.hermes/scripts/dom.py <command> --help` shows exact arguments.

## Exit codes

0 ok · 2 bad date/sector: ask again · 3 not found · 4 several matches: ask which · 5 unknown place: `map add` it only
if Filip described it, else ask · 6 batch: some lines failed (see ❌).

## Not here

The shopping list is timeplane (🛒 Zakupy): after „przywiozłem … z listy” add here, then tick them off there.
When `use` says „ostatnia sztuka”, ask whether to put it on the list. Buying/paying needs Filip's OK.
