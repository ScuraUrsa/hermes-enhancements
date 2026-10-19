# 07 · Open-source robot arm / humanoid you can teach and tele-operate

**Status vs Hermes:** new.
**Priority:** P4

## Goal and context
Filip asked about open-source (hardware and software) humanoids, and about robot arms on a wheeled or other base. Then he asked about buying a humanoid he can operate remotely, teach new skills, and fit with custom hands. Options discussed ranged from educational kits (Robotis), through research platforms, to commercial humanoids (Unitree G1).

Source: fjkazmierczak account.
- *Open-source humanoid robots* (2025-08-13)
- *Humanoid robot options* (2025-08-18)

Also from the other accounts:
- kazmierczakfilipjan: *Zapytania do wyszukiwania modeli* (2025-09-18, a printable mobile base for the PAROL6 arm), *Zwiększenie payloadu Parol6* (2025-10-26, which parts to change for more than 1 kg payload)
- koalamis6: *Robotyka miniatury VR* (2026-07-21, a small rover/forklift robot (CyberBricks scale) driving through a 3D-printed diorama, seen in VR from its own camera); *Technic Duplo Comparison* (2026-08-20, printable Duplo-size Technic parts for a child)

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

## Additions from the kazmierczakfilipjan and koalamis6 accounts
- **PAROL6 as the "real arm" step after SO-101.** PAROL6 is fully open (hardware and software) but has about 1 kg payload. More payload means larger stepper motors and gearboxes on joints 1–3, a stiffer base and a bigger power supply. In practice that is a redesign, so buy for the payload you need. A wheeled base would need to be self-designed: printables only offer small rover chassis.
- **Mini telepresence rover (cheap first project).** An ESP32-CAM or Raspberry Pi Zero 2 W rover at CyberBricks scale with a micro-servo lift. Stream the camera to a phone VR headset (WebRTC, stereo optional) and drive it over the tailnet. This teaches the same camera → teleop → policy loop as LeRobot, for about €50–100.
- **Duplo-size Technic for a child.** Print from existing open libraries (PrintableBricks and similar), with PLA+ for bricks and PETG for axles and gears. No custom design is needed.

## Open questions
- Is the goal learning and fun, or a real household helper? Household manipulation is still research-grade in 2026.
- Does Filip have a 3D printer?
