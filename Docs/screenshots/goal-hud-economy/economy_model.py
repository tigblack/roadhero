"""v10 economy check: price -> result tables, time saved, bonus compounding (old vs new). Zone 1 (Dust Flats) scale."""
FARM_D, FARM_H = 3.0, 14.0          # per minute, measured (stock autopilot, 10 min, clean save)
CRIT = 1 + 0.10 * 0.5               # average crit factor
GUN_INT = 0.62
MAMMOTH = 4000
READY = round(MAMMOTH / (90 / GUN_INT * CRIT))   # 26
def m(L): return 1 + 0.3 * (L - 1)
def copies_for(L): return 2 * max(1, L)
def level_cost(L, c): return 25 * max(1, copies_for(L) - max(0, c))
def add_copies(L, c, n):
    c += n
    while c >= copies_for(L): c -= copies_for(L); L += 1
    return L, c

print("READY hit for the Mammoth:", READY)
print()
print("## A. Price -> result (one weapon, the hood gun)")
print("| state | buy | gems | result | hit x |")
print("|---|---|---|---|---|")
for (L, c) in [(1, 0), (1, 1), (2, 0), (2, 3), (3, 0), (4, 0), (5, 0)]:
    st = f"Lv{L}, {c}/{copies_for(L)} copies"
    lc = level_cost(L, c)
    print(f"| {st} | level up | {lc} | Lv{L+1}, 0 copies | x{m(L+1)/m(L):.2f} |")
    L2, c2 = add_copies(L, c, 3)
    print(f"| {st} | Weapon Crate (3) | 60 | Lv{L2}, {c2}/{copies_for(L2)} | x{m(L2)/m(L):.2f} |")
    L3, c3 = add_copies(L, c, 15)
    print(f"| {st} | Big Crate (15) | 250 | Lv{L3}, {c3}/{copies_for(L3)} | x{m(L3)/m(L):.2f} |")
print()
# reaching Lv3 from Lv1/0 by different paths
paths = {"direct 50 + 100": 150, "crate 60 + level 75 (3 missing)": 60 + level_cost(2, 1), "two crates": 120}
print("## A2. Lv1 -> Lv3 (x1.6):", "; ".join(f"{k} = {v}" for k, v in paths.items()))
print()

print("## B. What a purchase is worth, in farm minutes (FM = 3 dmg or 14 HP of the zone; farm 3 dmg/min + bonus 0.75/min)")
r = FARM_D + 0.75
def lvl_value(D, L, H):
    """minutes earlier you reach the same hood-gun hit after H more minutes of farming"""
    return (D + r * H) * (m(L + 1) / m(L) - 1) / r
print("| purchase | gems | when | now | after +10 min | after +20 min | per 100 gems (+10 min) |")
print("|---|---|---|---|---|---|---|")
rows = [("Lv1->2", 50, 6.5, 1, "landing (base 6.5)"), ("Lv2->3", 100, 14, 2, "mid zone (base 14)"), ("Lv3->4", 150, 22, 3, "late zone (base 22)"), ("Lv4->5", 200, 30, 4, "zone end (base 30)")]
for name, g, D, L, when in rows:
    v0, v10, v20 = lvl_value(D, L, 0), lvl_value(D, L, 10), lvl_value(D, L, 20)
    print(f"| {name} | {g} | {when} | {v0:.1f} | {v10:.1f} | {v20:.1f} | {v10/g*100:.1f} |")
pack = 15 / r
print(f"| Damage Pack +15 | 150 | any time | {pack:.1f} | {pack:.1f} | {pack:.1f} | {pack/150*100:.1f} |")
print(f"| Armor Plating +70 HP | 150 | any time | 5.0 (HP) | 5.0 | 5.0 | 3.3 |")
print(f"| free bonus +3 dmg / +14 HP | 0 | every 2 min | 1.0 | 1.0 | 1.0 | - |")
print()

