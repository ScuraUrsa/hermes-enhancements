---
name: research-kit
description: >-
  Runs a fixed, exhaustive research procedure and writes a sourced report so Filip never has to search the web
  himself. Picks a research type (wiedza, decyzja-techniczna, zakupy, wycieczka, randka, osoba-firma,
  zdrowie-prawo-finanse, monitoring), loads its checklist of mandatory fields and sources, checks every link
  against the bibliography database before opening it, and enforces source, coverage and verification gates.
  Use for any request to research, compare, find the best option, plan a trip or a date, choose what to buy,
  or explain a topic ("zrób research", "zbadaj", "porównaj", "co kupić", "zaplanuj wyjazd", "gdzie na randkę",
  "jak działa").
version: 0.2.0
license: MIT
argument-hint: "[typ] [temat]"
metadata:
  hermes:
    tags: [Research, Reports, Citations, Bibliography, Shopping, Travel]
    category: research
    related_skills: [grounded-citations, llm-wiki, product-price-monitor]
    requires_toolsets: [web]
    config:
      - key: research.output_dir
        description: Working directory for research runs
        default: "~/research"
---

# Research kit

Plan i uzasadnienie: `plany/research/2026-10-23-standaryzacja-researchu/plan.md` (K76). Typy rozwijają K77–K80.

Every run follows the 8 steps below in order. Write each step's output to the run directory, so the work
survives context compaction. Do not skip a gate; if a gate fails, go back as the step says.

## Run checklist (copy into `brief.md` and tick as you go)

```
- [ ] 0 Start: date, type, mode, run dir
- [ ] 1 Brief: goal, scope, budget, dates, criteria, assumptions
- [ ] 2 Plan: questions, mandatory fields table, perspectives, sources, call budget
- [ ] 3 Gather: bibliography check first, broad → narrow, notes on disk
- [ ] 4 Source registry: every used or dropped source has a verdict in the bibliography; gates pass
- [ ] 5 Coverage: every mandatory field filled or marked "nie znaleziono"
- [ ] 6 Write: from notes and registry only, report template
- [ ] 7 Counter-review + verification of 5 key claims
- [ ] 8 Validate, deliver, track the decision's sources, ask for feedback
```

## Bibliography (applies to every web lookup, not only to research runs)

`skrypty/bib.py` keeps a memory of every link: when it was opened, whether it was useful, why it was dropped,
and which decisions rest on it. It runs without tokens; you only read its verdict.

| Verdict from `bib.py ocen` | What you do |
|---|---|
| `otworz` | open it (higher `punkty` first) |
| `uzyj-notatki` | use the stored note; open the page only if you need more than the note says |
| `sprawdz-ponownie` | open it: the page changed since it was judged, or the note is older than its class allows |
| `pomin` | do not open; it was dropped and has not changed. Override only for a reason: add `#bib-wymus` to the URL |

The hooks (Claude Code `integracje/claude-code/bib_hook.py`, Hermes plugin `integracje/hermes/bibliografia`) do
the checks on WebFetch, WebSearch, `web_extract`, `web_search` and `browser_navigate` automatically. Your part:
after using a source, record the verdict with a 1–3 sentence note that can be reused without reopening it:

```bash
python3 skrypty/bib.py ocena URL --werdykt uzyteczne --notatka "…" --temat "…" --przebieg <run-dir-name>
python3 skrypty/bib.py ocena URL --werdykt odrzucone --powod "SEO, brak testów" --przebieg <run-dir-name>
```

In Hermes the same is the `bibliografia` tool (`akcja: ocena`).

## 0. Start

1. Run `date +%F` and use it as the "as of" date. Never assume the year.
2. Pick the type from the table. If two fit, pick the one whose decision is costlier (zakupy over wiedza).
3. Read `typy/<typ>.md` and `kontekst/filip.md`. Do not read other type files.
4. Pick the mode: Standard by default; Szybki for a single fact or a purchase under 200 zł; Głęboki for trips,
   purchases over 2 000 zł, zdrowie-prawo-finanse, deployment plans, or when asked.
5. Create `<research.output_dir>/<date>-<slug>/`. Its name is the run id (`--przebieg`).

