"""Headless review renders for the Scarbound car (never saves the .blend).

Blender -b file.blend --factory-startup -noaudio --python render_views.py -- \
    --out DIR --tag before [--views game,game_zoom,front34,...] [--clay] [--only-clay] [--samples 48]

Views use identical cameras for every file so before/after pairs line up.
The game camera reproduces RoadGame's CameraRig: perspective, pitch 54 deg, vertical FOV 46 deg,
portrait 540x1170, halfWidth 13.5 m -> distance 68.9 m, focus 2.5 m ahead of the car.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--views", default="all")
ap.add_argument("--clay", action="store_true")
ap.add_argument("--only-clay", action="store_true")
ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--scale", type=float, default=1.0)
ap.add_argument("--lod", default="")
ap.add_argument("--baked", action="store_true")
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)

sc = bpy.context.scene
ROOT = bpy.data.objects["REFERENCE_PlayerCar_DoNotMerge"]


def hex_rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


# ---------------------------------------------------------------- what is rendered
lod_cols = [c for c in bpy.data.collections if c.name.startswith("LOD")]
for c in lod_cols:
    for ob in c.all_objects:
        ob.hide_render = True
if args.lod:
    # show the requested LOD meshes instead of LOD0 (swap mesh data on the LOD0 objects, in memory only)
    for ob in list(bpy.data.objects):
        lod = bpy.data.objects.get(ob.name + "_" + args.lod)
        if ob.type == "MESH" and lod is not None and lod.type == "MESH":
            ob.data = lod.data
if args.baked:
    # show the export materials M_<Set> (baked textures only), as the FBX / Unity side receives them
    exec(open(os.path.join(os.path.dirname(__file__), "tsets.py")).read())
    for sname, names in SETS.items():
        mat = bpy.data.materials.get("M_" + sname)
        for n in names:
            ob = bpy.data.objects.get(n)
            if ob is None or mat is None:
                continue
            me = ob.data.copy()
            me.materials.clear()
            me.materials.append(mat)
            me.polygons.foreach_set("material_index", [0] * len(me.polygons))
            ob.data = me
for c in bpy.data.collections:
    if c.name.startswith("PREVIEW"):
        for ob in c.objects:
            ob.hide_render = True

car_meshes = [o for o in [ROOT] + list(ROOT.children_recursive) if o.type == "MESH" and not o.hide_render]


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


lo, hi = bbox(car_meshes)
center = (lo + hi) * 0.5

# ---------------------------------------------------------------- world, sun, ground
world = bpy.data.worlds.new("ReviewWorld")
sc.world = world
nt = world.node_tree
bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (*hex_rgb("#BFC8D4"), 1)
bg.inputs[1].default_value = 0.85

sun_data = bpy.data.lights.new("ReviewSun", "SUN")
sun_data.energy = 3.6
sun_data.angle = math.radians(4)
sun_data.color = (1.0, 0.97, 0.92)
sun = bpy.data.objects.new("ReviewSun", sun_data)
sc.collection.objects.link(sun)
# Unity Euler(56, 118, 0): light travels (0.494, -0.829, -0.262) in Unity xyz -> Blender (x, z_u, y_u)
d = Vector((0.494, -0.262, -0.829)).normalized()
sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

fill_data = bpy.data.lights.new("ReviewFill", "SUN")
fill_data.energy = 0.9
fill_data.angle = math.radians(30)
fill_data.color = (0.82, 0.88, 1.0)
fill_data.use_shadow = False
fill = bpy.data.objects.new("ReviewFill", fill_data)
sc.collection.objects.link(fill)
fill.rotation_euler = Vector((0.55, 0.65, -0.52)).normalized().to_track_quat("-Z", "Y").to_euler()

ground_me = bpy.data.meshes.new("ReviewGround")
s = 300
ground_me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
ground = bpy.data.objects.new("ReviewGround", ground_me)
sc.collection.objects.link(ground)
gmat = bpy.data.materials.new("ReviewGroundMat")
gb = next(n for n in gmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
gb.inputs["Base Color"].default_value = (*hex_rgb("#E0B888"), 1)
gb.inputs["Roughness"].default_value = 0.95
ground_me.materials.append(gmat)
ground.location.z = min(0.0, lo.z) - 0.002

clay = bpy.data.materials.new("ReviewClay")
cb = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
cb.inputs["Base Color"].default_value = (0.36, 0.36, 0.36, 1)
cb.inputs["Roughness"].default_value = 0.55

# ---------------------------------------------------------------- render settings
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = args.samples
except Exception:
    pass
sc.render.film_transparent = False
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.render.resolution_percentage = 100

cam_data = bpy.data.cameras.new("ReviewCam")
cam = bpy.data.objects.new("ReviewCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def look_at(loc, target):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def W(name):
    ob = bpy.data.objects.get(name)
    return ob.matrix_world.translation.copy() if ob else None


GAME_PITCH = 54.0
GAME_FOV = 46.0
ASPECT = 540 / 1170
GAME_DIST = 13.5 / (math.tan(math.radians(GAME_FOV / 2)) * ASPECT)
GAME_FOCUS = Vector((0, 2.5, 0))
gd = Vector((0, math.cos(math.radians(GAME_PITCH)), -math.sin(math.radians(GAME_PITCH))))
GAME_POS = GAME_FOCUS - gd * GAME_DIST


def setup(view):
    cam_data.shift_x = cam_data.shift_y = 0
    cam_data.clip_start, cam_data.clip_end = 0.05, 400
    if view in ("game", "game_zoom"):
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "VERTICAL"
        cam.location = GAME_POS
        cam.rotation_euler = (math.radians(90 - GAME_PITCH), 0, 0)
        if view == "game":
            cam_data.angle_y = math.radians(GAME_FOV)
            return 540, 1170
        # same projection centre and orientation, narrower FOV: an exact magnified crop of the game frame
        fov = math.radians(4.4)
        cam_data.angle_y = fov
        bpy.context.view_layer.update()
        p = cam.matrix_world.inverted() @ Vector((0, -0.1, 0.7))
        k = 2 * math.tan(fov / 2)
        cam_data.shift_x = (p.x / -p.z) / k
        cam_data.shift_y = (p.y / -p.z) / k
        return 1000, 1000
    if view == "front34":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 50
        look_at(center + Vector((4.3, 6.0, 2.35)), center + Vector((0, 0.15, -0.05)))
        return 1500, 1000
    if view == "rear34":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 50
        look_at(center + Vector((-4.6, -5.8, 2.9)), center + Vector((0, -0.1, 0.0)))
        return 1500, 1000
    if view == "profile":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 5.7
        look_at((12, center.y, center.z), (0, center.y, center.z))
        return 1600, 760
    if view == "top":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 5.5
        cam.location = (center.x, center.y, 15)
        cam.rotation_euler = (0, 0, 0)
        return 900, 1400
    if view == "gun_close":
        t = W("TurretBase") or Vector((0.56, 1.05, 1.0))
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 50
        look_at(t + Vector((1.45, 1.75, 0.95)), t + Vector((-0.02, 0.32, 0.16)))
        return 1400, 1000
    if view == "gun_side":
        t = W("TurretBase") or Vector((0.56, 1.05, 1.0))
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = 2.2
        look_at(t + Vector((6, 0.35, 0.25)), t + Vector((0, 0.35, 0.25)))
        return 1400, 900
    if view == "wheel_fr":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 50
        look_at((2.6, 2.6, 0.75), (0.95, 1.45, 0.45))
        return 1200, 900
    if view == "under":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 35
        look_at((3.2, 3.4, 0.35), (0.0, 0.2, 0.3))
        return 1400, 900
    q = W("Quasimodo") or Vector((0, -2.09, 0.6))
    if view == "quasi_front":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 60
        look_at(q + Vector((1.25, 2.35, 1.55)), q + Vector((0.0, 0.05, 0.95)))
        return 1000, 1200
    if view == "quasi_back":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 60
        look_at(q + Vector((-1.15, -2.55, 1.35)), q + Vector((0.0, 0.0, 0.95)))
        return 1000, 1200
    if view == "quasi_side":
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "AUTO"
        cam_data.lens = 60
        look_at(q + Vector((2.9, 0.15, 1.15)), q + Vector((0.0, 0.1, 0.9)))
        return 1000, 1200
    raise ValueError(view)


ALL = ["game", "game_zoom", "front34", "rear34", "profile", "top", "gun_close", "gun_side",
       "quasi_front", "quasi_back", "quasi_side"]
views = ALL if args.views == "all" else args.views.split(",")
modes = []
if not args.only_clay:
    modes.append("mat")
if args.clay or args.only_clay:
    modes.append("clay")

written = []
for mode in modes:
    bpy.context.view_layer.material_override = clay if mode == "clay" else None
    bg.inputs[1].default_value = 0.5 if mode == "clay" else 0.85
    sun_data.energy = 2.9 if mode == "clay" else 3.6
    fill_data.energy = 0.6 if mode == "clay" else 0.9
    for v in views:
        rx, ry = setup(v)
        sc.render.resolution_x = int(rx * args.scale)
        sc.render.resolution_y = int(ry * args.scale)
        suffix = "" if mode == "mat" else "_clay"
        path = os.path.join(args.out, f"{args.tag}_{v}{suffix}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        written.append(path)
        print("RENDERED", path, flush=True)
print("DONE", len(written))
