import sys, importlib, math
from pathlib import Path
_SCRIPT_DIR = Path(__file__).resolve().parent
_LIB = str(_SCRIPT_DIR / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
import mb
importlib.reload(mb)
from mb import MB, C, shade, mixc, glow, fillet, arc, rrect, circle, resample, frame_from_z, hash01, replace_mesh, tri_count


def mesh_stats(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = bm.calc_volume(signed=True)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bound = sum(1 for e in bm.edges if e.is_boundary)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    return dict(volume=round(vol, 6), nonmanifold=nonman, boundary=bound, tris=tris)
SP = str(_SCRIPT_DIR)


def load(name):
    exec(open(SP + "/" + name).read(), globals())