print("## C. Time to boss-ready after the landing: hit >= %d (or the same dps) AND max HP >= (9.4 - regen) x fight(85%% gun time) / 0.7" % READY)
FARM_REGEN = 0.23     # regen per second gained per minute of farming (1 -> 3.3 in 10 min)
BOSS_DPS = 16 / 1.7   # nominal regular blows (measured 7.65-9.3/s on the non-dodging bot)
def ready_time(L, with_bonus=True, dmg0=6.5, hp0=100.0, regen0=1.0, extra_d=0.0, extra_h=0.0):
    D, H, R = dmg0 + extra_d, hp0 + extra_h, regen0
    t, nxt, kind = 0.0, 0.5, 0          # first bonus offer about half a minute after the landing (45 s into the game)
    while t < 40:
        hit = D * m(L)
        dps = hit * CRIT / GUN_INT
        fight = MAMMOTH / (dps * 0.85)          # the guns are on the boss ~85 % of the fight
        need = max(0.0, BOSS_DPS - R) * fight / 0.7   # come out with >= 30 % HP
        if (hit >= READY or dps >= MAMMOTH / 90) and H >= need: return t, hit, H, need
        dt = 1 / 60
        D += FARM_D * dt; H += FARM_H * dt; R += FARM_REGEN * dt
        if with_bonus and t >= nxt:
            if kind == 0: H += 14
            else: D += 3
            kind = 1 - kind; nxt = t + 2.0
        t += dt
    return None, 0, 0, 0
print("| choice | gems | minutes to ready | hit / HP at that moment | HP needed |")
print("|---|---|---|---|---|")
for name, L, wb, xd, xh, g in [("nothing", 1, True, 0, 0, 0), ("Lv2 at the landing (the guided step)", 2, True, 0, 0, 50),
                               ("Lv2, no bonus claims", 2, False, 0, 0, 50), ("Lv2 + Armor Plating +70 HP (200)", 2, True, 0, 70, 200),
                               ("Lv2 + Damage Pack +15 (200)", 2, True, 15, 0, 200)]:
    tr, hit, H, need = ready_time(L, wb, extra_d=xd, extra_h=xh)
    print(f"| {name} | {g} | {tr:.1f} | {hit:.1f} / {H:.0f} | {need:.0f} |")
print()
print("## D. Free bonus: compounding old (+35% dmg / +60% HP of the current value, every 100 s) vs new (1 FM flat, every 120 s)")
def sim(kind, minutes=30.0, dt=1.0):
    D, H = 5.5, 100.0
    t, nxt, k = 0.0, 45.0, 0          # first offer 45 s in, HP first
    out = {}
    while t <= minutes * 60 + 1e-6:
        if abs(t / 60 - round(t / 60)) < 1e-9 and round(t / 60) in (5, 10, 20, 30): out[int(round(t / 60))] = (D, H)
        D += FARM_D / 60 * dt; H += FARM_H / 60 * dt
        if kind and t >= nxt:
            if kind == "old":
                if k == 0: H += max(20, round(H * 0.6))
                else: D += max(2, round(D * 0.35, 1))
                nxt = t + 100
            else:
                if k == 0: H += 14
                else: D += 3.0
                nxt = t + 120
            k = 1 - k
        t += dt
    return out
F, O, N = sim(None), sim("old"), sim("new")
print("| minute | farm only: dmg / HP | old bonus: dmg / HP | new bonus: dmg / HP |")
print("|---|---|---|---|")
for mi in (5, 10, 20, 30):
    print(f"| {mi} | {F[mi][0]:.1f} / {F[mi][1]:.0f} | {O[mi][0]:.1f} / {O[mi][1]:.0f} | {N[mi][0]:.1f} / {N[mi][1]:.0f} |")
print()
print("bonus share of the damage at 30 min: old %.0f%%, new %.0f%%" % ((O[30][0] - F[30][0]) / O[30][0] * 100, (N[30][0] - F[30][0]) / N[30][0] * 100))
print("bonus share of max HP at 30 min: old %.0f%%, new %.0f%%" % ((O[30][1] - F[30][1]) / O[30][1] * 100, (N[30][1] - F[30][1]) / N[30][1] * 100))
print()
print("## E. Gems in zone 1: landing 50 + free 20 (every 4 h) + 2 stashes x 25 + Mammoth 50 = 170 -> e.g. Lv2 (50) + Lv3 (100) + 20 spare")
