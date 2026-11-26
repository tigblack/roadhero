"""The Sludge Baron's arena: a drained settling tank on a pump-station island in the toxic moat.

Fight space (r < 20 m around Unity (-15.6, 264)): flat. A concrete clarifier floor with a painted hazard ring, the
scraper's radial rails, the glowing central sump grate and a low broken rim, all flush with the ground (the car and
the boss move as before; the road still crosses north-south). Height and the central landmark come from the island
edge (r 23-27, outside the boss leash of 21 m): the pump tower (west, ~13 m, glowing gauge tank and stack), a
leaking storage tank with an outfall into the moat (east), a pump house (north-east), a pump unit (south-west) and
two floodlight masts. Every solid piece has a collision proxy; positions are checked against spawns and roads.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import tw_env as EV
import tw_lib as L
from tw_env import E, R, S, SC, T, V, rnd
from tw_lib import Acc
from tw_structures import add_collider, new_obj, zone_coll

C = Vector((-15.6, 264.0, 0.0))          # Blender (x, y = Unity z)


def polar(r_, compass_deg):
    a = math.radians(compass_deg)
    return C + Vector((math.sin(a) * r_, math.cos(a) * r_, 0.0))


def floor_mesh():
    a = Acc('TW_ArenaFloor')
    r = rnd(64)
    rings = [0.0, 2.7, 3.2, 5.0, 8.0, 11.0, 14.0, 16.4, 17.2, 18.1, 18.9, 19.6]
    n = 72
    # concrete disc with colour variation (moss towards the rim, sludge stains, a darker drained basin)
    co, faces = [], []
    idx = {}
    for i, rr in enumerate(rings):
        for k in range(n if rr > 0 else 1):
            idx[(i, k)] = len(co)
            ang = 2 * math.pi * k / n
            co.append(V(math.cos(ang) * rr, math.sin(ang) * rr, 0.014))
    for i in range(len(rings) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            if i == 0:
                faces.append((idx[(0, 0)], idx[(1, k)], idx[(1, k1)]))
            else:
                faces.append((idx[(i, k)], idx[(i + 1, k)], idx[(i + 1, k1)], idx[(i, k1)]))
    fs = a.poly(co, faces, E['concrete'], uv=None, sharp=None)
    for f in fs:
        for l in f.loops:
            c = l.vert.co
            rr = math.hypot(c.x, c.y)
            n1 = L.smooth_noise3((c.x, c.y, 0.0), 3, 0.18)
            n2 = L.smooth_noise3((c.x, c.y, 0.0), 9, 0.5)
            base = np.array(L.hexlin('#67665A'))
            base = base * (0.86 + 0.1 * n1 + 0.04 * n2)
            moss = max(0.0, min(1.0, (rr - 13.0) / 6.0)) * (0.5 + 0.5 * max(0.0, n1))
            base = base * (1 - moss * 0.6) + np.array(L.hexlin('#55602F')) * moss * 0.6
            stain = max(0.0, n2 - 0.35) * 1.6
            base = base * (1 - stain * 0.45) + np.array(L.hexlin('#33391F')) * stain * 0.45
            basin = max(0.0, 1.0 - rr / 9.0)
            base = base * (1 - 0.18 * basin)
            l[a.main.lc] = (base[0], base[1], base[2], 1.0)
            l[a.main.lp].uv = (0.08 + 0.2 * stain, 0.0)
    # painted hazard ring (u along the circumference)
    ring_f = a.poly(*ring_strip(17.25, 18.05, 0.024, 96), E['hazard'], uv=ring_uv(17.25, 18.05), sharp=None)
    # scraper rails: four radial steel strips from the sump to the rim (flush, readable from the camera)
    for ang in (45, 135, 225, 315):
        d = Vector((math.sin(math.radians(ang)), math.cos(math.radians(ang)), 0))
        side = Vector((-d.y, d.x, 0))
        for s in (-0.6, 0.6):
            p0 = d * 3.3 + side * s
            p1 = d * 17.0 + side * s
            a.box(((p1 - p0).length, 0.16, 0.05), T((p0 + p1) / 2 + V(0, 0, 0.025)) @ R('Z', math.degrees(math.atan2(d.y, d.x))), E['steel_dk'], bevel=0.015, segs=1)
        for t in np.linspace(4.0, 16.5, 6):
            q = d * t
            a.box((0.22, 1.5, 0.04), T(q + V(0, 0, 0.022)) @ R('Z', math.degrees(math.atan2(d.y, d.x))), E['rust'], bevel=0.01, segs=1)
    # central sump: steel ring, grate bars, toxic glow below
    a.cyl(2.65, 0.02, T(V(0, 0, 0.0)), E['toxic'], segs=40)
    a.lathe([(2.55, 0.0), (2.95, 0.0), (3.0, 0.06), (2.6, 0.08), (2.55, 0.0)], 48, Matrix(), E['steel_dk'], cap_bottom=False, cap_top=False, sharp=60)
    for k in range(-5, 6):
        x = k * 0.45
        hl = math.sqrt(max(0.0, 2.6 ** 2 - x * x))
        a.box((0.14, hl * 2, 0.07), T(V(x, 0, 0.045)), E['steel_dk'], bevel=0.02, segs=1)
    a.box((5.2, 0.16, 0.08), T(V(0, 0, 0.06)), E['steel_dk'], bevel=0.02, segs=1)
    # low broken rim (15 cm lip), open where the road passes (north / south)
    for k in range(48):
        ang = 360.0 * k / 48
        if min(abs(((ang - 0 + 180) % 360) - 180), abs(((ang - 180 + 180) % 360) - 180)) < 18:
            continue
        if r.random() < 0.18:
            continue
        rad = math.radians(ang)
        p = V(math.sin(rad) * 19.95, math.cos(rad) * 19.95, 0.07)
        a.box((2.4, 0.55, 0.16 + r.uniform(0, 0.08)), T(p) @ R('Z', -ang) @ R('X', r.uniform(-3, 3)), E['concrete_dk'], bevel=0.06, segs=2)
    return a.build()


def ring_strip(r0, r1, z, n):
    co, faces = [], []
    for k in range(n + 1):
        ang = 2 * math.pi * k / n
        co.append(V(math.cos(ang) * r0, math.sin(ang) * r0, z))
        co.append(V(math.cos(ang) * r1, math.sin(ang) * r1, z))
    for k in range(n):
        faces.append((2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1))
    return co, faces


def ring_uv(r0, r1):
    def uv(l, f):
        c = l.vert.co
        ang = math.atan2(c.y, c.x)
        fc = f.calc_center_median()
        ac = math.atan2(fc.y, fc.x)
        if ang - ac > math.pi:
            ang -= 2 * math.pi
        elif ac - ang > math.pi:
            ang += 2 * math.pi
        rr = math.hypot(c.x, c.y)
        return ang * (r0 + r1) / 2, (rr - r0) / (r1 - r0)
    return uv


def pump_tower():
    """Arena landmark: concrete base, steel gauge tank with a glowing sight band, roof, stack, ladder, platform."""
    a = Acc('TW_PumpTower')
    a.cyl(3.4, 0.5, T(V(0, 0, -0.2)), E['concrete_dk'], segs=32, bevel=0.1)
    a.cyl(3.0, 3.6, T(V(0, 0, 0.2)), E['concrete'], segs=32, bevel=0.15)
    a.lathe([(3.02, 0.35), (3.02, 1.1)], 32, Matrix(), S('#FFFFFF', 0.1, strip='concrete'), cap_bottom=False, cap_top=False)
    a.box((1.4, 0.3, 2.2), T(V(0, -3.0, 1.3)), E['steel_dk'], bevel=0.05)
    a.box((1.0, 0.32, 0.25), T(V(0, -3.02, 2.55)), E['hazard'], bevel=0.04)
    a.cyl(3.3, 0.35, T(V(0, 0, 3.75)), E['steel_dk'], segs=32, bevel=0.06)
    prof = [(2.4, 4.1), (2.45, 4.3), (2.45, 5.2), (2.47, 5.25), (2.47, 6.5), (2.45, 6.55), (2.45, 7.8), (2.2, 8.1), (1.0, 8.6), (0.0, 8.7)]
    bands = [E['tank_green'], E['tank_green'], E['steel_dk'], E['toxic'], E['steel_dk'], E['drips'], E['tank_dk'], E['tank_dk'], E['tank_dk']]
    a.lathe(prof, 32, Matrix(), surf_fn=lambda i: bands[min(i, len(bands) - 1)], cap_bottom=True, sharp=60)
    for k in range(20):
        ang = 2 * math.pi * k / 20
        a.cyl(0.035, 1.0, T(V(math.cos(ang) * 3.15, math.sin(ang) * 3.15, 4.0)), E['yellow'], segs=6)
    a.lathe([(3.12, 4.95), (3.18, 4.95), (3.18, 5.0), (3.12, 5.0)], 40, Matrix(), E['yellow'], cap_bottom=False, cap_top=False)
    a.cyl(0.55, 5.2, T(V(1.2, 1.0, 8.3)), E['rust'], segs=16, r2=0.45, bevel=0.05)
    a.lathe([(0.47, 13.3), (0.52, 13.45), (0.52, 13.9), (0.45, 13.95)], 16, T(V(1.2, 1.0, 0)), E['hazard'], cap_bottom=False, cap_top=False)
    for s in (-0.26, 0.26):
        a.cyl_between(V(s, -3.35, 0.2), V(s, -2.55, 8.2), 0.04, E['steel'], segs=6)
    for k in range(20):
        z = 0.6 + k * 0.38
        y = -3.35 + 0.8 * (z - 0.2) / 8.0
        a.cyl_between(V(-0.26, y, z), V(0.26, y, z), 0.025, E['steel'], segs=5)
    for k in range(3):
        ang = math.radians(200 + k * 35)
        d = Vector((math.cos(ang), math.sin(ang), 0))
        a.tube([d * 2.9 + V(0, 0, 1.6), d * 4.2 + V(0, 0, 1.4), d * 5.0 + V(0, 0, 0.5), d * 5.6 + V(0, 0, -0.2)], 0.32, E['rust'], segs=12)
    a.cyl(0.07, 0.25, T(V(-2.6, -1.4, 3.4)), E['lamp'], segs=8, bevel=0.02)
    a.cyl(0.07, 0.25, T(V(2.6, -1.4, 3.4)), E['lamp'], segs=8, bevel=0.02)
    return a.build()


def floodlight_mast():
    a = Acc('TW_FloodMast')
    a.cyl(0.55, 0.4, T(V(0, 0, -0.1)), E['concrete'], segs=14, bevel=0.06)
    a.cyl(0.14, 7.6, Matrix(), E['steel_dk'], segs=10, r2=0.1)
    a.box((1.6, 0.25, 0.18), T(V(0, 0, 7.4)), E['steel_dk'], bevel=0.04)
    for x in (-0.55, 0.0, 0.55):
        a.box((0.42, 0.3, 0.32), T(V(x, -0.12, 7.65)) @ R('X', -25), E['steel'], bevel=0.04)
        a.box((0.34, 0.04, 0.24), T(V(x, -0.28, 7.6)) @ R('X', -25), E['lamp'], bevel=0.01)
    a.box((0.3, 0.3, 0.6), T(V(0, 0, 1.0)), E['hazard'], bevel=0.04)
    return a.build()


def pump_house():
    a = Acc('TW_PumpHouse')
    W, D, H = 6.0, 4.6, 3.6
    a.box((W + 0.6, D + 0.6, 0.4), T(V(0, 0, 0.0)), E['concrete_dk'], bevel=0.1)
    a.box((W, D, H), T(V(0, 0, H / 2 + 0.2)), E['concrete'], bevel=0.12)
    a.box((W + 0.01, D + 0.01, 0.9), T(V(0, 0, 0.65)), S('#FFFFFF', 0.05, strip='concrete'), bevel=0.12)
    a.box((W + 0.5, D + 0.8, 0.12), T(V(0, 0, H + 0.5)) @ R('X', 6), E['corr_rust'], bevel=0.03)
    a.box((1.6, 0.12, 2.4), T(V(-1.2, -D / 2 - 0.05, 1.4)), E['corr'], bevel=0.03)
    a.box((1.7, 0.14, 0.2), T(V(-1.2, -D / 2 - 0.06, 2.75)), E['hazard'], bevel=0.03)
    a.box((1.3, 0.1, 0.7), T(V(1.5, -D / 2 - 0.04, 2.6)), E['black'], bevel=0.02)
    a.box((0.06, 1.2, 1.2), T(V(W / 2 + 0.04, 0, 2.3)), E['label'], bevel=0.02)
    a.cyl(0.5, 1.2, T(V(1.6, 0.8, H + 0.4)), E['rust'], segs=14, bevel=0.05)
    a.lathe([(0.0, 0.0), (0.7, 0.0), (0.7, 0.15), (0.0, 0.3)], 14, T(V(1.6, 0.8, H + 1.6)), E['steel_dk'], sharp=50)
    a.tube([V(W / 2, 1.4, 1.2), V(W / 2 + 1.6, 1.4, 1.1), V(W / 2 + 2.6, 1.6, 0.4), V(W / 2 + 3.4, 1.6, -0.2)], 0.38, E['rust'], segs=12)
    a.cyl(0.08, 0.22, T(V(-1.2, -D / 2 - 0.35, 2.9)), E['lamp'], segs=8, bevel=0.02)
    return a.build()


def place(name, me, pos, yaw, sc, radius, boxes, check=True):
    x, y = pos.x, pos.y
    if check and not sc.clear(x, y, radius, margin=1.0, road_margin=1.0):
        print('TW_ARENA skip (not clear)', name, (round(x, 1), round(y, 1)), flush=True)
        return None
    o = new_obj(name, me)
    o.location = (x, y, 0.0)
    o.rotation_euler = (0, 0, math.radians(yaw))
    bpy.context.view_layer.update()
    if boxes:
        add_collider(o, [(o.matrix_world @ Vector(c), s, yaw + yw) for c, s, yw in boxes])
    return o


def build(sc):
    rep = {}
    arena = sc.one('World/Arena')
    if arena is not None:
        me = floor_mesh()
        L.swap_mesh(arena, me, 'drained settling tank floor: hazard ring, scraper rails, glowing sump (flush)')
        rep['floor_tris'] = L.tri_count(me)
    tw = pump_tower()
    o = place('TW_Arena_PumpTower', tw, polar(26.0, 270.0), 0.0, sc, 3.6, [(V(0, 0, 4.0), (6.6, 6.6, 8.0), 0.0), (V(0, 0, 4.0), (6.6, 6.6, 8.0), 45.0)])
    rep['pump_tower'] = bool(o)
    # pipes from the tower across the west moat to the shore, on supports in the sludge
    pipe = EV.pipe_run(71, [polar(29.0, 268.0) + V(0, 0, 1.3), polar(36.0, 268.0) + V(0, 0, 1.3), polar(44.0, 266.0) + V(0, 0, 1.3)], 0.42, 4.0, name='TW_Arena_PipeWest')
    po = new_obj('TW_Arena_PipeWest', pipe)
    add_collider(po, [((polar(29.0, 268.0) + polar(44.0, 266.0)) / 2 + V(0, 0, 1.0), ((polar(29.0, 268.0) - polar(44.0, 266.0)).length, 1.6, 2.2),
                       math.degrees(math.atan2((polar(44.0, 266.0) - polar(29.0, 268.0)).y, (polar(44.0, 266.0) - polar(29.0, 268.0)).x)))])
    tank = EV.storage_tank(81, 2.8, 5.0, 'tank_green')
    o = place('TW_Arena_Tank', tank, polar(26.5, 92.0), 200.0, sc, 3.4, [(V(0, 0, 2.8), (6.0, 6.0, 5.6), 0.0), (V(0, 0, 2.8), (6.0, 6.0, 5.6), 45.0)])
    rep['tank'] = bool(o)
    ph = pump_house()
    o = place('TW_Arena_PumpHouse', ph, polar(26.0, 38.0), 205.0, sc, 3.8, [(V(0, 0, 2.0), (6.4, 5.0, 4.0), 0.0)])
    rep['pump_house'] = bool(o)
    pu = EV.pump_unit(91)
    o = place('TW_Arena_PumpUnit', pu, polar(25.0, 208.0), 120.0, sc, 2.0, [(V(0, 0, 0.9), (3.1, 2.1, 1.8), 0.0)])
    rep['pump_unit'] = bool(o)
    mast = floodlight_mast()
    rep['masts'] = 0
    for k, (rr, comp, yaw) in enumerate(((22.5, 150.0, 330.0), (22.5, 322.0, 140.0), (23.0, 60.0, 240.0))):
        o = place('TW_Arena_FloodMast_%d' % k, mast, polar(rr, comp), yaw, sc, 0.8, [(V(0, 0, 3.8), (0.7, 0.7, 7.6), 0.0)])
        rep['masts'] += bool(o)
    # drum clusters by the buildings (solid, with colliders)
    drums = [EV.drum('yel', 'upright', 1), EV.drum('olive', 'tipped', 2), EV.drum('blue', 'upright', 3, leak=True)]
    rep['drums'] = 0
    for k, (rr, comp) in enumerate(((23.0, 255.0), (24.0, 286.0), (23.5, 108.0), (23.0, 48.0), (22.5, 196.0))):
        p = polar(rr, comp)
        o = place('TW_Arena_Drum_%d' % k, drums[k % 3], p, comp * 1.7, sc, 0.7, [(V(0, 0, 0.45), (0.8, 0.8, 0.9), 0.0)])
        rep['drums'] += bool(o)
    # glowing outfall from the tank side into the moat
    of = EV.outfall(93)
    o = place('TW_Arena_Outfall', of, polar(30.5, 118.0), 118.0 - 90.0, sc, 1.6, [(V(-1.8, 0, 0.5), (3.0, 1.4, 1.0), 0.0)])
    rep['outfall'] = bool(o)
    print('TW_ARENA', rep, flush=True)
    return rep
