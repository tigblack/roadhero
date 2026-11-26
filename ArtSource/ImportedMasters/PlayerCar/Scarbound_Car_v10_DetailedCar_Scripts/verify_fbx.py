"""Reimport each exported FBX into an empty scene and check hierarchy, names, scale, tris, bounds."""
import bpy, sys, os, json
from mathutils import Vector
exp = sys.argv[sys.argv.index("--") + 1]
need = ["REFERENCE_PlayerCar_DoNotMerge", "Body.573", "Details", "TurretBase", "TurretYaw", "TurretPitch", "Barrel0", "GunMesh",
        "GunCradle", "HoodGun_Muzzle", "Harpooner", "Launcher", "Muzzle.018", "Quasimodo", "Cloak", "HeadMesh", "HandR", "HandL",
        "WheelSteer.082", "Wheel.082", "Wheel.084", "Wheel.085", "BrakeCaliper_FL", "Underbody"]
out = {}
for lv in (0, 1, 2):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = os.path.join(exp, "Scarbound_Car_v10_DetailedCar_LOD%d.fbx" % lv)
    bpy.ops.import_scene.fbx(filepath=path)
    obs = bpy.data.objects
    meshes = [o for o in obs if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    root = obs.get("REFERENCE_PlayerCar_DoNotMerge")
    missing = [n for n in need if n not in obs]
    uv_ok = all([u.name for u in o.data.uv_layers][:2] == ["UVMap", "Unity_MaterialParams"] for o in meshes)
    col_ok = all("Color" in o.data.color_attributes for o in meshes)
    mats = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
    imgs = sorted({i.name for i in bpy.data.images})
    muzzle = obs.get("HoodGun_Muzzle")
    out["LOD%d" % lv] = dict(objects=len(obs), mesh_objects=len(meshes), tris=tris, size_m=[round(v, 3) for v in (hi - lo)],
                             root_scale=[round(v, 4) for v in root.matrix_world.to_scale()] if root else None, missing=missing,
                             uv_layers_ok=uv_ok, color_attr_ok=col_ok, materials=mats, images=len(imgs),
                             muzzle_world=[round(v, 3) for v in muzzle.matrix_world.translation] if muzzle else None)
    print("VERIFY", lv, json.dumps(out["LOD%d" % lv]), flush=True)
json.dump(out, open(os.path.join(exp, "reimport_check.json"), "w"), indent=2)
