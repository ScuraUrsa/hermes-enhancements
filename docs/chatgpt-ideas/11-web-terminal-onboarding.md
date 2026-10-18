# 11 · Web terminal with one-click user provisioning

**Status vs Hermes:** new. Access today is tmux plus Tailscale SSH. The old `open-terminal` container on port 8001 was removed on 2026-10-06.
**Priority:** P4

## Goal and context
Filip wanted a link that opens a browser terminal. On first visit it automatically creates a Linux user with a home directory and a predefined `.bashrc` on a VM. Use cases: workshops, demos, giving someone a sandbox.

Source: fjkazmierczak account, *Web-based terminal setup* (2025-03-20).

## Architecture
Don't create real host users from a public link. Give every visitor an **ephemeral container**:
```
browser → reverse proxy (Caddy, Tailscale/Cloudflare Access auth) → spawner
          spawner (small FastAPI) → docker run --rm per session (image with bashrc/tools, CPU/RAM limits,
                                     no host mounts, idle timeout) → ttyd inside container
```
Off-the-shelf alternatives: JupyterHub with DockerSpawner (terminal plus notebooks), or Coder/code-server for full IDEs.

## Implementation plan
1. A sandbox image: Ubuntu, predefined bashrc and tools, a non-root user.
2. Spawner: create a container per authenticated identity and route `/u/<id>` to its ttyd. Clean up after 30 min idle.
3. Auth: start with Cloudflare Access email OTP or Tailscale identity. Never anonymous.
4. Limits: `--memory 512m --cpus 0.5 --pids-limit 256`, network egress allow-list.

## Deployment plan
Run on the dev VM first. Expose it through the existing Cloudflare tunnel docs only if there is a real audience.

## Configuration
Image tag, limits, idle timeout, the allowed identities list.

## Cost / hardware
About 100–200 MB RAM per active session. This rules out more than ~10 sessions on the 8 GB prod VM.

## Open questions
Who is the audience? Without one, this is a nice-to-have.
