"""The seven Ashen Winter enemies (third zone, index 2), built from code in Blender 5.2 (see aw_lib.py).

Every builder follows the concept sheet AshenWinter_Enemies_Concept_v1_2026-11-25.png:
main masses -> recognition traits -> blocking at game proportions -> profiles / joints / chips -> paint and snow.
Rigid parts sit at their joints (identity rest rotations); Unity animates them (Scripts/World/AshenEnemies.cs).
The builders model the creature's left side at +x; aw_build.py mirrors every creature afterwards (aw_lib.mirror_x),
so the ...L parts end on the creature's left and the asymmetric arms sit on the concept's sides.
Sizes are metres at the game's scale (the player's pickup is about 4.6 m long and 1.9 m tall).

  01 ASH PECKER           (Scav)          small biped bird, long S-neck, tubular beak-gun with a clamp
  02 SNOW REAPER          (Raider)        low predator on hind legs and two huge ice-pick fore blades, spiky tail
  03 NEEDLE WALKER        (Spearman)      small body on exactly three long legs, horizontal needle launcher
  04 BOILER SPITTER       (Crossbow)      low wide boiler on four short legs, tilted mortar pipe, glowing firebox
  05 CONCRETE EXECUTIONER (Brute)         slab-shouldered heavy, square-muzzle cannon arm, open claw hand
  06 WHITEOUT RAIDER      (Buggy)         snow-plough sled: two front skis, rear tracks, open rotary turret, driver
  07 BLACK REACTOR        (BossColossus)  huge biped: concrete carapace, reactor core port, fist arm and claw arm
"""
import math
import random

from mathutils import Matrix, Vector

import aw_lib as A
from aw_lib import (AAcc, C, V, T, R, ball, blob, blade, box, broken_chimney, cables, coil_spring, feather,
                    frame, gatling, horn, lathe_at, limb, mottle, pipe, prism, railing, rebar, recolor, ring,
                    ski, slab, snow_pillow, sweep, torus, track_loop, wheel, glow_eye)


def finish_paint(acc, lo=0.0, hi=0.6, k=0.35):
    """Soot toward the ground on everything (lo z, hi z, strength)."""
    recolor(acc, list(acc.bm.faces), A.soot(lo, hi, k))


def scale_xy(sx, sy):
    return Matrix.Diagonal((sx, sy, 1.0, 1.0))


def on_surface(c, normal, up=(0, 0, 1)):
    """Rotation for a plate lying on a surface: local z = the surface normal."""
    return frame(normal, Vector(up) - Vector(normal).normalized() * Vector(normal).normalized().dot(Vector(up)) + Vector((0.01, 0.0, 0.0)))


# =============================================================================================== 01 ASH PECKER (Scav)
def ash_pecker(offset=(0, 0, 0)):
    """Masses: big hunched feather body, thick S-neck, long skull-like head running into a tapered beak, a round
    rusty pipe muzzle, two long thin legs with big claws.
    Traits: a ragged feather coat that hangs below the belly and trails into a drooping tail; a dark feather mane up
    the back of the neck over bare rust-brown sinew; head far forward, the beak drooping into a flared pipe muzzle
    with a slot on top; long splayed bird legs with ring joints and big dark claws; snow on the back and the head."""
    cr = A.Creature('AW_AshPecker', '01_AshPecker (Scav)', 'Scav', offset)
    rnd = random.Random(101)

    body = AAcc('body')
    bc = V(0, -0.07, 1.01)
    hx, hy = 0.33, 0.39
    bf = blob(body, bc, (hx, hy, 0.34), C['feather'], M=R('X', -16), e=(0.8, 0.8), amp=0.035, freq=3.0, seed=3,
              segs=22, rings=14)
    recolor(body, bf, mottle(0.12, 5.0, 7))
    # feather coat: rows of pointed masses hanging down and back all round (ragged silhouette)
    pal = [C['feather'], C['feather_dk'], C['feather_lt'], C['feather']]
    for row, z in enumerate((1.27, 1.15, 1.03, 0.91, 0.80)):
        n = 13
        for k in range(n):
            az = math.radians(-165 + 330 * k / (n - 1)) + (0.08 if row % 2 else 0.0)
            if row == 0 and abs(math.degrees(az)) < 30:
                continue
            dx, dy = math.sin(az), math.cos(az)
            rr = 0.86 * (1.0 - 0.15 * abs(z - 1.03) / 0.24)
            base = V(dx * hx * rr, bc.y + dy * hy * rr, z)
            tip = base + V(dx * 0.14, dy * 0.07 - 0.10, -0.29 - 0.07 * rnd.random())
            surf = C['feather_or'] if rnd.random() < 0.16 else pal[(k + row) % 4]
            blade(body, base, tip, 0.17 + 0.04 * rnd.random(), 0.04, V(dy, -dx, 0), surf, bend=V(dx * 0.06, 0, 0.04), n=6)
    # the drooping tail: long ragged feathers trailing back and down
    for k, x in enumerate((-0.14, -0.05, 0.05, 0.14)):
        blade(body, V(x, -0.40, 0.96), V(x * 2.0, -0.86 - 0.05 * (k % 2), 0.52 + 0.04 * k), 0.17, 0.036, V(1, 0, 0),
              C['feather_or'] if k == 2 else (C['feather_dk'] if k % 2 else C['feather']), bend=V(0, 0, 0.08), n=6)
    snow_pillow(body, (0.0, -0.16, 1.33), (0.20, 0.23, 0.065), R('X', -12), seed=4)
    snow_pillow(body, (0.13, 0.08, 1.32), (0.09, 0.10, 0.035), seed=5)
    finish_paint(body, 0.55, 1.0, 0.3)
    cr.part('Body', body, (0, 0, 0.88))

    # wings: short ragged fans of big pointed feathers (parts: they flutter on hits and shots)
    for s in (1, -1):
        w = AAcc('wing')
        sh = V(0.31 * s, 0.05, 1.18)
        for k in range(5):
            tip = V(0.45 * s + 0.03 * s * k, -0.22 - 0.12 * k, 0.66 + 0.06 * k * (1 if k < 3 else -0.5))
            surf = C['feather_or'] if k in (1, 3) else (C['feather_lt'] if k % 2 else C['feather'])
            blade(w, sh + V(0.02 * s, -0.05 * k, -0.035 * k), tip, 0.20 - 0.014 * k, 0.045, V(0, 1, 0.45), surf,
                  bend=V(0.08 * s, 0.02, 0.02), n=6)
        for k in range(3):
            blade(w, sh + V(0.03 * s, 0.02 - 0.06 * k, 0.02), sh + V(0.12 * s, -0.12 - 0.07 * k, -0.22), 0.12, 0.04,
                  V(0, 1, 0.45), C['feather_dk'], n=5)
        snow_pillow(w, sh + V(0.03 * s, -0.09, 0.04), (0.06, 0.10, 0.03), seed=11 + s)
        cr.part('WingL' if s > 0 else 'WingR', w, sh, parent='Body', shadow=False)

    # neck: thick curved S of striated rust-brown sinew, a dark feather mane down its back, a ragged ruff at its base
    neck = AAcc('neck')
    npts = [V(0, 0.20, 1.17), V(0, 0.30, 1.33), V(0, 0.36, 1.46), V(0, 0.45, 1.55), V(0, 0.55, 1.59)]
    limb(neck, npts, [0.15, 0.13, 0.118, 0.11, 0.112], C['cable_br'], segs=14, per=4)
    for i in range(len(npts) - 1):
        a_, b_ = npts[i], npts[i + 1]
        tg = (b_ - a_).normalized()
        back = V(0, -tg.z, tg.y).normalized()           # the neck's back side (perpendicular, toward the tail / up)
        if back.z < 0:
            back = -back
        for j, sx in enumerate((-0.05, 0.0, 0.05)):
            p0 = a_.lerp(b_, 0.3 + 0.35 * (j % 2)) + back * 0.08 + V(sx, 0, 0)
            tip = p0 + back * 0.11 + V(sx * 1.6, -0.10, -0.05)
            blade(neck, p0, tip, 0.085, 0.026, V(1, 0, 0), C['feather_dk'] if (i + j) % 2 else C['feather'], n=5)
    for k in range(10):
        a = 2 * math.pi * k / 10
        blade(neck, V(0.11 * math.cos(a), 0.22 + 0.08 * math.sin(a), 1.27),
              V(0.21 * math.cos(a), 0.15 + 0.12 * math.sin(a), 1.06), 0.12, 0.032, V(-math.sin(a), math.cos(a), 0),
              C['feather_dk'] if k % 2 else C['feather'], n=5)
    cr.part('Neck', neck, (0, 0.20, 1.17), parent='Body')

    # head + beak: a long dark skull-like head, amber eye, the beak tapering forward into a flared rusty pipe muzzle
    head = AAcc('head')
    ball(head, (0, 0.63, 1.59), (0.15, 0.21, 0.15), C['feather_dk'], segs=16, rings=10)
    for k in range(11):
        a = math.radians(-150 + 300 * k / 10)
        base = V(0.12 * math.sin(a), 0.58 + 0.12 * math.cos(a), 1.63)
        blade(head, base, base + V(0.11 * math.sin(a), -0.14 + 0.05 * math.cos(a), 0.05 + 0.03 * (k % 2)), 0.065, 0.022,
              V(math.cos(a), -math.sin(a), 0), C['feather'] if k % 2 else C['feather_dk'], n=5)
    for k in range(7):
        x = -0.08 + 0.027 * k
        blade(head, V(x, 0.60, 1.69), V(x * 1.7, 0.38 - 0.04 * (k % 2), 1.75 + 0.03 * (k % 3)), 0.065, 0.022,
              V(1, 0, 0), C['feather_dk'] if k % 2 else C['feather'], n=5)
    snow_pillow(head, (0, 0.58, 1.71), (0.08, 0.11, 0.04), seed=21)
    for s in (1, -1):
        ball(head, (0.095 * s, 0.74, 1.62), 0.042, C['black'], segs=10, rings=7)
        glow_eye(head, (0.112 * s, 0.75, 1.625), 0.029)
    bpts = [V(0, 0.74, 1.56), V(0, 0.90, 1.51), V(0, 1.05, 1.44), V(0, 1.17, 1.38)]
    limb(head, bpts, [0.125, 0.112, 0.104, 0.10], C['ash_lt'], segs=16, per=3)
    limb(head, [V(0, 0.79, 1.49), V(0, 0.95, 1.43), V(0, 1.10, 1.375)], [0.015, 0.015, 0.013], C['black'], segs=6, per=2)
    d = (bpts[-1] - bpts[-2]).normalized()
    c0 = bpts[-1] - d * 0.10
    lathe_at(head, [(0.092, -0.02), (0.126, 0.0), (0.128, 0.20), (0.150, 0.29), (0.146, 0.33), (0.104, 0.33), (0.090, 0.02)],
             c0, d, C['rust'], segs=22, caps=(False, False), sharp=40)
    lathe_at(head, [(0.0, 0.22), (0.096, 0.22), (0.0, 0.22)], c0, d, C['bore'], segs=16, caps=(False, False))
    for t in (0.03, 0.17):
        ring(head, c0 + d * t, d, 0.136, 0.034, 0.03, C['rust_dk'], segs=20)
    up = d.cross(V(1, 0, 0)).normalized()
    if up.z < 0:
        up = -up
    box(head, c0 + d * 0.10 + up * 0.125, (0.12, 0.05, 0.03), C['bore'], M=frame(up, d), bevel=0.01)
    for k in range(3):
        p = c0 + d * (0.31 - 0.02 * k) + V(0.035 * (k - 1), 0, -0.13)
        horn(head, p, p + V(0, 0.01, -0.06 - 0.025 * k), 0.013, C['rust_dk'], segs=6, n=4)
    cr.part('Head', head, (0, 0.53, 1.58), parent='Neck')
    cr.part('Muzzle', None, c0 + d * 0.34, parent='Head')

    # legs: long thin splayed bird legs, ring joints, gripping toes with big dark claws
    for s in (1, -1):
        leg = AAcc('leg')
        hip = V(0.15 * s, -0.05, 0.86)
        ank = V(0.185 * s, -0.18, 0.45)
        limb(leg, [hip, V(0.17 * s, -0.08, 0.66), ank], [0.088, 0.06, 0.044], C['cable_dk'], segs=10, per=3)
        cr.part('LegL' if s > 0 else 'LegR', leg, hip, parent='Body')
        foot = AAcc('foot')
        limb(foot, [ank, V(0.195 * s, -0.10, 0.24), V(0.205 * s, 0.0, 0.055)], [0.044, 0.038, 0.033], C['ash_lt'], segs=8, per=3)
        ring(foot, ank, V(0, 0.2, 1), 0.056, 0.06, 0.022, C['rust_dk'], segs=12)
        ring(foot, V(0.20 * s, -0.05, 0.16), V(0, 0.3, 1), 0.046, 0.042, 0.014, C['rust_dk'], segs=12)
        toe0 = V(0.205 * s, 0.0, 0.055)
        for ang in (-34, 0, 34, 180):
            a = math.radians(ang)
            dvec = V(math.sin(a) * s if ang != 180 else 0.0, math.cos(a), 0)
            Lt = 0.23 if ang != 180 else 0.12
            p2 = toe0 + dvec * Lt + V(0, 0, -0.035)
            limb(foot, [toe0, toe0 + dvec * Lt * 0.5 + V(0, 0, -0.012), p2], [0.029, 0.023, 0.017], C['ash_lt'], segs=6, per=2)
            horn(foot, p2, p2 + dvec * 0.08 + V(0, 0, -0.035), 0.019, C['claw'], segs=6, n=4)
        cr.part('FootL' if s > 0 else 'FootR', foot, ank, parent='LegL' if s > 0 else 'LegR')
    return cr


