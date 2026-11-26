"""Export the Ashen Winter enemies as a runtime bundle for Unity (Scripts/World/Mutants.cs, zone 2 bundle).

    Blender -b AshenWinter_Enemies_v1.blend --python aw_export.py -- --output Assets/RoadGame/Resources/Creatures/AshenWinterEnemies

Same format and manifest as the swamp mutants (mut_export.py, reused as is): 14 float32 per vertex (position,
normal, linear colour RGBA, UV0, UV1 = gloss / metal), Unity axes (x, z, y) with reversed winding, int32 indices
per submesh; manifest.json lists the creatures (Unity ModelId, root node, rest-pose height and footprint) and every
node with its parent, joint pivot, mesh, materials and LOD level. The .blend is read only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aw_lib  # noqa: E402,F401  (puts the mutant scripts on sys.path)
import mut_export  # noqa: E402

if __name__ == '__main__':
    mut_export.main()
