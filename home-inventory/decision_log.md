# Decision log: home-inventory (2026-10-15)

**Goal.** Filip (2026-10-13): Hermes should know what is at home (food and chemicals first), each product's expiry
date and its exact place down to the shelf sector; he reports purchases by voice („przywiozłem X, ważne do Y”) and
asks „gdzie mam …?”; meal planning should surface food that expires soon.

**Decisions.**
- One stdlib script + skill (the `weather` pattern), no service, no new chat channel. Voice works because the HA
  pipeline already talks to Hermes, which loads the skill.
- SQLite under `~/.hermes/autonomy/home-inventory/` → covered by the existing nightly backup. Notion was not chosen as
  the store: offline, fast, testable; a Notion view can be exported later if Filip wants to browse it.
- Places are a tree with shelf/drawer order (pos 1 = top), so answers can say „2. półka od góry (3. od dołu)”. The
  sector is stored per batch (side × depth) rather than as extra tree levels, so a shelf does not need nine children.
- Items have a usual place: after the first time, „przywiozłem mleko” needs no place.
- Stock is kept in batches with their own expiry; `use` consumes earliest-expiry first.
- The shopping list stays in timeplane (another thread owns it); this tool does not duplicate it.
- Matching is deterministic (diacritics folding, prefix stems, difflib ≥ 0.8) so DeepSeek can drive it; ambiguity
  returns exit 4 with candidates instead of guessing.

**Follow-ups.** WOBI role + feature registry entry when it graduates from the manual deploy; Filip describes the flat
once (outline import); the timeplane meal procedure calls `dom plan`; optional morning `dom remind` cron job.
