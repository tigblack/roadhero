"""Toxic Wetlands characters: six swamp enemies and the Sludge Baron, built into the existing rig parts.

Every zone-1 spawn root keeps its hierarchy (Spawn_<id>_<Model> / Scale / Torso, LegL/LegLMesh, LegR/LegRMesh,
ArmL/ArmLMesh, ArmR/ArmRMesh, ArmR/Weapon; Buggy: Body / Gun / Muzzle, WheelSteer / Wheel). Only the mesh data
of the mesh objects changes; pivots, names, unity_id and the empties' transforms are untouched, so Unity's
procedural animation (leg / arm swings, raise to aim, wind-up, slam, death pose, wheel spin, turret yaw) works
as before. All instances of one enemy type share its meshes. Geometry is designed in the rig's 'Scale' space
(Blender: x right, y forward, z up; same numbers as ModelsActors.cs with y and z swapped) and moved into each
part's local frame, measured from the scene.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

import tw_lib as L
from tw_lib import Acc, Surf


def C(h, gloss=0.2, metal=0.0, glow=0.0, strip='plain'):
    return Surf(h, gloss, metal, glow, strip, 'TW_Character')


# ------------------------------------------------------------------------------------------------ palette
K = {
    'orange':     C('#C8692F', 0.30, strip='rubber'),     # faded hazmat orange: the enemy colour of the zone
    'orange_dk':  C('#9A4A26', 0.28, strip='rubber'),
    'rust_suit':  C('#A4502C', 0.26, strip='rubber'),
    'olive':      C('#666842', 0.20, strip='rubber'),
    'olive_dk':   C('#45482F', 0.22, strip='rubber'),
    'khaki':      C('#8C8058', 0.04, strip='canvas'),
    'khaki_dk':   C('#6A6043', 0.04, strip='canvas'),
    'greygreen':  C('#6E786A', 0.06, strip='canvas'),
    'rubber':     C('#2B2D27', 0.32, strip='rubber'),
    'boot':       C('#30322A', 0.38, strip='rubber'),
    'yellow_rub': C('#D69A2E', 0.36, strip='rubber'),
    'leather':    C('#6E4C31', 0.12, strip='leather'),
    'leather_dk': C('#47321F', 0.12, strip='leather'),
    'wood':       C('#7A5B3C', 0.08, strip='leather'),
    'steel':      C('#8F948F', 0.50, 0.70, strip='metal'),
    'steel_dk':   C('#454946', 0.45, 0.60, strip='metal'),
    'rust':       C('#FFFFFF', 0.18, 0.22, strip='rust'),
    'rust_red':   C('#8E3A24', 0.30, 0.25, strip='metal'),
    'brass':      C('#B08A45', 0.55, 0.85, strip='metal'),
    'hazard':     C('#FFFFFF', 0.40, 0.10, strip='hazard'),
    'drum_yel':   C('#D3A22F', 0.45, 0.12, strip='metal'),
    'drum_olive': C('#6C6D3D', 0.42, 0.12, strip='metal'),
    'lens':       C('#C9F25A', 0.90, 0.0, glow=0.62),
    'lens_rim':   C('#2F312B', 0.45, 0.4, strip='metal'),
    'toxic':      C('#A9DC3C', 0.60, 0.0, glow=0.50),
    'toxic_dim':  C('#86B035', 0.55, 0.0, glow=0.22),
    'skin':       C('#D8B497', 0.10),
    'tape':       C('#B9AC86', 0.08, strip='canvas'),
    'tarp_or':    C('#B9683A', 0.10, strip='canvas'),
    'tarp_bl':    C('#526A7C', 0.10, strip='canvas'),
    'glass':      C('#9FC4A0', 0.90, 0.0, glow=0.10),
    'black':      C('#1E1F1C', 0.40, 0.10),
    'cream':      C('#E3D8B8', 0.30, 0.05),
    'mud':        C('#5A4E35', 0.10, strip='plain'),
    'algae':      C('#6F8A2A', 0.30, 0.0, glow=0.05),
}

Q = [0.7]   # segment budget multiplier (0.7 = enemies, 1.0 = boss close-ups)


def sg(n, lo=6):
    return max(lo, int(round(n * Q[0])))


class CAcc(Acc):
    """Character accumulator: every revolved / swept primitive takes the segment budget Q."""

    def lathe(self, prof, segs, *a, **kw):
        return super().lathe(prof, sg(segs, 8), *a, **kw)

    def tube(self, pts, radii, surf=None, segs=10, *a, **kw):
        return super().tube(pts, radii, surf, sg(segs, 5), *a, **kw)


T = Matrix.Translation
X = (1, 0, 0)


def R(ax, deg):
    return Matrix.Rotation(math.radians(deg), 4, ax)


def SC(x, y, z):
    return Matrix.Diagonal((x, y, z, 1.0))


def V(x, y, z):
    return Vector((x, y, z))


# ------------------------------------------------------------------------------------------------ shapes

def section(cx, cy, hw, hd, n=24, p=2.6, front=1.0):
    """Superellipse ring in the XY plane (front > 1 pushes the +y half forward: chest / belly)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        x = hw * math.copysign(abs(c) ** (2 / p), c)
        y = hd * math.copysign(abs(s) ** (2 / p), s)
        if y > 0:
            y *= front
        pts.append((cx + x, cy + y))
    return pts


def body_loft(acc, rows, surf, n=24, p=2.6):
    """rows: [(z, hw, hd, front, dy)] bottom -> top; closed caps."""
    secs = []
    for (z, hw, hd, front, dy) in rows:
        secs.append([V(x, y, z) for x, y in section(0.0, dy, hw, hd, n, p, front)])
    return acc.loft(secs, surf)


