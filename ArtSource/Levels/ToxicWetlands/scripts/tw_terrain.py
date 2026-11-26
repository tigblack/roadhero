"""Toxic Wetlands terrain: swamp ground tiles, water surfaces, hills and bump rows of the second zone.

Ground and water come from the layout grid (data/ToxicWetlands_surfaces.bytes, written by tw_layout.py), the
same grid Unity samples for the ground height and wheel water contacts. Ground: 25 m tiles (frustum culling);
tiles with water or banks use the 0.5 m grid points exactly, flat tiles 2.5 m; short skirts hide T-junction
seams. Water: flat quads at the water level over every cell that dips below it; the jagged outer row lies under
the bank, so the visible shoreline is the smooth bank / water intersection. Hills and bump rows are rebuilt from
Unity's MoundPiece formula (h = top (1 - t^2)^2) like the v13 Dust Flats pass, coloured as mossy mud mounds.
"""
import json
import math
import os
import struct

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import tw_lib as L

TILE = 25.0
ZX0, ZX1, ZZ0, ZZ1 = -100.0, 100.0, 100.0, 300.0


def load_grid(data_dir):
    b = open(os.path.join(data_dir, 'ToxicWetlands_surfaces.bytes'), 'rb').read()
    nx, nz, x0, z0, step, level = struct.unpack('<iiffff', b[4:28])
    n = nx * nz
    h = np.frombuffer(b[28:28 + 2 * n], '<i2').reshape(nz, nx).astype(np.float64) / 1000.0
    tox = np.frombuffer(b[28 + 2 * n:28 + 3 * n], np.uint8).reshape(nz, nx).astype(np.float64) / 255.0
    return dict(nx=nx, nz=nz, x0=x0, z0=z0, step=step, level=level, h=h, tox=tox)


def sample(g, arr, x, z):
    fx = np.clip((np.asarray(x) - g['x0']) / g['step'], 0, g['nx'] - 1.000001)
    fz = np.clip((np.asarray(z) - g['z0']) / g['step'], 0, g['nz'] - 1.000001)
    ix, iz = np.floor(fx).astype(int), np.floor(fz).astype(int)
    tx, tz = fx - ix, fz - iz
    a = arr[iz, ix]; c = arr[iz, ix + 1]; d = arr[iz + 1, ix]; e = arr[iz + 1, ix + 1]
    out = (a * (1 - tx) + c * tx) * (1 - tz) + (d * (1 - tx) + e * tx) * tz
    inside = (np.asarray(x) >= g['x0']) & (np.asarray(x) <= g['x0'] + (g['nx'] - 1) * g['step']) & \
             (np.asarray(z) >= g['z0']) & (np.asarray(z) <= g['z0'] + (g['nz'] - 1) * g['step'])
    return np.where(inside, out, 0.0)


def vnoise(x, z, scale, seed):
    gx, gz = np.asarray(x) / scale, np.asarray(z) / scale
    ix, iz = np.floor(gx).astype(np.int64), np.floor(gz).astype(np.int64)
    fx, fz = gx - ix, gz - iz

    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 2147483647) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 65535.0
    ux, uz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b, c, d = h(ix, iz), h(ix + 1, iz), h(ix, iz + 1), h(ix + 1, iz + 1)
    return (a * (1 - ux) + b * ux) * (1 - uz) + (c * (1 - ux) + d * ux) * uz


