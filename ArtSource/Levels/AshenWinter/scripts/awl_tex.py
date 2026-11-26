"""Ashen Winter level textures (numpy only; Blender's bundled python3.13 works).

    python3 awl_tex.py <out_dir>

T_Trim_Ashen_BaseMap_2K.png   2048 x 2048, 16 strips of 128 px (order: awl_lib.TRIM_STRIPS)
T_Ground_Ashen_BaseMap_2K.png 2048 x 2048 world-projected ground detail (36 m per tile)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aw_texkit as K  # noqa: E402

TRIM_ORDER = ['plain', 'metal', 'rust', 'panel', 'corrugated', 'plank', 'concrete', 'hazard',
              'snow', 'ash', 'bark', 'grille', 'ice', 'tread', 'cloth', 'chevron']

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'textures')
    os.makedirs(out, exist_ok=True)
    K.save_png(os.path.join(out, 'T_Trim_Ashen_BaseMap_2K.png'), K.atlas_raw(TRIM_ORDER, 2048, 128))
    K.save_png(os.path.join(out, 'T_Ground_Ashen_BaseMap_2K.png'), K.ground(2048))
    print('AWL_TEX', out)