# =============================================================================================== 02 SNOW REAPER (Raider)
def snow_reaper(offset=(0, 0, 0)):
    """Masses: hunched muscular body, two huge fore limbs ending in ice-pick blades, crouched hind legs, long tail.
    Traits: blades nearly touching the ground on both sides with a wide stance; elbows arching above the back; small
    head sunk between massive plated shoulders; arched back of bone plates running into a long spiky tail."""
    cr = A.Creature('AW_SnowReaper', '02_SnowReaper (Raider)', 'Raider', offset)

    body = AAcc('body')
    spine = [V(0, -0.82, 1.02), V(0, -0.38, 1.36), V(0, 0.06, 1.42), V(0, 0.45, 1.26), V(0, 0.66, 1.04)]
    bf = sweep(body, spine, [0.27, 0.38, 0.47, 0.44, 0.27], [0.27, 0.34, 0.38, 0.34, 0.22], C['hide'], n=20,
               p=2.2, belly=0.15, noise=(0.03, 3.0, 5), top_bulge=0.15)
    recolor(body, bf, mottle(0.18, 4.0, 3, dark='#4A2424', dark_thr=0.35, dark_k=0.4))
    for s in (1, -1):
        cables(body, V(0.30 * s, -0.58, 1.06), V(0.42 * s, 0.40, 1.22), n=3, r=0.075, R_=0.075, turns=0.6,
               surf=C['cable_dk'], seed=3 + s)
        cables(body, V(0.18 * s, 0.30, 1.40), V(0.40 * s, 0.56, 1.04), n=3, r=0.065, R_=0.055, turns=0.5,
               surf=C['cable_dk'], seed=7 + s)
        cables(body, V(0.12 * s, -0.70, 1.15), V(0.30 * s, -0.10, 1.38), n=3, r=0.06, R_=0.05, turns=0.5,
               surf=C['cable_dk'], seed=9 + s)
    # big curved bone plates stacked on each shoulder (rising above the sunk head), plus orange paint marks
    for s in (1, -1):
        blade(body, V(0.16 * s, 0.04, 1.58), V(0.80 * s, 0.74, 1.34), 0.66, 0.14, V(0.18 * s, -0.6, 0.8), C['bone'],
              bend=V(0.16 * s, 0.0, 0.30), n=9, base_k=0.9, tip_k=0.28, edge=C['concrete_lt'])
        blade(body, V(0.10 * s, -0.12, 1.66), V(0.56 * s, 0.30, 1.98), 0.50, 0.12, V(0.12 * s, -0.7, 0.75), C['bone'],
              bend=V(0.10 * s, 0.0, 0.10), n=8, base_k=0.9, tip_k=0.15)
        blade(body, V(0.12 * s, -0.36, 1.50), V(0.50 * s, 0.02, 1.60), 0.40, 0.10, V(0.1 * s, -0.8, 0.6), C['bone'],
              bend=V(0.06 * s, 0, 0.12), n=7, base_k=0.9, tip_k=0.2)
        blade(body, V(0.46 * s, 0.32, 1.44), V(0.62 * s, 0.56, 1.32), 0.14, 0.15, V(0.18 * s, -0.6, 0.8), C['rust_or'], n=4)
        blade(body, V(0.30 * s, 0.10, 1.66), V(0.40 * s, 0.30, 1.66), 0.10, 0.13, V(0.12 * s, -0.7, 0.75), C['rust_or'], n=4)
    for k in range(8):
        y = 0.26 - 0.16 * k
        z = 1.66 - 0.035 * k - 0.02 * k * k * 0.3
        h = 0.50 - 0.035 * k
        blade(body, V(0, y + 0.06, z - 0.10), V(0, y - 0.24, z + h), 0.26 - 0.014 * k, 0.08, V(1, 0, 0),
              C['bone'] if k % 2 == 0 else C['bone_dk'], bend=V(0, -0.10, 0.02), n=6, base_k=0.9)
        for sg in (1, -1):
            if k % 2 == 0 and k < 7:
                blade(body, V(0.16 * sg, y, z - 0.14), V(0.30 * sg, y - 0.16, z + h * 0.55), 0.16, 0.06,
                      V(0.3 * sg, 1, 0), C['bone_dk'], bend=V(0.02 * sg, -0.05, 0.02), n=5, base_k=0.9)
    snow_pillow(body, (0.34, 0.22, 1.56), (0.13, 0.17, 0.045), R('Y', 20), seed=31)
    snow_pillow(body, (-0.32, 0.05, 1.60), (0.11, 0.13, 0.04), R('Y', -18), seed=32)
    snow_pillow(body, (0.0, -0.30, 1.50), (0.10, 0.18, 0.035), seed=33)
    finish_paint(body, 0.6, 1.2, 0.3)
    cr.part('Body', body, (0, -0.25, 1.05))

    head = AAcc('head')
    blob(head, (0, 0.80, 0.98), (0.18, 0.20, 0.16), C['hide_dk'], e=(0.7, 0.8), segs=16, rings=10)
    blade(head, V(0, 0.70, 1.13), V(0, 1.04, 0.93), 0.34, 0.11, V(1, 0, 0), C['bone'], bend=V(0, 0, 0.07), n=7,
          base_k=1.0, tip_k=0.35)
    for s in (1, -1):
        blade(head, V(0.10 * s, 0.74, 1.10), V(0.24 * s, 0.64, 1.25), 0.11, 0.045, V(0, 1, 0), C['bone_dk'], n=5)
        ball(head, (0.08 * s, 0.965, 1.00), 0.036, C['black'], segs=10, rings=7)
        glow_eye(head, (0.085 * s, 0.985, 1.005), 0.026)
    for k in range(8):
        x = -0.105 + 0.03 * k
        horn(head, V(x, 0.95, 0.91), V(x, 0.985, 0.81 - 0.025 * (k % 2)), 0.017, C['bone'], segs=6, n=4)
    cr.part('Head', head, (0, 0.66, 1.02), parent='Body')

    for s in (1, -1):
        nm = 'L' if s > 0 else 'R'
        sh = V(0.40 * s, 0.38, 1.24)
        el = V(0.88 * s, 0.58, 1.54)
        wr = V(1.02 * s, 1.00, 0.95)
        arm = AAcc('arm')
        cables(arm, sh, el, n=4, r=0.08, R_=0.095, turns=0.5, surf=C['cable_dk'], seed=41 + s)
        ball(arm, el, 0.14, C['hide_dk'], segs=12, rings=8)
        blade(arm, sh + V(0.05 * s, -0.05, 0.14), el + V(0.02 * s, -0.10, 0.14), 0.32, 0.09, V(0.3 * s, 0, 1),
              C['bone_dk'], bend=V(0.02 * s, 0, 0.09), n=6, base_k=0.9)
        snow_pillow(arm, el + V(0.0, -0.06, 0.17), (0.07, 0.09, 0.025), seed=44 + s)
        cr.part('Arm' + nm, arm, sh, parent='Body')
        fore = AAcc('fore')
        cables(fore, el, wr, n=4, r=0.075, R_=0.08, turns=0.6, surf=C['cable_dk'], seed=51 + s)
        slab(fore, (el + wr) * 0.5 + V(0.08 * s, 0.03, 0.06), (0.17, 0.15, 0.44), C['bone'], M_=frame(wr - el, V(s, 0, 0)), seed=60 + s)
        cr.part('Fore' + nm, fore, el, parent='Arm' + nm)
        bl = AAcc('blade')
        tip = V(0.95 * s, 1.30, 0.05)
        blade(bl, wr + V(0, -0.06, 0.08), tip, 0.36, 0.09, V(0.25 * s, -1, 0.15), C['bone'], bend=V(0.15 * s, 0.32, 0.08),
              n=11, base_k=1.0, tip_k=0.0, edge=C['concrete_lt'])
        blade(bl, wr + V(0.02 * s, 0.02, 0.0), wr + V(0.07 * s, 0.26, -0.46), 0.17, 0.10, V(0.25 * s, -1, 0.15),
              C['rust_or'], n=5)
        slab(bl, wr + V(0, 0.0, 0.05), (0.25, 0.21, 0.17), C['bone_dk'], seed=70 + s)
        horn(bl, wr + V(0.06 * s, 0.05, 0.10), wr + V(0.19 * s, -0.12, 0.33), 0.045, C['bone_dk'], segs=6, n=4)
        snow_pillow(bl, wr + V(0, -0.02, 0.155), (0.07, 0.08, 0.025), seed=80 + s)
        cr.part('Blade' + nm, bl, wr, parent='Fore' + nm)

    for s in (1, -1):
        nm = 'L' if s > 0 else 'R'
        hip = V(0.30 * s, -0.66, 0.96)
        kn = V(0.40 * s, -0.36, 0.56)
        an = V(0.42 * s, -0.70, 0.22)
        th = AAcc('thigh')
        cables(th, hip, kn, n=4, r=0.09, R_=0.10, turns=0.5, surf=C['cable'], seed=91 + s)
        ball(th, hip, 0.18, C['hide_dk'], segs=12, rings=8)
        cr.part('Thigh' + nm, th, hip, parent='Body')
        sh_ = AAcc('shin')
        limb(sh_, [kn, (kn + an) * 0.5 + V(0, 0.03, 0), an], [0.095, 0.075, 0.065], C['hide_dk'], segs=10, per=3)
        limb(sh_, [an, an + V(0, 0.14, -0.12), an + V(0.0, 0.25, -0.20)], [0.065, 0.06, 0.055], C['hide'], segs=8, per=2)
        toe = an + V(0, 0.25, -0.20)
        for ang in (-30, 0, 30):
            a = math.radians(ang)
            dv = V(math.sin(a), math.cos(a), 0)
            horn(sh_, toe, toe + dv * 0.17 + V(0, 0, -0.01), 0.034, C['claw'], bend=V(0, 0, 0.03), segs=6, n=5)
        cr.part('Shin' + nm, sh_, kn, parent='Thigh' + nm)

    tail = AAcc('tail')
    tpts = [V(0, -0.80, 1.10), V(0, -1.25, 1.34), V(0, -1.70, 1.40), V(0, -2.12, 1.28), V(0, -2.48, 1.08)]
    tf = limb(tail, tpts, [0.18, 0.14, 0.10, 0.06, 0.02], C['hide'], segs=12, per=4)
    recolor(tail, tf, mottle(0.15, 5.0, 9, dark='#4A2424', dark_thr=0.4, dark_k=0.3))
    path = A.catmull(tpts, 4)
    for k in range(1, 12):
        i = int(k * (len(path) - 2) / 12) + 1
        p = path[i]
        tg = (path[i + 1] - path[i - 1]).normalized()
        up = (V(0, 0, 1) - tg * tg.z).normalized()
        h = 0.30 * (1.0 - k / 13.0)
        blade(tail, p + up * 0.05, p + up * (0.05 + h) - tg * 0.12, 0.13 * (1 - k / 14), 0.05,
              tg, C['bone'] if k % 2 else C['bone_dk'], n=5, base_k=0.9)
    cr.part('Tail', tail, (0, -0.80, 1.10), parent='Body')
    return cr


