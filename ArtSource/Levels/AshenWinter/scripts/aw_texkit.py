"""Ashen Winter: procedural texture strips shared by the enemy atlas and the level atlases (numpy only).

Like every RoadGame/Toon map, most strips are calm, near-white detail multiplied by the vertex colour (concrete
cracks and pores, ash grain, feather vanes, twisted cable strands, snow sparkle). Rust and the worn orange / black
hazard paint carry their own colour. Every strip tiles along u (periodic noise); strips are rendered at twice the
target size and box-filtered down. Reuses the noise toolkit of the Toxic Wetlands pass (tw_tex.py).
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TW = os.path.abspath(os.path.join(HERE, '..', '..', 'ToxicWetlands', 'scripts'))
if TW not in sys.path:
    sys.path.insert(0, TW)
from tw_tex import (blur, disc_mask, lerp, noise, rgb, save_png, sstep, strip_metal, strip_panel,  # noqa: E402,F401
                    strip_plain, strip_rust)

H = 128


def one(w, h=H):
    return np.ones((h, w, 3), np.float32)


def ridges(w, fmin, fmax, beta, seed, width, aniso=(1.0, 1.0), h=H):
    """Thin dark lines where periodic noise crosses zero (cracks, veins)."""
    n = noise(h, w, fmin, fmax, beta, seed, aniso)
    return np.clip(1.0 - np.abs(n) / width, 0.0, 1.0) ** 2


def concrete(w, seed, h=H):
    """Light weathered concrete: soft mottle, pores, hairline cracks, a few chipped spots, rain streaks."""
    b = one(w, h) * (0.93 + 0.05 * noise(h, w, 3, 60, 2.4, seed) + 0.02 * noise(h, w, 60, 500, 1.2, seed + 1))[..., None]
    rng = np.random.default_rng(seed)
    pts = [(rng.random() * w, rng.random() * h) for _ in range(w // 2)]
    pores = disc_mask(h, w, pts, [0.6 + rng.random() * 1.1 for _ in pts], 0.8)
    b = lerp(b, b * 0.80, pores * 0.55)
    cr = ridges(w, 4, 50, 1.7, seed + 2, 0.035, h=h)
    b = lerp(b, b * 0.58, cr * 0.8)
    chips = sstep(0.72, 0.86, noise(h, w, 10, 160, 1.6, seed + 3))
    b = lerp(b, b * 0.86, chips * 0.6)
    streak = np.clip(noise(h, w, 30, 500, 1.2, seed + 4, aniso=(1.0, 0.04)), 0, 1)
    vv = np.linspace(0.0, 1.0, h)[:, None]
    return lerp(b, b * rgb((0.86, 0.86, 0.84)), streak * (1 - vv) * 0.4)


def ash(w, seed, h=H):
    """Charred surface: dark cracks of a burnt crust, pale ash flecks."""
    b = one(w, h) * (0.92 + 0.07 * noise(h, w, 4, 90, 2.0, seed))[..., None]
    cr = ridges(w, 6, 70, 1.6, seed + 1, 0.05, h=h)
    b = lerp(b, b * 0.55, cr * 0.85)
    fl = sstep(0.62, 0.8, noise(h, w, 60, 600, 1.0, seed + 2))
    return lerp(b, b * 1.35, fl * 0.7)


def feather(w, seed, h=H):
    """Feather vanes: a shaft along v = 0.5, barbs slanting away from it, ragged dark tips toward the edges."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = (yy - h * 0.5) / (h * 0.5)
    barb = 0.5 + 0.5 * np.cos((xx * 0.9 + np.abs(v) * 34.0 + 3.0 * noise(h, w, 2, 20, 2.0, seed)) * (2 * np.pi / 9.0))
    b = one(w, h) * (0.82 + 0.18 * barb)[..., None]
    shaft = np.clip(1.0 - np.abs(v) / 0.06, 0, 1)
    b = lerp(b, b * 1.12, shaft * 0.7)
    rag = sstep(0.55, 0.95, np.abs(v) + 0.25 * noise(h, w, 8, 80, 1.6, seed + 1))
    return lerp(b, b * 0.62, rag * 0.6)


def hide(w, seed, h=H):
    """Dark leathery hide with fine wrinkles and a few scars."""
    b = one(w, h) * (0.92 + 0.05 * noise(h, w, 2, 40, 2.4, seed))[..., None]
    wr = ridges(w, 10, 120, 1.5, seed + 1, 0.04, aniso=(1.0, 0.45), h=h)
    b = lerp(b, b * 0.70, wr * 0.7)
    sc = ridges(w, 2, 12, 2.2, seed + 2, 0.02, h=h)
    return lerp(b, b * 1.2, sc * 0.5)


