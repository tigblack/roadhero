# Detailed Blender car in RoadGame

The runtime car now loads `Resources/Cars/ScarboundDetailed.prefab` through
`ImportedCar`. The prefab contains the authored body, underside, four wheels
and stationary calipers, hood gun with cradle, harpoon and Quasimodo. Existing
driving, suspension, steering, recoil and arm IK animate its original pivots.
`Game.unity` uses it automatically through `Models.PlayerCar`; no scene drop-in
is necessary. The procedural generator remains a fallback if the asset is absent.

Source: `/Users/arthuri/Blender Proj/car/Scarbound_Car_v10_DetailedCar.blend`.
The source is read only. Six sets of baked BaseColor, Normal,
MetallicSmoothness and AO maps are in `Assets/RoadGame/Art/Cars/ScarboundDetailed`.
The shader keeps linear vertex alpha for lamps, while baked color replaces
vertex RGB. Other level and procedural materials retain their existing defaults.

The prefab has a single LODGroup; every animatable mesh has three levels.
Transitions are 0.55 / 0.28 / 0.001 screen-relative size before quality LOD bias.
LOD0/1/2 contain 330,174 / 139,558 / 47,789 nondegenerate triangles. Normals,
linear colors, UV0 and gloss/metal UV1 are retained. Unity calculates tangents
from the final geometry. Serialized Mesh assets, materials and PNGs are ordinary
Unity assets; Blender/FBX import plugins are not required to run the game.

## Rebuild

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  -b '/Users/arthuri/Blender Proj/car/Scarbound_Car_v10_DetailedCar.blend' -noaudio \
  --python Tools/Blender/export_detailed_car.py -- \
  --output Exports/Blender/2026-11-19/DetailedCar
```

Copy the four map types per set from the source `_Export/Textures` directory
into `Assets/RoadGame/Art/Cars/ScarboundDetailed/Textures`. Then run:

```sh
Unity -batchmode -disableaudio -projectPath "$PWD" \
  -executeMethod RoadGame.EditorTools.ImportedCarSetup.BuildAndBakeIcon \
  -quit -logFile Logs/blender_car_icon.log
```

The command rebuilds mesh assets while retaining their GUIDs, rebuilds the
prefab, verifies all texture/vertex streams, animation hooks and dimensions,
and bakes the Car UI icon. `-carInput /absolute/path` overrides the mesh input.
`ImportedCarSetup.Validate` can recheck the existing prefab separately.

The exported muzzle marker keeps its authored position but aligns Unity +Z
with the barrel; the Blender arrow empty used a different local display axis.
Gun dimensions: trunnion above plate 0.363 m, bore offset 0.055 m,
muzzle distance 1.02 m, rear grips about -0.42 m, recoil 0.05 m.

## Verification

`Docs/screenshots/blender-car-integration` contains the import report and
captures from actual Play Mode. `Logs/blender_car_*.log` contains import,
icon, driving and weapon-clearance runs. All work runs are muted.

The `cannoncheck` uses conservative primitives that enclose every source
polygon of the detailed gun and cradle, the complete recoil stroke and the
full-detail body/crew mesh colliders. It ignores lower LOD copies. Regenerate
pitch tables with `Tools/guntables.py` after changing weapon or body geometry,
then rerun clearance. As with the existing test, angular sampling is discrete;
tables retain a guard between measurements. The remaining homing trajectory is
checked at the resting recoil position. Harpoon tests cast full-detail mesh
edges against the car for 360 turning, recoil, lean and stepping poses.

The round's initial straight run extends until it leaves the padded pickup
footprint (minimum 1 m), preventing a homing round from descending through the
cab, bed or operator. Pitch tables account for both the body and operator;
their guard also wraps across the -180/+180 degree seam.

Final checks on 2026-11-19: 360 resting gun poses, 576 target aims and 360
harpoon poses had zero contacts with the car/crew. The minimum measured pitch
margin is 1 degree. The 24-second intro run completed with 17 shots/17 hits
and two harpoons/two retrieved wrecks, with no compilation, shader or runtime
exceptions. Six close-up views and four portrait gameplay frames were saved.
See `verification.json` beside the captures. The enclosing source geometry can
be rechecked with `validate_detailed_gun_proxies.py --source-dir <scripts-dir>`
in Blender's Python.

Original code, shader and Car icon files are backed up under
`Exports/Blender/2026-11-19/CarIntegrationBackup`.
