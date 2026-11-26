import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imgtools
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b, a, c = (os.path.join(root, x) for x in ('renders/before', 'renders/after', 'compare'))
os.makedirs(c, exist_ok=True)
T = {'01_overview': 'OVERVIEW', '01b_top_outline': 'TOP VIEW OUTLINE', '02_intro_canyon': 'INTRO CANYON GAME CAM', '02b_intro_canyon_low': 'INTRO CANYON',
     '03_road_section': 'ROAD GAME CAM', '04_camp': 'CAMP GAME CAM', '05_ramp_intro': 'RAMP GAME CAM', '05b_ramp_side': 'RAMP',
     '06_works_entrance': 'WORKS GAME CAM', '06b_works_side': 'MAMMOTH WORKS', '07_hangar_interior': 'HANGAR GAME CAM', '07b_hangar_low': 'HANGAR',
     '08_river_bridge1': 'BRIDGE 1 GAME CAM', '08b_river_bridge1_low': 'ROAD BRIDGE', '09_river_ford_centre': 'FORD GAME CAM',
     '09b_car_in_ford': 'CAR IN FORD', '10_river_bridge2': 'BRIDGE 2 GAME CAM', '10b_river_bridge2_low': 'TRACK BRIDGE',
     '11_river_east': 'RIVER EAST GAME CAM', '12_ford_north': 'FORD NORTH GAME CAM'}
for f in sorted(glob.glob(os.path.join(b, '*.png'))):
    n = os.path.splitext(os.path.basename(f))[0]
    g = os.path.join(a, n + '.png')
    if os.path.exists(g):
        imgtools.before_after(f, g, os.path.join(c, n + '_v11_v12.png'), T.get(n, n.upper()), labels=('BEFORE  V11', 'AFTER  V12'))
        print('CMP', n)
game = ['02_intro_canyon', '03_road_section', '04_camp', '05_ramp_intro', '06_works_entrance', '07_hangar_interior',
        '08_river_bridge1', '09_river_ford_centre', '10_river_bridge2', '11_river_east', '12_ford_north']
tiles = []; labels = []
for n in game:
    tiles += [os.path.join(b, n + '.png'), os.path.join(a, n + '.png')]
    labels += [n[3:].replace('_', ' ')[:16] + ' V11', n[3:].replace('_', ' ')[:16] + ' V12']
imgtools.sheet(tiles[:12], os.path.join(c, '00_game_camera_v11_v12_part1.png'), 6, 300, labels=labels[:12])
imgtools.sheet(tiles[12:], os.path.join(c, '00_game_camera_v11_v12_part2.png'), 5, 300, labels=labels[12:])
imgtools.sheet([os.path.join(a, n + '.png') for n in game], os.path.join(c, '00_game_camera_v12_thumbnails_25pct.png'), 11, 135, labels=None)
pres = ['01_overview', '01b_top_outline', '08b_river_bridge1_low', '10b_river_bridge2_low', '09b_car_in_ford', '05b_ramp_side', '06b_works_side', '07b_hangar_low']
imgtools.sheet([os.path.join(a, n + '.png') for n in pres if os.path.exists(os.path.join(a, n + '.png'))], os.path.join(c, '00_v12_presentation_sheet.png'), 2, 760, labels=pres)
print('CMP done')
