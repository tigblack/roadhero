"""v12 step: validation + integration data (Unity coordinates: Unity (x, y, z) = Blender (x, z, y))."""
import bpy, json, math, os
import numpy as np
from mathutils import Vector
import rg_layout12 as LY
import rg_baseline as B


def U(x, y, z=0.0):
    return [round(float(x), 3), round(float(z), 3), round(float(y), 3)]


def river_checks(ctx):
    river = ctx['river']; poly = ctx['outline']
    # grid over the corridor inside the playable area
    xs = np.arange(-110, 110, 0.5); ys = np.arange(-110, 110, 0.5)
    X, Y = np.meshgrid(xs, ys); X = X.ravel(); Y = Y.ravel()
    inside = LY.point_in_poly(poly, X, Y)
    near = river.corridor(X, Y, 0.5) & inside
    X, Y = X[near], Y[near]
    z, d, w, b, D, idx = river.height(X, Y)
    depth = np.clip(LY.WATER_Z - z, 0, None)
    # slopes from finite differences of the height function
    h = 0.25
    zx, *_ = river.height(X + h, Y); zy, *_ = river.height(X, Y + h)
    slope = np.degrees(np.arctan(np.hypot((zx - z) / h, (zy - z) / h)))
    kinds = np.array([river.kind[i] for i in idx])
    ford = kinds == 'ford'
    return dict(samples=int(len(X)), max_water_depth_m=round(float(depth.max()), 3),
                max_water_depth_ford_m=round(float(depth[ford].max()) if ford.any() else 0.0, 3),
                car_ground_clearance_m=LY.CAR_CLEARANCE, body_stays_dry=bool(depth.max() < LY.CAR_CLEARANCE),
                max_bank_slope_deg=round(float(slope.max()), 1), p95_bank_slope_deg=round(float(np.percentile(slope, 95)), 1),
                max_ford_slope_deg=round(float(slope[ford].max()) if ford.any() else 0.0, 1),
                max_step_cm=round(float(np.abs(np.diff(np.sort(z))).max() * 100), 2))


def floors_vs_river(ctx):
    river = ctx['river']; lv = ctx['level']
    hits = []
    for f in lv.floors:
        r = f['rect']; c = r['center']
        if not (-262 < c[2] < 100 and -100 < c[0] < 100):
            continue
        a = math.radians(r.get('yaw', 0)); hx, hz = r['half']
        pts = []
        for u in np.linspace(-1, 1, 7):
            for v in np.linspace(-1, 1, 7):
                lx, lz = u * hx, v * hz
                pts.append((c[0] + lx * math.cos(a) + lz * math.sin(a), c[2] - lx * math.sin(a) + lz * math.cos(a)))
        pts = np.array(pts)
        wet = river.corridor(pts[:, 0], pts[:, 1], 0.0)
        if wet.any():
            hits.append(dict(floor=f['name'], wet_fraction=round(float(wet.mean()), 3)))
    return hits


