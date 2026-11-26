"""v13 step: hills, road hills and bump rows rebuilt from the exact Unity MoundPiece height
(rho = |(lx/hx, lz/hz)|, t = clamp01((rho - plateau)/(1 - plateau)), h = top * (1 - t^2)^2) on dense elliptical
polar meshes (no more 300-600 tri blobs): rounded shoulders, soft feathered rim tucked 4 cm under the ground,
shallow erosion rills (<= 4.5 cm, open-ground hills only), ground-sampled colours with crest/lee/rill shading.
Hill rock outcrops (HillXDecor) become rounded, flat-capped sandstone boulders on the same footprints."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_sculpt as S

MOUND_RES = {  # name prefix -> (angular segments, slope rings, plateau rings)
    'Hill': (88, 30, 4), 'RoadHill': (72, 26, 5), 'Bumps': (44, 16, 0),
}


def rect_axes(fl):
    rc = fl['rect']; yaw = math.radians(rc.get('yaw', 0.0))
    C = np.array((rc['center'][0], rc['center'][2]))
    R = np.array((math.cos(yaw), -math.sin(yaw))); F = np.array((math.sin(yaw), math.cos(yaw)))
    return C, R, F, rc['half'][0], rc['half'][1]


def mound_height(fl, x, y):
    """Exact Unity MoundPiece.Height for world (x, y) arrays (0 outside the ellipse)."""
    C, R, F, hx, hz = rect_axes(fl)
    dx = x - C[0]; dy = y - C[1]
    lx = dx * R[0] + dy * R[1]; lz = dx * F[0] + dy * F[1]
    rho = np.sqrt((lx / hx) ** 2 + (lz / hz) ** 2)
    p = fl.get('plateau', 0.0) or 0.0
    t = np.clip((rho - p) / (1 - p), 0, 1)
    k = 1 - t * t
    return np.where(rho >= 1, 0.0, fl['top'] * k * k)


def all_mounds(level):
    return [f for f in level.floors if f.get('type') == 'MoundPiece' and abs(f['rect']['center'][2]) < 130]


def terrain_height(level, x, y):
    """Max of every zone-0 mound at world (x, y) (flat ground = 0)."""
    h = np.zeros_like(np.asarray(x, np.float64))
    for f in all_mounds(level):
        h = np.maximum(h, mound_height(f, x, y))
    return h


def build_mound(fl, sampler, kind, seed, level):
    C, R, F, hx, hz = rect_axes(fl)
    top = fl['top']; p = fl.get('plateau', 0.0) or 0.0
    na, ns, npl = MOUND_RES[kind]
    # ring parameters: centre, plateau rings, slope rings (denser at the shoulder and the toe), skirt
    rings = [0.0]
    if p > 0:
        rings += list(np.linspace(0, p, npl + 1)[1:])
        ts = np.linspace(0, 1, ns + 1)[1:]
    else:
        ts = np.linspace(0, 1, ns + 1)[1:]
    ts = 0.55 * ts + 0.45 * (0.5 - 0.5 * np.cos(np.pi * ts))        # mild clustering at the shoulder and the toe
    rings += list(p + (1 - p) * ts)
    rings += [1.025, 1.06]
    rings = np.array(sorted(set(np.round(rings, 6))))
    th = np.linspace(0, 2 * np.pi, na, endpoint=False)
    RH, TH = np.meshgrid(rings, th, indexing='ij')           # (nr, na)
    lx = hx * RH * np.cos(TH); lz = hz * RH * np.sin(TH)
    X = C[0] + R[0] * lx + F[0] * lz; Y = C[1] + R[1] * lx + F[1] * lz
    tt = np.clip((RH - p) / (1 - p), 0, 1)
    Z = np.where(RH >= 1, 0.0, top * (1 - tt * tt) ** 2)
    # skirt: tuck under the ground plane (no z-fighting at the feathered rim)
    Z = Z - 0.012 - 0.03 * S.smoothstep(1.0, 1.06, RH)
    rills = np.zeros_like(Z)
    if kind == 'Hill':
        # shallow erosion rills running down the slope (visual only, <= 4.5 cm)
        band = S.smoothstep(0.18, 0.45, tt) * (1 - S.smoothstep(0.88, 1.0, tt))
        g = S.ridged2(np.cos(TH) * 5.5 + C[0] * 0.01, np.sin(TH) * 5.5 + RH * 0.9, seed, 3, 1.0)
        rills = -0.045 * band * np.clip((g - 0.62) / 0.38, 0, 1) ** 1.5
        Z = Z + rills
    # mesh: rows = rings (inner -> outer), columns = angles (wrap); centre fan for ring 0
    nr = len(rings)
    co = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    idx = np.arange(nr * na).reshape(nr, na)
    tris = []
    for i in range(1, nr - 1):
        a = idx[i, :]; b = idx[i, np.r_[1:na, 0]]; c = idx[i + 1, np.r_[1:na, 0]]; d = idx[i + 1, :]
        tris.append(np.stack([a, b, c], 1)); tris.append(np.stack([a, c, d], 1))
    a = idx[1, :]; b = idx[1, np.r_[1:na, 0]]
    tris.append(np.stack([np.full(na, idx[0, 0]), a, b], 1))
    tris = np.concatenate(tris)
    # drop the duplicate centre vertices (ring 0 repeated na times): remap all to idx[0,0]
    remap = np.arange(len(co)); remap[idx[0, :]] = idx[0, 0]
    tris = remap[tris]
    used = np.unique(tris); rm = -np.ones(len(co), np.int64); rm[used] = np.arange(len(used))
    co = co[used]; tris = rm[tris]
    fn, _ = S.face_normals(co, tris)
    if (fn[:, 2] < 0).mean() > 0.5:
        tris = tris[:, ::-1]
    vn = S.vertex_normals(co, tris)
    # colours: ground sampled + crest light, lee side (east, away from the westerly wind) darker, rills darker
    gx = co[:, 0]; gy = co[:, 1]
    base = sampler.many(gx, gy)
    hh = np.clip(co[:, 2] / max(0.1, top), 0, 1)
    k = 0.95 + 0.09 * hh
    lee = np.clip(vn[:, 0], 0, 1) * (1 - vn[:, 2]) * 2.2
    k *= 1.0 - 0.06 * lee
    rr = rills.ravel()[used] if kind == 'Hill' else np.zeros(len(co))
    k *= 1.0 + 3.0 * rr                           # rr <= 0 -> darker in the grooves
    dxv = co[:, 0] - C[0]; dyv = co[:, 1] - C[1]
    rho_v = np.sqrt((dxv * R[0] + dyv * R[1]) ** 2 / hx ** 2 + (dxv * F[0] + dyv * F[1]) ** 2 / hz ** 2)
    toe = S.smoothstep(0.72, 0.97, rho_v) * (1 - S.smoothstep(1.0, 1.05, rho_v))
    col = base * k[:, None]
    col *= (1 - 0.03 * toe)[:, None]; col[:, 0] *= 1 + 0.03 * toe       # finer, redder sediment at the foot
    vcol = np.ones((len(co), 4)); vcol[:, :3] = np.clip(col, 0, 1)
    arr = S.arrays_from_tris(co, tris, vcol, uv_tile=40.0)
    return arr, len(tris)


def rebuild_decor_rocks(ob, level, seed, ctx):
    """Faceted outcrop rocks -> rounded flat-capped sandstone boulders on the same footprints & heights."""
    me = ob.data
    comps = L.mesh_components(me, weld=0.01)
    M = ob.matrix_world
    acc = L.MeshAccumulator(); n = 0
    r = random.Random(seed)
    for pts, vc in comps:
        if len(pts) < 8:
            continue
        P = np.array([(M @ Vector(c))[:] for c in pts])
        base, yaw, half, zmin = L.pca_frame(P)
        hgt = half.z
        if max(half.x, half.y) < 0.12:
            continue
        hx = max(0.15, half.x * 1.02); hy = max(0.15, half.y * 1.02)
        hz = max(0.12, hgt / 1.75)
        subdiv = 4 if max(hx, hy, hz) > 1.2 else (3 if max(hx, hy, hz) > 0.35 else 2)
        tone = tuple(np.clip(vc[:, :3].mean(0) * 1.0, 0, 1)) if len(vc) else None
        part = S.boulder_part(seed * 131 + n, hx, hy, hz, subdiv=subdiv, lumpy=r.uniform(0.12, 0.2),
                              flat_top=r.uniform(0.25, 0.45), strata=r.uniform(0.4, 0.8), bury=0.16, tone=tone,
                              tilt=r.uniform(-0.06, 0.06))
        a = part.arrays(); part.free()
        W = Matrix.Translation((base.x, base.y, zmin)) @ Matrix.Rotation(yaw, 4, 'Z')
        Mi = M.inverted()
        acc.add(a, Mi @ W); n += 1
    if acc.empty():
        return 0
    mats = [s.material for s in ob.material_slots]
    new = acc.build(me.name + '__v13', materials=mats[:1], sharp_angle=80.0, weighted=False)
    users, _ = L.swap_mesh(me, new, note='v13: rounded flat-capped sandstone boulders (superellipsoid blocks, lumps, soft strata, buried base) on the v11 footprints')
    for o in users:
        L.set_object_materials(o, mats[:1])
    return n


def run(ctx):
    level = ctx['level']; sampler = ctx['ground_sampler']
    stats = {'mounds': {}, 'decor': {}}
    for i, fl in enumerate(all_mounds(level)):
        nm = fl['name']
        ob = bpy.data.objects.get(nm)
        if ob is None or ob.type != 'MESH':
            continue
        kind = 'RoadHill' if nm.startswith('RoadHill') else ('Bumps' if nm.startswith('Bumps') else 'Hill')
        arr, nt = build_mound(fl, sampler, kind, 1700 + i, level)
        # mesh in object space
        Mi = np.array(ob.matrix_world.inverted())
        arr['co'] = arr['co'] @ Mi[:3, :3].T + Mi[:3, 3]
        mats = [s.material for s in ob.material_slots][:1]
        old_tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        new = S.build_mesh(ob.data.name + '__v13', [arr], mats, smooth_angle=89.0)
        users, _ = L.swap_mesh(ob.data, new, note=f'v13: exact MoundPiece surface on a dense elliptical mesh ({kind}); feathered rim, rills, ground colours')
        for o in users:
            L.set_object_materials(o, mats)
        stats['mounds'][nm] = (old_tris, nt)
    for i, nm in enumerate(['Hill0aDecor', 'Hill0bDecor', 'Hill0cDecor', 'Hill0dDecor']):
        ob = bpy.data.objects.get(nm)
        if ob:
            stats['decor'][nm] = rebuild_decor_rocks(ob, level, 1800 + i, ctx)
    ctx['stats']['terrain'] = stats
    print('STEP13 terrain', {k: len(v) for k, v in stats.items()}, flush=True)
