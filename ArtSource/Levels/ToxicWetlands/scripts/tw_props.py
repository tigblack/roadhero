"""Toxic Wetlands destructible props: swamp versions of the second zone's spawn props (same footprints / heights).

Each zone-1 spawn root keeps its hierarchy (Spawn_<id>_<Model> / Body); only Body's mesh data changes. Variants are
assigned by spawn id, so the look is stable between builds. Sizes match the gameplay values in Defs.cs: collider
radius ~0.85 x spec radius (rocks are measured from the mesh), HP bar at the spec height.
"""
import math

import bpy
from mathutils import Matrix, Vector

import tw_lib as L
import tw_env as EV
from tw_env import E, R, S, SC, T, V, curve, rnd
from tw_lib import Acc


def reed_bush(seed):
    """DryBush -> reed clump with cattails and a dead twiggy shrub (r 0.8, h ~2)."""
    r = rnd(seed)
    a = Acc('TW_Prop_ReedBush_%d' % seed)
    dry = (0.25, 0.55, 0.1)[seed % 3]
    nbl = 46
    for i in range(nbl):
        ang = r.uniform(0, 6.28); d = r.uniform(0, 0.75) ** 0.8
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.05)
        hgt = r.uniform(1.0, 1.85)
        bend = V(math.cos(ang), math.sin(ang), 0) * hgt * r.uniform(0.1, 0.35)
        col = E['reed_dk'].mix(E['reed'], r.uniform(0.2, 1.0))
        if r.random() < dry:
            col = col.mix(E['reed_tip'], 0.65)
        a.tube([base, base + bend * 0.15 + V(0, 0, hgt * 0.42), base + bend * 0.6 + V(0, 0, hgt * 0.8), base + bend + V(0, 0, hgt)],
               [0.04, 0.034, 0.02, 0.0], col, segs=4, flat=0.32, caps=False)
    for i in range(6):
        ang = r.uniform(0, 6.28); d = r.uniform(0, 0.55)
        base = V(math.cos(ang) * d, math.sin(ang) * d, -0.05)
        top = base + V(r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), r.uniform(1.8, 2.15))
        a.tube([base, (base + top) / 2, top], 0.016, E['stalk'], segs=4)
        a.cyl(0.05, 0.26, T(top - V(0, 0, 0.32)), E['cattail'], segs=8, bevel=0.02)
    for i in range(3):
        ang = r.uniform(0, 6.28)
        b0 = V(math.cos(ang) * 0.2, math.sin(ang) * 0.2, 0.0)
        b1 = b0 + V(math.cos(ang) * 0.5, math.sin(ang) * 0.5, r.uniform(0.9, 1.3))
        a.tube(curve(b0, b0 + V(0, 0, 0.6), b1, 4), [0.05, 0.04, 0.03, 0.02, 0.0], E['dead_dk'], segs=5)
    if seed % 3 == 2:
        for i in range(3):
            ang = r.uniform(0, 6.28)
            c = V(math.cos(ang) * 0.75, math.sin(ang) * 0.75, 0)
            a.cyl(0.025, 0.2, T(c), E['gill'], segs=6)
            a.lathe([(0.0, 0.3), (0.09, 0.26), (0.11, 0.2), (0.0, 0.21)], 10, T(c), E['glowcap'], sharp=None)
    a.sphere((0.95, 0.9, 0.18), T(V(0, 0, -0.04)), E['mud'], 12, 5)
    a.sphere((0.7, 0.7, 0.14), T(V(0.1, -0.05, 0.02)), E['moss'], 12, 5)
    return a.build()


