"""Gameplay layout from the v10 export metadata (scene['roadgame_source_metadata']), in Blender XY.
Used to keep new decoration off roads, ramps/run-ups/landings, routes, keep-out areas and spawns.
Unity (x, y, z) -> Blender (x, z, y)."""
import bpy, json, math
import numpy as np


class Level:
    def __init__(self, scene=None):
        sc = scene or bpy.context.scene
        md = json.loads(sc['roadgame_source_metadata'])
        self.md = md
        self.roads = []
        for r in md['roads']:
            if r.get('zone', 0) != 0:
                continue
            p = r['points']
            pts = np.array([(p[i], p[i + 2]) for i in range(0, len(p), 3)], np.float64)
            self.roads.append((pts, float(r['width'])))
        self.floors = [f for f in md['floors']]
        self.keepouts = md['keepouts']
        self.holes = md['holes']
        def poly(flat):
            return np.array([(flat[i], flat[i + 2]) for i in range(0, len(flat), 3)], np.float64)
        self.routes = [(poly(md['worksRoute']), 10.0), (poly(md['mesaRoute']), 6.5)]
        self.spawns = [(s['position'][0], s['position'][2], s.get('radius', 1.0), s.get('kind', ''), s.get('name', ''))
                       for s in md['spawns'] if s.get('zone', 0) == 0]
        self.player_start = (md['playerStart'][0], md['playerStart'][2])

    @staticmethod
    def _seg_dist(pts, x, y):
        a = pts[:-1]; b = pts[1:]
        d = b - a; L2 = (d ** 2).sum(1) + 1e-9
        t = np.clip(((x - a[:, 0]) * d[:, 0] + (y - a[:, 1]) * d[:, 1]) / L2, 0, 1)
        px = a[:, 0] + t * d[:, 0]; py = a[:, 1] + t * d[:, 1]
        return float(np.sqrt((px - x) ** 2 + (py - y) ** 2).min())

    def road_clearance(self, x, y):
        """Distance from (x,y) to the nearest road edge (negative = on the road)."""
        best = 1e9
        for pts, w in self.roads:
            best = min(best, self._seg_dist(pts, x, y) - w / 2)
        return best

    @staticmethod
    def in_rect(x, y, center, half, yaw_deg, margin=0.0):
        cx, cy = center[0], center[2]
        dx, dy = x - cx, y - cy
        a = math.radians(yaw_deg)
        lx = dx * math.cos(a) - dy * math.sin(a)
        ly = dx * math.sin(a) + dy * math.cos(a)
        return abs(lx) <= half[0] + margin and abs(ly) <= half[1] + margin

    def on_floor(self, x, y, margin=0.0):
        for f in self.floors:
            r = f['rect']
            if self.in_rect(x, y, r['center'], r['half'], r.get('yaw', 0), margin):
                return f['name']
        return None

    def in_keepout(self, x, y, margin=0.0):
        for k in self.keepouts:
            if self.in_rect(x, y, k['center'], k['half'], k.get('yaw', 0), margin):
                return True
        return False

    def near_route(self, x, y, margin=0.0):
        for pts, w in self.routes:
            if self._seg_dist(pts, x, y) < w / 2 + margin:
                return True
        return False

    def near_spawn(self, x, y, margin=0.5, kinds=('Enemy', 'Boss', 'Pickup', 'Chest')):
        for sx, sy, r, k, n in self.spawns:
            if any(t.lower() in k.lower() for t in kinds) and math.hypot(x - sx, y - sy) < r + margin:
                return True
        return False

    def clear_for_decor(self, x, y, road_margin=1.5, floor_margin=1.5, keepout=True, route_margin=1.5):
        """True if a new decoration at (x,y) does not touch a gameplay lane."""
        if self.road_clearance(x, y) < road_margin:
            return False
        if self.on_floor(x, y, floor_margin):
            return False
        if keepout and self.in_keepout(x, y, 0.0):
            return False
        if self.near_route(x, y, route_margin):
            return False
        return True
