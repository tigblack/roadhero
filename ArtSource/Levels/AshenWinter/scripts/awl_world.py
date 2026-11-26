"""Ashen Winter environment: everything of the third zone outside the props and the ground tiles.

Reads the layout (data/AshenWinter_layout.json, awl_layout.py) for the gameplay structures - the same numbers Unity
uses for their floors and colliders (AshenSurfaces.cs) - and the world metadata exported with that layout active
(data/AshenWinter_world.json: roads and the spawns where the generator put them) to keep decor off spawns and roads.

Collections (children of Zone_02_AshenWinter): Terrain, Roads, Ramps, Bunker, ReactorArena, ReactorBackdrop,
BurntForest, Wrecks, Props, Collision (proxy meshes, exported as collider buffers only), LOD, DevSpawns.
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import tw_lib as L
import awl_lib as W
from awl_lib import LAcc, P, V, T, R, rnd, slab, snow_pillow, snow_tint, ring, lathe_at

ZONE = 'Zone_02_AshenWinter'
COLL = {k: None for k in ('Terrain', 'Roads', 'Ramps', 'Bunker', 'ReactorArena', 'ReactorBackdrop', 'BurntForest',
                          'Wrecks', 'Props', 'Collision', 'LOD', 'DevSpawns')}


def coll(name):
    if COLL.get(name) is None:
        c = L.ensure_collection(name, bpy.data.collections[ZONE])
        if name in ('Collision', 'LOD'):
            c.hide_render = True
        COLL[name] = c
    return COLL[name]


def new_obj(name, me, cname, roof=False, no_shadow=False):
    o = L.new_object(name, me, coll(cname))
    o['editing_zone'] = 2
    o['tw_stage'] = 'new in the Ashen Winter pass'
    if roof:
        o['tw_roof'] = True
    if no_shadow:
        o['tw_no_shadow'] = True
    return o


def add_collider(obj, boxes, name=None):
    """boxes: [(centre (Blender world), size (x, y, z), yaw_deg)] -> a proxy mesh (not drawn) for obj's collider."""
    a = LAcc((name or obj.name) + '_COL')
    inv = obj.matrix_world.inverted()
    for c, size, yaw in boxes:
        a.box(size, inv @ T(Vector(c)) @ R('Z', -yaw), P['steel'], bevel=0.0)
    me = a.build()
    p = bpy.data.objects.new(me.name, me)
    coll('Collision').objects.link(p)
    p.matrix_world = obj.matrix_world.copy()
    p['tw_no_export'] = True
    p['tw_collider_for'] = obj.name
    p.hide_render = True
    obj['tw_collider'] = p.name
    obj['tw_collider_convex'] = False
    return p


def hide(o, note, colliders=False):
    o['tw_hidden'] = True
    o['tw_stage'] = note
    if colliders:
        o['aw_disable_colliders'] = True
    o.hide_render = True
    o.hide_viewport = True


def ux(p):
    """Unity (x, z[, y]) -> Blender Vector."""
    return V(p[0], p[1], p[2] if len(p) > 2 else 0.0)


def fwd(yaw_deg):
    a = math.radians(yaw_deg)
    return V(math.sin(a), math.cos(a), 0.0)


def right_of(yaw_deg):
    a = math.radians(yaw_deg)
    return V(math.cos(a), -math.sin(a), 0.0)


def profile(u, a, b):
    """FloorPiece.Profile (Ground.cs): smooth ease-in / ease-out of a slope, u 0..1 -> 0..1."""
    a = min(max(a, 0.0), 0.45); b = min(max(b, 0.0), 0.45)
    m = 1.0 - 0.5 * a - 0.5 * b
    if a > 0 and u < a:
        s = u * u / (2 * a)
    elif b > 0 and u > 1 - b:
        s = (1 - 0.5 * a - 0.5 * b) - (1 - u) * (1 - u) / (2 * b)
    else:
        s = u - 0.5 * a
    return min(1.0, max(0.0, s / m))


ZMIN_ZONE, ZMAX_ZONE = 300.0, 500.0
STATION_CLEAR = 13.0     # m round a repair pad's centre kept free of decor (pad ring ~9 m + the shed)


class World:
    """Layout, roads and spawns for placement checks."""

    def __init__(self, data_dir, scene_json):
        self.L = json.load(open(os.path.join(data_dir, 'AshenWinter_layout.json')))
        wpath = os.path.join(data_dir, 'AshenWinter_world.json')
        md = json.load(open(wpath)) if os.path.exists(wpath) else json.load(open(scene_json))['metadata']
        self.md = md
        self.roads = [(np.array(r['points']).reshape(-1, 3)[:, [0, 2]], r['width']) for r in md['roads'] if r['zone'] == 2]
        self.spawns = [s for s in md['spawns'] if s.get('zone') == 2]
        self.rects = self.L['exclusions']
        self.taken = []          # (x, z, r) of decor already placed
        # the zone's repair pads (the car respawns and arrives from the DEV menu there): no decor on them or round them
        self.stations = []
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.split('.')[0] == 'Pad' and o.get('unity_id'):
                bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
                c = sum(bb, Vector()) / 8
                if ZMIN_ZONE <= c.y <= ZMAX_ZONE:
                    self.stations.append((c.x, c.y))

    def road_dist(self, x, z):
        best = 1e9
        for pts, w in self.roads:
            for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
                vx, vz = bx - ax, bz - az
                t = max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / max(vx * vx + vz * vz, 1e-9)))
                best = min(best, math.hypot(x - ax - t * vx, z - az - t * vz) - w / 2)
        return best

    def spawn_clear(self, x, z, r, margin=1.2):
        for s in self.spawns:
            sx, _, sz = s['position']
            rad = s.get('radius', 1.0) * s.get('scale', 1.0)
            if s['kind'] == 'Boss':
                continue
            if math.hypot(sx - x, sz - z) < r + rad + margin:
                return False
        return True

    def in_rects(self, x, z, pad=0.0, names=None):
        for rc in self.rects:
            if names and not rc['name'].startswith(names):
                continue
            a = math.radians(rc['yaw'])
            dx, dz = x - rc['x'], z - rc['z']
            lx = dx * math.cos(a) - dz * math.sin(a)
            lz = dx * math.sin(a) + dz * math.cos(a)
            if abs(lx) <= rc['halfX'] + pad and abs(lz) <= rc['halfZ'] + pad:
                return True
        return False

    def free(self, x, z, r, road_margin=2.0, spawn_margin=1.2, rect_pad=1.0, decor_margin=0.6):
        if abs(x) > 93 or z < 307 or z > 493:
            return False
        if self.road_dist(x, z) < r + road_margin:
            return False
        if not self.spawn_clear(x, z, r, spawn_margin):
            return False
        if self.in_rects(x, z, r + rect_pad):
            return False
        for (px, pz) in self.stations:
            if math.hypot(px - x, pz - z) < STATION_CLEAR + r:
                return False
        for (tx, tz, tr) in self.taken:
            if math.hypot(tx - x, tz - z) < r + tr + decor_margin:
                return False
        return True

    def take(self, x, z, r):
        self.taken.append((x, z, r))


# ================================================================================================ originals

def hide_originals(w):
    """Old Salt Flats visuals that the pass replaces (renderers off; colliders stay unless noted)."""
    n = 0
    for o in bpy.data.objects:
        if not o.get('unity_id') or o.type != 'MESH':
            continue
        base = o.name.split('.')[0]
        if base in ('Ground', 'Decor', 'Arena', 'Hill2aDecor', 'Hill2bDecor', 'Hill2cDecor', 'CanopyPosts', 'CanopyRoof',
                    'LampPool', 'Billboard'):
            hide(o, 'replaced by the Ashen Winter pass')
            n += 1
        elif base == 'Cliff':
            hide(o, 'drawn as the Ashen Winter snow massifs (the wall collider stays the boundary)')
            n += 1
    # the old canopy's posts stand where the bunker's tunnel walls are: its colliders go too
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.name.split('.')[0] == 'Canopy' and o.get('unity_id'):
            o['aw_disable_colliders'] = True
            o['tw_stage'] = 'old canopy: colliders off (the bunker replaces it)'
    return n