def bog_rock(seed):
    """RedRock -> mossy slate boulder (about 2.2 m wide, 1.9 m tall)."""
    r = rnd(seed)
    a = Acc('TW_Prop_BogRock_%d' % seed)
    hx, hy, hz = 1.15 * r.uniform(0.92, 1.08), 1.0 * r.uniform(0.9, 1.05), 0.98

    def deform(co):
        n = L.smooth_noise3(co, seed, 0.9)
        n2 = L.smooth_noise3(co, seed + 7, 2.3)
        k = 1.0 + 0.13 * n + 0.04 * n2
        z = co.z * k
        if z > 0.45 * hz:          # a slightly flattened, broad top
            z = 0.45 * hz + (z - 0.45 * hz) * 0.75
        return Vector((co.x * k, co.y * k, max(z, -0.2)))
    faces = a.superellipsoid((hx, hy, hz), (0.5, 0.62), T(V(0, 0, hz * 0.92)), E['stone'], 22, 13, deform=deform)
    for f in faces:
        nz = f.normal.z
        for l in f.loops:
            if nz > 0.5:
                l[a.main.lc] = E['moss_flat'].rgba
            elif l.vert.co.z < 0.35:
                l[a.main.lc] = E['stone_dk'].rgba
    # second smaller stone and a moss tuft
    a.superellipsoid((0.5, 0.42, 0.36), (0.55, 0.6), T(V(hx * 0.95, -hy * 0.35, 0.22)) @ R('Z', 30), E['stone_dk'], 14, 8)
    if seed % 2:
        for i in range(4):
            ang = r.uniform(0, 6.28)
            p = V(math.cos(ang) * 0.4, math.sin(ang) * 0.4, hz * 1.75)
            a.tube([p, p + V(0, 0, r.uniform(0.25, 0.4))], [0.03, 0.0], E['reed'], segs=4, flat=0.35)
    return a.build()


def pipe_stack(seed):
    """Pipes -> rusty pipe stack on sleepers, algae and a leaking end (r 1.2, h ~1.5)."""
    r = rnd(seed)
    a = Acc('TW_Prop_PipeStack_%d' % seed)
    for y in (-0.8, 0.8):
        a.box((2.1, 0.22, 0.16), T(V(0, y, 0.06)), E['plank_dk'], bevel=0.03)
    rr = 0.21
    rows = [(-2 * rr - 0.02, 0), (0, 0), (2 * rr + 0.02, 0), (-rr - 0.01, 1), (rr + 0.01, 1), (0, 2)]
    for k, (x, row) in enumerate(rows):
        z = 0.14 + rr + row * rr * 1.75
        L_ = r.uniform(2.1, 2.5)
        off = r.uniform(-0.2, 0.2)
        c0, c1 = V(x, -L_ / 2 + off, z), V(x, L_ / 2 + off, z)
        a.cyl_between(c0, c1, rr, E['rust'] if k % 3 else E['galv'], segs=14)
        for c in (c0, c1):
            a.cyl(rr * 0.8, 0.02, T(c) @ (Vector((0, 1 if c is c1 else -1, 0)).to_track_quat('Z', 'Y').to_matrix().to_4x4()), E['black'], segs=12)
    for i in range(3):
        p = V(r.uniform(-0.4, 0.4), r.uniform(-0.8, 0.8), 0.14 + rr * 2 + rr * 1.75 * 2)
        a.tube([p, p + V(r.uniform(-0.1, 0.1), 0, -0.4), p + V(0, 0.05, -0.75)], [0.03, 0.022, 0.0], E['algae_dk'], segs=4, flat=0.6)
    end = V(0, 1.2 + r.uniform(-0.1, 0.1), 0.14 + rr)
    a.tube([end, end + V(0, 0.15, -0.12), end + V(0, 0.3, -0.33)], [0.1, 0.08, 0.06], E['toxic'], segs=6)
    a.cyl(0.6, 0.012, T(V(0, 1.6, 0.0)) @ SC(1.0, 0.75, 1.0), E['toxic_goo'], segs=14)
    a.sphere((1.35, 1.2, 0.09), T(V(0, 0, -0.03)), E['mud'], 12, 4)
    return a.build()


