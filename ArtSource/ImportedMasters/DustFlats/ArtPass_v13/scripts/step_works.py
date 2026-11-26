"""Step: Mammoth Works industrial landmark. Details are appended inside the existing objects
(so roof / lid pieces stay in the Roofs collection and fade with them in Unity). Engineering detail is kept
flush with walls or above head height, outside the 10 m driving lanes and the 48 x 34 m arena floor.
Blender coords: hangar floor z = -4.5 (rect x 28..76, y 54..88), roof slab top z ~ 3.4,
entrance ramp x 22..42 / y 37..47, tunnel y 37..47 then north to y 53."""
import bpy, math, random
import numpy as np
from mathutils import Vector, Matrix
import rg_lib as L
import rg_kit as K
from step_rocks import original_arrays
from step_structures import with_mat

LAMP = (1.0, 0.86, 0.55, 0.25, 0.6, 0.0)          # self-lit (alpha < 1 -> emission in RoadToon)
RED_LAMP = (1.0, 0.18, 0.08, 0.3, 0.6, 0.0)


def S(kind, k=1.0):
    return L.surf(kind, k)


def augment2(ob, ctx, build_fn, note, retex=None):
    me = ob.data
    arr = original_arrays(me, np.ones(len(me.vertices), bool))
    arr = with_mat(arr, 0)
    if retex:
        arr = retex(arr)
    acc = L.MeshAccumulator(); acc.add(arr)
    p = L.Part(); build_fn(p)
    acc.add(with_mat(p.arrays(), 1)); p.free()
    mats = [ob.material_slots[0].material, ctx['mats']['Trim_Structures']]
    new = acc.build(me.name + '__v11', materials=mats, sharp_angle=35.0)
    users, _ = L.swap_mesh(me, new, note=note)
    for o in users:
        L.set_object_materials(o, mats)


def retex_walls(strip, pred, m_per_u=3.0, darken=1.0):
    """Move original vertical faces matching pred(centre, normal) to the trim slot with strip UVs (V = height)."""
    def fn(arr):
        arr = dict(arr); arr['mat'] = arr['mat'].copy(); arr['uv'] = arr['uv'].copy(); arr['col'] = arr['col'].copy()
        v0, v1 = K._strip(strip)
        co = arr['co']; li = 0
        for fi, n in enumerate(arr['flen']):
            idx = arr['lv'][li:li + n]; pts = co[idx]
            nrm = np.cross(pts[1] - pts[0], pts[2] - pts[0]); nl = np.linalg.norm(nrm)
            if nl > 1e-9:
                nrm = nrm / nl
                c = pts.mean(0)
                if abs(nrm[2]) < 0.2 and pred(c, nrm):
                    t = np.array([-nrm[1], nrm[0], 0.0]); t /= max(1e-6, np.linalg.norm(t))
                    zmin, zmax = pts[:, 2].min(), pts[:, 2].max()
                    for k, vi in enumerate(idx):
                        q = co[vi]
                        u = float(q @ t) / m_per_u
                        v = v0 + (v1 - v0) * (q[2] - zmin) / max(zmax - zmin, 1e-3)
                        arr['uv'][li + k] = (u, v)
                        arr['col'][li + k, :3] *= darken
                    arr['mat'][fi] = 1
            li += n
        return arr
    return fn


