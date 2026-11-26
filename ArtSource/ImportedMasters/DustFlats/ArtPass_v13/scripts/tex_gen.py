"""Procedural, seamless source textures for the DustFlats v11 art pass (numpy inside Blender).

blender -b --factory-startup --python tex_gen.py -- --out ../textures [--only ground,road,rock,trim]

BaseMaps (RoadGame/Toon multiplies them by vertex colour, so most are near-neutral detail maps):
  T_Ground_DustFlats_BaseMap_2K.png   2048^2, world-UV tile 40 m (1.95 cm/px)
  T_Road_Asphalt_BaseMap_1Kx2K.png    1024x2048, U = full road width incl. sandy shoulders, V tile = 32 m
  T_Rock_Strata_BaseMap_1K.png        1024^2, box-projected, tile 6 m
  T_Trim_Structures_BaseMap_2K.png    2048^2 trim sheet, 8 horizontal strips (tile in U)
Extra PBR maps (not used by the current RoadToon shader) go to ../textures/pbr_extra:
  *_Normal (OpenGL/Y+), *_Roughness, *_AO, all derived from the same height fields.
"""
import bpy, numpy as np, os, sys, argparse, math

# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------
def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)

def save_png(arr, path, srgb_encode=True):
    """arr: HxWx{1,3,4} float in linear (if srgb_encode) or raw data (normal/rough/ao). Row 0 = top."""
    a = np.asarray(arr, np.float32)
    if a.ndim == 2: a = a[..., None]
    if a.shape[2] == 1: a = np.repeat(a, 3, 2)
    if a.shape[2] == 3: a = np.concatenate([a, np.ones(a.shape[:2] + (1,), np.float32)], 2)
    if srgb_encode: a[..., :3] = to_srgb(a[..., :3])
    a = np.clip(a, 0, 1)
    h, w = a.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = 'sRGB' if srgb_encode else 'Non-Color'
    im.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    im.filepath_raw = path; im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    print("TEX", os.path.basename(path), w, h, flush=True)

def vnoise(W, H, cx, cy, rs):
    """Tileable smooth value noise in [0,1]; cx, cy = cells across width/height."""
    g = rs.random((cy, cx)).astype(np.float32)
    x = (np.arange(W) + 0.5) * cx / W; y = (np.arange(H) + 0.5) * cy / H
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = x - x0; fy = y - y0
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    x0 %= cx; y0 %= cy; x1 = (x0 + 1) % cx; y1 = (y0 + 1) % cy
    a = g[np.ix_(y0, x0)]; b = g[np.ix_(y0, x1)]; c = g[np.ix_(y1, x0)]; d = g[np.ix_(y1, x1)]
    fx = fx[None, :]; fy = fy[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

def fbm(W, H, cx, cy, rs, octaves=4, gain=0.5, lac=2):
    s = np.zeros((H, W), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        s += amp * vnoise(W, H, int(cx * lac ** o), int(cy * lac ** o), rs); tot += amp; amp *= gain
    return s / tot

def blur(a, sigma_px):
    """Periodic gaussian blur via FFT (keeps tiling)."""
    H, W = a.shape
    ky = np.fft.fftfreq(H)[:, None]; kx = np.fft.fftfreq(W)[None, :]
    G = np.exp(-2 * (math.pi ** 2) * (sigma_px ** 2) * (kx ** 2 + ky ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * G)).astype(np.float32)

def voronoi(W, H, cx, cy, rs, jitter=0.85):
    """Tileable Voronoi: returns F1, F2 in pixels and nearest cell id."""
    pts = rs.random((cy, cx, 2)) * jitter + (1 - jitter) / 2
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xs + 0.5) / W * cx; v = (ys + 0.5) / H * cy
    iu = np.floor(u).astype(int); iv = np.floor(v).astype(int)
    F1 = np.full((H, W), 1e9, np.float32); F2 = np.full((H, W), 1e9, np.float32); ID = np.zeros((H, W), np.int32)
    sx = W / cx; sy = H / cy
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cu = iu + dx; cv = iv + dy
            p = pts[cv % cy, cu % cx]
            d = np.hypot((cu + p[..., 0] - u) * sx, (cv + p[..., 1] - v) * sy)
            cid = (cv % cy) * cx + (cu % cx)
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d)); ID = np.where(closer, cid, ID); F1 = np.where(closer, d, F1)
    return F1, F2, ID

