using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// A coarse map of where the car can drive on a zone's surface: 2 m cells, a cell is free when nothing the car stops
    /// at (rock, cliff, wall, palisade, building, gate, ledge) stands there at body height; things that can be shot to
    /// pieces do not count. Built a few rows per frame the first time a zone needs it (about 11 000 cells a zone).
    /// The goal pointer uses it to lead back to the road from anywhere off it: out of a camp through the palisade's
    /// opening, around a ridge or a rock wall, never straight into an obstacle.
    /// </summary>
    public static class NavGrid
    {
        public const float Cell = 2f;
        const float XMin = -112f, Width = 224f;
        static readonly int NX = Mathf.CeilToInt(Width / Cell);
        static readonly int NZ = Mathf.CeilToInt(Content.ZoneLength / Cell);
        static readonly byte[][] cells = new byte[Content.ZoneCount][];     // 1 free, 2 blocked
        static readonly int[] rowsDone = new int[Content.ZoneCount];
        static readonly Collider[] buf = new Collider[16];

        // search buffers (one zone at a time)
        static int[] prev, seen, goal, queue;
        static int seenStamp, goalStamp;
        static int goalKey = int.MinValue, goalZone = -1;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void ResetStatics()
        {
            for (int i = 0; i < cells.Length; i++) { cells[i] = null; rowsDone[i] = 0; }
            goalKey = int.MinValue; goalZone = -1;
        }

        public static bool Ready(int zone) => zone >= 0 && zone < Content.ZoneCount && cells[zone] != null && rowsDone[zone] >= NZ;

        /// <summary>Builds up to `rows` more rows of a zone's map; call every frame until Ready.</summary>
        public static void Build(int zone, int rows)
        {
            if (zone < 0 || zone >= Content.ZoneCount || Ready(zone)) return;
            if (cells[zone] == null) cells[zone] = new byte[NX * NZ];
            var c = cells[zone];
            int end = Mathf.Min(NZ, rowsDone[zone] + rows);
            for (int iz = rowsDone[zone]; iz < end; iz++)
                for (int ix = 0; ix < NX; ix++)
                    c[iz * NX + ix] = Free(Center(zone, ix, iz)) ? (byte)1 : (byte)2;
            rowsDone[zone] = end;
        }

        static Vector3 Center(int zone, int ix, int iz) => new Vector3(XMin + (ix + 0.5f) * Cell, 0f, Content.ZoneMinZ(zone) + (iz + 0.5f) * Cell);

        static bool ToCell(int zone, Vector3 p, out int ix, out int iz)
        {
            ix = Mathf.FloorToInt((p.x - XMin) / Cell);
            iz = Mathf.FloorToInt((p.z - Content.ZoneMinZ(zone)) / Cell);
            return ix >= 0 && ix < NX && iz >= 0 && iz < NZ;
        }

        /// <summary>The car's body at a cell: a capsule a little narrower than the car (it fits between two blocked cells).</summary>
        static bool Free(Vector3 c)
        {
            int n = Physics.OverlapCapsuleNonAlloc(c + Vector3.up * 0.95f, c + Vector3.up * 1.6f, 0.9f, buf, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var col = buf[i];
                if (col.attachedRigidbody != null) continue;               // the car itself
                if (col.GetComponentInParent<Target>() != null) continue;   // it can be shot to pieces
                return false;
            }
            return true;
        }

        static bool IsFree(int zone, int ix, int iz) => ix >= 0 && ix < NX && iz >= 0 && iz < NZ && cells[zone][iz * NX + ix] == 1;

        static void EnsureBuffers()
        {
            int n = NX * NZ;
            if (prev != null && prev.Length == n) return;
            prev = new int[n]; seen = new int[n]; goal = new int[n]; queue = new int[n];
        }

        /// <summary>Marks the cells along a polyline (the part inside the zone) as the search's goal; `key` names it.</summary>
        static void MarkGoal(int zone, IReadOnlyList<Vector3> pts, int key)
        {
            if (goalKey == key && goalZone == zone) return;
            goalKey = key; goalZone = zone;
            goalStamp++;
            for (int i = 0; i < pts.Count; i++)
            {
                var a = pts[i]; var b = i + 1 < pts.Count ? pts[i + 1] : pts[i];
                if (Mathf.Abs(a.y) > 1.2f && Mathf.Abs(b.y) > 1.2f) continue;     // under the ground / up on a plateau
                float len = Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z));
                int steps = Mathf.Max(1, Mathf.CeilToInt(len / (Cell * 0.5f)));
                for (int s = 0; s <= steps; s++)
                {
                    var q = Vector3.Lerp(a, b, s / (float)steps);
                    if (Mathf.Abs(q.y) > 1.2f) continue;
                    if (ToCell(zone, q, out int ix, out int iz) && cells[zone][iz * NX + ix] == 1) goal[iz * NX + ix] = goalStamp;
                }
            }
        }

        static void MarkGoalPoint(int zone, Vector3 at, float radius, int key)
        {
            if (goalKey == key && goalZone == zone) return;
            goalKey = key; goalZone = zone;
            goalStamp++;
            int r = Mathf.CeilToInt(radius / Cell);
            if (!ToCell(zone, at, out int cx, out int cz)) { cx = Mathf.Clamp(cx, 0, NX - 1); cz = Mathf.Clamp(cz, 0, NZ - 1); }
            for (int dz = -r; dz <= r; dz++)
                for (int dx = -r; dx <= r; dx++)
                {
                    if (dx * dx + dz * dz > r * r) continue;
                    if (IsFree(zone, cx + dx, cz + dz)) goal[(cz + dz) * NX + cx + dx] = goalStamp;
                }
        }

        /// <summary>The drivable way from p to the nearest point of a route (on the surface, in p's zone).</summary>
        public static bool WayToRoute(Vector3 p, IReadOnlyList<Vector3> route, int key, List<Vector3> way)
        {
            int zone = Content.ZoneIndexAt(p.z);
            if (!Ready(zone)) return false;
            EnsureBuffers();
            MarkGoal(zone, route, key);
            return Search(zone, p, way);
        }

        /// <summary>The drivable way from p to within `radius` of a point (a camp: in through its opening).</summary>
        public static bool WayToPoint(Vector3 p, Vector3 at, float radius, List<Vector3> way)
        {
            int zone = Content.ZoneIndexAt(p.z);
            if (!Ready(zone) || Content.ZoneIndexAt(at.z) != zone) return false;
            EnsureBuffers();
            MarkGoalPoint(zone, at, radius, 7919 * Mathf.RoundToInt(at.x) + Mathf.RoundToInt(at.z) * 31 + Mathf.RoundToInt(radius));
            return Search(zone, p, way);
        }

        static readonly int[] DX = { 1, -1, 0, 0, 1, 1, -1, -1 };
        static readonly int[] DZ = { 0, 0, 1, -1, 1, -1, 1, -1 };

        /// <summary>Breadth-first over free cells (8 neighbours, no corner cutting) from p's cell to the nearest goal cell.</summary>
        static bool Search(int zone, Vector3 p, List<Vector3> way)
        {
            way.Clear();
            if (!ToCell(zone, p, out int sx, out int sz)) return false;
            // the car may stand in a blocked cell (pressed to a fence): start from the nearest free one
            if (!IsFree(zone, sx, sz))
            {
                bool found = false;
                for (int r = 1; r <= 3 && !found; r++)
                    for (int dz = -r; dz <= r && !found; dz++)
                        for (int dx = -r; dx <= r && !found; dx++)
                            if (IsFree(zone, sx + dx, sz + dz)) { sx += dx; sz += dz; found = true; }
                if (!found) return false;
            }
            var c = cells[zone];
            seenStamp++;
            int head = 0, tail = 0, start = sz * NX + sx, hit = -1;
            queue[tail++] = start; seen[start] = seenStamp; prev[start] = -1;
            while (head < tail)
            {
                int cur = queue[head++];
                if (goal[cur] == goalStamp) { hit = cur; break; }
                int cx = cur % NX, cz = cur / NX;
                for (int k = 0; k < 8; k++)
                {
                    int nx = cx + DX[k], nz = cz + DZ[k];
                    if (nx < 0 || nx >= NX || nz < 0 || nz >= NZ) continue;
                    int ni = nz * NX + nx;
                    if (seen[ni] == seenStamp || c[ni] != 1) continue;
                    if (k >= 4 && (c[cz * NX + nx] != 1 || c[nz * NX + cx] != 1)) continue;   // no cutting a corner
                    seen[ni] = seenStamp; prev[ni] = cur;
                    queue[tail++] = ni;
                }
            }
            if (hit < 0) return false;
            // cells back to the start, then pulled tight (a straight run wherever the free cells allow it)
            tmp.Clear();
            for (int i = hit; i >= 0; i = prev[i]) tmp.Add(i);
            tmp.Reverse();
            way.Add(new Vector3(p.x, 0f, p.z));
            int anchor = 0;
            while (anchor < tmp.Count - 1)
            {
                int far = anchor + 1;
                for (int j = Mathf.Min(tmp.Count - 1, anchor + 40); j > anchor + 1; j--)
                    if (Straight(zone, tmp[anchor], tmp[j])) { far = j; break; }
                way.Add(Center(zone, tmp[far] % NX, tmp[far] / NX));
                anchor = far;
            }
            if (way.Count == 1) way.Add(Center(zone, tmp[0] % NX, tmp[0] / NX));
            return true;
        }

        static readonly List<int> tmp = new List<int>(256);

        /// <summary>True when the straight line between two cells crosses free cells only (sampled every half cell).</summary>
        static bool Straight(int zone, int a, int b)
        {
            float ax = a % NX + 0.5f, az = a / NX + 0.5f, bx = b % NX + 0.5f, bz = b / NX + 0.5f;
            float len = Mathf.Sqrt((bx - ax) * (bx - ax) + (bz - az) * (bz - az));
            int steps = Mathf.Max(1, Mathf.CeilToInt(len * 2f));
            for (int s = 1; s < steps; s++)
            {
                float t = s / (float)steps;
                int ix = Mathf.FloorToInt(ax + (bx - ax) * t), iz = Mathf.FloorToInt(az + (bz - az) * t);
                if (!IsFree(zone, ix, iz)) return false;
            }
            return true;
        }
    }
}
