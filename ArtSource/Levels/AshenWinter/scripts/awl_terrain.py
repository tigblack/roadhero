"""Ashen Winter terrain: snow-and-ash ground tiles and the zone's hills / bump rows.

Ground comes from the layout grid (data/AshenWinter_surfaces.bytes, written by awl_layout.py), the same grid Unity
samples for the ground height (AshenSurfaces): 25 m tiles for frustum culling, 5 m cells on flat ground (a fan that
takes every 1 m edge vertex of a finer neighbour: no T-junctions) and a 1 m grid in cells with the ravine.
Colour (vertex colours times a world-projected detail map): dirty milky snow with drifts of graphite ash and a few
black charred patches, grey slush along the roads, a dark ash floor in the ravine. Hills and bump rows are rebuilt
from Unity's MoundPiece formula (h = top (1 - t^2)^2) as snow mounds with ash on the lee side.
"""
import math
import os
import struct

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

import tw_lib as L
import awl_lib as W
from tw_terrain import vnoise, sstep

TILE = 25.0
ZX0, ZX1, ZZ0, ZZ1 = -100.0, 100.0, 300.0, 500.0
CELL, FINE = 5.0, 1.0

GP = {k: np.array(L.hexlin(v)) for k, v in {
    'snow': '#C9CCD2', 'snow_shade': '#AEB2BA', 'ash': '#5C5E62', 'ash_dk': '#3A3B3E', 'char': '#2C2C2E',
    'slush': '#8D8F93', 'track': '#6E7074', 'bed': '#3B3C3F'}.items()}


def load_grid(data_dir):
    b = open(os.path.join(data_dir, 'AshenWinter_surfaces.bytes'), 'rb').read()
    nx, nz, x0, z0, step = struct.unpack('<iifff', b[4:24])
    h = np.frombuffer(b[24:24 + 2 * nx * nz], '<i2').reshape(nz, nx).astype(np.float64) / 1000.0
    return dict(nx=nx, nz=nz, x0=x0, z0=z0, step=step, h=h)


def sample(g, x, z):
    fx = np.clip((np.asarray(x) - g['x0']) / g['step'], 0, g['nx'] - 1.000001)
    fz = np.clip((np.asarray(z) - g['z0']) / g['step'], 0, g['nz'] - 1.000001)
    ix, iz = np.floor(fx).astype(int), np.floor(fz).astype(int)
    tx, tz = fx - ix, fz - iz
    arr = g['h']
    a = arr[iz, ix]; c = arr[iz, ix + 1]; d = arr[iz + 1, ix]; e = arr[iz + 1, ix + 1]
    out = (a * (1 - tx) + c * tx) * (1 - tz) + (d * (1 - tx) + e * tx) * tz
    inside = (np.asarray(x) >= g['x0']) & (np.asarray(x) <= g['x0'] + (g['nx'] - 1) * g['step']) & \
             (np.asarray(z) >= g['z0']) & (np.asarray(z) <= g['z0'] + (g['nz'] - 1) * g['step'])
    return np.where(inside, out, 0.0)


def road_distance(md, x, z, zone=2):
    d = np.full(np.shape(x), 1e9)
    for r in md['roads']:
        if r['zone'] != zone:
            continue
        p = np.array(r['points']).reshape(-1, 3)
        for (ax, _, az), (bx, _, bz) in zip(p[:-1], p[1:]):
            vx, vz = bx - ax, bz - az
            L2 = max(vx * vx + vz * vz, 1e-9)
            t = np.clip(((x - ax) * vx + (z - az) * vz) / L2, 0, 1)
            d = np.minimum(d, np.hypot(x - ax - t * vx, z - az - t * vz) - r['width'] / 2)
    return d


