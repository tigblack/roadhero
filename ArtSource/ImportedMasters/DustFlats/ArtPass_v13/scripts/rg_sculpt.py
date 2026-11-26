"""v13 SmoothPass sculpt toolkit (runs inside Blender).

* vectorised gradient noise (fbm / ridged) for heightfields;
* heightfield / curvilinear-band meshes (triangles split along the shorter 3D diagonal);
* quadric decimation of the dense sculpt (Decimate COLLAPSE) with point attributes carried through;
* attribute finishing for the RoadGame pipeline: 'Color' (CORNER float colour, A = 1), 'UVMap' (box projection in
  metres / tile), 'Unity_MaterialParams' (gloss, metal) and per-face material indices;
* rounded sandstone boulders (displaced icosphere: lumps, soft strata grooves, flattened cap, buried base).
Organic forms are sculpted procedurally (sculpt-mode operators are not usable from scripts / headless)."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix, noise as mnoise
import rg_lib as L

# ------------------------------------------------------------------------------------------------ noise
_M32 = np.uint64(0xFFFFFFFF)


def _hash(ix, iy, seed):
    ix = (np.asarray(ix, np.int64) + 1000003).astype(np.uint64) & _M32
    iy = (np.asarray(iy, np.int64) + 2000029).astype(np.uint64) & _M32
    n = ((ix * np.uint64(0x27D4EB2D)) ^ (iy * np.uint64(0x165667B1)) ^ np.uint64((seed * 0x9E3779B1) & 0xFFFFFFFF)) & _M32
    n = ((n ^ (n >> np.uint64(15))) * np.uint64(0x2C1B3C6D)) & _M32
    n = ((n ^ (n >> np.uint64(12))) * np.uint64(0x297A2D39)) & _M32
    n = n ^ (n >> np.uint64(15))
    return (n & np.uint64(0xFFFFFF)).astype(np.float64) / 16777216.0


def perlin2(x, y, seed=0):
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64)
    x0 = np.floor(x); y0 = np.floor(y); fx = x - x0; fy = y - y0
    ix = x0.astype(np.int64); iy = y0.astype(np.int64)

    def g(i, j, dx, dy):
        a = _hash(i, j, seed) * (2.0 * np.pi)
        return np.cos(a) * dx + np.sin(a) * dy
    u = fx * fx * fx * (fx * (fx * 6 - 15) + 10); v = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    n00 = g(ix, iy, fx, fy); n10 = g(ix + 1, iy, fx - 1, fy)
    n01 = g(ix, iy + 1, fx, fy - 1); n11 = g(ix + 1, iy + 1, fx - 1, fy - 1)
    return ((n00 + (n10 - n00) * u) * (1 - v) + (n01 + (n11 - n01) * u) * v) * 1.4142


def fbm2(x, y, seed=0, octaves=4, freq=1.0, lac=2.03, gain=0.5):
    tot = 0.0; amp = 1.0; norm = 0.0; f = freq
    for o in range(octaves):
        tot = tot + amp * perlin2(np.asarray(x) * f, np.asarray(y) * f, seed + 101 * o)
        norm += amp; amp *= gain; f *= lac
    return tot / norm


def ridged2(x, y, seed=0, octaves=3, freq=1.0):
    """0..1, sharp crests along the zero lines of the noise (gullies / cracks when inverted)."""
    return 1.0 - np.abs(fbm2(x, y, seed, octaves, freq))


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def smootherstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


def soft_terrace(z, band, sharp=0.6, phase=0.0):
    """Soft sedimentary steps: flattens benches every 'band' metres (0 = no change, 1 = hard steps)."""
    q = (z - phase) / band
    f = np.floor(q); t = q - f
    k = 1.0 + 6.0 * sharp
    st = 0.5 + 0.5 * np.tanh(k * (t - 0.5)) / math.tanh(k * 0.5)
    return (f + st) * band + phase


def blur2(Z, sigma_cells):
    """Separable gaussian blur of a 2D array (edge-extended)."""
    if sigma_cells <= 0.05:
        return Z.copy()
    r = int(math.ceil(3 * sigma_cells))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_cells) ** 2); k /= k.sum()
    P = np.pad(Z, ((0, 0), (r, r)), mode='edge')
    A = np.zeros_like(Z)
    for i, w in enumerate(k):
        A += w * P[:, i:i + Z.shape[1]]
    P = np.pad(A, ((r, r), (0, 0)), mode='edge')
    B = np.zeros_like(Z)
    for i, w in enumerate(k):
        B += w * P[i:i + Z.shape[0], :]
    return B


# ------------------------------------------------------------------------------------------------ meshes
def grid_tris(X, Y, Z, keep=None, flip=False):
    """(ny,nx) grids -> co (N,3), tris (M,3); quads split along their shorter 3D diagonal. keep: (ny-1,nx-1) cells."""
    ny, nx = Z.shape
    co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1).astype(np.float64)
    idx = np.arange(ny * nx).reshape(ny, nx)
    a = idx[:-1, :-1]; b = idx[:-1, 1:]; c = idx[1:, 1:]; d = idx[1:, :-1]
    if keep is None:
        keep = np.ones(a.shape, bool)
    a, b, c, d = a[keep], b[keep], c[keep], d[keep]
    dac = np.linalg.norm(co[a] - co[c], axis=1); dbd = np.linalg.norm(co[b] - co[d], axis=1)
    s = (dac <= dbd)[:, None]
    t1 = np.where(s, np.stack([a, b, c], 1), np.stack([a, b, d], 1))
    t2 = np.where(s, np.stack([a, c, d], 1), np.stack([b, c, d], 1))
    tris = np.concatenate([t1, t2])
    if flip:
        tris = tris[:, ::-1]
    used = np.unique(tris); remap = -np.ones(len(co), np.int64); remap[used] = np.arange(len(used))
    return co[used], remap[tris], used


def face_normals(co, tris):
    p0, p1, p2 = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0); fa = np.linalg.norm(fn, axis=1)
    return fn / np.maximum(fa, 1e-12)[:, None], fa * 0.5


def vertex_normals(co, tris):
    fn, fa = face_normals(co, tris)
    vn = np.zeros_like(co)
    for k in range(3):
        np.add.at(vn, tris[:, k], fn * fa[:, None])
    return vn / np.maximum(np.linalg.norm(vn, axis=1), 1e-12)[:, None]


def mesh_from_tris(name, co, tris, point_attrs=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co)); me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.loops.add(len(tris) * 3); me.loops.foreach_set('vertex_index', tris.astype(np.int32).ravel())
    me.polygons.add(len(tris)); me.polygons.foreach_set('loop_start', np.arange(0, len(tris) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    for nm, arr in (point_attrs or {}).items():
        arr = np.asarray(arr, np.float32)
        if arr.ndim == 1:
            at = me.attributes.new(nm, 'FLOAT', 'POINT'); at.data.foreach_set('value', arr)
        else:
            at = me.attributes.new(nm, 'FLOAT_VECTOR', 'POINT'); at.data.foreach_set('vector', arr[:, :3].ravel())
    me.validate(clean_customdata=False)
    return me


def read_tris(me, point_attrs=()):
    me.calc_loop_triangles()
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    lt = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get('vertices', lt)
    out = {}
    for nm in point_attrs:
        at = me.attributes.get(nm)
        if at is None:
            continue
        if at.data_type == 'FLOAT':
            a = np.zeros(n); at.data.foreach_get('value', a)
        else:
            a = np.zeros(n * 3); at.data.foreach_get('vector', a); a = a.reshape(-1, 3)
        out[nm] = a
    return co, lt.reshape(-1, 3).astype(np.int64), out


def decimate(co, tris, ratio, point_attrs=None):
    """Quadric collapse decimation; point attributes are interpolated through the collapse."""
    if ratio >= 0.999:
        return co, tris, dict(point_attrs or {})
    me = mesh_from_tris('__v13_dec', co, tris, point_attrs)
    ob = bpy.data.objects.new('__v13_dec', me); bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = float(ratio)
    m.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg)
    out = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
    c2, t2, at = read_tris(out, list((point_attrs or {}).keys()))
    bpy.data.meshes.remove(out)
    return c2, t2, at


def sub_tris(co, tris, fmask):
    t = tris[fmask]
    used = np.unique(t); rm = -np.ones(len(co), np.int64); rm[used] = np.arange(len(used))
    return co[used], rm[t], used


def arrays_from_tris(co, tris, vcol, fmat=None, prm=(0.0, 0.0), uv_tile=6.0, fprm=None, corner_col=None):
    """MeshAccumulator arrays: corner colours from per-vertex colours (N,4) or given corner colours (M*3,4),
    box-projected UVs (metres / tile)."""
    fn, _ = face_normals(co, tris)
    lv = tris.ravel()
    col = np.asarray(vcol, np.float32)[lv] if corner_col is None else np.asarray(corner_col, np.float32)
    ax = np.repeat(np.argmax(np.abs(fn), 1), 3)
    P = co[lv]
    u = np.where(ax == 0, P[:, 1], P[:, 0])
    v = np.where(ax == 2, P[:, 1], P[:, 2])
    uv = (np.stack([u, v], 1) / uv_tile).astype(np.float32)
    if fprm is None:
        pr = np.tile(np.array(prm, np.float32), (len(lv), 1))
    else:
        pr = np.repeat(np.asarray(fprm, np.float32), 3, axis=0)
    mat = np.zeros(len(tris), np.int32) if fmat is None else np.asarray(fmat, np.int32)
    return dict(co=co.astype(np.float64), flen=np.full(len(tris), 3, np.int32), lv=lv.astype(np.int32),
                col=col, uv=uv, prm=pr, mat=mat)


def build_mesh(name, arrays_list, materials, smooth_angle=75.0):
    acc = L.MeshAccumulator()
    for a in arrays_list:
        acc.add(a)
    return acc.build(name, materials=materials, sharp_angle=smooth_angle, weighted=False)


# ------------------------------------------------------------------------------------------------ colours
ROCK_TONES = [(0.50, 0.21, 0.115), (0.55, 0.25, 0.14), (0.46, 0.20, 0.12), (0.58, 0.29, 0.16)]
SAND = np.array((0.60, 0.37, 0.18)); SAND_LIGHT = np.array((0.70, 0.46, 0.25))


def S_streak(x, y, z, seed):
    """Vertical desert-varnish streaks: varies quickly along a face, slowly with height."""
    a = fbm2((x + y) * 0.85, z * 0.07 + (x - y) * 0.02, seed + 77, 3)
    return np.clip((a - 0.05) * 2.2, 0, 1)


def rock_colours(co, vn, tone=(0.50, 0.21, 0.115), seed=0, band=1.15, cavity=None, top_z=None, dust=1.0):
    """Sandstone colour per vertex: strata bands by world z, lighter caps/edges, darker base & cavities,
    wind-blown sand on flat ledges. cavity: per-vertex concavity (>0 concave)."""
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    tone = np.array(tone)
    w = fbm2(x * 0.11, y * 0.11, seed + 7, 3)
    ph = z / band + 0.55 * w
    s = 0.5 + 0.5 * np.sin(2 * np.pi * ph)
    s2 = 0.5 + 0.5 * np.sin(2 * np.pi * (z / (band * 2.7) + 0.3 * w + 0.37))
    k = 0.84 + 0.26 * s + 0.10 * (s2 - 0.5)
    streak = S_streak(x, y, z, seed)
    k = k * (1.0 - 0.13 * streak)
    c = tone[None, :] * k[:, None]
    # warm/cool variation across the massif
    m = fbm2(x * 0.035, y * 0.035, seed + 31, 3)
    c *= (1.0 + 0.10 * m)[:, None]
    c[:, 0] *= 1.0 + 0.04 * m
    nz = np.clip(vn[:, 2], -1, 1)
    # caps lighter, overhang-ish faces darker
    c *= (0.93 + 0.12 * np.clip(nz, 0, 1))[:, None]
    if top_z is not None:
        h = np.clip(z / max(0.5, top_z), 0, 1)
        c *= (0.84 + 0.20 * h)[:, None]
    if cavity is not None:
        c *= (1.0 - 0.28 * np.clip(cavity, 0, 1) + 0.10 * np.clip(-cavity, 0, 1))[:, None]
    # sand dust on flat ledges / tops
    flat = smoothstep(0.80, 0.97, nz) * dust
    sand = (SAND[None, :] * (0.95 + 0.1 * fbm2(x * 0.4, y * 0.4, seed + 3, 2))[:, None])
    c = c * (1 - 0.55 * flat[:, None]) + sand * (0.55 * flat[:, None])
    out = np.ones((len(co), 4)); out[:, :3] = np.clip(c, 0.0, 1.0)
    return out


# ------------------------------------------------------------------------------------------------ boulders
def _rounded_box_dirs(cuts):
    """Unit-cube surface points (quad grid, 'cuts' per edge) -> list of local positions in [-1,1]^3 + faces."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True)
    return bm


