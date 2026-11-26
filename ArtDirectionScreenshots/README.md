# Scarbound: five Unity art-direction prototypes

All five PNGs are **540×1170**, rendered from the actual Unity GameView in the current RoadGame project. They show one staged, frozen combat moment against the actual Mammoth boss in Dust Flats. Actual player/enemy models, world geometry, effects and game HUD are retained.

| PNG | Style | Main differences |
| --- | --- | --- |
| `01_casual_3d.png` | Bright casual 3D | Rounded versions of existing vehicle/prop meshes, saturated clean colors, soft lighting and shadows, broad plastic highlights. |
| `02_realistic.png` | Realistic material/lighting treatment | Existing geometry with continuous URP PBR shading, rough metal, rust, scratches, dust, restrained color and natural shadows. This compares material direction on the current models rather than replacing them with new high-detail assets. |
| `03_low_poly.png` | POLYGON / Synty-inspired low poly | Coarser vehicle/prop meshes, flat face normals, matte color planes and faceted terrain/rocks; road topology and markings preserved. No Synty assets were imported. |
| `04_comic_cel_shading.png` | Comic cel shading | Three light bands, navy ink silhouettes, hatching, graphic contrast and a restricted warm/teal palette. Clear outlines help mobile players distinguish the car, enemy and attacks quickly. |
| `05_pixel_art.png` | Pixel-art rendering prototype | The world renders at180×390 with Point upscaling to540×1170 and a20-color palette. The same HUD stays at native resolution for readable health, currency and controls; crisp retro silhouettes can give the game a recognizable identity on a phone. |

Camera transform, field of view, aspect, projection and non-jittered projection matrices, player/enemy transforms, HP, floating damage label, HUD text and layout are fixed. Gameplay scripts are disabled, particles paused, and game time frozen while the Editor keeps rendering. Before and after every image, the actual pinned GameView render target is checked to be540×1170. The frozen-state SHA256 is identical for all five; see `verification.json` and `capture-manifest.txt`.

Every final PNG was opened at full size. All five were also compared as180×390 thumbnails. No image-generation or paint-over process was used.

The experiment runs only in Play Mode with cloned materials/meshes/render-pipeline settings and an isolated preview save key. The scene and gameplay assets are not saved with these styles, and the public website is not changed.

Reproduction tools:

- `Assets/RoadGame/Editor/ArtDirection/ArtDirectionCapture.cs`: prepare one frozen scene; start with `ArtDirectionCapture.Begin()` through the connected Unity Editor.
- `Tools/ArtDirection/CaptureGameViews.cs`: atomically capture all five via the installed Unity Pipeline `CaptureGameView(source=screen)` implementation.
- `Tools/ArtDirection/FinishPreview.cs`: verify the final state and leave Play Mode, restoring the original pipeline and editor options.

Use the installed Unity CLI connection to this project. Compile preview scripts first with `unity recompile`, then evaluate the files with `unity command script eval --file <path>`; allow90seconds for scene preparation and capture.
