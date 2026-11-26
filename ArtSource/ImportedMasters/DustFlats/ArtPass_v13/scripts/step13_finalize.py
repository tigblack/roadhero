"""v13 step: validation against the v12 baseline + drivable-surface agreement + river depth vs the reference car,
triangle stats by category, cleanup (orphan meshes), scene props."""
import bpy, os, json, math
import numpy as np
import rg_check13 as C
import rg_layout12 as LY


def category(o):
    n = o.name; p = o.parent.name if o.parent else ''
    if n.endswith(('_LOD1', '_LOD2')):
        return 'LOD (extra)'
    if n.startswith(('Hill', 'RoadHill', 'Bumps', 'Kicker')):
        return 'Terrain: hills, bumps, kickers'
    if n.startswith(('Mesa', 'Plateau', 'Ridge0')) or p in ('LookoutMesa',):
        return 'Rock massifs: mesa, plateau, ridge'
    if n.startswith(('Cliff', 'AP_Cliff')):
        return 'Perimeter & canyon cliffs'
    if n.startswith(('AP_Scree', 'AP_SandDrift')):
        return 'Scree & drifts'
    if n.startswith('Road'):
        return 'Roads'
    if n.startswith('Ramp'):
        return 'Jump ramps'
    if n.startswith(('Garage', 'Hangar', 'Works', 'Tunnel', 'Vents', 'Gate', 'Pad', 'Billboard', 'Palisade')) or o.data.name.startswith(('Shack', 'Tent', 'Tower')):
        return 'Buildings & structures'
    if n.startswith('AP_Bridge'):
        return 'Bridges'
    if n.startswith('AP_River') or n == 'Ground':
        return 'Ground & river'
    if o.data.name.startswith(('Barrels', 'Tires', 'Crates', 'JunkPile', 'CarWreck', 'Boulder', 'Chest')) or n in ('Barricade', 'Funnel', 'BigJump0Course.001', 'Wreck', 'Decor', 'GuideChevrons'):
        return 'Props'
    return 'Other (characters, vehicles, vegetation, backdrop, decals)'


def tri_stats():
    z = bpy.data.collections[C.ZONE]
    out = {}
    for o in z.all_objects:
        if o.type != 'MESH':
            continue
        o.data.calc_loop_triangles()
        c = category(o)
        a = out.setdefault(c, [0, 0]); a[0] += len(o.data.loop_triangles); a[1] += 1
    return out


def run(ctx):
    sc = bpy.context.scene
    root = ctx['root']
    rep = {}
    bpath = os.path.join(root, 'ArtPass_v13', 'stats', 'baseline_v12_fingerprint.json')
    base = json.load(open(bpath)) if os.path.exists(bpath) else None
    now = C.fingerprint()
    if base:
        issues, new = C.compare(base, now)
        rep['identity_issues'] = issues
        rep['new_objects'] = len(new)
        rep['objects_checked'] = len(base)
    z = bpy.data.collections[C.ZONE]
    bad = {}; degen = 0; degen_lod = 0
    for o in z.all_objects:
        if o.type != 'MESH':
            continue
        b = C.attributes_ok(o)
        if b:
            bad[o.name] = b
        d = C.mesh_sanity(o)['degenerate']
        if o.name.endswith(('_LOD1', '_LOD2')):
            degen_lod += d
        else:
            degen += d
    rep['meshes_missing_pipeline_attributes'] = bad
    rep['degenerate_triangles_lod0'] = degen
    rep['degenerate_triangles_lod_meshes'] = degen_lod
    rep['roofs_separate'] = [o.name for o in ctx['roofs'].objects]
    rep['surface_agreement_m'] = C.surface_agreement(ctx['level'])
    rep['river'] = dict(water_level=LY.WATER_Z, ground_to_bed_main=LY.DEPTH_MAIN, ground_to_bed_ford=LY.DEPTH_FORD,
                        water_depth_main=round(LY.DEPTH_MAIN + LY.WATER_Z, 3), water_depth_ford=round(LY.DEPTH_FORD + LY.WATER_Z, 3),
                        reference_car_clearance=LY.CAR_CLEARANCE, note='river channel, water and bridges carried over from v12 unchanged')
    rep['triangles_by_category'] = tri_stats()
    rep['ok'] = (not rep.get('identity_issues')) and not bad
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    sdir = os.path.join(root, 'ArtPass_v13', 'stats'); os.makedirs(sdir, exist_ok=True)
    json.dump(rep, open(os.path.join(sdir, 'v13_validation.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    json.dump(ctx['stats'], open(os.path.join(sdir, 'v13_build_stats.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    sc['artpass_v13_validation'] = json.dumps({k: v for k, v in rep.items() if k not in ('surface_agreement_m', 'triangles_by_category')}, default=str)
    print('VALIDATION13', json.dumps({k: v for k, v in rep.items() if k != 'surface_agreement_m'}, default=str)[:3000], flush=True)
    worst = sorted(((k, v['max_abs']) for k, v in rep['surface_agreement_m'].items() if v.get('max_abs') is not None), key=lambda t: -t[1])[:12]
    print('SURFACE13 worst', worst, flush=True)
