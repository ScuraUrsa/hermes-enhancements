# Decision log: identity-vault (2026-10-12)

**Goal.** Let Claude and Hermes create accounts and log in as Filip, with Bitwarden as the only
place secrets live, Filip's consent per account and per login (with where and why), generated
initial passwords plus a rotation reminder, Filip handling anti-bot checks, and a map of his accounts
and their connections.

## What was checked

- Hermes upstream (`NousResearch/hermes-agent`, fork PR #5 at `a8e91bb1`) already has a credential
  vault with a Bitwarden backend (`agent/vault_backends/bitwarden.py`) and model-blind autofill
  (`tools/browser_vault_tool.py`: `browser_vault_list/unlock/fill/enter_code/save_login`). It appeared
  in tag `v2026.9.11`; the VMs run `v0.20.0 (a6ede70, 2026-08-08)` and do not have it. Payment fills
  ask for confirmation; logins do not. The classifier fills only `current-password` fields, not
  `new-password`.
- `pre_tool_call` plugin hooks can `block` or `approve` a tool call, but the `approve` gate is skipped
  under YOLO / `approvals.mode: off`, which is how prod runs. `request_elicitation_consent`
  (`tools/approval_prompt.py`) is a per-call prompt that ignores YOLO and fails closed in headless runs.
- Bitwarden's own options for agents: an MCP server (local, `bw`-based; the model can read items,
  so passwords would enter the context) and the Agent Access SDK (2026-03, "very early alpha",
  CLI approval per credential, meant for sample data). Sources: bitwarden.com/blog/introducing-agent-access-sdk,
  cyberinsider.com (MCP server launch).
- Account-map tools: self-hosted subscription trackers (Wallos, SubTrackr) track money, not
  logins; `abhavij71-ops/AccountManager` (PHP + SQLite) tracks which e-mail/phone is behind each
  account but has no connection graph and would be one more service to host and back up. Nothing
  found that maps OAuth / "login with" dependencies.

## Decisions

1. **Build on Hermes' vault instead of a new credential path.** Consent is added by a plugin
   (`identity_vault`) using `request_elicitation_consent`; `browser_vault_fill` is gated on a fresh
   per-login grant. Alternative rejected: Bitwarden MCP server (model sees passwords), Agent Access
   SDK (alpha, not for real data; revisit when stable).
2. **Prod needs the Hermes upgrade** to ≥ v2026.9.11 for `browser_vault_*`. This is already planned
   (fork PR #5, WOBI `hermes_ref`). Until then only the Claude Code path (Bitwarden extension on the
   PC) and the CLI work.
3. **Account map in Notion**, one database with two self-relations, maintained by `hidentity map`
   and auto-filled on every agent-created account. Alternative rejected: a dedicated tool (nothing
   fits, and Filip already lives in Notion). Bitwarden stays the only place for secrets; Notion holds
   the item id.
4. **Identity = a Bitwarden Identity item** in folder `Identity`. Shareable: name, e-mail, phone,
   address, company, custom text fields. Never shared by tooling: SSN/PESEL, passport, licence,
   hidden fields.
5. **Initial password**: `bw generate -ulns --length 24`, rotate-by = creation + 3 days
   (`HIDENTITY_ROTATE_DAYS`); rotation is detected via `passwordRevisionDate` or `mark-rotated`.
6. Secrets never in argv: item JSON goes to `bw` via stdin, the session token via env.

7. **Identities agents create (2026-10-27, Filip)**: folder `Agentowy` holds `Prawdziwy Ja` (his real
   identity; every use needs his explicit yes) and identities Hermes and Claude create: formal/private
   versions of Filip with other e-mails (`self-variant`) and generated personas (`persona`). Kind and
   consent level live in `hermes_kind` / `hermes_consent`; an unmarked item counts as real, the real
   one is always `always`, agents cannot set `none`. Personas: creation and data sharing need no
   consent; accounts and logins still ask, per Filip's standing rule that no account is created
   without his approval. E-mail via `--email` or plus addressing; truly unlinked personas need a
   forwarding-alias service (follow-up).

8. **Exposure map in the same Notion database** (2026-10-30, Filip: map which identity each account
   knows about and what, then migrate to stay as anonymous as possible). New columns rather than a
   second database: one row per account already exists and Notion views can group by `Identity`;
   `Identity` stays a select filled from the Bitwarden names so no relation has to be kept in sync.
   `hidentity map exposure` computes the leaks; `map upgrade` migrates the existing map in place.
9. **Identity, e-mail and platform maps as four sibling databases** (2026-10-31, Filip: a map per
   identity and per e-mail of accounts and traces, e-mails need not belong to an identity, and the
   reverse map of what each platform knows). Relations plus Notion rollups give all three views
   without a sync job; `Ślady` covers what is not an account. Selects on the account map stay as a
   fallback for rows not linked yet. Values of personal data never go into Notion, only field names.

## Follow-ups

- E-mail aliases for personas that must not link back to Filip: a forwarding service (SimpleLogin,
  addy.io or Firefox Relay through Bitwarden's username generator) needs an account and API key from
  Filip.

- WOBI role `identity_vault` (install `bw`, plugin, skill, cron job) once prod runs a Hermes with the vault.
- Sign-up forms with a "confirm password" field: `browser_vault_fill` fills only one field; either
  call it twice after focusing, or extend the classifier upstream (`new-password` on sign-up pages).
- Watch Bitwarden Agent Access SDK for a stable release; it would replace the plugin's grant logic.
- Seed the map with Filip's real accounts (Google ×4, Claude, Notion, GitHub, Ollama, Tailscale,
  ElevenLabs, Twilio, Meta): done for the ones known from the project context; Filip fills the rest.