# =============================================================================================== 03 NEEDLE WALKER (Spearman)
WALKER_LEGS = (('A', 55.0), ('B', 125.0), ('C', 270.0))


def needle_walker(offset=(0, 0, 0)):
    """Masses: small barrel body with a ragged mane, horizontal needle pack on top, three long spread legs.
    Traits: exactly three legs in a stable triangle; open ring joints, thin ribbed segments, small gripping feet;
    deep amber sensor; forward needle launcher with an orange / black clamp."""
    cr = A.Creature('AW_NeedleWalker', '03_NeedleWalker (Spearman)', 'Spearman', offset)
    rnd = random.Random(303)
    body = AAcc('body')
    cz = 2.45
    lathe_at(body, [(0.0, -0.30), (0.20, -0.30), (0.29, -0.17), (0.31, 0.04), (0.27, 0.22), (0.12, 0.27), (0.0, 0.28)],
             V(0, 0, cz), V(0, 0, 1), C['steel_dk'], segs=20, sharp=45)
    ring(body, V(0, 0, cz - 0.22), V(0, 0, 1), 0.30, 0.08, 0.05, C['rust_dk'], segs=20)
    ring(body, V(0, 0, cz + 0.06), V(0, 0, 1), 0.325, 0.06, 0.04, C['rust'], segs=20)
    # sensor: a deep visor with two amber eyes
    box(body, (0, 0.25, cz - 0.02), (0.34, 0.20, 0.24), C['steel'], bevel=0.03)
    box(body, (0, 0.33, cz - 0.01), (0.25, 0.06, 0.11), C['bore'], bevel=0.015)
    for s in (1, -1):
        glow_eye(body, (0.055 * s, 0.335, cz - 0.01), 0.034)
    box(body, (0, 0.31, cz + 0.11), (0.36, 0.12, 0.05), C['steel_dk'], bevel=0.015)
    # ragged mane of rust-brown tendrils over the top and the back
    for k in range(18):
        az = math.radians(60 + 240 * k / 17)
        base = V(0.20 * math.cos(az), 0.20 * math.sin(az) - 0.02, cz + 0.22)
        drop = 0.25 + 0.22 * rnd.random()
        tip = base + V(0.18 * math.cos(az), 0.16 * math.sin(az) - 0.10, -drop)
        surf = C['cable_br'] if k % 3 else C['rust_dk']
        blade(body, base, tip, 0.09, 0.05, V(-math.sin(az), math.cos(az), 0), surf,
              bend=V(0.04 * math.cos(az), 0.04 * math.sin(az), 0.08), n=6)
    for k in range(7):
        az = math.radians(100 + 30 * k)
        base = V(0.14 * math.cos(az), 0.14 * math.sin(az), cz + 0.28)
        blade(body, base, base + V(0.12 * math.cos(az), 0.10 * math.sin(az) - 0.15, 0.10), 0.06, 0.035,
              V(-math.sin(az), math.cos(az), 0), C['cable_br'], n=5)
    # the coiled hose on the left flank (into the launcher mount)
    hp = [V(0.28, 0.0, cz - 0.05), V(0.42, 0.05, cz - 0.10), V(0.48, -0.08, cz - 0.24), V(0.38, -0.20, cz - 0.30),
          V(0.30, -0.12, cz - 0.20), V(0.34, 0.02, cz + 0.08), V(0.22, 0.06, cz + 0.30)]
    pipe(body, hp, 0.032, C['rust_dk'], segs=8, per=4)
    for t in (0.15, 0.35, 0.55, 0.75):
        p = A.catmull(hp, 4)[int(t * (len(hp) - 1) * 4)]
        ring(body, p, V(0, 0, 1), 0.04, 0.025, 0.012, C['steel_dk'], segs=10)
    # hip hubs: dark organic joints
    for nm, az in WALKER_LEGS:
        a = math.radians(az)
        ball(body, V(0.22 * math.cos(a), 0.22 * math.sin(a), cz - 0.26), 0.11, C['cable_dk'], segs=12, rings=8)
    snow_pillow(body, (0.0, -0.08, cz + 0.29), (0.10, 0.10, 0.035), seed=34)
    cr.part('Body', body, (0, 0, cz))

    # launcher: a mount block, five long needles, an orange / black clamp, conical steel tips
    lz = cz + 0.33
    lau = AAcc('launcher')
    box(lau, (0, 0.02, lz - 0.04), (0.36, 0.36, 0.22), C['steel'], bevel=0.03)
    box(lau, (0, -0.12, lz + 0.04), (0.30, 0.16, 0.16), C['rust_dk'], bevel=0.02)
    offs = ((-0.085, 0.055), (0.0, 0.09), (0.085, 0.055), (-0.045, -0.035), (0.045, -0.035))
    for (ox, oz) in offs:
        a = V(ox, -0.05, lz + oz)
        b = V(ox, 1.20, lz + oz)
        A_ = lau.cyl_between(a, b, 0.028, C['gunmetal'], 10, caps=True)
        horn(lau, b, b + V(0, 0.22, 0), 0.032, C['steel_lt'], segs=8, n=4)
        ring(lau, b - V(0, 0.02, 0), V(0, 1, 0), 0.038, 0.03, 0.012, C['steel_dk'], segs=10)
    box(lau, (0, 0.52, lz + 0.03), (0.30, 0.13, 0.25), C['hazard'], bevel=0.02)
    box(lau, (0, 0.92, lz + 0.03), (0.27, 0.06, 0.22), C['rust_dk'], bevel=0.015)
    box(lau, (0, 0.22, lz + 0.03), (0.31, 0.08, 0.26), C['rust'], bevel=0.015)
    snow_pillow(lau, (0, 0.02, lz + 0.075), (0.12, 0.13, 0.03), seed=36)
    cr.part('Launcher', lau, (0, 0.02, lz), parent='Body')
    cr.part('Muzzle', None, (0, 1.44, lz + 0.03), parent='Launcher')

    # legs: hip -> knee (open ring joint) -> long ribbed shin -> small gripping foot; a wide tripod
    for nm, az in WALKER_LEGS:
        a = math.radians(az)
        dirv = V(math.cos(a), math.sin(a), 0)
        hip = V(0, 0, cz - 0.26) + dirv * 0.22
        knee = V(0, 0, 1.98) + dirv * 0.95
        foot = V(0, 0, 0.05) + dirv * 1.55
        up = AAcc('leg')
        up.cyl_between(hip, knee, 0.085, C['steel'], 12, caps=True)
        for t in (0.25, 0.7):
            ring(up, hip.lerp(knee, t), knee - hip, 0.08, 0.05, 0.02, C['rust_dk'], segs=12)
        cables(up, hip + V(0, 0, -0.04), knee + V(0, 0, -0.06), n=2, r=0.025, R_=0.06, turns=0.7, surf=C['cable_dk'],
               seed=110 + int(az))
        cr.part('Leg' + nm, up, hip, parent='Body')
        sh = AAcc('shin')
        axis = Vector((-math.sin(a), math.cos(a), 0))       # knee hinge axis (tangent)
        sh.cyl_between(knee - axis * 0.10, knee + axis * 0.10, 0.15, C['steel'], 16, caps=True)
        ring(sh, knee, axis, 0.18, 0.07, 0.04, C['rust_dk'], segs=16)
        ball(sh, knee, 0.085, C['cable_dk'], segs=10, rings=7)
        ank = foot + V(0, 0, 0.16)
        sh.cyl_between(knee, ank, 0.078, C['steel'], 12, caps=True, r2=0.064)
        for k in range(8):
            t = 0.10 + 0.10 * k
            ring(sh, knee.lerp(ank, t), ank - knee, 0.088 - 0.01 * t, 0.03, 0.016,
                 C['rust_dk'] if k % 2 else C['rust'], segs=12)
        for t in (0.12, 0.22):
            ring(sh, knee.lerp(ank, t), ank - knee, 0.092, 0.07, 0.02, C['hazard'], segs=14)
        ring(sh, ank, ank - knee, 0.06, 0.04, 0.02, C['rust_dk'], segs=12)
        ball(sh, ank, 0.05, C['cable_dk'], segs=10, rings=6)
        for k in range(3):
            b = math.radians(az + (k - 1) * 70)
            dv = V(math.cos(b), math.sin(b), 0)
            horn(sh, ank + dv * 0.02, foot + dv * 0.14 + V(0, 0, -0.04), 0.03, C['claw'], bend=V(0, 0, 0.06), segs=6, n=5)
        cr.part('Shin' + nm, sh, knee, parent='Leg' + nm)
    return cr