def draw_polyline(field, pts, width, value=1.0, soft=1.0, wrap=True):
    """Max-composite an antialiased polyline (pixel coords) of given half-width into field."""
    H, W = field.shape
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        r = width + soft + 1
        xa = int(math.floor(min(x0, x1) - r)); xb = int(math.ceil(max(x0, x1) + r))
        ya = int(math.floor(min(y0, y1) - r)); yb = int(math.ceil(max(y0, y1) + r))
        ys, xs = np.mgrid[ya:yb + 1, xa:xb + 1].astype(np.float32)
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy + 1e-6
        t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / L2, 0, 1)
        d = np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy))
        val = value * np.clip((width + soft - d) / soft, 0, 1)
        yi = (ys.astype(int) % H) if wrap else np.clip(ys.astype(int), 0, H - 1)
        xi = (xs.astype(int) % W) if wrap else np.clip(xs.astype(int), 0, W - 1)
        np.maximum.at(field, (yi, xi), val)

def crack_walk(rs, x, y, ang, steps, step_len, wiggle=0.35, branch=0.08, depth=0, out=None):
    out = out if out is not None else []
    pts = [(x, y)]
    for i in range(steps):
        ang += rs.normal(0, wiggle)
        x += math.cos(ang) * step_len; y += math.sin(ang) * step_len
        pts.append((x, y))
        if depth < 2 and rs.random() < branch:
            crack_walk(rs, x, y, ang + rs.choice([-1, 1]) * rs.uniform(0.5, 1.1), int(steps * rs.uniform(0.2, 0.5)),
                       step_len * 0.8, wiggle, branch * 0.5, depth + 1, out)
    out.append((pts, depth))
    return out

