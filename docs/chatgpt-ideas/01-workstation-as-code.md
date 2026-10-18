# 01 · Workstation as code (WSL/laptop → reproducible image → remote dev desktop)

**Status vs Hermes:** partly exists. `packer-images` builds the Hermes VM OVA, WOBI `roles/laptop_host` sets up the Windows host, and the `linux-vm-maintenance` skill handles disk cleanup. Nothing captures Filip's own dev environment as an image.
**Priority:** P2

## Goal and context
Filip wants his day-to-day environment (WSL Ubuntu with terraform/tfenv, ansible, docker, dotnet, kubectl/krew, minikube, zsh, fzf, many cloned repos) to be rebuildable as an image. He also wants to run it as a remote desktop: a Linux VM for work and, possibly, a Windows VM for media and games. He tried the "export the WSL tarball, then convert it to a VHD" route by hand. It took several long sessions on loop devices, GRUB in a chroot, and missing waagent/sshd, and it never produced a bootable result.

Source: fjkazmierczak account.
- *Packer Terraform Azure VMs* (2025-07-23)
- *Instalacja WSL w Windows* (2025-08-11)
- *Packer WSL Ubuntu Image* (2025-08-12)
- *Packer image for WSL* (2025-08-13)
- *Prepare WSL for Azure VM* (2025-08-19)
- *Redirect Installations to /mnt* (2025-03-19, a disk-full root partition on a cloud VM)

## Architecture
Don't convert a live WSL rootfs into a bootable disk. **Rebuild the environment from declarative code** instead:

```
dotfiles + tool manifest (YAML)          ← single source of truth, in git
        │
        ├── Ansible role "workstation"    ← installs tools; same role for every target
        │       ├── target: WSL (ansible-pull on the laptop)
        │       ├── target: Packer build (VirtualBox OVA locally / azure-arm optional)
        │       └── target: devcontainer / distrobox (fast, no VM)
        │
        └── data layer (NOT baked into images)
                ├── repos: a `repos.yaml` list → `ghq`/script clones them
                ├── secrets: Bitwarden (bws / bw CLI), never in the image
                └── personal files: Syncthing (already running on the Hermes VM)
```

Remote desktop (optional, phase 3): an Ubuntu VM with xrdp or KasmVNC, reached over Tailscale. A Windows gaming VM in the cloud is not cost-effective (see Cost).

## Implementation plan
1. Inventory: dump `apt-mark showmanual`, `pipx list`, `~/.local/bin`, tfenv/rbenv versions and git remotes under `~/` into a draft `workstation.yaml`. Filip reviews it.
2. Write an Ansible role `workstation` in WOBI. Reuse the `base` role's sha256-checked download helpers, and keep the package-type pattern Filip already uses: `{name: {type: package|binary|pipx|toolcache}}`.
3. Dotfiles repo (chezmoi), with the zsh/fzf config templated per host.
4. `repos.yaml` plus a clone script. Secrets get pulled at runtime from Bitwarden.
5. A Packer template that runs the same role. Build locally to an OVA first; `azure-arm` is a second source block.
6. Test: build in CI (or on the dev VM), boot, run `workstation-check` (each tool prints its version).

## Deployment plan
- Phase 1: apply the role to a fresh WSL distro (`wsl --import` of a stock Ubuntu rootfs). Success means parity with the current WSL in under 30 minutes.
- Phase 2: a Packer OVA for VirtualBox on the Windows PC (the same flow as the Hermes VM).
- Phase 3 (only if needed): Azure VM from the image, auto-shutdown, Tailscale only, no public SSH.

## Configuration
- `workstation.yaml` (tools plus pinned versions), `repos.yaml`, a chezmoi data file per host.
- WSL `/etc/wsl.conf` (`[boot] systemd=true`), plus the data disk location (move Docker data off the C: drive).
- For cloud VMs: put `/var/lib/docker` on the data disk from the start, which avoids the "root full, /mnt empty" problem.

## Cost / hardware
- Local WSL and an OVA cost nothing.
- An Azure B2ms Linux desktop with auto-shutdown runs roughly €15–40/month, depending on hours.
- A GPU Windows VM for games is NV-series, roughly €0.5–1+/h, so local hardware is far cheaper.

## Open questions
- Is the goal reproducibility (rebuild the laptop fast) or an always-on remote desktop? The answer decides whether phase 3 is worth doing.
- Work vs private: the work WSL may contain employer code or secrets, which must not go into a private image.

## Notes
The 2025 manual WSL→VHD attempt is a useful lesson. Treat images as build outputs of code, never as snapshots of a hand-tuned machine.