def tube_limb(acc, a, b, ra, rb, surf, segs=14, mid=None):
    """Tapered limb between points (rounded ends from spheres added by the caller)."""
    a, b = Vector(a), Vector(b)
    pts = [a + (b - a) * t for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    rad = [ra + (rb - ra) * t for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    if mid:
        rad[2] *= mid
    return acc.tube(pts, rad, surf, segs=segs)


def ball(acc, c, r, surf, segs=16, rings=10, M=None):
    if isinstance(r, (int, float)):
        r = (r, r, r)
    m = T(c) if M is None else T(c) @ M
    return acc.sphere(r, m, surf, segs, sg(rings, 4))


def blob(acc, c, half, surf, e=(0.6, 0.6), M=None, segs=20, rings=12):
    m = T(c) if M is None else T(c) @ M
    return acc.superellipsoid(half, e, m, surf, sg(segs, 8), sg(rings, 5))


def ring(acc, c, r_in, r_out, h, surf, axis='Z', segs=20):
    segs = sg(segs, 8)
    """Flat ring (washer / band) as a lathe."""
    prof = [(r_in, -h / 2), (r_out, -h / 2), (r_out + 0.002, 0.0), (r_out, h / 2), (r_in, h / 2), (r_in, -h / 2)]
    M = T(c)
    if axis == 'X':
        M = M @ R('Y', 90)
    elif axis == 'Y':
        M = M @ R('X', -90)
    return acc.lathe(prof, segs, M, surf, cap_bottom=False, cap_top=False, sharp=60)


def canister(acc, c, r, h, surf, band, axis_m=None, segs=18, cap=None):
    """Filter canister: rounded can with two grooves and a face plate (z axis = outward)."""
    M = T(c) @ (axis_m or Matrix())
    prof = [(0.0, 0.0), (r * 0.92, 0.0), (r, h * 0.08), (r, h * 0.3), (r * 0.93, h * 0.34), (r, h * 0.38),
            (r, h * 0.62), (r * 0.93, h * 0.66), (r, h * 0.7), (r, h * 0.9), (r * 0.9, h), (r * 0.35, h * 1.02), (0.0, h * 1.02)]
    bands = [band if i in (2, 3, 6, 7) else surf for i in range(len(prof) - 1)]
    return acc.lathe(prof, segs, M, surf_fn=lambda i: bands[min(i, len(bands) - 1)], sharp=70)


def hose(acc, pts, r, surf, segs=8, ridges=True):
    """Corrugated hose along a smooth curve (Catmull-Rom through pts)."""
    P = [Vector(p) for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0 = P[max(0, i - 1)]; p1 = P[i]; p2 = P[i + 1]; p3 = P[min(len(P) - 1, i + 2)]
        for k in range(6):
            t = k / 6
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    if ridges:
        rad = [r * (1.0 + 0.12 * (i % 2)) for i in range(len(out))]
    else:
        rad = r
    return acc.tube(out, rad, surf, segs=segs)


def shell_cap(acc, c, radii, max_deg, thick, surf, segs=28, rings=8):
    """Front (+y) spherical cap of an ellipsoid (radii), max_deg half-angle, with a rolled rim: armour plates."""
    prof = []
    for i in range(rings + 1):
        ph = math.radians(max_deg) * i / rings
        prof.append((math.sin(ph), math.cos(ph)))
    out = [(r * (1.0 + thick), z * (1.0 + thick)) for r, z in prof]
    inner = [(r, z) for r, z in reversed(prof)]
    full = [(0.0, out[0][1])] + out[1:] + [(inner[0][0] * 0.995, inner[0][1] * 0.995)] + inner[1:-1] + [(0.0, inner[-1][1])]
    M = T(c) @ SC(radii[0], radii[1], radii[2]) @ R('X', -90)
    return acc.lathe(full, segs, M, surf, cap_bottom=False, cap_top=False, sharp=70)


# ------------------------------------------------------------------------------------------------ heads

def head_base(acc, hy, hk, skin):
    acc.cyl_between(V(0, 0, 1.56), V(0, 0.01, 1.70), 0.075, skin, segs=12)
    ball(acc, V(0, 0, hy), (0.17 * hk, 0.17 * hk, 0.18 * hk), skin, 20, 12)


def gas_mask(acc, hy, hk, style, rubber, lens, filt, band, rim=None, fscale=1.0):
    """style: 'full1' (one snout filter), 'full2' (two cheek filters), 'half' (respirator), 'boss'."""
    rim = rim or K['lens_rim']
    if style == 'half':
        blob(acc, V(0, 0.105 * hk, hy - 0.075 * hk), (0.115 * hk, 0.085 * hk, 0.085 * hk), rubber, (0.6, 0.7))
        for s in (-1, 1):
            canister(acc, V(s * 0.085 * hk, 0.15 * hk, hy - 0.11 * hk), 0.048 * hk, 0.06 * hk, filt, band,
                     R('Z', s * 35) @ R('X', -70))
        # goggles: rubber band + two round lenses
        ring(acc, V(0, 0, hy + 0.035 * hk), 0.175 * hk, 0.187 * hk, 0.05 * hk, rubber, segs=24)
        for s in (-1, 1):
            c = V(s * 0.068 * hk, 0.15 * hk, hy + 0.04 * hk)
            acc.cyl(0.056 * hk, 0.05 * hk, T(c) @ R('X', -90), rim, segs=18, bevel=0.012 * hk)
            acc.cyl(0.045 * hk, 0.012 * hk, T(c + V(0, 0.05 * hk, 0)) @ R('X', -90), lens, segs=18, bevel=0.004)
        return
    # full face shell over the front of the head
    blob(acc, V(0, 0.07 * hk, hy - 0.01 * hk), (0.165 * hk, 0.135 * hk, 0.185 * hk), rubber, (0.55, 0.65), segs=24, rings=14)
    for s in (-1, 1):
        big = 1.25 if style == 'boss' else 1.0
        c = V(s * 0.07 * hk, 0.175 * hk, hy + 0.045 * hk)
        acc.cyl(0.058 * hk * big, 0.045 * hk, T(c) @ R('X', -90) @ R('Y', s * 12), rim, segs=20, bevel=0.012 * hk)
        acc.cyl(0.048 * hk * big, 0.012 * hk, T(c + V(s * 0.005, 0.044 * hk, 0)) @ R('X', -90) @ R('Y', s * 12), lens, segs=20, bevel=0.004)
    # snout
    acc.cyl(0.062 * hk, 0.07 * hk, T(V(0, 0.17 * hk, hy - 0.085 * hk)) @ R('X', -100), rubber, segs=18, bevel=0.015 * hk)
    if style in ('full1', 'boss'):
        r = 0.075 * hk * (1.35 if style == 'boss' else 1.0)
        canister(acc, V(0, 0.225 * hk, hy - 0.095 * hk), r, 0.1 * hk, filt, band, R('X', -100), segs=20)
    if style in ('full2', 'boss'):
        for s in (-1, 1):
            canister(acc, V(s * 0.13 * hk * (1 + 0.25 * (fscale - 1)), 0.11 * hk, hy - 0.11 * hk), 0.06 * hk * fscale, 0.085 * hk * fscale, filt, band,
                     R('Z', s * 70) @ R('X', -95), segs=18)


def hood(acc, hy, hk, surf, back=0.035, low=0.16):
    prof = [(0.0, hy + 0.255 * hk), (0.07 * hk, hy + 0.245 * hk), (0.165 * hk, hy + 0.19 * hk), (0.215 * hk, hy + 0.08 * hk),
            (0.228 * hk, hy - 0.04 * hk), (0.222 * hk, hy - low * hk), (0.205 * hk, hy - (low + 0.02) * hk)]
    prof = [(r, z) for r, z in reversed(prof)]
    gap = math.radians(58)
    acc.lathe(prof, 26, T(V(0, -back, 0)) @ SC(1.0, 1.08, 1.0), surf, cap_bottom=False, cap_top=False, sharp=None,
              arc=(math.pi / 2 + gap, math.pi / 2 - gap + 2 * math.pi))
    # rolled rim along the face opening
    rim = []
    for r, z in prof:
        for a in (math.pi / 2 + gap,):
            pass
    for side in (-1, 1):
        a = math.pi / 2 + side * gap
        pts = [V(r * math.cos(a), r * math.sin(a) * 1.08 - back, z) for r, z in prof if r > 0.02]
        acc.tube(pts, 0.018 * hk, surf, segs=8)


def boot(acc, x, bw, surf, sole, cap=None, tall=0.24, big=1.0):
    """Rubber boot in leg space (hip at origin, ankle ~ -0.8)."""
    w = 0.115 * bw * big
    acc.cyl(w, tall, T(V(x, 0.0, -0.84)), surf, segs=16, bevel=0.03)
    blob(acc, V(x, 0.07 * big, -0.875), (w * 1.02, 0.19 * big, 0.08), surf, (0.45, 0.55))
    blob(acc, V(x, 0.07 * big, -0.935), (w * 1.1, 0.205 * big, 0.03), sole, (0.25, 0.4), segs=16, rings=6)
    if cap:
        blob(acc, V(x, 0.17 * big, -0.875), (w * 0.95, 0.075 * big, 0.068), cap, (0.5, 0.6))


def glove(acc, bw, surf, cuff, big=1.0):
    """Big rubber glove at the end of an arm (arm space: shoulder at origin, hand ~ -0.64)."""
    k = bw * big * 1.12
    acc.cyl(0.074 * k, 0.1, T(V(0, 0, -0.58)) @ R('X', 180), cuff, segs=16, r2=0.086 * k, bevel=0.015)
    blob(acc, V(0, 0.005, -0.67), (0.074 * k, 0.064 * k, 0.088 * k), surf, (0.55, 0.6))
    blob(acc, V(0.0, 0.058 * k, -0.648), (0.03 * k, 0.032 * k, 0.052 * k), surf, (0.7, 0.7), R('X', -25), segs=12, rings=8)


# ------------------------------------------------------------------------------------------------ humanoid kit

class Kit:
    """Builds the six part meshes of a humanoid in Scale space; part frames come from the scene."""

    def __init__(self, name, bw=1.0, hk=1.15):
        self.name, self.bw, self.hk = name, bw, hk
        self.hy = 1.82
        self.torso = CAcc(name + '_Torso', 'char', 'TW_Character')
        self.legL = CAcc(name + '_LegL', 'char', 'TW_Character')
        self.legR = CAcc(name + '_LegR', 'char', 'TW_Character')
        self.armL = CAcc(name + '_ArmL', 'char', 'TW_Character')
        self.armR = CAcc(name + '_ArmR', 'char', 'TW_Character')
        self.weapon = CAcc(name + '_Weapon', 'char', 'TW_Character')

    # pelvis + torso loft
    def trunk(self, suit, pants, chest=1.0, belly=0.0, waist=1.0):
        bw = self.bw
        t = self.torso
        blob(t, V(0, 0, 1.0), (0.235 * bw, 0.165 * bw, 0.15), pants, (0.6, 0.65))
        rows = [(0.94, 0.20 * bw * waist, 0.15 * bw, 1.0, 0.0), (1.05, 0.225 * bw * waist, 0.16 * bw, 1.0 + belly * 0.4, 0.0),
                (1.18, 0.245 * bw, 0.17 * bw, 1.0 + belly, 0.01), (1.32, 0.275 * bw * chest, 0.18 * bw, 1.0 + belly * 0.7, 0.01),
                (1.45, 0.29 * bw * chest, 0.185 * bw, 1.0, 0.0), (1.55, 0.27 * bw * chest, 0.17 * bw, 1.0, -0.01),
                (1.62, 0.19 * bw, 0.13 * bw, 1.0, -0.01), (1.665, 0.06 * bw, 0.05 * bw, 1.0, -0.01)]
        body_loft(t, rows, suit)
        # shoulder caps so the arm pivots never show a gap
        for s in (-1, 1):
            ball(t, V(s * 0.3 * bw, 0, 1.53), (0.11 * bw, 0.11 * bw, 0.1 * bw), suit)

    def belt(self, surf, buckle=None, z=1.08):
        bw = self.bw
        ring(self.torso, V(0, 0, z), 0.235 * bw, 0.25 * bw, 0.07, surf, segs=26)
        if buckle:
            blob(self.torso, V(0, 0.17 * bw, z), (0.06, 0.02, 0.045), buckle, (0.3, 0.4))

    def legs(self, pants, bootc, sole, knee=None, cap=None, wader=None, big=1.0):
        bw = self.bw
        for acc in (self.legL, self.legR):
            ball(acc, V(0, 0, -0.01), 0.112 * bw, pants)
            tube_limb(acc, V(0, 0, 0), V(0, 0.012, -0.46), 0.115 * bw, 0.097 * bw, pants)
            ball(acc, V(0, 0.012, -0.46), 0.096 * bw, pants, 14, 8)
            tube_limb(acc, V(0, 0.012, -0.46), V(0, 0, -0.78), 0.094 * bw, 0.084 * bw, pants)
            if wader:
                acc.cyl(0.108 * bw, 0.5, T(V(0, 0.0, -0.84)), wader, segs=18, r2=0.118 * bw, bevel=0.03)
                ring(acc, V(0, 0.0, -0.34), 0.105 * bw, 0.125 * bw, 0.05, wader, segs=18)
            if knee:
                blob(acc, V(0, 0.085 * bw, -0.46), (0.085 * bw, 0.045 * bw, 0.09), knee, (0.45, 0.55))
            boot(acc, 0.0, bw, bootc, sole, cap, big=big)

    def arms(self, sleeve, glovec, cuff, left_extra=None, right_extra=None, pad=None, big=1.0, bare=None):
        bw = self.bw
        for acc, extra in ((self.armL, left_extra), (self.armR, right_extra)):
            ball(acc, V(0, 0, 0), 0.104 * bw, sleeve)
            tube_limb(acc, V(0, 0, 0), V(0, -0.008, -0.3), 0.096 * bw, 0.082 * bw, sleeve)
            ball(acc, V(0, -0.008, -0.3), 0.08 * bw, sleeve, 14, 8)
            tube_limb(acc, V(0, -0.008, -0.3), V(0, -0.01, -0.56), 0.077 * bw, 0.066 * bw, bare or sleeve)
            glove(acc, bw, glovec, cuff, big)
            if pad:
                blob(acc, V(0, 0.0, -0.06), (0.115 * bw, 0.11 * bw, 0.075 * bw), pad, (0.45, 0.6))
            if extra:
                extra(acc)

    def build(self):
        return {'Torso': self.torso.build(), 'LegL': self.legL.build(), 'LegR': self.legR.build(),
                'ArmL': self.armL.build(), 'ArmR': self.armR.build(), 'Weapon': self.weapon.build()}


# ------------------------------------------------------------------------------------------------ enemies
# Weapon space (Blender local of the Weapon object): grip at the origin, weapon along -z, the gun's top along +y.

def build_scav():
    k = Kit('TW_Scav', bw=0.95, hk=1.2)
    bw, hk, hy = k.bw, k.hk, k.hy
    k.trunk(K['khaki'], K['olive_dk'], chest=0.98)
    # hooded rain cape (capelet) over the shoulders, frayed hem
    t = k.torso
    secs = []
    for j, (z, r, d) in enumerate([(1.30, 0.40, 0.31), (1.40, 0.38, 0.29), (1.50, 0.34, 0.25), (1.58, 0.27, 0.2), (1.64, 0.17, 0.14)]):
        ring_pts = []
        for i in range(28):
            a = 2 * math.pi * i / 28
            wav = 1.0 + (0.05 * math.sin(a * 7) if j == 0 else 0.0)
            ring_pts.append(V(math.cos(a) * r * bw * wav, math.sin(a) * d * bw * wav, z + (0.02 * math.sin(a * 5) if j == 0 else 0)))
        secs.append(ring_pts)
    t.loft(secs, K['khaki'], cap0=False, cap1=True)
    t.loft([[p + V(0, 0, -0.012) for p in secs[0]], secs[0]], K['khaki_dk'], cap0=False, cap1=False)
    head_base(t, hy, hk, K['skin'])
    hood(t, hy, hk, K['khaki'])
    gas_mask(t, hy, hk, 'half', K['rubber'], K['lens'], K['olive_dk'], K['toxic_dim'])
    # big junk backpack: duffel + rolled orange tarp + green jerrycan + pipe + lantern
    blob(t, V(0, -0.33, 1.3), (0.25, 0.17, 0.28), K['khaki_dk'], (0.45, 0.55))
    for s in (-1, 1):
        t.box((0.05, 0.03, 0.5), T(V(s * 0.15, -0.16, 1.4)) @ R('X', 8), K['leather_dk'], bevel=0.012)
    t.cyl(0.11, 0.56, T(V(-0.28, -0.32, 1.66)) @ R('Y', 90), K['tarp_or'], segs=18, bevel=0.03)
    for xx in (-0.18, 0.18):
        ring(t, V(xx, -0.32, 1.66), 0.105, 0.118, 0.035, K['leather_dk'], axis='X', segs=16)
    t.box((0.2, 0.13, 0.3), T(V(0.27, -0.36, 1.18)) @ R('Z', 8), K['drum_olive'], bevel=0.035)
    t.cyl(0.03, 0.06, T(V(0.31, -0.36, 1.33)), K['steel_dk'], segs=10)
    t.cyl_between(V(-0.2, -0.36, 1.05), V(-0.27, -0.33, 2.05), 0.04, K['rust'], segs=10, bevel=0.01)
    t.cyl_between(V(-0.27, -0.33, 2.05), V(-0.28, -0.33, 2.12), 0.05, K['steel_dk'], segs=10, bevel=0.01)
    # lantern with a toxic-green glow hanging from the pack
    t.cyl(0.05, 0.12, T(V(0.22, -0.46, 1.42)), K['steel_dk'], segs=12, bevel=0.01)
    t.cyl(0.04, 0.08, T(V(0.22, -0.46, 1.44)), K['toxic'], segs=12)
    # legs / arms
    k.legs(K['olive_dk'], K['boot'], K['black'], knee=K['khaki_dk'])
    k.arms(K['khaki'], K['rubber'], K['olive_dk'])
    # home-made pipe gun: taped wooden stock, pipe barrel, jar magazine of glowing sludge
    w = k.weapon
    w.box((0.085, 0.13, 0.3), T(V(0, 0.02, 0.1)), K['wood'], bevel=0.03)
    w.cyl(0.046, 1.02, T(V(0, 0.03, 0.06)) @ R('X', 180), K['steel_dk'], segs=14, bevel=0.008)
    for z in (-0.32, -0.62, -0.9):
        ring(w, V(0, 0.03, z), 0.045, 0.058, 0.04, K['tape'], segs=14)
    w.cyl(0.062, 0.07, T(V(0, 0.03, -0.92)) @ R('X', 180), K['rust'], segs=14, bevel=0.01)
    w.cyl(0.06, 0.14, T(V(0, -0.11, -0.28)) @ R('X', 180), K['glass'], segs=14, bevel=0.02)
    w.cyl(0.05, 0.11, T(V(0, -0.115, -0.295)) @ R('X', 180), K['toxic'], segs=14)
    w.cyl(0.064, 0.03, T(V(0, -0.11, -0.27)) @ R('X', 180), K['steel_dk'], segs=14)
    w.cyl_between(V(0, 0.09, -0.15), V(0, 0.09, -0.45), 0.022, K['steel'], segs=10)
    return k.build()


def build_raider():
    k = Kit('TW_Raider', bw=1.0, hk=1.15)
    bw, hk, hy = k.bw, k.hk, k.hy
    t = k.torso
    k.trunk(K['orange'], K['orange_dk'], chest=1.03)
    # chest armour cut from a yellow chemical drum: hazard band + drop label, rusty rim
    secs = []
    for z, r in ((1.12, 0.27), (1.2, 0.285), (1.42, 0.31), (1.56, 0.29)):
        secs.append([V(math.cos(a) * r * bw, math.sin(a) * r * 0.72 * bw + 0.012, z) for a in [2 * math.pi * i / 28 for i in range(28)]])
    t.loft(secs, K['drum_yel'], cap0=False, cap1=False)
    ring(t, V(0, 0.012, 1.155), 0.268 * bw, 0.292 * bw, 0.07, K['hazard'], segs=28)
    ring(t, V(0, 0.012, 1.555), 0.27 * bw, 0.298 * bw, 0.035, K['rust_red'], segs=28)
    blob(t, V(0.0, 0.235, 1.34), (0.085, 0.012, 0.085), C('#E7D9A8', 0.3, strip='plain'), (0.3, 0.3))
    blob(t, V(0.0, 0.244, 1.34), (0.04, 0.008, 0.05), K['toxic'], (0.6, 0.6))
    # one big spiked pauldron on the left shoulder (a rusty hub cap)
    t.lathe([(0.0, 0.0), (0.2, 0.0), (0.21, 0.03), (0.17, 0.09), (0.08, 0.12), (0.0, 0.125)], 22,
            T(V(-0.33, 0, 1.6)) @ R('Y', -28), K['rust'], cap_bottom=True, sharp=60)
    for i in range(3):
        a = math.radians(-90 + i * 60)
        p = V(-0.33, 0, 1.6) + Vector((math.cos(a) * 0.12, math.sin(a) * 0.12, 0.1))
        t.cyl(0.03, 0.13, T(p) @ R('Y', -28), K['steel'], segs=10, r2=0.003)
    head_base(t, hy, hk, K['skin'])
    gas_mask(t, hy, hk, 'full1', K['rubber'], K['lens'], K['steel_dk'], K['toxic_dim'])
    # rubber fin crest (the raider's mohawk)
    for i in range(6):
        zz = 0.13 - i * 0.055
        hgt = 0.12 - abs(i - 2.2) * 0.022
        blob(t, V(0, zz * hk, hy + 0.17 * hk + hgt * 0.4), (0.022, 0.035, hgt), K['orange'], (0.5, 0.5), R('X', -10 + i * 6))
    k.legs(K['orange_dk'], K['boot'], K['black'], knee=K['rust'])
    k.arms(K['orange'], K['rubber'], K['orange_dk'], pad=None)
    # valve mace: pipe shaft, a rusty T-fitting studded with bolts and a big red valve wheel
    w = k.weapon
    w.cyl(0.04, 1.05, T(V(0, 0, 0.16)) @ R('X', 180), K['steel_dk'], segs=12, bevel=0.008)
    ring(w, V(0, 0, 0.02), 0.04, 0.05, 0.12, K['tape'], segs=12)
    w.cyl(0.085, 0.24, T(V(0, 0, -0.78)) @ R('X', 180), K['rust'], segs=16, bevel=0.025)
    w.cyl(0.075, 0.26, T(V(-0.13, 0, -0.93)) @ R('Y', 90), K['rust'], segs=16, bevel=0.02)
    for s in (-1, 1):
        ring(w, V(s * 0.12, 0, -0.93), 0.07, 0.095, 0.035, K['steel_dk'], axis='X', segs=16)
    for i in range(6):
        a = 2 * math.pi * i / 6
        w.cyl(0.024, 0.09, T(V(math.cos(a) * 0.08, math.sin(a) * 0.08, -0.84)) @ R('Z', math.degrees(a)) @ R('Y', 90), K['steel'], segs=8, r2=0.004)
    # valve wheel on top (red), spokes
    wc = V(0, 0.15, -0.93)
    w.lathe([(0.12, -0.012), (0.145, -0.02), (0.15, 0.0), (0.145, 0.02), (0.12, 0.012), (0.12, -0.012)], 28,
            T(wc) @ R('X', -90), K['rust_red'], cap_bottom=False, cap_top=False)
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        w.cyl_between(wc, wc + V(math.cos(a) * 0.125, 0, math.sin(a) * 0.125), 0.013, K['rust_red'], segs=8)
    w.cyl_between(V(0, 0.07, -0.93), wc + V(0, 0.01, 0), 0.025, K['steel_dk'], segs=10)
    return k.build()


def build_spearman():
    k = Kit('TW_Spearman', bw=1.0, hk=1.15)
    bw, hk, hy = k.bw, k.hk, k.hy
    t = k.torso
    k.trunk(K['orange'], K['olive_dk'], chest=1.0)
    # chest waders (olive rubber bib) with suspenders over the orange rain jacket
    secs = []
    for z, r, d in ((0.94, 0.222, 0.168), (1.1, 0.25, 0.18), (1.24, 0.268, 0.19), (1.36, 0.292, 0.2)):
        secs.append([V(x, y + 0.004, z) for x, y in section(0, 0, r * bw, d * bw, 26, 2.6)])
    t.loft(secs, K['olive'], cap0=False, cap1=False)
    for s in (-1, 1):
        t.tube([V(s * 0.12, 0.17, 1.33), V(s * 0.16, 0.12, 1.5), V(s * 0.18, 0.0, 1.6), V(s * 0.15, -0.14, 1.5), V(s * 0.11, -0.19, 1.3)],
               0.022, K['leather_dk'], segs=8, flat=0.45)
    # boonie hat over the gas mask
    head_base(t, hy, hk, K['skin'])
    gas_mask(t, hy, hk, 'full2', K['rubber'], K['lens'], K['olive_dk'], K['toxic_dim'])
    t.lathe([(0.0, 0.0), (0.33, 0.0), (0.34, 0.02), (0.3, 0.035), (0.2, 0.045), (0.19, 0.12), (0.15, 0.17), (0.0, 0.18)], 26,
            T(V(0, -0.01, hy + 0.11 * hk)) @ R('X', -6), K['khaki'], cap_bottom=True, sharp=None)
    ring(t, V(0, -0.012, hy + 0.17 * hk), 0.19, 0.205, 0.04, K['olive_dk'], segs=24)
    # quiver tube on the back with three spare spears
    t.cyl(0.085, 0.62, T(V(-0.08, -0.25, 1.05)) @ R('X', -12) @ R('Y', 22), K['steel_dk'], segs=14, bevel=0.015)
    for i in range(3):
        o = V(-0.08 + (i - 1) * 0.045, -0.25 + (i % 2) * 0.03, 1.0)
        top = o + (R('X', -12) @ R('Y', 22)).to_3x3() @ V(0, 0, 1.25)
        t.cyl_between(o, top, 0.02, K['wood'], segs=8)
        t.cyl(0.045, 0.17, T(top) @ (R('X', -12) @ R('Y', 22)), K['steel'], segs=10, r2=0.002)
    k.legs(K['olive_dk'], K['olive'], K['black'], wader=K['olive'])
    # round shield from a chemical-drum lid on the left forearm: olive lid, hazard rim, green splash
    def shield(acc):
        c = V(0.0, 0.11, -0.42)
        M = T(c) @ R('X', -90)
        acc.lathe([(0.0, 0.035), (0.29, 0.03), (0.31, 0.015), (0.33, 0.0), (0.315, -0.02), (0.3, -0.03), (0.0, -0.03)], 32, M,
                  surf_fn=lambda i: K['drum_olive'] if i < 1 else (K['hazard'] if i in (1, 2, 3) else K['steel_dk']), sharp=55)
        acc.lathe([(0.0, 0.0), (0.16, 0.0), (0.17, 0.006), (0.0, 0.008)], 24, M @ T(V(0.02, 0.03, 0.035)), K['toxic_dim'], sharp=None)
        acc.lathe([(0.0, 0.0), (0.07, 0.0), (0.075, 0.03), (0.0, 0.04)], 16, M @ T(V(0, 0, 0.04)), K['steel'], sharp=50)
    k.arms(K['orange'], K['rubber'], K['orange_dk'], left_extra=shield)
    # spear: wooden shaft, steel leaf blade, a strapped vial of glowing chemical
    w = k.weapon
    w.cyl(0.035, 2.18, T(V(0, 0, 0.5)) @ R('X', 180), K['wood'], segs=10, bevel=0.006)
    w.lathe([(0.0, 0.0), (0.04, 0.0), (0.075, 0.12), (0.06, 0.28), (0.0, 0.44)], 12,
            T(V(0, 0, -1.62)) @ R('X', 180) @ SC(1.0, 0.42, 1.0), K['steel'], sharp=45)
    ring(w, V(0, 0, -1.6), 0.03, 0.05, 0.08, K['tape'], segs=10)
    w.cyl(0.032, 0.16, T(V(0.0, 0.055, -1.4)) @ R('X', 180), K['glass'], segs=12, bevel=0.01)
    w.cyl(0.026, 0.12, T(V(0.0, 0.055, -1.415)) @ R('X', 180), K['toxic'], segs=12)
    ring(w, V(0, 0.03, -1.36), 0.03, 0.045, 0.03, K['tape'], segs=10)
    return k.build()


def build_crossbow():
    k = Kit('TW_Crossbow', bw=1.0, hk=1.15)
    bw, hk, hy = k.bw, k.hk, k.hy
    t = k.torso
    k.trunk(K['greygreen'], K['olive_dk'], chest=1.0)
    # long leather work apron
    ap_secs = []
    for z, hw, d in ((0.98, 0.21, 0.19), (1.15, 0.235, 0.205), (1.32, 0.255, 0.21), (1.45, 0.2, 0.205)):
        row = []
        for i in range(9):
            u = -1 + 2 * i / 8
            x = u * hw
            row.append(V(x, d * math.sqrt(max(0.0, 1 - (u * 0.86) ** 2)) * 1.0 + 0.012, z))
        ap_secs.append(row)
    t.loft(ap_secs, K['leather'], cap0=False, cap1=False, closed=False)
    head_base(t, hy, hk, K['skin'])
    hood(t, hy, hk, K['greygreen'], back=0.04, low=0.13)
    gas_mask(t, hy, hk, 'full1', K['rubber'], K['lens'], K['steel_dk'], K['toxic_dim'])
    # bolt quiver: an old red extinguisher on the back, diagonal, bolts with toxic-green fletching
    Mq = T(V(0.2, -0.27, 1.12)) @ R('Y', -28) @ R('X', -14)
    t.lathe([(0.0, 0.0), (0.12, 0.0), (0.135, 0.05), (0.135, 0.66), (0.1, 0.73), (0.0, 0.74)], 18, Mq, K['rust_red'], sharp=60)
    ring(t, Mq @ Vector((0, 0, 0.12)), 0.134, 0.142, 0.05, K['hazard'], segs=18)
    ring(t, Mq @ Vector((0, 0, 0.3)), 0.104, 0.112, 0.06, K['leather_dk'], segs=18)
    for i in range(5):
        o = Mq @ Vector(((i - 2) * 0.045, ((i % 2) - 0.5) * 0.05, 0.6))
        top = Mq @ Vector(((i - 2) * 0.05, ((i % 2) - 0.5) * 0.05, 1.08))
        t.cyl_between(o, top, 0.014, K['wood'], segs=6)
        t.box((0.016, 0.1, 0.14), T(top) @ (Mq.to_quaternion().to_matrix().to_4x4()), K['toxic_dim'], bevel=0.005)
    for s in (-1, 1):
        t.tube([V(s * 0.2, 0.14, 1.36), V(s * 0.2, 0.0, 1.62), V(s * 0.18, -0.2, 1.4)], 0.02, K['leather_dk'], segs=8, flat=0.5)
    k.legs(K['olive_dk'], K['boot'], K['black'], knee=K['leather'])
    k.arms(K['greygreen'], K['leather_dk'], K['leather'])
    # crossbow: wooden stock, leaf-spring bow arms, scope pipe, loaded bolt
    w = k.weapon
    w.box((0.1, 0.12, 0.92), T(V(0, 0, -0.38)), K['wood'], bevel=0.03)
    w.box((0.08, 0.1, 0.16), T(V(0, -0.1, 0.0)) @ R('X', 20), K['wood'], bevel=0.025)
    c = V(0, 0.0, -0.78)
    for s in (-1, 1):
        pts = [c, c + V(s * 0.22, 0.0, -0.01), c + V(s * 0.42, 0.0, 0.05), c + V(s * 0.56, 0.0, 0.16)]
        w.tube(pts, [0.045, 0.04, 0.032, 0.022], K['rust'], segs=10, flat=0.45)
        w.cyl(0.025, 0.04, T(c + V(s * 0.56, 0.0, 0.16)) @ R('Y', 90), K['steel_dk'], segs=8)
    w.tube([V(-0.55, 0.0, -0.62), V(0, 0.0, -0.5), V(0.55, 0.0, -0.62)], 0.006, K['cream'], segs=6)
    w.cyl(0.012, 0.6, T(V(0, 0.07, -0.3)) @ R('X', 180), K['steel'], segs=8)
    w.lathe([(0.0, 0.0), (0.03, 0.0), (0.0, 0.1)], 8, T(V(0, 0.07, -0.9)) @ R('X', 180), K['toxic'], sharp=40)
    w.cyl(0.035, 0.32, T(V(0, 0.13, -0.15)) @ R('X', 180), K['steel_dk'], segs=12, bevel=0.01)
    w.cyl(0.03, 0.01, T(V(0, 0.13, -0.475)) @ R('X', 180), K['lens'], segs=12)
    return k.build()


def build_brute():
    k = Kit('TW_Brute', bw=1.4, hk=1.05)
    bw, hk, hy = k.bw, k.hk, k.hy
    t = k.torso
    k.trunk(K['orange'], K['orange_dk'], chest=1.05, belly=0.25)
    # quilted suit seams + reinforced shoulders
    for z in (1.18, 1.36):
        ring(t, V(0, 0.01, z), 0.0, 0.255 * bw if z < 1.3 else 0.288 * bw, 0.025, K['orange_dk'], segs=28)
    for s in (-1, 1):
        t.lathe([(0.0, 0.0), (0.2, 0.0), (0.215, 0.04), (0.18, 0.11), (0.09, 0.14), (0.0, 0.145)], 22,
                T(V(s * 0.33 * bw, 0, 1.58)) @ R('Y', s * 25), K['rust'], cap_bottom=True, sharp=60)
    head_base(t, hy, hk, K['skin'])
    hood(t, hy, hk, K['orange'], back=0.03, low=0.2)
    gas_mask(t, hy, hk, 'full2', K['rubber'], K['lens'], K['steel_dk'], K['toxic_dim'], fscale=1.6)
    # big twin filter drums on the chest straps + tank on the back with hoses to the mask
    for s in (-1, 1):
        canister(t, V(s * 0.17 * bw, 0.2 * bw, 1.36), 0.075 * bw, 0.1 * bw, K['olive_dk'], K['toxic_dim'], R('X', -80), segs=16)
        t.tube([V(s * 0.17 * bw, 0.2 * bw, 1.46), V(s * 0.15, 0.28, 1.62), V(s * 0.12, 0.2, hy - 0.16)], 0.025, K['rubber'], segs=6)
    Mt = T(V(0, -0.36 * bw, 1.08))
    t.lathe([(0.0, 0.0), (0.2, 0.0), (0.24, 0.05), (0.24, 0.55), (0.2, 0.62), (0.08, 0.64), (0.0, 0.645)], 22,
            Mt @ SC(1.0, 0.9, 1.0), K['rust_red'], sharp=60)
    for z in (0.15, 0.47):
        ring(t, Mt @ Vector((0, 0, z)), 0.235, 0.252, 0.05, K['hazard'], segs=22)
    t.cyl(0.07, 0.22, T(V(0, -0.36 * bw + 0.205, 1.25)) @ R('X', -90), K['steel_dk'], segs=14)
    t.cyl(0.055, 0.03, T(V(0, -0.36 * bw + 0.215, 1.43)) @ R('X', -90), K['toxic'], segs=14)
    t.cyl(0.06, 0.08, Mt @ T(V(0, 0, 0.64)), K['steel'], segs=12, bevel=0.01)
    for s in (-1, 1):
        hose(t, [V(s * 0.1, -0.36 * bw, 1.72), V(s * 0.24, -0.25, 1.86), V(s * 0.25, 0.0, 1.85), V(s * 0.17, 0.13, hy - 0.12)], 0.035, K['rubber'])
    k.legs(K['orange_dk'], K['boot'], K['black'], knee=K['rust'], cap=K['steel'], big=1.08)
    k.arms(K['orange'], K['rubber'], K['orange_dk'], big=1.1)
    # sludge cannon: pipe barrel, bell mouth, valve, pressure gauge, wooden grip
    w = k.weapon
    w.box((0.13, 0.2, 0.42), T(V(0, -0.04, 0.12)), K['wood'], bevel=0.04)
    w.cyl(0.085, 1.0, T(V(0, 0, 0.0)) @ R('X', 180), K['steel_dk'], segs=16, bevel=0.01)
    w.lathe([(0.08, 0.0), (0.1, 0.06), (0.15, 0.17), (0.23, 0.27), (0.24, 0.3), (0.2, 0.3), (0.13, 0.22), (0.075, 0.1)], 22,
            T(V(0, 0, -0.95)) @ R('X', 180), K['brass'], cap_bottom=False, cap_top=False, sharp=70)
    for z in (-0.3, -0.62):
        ring(w, V(0, 0, z), 0.08, 0.1, 0.06, K['brass'], segs=16)
    w.cyl_between(V(0, 0.08, -0.4), V(0, 0.2, -0.4), 0.02, K['steel_dk'], segs=8)
    wc = V(0, 0.21, -0.4)
    w.lathe([(0.06, -0.008), (0.075, -0.013), (0.078, 0.0), (0.075, 0.013), (0.06, 0.008), (0.06, -0.008)], 20,
            T(wc) @ R('X', -90), K['rust_red'], cap_bottom=False, cap_top=False)
    w.cyl(0.05, 0.05, T(V(0.09, 0.03, -0.2)) @ R('Y', 90), K['steel'], segs=14, bevel=0.01)
    w.cyl(0.04, 0.01, T(V(0.14, 0.03, -0.2)) @ R('Y', 90), K['cream'], segs=14)
    hose(w, [V(-0.05, -0.06, -0.2), V(-0.14, -0.12, 0.0), V(-0.12, -0.1, 0.2)], 0.03, K['rubber'])
    return k.build()


def build_baron():
    """The Sludge Baron: rubber work suit, belly boiler plate, yellow gauntlets and boots, back tank with a glowing
    window, big-eyed gas mask with three filters, short top hat, giant pipe wrench."""
    k = Kit('TW_SludgeBaron', bw=1.35, hk=1.1)
    bw, hk, hy = k.bw, k.hk, k.hy
    t = k.torso
    suit = C('#3D4430', 0.30, strip='rubber')
    suit_dk = C('#2C3124', 0.30, strip='rubber')
    k.trunk(suit, suit_dk, chest=1.05, belly=0.0)
    # round belly under a riveted rust boiler plate with a hazard band
    ball(t, V(0, 0.08, 1.22), (0.36 * bw, 0.33 * bw, 0.32 * bw), suit, 24, 14)
    br = (0.36 * bw * 1.04, 0.33 * bw * 1.04, 0.32 * bw * 1.04)
    shell_cap(t, V(0, 0.08, 1.22), br, 52, 0.035, K['rust'])
    for i in range(12):
        a = 2 * math.pi * i / 12
        d = Vector((math.cos(a) * math.sin(math.radians(46)), math.cos(math.radians(46)), math.sin(a) * math.sin(math.radians(46))))
        ball(t, V(0, 0.08, 1.22) + Vector((d.x * br[0] * 1.06, d.y * br[1] * 1.06, d.z * br[2] * 1.06)), 0.02 * bw, K['steel'], 8, 5)
    ring(t, V(0, 0.06, 0.98), 0.0, 0.3 * bw, 0.08, K['hazard'], segs=28)
    # pauldrons
    for s in (-1, 1):
        t.lathe([(0.0, 0.0), (0.22, 0.0), (0.235, 0.04), (0.2, 0.12), (0.1, 0.16), (0.0, 0.165)], 24,
                T(V(s * 0.33 * bw, 0, 1.6)) @ R('Y', s * 24), K['rust'], cap_bottom=True, sharp=60)
        for i in range(3):
            a = math.radians(-60 + i * 60)
            ball(t, V(s * 0.33 * bw, 0, 1.6) + (R('Y', s * 24).to_3x3() @ V(math.cos(a) * 0.15, math.sin(a) * 0.15, 0.13)), 0.022, K['steel'], 8, 5)
    # head: hazmat hood, big-eyed mask with three filters, short top hat with a toxic band
    head_base(t, hy, hk, K['skin'])
    hood(t, hy, hk, suit, back=0.03, low=0.22)
    gas_mask(t, hy, hk, 'boss', K['rubber'], K['lens'], K['steel_dk'], K['toxic'])
    hat_z = hy + 0.2 * hk
    t.cyl(0.3, 0.035, T(V(0, -0.02, hat_z)), K['black'], segs=28, bevel=0.012)
    t.lathe([(0.19, 0.0), (0.2, 0.2), (0.205, 0.22), (0.19, 0.235), (0.0, 0.24)], 26, T(V(0, -0.02, hat_z + 0.02)), K['black'], cap_bottom=False, sharp=55)
    ring(t, V(0, -0.02, hat_z + 0.075), 0.198, 0.212, 0.06, K['toxic_dim'], segs=26)
    blob(t, V(0, 0.19, hat_z + 0.075), (0.045, 0.02, 0.045), K['brass'], (0.4, 0.4))
    # back tank with a glowing window, valves, hazard bands; hoses to the side filters
    Mt = T(V(0, -0.38 * bw, 1.05))
    t.lathe([(0.0, 0.0), (0.22, 0.0), (0.27, 0.06), (0.27, 0.7), (0.22, 0.78), (0.1, 0.8), (0.0, 0.805)], 26, Mt, K['rust_red'], sharp=60)
    for z in (0.14, 0.6):
        ring(t, Mt @ Vector((0, 0, z)), 0.268, 0.285, 0.06, K['hazard'], segs=26)
    blob(t, Mt @ Vector((0.0, -0.27, 0.38)), (0.075, 0.02, 0.17), K['toxic'], (0.4, 0.4))
    t.cyl(0.07, 0.1, Mt @ T(V(0.0, 0.0, 0.8)), K['steel'], segs=14, bevel=0.012)
    for s in (-1, 1):
        t.cyl(0.11, 0.55, Mt @ T(V(s * 0.3, -0.04, 0.12)), K['steel_dk'], segs=16, bevel=0.03)
        t.cyl(0.08, 0.04, Mt @ T(V(s * 0.3, -0.04, 0.67)), K['toxic_dim'], segs=14)
        hose(t, [Mt @ Vector((s * 0.3, -0.04, 0.7)), V(s * 0.38, -0.3, 1.95), V(s * 0.3, 0.0, 1.92), V(s * 0.15, 0.12, hy - 0.12)], 0.04, K['rubber'])
    # sludge drips running down the curved plate (points on the shell surface), a pressure gauge
    bc = V(0, 0.08, 1.22)
    for x, z0, l, w in ((-0.16, 1.5, 0.34, 0.03), (0.19, 1.44, 0.42, 0.035), (0.04, 1.2, 0.22, 0.025), (-0.3, 1.25, 0.26, 0.025)):
        pts = []
        for j in range(7):
            z = z0 - l * j / 6
            u = (x / br[0]) ** 2 + ((z - bc.z) / br[2]) ** 2
            yy = bc.y + br[1] * 1.035 * math.sqrt(max(0.0, 1.0 - u)) + 0.012
            pts.append(V(x + 0.01 * math.sin(j * 1.7), yy, z))
        t.tube(pts, [w * (1.0 - 0.35 * j / 6) for j in range(7)], K['toxic'], segs=8, flat=0.55)
        t.sphere((w * 1.3, w * 0.8, w * 1.4), T(pts[-1]), K['toxic'], 10, 6)
    gp = V(0.22, bc.y + br[1] * 1.035 * math.sqrt(max(0.0, 1.0 - (0.22 / br[0]) ** 2 - ((1.12 - bc.z) / br[2]) ** 2)) + 0.02, 1.12)
    t.cyl(0.075, 0.05, T(gp) @ R('X', -90) @ R('Y', 18), K['brass'], segs=16, bevel=0.012)
    t.cyl(0.06, 0.01, T(gp + V(0.008, 0.05, 0)) @ R('X', -90) @ R('Y', 18), K['cream'], segs=16)
    t.box((0.008, 0.004, 0.05), T(gp + V(0.01, 0.062, 0.012)) @ R('Y', 35), K['black'], bevel=0.001)
    yellow = C('#D9962B', 0.36, strip='rubber')
    k.legs(suit_dk, yellow, K['black'], knee=K['rust'], cap=K['steel'], big=1.12)
    for acc in (k.legL, k.legR):
        blob(acc, V(0, 0.07 * bw, -0.66), (0.08 * bw, 0.04 * bw, 0.13), K['rust'], (0.45, 0.55))
    def gauntlet(acc):
        acc.cyl(0.085 * bw, 0.2, T(V(0, -0.01, -0.58)), K['rust'], segs=16, r2=0.075 * bw, bevel=0.02)
    k.arms(suit, yellow, yellow, left_extra=gauntlet, right_extra=gauntlet, big=1.15)
    # giant pipe wrench: I-beam handle with hazard tape, hook jaw, knurled nut, sliding jaw, toxic drips
    w = k.weapon
    w.box((0.085, 0.14, 1.0), T(V(0, 0, -0.38)), K['rust_red'], bevel=0.035)
    w.box((0.1, 0.155, 0.22), T(V(0, 0, 0.0)), K['hazard'], bevel=0.035)
    w.box((0.14, 0.24, 0.26), T(V(0, 0.04, -0.98)), K['steel_dk'], bevel=0.05)
    w.box((0.12, 0.34, 0.1), T(V(0, 0.2, -1.07)) @ R('X', 8), K['steel'], bevel=0.035)
    w.box((0.12, 0.3, 0.1), T(V(0, 0.18, -0.86)) @ R('X', -6), K['steel'], bevel=0.035)
    for i in range(6):
        w.box((0.13, 0.018, 0.03), T(V(0, 0.33 - i * 0.04, -1.122)), K['steel_dk'], bevel=0.006)
    w.cyl(0.075, 0.12, T(V(-0.06, 0.04, -0.75)) @ R('Y', 90), K['brass'], segs=18, bevel=0.012)
    for x in (-0.03, 0.0, 0.03):
        ring(w, V(x, 0.04, -0.75), 0.07, 0.08, 0.012, K['steel_dk'], axis='X', segs=18)
    for z, l in ((-1.1, 0.14), (-1.05, 0.2)):
        w.tube([V(0.04, 0.33, z), V(0.04, 0.33, z - l)], [0.02, 0.012], K['toxic'], segs=8)
    return k.build()


# ------------------------------------------------------------------------------------------------ buggy
# Body space: Blender x right, y forward, z up (Unity Body local with y/z swapped).

def build_buggy():
    body = CAcc('TW_Buggy_Body', 'char', 'TW_Character')
    gun = CAcc('TW_Buggy_Gun', 'char', 'TW_Character')
    wf = CAcc('TW_Buggy_WheelFront', 'char', 'TW_Character')
    wr = CAcc('TW_Buggy_WheelRear', 'char', 'TW_Character')
    paint = C('#A9552F', 0.42, 0.10, strip='metal')       # rust-orange swamp runner (enemy warm)
    paint_dk = C('#7A3D24', 0.40, 0.10, strip='metal')
    mudc = C('#FFFFFF', 0.12, strip='rubber')
    b = body
    # tub with mud caked low, hood, side skirts
    b.box((1.55, 2.8, 0.44), T(V(0, 0.05, 0.62)), paint, bevel=0.15)
    b.box((1.6, 2.6, 0.18), T(V(0, 0.05, 0.47)), C('#5A4E35', 0.10, strip='plain'), bevel=0.07)
    b.box((1.3, 0.8, 0.2), T(V(0, 1.05, 0.82)) @ R('X', -8), paint_dk, bevel=0.08)
    # hazard front bumper + welded rebar grille (protective cage over the nose)
    b.box((1.62, 0.18, 0.2), T(V(0, 1.52, 0.52)), K['hazard'], bevel=0.05)
    for x in (-0.78, 0.78):
        b.tube([V(x, 1.5, 0.45), V(x * 0.98, 1.72, 0.62), V(x * 0.95, 1.62, 1.05), V(x * 0.9, 1.25, 1.12)], 0.045, K['steel_dk'], segs=10)
    b.tube([V(-0.74, 1.66, 0.95), V(0.0, 1.69, 0.98), V(0.74, 1.66, 0.95)], 0.04, K['steel_dk'], segs=10)
    for i in range(7):
        x = -0.6 + i * 0.2
        b.tube([V(x, 1.6, 0.5), V(x, 1.69, 0.72), V(x, 1.66, 0.95)], 0.018, K['rust'], segs=8)
    b.tube([V(-0.72, 1.68, 0.73), V(0.72, 1.68, 0.73)], 0.018, K['rust'], segs=8)
    # headlights
    for x in (-0.5, 0.5):
        b.cyl(0.09, 0.08, T(V(x, 1.43, 0.86)) @ R('X', -90), K['steel_dk'], segs=14, bevel=0.015)
        b.cyl(0.07, 0.01, T(V(x, 1.51, 0.86)) @ R('X', -90), C('#F3E2A0', 0.6, glow=0.5), segs=14)
    # engine block at the back with upswept rusty exhausts
    b.box((1.05, 0.64, 0.46), T(V(0, -1.12, 0.95)), K['steel_dk'], bevel=0.08)
    for x in (-0.38, 0.38):
        b.cyl_between(V(x, -1.32, 1.12), V(x * 1.3, -1.55, 1.72), 0.07, K['rust'], segs=12)
        b.cyl(0.085, 0.08, T(V(x * 1.3, -1.55, 1.7)) @ R('X', 20), K['steel_dk'], segs=12, bevel=0.01)
    # snorkel air intake up the right A-pillar with a mushroom cap
    b.tube([V(0.6, 1.0, 0.85), V(0.72, 0.85, 1.0), V(0.78, 0.62, 1.3), V(0.8, 0.55, 1.6)], 0.07, K['steel_dk'], segs=12)
    b.lathe([(0.0, 0.0), (0.1, 0.0), (0.13, 0.04), (0.14, 0.1), (0.1, 0.14), (0.0, 0.15)], 16, T(V(0.8, 0.55, 1.58)), K['rust'], sharp=60)
    # roll cage (gun mount on the front cross bar at z 2.0, y 0.22)
    cage = K['steel_dk']
    bot = [V(-0.66, 0.5, 0.8), V(0.66, 0.5, 0.8), V(-0.66, -0.75, 0.8), V(0.66, -0.75, 0.8)]
    top = [V(-0.52, 0.22, 1.78), V(0.52, 0.22, 1.78), V(-0.52, -0.66, 1.78), V(0.52, -0.66, 1.78)]
    for i in range(4):
        b.cyl_between(bot[i], top[i], 0.065, cage, segs=12)
    for a_, b_ in ((0, 1), (2, 3), (0, 2), (1, 3)):
        b.cyl_between(top[a_], top[b_], 0.065, cage, segs=12)
    for p in top:
        ball(b, p, 0.075, cage, 12, 8)
    b.cyl(0.08, 0.2, T(V(0, 0.22, 1.78)), cage, segs=12)
    # algae strands hanging from the cage
    for x, y, l in ((-0.52, -0.2, 0.45), (0.3, -0.66, 0.35), (0.52, 0.0, 0.3)):
        b.tube([V(x, y, 1.76), V(x + 0.02, y + 0.03, 1.76 - l * 0.5), V(x - 0.01, y + 0.02, 1.76 - l)], [0.03, 0.025, 0.012], K['algae'], segs=7)
    # jerrycans (green and orange) and a leaking chemical drum strapped at the back
    for x, col in ((-0.86, C('#4C6A3C', 0.42, 0.1, strip='metal')), (0.86, C('#C2622E', 0.42, 0.1, strip='metal'))):
        b.box((0.16, 0.4, 0.5), T(V(x, -0.35, 0.95)), col, bevel=0.04)
        b.box((0.08, 0.16, 0.06), T(V(x, -0.3, 1.24)), col, bevel=0.02)
    b.lathe([(0.0, 0.0), (0.24, 0.0), (0.25, 0.03), (0.25, 0.58), (0.24, 0.61), (0.0, 0.61)], 20, T(V(0.0, -1.62, 0.5)),
            K['drum_yel'], sharp=60)
    ring(b, V(0, -1.62, 0.8), 0.245, 0.262, 0.06, K['hazard'], segs=20)
    b.tube([V(0.12, -1.55, 0.7), V(0.12, -1.55, 0.45)], [0.035, 0.02], K['toxic'], segs=8)
    # driver: gas mask, olive hood, orange jacket
    blob(b, V(0, -0.3, 1.08), (0.24, 0.17, 0.25), K['orange'], (0.5, 0.55))
    ball(b, V(0, -0.27, 1.48), (0.2, 0.2, 0.21), K['olive'], 18, 12)
    blob(b, V(0, -0.14, 1.45), (0.15, 0.1, 0.15), K['rubber'], (0.55, 0.65))
    for s in (-1, 1):
        b.cyl(0.05, 0.04, T(V(s * 0.065, -0.06, 1.5)) @ R('X', -90), K['lens_rim'], segs=14, bevel=0.01)
        b.cyl(0.042, 0.01, T(V(s * 0.065, -0.02, 1.5)) @ R('X', -90), K['lens'], segs=14)
    canister(b, V(0, -0.04, 1.39), 0.06, 0.08, K['olive_dk'], K['toxic_dim'], R('X', -100))
    # mud splatter on the lower body sides
    rnd = L.rng(73)
    for i in range(14):
        x = rnd.choice((-1, 1)) * 0.79
        y = -1.2 + rnd.random() * 2.5
        z = 0.42 + rnd.random() * 0.22
        blob(b, V(x, y, z), (0.03, 0.06 + rnd.random() * 0.08, 0.04 + rnd.random() * 0.05), C('#4D4330', 0.15), (0.6, 0.6))
    # gun: MG with a rusty shield plate, drum magazine (gun space: pivot at the mount, barrels along +y)
    g = gun
    g.cyl(0.06, 0.25, T(V(0, 0, -0.25)), K['steel_dk'], segs=12)
    g.box((0.26, 0.46, 0.2), T(V(0, 0.05, 0.06)), K['steel_dk'], bevel=0.05)
    for x in (-0.06, 0.06):
        g.cyl_between(V(x, 0.2, 0.08), V(x, 1.0, 0.08), 0.032, C('#2A2C2E', 0.55, 0.85, strip='metal'), segs=12)
        g.cyl(0.042, 0.06, T(V(x, 0.97, 0.08)) @ R('X', -90), K['steel'], segs=12, bevel=0.01)
    g.box((0.6, 0.04, 0.34), T(V(0, 0.3, 0.15)) @ R('X', -10), K['rust'], bevel=0.015)
    g.box((0.62, 0.05, 0.08), T(V(0, 0.29, 0.32)) @ R('X', -10), K['hazard'], bevel=0.015)
    g.cyl(0.11, 0.08, T(V(0.2, 0.0, -0.02)) @ R('Y', 90), K['olive'], segs=16, bevel=0.015)
    # wheels: chunky mud tyres with caked mud on the sidewalls and rusty dish hubs (axle along x)
    for acc, r, wdt in ((wf, 0.5, 0.38), (wr, 0.6, 0.52)):
        hw = wdt / 2
        prof = [(r * 0.55, -hw + 0.02), (r * 0.86, -hw - 0.015), (r * 0.98, -hw + r * 0.12), (r, -hw * 0.5), (r, hw * 0.5),
                (r * 0.98, hw - r * 0.12), (r * 0.86, hw + 0.015), (r * 0.55, hw - 0.02)]
        acc.lathe(prof, 22, R('Y', 90), C('#2A2B26', 0.18, strip='rubber'), cap_bottom=False, cap_top=False, sharp=None)
        for i in range(9):
            a = 2 * math.pi * i / 9
            for row in (-1, 1):
                aa = a + (math.pi / 9 if row > 0 else 0.0)
                c = V(row * hw * 0.42, math.cos(aa) * (r + 0.02), math.sin(aa) * (r + 0.02))
                acc.box((hw * 0.72, r * 0.32, r * 0.15), T(c) @ R('X', math.degrees(aa) + 90), C('#33342D', 0.18, strip='rubber'), bevel=0.03, segs=1)
        for side in (-1, 1):
            acc.lathe([(0.0, 0.0), (r * 0.5, 0.0), (r * 0.56, 0.03), (r * 0.3, 0.06), (0.0, 0.065)], 20,
                      R('Y', 90 * side) @ T(V(0, 0, hw - 0.04)), K['rust'], sharp=60)
            for i in range(5):
                a = 2 * math.pi * i / 5
                ball(acc, V(side * (hw + 0.02), math.cos(a) * r * 0.25, math.sin(a) * r * 0.25), 0.02, K['steel'], 8, 5)
            # mud caked on the sidewall (flat ring)
            acc.lathe([(r * 0.6, 0.0), (r * 0.86, 0.0)], 16, R('Y', 90 * side) @ T(V(0, 0, hw + 0.012)), C('#4E4431', 0.12),
                      cap_bottom=False, cap_top=False)
    return {'Body': body.build(), 'Gun': gun.build(), 'WheelFront': wf.build(), 'WheelRear': wr.build()}


# ------------------------------------------------------------------------------------------------ scene binding

BUILDERS = {'Scav': build_scav, 'Raider': build_raider, 'Spearman': build_spearman, 'Crossbow': build_crossbow,
            'Brute': build_brute, 'BossBaron': build_baron, 'Buggy': build_buggy}


def base_name(o):
    return o.name.split('.')[0]


def spawn_roots(model):
    return [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('Spawn_1') and o.name.endswith('_' + model)
            and o.parent is not None]


def part_objects(root):
    """Maps part key -> object for one spawn root."""
    out = {}
    for o in root.children_recursive:
        n = base_name(o)
        if o.type != 'MESH':
            continue
        if n == 'Torso':
            out['Torso'] = o
        elif n in ('LegLMesh', 'LegRMesh', 'ArmLMesh', 'ArmRMesh'):
            out[n[:4]] = o
        elif n == 'Weapon':
            out['Weapon'] = o
        elif n == 'Body':
            out['Body'] = o
        elif n == 'Gun':
            out['Gun'] = o
        elif n == 'Wheel':
            # front wheels sit at y = +1 (Blender), rear at y = -1
            out.setdefault('Wheels', []).append(o)
    return out


def scale_space(root):
    sc = [c for c in root.children if base_name(c) == 'Scale']
    return sc[0] if sc else root


def localize(mesh, M):
    """Move mesh vertices from design space into the part's local frame: v_local = M^-1 v_design."""
    mesh.transform(M.inverted())
    return mesh


def bind(model, meshes):
    """Assign the built meshes to every spawn of the model. Torso geometry is designed in Scale space (the Torso
    object has an identity local transform), legs / arms in their pivot frames (hip / shoulder at the origin,
    identity rotation), the weapon in its own frame, the buggy parts in Body / Gun / Wheel frames."""
    roots = spawn_roots(model)
    for r in roots:
        pr = part_objects(r)
        if model == 'Buggy':
            L.swap_mesh(pr['Body'], meshes['Body'])
            L.swap_mesh(pr['Gun'], meshes['Gun'])
            Bi = pr['Body'].matrix_world.inverted()
            for w in pr['Wheels']:
                y = (Bi @ w.matrix_world.translation).y
                L.swap_mesh(w, meshes['WheelFront'] if y > 0 else meshes['WheelRear'])
            continue
        for key in ('Torso', 'LegL', 'LegR', 'ArmL', 'ArmR', 'Weapon'):
            if key in pr:
                L.swap_mesh(pr[key], meshes[key])
    if roots and model != 'Buggy':
        pr = part_objects(roots[0])
        for key in ('Torso', 'LegL', 'ArmL'):
            ml = pr[key].matrix_local
            ident = all(abs(ml[i][j] - (1.0 if i == j else 0.0)) < 1e-4 for i in range(3) for j in range(4))
            if not ident:
                print('TW_CHAR WARNING non-identity part frame', model, key, ml)
        wv = pr['Weapon'].matrix_local.to_3x3() @ Vector((0, 0, -1))
        print('TW_CHAR', model, 'weapon -z in arm space ->', tuple(round(c, 3) for c in wv), flush=True)
    return len(roots)


def vertex_ao(objects, strength=0.55, dist=0.35, rays=20, seed=3):
    """Bake soft ambient occlusion into the Color attribute of the objects' meshes, measured on the assembled
    character (all parts of one instance). Meshes shared by instances are processed once."""
    import random
    from mathutils import Vector as Vec
    verts, polys = [], []
    for o in objects:
        mw = o.matrix_world
        base = len(verts)
        verts.extend([mw @ v.co for v in o.data.vertices])
        polys.extend([[base + i for i in p.vertices] for p in o.data.polygons])
    tree = BVHTree.FromPolygons(verts, polys, epsilon=0.0)
    rnd = random.Random(seed)
    dirs = []
    for i in range(rays):
        u, v = (i + 0.5) / rays, rnd.random()
        r = math.sqrt(u)
        th = 2 * math.pi * v
        dirs.append((r * math.cos(th), r * math.sin(th), math.sqrt(max(0.0, 1 - u))))
    done = set()
    for o in objects:
        me = o.data
        if me.name in done:
            continue
        done.add(me.name)
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        scale = mw.to_scale()[0]
        ao = []
        for v in me.vertices:
            p = mw @ v.co
            n = (nmat @ v.normal).normalized()
            t = n.orthogonal().normalized()
            b = n.cross(t)
            hit = 0
            for dx, dy, dz in dirs:
                d = t * dx + b * dy + n * dz
                loc, _, _, _ = tree.ray_cast(p + n * 0.004 * scale, d, dist * scale)
                if loc is not None:
                    hit += 1
            ao.append(1.0 - hit / rays)
        col = me.color_attributes.get('Color')
        if col is None:
            continue
        for li, loop in enumerate(me.loops):
            a = ao[loop.vertex_index]
            k = 1.0 - strength * (1.0 - a)
            c = col.data[li].color
            col.data[li].color = (c[0] * k, c[1] * k, c[2] * k, c[3])
    return len(done)


QUALITY = {'BossBaron': 0.9}
MUD = (0.20, 0.16, 0.08)


def mud_legs(me, z0=-0.42, z1=-0.95, strength=0.62):
    """Darken and brown the lower legs / boots like wading through sludge (leg local z: hip 0 .. sole -0.95)."""
    col = me.color_attributes.get('Color')
    if col is None:
        return
    for li, loop in enumerate(me.loops):
        z = me.vertices[loop.vertex_index].co.z
        if z > z0:
            continue
        t = min(1.0, (z0 - z) / (z0 - z1)) ** 0.8 * strength
        c = col.data[li].color
        col.data[li].color = (c[0] * (1 - t) + MUD[0] * t, c[1] * (1 - t) + MUD[1] * t, c[2] * (1 - t) + MUD[2] * t, c[3])


def build_all(models=None):
    report = {}
    for model, fn in BUILDERS.items():
        if models and model not in models:
            continue
        Q[0] = QUALITY.get(model, 0.58)
        meshes = fn()
        for key in ('LegL', 'LegR'):
            if key in meshes:
                mud_legs(meshes[key])
        n = bind(model, meshes)
        roots = spawn_roots(model)
        if roots:
            parts = part_objects(roots[0])
            objs = [v for k, v in parts.items() if k != 'Wheels'] + parts.get('Wheels', [])
            vertex_ao(objs, dist=0.35 if model != 'BossBaron' else 0.3)
        tris = {k: L.tri_count(m) for k, m in meshes.items()}
        report[model] = {'instances': n, 'tris': tris, 'total_tris': sum(tris.values()) if model != 'Buggy' else
                         tris['Body'] + tris['Gun'] + 2 * tris['WheelFront'] + 2 * tris['WheelRear']}
        if model not in ('Buggy',):
            report[model]['total_tris'] = tris['Torso'] + tris['LegL'] + tris['LegR'] + tris['ArmL'] + tris['ArmR'] + tris['Weapon']
        print('TW_CHAR', model, report[model], flush=True)
    return report
