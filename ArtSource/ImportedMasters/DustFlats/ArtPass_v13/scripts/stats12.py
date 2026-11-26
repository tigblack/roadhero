import bpy, sys, json, collections, re
out = sys.argv[sys.argv.index('--') + 1]
ACTOR = ('torso', 'arm3', 'leg3', 'w_', 'buggy', 'quasimodo', 'harpoon', 'hoodmg', 'playercar', 'wheel3', 'carwheel', 'boss_')
def cat(o):
    n = o.name; m = o.data.name
    if n.startswith('PREVIEW_'): return None
    if any(m.startswith(a) for a in ACTOR): return 'actors/car (untouched)'
    if n.startswith(('AP_Ground_Backdrop', 'AP_Backdrop')): return 'backdrop (presentation horizon)'
    if n.startswith('AP_River'): return 'river (water, fords, vegetation, boulders)'
    if n.startswith('AP_Bridge'): return 'bridges'
    if n in ('Cliff.003', 'Cliff.004', 'Cliff.011', 'Cliff.012', 'Cliff.014', 'AP_Cliff_NorthEast') or n.startswith('AP_Scree'): return 'perimeter cliffs + scree'
    if m.startswith(('Cliff', 'Mesa', 'Ridge', 'Boulder', 'Plateau')) or 'Decor' in m: return 'other rocks/decor'
    if n in ('Ground',) or n.startswith(('AP_SandDrift', 'AP_Ground')): return 'ground (+drifts, ruts)'
    if m.startswith(('Ramp', 'Kicker', 'BigJump', 'Funnel', 'Guide', 'Barricade')): return 'ramps/kickers/guides'
    if m.startswith(('Road', 'Bumps', 'Hill', 'RoadHill')): return 'roads/terrain'
    if m.startswith(('Works', 'Hangar', 'Vents', 'TunnelLid', 'GroundFill', 'Lamp', 'FlatQuad')): return 'mammoth works'
    if m.startswith(('Shack', 'Tent', 'Tower', 'Garage', 'gate', 'Palisade', 'repairpad', 'billboard')): return 'buildings/camps'
    return 'props/other'
res = collections.Counter(); objs = collections.Counter(); seen = {}
for o in bpy.context.scene.objects:
    if o.type != 'MESH': continue
    c = cat(o)
    if c is None: continue
    if o.data.name not in seen:
        o.data.calc_loop_triangles(); seen[o.data.name] = len(o.data.loop_triangles)
    res[c] += seen[o.data.name]; objs[c] += 1
json.dump(dict(triangles=dict(res), objects=dict(objs), total=sum(res.values())), open(out, 'w'), indent=1)
print('S12', json.dumps(dict(res)), 'TOTAL', sum(res.values()))
