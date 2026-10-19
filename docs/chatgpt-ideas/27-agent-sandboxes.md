# 27 · Disposable sandboxes for agents (Cursor-style "computers per agent")

**Status vs Hermes:** partly exists. Claude Code runs in git worktrees (`cc_run.py`); WOBI role `desktop` gives the VM a virtual screen; a `hermes-dev` VM exists for testing; the host daemon manages VM lifecycle (`vm-lifecycle` skill). Missing: per-task isolated machines (microVM/container) with snapshot reset, and network/egress policy per task.
**Priority:** P3

## Goal and context
Filip wants Hermes to give each agent task its own throw-away computer, the way Cursor does for background agents. Related wishes:
- run OpenClaw-style agents with a small local "brain" container while all execution happens on remote, disposable worker VMs, with GitOps (a CI-built image each time the agent edits its own code);
- one shared tool container (e.g. Ansible) used by several VMs, with a second one started on conflict;
- a safe lab to run malware samples for analysis.

Source: kazmierczakfilipjan.
- *Shared container between VMs* (2025-12-04)
- *Malware Analysis in VM* (2026-04-02)
- *GitOps OpenClaw Deployment* (2026-04-07), *Security of OpenClaw on Linux* (2026-04-09)
- *Odwzorowanie środowiska Cursor* (2026-08-04, Firecracker vs Docker, and how Open WebUI gives agents a workspace)

## Architecture
```
Kanban task ─► dispatcher ─► sandbox broker
                               ├─ tier 1: rootless container (podman) from a pinned image, worktree mounted,
                               │          egress allow-list (package mirrors, GitHub), CPU/RAM limits
                               ├─ tier 2: Firecracker microVM (via firecracker-containerd or Kata) for untrusted code,
                               │          snapshot → boot in <1 s, destroyed after the task
                               └─ tier 3: full VM on the Proxmox node (GUI/desktop tasks, malware lab on an isolated VLAN)
result = git branch / artifact only; nothing else leaves the sandbox
```
Tier choice by task label: `trusted-code` → 1, `untrusted`/`internet-code` → 2, `gui`/`malware` → 3.

## Implementation plan
1. Tier 1 first: wrap `cc_run.py` so it can start Claude Code inside a podman container with the worktree mounted and egress limited. Compare results and speed with the current direct runs.
2. Tier 2 POV on the Proxmox node (KVM is needed; nested KVM in VirtualBox is too slow): Kata Containers with the Firecracker hypervisor, so the same container images work.
3. Self-update via GitOps: the agent image is built by GitHub Actions from the repo; Hermes only pulls tagged images. No agent writes to its own running image.
4. Malware lab: a separate Proxmox VM template on an isolated bridge with no route to the LAN or tailnet, plus REMnux/FLARE tools, reset from snapshot after each run. Manual use only.

## Deployment plan
A WOBI role for podman and the broker. Kata/Firecracker only on the Proxmox node ([19](19-homelab-virtualization.md)).

## Configuration
Image tags (pinned), egress allow-list per tier, resource limits, max lifetime per sandbox.

## Cost / hardware
Tier 1 is free on the current VM. Tier 2/3 need the Proxmox node with VT-x and ~16 GB RAM spare.

## Open questions
- Is the extra isolation needed for Filip's own repos, or only for third-party code and web-browsing agents?
- The "one shared Ansible container for many VMs" idea: a pinned image per VM is simpler and avoids locking. Keep the shared one only if licences or caches make it worth it.
