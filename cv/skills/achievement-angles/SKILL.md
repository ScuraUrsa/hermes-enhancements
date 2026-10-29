---
name: achievement-angles
description: "Opisanie tego samego osiągnięcia Filipa na różne sposoby (DevOps/infrastruktura, bezpieczeństwo, IAM, SRE, koszty, zarządzanie…) i wybór wersji pod profil firmy i stanowisko; prowadzi bank osiągnięć do CV."
version: 0.1.0
author: Claude Code (for Filip), 2026-10-29
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cv, resume, osiągnięcie, osiągnięcia, perspektywa, jak to opisać, przeformułuj, devops, bezpieczeństwo, security, iam, sre, finops, bank osiągnięć, achievement]
    related_skills: [cv-writer]
---

# achievement-angles — jedno osiągnięcie, wiele perspektyw

The same piece of work reads differently to a bank's security team, a startup's platform team and an IAM
hiring manager. This skill thinks through those readings before a CV is written.

Use when:
- `cv-writer` tailors a CV (step 5) — always.
- Filip asks: "jak opisać to osiągnięcie?", "opisz to od strony bezpieczeństwa", "jak to sprzedać pod IAM?",
  "dodaj do banku osiągnięć <coś>", "pokaż wersje dla <firma/stanowisko>".

## Files

`~/.hermes/autonomy/cv/achievements.yaml` — the achievement bank. Format: `achievements.example.yaml` next to
this skill (copy it to start the bank).
Lens catalogue and company/role weights: `references/lenses.md` — load it every time.

## Step 1 — fact sheet (once per achievement)

From Filip's words, `master.yaml` or an old CV, write the facts only:
context (company, team, period), problem, what Filip personally did (vs the team), scope (systems, users,
accounts, environments), technologies, measurable results (time, cost, incidents, %, count), who benefited.

Missing numbers: ask Filip ("ile kont / serwisów / godzin to było, mniej więcej?"). An estimate he gives is
stored as an estimate (`~40`, `about 40`) and stays an estimate in every variant. Never invent a number.

## Step 2 — lens variants

For each lens in `references/lenses.md`, ask its question against the fact sheet:

- **There is real evidence** for that lens → write one CV bullet (≤ 2 lines): action verb + what + result in the
  lens's own vocabulary and metric. Add 3–6 ATS keywords that the bullet honestly supports.
- **No evidence** → mark the lens `n/a` with a one-line reason. Do not stretch: "used Terraform" is not a
  security achievement unless something security-relevant was actually done.
- **Partial evidence** → write the variant, mark `needs_check`, and put the question for Filip in `question`.

Each variant must be true on its own. Changing the emphasis is allowed; changing the facts is not.

## Step 3 — pick for a target

Input: company profile (from `cv-writer` research) + role + keywords from the ad.

1. Score each non-`n/a` lens: company weight + role weight from `references/lenses.md`, +1 per ad keyword the
   variant covers.
2. Primary lens = highest score → its variant is the bullet in this CV.
3. A second lens may become a **second bullet** only if it describes a really different part of the work and the
   CV has room; never two bullets that say the same thing twice.
4. Adjust the chosen variant to the ad's wording (their term for the same thing: "access management" vs
   "IAM", "platform" vs "infrastructure") without changing facts.
5. Tell `cv-writer` (or Filip) which lens was chosen and why in one line, e.g.
   "Bank → bezpieczeństwo i IAM ważniejsze niż szybkość wdrożeń, więc wersja IAM."

## Step 4 — save

Write new/changed variants to `achievements.yaml` with `status: draft`. Show Filip new variants in a short list
(lens → bullet); after his OK set `status: approved`. `cv-writer` prefers `approved` variants and may use
`draft` ones only after telling Filip. Record in `used_in` which application used which variant.

## Example (made up, for the shape only)

Facts: moved 40 services from VMs to AKS with Terraform; replaced service-principal secrets with workload identity;
deploys went from ~2 h manual to 15 min pipeline; led 3 people.

| Lens | Variant |
|---|---|
| DevOps / infra | Migrated 40 services from VMs to AKS with Terraform and CI/CD pipelines, cutting deployment time from ~2 h to 15 min. |
| Security | Removed long-lived credentials from 40 services by moving them to workload identity during an AKS migration. |
| IAM | Replaced static service-principal secrets with Entra ID workload identity for 40 services, giving each one a least-privilege identity. |
| Leadership | Led a team of 3 engineers through a 40-service migration to AKS, delivered without production downtime. ← only if "no downtime" is a fact |
| FinOps | `n/a` — no cost data. Question: did the migration change hosting cost? |

## Rules

- Truth first; when in doubt, ask Filip instead of writing.
- Never write a variant that claims a role Filip did not have (owner vs contributor, led vs took part).
- Keep tool and product names exact. Bullets in the CV's target language; `cv-writer` translates from the
  English or Polish master variant, never from another translation.
- Replies to Filip: Polish, short list of variants, the recommended one marked.
