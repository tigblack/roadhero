"""Ashen Winter enemies: the creature atlas T_AshenEnemies_BaseMap_1K.png (1024 x 1024, 16 strips of 64 px).

    python3 aw_enemy_tex.py <out_dir>        (numpy only; Blender's bundled python3.13 works)

Strips (top to bottom) match aw_lib.STRIPS. Detail is calm and near white (multiplied by the vertex colours in
RoadGame/Toon); rust and the orange / black hazard paint carry their own colour.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'Levels', 'AshenWinter', 'scripts'))
sys.path.insert(0, KIT)
import aw_texkit as K  # noqa: E402

ORDER = ['plain', 'concrete', 'ash', 'feather', 'hide', 'cable', 'rust', 'metal',
         'snow', 'hazard', 'tread', 'cloth', 'bone', 'ice', 'grille', 'panel']
NAME = 'T_AshenEnemies_BaseMap_1K.png'

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'textures')
    os.makedirs(out, exist_ok=True)
    img = K.atlas(ORDER)
    path = os.path.join(out, NAME)
    K.save_png(path, img)
    print('AW_ENEMY_TEX', path, img.shape)
