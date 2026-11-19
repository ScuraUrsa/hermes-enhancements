---
name: wyjscie
description: "Przygotowanie do wyjścia z domu: pogoda w oknie wyjścia, z kim i jaka okazja, strój z garderoby, lista do spakowania (osobna długa lista z dzieckiem), godzina szykowania. Uruchom ~/.hermes/scripts/wyjscie.py zamiast układać listę z pamięci."
version: 0.1.0
author: Claude Code (for Filip), 2026-10-25
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [wyjście, wychodzę, wychodzimy, co spakować, co zabrać, co ubrać, w co się ubrać, strój, ubiór, lista rzeczy, torba, z dzieckiem, z Teosiem, przygotuj wyjście, pakowanie, packing, outfit]
    related_skills: [weather, home-inventory, hermes-timeplane, research-kit]
---

# wyjscie: przygotowanie do wyjścia z domu

Use when Filip goes out („wychodzę o 15 z Teosiem na plac zabaw”, „co ubrać na wesele w sobotę?”, „co spakować
na basen”), when a timeplane event outside home is coming up, and as a step of other procedures: `randka`
(K77), `wycieczka` (K78), `miejsca` (K106). It does **not** search places (that is `miejsca`) and does **not**
plan the route (that is `trasa`, K107): it takes their results as input. Reply in Polish, short.

## Procedure

1. **Context (no questions yet).** From the calendar event / Filip's message / the calling procedure take:
   start and end, destination city, place type, occasion, who goes (child?), who we meet (CRM: birthday,
   name day, anniversary → gift). Defaults: start from home (Gdańsk), 2 h, no child.
2. **Ask at most 2 questions, only if they change the result:** occasion/dress code when unknown and the event
   looks formal; „z Teosiem?” when unclear. Never ask about the weather or what is in the wardrobe.
3. **Route.** If the `trasa` procedure has run, save its JSON and pass `--trasa-json` (it gives `wyjdz_o`,
   the means of transport per leg and minutes outdoors). Otherwise pass `--transport` from Filip's words and
   `--wyjazd` if known.
4. **Run the script** (one call):
   `python3 ~/.hermes/scripts/wyjscie.py plan --od "<start>" --do "<end>" [--gdzie <city>] [--okazja <o>] [--miejsce <a,b>] [--transport <t,u>] [--z-dzieckiem] [--trasa-json f] [--dodaj "<item>"]...`
   - Dates: `2026-10-31 18:00`, `31.10 18:00`, `jutro 18:00`, `18:00` (today). `--do` may be just `23:00`.
   - Vocabulary: `wyjscie.py slownik` (occasions, place types, transport, weather flags). Unknown occasion: leave it out.
   - Venue-specific requirements found by `miejsca` (field „co zabrać” from the venue's site: e.g. „obowiązkowy
     czepek”, „wejście tylko w skarpetkach antypoślizgowych”) go in `--dodaj`, one per item.
   - `--json` when another procedure consumes the result.
5. **Answer** from the output only: first the departure line („Szykuj się od 14:30, wyjście 15:00”), the weather
   line, the outfit (name + where it lies), then the packing list grouped as printed, then the hints. Matrix:
   send as a checklist; voice: 2 sentences (when to start, the 3 most important items, umbrella yes/no).
6. **Timeplane** (when the outing is in the plan): add a task „Spakuj się: <event>” at `szykuj_od` with the list
   as its body; for formal occasions also „Przygotuj strój (prasowanie, buty)” the evening before.
7. **Re-check** the weather the evening before and 60 min before leaving (with the `trasa` re-check); write
   only if something changes (umbrella appears, warmth level changes by ≥ 1).
8. **After return** (optional, once): „Czegoś zabrakło albo było zbędne?” → add to profile `zawsze` / `pomijaj`.

## Wardrobe

Clothes live in home-inventory (`dom.py`, category `ubrania`). The script reads attributes from the item's note:
`typ:<kurtka|płaszcz|sweter|koszula|spodnie|buty|…> ciepło:<1–5> styl:<sport|casual|smart|elegancki|formalny> woda:<tak|nie> kto:<filip|teos|…> kolor:<…> stan:<czyste|pranie>`.
Adding a piece: `python3 ~/.hermes/scripts/dom.py add "płaszcz wełniany granatowy" --cat ubrania --where "Sypialnia > Szafa" --note "typ:płaszcz ciepło:4 styl:elegancki kto:filip kolor:granat"`.
In the laundry / washed: `dom.py set "<name>" --tag stan:pranie` / `--tag stan:czyste` (changes one attribute, keeps the rest of the note; needs home-inventory PR #43). No wardrobe yet → the script gives a generic outfit; say so once.

## Rules

- Never buy, order a taxi, book or message anyone from here; those steps belong to `trasa`, `randka`, `zakupy`
  and need Filip's „tak” per item.
- Profile with personal items and exceptions: `~/.hermes/autonomy/wyjscie/profil.json` (private, not in git):
  `{"zawsze": ["okulary"], "pomijaj": [], "dziecko": {"pieluchy": true, "wozek": true}}`. Names of people and
  carers stay in Notion/CRM, never in git.
- Exit 2 = bad date: ask again. Weather missing (network, > 16 days ahead): say the forecast will be checked
  closer to the date, still give the list.
