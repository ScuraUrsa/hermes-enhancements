---
name: identity-vault
description: Create accounts and sign in as Filip or as identities created for him, with Bitwarden, from Claude Code (on his PC or a Hermes VM). Use when a task needs a new web/app account, personal data on a form, a login to a site, a new identity (a formal/private version of Filip or a generated persona), and when maintaining the Notion account map.
---

# Identity vault for Claude Code

Bitwarden is the source of truth: folder `Agentowy` (Identity items: `Prawdziwy Ja` with Filip's real
data, his formal/private versions, generated personas), folder `Agentowy/Konta` (logins created by
agents). The `hidentity` CLI (repo
`hermes-enhancements/identity-vault`) wraps `bw` so secrets never reach the model or the logs.
The account map is the Notion database **Konta i połączenia**.

## Consent

`hidentity identities` shows each identity's `kind` and `consent`. Ask Filip in chat in Polish, with
**where** (origin), **why** (the task) and **what data / which identity**, and wait for his yes:

- anything with `Prawdziwy Ja` (share, account, login): always, and name it as his real data;
- a `self-variant` (his formal/private version): before creating it and before every use;
- a `persona` with consent `account`: before an account or a login with it; sharing its data and
  creating a new persona need no question (Filip 2026-10-27);
- consent `none` (only Filip sets it in Bitwarden): no question.

One yes covers one account or one login. Then run the command: Claude Code's permission
prompt shows it to him again. Never answer for him, never batch several accounts into one question.

## Setup check

```
bw status                 # must be "unlocked"; else Filip runs `bw unlock` and exports BW_SESSION
hidentity status
hidentity coverage        # what the vault knows about Filip (field names, never values)
```

## Create an identity

```
hidentity identities
hidentity persona --kind persona --name "Tor 1" --purpose "przeglądanie przez Tor" --email-plus <inbox>
hidentity persona --kind self-variant --name "Filip formalny" --purpose "urzędy, praca" \
  --email <his formal address> --copy first_name,last_name,city      # ask first: copies his real data
```
A persona gets made-up Polish data (name, username, city, birth date). Pass `--set
field=value` to adjust. Copied real values never appear in the output. Use `--identity "<name>"` on
`share` and `create` to act as that identity.

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
