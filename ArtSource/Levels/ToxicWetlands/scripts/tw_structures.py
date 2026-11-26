"""Toxic Wetlands structures: the second zone's buildings, landmarks and borders in the swamp style.

Static v10 objects keep their Unity IDs: meshes are swapped in place (the generated colliders, occluder fading and
gate animation stay attached to the same objects in Unity). New objects (arena buildings, dam, berms) carry
collision proxies (tw_collider -> a hidden proxy mesh) so visible geometry and physics agree. Coordinates: Blender
(x, y = Unity z, z = up). Positions near gameplay objects are checked against the snapshot's spawns and roads.
"""
import colorsys
import json
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import tw_env as EV
import tw_lib as L
from tw_env import E, R, S, SC, T, V, curve, rnd
from tw_lib import Acc

ZONE = 'Zone_01_ToxicWetlands'
PROXY_COLL = 'Zone_01 — Collision proxies (not drawn, exported as collider buffers)'


# ------------------------------------------------------------------------------------------------ lookup

class Scene:
    def __init__(self, scene_json):
        sc = json.load(open(scene_json))
        self.md = sc['metadata']
        byid = {n['id']: n for n in sc['nodes']}

        def path(n):
            p = []
            while n:
                p.append(n['name']); n = byid.get(n['parentId'])
            return '/'.join(reversed(p))
        self.by_path = {}
        for o in bpy.data.objects:
            n = byid.get(str(o.get('unity_id')))
            if n is not None:
                self.by_path.setdefault(path(n), []).append(o)
        self.spawns = [s for s in self.md['spawns'] if s['zone'] == 1]
        self.roads = [np.array(r['points']).reshape(-1, 3)[:, [0, 2]] for r in self.md['roads'] if r['zone'] == 1]
        self.road_w = [r['width'] for r in self.md['roads'] if r['zone'] == 1]

    def get(self, path):
        return self.by_path.get(path, [])

    def one(self, path):
        objs = self.get(path)
        return objs[0] if objs else None

    def clear(self, x, z, radius, margin=1.5, road_margin=1.5):
        """True when a footprint circle (Unity x, z) stays clear of every spawn and road."""
        for s in self.spawns:
            sx, _, sz = s['position']
            if math.hypot(sx - x, sz - z) < radius + s['radius'] * s.get('scale', 1.0) + margin:
                return False
        for pts, w in zip(self.roads, self.road_w):
            for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
                vx, vz = bx - ax, bz - az
                t = max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / max(vx * vx + vz * vz, 1e-9)))
                if math.hypot(x - ax - t * vx, z - az - t * vz) < radius + w / 2 + road_margin:
                    return False
        return True


def zone_coll():
    return bpy.data.collections[ZONE]


def proxy_coll():
    c = bpy.data.collections.get(PROXY_COLL)
    if c is None:
        c = bpy.data.collections.new(PROXY_COLL)
        zone_coll().children.link(c)
        c.hide_render = True
    return c


def add_collider(obj, boxes, name=None):
    """boxes: [(centre Vector (world, Blender), size (x, y, z), yaw_deg)] -> proxy mesh in obj's local frame."""
    a = Acc((name or obj.name) + '_COL')
    inv = obj.matrix_world.inverted()
    for c, size, yaw in boxes:
        a.box(size, inv @ T(Vector(c)) @ R('Z', yaw), E['steel'], bevel=0.0)
    me = a.build()
    p = bpy.data.objects.new(me.name, me)
    proxy_coll().objects.link(p)
    p.matrix_world = obj.matrix_world.copy()
    p['tw_no_export'] = True
    p['tw_collider_for'] = obj.name
    p.hide_render = True
    obj['tw_collider'] = p.name
    obj['tw_collider_convex'] = False
    return p


def new_obj(name, me, parent=None, coll=None):
    o = L.new_object(name, me, coll or zone_coll())
    if parent is not None:
        o.parent = parent
    return o