def recolor_mesh(o, fn, note):
    """Copy the object's mesh with new vertex colours fn(position, rgba) -> rgba (v10 meshes keep their UVs)."""
    mats = [sl.material for sl in o.material_slots]      # v10 objects link their materials to the object
    me = o.data.copy()
    me.name = o.data.name + '_ash'
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    col = me.color_attributes.get('Color')
    if col is not None:
        mw = o.matrix_world
        if col.domain == 'CORNER':
            for lp in me.loops:
                p = mw @ me.vertices[lp.vertex_index].co
                c = col.data[lp.index].color
                col.data[lp.index].color = fn(p, tuple(c), me.vertices[lp.vertex_index].normal)
        else:
            for v in me.vertices:
                c = col.data[v.index].color
                col.data[v.index].color = fn(mw @ v.co, tuple(c), v.normal)
    L.swap_mesh(o, me, note)
    return o


def ashen_palette(p, c, n):
    """Salt-flats colours -> Ashen Winter: whites become snow, warm tones become rust / burnt timber, hazard stays."""
    r, g, b, a = c
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if a < 0.98:
        return c
    up = n.z if hasattr(n, 'z') else 0.0
    sat = max(r, g, b) - min(r, g, b)
    if r > 0.45 and g > 0.25 and b < 0.12 and sat > 0.3:      # hazard yellow / orange: keep
        return c
    if sat > 0.18 and r > g > b:                                # warm (wood, terracotta, rust) -> dark rust / burnt wood
        k = 0.42
        return (r * k, g * k * 0.85, b * k * 0.8, a)
    if lum > 0.45:                                              # salt whites -> concrete grey, snow on top faces
        base = W.P['concrete'].rgb
        sn = W.P['snow'].rgb
        t = max(0.0, (up - 0.55) / 0.45)
        return (base[0] * (1 - t) + sn[0] * t, base[1] * (1 - t) + sn[1] * t, base[2] * (1 - t) + sn[2] * t, a)
    if b > r and sat > 0.1:                                     # salt-flats blue paint -> dark steel grey
        st = W.P['steel'].rgb
        k = 0.6 + 0.6 * lum
        return (st[0] * k, st[1] * k, st[2] * k, a)
    k = 0.75
    return (r * k, g * k, b * k * 1.05, a)


def rock_palette(p, c, n):
    """Salt rocks -> dark rock with snow on the upward faces (the ridge, the plateau's skirt)."""
    r, g, b, a = c
    if a < 0.98:
        return c
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    up = n.z if hasattr(n, 'z') else 0.0
    base = W.P['rock'].rgb if lum > 0.3 else W.P['rock_dk'].rgb
    k = 0.85 + 0.3 * min(1.0, lum)
    rc = (base[0] * k, base[1] * k, base[2] * k)
    sn = W.P['snow'].rgb
    t = max(0.0, min(1.0, (up - 0.6) / 0.3))
    return (rc[0] * (1 - t) + sn[0] * t, rc[1] * (1 - t) + sn[1] * t, rc[2] * (1 - t) + sn[2] * t, a)


def restyle_structures(w):
    """Palisades, gate, station pad, plateau, kickers, ridge: same meshes, Ashen colours."""
    names = ('Palisade', 'GateTowers', 'GateBarrier', 'Pad', 'Plateau', 'Ramp', 'Kicker2a', 'Kicker2b', 'Kicker2c', 'Ridge2')
    n = 0
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and o.get('unity_id') and o.name.split('.')[0] in names and not o.get('tw_hidden'):
            fn = rock_palette if o.name.split('.')[0] in ('Ridge2', 'Plateau') else ashen_palette
            recolor_mesh(o, fn, 'Ashen Winter colours (same mesh)')
            n += 1
    return n


# ================================================================================================ roads

