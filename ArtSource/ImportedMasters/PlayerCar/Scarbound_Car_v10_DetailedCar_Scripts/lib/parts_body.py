"""Car body + cab, DetailedCar pass. A high-resolution port of ModelsCar.BuildCarBody (same shape functions,
same proportions) with real panel gaps, recessed glass with thickness and rubber seals.

Built in Unity space (x right, y up, z forward) and written in Blender space (x, z, y).
"""
import math

from mathutils import Vector

import carshape as cs
from carshape import (BedFloorY, BedFrontZ, BedInnerX, BedRearZ, BodyShoulderR, CarArchCut, CarBottom, CarCrown,
                      CarHalfWidth, CarTop, CarZFront, CarZRear, CabinRoofY, SideX, StripeIn, StripeOut, clamp01, lerp)
from mb import MB, C, TAU, mixc, rrect, shade

CarPaintC, CarPaintLow, CarStripe = C("#3B4049"), C("#2C3037"), C("#EFE4CC")
CarUnder, BedWall, CarGlass = C("#1B1C1F"), C("#30343B"), C("#45616F")
CarRubber, CarTrim = C("#302C2C"), C("#1F2125")
GLOSS_PAINT, GLOSS_CAB = 0.78, 0.82

# ---------------------------------------------------------------- ring layout (right half, constant count)
BOTTOM_F = [0.0, 0.25, 0.5, 0.75, 1.0]                 # 0..4   bottom (0 = centre)
WALL_F = [0.33, 0.67, 1.0]                             # 5..7   wheel-well wall
ROOF_F = [0.5, 1.0]                                    # 8..9   arch roof out to the skin
ROCK_S = (0.5 - 0.3) / 0.57                            # rocker / door-bottom seam at y = 0.50 (door region)
W1, W2 = 0.004, 0.010                                  # groove: lip offset, edge offset (m)
_ds1, _ds2 = W1 / 0.57, W2 / 0.57
SIDE_F = [0.04, 0.09, 0.15, 0.21, 0.27, 0.315, ROCK_S - _ds2, ROCK_S - _ds1, ROCK_S, ROCK_S + _ds1, ROCK_S + _ds2,
          0.40, 0.46, 0.52, 0.58, 0.64, 0.70, 0.76, 0.82, 0.87, 0.92, 0.96, 1.0]
N_ARC = 10
HOOD_X = 0.640
TOP_X = [0.70, HOOD_X + W2 + 0.005, HOOD_X + W1 + 0.001, HOOD_X, HOOD_X - W1 - 0.001, HOOD_X - W2 - 0.005,
         0.58, 0.52, 0.48, StripeOut, 0.40, 0.35, StripeIn, 0.25, 0.20, 0.15, 0.10, 0.05, 0.0]
J_SIDE0 = len(BOTTOM_F) + len(WALL_F) + len(ROOF_F)   # 10
J_ROCK = J_SIDE0 + SIDE_F.index(ROCK_S)
J_ARC0 = J_SIDE0 + len(SIDE_F)                        # first arc point
J_TOP0 = J_ARC0 + N_ARC                               # first deck point
J_HOOD = J_TOP0 + TOP_X.index(HOOD_X)
J_STRIPE_OUT = J_TOP0 + TOP_X.index(StripeOut)
J_STRIPE_IN = J_TOP0 + TOP_X.index(StripeIn)
NR = J_TOP0 + len(TOP_X)                              # points in the right half
NOMINAL_XT = 0.74

# grooves (Unity z) -------------------------------------------------------------------------------
DOOR_FRONT_Z, DOOR_REAR_Z = 0.56, -0.52
COWL_Z, HOOD_FRONT_Z = 0.64, 2.26
ROCK_Z0, ROCK_Z1 = -0.88, 0.97
GROOVE_D = 0.0062


