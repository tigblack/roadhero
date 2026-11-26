using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// The player's next meaningful goal after the intro, for the goal widget (title = the goal and what it gives,
    /// sub = the step towards it right now) and the route pointer:
    ///  1. the first weapon level, paid by the landing reward: one clear step of growth before the boss;
    ///  2. "see it": the next hits on something close show the new number;
    ///  3. the zone boss -> its weapon, with a readiness mark (per-hit damage that beats it in ~90 s) and a route along
    ///     the road to the Mammoth Works turn-off, down the ramp, through the tunnel into the hangar;
    ///  4. "try the new weapon" on a group (the nearest camp) until it lands a hit that shows what it does;
    ///  5. the next zone's boss, ... and finally free play.
    /// Free driving is never blocked: the widget only says what to come back to.
    /// </summary>
    public static class Goals
    {
        public enum Kind { None, Upgrade, SeeUpgrade, Boss, TryWeapon, Done }

        public class Goal
        {
            public Kind kind;
            public string title, sub;
            public Icon icon;
            public bool hasTarget;
            public Vector3 target;                   // where the pointer leads (the next point of the way)
            public Vector3 destination;              // the goal itself (minimap icon, distance)
            public float distance;                   // along the way when there is a route
            public bool ready;                       // boss: strong enough
            public int zone;
        }

        static readonly Goal current = new Goal();
        static readonly List<Vector3> route = new List<Vector3>();
        static readonly List<Vector3> exitRoute = new List<Vector3>();
        static int routeFor = -1;
        /// <summary>The way the pointer follows this frame (to the boss, or out of the hangar); null when none.</summary>
        public static List<Vector3> ActiveRoute { get; private set; }

        /// <summary>Session time until which the "see the new damage" step lasts after a purchase.</summary>
        public static float SeeUpgradeUntil = -1f;
        public static int SeeUpgradeWeapon = -1;
        public static double SeeUpgradeFrom, SeeUpgradeTo;

        // a drivable way back to the route (or to the crowd) from off it, re-planned on the NavGrid twice a second
        static readonly List<Vector3> way = new List<Vector3>();
        static readonly List<Vector3> wayPlus = new List<Vector3>();
        static float wayAt = -99f;
        static Vector3 wayFrom;
        static int wayFor = int.MinValue;
        static bool wayOk;
        static bool onWay;    // following the drivable way back: until the car is really on the route again (hysteresis)

        // the nearest group for "try the new weapon" (re-picked twice a second)
        static Vector3 groupAt;
        static bool groupFound;
        static float groupPicked = -99f;

        /// <summary>Also called by Game.ResetProgress: a new game must not inherit the old one's steps or timers.</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void ResetStatics()
        {
            route.Clear(); exitRoute.Clear(); routeFor = -1; ActiveRoute = null; textAt = -99f; textKind = Kind.None; textZone = -2;
            current.title = current.sub = null;
            SeeUpgradeUntil = -1f; SeeUpgradeWeapon = -1; groupPicked = -99f; groupFound = false;
            way.Clear(); wayPlus.Clear(); wayAt = -99f; wayFor = int.MinValue; wayOk = false; onWay = false;
        }

        // Russian names for the guidance (item names stay as in the garage)
        public static readonly string[] BossAcc = { "МАМОНТА", "МАТКУ ТРЯСИНЫ", "ЧЁРНЫЙ РЕАКТОР", "ПОЛКОВОДЦА" };
        public static readonly string[] WeaponWhat = { "очередь по одной цели", "удар по площади", "дальний колющий удар", "взрыв по большой площади" };

        /// <summary>What beating a zone's boss gives, in a few words.</summary>
        public static string RewardShort(int zone)
        {
            var z = Content.Zones[zone];
            if (z.unlockWeapon >= 0) return Content.Weapons[z.unlockWeapon].name + ": " + WeaponWhat[z.unlockWeapon];
            if (z.unlockArmor >= 0) return Content.Armors[z.unlockArmor].name;
            if (zone + 1 < Content.ZoneCount) return "путь в " + Content.Zones[zone + 1].name;
            return "титул покорителя пустоши";
        }

        static string MainTitle(int zb) => zb >= 0 ? BossTitle(zb) : "Пустошь покорена";

        /// <summary>"Победи МАМОНТА →" / "Pipe Hammer: удар по площади" (two lines: the reward's name never breaks).</summary>
        public static string BossTitle(int zone) => "Победи " + BossAcc[zone] + " →\n" + RewardShort(zone);

        /// <summary>The lowest zone whose boss was never beaten (the gates on the way are open), -1 when all are.</summary>
        public static int NextBoss(SaveData d)
        {
            for (int z = 0; z <= Mathf.Min(d.unlockedZone, Content.ZoneCount - 1); z++) if (d.bossKills[z] == 0) return z;
            return -1;
        }

        static float textAt = -99f;
        static Kind textKind = Kind.None;
        static int textZone = -2;
        static bool textReady;
        /// <summary>Texts are rebuilt when the step or "ready" changes and 4 times a second otherwise (no strings every frame).</summary>
        static bool NeedText(Goal c, Kind k)
        {
            float now = Time.unscaledTime;
            if (k != textKind || c.zone != textZone || c.ready != textReady || now - textAt > 0.25f || c.title == null)
            {
                textKind = k; textZone = c.zone; textReady = c.ready; textAt = now;
                return true;
            }
            return false;
        }

        /// <summary>The goal of this frame (call once per frame; cheap).</summary>
        public static Goal Evaluate(Game g)
        {
            var c = current;
            c.hasTarget = false; c.ready = false; c.zone = -1; c.distance = 0f;
            ActiveRoute = null;
            var d = g.progress.d;
            var p = g.player.Pos;
            if (DevTravel.IntroRunning(d)) { c.kind = Kind.None; return c; }
            int zb = NextBoss(d);
            // a DEV test visit to a zone the save has not unlocked: that zone's boss (the visit counts no progress)
            bool testVisit = DevTravel.InTestZone(g);
            if (testVisit) zb = Content.ZoneIndexAt(p.z);

            // a weapon just unlocked: try it where it shines (it is what the boss just gave)
            if (d.tryWeapon >= 0 && d.tryWeapon < Content.Weapons.Length && g.progress.WeaponOwned(d.tryWeapon))
            {
                var w = Content.Weapons[d.tryWeapon];
                c.kind = Kind.TryWeapon;
                c.icon = Tex.DamageIcon(w.type);
                if (NeedText(c, c.kind))
                {
                    c.title = "Опробуй " + w.name + ":\n" + WeaponWhat[d.tryWeapon];
                    c.sub = w.aoe > 0f ? "Въезжай в группу врагов — бьёт всех рядом" : "Подъезжай к врагам — бьёт сам";
                }
                if (g.SessionTime - groupPicked > 0.5f) { groupPicked = g.SessionTime; groupFound = NearestGroup(g, p, out groupAt); }
                if (groupFound)
                {
                    c.hasTarget = true; c.destination = c.target = groupAt;
                    if (Flat(groupAt - p) > 12f)
                    {
                        var wb = WayBack(p, null, groupAt, 2000 + Mathf.RoundToInt(groupAt.x) * 1009 + Mathf.RoundToInt(groupAt.z));
                        if (wb != null) { c.target = PointAlong(wb, p, 12f, out _); ActiveRoute = wb; }
                    }
                }
                Finish(c, p);
                return c;
            }
            // right after a purchase: hit something close and see the new number
            if (g.SessionTime < SeeUpgradeUntil && SeeUpgradeWeapon >= 0)
            {
                c.kind = Kind.SeeUpgrade;
                c.icon = Tex.DamageIcon(Content.Weapons[SeeUpgradeWeapon].type);
                if (NeedText(c, c.kind))
                {
                    c.title = MainTitle(zb);
                    c.sub = "Урон " + Fmt.Num(SeeUpgradeFrom) + " → " + Fmt.Num(SeeUpgradeTo) + ": смотри на зелёные числа";
                }
                var t = World.I != null ? World.I.Nearest(p, 30f) : null;
                if (t != null) { c.hasTarget = true; c.target = c.destination = t.Pos; }
                Finish(c, p);
                return c;
            }
            // the first weapon level (paid by the landing reward)
            if (d.upgradesBought == 0 && d.weaponLevel[0] == 1)
            {
                int cost = g.progress.WeaponLevelCost(0);
                if (cost >= 0 && d.gems >= cost)
                {
                    c.kind = Kind.Upgrade;
                    c.icon = Icon.Wrench;
                    if (NeedText(c, c.kind))
                    {
                        c.title = MainTitle(zb);
                        c.sub = "Шаг 1: в GARAGE улучши пулемёт: урон " + Fmt.Num(g.progress.WeaponHitDamage(0)) + " → " +
                                Fmt.Num(g.progress.WeaponHitDamageAt(0, 2));
                    }
                    return c;
                }
            }
            // the next boss (through the gates on the way)
            if (zb >= 0)
            {
                c.kind = Kind.Boss;
                c.zone = zb;
                c.icon = Icon.Skull;
                // ready = the fight ends within ~90 s AND the car lives through it (Balance.BossHpNeed)
                var P = g.progress;
                double ready = Balance.BossReadyHit(zb), have = P.DisplayDamage(), dps = P.TotalDps();
                bool dmgOk = have >= ready || dps >= Content.Zones[zb].boss.hp / 90.0;
                double hpNeed = Math.Ceiling(Balance.BossHpNeed(zb, dps, P.Regen, P.DamageTakenMul) / 10.0) * 10.0;
                bool hpOk = P.MaxHP >= hpNeed;
                c.ready = dmgOk && hpOk;
                if (NeedText(c, c.kind))
                {
                    c.title = MainTitle(zb);
                    c.sub = testVisit ? "Тестовый визит: прогресс не засчитывается"
                          : c.ready ? "Урон " + Fmt.Num(have) + ", HP " + Fmt.Num(P.MaxHP) + " — ты готов! Езжай за стрелкой"
                          : !dmgOk ? "Урон " + Fmt.Num(have) + " из " + Fmt.Num(ready) + ": ломай всё по пути и копи силу"
                          : "Урон есть, HP " + Fmt.Num(P.MaxHP) + " из " + Fmt.Num(hpNeed) + ": ломай кактусы и хлам";
                }
                BuildBossRoute(zb);
                c.destination = route.Count > 0 ? route[route.Count - 1] : World.I.bossSpawns[zb].pos;
                c.hasTarget = true;
                c.target = PointAlong(route, p, 14f, out c.distance);
                ActiveRoute = route;
                // off the road: back to it the way a car can drive (out of a camp through its opening, around rocks, round
                // to the top of the Works ramp when the car is beside its trench). Once on that way, it is followed until
                // the car is really back on the route: near the 12 m mark the plain pointer would aim across the trench.
                ClosestSegment(route, p, out _, out float offRoute);
                if (offRoute > 12f) onWay = true;
                else if (offRoute < 3f) onWay = false;
                // beside a bridge's approach, a trench or a wall the straight line to the mark ahead can cross what a car
                // cannot drive through (under a low deck, into a trench wall): then the drivable way back to the road
                if (!onWay && offRoute > 1.5f && !NavGrid.LineFree(p, c.target)) onWay = true;
                if (onWay)
                {
                    var wb = WayBack(p, route, Vector3.zero, 1000 + zb);
                    if (wb != null) { c.target = PointAlong(wb, p, 12f, out c.distance); ActiveRoute = wb; }
                }
                Finish(c, p, false);
                return c;
            }
            c.kind = Kind.Done;
            c.icon = Icon.Star;
            if (NeedText(c, c.kind))
            {
                c.title = "Пустошь покорена";
                c.sub = "Копи силу: каждый обломок делает машину сильнее";
            }
            return c;
        }

        static float Flat(Vector3 v) { v.y = 0f; return v.magnitude; }

        /// <summary>
        /// A drivable way from p back to a route (or to a point) over the zone's NavGrid, then on along the route; null
        /// under the ground or up on a plateau (the plain pointer then), or while the zone's map is still being built.
        /// </summary>
        static List<Vector3> WayBack(Vector3 p, List<Vector3> toRoute, Vector3 toPoint, int key)
        {
            if (Mathf.Abs(p.y) > 1.2f) return null;
            int zone = Content.ZoneIndexAt(p.z);
            if (p.z < Content.ZoneMinZ(0) || zone < 0 || zone >= Content.ZoneCount) return null;
            if (!NavGrid.Ready(zone)) { NavGrid.Build(zone, 8); return null; }
            float now = Time.unscaledTime;
            if (key != wayFor || now - wayAt > 0.6f || Flat(p - wayFrom) > 4f)
            {
                wayFor = key; wayAt = now; wayFrom = p;
                wayOk = toRoute != null ? NavGrid.WayToRoute(p, toRoute, key, way) : NavGrid.WayToPoint(p, toPoint, 7f, way);
                if (wayOk)
                {
                    wayPlus.Clear();
                    wayPlus.AddRange(way);
                    if (toRoute != null)
                    {
                        int s = ClosestSegment(toRoute, way[way.Count - 1], out _, out _);
                        for (int i = s + 1; i < toRoute.Count; i++) wayPlus.Add(toRoute[i]);
                    }
                    else wayPlus.Add(toPoint);
                }
            }
            return wayOk ? wayPlus : null;
        }

        /// <summary>
        /// Distance, and the way out of the Mammoth's hangar: under the ground with the goal up on the surface, the
        /// pointer leads back through the tunnel and up the ramp first (a straight line would point into the rock).
        /// </summary>
        static void Finish(Goal c, Vector3 p, bool setDistance = true)
        {
            if (!c.hasTarget) return;
            if (setDistance) c.distance = Flat(c.destination - p);
            if (p.y < -1.5f && c.target.y > -1.5f && Structures.WorksRoute != null && Structures.WorksRoute.Length > 1)
            {
                if (exitRoute.Count == 0)
                {
                    exitRoute.Add(Structures.WorksBossHome + new Vector3(0f, 0f, -8f));
                    for (int i = Structures.WorksRoute.Length - 1; i >= 0; i--) exitRoute.Add(Structures.WorksRoute[i]);
                }
                c.target = PointAlong(exitRoute, p, 14f, out _);
                ActiveRoute = exitRoute;
                // pushed into a corner of the hangar (a boss fight does that), the mark 14 m along the way out can lie
                // behind a wall: then the farthest point of the way out the car can see, back to its start in the
                // middle of the hangar (from there the rest of the way is in sight again)
                var eye = p + Vector3.up * 0.9f;
                if (Ground.Blocked(eye, c.target + Vector3.up * 0.9f))
                {
                    int seg = ClosestSegment(exitRoute, p, out _, out _);
                    var pick = exitRoute[0];
                    for (int i = Mathf.Min(exitRoute.Count - 1, seg + 1); i >= 0; i--)
                        if (!Ground.Blocked(eye, exitRoute[i] + Vector3.up * 0.9f)) { pick = exitRoute[i]; break; }
                    c.target = pick;
                }
            }
        }

        /// <summary>The nearest camp with a crowd (three or more things to hit close to it); falls back to the nearest camp.</summary>
        static bool NearestGroup(Game g, Vector3 p, out Vector3 at)
        {
            at = p;
            int zi = Mathf.Clamp(Mathf.Min(Content.ZoneIndexAt(p.z), g.progress.d.unlockedZone), 0, Content.ZoneCount - 1);
            float best = float.MaxValue, bestAny = float.MaxValue;
            Vector3 any = p;
            bool found = false, foundAny = false;
            var list = World.I.activeTargets;
            foreach (var cp in World.I.camps[zi])
            {
                float dd = Flat(cp - p);
                if (dd < bestAny) { bestAny = dd; any = cp; foundAny = true; }
                int n = 0;
                for (int i = 0; i < list.Count && n < 3; i++)
                {
                    var t = list[i];
                    if (t == null || !t.Targetable || t.IsBoss) continue;
                    if (Flat(t.Pos - cp) < 11f) n++;
                }
                if (n >= 3 && dd < best) { best = dd; at = cp; found = true; }
            }
            if (!found && foundAny) { at = any; found = true; }
            return found;
        }

        // ------------------------------------------------------------------ route
        /// <summary>
        /// The drivable way to a zone's boss: the main roads of the zones on the way (each ends at the next gate), then
        /// for the Mammoth the turn-off at the Works sign, the entrance ramp, the tunnel and the hangar (WorksRoute);
        /// for the later bosses the road to their arena.
        /// </summary>
        static void BuildBossRoute(int zb)
        {
            if (routeFor == zb && route.Count > 0) return;
            routeFor = zb;
            route.Clear();
            var w = World.I;
            for (int z = 0; z <= zb; z++)
            {
                var road = w.roads[z][0];
                if (z < zb) { route.AddRange(road); continue; }
                if (zb == 0)
                {
                    // along the main road to the Works turn-off, then down into the hangar
                    var turn = Structures.WorksRoute[0];
                    int cut = NearestIndex(road, turn);
                    for (int i = 0; i <= cut; i++) route.Add(road[i]);
                    for (int i = 0; i < Structures.WorksRoute.Length; i++) route.Add(Structures.WorksRoute[i]);
                    route.Add(Structures.WorksBossHome + new Vector3(0f, 0f, -8f));
                }
                else
                {
                    var arena = w.arenaCenters[zb];
                    int cut = NearestIndex(road, arena);
                    for (int i = 0; i <= cut; i++) route.Add(road[i]);
                    route.Add(arena);
                }
            }
        }

        static int NearestIndex(List<Vector3> pts, Vector3 q)
        {
            int best = 0; float bd = float.MaxValue;
            for (int i = 0; i < pts.Count; i++)
            {
                var dd = pts[i] - q; dd.y = 0f;
                if (dd.sqrMagnitude < bd) { bd = dd.sqrMagnitude; best = i; }
            }
            return best;
        }

        /// <summary>
        /// The pointer's aim: the point `ahead` metres further along a route from the car's closest point on it (on the
        /// car's own level: the tunnel under the lid is not "close" to a car driving over it). Off the route by more than
        /// 25 m, it leads back to the route first. `left` = the way still to go (back to the route + along it).
        /// </summary>
        public static Vector3 PointAlong(List<Vector3> pts, Vector3 p, float ahead, out float left)
        {
            left = 0f;
            if (pts == null || pts.Count == 0) return p;
            if (pts.Count == 1) { left = Flat(pts[0] - p); return pts[0]; }
            int seg = ClosestSegment(pts, p, out float segT, out float off);
            var closest = pts[seg] + (pts[seg + 1] - pts[seg]) * segT;
            // the way still to go
            left = off + Flat(pts[seg + 1] - closest);
            for (int i = seg + 1; i < pts.Count - 1; i++) left += Flat(pts[i + 1] - pts[i]);
            if (off > 25f) return closest;
            // walk `ahead` metres along the polyline
            float rest = ahead;
            var cur = closest;
            for (int i = seg; i < pts.Count - 1; i++)
            {
                var next = pts[i + 1];
                var s = next - cur; float len = new Vector2(s.x, s.z).magnitude;
                if (len >= rest) return cur + s * (rest / Mathf.Max(1e-4f, len));
                rest -= len;
                cur = next;
            }
            return pts[pts.Count - 1];
        }

        /// <summary>The segment of a route closest to p on p's own level (another level counts as far away).</summary>
        public static int ClosestSegment(List<Vector3> pts, Vector3 p, out float segT, out float offRoute)
        {
            int bestSeg = 0; float bestT = 0f, bestScore = float.MaxValue, bestOff = 0f;
            for (int i = 0; i < pts.Count - 1; i++)
            {
                var a = pts[i]; var b = pts[i + 1];
                var ab = b - a; ab.y = 0f;
                var ap = p - a; ap.y = 0f;
                float t = Mathf.Clamp01(Vector3.Dot(ap, ab) / Mathf.Max(1e-4f, ab.sqrMagnitude));
                var q = a + (b - a) * t;
                var dd = p - q;
                float dy = Mathf.Abs(dd.y);
                dd.y = 0f;
                float flat = dd.magnitude;
                float score = flat + (dy > 2.2f ? 40f + dy * 5f : 0f);
                if (score < bestScore) { bestScore = score; bestSeg = i; bestT = t; bestOff = flat; }
            }
            segT = bestT; offRoute = bestOff;
            return bestSeg;
        }
    }
}