def road_strips(w):
    """Snow banks and slush shoulders along every road edge (a low lofted bank, gaps at junctions and structures),
    concrete barrier runs on curves and near the structures, amber lamps on short posts."""
    acc = LAcc('AW_Road_Banks')
    bar = LAcc('AW_Road_Barriers')
    lamps = LAcc('AW_Road_Lamps')
    boxes = []
    rr = rnd(5)
    for ri, (pts, width) in enumerate(w.roads):
        # resample every 2 m
        seg = []
        for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
            n = max(1, int(math.hypot(bx - ax, bz - az) / 2.0))
            for k in range(n):
                t = k / n
                seg.append((ax + (bx - ax) * t, az + (bz - az) * t))
        seg.append(tuple(pts[-1]))
        seg = np.array(seg)
        for side in (-1, 1):
            run = []

            def flush(run):
                if len(run) < 4:
                    return
                secs = []
                for (x, z, nx, nz) in run:
                    prof = [(0.0, -0.05), (0.25, 0.10), (0.9, 0.26 + 0.06 * math.sin(x * 0.7 + z * 0.3)), (1.6, 0.18), (2.2, -0.05)]
                    secs.append([V(x + nx * d, z + nz * d, hh) for d, hh in prof])
                f = acc.loft(secs, P['snow_dirty'], cap0=False, cap1=False, closed=False)
                recolor_mesh_faces(acc, f)
            for i in range(len(seg)):
                a = seg[max(0, i - 1)]; b = seg[min(len(seg) - 1, i + 1)]
                tx, tz = b[0] - a[0], b[1] - a[1]
                tl = math.hypot(tx, tz) or 1.0
                nx, nz = tz / tl * side, -tx / tl * side
                x = seg[i][0] + nx * (width / 2 + 0.3)
                z = seg[i][1] + nz * (width / 2 + 0.3)
                ok = (abs(x) < 95 and 302 < z < 498 and not w.in_rects(x, z, 0.5, ('AshenBunker', 'AshenArena', 'AshenJump'))
                      and w.road_dist(x + nx * 1.2, z + nz * 1.2) > 0.6 and w.spawn_clear(x + nx, z + nz, 0.8, 0.2))
                if ok:
                    run.append((x, z, nx, nz))
                else:
                    flush(run); run = []
            flush(run)
        if ri != 0:
            continue
        # barriers: runs of 3-4 jersey segments every ~38 m on the outer side of the main road, gaps between
        d_acc = 0.0
        for i in range(2, len(seg) - 2, 1):
            d_acc += 2.0
            if d_acc < 26.0:
                continue
            a, b = seg[i - 1], seg[i + 1]
            tx, tz = b[0] - a[0], b[1] - a[1]
            tl = math.hypot(tx, tz) or 1.0
            side = 1 if (i // 19) % 2 else -1
            nx, nz = tz / tl * side, -tx / tl * side
            yaw = math.degrees(math.atan2(tx, tz))
            nseg = 3 + (i % 2)
            okall = True
            cs = []
            for k in range(nseg):
                cx = seg[i][0] + nx * (width / 2 + 1.1) + tx / tl * (k - nseg / 2) * 3.1
                cz = seg[i][1] + nz * (width / 2 + 1.1) + tz / tl * (k - nseg / 2) * 3.1
                if not (abs(cx) < 92 and 306 < cz < 494) or not w.spawn_clear(cx, cz, 1.2, 0.4) or \
                        w.in_rects(cx, cz, 0.5, ('AshenBunker', 'AshenArena', 'AshenJump')) or w.road_dist(cx, cz) < 0.4:
                    okall = False
                    break
                cs.append((cx, cz))
            if not okall:
                continue
            d_acc = 0.0
            for k, (cx, cz) in enumerate(cs):
                W.jersey_barrier(bar, V(cx, cz, 0.0), yaw, 3.0, seed=i * 7 + k)
                w.take(cx, cz, 1.6)
            mx = sum(c[0] for c in cs) / len(cs); mz = sum(c[1] for c in cs) / len(cs)
            boxes.append((V(mx, mz, 0.42), (0.62, 3.1 * len(cs), 0.85), yaw))
            lx = cs[-1][0] + tx / tl * 2.3; lz = cs[-1][1] + tz / tl * 2.3
            W.lamp_post(lamps, V(lx, lz, 0.0), seed=i)
    # amber lamps on short posts along the main road (alternating sides, every ~24 m), not on spawns or structures
    pts, width = w.roads[0]
    run = 0.0
    side = 1
    for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
        L_ = math.hypot(bx - ax, bz - az)
        run += L_
        if run < 24.0:
            continue
        tx, tz = (bx - ax) / max(L_, 1e-6), (bz - az) / max(L_, 1e-6)
        nx, nz = tz * side, -tx * side
        lx, lz = bx + nx * (width / 2 + 0.9), bz + nz * (width / 2 + 0.9)
        if abs(lx) < 92 and 306 < lz < 494 and w.spawn_clear(lx, lz, 0.4, 0.6) and not w.in_rects(lx, lz, 0.5, ('AshenBunker', 'AshenArena', 'AshenJump')) \
                and w.road_dist(lx, lz) > 0.3:
            W.lamp_post(lamps, V(lx, lz, 0.0), seed=int(lz))
            w.take(lx, lz, 0.4)
            run = 0.0
            side = -side
    objs = []
    for a_, nm in ((acc, 'AW_Road_Banks'), (bar, 'AW_Road_Barriers'), (lamps, 'AW_Road_Lamps')):
        me = a_.build(nm)
        objs.append(new_obj(nm, me, 'Roads', no_shadow=(nm == 'AW_Road_Banks')))
    if boxes:
        add_collider(objs[1], boxes)
    return {'barrier_runs': len(boxes)}


def recolor_mesh_faces(acc, faces):
    """Banks: grey slush at the road side, cleaner snow on the outer crest (by distance along the section)."""
    snow = P['snow'].rgb
    for f in faces:
        for lp in f.loops:
            c = lp[acc.main.lc]
            t = 0.5 + 0.5 * math.sin(lp.vert.co.x * 0.31 + lp.vert.co.y * 0.17)
            k = 0.35 + 0.4 * t if lp.vert.co.z > 0.12 else 0.1
            lp[acc.main.lc] = (c[0] * (1 - k) + snow[0] * k, c[1] * (1 - k) + snow[1] * k, c[2] * (1 - k) + snow[2] * k, c[3])


# ================================================================================================ bunker

def bunker(w):
    """The bunker over the main road (bottom-centre inset of the environment concept): a low massive trapezoid
    portal set into a snow mound, a wide low drive-through tunnel with wall thickness, ceiling and floor, sloped
    wing walls with faded orange stripes, exactly three round vent grilles on top, sparse amber lights inside."""
    b = w.L['bunker']
    c = V(b['x'], b['z'], 0.0)
    yaw = b['yaw']
    F, Rt = fwd(yaw), right_of(yaw)
    hw, hl, H, wall = b['innerHalfWidth'], b['halfLength'], b['height'], b['wall']
    M = T(c) @ R('Z', -yaw)          # local x across the road, local y along it (north), z up
    walls = LAcc('AW_Bunker_Walls')
    roof = LAcc('AW_Bunker_Roof')
    mound = LAcc('AW_Bunker_Mound')
    # tunnel side walls (thick), inner ribs, kerbs, the floor apron
    for s in (-1, 1):
        walls.box((wall, 2 * hl, H), M @ T(V(s * (hw + wall / 2), 0, H / 2)), P['concrete'], bevel=0.04)
        for k in range(6):
            y = -hl + 1.4 + k * (2 * hl - 2.8) / 5
            walls.box((0.35, 0.6, H - 0.2), M @ T(V(s * (hw - 0.12), y, (H - 0.2) / 2)), P['concrete_dk'], bevel=0.03)
        walls.box((0.5, 2 * hl, 0.25), M @ T(V(s * (hw - 0.25), 0, 0.12)), P['hazard'], bevel=0.02)
        for k in range(3):
            y = -hl + 3.0 + k * (2 * hl - 6.0) / 2
            walls.box((0.12, 0.5, 0.22), M @ T(V(s * (hw - 0.05), y, H - 0.8)), P['steel_dk'], bevel=0.01)
            walls.box((0.06, 0.38, 0.12), M @ T(V(s * (hw - 0.12), y, H - 0.8)), P['lamp'], bevel=0.01)
    # ceiling slab and beams (the roof object: it fades while the car is under it)
    roof.box((2 * hw + 2 * wall, 2 * hl, 0.9), M @ T(V(0, 0, H + 0.45)), P['concrete_dk'], bevel=0.05)
    for k in range(5):
        y = -hl + 1.6 + k * (2 * hl - 3.2) / 4
        roof.box((2 * hw, 0.5, 0.45), M @ T(V(0, y, H - 0.2)), P['concrete'], bevel=0.03)
    # portals at both ends: trapezoid frame (sloped sides), thick top lintel, wing walls into the mound
    for e in (-1, 1):
        y0 = e * (hl + 0.6)
        Mp = M @ T(V(0, y0, 0))
        # lintel over the opening
        walls.box((2 * hw + 2.2, 1.6, 1.5), Mp @ T(V(0, 0, H + 0.75)), P['concrete'], bevel=0.06)
        for s in (-1, 1):
            # sloped portal side: a prism leaning outward (wide at the base)
            base_in, base_out, top_in, top_out = hw, hw + 4.6, hw, hw + 1.6
            pts_b = [V(s * base_in, -0.8, 0), V(s * base_out, -0.8, 0), V(s * base_out, 0.8, 0), V(s * base_in, 0.8, 0)]
            pts_t = [V(s * top_in, -0.8, H + 1.5), V(s * top_out, -0.8, H + 1.5), V(s * top_out, 0.8, H + 1.5), V(s * top_in, 0.8, H + 1.5)]
            if s < 0:
                pts_b = [pts_b[1], pts_b[0], pts_b[3], pts_b[2]]
                pts_t = [pts_t[1], pts_t[0], pts_t[3], pts_t[2]]
            f = W.prism_world(walls, [Mp @ p for p in pts_b], [Mp @ p for p in pts_t], P['concrete'])
            # faded orange stripes on the sloped faces (two diagonal bands)
            for k in range(2):
                zc = 1.2 + k * 2.2
                xo = hw + 4.6 - (3.0 * zc / (H + 1.5)) - 0.2
                Ms = Mp @ T(V(s * xo, -0.81 * e * 0, zc)) @ R('Y', s * 28)
                walls.box((1.9, 1.66, 0.9), Ms, P['paint_or'], bevel=0.02)
            # hazard-striped bumper at the inner corner, a caged lamp
            walls.box((0.6, 0.8, 1.1), Mp @ T(V(s * (hw - 0.3), -e * 0.2, 0.55)), P['hazard'], bevel=0.05)
            walls.box((0.25, 0.3, 0.3), Mp @ T(V(s * (hw - 0.2), -e * 0.75, 1.6)), P['lamp'], bevel=0.02)
            # wing wall stepping back into the mound
            Mw = Mp @ T(V(s * (hw + 6.5), e * 1.4, 1.6)) @ R('Z', s * e * 25)
            walls.box((5.5, 1.2, 3.2), Mw, P['concrete_dk'], bevel=0.05)
        snow_pillow(roof, Mp @ V(0, 0, H + 1.5), (hw + 1.0, 0.9, 0.14), M.to_3x3().to_4x4(), seed=11 + e, surf=P['snow'])
        for k in range(9):
            x = -hw - 0.5 + (2 * hw + 1.0) * k / 8
            W.horn(roof, Mp @ V(x, -e * 0.82, H + 0.1), Mp @ V(x, -e * 0.82, H + 0.1 - 0.25 - 0.35 * ((k * 7) % 3) / 2), 0.06, P['ice'], segs=5, n=3)
    # the vent block on top: three big round grilles in a concrete housing
    vb = M @ V(0, -hl + 2.2, H + 0.9)
    roof.box((9.0, 3.2, 2.0), M @ T(V(0, -hl + 2.2, H + 0.9 + 1.0)), P['concrete'], bevel=0.08)
    for k in range(3):
        x = -3.0 + 3.0 * k
        cc = M @ V(x, -hl + 2.2 - 1.62, H + 1.95)
        lathe_at(roof, [(0.0, 0.0), (1.12, 0.0), (1.2, 0.06), (1.2, 0.22), (1.05, 0.24), (0.98, 0.10), (0.0, 0.10)], cc,
                 -F, P['steel_dk'], segs=24, caps=(False, False), sharp=40)
        lathe_at(roof, [(0.0, 0.11), (0.97, 0.11)], cc, -F, P['grille'], segs=24, caps=(False, False))
        for j in range(5):
            zz = -0.7 + 0.35 * j
            ww = math.sqrt(max(0.0, 0.97 ** 2 - zz ** 2))
            roof.cyl_between(cc + Rt * (-ww) + V(0, 0, zz) - F * 0.14, cc + Rt * ww + V(0, 0, zz) - F * 0.14, 0.05, P['steel'], 6)
    snow_pillow(roof, M @ V(0, -hl + 2.2, H + 2.95), (4.2, 1.4, 0.2), M.to_3x3().to_4x4(), seed=21, surf=P['snow'])
    # the mound: a snow dome over the tunnel, cut away in front of the portals; rock outcrops on its flanks
    mx, my, mh = b['moundHalfX'], b['moundHalfZ'], H + 3.2
    nxg, nyg = 38, 24
    verts, idx = [], {}
    for j in range(nyg + 1):
        for i in range(nxg + 1):
            lx = -mx + 2 * mx * i / nxg
            ly = -my + 2 * my * j / nyg
            rr_ = math.sqrt((lx / mx) ** 2 + (ly / my) ** 2)
            if rr_ > 1.0:
                continue
            if abs(lx) < hw + wall + 0.8 and abs(ly) > hl + 0.2:
                continue
            hh = mh * (1 - rr_ ** 2) ** 1.15 + 0.25 * W.smooth_noise3(V(lx * 0.3, ly * 0.3, 0), 3, 1.0)
            if abs(lx) < hw + wall + 0.8:
                hh = max(hh, H + 1.2)
            idx[(i, j)] = len(verts)
            verts.append(M @ V(lx, ly, max(0.0, hh) - 0.05))
    faces = []
    for j in range(nyg):
        for i in range(nxg):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(k in idx for k in q):
                faces.append([idx[k] for k in q])
    mf = mound.poly([tuple(v) for v in verts], faces, P['snow'], sharp=None)
    # ash on steep and low parts, cleaner snow on the crown
    for f in mf:
        for lp in f.loops:
            z = lp.vert.co.z
            k = max(0.0, min(1.0, 1.2 - z / 3.0)) * 0.45
            cc_ = lp[mound.main.lc]
            ash = P['ash_lt'].rgb
            lp[mound.main.lc] = (cc_[0] * (1 - k) + ash[0] * k, cc_[1] * (1 - k) + ash[1] * k, cc_[2] * (1 - k) + ash[2] * k, cc_[3])
    rr = rnd(31)
    for k in range(9):
        s = 1 if k % 2 else -1
        lx = s * rr.uniform(hw + 4.0, mx - 3.0)
        ly = rr.uniform(-my + 2.5, my - 2.5)
        rr_ = math.sqrt((lx / mx) ** 2 + (ly / my) ** 2)
        hh = mh * max(0.0, 1 - rr_ ** 2) ** 1.15
        W.rock_outcrop(mound, M @ V(lx, ly, max(0.0, hh - 0.9)), (rr.uniform(2.0, 3.4), rr.uniform(1.8, 3.0), rr.uniform(1.6, 2.6)), 300 + k)
    for k in range(4):
        s = 1 if k % 2 else -1
        W.burnt_tree(mound, M @ V(s * rr.uniform(hw + 5, mx - 4), rr.uniform(-my + 3, my - 3), mh * 0.45), 340 + k, height=5.0)
    ow = new_obj('AW_Bunker_Walls', walls.build(), 'Bunker')
    orf = new_obj('AW_Bunker_Roof', roof.build(), 'Bunker', roof=True)
    om = new_obj('AW_Bunker_Mound', mound.build(), 'Bunker', roof=True)
    # colliders: tunnel walls + portal sides (one proxy), the mound flanks (stepped blocks)
    boxes = []
    for s in (-1, 1):
        boxes.append((M @ V(s * (hw + wall / 2), 0, H / 2), (wall, 2 * hl + 1.6, H + 1.5), yaw))
        for e in (-1, 1):
            boxes.append((M @ V(s * (hw + 2.6), e * (hl + 0.6), (H + 1.5) / 2), (4.6, 1.6, H + 1.5), yaw))
    add_collider(ow, boxes)
    mb = []
    for s in (-1, 1):
        for (x0, x1, hy, hh) in ((hw + wall, mx * 0.9, my * 0.86, 1.6), (hw + wall, mx * 0.72, my * 0.75, 3.8), (hw + wall, mx * 0.5, my * 0.6, 7.0)):
            mb.append((M @ V(s * (x0 + x1) / 2, 0, hh / 2), (x1 - x0, 2 * hy, hh), yaw))
    add_collider(om, mb)
    return {'bunker': (round(b['x'], 2), round(b['z'], 2), round(yaw, 2))}


# ================================================================================================ arena

def arena(w):
    """The reactor arena (bottom-right inset): a raised round concrete deck on the main road (1.2 m; the floor and
    its edge colliders are AshenSurfaces' with the same numbers), a retaining wall of big stone blocks with icicles,
    a yellow floor ring, low segmented barriers and amber lamps on the rim, cover blocks at the periphery, broken
    arc ribs round it and the ruined reactor workshop behind with its hot opening."""
    a = w.L['arena']
    c = V(a['x'], a['z'], 0.0)
    R_, h = a['radius'], a['height']
    deck = LAcc('AW_Arena_Deck')
    wallacc = LAcc('AW_Arena_Wall')
    rim = LAcc('AW_Arena_Rim')
    opens = [(rp['angle'], math.degrees(math.asin(min(1.0, (rp['halfX'] + 0.2) / R_)))) for rp in a['ramps']]

    def in_open(ang, pad=0.0):
        return any(abs(((ang - o + 180) % 360) - 180) < hh + pad for o, hh in opens)
    # deck top: a disc of concrete with a worn burnt centre
    f = W.disc(deck, c, R_, h, P['concrete'], segs=96)
    for ff in f:
        for lp in ff.loops:
            p = lp.vert.co
            d = math.hypot(p.x - c.x, p.y - c.y)
            n = W.smooth_noise3(V(p.x * 0.2, p.y * 0.2, 0), 9, 1.0)
            k = 0.86 + 0.1 * n - 0.25 * max(0.0, 1.0 - d / 5.0)
            col = P['concrete'].rgb
            lp[deck.main.lc] = (col[0] * k, col[1] * k, col[2] * k, 1.0)
    # the yellow ring (dashed) and an inner thin ring
    for (r0, r1, nseg, gap) in ((7.0, 7.9, 28, 0.35), (10.6, 10.9, 48, 0.5)):
        W.ring_band(deck, c, r0, r1, h + 0.012, P['paint_yel'], nseg=nseg, gap=gap)
    # retaining wall: big stone blocks round the deck edge, joints, icicles under the coping
    rr = rnd(41)
    nb = 64
    for k in range(nb):
        ang = 360.0 * (k + 0.5) / nb
        if in_open(ang, -0.5):
            continue
        d = V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0)
        yawb = math.degrees(math.atan2(d.x, d.y))
        for row in range(2):
            hz = h / 2 + 0.1
            zc = -0.25 + row * hz + hz / 2
            slab(wallacc, c + d * (R_ + 0.35 + 0.05 * row) + V(0, 0, zc), (2 * math.pi * (R_ + 0.4) / nb + 0.05, 0.8, hz - 0.04),
                 P['concrete_dk'] if (k + row) % 3 == 0 else P['concrete'], M_=R('Z', -yawb), seed=900 + k * 2 + row, chip=0.05, e=0.12,
                 segs=6, rings=4)
        wallacc.box((2 * math.pi * (R_ + 0.45) / nb + 0.06, 1.0, 0.22), T(c + d * (R_ + 0.4) + V(0, 0, h + 0.05)) @ R('Z', -yawb),
                    P['concrete_lt'], bevel=0.03)
        if k % 2 == 0:
            for j in range(2):
                p = c + d * (R_ + 0.92) + V(0, 0, h - 0.05)
                p = p + V(-d.y, d.x, 0) * rr.uniform(-0.6, 0.6)
                W.horn(wallacc, p, p + V(0, 0, -rr.uniform(0.25, 0.7)), 0.05, P['ice'], segs=5, n=3)
    # rim: low segmented barriers (gaps between segments) and amber lamps on posts; the parapet colliders are code
    nseg = 48
    for k in range(nseg):
        ang = 360.0 * (k + 0.5) / nseg
        if in_open(ang, 1.0):
            continue
        d = V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0)
        yawb = math.degrees(math.atan2(-d.y, d.x))
        W.jersey_barrier(rim, c + d * (R_ - 0.3) + V(0, 0, h), yawb, 2 * math.pi * (R_ - 0.3) / nseg - 0.35, height=0.8, seed=k)
        if k % 6 == 3:
            W.lamp_post(rim, c + d * (R_ - 0.3) + V(0, 0, h + 0.8), height=0.45, seed=k)
    # cover at the periphery: concrete blocks and barrier pieces (the centre stays free for the boss)
    cover = LAcc('AW_Arena_Cover')
    cboxes = []
    for k, (ang, rad) in enumerate(((35, 15.5), (110, 14.5), (160, 15.8), (215, 15.0), (325, 14.8), (290, 16.0))):
        if in_open(ang, 18.0):
            continue
        d = V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0)
        p = c + d * rad
        yawb = math.degrees(math.atan2(-d.y, d.x))
        for j in range(2):
            q = p + V(-d.y, d.x, 0) * (j - 0.5) * 1.9
            W.concrete_block(cover, q + V(0, 0, h), yawb + rr.uniform(-8, 8), 950 + k * 3 + j, size=(1.8, 1.0, 0.95))
        cboxes.append((p + V(0, 0, h + 0.5), (1.2, 3.9, 1.0), yawb))
    # arc ribs round the deck (outside it, on the valley floor)
    ribs = LAcc('AW_Arena_Ribs')
    rboxes = []
    for k, ang in enumerate((52, 128, 232, 308)):
        d = V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0)
        p = c + d * (R_ + 3.2)
        lean = math.degrees(math.atan2(-d.x, -d.y))
        W.arc_rib(ribs, p, lean, 8.0 + 1.5 * (k % 2), 4.2, 960 + k, thick=1.9)
        rboxes.append((p + V(0, 0, 1.2), (2.4, 2.6, 2.4), lean))
    od = new_obj('AW_Arena_Deck', deck.build(), 'ReactorArena')
    owl = new_obj('AW_Arena_Wall', wallacc.build(), 'ReactorArena')
    orim = new_obj('AW_Arena_Rim', rim.build(), 'ReactorArena')
    oc = new_obj('AW_Arena_Cover', cover.build(), 'ReactorArena')
    orb = new_obj('AW_Arena_Ribs', ribs.build(), 'ReactorArena')
    if cboxes:
        add_collider(oc, cboxes)
    add_collider(orb, rboxes)
    # the ramps: asphalt slopes with the FloorPiece profile, concrete cheeks, the dashed line continuing up
    for i, rp in enumerate(a['ramps']):
        ramp_mesh(rp, h, 'AW_Arena_Ramp%d' % i, ease=(0.3, 0.3), surf=P['asphalt'], line=True, cheeks=True, coll_name='ReactorArena')
    # the reactor workshop behind the arena (hot opening facing the deck), its LOD as a simplified far version
    ws = w.L['landmarks']['workshop']
    wa = LAcc('AW_Reactor_Workshop')
    W.workshop(wa, V(ws['x'], ws['z'], 0.0), ws['halfX'], ws['halfZ'], ws['height'], seed=7)
    o = new_obj('AW_Reactor_Workshop', wa.build(), 'ReactorBackdrop')
    add_collider(o, [(V(ws['x'], ws['z'], ws['height'] / 2), (2 * ws['halfX'] + 0.7, 2 * ws['halfZ'] + 0.7, ws['height']), 0.0)])
    return {'deck_r': R_, 'ramps': len(a['ramps']), 'cover': len(cboxes), 'ribs': len(rboxes)}


