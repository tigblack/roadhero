"""Quasimodo, DetailedCar pass. Built in crew space (Quasimodo empty: feet on the bed floor at z = 0, facing +Y)
and moved into each part's own pivot space, so the game's rigid parts and IK pivots are kept.

Body volumes come from ModelsActors.QuasiBody (Unity -> Blender: (x, y, z) -> (x, z, y))."""
import math

from mathutils import Matrix, Vector

from mb import MB, C, TAU, circle, fillet, hash01, mixc, rrect, shade

QCloak, QCloakDark, QCloakLight, QHole = C("#5D4535"), C("#4A372A"), C("#73573F"), C("#2A1F18")
QHoodIn, QSkin, QSkinLight, QSkinShade = C("#1F1712"), C("#C9A386"), C("#D5B399"), C("#A57E65")
QSocket, QStubble, QBrow, QTeeth = C("#6E5242"), C("#8E8780"), C("#4A3B33"), C("#D7CB9C")
QMouth, QEyeWhite, QPupil, QTrousers = C("#3A1F1A"), C("#D6CBB0"), C("#17110E"), C("#3C3732")
QBoots, QSole, QWrap = C("#6A4A33"), C("#33251C"), C("#7B6B57")
QLeather, QLeatherDark, QBrass, QIron = C("#5B3E2B"), C("#3E2A1E"), C("#B08D57"), C("#6E7378")
QTunic = C("#4F3B2E")

CLOTH = ("MAT_Cloth", (0.07, 0.0))


def B(x, y, z):
    """Unity crew coordinates -> Blender crew coordinates."""
    return Vector((x, z, y))


# ---------------------------------------------------------------- body volumes (crew, Blender)
ELL = [  # centre, radii (Blender x, y, z)
    ("hips", B(0, 0.64, -0.06), Vector((0.19, 0.16, 0.13))),
    ("belly", B(0, 0.85, 0.07), Vector((0.22, 0.19, 0.19))),
    ("chest", B(0, 0.98, 0.10), Vector((0.24, 0.16, 0.12))),
    ("hump", B(0.04, 1.08, -0.07), Vector((0.26, 0.235, 0.2))),
    ("hump2", B(-0.07, 1.11, -0.03), Vector((0.16, 0.16, 0.13))),
    ("shR", B(0.19, 1.03, 0.10), Vector((0.1, 0.1, 0.1))),
    ("shL", B(-0.18, 0.975, 0.10), Vector((0.095, 0.095, 0.095))),
]


def capsule_spheres(a, b, r, n=7):
    a, b = Vector(a), Vector(b)
    return [(a.lerp(b, k / (n - 1)), Vector((r, r, r))) for k in range(n)]


def ray_ellipsoid_exit(o, d, c, rad):
    """Largest t >= 0 with o + t d inside the ellipsoid (None if missed)."""
    oc = Vector(((o.x - c.x) / rad.x, (o.y - c.y) / rad.y, (o.z - c.z) / rad.z))
    dd = Vector((d.x / rad.x, d.y / rad.y, d.z / rad.z))
    A = dd.dot(dd)
    Bq = 2 * oc.dot(dd)
    Cq = oc.dot(oc) - 1
    disc = Bq * Bq - 4 * A * Cq
    if disc < 0:
        return None
    t1 = (-Bq + math.sqrt(disc)) / (2 * A)
    return t1 if t1 > 0 else None


def envelope(vols, z, theta, cx=0.0, cy=0.0):
    o = Vector((cx, cy, z))
    d = Vector((math.sin(theta), math.cos(theta), 0.0))
    best = 0.0
    for (c, rad) in vols:
        t = ray_ellipsoid_exit(o, d, c, rad)
        if t is not None and t > best:
            best = t
    return best


