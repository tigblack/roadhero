"""v13 massif sculpting: designed heightfields for rock bodies with exact drivable floors.

A massif = a set of Unity floors (FloorPiece rects with their exact height functions). Every floor contributes
    term_F(p) = h_F(clamp_F(p)) - D(dist to F shrunk on its drop edges)
where D is a fall profile (rounded shoulder of radius rho, then a straight face of slope k). Drop edges facing
lower floors (or the ground where there is no room: river, roads) use the tight 'inner' profile (near-vertical,
0.2 m shoulder, inside the lane margins); edges facing open ground use the 'outer' profile (larger shoulder,
72-78 deg face, eroded / buttressed outline via noise on the distance, rounded corners, talus apron with
debris). Result = max over floors, talus and ground; rough faces, soft sedimentary benches on steep parts, a
small blur. Safe zones (floor rects minus their drop margins) are re-clamped to the exact Unity height (+1.2 cm
lift against z-fighting), so the car's surface is unchanged. The grid is a tensor product, dense (4-6 cm) in
bands around wall lines, coarse on decks; the dense mesh is quadric-decimated before attributes are written."""
import math
import numpy as np
import rg_sculpt as S


class Floor:
    def __init__(self, fl):
        rc = fl['rect']; self.name = fl['name']
        self.c = np.array((rc['center'][0], rc['center'][2]), float)
        yaw = math.radians(rc.get('yaw', 0.0))
        self.R = np.array((math.cos(yaw), -math.sin(yaw))); self.F = np.array((math.sin(yaw), math.cos(yaw)))
        self.hx, self.hz = float(rc['half'][0]), float(rc['half'][1])
        self.h0, self.h1 = float(fl['h0']), float(fl['h1'])
        self.ei = min(max(float(fl.get('easeIn', 0.0)), 0.0), 0.45); self.eo = min(max(float(fl.get('easeOut', 0.0)), 0.0), 0.45)

    def local(self, x, y):
        dx = x - self.c[0]; dy = y - self.c[1]
        return dx * self.R[0] + dy * self.R[1], dx * self.F[0] + dy * self.F[1]

    def world(self, lx, lz):
        return self.c[0] + self.R[0] * lx + self.F[0] * lz, self.c[1] + self.R[1] * lx + self.F[1] * lz

    def profile(self, u):
        a, b = self.ei, self.eo
        m = 1 - 0.5 * a - 0.5 * b
        s = np.where(u < a, u * u / (2 * a + 1e-9), np.where(u > 1 - b, m - (1 - u) ** 2 / (2 * b + 1e-9), u - 0.5 * a))
        return np.clip(s / m, 0, 1)

    def h_local(self, lz):
        lz = np.asarray(lz, float)
        if abs(self.h0 - self.h1) < 1e-6:
            return np.full_like(lz, self.h0)
        u = np.clip((lz + self.hz) / max(0.01, 2 * self.hz), 0, 1)
        return self.h0 + (self.h1 - self.h0) * self.profile(u)

    def h(self, x, y):
        lx, lz = self.local(x, y)
        return self.h_local(np.clip(lz, -self.hz, self.hz))

    def contains(self, x, y, m=0.0):
        lx, lz = self.local(x, y)
        return (np.abs(lx) <= self.hx + m) & (np.abs(lz) <= self.hz + m)


def floor_union_height(floors, x, y, exclude=None):
    """Highest floor containing (x, y); -1e9 where none (ground)."""
    h = np.full(np.shape(x), -1e9)
    for f in floors:
        if f is exclude:
            continue
        inside = f.contains(x, y)
        if inside.any():
            h = np.where(inside, np.maximum(h, f.h(x, y)), h)
    return h


def fall(x, rho, k):
    """Rounded shoulder (circle radius rho) continued by a straight face of slope k (x >= 0 outward)."""
    th = np.arctan(k)
    xt = rho * np.sin(th); dt = rho * (1 - np.cos(th))
    x = np.maximum(x, 0.0)
    return np.where(x <= xt, rho - np.sqrt(np.maximum(rho * rho - x * x, 0.0)), dt + k * (x - xt))


