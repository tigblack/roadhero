"""Toxic Wetlands textures: calm stylized detail maps (tileable, low noise), written as 8-bit sRGB PNG.

    python3 tw_tex.py <out_dir>          (numpy only; Blender's bundled python3.13 works)

Like the v13 Dust Flats maps these are mostly near-white detail multiplied by vertex colours in RoadGame/Toon.
Rust, moss, hazard stripes, toxic drips, labels, tyre tread and mud splats carry their own colour.
All noise is periodic (filtered white noise in the Fourier domain), so every map tiles without seams.
"""
import math
import os
import struct
import sys
import zlib

import numpy as np

# ------------------------------------------------------------------------------------------------ png io

def save_png(path, img):
    """img: float array (h, w, 3|4) in 0..1, row 0 = top of the image."""
    img = np.clip(img, 0.0, 1.0)
    h, w, c = img.shape
    data = (img * 255.0 + 0.5).astype(np.uint8)
    raw = b''.join(b'\x00' + data[y].tobytes() for y in range(h))
    ctype = 6 if c == 4 else 2

    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


# ------------------------------------------------------------------------------------------------ noise

def noise(h, w, fmin, fmax, beta=2.0, seed=0, aniso=(1.0, 1.0)):
    """Periodic band-limited noise in [-1, 1]. fmin/fmax in cycles per image; aniso stretches (x, y) frequencies."""
    rng = np.random.default_rng(seed)
    wn = rng.standard_normal((h, w))
    F = np.fft.rfft2(wn)
    fy = np.fft.fftfreq(h)[:, None] * h * aniso[1]
    fx = np.fft.rfftfreq(w)[None, :] * w * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    amp = np.where(f > 0, (np.maximum(f, 1e-6)) ** (-beta / 2.0), 0.0)
    band = np.clip((f - fmin) / max(fmin * 0.5, 1e-6), 0, 1) * np.clip((fmax - f) / max(fmax * 0.25, 1e-6), 0, 1)
    n = np.fft.irfft2(F * amp * band, s=(h, w))
    n -= n.mean()
    s = np.abs(n).max() + 1e-9
    return n / s


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blur(img, sigma):
    """Periodic gaussian blur (FFT)."""
    h, w = img.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2 * (math.pi ** 2) * (sigma ** 2) * (fx * fx + fy * fy))
    if img.ndim == 2:
        return np.fft.irfft2(np.fft.rfft2(img) * g, s=(h, w))
    return np.stack([np.fft.irfft2(np.fft.rfft2(img[..., k]) * g, s=(h, w)) for k in range(img.shape[2])], -1)


