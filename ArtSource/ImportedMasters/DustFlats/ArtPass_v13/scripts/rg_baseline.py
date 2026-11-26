"""Baseline capture (v10, before any step) and validation of the v11 result against it."""
import bpy, math, json
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import rg_lib as L

RAMPS = ['Ramp', 'Ramp.001', 'Ramp.002', 'Ramp.006', 'Ramp.007']
CELL = 0.5


def _props(o):
    out = {}
    for k in o.keys():
        if k.startswith('unity_') or k == 'editing_zone':
            v = o[k]
            out[k] = v.to_list() if hasattr(v, 'to_list') else v
    return out


def _bvh_world(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = o.evaluated_get(dg).to_mesh()
    M = o.matrix_world
    verts = [M @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    o.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts


def _deck_samples(o, n=12):
    bvh, verts = _bvh_world(o)
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    out = []
    for i in range(n):
        for j in range(n):
            x = min(xs) + (max(xs) - min(xs)) * (0.08 + 0.84 * i / (n - 1))
            y = min(ys) + (max(ys) - min(ys)) * (0.08 + 0.84 * j / (n - 1))
            hit = bvh.ray_cast(Vector((x, y, max(zs) + 5)), Vector((0, 0, -1)))
            if hit[0] is not None:
                out.append((x, y, hit[0].z))
    return out


def _hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 3))))
    if len(pts) < 3:
        return np.array(pts)
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def _occupancy(objs):
    """Set of (i, j) 0.5 m cells covered by the convex hulls of each welded rock component (world XY)."""
    cells = set()
    for o in objs:
        M = np.array(o.matrix_world)
        for pts, _ in L.mesh_components(o.data):
            w = pts @ M[:3, :3].T + M[:3, 3]
            low = w[w[:, 2] < max(1.0, w[:, 2].min() + 0.6)]
            if len(low) < 3:
                low = w
            h = _hull(low[:, :2])
            if len(h) < 3:
                continue
            x0, y0 = h.min(0); x1, y1 = h.max(0)
            gx = np.arange(math.floor(x0 / CELL), math.ceil(x1 / CELL) + 1)
            gy = np.arange(math.floor(y0 / CELL), math.ceil(y1 / CELL) + 1)
            GX, GY = np.meshgrid(gx, gy)
            px = (GX + 0.5) * CELL; py = (GY + 0.5) * CELL
            inside = np.ones(px.shape, bool)
            for k in range(len(h)):
                a = h[k]; b = h[(k + 1) % len(h)]
                inside &= ((b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])) >= -1e-6
            for i, j in zip(GX[inside], GY[inside]):
                cells.add((int(i), int(j)))
    return cells


def capture(ctx):
    sc = bpy.context.scene
    objs = {}
    for o in sc.objects:
        objs[o.name] = dict(type=o.type, parent=o.parent.name if o.parent else None,
                            mw=[round(x, 5) for row in o.matrix_world for x in row],
                            colls=sorted(c.name for c in o.users_collection), props=_props(o),
                            mesh=o.data.name if o.type == 'MESH' else None,
                            mesh_props={k: o.data[k] for k in o.data.keys() if k.startswith('unity_')} if o.type == 'MESH' else {})
    ramps = {nm: _deck_samples(bpy.data.objects[nm]) for nm in RAMPS if nm in bpy.data.objects}
    rock_objs = [bpy.data.objects[n] for n in ctx['rock_objects'] if n in bpy.data.objects and n not in ('Plateau', 'MesaRock')]
    occ = _occupancy(rock_objs)
    me_tris = 0
    seen = set()
    for o in sc.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles(); me_tris += len(o.data.loop_triangles)
    return dict(objects=objs, collections=sorted(c.name for c in bpy.data.collections), ramps=ramps, rock_occ=occ, tris=me_tris)