# =============================================================================================== 04 BOILER SPITTER (Crossbow)
BOILER_LEGS = (('FL', 1, 1), ('FR', -1, 1), ('BL', 1, -1), ('BR', -1, -1))


def boiler_spitter(offset=(0, 0, 0)):
    """Masses: very low wide oval boiler, big tilted mortar pipe on top, four short splayed legs.
    Traits: rounded armour with rings and sections; torn pale insulation patches; front firebox grille with heat;
    a thick-walled pipe with a wide mouth and a hot dark interior; ribbed leg joints."""
    cr = A.Creature('AW_BoilerSpitter', '04_BoilerSpitter (Crossbow)', 'Crossbow', offset)
    rnd = random.Random(404)
    body = AAcc('body')
    Sxy = scale_xy(1.0, 0.84)
    prof = [(0.0, 0.40), (0.66, 0.42), (0.90, 0.53), (1.00, 0.72), (1.01, 0.95), (0.96, 1.16), (0.80, 1.35),
            (0.48, 1.48), (0.0, 1.52)]
    bf = body.lathe(prof, 28, Sxy, C['panel'], True, True, 40)
    recolor(body, bf, mottle(0.10, 3.0, 4))
    for z, r_ in ((0.74, 1.025), (1.12, 0.99), (1.36, 0.82)):
        body.lathe([(r_ - 0.03, z - 0.05), (r_ + 0.03, z - 0.04), (r_ + 0.03, z + 0.04), (r_ - 0.03, z + 0.05)], 28,
                   Sxy, C['rust_dk'], False, False, 40)
        for k in range(16):
            a = 2 * math.pi * k / 16
            ball(body, (math.cos(a) * (r_ + 0.035), math.sin(a) * (r_ + 0.035) * 0.84, z), 0.022, C['steel'], segs=6, rings=4)
    # hazard panels on the lower front band
    for k in range(5):
        a = math.radians(60 + 15 * k)
        p = V(math.cos(a) * 1.0, math.sin(a) * 0.84, 0.93)
        box(body, p, (0.20, 0.03, 0.22), C['hazard'], M=frame(V(math.cos(a), math.sin(a) * 1.2, 0), V(0, 0, 1)), bevel=0.01)
    # torn pale insulation (big chipped patches lying on the armour)
    for k, (az, z, w, h) in enumerate(((32, 0.98, 0.70, 0.62), (-50, 1.02, 0.62, 0.55), (150, 0.92, 0.55, 0.50),
                                         (-140, 1.10, 0.50, 0.42), (100, 1.28, 0.55, 0.40), (-95, 0.86, 0.45, 0.38),
                                         (62, 1.22, 0.40, 0.34))):
        a = math.radians(az)
        n = V(math.cos(a), math.sin(a) / 0.84, 0.25 if z > 1.2 else 0.05).normalized()
        p = V(math.cos(a) * 1.0, math.sin(a) * 0.84, z) + n * 0.02
        slab(body, p, (w, h, 0.09), C['concrete_lt'], M_=frame(n, V(0, 0, 1)), seed=410 + k, chip=0.04, e=0.25)
    # firebox: dark recess, vertical bars (the heat behind them is the Fire part)
    fz = 0.72
    box(body, (0, 0.80, fz), (0.62, 0.12, 0.40), C['steel_dk'], bevel=0.03)
    box(body, (0, 0.835, fz), (0.50, 0.04, 0.30), C['bore'], bevel=0.01)
    for k in range(6):
        x = -0.21 + 0.084 * k
        body.cyl_between(V(x, 0.895, fz - 0.16), V(x, 0.895, fz + 0.16), 0.018, C['steel_dk'], 8)
    body.cyl_between(V(-0.25, 0.885, fz + 0.16), V(0.25, 0.885, fz + 0.16), 0.02, C['steel_dk'], 8)
    body.cyl_between(V(-0.25, 0.885, fz - 0.16), V(0.25, 0.885, fz - 0.16), 0.02, C['steel_dk'], 8)
    # railings on top (back left), a curled pipe, snow
    railing(body, [V(-0.55, -0.15, 1.40), V(-0.62, -0.45, 1.36), V(-0.35, -0.66, 1.38), V(-0.05, -0.62, 1.44)], h=0.24,
            r=0.018)
    railing(body, [V(0.30, -0.55, 1.42), V(0.58, -0.40, 1.38)], h=0.22, r=0.018, mid=False)
    pipe(body, [V(-0.92, -0.30, 0.95), V(-1.10, -0.40, 1.10), V(-1.08, -0.62, 1.30), V(-0.85, -0.70, 1.32)], 0.05,
         C['rust_dk'], flanges=(0.1, 0.9))
    snow_pillow(body, (0.15, -0.15, 1.50), (0.42, 0.40, 0.07), seed=430)
    snow_pillow(body, (-0.62, 0.28, 1.36), (0.22, 0.20, 0.05), R('Y', -22), seed=431)
    snow_pillow(body, (0.55, 0.52, 1.25), (0.20, 0.16, 0.04), R('Y', 25), seed=432)
    finish_paint(body, 0.4, 1.1, 0.3)
    cr.part('Body', body, (0, 0, 0.95))

    fire = AAcc('fire')
    box(fire, (0, 0.862, fz), (0.46, 0.02, 0.26), C['fire'], bevel=0.005)
    ball(fire, (0, 0.868, fz - 0.03), (0.16, 0.012, 0.09), C['fire_core'], segs=10, rings=6)
    cr.part('Fire', fire, (0, 0.82, fz), parent='Body', shadow=False)

    # the mortar pipe: thick wall, staves and hoops, a wide dark mouth with a hot glow inside
    base = V(0.06, 0.06, 1.38)
    axis = V(0.10, 0.44, 0.89).normalized()
    pp = AAcc('pipe')
    Lp = 0.95
    lathe_at(pp, [(0.0, -0.05), (0.40, -0.05), (0.42, 0.0), (0.42, Lp - 0.08), (0.46, Lp), (0.45, Lp + 0.02),
                  (0.35, Lp + 0.02), (0.34, Lp - 0.04), (0.34, 0.20), (0.0, 0.20)], base, axis, C['steel'], segs=24,
             caps=(False, False), sharp=40)
    Mx = frame(axis)
    u, v = Mx.col[0].xyz, Mx.col[1].xyz
    for k in range(14):
        a = 2 * math.pi * k / 14
        rd = u * math.cos(a) + v * math.sin(a)
        pp.box((0.10, 0.025, Lp - 0.12), T(base + axis * (Lp * 0.48) + rd * 0.43) @ basis_from(rd, axis), C['steel_dk'],
               bevel=0.008, segs=1)
    for t in (0.12, 0.52, 0.90):
        ring(pp, base + axis * (Lp * t), axis, 0.47, 0.07, 0.06, C['rust'], segs=24)
    lathe_at(pp, [(0.0, 0.21), (0.30, 0.21), (0.33, 0.30)], base, axis, C['ember'], segs=18, caps=(False, False))
    ball(pp, base + axis * 0.26, (0.18, 0.18, 0.07), C['fire_core'], segs=12, rings=6, M=frame(axis))
    lathe_at(pp, [(0.335, 0.30), (0.337, 0.62)], base, axis, C['fire'], segs=18, caps=(False, False))
    lathe_at(pp, [(0.336, 0.62), (0.338, 0.80)], base, axis, C['ember'], segs=18, caps=(False, False))
    snow_pillow(pp, base + axis * (Lp + 0.02) + V(0, -0.30, 0.02), (0.10, 0.06, 0.025), seed=440)
    cr.part('Pipe', pp, base, parent='Body')
    cr.part('Muzzle', None, base + axis * (Lp + 0.04), parent='Pipe')

    # four short legs: ribbed (accordion) upper joint, a blocky hazard-striped foot with a claw
    for nm, sx, sy in BOILER_LEGS:
        hip = V(0.78 * sx, 0.46 * sy, 0.74)
        knee = V(1.08 * sx, 0.66 * sy, 0.48)
        foot = V(1.25 * sx, 0.82 * sy, 0.0)
        lg = AAcc('leg')
        lg.cyl_between(hip, knee, 0.13, C['cable_dk'], 12)
        for k in range(5):
            ring(lg, hip.lerp(knee, 0.1 + 0.2 * k), knee - hip, 0.17, 0.05, 0.05, C['rust_dk'] if k % 2 else C['rust'], segs=14)
        ball(lg, hip, 0.17, C['steel_dk'], segs=12, rings=8)
        cr.part('Leg' + nm, lg, hip, parent='Body')
        ft = AAcc('foot')
        ball(ft, knee, 0.15, C['rust_dk'], segs=12, rings=8)
        d = (foot - knee)
        mid = knee.lerp(foot, 0.45)
        slab(ft, mid, (0.26, 0.24, d.length * 0.85), C['steel_dk'], M_=frame(d, V(sx, 0, 0)), seed=450 + sx * 3 + sy,
             chip=0.015, e=0.3)
        box(ft, knee.lerp(foot, 0.42) + V(0.0, 0.0, 0.0), (0.27, 0.25, 0.20), C['hazard'], M=frame(d, V(sx, 0, 0)), bevel=0.02)
        horn(ft, foot + V(0, 0, 0.07), foot + V(0.12 * sx, 0.12 * sy, -0.02), 0.06, C['claw'], segs=6, n=4)
        slab(ft, foot + V(0, 0, 0.05), (0.30, 0.30, 0.10), C['steel'], seed=460 + sx + sy, chip=0.02)
        cr.part('Foot' + nm, ft, knee, parent='Leg' + nm)
    return cr


def basis_from(radial, axis):
    """Rotation with local x = the tangent around the axis, local y = radial, local z = axis (staves on a pipe)."""
    z = Vector(axis).normalized()
    y = (Vector(radial) - z * Vector(radial).dot(z)).normalized()
    x = y.cross(z).normalized()
    return Matrix((x, y, z)).transposed().to_4x4()


