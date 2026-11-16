# 15 · Personal values system as a checkable knowledge base

**Status vs Hermes:** new. `life-management` exists but doesn't cover values or principles.
**Priority:** P5

## Goal and context
Filip asked how to formalise and write down his own value system and ethics, so that he can come back to past decisions. He also wanted to use mathematical logic to check that the principles are consistent, and to test whether a given dilemma fits the system. He asked whether software exists for this, including legal-reasoning tools.

Source: fjkazmierczak account, *Sformalizowanie systemu wartości* (2025-03-03).

## Architecture
```
values/ (git, private): principles.md (id, statement, priority, rationale, examples)
   ├─ decisions/  YYYY-MM-DD-<topic>.md (dilemma, principles applied, outcome, review date)
   └─ formal/     principles encoded as rules (Prolog / ASP via clingo, or s(CASP) for explainable answers)
        → `check consistency` (contradiction detection) and `evaluate dilemma` → which rules fire, conflicts
Hermes skill: "czy to zgodne z moimi zasadami?" → retrieves principles + past decisions, runs the checker,
              explains; never decides for Filip.
```
s(CASP) and clingo come from the legal-reasoning tradition and support defeasible rules (exceptions and priorities), which suits ethics better than classical logic.

## Implementation plan
1. Write about 20 principles in plain language with priorities. Filip writes them; Hermes only interviews him.
2. Encode 5 of them in s(CASP) as a pilot, with 3 past dilemmas as tests.
3. Add a decision journal template, with a timeplane reminder to review decisions after 3 months.
4. Expand the encoding only if the pilot helps.

## Deployment plan
A private repo, or the Obsidian vault (already synced via Syncthing to the VM). The checker runs locally (SWI-Prolog plus s(CASP), CPU only).

## Configuration / Cost
Free, CPU only.

## Open questions
Should this live in Obsidian (human-first) or a repo (machine-first)? Is this a technical project or a reflection practice? The second is fine without code.
