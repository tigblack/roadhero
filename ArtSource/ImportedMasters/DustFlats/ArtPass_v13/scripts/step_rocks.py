"""Step: rocks & canyon. Every rounded v10 rock blob is replaced (inside the same mesh datablock name,
same object/origin/props) by a faceted, layered sandstone rock fitted to the blob's footprint
(centre, yaw, half-extents) so the visible obstacle edge stays where the Unity rock collider is.
Some blobs become asymmetric 2-3 rock groups; scree and sand drifts are added as separate objects
only where they don't touch roads, ramps/run-ups/landings, routes or keep-out areas."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_rocks as R

# object name -> mode
ROCK_OBJECTS = {
    'Cliff': 'cliff', 'Cliff.001': 'cliff', 'Cliff.002': 'cliff', 'Cliff.003': 'cliff', 'Cliff.004': 'cliff',
    'Cliff.011': 'cliff', 'Cliff.012': 'cliff', 'Cliff.014': 'cliff', 'Ridge0.001': 'cliff',
    'Plateau': 'mixed', 'MesaRock': 'mixed', 'MesaEdgeStones': 'pebbles',
    'Hill0aDecor': 'pebbles', 'Hill0bDecor': 'pebbles', 'Hill0cDecor': 'pebbles', 'Hill0dDecor': 'pebbles',
}
BOULDER_MESHES = ['Boulder_0_0', 'Boulder_1_0']
KEEP_BODY_EXTENT = 9.0   # components wider than this (plateau / mesa bodies) keep their v10 polygons


def original_arrays(me, keep_vert_mask):
    """Arrays for the polygons of 'me' whose vertices are all in keep_vert_mask (original attributes)."""
    n = len(me.vertices)
    co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    ls = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('loop_start', ls)
    lt = np.zeros(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
    col = np.zeros(len(me.loops) * 4, np.float32); me.color_attributes['Color'].data.foreach_get('color', col)
    uv = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers['UVMap'].data.foreach_get('uv', uv)
    prm = np.zeros(len(me.loops) * 2, np.float32); me.uv_layers['Unity_MaterialParams'].data.foreach_get('uv', prm)
    col = col.reshape(-1, 4); uv = uv.reshape(-1, 2); prm = prm.reshape(-1, 2)
    keep = [i for i in range(len(ls)) if keep_vert_mask[lv[ls[i]:ls[i] + lt[i]]].all()]
    if not keep:
        return None
    loops = np.concatenate([np.arange(ls[i], ls[i] + lt[i]) for i in keep])
    used = np.unique(lv[loops]); remap = -np.ones(n, np.int32); remap[used] = np.arange(len(used))
    return dict(co=co[used], flen=lt[keep].astype(np.int32), lv=remap[lv[loops]].astype(np.int32),
                col=col[loops], uv=uv[loops] * 0 + uv[loops], prm=prm[loops], mat=np.zeros(len(keep), np.int32))


def comp_vertex_membership(me, comps_pts, weld=0.01):
    """For each original vertex, index of the welded component it belongs to (nearest point)."""
    from mathutils.kdtree import KDTree
    allp = np.concatenate([c for c, _ in comps_pts]); ids = np.concatenate([np.full(len(c), i) for i, (c, _) in enumerate(comps_pts)])
    kd = KDTree(len(allp))
    for i, p in enumerate(allp):
        kd.insert(p, i)
    kd.balance()
    n = len(me.vertices); co = np.zeros(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    out = np.zeros(n, np.int32)
    for i in range(n):
        _, j, _ = kd.find(co[i]); out[i] = ids[j]
    return out


def choose_style(r, hx, hy, hz):
    asp = hz / max(hx, hy, 0.1)
    if asp > 0.9:
        return r.choice(['spire', 'block', 'block'])
    if asp > 0.5:
        return r.choice(['block', 'round', 'block', 'slab'])
    return r.choice(['slab', 'round', 'slab'])


def rebuild_rock_mesh(ob, mode, seed, ctx, stats):
    me = ob.data
    level = ctx['level']
    comps = L.mesh_components(me)
    rr = random.Random(seed)
    tilt = (math.radians(rr.uniform(2.0, 6.0)), rr.uniform(0, 2 * math.pi))
    acc = L.MeshAccumulator()
    Mw = ob.matrix_world.copy()
    footprints = []     # world (x, y, hx, hy, yaw) of new rocks for scree / drifts
    body_mask = None
    n_new = 0
    for ci, (pts, vcol) in enumerate(comps):
        if len(pts) < 4:
            continue
        ext = pts.max(0) - pts.min(0)
        if mode == 'mixed' and max(ext[0], ext[1]) > KEEP_BODY_EXTENT:
            if body_mask is None:
                memb = comp_vertex_membership(me, comps)
                body_mask = np.zeros(len(me.vertices), bool)
            body_mask |= (memb == ci)
            continue
        base, yaw, half, zmin = L.pca_frame(pts)
        hx, hy, hz = max(0.12, half.x * 0.97), max(0.12, half.y * 0.97), max(0.1, half.z)
        if zmin < 0.3:
            base.z = 0.0
        else:
            base.z = zmin
        r = random.Random(seed * 1000 + ci)
        small = max(hx, hy) < 1.0 or mode == 'pebbles'
        M0 = Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, 'Z')
        pieces = []
        if small:
            hzz = hz * r.uniform(0.9, 1.1)
            pieces.append((Matrix(), hx, hy, hzz, r.choice(['round', 'slab', 'block']), 1))
        elif max(hx, hy) > 2.5 and r.random() < 0.24:
            # asymmetric group: main rock pushed to one side + 1-2 lower satellites
            ang = r.uniform(0, 2 * math.pi)
            off = Vector((math.cos(ang) * hx * 0.22, math.sin(ang) * hy * 0.22, 0))
            pieces.append((Matrix.Translation(off), hx * 0.74, hy * 0.74, hz * r.uniform(0.95, 1.12), choose_style(r, hx, hy, hz), None))
            for k in range(r.randint(1, 2)):
                a2 = ang + math.pi + r.uniform(-0.9, 0.9)
                o2 = Vector((math.cos(a2) * hx * 0.55, math.sin(a2) * hy * 0.55, 0))
                s2 = r.uniform(0.36, 0.48)
                pieces.append((Matrix.Translation(o2) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z'), hx * s2, hy * s2,
                               hz * r.uniform(0.38, 0.62), r.choice(['round', 'slab', 'block']), None))
        else:
            hf = r.uniform(0.92, 1.08) * (r.uniform(1.12, 1.28) if r.random() < 0.2 else 1.0)
            pieces.append((Matrix(), hx, hy, hz * hf, choose_style(r, hx, hy, hz), None))
        for (Mp, px, py, pz, st, strata) in pieces:
            part = R.make_rock(seed * 7919 + ci * 31 + n_new, px, py, pz, st, strata=strata, tilt=tilt,
                               detail=1.0 if not small else 0.6)
            Mloc = M0 @ Mp
            a = part.arrays(); acc.add(a, Mloc); part.free()
            stats['tris'] += int(sum(a['flen'] - 2)); n_new += 1
            c = Mw @ (Mloc @ Vector((0, 0, 0)))
            footprints.append((c.x, c.y, px, py, yaw, pz, small))
    if body_mask is not None:
        arr = original_arrays(me, body_mask)
        if arr is not None:
            acc.add(arr)
    new = acc.build(me.name + '__v11', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50.0)
    users, _ = L.swap_mesh(me, new, note=f'v11: {n_new} faceted layered rocks fitted to v10 blob footprints')
    for o in users:
        L.set_object_materials(o, [ctx['mats']['Rock_Strata']])
    stats['rocks'] += n_new
    return footprints


def inside_any(fps, x, y, shrink=0.85):
    for (cx, cy, hx, hy, yaw, hz, small) in fps:
        dx, dy = x - cx, y - cy
        if abs(dx) > hx + 1 and abs(dy) > hy + 1 and math.hypot(dx, dy) > max(hx, hy) + 1:
            continue
        lx = dx * math.cos(-yaw) - dy * math.sin(-yaw); ly = dx * math.sin(-yaw) + dy * math.cos(-yaw)
        if (lx / (hx * shrink)) ** 2 + (ly / (hy * shrink)) ** 2 < 1.0:
            return True
    return False


def scatter_scree_and_drifts(name, fps, ctx, seed, parent):
    level = ctx['level']; sampler = ctx['ground_sampler']
    r = random.Random(seed)
    scree = L.MeshAccumulator(); drifts = L.MeshAccumulator()
    ns = nd = 0
    big = [f for f in fps if not f[6]]
    for (cx, cy, hx, hy, yaw, hz, small) in big:
        if r.random() < 0.5:
            ang0 = r.uniform(0, 2 * math.pi)
            for k in range(r.randint(2, 5)):
                a = ang0 + r.uniform(-0.7, 0.7)
                ex = hx * math.cos(a); ey = hy * math.sin(a)
                rad = math.hypot(ex, ey) + r.uniform(0.0, 1.1)
                wx = cx + math.cos(a + yaw) * rad; wy = cy + math.sin(a + yaw) * rad
                if not level.clear_for_decor(wx, wy, road_margin=1.0, floor_margin=1.0, keepout=True, route_margin=1.0):
                    continue
                if inside_any(big, wx, wy, 0.8):
                    continue
                s = r.uniform(0.22, 0.65) * (1.4 if r.random() < 0.15 else 1.0)
                part = R.scree_piece(seed * 977 + ns, s)
                M = Matrix.Translation((wx, wy, -0.04)) @ Matrix.Rotation(r.uniform(0, 6.28), 4, 'Z')
                scree.add(part.arrays(), M); part.free(); ns += 1
        if hz > 1.0 and r.random() < 0.34:
            a = r.uniform(0, 2 * math.pi)
            ex = hx * math.cos(a); ey = hy * math.sin(a)
            rad = math.hypot(ex, ey) * 0.92
            wx = cx + math.cos(a + yaw) * rad; wy = cy + math.sin(a + yaw) * rad
            length = min(5.0, max(2.0, 1.2 * max(hx, hy))) * r.uniform(0.8, 1.1)
            width = r.uniform(1.2, 2.2); height = r.uniform(0.22, 0.42)
            tang = a + yaw + math.pi / 2
            ok = all(level.clear_for_decor(wx + math.cos(tang) * t * length * 0.5 + math.cos(a + yaw) * width * 0.5,
                                           wy + math.sin(tang) * t * length * 0.5 + math.sin(a + yaw) * width * 0.5,
                                           road_margin=0.6, floor_margin=0.8, keepout=True, route_margin=0.8) for t in (-1, 0, 1))
            if not ok:
                continue
            M = Matrix.Translation((wx, wy, 0)) @ Matrix.Rotation(tang, 4, 'Z')
            part = R.sand_drift_arrays(seed * 31 + nd, length, width, height, sampler, M)
            drifts.add(part.arrays(), M); part.free(); nd += 1
    coll = ctx['coll_rocks']
    if not scree.empty():
        me = scree.build('AP_Scree_' + name, materials=[ctx['mats']['Rock_Strata']], sharp_angle=50)
        L.new_object('AP_Scree_' + name, me, coll, parent=parent, mats=[ctx['mats']['Rock_Strata']],
                     note=f'new: {ns} scree stones at the base of {name} (kept off roads/ramps/routes)')
    if not drifts.empty():
        me = drifts.build('AP_SandDrift_' + name, materials=[ctx['mats']['Ground']], sharp_angle=80, weighted=False)
        L.new_object('AP_SandDrift_' + name, me, ctx['coll_ground'], parent=parent, mats=[ctx['mats']['Ground']],
                     note=f'new: {nd} low wind-blown sand drifts against {name} (Ground material, seamless rim)')
    return ns, nd


def rebuild_boulders(ctx, stats):
    for mn in BOULDER_MESHES:
        me = bpy.data.meshes.get(mn)
        if me is None:
            continue
        comps = L.mesh_components(me)
        acc = L.MeshAccumulator()
        for ci, (pts, _) in enumerate(comps):
            base, yaw, half, zmin = L.pca_frame(pts)
            base.z = 0.0 if zmin < 0.3 else zmin
            r = random.Random(hash(mn) % 1000 + ci)
            big = max(half.x, half.y) > 1.0
            part = R.make_rock(4000 + ci + len(mn), half.x * 0.97, half.y * 0.97, half.z * r.uniform(0.95, 1.1),
                               choose_style(r, half.x, half.y, half.z) if big else 'round',
                               strata=None if big else 1, tilt=(math.radians(4), 1.0), detail=1.0 if big else 0.6)
            a = part.arrays(); acc.add(a, Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, 'Z')); part.free()
            stats['tris'] += int(sum(a['flen'] - 2)); stats['rocks'] += 1
        # a few pebbles hugging the base (part of the prop family, inside its spawn radius)
        r = random.Random(len(mn) * 13)
        for k in range(3):
            ang = r.uniform(0, 6.28); rad = r.uniform(1.6, 2.1)
            part = R.scree_piece(9000 + k + len(mn), r.uniform(0.2, 0.35))
            acc.add(part.arrays(), Matrix.Translation((math.cos(ang) * rad, math.sin(ang) * rad, -0.03))); part.free()
        new = acc.build(mn + '__v11', materials=[ctx['mats']['Rock_Strata']], sharp_angle=50.0)
        users, _ = L.swap_mesh(me, new, note='v11: faceted boulder family (instancing kept)')
        for o in users:
            L.set_object_materials(o, [ctx['mats']['Rock_Strata']])


def run(ctx):
    stats = dict(rocks=0, tris=0, scree=0, drifts=0)
    for i, (nm, mode) in enumerate(ROCK_OBJECTS.items()):
        ob = bpy.data.objects.get(nm)
        if ob is None:
            print('missing rock object', nm); continue
        fps = rebuild_rock_mesh(ob, mode, 101 + i * 17, ctx, stats)
        if mode == 'cliff' or nm in ('Plateau',):
            ns, nd = scatter_scree_and_drifts(nm, fps, ctx, 555 + i, ob.parent)
            stats['scree'] += ns; stats['drifts'] += nd
    rebuild_boulders(ctx, stats)
    ctx['stats']['rocks'] = stats
    print('STEP rocks done', stats, flush=True)