def components(o):
    """Connected components of a mesh in world space: list of (centre, half extents, vertex count)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    mw = o.matrix_world
    seen = set()
    out = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]; idx = []
        seen.add(v.index)
        while stack:
            u = stack.pop(); idx.append(u.index)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index); stack.append(w)
        pts = [mw @ bm.verts[i].co for i in idx]
        mn = Vector([min(p[k] for p in pts) for k in range(3)])
        mx = Vector([max(p[k] for p in pts) for k in range(3)])
        out.append(((mn + mx) / 2, (mx - mn) / 2, len(idx)))
    bm.free()
    return out


# ------------------------------------------------------------------------------------------------ recolour

def swamp_recolor(me, wet_height=0.45):
    """Map the desert palette of a v10 mesh to the swamp palette (concrete -> mossy grey, sand / terracotta ->
    mud, reds -> rust, timber -> wet dark wood; hazard yellow and lamps stay) plus a wet algae band near the ground."""
    col = me.color_attributes.get('Color')
    if col is None:
        return 0
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    z = co.reshape(-1, 3)[lv, 2]
    c = np.empty(len(me.loops) * 4, np.float32)
    col.data.foreach_get('color', c)
    c = c.reshape(-1, 4)
    out = c.copy()
    for i in range(len(c)):
        r_, g_, b_ = [max(0.0, min(1.0, x)) ** (1 / 2.2) for x in c[i, :3]]
        h, s, v = colorsys.rgb_to_hsv(r_, g_, b_)
        hd = h * 360
        if c[i, 3] < 0.99:            # self-lit: keep
            continue
        if 40 <= hd <= 62 and s > 0.45:            # hazard yellow
            nr, ng, nb = r_ * 0.95, g_ * 0.92, b_ * 0.85
        elif (hd < 14 or hd > 340) and s > 0.4:    # reds -> rust
            nr, ng, nb = colorsys.hsv_to_rgb(16 / 360, 0.62, v * 0.82)
        elif 12 <= hd <= 40 and s > 0.22:          # sand / terracotta / timber
            if v > 0.55:
                nr, ng, nb = colorsys.hsv_to_rgb(65 / 360, 0.12, v * 0.72)     # pale concrete with an olive cast
            elif v > 0.35:
                nr, ng, nb = colorsys.hsv_to_rgb(48 / 360, 0.28, v * 0.75)     # mud / weathered wood
            else:
                nr, ng, nb = colorsys.hsv_to_rgb(38 / 360, 0.35, v * 0.8)      # wet dark wood
        elif s < 0.16:                              # greys: a slightly green, damp grey
            nr, ng, nb = r_ * 0.94, g_ * 0.98, b_ * 0.9
        else:
            nr, ng, nb = colorsys.hsv_to_rgb(70 / 360, min(0.35, s * 0.6), v * 0.85)
        k = 1.0
        if z[i] < wet_height:                       # wet algae band at the base
            t = 1.0 - max(0.0, z[i]) / wet_height
            nr, ng, nb = nr * (1 - 0.35 * t) + 0.23 * 0.35 * t, ng * (1 - 0.3 * t) + 0.27 * 0.3 * t, nb * (1 - 0.4 * t) + 0.12 * 0.4 * t
        out[i, :3] = [max(0.0, x) ** 2.2 * k for x in (nr, ng, nb)]
    col.data.foreach_set('color', out.ravel())
    return len(c)


def swap_or_recolor(o, me=None, note='swamp restyle'):
    if me is not None:
        L.swap_mesh(o, me, note)
    else:
        new = o.data.copy()
        new.name = o.data.name + '_swamp'
        swamp_recolor(new)
        L.swap_mesh(o, new, note + ' (recoloured)')
    return o


# ------------------------------------------------------------------------------------------------ rock tunnel

def mossy_boulders(comps, name, seed, colour=None, min_verts=30):
    """Rounded mossy boulders on the footprints of the original faceted rocks (their hull colliders stay)."""
    a = Acc(name)
    r = rnd(seed)
    for k, (c, half, n) in enumerate(comps):
        if n < min_verts:
            continue
        hx, hy, hz = max(half.x, 0.4), max(half.y, 0.4), max(half.z, 0.4)

        def deform(co, s=seed + k):
            q = L.smooth_noise3(co, s, 0.55)
            kk = 1.0 + 0.1 * q
            return Vector((co.x * kk, co.y * kk, co.z * kk))
        faces = a.superellipsoid((hx * 0.98, hy * 0.98, hz), (0.55, 0.6), T(c), colour or E['stone_dk'], 18, 11, deform=deform)
        for f in faces:
            cz = f.calc_center_median()
            n_ = L.smooth_noise3(cz, seed + k, 0.4)
            if f.normal.z > 0.8 and n_ > -0.15:
                tint = E['moss_flat'].rgba
            elif f.normal.z > 0.55 and n_ > 0.35:
                tint = E['moss_flat'].mix(E['stone'], 0.5).rgba
            elif cz.z < 0.5:
                tint = E['dead_wet'].rgba
            else:
                continue
            for l in f.loops:
                l[a.main.lc] = tint
    return a.build()


def rock_tunnel(sc):
    rep = {}
    for side in ('W', 'E'):
        o = sc.one('World/Structures/RockTunnel/RockMass' + side)
        if o is None:
            continue
        comps = components(o)
        me = mossy_boulders(comps, 'TW_SlagMound' + side, 31 if side == 'W' else 37)
        me.transform(o.matrix_world.inverted())
        # roots and vines over the road-facing side, reeds at the toe
        L.swap_mesh(o, me, 'mossy slag mound on the rock hull footprints')
        rep['RockMass' + side] = len(comps)
    # the rock bridge over the road becomes a rusty pipe rack (still fades for the car below)
    o = sc.one('World/Structures/RockTunnel/RockBridge')
    if o is not None:
        a = Acc('TW_PipeRack')
        x0, x1, z0, z1 = -23.4, -7.0, 176.4, 195.6
        for k in range(6):
            y = z0 + (z1 - z0) * k / 5
            a.box((x1 - x0, 0.35, 0.45), T(V((x0 + x1) / 2, y, 4.45)), E['rust'], bevel=0.06)
            if k in (0, 5):
                a.box((x1 - x0 - 0.4, 0.37, 0.16), T(V((x0 + x1) / 2, y, 4.38)), E['hazard'], bevel=0.03)
        for x, rr, surf in ((-19.0, 0.62, E['rust']), (-14.6, 0.75, E['galv']), (-10.3, 0.55, E['rust'])):
            a.cyl_between(V(x, z0 - 2.2, 5.3), V(x, z1 + 2.2, 5.3), rr, surf, segs=16)
            for y in np.linspace(z0, z1, 6):
                a.cyl(rr + 0.07, 0.14, T(V(x, y - 0.07, 5.3)) @ R('X', -90), E['steel_dk'], segs=16, bevel=0.02)
        a.box((2.0, z1 - z0, 0.08), T(V(-21.8, (z0 + z1) / 2, 4.75)), S('#FFFFFF', 0.4, 0.5, strip='grate'), bevel=0.01)
        for y in np.linspace(z0 + 1.5, z1 - 1.5, 5):
            a.tube([V(-16.8, y, 4.25), V(-16.75, y + 0.05, 3.6), V(-16.8, y, 3.0)], [0.05, 0.04, 0.0], E['algae_dk'], segs=4, flat=0.6)
        a.tube([V(-12.4, 186.0, 4.6), V(-12.4, 186.05, 4.0)], [0.08, 0.05], E['toxic'], segs=6)
        me = a.build()
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'rusty pipe rack over the road (fades for the car below)')
        rep['RockBridge'] = 'pipe rack'
    o = sc.one('World/Structures/RockTunnel/TunnelPosts')
    if o is not None:
        a = Acc('TW_TunnelColumns')
        for x in (-19.8, -9.2):
            for y in (177.0, 195.0):
                a.box((0.46, 0.46, 4.4), T(V(x, y, 2.2)), E['rust_pl'], bevel=0.05)
                a.box((0.5, 0.5, 0.6), T(V(x, y, 1.6)), E['hazard'], bevel=0.05)
                a.box((0.9, 0.9, 0.35), T(V(x, y, 0.12)), E['concrete'], bevel=0.06)
        me = a.build()
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'steel columns with hazard bands')
    return rep


# ------------------------------------------------------------------------------------------------ underpass and pipeline

def pipeline(sc):
    px, y0, y1, h = 20.0, 186.0, 232.0, 1.55
    parts = {'World/Structures/Underpass/Pipeline': [(186.0, 197.0), (216.0, 232.0)],
             'World/Structures/Underpass/PipelineOver': [(197.0, 216.0)]}
    for path, spans in parts.items():
        o = sc.one(path)
        if o is None:
            continue
        a = Acc('TW_' + path.split('/')[-1])
        for (s0, s1) in spans:
            a.cyl_between(V(px, s0, h), V(px, s1, h), 1.0, E['rust'], segs=20)
            yy = s0
            while yy <= s1 + 0.01:
                a.cyl(1.1, 0.24, T(V(px, yy - 0.12, h)) @ R('X', -90), E['steel_dk'], segs=20, bevel=0.03)
                if path.endswith('Pipeline'):
                    a.box((2.4, 0.6, 0.6), T(V(px, yy + 3.0, 0.3)), E['concrete'], bevel=0.08)
                yy += 6.0
            for k in range(int((s1 - s0) / 7)):
                y = s0 + 3.5 + k * 7
                a.tube([V(px + 0.95, y, h - 0.3), V(px + 1.0, y + 0.03, h - 0.9), V(px + 0.98, y, h - 1.4)], [0.05, 0.04, 0.0], E['algae_dk'], segs=4, flat=0.6)
            if path.endswith('Pipeline') and s0 < 190:
                a.tube([V(px - 0.9, 190.4, 1.1), V(px - 1.2, 190.5, 0.6), V(px - 1.3, 190.6, 0.03)], [0.09, 0.07, 0.05], E['toxic'], segs=6)
                a.cyl(0.9, 0.015, T(V(px - 1.6, 190.6, 0.0)) @ SC(1.0, 0.8, 1.0), E['toxic_goo'], segs=14)
        me = a.build()
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'rusty pipeline (same axis, radius and collider)')
    for path in ('World/Structures/Underpass/UnderpassBody', 'World/Structures/Underpass/UnderpassLid',
                 'World/Structures/Underpass/UnderpassPortal', 'World/Structures/Underpass/GroundFill',
                 'World/Structures/PipeJump/Ramp', 'World/Structures/BigJump1/Ramp',
                 'World/Terrain/BigJump1Course/BigJump1Course', 'World/Terrain/Kicker1a/Kicker1a',
                 'World/Terrain/Kicker1b/Kicker1b', 'World/Terrain/Kicker1c/Kicker1c'):
        for o in sc.get(path):
            swap_or_recolor(o)


# ------------------------------------------------------------------------------------------------ camps

def palisades(sc):
    out = 0
    for o in sc.get('World/Palisade'):
        comps = components(o)
        centre = o.matrix_world.translation
        angles = sorted({round(math.degrees(math.atan2(c.x - centre.x, c.y - centre.y)) % 360.0, 0) for c, half, n in comps if half.z > 0.6})
        present = set(int(a) for a in angles)
        a = Acc('TW_Stockade_%d' % out)
        r = rnd(41 + out)
        radius = 15.5
        n = int(round(2 * math.pi * radius / 0.62))
        prev = None
        for i in range(n):
            ang = i / n * 360.0
            if not any(abs(((ang - p + 180) % 360) - 180) <= 1.5 for p in present):
                prev = None
                continue
            rad = math.radians(ang)
            p = V(math.sin(rad) * radius, math.cos(rad) * radius, 0)
            if i % 7 == 3:
                # a rusty corrugated sheet between stakes
                tang = V(math.cos(rad), -math.sin(rad), 0)
                a.box((1.9, 0.05, 1.6), T(p + V(0, 0, 0.95)) @ R('Z', -ang) @ R('Y', r.uniform(-4, 4)), E['corr_rust'], bevel=0.015, segs=1)
            h = r.uniform(1.7, 2.4)
            tilt = R('X', r.uniform(-5, 5)) @ R('Y', r.uniform(-5, 5))
            col = E['post'].mix(E['dead'], r.uniform(0.0, 0.5))
            a.lathe([(0.0, -0.2), (0.17, -0.2), (0.16, h * 0.85), (0.1, h * 0.96), (0.0, h)], 6, T(p) @ tilt, col, sharp=40)
            if i % 9 == 5:
                a.box((1.2, 0.04, 0.9), T(p + V(0, 0, 1.3)) @ R('Z', -ang + 4), E['tarp'], bevel=0.01, segs=1)
            if prev is not None and i % 2 == 0:
                q0, q1 = prev + V(0, 0, 1.55), p + V(0, 0, 1.55)
                a.tube([q0, (q0 + q1) / 2 + V(0, 0, -0.08), q1], 0.012, E['steel_dk'], segs=4)
            prev = p
        me = a.build()
        L.swap_mesh(o, me, 'swamp stockade on the same ring and gaps (box colliders unchanged)')
        out += 1
    return out


def billboard(sc):
    o = sc.one('World/Billboard')
    if o is None:
        return
    a = Acc('TW_Billboard')
    for x in (-2.2, 2.2):
        a.cyl(0.16, 4.4, T(V(x, 0, -0.2)), E['rust_pl'], segs=10, bevel=0.03)
        a.box((0.7, 0.7, 0.3), T(V(x, 0, 0.1)), E['concrete'], bevel=0.06)
    a.box((6.2, 0.18, 2.8), T(V(0, 0, 4.4)), E['plank_dk'], bevel=0.05)
    a.box((6.4, 0.22, 0.22), T(V(0, -0.02, 5.85)), E['hazard'], bevel=0.04)
    a.box((6.4, 0.22, 0.22), T(V(0, -0.02, 2.95)), E['hazard'], bevel=0.04)
    # one big warning icon (custom uv over a single 128 px label cell)
    lo, h = L.strip_band('label')
    us = L.TRIM_SCALE['label']
    icon = 0.5   # metres of one icon at the label strip scale

    def uv(l, f):
        co = l.vert.co
        return (((co.x + 1.0) / 2.0) * icon, (co.z - 3.45) / 2.0)
    a.poly([V(-1.0, -0.11, 3.45), V(1.0, -0.11, 3.45), V(1.0, -0.11, 5.45), V(-1.0, -0.11, 5.45)], [(0, 1, 2, 3)],
           E['label'], uv=uv, sharp=30)
    for x in (-2.15, 2.15):
        a.box((1.6, 0.04, 1.6), T(V(x * 0.95, -0.1, 4.4)), S('#C9BE98', 0.3, strip='drips'), bevel=0.01)
    a.cyl(0.08, 0.2, T(V(0, -0.5, 6.0)), E['lamp'], segs=8, bevel=0.02)
    a.cyl_between(V(0, -0.1, 5.9), V(0, -0.5, 6.05), 0.03, E['steel_dk'], segs=5)
    me = a.build()
    L.swap_mesh(o, me, 'swamp warning billboard')


# ------------------------------------------------------------------------------------------------ gate to the next zone

def gate2(sc):
    t = sc.one('World/Gate2/GateTowers')
    b = sc.one('World/Gate2/BarrierPivot/GateBarrier')
    if t is not None:
        a = Acc('TW_Gate2Towers')
        for x in (-7.3, 7.3):
            a.box((4.4, 4.2, 1.0), T(V(x, 0, 0.5)), E['concrete'], bevel=0.12)
            a.box((3.6, 3.4, 5.2), T(V(x, 0, 3.6)), E['corr_rust'], bevel=0.08)
            a.box((3.8, 3.6, 0.5), T(V(x, 0, 1.25)), E['hazard'], bevel=0.06)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    a.box((0.32, 0.32, 7.4), T(V(x + sx * 1.85, sy * 1.75, 3.7)), E['steel_dk'], bevel=0.04)
            a.box((4.6, 4.4, 0.25), T(V(x, 0, 6.35)), E['plank_dk'], bevel=0.04)
            a.lathe([(3.3, 0.0), (3.2, 0.06), (1.6, 0.9), (0.0, 1.2)], 4, T(V(x, 0, 7.1)) @ R('Z', 45), E['corr'], cap_bottom=True, sharp=30)
            a.cyl(0.12, 0.3, T(V(x - 1.6 * (1 if x > 0 else -1), -1.9, 5.5)), E['lamp'], segs=8, bevel=0.03)
            a.box((0.06, 1.4, 1.4), T(V(x + (1.82 if x < 0 else -1.82), 0, 3.6)), E['label'], bevel=0.02)
            a.tube([V(x - 1.4, -1.75, 2.0), V(x - 1.42, -1.8, 1.0), V(x - 1.45, -1.78, 0.05)], [0.06, 0.04, 0.03], E['toxic'], segs=5)
        me = a.build()
        print('TW_STRUCT gate towers frame', [round(v, 3) for v in t.matrix_local.to_euler()], tuple(round(v, 2) for v in t.matrix_world.translation))
        L.swap_mesh(t, me, 'swamp gate towers (same footprint)')
    if b is not None:
        a = Acc('TW_Gate2Barrier')
        for z in (0.9, 2.2, 3.4):
            a.cyl_between(V(-5.0, 0, z), V(5.0, 0, z), 0.16, E['rust'], segs=12)
        for x in np.linspace(-4.6, 4.6, 7):
            a.box((0.3, 0.3, 3.9), T(V(x, 0, 2.0)), E['hazard'], bevel=0.05)
            a.lathe([(0.0, 0.0), (0.09, 0.0), (0.0, 0.45)], 8, T(V(x, 0, 3.95)), E['steel'], sharp=40)
        a.box((10.0, 0.25, 0.3), T(V(0, 0, 0.18)), E['steel_dk'], bevel=0.05)
        me = a.build()
        print('TW_STRUCT gate barrier frame', [round(v, 3) for v in b.matrix_world.to_euler()], tuple(round(v, 2) for v in b.matrix_world.translation))
        L.swap_mesh(b, me, 'swamp gate barrier (animated by Unity Gate)')


# ------------------------------------------------------------------------------------------------ hills

def hill_decor(sc):
    n = 0
    for path in ('World/Terrain/Hill1aDecor', 'World/Terrain/Hill1bDecor', 'World/Terrain/Hill1cDecor'):
        o = sc.one(path)
        if o is None:
            continue
        comps = components(o)
        me = mossy_boulders(comps, 'TW_' + path.split('/')[-1], 51 + n, colour=E['stone'], min_verts=10)
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'mossy boulders on the hill top')
        n += 1
    return n