def cable(w, seed, h=H):
    """Twisted cable / sinew strands: helical grooves slanting across the strip, glossy ridges between them."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ph = (xx * 1.0 + yy * 1.6 + 6.0 * noise(h, w, 2, 16, 2.2, seed)) * (2 * np.pi / 22.0)
    s = 0.5 + 0.5 * np.cos(ph)
    b = one(w, h) * (0.62 + 0.38 * s ** 0.6)[..., None]
    fib = noise(h, w, 30, 500, 1.0, seed + 1, aniso=(1.0, 0.25))
    return b * (1.0 + 0.06 * fib)[..., None]


def snow(w, seed, h=H):
    """Soft snow: gentle mottle, bluish hollows, a few bright sparkles."""
    b = one(w, h) * (0.95 + 0.04 * noise(h, w, 2, 30, 2.6, seed))[..., None]
    hol = sstep(0.3, 0.8, noise(h, w, 4, 60, 2.2, seed + 1))
    b = lerp(b, b * rgb((0.86, 0.89, 0.95)), hol * 0.6)
    rng = np.random.default_rng(seed + 2)
    pts = [(rng.random() * w, rng.random() * h) for _ in range(w // 6)]
    sp = disc_mask(h, w, pts, [0.6 + rng.random() * 0.8 for _ in pts], 0.6)
    return lerp(b, b * 1.06, sp)


def hazard(w, seed, h=H, period=96.0):
    """Worn orange / black diagonal stripes (own colour); paint chipped to bare grey metal here and there."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    s = ((xx + yy) / period) % 1.0
    m = sstep(0.47, 0.53, s) * (1 - sstep(0.97, 1.0, s))
    orange = rgb((0.86, 0.47, 0.14))
    black = rgb((0.11, 0.10, 0.10))
    b = lerp(orange, black, m)
    wear = sstep(0.6, 0.8, noise(h, w, 10, 260, 1.6, seed))
    b = lerp(b, rgb((0.42, 0.40, 0.38)), wear * 0.7)
    dirt = sstep(0.4, 0.9, noise(h, w, 3, 40, 2.2, seed + 1))
    b = lerp(b, b * 0.72, dirt * 0.5)
    return b * (0.96 + 0.04 * noise(h, w, 2, 40, 2.5, seed + 2))[..., None]


def tread(w, seed, h=H, period=32):
    """Track tread: cleats across the belt every period px (u runs along the belt), a centre guide groove."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.abs(yy - h * 0.5) / (h * 0.5)
    cleat = (xx % period) < period * 0.42
    b = np.ones((h, w, 3), np.float32) * 0.70
    b[cleat] = 1.0
    b[(v < 0.12)] *= 0.8
    edge = v > 0.9
    b[edge] = 0.6
    return b * (0.95 + 0.05 * noise(h, w, 4, 80, 2.0, seed))[..., None]


def cloth(w, seed, h=H):
    """Coarse canvas / fur lining: weave, seams, stains."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    weave = 0.95 + 0.035 * np.sin(xx * 2.0) * np.sin(yy * 2.0)
    b = one(w, h) * weave[..., None]
    fur = noise(h, w, 40, 600, 1.0, seed, aniso=(0.3, 1.0))
    b *= (0.96 + 0.05 * fur)[..., None]
    stain = sstep(0.45, 0.8, noise(h, w, 4, 50, 2.4, seed + 1))
    return lerp(b, b * rgb((0.80, 0.78, 0.70)), stain * 0.5)


def bone(w, seed, h=H):
    b = one(w, h) * (0.94 + 0.04 * noise(h, w, 2, 40, 2.4, seed))[..., None]
    cr = ridges(w, 8, 80, 1.6, seed + 1, 0.03, aniso=(0.3, 1.0), h=h)
    b = lerp(b, b * 0.7, cr * 0.6)
    stain = sstep(0.5, 0.85, noise(h, w, 3, 40, 2.2, seed + 2))
    return lerp(b, b * rgb((0.84, 0.82, 0.76)), stain * 0.6)


def ice(w, seed, h=H):
    """Icicles / frost: vertical streaks, bright edges."""
    st = noise(h, w, 20, 400, 1.2, seed, aniso=(1.0, 0.03))
    b = one(w, h) * (0.9 + 0.1 * st)[..., None]
    vv = np.linspace(0.0, 1.0, h)[:, None]
    return lerp(b, b * rgb((0.85, 0.92, 1.0)), (vv * np.ones((1, w))) * 0.4)


