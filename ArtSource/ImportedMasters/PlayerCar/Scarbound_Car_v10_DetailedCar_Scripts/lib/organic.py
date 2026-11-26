"""Headless-safe 'sculpt' pipeline (blender-sculpting skill): union of primitives -> voxel remesh (fuses parts,
even density) -> volume-preserving smooth -> collapse decimate -> RoadGame attributes re-assigned by region."""
import math

import bpy
import numpy as np
from mathutils import Vector


def remesh_union(me_in, voxel=0.003, smooth=6, smooth_factor=0.6, target_tris=4000, name="organic", collection=None):
    col = collection or bpy.context.scene.collection
    ob = bpy.data.objects.new("_organic_tmp", me_in)
    col.objects.link(ob)
    r = ob.modifiers.new("remesh", "REMESH")
    r.mode = "VOXEL"
    r.voxel_size = voxel
    r.use_smooth_shade = True
    if smooth:
        s = ob.modifiers.new("smooth", "LAPLACIANSMOOTH")
        s.iterations = smooth
        s.lambda_factor = smooth_factor
        s.use_volume_preserve = True
        s.use_normalized = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tmp = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    tris = sum(len(p.vertices) - 2 for p in tmp.polygons)
    ob.modifiers.clear()
    ob.data = tmp
    if target_tris and tris > target_tris:
        d = ob.modifiers.new("decimate", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = target_tris / tris
        d.use_collapse_triangulate = False
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    else:
        out = tmp.copy()
    out.name = name
    bpy.data.objects.remove(ob)
    for m in (me_in, tmp):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return out


def paint(me, colfn, mats, uv_center=(0, 0, 0), uv_scale=1.0):
    """Write Color / UVMap / Unity_MaterialParams + material indices on an arbitrary mesh.
    colfn(position Vector) -> (rgba linear, (gloss, metal), material_name)."""
    me.materials.clear()
    for m in mats:
        me.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    mi = {m: i for i, m in enumerate(mats)}
    nv = len(me.vertices)
    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    vcol = np.zeros((nv, 4), np.float32)
    vgm = np.zeros((nv, 2), np.float32)
    vmat = np.zeros(nv, np.int32)
    for i in range(nv):
        c, gm, m = colfn(Vector(co[i]))
        vcol[i] = c
        vgm[i] = gm
        vmat[i] = mi[m]
    # faces: material by majority of their vertices
    nl = len(me.loops)
    lv = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    pstart = np.empty(len(me.polygons), np.int32)
    ptot = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", pstart)
    me.polygons.foreach_get("loop_total", ptot)
    fm = np.array([np.bincount(vmat[lv[s:s + t]]).argmax() for s, t in zip(pstart, ptot)], np.int32)
    me.polygons.foreach_set("material_index", fm)
    for a in list(me.color_attributes):
        me.color_attributes.remove(a)
    ca = me.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
    ca.data.foreach_set("color", vcol[lv].ravel())
    me.color_attributes.active_color = ca
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    c = np.array(uv_center, np.float32)
    d = co[lv] - c
    u = (np.arctan2(d[:, 0], d[:, 1]) / (2 * math.pi) + 0.5) * uv_scale
    v = (np.arctan2(d[:, 2], np.hypot(d[:, 0], d[:, 1])) / math.pi + 0.5) * uv_scale
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.stack([u, v], 1).astype(np.float32).ravel())
    p = me.uv_layers.new(name="Unity_MaterialParams")
    p.data.foreach_set("uv", vgm[lv].ravel())
    me.uv_layers.active = uv
    uv.active_render = True
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    me.update()
    return me


def ell_dist(p, c, r):
    return math.sqrt(((p.x - c[0]) / r[0]) ** 2 + ((p.y - c[1]) / r[1]) ** 2 + ((p.z - c[2]) / r[2]) ** 2)


def join_meshes(meshes, name):
    """Join meshes (each with the RoadGame attributes) into one mesh via temp objects."""
    col = bpy.context.scene.collection
    objs = []
    for me in meshes:
        o = bpy.data.objects.new("_join_tmp", me)
        col.objects.link(o)
        objs.append(o)
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    me = objs[0].data
    me.name = name
    bpy.data.objects.remove(objs[0])
    for m in meshes[1:]:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return me
