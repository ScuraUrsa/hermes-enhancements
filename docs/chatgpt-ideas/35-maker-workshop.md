# 35 · Home maker workshop (Prusa MK4S + MMU3, 3D scanning, small CNC, workbench)

**Status vs Hermes:** new. 3D printing and CNC appear only as ytdigest categories.
**Priority:** P3

## Goal and context
Filip owns a **Prusa MK4S** (with MMU3 plans) and prints practical items. Across many threads he:
- debugged the printer (X-axis self-test failure from a misaligned motor pulley, a part lifting off the bed and the PrusaSlicer brim setting, subtracting a cylinder in PrusaSlicer);
- planned an IKEA Lack enclosure for MK4 + MMU3 and asked which parts to print and which to buy;
- collected print ideas: Gridfinity bases, wardrobe/shelf organisers with standing labels, a hanging screw rail, a broom holder, wardrobe feet (PETG filled with epoxy), homebrewing and knitting accessories;
- wants to scan large spaces (the inside of a cabinet with a ventilation duct) with a Galaxy S20 FE and Kiri Engine using ArUco markers for scale, to design drawers that fit;
- asked about filaments (SUNLU TPU for silicone-mask moulds, PETG, PLA+ and where to buy in Poland);
- asked about a desktop CNC under 5,000 PLN for "any material", and a metal-capable one;
- designed a woodworking workbench (frame, height, levelling feet from local DIY stores);
- asked about home PCB making and how multilayer PCBs and chips are made.

Source: kazmierczakfilipjan.
- *Druk 3d dla browarnika*, *Przydatne wydruki 3d* (2025-12-04), *CNC do 5000 zł* (2025-12-19), *Druk 3D organizery szafy* (2026-01-17)
- *Skręcony kabel osi X* (2026-02-25), *First Big Print Ideas* (2026-02-28), *Nazwa chwytaka miotły* (2026-03-01), *Problem z drukiem 3D* (2026-03-02), *Szyna na śrubki 3D*, *Odejmowanie walca w PrusaSlicer* (2026-03-03)
- *Płytka perforowana vs scalona* (2026-04-08), *Prusa MK4 MMU3 Enclosure Assembly* (2026-07-06), *Projekt stołu stolarskiego* (2026-07-08)
- *Skanowanie dużych przedmiotów*, *TPU SUNLU do matryc* (2026-07-30)

## Architecture
```
design: OpenSCAD/CadQuery models in git (parametric: Gridfinity bins, labels, screw rail)  ← agent-editable
scan  : phone photogrammetry (Kiri/Polycam photo mode) + printed ArUco board for scale → mesh → measure in Blender/FreeCAD
print : PrusaSlicer profiles in git → Prusa Connect (or PrusaLink on LAN) → printer
monitor: PrusaLink API → Home Assistant (Prusa integration) → Hermes notifications (done, error, filament out)
library: printables links + own models indexed in Obsidian ("maker" folder)
```

## Implementation plan
1. **Printer in HA.** Enable PrusaLink on the MK4S and add the HA Prusa integration. Hermes posts "print done / failed" to Matrix.
2. **Parametric models repo.** Start with Gridfinity (use `gridfinity-rebuilt-openscad`) and the standing shelf labels. Claude Code can then generate variants ("bin 2×3 for M4 screws") and the STL is built in CI.
3. **Enclosure.** Make a BOM for the Lack + MMU3 enclosure from the Printables project (printed parts vs bought: acrylic panels, hinges, magnets, LED). Print in PETG.
4. **Scanning workflow note.** Print an ArUco/ChArUco board, scan the cabinet in photo mode, scale the mesh with the board, model the drawers around the measured duct.
5. **CNC decision.** For wood/plastic/aluminium a 3018-class router is enough (~1,500–3,000 PLN). Real steel milling does not fit the 5,000 PLN desktop budget. Decide after the drawer/workbench projects show a real need.

## Deployment plan
HA integration via the HA flow scripts. The models repo is a new private GitHub repo with an OpenSCAD CI job.

## Configuration
PrusaLink API key (in Bitwarden), slicer profiles, filament presets.

## Cost / hardware
Enclosure ~€100–150 in parts. Filament ~€15–25/kg. CNC 3018 Pro ~€300–600.

## Open questions
- Is the MMU3 already bought?
- Should Hermes queue prints automatically, or only report status? Auto-start is unsafe without someone checking the bed.
