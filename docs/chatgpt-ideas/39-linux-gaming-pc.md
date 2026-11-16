# 39 · Moving the gaming PC off Windows 10 (Linux + Proton, or an isolated Windows)

**Status vs Hermes:** new. Related: hermes-enhancements `steam-games/` (game suggestions, achievements as XP, break reminders), which reads Steam data but does not touch the gaming PC's OS.
**Priority:** P4

## Goal and context
Windows 10 is out of support. Filip asked whether a Linux distro is better for gaming, which Steam games require Windows (mostly kernel anti-cheat), whether those games exist on consoles, the workarounds on Linux, and whether an unsupported Windows 10 is safe enough if used only for games that need Windows.

Source: kazmierczakfilipjan, *Linux vs Windows 10 Gaming* (2026-07-07).

## Architecture
```
gaming PC: Linux gaming distro (Bazzite or Nobara; or Ubuntu + Steam + Proton-GE)
  check each owned game on ProtonDB / areweanticheatyet before switching
Windows-only games (kernel anti-cheat): either
  (a) dual boot with Windows 11 (supported, if the CPU/TPM allow), or
  (b) keep Windows 10 offline-ish: separate disk, games only, no browser/mail logins, ESU or a firewall profile
Sunshine on the PC → Moonlight clients (see 09)
```

## Implementation plan
1. Script: export the Steam library (the steam-games data already has it) and check each title against ProtonDB and the anti-cheat database. Output: "works", "works with tweaks", "Windows only".
2. If the "Windows only" list is short and unimportant, switch to Bazzite on a second SSD first and keep Windows until it is proven.
3. If important games are Windows-only: dual boot with Windows 11, or keep Windows 10 strictly as a games-only system with no personal accounts.

## Deployment plan
Manual install on the PC. The library-check script goes into `steam-games/`.

## Configuration
Steam API key (already used by steam-games), Proton versions per game.

## Cost / hardware
Free; a second SSD (~€50) makes the trial reversible.

## Open questions
- Which games does the group actually play (Valheim runs natively on Linux)?
- Does the PC support Windows 11 (TPM 2.0, CPU generation)?