def normal_from_height(h, strength):
    """OpenGL (Y+) tangent-space normal map from a tileable height field (row 0 = top)."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    n = np.stack([-gx, gy, np.ones_like(h)], -1)  # image rows go down -> +gy means surface rises downward
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5

def ao_from_height(h, sigma, strength):
    cav = h - blur(h, sigma)
    return np.clip(1.0 + cav * strength, 0.45, 1.0)

def disc(field, cx, cy, r, value, soft=1.0, mode='max'):
    H, W = field.shape
    xa, xb = int(cx - r - soft - 1), int(cx + r + soft + 1); ya, yb = int(cy - r - soft - 1), int(cy + r + soft + 1)
    ys, xs = np.mgrid[ya:yb + 1, xa:xb + 1].astype(np.float32)
    d = np.hypot(xs - cx, ys - cy)
    a = np.clip((r + soft - d) / soft, 0, 1)
    yi = ys.astype(int) % H; xi = xs.astype(int) % W
    if mode == 'max':
        np.maximum.at(field, (yi, xi), a * value)
    else:  # 'min' (value < 1 darkens)
        np.minimum.at(field, (yi, xi), 1 - a * (1 - value))
    return a

# ------------------------------------------------------------------------------------------------
# GROUND  (2048^2, tile 40 m)
# ------------------------------------------------------------------------------------------------
def gen_ground(out, pbr):
    N = 2048; rs = np.random.default_rng(1701)
    big = fbm(N, N, 2, 2, rs, 3, 0.55)                 # 16 m features
    mid = fbm(N, N, 6, 6, rs, 3, 0.5)                  # ~5 m
    fine = fbm(N, N, 48, 48, rs, 2, 0.5)               # ~0.6 m, very low contrast
    # compacted (packed) sand patches: calm, slightly darker, smoother
    packed = np.clip((fbm(N, N, 4, 4, rs, 3, 0.5) - 0.52) / 0.10, 0, 1)
    packed = blur(packed, 10)
    # rare crack clusters inside a few packed patches
    crackmask = np.clip((fbm(N, N, 3, 3, rs, 2, 0.5) - 0.50) / 0.08, 0, 1) * np.clip(packed * 1.6, 0, 1)
    F1, F2, ID = voronoi(N, N, 22, 22, rs, 0.9)        # ~1.45 m cells
    edge = F2 - F1
    crack = np.clip(1 - (edge - 1.2) / 2.6, 0, 1)      # 2-3 px wide lines
    wob = vnoise(N, N, 90, 90, rs)
    crack *= np.clip((crackmask - 0.10 - 0.25 * wob) / 0.2, 0, 1)
    # cells inside the cracked areas curl slightly: lighter centres, darker rims
    cellshade = np.clip(edge / 40.0, 0, 1) * crackmask
    # wind ripples on loose sand (outside packed patches), long and soft
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float32)
    warp = (fbm(N, N, 5, 5, rs, 2) - 0.5) * 60
    rip = np.sin((xs * 0.6 + ys * 0.8 + warp) * (2 * math.pi / 34.0))
    ripmask = (1 - packed) * np.clip((mid - 0.35) / 0.3, 0, 1)
    # sparse pebbles
    peb = np.zeros((N, N), np.float32); peb_h = np.zeros((N, N), np.float32)
    for i in range(420):
        x, y = rs.uniform(0, N, 2); r = rs.uniform(1.6, 4.5) * (2.0 if rs.random() < 0.06 else 1.0)
        disc(peb, x, y, r, rs.uniform(0.5, 1.0), 1.2)
        disc(peb_h, x, y, r, 1.0, r * 0.8)
    # luminance (neutral detail; hue comes from vertex colour)
    L = (0.90 + 0.06 * (big - 0.5) + 0.05 * (mid - 0.5) + 0.025 * (fine - 0.5)
         - 0.025 * packed + 0.010 * rip * ripmask
         - 0.22 * crack + 0.03 * cellshade - 0.10 * peb)
    # subtle hue: packed sand a touch redder, ripples/loose sand a touch yellower, pebbles cooler
    R = L * (1.0 + 0.010 * packed); G = L * (1.0 - 0.006 * packed + 0.006 * (1 - packed)); B = L * (1.0 - 0.015 * packed + 0.04 * peb)
    col = np.stack([R, G, B], -1)
    col = np.clip(col, 0, 1) ** 2.2 * 1.0  # values above are perceptual -> linear
    save_png(col, os.path.join(out, 'basemap', 'T_Ground_DustFlats_BaseMap_2K.png'))
    if pbr:
        h = 0.5 * big + 0.25 * mid + 0.06 * rip * ripmask - 0.9 * crack + 0.5 * peb_h - 0.1 * packed
        save_png(normal_from_height(h, 6.0), os.path.join(out, 'pbr_extra', 'T_Ground_DustFlats_Normal_2K.png'), False)
        rough = np.clip(0.93 - 0.06 * packed + 0.04 * crack, 0, 1)
        save_png(rough, os.path.join(out, 'pbr_extra', 'T_Ground_DustFlats_Roughness_2K.png'), False)
        save_png(ao_from_height(h, 6, 3.0), os.path.join(out, 'pbr_extra', 'T_Ground_DustFlats_AO_2K.png'), False)

# ------------------------------------------------------------------------------------------------
# ROAD  (1024 x 2048; U across full road width; V tile 32 m)
# ------------------------------------------------------------------------------------------------
def gen_road(out, pbr):
    W, H = 1024, 2048; rs = np.random.default_rng(4242)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xs + 0.5) / W; v = (ys + 0.5) / H          # v grows downward in image rows (tiles anyway)
    asphalt = np.array([0.205, 0.180, 0.215])         # linear muted grey-lilac
    sand = np.array([0.60, 0.38, 0.19])
    big = fbm(W, H, 3, 6, rs, 3, 0.55); mid = fbm(W, H, 10, 20, rs, 3, 0.5)
    grain = rs.random((H, W)).astype(np.float32); grain = blur(grain, 0.8)
    agg = np.clip((grain - 0.5) * 3.0, -1, 1)
    # tyre polish bands (two per lane)
    bands = np.zeros((H, W), np.float32)
    for c in (0.22, 0.33, 0.67, 0.78):
        bands += np.exp(-((u - c) / 0.045) ** 2)
    bands *= 0.6 + 0.4 * fbm(W, H, 2, 12, rs, 2)
    lum = 1.0 + 0.10 * (big - 0.5) + 0.07 * (mid - 0.5) + 0.035 * agg * (1 - 0.6 * bands) - 0.05 * bands
    col = asphalt[None, None, :] * lum[..., None]
    hfield = 0.02 * agg + 0.1 * (mid - 0.5)
    # patches (newer, darker, crisp edges)
    patch = np.zeros((H, W), np.float32)
    for (pu, pv, pw, ph) in ((0.30, 0.18, 0.20, 0.07), (0.68, 0.64, 0.24, 0.05), (0.42, 0.86, 0.14, 0.035)):
        rough_edge = (vnoise(W, H, 60, 120, rs) - 0.5) * 0.014 + (vnoise(W, H, 14, 28, rs) - 0.5) * 0.02
        m = ((np.abs(u - pu) < pw / 2 + rough_edge) & (np.abs(v - pv) < ph / 2 + rough_edge)).astype(np.float32)
        patch = np.maximum(patch, m)
    patch = blur(patch, 0.7)
    rim = np.clip(blur(patch, 2.5) - patch, 0, 1) * 4 + np.clip(patch - blur(patch, 2.5), 0, 1) * 2
    col = col * (1 - patch[..., None] * 0.13) * (1 - 0.12 * np.clip(rim, 0, 1)[..., None])
    hfield += 0.05 * patch
    # cracks: two long branching cracks, one sealed (tar) crack, one alligator cluster
    crack = np.zeros((H, W), np.float32); crack_h = np.zeros((H, W), np.float32); tar = np.zeros((H, W), np.float32)
    for (x, y, a, steps) in ((0.45 * W, 0.02 * H, math.pi / 2 + 0.2, 70), (0.62 * W, 0.47 * H, math.pi / 2 - 0.3, 55)):
        for pts, depth in crack_walk(rs, x, y, a, steps, 9.0, 0.32, 0.12):
            draw_polyline(crack, pts, 1.5 if depth == 0 else 0.9, 1.0, 1.0)
            draw_polyline(crack_h, pts, 5.0, 1.0, 5.0)
    for pts, depth in crack_walk(rs, 0.25 * W, 0.72 * H, 0.15, 60, 9.0, 0.18, 0.0):
        draw_polyline(tar, pts, 5.5, 1.0, 2.0)
    F1, F2, _ = voronoi(W, H, 26, 52, rs, 0.9)
    ally_m = np.exp(-(((u - 0.74) / 0.11) ** 2 + ((v - 0.30) / 0.05) ** 2))
    ally = np.clip(1 - (F2 - F1 - 0.8) / 1.6, 0, 1) * np.clip((ally_m - 0.25) / 0.4, 0, 1)
    crack = np.maximum(crack, ally * 0.9)
    col = col * (1 - 0.55 * crack[..., None]) * (1 + 0.06 * np.clip(crack_h - crack, 0, 1)[..., None])
    col = col * (1 - 0.30 * tar[..., None])
    hfield -= 0.6 * crack - 0.02 * tar
    # markings: worn white edge lines and yellow centre dashes (4 dashes per 32 m tile)
    erode = fbm(W, H, 30, 60, rs, 3, 0.55)
    edge_l = ((np.abs(u - 0.072) < 0.0085) | (np.abs(u - 0.928) < 0.0085)).astype(np.float32)
    edge_l = blur(edge_l, 0.9) * np.clip((erode - 0.30) / 0.12, 0, 1)
    edge_l *= np.clip((fbm(W, H, 2, 16, rs, 2) - 0.25) / 0.1, 0, 1)   # broken sections
    dash_v = (v * 4.0) % 1.0
    dash = ((np.abs(u - 0.5) < 0.0105) & (dash_v > 0.08) & (dash_v < 0.46)).astype(np.float32)
    dash = blur(dash, 0.9) * np.clip((erode - 0.26) / 0.10, 0, 1) * (1 - 0.8 * patch)
    white = np.array([0.80, 0.77, 0.70]); yellow = np.array([0.90, 0.55, 0.06])
    col = col * (1 - edge_l[..., None]) + white * edge_l[..., None] * (0.9 + 0.1 * lum[..., None])
    col = col * (1 - dash[..., None]) + yellow * dash[..., None] * (0.92 + 0.08 * lum[..., None])
    hfield += 0.03 * (edge_l + dash)
    # sandy shoulders and wind-blown sand fingers onto the asphalt
    edge_d = np.minimum(u, 1 - u)                     # 0 at the very edge
    shoulder = np.clip((0.045 - edge_d) / 0.03, 0, 1)
    fingers = fbm(W, H, 4, 24, rs, 4, 0.55)
    dust = np.clip((0.13 - edge_d) / 0.11, 0, 1) ** 1.6 * (0.35 + 0.65 * fingers)
    drift = np.clip((fingers - 0.62) / 0.12, 0, 1) * np.clip((0.22 - edge_d) / 0.18, 0, 1)
    sandiness = np.clip(np.maximum(shoulder, 0.55 * dust + 0.75 * drift), 0, 1)
    sandcol = sand[None, None, :] * (0.92 + 0.1 * mid[..., None])
    col = col * (1 - sandiness[..., None]) + sandcol * sandiness[..., None]
    hfield += 0.15 * sandiness
    save_png(col, os.path.join(out, 'basemap', 'T_Road_Asphalt_BaseMap_1Kx2K.png'))
    if pbr:
        save_png(normal_from_height(hfield, 10.0), os.path.join(out, 'pbr_extra', 'T_Road_Asphalt_Normal_1Kx2K.png'), False)
        rough = np.clip(0.80 - 0.12 * bands - 0.08 * tar + 0.12 * sandiness + 0.05 * crack - 0.1 * (edge_l + dash), 0, 1)
        save_png(rough, os.path.join(out, 'pbr_extra', 'T_Road_Asphalt_Roughness_1Kx2K.png'), False)
        save_png(ao_from_height(hfield, 4, 4.0), os.path.join(out, 'pbr_extra', 'T_Road_Asphalt_AO_1Kx2K.png'), False)

# ------------------------------------------------------------------------------------------------
# ROCK  (1024^2, tile 6 m) — soft strata, grain, a few fractures; neutral (vertex colour gives hue)
# ------------------------------------------------------------------------------------------------
def gen_rock(out, pbr):
    N = 1024; rs = np.random.default_rng(777)
    ys, xs = np.mgrid[0:N, 0:N].astype(np.float32)
    warp = (fbm(N, N, 3, 2, rs, 3) - 0.5) * 70
    # strata: layered bands of varying thickness (vertical position = image row)
    yy = ys + warp
    layer = np.sin(yy * 2 * math.pi / 170) * 0.6 + np.sin(yy * 2 * math.pi / 61 + 1.3) * 0.4
    lines = np.abs(np.sin(yy * 2 * math.pi / 122)) ; lines = np.clip(1 - lines / 0.05, 0, 1)
    lines *= np.clip((fbm(N, N, 8, 2, rs, 2) - 0.35) / 0.2, 0, 1)
    mott = fbm(N, N, 4, 4, rs, 4, 0.55)
    grain = blur(rs.random((N, N)).astype(np.float32), 1.0)
    # vertical fractures (few, soft)
    frac = np.zeros((N, N), np.float32)
    for i in range(3):
        x = rs.uniform(0, N); y = rs.uniform(0, N)
        for pts, d in crack_walk(rs, x, y, math.pi / 2 + rs.normal(0, 0.25), 16, 12.0, 0.25, 0.04):
            draw_polyline(frac, pts, 1.6 if d == 0 else 1.0, 1.0, 1.5)
    blot = fbm(N, N, 10, 10, rs, 3, 0.55)
    spots = np.clip((fbm(N, N, 24, 24, rs, 2, 0.5) - 0.62) / 0.08, 0, 1)
    L = (0.92 + 0.022 * layer + 0.10 * (mott - 0.5) + 0.06 * (blot - 0.5) + 0.03 * (grain - 0.5)
         - 0.04 * lines * 0.5 - 0.05 * spots - 0.20 * frac)
    col = np.stack([L * 1.01, L, L * 0.985], -1)
    col = np.clip(col, 0, 1) ** 2.2
    save_png(col, os.path.join(out, 'basemap', 'T_Rock_Strata_BaseMap_1K.png'))
    if pbr:
        h = 0.3 * layer + 0.3 * mott + 0.1 * grain - 0.5 * lines - 0.8 * frac
        save_png(normal_from_height(h, 5.0), os.path.join(out, 'pbr_extra', 'T_Rock_Strata_Normal_1K.png'), False)
        save_png(np.clip(0.9 + 0.05 * (grain - 0.5), 0, 1), os.path.join(out, 'pbr_extra', 'T_Rock_Strata_Roughness_1K.png'), False)
        save_png(ao_from_height(h, 5, 2.5), os.path.join(out, 'pbr_extra', 'T_Rock_Strata_AO_1K.png'), False)

# ------------------------------------------------------------------------------------------------
# TRIM SHEET  (2048^2, 8 strips of 256 px; strip k occupies UV v in [k/8, (k+1)/8], tiles in U)
# ------------------------------------------------------------------------------------------------
TRIM_STRIPS = {
    'plain':      (0.0, 0.0625),   # white: pure vertex colour
    'grime':      (0.0625, 0.125), # soft vertical grime gradient (bottom dark)
    'board_a':    (0.125, 0.25),   # wood board, grain along U
    'board_b':    (0.25, 0.375),   # weathered grey board with cracks and nails
    'corrugated': (0.375, 0.5),    # corrugated sheet, ribs across U, rust streaks at bottom
    'panel':      (0.5, 0.625),    # painted steel panel: seams across U, rivet rows, edge wear
    'rustplate':  (0.625, 0.75),   # rusty plate
    'concrete':   (0.75, 0.875),   # concrete with joints and stains
    'hazard':     (0.875, 0.9375), # black/yellow diagonal stripes (coloured)
    'diamond':    (0.9375, 1.0),   # diamond tread plate
}

def gen_trim(out, pbr):
    N = 2048; rs = np.random.default_rng(99)
    img = np.ones((N, N, 3), np.float32); hh = np.zeros((N, N), np.float32); rough = np.full((N, N), 0.8, np.float32)
    def rows(name):
        v0, v1 = TRIM_STRIPS[name]
        # UV v=0 is the bottom image row
        r0 = int(round((1 - v1) * N)); r1 = int(round((1 - v0) * N))
        return r0, r1
    def strip_coords(name):
        r0, r1 = rows(name); h = r1 - r0
        ys, xs = np.mgrid[0:h, 0:N].astype(np.float32)
        t = 1 - (ys + 0.5) / h     # 0 bottom of strip, 1 top
        return r0, r1, xs, t, h
    # plain
    r0, r1 = rows('plain'); img[r0:r1] = 1.0; rough[r0:r1] = 0.7
    # grime gradient
    r0, r1, xs, t, h = strip_coords('grime')
    n = fbm(N, h, 16, 2, rs, 3)
    g = 0.62 + 0.38 * np.clip(t * 1.4 + (n - 0.5) * 0.4, 0, 1)
    img[r0:r1] = g[..., None] ** 2.2
    # wood boards
    for name, base, grey, crk in (('board_a', 1.0, 0.0, 0.0), ('board_b', 0.95, 1.0, 1.0)):
        r0, r1, xs, t, h = strip_coords(name)
        warp = (fbm(N, h, 3, 2, rs, 3) - 0.5) * 46 + (fbm(N, h, 14, 2, rs, 2) - 0.5) * 9
        phase = (t * h + warp) / rs.uniform(10, 14)
        lines = np.clip(1 - np.abs((phase % 1.0) - 0.5) * 2 / 0.16, 0, 1) ** 1.5
        lines *= np.clip((fbm(N, h, 10, 3, rs, 3) - 0.3) / 0.35, 0, 1)
        rings = lines
        streak = fbm(N, h, 3, 24, rs, 3, 0.6)
        L = 0.87 + 0.16 * (streak - 0.5) - 0.13 * lines
        # darker board edges (top/bottom of the strip) and end joints every 2 m (512 px)
        edge = np.clip(1 - np.minimum(t, 1 - t) / 0.07, 0, 1)
        L -= 0.22 * edge ** 2
        joint = np.clip(1 - np.abs(((xs + 0.5) % 512) - 256) / 3.0, 0, 1) * 0 + np.clip(1 - np.minimum(xs % 512, 512 - xs % 512) / 3.0, 0, 1)
        L -= 0.35 * joint
        # knots
        for i in range(5):
            kx = rs.uniform(0, N); ky = rs.uniform(0.25, 0.75) * h
            d = np.hypot((xs - kx) / 2.2, (t * h - ky))
            L -= 0.18 * np.exp(-(d / 5.0) ** 2) - 0.05 * np.exp(-((d - 9) / 2.0) ** 2)
        # nails near the joints
        tmp = np.zeros((h, N), np.float32)
        for jx in range(0, N, 512):
            for ny in (0.28, 0.72):
                disc(tmp, (jx + 14) % N, ny * h, 3.2, 1.0, 1.0); disc(tmp, (jx - 14) % N, ny * h, 3.2, 1.0, 1.0)
        L = L * (1 - 0.45 * tmp)
        if crk:
            cr = np.zeros((h, N), np.float32)
            for i in range(7):
                x = rs.uniform(0, N); y = rs.uniform(0.2, 0.8) * h
                for pts, d in crack_walk(rs, x, y, rs.choice([0, math.pi]) + rs.normal(0, 0.05), 14, 10.0, 0.06, 0.0):
                    draw_polyline(cr, pts, 1.0, 1.0, 1.0)
            L -= 0.3 * cr
        col = np.stack([L, L, L], -1)
        if grey:  # sun-bleached grey wood: lower contrast, cooler
            col = col * 0.9 + 0.08
        img[r0:r1] = np.clip(col, 0, 1) ** 2.2
        hh[r0:r1] = 0.3 * rings + 0.2 * streak - 0.8 * edge ** 2 - 0.8 * joint
        rough[r0:r1] = 0.88
    # corrugated
    r0, r1, xs, t, h = strip_coords('corrugated')
    rib = np.sin(xs * 2 * math.pi / 48.0)            # 48 px ribs (~7.5 cm at 2 m/U... visual)
    shade = 0.88 + 0.10 * rib
    streaks = fbm(N, h, 120, 2, rs, 2, 0.5)
    rustst = np.clip((streaks - 0.55) / 0.2, 0, 1) * np.clip(1 - t / 0.55, 0, 1)
    dirt = fbm(N, h, 10, 2, rs, 3)
    col = np.stack([shade, shade, shade], -1) * (0.95 + 0.1 * (dirt[..., None] - 0.5))
    rustc = np.array([0.55, 0.30, 0.17])
    col = col * (1 - 0.6 * rustst[..., None]) + rustc * 0.6 * rustst[..., None] * shade[..., None]
    edge = np.clip(1 - np.minimum(t, 1 - t) / 0.04, 0, 1)
    col *= (1 - 0.25 * edge[..., None])
    img[r0:r1] = np.clip(col, 0, 1) ** 2.2
    hh[r0:r1] = 0.6 * rib; rough[r0:r1] = 0.55 + 0.3 * rustst
    # painted panel
    r0, r1, xs, t, h = strip_coords('panel')
    seam = np.clip(1 - np.minimum(xs % 384, 384 - xs % 384) / 2.5, 0, 1)       # panel every 384 px
    wear = fbm(N, h, 30, 4, rs, 4, 0.6)
    edgezone = np.clip(1 - np.minimum(t, 1 - t) / 0.12, 0, 1) + 0.8 * np.clip(1 - np.minimum(xs % 384, 384 - xs % 384) / 18, 0, 1)
    chip = np.clip((wear - 0.62 + 0.25 * np.clip(edgezone, 0, 1)) / 0.06, 0, 1) * np.clip(edgezone, 0, 1)
    L = 0.94 + 0.05 * (fbm(N, h, 8, 2, rs, 2) - 0.5)
    col = np.stack([L, L, L], -1)
    bare = np.array([0.62, 0.60, 0.58])     # chipped paint shows bright steel/primer
    col = col * (1 - chip[..., None]) + bare * chip[..., None]
    col *= (1 - 0.5 * seam[..., None])
    riv = np.zeros((h, N), np.float32); rivh = np.zeros((h, N), np.float32)
    for x in np.arange(24, N, 48):
        for ry in (0.12, 0.88):
            disc(riv, x, ry * h, 4.0, 1.0, 1.0); disc(rivh, x, ry * h, 4.0, 1.0, 3.0)
    col = col * (1 - 0.25 * riv[..., None]) + 0.25 * riv[..., None] * (0.7 + 0.3 * rivh[..., None])
    img[r0:r1] = np.clip(col, 0, 1) ** 2.2
    hh[r0:r1] = -0.8 * seam + 0.6 * rivh - 0.2 * chip; rough[r0:r1] = 0.5 + 0.25 * chip
    # rusty plate (carries colour)
    r0, r1, xs, t, h = strip_coords('rustplate')
    blot = fbm(N, h, 16, 2, rs, 5, 0.6)
    pit = blur(rs.random((h, N)).astype(np.float32), 0.8)
    a = np.clip((blot - 0.42) / 0.25, 0, 1)
    base = np.array([0.70, 0.62, 0.56]); rc1 = np.array([0.60, 0.33, 0.18]); rc2 = np.array([0.36, 0.17, 0.09])
    col = base * (1 - a[..., None]) + (rc1 * (1 - a[..., None] * 0.5) + rc2 * a[..., None] * 0.5) * a[..., None]
    col *= (0.92 + 0.12 * (pit[..., None] - 0.5))
    col = col * 0.85 + 0.15 * col.mean(-1, keepdims=True)
    img[r0:r1] = np.clip(col, 0, 1) ** 2.2 * 1.2
    hh[r0:r1] = 0.4 * blot + 0.2 * pit; rough[r0:r1] = 0.75 + 0.15 * a
    # concrete
    r0, r1, xs, t, h = strip_coords('concrete')
    mott = fbm(N, h, 12, 2, rs, 5, 0.55)
    pores = np.zeros((h, N), np.float32)
    for i in range(220):
        disc(pores, rs.uniform(0, N), rs.uniform(0, h), rs.uniform(1.0, 2.6), 1.0, 1.2)
    joint = np.clip(1 - np.minimum(xs % 1024, 1024 - xs % 1024) / 3.0, 0, 1)
    stain = np.clip(1 - t / 0.35, 0, 1) * (0.5 + 0.5 * fbm(N, h, 40, 2, rs, 2))
    drip = np.clip((fbm(N, h, 90, 1, rs, 2) - 0.6) / 0.15, 0, 1) * np.clip(t, 0, 1) * 0.6
    L = 0.90 + 0.10 * (mott - 0.5) - 0.07 * pores - 0.4 * joint - 0.14 * stain - 0.08 * drip
    img[r0:r1] = np.clip(np.stack([L, L * 0.99, L * 0.97], -1), 0, 1) ** 2.2
    hh[r0:r1] = 0.2 * mott - 0.5 * pores - 0.9 * joint; rough[r0:r1] = 0.92
    # hazard stripes (coloured; use with white vertex colour)
    r0, r1, xs, t, h = strip_coords('hazard')
    ph = ((xs + t * h) / 128.0) % 1.0
    yel = np.array([0.92, 0.58, 0.04]); blk = np.array([0.035, 0.033, 0.03])
    m = (ph < 0.5).astype(np.float32); m = blur(m, 0.7)
    wear = np.clip((fbm(N, h, 40, 3, rs, 4, 0.6) - 0.66) / 0.08, 0, 1) * 0.6
    col = yel * m[..., None] + blk * (1 - m[..., None])
    col = col * (1 - wear[..., None]) + np.array([0.35, 0.33, 0.30]) * wear[..., None]
    edge = np.clip(1 - np.minimum(t, 1 - t) / 0.06, 0, 1)
    col *= (1 - 0.3 * edge[..., None])
    img[r0:r1] = np.clip(col, 0, 1)
    rough[r0:r1] = 0.55
    # diamond plate
    r0, r1, xs, t, h = strip_coords('diamond')
    p = 32.0
    a1 = ((xs + t * h) % p) / p - 0.5; a2 = ((xs - t * h) % p) / p - 0.5
    cell = (np.floor((xs + t * h) / p) + np.floor((xs - t * h) / p)) % 2
    bump = np.clip(1 - (np.abs(a1) / 0.09 + np.abs(a2) / 0.32), 0, 1) * (cell == 0) + \
           np.clip(1 - (np.abs(a2) / 0.09 + np.abs(a1) / 0.32), 0, 1) * (cell == 1)
    L = 0.82 + 0.15 * bump + 0.05 * (fbm(N, h, 20, 2, rs, 3) - 0.5)
    img[r0:r1] = np.clip(np.stack([L, L, L], -1), 0, 1) ** 2.2
    hh[r0:r1] = bump; rough[r0:r1] = 0.45 - 0.1 * bump
    save_png(img, os.path.join(out, 'basemap', 'T_Trim_Structures_BaseMap_2K.png'))
    if pbr:
        save_png(normal_from_height(hh, 4.0), os.path.join(out, 'pbr_extra', 'T_Trim_Structures_Normal_2K.png'), False)
        save_png(rough, os.path.join(out, 'pbr_extra', 'T_Trim_Structures_Roughness_2K.png'), False)
        save_png(ao_from_height(hh, 4, 1.5), os.path.join(out, 'pbr_extra', 'T_Trim_Structures_AO_2K.png'), False)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--only', default='')
    ap.add_argument('--no-pbr', action='store_true')
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(a.out, 'basemap'), exist_ok=True); os.makedirs(os.path.join(a.out, 'pbr_extra'), exist_ok=True)
    only = set(x for x in a.only.split(',') if x)
    for nm, fn in (('ground', gen_ground), ('road', gen_road), ('rock', gen_rock), ('trim', gen_trim)):
        if not only or nm in only:
            fn(a.out, not a.no_pbr)
