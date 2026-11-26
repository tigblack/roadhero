using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Driving data of the third zone (Ashen Winter, ArtSource/Levels/AshenWinter, scripts/awl_layout.py): the same
    /// layout file places the Blender art and the gameplay floors, so what is drawn is what the car drives on.
    ///  - the arena: a round concrete deck 1.2 m above the valley on the main road, a ramp where the road meets it on
    ///    either side, a face round the deck that stops a car below (a ledge) and a low parapet that keeps the fight on
    ///    the deck (the boss's spawn stands on it);
    ///  - the jump: a concrete launch ramp on the side track, over a shallow ravine, onto a landing pad;
    ///  - the ravine: a 0.5 m base height grid (header 'AWSF'), gentle banks (the car and enemies drive through it);
    ///  - keep-out rectangles for the generator: the few spawns that stood where the bunker, the arena, the jump or a
    ///    landmark now stands are moved by World.KeepClearOfStructures; IDs, specs and rewards stay.
    /// Active only with the Ashen Winter art bundle (Levels/AshenWinterZ2) and its layout.
    /// </summary>
    public static class AshenSurfaces
    {
        public const string LayoutResource = "Levels/AshenWinter_layout";
        const string GridResource = "Levels/AshenWinter_surfaces";
        public static bool Active { get; private set; }
        public static Layout Data { get; private set; }
        /// <summary>Editor exports (-ashenLayout): the layout without the art bundle, to measure where the generator
        /// moves the spawns that stood in the new structures.</summary>
        public static bool ForceForExport;

        [Serializable] public sealed class Rect { public string name; public float x, z, halfX, halfZ, yaw; public float r = 0.7f, g = 0.7f, b = 0.7f; }
        [Serializable] public sealed class Ramp { public float x, z, yaw, halfX, halfZ, angle; }
        [Serializable] public sealed class Arena { public float x, z, radius, height, rampLength, rampHalfWidth; public Ramp[] ramps; }
        [Serializable] public sealed class Bunker { public float x, z, yaw, innerHalfWidth, halfLength, height, wall, moundHalfX, moundHalfZ; }
        [Serializable] public sealed class Jump { public float x, z, yaw, halfWidth, length, height, boost; }
        [Serializable] public sealed class Pad { public float x, z, radius; }
        [Serializable] public sealed class SpawnY { public int id; public float y; }
        [Serializable] public sealed class Layout
        {
            public int version, zone;
            public Arena arena;
            public Bunker bunker;
            public Jump jump;
            public Pad pad;
            public Rect[] exclusions, marks;
            public SpawnY[] spawnY;
        }

        /// <summary>The arena deck: a flat round floor.</summary>
        public sealed class DeckPiece : FloorPiece
        {
            public float radius;
            public override bool Contains(Vector2 l) => l.sqrMagnitude <= radius * radius;
        }

        static int nx, nz;
        static float x0, z0, step;
        static short[] heights;
        public static FloorPiece DeckFloor { get; private set; }
        public static FloorPiece JumpFloor { get; private set; }
        static readonly List<FloorPiece> rampFloors = new List<FloorPiece>();
        public static IReadOnlyList<FloorPiece> RampFloors => rampFloors;
        /// <summary>Colliders built round the arena and the jump (tests).</summary>
        public static int ColliderCount { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void Reset() { Active = false; DeckFloor = null; JumpFloor = null; rampFloors.Clear(); ColliderCount = 0; }

        /// <summary>Call with WetlandSurfaces.Plan (before the zones generate): floors, keep-out areas, map marks.</summary>
        public static void Plan()
        {
            Reset();
            if (ImportedLevel.SuppressIntegration || (!ForceForExport && Resources.Load<TextAsset>(ImportedLevel.AshenManifestResource) == null)) return;
            if (Data == null && !LoadLayout()) return;
            if (heights == null) LoadGrid();
            Active = true;
            var L = Data;
            foreach (var r in L.exclusions) Structures.Exclusions.Add(ToRect(r));
            foreach (var r in L.marks) Structures.Marks.Add(new Structures.MapMark { r = ToRect(r), c = new Color(r.r, r.g, r.b) });
            var a = L.arena;
            var center = new Vector3(a.x, 0f, a.z);
            DeckFloor = Ground.Add(new DeckPiece
            {
                name = "AshenArenaDeck", rect = new ORect(center, 0f, a.radius, a.radius), radius = a.radius,
                h0 = a.height, h1 = a.height, easeIn = 0f, easeOut = 0f, surface = SurfaceKind.Concrete
            });
            foreach (var rp in a.ramps)
                rampFloors.Add(Ground.Add(new FloorPiece
                {
                    name = "AshenArenaRamp", rect = new ORect(new Vector3(rp.x, 0f, rp.z), rp.yaw, rp.halfX, rp.halfZ),
                    h0 = 0f, h1 = a.height, easeIn = 0.3f, easeOut = 0.3f, surface = SurfaceKind.Asphalt
                }));
            var j = L.jump;
            var f = new Vector3(Mathf.Sin(j.yaw * Mathf.Deg2Rad), 0f, Mathf.Cos(j.yaw * Mathf.Deg2Rad));
            var lip = new Vector3(j.x, 0f, j.z);
            // a launch floor of its own (Structures.Ramp would also have the generator build a ramp model: new objects
            // before the snapshot capture would shift the preorder IDs the other zones' bundles are matched by)
            JumpFloor = Ground.Add(new FloorPiece
            {
                name = "AshenJump", rect = new ORect(lip - f * (j.length * 0.5f), j.yaw, j.halfWidth, j.length * 0.5f),
                h0 = 0f, h1 = j.height, surface = SurfaceKind.Concrete, easeIn = 0.3f, easeOut = 0f, launch = true, boost = j.boost,
                enemyWalkable = false
            });
        }

        static ORect ToRect(Rect r) => new ORect(new Vector3(r.x, 0f, r.z), r.yaw, r.halfX, r.halfZ);

        static bool LoadLayout()
        {
            var asset = Resources.Load<TextAsset>(LayoutResource);
            if (asset == null) return false;
            try
            {
                var l = JsonUtility.FromJson<Layout>(asset.text);
                if (l == null || l.arena == null || l.arena.ramps == null || l.jump == null || l.exclusions == null || l.marks == null)
                    throw new System.IO.InvalidDataException("incomplete layout");
                Data = l;
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError("RoadGame: invalid Ashen Winter layout: " + e.Message);
                return false;
            }
            finally { Resources.UnloadAsset(asset); }
        }

        static void LoadGrid()
        {
            var asset = Resources.Load<TextAsset>(GridResource);
            if (asset == null) return;
            var b = asset.bytes;
            try
            {
                if (b.Length < 24 || b[0] != 'A' || b[1] != 'W' || b[2] != 'S' || b[3] != 'F') throw new System.IO.InvalidDataException("header");
                nx = BitConverter.ToInt32(b, 4); nz = BitConverter.ToInt32(b, 8);
                x0 = BitConverter.ToSingle(b, 12); z0 = BitConverter.ToSingle(b, 16); step = BitConverter.ToSingle(b, 20);
                if (nx < 2 || nz < 2 || step <= 0f || b.Length != 24 + nx * nz * 2) throw new System.IO.InvalidDataException("size");
                heights = new short[nx * nz];
                Buffer.BlockCopy(b, 24, heights, 0, nx * nz * 2);
            }
            catch (Exception e)
            {
                heights = null;
                Debug.LogError("RoadGame: invalid Ashen Winter surface data: " + e.Message);
            }
            finally { Resources.UnloadAsset(asset); }
        }

        /// <summary>Bilinear base height of the zone's ground (0 = flat) at x, z.</summary>
        public static float Height(float x, float z)
        {
            if (!Active || heights == null) return 0f;
            float fx = (x - x0) / step, fz = (z - z0) / step;
            if (fx < 0f || fz < 0f || fx > nx - 1 || fz > nz - 1) return 0f;
            int ix = Mathf.Min((int)fx, nx - 2), iz = Mathf.Min((int)fz, nz - 2);
            float tx = fx - ix, tz = fz - iz;
            int i = iz * nx + ix;
            float a = heights[i], c = heights[i + 1], d = heights[i + nx], e = heights[i + nx + 1];
            return ((a * (1f - tx) + c * tx) * (1f - tz) + (d * (1f - tx) + e * tx) * tz) * 0.001f;
        }

        /// <summary>Base ground height and normal in the zone's ravine; false (0, up) elsewhere.</summary>
        public static bool TrySampleBase(float x, float z, out float h, out Vector3 normal)
        {
            h = 0f; normal = Vector3.up;
            if (!Active || heights == null || z < z0 || x < x0 || z > z0 + (nz - 1) * step || x > x0 + (nx - 1) * step) return false;
            h = Height(x, z);
            if (h >= -0.00001f) { h = 0f; return false; }
            const float e = 0.25f;
            float dx = (Height(x + e, z) - Height(x - e, z)) / (2f * e);
            float dz = (Height(x, z + e) - Height(x, z - e)) / (2f * e);
            normal = new Vector3(-dx, 1f, -dz).normalized;
            return true;
        }

        /// <summary>The boss stands on the arena deck: spawn heights from the layout (IDs unchanged).</summary>
        public static void ApplySpawnPositions(IList<SpawnPoint> spawns)
        {
            if (!Active || Data.spawnY == null) return;
            foreach (var s in Data.spawnY)
                for (int i = 0; i < spawns.Count; i++)
                    if (spawns[i].id == s.id) { var p = spawns[i].pos; p.y = s.y; spawns[i].pos = p; break; }
        }

        /// <summary>
        /// After the art is imported: the arena's face (a ledge: it stops a car below, a car on the deck drives over it),
        /// its parapet (keeps the car and the fighters on the deck except over the ramps), the ramps' side faces and
        /// the jump ramp's sides and back. Built after ImportedLevel so the snapshot IDs of the world stay as they were.
        /// </summary>
        public static void BuildColliders(Transform parent)
        {
            if (!Active || DeckFloor == null) return;
            var g = new GameObject("AshenColliders").transform;
            g.SetParent(parent, false);
            var a = Data.arena;
            var c = new Vector3(a.x, 0f, a.z);
            float R = a.radius, h = a.height;
            // openings where the ramps meet the deck
            var open = new List<(float ang, float half)>();
            foreach (var rp in a.ramps) open.Add((rp.angle, Mathf.Asin(Mathf.Clamp01((rp.halfX + 0.2f) / R)) * Mathf.Rad2Deg));
            const int n = 90;
            for (int i = 0; i < n; i++)
            {
                float ang = 360f * (i + 0.5f) / n;
                bool gap = false;
                foreach (var o in open) if (Mathf.Abs(Mathf.DeltaAngle(ang, o.ang)) < o.half) gap = true;
                var dir = new Vector3(Mathf.Cos(ang * Mathf.Deg2Rad), 0f, Mathf.Sin(ang * Mathf.Deg2Rad));
                float seg = 2f * Mathf.PI * (R + 0.3f) / n + 0.12f;
                float yaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                // the ramps meet the deck here: no face, no parapet (their own side faces close the gap's edges)
                if (gap) continue;
                // the face under the deck's edge: a ledge (top 5 cm under the deck)
                var face = Box(g, "ArenaFace", c + dir * (R + 0.3f) + Vector3.up * ((h - 0.05f - 0.6f) * 0.5f), new Vector3(seg, h - 0.05f + 0.6f, 0.6f), yaw);
                Ground.AddLedge(face, DeckFloor, h - 0.05f);
                // the parapet on the rim (the drawn concrete barriers stand on it)
                Box(g, "ArenaParapet", c + dir * (R - 0.25f) + Vector3.up * (h + 0.45f), new Vector3(seg, 0.9f, 0.5f), yaw);
            }
            foreach (var rp in rampFloors) RampSides(g, "ArenaRampSide", rp);
            if (JumpFloor != null)
            {
                RampSides(g, "JumpSide", JumpFloor);
                var r = JumpFloor.rect;
                var back = Box(g, "JumpBack", r.World(0f, r.half.y + 0.25f, (JumpFloor.h1 - 0.1f) * 0.5f), new Vector3(r.half.x * 2f, JumpFloor.h1 - 0.1f, 0.5f), r.Yaw);
                Ground.AddLedge(back, JumpFloor, JumpFloor.h1 - 0.15f);
            }
            Debug.Log($"RoadGame ASHEN colliders: {ColliderCount} (deck r={R} h={h}, ramps {rampFloors.Count}, jump {(JumpFloor != null)})");
        }

        /// <summary>Sloped faces along both long sides of a ramp floor (ledges: their top 15 cm under the ramp).</summary>
        static void RampSides(Transform g, string name, FloorPiece p)
        {
            var r = p.rect;
            const int steps = 4;
            for (int s = -1; s <= 1; s += 2)
                for (int k = 0; k < steps; k++)
                {
                    float za = -r.half.y + 2f * r.half.y * k / steps, zb = -r.half.y + 2f * r.half.y * (k + 1) / steps;
                    float top = Mathf.Max(p.HeightLocal(za), p.HeightLocal(zb));
                    if (top < 0.25f) continue;
                    var a = r.World(s * (r.half.x + 0.2f), za, 0f);
                    var b = r.World(s * (r.half.x + 0.2f), zb, 0f);
                    float hh = top - 0.15f + 0.6f;
                    var box = Box(g, name, (a + b) * 0.5f + Vector3.up * (top - 0.15f - hh * 0.5f), new Vector3(0.4f, hh, (b - a).magnitude + 0.05f), r.Yaw);
                    Ground.AddLedge(box, p, top - 0.15f);
                }
        }

        static BoxCollider Box(Transform parent, string name, Vector3 center, Vector3 size, float yaw)
        {
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(center, Quaternion.Euler(0f, yaw, 0f));
            var bc = go.AddComponent<BoxCollider>();
            bc.size = size;
            ColliderCount++;
            return bc;
        }

        /// <summary>Paints the ravine on the minimap (darker ash).</summary>
        public static void PaintMinimapOverlay(Color32[] pixels, int width, int height, float xMin, float zMin, float pixelsPerM)
        {
            if (!Active || heights == null || pixels == null || pixels.Length != width * height || pixelsPerM <= 0f) return;
            var ash = new Color32(92, 92, 96, 255);
            float zMax = z0 + (nz - 1) * step, xMax = x0 + (nx - 1) * step;
            int r0 = Mathf.Max(0, Mathf.FloorToInt((z0 - zMin) * pixelsPerM)), r1 = Mathf.Min(height - 1, Mathf.CeilToInt((zMax - zMin) * pixelsPerM));
            int c0 = Mathf.Max(0, Mathf.FloorToInt((x0 - xMin) * pixelsPerM)), c1 = Mathf.Min(width - 1, Mathf.CeilToInt((xMax - xMin) * pixelsPerM));
            for (int row = r0; row <= r1; row++)
            {
                float z = zMin + (row + 0.5f) / pixelsPerM;
                for (int col = c0; col <= c1; col++)
                {
                    float x = xMin + (col + 0.5f) / pixelsPerM;
                    float hh = Height(x, z);
                    if (hh > -0.2f) continue;
                    int p = row * width + col;
                    pixels[p] = Color32.Lerp(pixels[p], ash, Mathf.Clamp01(-hh / 0.6f) * 0.8f);
                }
            }
        }
    }
}
