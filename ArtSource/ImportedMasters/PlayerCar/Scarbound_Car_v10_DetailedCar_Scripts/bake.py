"""Headless Cycles bake of the procedural surface materials into per-texture-set maps (never saves the .blend).
Blender -b file.blend --factory-startup -noaudio --python bake.py -- --out DIR [--sets A,B] [--res 2048] [--body-res 4096]
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--sets", default="all")
ap.add_argument("--res", type=int, default=2048)
ap.add_argument("--body-res", type=int, default=4096)
ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--only", default="")
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)
exec(open(os.path.join(os.path.dirname(__file__), "tsets.py")).read())

sc = bpy.context.scene
sc.render.engine = "CYCLES"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = "GPU"
except Exception as e:
    print("GPU setup failed, CPU bake:", e)
sc.cycles.samples = args.samples
sc.cycles.use_denoising = False
sc.render.bake.margin_type = "EXTEND"
if sc.world is None:
    sc.world = bpy.data.worlds.new("BakeWorld")
sc.world.light_settings.distance = 0.25

O = bpy.data.objects
sets = SETS if args.sets == "all" else {k: SETS[k] for k in args.sets.split(",")}


def mats_of(objs):
    out = []
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material not in out:
                out.append(s.material)
    return out


def target_nodes(mats, img):
    for m in mats:
        nt = m.node_tree
        n = nt.nodes.get("BAKE_TARGET") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "BAKE_TARGET"
        n.image = img
        for x in nt.nodes:
            x.select = False
        n.select = True
        nt.nodes.active = n


def bake(objs, mats, img, btype, **kw):
    target_nodes(mats, img)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    sc.render.bake.margin = 16 if img.size[0] >= 4096 else 8
    t0 = time.time()
    bpy.ops.object.bake(type=btype, **kw)
    return time.time() - t0


def with_emission_from(mats, socket_name):
    """Route a Principled input (linked source or value) to an Emission shader for an EMIT bake."""
    saved = []
    for m in mats:
        nt = m.node_tree
        p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        em = nt.nodes.new("ShaderNodeEmission")
        em.name = "BAKE_EMIT"
        inp = p.inputs[socket_name]
        if inp.is_linked:
            nt.links.new(inp.links[0].from_socket, em.inputs["Color"])
        else:
            v = inp.default_value
            em.inputs["Color"].default_value = (v, v, v, 1.0) if isinstance(v, float) else tuple(v)
        em.inputs["Strength"].default_value = 1.0
        old = out.inputs["Surface"].links[0].from_socket
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        saved.append((nt, old, out, em))
    return saved


def restore(saved):
    for nt, old, out, em in saved:
        nt.links.new(old, out.inputs["Surface"])
        nt.nodes.remove(em)


def new_img(name, res, data):
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if data else "sRGB"
    img.generated_color = (0.5, 0.5, 1.0, 1.0) if "Normal" in name else (0, 0, 0, 1)
    return img


def save(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


summary = {}
for sname, names in sets.items():
    objs = [O[n] for n in names]
    others = [o for o in bpy.data.objects if o.type == "MESH" and o not in objs]
    for o in others:
        o.hide_render = True
    for o in objs:
        o.hide_render = False
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
        o.data.uv_layers["UVMap"].active_render = True
    res = args.body_res if sname == "CarBody" else args.res
    mats = mats_of(objs)
    t = {}
    imgs = {}
    for key, data in (("BaseColor", False), ("Roughness", True), ("Metallic", True), ("Normal", True), ("AO", True), ("Emission", False)):
        imgs[key] = new_img("T_%s_%s" % (sname, key), res, data)
    # albedo through an emission shader: the Diffuse Color pass would return (1 - metallic) * albedo (dark metals)
    sv = with_emission_from(mats, "Base Color")
    t["BaseColor"] = bake(objs, mats, imgs["BaseColor"], "EMIT")
    restore(sv)
    if args.only == "BaseColor":
        save(imgs["BaseColor"], os.path.join(args.out, "T_%s_BaseColor.png" % sname))
        summary[sname] = {"BaseColor": round(t["BaseColor"], 1), "res": res}
        print("BAKED", sname, summary[sname], flush=True)
        for o in others:
            o.hide_render = False
        continue
    t["Roughness"] = bake(objs, mats, imgs["Roughness"], "ROUGHNESS")
    t["Normal"] = bake(objs, mats, imgs["Normal"], "NORMAL", normal_space="TANGENT")
    sv = with_emission_from(mats, "Metallic")
    t["Metallic"] = bake(objs, mats, imgs["Metallic"], "EMIT")
    restore(sv)
    sc.cycles.samples = 64
    t["AO"] = bake(objs, mats, imgs["AO"], "AO")
    sc.cycles.samples = args.samples
    t["Emission"] = bake(objs, mats, imgs["Emission"], "EMIT")
    for key, img in imgs.items():
        save(img, os.path.join(args.out, "T_%s_%s.png" % (sname, key)))
    # packed maps: Unity URP MetallicSmoothness (R = metal, A = 1 - roughness) and ORM (R AO, G rough, B metal)
    def px(img):
        a = np.empty(res * res * 4, np.float32)
        img.pixels.foreach_get(a)
        return a.reshape(res, res, 4)
    R, M, A = px(imgs["Roughness"]), px(imgs["Metallic"]), px(imgs["AO"])
    ms = np.zeros((res, res, 4), np.float32)
    ms[..., 0] = M[..., 0]
    ms[..., 3] = 1.0 - R[..., 0]
    img_ms = bpy.data.images.new("T_%s_MetallicSmoothness" % sname, res, res, alpha=True)
    img_ms.colorspace_settings.name = "Non-Color"
    img_ms.pixels.foreach_set(ms.ravel())
    save(img_ms, os.path.join(args.out, "T_%s_MetallicSmoothness.png" % sname))
    orm = np.ones((res, res, 4), np.float32)
    orm[..., 0], orm[..., 1], orm[..., 2] = A[..., 0], R[..., 0], M[..., 0]
    img_orm = bpy.data.images.new("T_%s_ORM" % sname, res, res, alpha=False)
    img_orm.colorspace_settings.name = "Non-Color"
    img_orm.pixels.foreach_set(orm.ravel())
    save(img_orm, os.path.join(args.out, "T_%s_ORM.png" % sname))
    summary[sname] = {k: round(v, 1) for k, v in t.items()}
    summary[sname]["res"] = res
    print("BAKED", sname, summary[sname], flush=True)
    for o in others:
        o.hide_render = False
print("BAKE_DONE", summary)
