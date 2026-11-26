"""Final touches of the editable .blend: presentation light and cameras (not exported) and a START HERE text."""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awl_render as AR  # noqa: E402

TEXT = """Ashen Winter / Пепельная зима — третья зона RoadGame (индекс 2, бывшие Salt Flats)

Коллекции (внутри Zone_02_AshenWinter — всё, что уходит в Unity, бандл Levels/AshenWinterZ2):
- Terrain — земля тайлами 25 м, курганы-холмы, снежные массивы по краям зоны, сугробы.
- Roads — снежные обочины, отбойники, фонари на столбиках.
- Ramps — прыжковая рампа с шевронами, площадка приземления, объездной путь.
- Bunker — бункер над главной дорогой: портал, тоннель, три решётки, курган.
- ReactorArena — приподнятая арена: площадка, подпорная стена, кольцо, парапет, укрытия, арочные рёбра, пандусы.
- ReactorBackdrop — цех реактора, градирня, труба, трубопровод, опоры ЛЭП, виадук.
- BurntForest, Wrecks, Props — обгоревший лес, остовы машин, бетонные блоки и выходы породы.
- Collision — прокси коллизий (не рисуются; экспортируются как коллайдеры).
- LOD — уровни LODGroup (упрощённые дальние версии).
- DevSpawns — точка прибытия DEV-меню (ремонтная площадка зоны).
- RoadGame — EDITABLE LEVEL — пустышки иерархии Unity (корни спавнов). Не переименовывать.

Правила:
- 1 unit = 1 м, Z вверх. Unity (x, y, z) = Blender (x, z, y).
- Игровые размеры (арена, пандусы, рампа, бункер, зоны запрета) — в data/AshenWinter_layout.json; Unity читает тот же файл (AshenSurfaces.cs).
- Атрибуты меша: Color (CORNER, FLOAT_COLOR; альфа < 1 = самосвечение), UVMap, Unity_MaterialParams (x глянец, y металл).
- unity_id у объектов снимка: по нему Unity находит живой объект. tw_hidden = исходник выключен; aw_disable_colliders = выключены и его коллайдеры.
- tw_collider = имя прокси коллизии; tw_roof = крыша, прозрачнеет над машиной.

Сборка и экспорт: ArtSource/Levels/AshenWinter/README.md.
"""


def main():
    AR.stage()
    for name, (pos, look, lens) in AR.VIEWS.items():
        cam = bpy.data.objects.new('CAM_' + name, bpy.data.cameras.new('CAM_' + name))
        bpy.data.collections[AR.STAGE].objects.link(cam)
        AR.aim(cam, pos, look, lens)
    bpy.context.scene.camera = bpy.data.objects['CAM_overview']
    t = bpy.data.texts.get('START HERE — Ashen Winter') or bpy.data.texts.new('START HERE — Ashen Winter')
    t.clear(); t.write(TEXT)
    for c in bpy.data.collections:
        if c.name in ('LOD', 'Collision'):
            c.hide_viewport = True
    out = sys.argv[sys.argv.index('--') + 1]
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    print('AWL_FINAL saved', out, flush=True)


if __name__ == '__main__':
    main()