def ramp_mesh(rp, height, name, ease=(0.3, 0.3), surf=None, line=False, cheeks=True, coll_name='Ramps', chevrons=False):
    """A ramp whose top follows FloorPiece.Profile exactly (same rect, heights and easing as the Unity floor), with
    a solid body down to the ground, concrete cheeks on both sides (top 0.25 m over the surface) and optional
    chevrons / a dashed centre line."""
    yaw = rp['yaw']
    c = V(rp['x'], rp['z'], 0.0)
    hx, hz = rp['halfX'], rp['halfZ']
    M = T(c) @ R('Z', -yaw)
    acc = LAcc(name)
    n = 22
    top, bot = [], []
    for i in range(n + 1):
        u = i / n
        y = -hz + 2 * hz * u
        hh = height * profile(u, ease[0], ease[1])
        top.append((y, hh))
    # deck surface strips (across: 4 quads)
    xs = [-hx, -hx * 0.5, 0.0, hx * 0.5, hx]
    vts = []
    for (y, hh) in top:
        for x in xs:
            vts.append(M @ V(x, y, hh + 0.02))
    fi = []
    for i in range(n):
        for j in range(4):
            a0 = i * 5 + j
            fi.append((a0, a0 + 1, a0 + 6, a0 + 5))
    uvf = (lambda lp, f: (0.0, 0.5))
    fsurf = surf or P['concrete']
    acc.poly([tuple(v) for v in vts], fi, fsurf, sharp=None)
    if chevrons:
        # chevron band along the middle (strip u runs up the ramp)
        cv = []
        for (y, hh) in top:
            cv.append(M @ V(-hx * 0.55, y, hh + 0.03))
            cv.append(M @ V(hx * 0.55, y, hh + 0.03))
        cf = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(n)]
        vmap = {}
        for i in range(n + 1):
            vmap[2 * i] = (top[i][0] + hz, 0.0)
            vmap[2 * i + 1] = (top[i][0] + hz, 1.0)
        pt = L._Part()
        bm_ = pt.bm
        vv = [bm_.verts.new(p) for p in cv]
        faces = [bm_.faces.new([vv[k] for k in q]) for q in cf]
        bm_.verts.index_update()
        acc.paint(faces, P['chevron'], lambda lp, f: (vmap[lp.vert.index][0], vmap[lp.vert.index][1]), part=pt)
        acc._commit(pt)
    if line:
        for i in range(0, n, 2):
            y0, h0 = top[i]; y1, h1 = top[i + 1]
            pts = [M @ V(-0.08, y0, h0 + 0.035), M @ V(0.08, y0, h0 + 0.035), M @ V(0.08, y1, h1 + 0.035), M @ V(-0.08, y1, h1 + 0.035)]
            acc.poly([tuple(p) for p in pts], [(0, 1, 2, 3)], P['paint_yel'], sharp=None)
    # body sides and the high end face (solid down to the ground)
    for s in (-1, 1):
        side = [M @ V(s * hx, y, hh + 0.02) for (y, hh) in top] + [M @ V(s * hx, y, -0.1) for (y, hh) in reversed(top)]
        ids = list(range(len(side)))
        acc.poly([tuple(p) for p in side], [list(reversed(ids)) if s > 0 else ids], P['concrete_dk'], sharp=30)
        if cheeks:
            for i in range(n):
                y0, h0 = top[i]; y1, h1 = top[i + 1]
                if max(h0, h1) < 0.05:
                    continue
                cx_ = s * (hx + 0.28)
                acc.box((0.55, (y1 - y0) + 0.02, max(h0, h1) + 0.35), M @ T(V(cx_, (y0 + y1) / 2, (max(h0, h1) + 0.35) / 2 - 0.1)),
                        P['concrete'], bevel=0.02)
    yh, hh = top[-1]
    if hh > 0.3 and not chevrons:
        pass
    o = new_obj(name, acc.build(), coll_name)
    return o


