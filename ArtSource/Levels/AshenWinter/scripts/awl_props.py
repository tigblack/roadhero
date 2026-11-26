"""Ashen Winter destructible props: the third zone's twelve spawn props (and the hidden stash) in their new looks.

Each zone-2 spawn root keeps its hierarchy (Spawn_<id>_<Model> / Body); only Body's mesh data changes. Variants are
assigned by spawn id, so the look is stable between builds. Footprints and heights follow the gameplay values in
Defs.cs (spec radius / height); the HP bar sits at the spec height.
"""
import math

import bpy
from mathutils import Matrix, Vector

import tw_lib as L
import awl_lib as W
from awl_lib import LAcc, P, V, T, R, rnd, slab, snow_pillow, snow_tint, ring, lathe_at


def burnt_tree(seed):
    """SaltCrystal (r 0.8, h 2.4) -> a small charred tree, broken or with a couple of bare branches."""
    a = LAcc('AW_Prop_BurntTree_%d' % seed)
    W.burnt_tree(a, V(0, 0, 0), seed, height=3.0 + 0.4 * (seed % 3), lean=8.0, broken=seed % 3 == 1, branches=3)
    snow_pillow(a, V(0.1, -0.05, 0.0), (0.75, 0.7, 0.14), seed=seed, surf=P['snow'])
    return a.build()


def concrete_block(seed):
    """Skull (r 1.0, h 2.0) -> a pile of chipped concrete blocks with rebar, snow on top."""
    r = rnd(seed)
    a = LAcc('AW_Prop_ConcreteBlock_%d' % seed)
    slab(a, V(0, 0, 0.42), (1.7, 1.2, 0.84), P['concrete'], M_=R('Z', r.uniform(-15, 15)), seed=seed, chip=0.08)
    slab(a, V(0.15, 0.1, 1.15), (1.2, 0.9, 0.62), P['concrete_lt'], M_=R('Z', r.uniform(-30, 30)) @ R('Y', r.uniform(-8, 8)), seed=seed + 1, chip=0.08)
    if seed % 2 == 0:
        slab(a, V(-0.75, -0.4, 0.3), (0.8, 0.6, 0.6), P['concrete_dk'], M_=R('Z', 35), seed=seed + 2, chip=0.06)
    for k in range(3):
        W.A.rebar(a, V(r.uniform(-0.4, 0.4), r.uniform(-0.3, 0.3), 1.35), V(r.uniform(-0.4, 0.4), r.uniform(-0.4, 0.4), 1), r.uniform(0.35, 0.7),
                  r=0.025, bend=V(r.uniform(-0.2, 0.2), 0.1, 0.05) if k == 0 else None, surf=P['rust_dk'])
    snow_pillow(a, V(0.15, 0.1, 1.46), (0.45, 0.35, 0.07), seed=seed, surf=P['snow'])
    snow_pillow(a, V(0, 0, 0.0), (1.1, 0.8, 0.16), seed=seed + 3, surf=P['snow_dirty'])
    return a.build()


def supply_crates(seed):
    """Crates (r 1.0, h 1.9) -> two or three snowed supply crates (wood and steel)."""
    r = rnd(seed)
    a = LAcc('AW_Prop_Crates_%d' % seed)
    boxes = [(V(-0.35, 0, 0.45), (0.95, 0.9, 0.9), P['plank']), (V(0.5, 0.15, 0.4), (0.8, 0.8, 0.8), P['steel_dk']),
             (V(0.0, 0.05, 1.3), (0.8, 0.75, 0.78), P['plank'] if seed % 2 else P['rust_or'])]
    for k, (c, s, surf) in enumerate(boxes):
        M = T(c) @ R('Z', r.uniform(-12, 12))
        f = a.box(s, M, surf, bevel=0.04)
        a.box((s[0] + 0.04, 0.06, s[2] + 0.04), M @ T(V(0, s[1] / 2, 0)), P['steel_dk'], bevel=0.01)
        a.box((s[0] + 0.04, s[1] + 0.04, 0.08), M @ T(V(0, 0, s[2] * 0.25)), P['steel_dk'], bevel=0.01)
        snow_pillow(a, c + V(0, 0, s[2] / 2), (s[0] * 0.42, s[1] * 0.42, 0.06), seed=seed + k, surf=P['snow'])
    return a.build()


