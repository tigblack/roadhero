"""v12 step: presentation only (PREVIEW collection, excluded from FBX): light rig, review cameras incl. the Unity
game camera, scale-check copies of the reference car in a ford and in the main channel, viewport overlays without
relationship lines / gizmos, README text."""
import bpy, math
import numpy as np
from mathutils import Vector, Matrix
import rg_light, rg_cams
import rg_layout12 as LY

README = """ART PASS v12 — DustFlats 'River' (built on v11 incl. the live session state)
====================================================================
Script: ArtPass_v12/scripts/build_v12.py (runs on the open file). Details: ArtPass_v12/README_ArtPass_v12.md
Layout changes (intentional): winding outline (new perimeter rock bands, flared canyon mouth, NE wall closed),
shallow river carved into Ground (bed, banks, point bars, water surface), 3 fords, 2 bridges, 44 spawn roots
moved out of the channel, 97 Decor pieces removed. Integration data: ArtPass_v12/data/*.json (Unity coordinates).
Water level z = -0.22, max water depth 0.22 m (ref. car clearance 0.30 m), fords 0.09 m.
PREVIEW collection: lights, CAM_* review cameras (CAM_Game_* = Unity CameraRig 54 deg / 46 deg / 540x1170),
PREVIEW_Car_* scale checks (linked copies of the reference car, not exported).
"""


def copy_car(name, loc, yaw, coll):
    src = bpy.data.objects.get('REFERENCE_PlayerCar_DoNotMerge')
    if src is None:
        return None
    old = bpy.data.objects.get(name)
    if old:
        for o in list(old.children_recursive) + [old]:
            bpy.data.objects.remove(o)
    mapping = {}
    for o in [src] + list(src.children_recursive):
        c = bpy.data.objects.new(name if o is src else name + '_' + o.name, o.data)
        coll.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        for k in list(c.keys()):
            del c[k]
        c['artpass_v12'] = 'presentation scale check (not exported)'
        mapping[o] = c
    for o, c in mapping.items():
        if o.parent in mapping:
            mw = c.matrix_world.copy(); c.parent = mapping[o.parent]; c.matrix_world = mw
        for i, s in enumerate(o.material_slots):
            if i < len(c.material_slots):
                c.material_slots[i].link = 'OBJECT'; c.material_slots[i].material = s.material
    root = mapping[src]
    T = Matrix.Translation(loc) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Translation(-src.matrix_world.translation)
    root.matrix_world = T @ src.matrix_world
    return root


def run(ctx):
    sc = bpy.context.scene
    rg_light.setup(sc)
    coll = bpy.data.collections.get(rg_light.COL_NAME)
    for o in list(coll.objects):
        if o.name.startswith('CAM_'):
            bpy.data.objects.remove(o)
    for name, kind, p in rg_cams.SHOTS_V12:
        cname = 'CAM_' + ('Game_' if kind == 'game' else 'View_') + name
        if kind == 'game':
            cam = rg_cams.game_camera(cname, p['car'], p.get('floor', 0.0), collection=coll)
        elif kind == 'ortho':
            cd = bpy.data.cameras.new(cname); cd.type = 'ORTHO'; cd.ortho_scale = p['scale']; cd.sensor_fit = 'VERTICAL'; cd.clip_end = 3000
            cam = bpy.data.objects.new(cname, cd); coll.objects.link(cam); cam.location = (p['center'][0], p['center'][1], 400)
        else:
            cam = rg_cams.free_camera(cname, p['loc'], p['look'], p.get('lens', 35), collection=coll)
        cam['artpass_v12'] = 'review camera (not exported)'
    # reference car copies: centre ford and main channel (wheels on the bed)
    river = ctx['river']
    import step12_river as RV
    fords = RV.ford_list(river)
    placed = []
    for nm, st in (('PREVIEW_Car_InFord', fords[1] if len(fords) > 1 else fords[0]), ('PREVIEW_Car_InChannel', None)):
        if st is None:
            # deepest main-channel station inside the playable area, away from bridges and fords
            cand = [i for i, k in enumerate(river.kind) if k == 'main' and LY.point_in_poly(ctx['outline'], *river.P[i]) and abs(river.curv[i]) < 0.01]
            st = cand[len(cand) // 2]
        P = river.P[st]; N = river.N[st]
        z, *_ = river.height(np.array([P[0]]), np.array([P[1]]))
        yaw = math.atan2(N[1], N[0]) - math.pi / 2
        car = copy_car(nm, Vector((P[0], P[1], float(z[0]))), yaw, coll)
        placed.append(dict(name=nm, x=float(P[0]), y=float(P[1]), bed_z=round(float(z[0]), 3), water_depth=round(float(LY.WATER_Z - z[0]), 3)))
    ctx['scale_cars'] = placed
    sc.camera = bpy.data.objects.get('CAM_Game_09_river_ford_centre') or sc.camera
    sc.render.resolution_x, sc.render.resolution_y = rg_cams.W, rg_cams.H
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.type = 'MATERIAL'; sp.clip_end = 4000
                        sp.overlay.show_relationship_lines = False
                        sp.show_gizmo = False
    t = bpy.data.texts.get('ART PASS v12 — README') or bpy.data.texts.new('ART PASS v12 — README')
    t.clear(); t.write(README)
    st = bpy.data.texts.get('START HERE — RoadGame level')
    if st and 'ART PASS v12' not in st.as_string():
        st.write('\nART PASS v12 (river, bridges, winding outline): see "ART PASS v12 — README".\n')
    print('STEP12 presentation done', placed, flush=True)
