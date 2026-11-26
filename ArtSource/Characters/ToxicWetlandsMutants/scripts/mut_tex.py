"""Toxic Wetlands mutants: the creature atlas T_Mutant_Wetlands_BaseMap_1K.png (1024 x 1024, 16 strips of 64 px).

    python3 mut_tex.py <out_dir>        (numpy only; Blender's bundled python3.13 works)

Like the level's maps these are calm, mostly near-white detail multiplied by the vertex colours in RoadGame/Toon:
wet skin pores, warts, bark fibres, chitin speckles, mushroom gills and caps, veins, wet flesh, bone, moss, cracked
glass. Rust, painted metal, tyre tread and hazard stripes carry their own colour. Strips are rendered at 2048 x 128
and box-filtered to 1024 x 64; every strip tiles along u (periodic noise).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TW = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'Levels', 'ToxicWetlands', 'scripts'))
sys.path.insert(0, TW)
from tw_tex import blur, disc_mask, lerp, noise, rgb, save_png, sstep, strip_bark, strip_metal, strip_plain, strip_rust, strip_tire  # noqa: E402

H = 128
ORDER = ['plain', 'skin', 'warts', 'bark', 'chitin', 'gill', 'veins', 'rust',
         'metal', 'tire', 'bone', 'moss', 'flesh', 'cap', 'glass', 'hazard']


def one(w):
    return np.ones((H, w, 3), np.float32)


def ridges(w, fmin, fmax, beta, seed, width, aniso=(1.0, 1.0)):
    """Thin dark lines where periodic noise crosses zero (veins, cracks)."""
    n = noise(H, w, fmin, fmax, beta, seed, aniso)
    return np.clip(1.0 - np.abs(n) / width, 0.0, 1.0) ** 2


def skin(w, seed):
    b = one(w) * (0.93 + 0.05 * noise(H, w, 2, 40, 2.4, seed) + 0.02 * noise(H, w, 60, 500, 1.2, seed + 1))[..., None]
    rng = np.random.default_rng(seed)
    pts = [(rng.random() * w, rng.random() * H) for _ in range(w // 3)]
    pores = disc_mask(H, w, pts, [0.8 + rng.random() * 1.4 for _ in pts], 0.9)
    b = lerp(b, b * 0.72, pores * 0.8)
    pts2 = [(rng.random() * w, rng.random() * H) for _ in range(w // 12)]
    spk = disc_mask(H, w, pts2, [1.5 + rng.random() * 2.5 for _ in pts2], 1.4)
    return lerp(b, b * 1.12, spk * 0.6)


def warts(w, seed):
    b = skin(w, seed)
    rng = np.random.default_rng(seed + 5)
    pts = [(rng.random() * w, rng.random() * H) for _ in range(w // 9)]
    rad = [3 + rng.random() ** 1.7 * 10 for _ in pts]
    m = disc_mask(H, w, pts, rad, 2.5)
    core = disc_mask(H, w, pts, [r * 0.55 for r in rad], 2.0)
    ring = np.clip(m - core, 0, 1)
    b = lerp(b, b * 0.78, ring * 0.7)
    return lerp(b, b * 1.18, core * 0.75)


def bark(w, seed):
    b = strip_bark(w, seed)
    knots = sstep(0.75, 0.9, noise(H, w, 6, 60, 2.0, seed + 3))
    return lerp(b, b * 0.72, knots * 0.6)


def chitin(w, seed):
    b = one(w) * (0.92 + 0.05 * noise(H, w, 2, 30, 2.5, seed))[..., None]
    cracks = ridges(w, 6, 60, 1.8, seed + 1, 0.045)
    b = lerp(b, b * 0.62, cracks * 0.75)
    rng = np.random.default_rng(seed + 2)
    pts = [(rng.random() * w, rng.random() * H) for _ in range(w // 5)]
    spk = disc_mask(H, w, pts, [0.8 + rng.random() * 2.2 for _ in pts], 1.0)
    b = lerp(b, b * 1.15, spk * 0.55)
    edge = sstep(0.75, 1.0, np.abs(np.linspace(-1, 1, H)))[:, None]
    return lerp(b, b * 0.85, edge * np.ones((1, w)) * 0.5)


def gill(w, seed):
    xx = np.arange(w, dtype=np.float32)[None, :]
    wob = 3.0 * noise(H, w, 1, 8, 2.5, seed)
    lines = 0.5 + 0.5 * np.cos((xx + wob) * (2 * np.pi / 7.0))
    b = one(w) * (0.80 + 0.2 * lines)[..., None]
    vv = np.linspace(0.0, 1.0, H)[:, None]
    return b * (0.9 + 0.1 * vv)[..., None]


def veins(w, seed):
    b = one(w) * (0.96 + 0.03 * noise(H, w, 2, 30, 2.5, seed))[..., None]
    v1 = ridges(w, 4, 40, 2.0, seed + 1, 0.05)
    v2 = ridges(w, 12, 120, 1.6, seed + 2, 0.035)
    return lerp(b, b * 0.55, np.clip(v1 * 0.85 + v2 * 0.5, 0, 1))


def bone(w, seed):
    b = one(w) * (0.94 + 0.04 * noise(H, w, 2, 40, 2.4, seed))[..., None]
    cr = ridges(w, 8, 80, 1.6, seed + 1, 0.03, aniso=(0.3, 1.0))
    b = lerp(b, b * 0.7, cr * 0.6)
    stain = sstep(0.5, 0.85, noise(H, w, 3, 40, 2.2, seed + 2))
    return lerp(b, b * rgb((0.86, 0.80, 0.66)), stain * 0.7)


def moss(w, seed):
    base = one(w) * (0.9 + 0.08 * noise(H, w, 4, 80, 1.8, seed))[..., None]
    rng = np.random.default_rng(seed + 1)
    pts = [(rng.random() * w, rng.random() * H) for _ in range(w // 2)]
    m = disc_mask(H, w, pts, [1.0 + rng.random() * 2.5 for _ in pts], 1.2)
    b = lerp(base * 0.8, base * 1.12, m)
    return b


def flesh(w, seed):
    fib = noise(H, w, 20, 600, 1.0, seed, aniso=(0.05, 1.0))
    b = one(w) * (0.92 + 0.07 * fib)[..., None]
    v = ridges(w, 3, 30, 2.0, seed + 1, 0.05)
    b = lerp(b, b * rgb((0.70, 0.52, 0.58)), v * 0.6)
    gl = sstep(0.7, 0.9, noise(H, w, 20, 200, 1.4, seed + 2))
    return lerp(b, b * 1.12, gl * 0.6)


def cap(w, seed):
    b = one(w) * (0.92 + 0.05 * noise(H, w, 2, 30, 2.5, seed))[..., None]
    rng = np.random.default_rng(seed + 1)
    pts = [(rng.random() * w, rng.random() * H * 0.8 + H * 0.2) for _ in range(w // 14)]
    spots = disc_mask(H, w, pts, [2 + rng.random() * 5 for _ in pts], 1.6)
    b = lerp(b, b * rgb((1.18, 1.1, 0.95)), spots * 0.75)
    rad = noise(H, w, 30, 300, 1.2, seed + 2, aniso=(1.0, 0.08))
    return b * (1.0 + 0.04 * rad)[..., None]


def glass(w, seed):
    b = one(w) * (0.95 + 0.04 * noise(H, w, 2, 20, 2.5, seed))[..., None]
    cr = ridges(w, 3, 30, 1.4, seed + 1, 0.02)
    return lerp(b, b * 0.45, cr * 0.9)


def hazard(w, seed):
    yy, xx = np.mgrid[0:H, 0:w].astype(np.float32)
    s = ((xx + yy) % 64) < 32
    b = np.where(s[..., None], rgb((0.92, 0.70, 0.16)), rgb((0.10, 0.09, 0.08)))
    return b * (0.95 + 0.05 * noise(H, w, 4, 80, 2.0, seed))[..., None]


FUNCS = {'plain': strip_plain, 'skin': skin, 'warts': warts, 'bark': bark, 'chitin': chitin, 'gill': gill,
         'veins': veins, 'rust': strip_rust, 'metal': strip_metal, 'tire': strip_tire, 'bone': bone, 'moss': moss,
         'flesh': flesh, 'cap': cap, 'glass': glass, 'hazard': hazard}


def atlas(w=2048):
    bands = []
    for i, k in enumerate(ORDER):
        b = FUNCS[k](w, 300 + i * 11)
        b = b.reshape(H // 2, 2, w // 2, 2, 3).mean(axis=(1, 3))      # 2048x128 -> 1024x64
        bands.append(b)
    return np.concatenate(bands, axis=0)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'textures')
    os.makedirs(out, exist_ok=True)
    img = atlas()
    path = os.path.join(out, 'T_Mutant_Wetlands_BaseMap_1K.png')
    save_png(path, img)
    print('MUT_TEX', path, img.shape)