def ground_colour(g, md, layout, x, z):
    h = sample(g, x, z)
    n1 = vnoise(x, z, 23.0, 11)
    n2 = vnoise(x, z, 7.5, 12)
    n3 = vnoise(x, z, 41.0, 13)
    col = GP['snow'][None, :] * (0.95 + 0.08 * n3)[:, None]
    shade = sstep(0.55, 0.85, n2) * 0.5
    col = col * (1 - shade[:, None]) + GP['snow_shade'][None, :] * shade[:, None]
    n4 = vnoise(x, z, 3.2, 14)
    # ash drifts: wider toward the reactor (north), where the soot fell thickest (the concept's greyer far plain)
    north = sstep(380.0, 490.0, z)
    ash = sstep(0.56 - 0.08 * north, 0.78 - 0.06 * north, n1 * 0.45 + n2 * 0.35 + n4 * 0.2)
    col = col * (1 - ash[:, None] * 0.75) + GP['ash'][None, :] * (ash[:, None] * 0.75)
    haze = north * 0.22
    col = col * (1 - haze[:, None]) + GP['ash'][None, :] * haze[:, None]
    fleck = sstep(0.72, 0.86, n4) * 0.35
    col = col * (1 - fleck[:, None]) + GP['ash_dk'][None, :] * fleck[:, None]
    char = sstep(0.84, 0.93, n1) * ash
    col = col * (1 - char[:, None] * 0.7) + GP['char'][None, :] * (char[:, None] * 0.7)
    rd = road_distance(md, x, z)
    slush = sstep(4.5, 0.4, rd)
    col = col * (1 - slush[:, None] * 0.75) + GP['slush'][None, :] * (slush[:, None] * 0.75)
    # slush round the arena and the jump pad, the bunker approaches (worn by traffic)
    a = layout['arena']
    da = np.hypot(x - a['x'], z - a['z']) - a['radius']
    ring_ = sstep(6.0, 0.0, np.abs(da))
    col = col * (1 - ring_[:, None] * 0.45) + GP['track'][None, :] * (ring_[:, None] * 0.45)
    bed = sstep(-0.15, -0.6, h)
    col = col * (1 - bed[:, None] * 0.85) + GP['bed'][None, :] * (bed[:, None] * 0.85)
    gloss = 0.05 + 0.18 * slush
    return col, gloss


def set_attrs(me, col, gloss, x, z):
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv0 = me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    C = np.ones((len(x), 4), np.float32)
    C[:, :3] = col
    ca.data.foreach_set('color', C[lv].ravel())
    P_ = np.zeros((len(x), 2), np.float32)
    P_[:, 0] = gloss
    uv1.data.foreach_set('uv', P_[lv].ravel())
    U = np.stack([x / 36.0, z / 36.0], 1).astype(np.float32)
    uv0.data.foreach_set('uv', U[lv].ravel())
    for p in me.polygons:
        p.use_smooth = True