def chem_drums(seed):
    """Barrels -> three chemical drums, one tipped and leaking (r 0.9, h ~1)."""
    r = rnd(seed)
    a = Acc('TW_Prop_ChemDrums_%d' % seed)
    variants = [('yel', 'olive', 'blue'), ('olive', 'yel', 'rust'), ('blue', 'yel', 'olive')][seed % 3]
    prof = [(0.0, 0.0), (0.27, 0.0), (0.295, 0.02), (0.3, 0.06), (0.3, 0.19), (0.315, 0.21), (0.3, 0.23), (0.3, 0.33),
            (0.302, 0.35), (0.302, 0.53), (0.3, 0.55), (0.3, 0.65), (0.315, 0.67), (0.3, 0.69), (0.3, 0.82), (0.295, 0.86),
            (0.27, 0.88), (0.0, 0.88)]

    def drum_at(M, var):
        body = {'yel': E['drum_yel'], 'olive': E['drum_olive'], 'blue': E['drum_blue'], 'rust': E['rust']}[var]
        bands = [(E['label'] if var == 'yel' else E['hazard']) if 8 <= i <= 9 and var != 'rust' else body for i in range(len(prof) - 1)]
        a.lathe(prof, 18, M, surf_fn=lambda i: bands[i], sharp=60)
        a.cyl(0.04, 0.025, M @ T(V(0.13, 0.0, 0.88)), E['steel_dk'], segs=8)
    drum_at(T(V(-0.32, 0.2, 0)) @ R('Z', r.uniform(0, 90)), variants[0])
    drum_at(T(V(0.34, 0.28, 0)) @ R('Z', r.uniform(0, 90)) @ R('X', 4), variants[1])
    M = T(V(0.05, -0.55, 0.3)) @ R('Z', r.uniform(-30, 30)) @ R('Y', 90) @ T(V(0, 0, -0.44))
    drum_at(M, variants[2])
    lip = T(V(0.05, -0.55, 0.3)) @ R('Z', 0) @ V(0.44, 0, 0)
    a.tube([V(0.5, -0.55, 0.22), V(0.68, -0.6, 0.08), V(0.85, -0.62, 0.02)], [0.07, 0.05, 0.03], E['toxic'], segs=6)
    a.cyl(0.7, 0.012, T(V(1.0, -0.55, 0.0)) @ SC(1.0, 0.7, 1.0), E['toxic_goo'], segs=16)
    a.sphere((1.1, 1.0, 0.07), T(V(0, 0, -0.03)), E['mud'], 12, 4)
    return a.build()


def junk_heap(seed):
    """JunkPile -> mud heap with tyres, corrugated sheets, a drum, a crate, a pipe and moss (r 1.4, h ~1.9)."""
    r = rnd(seed)
    a = Acc('TW_Prop_JunkHeap_%d' % seed)

    def deform(co):
        return Vector((co.x, co.y, co.z * (1.0 + 0.15 * L.smooth_noise3(co, seed, 1.5))))
    a.superellipsoid((1.45, 1.25, 0.75), (0.7, 0.75), T(V(0, 0, 0.05)), E['mud'], 18, 9, deform=deform)
    a.sphere((0.9, 0.8, 0.2), T(V(-0.3, 0.2, 0.68)), E['moss'], 12, 5)
    for i in range(3):
        c = V(r.uniform(-0.7, 0.7), r.uniform(-0.6, 0.6), 0.5 + i * 0.12)
        a.lathe([(0.2, -0.11), (0.36, -0.11), (0.4, -0.06), (0.4, 0.06), (0.36, 0.11), (0.2, 0.11), (0.2, -0.11)], 14,
                T(c) @ R('X', r.uniform(30, 80)) @ R('Z', r.uniform(0, 180)), E['tire'], cap_bottom=False, cap_top=False)
    for i in range(2):
        a.box((1.4, 0.9, 0.04), T(V(r.uniform(-0.4, 0.4), r.uniform(-0.4, 0.4), 0.7 + i * 0.2)) @ R('X', r.uniform(-30, 30)) @ R('Y', r.uniform(-25, 25)) @ R('Z', r.uniform(0, 180)),
              E['corr_rust'], bevel=0.015, segs=1)
    a.box((0.6, 0.6, 0.55), T(V(0.7, -0.5, 0.45)) @ R('Z', 20) @ R('X', 12), E['plank'], bevel=0.05)
    a.cyl_between(V(-0.9, 0.5, 0.3), V(-0.2, 0.9, 1.7), 0.12, E['rust'], segs=10)
    a.lathe([(0.0, 0.0), (0.27, 0.0), (0.3, 0.05), (0.3, 0.83), (0.27, 0.88), (0.0, 0.88)], 14,
            T(V(0.2, 0.6, 0.55)) @ R('X', 70) @ R('Z', 30), E['drum_yel'], sharp=60)
    return a.build()


