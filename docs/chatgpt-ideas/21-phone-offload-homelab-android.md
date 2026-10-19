# 21 · Phone offload: agent-controlled Android, a homelab Android, and a minimal phone

**Status vs Hermes:** partly exists. Skill `devices/phone-control` + WOBI role `phone_control` (ADB over a tunnel, mobile-mcp, scrcpy on the PC); Termux → mosh → tmux on the VM (feature `phone-terminal`, guide `tasks/hermes-na-telefonie-przewodnik.md`); Claude Code Remote Control is in use. Missing: Android instances in the homelab, an agent guard, the minimal-phone setup.
**Priority:** P2

## Goal and context
Filip wants three things, from small to large:
1. Give tasks to Claude Code / Hermes from the phone and see the result (Remote Control, Termux).
2. Let an agent **operate the phone** (tap, type, open apps, read the screen) over USB ADB or over the tailnet.
3. Long term, carry the phone much less. Run what can live in the homelab there: two Android instances, one for Filip and one for the agent, with a guard that stops the agent changing passwords or security settings. Carry only a minimal device for calls, 2FA and navigation. He also wants to quit social media.

Source:
- koalamis6: *Konfiguracja Claude Code zdalnie* (2026-10-06), *Sterowanie telefonem Claude Code* (2026-10-07, Galaxy S20 FE, Android 13 / One UI 5.1, Tailscale already set up), *Przewijanie Hermesa w Termuxie* (2026-10-09, touch scroll in the Hermes TUI scrolls command history instead of output)
- kazmierczakfilipjan: *Self-hosting telefonu i AI* (2026-07-23)

## Architecture
```
Filip's phone (S20 FE) ──USB──► Windows PC (adb)  ──► phone-control skill (Claude Code / Hermes)
                    └─ wireless ADB over tailnet (adb tcpip, tailnet ACL: only the PC/VM) ──┘
Homelab (Proxmox, see 19):
  android-filip  : Waydroid or Android-x86 / redroid container, Filip's apps (mail, reading, banking web)
  android-agent  : redroid container, separate Google-free profile, agent's apps only
                   guard = Android device-owner policy (Test DPC / custom DPC): block Settings→Security,
                   account changes, app installs; ADB only from the Hermes host
  access         : scrcpy over the tailnet from any device
Carry: minimal phone (dumb phone or GrapheneOS Pixel with only calls, 2FA, maps, Signal)
```

## Implementation plan
1. **Termux scroll fix (minutes).** Use the Termux extra-keys row with PgUp/PgDn, or run Hermes inside tmux with `mouse on`, so swipes scroll output. Document it in the Hermes phone how-to.
2. **Phone control.** Use the existing `phone-control` skill (USB via the Windows PC). Add a wireless-ADB mode over the tailnet with ACLs, for when the phone is not plugged in.
3. **Agent Android in the homelab.** Start one `redroid` container on the Proxmox node. Run `scrcpy` from Filip's devices, and give the agent an ADB endpoint. Install a device-owner policy that blocks security settings and account changes. Test that the agent cannot change the lock screen or the Google account.
4. **Filip's Android in the homelab.** Second instance for reading, mail and long-form use, reached through scrcpy or a tablet.
5. **Minimal-phone trial.** Two weeks with social apps removed from the phone. Social media only from the homelab instance with a time budget (Hermes break reminders, as in steam-games).

## Deployment plan
redroid containers via a WOBI role on the Proxmox node (needs `binder` kernel modules). scrcpy clients installed by hand. Tailnet ACL change through Git.

## Configuration
Tailscale ACL (ADB port 5555 only from the Hermes host), device-owner policy JSON, redroid image version pinned.

## Cost / hardware
Software is free. redroid needs ~2–4 GB RAM per instance. A GrapheneOS Pixel is ~€300–500 used; a 4G dumb phone with hotspot ~€60.

## Open questions
- Which bank and 2FA apps refuse to run in an emulated Android (Play Integrity)? Those must stay on the carried device.
- Is navigation in the car handled by the car's own system, or does the minimal phone need maps?
- Is a full "agent Android" worth it, or is the agent driving Filip's real phone over ADB enough?
