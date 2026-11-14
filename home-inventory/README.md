# home-inventory — spiżarnia i mapa mieszkania

Hermes keeps track of what is at home (food and household chemicals first, clothes and anything else too), **where it
lies** (room → furniture → shelf numbered from the top → sector left/centre/right × front/middle/back) and **until when
it is good**. Filip talks to Hermes (chat or the Home Assistant voice pipeline, which goes through the same Hermes
API), Hermes runs `dom.py` through the skill.

| File | Deployed to |
|---|---|
| `dom.py` | `~/.hermes/scripts/dom.py` (mode 755) |
| `SKILL.md` | `~/.hermes/skills/productivity/home-inventory/SKILL.md` |
| `dom_labels.py` | `~/.hermes/scripts/dom_labels.py` (mode 755) |
| `dom_qr.py` | `~/.hermes/scripts/dom_qr.py` (QR encoder for labels and cards, standard library) |
| `dom_web.py` | `~/.hermes/scripts/dom_web.py` (mode 755), user service on 127.0.0.1:8795 + `tailscale serve` at `/dom` |
| `mapa-przyklad.txt` | example outline for `dom map import` (not deployed) |

- Standard library only (Python 3.10+). State: SQLite `~/.hermes/autonomy/home-inventory/dom.db` (inside `~/.hermes`,
  so the nightly encrypted backup carries it). `DOM_DB` overrides the path; the real home comes from passwd, so it
  works for worker profiles with a fake `$HOME`.
- Runs on **prod** (Filip-facing). No network, no secrets, no LLM calls.
- Polish input is tolerated: diacritics, inflection („mleka” finds „mleko”) and small dictation typos.

## Commands

```
dom map add "Pokój Teosia > Szafa 1 > Półka 3"      create places (missing levels too)
dom map import mapa.txt | -                          indented outline, shelves top to bottom
dom map show ["lodówka"]                              tree with item counts
dom add "mleko" --qty 2 --unit l --exp 20.10 --where "lodówka > półka 1" --side lewo --depth przód
dom where "body Teosia z długim rękawem"              where it is, how many, expiry
dom list --where "lodówka" | --cat chemia
dom use "mleko" [--qty 1 | --all]                     earliest expiry first (FEFO)
dom throw "jogurt" --expired-only --all
dom move "body" --where "komoda > szuflada 2"
dom set "śmietana" --opened --days-after-opening 3
dom expiring --days 7 · dom plan --days 5 · dom remind --days 2 · dom history ["mleko"]
dom batch 'add …' 'add …'                             several writes, each verified (exit 6 if any failed)
dom photo add "pokój Teosia > szafa 1" --file szafa.jpg   photo of a piece of furniture or a room
dom photo mark "… > półka 2" --box 0,20,50,45         correct a shelf's area (% of the photo)
dom show "body Teosia"                                photo with a red circle + directions, prints MEDIA:/path.jpg
```

### Photos and "show me"

- Photos live in `photos/` next to `dom.db` (`~/.hermes/autonomy/home-inventory/photos`, so the nightly backup has
  them). Shelves and drawers without a marked box are equal bands, 1 = top; `--side` picks the left/middle/right third.
  Drawing needs Pillow (on prod already); everything else stays standard library.
- `show` prints `MEDIA:/abs/path.jpg`; Hermes turns that line into an image attachment (Matrix).
- `dom_qr.py` is a small standard-library QR encoder (byte mode, versions 1–40), checked against OpenCV's decoder;
  `dom_labels.py` uses it, so labels need no extra package.

Exit codes: 0 ok, 1 error, 2 bad date/sector, 3 not found, 4 ambiguous, 5 unknown place, 6 batch partly failed. `--json` everywhere.

## QR labels and business cards (idea from Homebox's label maker, 2026-10-31)

```
dom code "Pokój Teosia > Szafa 1" --sub      codes D001, D002, ... for the wardrobe and every shelf in it
dom code --list                              all codes;  "#D007" (or "D7", "d-007") works wherever a place is expected
dom_labels.py labels --where "Pokój Teosia" [--assign] [--size 70x37 --cols 3 --rows 8] [--outline] --out n.html
dom_labels.py labels D001 D004 --copies 2 --out n.html
dom_labels.py card --name "..." --phone ... --email ... [--title ...] [--org ...] [--url ...] --out wizytowki.html
dom_web.py [--port 8795]                     the page a label opens: what lies there, what is inside (read-only)
```

- A label = QR (URL `$DOM_LABEL_URL/<code>`, default `https://hermes-vm-1.tail5c846a.ts.net/dom/<code>`, tailnet only),
  the code in big letters (works by voice without a phone: „co jest w D007”) and the path.
- Output is HTML with exact millimetre sizes for A4 sticker sheets (default 3×8 of 70×37 mm); print at 100%.
- Business cards: 85×55 mm, 10 per A4, with a vCard QR (a phone camera saves the contact, no app needed).
- Codes live in `places.code` (added to an existing DB automatically). They never change when a place is renamed or
  moved, so printed labels stay valid; a removed place's code is not reused.

## Integration

- **Shopping list** stays in timeplane (🛒 Zakupy). After „przywiozłem X z listy”, the skill adds X here and ticks it
  off there; when `use` empties an item it asks whether to put it on the list.
- **Meal planning**: the timeplane meal procedure should call `dom plan --days 5` and build meals around what it lists.
- **Morning reminder** (optional): a no-agent Hermes cron job running `dom remind --days 2`; empty output = nothing
  to say.

## Deploy (until a WOBI role exists)

```bash
scp dom.py dom_qr.py SKILL.md ubuntu@<vm>:/tmp/ && ssh ubuntu@<vm> 'install -m 755 /tmp/dom.py ~/.hermes/scripts/ \
  && install -m 644 /tmp/dom_qr.py ~/.hermes/scripts/ \
  && install -Dm 644 /tmp/SKILL.md ~/.hermes/skills/productivity/home-inventory/SKILL.md'
```

## Test

```bash
python3 -m pytest -q home-inventory/test_dom.py      # offline, fixed date via DOM_TODAY
python3 -m pytest -q home-inventory/test_labels_web.py
```