def toxic_tank(seed):
    """OilTank -> horizontal chemical tank on concrete saddles, hazard band, leaking valve (r 2.0, h ~3.2)."""
    r = rnd(seed)
    a = Acc('TW_Prop_ToxicTank_%d' % seed)
    body = (E['tank'], E['tank_green'], E['drum_yel'])[seed % 3]
    L_, rad = 3.6, 1.1
    M = T(V(0, 0, 1.45)) @ R('X', 90) @ T(V(0, 0, -L_ / 2))
    prof = [(0.0, -0.22), (rad * 0.55, -0.15), (rad * 0.92, -0.04), (rad, 0.06), (rad, L_ - 0.06), (rad * 0.92, L_ + 0.04),
            (rad * 0.55, L_ + 0.15), (0.0, L_ + 0.22)]
    a.lathe(prof, 26, M, body, sharp=None)
    a.lathe([(rad + 0.012, L_ * 0.42), (rad + 0.012, L_ * 0.58)], 26, M, E['hazard'], cap_bottom=False, cap_top=False)
    a.lathe([(rad + 0.01, L_ * 0.15), (rad + 0.01, L_ * 0.3)], 26, M, E['drips'], cap_bottom=False, cap_top=False)
    for y in (-1.1, 1.1):
        a.box((2.1, 0.45, 0.65), T(V(0, y, 0.3)), E['concrete'], bevel=0.08)
        a.box((2.2, 0.3, 0.14), T(V(0, y, 0.68)), E['steel_dk'], bevel=0.03)
    a.cyl(0.18, 0.4, T(V(0, 0.4, 1.45 + rad - 0.05)), E['steel_dk'], segs=10, bevel=0.03)
    a.cyl(0.28, 0.06, T(V(0, 0.4, 1.45 + rad + 0.35)), E['steel_dk'], segs=12, bevel=0.02)
    # valve + leak
    a.cyl_between(V(rad - 0.1, -0.9, 0.9), V(rad + 0.45, -0.9, 0.9), 0.1, E['rust'], segs=10)
    a.lathe([(0.14, -0.015), (0.17, -0.02), (0.18, 0.0), (0.17, 0.02), (0.14, 0.015), (0.14, -0.015)], 14,
            T(V(rad + 0.3, -0.9, 1.15)), E['red'], cap_bottom=False, cap_top=False)
    a.cyl_between(V(rad + 0.3, -0.9, 0.95), V(rad + 0.3, -0.9, 1.15), 0.025, E['steel_dk'], segs=6)
    a.tube([V(rad + 0.45, -0.9, 0.85), V(rad + 0.6, -0.9, 0.5), V(rad + 0.65, -0.9, 0.03)], [0.07, 0.05, 0.04], E['toxic'], segs=6)
    a.cyl(0.95, 0.014, T(V(rad + 0.8, -0.8, 0.0)) @ SC(1.0, 0.8, 1.0), E['toxic_goo'], segs=16)
    # ladder
    for s in (-0.18, 0.18):
        a.cyl_between(V(-rad - 0.12, s, 0.0), V(-rad - 0.05, s, 2.4), 0.025, E['steel'], segs=6)
    for k in range(6):
        z = 0.3 + k * 0.38
        a.cyl_between(V(-rad - 0.11 + z * 0.03, -0.18, z), V(-rad - 0.11 + z * 0.03, 0.18, z), 0.018, E['steel'], segs=5)
    return a.build()