def smooth_step(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def folds(theta, seed, n=11, width=0.32):
    """Fold profile around the body: ridges (+) and valleys (-), smooth, deterministic."""
    v = 0.0
    for k in range(n):
        c = TAU * (k + 0.37 * hash01(k * 3 + seed)) / n
        w = width * (0.7 + 0.6 * hash01(k * 5 + seed + 1))
        s = 1.0 if hash01(k * 7 + seed + 2) > 0.38 else -0.75
        dth = math.atan2(math.sin(theta - c), math.cos(theta - c))
        if abs(dth) < w:
            q = math.cos(dth / w * math.pi / 2)
            v += s * q * q
    return v


def solid_shell(b, outer, inner, col_out, col_in, col_edge, cu=False, mat=CLOTH, edges=("top", "bottom", "left", "right"),
                flip=False):
    """Cloth with thickness: outer grid + inner grid (facing inward) stitched along the open edges."""
    b.m(mat[0], mat[1][0], mat[1][1])
    oi = b.grid(outer, col_out, cv=cu, flip=flip)
    ii = b.grid(inner, col_in, cv=cu, flip=not flip)
    nu, nv = len(outer), len(outer[0])
    if "top" in edges:
        b.stitch([ii[0], oi[0]], col_edge, cv=cu, flip=flip)
    if "bottom" in edges:
        b.stitch([oi[-1], ii[-1]], col_edge, cv=cu, flip=flip)
    if not cu:
        if "left" in edges:
            b.stitch([[oi[i][0] for i in range(nu)], [ii[i][0] for i in range(nu)]], col_edge, cv=False, flip=flip)
        if "right" in edges:
            b.stitch([[ii[i][nv - 1] for i in range(nu)], [oi[i][nv - 1] for i in range(nu)]], col_edge, cv=False, flip=flip)
    return oi, ii


def grid_normals(P, closed_v=False):
    nu, nv = len(P), len(P[0])
    N = []
    for i in range(nu):
        row = []
        for j in range(nv):
            a = Vector(P[min(i + 1, nu - 1)][j]) - Vector(P[max(i - 1, 0)][j])
            if closed_v:
                c = Vector(P[i][(j + 1) % nv]) - Vector(P[i][(j - 1) % nv])
            else:
                c = Vector(P[i][min(j + 1, nv - 1)]) - Vector(P[i][max(j - 1, 0)])
            n = a.cross(c)
            row.append(n.normalized() if n.length > 1e-9 else Vector((0, 0, 1)))
        N.append(row)
    return N


# ---------------------------------------------------------------- arm geometry from the rig (crew space)
def arm_capsules(rig):
    """rig: dict with 'shR','elR','haR','shL','elL','haL' crew-space Vectors."""
    vols = []
    for s in ("R", "L"):
        vols += capsule_spheres(rig["sh" + s], rig["el" + s], 0.078, 8)
    return vols


# ---------------------------------------------------------------- cape (mantle over hump, shoulders, arms)
def outward_ok(rows, i, j):
    """True if quad (i,j)->(i,j+1)->(i+1,j+1)->(i+1,j) faces away from the vertical body axis."""
    P = [Vector(rows[i][j]), Vector(rows[i][j + 1]), Vector(rows[i + 1][j + 1]), Vector(rows[i + 1][j])]
    n = Vector((0, 0, 0))
    for k in range(4):
        a, c = P[k], P[(k + 1) % 4]
        n += Vector(((a.y - c.y) * (a.z + c.z), (a.z - c.z) * (a.x + c.x), (a.x - c.x) * (a.y + c.y)))
    m = sum(P, Vector()) / 4
    return n.dot(Vector((m.x, m.y, 0))) > 0


def open_half(z):
    return math.radians(7 + 55 * smooth_step(1.2, 0.86, z))


def cape_hem(theta):
    back = 0.5 + 0.5 * math.cos(theta - math.pi)
    z = 0.875 - 0.03 * back + 0.035 * (1 - back) ** 2
    z += (hash01(int(theta * 40) + 3) - 0.5) * 0.02
    for k in range(9):
        c = TAU * (k + 0.5) / 9 + 0.3 * hash01(k + 77)
        dth = abs(math.atan2(math.sin(theta - c), math.cos(theta - c)))
        if dth < 0.07:
            z += (0.07 - dth) / 0.07 * (0.045 + 0.03 * hash01(k + 5))
    return z


def cape(b, rig):
    support = [(c, r) for (n, c, r) in ELL if n in ("hump", "hump2", "shR", "shL", "chest")]
    support += capsule_spheres(B(0, 1.12, 0.12), B(0, 1.27, 0.2), 0.07, 5)     # neck
    support += arm_capsules(rig)
    Z_TOP, Z_LOW = 1.345, 0.80
    zt = [Z_TOP - k * 0.01 for k in range(int((Z_TOP - Z_LOW) / 0.01) + 1)]
    NA = 360
    table = []
    run = [0.0] * NA
    for z in zt:                       # drape: cloth falls from the widest support above, slightly inward
        row = []
        for k in range(NA):
            e = envelope(support, z, TAU * k / NA, 0.0, 0.0)
            run[k] = max(e, run[k] - 0.0035)
            row.append(run[k])
        table.append(row)

    def r_at(z, th):
        fz = (Z_TOP - z) / 0.01
        i0 = max(0, min(len(zt) - 2, int(fz)))
        tz = max(0.0, min(1.0, fz - i0))
        fk = (th % TAU) / TAU * NA
        k0 = int(fk) % NA
        tk = fk - int(fk)
        def g(i):
            return table[i][k0] * (1 - tk) + table[i][(k0 + 1) % NA] * tk
        return g(i0) * (1 - tz) + g(i0 + 1) * tz

    NT, NR = 72, 40
    outer = []
    for i in range(NR):
        v = (i / (NR - 1)) ** 1.35
        row = []
        for j in range(NT + 1):
            # column angle: interpolate the opening between top and this column's hem
            th_top = open_half(Z_TOP) + (TAU - 2 * open_half(Z_TOP)) * j / NT
            hz = cape_hem(th_top)
            z = Z_TOP + (hz - Z_TOP) * v
            oh = open_half(z)
            th = oh + (TAU - 2 * oh) * j / NT
            r = r_at(z, th) + 0.014
            depth = smooth_step(1.25, 1.0, z)
            r += 0.026 * depth * folds(th, 3) + 0.01 * depth * folds(th * 2.0, 9, 7, 0.25)
            row.append(Vector((math.sin(th) * r, math.cos(th) * r, z)))
        outer.append(row)
    assert outward_ok(outer, NR // 2, NT // 2), "cape winding"
    N = grid_normals(outer)
    probe = outer[NR // 2][NT // 2]
    sgn = 1.0 if N[NR // 2][NT // 2].dot(Vector((probe.x, probe.y, 0))) > 0 else -1.0
    inner = [[outer[i][j] - N[i][j] * sgn * 0.007 for j in range(NT + 1)] for i in range(NR)]

    def ccol(i, j):
        p = outer[i][j]
        th = math.atan2(p.x, p.y)
        f = folds(th, 3) + 0.4 * folds(th * 2.0, 9, 7, 0.25)
        dep = smooth_step(1.25, 1.0, p.z)
        k = max(-1.0, min(1.0, f * dep))
        base = mixc(QCloak, QCloakLight, 0.35 * k) if k > 0 else mixc(QCloak, QCloakDark, -0.7 * k)
        return shade(base, 0.97 + 0.06 * hash01(i * 3 + j // 6))
    b.m("MAT_Cloth", 0.07, 0.0)
    oi = b.grid([[tuple(p) for p in r] for r in outer], QCloak, colfn=ccol)
    ii = b.grid([[tuple(p) for p in r] for r in inner], QHole, flip=True)
    b.stitch([oi[-1], ii[-1]], shade(QCloakDark, 0.9), cv=False)
    b.stitch([ii[0], oi[0]], QCloakDark, cv=False)
    b.stitch([[oi[i][0] for i in range(NR)], [ii[i][0] for i in range(NR)]], QCloakDark, cv=False)
    b.stitch([[ii[i][NT] for i in range(NR)], [oi[i][NT] for i in range(NR)]], QCloakDark, cv=False)
    # torn strips hanging from the hem (thin solid shells)
    for k in range(7):
        j = int(NT * (0.08 + 0.84 * hash01(k * 9 + 1)))
        j = min(j, NT - 2)
        p, q = outer[-1][j], outer[-1][j + 2]
        out = Vector((p.x + q.x, p.y + q.y, 0)).normalized()
        L = 0.05 + 0.05 * hash01(k + 31)
        m = (p + q) / 2
        w = q - p
        c1 = m + Vector((0, 0, -L * 0.5)) + out * 0.004
        tip = m + Vector((0, 0, -L)) + out * 0.008
        rows_s = [[p, q], [c1 - w * 0.33, c1 + w * 0.33], [tip - w * 0.06, tip + w * 0.06]]
        outer_s = [[tuple(v) for v in r] for r in rows_s]
        inner_s = [[tuple(v - out * 0.004) for v in r] for r in rows_s]
        solid_shell(b, outer_s, inner_s, QCloakDark, QHole, QCloakDark)
    def surf(theta, z):
        oh = open_half(z)
        r = r_at(z, theta) + 0.014
        depth = smooth_step(1.25, 1.0, z)
        r += 0.026 * depth * folds(theta, 3) + 0.01 * depth * folds(theta * 2.0, 9, 7, 0.25)
        return Vector((math.sin(theta) * r, math.cos(theta) * r, z))
    return outer, surf


# ---------------------------------------------------------------- tunic + skirt (closed tube under the cape)
def tunic(b):
    body = [(c, r) for (n, c, r) in ELL if n in ("hips", "belly", "chest", "hump", "hump2")]
    NT = 64
    ys_skirt = [(0.9, 0.215, 0.198, 0.02), (0.78, 0.235, 0.21, 0.005), (0.66, 0.255, 0.222, -0.01), (0.57, 0.27, 0.23, -0.018),
                (0.5, 0.282, 0.236, -0.022)]
    zs = [1.2 - k * 0.022 for k in range(32)]       # 1.20 .. 0.518
    belt_z = 0.80
    rows = []
    for zi, z in enumerate(zs):
        row = []
        for j in range(NT):
            th = TAU * j / NT
            e = envelope(body, z, th, 0.0, 0.02)
            # skirt flare below the hips (C# drape radii)
            if z < 0.9:
                for (y0, rx0, rz0, cz0), (y1, rx1, rz1, cz1) in zip(ys_skirt, ys_skirt[1:]):
                    if y1 <= z <= y0:
                        t = (y0 - z) / (y0 - y1)
                        rx, rz, cz = rx0 + (rx1 - rx0) * t, rz0 + (rz1 - rz0) * t, cz0 + (cz1 - cz0) * t
                        break
                else:
                    rx, rz, cz = 0.282, 0.236, -0.022
                ex = 1.0 / math.sqrt((math.sin(th) / rx) ** 2 + (math.cos(th) / rz) ** 2)
                e = max(e * 0.92, ex)
            r = e + 0.012
            cinch = math.exp(-((z - belt_z) / 0.025) ** 2)
            r -= 0.012 * cinch
            below = smooth_step(belt_z, belt_z - 0.25, z)
            above = smooth_step(belt_z, belt_z + 0.12, z) * (1 - smooth_step(belt_z + 0.12, belt_z + 0.3, z))
            r += 0.02 * below * folds(th, 21, 14, 0.24) + 0.007 * above * folds(th, 23, 18, 0.18)
            row.append((math.sin(th) * r, math.cos(th) * r + 0.0, z))
        rows.append(row)
    # frayed hem: last rows follow an uneven hem line
    for j in range(NT):
        th = TAU * j / NT
        hz = 0.5 + (hash01(j * 3 + 11) - 0.35) * 0.03
        for k in range(1, 4):
            zi = len(zs) - k
            p = rows[zi][j]
            z_target = hz + (k - 1) * 0.022
            rows[zi][j] = (p[0], p[1], z_target)
    assert outward_ok(rows, 10, NT // 4), "tunic winding"
    N = grid_normals(rows, closed_v=True)
    probe = Vector(rows[10][NT // 4])
    sgn = 1.0 if N[10][NT // 4].dot(Vector((probe.x, probe.y, 0))) > 0 else -1.0
    inner = [[tuple(Vector(rows[i][j]) - N[i][j] * sgn * 0.006) for j in range(NT)] for i in range(len(rows))]
    flip = False
    b.m("MAT_Cloth", 0.08, 0.0)
    def tcol(i, j):
        p = rows[i][j]
        th = math.atan2(p[0], p[1])
        below = smooth_step(belt_z, belt_z - 0.25, p[2])
        f = folds(th, 21, 14, 0.24) * below
        k = max(-1.0, min(1.0, f))
        return mixc(QTunic, shade(QTunic, 1.25), 0.4 * k) if k > 0 else mixc(QTunic, QCloakDark, -0.6 * k)
    oi = b.grid(rows, QTunic, cv=True, flip=flip, colfn=tcol)
    ii = b.grid(inner, QHole, cv=True, flip=not flip)
    b.stitch([oi[-1], ii[-1]], QCloakDark, cv=True, flip=flip)
    b.stitch([ii[0], oi[0]], QCloakDark, cv=True, flip=flip)
    return rows


def tunic_radius(rows, z, th):
    """Approximate tunic outer radius at height z, angle th (for straps / belt)."""
    best = None
    for row in rows:
        if best is None or abs(row[0][2] - z) < abs(best[0][2] - z):
            best = row
    NT = len(best)
    k = (th % TAU) / TAU * NT
    p = Vector(best[int(k) % NT])
    return Vector((p.x, p.y, 0)).length


# ---------------------------------------------------------------- belt, pouch, bandolier, clasp
def gear(b, trows, cape_outer, open_half, surf=None):
    # rope belt (twisted look: two interleaved strands)
    zb = 0.80
    path = []
    for k in range(97):
        th = TAU * k / 96
        r = tunic_radius(trows, zb, th) + 0.004
        path.append((math.sin(th) * r, math.cos(th) * r, zb + 0.004 * math.sin(th * 3)))
    b.m("MAT_Cloth", 0.2, 0.0)
    for ph in (0.0, math.pi):
        strand = []
        for k, p in enumerate(path):
            th = TAU * k / 96
            off = 0.0065 * math.cos(th * 34 + ph)
            strand.append((p[0], p[1], p[2] + off))
        b.tube(strand[:-1], 0.0075, 8, shade(QWrap, 1.0 if ph == 0 else 0.86), closed=True)
    # knot at the front-left and two hanging ends
    th = math.radians(-28)
    r = tunic_radius(trows, zb, th) + 0.012
    kc = Vector((math.sin(th) * r, math.cos(th) * r, zb))
    b.ellipsoid(tuple(kc), (0.022, 0.018, 0.02), shade(QWrap, 0.95), 14, 8)
    for s, L in ((-1, 0.16), (1, 0.12)):
        a = kc + Vector((s * 0.01, 0.0, -0.01))
        pts = [a, a + Vector((s * 0.012, 0.012, -L * 0.4)), a + Vector((s * 0.02, 0.016, -L * 0.8)), a + Vector((s * 0.018, 0.02, -L))]
        b.tube([tuple(p) for p in pts], 0.0072, 8, QWrap)
        b.ellipsoid(tuple(pts[-1] + Vector((0, 0, -0.006))), (0.011, 0.011, 0.016), shade(QWrap, 0.8), 10, 6)
    # leather pouch on the right hip with flap, stitching strap and brass buckle
    th = math.radians(115)
    r = tunic_radius(trows, 0.74, th)
    nrm = Vector((math.sin(th), math.cos(th), 0))
    cpos = nrm * (r + 0.026) + Vector((0, 0, 0.73))
    rot = Matrix.Rotation(-th, 3, "Z")
    b.m("MAT_Leather", 0.35, 0.0)
    with b.at(tuple(cpos), rot):
        b.rbox((0, 0, 0), (0.055, 0.024, 0.05), 0.014, 2, QLeather)
        b.rbox((0, 0.004, 0.032), (0.058, 0.025, 0.022), 0.012, 2, QLeatherDark, rot=(-12, 0, 0))
        b.rbox((0, 0.028, 0.0), (0.012, 0.003, 0.05), 0.002, 1, QLeatherDark)
        b.m("MAT_Metal", 0.7, 0.9)
        b.rbox((0, 0.032, 0.012), (0.012, 0.003, 0.009), 0.002, 1, QBrass)
        b.m("MAT_Leather", 0.35, 0.0)
        b.rbox((0, -0.02, 0.07), (0.03, 0.004, 0.035), 0.004, 1, QLeatherDark)    # loop to the belt
    # bandolier: from the right shoulder over the cape to the left hip, following the cape surface
    outer = cape_outer
    nrow, ncol = len(outer), len(outer[0])

    def cape_point(theta, z):
        best_i = min(range(nrow), key=lambda i: abs(outer[i][ncol // 2].z - z))
        row = outer[best_i]
        j = min(range(ncol), key=lambda j: abs(math.atan2(math.sin(math.atan2(row[j].x, row[j].y) - theta),
                                                         math.cos(math.atan2(row[j].x, row[j].y) - theta))))
        return row[j]

    strap = []
    NS = 72
    for k in range(NS):
        th = TAU * k / NS
        z = 1.045 + 0.145 * math.cos(th - math.radians(80))
        if abs(math.atan2(math.sin(th), math.cos(th))) < open_half(z) + 0.05:
            r = tunic_radius(trows, z, th) + 0.012
            p = Vector((math.sin(th) * r, math.cos(th) * r, z))
        else:
            p = surf(th, z)
            p = p + Vector((p.x, p.y, 0)).normalized() * 0.01
        strap.append(tuple(p))
    from parts_details import catmull
    b.m("MAT_Leather", 0.3, 0.0)
    b.sweep(strap, rrect(0.007, 0.038, 0.002, 1), QLeather, closed_path=True, caps=False, up=(0, 0, 1))
    mid = Vector(strap[2])
    n = Vector((mid.x, mid.y, 0)).normalized()
    b.m("MAT_Metal", 0.75, 0.9)
    with b.at(tuple(mid + n * 0.006), Matrix.Rotation(-math.atan2(n.x, n.y), 3, "Z")):
        b.rbox((0, 0, 0), (0.026, 0.005, 0.024), 0.004, 2, QBrass)
        b.m("MAT_Metal", 0.1, 0.0)
        b.rbox((0, 0.004, 0), (0.016, 0.003, 0.014), 0.002, 1, QHole)
    b.m("MAT_Leather", 0.35, 0.0)
    for t in (0.06, 0.12, 0.88):
        p = Vector(strap[int(t * NS)])
        n = Vector((p.x, p.y, 0)).normalized()
        with b.at(tuple(p + n * 0.012), Matrix.Rotation(-math.atan2(n.x, n.y), 3, "Z")):
            b.rbox((0, 0, -0.012), (0.024, 0.012, 0.03), 0.008, 2, QLeatherDark)
            b.rbox((0, 0.004, 0.014), (0.026, 0.013, 0.01), 0.006, 2, QLeather)
    # brooch clasp at the throat holding the mantle's front edges
    zc = 1.2
    oh = open_half(zc)
    r = 0.13
    cpos = Vector((0.0, 0.12, zc))
    b.m("MAT_Metal", 0.8, 0.95)
    with b.at(tuple(cpos), (-75, 0, 0)):
        b.lathe(fillet([(0.0, 0.0), (0.03, 0.0), (0.03, 0.006), (0.024, 0.012), (0.0, 0.014)], [0, 0.002, 0.003, 0.004, 0], 2), 24, QBrass)
        b.m("MAT_Metal", 0.6, 0.9)
        b.lathe([(0.0, 0.012), (0.012, 0.012), (0.0, 0.02)], 12, shade(QBrass, 0.7))
    b.m("MAT_Leather", 0.3, 0.0)
    for s in (-1, 1):
        b.tube([(s * 0.06, 0.1, zc - 0.01), (s * 0.03, 0.125, zc), (s * 0.012, 0.128, zc)], 0.005, 8, QLeatherDark)


def body_build(rig):
    b = MB("MAT_Cloth", 0.07, 0.0)
    outer, surf = cape(b, rig)
    trows = tunic(b)
    gear(b, trows, outer, open_half, surf)
    return b
