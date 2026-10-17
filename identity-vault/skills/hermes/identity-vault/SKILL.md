---
name: identity-vault
description: Create accounts and log in as Filip using Bitwarden, with his consent for every account and every login. Use when a task needs a new account on a website or app, needs Filip's personal data on a form, or needs to sign in to a site (Instagram, Messenger, shops, portals).
---

# Identity vault: accounts and logins as Filip

Hermes never sees a password. Bitwarden holds Filip's identity (folder `Identity`) and the logins;
`browser_vault_fill` types passwords into the page model-blind. The `identity_vault` plugin adds the
consent step Filip requires: **ask before every account creation and before every login**, with where
and why.

## Rules

1. Never create an account or log in without Filip's approval through the tools below. Chat "ok" is
   not enough; the tool shows him the prompt.
2. Always give a true, specific `purpose` ("pobrać wiadomości z Messengera, żeby odpisać Oli").
3. Never type personal data from memory. Use `identity_share` for identity values, `browser_vault_fill`
   for passwords. Never run `bw get password`, `bw list items`, `hidentity create` in the terminal
   (blocked).
4. Captchas, "I am not a robot", SMS or e-mail codes, OAuth consent screens: stop and tell Filip what
   is on the screen; he solves it (for codes use `browser_vault_enter_code`).
5. After a sign-up, tell Filip in Polish: which account, which data went in, and that he should change
   the generated password in Bitwarden by the date in the result (`hermes_rotate_by`).
6. Prefer an existing login over a new account. Check with `browser_vault_list` first.
7. Nothing of this works in cron or `-q` runs (consent fails closed). Do not try to work around it.

## Create an account

```
identity_coverage()                                  # what the vault can offer
browser_vault_unlock("bitwarden")                    # Filip types the master password (once per session)
identity_create_account(site_url="https://shop.example.com", username="<Filip's email from identity_coverage/identity_share>",
                        purpose="...", shared_fields=["first_name","last_name","email"])
identity_share(site="shop.example.com", purpose="...", fields=["first_name","last_name","email"])
# open the sign-up page, type the shared values + username yourself,
browser_vault_fill("<handle from identity_create_account>")   # password (+ confirm field if the site has one: type nothing, call again)
# submit; hand captcha / verification to Filip
```

If `identity_create_account` returns `exists`, log in instead.

## Log in as Filip

```
browser_vault_list()                                 # find the handle, e.g. bw:<id> for instagram.com
identity_request_login(handle="bw:<id>", site="instagram.com", purpose="pobrać nowe wiadomości od ...")
# navigate to the login page on exactly that origin, type the username,
browser_vault_fill("bw:<id>")
# 2FA: browser_vault_enter_code("bw:<id>")  (TOTP is automatic if saved; else Filip types the code)
```

A grant is for one fill and expires after a few minutes; ask again for a new login.

## Account map

Every account Hermes creates lands in the Notion database **Konta i połączenia** automatically. When
you learn a new connection (e.g. a site now has "Login with Google", or an app got access to Notion),
record it: `hidentity map add --name "<app>" --url ... --login-via google` and
`hidentity map link "<app>" "Google (fjkazmierczak)" --via` or `--connected`. Rotation reminders:
`hidentity rotation-due` (a daily no-agent cron job reports them to Filip).