def frozen_tires(seed):
    """Tires (r 0.9, h 1.7) -> a stack of old tyres with snow and a few icicles."""
    r = rnd(seed)
    a = LAcc('AW_Prop_Tires_%d' % seed)
    n = 4 if seed % 2 else 5
    for k in range(n):
        c = V(r.uniform(-0.06, 0.06), r.uniform(-0.06, 0.06), 0.18 + k * 0.32)
        lathe_at(a, [(0.24, -0.15), (0.38, -0.16), (0.45, -0.08), (0.45, 0.08), (0.38, 0.16), (0.24, 0.15), (0.22, 0.0), (0.24, -0.15)],
                 c, V(r.uniform(-0.08, 0.08), r.uniform(-0.08, 0.08), 1), P['tire'], segs=16, caps=(False, False), sharp=None)
    snow_pillow(a, V(0, 0, 0.18 + (n - 1) * 0.32 + 0.14), (0.38, 0.38, 0.06), seed=seed, surf=P['snow'])
    if seed % 2 == 0:
        lathe_at(a, [(0.24, -0.15), (0.38, -0.16), (0.45, -0.08), (0.45, 0.08), (0.38, 0.16), (0.24, 0.15), (0.22, 0.0), (0.24, -0.15)],
                 V(0.7, 0.1, 0.42), V(1, 0.2, 0.15), P['tire'], segs=16, caps=(False, False), sharp=None)
    snow_pillow(a, V(0, 0, 0.0), (0.8, 0.8, 0.14), seed=seed + 1, surf=P['snow_dirty'])
    return a.build()


def frost_rock(seed):
    """SaltRock (r 2.2, h 3.4) -> a big dark split boulder with a snow cap and ice streaks."""
    r = rnd(seed)
    a = LAcc('AW_Prop_FrostRock_%d' % seed)
    surf = P['rock'] if seed % 2 else P['rock_dk']
    slab(a, V(0, 0, 1.45), (3.6, 3.0, 2.9), surf, M_=R('Z', r.uniform(0, 360)) @ R('X', r.uniform(-6, 6)), seed=seed, chip=0.35, e=0.45)
    slab(a, V(1.2, -0.6, 0.7), (1.6, 1.4, 1.4), P['rock_dk'], M_=R('Z', r.uniform(0, 360)), seed=seed + 1, chip=0.2, e=0.4)
    snow_pillow(a, V(0.0, 0.1, 2.85), (1.25, 1.05, 0.22), seed=seed, surf=P['snow'])
    snow_pillow(a, V(1.25, -0.6, 1.4), (0.55, 0.45, 0.1), seed=seed + 2, surf=P['snow'])
    for k in range(4):
        ang = r.uniform(0, 6.28)
        p = V(math.cos(ang) * 1.5, math.sin(ang) * 1.3, r.uniform(1.6, 2.4))
        W.horn(a, p, p + V(0, 0, -r.uniform(0.3, 0.7)), 0.06, P['ice'], segs=5, n=3)
    snow_pillow(a, V(0, 0, 0.0), (2.0, 1.8, 0.2), seed=seed + 3, surf=P['snow_dirty'])
    return a.build()


def fallen_pylon(seed):
    """RibCage (r 2.4, h 3.2) -> a toppled section of a lattice pylon lying across the snow, its wires tangled."""
    a = LAcc('AW_Prop_FallenPylon_%d' % seed)
    yaw = 30.0 if seed % 2 else -20.0
    M = R('Z', yaw) @ R('Y', 72) @ T(V(0, 0, -2.4))
    tmp = LAcc('tmp')
    W.lattice_pylon(a, V(0, 0, 0), height=6.0, width=1.6, seed=seed, top_width=0.7, arms=False)
    a.transform(list(a.bm.faces), M)
    a.bm.normal_update()
    W.broken_wire(a, V(1.2, 0.4, 1.6), 2.2, seed)
    W.wire(a, V(-2.0, -0.5, 0.9), V(1.8, 0.8, 1.3), 0.7)
    slab(a, V(-1.6, -0.2, 0.3), (1.2, 1.2, 0.6), P['concrete_dk'], seed=seed, chip=0.06)
    snow_pillow(a, V(0, 0, 0.0), (2.2, 1.4, 0.18), R('Z', yaw), seed=seed, surf=P['snow'])
    tmp.bm.free()
    return a.build()