# =============================================================================================== 05 CONCRETE EXECUTIONER (Brute)
def executioner(offset=(0, 0, 0)):
    """Masses: wide rectangular torso under a yoke of concrete slabs, small sunk head, short blocky legs, a long cannon
    arm and an open mechanical hand.
    Traits: shoulders of several big cracked slabs with gaps, rebar and snow; square cannon muzzle with a deep bore and
    hazard stripes; sinew cables between the plates; asymmetric arms."""
    cr = A.Creature('AW_Executioner', '05_ConcreteExecutioner (Brute)', 'Brute', offset)
    pel = AAcc('pelvis')
    blob(pel, (0, 0, 1.22), (0.50, 0.34, 0.28), C['cable_dk'], e=(0.6, 0.8), segs=18, rings=10)
    pel.lathe([(0.0, -0.08), (0.53, -0.08), (0.55, 0.0), (0.53, 0.08), (0.0, 0.08)], 24, T((0, 0, 1.36)) @ scale_xy(1.0, 0.70),
              C['rust_dk'], False, False, 40)
    box(pel, (0, 0.38, 1.36), (0.22, 0.06, 0.18), C['steel'], bevel=0.02)
    for s in (1, -1):
        cables(pel, V(0.25 * s, 0.05, 1.05), V(0.38 * s, 0.0, 1.32), n=3, r=0.07, R_=0.08, turns=0.5, surf=C['cable'], seed=500 + s)
    cr.part('Pelvis', pel, (0, 0, 1.22))

    for s in (1, -1):
        nm = 'L' if s > 0 else 'R'
        hip = V(0.42 * s, 0.0, 1.14)
        knee = V(0.50 * s, 0.14, 0.62)
        ank = V(0.52 * s, 0.03, 0.18)
        th = AAcc('thigh')
        cables(th, hip, knee, n=5, r=0.09, R_=0.12, turns=0.5, surf=C['cable'], seed=510 + s)
        slab(th, hip.lerp(knee, 0.5) + V(0.07 * s, 0.13, 0.0), (0.36, 0.16, 0.42), C['concrete'], M_=R('X', -12), seed=512 + s)
        cr.part('Thigh' + nm, th, hip, parent='Pelvis')
        sh = AAcc('shin')
        cables(sh, knee, ank, n=4, r=0.08, R_=0.09, turns=0.5, surf=C['cable_dk'], seed=520 + s)
        slab(sh, knee.lerp(ank, 0.45) + V(0.0, 0.10, 0.0), (0.36, 0.30, 0.50), C['concrete_dk'], seed=522 + s)
        box(sh, knee + V(0.0, 0.18, 0.02), (0.34, 0.10, 0.20), C['hazard'], M=R('X', -15), bevel=0.02)
        slab(sh, ank + V(0, 0.12, -0.08), (0.46, 0.66, 0.22), C['concrete_dk'], seed=524 + s)
        slab(sh, ank + V(0.0, 0.46, -0.12), (0.40, 0.22, 0.14), C['concrete'], seed=526 + s)
        snow_pillow(sh, ank + V(0, 0.30, 0.05), (0.14, 0.14, 0.03), seed=528 + s)
        cr.part('Shin' + nm, sh, knee, parent='Thigh' + nm)

    tor = AAcc('torso')
    for s in (1, -1):
        cables(tor, V(0.22 * s, 0.02, 1.36), V(0.52 * s, 0.05, 2.30), n=4, r=0.085, R_=0.11, turns=0.6, surf=C['cable_dk'], seed=530 + s)
        cables(tor, V(0.08 * s, 0.12, 1.40), V(0.30 * s, 0.22, 2.20), n=3, r=0.07, R_=0.07, turns=0.6, surf=C['cable_br'], seed=534 + s)
    blob(tor, (0, 0.0, 1.85), (0.42, 0.28, 0.48), C['hide_dk'], e=(0.7, 0.8), segs=16, rings=10)
    box(tor, (0, 0.22, 2.02), (0.34, 0.12, 0.42), C['steel_dk'], bevel=0.04)
    box(tor, (0, 0.27, 2.08), (0.22, 0.04, 0.10), C['rust'], bevel=0.01)
    # the yoke: several big cracked slabs over both shoulders and the back, gaps between them
    yoke = [((-1.02, -0.05, 2.78), (0.78, 0.98, 0.42), R('Y', -18) @ R('X', 4), True),
            ((-0.52, 0.12, 2.98), (0.62, 0.72, 0.36), R('Y', -8) @ R('X', -6), False),
            ((-1.38, 0.10, 2.32), (0.42, 0.92, 0.62), R('Y', -12), True),
            ((1.04, -0.05, 2.80), (0.80, 0.96, 0.44), R('Y', 16) @ R('X', 3), True),
            ((0.56, 0.16, 3.00), (0.58, 0.70, 0.34), R('Y', 10) @ R('X', -5), False),
            ((1.40, 0.06, 2.30), (0.44, 0.90, 0.64), R('Y', 14), True),
            ((0.0, -0.46, 2.80), (0.92, 0.42, 0.62), R('X', 10), False),
            ((0.0, 0.10, 3.05), (0.40, 0.50, 0.26), R('X', -8), False)]
    for k, (c, size, Mr, haz) in enumerate(yoke):
        slab(tor, c, size, C['concrete'] if k % 3 else C['concrete_lt'], M_=Mr, seed=540 + k, chip=0.06)
        top = Vector(c) + (Mr @ Vector((0, 0, size[2] * 0.5))) + V(0, 0, 0.01)
        snow_pillow(tor, top, (size[0] * 0.36, size[1] * 0.38, 0.06), Mr, seed=560 + k)
        if haz:
            bot = Vector(c) + (Mr @ Vector((0, size[1] * 0.46, -size[2] * 0.25)))
            box(tor, bot, (size[0] * 0.8, 0.03, size[2] * 0.45), C['hazard'], M=Mr, bevel=0.01)
    for k, (p, dv, bend) in enumerate((((-1.1, -0.2, 3.0), (0.2, -0.2, 1), (0.1, 0.0, 0.1)),
                                       ((-0.7, 0.2, 3.15), (0.0, 0.1, 1), None),
                                       ((0.9, -0.1, 3.02), (-0.1, 0.0, 1), (0.12, 0.05, 0.0)),
                                       ((0.6, 0.3, 3.16), (0.1, 0.2, 1), None),
                                       ((0.2, -0.4, 3.1), (0.0, -0.3, 1), (0.0, -0.12, 0.05)))):
        rebar(tor, p, dv, 0.42 - 0.04 * k, bend=bend)
    cr.part('Torso', tor, (0, 0, 1.36), parent='Pelvis')

    hd = AAcc('head')
    blob(hd, (0, 0.30, 2.42), (0.20, 0.20, 0.22), C['cloth_dk'], e=(0.6, 0.8), segs=16, rings=10)
    slab(hd, (0, 0.46, 2.38), (0.24, 0.08, 0.24), C['concrete_dk'], seed=570, chip=0.02)
    for s in (1, -1):
        box(hd, (0.065 * s, 0.505, 2.43), (0.07, 0.02, 0.035), C['bore'], bevel=0.005)
        glow_eye(hd, (0.065 * s, 0.512, 2.43), 0.024)
    cr.part('Head', hd, (0, 0.26, 2.32), parent='Torso')

    # cannon arm (built at -x: the creature's right after the mirror): upper sinew, long square cannon with a deep bore, clamps and hazard panels
    shR = V(-0.88, 0.05, 2.40)
    elR = V(-1.02, 0.22, 1.86)
    gun = AAcc('gun')
    cables(gun, shR, elR, n=4, r=0.085, R_=0.10, turns=0.5, surf=C['cable'], seed=580)
    s0 = V(-1.02, -0.22, 1.68)
    e0 = V(-1.02, 1.98, 1.50)
    ax = (e0 - s0).normalized()
    Lg = (e0 - s0).length
    F = frame(ax, V(1, 0, 0))
    wall = 0.09
    W = 0.54
    for (dx, dz, sx, sz) in ((0, (W - wall) / 2, W, wall), (0, -(W - wall) / 2, W, wall),
                             ((W - wall) / 2, 0, wall, W - 2 * wall), (-(W - wall) / 2, 0, wall, W - 2 * wall)):
        off = F.col[0].xyz * dx + F.col[1].xyz * dz
        gun.box((sx, sz, Lg), T(s0 + ax * (Lg / 2) + off) @ F, C['steel'], bevel=0.02, segs=1)
    gun.box((W - 2 * wall, W - 2 * wall, Lg - 0.30), T(s0 + ax * ((Lg - 0.30) / 2)) @ F, C['bore'], bevel=0.0, segs=1)
    gun.box((W + 0.10, W + 0.10, 0.55), T(s0 + ax * 0.20) @ F, C['rust_dk'], bevel=0.04, segs=2)
    for t in (0.40, 0.72, 0.97):
        gun.box((W + 0.05, W + 0.05, 0.10), T(s0 + ax * (Lg * t)) @ F, C['rust'], bevel=0.015, segs=1)
    for sg in (1, -1):
        gun.box((0.03, W * 0.8, Lg * 0.34), T(s0 + ax * (Lg * 0.60) + F.col[0].xyz * (sg * (W / 2 + 0.016))) @ F, C['hazard'], bevel=0.005, segs=1)
    gun.box((W * 0.8, 0.03, Lg * 0.22), T(s0 + ax * (Lg * 0.84) + F.col[1].xyz * (W / 2 + 0.016)) @ F, C['hazard'], bevel=0.005, segs=1)
    gun.cyl_between(s0 + ax * 0.25 + F.col[1].xyz * (W / 2 + 0.09), s0 + ax * 1.35 + F.col[1].xyz * (W / 2 + 0.09), 0.065, C['steel'], 12)
    gun.box((0.10, 0.12, 0.40), T(s0 + ax * 0.75 + F.col[1].xyz * (W / 2 + 0.05)) @ F, C['steel_dk'], bevel=0.01, segs=1)
    snow_pillow(gun, s0 + ax * 0.9 + F.col[1].xyz * (W / 2 + 0.01), (0.18, 0.40, 0.03), seed=590)
    cr.part('ArmGun', gun, shR, parent='Torso')
    cr.part('Muzzle', None, e0 + ax * 0.02, parent='ArmGun')

    # open hand (built at +x: the creature's left after the mirror): sinew arm, concrete elbow pad, steel bracer, three big claws and a thumb
    shL = V(0.90, 0.02, 2.40)
    elL = V(1.18, 0.14, 1.80)
    wrL = V(1.30, 0.40, 1.26)
    al = AAcc('armL')
    cables(al, shL, elL, n=4, r=0.08, R_=0.10, turns=0.5, surf=C['cable'], seed=600)
    slab(al, elL + V(0.08, -0.06, 0.04), (0.30, 0.30, 0.30), C['concrete'], seed=602)
    cables(al, elL, wrL, n=4, r=0.07, R_=0.08, turns=0.6, surf=C['cable_dk'], seed=604)
    al.cyl_between(elL.lerp(wrL, 0.45), elL.lerp(wrL, 0.85), 0.14, C['steel_dk'], 12, caps=True)
    cr.part('ArmL', al, shL, parent='Torso')
    hd2 = AAcc('hand')
    box(hd2, wrL + V(0.0, 0.08, -0.10), (0.26, 0.24, 0.24), C['steel_dk'], bevel=0.04)
    for k, ang in enumerate((-25, 0, 25)):
        a = math.radians(ang)
        base = wrL + V(0.08 * math.sin(a), 0.16, -0.18)
        mid = base + V(0.10 * math.sin(a), 0.16, -0.16)
        tip = mid + V(0.05 * math.sin(a), 0.04, -0.26)
        limb(hd2, [base, mid], [0.055, 0.05], C['steel'], segs=8, per=2)
        ring(hd2, mid, mid - base, 0.06, 0.04, 0.02, C['rust_dk'], segs=10)
        horn(hd2, mid, tip, 0.05, C['claw'], bend=V(0, 0.08, 0.02), segs=8, n=5)
    horn(hd2, wrL + V(-0.10, 0.10, -0.16), wrL + V(-0.18, 0.30, -0.30), 0.045, C['claw'], bend=V(0, 0.05, 0.05), segs=8, n=5)
    cr.part('HandL', hd2, wrL, parent='ArmL')
    return cr


