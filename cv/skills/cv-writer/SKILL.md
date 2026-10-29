---
name: cv-writer
description: "Pisanie i dopasowanie CV (resume) Filipa pod konkretną ofertę i firmę, w wybranym języku, z tłumaczeniem i lokalizacją na podstawie ogłoszenia albo researchu firmy; render PDF przez RenderCV."
version: 0.1.0
author: Claude Code (for Filip), 2026-10-29
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cv, resume, życiorys, aplikacja, rekrutacja, ogłoszenie, oferta pracy, list motywacyjny, tłumaczenie cv, cv po angielsku, cv po niemiecku, lebenslauf, job application]
    related_skills: [achievement-angles]
---

# cv-writer — CV pod ofertę, w odpowiednim języku

Use when Filip asks for a CV or resume: "zrób mi CV pod tę ofertę", "dopasuj CV do <firma>", "przetłumacz CV na
niemiecki", "w jakim języku wysłać CV do <firma>?", "zaktualizuj CV", "dodaj do CV <osiągnięcie>".

Not for: sending applications or e-mails (needs Filip's OK every time), filling job portals, writing about anyone
other than Filip.

## Files (prod VM)

All state lives in `~/.hermes/autonomy/cv/` (included in the nightly backup):

| File | What |
|---|---|
| `master.yaml` | Full master CV in RenderCV YAML, Polish or English. Source of truth: every fact comes from here. |
| `achievements.yaml` | Achievement bank with per-lens variants, kept by the `achievement-angles` skill. |
| `applications/<YYYY-MM-DD>-<company>/` | One folder per application: `offer.md`, `research.md`, `cv.<lang>.yaml`, rendered PDF, `notes.md`. |

If `master.yaml` does not exist yet: ask Filip for his current CV (PDF/DOCX/LinkedIn export), convert it to
RenderCV YAML (`rendercv new "Filip Kaźmierczak"` gives the skeleton), show him a short summary of what you
extracted and what is missing, and save only after he confirms.

Render: `~/.hermes/autonomy/cv/venv/bin/rendercv render cv.<lang>.yaml` (PDF + PNG + Markdown in
`rendercv_output/`). Check the PNG of page 1 before you hand the PDF over.

## Workflow

1. **Offer.** Save the job ad to `offer.md` (text, link, date). Extract: role, seniority, must-haves,
   nice-to-haves, keywords, language of the ad, location, remote/hybrid.
2. **Company research** (`research.md`, short, with links): what they build, size, industry, HQ country,
   working language of the team, tech stack (job ads, engineering blog, GitHub), values, recent news.
   Classify the **company profile** (fintech/bank, startup, enterprise, software house/consulting, SaaS/big tech,
   public sector, security vendor, other) — `achievement-angles` uses it.
3. **Language** — decide with the rules below, tell Filip the choice and why in one line.
4. **Fit.** Map each requirement to evidence from `master.yaml`/`achievements.yaml`: ✅ have (with proof),
   🟡 partial, ❌ missing. Ask Filip at most 5 questions about experience that may fit but is not written down.
5. **Angles.** For every achievement you plan to use, load `achievement-angles` and pick the variant for this
   company profile and role (or generate one). Never write a new framing inline without that skill.
6. **Write** `cv.<lang>.yaml`: 1 page for < 5 years experience, else max 2. Summary of 3 sentences for this role.
   Bullets: action verb + what Filip did + measurable result. Keywords from the ad woven in naturally. No tables,
   icons or columns that ATS cannot read.
7. **Translate/localize** if the target language differs from the master (rules below).
8. **Render and check**: PDF renders, page count, no overflow, names/dates correct, clause present if needed.
9. **Hand over** to Filip in Polish: the PDF, the language choice, the fit table (short), what changed vs master,
   gaps to prepare for the interview. Offer a cover letter only if the ad asks for one.

## Choosing the language

Decide in this order and stop at the first rule that applies:

1. Filip named a language → use it.
2. The ad states it ("CV in English", "Bewerbung auf Deutsch") → use that.
3. Language of the ad itself → use it (a Polish company posting in English expects an English CV).
4. Research: working language of the team/HQ (international team, English-speaking HQ, English engineering blog)
   → English; a German/Austrian/Swiss-German company with a German ad → German.
5. Otherwise the language of the country of the job; for Poland → Polish.

When rules disagree (e.g. a Polish ad from a US company with an English-speaking team) or the role requires
two languages: recommend one and offer the second version. Two versions of the same CV must contain the same
facts.

## Translating and localizing

Translation is localization, not word-for-word. Load `references/localization.md` for the target country and
follow it. Always:

- Translate from `master.yaml` plus the chosen angle variants, never from another translation.
- Keep in the original: company names, product names, technology names (Kubernetes, Terraform, Entra ID),
  certification names (AZ-104, CKA), official project names.
- Job titles: use the term the target market uses for that role (e.g. "Inżynier DevOps" → "DevOps Engineer"
  in English and German). If a historic official title differs a lot, keep the market term and do not invent a
  higher seniority.
- Numbers, dates and units in the target format (`03.2024` vs `Mar 2024`, decimal comma vs point, currency).
- Keep the meaning of every metric exactly. Do not round up, do not change "about" to an exact number.
- Apply the country conventions: photo, date of birth, data-protection clause, page length, CV title.
- Set RenderCV's top-level `locale:` block so month names and "present" come out right: `language: german`,
  `french`, `spanish`, … are built in (`english` default). RenderCV 2.8 has **no Polish**: paste
  `references/locale-pl.yaml` instead. Section titles are the keys under `cv.sections`, so name them in the
  target language yourself (table in `references/localization.md`).
- Quality check: back-translate the summary and 3 bullets to Polish in your head and compare with the master;
  fix any drift in meaning, seniority or scope before rendering.
- If you are not confident in the language (anything beyond PL/EN/DE), say so and suggest a native check.

## Rules

- Truth first: only facts from `master.yaml`, `achievements.yaml` or Filip's answers. No invented numbers,
  tools, titles or responsibilities. A gap stays a gap; mention it to Filip instead of hiding it.
- Every new fact Filip gives goes back into `master.yaml` / `achievements.yaml` (after his OK), not only into
  one application.
- Personal data (phone, address, date of birth) only as in `master.yaml`; never post the CV anywhere,
  never send it to a recruiter or upload it without Filip's explicit OK for that specific send.
- Drafting can use a local llama.cpp model or a cheap cloud model; final wording of the CV and any translation
  into a foreign language goes through the strongest available model (Claude).
- Replies to Filip: Polish, short, PDF attached, links to the company sources used.
