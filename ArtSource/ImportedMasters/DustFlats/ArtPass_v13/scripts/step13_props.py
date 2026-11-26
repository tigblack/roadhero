"""v13 step: props & bridges.

* Barrels: re-lathed on the same spots with 32 segments and arc-rounded rims / hoops / lid edges (was 20).
* Tyres: re-lathed with 40 segments, rounded shoulders and sidewalls, tread lugs kept as alternating offsets (was 28).
* Boulder spawns: rounded flat-capped sandstone blocks on the v11 footprints.
* Crates, junk piles, car wrecks, chests, barricade, funnel barriers, jump-course scrap blocks, bus wreck,
  decor, bridges (road bridge, track bridge), river gap boulders: rounded component by component (rg_round:
  multi-segment bevels, true 16-40 segment cylinders for posts / rails / pipes)."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
import rg_round as RR
import rg_sculpt as S
from step_props import _paint_variant


def Sf(kind, k=1.0):
    return L.surf(kind, k)


def barrel32(p, M, r, h, paint, rr, segs=24):
    rim = Sf('steel', 0.85); rust = Sf('rust', 1.0)

    def pf(tag, i, j):
        if tag == 'rim':
            return rim
        if tag == 'hoop':
            return (paint[0] * 0.8, paint[1] * 0.8, paint[2] * 0.8, 1, 0.5, 0.2)
        if tag == 'foot':
            return L.mix(paint, rust, 0.65)
        if tag == 'lid':
            return (paint[0] * 0.9, paint[1] * 0.9, paint[2] * 0.9, 1, 0.45, 0.15)
        if rr.random() < 0.05:
            return L.mix(paint, rust, 0.45)
        return paint
    prof = [(r * 0.95, 0.0, 'foot'), (r * 0.99, 0.006, 'foot')]
    # rolled bottom chime (arc)
    for k in range(4):
        a = math.pi * k / 3
        prof.append((r * 1.0 + 0.016 * math.sin(a), 0.022 + 0.022 * (1 - math.cos(a)), 'rim'))
    prof += [(r * 0.99, 0.075, 'foot'), (r * 0.995, 0.16, 'body')]
    for zc in (h * 0.335, h * 0.665):     # rolled hoops (arc profile)
        prof.append((r * 1.0, zc - 0.03, 'body'))
        for k in range(3):
            a = math.pi * k / 2
            prof.append((r + 0.011 * math.sin(a), zc - 0.02 + 0.04 * k / 2, 'hoop'))
        prof.append((r * 1.0, zc + 0.03, 'body'))
    prof.append((r * 0.99, h - 0.075, 'rim'))
    for k in range(4):                     # rolled top chime
        a = math.pi * k / 3
        prof.append((r * 1.0 + 0.016 * math.sin(a), h - 0.06 + 0.04 * k / 3, 'rim'))
    prof += [(r * 0.985, h - 0.012, 'rim'), (r * 0.94, h - 0.02, 'lid'), (r * 0.94, h - 0.03, 'lid')]
    K.lathe(p, prof, segs, M, pf, 'plain')
    for (dx, dy, rb) in ((r * 0.5, 0.0, 0.06), (-r * 0.55, r * 0.2, 0.035)):
        q = M @ Vector((dx, dy, h - 0.03)); n = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
        K.cyl_between(p, q, q + n * 0.025, rb, rim, 16, bevel=0.006)


def tyre40(p, M, R, w, rr, rim=False, segs=24):
    rub = Sf('rubber', 1.0); side = Sf('rubber', 1.35); hub = Sf('steel', 0.7)
    ri = R * 0.48
    prof = [(ri, -w * 0.30, 'in')]
    # inner bead -> sidewall -> rounded shoulder -> tread -> shoulder -> sidewall -> bead (closed)
    for k in range(4):
        a = 0.5 * math.pi * k / 3
        prof.append((ri + (R * 0.86 - ri) * (k / 3), -w * (0.30 + 0.2 * math.sin(a)), 'side'))
    for k in range(5):
        a = 0.5 * math.pi * k / 4
        prof.append((R * 0.86 + R * 0.14 * math.sin(a), -w * 0.5 + w * 0.2 * (1 - math.cos(a)), 'tread'))
    prof.append((R, 0.0, 'tread'))
    for k in range(5):
        a = 0.5 * math.pi * (4 - k) / 4
        prof.append((R * 0.86 + R * 0.14 * math.sin(a), w * 0.5 - w * 0.2 * (1 - math.cos(a)), 'tread'))
    for k in range(4):
        a = 0.5 * math.pi * (3 - k) / 3
        prof.append((ri + (R * 0.86 - ri) * ((3 - k) / 3), w * (0.30 + 0.2 * math.sin(a)), 'side'))
    prof.append((ri, w * 0.30, 'in'))
    full = prof + [prof[0]]
    nt = len(full)

    def pf(tag, i, j):
        return side if tag == 'side' else rub

    def disp(i, j):
        if full[i][2] == 'tread' and abs(full[i][1]) < w * 0.33:
            return 0.016 if (j // 2) % 2 == 0 else -0.003
        return 0.0
    K.lathe(p, full, segs, M, pf, 'plain', cap_bottom=False, cap_top=False, disp=disp)
    if rim:
        K.cyl_between(p, M @ Vector((0, 0, -w * 0.3)), M @ Vector((0, 0, w * 0.3)), ri * 1.02, hub, 24, bevel=0.01)
        for k in range(5):
            a = k * 2 * math.pi / 5
            q = M @ Vector((math.cos(a) * ri * 0.5, math.sin(a) * ri * 0.5, w * 0.3))
            K.bolt(p, q, M.to_3x3() @ Vector((0, 0, 1)), 0.025, Sf('steel', 0.9), 0.02, segs=8)


def relathe_barrels(ctx):
    st = {}
    for k in range(3):
        me = bpy.data.meshes.get(f'Barrels_{k}_0')
        if me is None:
            continue
        rr = random.Random(1900 + k)
        p = L.Part(); n = 0
        for pts, vc in L.mesh_components(me, weld=0.00005):
            if len(pts) < 150:
                continue
            ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2
            paint = _paint_variant(vc[:, :3].mean(0) / 1.08)
            if ext[2] > 0.85:
                M = Matrix.Translation((c[0], c[1], pts[:, 2].min())) @ Matrix.Rotation(rr.uniform(0, 6.28), 4, 'Z')
            else:
                d = pts[:, :2] - c[:2]; w_, v = np.linalg.eigh(d.T @ d); ax = v[:, 1]
                yaw = math.atan2(ax[1], ax[0])
                M = (Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'Y')
                     @ Matrix.Translation((0, 0, -0.475)))
            barrel32(p, M, 0.36, 0.95, paint, rr); n += 1
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        old = sum(len(q.vertices) - 2 for q in me.polygons); mname = me.name
        mats = [ctx['mats']['Trim_Structures']]
        new = acc.build(me.name + '__v13', materials=mats, sharp_angle=40.0)
        users, _ = L.swap_mesh(me, new, note=f'v13: barrel family variant {k}: 24-segment lathe, rolled chimes & hoops ({n} barrels)')
        for o in users:
            L.set_object_materials(o, mats)
        st[mname] = (old, sum(len(q.vertices) - 2 for q in new.polygons), n)
    return st


def relathe_tyres(ctx):
    st = {}
    for k in range(3):
        me = bpy.data.meshes.get(f'Tires_{k}_0')
        if me is None:
            continue
        rr = random.Random(1950 + k)
        p = L.Part(); n = 0
        for pts, vc in L.mesh_components(me, weld=0.00005):
            if len(pts) < 150:
                continue
            ext = pts.max(0) - pts.min(0); c = (pts.max(0) + pts.min(0)) / 2
            if ext[2] < 0.4:
                R = max(ext[0], ext[1]) / 2; w = ext[2]
                M = Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(rr.uniform(0, 6.28), 4, 'Z')
                tyre40(p, M, R, w, rr, rim=False)
            else:
                R = ext[2] / 2
                d = pts[:, :2] - c[:2]; w_, v = np.linalg.eigh(d.T @ d); ax = v[:, 0]
                yaw = math.atan2(ax[1], ax[0])
                M = Matrix.Translation((c[0], c[1], c[2])) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'Y')
                tyre40(p, M, R, min(ext[0], ext[1]) * 0.9 if min(ext[0], ext[1]) < 0.45 else 0.3, rr, rim=(k == 1))
            n += 1
        acc = L.MeshAccumulator(); acc.add_part(p); p.free()
        old = sum(len(q.vertices) - 2 for q in me.polygons); mname = me.name
        mats = [ctx['mats']['Trim_Structures']]
        new = acc.build(me.name + '__v13', materials=mats, sharp_angle=40.0)
        users, _ = L.swap_mesh(me, new, note=f'v13: tyre family variant {k}: 24-segment lathe, rounded shoulders, tread lugs ({n} tyres)')
        for o in users:
            L.set_object_materials(o, mats)
        st[mname] = (old, sum(len(q.vertices) - 2 for q in new.polygons), n)
    return st


def boulders(ctx):
    from step13_massif import cluster_stacks, boulder_from_group, comp_list, full_arrays, with_mat
    st = {}
    for k in range(2):
        me = bpy.data.meshes.get(f'Boulder_{k}_0')
        if me is None:
            continue
        arr = full_arrays(me)
        comp, comps = comp_list(arr)
        groups = cluster_stacks(comps, 0.5)
        acc = L.MeshAccumulator()
        for i, g in enumerate(groups):
            acc.add(with_mat(boulder_from_group(g, 7000 + 50 * k + i, flat=0.4, lumpy=0.16, strata=0.7, bury=0.18), 0))
        old = sum(len(q.vertices) - 2 for q in me.polygons); mname = me.name
        mats = [ob.material_slots[0].material for ob in bpy.data.objects if ob.type == 'MESH' and ob.data == me][:1] or [ctx['mats']['Rock_Strata']]
        new = acc.build(me.name + '__v13', materials=mats, sharp_angle=80.0, weighted=False)
        users, _ = L.swap_mesh(me, new, note='v13: rounded flat-capped sandstone boulder (soft strata) on the v11 footprint')
        for o in users:
            L.set_object_materials(o, mats)
        st[mname] = (old, sum(len(q.vertices) - 2 for q in new.polygons))
    return st


PROP_MESHES = ['Crates_0_0', 'Crates_1_0', 'Crates_2_0', 'JunkPile_0_0', 'JunkPile_1_0', 'JunkPile_2_0',
               'CarWreck_0_0', 'CarWreck_1_0', 'CarWreck_2_0', 'Chest_0_0', 'Chest_1_0']
PROP_OBJECTS = ['Barricade', 'Funnel', 'BigJump0Course.001', 'Wreck', 'Decor', 'AP_Bridge_Road0', 'AP_Bridge_Track',
                'GuideChevrons']


def role_prop(size, c):
    s = np.sort(size)
    if s[0] < 0.065 and s[2] > 0.4:
        return 'board'
    if s[0] >= 0.3 and s[2] >= 1.5:
        return 'detail'
    return 'prop'


def run(ctx):
    st = {}
    st['barrels'] = relathe_barrels(ctx)
    st['tyres'] = relathe_tyres(ctx)
    st['boulders'] = boulders(ctx)
    for mn in PROP_MESHES:
        me = bpy.data.meshes.get(mn)
        users = [o for o in bpy.data.objects if o.type == 'MESH' and o.data == me] if me else []
        if users:
            st[mn] = RR.rebuild_object_mesh(users[0], role_fn=role_prop, note='v13: rounded prop (shared by all instances)', keep_below=0.008)
    for nm in PROP_OBJECTS:
        ob = bpy.data.objects.get(nm)
        if ob is not None and ob.type == 'MESH':
            kb = 0.025 if nm in ('Decor', 'Barricade') else 0.012
            st[nm] = RR.rebuild_object_mesh(ob, role_fn=role_prop, note='v13: rounded (multi-segment bevels, true cylinders)', keep_below=kb)
    ctx['stats']['props'] = st
    print('STEP13 props', {k: (v if not isinstance(v, dict) or 'old' not in v else (v['old'], v['new'])) for k, v in st.items()}, flush=True)
