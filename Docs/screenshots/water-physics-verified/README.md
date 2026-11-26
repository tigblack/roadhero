# Shallow river physics — 2026-11-19

The river now applies per-wheel, flow-relative hydrodynamic drag and wet grip to the actual car controller. Asymmetric immersion also creates yaw torque. The 9 cm ford and approximately 22 cm main channel remain drivable on their beds. The water volume excludes the bridge decks, flight above the surface and space below the bed.

`water-checks.json`: 49 checks passed across seven real controller runs. A 10 m/s coast ended at 2.46 m/s in the channel and 5.92 m/s on a verified flat dry road after approximately 0.81 s. The car restarted from rest, crossed the ford and drove in reverse while immersed. Both bridge decks had zero water force and emitted no new water effects. Entry/exit splashes, wheel sprays, ripples and clearing water contact on the far bank were checked.

`../water-drop/waterdrop-checks.json`: 10 additional checks passed after a 2 m vertical drop with zero commanded horizontal input. The car landed on the bed, produced a splash and expanding ripples, stayed immersed, and emitted no sand puff/tire dust or recovery.

Visuals use a dedicated animated URP water shader, a bounded 256-droplet particle system and up to 16 pooled water-clipped ripple rings. Dry tire tracks, dust and tire smoke are disabled at submerged wheels.

The first development run in `../water-physics/` identified a test route blocked by existing props on the southern bridge approach. The verified run starts at the actual bridge foot to isolate the complete deck crossing. No river physics change or scenery removal was needed.

Work runs used `-disableaudio`, editor master mute and isolated `_water_physics_verified` / `_water_drop` test saves. Player saves and audio settings were preserved.

Reproduce from the Unity project root:

```sh
Unity -batchmode -disableaudio -projectPath "$PWD" -executeMethod RoadGame.EditorTools.AutoCapture.Run -captureScenario water -captureOut "$PWD/Docs/screenshots/water-physics-verified" -captureTimes 1.5,2.7,6,9.6,10,15,21,27,37,43,45,48 -captureSaveKey _water_physics_verified -captureSize 540x1170
Unity -batchmode -disableaudio -projectPath "$PWD" -executeMethod RoadGame.EditorTools.AutoCapture.Run -captureScenario waterdrop -captureOut "$PWD/Docs/screenshots/water-drop" -captureTimes 1,2,4,6 -captureSaveKey _water_drop -captureSize 540x1170
```

Public WebGL release: Sites version 10, source commit `e4c230c02ec5dce52cf2a0ee14552a72f948c293`, deployment `appgdep_6afe380056f48191ba5fc44dc73effeb` succeeded. Public build-info and all five data-part URLs verified. Full Safari gameplay launch was not confirmed: native browser automation stopped accepting keyboard/coordinate input while the window showed world preparation. Unity controller/visual checks passed; no claim of browser gameplay verification.