def power_pylon(seed):
    """Turbine (r 1.6, h 9) -> a lattice power pylon (9 m) with cross arms, insulators and snapped hanging wires."""
    a = LAcc('AW_Prop_PowerPylon_%d' % seed)
    W.lattice_pylon(a, V(0, 0, 0), height=8.6, width=2.4, seed=seed, top_width=0.8, arms=True)
    for k, p in enumerate(W.arm_points(V(0, 0, 0), 8.6, 2.4, 0.8)):
        if (k + seed) % 2 == 0:
            W.broken_wire(a, p, 3.5 + k * 0.6, seed + k)
    slab(a, V(0, 0, 0.2), (2.9, 2.9, 0.4), P['concrete_dk'], seed=seed, chip=0.05)
    snow_pillow(a, V(0, 0, 0.4), (1.3, 1.3, 0.1), seed=seed, surf=P['snow'])
    return a.build()


def snowed_wreck(seed):
    """CarWreck (r 2.3, h 2.4) -> a burnt-out car sunk in snow."""
    a = LAcc('AW_Prop_SnowedWreck_%d' % seed)
    W.car_wreck(a, V(0, 0, -0.1), 15.0 * (seed % 3 - 1), seed, 'car')
    return a.build()


def fuel_drums(seed):
    """Barrels (r 0.9, h 1.8) -> rusty fuel drums, one on its side, snow caps."""
    r = rnd(seed)
    a = LAcc('AW_Prop_FuelDrums_%d' % seed)
    spots = [V(-0.32, 0.15, 0), V(0.34, 0.2, 0), V(0.0, -0.38, 0)]
    for k, c in enumerate(spots[:2 + seed % 2]):
        surf = P['rust'] if (k + seed) % 2 else P['steel_dk']
        lathe_at(a, [(0.0, 0.0), (0.29, 0.0), (0.3, 0.04), (0.29, 0.30), (0.305, 0.32), (0.29, 0.34), (0.29, 0.86), (0.3, 0.9),
                     (0.0, 0.9)], c, V(0, 0, 1), surf, segs=14, sharp=45)
        snow_pillow(a, c + V(0, 0, 0.9), (0.24, 0.24, 0.05), seed=seed + k, surf=P['snow'])
        if k == 0:
            a.box((0.5, 0.06, 0.14), T(c + V(0, -0.29, 0.55)), P['hazard'], bevel=0.005)
    lathe_at(a, [(0.0, 0.0), (0.29, 0.0), (0.3, 0.04), (0.29, 0.86), (0.3, 0.9), (0.0, 0.9)], V(0.65, -0.35, 0.3), V(1, 0.3, 0),
             P['rust'], segs=14, sharp=45)
    snow_pillow(a, V(0, 0, 0), (1.0, 0.9, 0.14), seed=seed + 5, surf=P['snow_dirty'])
    return a.build()


