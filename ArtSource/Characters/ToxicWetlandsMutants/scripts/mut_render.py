"""Presentation renders of the mutants (EEVEE): front / side / back turnaround, a 3/4 hero view and a view from the
game's camera angle (pitch 54 deg). Used by mut_build.py --render and on its own:

    Blender -b ToxicWetlands_Mutants_v2.blend --python mut_render.py -- --out <dir> [--res 1024] [--only leechling,...]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

VIEWS = ('front', 'side', 'back', 'three', 'game')
STUDIO = 'MUT_Studio'


def studio(bg=(0.78, 0.75, 0.70), ground=(0.64, 0.61, 0.56)):
    """Neutral light stage like the concept sheet: warm grey world, soft key from the front-left, a cool rim."""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.view_settings.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = -0.15
    sc.render.film_transparent = False
    try:
        sc.eevee.taa_render_samples = 48
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    w = bpy.data.worlds.get('MUT_World') or bpy.data.worlds.new('MUT_World')
    sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes.get('Background')
    bgn.inputs['Color'].default_value = (*bg, 1.0)
    bgn.inputs['Strength'].default_value = 0.75
    coll = bpy.data.collections.get(STUDIO)
    if coll is None:
        coll = bpy.data.collections.new(STUDIO)
        sc.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    # ground disc
    me = bpy.data.meshes.new('MUT_Ground')
    r = 600.0
    me.from_pydata([(-r, -r, 0), (r, -r, 0), (r, r, 0), (-r, r, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('MUT_Ground', me)
    mat = bpy.data.materials.get('MUT_GroundMat') or bpy.data.materials.new('MUT_GroundMat')
    mat.use_nodes = True
    b = mat.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*ground, 1.0)
    b.inputs['Roughness'].default_value = 0.9
    me.materials.append(mat)
    coll.objects.link(g)
    key = bpy.data.objects.new('MUT_Key', bpy.data.lights.new('MUT_Key', 'SUN'))
    key.data.energy = 3.2
    key.data.angle = math.radians(8)
    key.data.color = (1.0, 0.96, 0.90)
    key.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-35))
    coll.objects.link(key)
    rim = bpy.data.objects.new('MUT_Rim', bpy.data.lights.new('MUT_Rim', 'SUN'))
    rim.data.energy = 1.1
    rim.data.angle = math.radians(20)
    rim.data.color = (0.80, 0.88, 1.0)
    rim.rotation_euler = (math.radians(60), math.radians(10), math.radians(150))
    coll.objects.link(rim)
    cam = bpy.data.objects.new('MUT_Cam', bpy.data.cameras.new('MUT_Cam'))
    coll.objects.link(cam)
    sc.camera = cam
    return cam


def bounds(root):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in root.children_recursive:
        if o.type != 'MESH' or o.get('unity_lod_level'):
            continue
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)))
            hi = Vector((max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)))
    return lo, hi


def aim(cam, target, direction, dist):
    cam.location = target + direction.normalized() * dist
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(root, out_dir, res=768, views=VIEWS, tag=None):
    """Renders the creature 'root' (others hidden). Returns the written file paths."""
    sc = bpy.context.scene
    cam = sc.camera
    tag = tag or root.name
    roots = [o for o in bpy.data.objects if o.get('mut_root')]
    for r in roots:
        for o in [r] + list(r.children_recursive):
            o.hide_render = (r != root) or bool(o.get('unity_lod_level'))
    lo, hi = bounds(root)
    ctr = (lo + hi) * 0.5
    size = hi - lo
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    out = []
    for v in views:
        cd = cam.data
        if v in ('front', 'side', 'back'):
            cd.type = 'ORTHO'
            span = max(size.z, size.x if v != 'side' else size.y) * 1.18
            cd.ortho_scale = max(span, 0.5)
            d = {'front': Vector((0, 1, 0.08)), 'side': Vector((1, 0, 0.08)), 'back': Vector((0, -1, 0.08))}[v]
            aim(cam, ctr, d, 40.0)
        elif v == 'three':
            cd.type = 'PERSP'
            cd.lens = 50
            d = Vector((0.75, 0.95, 0.55))
            span = max(size.x, size.y, size.z)
            aim(cam, ctr + Vector((0, 0, -size.z * 0.05)), d, span * 1.75 + 0.5)
        else:  # game camera angle: looks down at 54 deg from behind-right of the creature's facing
            cd.type = 'PERSP'
            cd.lens = 42
            p = math.radians(54)
            d = Vector((0.35, -math.cos(p), math.sin(p) + 0.12))
            span = max(size.x, size.y, size.z)
            aim(cam, ctr, d, span * 2.6 + 1.5)
        cd.clip_start = 0.05
        cd.clip_end = 400
        path = os.path.join(out_dir, f'{tag}_{v}.png')
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        out.append(path)
    for r in roots:
        for o in [r] + list(r.children_recursive):
            o.hide_render = bool(o.get('unity_lod_level'))
    return out


def silhouettes(out_dir, res=512):
    """Black silhouettes on white from the game camera angle and from the side (shape readability without colour)."""
    sc = bpy.context.scene
    vl = bpy.context.view_layer
    mat = bpy.data.materials.get('MUT_Silhouette') or bpy.data.materials.new('MUT_Silhouette')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    old_override = vl.material_override
    vl.material_override = mat
    w = sc.world
    bg = w.node_tree.nodes.get('Background')
    old_col = tuple(bg.inputs['Color'].default_value)
    old_str = bg.inputs['Strength'].default_value
    bg.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    old_vt = sc.view_settings.view_transform
    sc.view_settings.view_transform = 'Standard'
    ground = bpy.data.objects.get('MUT_Ground')
    if ground is not None:
        ground.hide_render = True
    paths = []
    try:
        for r in [o for o in bpy.data.objects if o.get('mut_root')]:
            paths += render(r, out_dir, res, ('game', 'side'), tag='sil_' + r.name)
    finally:
        vl.material_override = old_override
        bg.inputs['Color'].default_value = old_col
        bg.inputs['Strength'].default_value = old_str
        sc.view_settings.view_transform = old_vt
        if ground is not None:
            ground.hide_render = False
    return paths


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--res', type=int, default=1024)
    p.add_argument('--only', default='')
    p.add_argument('--views', default=','.join(VIEWS))
    p.add_argument('--silhouettes', action='store_true')
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    studio()
    only = [s for s in a.only.split(',') if s]
    for r in [o for o in bpy.data.objects if o.get('mut_root')]:
        if only and not any(k.lower() in r.name.lower() for k in only):
            continue
        render(r, a.out, a.res, a.views.split(','))
        print('MUT_RENDER', r.name, flush=True)
    if a.silhouettes:
        silhouettes(a.out)
        print('MUT_SILHOUETTES', flush=True)


if __name__ == '__main__':
    main()
