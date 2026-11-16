# 19 · Homelab virtualization platform (Proxmox vs OpenStack, unusual OSes)

**Status vs Hermes:** new. Today everything runs in VirtualBox on the Windows PC (prod .107, dev .108), managed by WOBI `roles/laptop_host` and the hermes-infra host daemon design. The VM only autostarts after Windows logon, and Windows shutdown kills it uncleanly (HERMES_MAP §1).
**Priority:** P3

## Goal and context
Filip asked when to use Proxmox and when OpenStack, whether Azure has something like publisher/offer/sku image references, and how to run an OS Azure does not support (Qubes OS) through nested virtualization. A separate chat asked how to combine several old computers into one bigger one.

Source: fjkazmierczak account.
- *Proxmox vs OpenStack* (2025-08-08)
- *Prywatne użycie Twingate* (2025-03-03, the last question)

Also from the **kazmierczakfilipjan** account:
- *Homelab Power Management* (2026-07-07): old PCs/laptops as nodes, Proxmox on a management node, automatic power on/off without touching keyboards, Tailscale, Ansible; DIY storage vs Synology
- *Dyski do cloud storage* (2026-07-30): which disks for home "cloud storage" (Nextcloud, Immich) and why buy a NAS at all
- *Hyper-V vs VirtualBox* (2026-05-28), *Zwiększenie rozmiaru VDI*, *GRUB i problemy z bootem* (2026-06), *RHEL 10 ESXi Support* (2026-07-07): pain with VirtualBox VMs

## Architecture
For one person's homelab, **Proxmox VE** fits; OpenStack is meant for multi-tenant clouds and needs a team to run it. Target:
```
dedicated mini PC / old desktop (Proxmox VE, ZFS)
   ├─ VM hermes-prod, VM hermes-dev   (moved from VirtualBox; WOBI pull.sh unchanged)
   ├─ LXC: Home Assistant, Jellyfin (10), Mosquitto (06)
   ├─ GPU passthrough VM (optional, for llama.cpp / robotics training)
   └─ Proxmox Backup Server (on second disk/NAS)
old PCs → extra Proxmox cluster nodes or PBS target (not "one big computer": SSI is not practical)
Terraform (bpg/proxmox provider) + Packer proxmox-iso builder replace terraforge VirtualBox stacks
```
This removes the dependence on the Windows PC (sleep, logon autostart, unclean shutdowns), which is the main P1 survivability issue.

Qubes on Azure is not supported in practice (Xen-based, needs nested HVM). Run it on bare metal if it's wanted at all.

## Implementation plan
1. Hardware: pick a host with ≥ 32 GB RAM, 2 SSDs and an Intel iGPU, or reuse an old PC.
2. Install Proxmox. Write Terraform (bpg provider) and a Packer template that produces the same Ubuntu 22.04 base as `packer-images`.
3. Rebuild hermes-dev on Proxmox with WOBI `pull.sh --role dev` and run the tests.
4. Cut over prod the same way as the 2026-10-09 VirtualBox cutover (same IP/Tailscale identity, Syncthing, backup restore).
5. PBS nightly backups next to the existing encrypted rclone backup.

## Deployment plan
Run in parallel for 2 weeks (dev only), then do a prod cutover with a rollback path (the VirtualBox VM kept powered off).

## Configuration
Terraform vars per VM, Proxmox API token in Bitwarden, ZFS pool layout, VLANs (IoT vs lab).

## Cost / hardware
- A used mini PC (i5/i7, 32–64 GB) costs roughly 1,500–3,000 PLN.
- Power: about 15–30 W idle, roughly 15–30 PLN/month.
- Proxmox is free (no-subscription repo).

## Additions from the kazmierczakfilipjan account
- **Power control.** One always-on management node (low-power mini PC or the Hermes VM host) runs Proxmox or just the control tools. Other nodes sleep. Wake them with Wake-on-LAN (BIOS + NIC setting). Fall back to smart plugs with "power on after AC loss" in BIOS for machines without WoL. Shut them down with Ansible/SSH when idle (e.g. no running VMs for 30 min). Expose all of it as HA buttons and a Hermes skill. Laptops: keep the lid-close action as "nothing" and cap the battery charge if the BIOS allows.
- **Storage.** DIY beats a Synology on cost: a mini PC or old PC + 2× CMR HDDs (WD Red Plus / Seagate IronWolf) in a ZFS mirror, or TrueNAS/OMV as a VM with the disks passed through. Nextcloud/Immich run on top. Back up off-site (restic to cloud object storage), because a mirror is not a backup.
- **VirtualBox pain is the trigger.** Repeated disk-resize and boot problems are a reason to move workloads off VirtualBox on Windows to the Proxmox node rather than to Hyper-V.

## Open questions
- Is a dedicated always-on box acceptable at home (noise, power)?
- Should Hermes prod move off the PC at all? That is the main architectural decision.