# =============================================================================================== 06 WHITEOUT RAIDER (Buggy)
RAIDER_WHEELS = (-2.12, -1.78, -1.44, -1.10, -0.78)


def whiteout_raider(offset=(0, 0, 0)):
    """Masses: long low hull, wedge plough between two widely spaced front skis, wide rear track units, cockpit with a
    small hooded driver, an open rotary turret behind it.
    Traits: curved ski tips with visible suspension (orange coil springs); tracks wrapped round road wheels; plough with
    three amber lamps; side tanks with hazard bands; snow on the top panels, dark side mechanics."""
    cr = A.Creature('AW_WhiteoutRaider', '06_WhiteoutRaider (Buggy)', 'Buggy', offset)
    hull = AAcc('hull')
    box(hull, (0, -0.62, 0.80), (1.70, 3.70, 0.66), C['panel_dk'], bevel=0.06)
    box(hull, (0, -0.70, 1.16), (1.50, 2.90, 0.10), C['panel'], bevel=0.03)
    # plough: a wedge between the skis
    prism(hull, [V(-0.92, 1.02, 0.20), V(0.92, 1.02, 0.20), V(0.34, 2.58, 0.16), V(-0.34, 2.58, 0.16)],
          [V(-0.84, 1.05, 1.08), V(0.84, 1.05, 1.08), V(0.18, 2.18, 0.86), V(-0.18, 2.18, 0.86)], C['steel_lt'])
    box(hull, (0, 1.72, 0.96), (0.70, 0.40, 0.06), C['steel'], M=R('X', 12), bevel=0.015)
    for k in range(3):
        x = -0.20 + 0.20 * k
        box(hull, (x, 1.95, 0.92), (0.15, 0.07, 0.10), C['steel_dk'], M=R('X', 30), bevel=0.015)
        box(hull, (x, 1.99, 0.925), (0.11, 0.03, 0.07), C['lamp'], M=R('X', 30), bevel=0.01)
    for s in (1, -1):
        box(hull, (0.62 * s, 1.75, 0.45), (0.04, 0.80, 0.22), C['hazard'], M=R('Z', -21 * s), bevel=0.01)
    snow_pillow(hull, (0, 1.55, 1.04), (0.55, 0.45, 0.08), R('X', 14), seed=610)
    snow_pillow(hull, (0, 2.05, 0.90), (0.22, 0.20, 0.05), R('X', 22), seed=611)
    # cockpit: seat, roll cage, windscreen frame
    box(hull, (0, 0.30, 1.22), (0.62, 0.55, 0.16), C['cloth_dk'], bevel=0.04)
    box(hull, (0, 0.02, 1.50), (0.60, 0.12, 0.55), C['cloth_dk'], bevel=0.04)
    cage = [(-0.62, 0.95, 1.10), (-0.55, 0.85, 1.95), (0.55, 0.85, 1.95), (0.62, 0.95, 1.10)]
    pipe(hull, [V(*p) for p in cage], 0.035, C['steel_dk'], segs=8, per=3)
    pipe(hull, [V(-0.62, -0.20, 1.18), V(-0.55, -0.12, 1.90), V(0.55, -0.12, 1.90), V(0.62, -0.20, 1.18)], 0.035,
         C['steel_dk'], segs=8, per=3)
    for s in (1, -1):
        hull.cyl_between(V(0.55 * s, 0.85, 1.95), V(0.55 * s, -0.12, 1.90), 0.032, C['steel_dk'], 8)
    box(hull, (0, 0.98, 1.38), (1.10, 0.05, 0.40), C['glass'], M=R('X', -18), bevel=0.01)
    # side tanks with hazard bands, exhausts, rear rack, antenna
    for s in (1, -1):
        hull.cyl_between(V(0.98 * s, -1.62, 1.02), V(0.98 * s, -0.36, 1.02), 0.24, C['steel_dk'], 16, caps=True)
        for t in (-1.35, -0.62):
            ring(hull, V(0.98 * s, t, 1.02), V(0, 1, 0), 0.255, 0.10, 0.03, C['hazard'], segs=16)
        snow_pillow(hull, (0.98 * s, -1.0, 1.24), (0.14, 0.50, 0.035), seed=612 + s)
        box(hull, (0.80 * s, -1.45, 0.86), (0.18, 2.20, 0.06), C['steel'], bevel=0.02)
        for k, (y, z, h) in enumerate(((0.55, 0.80, 0.40), (-0.05, 0.84, 0.46), (-2.0, 0.92, 0.30))):
            box(hull, (0.87 * s, y, z), (0.05, 0.55, h), C['panel'] if k % 2 else C['steel_lt'], bevel=0.015)
            snow_pillow(hull, (0.80 * s, y, 1.17), (0.07, 0.22, 0.025), seed=660 + k + s)
    for k in range(2):
        pipe(hull, [V(-0.55 + 0.18 * k, -2.42, 0.95), V(-0.55 + 0.18 * k, -2.55, 1.20), V(-0.55 + 0.18 * k, -2.52, 1.62)],
             0.045, C['rust_dk'], segs=8, flanges=(0.6,))
    railing(hull, [V(-0.55, -1.55, 1.21), V(-0.62, -2.35, 1.21), V(0.62, -2.35, 1.21), V(0.55, -1.55, 1.21)], h=0.32, r=0.022)
    box(hull, (0.30, -2.00, 1.35), (0.45, 0.50, 0.28), C['rust_dk'], bevel=0.03)
    snow_pillow(hull, (0.30, -2.00, 1.49), (0.18, 0.20, 0.035), seed=615)
    hull.cyl_between(V(0.70, -2.30, 1.20), V(0.72, -2.32, 2.65), 0.014, C['steel_dk'], 6)
    snow_pillow(hull, (-0.25, -1.20, 1.21), (0.40, 0.55, 0.05), seed=616)
    # suspension (rigid part of the hull): A-arms to the ski spindles, coil-over shocks with orange springs
    for s in (1, -1):
        top = V(1.35 * s, 1.86, 0.62)
        for dy in (-0.14, 0.14):
            hull.cyl_between(V(0.80 * s, 1.56 + dy, 0.62), top + V(0, dy * 0.3, -0.05), 0.035, C['steel_dk'], 8)
            hull.cyl_between(V(0.80 * s, 1.56 + dy, 0.38), top + V(0, dy * 0.3, -0.36), 0.035, C['steel_dk'], 8)
        a = V(0.98 * s, 1.50, 1.05)
        b = top + V(-0.03 * s, 0, -0.06)
        hull.cyl_between(a, b, 0.045, C['rust_dk'], 10)
        coil_spring(hull, a.lerp(b, 0.12), a.lerp(b, 0.78), 0.075, 0.016, turns=7)
    finish_paint(hull, 0.2, 1.0, 0.3)
    cr.part('Body', hull, (0, 0, 0.80))

    for s in (1, -1):
        nm = 'L' if s > 0 else 'R'
        top = V(1.35 * s, 1.86, 0.62)
        sk = AAcc('ski')
        ski(sk, V(1.35 * s, 1.80, 0.02), 1.80, 0.28, C['steel_dk'], tip_rise=0.30, thick=0.05)
        box(sk, (1.35 * s, 1.80, 0.12), (0.18, 0.40, 0.14), C['rust_dk'], bevel=0.02)
        sk.cyl_between(V(1.35 * s, 1.86, 0.12), top, 0.05, C['steel'], 10, caps=True)
        ring(sk, top + V(0, 0, -0.06), V(0, 0, 1), 0.075, 0.08, 0.03, C['rust'], segs=12)
        snow_pillow(sk, (1.35 * s, 2.30, 0.20), (0.08, 0.12, 0.02), R('X', -30), seed=620 + s)
        cr.part('Ski' + nm, sk, top, parent='Body')
        # track belt + wheels: the belt scrolls (uv), the wheels spin
        tr = AAcc('track')
        track_loop(tr, 0.80 * s, -2.42, -0.48, 0.30, 0.28, 0.33, 0.56, C['tread'], thick=0.07)
        cr.part('Track' + nm, tr, (0.80 * s, -1.45, 0.33), parent='Body')
        for k, y in enumerate(RAIDER_WHEELS):
            wh = AAcc('wheel')
            wheel(wh, V(0.80 * s, y, 0.25), V(1, 0, 0), 0.19, 0.42)
            cr.part(f'Wheel{nm}{k}', wh, (0.80 * s, y, 0.25), parent='Body')
        for nm2, y, r_, z in (('Idler', -0.48, 0.25, 0.33), ('Sprocket', -2.42, 0.27, 0.33)):
            wh = AAcc('wheel')
            wheel(wh, V(0.80 * s, y, z), V(1, 0, 0), r_, 0.40, spokes=6)
            cr.part(f'{nm2}{nm}', wh, (0.80 * s, y, z), parent='Body')

    # the driver: small, hooded, fur-lined hood, amber goggles; head is its own part (looks around)
    dr = AAcc('driver')
    blob(dr, (0, 0.30, 1.50), (0.22, 0.16, 0.26), C['cloth'], e=(0.7, 0.8), segs=14, rings=9)
    for s in (1, -1):
        limb(dr, [V(0.20 * s, 0.34, 1.62), V(0.28 * s, 0.55, 1.45), V(0.25 * s, 0.82, 1.38)], [0.06, 0.05, 0.045], C['cloth'],
             segs=8, per=2)
        ball(dr, (0.25 * s, 0.84, 1.37), 0.05, C['cloth_dk'], segs=8, rings=6)
    dr.cyl_between(V(-0.30, 0.86, 1.36), V(0.30, 0.86, 1.36), 0.022, C['steel_dk'], 8)
    cr.part('Driver', dr, (0, 0.30, 1.30), parent='Body')
    dh = AAcc('driverhead')
    blob(dh, (0, 0.34, 1.83), (0.17, 0.17, 0.19), C['cloth'], e=(0.7, 0.8), segs=14, rings=10)
    torus(dh, (0, 0.47, 1.82), (0, 1, 0.1), 0.10, 0.045, C['fur'], segs=18, rsegs=8)
    ball(dh, (0, 0.47, 1.81), (0.085, 0.03, 0.10), C['black'], segs=12, rings=8)
    for s in (1, -1):
        glow_eye(dh, (0.04 * s, 0.50, 1.83), 0.022, C['amber_soft'])
    snow_pillow(dh, (0, 0.30, 2.00), (0.08, 0.09, 0.025), seed=640)
    cr.part('DriverHead', dh, (0, 0.32, 1.66), parent='Driver')

    # the turret: ring, pedestal, gun cradle with a four-barrel rotary gun and a hazard ammo box
    tu = AAcc('turret')
    lathe_at(tu, [(0.0, 0.0), (0.50, 0.0), (0.53, 0.06), (0.50, 0.14), (0.0, 0.14)], V(0, -0.62, 1.20), V(0, 0, 1),
             C['steel_dk'], segs=24, caps=(False, False), sharp=40)
    lathe_at(tu, [(0.0, 0.14), (0.30, 0.14), (0.26, 0.62), (0.0, 0.62)], V(0, -0.62, 1.20), V(0, 0, 1), C['steel'],
             segs=16, sharp=40)
    box(tu, (0.44, -0.68, 1.98), (0.28, 0.52, 0.36), C['hazard'], bevel=0.02)
    box(tu, (0.30, -0.68, 1.98), (0.03, 0.40, 0.26), C['steel_dk'], bevel=0.005)
    snow_pillow(tu, (0.44, -0.68, 2.16), (0.10, 0.19, 0.03), seed=650)
    cr.part('Turret', tu, (0, -0.62, 1.20), parent='Body')
    gn = AAcc('gun')
    box(gn, (0, -0.64, 2.00), (0.40, 0.70, 0.36), C['steel'], bevel=0.04)
    box(gn, (0, -0.95, 2.04), (0.26, 0.18, 0.24), C['rust_dk'], bevel=0.02)
    gn.cyl_between(V(-0.21, -0.64, 2.00), V(0.21, -0.64, 2.00), 0.10, C['steel_dk'], 12)
    cr.part('Gun', gn, (0, -0.64, 2.00), parent='Turret')
    br = AAcc('barrels')
    gatling(br, V(0, -0.30, 2.00), V(0, 1, 0), n=4, rb=0.05, length=1.05, cluster=0.095)
    cr.part('Barrels', br, (0, -0.30, 2.00), parent='Gun')
    cr.part('Muzzle', None, (0, 0.78, 2.00), parent='Gun')
    return cr


