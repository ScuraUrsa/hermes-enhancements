# 34 · Secure messaging channel between Filip and his agent

**Status vs Hermes:** already done. A Continuwuity Matrix server reachable only over Tailscale (WOBI role `matrix`, server side done 2026-10-09) plus the `notification_bridge`. Email via `himalaya`. No Nextcloud Talk, Signal or WhatsApp bot.
**Priority:** P5

## Goal and context
Filip compared, for talking to a self-hosted agent (OpenClaw then): self-hosted Nextcloud Talk vs WhatsApp and other messengers, hardening a Nextcloud Talk server in a VirtualBox homelab, a Twilio number registered to Signal for the agent, and Element/Matrix.

Source: kazmierczakfilipjan, *Self-hosted Nextcloud vs WhatsApp* (2026-05-15).

## Architecture (as built)
Matrix over the tailnet, end-to-end encrypted rooms, no public federation. This was the conclusion of that thread as well: a rented VoIP number on Signal is fragile (number recycling, registration lock), and Nextcloud Talk is heavier to run and secure than a Matrix homeserver.

## Implementation plan
Nothing new. Possible follow-ups:
1. Confirm E2EE is on in the Hermes rooms and the bot's device keys are verified.
2. Back up the Matrix signing key with the existing `hermes_backup.sh`.

## Deployment plan / Configuration / Cost
Existing WOBI role; no extra cost.

## Open questions
- Is a family-facing channel needed (family members are not on the tailnet)? That would be the only reason to revisit Signal or a public Matrix server.