def grille(w, seed, h=H, period=24):
    """Vent / firebox grille: dark horizontal slots between light bars (slots run along u)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    slot = (yy % period) < period * 0.45
    b = one(w, h) * 0.95
    b[slot] = 0.22
    return b * (0.95 + 0.05 * noise(h, w, 3, 60, 2.0, seed))[..., None]


def plain(w, seed, h=H):
    return one(w, h) * (0.965 + 0.02 * noise(h, w, 2, 40, 2.5, seed))[..., None]


def metal(w, seed, h=H):
    return strip_metal(w, seed) if h == 128 else plain(w, seed, h)


def rust(w, seed, h=H):
    return strip_rust(w, seed) if h == 128 else plain(w, seed, h)


def panel(w, seed, h=H):
    return strip_panel(w, seed) if h == 128 else plain(w, seed, h)


FUNCS = {'plain': plain, 'concrete': concrete, 'ash': ash, 'feather': feather, 'hide': hide, 'cable': cable,
         'rust': rust, 'metal': metal, 'snow': snow, 'hazard': hazard, 'tread': tread, 'cloth': cloth,
         'bone': bone, 'ice': ice, 'grille': grille, 'panel': panel}


def atlas(order, w=2048, h=H):
    """Strips stacked top to bottom in 'order' (first = top of the image), rendered at w x h, filtered to half."""
    bands = []
    for i, k in enumerate(order):
        b = FUNCS[k](w, 700 + i * 13, h) if k not in ('metal', 'rust', 'panel') else FUNCS[k](w, 700 + i * 13)
        b = b.reshape(h // 2, 2, w // 2, 2, 3).mean(axis=(1, 3))
        bands.append(b)
    return np.concatenate(bands, axis=0)


# ---------------------------------------------------------------------------------------------- level strips
from tw_tex import strip_corrugated, strip_plank  # noqa: E402


def corrugated(w, seed, h=H):
    return strip_corrugated(w, seed) if h == 128 else plain(w, seed, h)


def plank(w, seed, h=H):
    return strip_plank(w, seed) if h == 128 else plain(w, seed, h)


def bark(w, seed, h=H):
    """Burnt bark: vertical fibres (along u = up the trunk), deep charred cracks, a few pale ash flecks."""
    fib = noise(h, w, 20, 700, 1.0, seed, aniso=(1.0, 0.05))
    b = one(w, h) * (0.86 + 0.12 * fib)[..., None]
    cr = ridges(w, 6, 90, 1.5, seed + 1, 0.05, aniso=(1.0, 0.18), h=h)
    b = lerp(b, b * 0.45, cr * 0.85)
    fl = sstep(0.7, 0.86, noise(h, w, 40, 500, 1.0, seed + 2))
    return lerp(b, b * 1.5, fl * 0.6)


def chevron(w, seed, h=H, period=128.0):
    """Ramp chevrons: yellow '>' marks on worn dark concrete (own colour); u runs up the ramp."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = np.abs(yy - h * 0.5) / (h * 0.5)
    s = ((xx + v * h * 0.55) % period) / period
    m = (s > 0.08) & (s < 0.36) & (v < 0.86)
    base = rgb((0.42, 0.42, 0.41)) * (0.92 + 0.08 * noise(h, w, 3, 60, 2.2, seed))[..., None]
    yel = rgb((0.88, 0.66, 0.18))
    b = np.where(m[..., None], yel * np.ones_like(base), base)
    wear = sstep(0.55, 0.8, noise(h, w, 12, 300, 1.4, seed + 1))
    b = lerp(b, base * 1.05, wear * m * 0.75)
    cr = ridges(w, 4, 50, 1.7, seed + 2, 0.03, h=h)
    return lerp(b, b * 0.6, cr * 0.7)


FUNCS.update({'corrugated': corrugated, 'plank': plank, 'bark': bark, 'chevron': chevron})


def atlas_raw(order, w=2048, h=H):
    """Strips stacked top to bottom at their final size (w x h each, no filtering)."""
    out = []
    for i, k in enumerate(order):
        fn = FUNCS[k]
        out.append(fn(w, 900 + i * 17) if k in ('metal', 'rust', 'panel', 'corrugated', 'plank') else fn(w, 900 + i * 17, h))
    return np.concatenate(out, axis=0)


def ground(n=2048, seed=5):
    """World-projected ground detail (36 m per tile, multiplied by the vertex colours): wind-blown snow grain, soft
    drifts of mottle, ash specks and a few dark char flecks. Calm, near white."""
    b = np.ones((n, n, 3), np.float32) * (0.93 + 0.05 * noise(n, n, 2, 40, 2.4, seed))[..., None]
    streak = noise(n, n, 6, 300, 1.4, seed + 1, aniso=(1.0, 0.25))
    b *= (1.0 + 0.04 * streak)[..., None]
    rng = np.random.default_rng(seed)
    pts = [(rng.random() * n, rng.random() * n) for _ in range(n * 2)]
    specks = disc_mask(n, n, pts, [0.6 + rng.random() * 1.4 for _ in pts], 0.7)
    b = lerp(b, b * 0.72, specks * 0.6)
    pts2 = [(rng.random() * n, rng.random() * n) for _ in range(n // 3)]
    sp2 = disc_mask(n, n, pts2, [0.8 + rng.random() * 1.0 for _ in pts2], 0.6)
    return lerp(b, b * 1.08, sp2)