| Typ | Use for |
|---|---|
| wiedza | a topic, concept, "how does X work", state of knowledge |
| decyzja-techniczna | choosing a tool or planning a deployment (uses plany/SZABLON.md) |
| zakupy | choosing and buying an item, discounts, loyalty points |
| wycieczka | trips, holidays, weekends away |
| randka | dates, evenings out, family outings |
| osoba-firma | checking a company, contractor, seller or service |
| zdrowie-prawo-finanse | health, law, taxes, money decisions |
| monitoring | recurring watch of prices, promotions, news, events |

| Mode | Tool calls | Subagents | Min sources / domains |
|---|---|---|---|
| Szybki | 5–15 | 0 | 3 / 2 |
| Standard | 20–60 | 2–4 | 8 / 4 |
| Głęboki | 60–200 | 4–10 | 15 / 6 |

## 1. Brief

Ask only the type's start questions whose answer changes the result, at most 3. If there is no answer, do not
wait: take the defaults from `kontekst/filip.md` and the type file, and list every assumption at the top of
`brief.md`.

## 2. Plan

Write `plan.json` with: research questions; the type's mandatory fields as a table of items × fields; 3–5
perspectives (who would judge this differently); default sources from the type file; the call budget of the
mode. Every mandatory field must name at least one source to check. Only proceed when it does.

## 3. Gather

- Before opening candidate links, run `bib.py ocen URL…` (the hooks do it for single fetches) and follow the
  verdict table above. Reuse notes of useful sources instead of reopening them.
- Start with short, broad queries; narrow after seeing what exists. Prefer the type's default sources and
  primary sources over SEO content farms.
- In Standard and Głęboki, split the plan into tasks and give each subagent: objective, output format (notes
  file with source URL, date, verbatim quote per claim), sources to use, what is out of scope, and the rule
  to record a verdict for every source it opened.
- Subagents write `notatki/<task>.md`. The lead reads notes, not raw pages.
- Stop when the mode's budget is spent or every field has evidence; do not keep searching for sources that
  do not exist.

## 4. Source registry

Every source you opened has a verdict in the bibliography with `--przebieg <run id>` (dropped ones with the
reason). Then write the run's registry: `python3 skrypty/bib.py rejestr --przebieg <run id> -o zrodla.json`.
Gates: the mode's minimum sources and domains, at least 30% official/primary where the type says so, no
single source above 25% of citations. A failed gate → back to 3.

## 5. Coverage

Fill `pokrycie.md` from the items × fields table. For each empty field run targeted queries (back to 3, at
most 2 loops). After that, mark it "nie znaleziono" with what was tried and a link where Filip could check.

## 6. Write

Use `szablony/raport.md` and the rules in `szablony/standard-raportu.md`. Write only from notes and the
registry; add no new sources here. Every external fact gets a citation number. Mark claims from model
knowledge `[niezweryfikowane]`. Put the answer or decision in the first 5 lines.

## 7. Counter-review and verification

1. Review the draft as a sceptic: find at least 3 problems (missing option, stale price, weak source,
   unsupported conclusion) and fix them.
2. Pick the 5 claims the decision depends on. For each, write a verification question and answer it with a
   fresh query, independent of the draft. Fix any mismatch.
3. Re-check prices, availability and opening hours older than the type's freshness limit.

## 8. Validate, deliver, track

1. Run `python3 skrypty/waliduj_raport.py <run dir>`. Only proceed when it passes; on failure fix and rerun.
2. Save the report where the type says: Notion "Baza wiedzy Hermesa" → database "Raporty" (non-technical,
   plus a `.md` copy in Obsidian), or `plany/research/` (technical). Exports: `skrypty/eksport_raportu.py`.
3. If the report leads to a decision (buy, book, choose, deploy), register its sources for re-checking:
   `python3 skrypty/bib.py decyzja dodaj <ID> --tytul "…" --link <report link> --klasa <klasa> --z-raportu raport.md`.
   Classes: `na-zywo` 15 min (live situation, e.g. a fire), `krytyczna` 1 h (critical or emergency),
   `ceny` and `news` 1 day, `zwykla` 7 days, `kod` 30 days. A changed source marks the decision `do-przegladu`
   and the cron job `bib.py sprawdz-decyzje` tells Filip.
4. Send Filip a short message with the link and the answer in one or two sentences.
5. Ask: "Czy po przeczytaniu musiałeś czegoś szukać sam? Czego brakowało?" Save the answer to
   `ewaluacje/<typ>/feedback.jsonl`.