def section_right(z, open_):
    rS = BodyShoulderR
    w = CarHalfWidth(z)
    yBot = CarBottom(z)
    top = CarTop(z)
    crown = CarCrown(z)
    yTop = top - rS
    cut, wellX = CarArchCut(z, yBot)
    cut = min(cut, yTop - 0.03)
    sCut = clamp01((cut - yBot) / max(0.01, yTop - yBot))
    wx = min(wellX, w * 0.7)
    pts = [(wx * f, yBot) for f in BOTTOM_F]
    pts += [(wx, lerp(yBot, cut, f)) for f in WALL_F]
    xs = SideX(w, sCut)
    pts += [(lerp(wx, xs, f), cut) for f in ROOF_F]
    for f in SIDE_F:
        s = sCut + (1.0 - sCut) * f
        pts.append((SideX(w, s), lerp(yBot, yTop, s)))
    xt = SideX(w, 1.0) - rS
    for a in range(1, N_ARC + 1):
        ang = math.radians(a * 90.0 / N_ARC)
        pts.append((xt + rS * math.cos(ang), yTop + rS * math.sin(ang)))
    if not open_:
        for X in TOP_X:
            x = min(X, xt * X / NOMINAL_XT)
            u = x / xt if xt > 0.01 else 0.0
            pts.append((x, top + crown * (1 - u * u)))
    else:
        xi = min(BedInnerX, xt - 0.06)
        fl = BedFloorY - 0.025          # under the 23 mm plank floor (plank tops = game floor)
        pts += [(xt - 0.02, top), (xi + 0.012, top), (xi + 0.0035, top - 0.0035), (xi, top - 0.012)]
        pts += [(xi, y) for y in (top - 0.05, top - 0.12, top - 0.2, top - 0.28, fl + 0.04)]
        pts += [(xi, fl + 0.012), (xi - 0.0035, fl + 0.0035), (xi - 0.012, fl)]
        pts += [(x, fl) for x in (0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0)]
    assert len(pts) == NR, (len(pts), NR)
    return pts


def needs_flip(rows, i, j, expect):
    """True if quad (i,j)->(i,j+1)->(i+1,j+1)->(i+1,j) of `rows` faces away from `expect` (Blender dir)."""
    n = len(rows[0])
    P = [Vector(rows[i][j]), Vector(rows[i][(j + 1) % n]), Vector(rows[i + 1][(j + 1) % n]), Vector(rows[i + 1][j])]
    nn = Vector((0, 0, 0))
    for k in range(4):
        a, c = P[k], P[(k + 1) % 4]
        nn += Vector(((a.y - c.y) * (a.z + c.z), (a.z - c.z) * (a.x + c.x), (a.x - c.x) * (a.y + c.y)))
    return nn.dot(Vector(expect)) < 0