def disc_mask(h, w, pts, radii, soft=1.5, wrap=True):
    """Union of soft discs (periodic)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.zeros((h, w), np.float32)
    for (cx, cy), r in zip(pts, radii):
        x0, x1 = int(cx - r - 3), int(cx + r + 4)
        y0, y1 = int(cy - r - 3), int(cy + r + 4)
        xs = np.arange(x0, x1) % w if wrap else np.arange(max(0, x0), min(w, x1))
        ys = np.arange(y0, y1) % h if wrap else np.arange(max(0, y0), min(h, y1))
        dx = (np.arange(x0, x1) - cx)[None, :] if wrap else (xs - cx)[None, :]
        dy = (np.arange(y0, y1) - cy)[:, None] if wrap else (ys - cy)[:, None]
        d = np.sqrt(dx * dx + dy * dy)
        v = np.clip((r - d) / soft + 0.5, 0, 1)
        sub = m[np.ix_(ys, xs)]
        m[np.ix_(ys, xs)] = np.maximum(sub, v)
    return m


def rgb(c):
    return np.array(c, np.float32)[None, None, :]


def lerp(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a + (b - a) * t


# ------------------------------------------------------------------------------------------------ maps

def ground(n=2048):
    """World-projected mud (36 m per tile): soft mottling, moss clumps, darker wet patches, a few pebbles."""
    L1 = noise(n, n, 2, 26, 3.0, 11)
    L2 = noise(n, n, 26, 180, 2.0, 12)
    L3 = noise(n, n, 180, 700, 1.0, 13)
    lum = 0.935 + 0.045 * L1 + 0.022 * L2 + 0.010 * L3
    img = np.repeat(lum[..., None], 3, -1)
    moss = sstep(0.18, 0.55, noise(n, n, 5, 70, 2.6, 14) + 0.25 * L2)
    img = lerp(img, img * rgb((0.90, 1.0, 0.80)), moss * 0.85)
    wet = sstep(0.35, 0.75, noise(n, n, 4, 50, 2.8, 15))
    img = lerp(img, img * rgb((0.84, 0.87, 0.84)), wet * 0.8)
    rng = np.random.default_rng(16)
    k = 420
    pts = rng.random((k, 2)) * n
    rad = 2.0 + rng.random(k) ** 2 * 5.0
    peb = disc_mask(n, n, pts, rad, 1.2)
    hi = disc_mask(n, n, pts - rad[:, None] * np.array([[0.25, 0.3]]), rad * 0.55, 1.2)
    img = lerp(img, img * rgb((0.80, 0.80, 0.76)), peb * 0.7)
    img = lerp(img, img * rgb((1.04, 1.04, 1.0)), hi * peb * 0.6)
    return img


def rock(n=1024):
    L1 = noise(n, n, 2, 20, 3.0, 21)
    L2 = noise(n, n, 20, 160, 2.0, 22)
    lum = 0.92 + 0.06 * L1 + 0.03 * L2
    pits = sstep(0.55, 0.8, noise(n, n, 30, 200, 1.6, 23))
    lum = lum - pits * 0.08
    img = np.repeat(lum[..., None], 3, -1)
    lich = sstep(0.4, 0.7, noise(n, n, 6, 60, 2.4, 24))
    return lerp(img, img * rgb((0.94, 1.0, 0.86)), lich * 0.6)


def organic(n=1024):
    """Bark / reed fibres running along v (vertical), mottling, a few dark cracks."""
    fib = noise(n, n, 8, 400, 1.2, 31, aniso=(1.0, 0.08))
    mott = noise(n, n, 2, 24, 3.0, 32)
    lum = 0.90 + 0.06 * fib + 0.04 * mott
    cr = sstep(0.82, 0.95, np.abs(noise(n, n, 10, 120, 1.4, 33, aniso=(1.0, 0.15))))
    lum -= cr * 0.18
    img = np.repeat(lum[..., None], 3, -1)
    moss = sstep(0.35, 0.7, noise(n, n, 4, 50, 2.5, 34))
    return lerp(img, img * rgb((0.88, 1.0, 0.78)), moss * 0.5)


# ---- trim strips (each 128 px tall, tileable along u) ----------------------------------------------------

def _band(w, h=128):
    return np.ones((h, w, 3), np.float32)


def strip_plain(w, seed):
    b = _band(w)
    return b * (0.965 + 0.02 * noise(128, w, 2, 40, 2.5, seed))[..., None]


def strip_metal(w, seed):
    """Painted metal: soft mottle, chipped spots, darker streaks running down from the top edge."""
    b = strip_plain(w, seed)
    chips = sstep(0.62, 0.78, noise(128, w, 12, 220, 1.6, seed + 1))
    b = lerp(b, b * rgb((0.62, 0.48, 0.38)), chips * 0.75)
    streak = np.clip(noise(128, w, 30, 400, 1.2, seed + 2, aniso=(1.0, 0.03)), 0, 1)
    vv = np.linspace(1.0, 0.0, 128)[:, None]
    b = lerp(b, b * rgb((0.80, 0.70, 0.60)), (streak * vv ** 1.5) * 0.6)
    edge = sstep(0.88, 1.0, np.abs(np.linspace(-1, 1, 128)))[:, None]
    return lerp(b, b * rgb((0.82, 0.78, 0.74)), edge * np.ones((1, w)) * 0.6)


def strip_rust(w, seed):
    base = rgb((0.56, 0.31, 0.17))
    n1 = noise(128, w, 4, 80, 2.3, seed)
    n2 = noise(128, w, 60, 500, 1.3, seed + 1)
    b = base * (1.0 + 0.16 * n1[..., None] + 0.07 * n2[..., None])
    dark = sstep(0.35, 0.7, noise(128, w, 10, 150, 1.8, seed + 2))
    b = lerp(b, rgb((0.30, 0.16, 0.09)), dark * 0.7)
    fleck = sstep(0.7, 0.85, noise(128, w, 80, 600, 1.0, seed + 3))
    return lerp(b, rgb((0.78, 0.48, 0.25)), fleck * 0.5)


def strip_panel(w, seed):
    b = strip_metal(w, seed)
    xs = np.arange(w)
    seam = np.zeros(w, np.float32)
    period = 256
    d = np.minimum(xs % period, period - xs % period)
    seam = np.where(d < 2, 0.55, np.where(d < 4, 1.08, 1.0))
    b = b * seam[None, :, None]
    rows = [14, 114]
    pts, rad = [], []
    for x in range(0, w, period):
        for dxs in (-10, 10):
            for y in rows + [64]:
                pts.append((x + dxs, y)); rad.append(3.2)
    m = disc_mask(128, w, pts, rad, 1.0)
    hi = disc_mask(128, w, [(px - 1.0, py - 1.0) for px, py in pts], [1.6] * len(pts), 1.0)
    b = lerp(b, b * 0.62, m * 0.8)
    return lerp(b, b * 1.25, hi * 0.8)


def strip_corrugated(w, seed):
    xs = np.arange(w) / 32.0 * 2 * math.pi
    ridge = 0.86 + 0.14 * (0.5 + 0.5 * np.sin(xs))
    b = _band(w) * ridge[None, :, None]
    b *= (0.97 + 0.02 * noise(128, w, 2, 30, 2.5, seed))[..., None]
    rust = np.clip(noise(128, w, 20, 300, 1.2, seed + 1, aniso=(1.0, 0.05)), 0, 1)
    vv = np.linspace(0.0, 1.0, 128)[:, None] ** 2.0
    return lerp(b, b * rgb((0.62, 0.40, 0.26)), rust * vv * 0.9)


def strip_plank(w, seed):
    """Two boards per strip height; grain along u, knots, a dark gap and nail heads near board ends."""
    h = 128
    grain = noise(h, w, 10, 900, 1.1, seed, aniso=(0.04, 1.0))
    b = (0.90 + 0.07 * grain)[..., None] * np.ones((1, 1, 3), np.float32)
    mott = noise(h, w, 2, 30, 2.6, seed + 1)
    b *= (1.0 + 0.04 * mott)[..., None]
    yy = np.arange(h)
    gap = (np.abs(yy - 64) < 2) | (yy < 2) | (yy > h - 3)
    b[gap] *= 0.55
    rng = np.random.default_rng(seed)
    kp = [(rng.random() * w, 20 + rng.random() * 88) for _ in range(w // 300)]
    km = disc_mask(h, w, kp, [6 + rng.random() * 5 for _ in kp], 2.5)
    b = lerp(b, b * 0.72, km)
    nails = []
    for x in range(64, w, 512):
        for y in (22, 42, 86, 106):
            nails.append((x, y))
    nm = disc_mask(h, w, nails, [3.0] * len(nails), 1.0)
    b = lerp(b, rgb((0.35, 0.33, 0.31)), nm * 0.9)
    wet = np.linspace(0.0, 1.0, h)[:, None] ** 3
    return lerp(b, b * rgb((0.80, 0.82, 0.78)), wet * 0.6)


def strip_concrete(w, seed):
    b = _band(w) * (0.94 + 0.04 * noise(128, w, 3, 60, 2.4, seed) + 0.02 * noise(128, w, 60, 500, 1.2, seed + 1))[..., None]
    pits = sstep(0.7, 0.86, noise(128, w, 60, 500, 1.3, seed + 2))
    b = lerp(b, b * 0.82, pits * 0.6)
    vv = np.linspace(0.0, 1.0, 128)[:, None]       # row 0 = top of band; bottom rows = waterline
    algae = sstep(0.55, 1.0, vv + 0.25 * noise(128, w, 6, 80, 2.0, seed + 3))
    b = lerp(b, b * rgb((0.66, 0.74, 0.52)), algae * 0.85)
    streak = np.clip(noise(128, w, 30, 500, 1.2, seed + 4, aniso=(1.0, 0.04)), 0, 1)
    return lerp(b, b * rgb((0.78, 0.76, 0.70)), streak * (1 - vv) * 0.5)


def strip_hazard(w, seed):
    h = 128
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    s = ((xx + yy) / 128.0) % 1.0
    m = sstep(0.47, 0.53, s) * (1 - sstep(0.97, 1.0, s)) + (1 - sstep(0.0, 0.03, s)) * 0.0
    yellow = rgb((0.91, 0.72, 0.16))
    black = rgb((0.13, 0.12, 0.11))
    b = lerp(yellow, black, m)
    wear = sstep(0.62, 0.8, noise(h, w, 10, 260, 1.6, seed))
    b = lerp(b, rgb((0.52, 0.50, 0.46)), wear * 0.75)
    return b * (0.96 + 0.04 * noise(h, w, 2, 40, 2.5, seed + 1))[..., None]


def strip_drips(w, seed):
    """Toxic green drips running down from the top edge (v = 1) over a near-white base."""
    h = 128
    b = strip_plain(w, seed)
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.zeros((h, w), np.float32)
    for i in range(w // 26):
        cx = rng.random() * w
        L = 30 + rng.random() * 90
        wd = 3 + rng.random() * 6
        dx = np.minimum(np.abs(xx - cx), w - np.abs(xx - cx))
        body = (dx < wd * (1.0 - 0.3 * (yy / max(L, 1)))) & (yy < L)
        m = np.maximum(m, body.astype(np.float32))
        m = np.maximum(m, disc_mask(h, w, [(cx, L)], [wd * 1.3], 1.5))
    m = np.clip(blur(m, 1.0), 0, 1)
    goo = rgb((0.62, 0.78, 0.22))
    b = lerp(b, goo * (0.9 + 0.1 * noise(h, w, 10, 200, 1.5, seed + 3))[..., None], m)
    stain = sstep(0.0, 0.6, 1 - yy / h) * 0.25
    return lerp(b, b * rgb((0.80, 0.86, 0.62)), stain)


def strip_moss(w, seed):
    base = rgb((0.50, 0.58, 0.27))
    n1 = noise(128, w, 4, 100, 2.2, seed)
    n2 = noise(128, w, 80, 700, 1.0, seed + 1)
    b = base * (1.0 + 0.18 * n1[..., None] + 0.08 * n2[..., None])
    light = sstep(0.4, 0.75, noise(128, w, 10, 160, 1.8, seed + 2))
    return lerp(b, rgb((0.66, 0.72, 0.34)), light * 0.6)


def strip_label(w, seed):
    """Yellow warning diamonds with a black drop on a light panel; 128 px squares along u."""
    h = 128
    b = strip_plain(w, seed) * rgb((0.93, 0.92, 0.88))
    yy, xx = np.mgrid[0:h, 0:128].astype(np.float32)
    cx, cy = 64.0, 64.0
    dia = (np.abs(xx - cx) + np.abs(yy - cy))
    tile = np.ones((h, 128, 3), np.float32) * rgb((0.93, 0.92, 0.88))
    border = sstep(56, 54, dia)
    inner = sstep(50, 48, dia)
    tile = lerp(tile, rgb((0.12, 0.11, 0.10)), border)
    tile = lerp(tile, rgb((0.93, 0.74, 0.14)), inner)
    # drop: circle + triangle top
    dy = yy - (cy + 8)
    r = np.sqrt((xx - cx) ** 2 + dy ** 2)
    drop = (r < 15) | ((yy < cy + 8) & (yy > cy - 26) & (np.abs(xx - cx) < (yy - (cy - 26)) * 15 / 34))
    tile = lerp(tile, rgb((0.10, 0.10, 0.09)), drop.astype(np.float32))
    reps = int(math.ceil(w / 128))
    full = np.concatenate([tile] * reps, axis=1)[:, :w]
    wear = sstep(0.6, 0.8, noise(h, w, 10, 220, 1.6, seed))
    return lerp(full, full * rgb((0.75, 0.68, 0.60)), wear * 0.6)


def strip_grate(w, seed):
    h = 128
    b = strip_metal(w, seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    slot = (np.abs(((xx % 32) - 16)) < 5) & (np.abs(yy - 64) < 50)
    return lerp(b, rgb((0.10, 0.10, 0.09)), slot.astype(np.float32) * 0.9)


def strip_bark(w, seed):
    fib = noise(128, w, 30, 900, 1.0, seed, aniso=(0.03, 1.0))
    b = (0.88 + 0.08 * fib)[..., None] * np.ones((1, 1, 3), np.float32)
    cr = sstep(0.8, 0.95, np.abs(noise(128, w, 40, 400, 1.2, seed + 1, aniso=(0.06, 1.0))))
    return lerp(b, b * 0.7, cr)


def strip_mud(w, seed):
    h = 128
    b = strip_plain(w, seed)
    rng = np.random.default_rng(seed)
    pts = [(rng.random() * w, rng.random() ** 0.6 * h) for _ in range(w // 10)]
    rad = [2 + rng.random() ** 2 * 14 for _ in pts]
    m = disc_mask(h, w, pts, rad, 2.0)
    vv = np.linspace(0.0, 1.0, h)[:, None]
    m = np.maximum(m, sstep(0.55, 1.0, vv + 0.2 * noise(h, w, 8, 120, 2.0, seed + 1)))
    mud = rgb((0.42, 0.36, 0.24)) * (1 + 0.12 * noise(h, w, 10, 200, 1.6, seed + 2))[..., None]
    return lerp(b, mud, m * 0.95)


def strip_canvas(w, seed):
    h = 128
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    weave = 0.96 + 0.025 * np.sin(xx * 2.2) * np.sin(yy * 2.2)
    b = _band(w) * weave[..., None]
    b *= (0.95 + 0.05 * noise(h, w, 2, 40, 2.4, seed))[..., None]
    seam = (np.abs(yy - 12) < 1.2) | (np.abs(yy - 116) < 1.2)
    stitch = seam & ((xx % 12) < 6)
    b[stitch] *= 0.7
    stain = sstep(0.45, 0.8, noise(h, w, 4, 50, 2.4, seed + 1))
    return lerp(b, b * rgb((0.80, 0.80, 0.68)), stain * 0.6)


def strip_tire(w, seed):
    h = 128
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.abs(yy - 64) / 64.0
    chevron = ((xx + v * 40) % 64) < 26
    b = np.ones((h, w, 3), np.float32) * 0.80
    b[chevron & (v < 0.85)] = 1.0
    groove = (np.abs(yy - 64) < 3)
    b[groove] = 0.6
    return b * (0.96 + 0.04 * noise(h, w, 4, 80, 2.0, seed))[..., None]


TRIM_FUNCS = {
    'plain': strip_plain, 'metal': strip_metal, 'rust': strip_rust, 'panel': strip_panel,
    'corrugated': strip_corrugated, 'plank': strip_plank, 'concrete': strip_concrete, 'hazard': strip_hazard,
    'drips': strip_drips, 'moss': strip_moss, 'label': strip_label, 'grate': strip_grate, 'bark': strip_bark,
    'mud': strip_mud, 'canvas': strip_canvas, 'tire': strip_tire,
}
TRIM_ORDER = ['plain', 'metal', 'rust', 'panel', 'corrugated', 'plank', 'concrete', 'hazard',
              'drips', 'moss', 'label', 'grate', 'bark', 'mud', 'canvas', 'tire']


def trim(w=2048):
    bands = [TRIM_FUNCS[k](w, 100 + i * 7) for i, k in enumerate(TRIM_ORDER)]
    return np.concatenate(bands, axis=0)


# ---- character strips -----------------------------------------------------------------------------------

def strip_rubber(w, seed):
    h = 128
    b = _band(w) * (0.95 + 0.03 * noise(h, w, 2, 30, 2.5, seed))[..., None]
    wr = noise(h, w, 20, 200, 1.6, seed + 1, aniso=(0.25, 1.0))
    b *= (1.0 + 0.035 * wr)[..., None]
    sheen = sstep(0.55, 0.8, noise(h, w, 4, 40, 2.4, seed + 2))
    return lerp(b, b * 1.04, sheen * 0.6)


def strip_leather(w, seed):
    h = 128
    b = _band(w) * (0.93 + 0.04 * noise(h, w, 3, 50, 2.3, seed) + 0.02 * noise(h, w, 100, 600, 1.0, seed + 1))[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    stitch = ((np.abs(yy - 10) < 1.3) | (np.abs(yy - 118) < 1.3)) & ((xx % 10) < 5)
    b[stitch] *= 0.72
    return b


def strip_tape(w, seed):
    h = 128
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    s = ((xx + yy) / 64.0) % 1.0
    m = sstep(0.46, 0.54, s)
    b = lerp(rgb((0.92, 0.74, 0.18)), rgb((0.14, 0.13, 0.12)), m)
    wear = sstep(0.65, 0.82, noise(h, w, 10, 200, 1.5, seed))
    return lerp(b, rgb((0.55, 0.52, 0.46)), wear * 0.6)


CHAR_FUNCS = {'plain': strip_plain, 'rubber': strip_rubber, 'canvas': strip_canvas, 'leather': strip_leather,
              'metal': strip_metal, 'rust': strip_rust, 'hazard': strip_tape, 'drips': strip_drips}
CHAR_ORDER = ['plain', 'rubber', 'canvas', 'leather', 'metal', 'rust', 'hazard', 'drips']


def character(w=1024):
    return np.concatenate([CHAR_FUNCS[k](w, 300 + i * 11) for i, k in enumerate(CHAR_ORDER)], axis=0)


# ---- road -----------------------------------------------------------------------------------------------

def road(w=1024, h=2048):
    """u across the road (0..1), v along it (tiling 0.5 -> 2 v units per image, ~30 m). Dark wet asphalt with
    moss in the cracks, mud tongues from the shoulders, puddles, faded centre dashes and edge lines."""
    xx = np.linspace(0, 1, w)[None, :]
    yy = np.arange(h)[:, None] / h
    asph = 0.41 + 0.04 * noise(h, w, 3, 60, 2.4, 41) + 0.025 * noise(h, w, 60, 600, 1.2, 42)
    img = np.repeat(asph[..., None], 3, -1) * rgb((1.0, 1.0, 0.98))
    # shoulders: mud (olive brown) with eroded edge
    edge_n = 0.03 * noise(h, w, 8, 120, 2.0, 43)
    dist = np.minimum(xx, 1 - xx) + edge_n
    shoulder = 1.0 - sstep(0.065, 0.11, dist)
    mud = rgb((0.40, 0.38, 0.26)) * (1 + 0.1 * noise(h, w, 6, 120, 2.0, 44))[..., None]
    img = lerp(img, mud, shoulder)
    # edge lines (faded cream) and centre dashes (faded yellow)
    line = sstep(0.006, 0.0, np.abs(dist - 0.14)) * (0.55 + 0.45 * sstep(-0.2, 0.4, noise(h, w, 6, 100, 2.0, 45)))
    img = lerp(img, rgb((0.70, 0.68, 0.58)), line * 0.6)
    dash = (np.abs(xx - 0.5) < 0.012) & (((yy * 8.0) % 1.0) < 0.42)
    dfade = 0.5 + 0.5 * sstep(-0.3, 0.5, noise(h, w, 6, 80, 2.0, 46))
    img = lerp(img, rgb((0.86, 0.70, 0.30)), dash.astype(np.float32) * dfade * 0.85)
    # cracks with moss
    cr = sstep(0.86, 0.97, np.abs(noise(h, w, 14, 220, 1.3, 47)))
    cr *= sstep(0.1, 0.18, dist)
    img = lerp(img, rgb((0.34, 0.40, 0.20)), cr * 0.8)
    # mud tongues and puddles
    tongue = sstep(0.55, 0.8, noise(h, w, 4, 50, 2.4, 48)) * (1 - sstep(0.12, 0.3, dist))
    img = lerp(img, mud * 0.9, tongue * 0.85)
    pud = sstep(0.62, 0.78, noise(h, w, 5, 60, 2.6, 49)) * sstep(0.12, 0.2, dist)
    img = lerp(img, img * rgb((0.55, 0.60, 0.56)), pud * 0.8)
    return img


def water_scum(n=512):
    """Unused by Unity's swamp water shader (procedural); kept for the Blender preview of floating algae."""
    a = sstep(0.3, 0.6, noise(n, n, 3, 40, 2.6, 51))
    return np.repeat(a[..., None], 3, -1)


def main(out):
    os.makedirs(out, exist_ok=True)
    jobs = [
        ('T_Ground_Wetlands_BaseMap_2K.png', ground),
        ('T_Rock_Wetlands_BaseMap_1K.png', rock),
        ('T_Organic_Wetlands_BaseMap_1K.png', organic),
        ('T_Trim_Wetlands_BaseMap_2K.png', trim),
        ('T_Character_Wetlands_BaseMap_1K.png', character),
        ('T_Road_Wetlands_BaseMap_1Kx2K.png', road),
    ]
    for name, fn in jobs:
        img = fn()
        # rows are generated top-down already; strips are listed top -> bottom in the atlas
        save_png(os.path.join(out, name), img.astype(np.float32))
        print('TEX', name, img.shape, flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'textures'))
