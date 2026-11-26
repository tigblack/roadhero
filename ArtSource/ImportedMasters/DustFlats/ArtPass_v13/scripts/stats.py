"""Scene statistics -> JSON. blender -b FILE --python stats.py -- --out stats.json"""
import bpy, sys, json, collections, os
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[argv.index('--out') + 1]
sc = bpy.context.scene
ACTOR = ('torso', 'arm3', 'leg3', 'w_', 'buggy', 'quasimodo', 'harpoon', 'hoodmg', 'playercar', 'wheel3', 'carwheel', 'boss_')
def group(o):
    m = o.data.name; n = o.name
    if any(m.startswith(a) for a in ACTOR): return 'actors_and_reference (untouched)'
    if m.startswith(('Cliff', 'Mesa', 'Ridge', 'Boulder', 'Plateau')) or 'Decor' in m or n.startswith('AP_Rock') or n.startswith('AP_Scree'): return 'rocks_terrain_decor'
    if m.startswith(('Road', 'Ramp', 'Kicker', 'BigJump', 'Funnel', 'Guide', 'Bumps', 'Hill', 'RoadHill', 'Barricade')) or n.startswith(('AP_Ramp', 'AP_Road')): return 'roads_ramps_terrain'
    if m.startswith(('Works', 'Hangar', 'Vents', 'TunnelLid', 'GroundFill', 'Lamp', 'FlatQuad')) or n.startswith('AP_Works'): return 'mammoth_works'
    if m.startswith(('Ground',)) or n.startswith('AP_Ground') or n.startswith('AP_Sand'): return 'ground'
    if m.startswith(('Shack', 'Tent', 'Tower', 'Garage', 'gate', 'Palisade', 'repairpad', 'billboard')) or n.startswith('AP_Camp') or n.startswith('AP_Build'): return 'buildings_camps'
    return 'props_other'
meshes = [o for o in sc.objects if o.type == 'MESH']
tri_inst = 0; per_group = collections.Counter(); per_group_n = collections.Counter()
uniq = {}
for o in meshes:
    me = o.data
    if me.name not in uniq:
        me.calc_loop_triangles(); uniq[me.name] = (len(me.loop_triangles), len(me.vertices))
    t = uniq[me.name][0]
    tri_inst += t; g = group(o); per_group[g] += t; per_group_n[g] += 1
mats_used = collections.Counter()
for o in meshes:
    for s in o.material_slots:
        if s.material: mats_used[s.material.name] += 1
imgs = []
for im in bpy.data.images:
    if im.type != 'IMAGE' or im.name in ('Render Result', 'Viewer Node'): continue
    users = [m.name for m in bpy.data.materials if m.node_tree and any(n.bl_idname == 'ShaderNodeTexImage' and n.image == im for n in m.node_tree.nodes)]
    imgs.append(dict(name=im.name, size=list(im.size), packed=im.packed_file is not None, filepath=im.filepath, used_by=users))
def walk(c):
    return {c.name: dict(objects=len(c.objects), meshes=sum(o.type == 'MESH' for o in c.objects), children=[walk(ch) for ch in c.children])}
res = dict(file=bpy.data.filepath, mesh_objects=len(meshes), empties=sum(o.type == 'EMPTY' for o in sc.objects),
           unique_meshes=len(uniq), triangles_with_instances=tri_inst,
           unique_triangles=sum(v[0] for v in uniq.values()), unique_vertices=sum(v[1] for v in uniq.values()),
           triangles_by_group=dict(per_group), objects_by_group=dict(per_group_n),
           materials_used=dict(mats_used), materials_total=len([m for m in bpy.data.materials if m.users]), images=imgs,
           collections=walk(sc.collection))
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
print("STATS", json.dumps({k: res[k] for k in ('mesh_objects', 'unique_meshes', 'triangles_with_instances', 'unique_triangles', 'materials_total')}))
print("GROUPS", json.dumps(res['triangles_by_group']))