# ================================================================================================ jump

def jump(w):
    """The concrete jump ramp on the side track (bottom-left inset): smooth entry, rise and a pronounced lip, side
    cheeks, two big yellow chevrons, hazard blocks and lamps; over the ravine onto a landing pad with a yellow ring."""
    j = w.L['jump']
    f = fwd(j['yaw'])
    lip = V(j['x'], j['z'], 0.0)
    cen = lip - f * (j['length'] / 2)
    rp = dict(x=cen.x, z=cen.y, yaw=j['yaw'], halfX=j['halfWidth'], halfZ=j['length'] / 2)
    o = ramp_mesh(rp, j['height'], 'AW_Jump_Ramp', ease=(0.3, 0.0), surf=P['concrete_lt'], chevrons=True, cheeks=True, coll_name='Ramps')
    deco = LAcc('AW_Jump_Deco')
    Rt = right_of(j['yaw'])
    # the lip: a steel edge, the back face, lamps on the cheeks, hazard blocks at the foot
    deco.box((2 * j['halfWidth'] + 0.4, 0.3, 0.2), T(lip + V(0, 0, j['height'] - 0.05)) @ R('Z', -j['yaw']), P['steel'], bevel=0.02)
    deco.box((2 * j['halfWidth'] + 1.1, 0.6, j['height']), T(lip + f * 0.3 + V(0, 0, j['height'] / 2 - 0.05)) @ R('Z', -j['yaw']),
             P['concrete_dk'], bevel=0.04)
    for s in (-1, 1):
        W.lamp_post(deco, lip + Rt * s * (j['halfWidth'] + 0.3) + V(0, 0, j['height'] + 0.2), height=0.6, seed=s + 3)
        deco.box((1.2, 1.2, 1.1), T(lip - f * j['length'] + Rt * s * (j['halfWidth'] + 1.3) + V(0, 0, 0.55)) @ R('Z', -j['yaw'] + 10 * s),
                 P['hazard'], bevel=0.05)
        W.lamp_post(deco, lip - f * (j['length'] + 1.5) + Rt * s * (j['halfWidth'] + 1.4), height=1.1, seed=s + 7)
    snow_pillow(deco, lip + V(0, 0, j['height'] + 0.02), (j['halfWidth'] * 0.4, 0.25, 0.06), R('Z', -j['yaw']), seed=5, surf=P['snow'])
    # landing pad: concrete disc flush with the ground, a dashed yellow ring and a cross
    pd = w.L['pad']
    pc = V(pd['x'], pd['z'], 0.0)
    pad = LAcc('AW_Jump_Pad')
    W.disc(pad, pc, pd['radius'], 0.03, P['concrete'], segs=48, rim=(pd['radius'] + 0.4, -0.05))
    W.ring_band(pad, pc, 5.6, 6.3, 0.045, P['paint_yel'], nseg=24, gap=0.38, steps=3)
    for ang in (0, 90):
        pad.box((7.0, 0.55, 0.02), T(pc + V(0, 0, 0.045)) @ R('Z', ang), P['paint_yel'], bevel=0.0)
    for k, ang in enumerate((45, 135, 225, 315)):
        p = pc + V(math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0) * (pd['radius'] + 0.9)
        W.lamp_post(pad, p, height=1.1, seed=20 + k)
    # stacked crates and drums at the pad's far edge (decor), debris in the ravine
    for k in range(3):
        p = pc + V(-pd['radius'] - 2.5, 3.0 - 2.2 * k, 0)
        W.concrete_block(pad, p, 15 * k, 70 + k)
    rv = w.L['ravine']
    for k in range(3):
        p = V(rv['x0'] + 4.0 + 5.0 * k, (rv['z0'] + rv['z1']) / 2 + (k - 1) * 1.2, -rv['depth'] + 0.1)
        slab(pad, p, (2.2, 1.2, 0.5), P['concrete_dk'], M_=R('Z', 30 * k) @ R('X', 10), seed=80 + k, chip=0.1)
    od = new_obj('AW_Jump_Deco', deco.build(), 'Ramps')
    op = new_obj('AW_Jump_Pad', pad.build(), 'Ramps')
    # the side track: from the main road to the run-up, and from the pad back towards the bunker
    track = LAcc('AW_Jump_Track')
    paths = [[(-15.0, 327.5), (0.0, 316.5), (16.0, 310.5), (25.5, 310.0), (28.0, 318.0)],
             [(28.0, 359.5), (22.0, 363.0), (11.0, 360.5)]]
    for pth in paths:
        pts = [V(x, z, 0.0) for x, z in pth]
        pts = W.A.catmull(pts, 6)
        secs = []
        for i, p in enumerate(pts):
            a_ = pts[max(0, i - 1)]; b_ = pts[min(len(pts) - 1, i + 1)]
            t = (b_ - a_).normalized()
            nrm = V(t.y, -t.x, 0)
            secs.append([p + nrm * 2.4 + V(0, 0, 0.025), p - nrm * 2.4 + V(0, 0, 0.025)])
        vts, fi = [], []
        for i, s_ in enumerate(secs):
            vts += [tuple(s_[0]), tuple(s_[1])]
            if i:
                fi.append((2 * i - 2, 2 * i, 2 * i + 1, 2 * i - 1))
        tf = track.poly(vts, fi, P['asphalt_lt'], sharp=None)
    ot = new_obj('AW_Jump_Track', track.build(), 'Ramps', no_shadow=True)
    return {'jump': (j['x'], j['z']), 'pad': (pd['x'], pd['z'])}


