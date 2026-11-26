# RoadGame audit 2026-11-24 (before the pass)

Evidence: Editor batch runs (muted, -disableaudio, Mobile quality) on the frozen base clone + muted headless Chrome
on the current WebGL build (2026-11-24-handling). No phone run.

## P0 — blocks play / progress
| # | Problem | Repro | Impact | Verify fix |
|---|---|---|---|---|
| P0-1 | Garage/Shop in landscape: panel taller than the screen, title + close X off-screen | 1170x540 (phone turned), open Garage | window cannot be closed with X; HUD unusable in landscape | `uilayout` shots at 1170x540/844x390: X fully on screen, panel inside safe area |
| P0-2 | Route pointer leads into a place the car cannot pass (west_north: under the main bridge) | routetest west_north | player following the arrow is stuck | routetest: west_north ARRIVED, no route cell under low decks |
| P0-3 | works_lid: bot stuck 150 s at (28,0,50) next to the works | routetest works_lid | (diagnosing) | routetest works_lid ARRIVED |

## P1 — feel, feedback, readability
| # | Problem | Repro | Impact | Verify |
|---|---|---|---|---|
| P1-1 | Enemies wedge on big props: Spore Brute pushes into a Stilt Shack (r=2 m) for 5 s, no attack | mutants, brute stop (1 of 3 runs, 2 of 5) | melee enemy never reaches the car; flaky test | MUTDIAG: brute reaches attack in < 4 s in 5/5 runs; mutants 116/116 x3 |
| P1-2 | Melee can land through a hut: sight test uses only the blocker layer (props on Default) | brute behind a shack within 4.65 m | hit through a wall | strike blocked by solid prop -> no damage (unit check in mutants) |
| P1-3 | Landscape HUD: idle joystick ring, DRAG hint, zone banner, popups stack on the car; camera shows half the world height of portrait | 1170x540 shots | car hidden, cramped view | landscape shots: car centre clear of HUD rects |
| P1-4 | Garage/Shop item titles: white text with soft grey outline on cream cards | garage/shop 540x1170 | low contrast titles | contrast >= 4.5:1, shots |
| P1-5 | Boss hangar: faded ceiling pieces stack into a grey haze over the arena | bossfight, boss1 | boss telegraphs and the car hard to read | shot comparison, combined occluder alpha capped |
| P1-6 | Newcomer bot ready for boss only at ~14 min (v10: 8.5 min); HP lags (426/540 at 10.9 min) | introplay | slow first boss | re-run after fixes, compare |

## P2 — polish
- Mixed RU/EN UI (boss bar "THE MAMMOTH" vs slot "МАМОНТ"; EN titles, RU descriptions).
- Shop gem total: gem icon overlaps the last digit.
- World labels: gain "+0.1" overlaps damage "-10.5" over one enemy.
- Car reads pale/chalky at game camera; materials hard to tell apart (paint/metal/rubber).
- WebGL: WASM heap grows to 494 MiB of the 512 MiB cap during world build; renderer RSS peak 1.8 GB (desktop Chrome).
- WebGL: one 417 ms frame during the first drive.
- Test tool: AutoCapture.Shoot NRE before the session exists.

## Measurements (before)
- Editor Mobile 540x1170 median render: calm 2.51-2.74 ms, camp fight 1.95-2.55, boss 1.81-2.61, zone 2 2.14-2.84, buggies 2.81-2.85; 0.68-0.94 M tris (car LOD0/1/2 = 330k/140k/48k).
- WebGL (Chrome, M5 Max, 390x844@3, local server): ready 6.6 s after Play; world 2155 ms; WASM heap 494 MiB (peak); renderer RSS 1.80 GB at ready -> 1.00 GB driving; GPU 359 -> 200 MiB; frames 16.7 ms p95, max 417 ms.