def build_ground(g, md, layout, coll):
    """Crack-free ground tiles (see the module doc); returns the new objects."""
    out = []
    mat = L.get_material(W.GROUND)
    ncx = int(round((ZX1 - ZX0) / CELL)); ncz = int(round((ZZ1 - ZZ0) / CELL))
    fine = np.zeros((ncz, ncx), bool)
    gx0, gz0 = g['x0'], g['z0']
    gx1, gz1 = gx0 + (g['nx'] - 1) * g['step'], gz0 + (g['nz'] - 1) * g['step']
    off = np.linspace(-0.5, CELL + 0.5, 12)
    OX, OZ = np.meshgrid(off, off)
    for cj in range(ncz):
        for ci in range(ncx):
            x0c, z0c = ZX0 + ci * CELL, ZZ0 + cj * CELL
            if x0c + CELL < gx0 - 1 or x0c > gx1 + 1 or z0c + CELL < gz0 - 1 or z0c > gz1 + 1:
                continue
            fine[cj, ci] = np.abs(sample(g, (x0c + OX).ravel(), (z0c + OZ).ravel())).max() > 1e-4
    k = int(round(CELL / FINE))
    cpt = int(round(TILE / CELL))
    tri = 0
    for tj in range(ncz // cpt):
        for ti in range(ncx // cpt):
            vid = {}
            vxz = []
            faces = []

            def lattice(i, j):
                key = ('L', i, j)
                if key not in vid:
                    vid[key] = len(vxz)
                    vxz.append((ZX0 + i * FINE, ZZ0 + j * FINE))
                return vid[key]

            def centre(ci, cj):
                key = ('C', ci, cj)
                if key not in vid:
                    vid[key] = len(vxz)
                    vxz.append((ZX0 + (ci + 0.5) * CELL, ZZ0 + (cj + 0.5) * CELL))
                return vid[key]

            def is_fine(ci, cj):
                return 0 <= ci < ncx and 0 <= cj < ncz and fine[cj, ci]
            for cj in range(tj * cpt, (tj + 1) * cpt):
                for ci in range(ti * cpt, (ti + 1) * cpt):
                    i0, j0 = ci * k, cj * k
                    if fine[cj, ci]:
                        for j in range(k):
                            for i in range(k):
                                faces.append((lattice(i0 + i, j0 + j), lattice(i0 + i + 1, j0 + j),
                                              lattice(i0 + i + 1, j0 + j + 1), lattice(i0 + i, j0 + j + 1)))
                        continue
                    ring_ = []
                    for i in (range(k) if is_fine(ci, cj - 1) else (0,)):
                        ring_.append(lattice(i0 + i, j0))
                    for j in (range(k) if is_fine(ci + 1, cj) else (0,)):
                        ring_.append(lattice(i0 + k, j0 + j))
                    for i in (range(k) if is_fine(ci, cj + 1) else (0,)):
                        ring_.append(lattice(i0 + k - i, j0 + k))
                    for j in (range(k) if is_fine(ci - 1, cj) else (0,)):
                        ring_.append(lattice(i0, j0 + k - j))
                    if len(ring_) == 4:
                        faces.append(tuple(ring_))
                    else:
                        c = centre(ci, cj)
                        for a in range(len(ring_)):
                            faces.append((c, ring_[a], ring_[(a + 1) % len(ring_)]))
            xz = np.array(vxz)
            x, z = xz[:, 0], xz[:, 1]
            hgt = sample(g, x, z)
            col, gloss = ground_colour(g, md, layout, x, z)
            name = f'AW_Ground_{ti}_{tj}'
            me = bpy.data.meshes.new(name)
            me.from_pydata([(float(a), float(b), float(c)) for a, b, c in zip(x, z, hgt)], [], faces)
            me.update()
            set_attrs(me, col, gloss, x, z)
            me.materials.append(mat)
            o = L.new_object(name, me, coll)
            o['tw_role'] = 'ground'
            o['editing_zone'] = 2
            tri += L.tri_count(me)
            out.append(o)
    # aprons behind the side walls (flat, coarse) up to the edge of the far view
    for side, (a, b) in (('W', (-175.0, -100.0)), ('E', (100.0, 175.0))):
        xs = np.linspace(a, b, 16)
        zs = np.linspace(ZZ0, ZZ1, 41)
        X, Z = np.meshgrid(xs, zs)
        x, z = X.ravel(), Z.ravel()
        faces = []
        for j in range(len(zs) - 1):
            for i in range(len(xs) - 1):
                q = j * len(xs) + i
                faces.append((q, q + 1, q + 1 + len(xs), q + len(xs)))
        me = bpy.data.meshes.new('AW_Ground_Apron' + side)
        me.from_pydata([(float(a_), float(b_), -0.02) for a_, b_ in zip(x, z)], [], faces)
        me.update()
        col, gloss = ground_colour(g, md, layout, x, z)
        set_attrs(me, col, gloss, x, z)
        me.materials.append(mat)
        o = L.new_object('AW_Ground_Apron' + side, me, coll)
        o['editing_zone'] = 2
        out.append(o)
        tri += L.tri_count(me)
    print('AWL_TERRAIN ground tiles', len(out), 'tris', tri, 'fine cells', int(fine.sum()), 'of', fine.size, flush=True)
    return out


def build_mound(fl, kind, seed):
    """A hill / bump from the MoundPiece formula, as a snow mound: bright crest, grey snow on the slopes, ash on the
    lee side and the toe (world coordinates; the v10 objects sit at the origin with identity transforms)."""
    rc = fl['rect']
    yaw = math.radians(rc.get('yaw', 0.0))
    cx, cz = rc['center'][0], rc['center'][2]
    hx, hz = rc['half']
    top = fl.get('top', 0.0) or 0.0
    if top <= 0:
        top = max(fl.get('h0', 0.0), fl.get('h1', 0.0))
    p = fl.get('plateau', 0.0) or 0.0
    na, ns = (80, 28) if kind == 'Hill' else (40, 14)
    rings = [0.0] + list(p + (1 - p) * (0.55 * np.linspace(0, 1, ns + 1)[1:] + 0.45 * (0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, ns + 1)[1:]))))
    rings += [1.03, 1.07]
    rings = np.array(sorted(set(np.round(rings, 6))))
    th = np.linspace(0, 2 * np.pi, na, endpoint=False)
    RH, TH = np.meshgrid(rings, th, indexing='ij')
    lx = hx * RH * np.cos(TH); lz = hz * RH * np.sin(TH)
    X = cx + lx * math.cos(yaw) + lz * math.sin(yaw)
    Z = cz - lx * math.sin(yaw) + lz * math.cos(yaw)
    tt = np.clip((RH - p) / (1 - p), 0, 1)
    Hh = np.where(RH >= 1, 0.0, top * (1 - tt * tt) ** 2) - 0.012 - 0.03 * sstep(1.0, 1.07, RH)
    sun = np.array([0.494, -0.262])
    slope_dir = np.stack([np.cos(TH), np.sin(TH)], -1)
    lee = np.clip(-(slope_dir[..., 0] * sun[0] + slope_dir[..., 1] * sun[1]), 0, 1) * sstep(0.1, 0.9, tt)
    n1 = vnoise(X, Z, 5.0, seed)
    crest = 1 - sstep(0.0, 0.6, tt)
    col = GP['snow_shade'][None, None, :] * (1 - crest[..., None]) + GP['snow'][None, None, :] * crest[..., None]
    col = col * (0.93 + 0.12 * n1[..., None])
    ashk = sstep(0.55, 0.8, n1) * 0.6 + lee * 0.45
    col = col * (1 - ashk[..., None]) + GP['ash'][None, None, :] * ashk[..., None]
    toe = sstep(0.8, 1.0, RH)
    col = col * (1 - toe[..., None] * 0.5) + GP['slush'][None, None, :] * (toe[..., None] * 0.5)
    nr = len(rings)
    verts = np.stack([X.ravel(), Z.ravel(), Hh.ravel()], 1)
    faces = []
    for r in range(nr - 1):
        for a in range(na):
            a1 = (a + 1) % na
            i0, i1, i2, i3 = r * na + a, r * na + a1, (r + 1) * na + a1, (r + 1) * na + a
            faces.append((i0, i3, i2) if r == 0 else (i0, i1, i2, i3))
    me = bpy.data.meshes.new('AW_' + fl['name'])
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv0 = me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    co = np.array([v.co for v in me.vertices])
    flat = col.reshape(-1, 3)
    kd = KDTree(len(verts))
    for i, v in enumerate(verts):
        kd.insert(Vector(v), i)
    kd.balance()
    vc = np.array([flat[kd.find(Vector(c))[1]] for c in co], np.float32)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    Cc = np.ones((len(co), 4), np.float32); Cc[:, :3] = vc
    ca.data.foreach_set('color', Cc[lv].ravel())
    P_ = np.zeros((len(co), 2), np.float32); P_[:, 0] = 0.08
    uv1.data.foreach_set('uv', P_[lv].ravel())
    U = np.stack([co[:, 0] / 36.0, co[:, 1] / 36.0], 1).astype(np.float32)
    uv0.data.foreach_set('uv', U[lv].ravel())
    for p_ in me.polygons:
        p_.use_smooth = True
    me.materials.append(L.get_material(W.GROUND))
    return me
