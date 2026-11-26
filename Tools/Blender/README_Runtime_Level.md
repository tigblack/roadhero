# Edited Dust Flats runtime bundle

`export_runtime_level.py` reads the completed Blender v13 scene and creates
`Assets/RoadGame/Resources/Levels/DustFlatsV13`. It does not change the `.blend`.
Run it using Blender's executable (see the command in the script docstring).
Then validate with system Python:

```sh
python3 Tools/Blender/validate_runtime_level.py Assets/RoadGame/Resources/Levels/DustFlatsV13
```

`manifest.json` contains source IDs, original Unity names and hierarchy paths,
Blender object names, parents by array index, transforms, material indices and
references to mesh resources. Static IDs match the 2026-11-17 Unity scene
snapshot. `spawnId` is inherited from each `Spawn_#####_*` root. Runtime code
must attach these visuals to live generated objects; the snapshot must not
create a second set of gameplay spawns.

All geometry and transforms use Unity metres, X right/Y up/Z forward. The
axis reflection is compensated by reversing triangle winding. Parent indices
may occur later in the array; resolve the hierarchy in a separate pass.

Each mesh `.bytes` is little endian:

1. `int32 vertexCount`, `int32 submeshCount`.
2. `vertexCount` records of 14 float32 values: position XYZ, normal XYZ,
   linear colour RGBA, UV0 XY, UV1 XY.
3. For each submesh: `int32 indexCount`, then `indexCount` int32 indices.

Materials belong to each object, ordered by mesh submesh. `Color.a` retains
RoadToon's self-light value; it is not surface opacity. UV1 retains gloss/metal
parameters. For opacity, use the material descriptor `alpha`. Six source PNG
textures are copied from packed Blender data; world UVs and road tiling are
specified per material. Water needs transparent rendering.

The bundle preserves custom/smooth corner-normal directions and splits all
normal/colour/UV seams. Nonzero normals are normalized; 74 malformed zero
normal corners are repaired using their triangle normal. 1,578 degenerate
triangles are omitted. Buffers are shared by mesh datablock when no per-object
modifiers or clipping alter evaluated geometry.

114 hidden LOD objects reference the source `id` through `lodOf`. Their exported
local transforms are identity: the source LOD builder copied local-space mesh
buffers but saved stale world-space transforms for hidden children. Source and
LOD local bounds agree within 0.12 m (largest differences are cliff decimation).
`colliderMesh` references 13 simplified rock/gap collision buffers without
creating extra visible objects.

Reference cars, presentation cameras/lights and horizon backdrop are excluded.
New river meshes are clipped to Unity Z <= 105 so their presentation extensions
do not overlay later zones. The river floor/physics integration is separate;
mesh import alone does not alter Ground.Sample or navigation.

`export_report.json` records the source SHA-256, texture hashes, buffer counts
and repairs; `validation_report.json` records binary/reference checks. The v13
export has 298 unique mesh buffers, 708 mesh objects, 192 spawn roots and
111,291,776 bytes of uncompressed mesh data including LODs. Unity import/build
compression reduces disk/download size; this is not an FBX material conversion.

Water correction: the double-sided Blender source plane was mostly wound downward.
The exporter orients all water triangles and normals upward for Unity backface
culling, preserving the original vertex teal tint and shallow-water elevation.

# Second zone: Toxic Wetlands bundle

`ArtSource/Levels/ToxicWetlands/scripts/tw_export.py` exports
`ArtSource/Levels/ToxicWetlands/ToxicWetlands_Zone01_v1.blend` to
`Assets/RoadGame/Resources/Levels/ToxicWetlandsZ1`. It uses the same mesh binary
format and manifest as the Dust Flats bundle, plus these second-zone fields:

- `zone: 1`. Every material also carries `zone`, a `baseKind` (`ground`, `flat`,
  `road`, `water`, `actor`, `toon`), `dust` and `aoFloor`.
- Static IDs are the node IDs of the 2026-11-17 v10 snapshot, which match the
  current project for this zone. New objects use `blender_<name>`.
- `spawnRoot` covers all 182 second-zone spawns: props, foot enemies, buggies
  and the boss. The Dust Flats bundle covers props only.
  - `ImportedLevel` swaps meshes and materials on the live spawn hierarchy,
    matching by path. Duplicate names, such as the four `WheelSteer`, are
    matched by the closest local position.
  - Empties and pivots are not touched, so the procedural animation in `Rig`
    still works.
  - Respawn reuses the same objects, so a respawned spawn keeps the new mesh.
- `colliderMesh` with `colliderConvex` references 54 proxy buffers: arena
  buildings, tanks, pumps, pipelines, outfalls, south-dam chunks and tree
  trunks.
- `clipZone0` and `clipZone0MaxZ` (104.5): when this bundle is applied,
  `ImportedLevel.ClipNorth` drops the triangles north of z = 104.5 from these
  first-zone v13 perimeter massifs and from their collision copies. 11 meshes
  are clipped. Without this, the massifs overlap the second zone and bury 25 of
  its spawns. The cut is hidden by the south dam.
- 34 LOD children: LOD1 at 50 % switches at screen size 0.25, LOD2 at 25 % at
  0.10.
- Objects flagged `tw_hidden` export with mesh -1: the source renderer is
  disabled and its colliders stay.

`ImportedLevel` captures the original hierarchy once, before any bundle is
applied. It then applies `DustFlatsV13` (zone 0) and `ToxicWetlandsZ1` (zone
1). `ImportedLevel.ForZone(i)` returns the bundle for a zone.

Water uses `Assets/RoadGame/Resources/Levels/ToxicWetlands_surfaces.bytes`,
written by `tw_layout.py`. Layout, little endian:

- `"TWSF"`;
- `int32 nx, nz`;
- `float32 x0, z0, step (0.5 m), waterLevel (-0.08)`;
- `nx*nz` `int16` heights in mm;
- `nx*nz` `uint8` toxicity.

The same grid builds the Blender ground and water meshes. At runtime it drives
`WetlandSurfaces`:

- the base height for `Ground.Sample`;
- still-water wheel contacts in `WaterPhysics`;
- splashes in `RiverWaterFx`;
- the minimap.

The pool bed is at most -0.32 m, so the deepest water is 0.24 m. Water renders
with `SwampWater.shader`.

Stats:

| Item | Count |
|---|---|
| Nodes | 1,297 |
| Mesh objects | 834 |
| Unique buffers | 464 |
| Materials | 11 |
| Triangles, including LODs | 645,469 |
| Uncompressed mesh data | 37,788,140 bytes |

Validation: `-captureScenario wetlands` (34 checks). The first-zone scenarios
`blenderlevel` and `water` must still pass.
