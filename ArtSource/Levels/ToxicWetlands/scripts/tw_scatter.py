"""Toxic Wetlands scatter: vegetation, debris and industrial clusters placed from the layout fields.

Rules use the same fields as the water layout (tw_layout.build): sdf (signed distance to the shoreline, negative in
water), h (ground height) and clear (distance to roads, spawns, structures, camps, the arena island). Nothing is
placed where clear < its footprint, so gameplay objects, roads and the fight space stay free.
* small decor (reeds, tufts, algae mats, puddles, stumps, mushrooms) is merged per 25 m tile (no colliders),
* trees, drums, sunk cars, tanks, pumps, outfalls, pipelines and boardwalks are shared-mesh instances; the solid
  ones get collision proxies (trees: trunk boxes).
Deterministic (fixed seeds).
"""
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import tw_env as EV
import tw_layout as LY
import tw_lib as L
from tw_env import E, R, S, SC, T, V
from tw_structures import add_collider, new_obj, zone_coll

TILE = 25.0


def merged_tiles(coll_name):
    c = bpy.data.collections.get(coll_name)
    if c is None:
        c = bpy.data.collections.new(coll_name)
        zone_coll().children.link(c)
    return c


class TileDecor:
    """Per-tile accumulation of small decor (copies of kit meshes with transforms)."""

    def __init__(self, prefix='TW_Decor', shadows=True):
        self.tiles = {}
        self.prefix = prefix
        self.shadows = shadows

    def add(self, mesh, M):
        x, y = M.translation.x, M.translation.y
        key = (int(math.floor((x + 100) / TILE)), int(math.floor((y - 100) / TILE)))
        a = self.tiles.get(key)
        if a is None:
            a = L.Acc('%s_%d_%d' % ((self.prefix,) + key))
            self.tiles[key] = a
        pt = L._Part()
        pt.bm.from_mesh(mesh)
        faces = list(pt.bm.faces)
        for f in faces:
            f.material_index = 0
        a.transform(faces, M, pt)
        a.mat_index('TW_Trim')
        a._commit(pt)

    def build(self, coll):
        out = []
        tris = 0
        for key, a in sorted(self.tiles.items()):
            me = a.build()
            o = L.new_object(me.name, me, coll)
            o['tw_role'] = 'decor'
            o['tw_no_shadow'] = not self.shadows
            tris += L.tri_count(me)
            out.append(o)
        return out, tris


