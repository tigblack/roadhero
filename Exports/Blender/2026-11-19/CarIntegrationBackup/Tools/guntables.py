"""Builds the hood machine gun's pitch tables (Turret.BarrelYaw/BarrelPitch, FireYaw/FirePitch) from a "cannoncheck" log.

The capture measures, every 2 degrees of yaw (-180..180), the lowest safe pitch of the gun's front parts (`gun`), of the
muzzle flash (`flash`) and of a round's straight launch run (`run`), and the highest raise the stock and grip allow
(`up`), and writes one `RoadGame GUNCHECK` line per yaw. This script keeps the tables 1-2 degrees inside what was
measured: near a cliff (the measurement jumps between two samples) the lower neighbour counts, and the knots are
chosen greedily so the linear table stays inside that band everywhere.

usage: python3 Tools/guntables.py <cannoncheck_log.txt>      (paste the printed arrays into Turret.cs)
run the check: Unity -batchmode -disableaudio -projectPath <project> -executeMethod RoadGame.EditorTools.AutoCapture.Run
               -captureScenario cannoncheck -captureTimes 25 -captureOut <dir> -captureQuality 0
"""
import re
import sys

LO, HI = 1.0, 2.0   # the table stays between (measured - HI) and (measured - LO) degrees

rows = {}
for line in open(sys.argv[1], errors='ignore'):
    m = re.search(r'GUNCHECK yaw=(-?\d+) gun=(-?[\d.]+) flash=(-?[\d.]+) run=(-?[\d.]+) up=(-?[\d.]+)', line)
    if m:
        g, f, r, u = (float(m.group(i)) for i in range(2, 6))
        rows[int(m.group(1))] = (g, min(g, f, r), u)
if not rows:
    sys.exit('no GUNCHECK lines in ' + sys.argv[1])
ys = sorted(rows)


def guard(v):
    """the measurement is every 2 deg: near a cliff the safe value between two samples can be the lower one"""
    return {y: min(v[ys[k]] for k in (i - 1, i, i + 1) if 0 <= k < len(ys)) for i, y in enumerate(ys)}


def greedy(vals):
    target = {y: vals[y] - (LO + HI) * 0.5 for y in ys}
    kx, kv = [ys[0]], [target[ys[0]]]
    i = 0
    while i < len(ys) - 1:
        best = None
        for j in range(i + 1, len(ys)):
            a, b = ys[i], ys[j]
            va, vb = kv[-1], target[b]
            ok = all(vals[ys[k]] - HI - 1e-6 <= va + (vb - va) * (ys[k] - a) / (b - a) <= vals[ys[k]] - LO + 1e-6 for k in range(i, j + 1))
            if ok:
                best = j
            elif best is not None and j - best > 3:
                break
        if best is None:
            best = i + 1
        kx.append(ys[best]); kv.append(target[ys[best]])
        i = best
    worst = 99.0
    for y in ys:
        for n in range(1, len(kx)):
            if y <= kx[n]:
                t = kv[n - 1] + (kv[n] - kv[n - 1]) * (y - kx[n - 1]) / (kx[n] - kx[n - 1])
                break
        worst = min(worst, vals[y] - t)
    return kx, kv, worst


def arr(name, v):
    return 'static readonly float[] %s = { %s };' % (name, ', '.join('%gf' % round(x, 2) for x in v))


bx, bv, bw = greedy(guard({y: rows[y][0] for y in ys}))
fx, fv, fw = greedy(guard({y: rows[y][1] for y in ys}))
up = {y: rows[y][2] for y in ys}
print(arr('BarrelYaw', bx)); print(arr('BarrelPitch', bv))
print(arr('FireYaw', fx)); print(arr('FirePitch', fv))
least = max(up, key=up.get)
print('// knots: barrel %d, fire %d; worst margin: barrel %.2f, fire %.2f deg' % (len(bx), len(fx), bw, fw))
print('// the stock / grip allow raising the gun to %.1f deg at worst (yaw %d): keep Turret.MaxUp above that' % (-up[least], least))