def boulder_part(seed, hx, hy, hz, subdiv=3, lumpy=0.14, flat_top=0.35, strata=0.6, bury=0.14, tone=None,
                 dust=1.0, uv_tile=3.0, tilt=0.0, cap_sand=True, squareness=None):
    """Weathered sandstone block (local frame, footprint ~ hx/hy, base buried 'bury'*hz under z = 0):
    a superellipsoid (rounded box, exponent 2.6-4) with lumps, soft strata grooves, flat cap, flat buried base."""
    r = random.Random(seed)
    cuts = {0: 1, 1: 2, 2: 3, 3: 5, 4: 7}.get(subdiv, 5)
    p = L.Part()
    bm = p.bm
    tmp = _rounded_box_dirs(cuts)
    for v in tmp.verts:
        bm.verts.new(v.co)
    bm.verts.ensure_lookup_table()
    tmp.verts.index_update()
    for f in tmp.faces:
        bm.faces.new([bm.verts[v.index] for v in f.verts])
    tmp.free()
    pe = squareness if squareness is not None else r.uniform(2.6, 3.8)
    off = Vector((r.uniform(-80, 80), r.uniform(-80, 80), r.uniform(-80, 80)))
    band = r.uniform(0.24, 0.4) * max(0.7, hz)
    ph = r.uniform(0, 1)
    ax = r.uniform(0, math.tau)
    skew = Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), 0))
    for v in bm.verts:
        c = v.co
        n = c.normalized()
        den = (abs(n.x) ** pe + abs(n.y) ** pe + abs(n.z) ** pe) ** (1.0 / pe)
        q0 = n / max(den, 1e-6)                                  # on the superellipsoid
        d = 1.0 + lumpy * mnoise.fractal(n * 1.2 + off, 0.65, 2.0, 3) + 0.03 * mnoise.noise(n * 4.0 + off * 1.7)
        q = Vector((q0.x * hx * d, q0.y * hy * d, q0.z * hz * d))
        q += skew * q.z                                           # slight lean of the stack
        if flat_top > 0 and q0.z > 0:
            zc = hz * (1.0 - flat_top)
            if q.z > zc:
                q.z = zc + (q.z - zc) * 0.3
        if strata > 0:
            side = max(0.0, 1.0 - abs(q0.z) * 1.15)
            t = (q.z / band + ph) % 1.0
            g = math.exp(-((t - 0.5) / 0.11) ** 2)
            k = 1.0 - strata * 0.085 * g * side
            q.x *= k; q.y *= k
        v.co = q
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + bury * hz
        if v.co.z < -bury * hz * 0.6:
            v.co.z = -bury * hz * 0.6 - (v.co.z + bury * hz * 0.6) * 0.15
    if tilt:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(tilt, 3, Vector((math.cos(ax), math.sin(ax), 0))))
    bm.normal_update()
    tone = tone or r.choice(ROCK_TONES)
    ztop = max(v.co.z for v in bm.verts)
    toneA = np.array(tone)

    def paint(co, nrm, f):
        zz = co.z
        s_ = 0.5 + 0.5 * math.sin(2 * math.pi * (zz / band + ph))
        k = (0.84 + 0.22 * s_) * (0.80 + 0.26 * max(0.0, min(1.0, (zz + bury * hz) / max(0.3, ztop + bury * hz))))
        c = toneA * k
        if cap_sand:
            fl = max(0.0, min(1.0, (nrm.z - 0.82) / 0.15)) * dust
            c = c * (1 - 0.5 * fl) + SAND * 0.5 * fl
        return (float(c[0]), float(c[1]), float(c[2]), 1.0, 0.0, 0.0)
    faces = list(bm.faces)
    p.paint_fn(faces, paint)
    p.uv_box(faces, uv_tile, offset=(r.random(), r.random()))
    return p


def pebble_arrays(seed, size, subdiv=1, tone=None):
    p = boulder_part(seed, size * random.Random(seed).uniform(0.8, 1.2), size, size * 0.6, subdiv=subdiv, lumpy=0.22,
                     flat_top=0.25, strata=0.0, bury=0.25, tone=tone, uv_tile=2.0)
    a = p.arrays(); p.free()
    return a