def build(scene_json):
    xs, zs, h, sdf, tox, clear, stats, issues = LY.build(scene_json)
    lvl = LY.LEVEL

    def field(arr, x, z):
        ix = int(round((x - LY.X0) / LY.STEP)); iz = int(round((z - LY.Z0) / LY.STEP))
        if ix < 0 or iz < 0 or ix >= len(xs) or iz >= len(zs):
            return None
        return float(arr[iz, ix])

    rnd = random.Random(2026)
    deco = TileDecor('TW_Decor', True)
    flat = TileDecor('TW_DecorFlat', False)
    coll = merged_tiles('Zone_01 — Swamp decor (merged per 25 m tile)')
    inst = merged_tiles('Zone_01 — Swamp props (instances)')
    # kit meshes (shared)
    reeds = [EV.reed_clump_lite(10 + k, radius=0.5 + 0.12 * (k % 3), height=1.4 + 0.25 * (k % 2), cattails=1 + k % 3, dry=0.2 + 0.15 * k) for k in range(4)]
    tufts = [EV.grass_tuft(20 + k) for k in range(3)]
    algae = [EV.lily_mat(30 + k, 0.8 + 0.4 * k) for k in range(3)]
    algae_tox = [EV.lily_mat(35 + k, 0.9 + 0.3 * k, toxic=True) for k in range(2)]
    stumps = [EV.stump(40 + k, 0.32 + 0.08 * k, 0.55 + 0.25 * k) for k in range(3)]
    shrooms = [EV.glow_shrooms(50 + k) for k in range(2)]
    puddles = [EV.puddle(60 + k, 0.9 + 0.5 * k) for k in range(3)]
    logs = [EV.fallen_log(70 + k, 3.8 + k, 0.25 + 0.05 * k) for k in range(2)]
    trees = [EV.dead_tree(80 + k, height=4.6 + 0.8 * k, broken=(k == 3), lean=4 + 3 * k) for k in range(5)]
    drums = [EV.drum('yel', 'sunk', 1), EV.drum('olive', 'tipped', 2), EV.drum('blue', 'sunk', 3), EV.drum('rust', 'upright', 4),
             EV.drum('yel', 'upright', 5, leak=True), EV.drum('red', 'tipped', 6)]
    sunk_car = [EV.car_roof(90 + k) for k in range(2)]
    boulders = [EV.boulder(95 + k, 0.8 + 0.3 * k) for k in range(3)]
    counts = {}
    trunks = []

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    def spot_ok(x, z, need):
        c = field(clear, x, z)
        return c is not None and c >= need

    # --- jittered grid sweep (2 m)
    for z in np.arange(LY.Z0 + 2.0, LY.Z1 - 2.0, 2.0):
        for x in np.arange(LY.X0 + 2.0, LY.X1 - 2.0, 2.0):
            px, pz = x + rnd.uniform(-0.9, 0.9), z + rnd.uniform(-0.9, 0.9)
            d = field(sdf, px, pz)
            hh = field(h, px, pz)
            if d is None:
                continue
            yaw = rnd.uniform(0, 360)
            M = lambda zz=0.0, s=1.0: T(V(px, pz, zz)) @ R('Z', yaw) @ SC(s, s, s)
            near_edge = abs(px) > 84.0
            if -1.6 < d < 1.4 and spot_ok(px, pz, 0.6):
                if rnd.random() < (0.17 if not near_edge else 0.3):
                    deco.add(reeds[rnd.randrange(4)], M(hh, rnd.uniform(0.8, 1.25))); bump('reeds')
                    continue
            if -5.0 < d < -1.0 and rnd.random() < 0.06:
                t = field(tox, px, pz) or 0.0
                mesh = algae_tox[rnd.randrange(2)] if t > 0.4 else algae[rnd.randrange(3)]
                flat.add(mesh, M(lvl, rnd.uniform(0.8, 1.4))); bump('algae')
                continue
            if (-3.2 < d < -0.4 and rnd.random() < 0.06 or 0.5 < d < 4.0 and rnd.random() < 0.05) and spot_ok(px, pz, 2.5):
                # merged into the tile decor; its trunk collider sits on a collider-only node
                s = rnd.uniform(0.85, 1.22)
                deco.add(trees[rnd.randrange(5)], T(V(px, pz, hh - 0.05)) @ R('Z', yaw) @ SC(s, s, s))
                trunks.append(V(px, pz, hh))
                bump('tree')
                continue
            if 0.4 < d < 3.0 and rnd.random() < 0.035 and spot_ok(px, pz, 1.2):
                deco.add(stumps[rnd.randrange(3)], M(hh - 0.03, rnd.uniform(0.8, 1.15))); bump('stump')
                if rnd.random() < 0.3:
                    deco.add(shrooms[rnd.randrange(2)], T(V(px + 0.8, pz + 0.3, hh)) @ R('Z', yaw)); bump('shrooms')
                continue
            if -2.5 < d < -0.6 and rnd.random() < 0.025 and spot_ok(px, pz, 2.0):
                deco.add(logs[rnd.randrange(2)], M(lvl - 0.12, 1.0)); bump('log')
                continue
            if -2.8 < d < -0.8 and rnd.random() < 0.018 and spot_ok(px, pz, 1.4):
                deco.add(drums[rnd.randrange(3)], M(lvl + 0.05, 1.0)); bump('sunk_drum')
                continue
            if d > 3.0 and rnd.random() < 0.035 and spot_ok(px, pz, 0.8):
                deco.add(tufts[rnd.randrange(3)], M(0.0, rnd.uniform(0.8, 1.4))); bump('tuft')
                continue
            if d > 3.0 and rnd.random() < 0.006 and spot_ok(px, pz, 1.5):
                flat.add(puddles[rnd.randrange(3)], M(0.0, rnd.uniform(0.8, 1.3))); bump('puddle')
                continue
            if d > 2.0 and rnd.random() < 0.004 and spot_ok(px, pz, 2.0):
                deco.add(boulders[rnd.randrange(3)], M(-0.1, rnd.uniform(0.7, 1.0))); bump('boulder')
                continue
            if near_edge and d > 0.0 and rnd.random() < 0.05 and spot_ok(px, pz, 1.0):
                deco.add(reeds[rnd.randrange(4)], M(hh, rnd.uniform(1.0, 1.4))); bump('edge_reeds')
    # --- hand-placed industrial clusters at the toxic hotspots (outfall + drums), checked for clearance
    for k, (tx, tz, tr) in enumerate(LY.TOXIC):
        if math.hypot(tx - LY.ARENA[0], tz - LY.ARENA[1]) < 40:
            continue
        best = None
        for ring in (3.0, 4.5, 6.0, 7.5):
            for a_ in range(0, 360, 20):
                px, pz = tx + math.sin(math.radians(a_)) * ring, tz + math.cos(math.radians(a_)) * ring
                d = field(sdf, px, pz); c = field(clear, px, pz)
                if d is not None and 0.6 < d < 2.2 and c is not None and c >= 3.2:
                    best = (px, pz, a_)
                    break
            if best:
                break
        if not best:
            continue
        px, pz, a_ = best
        yaw = (a_ + 180.0) % 360.0 - 90.0     # the outfall points into the pool (its local +x)
        o = new_obj('TW_Outfall_%d' % k, EV.outfall(200 + k), coll=inst)
        o.location = (px, pz, 0.0); o.rotation_euler = (0, 0, math.radians(yaw))
        bpy.context.view_layer.update()
        add_collider(o, [(o.matrix_world @ V(-1.6, 0, 0.5), (3.2, 1.4, 1.0), yaw)])
        bump('outfall')
        for j in range(3):
            ang = math.radians(a_ + 60 + j * 40)
            qx, qz = px + math.sin(ang) * 2.2, pz + math.cos(ang) * 2.2
            if spot_ok(qx, qz, 1.0):
                od = new_obj('TW_ToxDrum_%d_%d' % (k, j), drums[3 + j % 3], coll=inst)
                od.location = (qx, qz, field(h, qx, qz) or 0.0); od.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
                bpy.context.view_layer.update()
                add_collider(od, [(od.matrix_world.translation + V(0, 0, 0.45), (0.75, 0.75, 0.9), 0.0)])
                bump('drum')
    # --- storage tanks / pump units on dry ground near three pools (found by search)
    def find_dry(cx, cz, need, rmax=14.0):
        for ring in np.arange(2.0, rmax, 1.5):
            for a_ in range(0, 360, 15):
                px, pz = cx + math.sin(math.radians(a_)) * ring, cz + math.cos(math.radians(a_)) * ring
                d = field(sdf, px, pz); c = field(clear, px, pz)
                if d is not None and d > 1.8 and c is not None and c >= need:
                    return px, pz
        return None
    for k, (cx, cz, kind) in enumerate(((-62, 124, 'tank'), (62, 120, 'pump'), (-84, 214, 'tank'), (40, 284, 'pump'), (86, 150, 'car'), (-74, 255, 'car'))):
        spot = find_dry(cx, cz, 4.0 if kind == 'tank' else 2.6)
        if not spot:
            continue
        px, pz = spot
        if kind == 'tank':
            me = EV.storage_tank(300 + k, 2.4, 4.2, 'tank' if k % 2 else 'tank_dk')
            o = new_obj('TW_Tank_%d' % k, me, coll=inst)
            o.location = (px, pz, 0.0); o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
            bpy.context.view_layer.update()
            add_collider(o, [(o.matrix_world.translation + V(0, 0, 2.4), (5.4, 5.4, 4.8), 0.0), (o.matrix_world.translation + V(0, 0, 2.4), (5.4, 5.4, 4.8), 45.0)])
        elif kind == 'pump':
            o = new_obj('TW_Pump_%d' % k, EV.pump_unit(300 + k), coll=inst)
            o.location = (px, pz, 0.0); o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
            bpy.context.view_layer.update()
            add_collider(o, [(o.matrix_world @ V(0, 0, 0.9), (3.1, 2.1, 1.8), math.degrees(o.rotation_euler.z))])
        else:
            o = new_obj('TW_SunkCar_%d' % k, sunk_car[k % 2], coll=inst)
            d = field(sdf, cx, cz)
            o.location = (cx, cz, lvl); o.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
            bpy.context.view_layer.update()
            add_collider(o, [(o.matrix_world @ V(0, 0, 0.5), (1.9, 3.7, 1.2), math.degrees(o.rotation_euler.z))])
        bump(kind)
    # --- boardwalks over narrow channels, pipelines over pools
    for k, (a_pts) in enumerate(((-80, 175), (84, 218), (-48, 120), (8, 250))):
        px, pz = a_pts
        if field(sdf, px, pz) is None or field(sdf, px, pz) > 0:
            continue
        o = new_obj('TW_Boardwalk_%d' % k, EV.boardwalk(400 + k, 7.0, 1.5, 0.3), coll=inst)
        o.location = (px, pz, lvl + 0.02)
        o.rotation_euler = (0, 0, math.radians(90 if abs(px) > 70 else 0))
        bump('boardwalk')
    pipes = [[(-70, 236, 1.2), (-74, 248, 1.2), (-70, 262, 1.2)], [(72, 222, 1.3), (80, 236, 1.3), (82, 250, 1.3)], [(52, 112, 1.2), (66, 118, 1.2), (80, 132, 1.2)]]
    for k, pts in enumerate(pipes):
        ok = all(spot_ok(ax + (bx - ax) * t, az + (bz - az) * t, 1.6) for (ax, az, _), (bx, bz, _) in zip(pts[:-1], pts[1:]) for t in np.linspace(0.0, 1.0, 9))
        if not ok:
            continue
        me = EV.pipe_run(500 + k, [V(*p) for p in pts], 0.4, 5.0, name='TW_SwampPipe_%d' % k)
        o = new_obj('TW_SwampPipe_%d' % k, me, coll=inst)
        boxes = []
        for (ax, az, ah), (bx, bz, bh) in zip(pts[:-1], pts[1:]):
            mid = V((ax + bx) / 2, (az + bz) / 2, 1.0)
            ln = math.hypot(bx - ax, bz - az)
            boxes.append((mid, (ln, 1.4, 2.2), math.degrees(math.atan2(bz - az, bx - ax))))
        add_collider(o, boxes)
        bump('pipeline')
    objs, tris = deco.build(coll)
    fobjs, ftris = flat.build(coll)
    counts['decor_tiles'] = len(objs) + len(fobjs)
    counts['decor_tris'] = tris + ftris
    # trunk colliders: empties named TW_TreeTrunks_<tile> carrying one proxy each (all trunks of the tile)
    by_tile = {}
    for p in trunks:
        key = (int(math.floor((p.x + 100) / 25.0)), int(math.floor((p.y - 100) / 25.0)))
        by_tile.setdefault(key, []).append(p)
    for key, pts in by_tile.items():
        e = bpy.data.objects.new('TW_TreeTrunks_%d_%d' % key, None)
        inst.objects.link(e)
        e['editing_zone'] = 1
        e['tw_stage'] = 'collider-only node: dead tree trunks of this tile'
        add_collider(e, [(p + V(0, 0, 1.5), (0.6, 0.6, 3.0), 0.0) for p in pts])
    counts['trunk_collider_nodes'] = len(by_tile)
    print('TW_SCATTER', counts, flush=True)
    return counts
