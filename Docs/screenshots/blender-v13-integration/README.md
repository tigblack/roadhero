# Blender v13 → RoadGame

Source: `/Users/arthuri/Blender Proj/New Folder(1)/DustFlats_Level_v13_SmoothPass.blend`.
Source SHA-256: `3e5c69fae07b6b638e931db51673af2bc069e2ddc1ca826ddc06b93183a27651`.
The Blender source was read without changing it.

The imported first zone is active by default in `Assets/Scenes/Game.unity`.
`ImportedLevel` grafts the edited meshes onto the original deterministic gameplay hierarchy;
live destructible props receive their edited meshes at spawn time. Frozen actors and
reference cars are excluded. Gates, repair effects, roof fading, hit feedback and respawn
retain their gameplay components. All original static IDs resolve without ambiguity.

The runtime bundle contains 298 shared mesh buffers, 114 LOD objects, 13 collision proxies
and six colour textures. The exported vertex colours, custom normals, UV0 and UV1
gloss/metal parameters are preserved. The source's downward-facing water surface is
corrected in the export so Unity backface culling displays it correctly.

Driving surfaces use the exact Blender river profile, including shallow fords and point
bars, and two continuous curved bridge decks. Water is at -0.22 m; the main bed is at
-0.44 m and the fords at -0.31 m. New outline/bridge blockers replace stale first-zone
perimeter blockers. Forty-four authored spawn moves are preserved and seven additional
props are moved clear of bridge approaches while retaining their persistent IDs.
The minimap shows the new river, crossings and boundary.

`before/start_00.png` is the procedural game before integration. `after/blenderlevel_*.png`
are actual Unity game-camera captures at Mobile quality, 540×1170:

| Image | Scenario |
| --- | --- |
| 00 | Driving through the central ford |
| 01 | Driving across the main road bridge |
| 02 | Driving onto/across the track bridge |
| 03 | Garage and nearby environment |
| 04 | Mammoth Works with the roof fading |
| 05 | Intro ramp and canyon |
| 06 | Original Rust Canyon zone |

`after/integration-checks.json` records the actual car-controller crossings, source ID
mapping, river/deck support heights, live prop damage/destruction/respawn, gate state
and roof-fade checks. Each crossing records the car's minimum/maximum height and
recovery count. The test remembers reaching the end of each route instead of treating
later braking distance as a failed crossing.

The test uses its own save suffix and runs silently. Reproduce from the project root:

```sh
'/Applications/Unity/Hub/Editor/6000.6.4f1/Unity.app/Contents/MacOS/Unity' \
  -batchmode -disableaudio -projectPath "$PWD" \
  -executeMethod RoadGame.EditorTools.AutoCapture.Run \
  -captureScenario blenderlevel -captureTimes 4,12,21,30,35,40,45 \
  -captureSize 540x1170 -captureQuality 0 \
  -captureSaveKey _blender_v13_integration \
  -captureOut "$PWD/Docs/screenshots/blender-v13-integration/after" \
  -logFile "$PWD/Logs/blender_v13_integration.log"

python3 Tools/Blender/validate_runtime_level.py Assets/RoadGame/Resources/Levels/DustFlatsV13
```

Compilation, source/mapping diagnostics and drive telemetry are in
`Logs/blender_v13_integration.log`. These are Editor checks on the Mobile render path;
they are not measurements on a physical Android device.

Final result: 23 integration checks passed, zero failures. A separate fresh-game intro run
(`intro/intro_*.png`, `Logs/blender_v13_intro.log`) cleared both scouts, took off from the
new ramp and landed at approximately session 13.38 s, position Z -97.77 m, with full HP.
Save-position and recovery bounds follow the new first-zone outline, including its bays.