def sstep(e0, e1, x):
    t = np.clip((np.asarray(x) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def road_distance(scene_md, x, z):
    d = np.full(np.shape(x), 1e9)
    for r in scene_md['roads']:
        if r['zone'] != 1:
            continue
        p = np.array(r['points']).reshape(-1, 3)
        for (ax, _, az), (bx, _, bz) in zip(p[:-1], p[1:]):
            vx, vz = bx - ax, bz - az
            L2 = max(vx * vx + vz * vz, 1e-9)
            t = np.clip(((x - ax) * vx + (z - az) * vz) / L2, 0, 1)
            dd = np.hypot(x - ax - t * vx, z - az - t * vz) - r['width'] / 2
            d = np.minimum(d, dd)
    return d


# ground palette (linear)
GP = {k: np.array(L.hexlin(v)) for k, v in {
    'mud': '#5D5A3B', 'mud_light': '#7B7255', 'moss': '#56612F', 'moss_dark': '#3E4826',
    'wet': '#3A3726', 'edge': '#2F2D1F', 'bed': '#2A2A1C', 'track': '#6E6650'}.items()}


def ground_colour(g, md, x, z):
    h = sample(g, g['h'], x, z)
    lvl = g['level']
    n1 = vnoise(x, z, 17.0, 3)
    n2 = vnoise(x, z, 6.5, 4)
    n3 = vnoise(x, z, 31.0, 5)
    col = GP['mud'][None, :] * (0.88 + 0.24 * n3)[:, None]
    moss = sstep(0.52, 0.72, n1 * 0.7 + n2 * 0.3)
    col = col * (1 - moss[:, None] * 0.85) + GP['moss'][None, :] * (moss[:, None] * 0.85)
    dmoss = sstep(0.7, 0.85, n2) * moss
    col = col * (1 - dmoss[:, None] * 0.5) + GP['moss_dark'][None, :] * (dmoss[:, None] * 0.5)
    rd = road_distance(md, x, z)
    track = sstep(6.0, 1.0, rd)
    col = col * (1 - track[:, None] * 0.7) + GP['track'][None, :] * (track[:, None] * 0.7)
    wet = np.clip(h / lvl, 0, 1)                         # 0 on dry ground, 1 at the shoreline
    col = col * (1 - wet[:, None] * 0.75) + GP['wet'][None, :] * (wet[:, None] * 0.75)
    under = sstep(lvl, lvl - 0.08, h)
    col = col * (1 - under[:, None]) + GP['bed'][None, :] * under[:, None]
    edge = sstep(0.55, 0.95, wet) * (1 - under)
    col = col * (1 - edge[:, None] * 0.5) + GP['edge'][None, :] * (edge[:, None] * 0.5)
    gloss = 0.05 + 0.4 * wet
    return col, gloss


def grid_mesh(name, xs, zs, Hfun, colfun, skirt=0.12):
    """Regular grid (Unity x along xs, z along zs) -> Blender mesh with Color / UVMap / Unity_MaterialParams."""
    X, Z = np.meshgrid(xs, zs)
    x, z = X.ravel(), Z.ravel()
    hgt = Hfun(x, z)
    col, gloss = colfun(x, z)
    nxv, nzv = len(xs), len(zs)
    verts = np.stack([x, z, hgt], 1)
    faces = []
    for j in range(nzv - 1):
        for i in range(nxv - 1):
            a = j * nxv + i
            faces.append((a, a + 1, a + 1 + nxv, a + nxv))
    vlist = [tuple(v) for v in verts]
    vcol = [tuple(c) for c in col]
    vgl = list(gloss)
    # skirts along the four tile edges
    border = [j * nxv for j in range(nzv)][::-1] + list(range(nxv)) + [j * nxv + nxv - 1 for j in range(nzv)] + \
             [(nzv - 1) * nxv + i for i in range(nxv)][::-1]
    edges = [list(range(nxv)), [(nzv - 1) * nxv + i for i in range(nxv)][::-1],
             [j * nxv for j in range(nzv)][::-1], [j * nxv + nxv - 1 for j in range(nzv)]]
    for e in edges:
        base = len(vlist)
        for k, vi in enumerate(e):
            vx, vy, vz = vlist[vi]
            vlist.append((vx, vy, vz - skirt))
            vcol.append(vcol[vi]); vgl.append(vgl[vi])
        for k in range(len(e) - 1):
            faces.append((e[k + 1], e[k], base + k, base + k + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(vlist, [], faces)
    me.update()
    # Blender's +y is Unity's +z: a CCW quad in (x, z) seen from +Z is CCW from above -> normals up
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv0 = me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    C = np.ones((len(vlist), 4), np.float32)
    C[:, :3] = np.array(vcol, np.float32)
    ca.data.foreach_set('color', C[lv].ravel())
    P = np.zeros((len(vlist), 2), np.float32)
    P[:, 0] = np.array(vgl, np.float32)
    uv1.data.foreach_set('uv', P[lv].ravel())
    U = np.array([(v[0] / 36.0, v[1] / 36.0) for v in vlist], np.float32)
    uv0.data.foreach_set('uv', U[lv].ravel())
    for p in me.polygons:
        p.use_smooth = True
    me.validate()
    return me


CELL, FINE = 5.0, 1.0


def underground_cuts(md):
    """(x0, z0, x1, z1) openings in this zone's ground: each surface hole of the layout (axis-aligned here), and for
    holes in a row at the same z (the two ramps of the underpass) also the covered stretch between them."""
    holes = [h for h in md.get('holes', []) if ZZ0 <= h['center'][2] <= ZZ1 and abs(h.get('yaw', 0)) < 0.5]
    cuts = [(h['center'][0] - h['half'][0], h['center'][2] - h['half'][1], h['center'][0] + h['half'][0], h['center'][2] + h['half'][1]) for h in holes]
    rows = {}
    for c in cuts:
        rows.setdefault((round(c[1], 2), round(c[3], 2)), []).append(c)
    for (z0, z1), row in rows.items():
        if len(row) >= 2:
            cuts.append((min(c[0] for c in row), z0, max(c[2] for c in row), z1))
    return cuts


def build_ground(g, md, coll):
    """Two-level crack-free ground: 5 m cells on flat ground (a fan from the cell centre that takes every 1 m edge
    vertex of finer neighbours, so there are no T-junctions) and a 1 m grid in cells with banks or water. Heights
    at the vertices are the exact layout grid values; 25 m tiles are separate objects for frustum culling."""
    out = []
    mat = L.get_material('TW_GroundMud')
    ncx = int(round((ZX1 - ZX0) / CELL)); ncz = int(round((ZZ1 - ZZ0) / CELL))
    per = int(round(CELL / g['step']))
    fine = np.zeros((ncz, ncx), bool)
    for cj in range(ncz):
        for ci in range(ncx):
            ix0 = int(round((ZX0 + ci * CELL - g['x0']) / g['step'])); iz0 = int(round((ZZ0 + cj * CELL - g['z0']) / g['step']))
            sub = g['h'][max(0, iz0 - 1):iz0 + per + 2, max(0, ix0 - 1):ix0 + per + 2]
            fine[cj, ci] = np.abs(sub).max() > 1e-4
    # Openings into the ground: the underpass ramps (the surface holes of the layout) and the covered stretch between
    # them (its lid is a structure of its own that fades when the car is under it). The ground must not lie over them,
    # or a car down there is hidden from the camera. Cells touching an opening use the 1 m grid, and the 1 m quads
    # whose centres fall inside are left out.
    cuts = underground_cuts(md)
    for cj in range(ncz):
        for ci in range(ncx):
            x0c, z0c = ZX0 + ci * CELL, ZZ0 + cj * CELL
            if any(x0c < c[2] and x0c + CELL > c[0] and z0c < c[3] and z0c + CELL > c[1] for c in cuts):
                fine[cj, ci] = True
    k = int(round(CELL / FINE))
    cells_per_tile = int(round(TILE / CELL))
    tri = 0
    cut_quads = [0]
    for tj in range(ncz // cells_per_tile):
        for ti in range(ncx // cells_per_tile):
            vid = {}
            vxz = []
            faces = []

            def lattice(i, j):            # global 1 m lattice index -> vertex id
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
            for cj in range(tj * cells_per_tile, (tj + 1) * cells_per_tile):
                for ci in range(ti * cells_per_tile, (ti + 1) * cells_per_tile):
                    i0, j0 = ci * k, cj * k
                    if fine[cj, ci]:
                        for j in range(k):
                            for i in range(k):
                                qx, qz = ZX0 + (i0 + i + 0.5) * FINE, ZZ0 + (j0 + j + 0.5) * FINE
                                if any(c[0] < qx < c[2] and c[1] < qz < c[3] for c in cuts):
                                    cut_quads[0] += 1
                                    continue
                                faces.append((lattice(i0 + i, j0 + j), lattice(i0 + i + 1, j0 + j),
                                              lattice(i0 + i + 1, j0 + j + 1), lattice(i0 + i, j0 + j + 1)))
                        continue
                    # boundary ring CCW (seen from above): south edge (x+), east (z+), north (x-), west (z-)
                    ring = []
                    south = range(k) if is_fine(ci, cj - 1) else (0,)
                    for i in south:
                        ring.append(lattice(i0 + i, j0))
                    east = range(k) if is_fine(ci + 1, cj) else (0,)
                    for j in east:
                        ring.append(lattice(i0 + k, j0 + j))
                    north = range(k) if is_fine(ci, cj + 1) else (0,)
                    for i in north:
                        ring.append(lattice(i0 + k - i, j0 + k))
                    west = range(k) if is_fine(ci - 1, cj) else (0,)
                    for j in west:
                        ring.append(lattice(i0, j0 + k - j))
                    if len(ring) == 4:
                        faces.append(tuple(ring))
                    else:
                        c = centre(ci, cj)
                        for a in range(len(ring)):
                            faces.append((c, ring[a], ring[(a + 1) % len(ring)]))
            xz = np.array(vxz)
            x, z = xz[:, 0], xz[:, 1]
            hgt = sample(g, g['h'], x, z)
            col, gloss = ground_colour(g, md, x, z)
            name = f'TW_Ground_{ti}_{tj}'
            me = bpy.data.meshes.new(name)
            me.from_pydata([(float(a), float(b), float(c)) for a, b, c in zip(x, z, hgt)], [], faces)
            me.update()
            set_attrs(me, col, gloss, x, z)
            me.materials.append(mat)
            o = L.new_object(name, me, coll)
            o['tw_role'] = 'ground'
            tri += L.tri_count(me)
            out.append(o)
    # aprons behind the side walls (flat, coarse)
    for side, (a, b) in (('W', (-175.0, -100.0)), ('E', (100.0, 175.0))):
        xs = np.linspace(a, b, 16)
        zs = np.linspace(ZZ0, ZZ1, 41)
        me = grid_mesh('TW_Ground_Apron' + side, xs, zs, lambda x, z: np.zeros_like(x), lambda x, z: ground_colour(g, md, x, z), skirt=0.05)
        me.materials.append(mat)
        out.append(L.new_object('TW_Ground_Apron' + side, me, coll))
        tri += L.tri_count(me)
    print('TW_TERRAIN ground tiles', len(out), 'tris', tri, 'fine cells', int(fine.sum()), 'of', fine.size,
          'openings', [tuple(round(v, 2) for v in c) for c in cuts], 'quads left open', cut_quads[0], flush=True)
    return out


def set_attrs(me, col, gloss, x, z):
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    uv0 = me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', lv)
    C = np.ones((len(x), 4), np.float32)
    C[:, :3] = col
    ca.data.foreach_set('color', C[lv].ravel())
    P = np.zeros((len(x), 2), np.float32)
    P[:, 0] = gloss
    uv1.data.foreach_set('uv', P[lv].ravel())
    U = np.stack([x / 36.0, z / 36.0], 1).astype(np.float32)
    uv0.data.foreach_set('uv', U[lv].ravel())
    for p in me.polygons:
        p.use_smooth = True


# ---------------------------------------------------------------------------------------------- water

WC = {'shore': np.array(L.hexlin('#6B7638')), 'deep': np.array(L.hexlin('#3D4826')), 'mid': np.array(L.hexlin('#4F5B2C'))}


def build_water(g, coll):
    mat = L.get_material('TW_Water')
    lvl = g['level']
    out = []
    nt = int(round((ZX1 - ZX0) / TILE))
    sstride = int(round(FINE / g['step']))
    n = int(round(TILE / FINE))
    for tj in range(nt):
        for ti in range(nt):
            ix0 = int(round((ZX0 + ti * TILE - g['x0']) / g['step'])); iz0 = int(round((ZZ0 + tj * TILE - g['z0']) / g['step']))
            Hf = g['h'][iz0:iz0 + n * sstride + 1, ix0:ix0 + n * sstride + 1]
            # a 1 m water cell exists where any 0.5 m sample inside it dips below the level
            H = Hf[::sstride, ::sstride]
            T = g['tox'][iz0:iz0 + n * sstride + 1:sstride, ix0:ix0 + n * sstride + 1:sstride]
            low = np.full((n, n), 9.0)
            for dj in range(sstride + 1):
                for di in range(sstride + 1):
                    low = np.minimum(low, Hf[dj:dj + n * sstride:sstride, di:di + n * sstride:sstride][:n, :n])
            cell = low < lvl - 1e-4
            if not cell.any():
                continue
            vid = {}
            verts, cols, faces = [], [], []

            def V(i, j):
                k = (i, j)
                if k not in vid:
                    vid[k] = len(verts)
                    x = g['x0'] + ix0 * g['step'] + i * FINE; z = g['z0'] + iz0 * g['step'] + j * FINE
                    depth = max(0.0, lvl - H[j, i])
                    t = min(1.0, depth / 0.24)
                    c = WC['shore'] * (1 - t) + WC['deep'] * t
                    if 0.25 < t < 0.75:
                        c = c * 0.5 + WC['mid'] * 0.5
                    verts.append((x, z, lvl))
                    cols.append((c[0], c[1], c[2], float(T[j, i])))
                return vid[k]
            for j in range(n):
                for i in range(n):
                    if cell[j, i]:
                        faces.append((V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)))
            me = bpy.data.meshes.new(f'TW_Water_{ti}_{tj}')
            me.from_pydata(verts, [], faces)
            ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
            me.uv_layers.new(name='UVMap')
            uv1 = me.uv_layers.new(name='Unity_MaterialParams')
            lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
            C = np.array(cols, np.float32)
            ca.data.foreach_set('color', C[lv].ravel())
            P = np.zeros((len(verts), 2), np.float32); P[:, 0] = 0.85
            uv1.data.foreach_set('uv', P[lv].ravel())
            for p in me.polygons:
                p.use_smooth = True
            me.materials.append(mat)
            o = L.new_object(f'TW_Water_{ti}_{tj}', me, coll)
            o['tw_role'] = 'water'
            o['tw_no_shadow'] = True
            out.append(o)
    print('TW_TERRAIN water tiles', len(out), 'tris', sum(L.tri_count(o.data) for o in out), flush=True)
    return out


# ---------------------------------------------------------------------------------------------- mounds

def mound_height(fl, x, z):
    rc = fl['rect']
    yaw = math.radians(rc.get('yaw', 0.0))
    cx, cz = rc['center'][0], rc['center'][2]
    hx, hz = rc['half']
    dx, dz = x - cx, z - cz
    lx = dx * math.cos(yaw) - dz * math.sin(yaw)
    lz = dx * math.sin(yaw) + dz * math.cos(yaw)
    rho = np.sqrt((lx / hx) ** 2 + (lz / hz) ** 2)
    p = fl.get('plateau', 0.0) or 0.0
    t = np.clip((rho - p) / (1 - p), 0, 1)
    k = 1 - t * t
    return np.where(rho >= 1, 0.0, fl['top'] * k * k)


def build_mound(fl, kind, seed):
    rc = fl['rect']
    yaw = math.radians(rc.get('yaw', 0.0))
    cx, cz = rc['center'][0], rc['center'][2]
    hx, hz = rc['half']
    top = fl['top']
    p = fl.get('plateau', 0.0) or 0.0
    na, ns = (80, 28) if kind == 'Hill' else (40, 14)
    rings = [0.0] + list(p + (1 - p) * (0.55 * np.linspace(0, 1, ns + 1)[1:] + 0.45 * (0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, ns + 1)[1:]))))
    rings += [1.03, 1.07]
    rings = np.array(sorted(set(np.round(rings, 6))))
    th = np.linspace(0, 2 * np.pi, na, endpoint=False)
    RH, TH = np.meshgrid(rings, th, indexing='ij')
    lx = hx * RH * np.cos(TH); lz = hz * RH * np.sin(TH)
    # local -> world (inverse of ORect.Local)
    X = cx + lx * math.cos(yaw) + lz * math.sin(yaw)
    Z = cz - lx * math.sin(yaw) + lz * math.cos(yaw)
    tt = np.clip((RH - p) / (1 - p), 0, 1)
    Hh = np.where(RH >= 1, 0.0, top * (1 - tt * tt) ** 2) - 0.012 - 0.03 * sstep(1.0, 1.07, RH)
    # colours: mossy crest, olive slopes, muddy toe; a darker lee side
    sun = np.array([0.494, -0.262])
    slope_dir = np.stack([np.cos(TH), np.sin(TH)], -1)
    lee = np.clip(-(slope_dir[..., 0] * sun[0] + slope_dir[..., 1] * sun[1]), 0, 1) * sstep(0.1, 0.9, tt)
    n1 = vnoise(X, Z, 5.0, seed)
    crest = 1 - sstep(0.0, 0.6, tt)
    col = (np.array(L.hexlin('#5E6634'))[None, None, :] * (1 - crest[..., None]) + np.array(L.hexlin('#6F7A3A'))[None, None, :] * crest[..., None])
    col = col * (0.9 + 0.2 * n1[..., None])
    toe = sstep(0.75, 1.0, RH)
    col = col * (1 - toe[..., None]) + np.array(L.hexlin('#5D5A3B'))[None, None, :] * toe[..., None]
    col = col * (1 - 0.18 * lee[..., None])
    nr = len(rings)
    verts = np.stack([X.ravel(), Z.ravel(), Hh.ravel()], 1)
    faces = []
    for r in range(nr - 1):
        for a in range(na):
            a1 = (a + 1) % na
            i0, i1, i2, i3 = r * na + a, r * na + a1, (r + 1) * na + a1, (r + 1) * na + a
            faces.append((i0, i3, i2) if r == 0 else (i0, i1, i2, i3))
    me = bpy.data.meshes.new('TW_' + fl['name'])
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    # outward-up orientation check: flip if the first face points down
    if np.mean([p.normal.z for p in me.polygons]) < 0:
        for p in me.polygons:
            p.flip()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ca = me.color_attributes.new('Color', 'FLOAT_COLOR', 'CORNER')
    me.uv_layers.new(name='UVMap')
    uv1 = me.uv_layers.new(name='Unity_MaterialParams')
    co = np.array([v.co for v in me.vertices])
    # recompute colours on the welded vertices by nearest original sample
    flat = col.reshape(-1, 3)
    from mathutils.kdtree import KDTree
    kd = KDTree(len(verts))
    for i, v in enumerate(verts):
        kd.insert(Vector(v), i)
    kd.balance()
    vc = np.array([flat[kd.find(Vector(c))[1]] for c in co], np.float32)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    Cc = np.ones((len(co), 4), np.float32); Cc[:, :3] = vc
    ca.data.foreach_set('color', Cc[lv].ravel())
    P = np.zeros((len(co), 2), np.float32); P[:, 0] = 0.06
    uv1.data.foreach_set('uv', P[lv].ravel())
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(L.get_material('TW_GroundMud'))
    return me
