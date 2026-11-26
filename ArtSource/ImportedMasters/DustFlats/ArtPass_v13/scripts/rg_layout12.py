"""v12 layout: new winding playable boundary and the shallow river (Blender XY metres, Z up).

Boundary: inner edge of the perimeter cliffs (playable side), closed polygon, smoothed (Chaikin).
River: centreline control points with bed half-width w, bank width b, ground-to-bed depth D, kind.
Water level is flat at WATER_Z. Reference car: ground clearance 0.30 m, wheel radius ~0.45 m.
"""
import math
import numpy as np

WATER_Z = -0.22          # water surface (ground is z = 0)
DEPTH_MAIN = 0.44        # ground -> bed  => 0.22 m water at the deepest line
DEPTH_FORD = 0.31        # => 0.09 m water on fords
CAR_CLEARANCE = 0.30

# ------------------------------------------------------------------------------------------------
# Boundary (counter-clockwise, playable area on the left). 'gap' flags mark segments without new rocks.
# ------------------------------------------------------------------------------------------------
BOUNDARY_CTRL = [
    # north-east (new wall east of the gate)
    (30, 101), (44, 97.5), (58, 100), (71, 96.5), (83, 97.5),
    # NE corner, east wall with a spur and a bay
    (91, 92), (94.5, 82), (95, 72), (101, 62), (106, 52), (100, 44), (89.5, 41), (93, 30), (96, 20),
    (97, 8), (95.5, -6), (96.5, -20), (97.5, -32), (99, -44),
    # river outlet (east)
    (103.5, -52), (105, -60), (103.5, -66),
    (99, -74), (97, -84), (92, -93),
    # SE corner and south-east wall
    (84, -99), (74, -101.5), (63, -103), (52, -106), (41, -102), (31, -100.5), (25, -97.5), (19.5, -98.5),
    # flared canyon mouth (east) and the canyon
    (16, -101.5), (13.8, -106), (12.9, -112), (12.6, -118), (12.6, -250), (8, -253), (-8, -253), (-12.6, -250), (-12.6, -118),
    (-12.9, -112), (-13.8, -106), (-16, -101.5),
    # south-west wall
    (-20.5, -98.5), (-27, -103), (-38, -101), (-47, -96.5), (-55, -97.5), (-64, -100.5), (-75, -101.5),
    # SW corner, west wall with a bay, a spur between the camps and another bay
    (-86, -98), (-94, -90), (-97.5, -78), (-102, -66), (-99.5, -55), (-94, -47), (-95, -37), (-93, -27),
    (-87, -19), (-83, -11), (-87.5, -3), (-95, 5), (-101, 15), (-106, 27), (-104, 38), (-101, 47),
    (-100.5, 60), (-101, 75), (-100.2, 89),
    # NW corner and north-west wall with the river inlet and a spur
    (-96, 96.5), (-86, 97.5), (-72, 96.5), (-58, 97.5), (-46, 96.5), (-39, 99.5), (-27, 100.5),
    (-18, 96.5), (-8.5, 91.5), (1.5, 95), (10, 99.5), (16, 100.5),
]
# indices (in BOUNDARY_CTRL) of segments that keep existing geometry or stay open
CANYON_RANGE = ((12.0, 13.0), (-117.0, -252.0))   # existing canyon walls (Cliff / Cliff.001 / .002) are kept
GATE_X = (16.0, 30.0)                               # gate opening at the north (towers already there)


def chaikin(pts, it=3, closed=True):
    P = np.array(pts, float)
    for _ in range(it):
        Q = []
        n = len(P)
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            a = P[i]; b = P[(i + 1) % n]
            Q.append(0.75 * a + 0.25 * b); Q.append(0.25 * a + 0.75 * b)
        P = np.array(Q)
    return P


def resample(P, step, closed=True):
    Q = np.vstack([P, P[:1]]) if closed else P
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(s[-1] / step))
    t = np.linspace(0, s[-1], n, endpoint=not closed)
    x = np.interp(t, s, Q[:, 0]); y = np.interp(t, s, Q[:, 1])
    return np.c_[x, y], t


def boundary_polygon(step=1.0):
    P = chaikin(BOUNDARY_CTRL, 3, True)
    return resample(P, step, True)[0]