def validate(base, ctx):
    sc = bpy.context.scene
    rep = {}
    # 1. objects, hierarchy, transforms, props
    missing, reparent, moved, props_changed, coll_changed, mesh_props = [], [], [], [], [], []
    for nm, b in base['objects'].items():
        o = bpy.data.objects.get(nm)
        if o is None:
            if b['type'] in ('CAMERA', 'LIGHT'):
                continue
            missing.append(nm); continue
        if (o.parent.name if o.parent else None) != b['parent']:
            reparent.append(nm)
        mw = [round(x, 5) for row in o.matrix_world for x in row]
        if max(abs(a - c) for a, c in zip(mw, b['mw'])) > 1e-3:
            moved.append(nm)
        if _props(o) != b['props']:
            props_changed.append(nm)
        if sorted(c.name for c in o.users_collection) != b['colls']:
            coll_changed.append(nm)
        if o.type == 'MESH':
            mp = {k: o.data[k] for k in o.data.keys() if k.startswith('unity_')}
            if mp != b['mesh_props']:
                mesh_props.append(nm)
    rep['objects_checked'] = len(base['objects'])
    rep['missing_objects'] = missing; rep['reparented'] = reparent; rep['moved'] = moved
    rep['unity_props_changed'] = props_changed; rep['collection_membership_changed'] = coll_changed
    rep['mesh_unity_props_changed'] = mesh_props
    rep['collections_missing'] = [c for c in base['collections'] if c not in bpy.data.collections]
    # 2. pipeline attributes on every scene mesh
    bad_attr = []
    for me in {o.data for o in sc.objects if o.type == 'MESH'}:
        ok = ('Color' in me.color_attributes and me.color_attributes['Color'].domain == 'CORNER'
              and me.color_attributes['Color'].data_type == 'FLOAT_COLOR'
              and len(me.uv_layers) >= 2 and me.uv_layers[0].name == 'UVMap' and me.uv_layers[1].name == 'Unity_MaterialParams')
        if not ok:
            bad_attr.append(me.name)
    rep['meshes_missing_pipeline_attributes'] = bad_attr
    # 3. driving surface of ramps unchanged
    rd = {}
    for nm, samples in base['ramps'].items():
        o = bpy.data.objects.get(nm)
        bvh, _ = _bvh_world(o)
        diffs = []
        for (x, y, z) in samples:
            hit = bvh.ray_cast(Vector((x, y, z + 3)), Vector((0, 0, -1)))
            if hit[0] is not None:
                diffs.append(hit[0].z - z)
        d = np.abs(np.array(diffs)) if diffs else np.zeros(1)
        rd[nm] = dict(samples=len(diffs), max_abs_dz=round(float(d.max()), 4), over_2cm=int((d > 0.02).sum()))
    rep['ramp_deck_height_check'] = rd
    # 4. rocks stay within their v10 footprints (cells at ground level)
    occ = base['rock_occ']
    dil = set()
    for (i, j) in occ:
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                dil.add((i + di, j + dj))
    tot = out = 0; worst = 0.0
    for nm in ctx['rock_objects']:
        if nm in ('Plateau', 'MesaRock'):
            continue
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        M = np.array(o.matrix_world)
        co = np.zeros(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        w = co @ M[:3, :3].T + M[:3, 3]
        w = w[w[:, 2] < 0.8]
        for x, y, z in w:
            c = (int(math.floor(x / CELL)), int(math.floor(y / CELL)))
            tot += 1
            if c not in dil:
                out += 1
    rep['rock_ground_vertices_checked'] = tot
    rep['rock_ground_vertices_outside_v10_footprint_plus_0_5m'] = out
    rep['rock_outside_fraction'] = round(out / max(tot, 1), 4)
    # 5. new objects: no Unity IDs, not on roads / floors / routes
    lvl = ctx['level']; new_objs = [o for o in sc.objects if o.get('artpass_v11', '').startswith('new')]
    on_lane = {}
    for o in new_objs:
        if 'unity_id' in o:
            rep.setdefault('new_objects_with_unity_id', []).append(o.name)
        if o.name.startswith('AP_Ground_TyreRuts'):
            continue
        M = np.array(o.matrix_world)
        co = np.zeros(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        w = co @ M[:3, :3].T + M[:3, 3]
        bad = 0
        for x, y, z in w[::4]:
            if lvl.road_clearance(x, y) < 0 or lvl.on_floor(x, y, 0.0) or lvl.near_route(x, y, 0.0):
                bad += 1
        on_lane[o.name] = bad
    rep['new_objects'] = [o.name for o in new_objs]
    rep['new_object_vertices_on_roads_floors_routes(sampled)'] = on_lane
    tris = 0
    for o in sc.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
    rep['triangles_before'] = base['tris']; rep['triangles_after'] = tris
    rep['ok'] = not (missing or reparent or moved or props_changed or bad_attr or rep['collections_missing'])
    return rep