def sludge_pump(seed):
    """OilPump -> rusty swamp pumpjack: samson post, walking beam, horse head, crank and weights, sludge hose (h ~4.4)."""
    r = rnd(seed)
    a = Acc('TW_Prop_SludgePump_%d' % seed)
    a.box((1.4, 4.4, 0.3), T(V(0, 0, 0.12)), E['concrete'], bevel=0.08)
    # samson post (A-frame)
    for s in (-1, 1):
        a.cyl_between(V(s * 0.55, -0.6, 0.25), V(s * 0.12, 0.0, 3.1), 0.09, E['steel_dk'], segs=8)
        a.cyl_between(V(s * 0.55, 0.6, 0.25), V(s * 0.12, 0.0, 3.1), 0.09, E['steel_dk'], segs=8)
    a.cyl(0.14, 0.4, T(V(-0.2, 0, 3.15)) @ R('Y', 90), E['steel'], segs=10)
    # walking beam (rusty orange) with a hazard stripe and the horse head
    beam = E['red'].mix(E['rust_pl'], 0.4)
    a.box((0.3, 3.8, 0.38), T(V(0, 0.05, 3.32)) @ R('X', -6), beam, bevel=0.06)
    a.box((0.32, 1.0, 0.4), T(V(0, -0.6, 3.36)) @ R('X', -6), E['hazard'], bevel=0.06)
    head = [V(0, 1.95, 3.6), V(0, 2.35, 3.2), V(0, 2.4, 2.6), V(0, 2.2, 2.25)]
    a.tube(head, [0.32, 0.36, 0.3, 0.22], beam, segs=10, flat=0.5)
    a.cyl_between(V(0, 2.28, 2.3), V(0, 2.28, 0.5), 0.025, E['steel'], segs=5)
    # wellhead with a sludge hose into a puddle
    a.cyl(0.18, 0.5, T(V(0, 2.3, 0.25)), E['rust'], segs=10, bevel=0.03)
    a.tube([V(0.15, 2.3, 0.55), V(0.8, 2.6, 0.5), V(1.4, 2.3, 0.1), V(1.9, 1.8, 0.05)], 0.09, E['rubber'] if 'rubber' in E else E['black'], segs=8)
    a.cyl(1.0, 0.015, T(V(2.1, 1.5, 0.0)) @ SC(1.0, 0.85, 1.0), E['toxic_goo'], segs=16)
    # crank and counterweights behind
    a.box((1.0, 0.8, 0.7), T(V(0, -1.6, 0.6)), E['tank_green'], bevel=0.1)
    for s in (-1, 1):
        a.cyl(0.75, 0.16, T(V(s * 0.62, -1.75, 1.1)) @ R('Y', 90) @ T(V(0, 0, -0.08)), E['steel_dk'], segs=18, bevel=0.03)
        a.cyl_between(V(s * 0.62, -1.75, 1.1), V(s * 0.25, -1.75, 3.05), 0.06, E['steel'], segs=6)
    return a.build()


