---
name: identity-vault
description: Create accounts and sign in as Filip with Bitwarden from Claude Code (on his PC or a Hermes VM), asking him first every time. Use when a task needs a new web/app account, Filip's personal data on a form, or a login to a site, and when maintaining the Notion account map.
---

# Identity vault for Claude Code

Bitwarden is the source of truth: folder `Identity` (Filip's personal data as a Bitwarden Identity
item), folder `Accounts` (logins created by agents). The `hidentity` CLI (repo
`hermes-enhancements/identity-vault`) wraps `bw` so secrets never reach the model or the logs.
The account map is the Notion database **Konta i połączenia**.

## Consent, every time

Before `hidentity create` or `hidentity share`, and before any login, ask Filip in chat in Polish with
three things: **where** (origin), **why** (the task), **what data** (fields or the vault item). Wait
for his yes. One yes covers one account or one login. Then run the command: Claude Code's permission
prompt shows it to him again. Never answer for him, never batch several accounts into one question.

## Setup check

```
bw status                 # must be "unlocked"; else Filip runs `bw unlock` and exports BW_SESSION
hidentity status
hidentity coverage        # what the vault knows about Filip (field names, never values)
```

## Create an account

```
hidentity find https://shop.example.com                 # reuse if it exists
hidentity create --url https://shop.example.com --username <email from `hidentity share email`> \
  --purpose "<why>" --created-by Claude --shared first_name,last_name,email
```
Bitwarden generates the password and stores the item (`hermes_*` fields: who, why, what was shared,
rotate-by date); the account is added to the Notion map. Then fill the form:

- Identity values: `hidentity share first_name last_name email phone` (after Filip's yes) and type them.
- Password: **do not print it**. On Filip's PC use the Bitwarden browser extension's autofill in his
  Chrome (Claude in Chrome clicks the extension fill; Filip has it unlocked). On a Hermes VM let
  Hermes do the login with `browser_vault_fill` instead of Claude.
- Captcha, SMS/e-mail codes, OAuth consent: stop and tell Filip what to do; he completes it.
- Finish with a Polish message: account created, data shared, "zmień to hasło w Bitwarden do <date>".

## Log in as Filip

Ask (where, why), then let the Bitwarden extension autofill in his browser, or hand the login to
Hermes. Never `bw get password`, never paste a password into a page yourself.

## Account map

```
hidentity map list | mermaid
hidentity map add --name "Claude (fjkazmierczak)" --url https://claude.ai --login-via google --created-by Filip
hidentity map link "Claude (fjkazmierczak)" "Google (fjkazmierczak)" --via          # logs in via
hidentity map link "Claude Code" "Notion (Hermes workspace)" --connected          # integration
hidentity map sync                                                                # Bitwarden → Notion
hidentity rotation-due                                                            # passwords Filip still has to rotate
```
Record a new connection whenever you set one up (an OAuth grant, an MCP connector, "Login with ...").