# ================================================================================================ landmarks

def landmarks(w):
    """The plant's landmarks: the cracked cooling tower, the red-white chimney, the pipeline from the workshop over
    the road, lattice pylons with sagging and broken wires, the ruined viaduct (massive piers, surviving spans, gaps).
    Heavy pieces get a simplified far version (LOD) at export."""
    lm = w.L['landmarks']
    out = {}
    t = lm['tower']
    ta = LAcc('AW_CoolingTower')
    W.cooling_tower(ta, V(t['x'], t['z'], 0.0), t['rBase'], t['rWaist'], t['rTop'], t['height'], seed=3, crack_az=135.0)
    snow_pillow(ta, V(t['x'], t['z'], 0.0), (t['rBase'] + 1.5, t['rBase'] + 1.5, 0.6), seed=4, surf=P['snow_dirty'], amp=0.4)
    ot = new_obj('AW_CoolingTower', ta.build(), 'ReactorBackdrop')
    tb = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        p = V(t['x'] + math.cos(a) * (t['rBase'] - 0.4), t['z'] + math.sin(a) * (t['rBase'] - 0.4), 3.0)
        tb.append((p, (2 * t['rBase'] * math.tan(math.pi / 8) + 0.3, 1.2, 6.0), math.degrees(math.atan2(math.cos(a), math.sin(a)))))
    add_collider(ot, tb)
    ch = lm['chimney']
    ca = LAcc('AW_Chimney')
    W.striped_chimney(ca, V(ch['x'], ch['z'], 0.0), ch['rBase'], ch['rTop'], ch['height'])
    slab(ca, V(ch['x'], ch['z'], 0.6), (2 * ch['rBase'] + 2.2, 2 * ch['rBase'] + 2.2, 1.2), P['concrete_dk'], seed=6, chip=0.08)
    oc = new_obj('AW_Chimney', ca.build(), 'ReactorBackdrop')
    add_collider(oc, [(V(ch['x'], ch['z'], 3.0), (2 * ch['rBase'] + 1.8, 2 * ch['rBase'] + 1.8, 6.0), 0.0)])
    # the pipeline: out of the workshop's east wall, over the road (5.8 m clear), along the supports to the chimney
    ws = lm['workshop']
    pa = LAcc('AW_Pipeline')
    z0 = ws['z'] - 1.0
    route = [V(ws['x'] + ws['halfX'] - 0.5, z0, 6.4), V(ws['x'] + ws['halfX'] + 3.0, z0, 6.4)]
    sb = []
    for s in lm['pipeSupports']:
        route.append(V(s['x'], s['z'], 6.4))
    route.append(V(ch['x'] - ch['rBase'] - 0.3, ch['z'], 6.4))
    W.pipe(pa, route, 0.62, P['rust'], segs=16, per=2, flanges=(0.15, 0.4, 0.62, 0.85), flange_surf=P['steel_dk'])
    W.pipe(pa, [p + V(0, 1.6, -0.9) for p in route[:-1]], 0.34, P['rust_dk'], segs=12, per=2, flanges=(0.3, 0.7), flange_surf=P['steel_dk'])
    for s in lm['pipeSupports']:
        p = V(s['x'], s['z'], 0)
        for dx in (-0.9, 0.9):
            pa.cyl_between(p + V(dx, 0, 0), p + V(dx * 0.4, 0, 5.8), 0.16, P['rust_or'], 8)
        pa.box((2.6, 1.2, 0.3), T(p + V(0, 0, 5.85)), P['steel_dk'], bevel=0.02)
        slab(pa, p + V(0, 0, 0.3), (2.6, 1.6, 0.6), P['concrete_dk'], seed=int(s['x']), chip=0.05)
        sb.append((p + V(0, 0, 3.0), (2.4, 1.4, 6.0), 0.0))
    snow_tint(pa, list(pa.bm.faces), up=0.6, k=0.8)
    op = new_obj('AW_Pipeline', pa.build(), 'ReactorBackdrop')
    add_collider(op, sb)
    # lattice pylons with sagging wires between them, broken ones hanging
    pyl = LAcc('AW_Pylons')
    pb = []
    pts = [V(p['x'], p['z'], 0.0) for p in lm['pylons']]
    for k, p in enumerate(pts):
        W.lattice_pylon(pyl, p, height=18.0, width=4.2, seed=40 + k)
        slab(pyl, p + V(0, 0, 0.3), (5.2, 5.2, 0.6), P['concrete_dk'], seed=50 + k, chip=0.06)
        pb.append((p + V(0, 0, 2.0), (4.6, 4.6, 4.0), 0.0))
    order = sorted(range(len(pts)), key=lambda i: pts[i].y)
    for i0, i1 in zip(order[:-1], order[1:]):
        A_ = W.arm_points(pts[i0], 18.0, 4.2, 1.2)
        B_ = W.arm_points(pts[i1], 18.0, 4.2, 1.2)
        for k, (a, b) in enumerate(zip(A_, B_)):
            if (i0 + k) % 3 == 2:
                W.broken_wire(pyl, a, 7.0, i0 * 10 + k)
                continue
            W.wire(pyl, a, b, sag=(b - a).length * 0.06)
    oy = new_obj('AW_Pylons', pyl.build(), 'ReactorBackdrop')
    add_collider(oy, pb)
    # the ruined viaduct along the west side: piers, surviving spans, broken stubs over the gaps, fallen chunks
    vd = lm['viaduct']
    va = LAcc('AW_Viaduct')
    vb = []
    top_z = 8.4
    for k, z in enumerate(vd['piers']):
        W.viaduct_pier(va, V(vd['x'], z, 0.0), 6.9, 100 + k)
        vb.append((V(vd['x'], z, 3.5), (3.2, 2.4, 7.0), 0.0))
    for k, (z0_, z1_) in enumerate(vd['spans']):
        W.viaduct_span(va, V(vd['x'], z0_, 0.0), V(vd['x'], z1_, 0.0), top_z, seed=120 + k)
    for k, (z0_, z1_) in enumerate(vd['stubs']):
        a = V(vd['x'], z0_, 0.0); b = V(vd['x'], z1_, 0.0)
        W.viaduct_span(va, a, b, top_z - 0.4 * (k + 1), seed=140 + k, stub=True)
        for j in range(3):
            p = b + V((j - 1) * 2.4, 3.0 + 1.6 * j, 0.0)
            slab(va, p + V(0, 0, 0.5), (2.6, 2.0, 1.0), P['concrete'], M_=R('Z', 25 * j) @ R('X', 12), seed=150 + k * 3 + j, chip=0.15)
            snow_pillow(va, p + V(0, 0, 1.0), (1.0, 0.8, 0.12), seed=160 + j, surf=P['snow'])
    ov = new_obj('AW_Viaduct', va.build(), 'ReactorBackdrop')
    add_collider(ov, vb)
    out.update({'tower': (t['x'], t['z']), 'pylons': len(pts), 'viaduct_piers': len(vd['piers'])})
    return out