def sunk_wreck(seed):
    """CarWreck -> mossy car half sunk in mud, a loose tyre, algae (r 2.3, h ~1.8)."""
    r = rnd(seed)
    a = Acc('TW_Prop_SunkWreck_%d' % seed)
    body = (E['rust'], E['drum_blue'].mix(E['rust_pl'], 0.5), E['tank_green'].mix(E['rust_pl'], 0.4))[seed % 3]
    M = T(V(0, 0, -0.18)) @ R('X', r.uniform(-7, -3)) @ R('Y', r.uniform(5, 11))
    a.box((2.0, 4.3, 0.75), M @ T(V(0, 0, 0.42)), body, bevel=0.28)
    a.box((1.7, 2.1, 0.62), M @ T(V(0, -0.35, 1.08)), body, bevel=0.24)
    for y, ang in ((0.72, -32), (-1.42, 30)):
        a.box((1.55, 0.05, 0.42), M @ T(V(0, y, 1.08)) @ R('X', ang), E['glass'], bevel=0.02)
    a.box((1.62, 0.25, 0.25), M @ T(V(0, 2.16, 0.45)), E['steel_dk'], bevel=0.06)
    a.sphere((0.8, 1.0, 0.1), M @ T(V(0, -0.35, 1.38)), E['moss'], 14, 5)
    a.sphere((0.9, 0.7, 0.09), M @ T(V(0.1, 1.4, 0.82)), E['moss'], 12, 4)
    for x in (-1.0, 1.0):
        a.lathe([(0.2, -0.13), (0.38, -0.13), (0.42, -0.07), (0.42, 0.07), (0.38, 0.13), (0.2, 0.13), (0.2, -0.13)], 14,
                M @ T(V(x * 0.98, 1.35, 0.25)) @ R('Y', 90), E['tire'], cap_bottom=False, cap_top=False)
    a.lathe([(0.2, -0.12), (0.36, -0.12), (0.4, -0.06), (0.4, 0.06), (0.36, 0.12), (0.2, 0.12), (0.2, -0.12)], 14,
            T(V(1.8, -1.6, 0.12)) @ R('X', 85), E['tire'], cap_bottom=False, cap_top=False)
    for i in range(4):
        p = M @ V(r.uniform(-0.9, 0.9), r.uniform(-1.5, 1.5), 0.85)
        a.tube([p, p + V(0.03, 0, -0.3), p + V(0, 0, -0.55)], [0.035, 0.025, 0.0], E['algae_dk'], segs=4, flat=0.6)
    a.sphere((2.4, 2.9, 0.16), T(V(0, 0, -0.08)), E['mud'], 14, 4)
    return a.build()


def stilt_shack(seed):
    """Shack -> hut on stilts: plank floor, corrugated walls, rusty sloped roof with a tarp patch, lantern (h ~3.6)."""
    r = rnd(seed)
    a = Acc('TW_Prop_StiltShack_%d' % seed)
    W, D, F = 3.0, 2.6, 0.55
    for x in (-W / 2 + 0.15, W / 2 - 0.15):
        for y in (-D / 2 + 0.15, D / 2 - 0.15):
            a.cyl(0.1, F + 0.4, T(V(x, y, -0.3)), E['post'], segs=7, bevel=0.02)
    a.box((W + 0.3, D + 0.3, 0.14), T(V(0, 0, F)), E['plank_dk'], bevel=0.03)
    wall = (E['corr'], E['corr_rust'], E['plank_gr'])[seed % 3]
    H = 2.1
    a.box((W, 0.1, H), T(V(0, -D / 2, F + H / 2)), wall, bevel=0.02)
    a.box((W, 0.1, H), T(V(0, D / 2, F + H / 2)), wall, bevel=0.02)
    a.box((0.1, D, H), T(V(-W / 2, 0, F + H / 2)), wall, bevel=0.02)
    a.box((0.1, D, H), T(V(W / 2, 0, F + H / 2)), wall, bevel=0.02)
    a.box((0.9, 0.06, 1.6), T(V(0.5, -D / 2 - 0.05, F + 0.85)), E['plank'], bevel=0.02)
    a.box((0.6, 0.06, 0.45), T(V(-0.7, -D / 2 - 0.05, F + 1.35)), E['black'], bevel=0.02)
    # roof: slanted rusty sheet with a tarp patch
    a.box((W + 0.6, D + 0.7, 0.08), T(V(0, 0, F + H + 0.35)) @ R('X', -12), E['corr_rust'], bevel=0.02)
    a.box((1.4, 1.2, 0.04), T(V(-0.6, 0.3, F + H + 0.42)) @ R('X', -12) @ R('Z', 8), E['tarp'], bevel=0.01)
    # steps, lantern, barrel
    for k in range(3):
        a.box((0.8, 0.3, 0.08), T(V(0.5, -D / 2 - 0.35 - k * 0.28, F - 0.15 - k * 0.18)), E['plank'], bevel=0.015)
    a.cyl(0.06, 0.16, T(V(-1.0, -D / 2 - 0.12, F + 1.9)), E['lamp'], segs=8, bevel=0.02)
    a.lathe([(0.0, 0.0), (0.27, 0.0), (0.3, 0.05), (0.3, 0.83), (0.27, 0.88), (0.0, 0.88)], 14, T(V(W / 2 + 0.35, 0.6, 0.0)), E['drum_olive'], sharp=60)
    a.sphere((2.0, 1.8, 0.12), T(V(0, 0, -0.06)), E['mud'], 14, 4)
    return a.build()


