import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imgtools
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
groups = {'ramps': ['Ramp', 'Ramp.006', 'Ramp.002', 'Kicker0a.001', 'Kicker0d.001'],
          'buildings': ['Spawn_00122_Shack', 'Spawn_00123_Shack', 'Spawn_00128_Shack', 'Spawn_00138_Tower', 'Garage', 'Gate1'],
          'props': ['Spawn_00116_CarWreck', 'Spawn_00088_JunkPile', 'Spawn_00098_Barrels', 'Spawn_00075_Tires']}
for g, names in groups.items():
    tiles = []; labels = []
    for n in names:
        b = os.path.join(root, 'renders/before_closeups', n + '.png'); a = os.path.join(root, 'renders/after_closeups', n + '.png')
        if os.path.exists(b) and os.path.exists(a):
            tiles += [b, a]; labels += [n.replace('Spawn_', '')[:18] + ' V11', n.replace('Spawn_', '')[:18] + ' V12']
    imgtools.sheet(tiles, os.path.join(root, 'compare', f'00_{g}_v11_v12.png'), 4, 420, labels=labels)
    print('CC', g, len(tiles))