def scrap_hut(seed):
    """Shack (r 2.3, h 3.6) -> a corrugated scrap hut with a snow-loaded roof, a stovepipe and an amber window."""
    r = rnd(seed)
    a = LAcc('AW_Prop_ScrapHut_%d' % seed)
    a.box((3.2, 2.6, 2.4), T(V(0, 0, 1.2)), P['corrugated'] if seed % 2 else P['panel'], bevel=0.04)
    a.box((3.5, 3.0, 0.16), T(V(0, 0, 2.5)) @ R('X', 6), P['rust_dk'], bevel=0.03)
    snow_pillow(a, V(0, 0, 2.6), (1.6, 1.35, 0.3), R('X', 6), seed=seed, surf=P['snow'])
    a.box((0.9, 0.08, 1.8), T(V(-0.7, -1.32, 0.9)), P['plank'], bevel=0.02)
    a.box((0.7, 0.06, 0.5), T(V(0.7, -1.32, 1.5)), P['lamp_soft'], bevel=0.01)
    a.box((0.8, 0.1, 0.08), T(V(0.7, -1.34, 1.78)), P['steel_dk'], bevel=0.01)
    a.cyl_between(V(1.1, 0.6, 2.4), V(1.1, 0.6, 3.5), 0.12, P['steel_dk'], 10)
    W.ring(a, V(1.1, 0.6, 3.45), V(0, 0, 1), 0.16, 0.08, 0.05, P['rust_dk'], segs=10)
    a.box((1.2, 0.8, 0.6), T(V(-1.9, 0.7, 0.3)), P['plank'], bevel=0.03)
    snow_pillow(a, V(-1.9, 0.7, 0.6), (0.5, 0.35, 0.06), seed=seed + 1, surf=P['snow'])
    snow_pillow(a, V(0, 0, 0), (2.0, 1.7, 0.18), seed=seed + 2, surf=P['snow_dirty'])
    return a.build()


def frost_tent(seed):
    """Tent (r 1.5, h 2.6) -> a canvas ridge tent under snow, poles and a guy line."""
    a = LAcc('AW_Prop_FrostTent_%d' % seed)
    pts_b = [V(-1.2, -1.2, 0), V(1.2, -1.2, 0), V(1.2, 1.2, 0), V(-1.2, 1.2, 0)]
    a.poly([V(-1.25, -1.3, 0.05), V(1.25, -1.3, 0.05), V(0, -1.3, 2.2), V(-1.25, 1.3, 0.05), V(1.25, 1.3, 0.05), V(0, 1.3, 2.2)],
           [(0, 1, 2), (5, 4, 3), (0, 2, 5, 3), (1, 4, 5, 2)], P['tarp'], sharp=30)
    a.poly([V(-1.24, -1.31, 0.05), V(0, -1.31, 2.18), V(1.24, -1.31, 0.05)], [(0, 1, 2)], P['tarp'].k(0.75), sharp=30)
    snow_pillow(a, V(0, 0, 2.15), (0.55, 1.35, 0.18), seed=seed, surf=P['snow'])
    for s in (-1, 1):
        a.cyl_between(V(0, s * 1.35, 0), V(0, s * 1.35, 2.4), 0.04, P['steel_dk'], 6)
    a.cyl_between(V(0, -1.35, 2.3), V(0.2, -2.3, 0), 0.01, P['cable'], 4)
    snow_pillow(a, V(0, 0, 0), (1.6, 1.7, 0.14), seed=seed + 1, surf=P['snow_dirty'])
    return a.build()