class Raster:
    """Evaluate an expensive field fn(x, y) once on a regular grid; bilinear lookups afterwards."""
    def __init__(self, fn, x0, x1, y0, y1, res=0.4):
        self.x0, self.y0, self.res = x0, y0, res
        xs = np.arange(x0, x1 + res, res); ys = np.arange(y0, y1 + res, res)
        Xg, Yg = np.meshgrid(xs, ys)
        self.G = np.asarray(fn(Xg, Yg), float); self.nx = len(xs); self.ny = len(ys)

    def __call__(self, x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        fx = np.clip((x - self.x0) / self.res, 0, self.nx - 1.001); fy = np.clip((y - self.y0) / self.res, 0, self.ny - 1.001)
        i = np.floor(fx).astype(int); j = np.floor(fy).astype(int); tx = fx - i; ty = fy - j
        G = self.G
        return (G[j, i] * (1 - tx) + G[j, i + 1] * tx) * (1 - ty) + (G[j + 1, i] * (1 - tx) + G[j + 1, i + 1] * tx) * ty


def dense_axis(lo, hi, base, lines, band, fine):
    pts = [np.arange(lo, hi + 1e-6, base)]
    for L in lines:
        a = max(lo, L - band); b = min(hi, L + band)
        if b > a:
            pts.append(np.arange(a, b + 1e-6, fine))
    v = np.unique(np.round(np.concatenate(pts), 4))
    keep = np.concatenate([[True], np.diff(v) > fine * 0.45])
    return v[keep]


class Massif:
    def __init__(self, floors, xs, ys, seed=0, inner=(0.2, 9.5, 0.24), outer=(0.6, 3.6, 0.55),
                 corner_r=1.2, erode=0.6, bulge=1.6, talus=(0.22, 0.35, 1.5, 0.3), space_fn=None, cap_fn=None,
                 strata=(0.95, 0.7), blur_sigma=1.3, deck_lift=0.012, bench=(0.48, 1.6, 2.6), inner_shrink=None,
                 rims=None, inner_rho=None):
        self.floors = floors; self.xs = np.asarray(xs, float); self.ys = np.asarray(ys, float); self.seed = seed
        self.inner = inner; self.outer = outer; self.corner_r = corner_r; self.erode = erode; self.bulge = bulge
        self.talus = talus; self.space_fn = space_fn; self.cap_fn = cap_fn; self.strata = strata
        self.blur_sigma = blur_sigma; self.deck_lift = deck_lift; self.bench = bench
        self.inner_shrink = inner_shrink or {}; self.inner_rho = inner_rho or {}
        self.rims = rims or []          # (floor name, side, height, width)

    def edge_info(self, f, lxc, lzc, side):
        """Per point, at its nearest point on edge 'side': (drop 0..1, outer-style weight 0..1)."""
        eps = 0.06
        acc_drop = 0.0; acc_out = 0.0
        for sh in (-0.8, 0.0, 0.8):
            if side in ('w', 'e'):
                sg = -1 if side == 'w' else 1
                lz = np.clip(lzc + sh, -f.hz, f.hz)
                qx, qy = f.world(np.full_like(lz, sg * (f.hx + eps)), lz); ex, ey = f.world(np.full_like(lz, sg * f.hx), lz)
                q2x, q2y = f.world(np.full_like(lz, sg * (f.hx + 1.2)), lz)
            else:
                sg = -1 if side == 's' else 1
                lx = np.clip(lxc + sh, -f.hx, f.hx)
                qx, qy = f.world(lx, np.full_like(lx, sg * (f.hz + eps))); ex, ey = f.world(lx, np.full_like(lx, sg * f.hz))
                q2x, q2y = f.world(lx, np.full_like(lx, sg * (f.hz + 1.2)))
            nh = floor_union_height(self.floors, qx, qy, exclude=f)
            gnd = (nh < -1e8).astype(float)
            nh = np.where(nh < -1e8, 0.0, nh)
            hf = f.h(ex, ey)
            sp = self.space_fn(q2x, q2y) if self.space_fn is not None else 1.0
            acc_drop = acc_drop + S.smoothstep(0.04, 0.3, hf - nh)
            acc_out = acc_out + gnd * sp
        return acc_drop / 3.0, acc_out / 3.0

    def build(self):
        X, Y = np.meshgrid(self.xs, self.ys)
        self._G = np.zeros(X.shape)
        self._build_pass(X, Y, first=True)
        Z0 = self._Z0
        # recess field: horizontal strata grooves (by height) + vertical joints (along the faces)
        band, sharp = self.strata
        q = (Z0 - 0.17) / band
        tq = q - np.floor(q)
        grooves = np.exp(-((tq - 0.5) / 0.09) ** 2)
        joints = np.clip((S.ridged2(X * 0.42 + Y * 0.42, (X - Y) * 0.05, self.seed + 21, 2) - 0.86) / 0.14, 0, 1)
        self._G = (0.11 * grooves + 0.14 * joints) * (Z0 > 0.25)
        return self._build_pass(X, Y, first=False)

    def _build_pass(self, X, Y, first):
        shp = X.shape
        Z = np.zeros(shp)
        safe_h = np.full(shp, -1e9)
        owner = np.full(shp, -1)
        talus_z = np.zeros(shp)
        rock_w = np.zeros(shp)
        ri, ki, mi_def = self.inner; ro, ko, mo = self.outer
        bf, bw, bk = self.bench
        n_er = S.fbm2(X * 0.33, Y * 0.33, self.seed + 1, 4)
        n_bu = S.fbm2(X * 0.06, Y * 0.06, self.seed + 2, 3)
        n_gu = S.ridged2(X * 0.23 + 3.1, Y * 0.23 - 1.7, self.seed + 3, 3)
        n_ru = S.ridged2(X * 0.62 - 1.3, Y * 0.62 + 2.9, self.seed + 4, 2)
        n_bh = S.fbm2(X * 0.11, Y * 0.11, self.seed + 5, 2)
        t_h, t_lift, t_len, t_noise = self.talus
        th_o = math.atan(ko); xt_o = ro * math.sin(th_o); dt_o = ro * (1 - math.cos(th_o))
        th_b = math.atan(bk); xt_b = 0.35 * math.sin(th_b); dt_b = 0.35 * (1 - math.cos(th_b))
        for fi, f in enumerate(self.floors):
            lx, lz = f.local(X, Y)
            near = (np.abs(lx) <= f.hx + 16) & (np.abs(lz) <= f.hz + 16)
            if not near.any():
                continue
            mi = self.inner_shrink.get(f.name, mi_def)
            rho_i = self.inner_rho.get(f.name, ri)
            lxc = np.clip(lx, -f.hx, f.hx); lzc = np.clip(lz, -f.hz, f.hz)
            info = {s: self.edge_info(f, lxc, lzc, s) for s in ('w', 'e', 's', 'n')}
            rimw = {s: 0.0 for s in 'wesn'}; rimh = {s: 0.0 for s in 'wesn'}
            for (nm, sd, hh, ww) in self.rims:
                if nm == f.name:
                    rimw[sd] = ww; rimh[sd] = hh
            shr = {}; go = {}
            for s, (dr, ow) in info.items():
                shr[s] = dr * ((1 - ow) * mi + ow * (mo + self.corner_r)) + rimw[s] + 0.2 * (rimw[s] > 0)
                go[s] = dr * ow
            lo_x = -f.hx + shr['w']; hi_x = f.hx - shr['e']; lo_z = -f.hz + shr['s']; hi_z = f.hz - shr['n']
            dx = np.maximum(np.maximum(lo_x - lx, 0), lx - hi_x)
            dz = np.maximum(np.maximum(lo_z - lz, 0), lz - hi_z)
            gx = np.where(lx < 0, go['w'], go['e']); gz = np.where(lz < 0, go['s'], go['n'])
            d2 = dx * dx + dz * dz
            wx = np.where(d2 > 0, dx * dx / np.maximum(d2, 1e-12), 0.5)
            g = wx * gx + (1 - wx) * gz
            rimx = np.where(lx < 0, rimw['w'], rimw['e']); rimz = np.where(lz < 0, rimw['s'], rimw['n'])
            rim_off = wx * rimx + (1 - wx) * rimz + 0.2 * ((wx * rimx + (1 - wx) * rimz) > 0)
            rc = self.corner_r * g
            dist = np.sqrt(d2) - rc - rim_off * g + self._G * (dist_pre := np.sqrt(d2) > 0)          # outer faces start at the rect edge also on rim edges
            dist_in = np.sqrt(d2) + self._G * (np.sqrt(d2) > 0)
            d_out = dist + g * (self.erode * (0.5 * n_er + 0.5 * np.clip(n_gu - 0.55, 0, 1) * 2.2)
                                + 0.32 * np.clip((n_ru - 0.8) / 0.2, 0, 1) - self.bulge * np.clip(n_bu, -1, 1))
            hf = f.h_local(lzc)
            # outer: upper face, bench at bf * H, lower face
            Hb = hf * (bf + 0.08 * n_bh)
            has_b = S.smoothstep(2.4, 4.2, hf)
            x_up = xt_o + np.maximum(hf - Hb - dt_o, 0) / ko
            w_b = bw * (0.7 + 0.6 * (0.5 + 0.5 * n_bh))
            up = hf - fall(d_out, ro, ko)
            lowf = Hb - fall(d_out - x_up - w_b, 0.35, bk)
            outer_t = up + has_b * (np.maximum(up, lowf) - up)
            inner_t = hf - fall(dist_in, rho_i, ki)
            term = (1 - g) * inner_t + g * outer_t
            Z = np.maximum(Z, np.where(near, term, -1e9))
            inside_safe = near & (dist_in <= 1e-9) & (np.abs(lx) <= f.hx) & (np.abs(lz) <= f.hz) & (np.sqrt(d2) - rc <= 1e-9)
            upd = inside_safe & (hf > safe_h)
            safe_h = np.where(upd, hf, safe_h); owner = np.where(upd, fi, owner)
            H = np.maximum(hf, 0.0)
            x_foot = np.where(has_b > 0.5, x_up + w_b + xt_b + np.maximum(Hb - dt_b, 0) / bk, xt_o + np.maximum(H - dt_o, 0) / ko)
            zt = (t_h * H + t_lift) * (1 + t_noise * n_gu)
            u = np.clip((d_out - x_foot + 0.3) / (t_len + 0.25 * H), 0, 1)
            tal = np.where(near & (d_out > -0.1), g * zt * (1 - u) ** 1.9, 0.0)
            talus_z = np.maximum(talus_z, np.minimum(tal, H))
            rock_w = np.maximum(rock_w, np.where(near, g * (dist > -0.05) * (1 - u), 0.0))
            # rock rims along chosen edges (v10/v11 parapet rocks -> one layered rim)
            for s_, hh in rimh.items():
                if hh <= 0:
                    continue
                ww = rimw[s_]
                if s_ == 'w':
                    e = lx + f.hx
                    along = lz
                elif s_ == 'e':
                    e = f.hx - lx; along = lz
                elif s_ == 's':
                    e = lz + f.hz; along = lx
                else:
                    e = f.hz - lz; along = lx
                inside_ok = (np.abs(lx) <= f.hx + 0.6) & (np.abs(lz) <= f.hz + 0.6) & (e > -0.6) & (e < ww + 0.4)
                c0 = ww * 0.5
                hump = np.sqrt(np.clip(1 - ((e - c0) / (c0 + 0.25)) ** 2, 0, 1)) ** 0.7
                gaps_ = S.smoothstep(0.45, 0.75, S.fbm2(X * 0.25 + 7.0, Y * 0.25 - 3.0, self.seed + 6, 2) + 0.35)
                rim = hf + hh * hump * (0.7 + 0.3 * n_bh) * (1 - 0.65 * (1 - gaps_))
                Z = np.maximum(Z, np.where(near & inside_ok, rim, -1e9))
                rock_w = np.maximum(rock_w, np.where(near & inside_ok, hump, 0.0))
        has = safe_h > -1e8
        Z = np.maximum(Z, talus_z)
        if first:
            self._Z0 = Z
            return None
        gy_, gx_ = np.gradient(Z, self.ys, self.xs)
        slope = np.sqrt(gx_ ** 2 + gy_ ** 2)
        steep = S.smoothstep(1.1, 2.8, slope) * (~has)
        det = 0.06 * S.fbm2(X * 0.9, Y * 0.9, self.seed + 9, 3) + 0.035 * S.fbm2(X * 2.7, Y * 2.7, self.seed + 10, 2)
        Z = Z + (rock_w * 0.7 + steep * 0.7) * det * (~has) * (Z > 0.02)
        band, sharp = self.strata
        Zt = S.soft_terrace(Z, band, sharp, phase=0.17)
        Z = Z + (Zt - Z) * steep * 0.85
        Z = S.blur2(Z, self.blur_sigma)
        Z = np.where(has, safe_h + self.deck_lift, Z)
        if self.cap_fn is not None:
            Z = np.where(has, Z, np.minimum(Z, self.cap_fn(X, Y)))
        gy_, gx_ = np.gradient(Z, self.ys, self.xs)
        lap = np.gradient(gx_, self.xs, axis=1) + np.gradient(gy_, self.ys, axis=0)
        self.cav = np.clip(S.blur2(lap, 2.5) * 0.3, -1, 1)
        self.X, self.Y, self.Z, self.has, self.safe_h, self.owner = X, Y, Z, has, safe_h, owner
        return X, Y, Z


def massif_mesh(M, target_tris, tuck=-0.045):
    """Dense grid -> triangles (ground cells dropped, rim tucked under the ground) -> decimated.
    Returns co, tris, point attrs (deck, cav, owner)."""
    Z = M.Z.copy()
    low = (Z < 0.004) & (~M.has)
    keepv = ~low
    cells = keepv[:-1, :-1] | keepv[:-1, 1:] | keepv[1:, :-1] | keepv[1:, 1:]
    Z = np.where(low, tuck, Z)
    co, tris, used = S.grid_tris(M.X, M.Y, Z, cells)
    deck = M.has.ravel()[used].astype(float)
    cav = M.cav.ravel()[used]
    own = M.owner.ravel()[used].astype(float)
    ratio = min(1.0, target_tris / max(1, len(tris)))
    co2, t2, at = S.decimate(co, tris, ratio, {'deck': deck, 'cav': cav, 'own': own})
    return co2, t2, at, len(tris)