# ------------------------------------------------------------------------------------------------
def roof_details(p):
    zt = 3.42
    steel = S('steel_dark', 1.25); galv = S('galvanized', 0.85)
    # perimeter steel fascia channel
    for (a, b) in (((26.5, 52.5), (77.5, 52.5)), ((77.5, 52.5), (77.5, 89.5)), ((77.5, 89.5), (26.5, 89.5)), ((26.5, 89.5), (26.5, 52.5))):
        K.beam(p, (a[0], a[1], zt - 0.25), (b[0], b[1], zt - 0.25), 0.18, 0.55, steel, 'panel', 0.02, ext=0.18)
    # lattice trusses running N-S (top chord, bottom chord, verticals, diagonals)
    for x in (31.5, 40.5, 71.5):
        y0, y1 = 53.2, 88.8; h = 0.85
        K.beam(p, (x, y0, zt + h), (x, y1, zt + h), 0.2, 0.18, (0.42, 0.16, 0.06, 1, 0.45, 0.25), 'panel', 0.015)
        K.beam(p, (x, y0, zt + 0.1), (x, y1, zt + 0.1), 0.2, 0.16, steel, 'panel', 0.015)
        n = 12
        for i in range(n + 1):
            y = y0 + (y1 - y0) * i / n
            K.beam(p, (x, y, zt + 0.1), (x, y, zt + h), 0.1, 0.1, steel, 'plain', 0.0)
            if i < n:
                yb = y0 + (y1 - y0) * (i + 1) / n
                a, b = ((x, y, zt + 0.12), (x, yb, zt + h - 0.02)) if i % 2 == 0 else ((x, y, zt + h - 0.02), (x, yb, zt + 0.12))
                K.beam(p, a, b, 0.07, 0.07, steel, 'plain', 0.0)
    # HVAC units with fan grilles
    for (cx, cy) in ((47.0, 84.5), (63.0, 84.5)):
        K.box(p, (5.0, 2.6, 1.3), Matrix.Translation((cx, cy, zt + 0.7)), S('galvanized', 0.95), 'panel', 0.06, wear=S('steel'))
        K.box(p, (5.2, 2.8, 0.16), Matrix.Translation((cx, cy, zt + 0.08)), steel, 'plain', 0.02)
        for dx in (-1.3, 1.3):
            K.cyl_between(p, (cx + dx, cy, zt + 1.3), (cx + dx, cy, zt + 1.45), 0.95, S('steel_dark', 1.1), 16)
            K.cyl_between(p, (cx + dx, cy, zt + 1.45), (cx + dx, cy, zt + 1.5), 0.82, S('black', 1.4), 16)
            for k in range(3):   # fan blades
                a = k * 2 * math.pi / 3 + 0.4
                K.box(p, (0.75, 0.22, 0.03), Matrix.Translation((cx + dx, cy, zt + 1.5)) @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Translation((0.38, 0, 0)) @ Matrix.Rotation(0.35, 4, 'X'),
                      S('galvanized', 0.7), 'plain', 0.0)
        # duct into roof
        K.box(p, (1.0, 1.4, 0.9), Matrix.Translation((cx - 3.0, cy, zt + 0.45)), S('galvanized', 0.8), 'corrugated', 0.04)
    # exhaust stacks with rain caps and red warning lamps (landmark silhouette, casts long shadows)
    for i, (cx, cy, hgt) in enumerate(((75.0, 61.5, 4.2), (75.0, 65.0, 5.2), (75.0, 68.5, 3.6))):
        K.cyl_between(p, (cx, cy, zt - 0.1), (cx, cy, zt + hgt), 0.42, (0.48, 0.17, 0.07, 1, 0.3, 0.3), 16, 'rustplate', m_per_u=1.5)
        for z in (zt + 0.6, zt + hgt * 0.55, zt + hgt - 0.3):
            K.cyl_between(p, (cx, cy, z - 0.08), (cx, cy, z + 0.08), 0.47, steel, 16)
        K.cyl_between(p, (cx, cy, zt + hgt + 0.25), (cx, cy, zt + hgt + 0.5), 0.62, steel, 16, r2=0.08)
        for (dx, dy) in ((0.45, 0), (-0.45, 0)):
            K.beam(p, (cx + dx, cy + dy, zt + hgt), (cx + dx * 0.9, cy + dy, zt + hgt + 0.25), 0.04, 0.04, steel, 'plain', 0.0)
        K.cyl_between(p, (cx - 0.48, cy, zt + hgt - 0.25), (cx - 0.62, cy, zt + hgt - 0.25), 0.1, RED_LAMP, 8)
        # guy brackets to the roof
        K.beam(p, (cx, cy - 0.4, zt + 1.6), (cx, cy - 1.6, zt + 0.05), 0.07, 0.07, steel, 'plain', 0.0)
        K.beam(p, (cx - 0.4, cy, zt + 1.6), (cx - 1.6, cy, zt + 0.05), 0.07, 0.07, steel, 'plain', 0.0)
    # cable trays across the roof (HVAC -> stacks) on low stands
    for (a, b) in (((49.6, 84.5), (60.4, 84.5)), ((65.6, 84.5), (73.5, 84.5)), ((73.5, 84.5), (73.5, 70.0))):
        K.beam(p, (a[0], a[1], zt + 0.42), (b[0], b[1], zt + 0.42), 0.5, 0.1, galv, 'diamond', 0.0)
        L_ = (Vector(b) - Vector(a)).length
        for t in np.linspace(0, 1, max(2, int(L_ / 2.5) + 1)):
            q = Vector(a).lerp(Vector(b), t)
            K.beam(p, (q.x, q.y, zt), (q.x, q.y, zt + 0.38), 0.06, 0.06, steel, 'plain', 0.0)
    # corner warning beacons
    for (x, y) in ((26.9, 52.9), (77.1, 52.9), (77.1, 89.1), (26.9, 89.1)):
        K.cyl_between(p, (x, y, zt), (x, y, zt + 0.5), 0.07, steel, 8)
        K.cyl_between(p, (x, y, zt + 0.5), (x, y, zt + 0.72), 0.16, RED_LAMP, 10)
    # pendant lamps above the light pools (hang from the roof -> fade with it)
    for (x, y) in ((44, 64), (66, 64), (44, 79), (66, 79), (56, 71)):
        K.cyl_between(p, (x, y, 3.0), (x, y, 0.6), 0.04, steel, 6)
        K.cyl_between(p, (x, y, 0.6), (x, y, 0.15), 0.12, steel, 10)
        K.cyl_between(p, (x, y, 0.2), (x, y, -0.15), 0.75, S('paint_yellow', 0.8), 16, r2=0.25)
        K.cyl_between(p, (x, y, -0.16), (x, y, -0.19), 0.6, LAMP, 16)