def watch_post(seed):
    """Tower (r 1.5, h 6) -> a steel-and-timber watch post with a snowy roof and an amber lamp."""
    a = LAcc('AW_Prop_WatchPost_%d' % seed)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.cyl_between(V(sx * 1.0, sy * 1.0, 0), V(sx * 0.8, sy * 0.8, 4.2), 0.09, P['rust_or'], 6)
    for z in (1.4, 2.8):
        for k in range(4):
            a0 = [V(-1, -1, 0), V(1, -1, 0), V(1, 1, 0), V(-1, 1, 0)][k]
            a1 = [V(-1, -1, 0), V(1, -1, 0), V(1, 1, 0), V(-1, 1, 0)][(k + 1) % 4]
            sc = 1.0 - 0.2 * z / 4.2
            a.cyl_between(a0 * sc + V(0, 0, z), a1 * sc + V(0, 0, z + 1.2), 0.04, P['rust_or'], 4)
    a.box((2.1, 2.1, 0.14), T(V(0, 0, 4.25)), P['plank'], bevel=0.02)
    for k in range(4):
        d = [V(0, -1, 0), V(1, 0, 0), V(0, 1, 0), V(-1, 0, 0)][k]
        a.box((2.0 if k % 2 == 0 else 0.08, 0.08 if k % 2 == 0 else 2.0, 0.9), T(d * 1.0 + V(0, 0, 4.75)), P['plank'], bevel=0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a.cyl_between(V(sx * 0.95, sy * 0.95, 4.3), V(sx * 0.95, sy * 0.95, 5.6), 0.05, P['steel_dk'], 5)
    a.box((2.5, 2.5, 0.12), T(V(0, 0, 5.65)) @ R('X', 5), P['rust_dk'], bevel=0.02)
    snow_pillow(a, V(0, 0, 5.72), (1.2, 1.2, 0.22), R('X', 5), seed=seed, surf=P['snow'])
    W.lamp_post(a, V(0.8, -0.8, 4.3), height=0.4, seed=seed)
    snow_pillow(a, V(0, 0, 0), (1.5, 1.5, 0.14), seed=seed + 1, surf=P['snow_dirty'])
    return a.build()


def stash_box(seed):
    """Chest -> an orange strongbox half in the snow, a rag flag on a pole."""
    a = LAcc('AW_Prop_Stash_%d' % seed)
    M = T(V(0, 0, 0.1)) @ R('Y', 8) @ R('X', -6)
    a.box((1.1, 0.7, 0.6), M @ T(V(0, 0, 0.22)), W.S('#D07A2E', 0.40, 0.10, strip='metal'), bevel=0.07)
    a.box((1.14, 0.74, 0.12), M @ T(V(0, 0, 0.5)), W.S('#B4612A', 0.40, 0.10, strip='metal'), bevel=0.04)
    for x in (-0.35, 0.35):
        a.box((0.1, 0.06, 0.18), M @ T(V(x, -0.37, 0.4)), P['steel'], bevel=0.015)
    a.cyl_between(V(0.6, 0.35, 0.0), V(0.6, 0.35, 1.4), 0.025, P['steel_dk'], 6)
    a.poly([V(0.62, 0.35, 1.35), V(0.62, 0.35, 1.05), V(1.05, 0.38, 1.12), V(1.0, 0.36, 1.3)], [(0, 1, 2, 3), (3, 2, 1, 0)],
           W.S('#C2622C', 0.1, strip='cloth'), sharp=30)
    snow_pillow(a, V(0, 0, 0.62), (0.4, 0.25, 0.05), seed=seed, surf=P['snow'])
    snow_pillow(a, V(0, 0, 0.0), (0.95, 0.75, 0.2), seed=seed + 1, surf=P['snow'])
    return a.build()


BUILDERS = {
    'SaltCrystal': (burnt_tree, 3), 'Skull': (concrete_block, 3), 'Crates': (supply_crates, 2), 'Tires': (frozen_tires, 2),
    'SaltRock': (frost_rock, 3), 'RibCage': (fallen_pylon, 2), 'Turbine': (power_pylon, 2), 'CarWreck': (snowed_wreck, 3),
    'Barrels': (fuel_drums, 3), 'Shack': (scrap_hut, 3), 'Tent': (frost_tent, 2), 'Tower': (watch_post, 2),
    'Chest': (stash_box, 1),
}


def build_all():
    """Swap the Body meshes of every zone-2 prop spawn; returns {model: (variants, instances, tris per variant)}."""
    report = {}
    for model, (fn, nvar) in BUILDERS.items():
        meshes = [fn(200 + i) for i in range(nvar)]
        roots = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('Spawn_2') and o.name.endswith('_' + model)]
        n = 0
        for root in roots:
            sid = int(root.name.split('_')[1])
            for c in root.children:
                if c.type == 'MESH' and c.name.split('.')[0] == 'Body':
                    L.swap_mesh(c, meshes[sid % nvar], 'Ashen Winter prop')
                    n += 1
        report[model] = {'variants': nvar, 'instances': n, 'tris': [L.tri_count(m) for m in meshes]}
        print('AWL_PROP', model, report[model], flush=True)
    return report
