# 07 · Open-source robot arm / humanoid you can teach and tele-operate

**Status vs Hermes:** new.
**Priority:** P4

## Goal and context
Filip asked about open-source (hardware and software) humanoids, and about robot arms on a wheeled or other base. Then he asked about buying a humanoid he can operate remotely, teach new skills, and fit with custom hands. Options discussed ranged from educational kits (Robotis), through research platforms, to commercial humanoids (Unitree G1).

Source: fjkazmierczak account.
- *Open-source humanoid robots* (2025-08-13)
- *Humanoid robot options* (2025-08-18)

## Architecture
Start with the cheapest platform that teaches the whole learning loop: **Hugging Face LeRobot with an SO-101 leader/follower arm pair**. It is fully open, 3D-printable and costs a few hundred euros. Its pipeline:
```
leader arm (teleop) → record episodes (LeRobot dataset) → train policy (ACT / diffusion) on GPU
                    → run policy on follower arm (+ USB cameras)
remote teleop: leader arm or keyboard/VR at home ↔ follower via Tailscale (latency permitting)
```
Later options:
- put the arm on a mobile base (LeKiwi, an open-source LeRobot mobile base)
- buy a humanoid only once the software loop works

## Implementation plan
1. Buy or print an SO-101 kit (leader plus follower) and 2 USB cameras.
2. Install LeRobot on the PC (Windows/WSL with a GPU) or a Linux box. Calibrate the arms.
3. Record about 50 episodes of one task (pick a sock and drop it in a basket; this ties to [06](06-robot-vacuum-valetudo.md)), train ACT, then evaluate.
4. Phase 2: the LeKiwi mobile base. Hermes gets a "robot" tool that triggers named policies.

## Deployment plan
A local lab setup. Training runs on rented cloud GPUs if the local GPU is too weak.

## Configuration
LeRobot config per robot (ports, calibration files), the dataset repo (private on the HF Hub, or local).

## Cost / hardware
- SO-101 pair: roughly €250–500 assembled, less if self-printed.
- LeKiwi base: roughly €200–400.
- Training: the local GTX 1650 Ti (4 GB) is marginal. Rent a GPU (a few € per training run) or use an RTX-class card.
- Humanoids (Unitree G1 class) cost about €15k or more, and are not justified until step 3 works.

## Open questions
- Is the goal learning and fun, or a real household helper? Household manipulation is still research-grade in 2026.
- Does Filip have a 3D printer?
