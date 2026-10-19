# 09 · Remote access between home machines + one shared central PC

**Status vs Hermes:** partly exists. There is a Tailscale tailnet with Tailscale SSH (WOBI `roles/tailscale`), and phone → VM access via Termux, mosh and tmux. There is no remote *desktop* (GUI) between PCs, and no shared central-compute setup.
**Priority:** P3

## Goal and context
Filip asked several related questions:
- What can Twingate do for private use?
- Is Twingate enough to reach one PC from another, or does that also need RustDesk? He asked for a step-by-step setup.
- When does one powerful shared computer with minimal thin clients pay off? He compared this for a gaming group and for an office, and asked about ThinLinc for shared gaming.
- How do you combine several old computers into one bigger machine?

Source: fjkazmierczak account, *Prywatne użycie Twingate* (2025-03-03).

Also from the other accounts:
- koalamis6: *SSH i transfer video* (2026-08-03, Linux laptop → Windows PC over SSH with full desktop control; enabling OpenSSH on Windows 11; RDP logs out the local user)
- kazmierczakfilipjan: *Raspberry Pi laptop DIY* (2026-01-06, a 13" touch Raspberry Pi 5 laptop, 3D-printed case, as a thin client to Proxmox VMs)

## Architecture
Use the **Tailscale** network that already exists instead of Twingate, which would duplicate it. Layer a remote-desktop tool on top:
```
PC-A ──tailnet──► PC-B
  RustDesk (self-hosted ID/relay server on the VM, direct IP over tailnet)  or
  Sunshine (host) + Moonlight (client)  ← for gaming / low-latency desktop
Thin clients (old laptop / mini PC / phone) → Moonlight or RustDesk → central PC
```
The shared-central-PC idea only works for **one active GPU user at a time** unless the machine is set up for GPU partitioning, which needs Proxmox with vGPU and is impractical on consumer cards (see [19](19-homelab-virtualization.md)). Combining old PCs into one machine (SSI) is not practical. Use them as cluster nodes for separate workloads instead (k3s or Proxmox cluster).

## Implementation plan
1. Install Sunshine on the gaming/desktop PC and Moonlight on the clients. Pair them over the tailnet.
2. Optional: a self-hosted RustDesk server (`hbbs`/`hbbr`) as a container on the VM for non-gaming remote support (family PCs). Tailnet only.
3. Wake-on-LAN from the Hermes VM (`wakeonlan` via a HA button), so the PC can be off until needed.

## Deployment plan
Add RustDesk server and WoL scripts through a WOBI role. Install the desktop apps by hand or with winget.

## Configuration
Tailscale ACLs (who can reach which PC on port 47984–48010 for Sunshine, 21115–21119 for RustDesk), the RustDesk server key.

## Cost / hardware
Free software. The client can be an old laptop or a ~€150 mini PC with hardware HEVC decode.

## Additions from the koalamis6 and kazmierczakfilipjan accounts
- **Linux → Windows.** Use RDP tunnelled over SSH (`ssh -L 3389:localhost:3389`) or directly over the tailnet with Remmina/FreeRDP. Windows RDP logs out the local user, even with the same account. If someone sits at the PC, use RustDesk or Sunshine instead, which share the live session.
- **Pi 5 thin-client laptop.** Feasible, but a 13" touch panel, battery (UPS HAT) and printed case cost about as much as a used business ultrabook. Build it as a maker project, not to save money. Client software: Moonlight/RustDesk, or the Proxmox SPICE console.

## Open questions
- Who are the users (family, friends for LAN games, Filip only)?
- Does the router support WoL from the LAN, or does a smart plug need BIOS "power on after AC loss"?