def tarp_tent(seed):
    """Tent -> olive tarp lean-to on poles with a crate and a jerrycan (h ~2.4)."""
    r = rnd(seed)
    a = Acc('TW_Prop_TarpTent_%d' % seed)
    tarp = (E['tarp'], E['tarp_or'], S('#5E6E7A', 0.1, strip='canvas'))[seed % 3]
    ridge = 2.2
    for s in (-1, 1):
        a.cyl(0.05, ridge + 0.15, T(V(s * 1.1, 0, 0)), E['post'], segs=6)
    a.cyl_between(V(-1.25, 0, ridge), V(1.25, 0, ridge), 0.04, E['post'], segs=6)
    for s in (-1, 1):
        c00, c10 = V(-1.2, 0, ridge), V(1.2, 0, ridge)
        c01, c11 = V(-1.3, s * 1.35, 0.15), V(1.3, s * 1.35, 0.15)
        a.poly([c00, c10, c11, c01] if s > 0 else [c00, c01, c11, c10], [(0, 1, 2, 3)], tarp, sharp=30)
        a.poly([c00, c01, c11, c10] if s > 0 else [c00, c10, c11, c01], [(0, 1, 2, 3)], tarp.k(0.8), sharp=30)
    a.box((0.6, 0.5, 0.45), T(V(1.6, 0.9, 0.22)) @ R('Z', 15), E['plank'], bevel=0.04)
    a.box((0.18, 0.4, 0.5), T(V(1.65, -0.9, 0.25)), E['red'], bevel=0.04)
    a.sphere((1.7, 1.8, 0.1), T(V(0, 0, -0.05)), E['mud'], 12, 4)
    return a.build()


def bog_tower(seed):
    """Tower -> swamp watchtower: braced legs, plank deck with a rail, rusty roof, lantern, ladder (h ~6)."""
    r = rnd(seed)
    a = Acc('TW_Prop_BogTower_%d' % seed)
    Hd = 4.2
    legs = [V(-1.0, -1.0, 0), V(1.0, -1.0, 0), V(1.0, 1.0, 0), V(-1.0, 1.0, 0)]
    tops = [V(-0.75, -0.75, Hd), V(0.75, -0.75, Hd), V(0.75, 0.75, Hd), V(-0.75, 0.75, Hd)]
    for b0, t0 in zip(legs, tops):
        a.cyl_between(b0 + V(0, 0, -0.4), t0 + V(0, 0, 1.6), 0.1, E['post'], segs=7)
    for i in range(4):
        b0, b1 = legs[i], legs[(i + 1) % 4]
        t0, t1 = tops[i], tops[(i + 1) % 4]
        for z in (1.3, 2.9):
            f = z / Hd
            p0 = b0 * (1 - f) + t0 * f; p1 = b1 * (1 - f) + t1 * f
            a.cyl_between(p0, p1, 0.05, E['post'], segs=5)
        a.cyl_between(b0 * 0.7 + t0 * 0.3 + V(0, 0, 0), b1 * 0.3 + t1 * 0.7, 0.04, E['post'], segs=5)
    a.box((2.0, 2.0, 0.12), T(V(0, 0, Hd)), E['plank_dk'], bevel=0.03)
    for i in range(4):
        t0, t1 = tops[i], tops[(i + 1) % 4]
        a.cyl_between(t0 + V(0, 0, 0.95), t1 + V(0, 0, 0.95), 0.035, E['post'], segs=5)
        a.box(((t1 - t0).length, 0.05, 0.45), T((t0 + t1) / 2 + V(0, 0, 0.35)) @ R('Z', math.degrees(math.atan2((t1 - t0).y, (t1 - t0).x))), E['corr'], bevel=0.01)
    a.lathe([(1.6, 0.0), (1.55, 0.06), (0.9, 0.45), (0.0, 0.6)], 4, T(V(0, 0, Hd + 1.6)) @ R('Z', 45), E['corr_rust'], cap_bottom=True, sharp=30)
    a.cyl(0.08, 0.2, T(V(0.7, -0.75, Hd + 1.2)), E['lamp'], segs=8, bevel=0.02)
    for s in (-0.22, 0.22):
        a.cyl_between(V(s, -1.35, 0.0), V(s, -0.85, Hd), 0.03, E['steel'], segs=5)
    for k in range(9):
        z = 0.4 + k * 0.42
        y = -1.35 + 0.5 * z / Hd
        a.cyl_between(V(-0.22, y, z), V(0.22, y, z), 0.022, E['steel'], segs=5)
    a.box((0.06, 0.9, 0.6), T(V(1.02, 0.0, Hd + 0.4)), E['label'], bevel=0.01)
    a.sphere((1.6, 1.6, 0.1), T(V(0, 0, -0.05)), E['mud'], 12, 4)
    return a.build()


