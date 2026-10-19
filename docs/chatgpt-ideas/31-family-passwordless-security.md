# 31 · Passwordless family security (hardware keys + Bitwarden) and a compromise playbook

**Status vs Hermes:** new. Bitwarden is used for machine secrets (BWS) and `identity-vault/` holds Filip's Bitwarden-backed accounts; passkeys/FIDO appear only in its README and in [14](14-delegated-credential-access.md).
**Priority:** P2

## Goal and context
- Set up Bitwarden for a child so the child never has to remember any password, **including the Bitwarden master password**, using a hardware key. Preferably on the free plan. It must work on Android and Windows.
- Choose the key: YubiKey vs Token2, Solo 2+, Nitrokey Passkey, Google Titan. Which support FIDO2 PRF (needed for Bitwarden's passkey unlock)? Which have both USB-A and USB-C plus NFC, or biometrics? Price and availability in Poland.
- After a family member's Gmail and Messenger were taken over through a phishing link, find out how to know the incident is over and the phone is clean.

Source:
- koalamis6: *Porównanie YubiKey USB* (2026-08-26)
- kazmierczakfilipjan: *Securing compromised accounts* (2025-08-19), *Free vs Premium Bitwarden* (2026-06-01), *Find Gmail Accounts Linked* (2026-06-03)

## Architecture
```
child account (Bitwarden Free)
  login + vault unlock = passkey on a FIDO2 key with PRF ("log in with passkey" → unlocks vault without master password)
  key A (daily, NFC for Android + USB-C/A for PC)   key B (backup, kept at home)
  master password: long random, printed and sealed in the parent's safe (recovery only)
  Bitwarden emergency/recovery: parent's account (Families org, if bought later)
  site logins: passkeys where offered, else generated passwords autofilled by Bitwarden
parent tooling: Hermes reminder to test the backup key every 6 months
```

## Implementation plan
1. Pick the key from a short table: PRF support (verify against Bitwarden's current list), connectors, NFC, price in PLN. Buy two keys of the same model.
2. Enrol both keys as passkeys with PRF on the child's Bitwarden account. Test unlock on the Android phone (NFC) and Windows PC (USB).
3. Move the child's accounts into the vault. Turn on passkeys where sites offer them.
4. Write a one-page "lost key" procedure (backup key, then sealed master password, then re-enrol).
5. **Compromise playbook** (Hermes skill, generic for the family): revoke sessions, change passwords from a clean device, check account recovery email/phone and forwarding rules, list third-party app access, check Google "Your devices" and "Security activity", scan the phone (Play Protect, remove unknown device-admin apps), and warn contacts. Done when 14 days pass with no new sign-in alerts.

## Deployment plan
Manual setup with the child. The playbook goes into Hermes skills; nothing is stored about the child beyond the procedure.

## Configuration
None in Hermes beyond a calendar reminder.

## Cost / hardware
Two keys: Token2 PIN+ models from ~€25–35 each; YubiKey 5C NFC ~€60–70 each. Bitwarden Free is enough for this; Families (~€40/year) adds shared recovery.

## Open questions
- Does the child's Android browser and Bitwarden app version support PRF unlock today? Test before buying two keys.
- Bio keys (fingerprint) are easier for a child but cost more and have fewer PRF-confirmed models.
