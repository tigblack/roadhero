"""Final touches of the editable .blend: presentation lights / cameras (not exported) and a START HERE text."""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tw_present as PR  # noqa: E402

TEXT = """Toxic Wetlands — вторая зона RoadGame (индекс 1, бывший Rust Canyon)

Коллекции
- Zone_01_ToxicWetlands — всё, что экспортируется в Unity (бандл Levels/ToxicWetlandsZ1).
  * подколлекции: Ground & water (земля тайлами 25 м и вода), Swamp decor (декор, слитый по тайлам),
    Swamp props (крупные инстансы), LODs (уровни LODGroup), Collision proxies (коллайдеры, не рисуются).
- RoadGame — EDITABLE LEVEL — пустышки иерархии Unity (корни спавнов, Scale, LegL/ArmR и т. д.). Не переименовывать.
- References — машина игрока для масштаба.
- PREVIEW — Toxic Wetlands cameras and lights — свет и камеры презентации (не экспортируются).

Правила
- 1 unit = 1 м, Z вверх. Unity (x, y, z) = Blender (x, z, y).
- Атрибуты меша для Unity: Color (CORNER, FLOAT_COLOR; альфа < 1 = самосвечение), UVMap (атлас / тайлинг),
  Unity_MaterialParams (UV1: x = глянец, y = металл).
- У объектов исходного снимка есть unity_id: по нему Unity заменяет меш у живого объекта. Не удалять и не дублировать.
- Персонажи: меняются только меши Torso / LegL-R / ArmL-R / Weapon (багги: Body / Gun / Wheel). Пустышки-шарниры не двигать.
- tw_collider на объекте = имя меша-коллайдера (коллекция Collision proxies). tw_hidden = исходный объект выключен в игре.

Сборка и экспорт: ArtSource/Levels/ToxicWetlands/README.md (скрипты в scripts/, всё воспроизводимо).
"""


def main():
    PR.setup(64)
    cams = {
        'CAM_Overview': ((95.0, 70.0, 150.0), (-5.0, 205.0, 0.0), 30),
        'CAM_Arena': ((16.0, 222.0, 34.0), (-15.6, 264.0, 1.0), 30),
        'CAM_Arena_Low': ((-2.0, 232.0, 7.5), (-18.0, 268.0, 4.0), 28),
        'CAM_Boss': ((-20.0, 250.5, 7.0), (-15.6, 264.0, 5.2), 50),
    }
    for name, (loc, look, lens) in cams.items():
        PR.free_camera(name, loc, look, lens)
    for name, (x, z) in {'CAM_Game_Arena': (-12, 250), 'CAM_Game_CampWest': (-46, 160), 'CAM_Game_Ford': (-60, 128)}.items():
        PR.game_camera(name, (x, z))
    bpy.context.scene.camera = bpy.data.objects['CAM_Overview']
    t = bpy.data.texts.get('START HERE — Toxic Wetlands') or bpy.data.texts.new('START HERE — Toxic Wetlands')
    t.clear(); t.write(TEXT)
    for c in bpy.data.collections:
        if 'LODs' in c.name or 'Collision proxies' in c.name:
            c.hide_viewport = True
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.context.preferences.filepaths.save_version = 0     # no .blend1 backup next to the deliverable
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    bpy.ops.file.make_paths_relative()          # textures/ next to the .blend
    bpy.ops.wm.save_mainfile(compress=True)
    print('TW_FINAL saved', out, flush=True)


if __name__ == '__main__':
    main()
