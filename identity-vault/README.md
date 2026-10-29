# identity-vault

Claude and Hermes create accounts and log in **as Filip** or as identities they create for him,
with Bitwarden holding every secret. Filip's real identity is never used without his explicit yes. A
Notion database maps the accounts and how they connect.

```
Bitwarden (Password Manager)                       Notion
├── folder Agentowy/        Identity items          database "Konta i połączenia"
│   ├── "Prawdziwy Ja"      Filip's real data       one row per account, self-relations
│   │                       (always asks)           "Logs in via" and "Connected to"
│   ├── "Filip formalny"…   versions of Filip with
│   │                       their own e-mail (ask)
│   └── "Tor 1"…            generated personas
│                           (accounts/logins ask)
└── folder Agentowy/Konta/  Login items created by
                            agents, hermes_* fields
                            (who, why, what shared,
                            rotate-by)
```

## Identities

| Kind (`hermes_kind`) | What it is | Created by an agent | Using its data | Account / login with it |
|---|---|---|---|---|
| `real` | `Prawdziwy Ja` (or any item without `hermes_kind`) | never | asks | asks |
| `self-variant` | formal or private version of Filip, own e-mail, fields copied from the real one model-blind | asks | asks | asks |
| `persona` | generated, made-up data (sign-ups where Filip keeps his data private, Tor) | free | free | asks |

`hermes_consent` holds the level (`always`, `account`, `none`). Agents can set `always` or
`account`; only Filip lowers an identity to `none` (nothing asks), by editing the field in
Bitwarden. The real identity is always `always`, whatever its fields say.

E-mail for a new identity: `--email` (an inbox Filip set up) or `--email-plus BASE`, which makes
`base+<name>@domain` on an inbox Filip already reads. A plus address still reveals the base inbox; a
persona that must not link back to Filip needs an alias from a forwarding service (not set up yet).

| Piece | Where | Used by |
|---|---|---|
| `hidentity` CLI (`hidentity/`) | PC and VMs; wraps `bw`, prints metadata only | Claude Code, cron, Filip |
| Hermes plugin `identity_vault` (`hermes-plugin/`) | `~/.hermes/plugins/identity_vault` on prod | Hermes |
| Skill for Hermes (`skills/hermes/identity-vault`) | `~/.hermes/skills/identity/identity-vault` | Hermes |
| Skill for Claude Code (`skills/claude-code/identity-vault`) | `D:\hermes\.claude\skills\identity-vault` (and `~/.agents/skills` on dev) | Claude Code |
| `hermes/scripts/rotation_reminder.py` | no-agent cron job, daily 09:00 on prod | Filip gets the reminder |

## How consent works

- **Hermes**: the plugin's tools `identity_create_account`, `identity_share`,
  `identity_create_persona` (for a version of Filip) and `identity_request_login` open a confirmation
  whenever the identity's level calls for it (table above), in the surface Filip is using (chat buttons or the
  CLI panel) with *where* and *why*. `browser_vault_fill` is blocked unless a login was just approved.
  The prompt is not subject to YOLO mode and fails closed in cron and `-q` runs. Terminal commands that
  could leak secrets (`bw get password`, `bw list items`, `hidentity create|share|persona`) are blocked.
- **Claude Code**: the skill makes Claude ask Filip in chat (where, why, which data) before
  `hidentity create` / `hidentity share`; Claude Code's permission prompt shows the command again.
  Passwords are never printed: on the PC the Bitwarden browser extension autofills, on a VM Hermes
  fills model-blind (`browser_vault_fill`, upstream Hermes ≥ v2026.9.11).
- **Captcha, SMS/e-mail codes, OAuth consent screens, passkeys**: always Filip.
- **Generated passwords** come from `bw generate` (24 chars) and are stored with a rotate-by date
  (3 days). `hidentity rotation-due` lists what Filip still has to change; the cron job nags.

## Setup

1. Bitwarden: folder `Agentowy` with an *Identity* item named `Prawdziwy Ja` (fill what agents may
   use: name, e-mail, phone, address; custom text fields such as `birth_date` are shareable too,
   hidden fields and passport/ID numbers never are). `Agentowy/Konta` is created on the first account.
   Other names: `HIDENTITY_IDENTITY_FOLDER`, `HIDENTITY_ACCOUNTS_FOLDER`, `HIDENTITY_REAL_IDENTITY`.
2. `bw` CLI on the PC (winget `Bitwarden.CLI`) and on prod (`npm i -g @bitwarden/cli` or the WOBI role),
   pointed at the EU server once, then logged in: `bw config server https://vault.bitwarden.eu`,
   `bw login`, `bw unlock`. Filip's account lives on vault.bitwarden.eu; the default US server
   answers "Invalid master password".
3. `pip install -e identity-vault` (or copy `hidentity/` and set `HIDENTITY_PATH`).
4. Notion: the database exists under "Hermes Organized"; `NOTION_API_KEY` (env or `bws`) must have
   access to it. `hidentity map list` verifies.
5. Hermes: copy `hermes-plugin/identity_vault` to `~/.hermes/plugins/`, enable it and set
   `plugins.entries.identity_vault.hidentity_path`; copy the skill; add the cron job:
   `hermes cron add --name identity-rotation --schedule "0 9 * * *" --no-agent --command "python3 ~/.hermes/scripts/identity-vault/hermes/scripts/rotation_reminder.py"`.

## CLI

```
hidentity status | coverage | share <fields> | find <url> | create --url --username --purpose ...
hidentity identities | persona --kind persona|self-variant --name N --purpose P [--email E | --email-plus B] [--copy f,..] [--set f=v]
hidentity accounts | rotation-due | mark-rotated <id>
hidentity map init --parent <page> | list | add ... | link A B --via|--connected | sync | mermaid
```

Tests: `pytest` (offline fakes for `bw` and Notion). Lint: `ruff check .`.