def parapet_details(p, side):
    """Exterior pilasters, top coping, plinth and floodlights on the above-ground hangar walls."""
    steel = S('steel_dark', 1.2)
    if side in ('N', 'S'):
        y = 88.5 if side == 'N' else 53.5
        out = 1 if side == 'N' else -1
        K.beam(p, (27.0, y, 3.06), (77.0, y, 3.06), 1.25, 0.14, S('galvanized', 0.8), 'panel', 0.02)
        K.beam(p, (27.0, y + out * 0.62, 0.22), (77.0, y + out * 0.62, 0.22), 0.3, 0.44, S('concrete', 0.85), 'concrete', 0.03)
        for x in np.arange(29.0, 77.0, 4.1):
            K.box(p, (0.32, 0.28, 2.95), Matrix.Translation((x, y + out * 0.64, 1.5)), (0.40, 0.14, 0.05, 1, 0.42, 0.25), 'panel', 0.02)
        for x in (36.0, 52.0, 68.0):
            K.beam(p, (x, y + out * 0.5, 2.7), (x, y + out * 1.25, 2.9), 0.08, 0.08, steel, 'plain', 0.0)
            K.box(p, (0.6, 0.35, 0.3), Matrix.Translation((x, y + out * 1.3, 2.85)) @ Matrix.Rotation(-out * 0.5, 4, 'X'), steel, 'plain', 0.03)
            K.box(p, (0.5, 0.04, 0.22), Matrix.Translation((x, y + out * 1.47, 2.78)) @ Matrix.Rotation(-out * 0.5, 4, 'X'), LAMP, 'plain', 0.0)
    elif side == 'E':
        x = 76.5
        K.beam(p, (x, 53.5, 3.06), (x, 88.5, 3.06), 1.25, 0.14, S('galvanized', 0.8), 'panel', 0.02)
        K.beam(p, (x + 0.62, 53.5, 0.22), (x + 0.62, 88.5, 0.22), 0.3, 0.44, S('concrete', 0.85), 'concrete', 0.03)
        for y in np.arange(55.5, 88.0, 4.1):
            K.box(p, (0.28, 0.32, 2.95), Matrix.Translation((x + 0.64, y, 1.5)), (0.40, 0.14, 0.05, 1, 0.42, 0.25), 'panel', 0.02)
        # exterior pipe run along the east wall (to the stacks above)
        K.pipe(p, [(77.25, 56.0, 0.0), (77.25, 56.0, 2.2), (77.25, 74.0, 2.2), (77.25, 74.0, 3.4)], 0.18, (0.30, 0.33, 0.35, 1, 0.45, 0.5), 10)
        for y in np.arange(58.0, 74.0, 3.0):
            K.box(p, (0.3, 0.12, 0.4), Matrix.Translation((77.05, y, 2.2)), steel, 'plain', 0.0)
    elif side == 'W':
        x = 27.5
        K.beam(p, (x, 54.0, 3.06), (x, 80.0, 3.06), 1.3, 0.14, S('galvanized', 0.8), 'panel', 0.02)
        for y in np.arange(56.0, 79.0, 4.1):
            K.box(p, (0.28, 0.32, 2.95), Matrix.Translation((x - 0.66, y, 1.5)), (0.40, 0.14, 0.05, 1, 0.42, 0.25), 'panel', 0.02)


