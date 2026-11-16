# mail-guard

Safe mail reading for Hermes (plan K147: [bezpieczna poczta i linki](../docs/plany/research/2026-11-06-bezpieczna-poczta-i-linki.md),
source of truth in the project files `plany/research/2026-11-06-bezpieczna-poczta-i-linki.md`).

`mailguard` checks a mail **without any LLM** and returns a verdict (0–100, `ok` / `uwaga` / `podejrzany` /
`niebezpieczny`, reasons in Polish) plus a **card** that is safe to give a model. Stdlib only; Pillow is
optional (image re-encoding).

| Check | How |
|---|---|
| SPF / DKIM / DMARC | only the topmost `Authentication-Results` from `mx.google.com` is trusted; lower copies are counted as forgeries |
| Spoofing | lookalike domains (Cyrillic/Greek homoglyphs, `rn`→`m`, `0`→`o`, edit distance, brand in subdomain/name) against `data/protected_domains.txt`; display name with another address or a brand; Reply-To to another (free-mail) domain; bank-account-change wording |
| Links | never opened: shown text ≠ target, `user@host` trick, bare IP, punycode, shorteners, open redirectors, abused TLDs, `javascript:`/`data:` |
| Attachments | type from bytes, double extension, RLO in name, executables, Office macros / ActiveX / Equation Editor, PDF JavaScript/OpenAction/Launch, HTML with login form, encrypted / bomb / nested ZIP, ISO/IMG/LNK, optional clamd (`MAILGUARD_CLAMD=unix:/path` or `tcp:host:3310`); `needs_cdr` marks what must go through Dangerzone |
| Images | `sanitize_image` re-encodes to clean PNG (metadata, trailing payloads, polyglots dropped, pixel limit) |
| Hidden content | hidden HTML (display:none, white/tiny text, aria-hidden, hidden), zero-width/bidi, Unicode tag smuggling (decoded for the report only) |
| Prompt injection | EN/PL heuristics on visible, hidden and smuggled text, subject and sender name |

The **card** puts the verdict first, replaces URLs by `[L1]…` with a defanged list, and fences the untrusted
part (sender name, subject, body) between `<<<MAIL nonce>>>` and `<<<KONIEC MAIL nonce>>>` with a random
nonce; `<<<`/`>>>` from the sender are neutralised so the fence cannot be closed early.

```bash
pip install ./mail-guard            # or PYTHONPATH=mail-guard python3 -m mailguard ...
mailguard gmail fjkazmierczak --query "in:inbox newer_than:1d" --format summary
mailguard gmail fjkazmierczak --id 18c... --format card
mailguard analyze mail.eml --json
mailguard url "https://allegro.pl@evil.example/x"
mailguard save-attachments mail.eml --out ~/.hermes/quarantine/<id>/
```

Exit codes: 0 ok, 1 uwaga, 2 podejrzany, 3 niebezpieczny. Gmail tokens: `~/.hermes/google-accounts/<alias>/google_token.json`
(as `gacct`), refreshed in memory only. The Hitachi Energy work account is refused in code.

Python: `from mailguard.analyze import analyse, card; rep = analyse(raw_bytes); rep.to_dict(); card(rep)`.

`tests/attacks/` holds 32 attack mails (prompt injection hidden and visible, Unicode tags, fence break,
lookalikes, BEC, malicious attachments) plus one benign AI newsletter; `tests/make_attacks.py` rebuilds them.
Agents use the same corpus as an acceptance test: a profile fed these cards must take zero actions.

Skill for Hermes: `skills/hermes/mail-guard/SKILL.md`.