# ================================================================================================ borders

def border_massifs(w):
    """The zone's edges as snowy rock massifs over the old wall colliders: west / east along the sides (z 306-512),
    north along z = 500 either side of the gate. Burnt trees on the crests. The wall colliders stay the boundary."""
    out = []
    specs = [('AW_Massif_W', 'x', (-118.0, -93.0), (306.0, 512.0), 1.0),
             ('AW_Massif_E', 'x', (93.0, 118.0), (306.0, 512.0), -1.0),
             ('AW_Massif_NW', 'z', (493.0, 507.0), (-112.0, 4.0), 1.0),
             ('AW_Massif_NE', 'z', (493.0, 507.0), (24.0, 112.0), 1.0)]
    for name, axis, inner, along, sgn in specs:
        acc = LAcc(name)
        st = 2.0
        na = int((along[1] - along[0]) / st)
        nc = int((inner[1] - inner[0]) / st)

        def hfun(c, s):
            if axis == 'x':
                t = (c - inner[1]) / (inner[0] - inner[1]) if sgn > 0 else (c - inner[0]) / (inner[1] - inner[0])
            else:
                t = (c - inner[0]) / (inner[1] - inner[0])
            n1 = W.smooth_noise3(V(s * 0.06, c * 0.06, 0), 7, 1.0)
            n2 = W.smooth_noise3(V(s * 0.21, c * 0.21, 0), 8, 1.0)
            peak = (10.0 if axis == 'x' else 6.5) + 5.0 * n1
            n3 = W.smooth_noise3(V(s * 0.45, c * 0.45, 0), 9, 1.0)
            hh = peak * math.sin(min(1.0, max(0.0, t)) * math.pi * 0.62) ** 0.6 + (1.4 * n2 + 0.6 * n3) * min(1.0, t * 3)
            return max(-0.1, hh - 0.15 * (t < 0.04))
        verts, faces = [], []
        for i in range(na + 1):
            s_ = along[0] + (along[1] - along[0]) * i / na
            for j in range(nc + 1):
                c_ = inner[0] + (inner[1] - inner[0]) * j / nc
                hh = hfun(c_, s_)
                verts.append(V(c_, s_, hh) if axis == 'x' else V(s_, c_, hh))
        for i in range(na):
            for j in range(nc):
                a0 = i * (nc + 1) + j
                faces.append((a0, a0 + 1, a0 + nc + 2, a0 + nc + 1))
        f = acc.poly([tuple(v) for v in verts], faces, P['rock'], sharp=None)
        acc.bm.normal_update()
        if sum(ff.normal.z for ff in f) < 0:
            bmesh.ops.reverse_faces(acc.bm, faces=f)
            acc.bm.normal_update()
        for ff in f:
            nz = abs(ff.normal.z)
            for lp in ff.loops:
                z = lp.vert.co.z
                k = min(1.0, max(0.0, (nz - 0.55) / 0.35))
                # steep faces: rock broken up by snow streaks and drift tongues (no continuous dark band)
                co = lp.vert.co
                streak = W.smooth_noise3(V(co.x * 0.18, co.y * 0.18, co.z * 0.35), 11, 1.0)
                k = max(k, min(0.75, max(0.0, (streak + 0.05) * 1.6)), 0.55 * max(0.0, 1.0 - z / 1.6))
                base = P['rock_dk'].rgb if nz < 0.7 else P['rock'].rgb
                sn = P['snow'].rgb if z > 2.0 else P['snow_dirty'].rgb
                lp[acc.main.lc] = (base[0] * (1 - k) + sn[0] * k, base[1] * (1 - k) + sn[1] * k, base[2] * (1 - k) + sn[2] * k, 1.0)
        rr = rnd(sum(map(ord, name)))

        def c_of_t(t):
            # t = 0 on the playable side of the massif, 1 at its far side (the same t as hfun)
            if axis == 'x':
                return inner[1] + t * (inner[0] - inner[1]) if sgn > 0 else inner[0] + t * (inner[1] - inner[0])
            return inner[0] + t * (inner[1] - inner[0])
        for k in range(int((along[1] - along[0]) / 13)):
            s_ = along[0] + rr.uniform(0, along[1] - along[0])
            c_ = c_of_t(rr.uniform(0.35, 0.8))
            base = V(c_, s_, hfun(c_, s_) - 0.3) if axis == 'x' else V(s_, c_, hfun(c_, s_) - 0.3)
            W.burnt_tree(acc, base, 500 + k + int(s_), height=rr.uniform(5.0, 8.0))
        for k in range(int((along[1] - along[0]) / 15)):
            s_ = along[0] + rr.uniform(0, along[1] - along[0])
            c_ = c_of_t(rr.uniform(0.08, 0.5))
            base = V(c_, s_, hfun(c_, s_) - 0.8) if axis == 'x' else V(s_, c_, hfun(c_, s_) - 0.8)
            W.rock_outcrop(acc, base, (rr.uniform(3, 5), rr.uniform(3, 5), rr.uniform(2.5, 4.0)), 600 + k)
        o = new_obj(name, acc.build(), 'Terrain')
        out.append(o)
    return {'massifs': len(out)}


