"""Toxic Wetlands borders: overgrown berms along the side walls, a levee on the north wall, the south flood dam.

* West / east: the generated rock walls (Cliff.005 / .006) keep their colliders; the visible wall becomes an earth
  berm whose toe sits on the old rock line (x = -92.9 / +91.6), with stretches of concrete flood wall, outlet pipes,
  dead trees on the crest and moss.
* North (z = 300, Cliff.016 / .017 swapped in place, colliders kept): a lower levee with a concrete face; the gate
  to the third zone stays in the gap between them.
* South (z ~ 104.6): the first zone's v13 perimeter plateau is cut back at z = 104.5 in Unity (ImportedLevel.ClipNorth)
  and this concrete dam hides the cut. Its height follows the plateau's height along the cut (+0.8 m), its gate gap
  is the road's (x 12.4..31.6), a sluice lets the Dust Flats river into the swamp, and box colliders close it.
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


def vnoise1(x, seed, scale):
    """Smooth 1D value noise in [-1, 1]."""
    g = x / scale
    i = math.floor(g)
    f = g - i

    def h(n):
        n = (n * 374761393 + seed * 668265263) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 32767.5 - 1.0
    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


BERM = {
    'toe': '#2F2D1F', 'mud': '#4A4532', 'bank': '#56582F', 'moss': '#5B6631', 'crest': '#6A723A', 'dark': '#3C4426',
}
BC = {k: np.array(L.hexlin(v)) for k, v in BERM.items()}


def berm_mesh(name, along, toe, outward, seed, h_mid=6.4, depth=27.0, back_to=2.2, step=1.0):
    """Heightfield strip. along: (a0, a1) Blender range of the wall direction; toe(a) -> coordinate of the toe;
    outward: +1 / -1 direction across; the strip is built with axis 'x' across when along runs on y."""
    ds = [0.0, 0.35, 0.8, 1.4, 2.1, 2.9, 3.8, 4.9, 6.2, 7.8, 9.8, 12.2, 15.0, 18.5, 22.5, depth]
    a0, a1 = along
    rows = int(round((a1 - a0) / step)) + 1
    co, cols, gls = [], [], []
    for i in range(rows):
        a = a0 + i * step
        t = toe(a)
        H = h_mid + 1.3 * vnoise1(a, seed, 23.0) + 0.6 * vnoise1(a, seed + 3, 7.0)
        for d in ds:
            rise = (1.0 - math.exp(-d / 2.1)) ** 1.5
            h = H * rise
            if d > 11.0:
                h = H + (back_to - H) * min(1.0, (d - 11.0) / (depth - 11.0)) ** 1.2
            h += 0.35 * vnoise1(a * 1.7 + d * 3.1, seed + 11, 3.0) * min(1.0, d / 2.0)
            co.append((t + outward * d, a, h - (0.12 if d == 0.0 else 0.0)))
            n = 0.5 + 0.5 * vnoise1(a * 0.9 + d * 1.3, seed + 5, 4.0)
            if h < 0.45:
                c = BC['toe'] * (1 - h / 0.45) + BC['mud'] * (h / 0.45)
                g = 0.35
            elif h < 2.4:
                k = (h - 0.45) / 1.95
                c = BC['mud'] * (1 - k) + BC['bank'] * k
                g = 0.12
            else:
                c = BC['moss'] * (1 - n) + BC['crest'] * n
                if n < 0.25:
                    c = c * 0.6 + BC['dark'] * 0.4
                g = 0.05
            cols.append(c * (0.9 + 0.2 * n))
            gls.append(g)
    nd = len(ds)
    faces = []
    for i in range(rows - 1):
        for j in range(nd - 1):
            v0 = i * nd + j
            q = (v0, v0 + 1, v0 + nd + 1, v0 + nd)
            faces.append(q if outward > 0 else q[::-1])
    me = bpy.data.meshes.new(name)
    me.from_pydata(co, [], faces)
    me.update()
    if np.mean([p.normal.z for p in me.polygons]) < 0:
        for p in me.polygons:
            p.flip()
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv0 = me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    C = np.ones((len(co), 4), np.float32); C[:, :3] = np.array(cols)
    ca.data.foreach_set('color', C[lv].ravel())
    P = np.zeros((len(co), 2), np.float32); P[:, 0] = gls
    uv1.data.foreach_set('uv', P[lv].ravel())
    U = np.array([(c[0] / 36.0, c[1] / 36.0) for c in co], np.float32)
    uv0.data.foreach_set('uv', U[lv].ravel())
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(L.get_material('TW_GroundMud'))
    return me


def flood_walls(name, along, toe, outward, seed, axis='x', h=(2.4, 3.3), offset=1.15, every=14.0, length=(9.0, 15.0)):
    """Concrete flood-wall stretches in front of a berm: buttresses, coping, outlet pipes with toxic trickles."""
    a = Acc(name)
    r = rnd(seed)
    pos = along[0] + 4.0
    while pos < along[1] - 6.0:
        L_ = r.uniform(*length)
        if r.random() < 0.72:
            H = r.uniform(*h)
            mid = pos + L_ / 2
            t = toe(mid) + outward * offset

            def P(u, d, z):
                return V(t + outward * d, u, z) if axis == 'x' else V(u, t + outward * d, z)
            yaw = 90.0 if axis == 'x' else 0.0
            a.box((L_, 0.55, H), T(P(mid, 0.25, H / 2 - 0.15)) @ R('Z', yaw), E['concrete'], bevel=0.08)
            a.box((L_ + 0.2, 0.75, 0.22), T(P(mid, 0.25, H - 0.05)) @ R('Z', yaw), E['concrete_dk'], bevel=0.06)
            for k in range(int(L_ / 3.0) + 1):
                u = pos + k * L_ / max(1, int(L_ / 3.0))
                a.box((0.45, 0.9, H * 0.9), T(P(u, -0.1, H * 0.45 - 0.15)) @ R('Z', yaw), E['concrete_dk'], bevel=0.08)
            if r.random() < 0.65:
                u = pos + r.uniform(1.5, L_ - 1.5)
                z0 = r.uniform(0.7, 1.4)
                p0, p1 = P(u, 0.9, z0), P(u, -0.6, z0)
                a.cyl_between(p0, p1, 0.32, E['rust'], segs=12)
                a.cyl(0.38, 0.1, T(p1) @ ((p1 - p0).normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()), E['steel_dk'], segs=12, bevel=0.02)
                a.tube([p1 + V(0, 0, -0.15), p1 + (p1 - p0).normalized() * 0.3 + V(0, 0, -0.5), P(u, -1.2, 0.02)], [0.12, 0.09, 0.06], E['toxic'], segs=6)
                a.cyl(0.8, 0.015, T(P(u, -1.6, 0.0)), E['toxic_goo'], segs=14)
            for k in range(3):
                u = pos + r.uniform(0.5, L_ - 0.5)
                ln = r.uniform(0.6, 1.4)
                a.tube([P(u, -0.05, H), P(u, -0.12, H - ln * 0.5), P(u, -0.08, H - ln)], [0.05, 0.04, 0.0], E['algae_dk'], segs=4, flat=0.6)
        pos += L_ + r.uniform(3.0, every)
    return a.build()


def crest_trees(name_prefix, along, toe, outward, seed, axis='x', spacing=9.0, d_range=(5.5, 11.0), h_of=None):
    """Dead trees on the berm crest (kit meshes shared)."""
    r = rnd(seed)
    trees = [EV.dead_tree(300 + k, height=r.uniform(4.5, 7.0), broken=(k % 3 == 2)) for k in range(4)]
    out = []
    pos = along[0] + r.uniform(0, spacing)
    k = 0
    while pos < along[1]:
        d = r.uniform(*d_range)
        t = toe(pos) + outward * d
        z = h_of(pos, d) if h_of else 5.5
        loc = (t, pos, z - 0.2) if axis == 'x' else (pos, t, z - 0.2)
        o = new_obj('%s_%03d' % (name_prefix, k), trees[k % 4])
        o.location = loc
        o.rotation_euler = (0, 0, r.uniform(0, 6.28))
        s = r.uniform(0.85, 1.2)
        o.scale = (s, s, s)
        out.append(o)
        pos += spacing * r.uniform(0.6, 1.4)
        k += 1
    return out


def side_berms(sc):
    rep = {}
    for side, toe_x, out, path_name, seed in (('W', -92.9, -1.0, 'Cliff.005', 501), ('E', 91.6, 1.0, 'Cliff.006', 601)):
        cliffs = [o for o in bpy.data.objects if o.name == path_name]
        toe = (lambda a, tx=toe_x, s=seed: tx + (-0.25 if tx > 0 else 0.25) * (1 + vnoise1(a, s + 9, 11.0)) * 0.5)
        me = berm_mesh('TW_Berm' + side, (96.0, 304.0), toe, out, seed)
        bo = new_obj('TW_Berm' + side, me)
        walls = flood_walls('TW_FloodWall' + side, (100.0, 300.0), toe, out, seed + 1, axis='x')
        for ch in split_by_x(walls, 'TW_FloodWall' + side, 40.0, axis=1):
            new_obj(ch.name, ch)
        crest_trees('TW_BermTree' + side, (100.0, 300.0), toe, out, seed + 2, axis='x', spacing=5.0,
                    h_of=lambda a, d, s=seed: 6.4 + 1.3 * vnoise1(a, s, 23.0) + 0.6 * vnoise1(a, s + 3, 7.0) - 0.6)
        for o in cliffs:
            o['tw_hidden'] = True
            o['tw_stage'] = 'hidden: replaced by TW_Berm%s (its rock hull colliders stay as the boundary)' % side
            o.hide_render = True; o.hide_viewport = True
        rep[side] = {'tris': L.tri_count(me), 'walls': L.tri_count(walls)}
    return rep


def north_levee(sc):
    rep = {}
    for path_name, (x0, x1), seed in (('Cliff.016', (-104.0, -35.6), 701), ('Cliff.017', (-16.4, 104.0), 711)):
        o = bpy.data.objects.get(path_name)
        if o is None:
            continue
        toe = (lambda a, s=seed: 294.1 - 0.2 * (1 + vnoise1(a, s, 9.0)) * 0.5)
        # levee: along x, outward +y (north); built with axis swap
        ds = [0.0, 0.35, 0.8, 1.5, 2.4, 3.4, 4.6, 6.0, 7.6, 9.4, 11.5]
        co, faces, cols = [], [], []
        rows = int(round(x1 - x0)) + 1
        for i in range(rows):
            x = x0 + i * (x1 - x0) / (rows - 1)
            H = 4.3 + 0.5 * vnoise1(x, seed, 15.0)
            for d in ds:
                if d <= 6.0:
                    h = H * (1.0 - math.exp(-d / 1.5)) ** 1.4
                else:
                    h = H * (1.0 - (d - 6.0) / 5.5) ** 1.3
                h = max(0.0, h)
                co.append((x, toe(x) + d, h - (0.1 if d in (0.0, ds[-1]) else 0.0)))
                n = 0.5 + 0.5 * vnoise1(x * 0.8 + d * 1.1, seed + 3, 4.0)
                c = BC['mud'] if h < 1.0 else (BC['moss'] * (1 - n) + BC['crest'] * n)
                cols.append(c * (0.9 + 0.2 * n))
        nd = len(ds)
        for i in range(rows - 1):
            for j in range(nd - 1):
                v0 = i * nd + j
                faces.append((v0, v0 + nd, v0 + nd + 1, v0 + 1))
        me = bpy.data.meshes.new('TW_Levee_' + path_name)
        me.from_pydata(co, [], faces)
        me.update()
        if np.mean([p.normal.z for p in me.polygons]) < 0:
            for p in me.polygons:
                p.flip()
        ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
        me.uv_layers.new(name='UVMap')
        uv1 = me.uv_layers.new(name='Unity_MaterialParams')
        lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
        Cc = np.ones((len(co), 4), np.float32); Cc[:, :3] = np.array(cols)
        ca.data.foreach_set('color', Cc[lv].ravel())
        P = np.zeros((len(co), 2), np.float32); P[:, 0] = 0.06
        uv1.data.foreach_set('uv', P[lv].ravel())
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(L.get_material('TW_GroundMud'))
        me.transform(o.matrix_world.inverted())
        L.swap_mesh(o, me, 'swamp levee (rock hull colliders kept)')
        walls = flood_walls('TW_LeveeWall_' + path_name, (x0, x1), toe, 1.0, seed + 1, axis='y', h=(2.6, 3.4), offset=1.0)
        new_obj('TW_LeveeWall_' + path_name, walls)
        rep[path_name] = L.tri_count(me)
    return rep


def south_dam(sc, profile):
    """profile: numpy array of the clipped plateau height at x = -120..119 (1 m)."""
    a = Acc('TW_SouthDam')
    r = rnd(801)
    face_y = 104.6
    spans = [(-100.0, 12.4), (31.6, 100.0)]
    boxes = []
    seg = 6.0
    for (x0, x1) in spans:
        x = x0
        while x < x1 - 0.01:
            w = min(seg, x1 - x)
            xs = np.arange(int(math.floor(x)), int(math.ceil(x + w)) + 1)
            hh = max(profile[int(np.clip(xi + 120, 0, 239))] for xi in xs)
            H = max(3.6, math.ceil((hh + 0.8) * 2) / 2)
            cx = x + w / 2
            a.box((w, 1.8, H), T(V(cx, face_y - 0.9, H / 2 - 0.2)), E['concrete'], bevel=0.1)
            a.box((w + 0.05, 0.4, 0.9), T(V(cx, face_y + 0.02, 0.3)), S('#FFFFFF', 0.06, strip='concrete'), bevel=0.06)
            a.box((w + 0.1, 2.2, 0.35), T(V(cx, face_y - 0.95, H - 0.05)), E['concrete_dk'], bevel=0.08)
            a.box((0.9, 0.65, H * 0.96), T(V(x + 0.02, face_y + 0.3, H * 0.48 - 0.2)), E['concrete_dk'], bevel=0.1)
            if r.random() < 0.6:
                mw = w * r.uniform(0.4, 0.9)
                a.box((mw, 1.6, 0.1), T(V(cx + r.uniform(-0.5, 0.5), face_y - 0.95, H + 0.15)), E['moss_flat'], bevel=0.04, segs=2)
                a.tube([V(cx - mw * 0.3, face_y + 0.02, H + 0.1), V(cx - mw * 0.3, face_y + 0.06, H - 0.6)], [0.12, 0.0], E['moss_flat'], segs=5, flat=0.5)
            if r.random() < 0.55 and H > 4.0:
                z0 = r.uniform(1.2, min(3.2, H - 1.0))
                px = cx + r.uniform(-w * 0.3, w * 0.3)
                p0, p1 = V(px, face_y - 0.5, z0), V(px, face_y + 0.8, z0)
                a.cyl_between(p0, p1, 0.36, E['rust'], segs=12)
                a.cyl(0.44, 0.12, T(p1) @ R('X', -90), E['steel_dk'], segs=12, bevel=0.02)
                a.tube([p1 + V(0, 0.1, -0.2), p1 + V(0, 0.45, -0.6), V(px, face_y + 1.3, 0.02)], [0.14, 0.1, 0.07], E['toxic'], segs=6)
                a.cyl(1.0, 0.015, T(V(px, face_y + 1.9, 0.0)) @ SC(1.0, 0.8, 1.0), E['toxic_goo'], segs=14)
            for k in range(2):
                u = x + r.uniform(0.4, w - 0.4)
                ln = r.uniform(0.8, 2.0)
                a.tube([V(u, face_y + 0.04, H - 0.2), V(u, face_y + 0.1, H - ln * 0.5), V(u, face_y + 0.08, H - ln)], [0.06, 0.05, 0.0], E['algae_dk'], segs=4, flat=0.6)
            boxes.append((V(cx, face_y - 0.2, H / 2), (w, 1.8, H + 0.5), 0.0))
            x += w
        # end pillars at the road gap / edges
        for xe in (x0, x1):
            if abs(xe) < 99.0:
                a.box((1.4, 2.6, 7.2), T(V(xe + (0.7 if xe == x0 else -0.7), face_y - 0.6, 3.4)), E['concrete_dk'], bevel=0.12)
                a.box((1.5, 2.7, 0.6), T(V(xe + (0.7 if xe == x0 else -0.7), face_y - 0.6, 1.0)), E['hazard'], bevel=0.08)
    # sluice where the Dust Flats river reaches the dam (x ~ -35)
    sx = -35.0
    for s in (-1.6, 1.6):
        a.box((0.5, 0.6, 5.5), T(V(sx + s, face_y + 0.35, 2.6)), E['steel_dk'], bevel=0.05)
    a.box((2.8, 0.25, 3.2), T(V(sx, face_y + 0.25, 2.2)), E['rust'], bevel=0.04)
    a.box((2.9, 0.3, 0.3), T(V(sx, face_y + 0.3, 3.85)), E['hazard'], bevel=0.04)
    a.lathe([(0.45, -0.04), (0.55, -0.06), (0.58, 0.0), (0.55, 0.06), (0.45, 0.04), (0.45, -0.04)], 18,
            T(V(sx, face_y + 0.6, 5.6)) @ R('X', 90), E['red'], cap_bottom=False, cap_top=False)
    a.tube([V(sx, face_y + 0.4, 0.6), V(sx + 0.3, face_y + 1.6, 0.15), V(sx - 0.2, face_y + 3.5, 0.03)], [0.6, 0.55, 0.5], E['toxic_goo'], segs=8, flat=0.25)
    me = a.build()
    dam_tris = L.tri_count(me)
    chunks = split_by_x(me, 'TW_SouthDam', 32.0)
    for ch in chunks:
        o = new_obj(ch.name, ch)
        x0c = float(ch['tw_x0']); x1c = float(ch['tw_x1'])
        add_collider(o, [b for b in boxes if x0c <= b[0].x < x1c], ch.name)
    bpy.data.meshes.remove(me)
    # the old desert wall segment east of Gate1 hides behind the dam (its colliders stay)
    c15 = bpy.data.objects.get('Cliff.015')
    if c15 is not None:
        c15['tw_hidden'] = True
        c15['tw_stage'] = 'hidden behind TW_SouthDam (colliders kept)'
        c15.hide_render = True; c15.hide_viewport = True
    return {'tris': dam_tris, 'chunks': len(chunks), 'collider_boxes': len(boxes)}


def split_by_x(me, name, size, axis=0):
    """Split a mesh into chunks along one axis by face centre (frustum culling for 200 m long borders)."""
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(me)
    keys = {}
    for f in bm.faces:
        c = f.calc_center_median()[axis]
        keys.setdefault(int(math.floor(c / size)), []).append(f.index)
    out = []
    for k in sorted(keys):
        b2 = bm.copy()
        b2.faces.ensure_lookup_table()
        keep = set(keys[k])
        _bm.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
        loose = [v for v in b2.verts if not v.link_faces]
        if loose:
            _bm.ops.delete(b2, geom=loose, context='VERTS')
        m2 = bpy.data.meshes.new('%s_%02d' % (name, len(out)))
        b2.to_mesh(m2); b2.free()
        for mat in me.materials:
            m2.materials.append(mat)
        m2['tw_x0'] = k * size
        m2['tw_x1'] = (k + 1) * size
        out.append(m2)
    bm.free()
    return out


def build(sc, profile):
    rep = {'side': side_berms(sc), 'north': north_levee(sc), 'south': south_dam(sc, profile)}
    print('TW_BORDERS', rep, flush=True)
    return rep