def channel_pieces(river, seg=6.0):
    """ORect chain approximating the channel for Ground: holes + ChannelPiece floors (Unity coords, yaw deg)."""
    out = []
    n = len(river.P); s = river.s
    k = 0
    while k < n - 1:
        j = k
        while j < n - 1 and s[j] - s[k] < seg:
            j += 1
        a = river.P[k]; b = river.P[j]; c = (a + b) / 2; dvec = b - a
        L_ = float(np.linalg.norm(dvec)) + 1.0
        yaw = math.degrees(math.atan2(dvec[0], dvec[1]))
        wm = float(river.A[k:j + 1, 0].mean()); bm = float(river.A[k:j + 1, 1].mean()); Dm = float(river.A[k:j + 1, 2].mean())
        out.append(dict(center=U(c[0], c[1]), yaw_deg=round(yaw, 2), half=[round(wm + bm, 3), round(L_ / 2, 3)],
                        bed_half_width=round(wm, 3), bank_width=round(bm, 3), depth=round(Dm, 3), kind=river.kind[(k + j) // 2]))
        k = j
    return out


def run(ctx):
    sc = bpy.context.scene
    rep = {}
    base = ctx['baseline']
    # identity / hierarchy / props (spawn roots moved on purpose are reported, not failed)
    moved_expected = {m['object'] for m in ctx.get('moved_spawns', [])}
    missing, reparent, moved, props_changed = [], [], [], []
    for nm, b in base['objects'].items():
        o = bpy.data.objects.get(nm)
        if o is None:
            if b['type'] not in ('CAMERA', 'LIGHT') and not nm.startswith('AP_Scree_Cliff.0') and not nm.startswith('AP_SandDrift_Cliff.0') and nm != 'AP_Ground_TyreRuts':
                missing.append(nm)
            continue
        if (o.parent.name if o.parent else None) != b['parent']:
            reparent.append(nm)
        mw = [round(x, 5) for row in o.matrix_world for x in row]
        if max(abs(a - c) for a, c in zip(mw, b['mw'])) > 1e-3 and nm not in moved_expected and not nm.startswith('CAM_'):
            anc = o.parent; hit = False
            while anc is not None:
                if anc.name in moved_expected: hit = True; break
                anc = anc.parent
            if not hit:
                moved.append(nm)
        if B._props(o) != b['props']:
            props_changed.append(nm)
    bad_attr = []
    for me in {o.data for o in sc.objects if o.type == 'MESH'}:
        if not ('Color' in me.color_attributes and me.color_attributes['Color'].domain == 'CORNER'
                and len(me.uv_layers) >= 2 and me.uv_layers[0].name == 'UVMap' and me.uv_layers[1].name == 'Unity_MaterialParams'):
            bad_attr.append(me.name)
    rep.update(objects_checked=len(base['objects']), missing_objects=missing, reparented=reparent,
               moved_unexpectedly=moved, unity_props_changed=props_changed, meshes_missing_pipeline_attributes=bad_attr,
               collections_missing=[c for c in base['collections'] if c not in bpy.data.collections],
               spawn_roots_moved_on_purpose=len(moved_expected))
    rep['river'] = river_checks(ctx)
    rep['floors_touching_river'] = floors_vs_river(ctx)
    rep['bridges'] = []
    for b in ctx.get('bridges', []):
        zs = np.array([s['z_top'] for s in b['samples']]); ss = np.array([s['s'] for s in b['samples']])
        sl = np.degrees(np.arctan(np.abs(np.diff(zs) / np.maximum(np.diff(ss), 1e-3))))
        rep['bridges'].append(dict(name=b['name'], width_m=b['width'], span_m=b['span'], deck_height_m=b['deck_height'],
                                   max_approach_slope_deg=round(float(sl.max()), 1), car_width_m=2.0))
    tris = 0
    for o in sc.objects:
        if o.type == 'MESH' and not o.name.startswith('PREVIEW_'):
            o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
    rep['triangles_before_v11'] = base['tris']; rep['triangles_after_v12'] = tris
    rep['ok'] = not (missing or reparent or moved or bad_attr or rep['collections_missing']) and rep['river']['body_stays_dry']
    # ---------------- integration data ----------------
    river = ctx['river']; poly = ctx['outline']
    wh = river.water_halfwidth()
    data = dict(
        coordinate_system='Unity world (x, y up, z), metres; converted from Blender (x, z, y)',
        water_level_y=LY.WATER_Z, depth_main=LY.DEPTH_MAIN, depth_ford=LY.DEPTH_FORD,
        channel_profile='y(d) = -D*(1-0.12*(d/w)^2) for |d|<=w (bed, point bars raise the inner side in bends); '
                        'y = -0.88*D*(1-smoothstep((|d|-w)/b)) for w<|d|<w+b (banks); 0 outside. d = lateral distance to the centre line',
        centreline=[dict(p=U(p[0], p[1]), w=round(float(a[0]), 3), b=round(float(a[1]), 3), D=round(float(a[2]), 3),
                         water_half_width=round(float(h), 3), kind=k) for p, a, h, k in zip(river.P[::2], river.A[::2], wh[::2], river.kind[::2])],
        ground_pieces_suggestion=channel_pieces(river),
        fords=[dict(f, centre=U(*f['centre'])) for f in ctx.get('fords', [])],
        bridges=[dict({k: v for k, v in b.items() if k != 'samples'},
                      deck=[dict(s=s['s'], p=U(s['x'], s['y'], s['z_top']), half_width=s['half_width']) for s in b['samples']])
                 for b in ctx.get('bridges', [])],
        outline_inner_edge=[U(x, y) for x, y in poly[::2]],
        gap_blockers='AP_River_GapBoulders: boulder dams in the inlet (north) and outlet (east) gaps — need colliders',
        moved_spawns=ctx.get('moved_spawns', []),
        scale_check_cars=ctx.get('scale_cars', []),
    )
    ddir = os.path.join(ctx['root'], 'ArtPass_v12', 'data'); os.makedirs(ddir, exist_ok=True)
    json.dump(data, open(os.path.join(ddir, 'river_v12.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(rep, open(os.path.join(ctx['root'], 'ArtPass_v12', 'stats', 'v12_validation.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(ctx['stats'], open(os.path.join(ctx['root'], 'ArtPass_v12', 'stats', 'v12_build_stats.json'), 'w'), indent=1, ensure_ascii=False, default=str)
    for im in bpy.data.images:
        if im.source == 'FILE' and not im.packed_file and im.filepath:
            try: im.pack()
            except Exception: pass
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    sc['artpass_v12_validation'] = json.dumps({k: v for k, v in rep.items() if k != 'bridges'}, default=str)
    print('VALIDATION12', json.dumps(rep, default=str), flush=True)