def hangar_interior(p):
    """Crane rails on the column line, floodlights, cable trays, hazard kick-strips (flush with walls)."""
    steel = S('steel_dark', 1.2); yel = S('paint_yellow', 0.85)
    for (y, face) in ((87.2, 1), (54.8, -1)):
        # crane rail girder resting on corbels at the column heads (well above the arena floor)
        K.beam(p, (28.6, y, -0.55), (75.4, y, -0.55), 0.5, 0.6, yel, 'panel', 0.02)
        K.beam(p, (28.6, y, -0.15), (75.4, y, -0.15), 0.2, 0.12, steel, 'plain', 0.0)
        xs = np.arange(33.0, 76.0, 8.0) if face > 0 else np.arange(37.0, 78.0, 8.0)
        for x in xs:
            if x > 76:
                continue
            K.box(p, (0.9, 0.7, 0.4), Matrix.Translation((x, y + face * 0.05, -0.95)), steel, 'plain', 0.03)
            # floodlight on every column head, aimed into the arena
            yl = y - face * 0.32
            K.box(p, (0.7, 0.35, 0.4), Matrix.Translation((x + 1.8, yl, -0.95)) @ Matrix.Rotation(face * 0.6, 4, 'X'), steel, 'plain', 0.03)
            K.box(p, (0.6, 0.04, 0.3), Matrix.Translation((x + 1.8, yl - face * 0.19, -1.05)) @ Matrix.Rotation(face * 0.6, 4, 'X'), LAMP, 'plain', 0.0)
            K.beam(p, (x + 1.8, y + face * 0.25, -0.8), (x + 1.8, yl, -0.9), 0.06, 0.06, steel, 'plain', 0.0)
        # cable tray + two service pipes flush with the wall between columns
        yw = 88.0 - 0.18 if face > 0 else 54.0 + 0.18
        K.beam(p, (28.4, yw, -0.25), (75.6, yw, -0.25), 0.35, 0.08, S('galvanized', 0.8), 'diamond', 0.0)
        K.cyl_between(p, (28.4, yw - face * 0.05, -1.9), (75.6, yw - face * 0.05, -1.9), 0.12, (0.30, 0.33, 0.35, 1, 0.45, 0.5), 10)
        K.cyl_between(p, (28.4, yw - face * 0.05, -2.25), (75.6, yw - face * 0.05, -2.25), 0.09, (0.45, 0.12, 0.05, 1, 0.45, 0.3), 10)
        # hazard kick-strip along the wall base (2 cm plate)
        yk = 88.0 - 0.012 if face > 0 else 54.0 + 0.012
        for x0 in np.arange(28.5, 75.5, 4.0):
            K.sheet(p, (x0, yk, -4.5), (min(4.0, 75.5 - x0), 0, 0), (0, 0, 0.55), 0.02, (1, 1, 1, 1, 0.4, 0.1), 'hazard', 1.1)
    # east wall: tray + kick strip
    K.beam(p, (76.0 - 0.18, 54.5, -0.25), (76.0 - 0.18, 87.5, -0.25), 0.35, 0.08, S('galvanized', 0.8), 'diamond', 0.0)
    for y0 in np.arange(54.5, 87.5, 4.0):
        K.sheet(p, (75.988, y0, -4.5), (0, min(4.0, 87.5 - y0), 0), (0, 0, 0.55), 0.02, (1, 1, 1, 1, 0.4, 0.1), 'hazard', 1.1)
    # a few steel floor plates & drain grates (1.5 cm, flat; not obstacles)
    for (x, y, a) in ((40.0, 70.0, 0.1), (64.0, 73.0, -0.2), (52.5, 82.5, 0.0), (58.0, 59.0, 0.3)):
        K.box(p, (2.2, 1.6, 0.015), Matrix.Translation((x, y, -4.493)) @ Matrix.Rotation(a, 4, 'Z'), S('steel_dark', 1.5), 'diamond', 0.0)
    for (x, y) in ((70.5, 86.6), (34.5, 55.4)):
        K.box(p, (3.0, 0.5, 0.015), Matrix.Translation((x, y, -4.493)), S('black', 1.5), 'diamond', 0.0)


