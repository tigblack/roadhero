"""Integration FBX for Unity: carved Ground, water, bridges, cut road, gap boulders + guide meshes built from
data/river_v12.json (centre line, water edges, outline, Ground channel pieces, bridge drive strips).
Guides exist only in this FBX (not saved into the .blend)."""
import bpy, sys, os, json, math
import numpy as np
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(root, 'data', 'river_v12.json')))
coll = bpy.data.collections.new('INTEGRATION GUIDES (export only)'); bpy.context.scene.collection.children.link(coll)
def B(p):   # Unity -> Blender
    return (p[0], p[2], p[1])
def edges_obj(name, pts, closed=False):
    me = bpy.data.meshes.new(name)
    e = [(i, i + 1) for i in range(len(pts) - 1)] + ([(len(pts) - 1, 0)] if closed else [])
    me.from_pydata(pts, e, []); o = bpy.data.objects.new(name, me); coll.objects.link(o); return o
def quads_obj(name, quads):
    v = []; f = []
    for q in quads:
        f.append(tuple(range(len(v), len(v) + 4))); v += q
    me = bpy.data.meshes.new(name); me.from_pydata(v, [], f); o = bpy.data.objects.new(name, me); coll.objects.link(o); return o
cl = d['centreline']
edges_obj('AP_Guide_RiverCentreline_bed', [(c['p'][0], c['p'][2], -c['D']) for c in cl])
for sgn, nm in ((1, 'Left'), (-1, 'Right')):
    pts = []
    P = np.array([(c['p'][0], c['p'][2]) for c in cl]); T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.c_[-T[:, 1], T[:, 0]]
    for p, n, c in zip(P, N, cl):
        q = p + n * sgn * c['water_half_width']; pts.append((q[0], q[1], d['water_level_y']))
    edges_obj('AP_Guide_WaterEdge_' + nm, pts)
edges_obj('AP_Guide_Outline_InnerEdge', [B(p) for p in d['outline_inner_edge']], closed=True)
quads = []
for g in d['ground_pieces_suggestion']:
    c = g['center']; yaw = math.radians(g['yaw_deg']); hx, hz = g['half']
    ax = (math.cos(yaw), -math.sin(yaw)); az = (math.sin(yaw), math.cos(yaw))
    q = []
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        q.append((c[0] + ax[0] * sx * hx + az[0] * sz * hz, c[2] + ax[1] * sx * hx + az[1] * sz * hz, 0.05))
    quads.append(q)
quads_obj('AP_Guide_GroundChannelPieces', quads)
for b in d['bridges']:
    deck = b['deck']; quads = []
    for s0, s1 in zip(deck[:-1], deck[1:]):
        p0 = np.array([s0['p'][0], s0['p'][2]]); p1 = np.array([s1['p'][0], s1['p'][2]]); t = p1 - p0; t /= max(1e-6, np.linalg.norm(t))
        n = np.array([-t[1], t[0]]); h0 = s0['half_width']; h1 = s1['half_width']
        quads.append([(*(p0 - n * h0), s0['p'][1]), (*(p0 + n * h0), s0['p'][1]), (*(p1 + n * h1), s1['p'][1]), (*(p1 - n * h1), s1['p'][1])])
    quads_obj('AP_Guide_DriveSurface_' + b['name'].replace('AP_', ''), quads)
keep = ['Ground', 'AP_River_Water', 'AP_Bridge_Road0', 'AP_Bridge_Track', 'Road', 'AP_River_GapBoulders']
bpy.ops.object.select_all(action='DESELECT')
n = 0
for o in list(bpy.context.scene.objects):
    if o.name in keep or o.users_collection[0] == coll:
        o.hide_set(False); o.select_set(True); n += 1
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'MESH'}, apply_unit_scale=True, global_scale=1.0,
                         apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
                         use_custom_props=True, mesh_smooth_type='OFF', add_leaf_bones=False, bake_anim=False,
                         path_mode='RELATIVE', colors_type='LINEAR', prioritize_active_color=True)
print('FBXI', out, n)
