# 10 · Private "Netflix" for friends (self-hosted media server)

**Status vs Hermes:** new. WOBI `features/registry.yaml` only notes "move music/podcasts to Nextcloud later".
**Priority:** P3

## Goal and context
Filip wanted a private VOD platform for friends and asked for a ready-made repo. A 2026 chat covered the legal side in Poland: private use of downloaded films vs distribution, P2P sharing, and whether streaming to friends counts as distribution. He also asked about company discounts for streaming services.

Source: fjkazmierczak account.
- *Tworzenie platformy VOD* (2025-03-11)
- *Dozwolony użytek a torrenty* (2026-08-05)

## Architecture
```
media storage (NAS / USB disk on a Linux host)
   └─ Jellyfin (container) ── tailnet only ──► friends' devices (Tailscale share or invite)
         ▲ hardware transcoding (Intel QSV / NVIDIA NVENC) if available
```
Jellyfin is fully open source, free and has no account cloud, unlike Plex. Access for friends goes through Tailscale node sharing, with no public exposure.

**Legal guardrail:** only home videos, purchased DRM-free content and freely licensed films. Serving downloaded or copyrighted films to other people is distribution in Poland, even if private. The plan does not include any *arr/torrent automation.

## Implementation plan
1. Pick a host. The Hermes VM is too small (8 GB RAM, about 78 GB disk) and runs on the PC. Use the PC itself or a mini PC/NAS with an external disk.
2. Deploy Jellyfin with Docker Compose (official image) and set up libraries.
3. Tailscale: share the node with friends' tailnets, or use Funnel-free invites.
4. Hermes skill (optional): "co nowego w bibliotece?" through the Jellyfin API.

## Deployment plan
A WOBI role `jellyfin` targeting the media host, with backups of the Jellyfin config (not the media) in the existing encrypted backup.

## Configuration
Library paths, transcoding device, users per friend, parental profiles.

## Cost / hardware
- Software is free.
- A mini PC with an Intel N100 (QSV transcoding) costs roughly €150–200.
- Disk: about €20/TB.
- Power: about 10 W idle, which is negligible.

## Open questions
- What content, exactly? That decides whether this is legal.
- How many simultaneous remote streams? That decides upload bandwidth and transcoding needs.
