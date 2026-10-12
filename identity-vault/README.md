# identity-vault

Claude and Hermes create accounts and log in **as Filip**, with Bitwarden holding every secret and
Filip approving every account and every login. A Notion database maps the accounts and how they
connect.

```
Bitwarden (Password Manager)                    Notion
├── folder Identity/   Identity item "Filip"     database "Konta i połączenia"
│                      (name, e-mail, phone,     one row per account, self-relations
│                      address, custom fields)   "Logs in via" and "Connected to"
└── folder Accounts/   Login items created by
                       agents, hermes_* fields
                       (who, why, what shared,
                       rotate-by)
```

| Piece | Where | Used by |
|---|---|---|
| `hidentity` CLI (`hidentity/`) | PC and VMs; wraps `bw`, prints metadata only | Claude Code, cron, Filip |
| Hermes plugin `identity_vault` (`hermes-plugin/`) | `~/.hermes/plugins/identity_vault` on prod | Hermes |
| Skill for Hermes (`skills/hermes/identity-vault`) | `~/.hermes/skills/identity/identity-vault` | Hermes |
| Skill for Claude Code (`skills/claude-code/identity-vault`) | `D:\hermes\.claude\skills\identity-vault` (and `~/.agents/skills` on dev) | Claude Code |
| `hermes/scripts/rotation_reminder.py` | no-agent cron job, daily 09:00 on prod | Filip gets the reminder |

## How consent works

- **Hermes**: the plugin's tools `identity_create_account`, `identity_share` and
  `identity_request_login` each open a confirmation in the surface Filip is using (chat buttons or the
  CLI panel) with *where* and *why*. `browser_vault_fill` is blocked unless a login was just approved.
  The prompt is not subject to YOLO mode and fails closed in cron and `-q` runs. Terminal commands that
  could leak secrets (`bw get password`, `bw list items`, `hidentity create`) are blocked.
- **Claude Code**: the skill makes Claude ask Filip in chat (where, why, which data) before
  `hidentity create` / `hidentity share`; Claude Code's permission prompt shows the command again.
  Passwords are never printed: on the PC the Bitwarden browser extension autofills, on a VM Hermes
  fills model-blind (`browser_vault_fill`, upstream Hermes ≥ v2026.9.11).
- **Captcha, SMS/e-mail codes, OAuth consent screens, passkeys**: always Filip.
- **Generated passwords** come from `bw generate` (24 chars) and are stored with a rotate-by date
  (3 days). `hidentity rotation-due` lists what Filip still has to change; the cron job nags.

## Setup

1. Bitwarden: create folders `Identity` and `Accounts`; add an *Identity* item named `Filip` to
   `Identity` (fill what agents may use: name, e-mail, phone, address; custom text fields such as
   `birth_date` are shareable too, hidden fields and passport/ID numbers never are).
2. `bw` CLI logged in (`bw login`) on the PC and on prod (`npm i -g @bitwarden/cli` or the WOBI role).
3. `pip install -e identity-vault` (or copy `hidentity/` and set `HIDENTITY_PATH`).
4. Notion: the database exists under "Hermes Organized"; `NOTION_API_KEY` (env or `bws`) must have
   access to it. `hidentity map list` verifies.
5. Hermes: copy `hermes-plugin/identity_vault` to `~/.hermes/plugins/`, enable it and set
   `plugins.entries.identity_vault.hidentity_path`; copy the skill; add the cron job:
   `hermes cron add --name identity-rotation --schedule "0 9 * * *" --no-agent --command "python3 ~/.hermes/scripts/identity-vault/hermes/scripts/rotation_reminder.py"`.

## CLI

```
hidentity status | coverage | share <fields> | find <url> | create --url --username --purpose ...
hidentity accounts | rotation-due | mark-rotated <id>
hidentity map init --parent <page> | list | add ... | link A B --via|--connected | sync | mermaid
```

Tests: `pytest` (offline fakes for `bw` and Notion). Lint: `ruff check .`.
