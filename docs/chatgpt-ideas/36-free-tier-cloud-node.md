# 36 · Free-tier cloud node (Oracle Ampere A1) for a game server and an off-site fallback

**Status vs Hermes:** new. No Oracle Cloud usage; Azure only in old WOBI designs.
**Priority:** P4

## Goal and context
Filip runs a **Valheim** dedicated server on a DigitalOcean droplet (4 vCPU / 8 GB) and wanted to move it, plus an agent (OpenClaw then), to Oracle's Always Free Ampere A1 (4 ARM cores, 24 GB RAM, as one VM or up to four). He hit the "only 6 GB" shape limit and asked about lag on ARM. He also asked where Hermes can be hosted most cheaply.

Source: kazmierczakfilipjan, *ARM vs x86 Server Comparison*, *Oracle Always Free Limits* (2026-04-07), *Tanie hostowanie Hermesa* (2026-08-04).

## Architecture
```
OCI Always Free (A1.Flex, 4 OCPU / 24 GB, 200 GB block storage free)
  ├─ valheim: x86 binary via Box64 (or FEX) in a container — test performance first
  ├─ tailscale node (exit node / off-site relay)
  └─ off-site backup target for restic (Hermes backups, encrypted)
Hermes itself stays at home (needs local devices: HA, phone, laptop).
```

## Implementation plan
1. Create the A1 VM with the full 4 OCPU / 24 GB (the slider appears only for the A1.Flex shape). Convert the account to pay-as-you-go to avoid idle reclaim, with a budget alert at €1.
2. Run Valheim under Box64 for one session with friends. Compare tick rate and lag with the droplet. Keep the droplet until it passes.
3. Add Tailscale and use the node as an off-site restic target for `hermes_backup.sh` output.
4. Manage it with Ansible from WOBI (a new inventory group `oci`) and Terraform's OCI provider for the VM.

## Deployment plan
Terraform (OCI provider) for the instance and network; a WOBI role for Valheim, Tailscale and restic server.

## Configuration
OCI API key (in Bitwarden), shape, Valheim world backup schedule, restic repo password.

## Cost / hardware
€0 within Always Free limits. Dropping the droplet saves ~$48/month (4 vCPU / 8 GB basic).

## Open questions
- Does Valheim under Box64 hold up with the usual player count? If not, keep the droplet for Valheim and use OCI only for backups.
- Is the OCI region close enough to Poland (Frankfurt/Amsterdam) for game latency?