def entrance_details(p):
    steel = S('steel_dark', 1.2); yel = S('paint_yellow', 0.85)
    # portal frame on the tunnel mouth, flush with the side walls (opening stays 10 m)
    for y in (36.82, 47.18):
        K.box(p, (0.5, 0.36, 5.0), Matrix.Translation((34.45, y, -2.0)), yel, 'panel', 0.03, wear=S('steel'))
    K.box(p, (0.6, 11.2, 0.6), Matrix.Translation((34.4, 42.0, 0.0)), yel, 'panel', 0.03, wear=S('steel'))
    K.sheet(p, (34.08, 37.2, -0.28), (0, 9.6, 0), (0, 0, 0.5), 0.03, (1, 1, 1, 1, 0.4, 0.1), 'hazard', 1.0)
    # header plate rivets
    for y in np.linspace(37.5, 46.5, 10):
        K.bolt(p, (34.07, y, 0.2), (-1, 0, 0), 0.05, S('steel', 0.9), 0.04)
    # guard rails on top of the ramp side walls (posts + two rails)
    for y in (36.7, 47.3):
        xs = np.arange(22.4, 35.0, 1.6)
        for x in xs:
            K.beam(p, (x, y, 0.85), (x, y, 1.85), 0.07, 0.07, yel, 'plain', 0.0)
        for z in (1.35, 1.85):
            K.beam(p, (22.4, y, z), (34.6, y, z), 0.06, 0.06, yel, 'plain', 0.0)
        # cable tray on the outer face of the wall
        out = -1 if y < 42 else 1
        K.beam(p, (22.3, y + out * 0.42, 0.45), (34.8, y + out * 0.42, 0.45), 0.08, 0.3, S('galvanized', 0.8), 'diamond', 0.0)
    # wall lamps on the ramp walls (flat, 3 m above the local floor)
    for x in (26.0, 30.5, 35.0 - 1.5):
        floor_z = -4.5 * min(1.0, max(0.0, (x - 22.0) / 20.0))
        for y, face in ((37.02, 1), (46.98, -1)):
            K.box(p, (0.6, 0.1, 0.25), Matrix.Translation((x, y + face * 0.05, floor_z + 3.0)), steel, 'plain', 0.02)
            K.box(p, (0.5, 0.02, 0.15), Matrix.Translation((x, y + face * 0.11, floor_z + 2.97)), LAMP, 'plain', 0.0)
    # concrete wall panels: vertical pilaster joints (thin, flush)
    for y, face in ((37.0, 1), (47.0, -1)):
        for x in np.arange(23.5, 35.0, 2.5):
            K.box(p, (0.18, 0.04, 5.2), Matrix.Translation((x, y + face * 0.02, -2.0)), S('concrete_dark', 1.1), 'concrete', 0.0)
    # bollards at the top corners, outside the lane
    for (x, y) in ((21.6, 36.1), (21.6, 47.9)):
        K.cyl_between(p, (x, y, -0.05), (x, y, 1.1), 0.18, yel, 12, bevel=0.03)
        K.cyl_between(p, (x, y, 0.7), (x, y, 0.9), 0.19, S('black'), 12)
    # drainage channel grate across the ramp foot (flat)
    K.box(p, (0.6, 9.6, 0.02), Matrix.Translation((41.4, 42.0, -4.49)), S('black', 1.6), 'diamond', 0.0)