# ================================================================================================ scatter

TILE = 25.0


def scatter(w):
    """Burnt forest, rock and concrete outcrops, drifts, wrecks and clutter in the free ground: never on roads,
    spawns, structures or each other. Small pieces are merged per 25 m tile; solid ones get box colliders."""
    rr = rnd(77)
    tiles = {}

    def tile_acc(x, z, kind):
        key = (int((x + 100) // TILE), int((z - 300) // TILE), kind)
        if key not in tiles:
            tiles[key] = (LAcc('AW_%s_%d_%d' % (kind, key[0], key[1])), [])
        return tiles[key]
    counts = {'trees': 0, 'rocks': 0, 'drifts': 0, 'wrecks': 0, 'blocks': 0}

    def try_place(r, tries, **kw):
        for _ in range(tries):
            x = rr.uniform(-92, 92); z = rr.uniform(308, 492)
            if w.free(x, z, r, **kw):
                w.take(x, z, r)
                return x, z
        return None
    # burnt trees in loose groves
    for g in range(44):
        c = try_place(3.0, 60, road_margin=3.0, spawn_margin=2.0)
        if c is None:
            continue
        for k in range(rr.randint(2, 5)):
            x, z = c[0] + rr.uniform(-6, 6), c[1] + rr.uniform(-6, 6)
            if not w.free(x, z, 0.8, road_margin=2.5, spawn_margin=1.5, decor_margin=0.3):
                continue
            w.take(x, z, 0.8)
            acc, boxes = tile_acc(x, z, 'Forest')
            hgt = rr.uniform(4.5, 8.0)
            W.burnt_tree(acc, V(x, z, 0), 1000 + counts['trees'], height=hgt)
            if hgt > 6.0:
                boxes.append((V(x, z, 1.5), (0.6, 0.6, 3.0), 0.0))
            counts['trees'] += 1
    # rock / concrete outcrops
    for k in range(34):
        c = try_place(2.6, 50, road_margin=3.0, spawn_margin=2.0)
        if c is None:
            continue
        acc, boxes = tile_acc(c[0], c[1], 'Rocks')
        s = (rr.uniform(2.2, 3.6), rr.uniform(2.0, 3.2), rr.uniform(1.2, 2.4))
        W.rock_outcrop(acc, V(c[0], c[1], 0), s, 2000 + k, surf=P['concrete_dk'] if k % 3 == 0 else None)
        boxes.append((V(c[0], c[1], s[2] * 0.45), (s[0] * 0.85, s[1] * 0.85, s[2] * 0.9), 0.0))
        counts['rocks'] += 1
    # drifts (low, no colliders)
    for k in range(28):
        c = try_place(2.0, 40, road_margin=1.5, spawn_margin=1.0)
        if c is None:
            continue
        acc, boxes = tile_acc(c[0], c[1], 'Drifts')
        W.snow_drift(acc, V(c[0], c[1], -0.08), (rr.uniform(2.4, 4.4), rr.uniform(1.0, 1.8), rr.uniform(0.16, 0.3)), rr.uniform(0, 180), 3000 + k,
                     surf=P['snow_dirty'])
        counts['drifts'] += 1
    # wrecks: cars and a truck (static, solid)
    wa = LAcc('AW_Wrecks')
    wboxes = []
    for k, kind in enumerate(['car'] * 5 + ['truck']):
        r = 2.6 if kind == 'car' else 5.0
        c = try_place(r, 80, road_margin=2.5, spawn_margin=2.0)
        if c is None:
            continue
        yaw = rr.uniform(0, 360)
        W.car_wreck(wa, V(c[0], c[1], -0.05), yaw, 4000 + k, kind)
        wboxes.append((V(c[0], c[1], 0.9), (2.0, 4.3, 1.8) if kind == 'car' else (2.8, 8.0, 3.4), yaw))
        counts['wrecks'] += 1
    # concrete blocks and drums
    for k in range(26):
        c = try_place(1.2, 40, road_margin=2.0, spawn_margin=1.5)
        if c is None:
            continue
        acc, boxes = tile_acc(c[0], c[1], 'Blocks')
        yaw = rr.uniform(0, 180)
        W.concrete_block(acc, V(c[0], c[1], 0), yaw, 5000 + k)
        boxes.append((V(c[0], c[1], 0.4), (1.6, 1.0, 0.8), yaw))
        counts['blocks'] += 1
    # small debris (no colliders): charred stumps, concrete chunks with rebar, ash patches
    counts['debris'] = 0
    for k in range(90):
        c = try_place(0.7, 30, road_margin=1.0, spawn_margin=0.8, decor_margin=0.3)
        if c is None:
            continue
        acc, boxes = tile_acc(c[0], c[1], 'Debris')
        kind = k % 3
        if kind == 0:
            h = rr.uniform(0.5, 1.4)
            W.limb(acc, [V(c[0], c[1], -0.1), V(c[0] + rr.uniform(-0.1, 0.1), c[1] + rr.uniform(-0.1, 0.1), h * 0.6), V(c[0], c[1], h)],
                   [0.22, 0.18, 0.12], P['bark_char'], segs=6, per=2)
            W.snow_pillow(acc, V(c[0], c[1], 0.0), (0.45, 0.45, 0.1), seed=6000 + k, surf=P['ash'])
        elif kind == 1:
            slab(acc, V(c[0], c[1], 0.2), (rr.uniform(0.6, 1.2), rr.uniform(0.5, 0.9), 0.4), P['concrete_dk'],
                 M_=R('Z', rr.uniform(0, 180)) @ R('X', rr.uniform(-15, 15)), seed=6100 + k, chip=0.06, segs=6, rings=4)
            W.A.rebar(acc, V(c[0], c[1], 0.35), V(rr.uniform(-0.5, 0.5), rr.uniform(-0.5, 0.5), 1), 0.5, r=0.02, surf=P['rust_dk'])
        else:
            W.snow_pillow(acc, V(c[0], c[1], -0.06), (rr.uniform(1.0, 2.2), rr.uniform(0.8, 1.6), 0.05), R('Z', rr.uniform(0, 180)),
                          seed=6200 + k, surf=P['ash'], amp=0.15)
        counts['debris'] += 1
    for (key, (acc, boxes)) in tiles.items():
        cname = 'BurntForest' if key[2] in ('Forest', 'Debris') else 'Wrecks' if key[2] == 'Blocks' else 'Props' if key[2] == 'Rocks' else 'Terrain'
        o = new_obj(acc.name, acc.build(), cname, no_shadow=(key[2] in ('Drifts', 'Debris')))
        if boxes:
            add_collider(o, boxes)
    if wboxes:
        o = new_obj('AW_Wrecks', wa.build(), 'Wrecks')
        add_collider(o, wboxes)
    return counts


# ================================================================================================ dev spawns

def dev_spawns(w):
    """Markers of the DEV menu's safe arrival points (the repair pads the game also respawns the car on). Not
    exported: Unity uses the world's stations."""
    c = coll('DevSpawns')
    n = 0
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.split('.')[0] == 'Pad' and o.get('unity_id'):
            e = bpy.data.objects.new('DevSpawn_Zone3_AshenWinter', None)
            e.empty_display_type = 'SINGLE_ARROW'
            e.empty_display_size = 3.0
            bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
            e.location = sum(bb, Vector()) / 8
            e['tw_no_export'] = True
            e['aw_note'] = 'DEV «Локации» -> Зона 3: the car arrives on this repair pad, heading north'
            c.objects.link(e)
            n += 1
    return {'dev_spawns': n}