def ring_normals(pts):
    """In-section outward normals for a CCW right-half polyline (outward = right of travel)."""
    n = []
    for j in range(len(pts)):
        a = pts[max(j - 1, 0)]
        b = pts[min(j + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        n.append((dy / L, -dx / L))
    return n


def z_samples():
    zEndF, zEndR = CarZFront - 0.02, CarZRear + 0.02
    zs = set()
    z = zEndR
    while z < zEndF:
        zs.add(round(z, 5))
        z += 0.04
    for k in range(1, 15):                      # dense near both ends (the plan rounds off fast)
        zs.add(round(zEndR + 0.16 * (k / 15) ** 1.7, 5))
        zs.add(round(zEndF - 0.16 * (k / 15) ** 1.7, 5))
    for (axle, r) in ((cs.CarFrontAxleZ, cs.CarFrontWheelR), (cs.CarRearAxleZ, cs.CarRearWheelR)):
        ra = r + 0.07
        for k in range(0, 29):                  # arch circle sampled by angle: smooth openings
            th = math.pi * k / 28
            zs.add(round(axle + ra * math.cos(th) * 0.9995, 5))
    grooves = {}
    for zc in (DOOR_FRONT_Z, DOOR_REAR_Z, COWL_Z, HOOD_FRONT_Z):
        for off, depth in ((-W2, 0.0), (-W1, 0.25), (0.0, 1.0), (W1, 0.25), (W2, 0.0)):
            zz = round(zc + off, 5)
            zs.add(zz)
            if depth > 0:
                grooves.setdefault(zz, []).append((zc, depth))
    zs.add(zEndR)
    zs.add(zEndF)
    zs = sorted(v for v in zs if zEndR - 1e-6 <= v <= zEndF + 1e-6)
    # drop samples closer than 1.5 mm (keep groove samples)
    out = []
    for v in zs:
        if out and v - out[-1] < 0.012 and v not in grooves and out[-1] not in grooves and v not in (zEndR, zEndF):
            continue
        out.append(v)
    return out, grooves


def body_mesh():
    zs0, groove_z = z_samples()
    # sections with the bed: open between the bed ends, duplicated (closed + open) at both ends
    secs = []
    for z in zs0:
        inside = BedRearZ < z < BedFrontZ
        if abs(z - BedRearZ) < 1e-6 or abs(z - BedFrontZ) < 1e-6:
            continue
        secs.append((z, inside))
    secs.append((BedRearZ, False))
    secs.append((BedRearZ, True))
    secs.append((BedFrontZ, True))
    secs.append((BedFrontZ, False))
    order = {False: 0, True: 1}
    secs.sort(key=lambda s: (s[0], order[s[1]] if s[0] == BedRearZ else -order[s[1]]))

    rows, opens, zrow = [], [], []
    for (z, o) in secs:
        right = section_right(z, o)
        nrm = ring_normals(right)
        right = [list(p) for p in right]
        # ---- grooves: section-aligned (door seams, cowl, hood front) and ring-aligned (hood sides, rocker)
        dep = [0.0] * NR
        for (zc, depth) in groove_z.get(round(z, 5), []):
            if zc in (DOOR_FRONT_Z, DOOR_REAR_Z):
                jr = range(J_ROCK, J_TOP0)
            elif zc in (COWL_Z, HOOD_FRONT_Z) and not o:
                jr = range(J_HOOD, NR)
            else:
                jr = range(0)
            for j in jr:
                dep[j] = max(dep[j], depth)
        if COWL_Z - 1e-6 <= z <= HOOD_FRONT_Z + 1e-6 and not o:
            for j, d in ((J_HOOD, 1.0), (J_HOOD - 1, 0.25), (J_HOOD + 1, 0.25)):
                dep[j] = max(dep[j], d)
        if ROCK_Z0 <= z <= ROCK_Z1:
            for j, d in ((J_ROCK, 1.0), (J_ROCK - 1, 0.25), (J_ROCK + 1, 0.25)):
                dep[j] = max(dep[j], d)
        for j in range(NR):
            if dep[j] > 0:
                right[j][0] -= nrm[j][0] * GROOVE_D * dep[j]
                right[j][1] -= nrm[j][1] * GROOVE_D * dep[j]
        loop = [(p[0], p[1], z) for p in right] + [(-right[j][0], right[j][1], z) for j in range(NR - 2, 0, -1)]
        rows.append([(p[0], p[2], p[1]) for p in loop])           # -> Blender
        opens.append(o)
        zrow.append(z)
    np_ = len(rows[0])

    b = MB("MAT_CarPaint", GLOSS_PAINT, 0.0)

    def mirror_j(j):
        return j if j < NR else (2 * NR - 2) - j

    def colfn(i, j):
        jj = min(mirror_j(j), mirror_j((j + 1) % np_))
        o0, o1 = opens[i], opens[i + 1]
        if o0 != o1:
            if zrow[i] > (BedFrontZ + BedRearZ) * 0.5:
                return (CarPaintC, "MAT_CarPaint", (GLOSS_PAINT, 0.0))
            return (BedWall, "MAT_CarPaint", (0.4, 0.0))
        if o0 and jj >= J_TOP0:
            k = jj - J_TOP0
            if k < 3:
                return (CarPaintC, "MAT_CarPaint", (GLOSS_PAINT, 0.0))
            if k < 11:
                return (BedWall, "MAT_CarPaint", (0.4, 0.0))
            return (CarUnder, "MAT_CarPaint", (0.2, 0.0))
        if J_STRIPE_OUT <= jj < J_STRIPE_IN and not o0 and zrow[i] > BedFrontZ:
            return (CarStripe, "MAT_CarPaint", (GLOSS_PAINT, 0.0))
        if jj < J_SIDE0 - 1:
            return (CarUnder, "MAT_CarPaint", (0.35, 0.0))
        a = rows[i][j]
        c = rows[i + 1][(j + 1) % np_]
        if jj < J_ARC0 and (a[2] + c[2]) * 0.5 < 0.5:
            return (CarPaintLow, "MAT_CarPaint", (0.72, 0.0))
        return (CarPaintC, "MAT_CarPaint", (GLOSS_PAINT, 0.0))

    mid = min(range(len(zrow)), key=lambda k: abs(zrow[k] - 1.3))
    flip = needs_flip(rows, mid, NR - 2, (0, 0, 1))
    idx = b.grid(rows, CarPaintC, cv=True, colfn=colfn, flip=flip)
    # caps (front fascia backing and the flat tailgate face)
    for end, d in ((0, (0, -1, 0)), (len(rows) - 1, (0, 1, 0))):
        ring = idx[end]
        cen = Vector((0, 0, 0))
        for p in rows[end]:
            cen += Vector(p)
        cen /= len(rows[end])
        ci = b.vs([tuple(cen)])[0]
        for k in range(len(ring)):
            b.face_out([ci, ring[k], ring[(k + 1) % len(ring)]], ("d", d), col=CarPaintC, mat="MAT_CarPaint", gm=(GLOSS_PAINT, 0.0))
    return b, rows, idx, zrow, opens


# ---------------------------------------------------------------- cab with recessed glass
YB = 0.95


def cab_ring(z):
    roof = max(CabinRoofY(z), YB + 0.004)
    wb = min(0.8, CarHalfWidth(z) - 0.12)
    wt = min(wb - 0.1, 0.6)
    h = roof - YB
    rc = min(0.12, h * 0.45)
    side_h = max(0.004, h - rc)
    ug0 = min(0.07 / side_h, 0.82)
    pts = [(0.0, YB), (wb * 0.5, YB), (wb, YB)]
    for u in (ug0 * 0.5, ug0, ug0 + (1 - ug0) * 0.25, ug0 + (1 - ug0) * 0.5, ug0 + (1 - ug0) * 0.75, 1.0):
        pts.append((lerp(wb, wt, u), YB + side_h * u))
    for a in range(10, 91, 10):
        ang = math.radians(a)
        pts.append((wt - rc + rc * math.cos(ang), roof - rc + rc * math.sin(ang)))
    flat = wt - rc
    for X in (StripeOut + 0.012, StripeOut, 0.37, StripeIn, 0.225, 0.15, 0.075, 0.0):
        x = min(X, flat * X / 0.5)
        u = x / flat if flat > 0.01 else 0.0
        pts.append((x, roof + 0.018 * (1 - u * u)))
    return pts


# ring: 0-2 bottom, 3-8 side (u = ug0/2, ug0, .25, .5, .75, 1), 9-17 arc 10..90 deg, 18-25 roof
CJ_GLASS0 = 4                     # glass bottom edge (side)
CJ_GLASS1 = 9 + 2                 # arc 30deg: side glass top edge
CJ_WS = 9 + 5                     # arc 60deg: windshield edge (A-pillar band between)
CJ_STRIPE_OUT = 18 + 1
CJ_STRIPE_IN = 18 + 3
CNR = 26

WS_Z0, WS_Z1 = 0.155, 0.555
SG_Z0, SG_Z1 = -0.52, 0.48
CAB_DOOR_REAR_Z = -0.545


def cab_mesh(b):
    zs = set()
    z = 0.6
    while z > BedFrontZ + 0.01:
        zs.add(round(z, 5))
        z -= 0.02
    for v in (WS_Z0, WS_Z1, SG_Z0, SG_Z1, cs.RoofFrontZ, BedFrontZ + 0.003, CAB_DOOR_REAR_Z - W1, CAB_DOOR_REAR_Z, CAB_DOOR_REAR_Z + W1,
              DOOR_FRONT_Z):
        zs.add(round(v, 5))
    zs = sorted(zs, reverse=True)
    right_rows = [cab_ring(z) for z in zs]
    rows = []
    for zi, (z, right) in enumerate(zip(zs, right_rows)):
        right = [list(p) for p in right]
        if abs(z - CAB_DOOR_REAR_Z) < 1e-6:
            nrm = ring_normals(right)
            for j in range(3, CJ_GLASS1 + 1):
                right[j][0] -= nrm[j][0] * GROOVE_D
                right[j][1] -= nrm[j][1] * GROOVE_D
        loop = [(p[0], p[1], z) for p in right] + [(-right[j][0], right[j][1], z) for j in range(CNR - 2, 0, -1)]
        rows.append([(p[0], p[2], p[1]) for p in loop])
    n = len(rows[0])

    def mj(j):
        return j if j < CNR else (2 * CNR - 2) - j

    def region(i, j):
        """'ws' windshield, 'sg' side glass, None = painted shell (face (i, j) between rows i, i+1)."""
        za, zb = zs[i], zs[i + 1]
        zc = (za + zb) / 2
        jj, jn = mj(j), mj((j + 1) % n)
        lo, hi = min(jj, jn), max(jj, jn)
        if WS_Z0 < zc < WS_Z1 and lo >= CJ_WS:
            return "ws"
        if SG_Z0 < zc < SG_Z1 and lo >= CJ_GLASS0 and hi <= CJ_GLASS1:
            return "sg"
        return None

    def colfn(i, j):
        if region(i, j):
            return None
        jj, jn = mj(j), mj((j + 1) % n)
        lo = min(jj, jn)
        if CJ_STRIPE_OUT <= lo < CJ_STRIPE_IN and zs[i] < cs.RoofFrontZ + 0.03:
            return (CarStripe, "MAT_CarPaint", (GLOSS_CAB, 0.0))
        if lo < 2:
            return (CarUnder, "MAT_CarPaint", (0.35, 0.0))
        return (CarPaintC, "MAT_CarPaint", (GLOSS_CAB, 0.0))

    assert len(rows[0]) == 2 * CNR - 2
    flip = needs_flip(rows, len(rows) // 2, CNR - 2, (0, 0, 1))
    idx = b.grid(rows, CarPaintC, cv=True, colfn=colfn, flip=flip)
    # normals per grid vertex (finite differences), oriented by the face winding test below
    P = [[Vector(p) for p in r] for r in rows]

    def vnormal(i, j):
        a = P[min(i + 1, len(P) - 1)][j] - P[max(i - 1, 0)][j]
        c = P[i][(j + 1) % n] - P[i][(j - 1) % n]
        v = c.cross(a)
        if v.length < 1e-9:
            return Vector((0, 0, 1))
        return v.normalized()

    # orientation check: the roof centre normal must point up (+Z Blender)
    jc = CNR - 1
    sign = 1.0 if vnormal(len(P) // 2, jc).z > 0 else -1.0

    def N(i, j):
        return vnormal(i, j) * sign

    # glass regions: reveal walls, glass slab with thickness, rubber seal
    regions = {}
    for i in range(len(rows) - 1):
        for j in range(n):
            r = region(i, j)
            if r:
                key = (r, 0 if (r == "ws" or mj(j) == j) else 1)
                regions.setdefault(key, set()).add((i, j))
    D_GLASS, T_GLASS, D_SEAL, D_FLOOR, INSET = 0.011, 0.005, 0.004, 0.0175, 0.0008
    for key, faces in regions.items():
        verts = set()
        for (i, j) in faces:
            for (a, c) in ((i, j), (i, (j + 1) % n), (i + 1, j), (i + 1, (j + 1) % n)):
                verts.add((a, c))
        cen = sum((P[a][c] for (a, c) in verts), Vector()) / len(verts)
        ncen = sum((N(a, c) for (a, c) in verts), Vector()).normalized()
        ecount = {}
        for (i, j) in faces:
            j1 = (j + 1) % n
            for e in (((i, j), (i, j1)), ((i, j1), (i + 1, j1)), ((i + 1, j1), (i + 1, j)), ((i + 1, j), (i, j))):
                k = tuple(sorted(e))
                ecount[k] = ecount.get(k, 0) + 1
        bedges = [e for e, c in ecount.items() if c == 1]
        bset = {v for e in bedges for v in e}
        off = {}

        def ov(v, d):
            key2 = (v, d)
            if key2 not in off:
                off[key2] = b.vs([tuple(P[v[0]][v[1]] - N(*v) * d)])[0]
            return off[key2]

        # watertight recess in the shell: reveal walls down to a dark floor. Winding is inherited from the removed
        # region face (topologically consistent with the surrounding shell, even at thin window tips).
        bkeys = {tuple(sorted(e)) for e in bedges}
        for (i, j) in faces:
            j1 = (j + 1) % n
            quad = [(i, j), (i, j1), (i + 1, j1), (i + 1, j)]
            if flip:
                quad = quad[::-1]
            for k in range(4):
                va, vb = quad[k], quad[(k + 1) % 4]
                if tuple(sorted((va, vb))) in bkeys:
                    b.face([idx[va[0]][va[1]], idx[vb[0]][vb[1]], ov(vb, D_FLOOR), ov(va, D_FLOOR)], None, CarTrim, "MAT_CarPaint", (0.4, 0.0))
            b.face([ov(v, D_FLOOR) for v in quad], None, C("#101214"), "MAT_CarPaint", (0.3, 0.0))
        # glass slab: its own closed solid, inset from the reveal so its 5 mm edge shows in the gap
        gv = {}

        def gvert(v, d):
            key2 = (v, d)
            if key2 not in gv:
                p = P[v[0]][v[1]] - N(*v) * d
                if v in bset:
                    inward = cen - p
                    inward -= N(*v) * inward.dot(N(*v))
                    if inward.length > 1e-6:
                        p = p + inward.normalized() * INSET
                gv[key2] = b.vs([tuple(p)])[0]
            return gv[key2]
        # slab winding follows the region faces (closed and consistent by construction): top = shell order,
        # bottom = reversed, edge band traverses each boundary edge opposite to the top face
        gb = (0.9, 0.0)
        for (i, j) in faces:
            j1 = (j + 1) % n
            quad = [(i, j), (i, j1), (i + 1, j1), (i + 1, j)]
            if flip:
                quad = quad[::-1]
            b.face([gvert(v, D_GLASS) for v in quad], None, CarGlass, "MAT_Glass", gb)
            b.face([gvert(v, D_GLASS + T_GLASS) for v in quad[::-1]], None, shade(CarGlass, 0.6), "MAT_Glass", gb)
            for k in range(4):
                va, vb = quad[k], quad[(k + 1) % 4]
                if tuple(sorted((va, vb))) in bkeys:
                    b.face([gvert(vb, D_GLASS), gvert(va, D_GLASS), gvert(va, D_GLASS + T_GLASS), gvert(vb, D_GLASS + T_GLASS)],
                           None, shade(CarGlass, 1.25), "MAT_Glass", gb)
        # rubber seal: ordered boundary loop -> sweep a round profile, sitting in the reveal corner
        adj = {}
        for (va, vb) in bedges:
            adj.setdefault(va, []).append(vb)
            adj.setdefault(vb, []).append(va)
        start = bedges[0][0]
        loop = [start]
        prev = None
        cur = start
        while True:
            nxt = [v for v in adj[cur] if v != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            if cur == start:
                break
            loop.append(cur)
        path = []
        for v in loop:
            p = P[v[0]][v[1]]
            inward = (cen - p)
            inward -= N(*v) * inward.dot(N(*v))
            inward = inward.normalized() if inward.length > 1e-6 else Vector()
            path.append(tuple(p - N(*v) * (D_GLASS - 0.003) + inward * D_SEAL))
        if len(path) > 8:
            b.m("MAT_Rubber", 0.3, 0.0)
            b.tube(path, 0.0055, 8, CarRubber, closed=True, up=tuple(ncen))
            b.m("MAT_CarPaint", GLOSS_PAINT, 0.0)
    # back wall (flat cap at the bed's front) with a set-in rear window
    last = idx[-1]
    cen = sum((Vector(p) for p in rows[-1]), Vector()) / n
    ci = b.vs([tuple(cen)])[0]
    for k in range(n):
        b.face_out([ci, last[k], last[(k + 1) % n]], ("d", (0, -1, 0)), col=CarPaintC, mat="MAT_CarPaint", gm=(GLOSS_CAB, 0.0))
    first = idx[0]
    cen0 = sum((Vector(p) for p in rows[0]), Vector()) / n
    c0 = b.vs([tuple(cen0)])[0]
    for k in range(n):
        b.face_out([c0, first[k], first[(k + 1) % n]], ("d", (0, 1, 0)), col=CarPaintC, mat="MAT_CarPaint", gm=(GLOSS_CAB, 0.0))
    yw = BedFrontZ + 0.003            # cab back wall sits 3 mm ahead of the bed's front wall (no coplanar overlap)
    b.m("MAT_Glass", 0.9, 0.0)
    b.rbox((0, yw - 0.004, 1.158), (0.44, 0.006, 0.082), 0.02, 2, CarGlass)
    b.m("MAT_Rubber", 0.3, 0.0)
    outline = rrect(0.9, 0.176, 0.024, 4)
    b.tube([(x, yw - 0.0105, 1.158 + y) for (x, y) in outline], 0.0075, 8, CarRubber, closed=True, up=(0, -1, 0))
    b.m("MAT_CarPaint", GLOSS_PAINT, 0.0)
    return rows


def build():
    b, rows, idx, zrow, opens = body_mesh()
    cab_mesh(b)
    return b