def tunnel_details(p):
    steel = S('steel_dark', 1.2); yel = S('paint_yellow', 0.85)
    # support ribs flush with the tunnel walls every 4 m (east-west leg)
    for x in np.arange(38.0, 60.0, 4.0):
        for y, face in ((37.0, 1), (47.0, -1)):
            if 49.5 < x < 60.5 and face < 0:
                continue   # opening to the north leg
            K.box(p, (0.35, 0.08, 4.5), Matrix.Translation((x + 1.0, y, -2.25)), yel, 'panel', 0.015, wear=S('steel'))   # recessed: <= 4 cm into the lane
    # cable tray on the north wall
    K.beam(p, (36.0, 46.82, -0.6), (49.0, 46.82, -0.6), 0.35, 0.08, S('galvanized', 0.8), 'diamond', 0.0)
    for x in np.arange(36.5, 49.0, 2.0):
        K.box(p, (0.06, 0.3, 0.3), Matrix.Translation((x, 46.85, -0.45)), steel, 'plain', 0.0)


def lid_beams(p, x0, x1, y0, y1):
    """Ceiling beams under a tunnel lid (part of the lid -> fades with it)."""
    steel = S('steel_dark', 1.2)
    for x in np.arange(x0 + 1.0, x1, 4.0):
        K.beam(p, (x, y0 + 0.1, -0.22), (x, y1 - 0.1, -0.22), 0.3, 0.4, steel, 'panel', 0.015)


def vents_details(p):
    steel = S('steel_dark', 1.2)
    for (x, y) in ((44.0, 46.3), (58.8, 38.0), (58.8, 51.5)):
        for k in range(5):
            K.box(p, (1.05, 0.06, 0.1), Matrix.Translation((x, y - 0.42 + k * 0.21, 0.83)) @ Matrix.Rotation(0.5, 4, 'X'), S('galvanized', 0.8), 'plain', 0.0)
        K.box(p, (1.4, 1.4, 0.12), Matrix.Translation((x, y, 0.06)), S('concrete', 0.8), 'concrete', 0.02)
        for (dx, dy) in ((-0.62, -0.62), (0.62, -0.62), (-0.62, 0.62), (0.62, 0.62)):
            K.bolt(p, (x + dx, y + dy, 0.12), (0, 0, 1), 0.04, S('steel', 0.9), 0.04)


def run(ctx):
    done = []
    def do(name, fn, note, retex=None):
        ob = bpy.data.objects.get(name)
        if ob is None:
            print('works: missing', name); return
        augment2(ob, ctx, fn, note, retex); done.append(name)
    do('HangarRoof.001', roof_details, 'v11: roof fascia, lattice trusses, HVAC units, exhaust stacks, cable trays, beacons, pendant lamps (roof object)')
    do('HangarWallN', lambda p: parapet_details(p, 'N'), 'v11: pilasters, coping, plinth, floodlights')
    do('HangarWallS', lambda p: parapet_details(p, 'S'), 'v11: pilasters, coping, plinth, floodlights')
    do('HangarWallE', lambda p: parapet_details(p, 'E'), 'v11: pilasters, coping, plinth, pipe run')
    do('HangarWallW', lambda p: parapet_details(p, 'W'), 'v11: pilasters, coping')
    do('WorksHangar', hangar_interior, 'v11: crane girders, floodlights, cable trays, pipes, hazard kick-strips, floor plates; walls get concrete trim UV',
       retex=retex_walls('concrete', lambda c, n: (27.0 < c[0] < 77.0 and 53.0 < c[1] < 89.0 and c[2] < -0.2), 3.0, 1.0))
    do('WorksEntrance', entrance_details, 'v11: portal frame, guard rails, wall lamps, cable trays, panel joints, bollards, drain grate',
       retex=retex_walls('concrete', lambda c, n: (22.0 < c[0] < 35.5 and c[2] < 0.9), 3.0, 1.0))
    do('WorksTunnel', tunnel_details, 'v11: support ribs, cable tray',
       retex=retex_walls('concrete', lambda c, n: True, 3.0, 1.0))
    do('Vents', vents_details, 'v11: louvres, concrete curbs, bolts')
    do('TunnelLid0', lambda p: lid_beams(p, 35.0, 47.0, 36.4, 47.6), 'v11: ceiling beams (lid object)')
    do('TunnelLid1', lambda p: lid_beams(p, 47.0, 60.6, 36.4, 47.6), 'v11: ceiling beams (lid object)')
    ctx['stats']['works'] = done
    print('STEP works done', len(done), flush=True)