def stash_box(seed):
    """Chest -> orange waterproof strongbox half in the mud with a rag flag."""
    a = Acc('TW_Prop_Stash_%d' % seed)
    M = T(V(0, 0, 0.12)) @ R('Y', 8) @ R('X', -6)
    a.box((1.1, 0.7, 0.6), M @ T(V(0, 0, 0.22)), S('#D07A2E', 0.45, 0.1, strip='metal'), bevel=0.07)
    a.box((1.14, 0.74, 0.12), M @ T(V(0, 0, 0.5)), S('#B4612A', 0.45, 0.1, strip='metal'), bevel=0.04)
    for x in (-0.35, 0.35):
        a.box((0.1, 0.06, 0.18), M @ T(V(x, -0.37, 0.4)), E['steel'], bevel=0.015)
    a.box((0.16, 0.05, 0.08), M @ T(V(0, -0.37, 0.38)), E['yellow'], bevel=0.01)
    a.cyl(0.025, 1.4, T(V(0.6, 0.35, 0.0)), E['post'], segs=6)
    a.poly([V(0.62, 0.35, 1.35), V(0.62, 0.35, 1.05), V(1.05, 0.38, 1.12), V(1.0, 0.36, 1.3)], [(0, 1, 2, 3), (3, 2, 1, 0)], E['tarp_or'], sharp=30)
    a.sphere((0.95, 0.75, 0.16), T(V(0, 0, -0.04)), E['mud'], 12, 4)
    return a.build()


BUILDERS = {
    'DryBush': (reed_bush, 3), 'RedRock': (bog_rock, 3), 'Pipes': (pipe_stack, 2), 'Barrels': (chem_drums, 3),
    'JunkPile': (junk_heap, 2), 'OilTank': (toxic_tank, 3), 'OilPump': (sludge_pump, 2), 'CarWreck': (sunk_wreck, 3),
    'Shack': (stilt_shack, 3), 'Tent': (tarp_tent, 3), 'Tower': (bog_tower, 2), 'Chest': (stash_box, 1),
}


def build_all():
    """Swap the Body meshes of every zone-1 prop spawn; returns {model: (variants, instances, tris per variant)}."""
    report = {}
    for model, (fn, nvar) in BUILDERS.items():
        meshes = [fn(100 + i) for i in range(nvar)]
        roots = [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('Spawn_1') and o.name.endswith('_' + model)]
        n = 0
        for root in roots:
            sid = int(root.name.split('_')[1])
            for c in root.children:
                if c.type == 'MESH' and c.name.split('.')[0] == 'Body':
                    L.swap_mesh(c, meshes[sid % nvar], 'swamp prop (Toxic Wetlands)')
                    n += 1
        report[model] = {'variants': nvar, 'instances': n, 'tris': [L.tri_count(m) for m in meshes]}
        print('TW_PROP', model, report[model], flush=True)
    return report