def point_in_poly(poly, x, y):
    """Vectorised even-odd test; x, y arrays or scalars."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    inside = np.zeros(np.broadcast(x, y).shape, bool)
    px, py = poly[:, 0], poly[:, 1]
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi, xj, yj = px[i], py[i], px[j], py[j]
        cond = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        inside ^= cond
        j = i
    return inside


# ------------------------------------------------------------------------------------------------
# River: (x, y, w = bed half-width, b = bank width, kind)
# ------------------------------------------------------------------------------------------------
RIVER_CTRL = [
    (-52, 470, 4.6, 3.0, 'out'), (-30, 360, 4.4, 3.0, 'out'), (-44, 250, 4.2, 2.8, 'out'),
    (-36, 175, 4.0, 2.6, 'out'), (-34, 140, 4.0, 2.6, 'out'), (-33, 112, 3.6, 2.4, 'out'),
    (-33, 97, 3.2, 2.4, 'gap'),            # north inlet between the rocks
    (-35, 82, 3.8, 2.8, 'main'),
    (-33.5, 65, 4.4, 4.4, 'ford'),         # Ford N (mesa foot <-> hill 0c)
    (-33.5, 49, 4.0, 3.0, 'main'),
    (-24, 36, 4.6, 3.2, 'main'),
    (-14, 21, 4.4, 3.0, 'bridge'),         # Bridge 1: main road
    (-7, 8, 5.2, 3.2, 'main'),
    (-5.5, -6, 6.0, 6.0, 'ford'),          # Ford C (centre)
    (-2, -20, 4.8, 3.2, 'main'),
    (6, -30, 5.6, 3.2, 'main'),
    (12, -32.5, 6.2, 6.0, 'ford'),         # Ford S (centre <-> south)
    (27, -31.5, 4.0, 3.4, 'bridge2'),      # Bridge 2: track to the ridge pass
    (38, -29.5, 4.4, 3.0, 'main'),
    (47, -33.5, 4.0, 3.0, 'main'),
    (54, -41.5, 3.6, 2.6, 'main'),
    (64, -45.2, 2.3, 2.6, 'narrow'),
    (75, -45.6, 2.2, 2.5, 'narrow'),
    (85, -52, 3.2, 2.9, 'main'),
    (95, -57, 3.6, 2.6, 'main'),
    (104, -59.5, 3.2, 2.4, 'gap'),         # east outlet between the rocks
    (120, -63, 3.8, 2.6, 'out'), (150, -66, 4.2, 2.8, 'out'), (180, -70, 4.4, 2.8, 'out'),
    (240, -88, 4.6, 3.0, 'out'), (330, -70, 4.8, 3.0, 'out'), (450, -98, 5.0, 3.2, 'out'),
]


class River:
    def __init__(self, step=0.5):
        C = np.array([(p[0], p[1]) for p in RIVER_CTRL], float)
        attrs = np.array([(p[2], p[3], DEPTH_FORD if p[4] == 'ford' else DEPTH_MAIN) for p in RIVER_CTRL], float)
        kinds = [p[4] for p in RIVER_CTRL]
        # Catmull-Rom through the control points
        pts = []; at = []; kd = []
        n = len(C)
        for i in range(n - 1):
            p0 = C[max(i - 1, 0)]; p1 = C[i]; p2 = C[i + 1]; p3 = C[min(i + 2, n - 1)]
            L = np.linalg.norm(p2 - p1); m = max(2, int(L / step))
            for k in range(m):
                t = k / m
                t2, t3 = t * t, t * t * t
                q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
                s = t * t * (3 - 2 * t)                       # smooth attribute blend
                pts.append(q); at.append(attrs[i] * (1 - s) + attrs[i + 1] * s)
                kd.append(kinds[i] if s < 0.5 else kinds[i + 1])
        pts.append(C[-1]); at.append(attrs[-1]); kd.append(kinds[-1])
        self.P = np.array(pts); self.A = np.array(at); self.kind = kd
        d = np.diff(self.P, axis=0); seg = np.linalg.norm(d, axis=1)
        self.s = np.concatenate([[0], np.cumsum(seg)])
        T = np.vstack([d, d[-1:]]); T /= np.linalg.norm(T, axis=1, keepdims=True)
        self.T = T; self.N = np.c_[-T[:, 1], T[:, 0]]          # left normal
        # signed curvature (positive = turning left)
        ang = np.unwrap(np.arctan2(T[:, 1], T[:, 0]))
        k = np.gradient(ang, self.s + 1e-9)
        ker = np.ones(15) / 15
        self.curv = np.convolve(k, ker, mode='same')
        self.length = self.s[-1]

    def query(self, x, y):
        """For arrays x, y: nearest station index, signed lateral distance (left +), w, b, D, curvature."""
        x = np.atleast_1d(np.asarray(x, float)); y = np.atleast_1d(np.asarray(y, float))
        Pa = self.P[:-1]; Pb = self.P[1:]
        out_i = np.zeros(len(x), int); out_d = np.zeros(len(x)); out_t = np.zeros(len(x))
        for c0 in range(0, len(x), 4096):
            xx = x[c0:c0 + 4096, None]; yy = y[c0:c0 + 4096, None]
            dx = Pb[None, :, 0] - Pa[None, :, 0]; dy = Pb[None, :, 1] - Pa[None, :, 1]
            L2 = dx * dx + dy * dy + 1e-12
            t = np.clip(((xx - Pa[None, :, 0]) * dx + (yy - Pa[None, :, 1]) * dy) / L2, 0, 1)
            qx = Pa[None, :, 0] + t * dx; qy = Pa[None, :, 1] + t * dy
            dd = (xx - qx) ** 2 + (yy - qy) ** 2
            i = np.argmin(dd, axis=1)
            r = np.arange(len(i))
            sgn = np.sign((xx[:, 0] - qx[r, i]) * self.N[i, 0] + (yy[:, 0] - qy[r, i]) * self.N[i, 1])
            out_i[c0:c0 + 4096] = i; out_d[c0:c0 + 4096] = np.sqrt(dd[r, i]) * np.where(sgn == 0, 1, sgn)
            out_t[c0:c0 + 4096] = t[r, i]
        A = self.A[out_i] * (1 - out_t[:, None]) + self.A[np.minimum(out_i + 1, len(self.A) - 1)] * out_t[:, None]
        return out_i, out_d, A[:, 0], A[:, 1], A[:, 2], self.curv[out_i]

    def height(self, x, y):
        """Channel surface z (0 outside). Point bars on the inner side of bends."""
        i, d, w, b, D, k = self.query(x, y)
        ad = np.abs(d)
        bar = np.clip(np.sign(d) * k * 14.0 - 0.15, 0, 0.7)        # continuous in curvature (no thresholds)
        # bed: slightly deeper along the thalweg (shifted to the outer side in bends), raised point bar inside
        u = np.clip(ad / np.maximum(w, 1e-3), 0, 1)
        bed = -D * (1.0 - 0.12 * u * u)
        bed = bed * (1 - bar * np.clip((u - 0.25) / 0.75, 0, 1) ** 1.5 * 0.85)
        z = np.where(ad <= w, bed, 0.0)
        tb = np.clip((ad - w) / np.maximum(b, 1e-3), 0, 1)
        edge = -D * 0.88 * (1 - bar * 0.85)
        bank = edge * (1 - (tb * tb * (3 - 2 * tb)))          # smooth S-bank
        z = np.where((ad > w) & (ad < w + b), bank, z)
        return z, d, w, b, D, i

    def corridor(self, x, y, margin=0.0):
        i, d, w, b, D, k = self.query(x, y)
        return np.abs(d) < (w + b + margin)

    def water_halfwidth(self):
        """Per-station half-width of the water surface (where the bank crosses WATER_Z)."""
        w = self.A[:, 0]; b = self.A[:, 1]; D = self.A[:, 2]
        edge = -D * 0.88
        frac = np.clip(WATER_Z / edge, 0, 1)      # 1 - smoothstep(t) = frac -> solve
        ts = np.linspace(0, 1, 201); ss = 1 - ts * ts * (3 - 2 * ts)
        t = np.interp(frac, ss[::-1], ts[::-1])
        return w + t * b