# =============================================================================================== 07 BLACK REACTOR (BossColossus)
def black_reactor(offset=(0, 0, 0)):
    """Masses: overhanging concrete carapace over a round reactor casing, a low glowing core port, one huge block fist,
    one long thin claw arm, short wide legs on heavy stacked feet.
    Traits: carapace of big cracked slabs with snow on the edges; railing platform with broken chimneys on top; head
    almost hidden (an amber sensor slit); hazard band across the casing; very different arms; sinew between plates."""
    cr = A.Creature('AW_BlackReactor', '07_BlackReactor (BossColossus)', 'BossColossus', offset)
    rnd = random.Random(707)
    pel = AAcc('pelvis')
    blob(pel, (0, 0.0, 3.10), (1.25, 0.80, 0.55), C['cable_dk'], e=(0.6, 0.8), segs=20, rings=10)
    pel.lathe([(0.0, -0.12), (1.22, -0.12), (1.28, 0.0), (1.22, 0.12), (0.0, 0.12)], 28, T((0, 0, 3.32)) @ scale_xy(1.0, 0.68),
              C['rust_dk'], False, False, 40)
    for s in (1, -1):
        cables(pel, V(0.6 * s, 0.1, 2.75), V(1.05 * s, 0.0, 3.30), n=4, r=0.16, R_=0.18, turns=0.5, surf=C['cable'], seed=700 + s)
    cr.part('Pelvis', pel, (0, 0, 3.10))

    for s in (1, -1):
        nm = 'L' if s > 0 else 'R'
        hip = V(1.05 * s, 0.0, 3.00)
        knee = V(1.36 * s, 0.24, 1.85)
        ank = V(1.44 * s, 0.14, 0.95)
        th = AAcc('thigh')
        cables(th, hip, knee, n=5, r=0.22, R_=0.30, turns=0.5, surf=C['cable'], seed=710 + s)
        slab(th, hip.lerp(knee, 0.5) + V(0.15 * s, 0.42, 0.0), (0.80, 0.30, 0.82), C['concrete'], M_=R('X', -10), seed=712 + s)
        box(th, hip.lerp(knee, 0.65) + V(0.15 * s, 0.60, 0.0), (0.60, 0.05, 0.22), C['hazard'], M=R('X', -10), bevel=0.01)
        cr.part('Thigh' + nm, th, hip, parent='Pelvis')
        sh = AAcc('shin')
        cables(sh, knee, ank, n=5, r=0.20, R_=0.24, turns=0.5, surf=C['cable_dk'], seed=720 + s)
        slab(sh, knee.lerp(ank, 0.4) + V(0.05 * s, 0.30, 0.0), (0.86, 0.50, 0.70), C['concrete_dk'], seed=722 + s)
        slab(sh, knee + V(0.0, 0.30, 0.10), (0.70, 0.45, 0.45), C['concrete'], seed=723 + s)
        if s > 0:
            sh.cyl_between(knee + V(0.32, 0, 0), knee + V(0.52, 0, 0), 0.42, C['steel'], 20, caps=True)
            ring(sh, knee + V(0.50, 0, 0), V(1, 0, 0), 0.44, 0.06, 0.06, C['rust_dk'], segs=20)
            for k in range(8):
                a = 2 * math.pi * k / 8
                ball(sh, knee + V(0.53, 0.30 * math.cos(a), 0.30 * math.sin(a)), 0.045, C['steel_dk'], segs=6, rings=4)
        # heavy stacked foot
        slab(sh, V(1.46 * s, 0.30, 0.24), (1.50, 1.95, 0.48), C['concrete_dk'], seed=724 + s)
        slab(sh, V(1.44 * s, 0.10, 0.72), (1.15, 1.25, 0.52), C['concrete'], seed=725 + s)
        for k in range(3):
            slab(sh, V(1.46 * s + (k - 1) * 0.48, 1.35, 0.22), (0.44, 0.55, 0.42), C['concrete'], seed=726 + 3 * k + s)
            snow_pillow(sh, V(1.46 * s + (k - 1) * 0.48, 1.35, 0.44), (0.14, 0.18, 0.04), seed=740 + 3 * k + s)
        snow_pillow(sh, V(1.46 * s, -0.1, 0.99), (0.40, 0.42, 0.06), seed=750 + s)
        cr.part('Shin' + nm, sh, knee, parent='Thigh' + nm)

    tor = AAcc('torso')
    cc = V(0, 0.25, 4.75)
    cf = tor.superellipsoid((1.75, 1.50, 1.55), (0.75, 1.0), T(cc), C['panel_dk'], 28, 18)
    recolor(tor, cf, mottle(0.10, 2.0, 11))
    Sx = scale_xy(1.75 / 1.55, 1.50 / 1.55)
    for z, w_, surf in ((5.30, 0.30, C['hazard']), (4.20, 0.14, C['rust_dk']), (5.78, 0.12, C['rust_dk'])):
        zz = z - cc.z
        rr = 1.55 * (1 - abs(zz / 1.55) ** (2 / 0.75)) ** (0.75 / 2) + 0.03
        tor.lathe([(rr - 0.06, zz - w_ / 2), (rr + 0.02, zz - w_ / 2 + 0.02), (rr + 0.02, zz + w_ / 2 - 0.02), (rr - 0.06, zz + w_ / 2)],
                  32, T(cc) @ Sx, surf, False, False, 40)
    for s in (1, -1):
        box(tor, (0.65 * s, 1.52, 5.62), (0.42, 0.10, 0.20), C['grille'], M=R('X', -25), bevel=0.02)
        pipe(tor, [V(0.9 * s, -1.0, 6.0), V(1.4 * s, -0.2, 6.2), V(1.7 * s, 0.7, 5.6), V(1.5 * s, 1.3, 4.9), V(1.0 * s, 1.55, 4.6)],
             0.13, C['rust_dk'], segs=10, flanges=(0.25, 0.7))
        pipe(tor, [V(0.4 * s, -1.2, 6.1), V(0.6 * s, -0.4, 6.5), V(1.0 * s, 0.6, 6.0), V(1.2 * s, 1.1, 5.3)], 0.09,
             C['rust'], segs=8, flanges=(0.5,))
    for s in (1, -1):
        cables(tor, V(1.2 * s, 0.0, 3.5), V(1.6 * s, 0.2, 4.4), n=4, r=0.14, R_=0.18, turns=0.6, surf=C['cable'], seed=760 + s)
        cables(tor, V(1.5 * s, 0.3, 5.8), V(2.4 * s, 0.25, 6.05), n=4, r=0.15, R_=0.2, turns=0.6, surf=C['cable_dk'], seed=764 + s)
    cables(tor, V(-0.4, 0.4, 3.35), V(-0.5, 0.6, 3.6), n=3, r=0.12, R_=0.12, surf=C['cable'], seed=768)
    # the core port: a deep round recess with dark segments (the glowing core itself is the Port part)
    pc = V(0.18, 1.58, 4.12)
    pn = V(0.05, 1.0, -0.22).normalized()
    lathe_at(tor, [(0.0, -0.40), (0.62, -0.40), (0.66, -0.10), (0.96, 0.02), (1.02, 0.12), (0.84, 0.14), (0.70, 0.02)],
             pc, pn, C['steel_dk'], segs=28, caps=(False, False), sharp=35)
    F = frame(pn)
    for k in range(8):
        a = 2 * math.pi * k / 8 + 0.2
        rd = F.col[0].xyz * math.cos(a) + F.col[1].xyz * math.sin(a)
        tor.box((0.20, 0.30, 0.14), T(pc + rd * 0.80 + pn * 0.06) @ basis_from(rd, pn), C['gunmetal'], bevel=0.02, segs=1)
    lathe_at(tor, [(0.0, -0.36), (0.60, -0.36)], pc, pn, C['bore'], segs=24, caps=(False, False))
    pipe(tor, [pc + V(-0.95, 0.0, 0.25), pc + V(-1.0, 0.2, 0.8), pc + V(-0.6, 0.1, 1.2)], 0.09, C['rust_dk'], segs=8)
    # carapace: big chipped slabs arched over the shoulders and back, overhanging the front (a brow over the sensor),
    # over a dark backing shell so the joints between slabs read as dark seams instead of holes
    SH_C, SH_H, E1, E2 = Vector((0, -0.95, 5.95)), (2.95, 2.05, 1.75), 0.75, 0.80
    tor.superellipsoid(SH_H, (E1, E2), T(SH_C), C['concrete_dk'].k(0.7), 24, 12)

    def shell(x, y):
        """Height and normal of the backing shell's top at (x, y), or None outside it."""
        q = (abs(x / SH_H[0]) ** (2 / E2) + abs((y - SH_C.y) / SH_H[1]) ** (2 / E2)) ** (E2 / E1)
        if q >= 0.97:
            return None
        z = SH_H[2] * (1 - q) ** (E1 / 2)
        e = 0.02
        def h(a, b):
            qq = (abs(a / SH_H[0]) ** (2 / E2) + abs((b - SH_C.y) / SH_H[1]) ** (2 / E2)) ** (E2 / E1)
            return SH_H[2] * max(0.0, 1 - qq) ** (E1 / 2)
        gx = (h(x + e, y) - h(x - e, y)) / (2 * e)
        gy = (h(x, y + e) - h(x, y - e)) / (2 * e)
        return SH_C.z + z, Vector((-gx, -gy, 1.0)).normalized()
    k = 0
    for iy, y in enumerate((0.80, 0.18, -0.46, -1.10, -1.74, -2.36)):
        cols = 6 if iy in (0, 5) else 7
        for c in range(cols):
            x = (c / (cols - 1) - 0.5) * (5.3 if iy in (1, 2, 3) else 4.6) + rnd.uniform(-0.12, 0.12)
            got = shell(x, y)
            if got is None:
                continue
            z, n = got
            if z < 5.35:
                continue
            size = (1.12 + rnd.uniform(-0.1, 0.18), 1.02 + rnd.uniform(-0.1, 0.15), 0.42 + rnd.uniform(-0.04, 0.08))
            Mr = frame(n, Vector((1, 0, 0))) @ R('Z', rnd.uniform(-10, 10))
            p = Vector((x, y, z)) + n * (size[2] * 0.30)
            slab(tor, p, size, C['concrete'] if (k % 3) else C['concrete_lt'], M_=Mr, seed=780 + k, chip=0.08)
            top = p + n * (size[2] * 0.5)
            if n.z > 0.75 and rnd.random() < 0.8:
                snow_pillow(tor, top, (size[0] * 0.36, size[1] * 0.32, 0.09), Mr, seed=820 + k)
            k += 1
    # the overhanging brow at the front and the hanging side plates over the shoulders
    for c in range(5):
        x = (c / 4 - 0.5) * 3.4
        Mr = R('Y', -x * 9) @ R('X', 50)
        slab(tor, (x, 1.30, 6.62 - 0.15 * abs(x)), (0.95, 0.85, 0.40), C['concrete'], M_=Mr, seed=900 + c, chip=0.07)
        if abs(x) < 1.2:
            snow_pillow(tor, (x, 1.05, 6.98 - 0.1 * abs(x)), (0.30, 0.22, 0.06), R('X', 30), seed=930 + c)
    for sgn in (1, -1):
        for c in range(3):
            Mr = R('Y', 58 * sgn) @ R('X', -10 + 12 * c)
            slab(tor, (2.90 * sgn, 0.55 - 0.95 * c, 6.05), (0.95, 0.95, 0.44), C['concrete_lt'] if c % 2 else C['concrete'],
                 M_=Mr, seed=910 + c + 3 * (sgn > 0), chip=0.07)
    for s in (1, -1):
        box(tor, (2.75 * s, 1.15, 5.65), (0.55, 0.05, 0.26), C['hazard'], M=R('Z', -20 * s), bevel=0.01)
    for p, dv, bend in (((-2.0, 0.6, 6.8), (-0.2, 0.1, 1), (0.15, 0, 0.05)), ((-1.6, 0.9, 6.9), (0.1, 0.2, 1), None),
                        ((1.8, 0.4, 6.9), (0.2, 0.0, 1), (-0.1, 0.1, 0.1)), ((1.2, 1.1, 6.9), (0.0, 0.3, 1), None),
                        ((-2.4, -0.4, 6.5), (-0.3, -0.2, 1), None)):
        rebar(tor, p, dv, 0.75, r=0.035, bend=bend)
    # the sensor slit under the brow (head almost hidden)
    box(tor, (0, 1.42, 6.02), (1.30, 0.50, 0.50), C['bore'], bevel=0.05)
    box(tor, (0, 1.64, 6.04), (0.60, 0.05, 0.10), C['amber'], bevel=0.015)
    box(tor, (0, 1.62, 6.04), (0.72, 0.05, 0.16), C['steel_dk'], bevel=0.015)
    # top deck: railing platform and three chimneys (two broken)
    DZ = 7.62
    box(tor, (0, -0.45, DZ - 0.07), (2.60, 1.90, 0.14), C['steel_dk'], bevel=0.03)
    railing(tor, [V(-1.25, 0.45, DZ), V(-1.25, -1.35, DZ), V(1.25, -1.35, DZ), V(1.25, 0.45, DZ)], h=0.55, r=0.035,
            posts_every=0.5)
    railing(tor, [V(-1.25, 0.45, DZ), V(-0.5, 0.55, DZ)], h=0.55, r=0.035, posts_every=0.5)
    for i, (x, y, h, r_, broken) in enumerate(((-0.62, -0.88, 1.55, 0.30, False), (0.18, -1.02, 1.30, 0.34, True),
                                                (0.88, -0.65, 1.10, 0.28, True))):
        if broken:
            broken_chimney(tor, V(x, y, DZ), h, r_, C['steel_dk'], seed=850 + i, wall=0.07, jag=0.38)
        else:
            lathe_at(tor, [(0.0, 0.0), (r_, 0.0), (r_, h), (r_ + 0.05, h), (r_ + 0.05, h + 0.12), (r_ - 0.06, h + 0.12),
                           (r_ - 0.06, h - 0.3), (0.0, h - 0.3)], V(x, y, DZ), V(0, 0, 1), C['steel_dk'], segs=18, sharp=40)
        ring(tor, V(x, y, DZ + h * 0.35), V(0, 0, 1), r_ + 0.04, 0.08, 0.05, C['rust_dk'], segs=18)
    pipe(tor, [V(-0.3, -0.3, DZ + 0.03), V(-0.1, -0.5, DZ + 0.38), V(0.15, -0.95, DZ + 0.48)], 0.07, C['rust_dk'], segs=8)
    snow_pillow(tor, (0.1, 0.0, DZ + 0.01), (0.80, 0.45, 0.06), seed=860)
    cr.part('Torso', tor, (0, 0, 3.45), parent='Pelvis')

    core = AAcc('core')
    ball(core, pc - pn * 0.08, (0.30, 0.30, 0.30), C['fire_core'], segs=16, rings=10)
    lathe_at(core, [(0.0, -0.30), (0.46, -0.30), (0.52, -0.34)], pc, pn, C['fire'], segs=24, caps=(False, False))
    cr.part('Port', core, pc, parent='Torso', shadow=False)

    # heavy arm (built at -x: the creature's right after the mirror): thick sinew + blocks, a forearm of stacked slabs ending in a huge block fist
    shR = V(-2.55, 0.25, 6.00)
    elR = V(-3.15, 0.62, 4.00)
    ah = AAcc('armHeavy')
    cables(ah, shR, elR, n=5, r=0.24, R_=0.34, turns=0.5, surf=C['cable'], seed=870)
    for i in range(3):
        p = shR.lerp(elR, 0.2 + 0.3 * i) + V(-0.32, -0.05, 0.0)
        slab(ah, p, (0.55, 0.95, 0.85), C['concrete'], M_=R('Y', -12), seed=872 + i)
        snow_pillow(ah, p + V(-0.1, 0, 0.45), (0.18, 0.30, 0.05), seed=876 + i)
    cr.part('ArmHeavy', ah, shR, parent='Torso')
    fh = AAcc('foreHeavy')
    fist = V(-3.35, 1.30, 1.75)
    cables(fh, elR, fist + V(0, -0.2, 0.6), n=5, r=0.22, R_=0.3, turns=0.6, surf=C['cable_dk'], seed=880)
    for i in range(4):
        p = elR.lerp(fist, 0.15 + 0.22 * i)
        slab(fh, p + V(-0.05, 0.05, 0.0), (1.05 + 0.08 * i, 1.10, 0.62), C['concrete'] if i % 2 else C['concrete_dk'],
             M_=R('X', 12) @ R('Y', rnd.uniform(-8, 8)), seed=882 + i)
    for ix in range(3):
        for iz in range(3):
            p = fist + V((ix - 1) * 0.68, 0.30 + 0.12 * (iz == 1), (iz - 1) * 0.64)
            slab(fh, p, (0.74, 0.86, 0.68), C['concrete'] if (ix + iz) % 2 else C['concrete_lt'],
                 M_=R('X', rnd.uniform(-8, 8)) @ R('Z', rnd.uniform(-8, 8)), seed=890 + ix * 3 + iz)
    for ix in range(3):
        snow_pillow(fh, fist + V((ix - 1) * 0.62, 0.30, 0.90), (0.20, 0.24, 0.05), seed=900 + ix)
    cr.part('ForeHeavy', fh, elR, parent='ArmHeavy')

    # claw arm (built at +x: the creature's left after the mirror): longer, thinner sinew, a steel bracer, a long hand with four claws
    shL = V(2.60, 0.15, 5.92)
    elL = V(3.38, 0.50, 4.10)
    wrL = V(3.62, 1.15, 2.78)
    ac = AAcc('armClaw')
    cables(ac, shL, elL, n=5, r=0.14, R_=0.22, turns=0.6, surf=C['cable'], seed=910)
    slab(ac, shL.lerp(elL, 0.35) + V(0.22, 0.0, 0.1), (0.42, 0.70, 0.60), C['concrete'], M_=R('Y', 16), seed=912)
    cr.part('ArmClaw', ac, shL, parent='Torso')
    fc = AAcc('foreClaw')
    cables(fc, elL, wrL, n=4, r=0.12, R_=0.16, turns=0.6, surf=C['cable_dk'], seed=920)
    fc.cyl_between(elL.lerp(wrL, 0.35), elL.lerp(wrL, 0.80), 0.24, C['steel_dk'], 16, caps=True)
    for t in (0.38, 0.77):
        ring(fc, elL.lerp(wrL, t), wrL - elL, 0.27, 0.08, 0.05, C['rust_dk'], segs=16)
    cr.part('ForeClaw', fc, elL, parent='ArmClaw')
    hc = AAcc('handClaw')
    blob(hc, wrL + V(0.05, 0.18, -0.12), (0.28, 0.30, 0.24), C['steel_dk'], e=(0.6, 0.8), segs=14, rings=8)
    for i, ang in enumerate((-36, -12, 12, 36)):
        a = math.radians(ang)
        base = wrL + V(0.20 * math.sin(a), 0.38, -0.22)
        mid = base + V(0.22 * math.sin(a), 0.30, -0.30)
        tip = mid + V(0.10 * math.sin(a), -0.05, -0.75)
        limb(hc, [base, mid], [0.08, 0.07], C['cable_dk'], segs=8, per=2)
        ring(hc, mid, mid - base, 0.085, 0.06, 0.03, C['rust_dk'], segs=10)
        horn(hc, mid, tip, 0.075, C['claw'], bend=V(0, 0.22, 0.05), segs=8, n=6)
    horn(hc, wrL + V(-0.18, 0.25, -0.20), wrL + V(-0.36, 0.55, -0.70), 0.07, C['claw'], bend=V(-0.05, 0.12, 0.05), segs=8, n=6)
    cr.part('HandClaw', hc, wrL, parent='ForeClaw')
    return cr


BUILDERS = {'pecker': ash_pecker, 'reaper': snow_reaper, 'walker': needle_walker, 'boiler': boiler_spitter,
            'executioner': executioner, 'raider': whiteout_raider, 'reactor': black_reactor}
# parts that cast shadows (others: small details, glow cores)
SHADOW_PARTS = {}


def apply_shadows(cr):
    keep = SHADOW_PARTS.get(cr.name)
    if keep is None:
        return
    for o in cr.parts:
        if o.get('mut_part') not in keep:
            o['tw_no_shadow'] = True
