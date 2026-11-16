# 14 · Let another person log in as me without seeing my passwords

**Status vs Hermes:** partly exists. Bitwarden Secrets Manager covers **machine** secrets (WOBI `roles/bws`, `git-credential-bws`). Person-to-person sharing is not set up.
**Priority:** P4

## Goal and context
Filip wanted a trusted second person to log into services as him (streaming, bank and similar) without ever learning the passwords. He asked whether a tool could look like SSO or tokens to that person while using username and password underneath.

Source: fjkazmierczak account, *Third party credential access* (2025-08-25).

Also from the other accounts: koalamis6 *Porównanie YubiKey USB* (2026-08-26) and kazmierczakfilipjan *Securing compromised accounts* (2025-08-19) and *Free vs Premium Bitwarden* (2026-06-01). These are planned separately in [31](31-family-passwordless-security.md).

## Architecture and recommendation
- **Streaming and most web apps:** Bitwarden (Families/Organization) shared collection with "**hide passwords**" permission. Autofill works, but the password isn't shown. This is not cryptographically strong: a technical user can still extract it from the browser. Where the service offers them, use passkeys or per-profile household accounts instead.
- **Banks:** do not share credentials at all. It usually breaks the bank's terms and voids liability protection. Use the bank's own proxy/authorised-user feature (pełnomocnictwo) or a joint account.
- **"Fake SSO" credential proxy:** rejected. It means building a man-in-the-middle login service that holds plaintext passwords, which is a large security liability for little gain.

## Implementation plan
1. Bitwarden organisation (Families plan) with a "Shared with <person>" collection, hide-passwords enabled, and 2FA on both accounts.
2. Move only the shareable logins there. Rotate the passwords afterwards.
3. Write a review checklist: who has access to what. Run it quarterly (a Hermes reminder via timeplane).

## Deployment plan
SaaS only (Bitwarden cloud EU, which is already used for BWS). No self-hosting.

## Configuration
Collection permissions, emergency access settings (Bitwarden Emergency Access is a separate useful feature).

## Cost / hardware
Bitwarden Families costs about $40/year if not already paid.

## Open questions
Which services, exactly? Some (Netflix 2023+ household rules) restrict sharing regardless of the tool.
