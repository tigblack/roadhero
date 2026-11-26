using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Driving data for the Blender v13 art pass. The original hill, ramp and underground floors retain their
    /// gameplay behaviour. Only the flat sand is carved for the river, with separate continuous bridge decks.
    /// Wheels stay on the shallow bed; WaterPhysics applies the river's current, drag and wet tire grip.
    /// </summary>
    public static class DustFlatsSurfaces
    {
        const string ResourcePath = "Levels/DustFlats_v13_surfaces";
        const float BucketSize = 8f;
        static Layout layout;
        static readonly Dictionary<long, List<int>> riverBuckets = new Dictionary<long, List<int>>();
        static readonly List<RibbonFloorPiece> bridgeFloors = new List<RibbonFloorPiece>();
        public static bool Active { get; private set; }
        public static float WaterLevel => layout != null ? layout.waterLevel : -0.22f;
        public static int BridgeCount => Active ? bridgeFloors.Count : 0;

        /// <summary>Actual centreline and deck heights, useful for route validation and capture tools.</summary>
        public static IReadOnlyList<Vector3> GetBridgePath(int index)
        {
            if (!Active || index < 0 || index >= bridgeFloors.Count) return Array.Empty<Vector3>();
            var points = new List<Vector3>();
            foreach (var p in bridgeFloors[index].bridge.samples) points.Add(new Vector3(p.x, p.y, p.z));
            return points;
        }

        [Serializable] sealed class Layout
        {
            public float waterLevel;
            public Station[] stations;
            public Point[] outline;
            public Bridge[] bridges;
            public MovedSpawn[] movedSpawns;
        }
        [Serializable] sealed class Station { public float x, z, w, b, d, k; }
        [Serializable] sealed class Point { public float x, z; }
        [Serializable] sealed class DeckSample { public float x, y, z, halfWidth; }
        [Serializable] sealed class Bridge
        {
            public string name;
            public float rampLength, totalLength;
            public DeckSample[] samples;
        }
        [Serializable] sealed class MovedSpawn { public int id; public float x, y, z; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void Reset()
        {
            Active = false;
            bridgeFloors.Clear();
        }

        /// <summary>Call after the procedural structures and terrain have registered their floors.</summary>
        public static void Plan()
        {
            Reset();
            if (ImportedLevel.SuppressIntegration || Resources.Load<TextAsset>(ImportedLevel.ManifestResource) == null)
                return;
            if (layout == null)
            {
                var asset = Resources.Load<TextAsset>(ResourcePath);
                if (asset == null) return;
                layout = JsonUtility.FromJson<Layout>(asset.text);
                if (layout == null || layout.stations == null || layout.stations.Length < 2 ||
                    layout.outline == null || layout.outline.Length < 3 || layout.bridges == null)
                {
                    layout = null;
                    Debug.LogError("RoadGame: invalid Dust Flats v13 driving data.");
                    return;
                }
                BuildRiverIndex();
            }
            Active = true;
            foreach (var bridge in layout.bridges)
            {
                if (bridge.samples == null || bridge.samples.Length < 2) continue;
                var piece = new RibbonFloorPiece(bridge);
                Ground.Add(piece);
                bridgeFloors.Add(piece);
            }
        }

        static long Key(int x, int z) => ((long)x << 32) ^ (uint)z;
        static int Bucket(float value) => Mathf.FloorToInt(value / BucketSize);

        static void BuildRiverIndex()
        {
            riverBuckets.Clear();
            for (int i = 0; i < layout.stations.Length - 1; i++)
            {
                var a = layout.stations[i]; var b = layout.stations[i + 1];
                float radius = Mathf.Max(a.w + a.b, b.w + b.b) + 0.2f;
                for (int z = Bucket(Mathf.Min(a.z, b.z) - radius); z <= Bucket(Mathf.Max(a.z, b.z) + radius); z++)
                    for (int x = Bucket(Mathf.Min(a.x, b.x) - radius); x <= Bucket(Mathf.Max(a.x, b.x) + radius); x++)
                    {
                        long key = Key(x, z);
                        if (!riverBuckets.TryGetValue(key, out var list)) riverBuckets.Add(key, list = new List<int>());
                        list.Add(i);
                    }
            }
        }

        /// <summary>Returns false, zero and up outside the actual first-zone channel.</summary>
        public static bool TrySampleBase(float x, float z, out float h, out Vector3 normal)
        {
            h = 0f; normal = Vector3.up;
            if (!Active || z > Content.ZoneMaxZ(0) || z < -130f || Mathf.Abs(x) > 115f) return false;
            h = RiverHeight(x, z);
            if (h >= -0.00001f) return false;
            const float e = 0.06f;
            float dx = (RiverHeight(x + e, z) - RiverHeight(x - e, z)) / (2f * e);
            float dz = (RiverHeight(x, z + e) - RiverHeight(x, z - e)) / (2f * e);
            normal = new Vector3(-dx, 1f, -dz).normalized;
            return true;
        }

        /// <summary>Finite water volume above the carved bed; raised decks are excluded by the caller's height.</summary>
        public static bool TrySampleWater(float x, float z, out float bed, out Vector3 flow)
        {
            bed = 0f; flow = Vector3.zero;
            if (!Active || z > Content.ZoneMaxZ(0) || z < -130f || Mathf.Abs(x) > 115f) return false;
            bed = RiverHeight(x, z, out flow);
            return bed < WaterLevel - 0.002f;
        }

        static float RiverHeight(float x, float z) => RiverHeight(x, z, out _);

        static float RiverHeight(float x, float z, out Vector3 flow)
        {
            flow = Vector3.zero;
            if (!riverBuckets.TryGetValue(Key(Bucket(x), Bucket(z)), out var candidates)) return 0f;
            float best = float.PositiveInfinity, bestT = 0f, signedDistance = 0f;
            int nearest = -1;
            foreach (int i in candidates)
            {
                var a = layout.stations[i]; var b = layout.stations[i + 1];
                float vx = b.x - a.x, vz = b.z - a.z;
                float t = Mathf.Clamp01(((x - a.x) * vx + (z - a.z) * vz) / Mathf.Max(1e-8f, vx * vx + vz * vz));
                float dx = x - a.x - t * vx, dz = z - a.z - t * vz;
                float distance = dx * dx + dz * dz;
                if (distance >= best) continue;
                best = distance; bestT = t; nearest = i;
                signedDistance = Mathf.Sqrt(distance) * (dx * -vz + dz * vx < 0f ? -1f : 1f);
            }
            if (nearest < 0) return 0f;
            var p = layout.stations[nearest]; var q = layout.stations[nearest + 1];
            flow = new Vector3(q.x - p.x, 0f, q.z - p.z).normalized * 0.65f;
            float w = Mathf.Lerp(p.w, q.w, bestT), bank = Mathf.Lerp(p.b, q.b, bestT);
            float depth = Mathf.Lerp(p.d, q.d, bestT), d = Mathf.Abs(signedDistance);
            if (d >= w + bank) return 0f;
            // Identical to rg_layout12.River.height(), including raised point bars on the inside of bends.
            float bar = Mathf.Clamp(Mathf.Sign(signedDistance) * p.k * 14f - 0.15f, 0f, 0.7f);
            if (d <= w)
            {
                float u = Mathf.Clamp01(d / Mathf.Max(w, 0.001f));
                return -depth * (1f - 0.12f * u * u) *
                    (1f - bar * Mathf.Pow(Mathf.Clamp01((u - 0.25f) / 0.75f), 1.5f) * 0.85f);
            }
            float tBank = Mathf.Clamp01((d - w) / Mathf.Max(bank, 0.001f));
            return -depth * 0.88f * (1f - bar * 0.85f) * (1f - tBank * tBank * (3f - 2f * tBank));
        }

        /// <summary>Used by navigation to place its body probe above the river bed or the bridge deck.</summary>
        public static float SurfaceHeight(float x, float z)
        {
            if (!Active) return 0f;
            TrySampleBase(x, z, out float height, out _);
            foreach (var bridge in bridgeFloors)
            {
                var local = bridge.rect.Local(x, z);
                if (bridge.Contains(local)) height = Mathf.Max(height, bridge.Height(local));
            }
            return height;
        }

        /// <summary>A raised part of a bridge deck (more than `rise` over the ground under it). A car gets onto it only
        /// at the bridge's ends; from the side it meets the railing or the low arch under the deck.</summary>
        public static bool OnRaisedDeck(float x, float z, float rise = 0.35f)
        {
            if (!Active) return false;
            TrySampleBase(x, z, out float ground, out _);
            foreach (var bridge in bridgeFloors)
            {
                var local = bridge.rect.Local(x, z);
                if (bridge.Contains(local) && bridge.Height(local) > ground + rise) return true;
            }
            return false;
        }

        /// <summary>The first-zone outline, with tolerance for a car pressed into a wall. Later zones are unchanged.</summary>
        public static bool ContainsBoundary(float x, float z, float padding = 0f)
        {
            if (!Active || z > Content.ZoneMaxZ(0)) return true;
            // The north gate remains the connection into the next procedural zone.
            if (z > 94f && x >= 15f - padding && x <= 31f + padding) return true;
            bool inside = false;
            var points = layout.outline;
            float padSq = padding * padding;
            for (int i = 0, j = points.Length - 1; i < points.Length; j = i++)
            {
                var a = points[j]; var b = points[i];
                if ((a.z > z) != (b.z > z) && x < (b.x - a.x) * (z - a.z) / (b.z - a.z) + a.x)
                    inside = !inside;
                if (padding <= 0f) continue;
                float vx = b.x - a.x, vz = b.z - a.z;
                float t = Mathf.Clamp01(((x - a.x) * vx + (z - a.z) * vz) / Mathf.Max(1e-8f, vx * vx + vz * vz));
                float dx = x - a.x - t * vx, dz = z - a.z - t * vz;
                if (dx * dx + dz * dz <= padSq) return true;
            }
            return inside;
        }

        /// <summary>Paint the imported outline, shallow river and its two drivable bridge crossings.</summary>
        public static void PaintMinimapOverlay(Color32[] pixels, int width, int height,
            float xMin, float zMin, float pixelsPerM)
        {
            if (!Active || pixels == null || pixels.Length != width * height || pixelsPerM <= 0f) return;
            var intersections = new List<float>(16);
            int firstRow = Mathf.Max(0, Mathf.FloorToInt((-260f - zMin) * pixelsPerM));
            int lastRow = Mathf.Min(height - 1, Mathf.FloorToInt((Content.ZoneMaxZ(0) - zMin) * pixelsPerM));
            var outline = layout.outline;
            var zone = Content.Zones[0];
            // Scanline fill avoids a polygon test for every map pixel. Repaint only expanded bays which the old
            // square-map background had darkened, then shade the exterior of the new irregular boundary.
            for (int row = firstRow; row <= lastRow; row++)
            {
                float z = zMin + row / pixelsPerM;
                intersections.Clear();
                for (int i = 0, j = outline.Length - 1; i < outline.Length; j = i++)
                {
                    var a = outline[j]; var b = outline[i];
                    if ((a.z > z) != (b.z > z))
                        intersections.Add(a.x + (b.x - a.x) * (z - a.z) / (b.z - a.z));
                }
                intersections.Sort();
                int crossing = 0;
                bool inside = false;
                for (int column = 0; column < width; column++)
                {
                    float x = xMin + column / pixelsPerM;
                    while (crossing < intersections.Count && x >= intersections[crossing])
                    {
                        inside = !inside;
                        crossing++;
                    }
                    bool pointInside = inside || (z > 94f && x >= 15f && x <= 31f);
                    int pixel = row * width + column;
                    if (!pointInside)
                        pixels[pixel] = Color.Lerp((Color)pixels[pixel], zone.cliffDark, 0.82f);
                    else if (Mathf.Abs(x) > Content.ZoneHalfWidth ||
                        (z < Content.ZoneMinZ(0) - 4f && Mathf.Abs(x) > 9f))
                    {
                        float noise = Mathf.PerlinNoise(x * 0.05f, z * 0.05f) * 0.12f - 0.06f;
                        var color = zone.minimap;
                        pixels[pixel] = new Color(color.r + noise, color.g + noise, color.b + noise, 1f);
                    }
                }
            }

            void Stamp(float x, float z, float radius, Color32 color)
            {
                if (z < -260f || z > Content.ZoneMaxZ(0)) return;
                int cx = Mathf.RoundToInt((x - xMin) * pixelsPerM);
                int cy = Mathf.RoundToInt((z - zMin) * pixelsPerM);
                int r = Mathf.Max(1, Mathf.CeilToInt(radius * pixelsPerM));
                for (int dy = -r; dy <= r; dy++)
                {
                    int y = cy + dy;
                    if (y < firstRow || y > lastRow) continue;
                    for (int dx = -r; dx <= r; dx++)
                    {
                        int xx = cx + dx;
                        if (xx >= 0 && xx < width && dx * dx + dy * dy <= r * r)
                            pixels[y * width + xx] = color;
                    }
                }
            }

            var water = new Color32(57, 117, 113, 255);
            foreach (var station in layout.stations)
            {
                float fraction = Mathf.Clamp01(-WaterLevel / (station.d * 0.88f));
                float lo = 0f, hi = 1f;
                for (int n = 0; n < 7; n++)
                {
                    float t = (lo + hi) * 0.5f;
                    if (1f - t * t * (3f - 2f * t) > fraction) lo = t;
                    else hi = t;
                }
                Stamp(station.x, station.z, station.w + (lo + hi) * 0.5f * station.b, water);
            }

            var wall = new Color32(56, 42, 33, 255);
            for (int i = 0; i < outline.Length; i++)
            {
                var a = outline[i]; var b = outline[(i + 1) % outline.Length];
                if ((a.z + b.z) * 0.5f > 95f && (a.x + b.x) * 0.5f >= 15f && (a.x + b.x) * 0.5f <= 31f)
                    continue;
                int steps = Mathf.Max(1, Mathf.CeilToInt(Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z)) * pixelsPerM));
                for (int n = 0; n <= steps; n++)
                {
                    float t = n / (float)steps;
                    Stamp(Mathf.Lerp(a.x, b.x, t), Mathf.Lerp(a.z, b.z, t), 1.1f, wall);
                }
            }
            var deck = new Color32(104, 91, 77, 255);
            foreach (var bridge in layout.bridges)
                for (int i = 0; i < bridge.samples.Length - 1; i++)
                {
                    var a = bridge.samples[i]; var b = bridge.samples[i + 1];
                    int steps = Mathf.Max(1, Mathf.CeilToInt(Vector2.Distance(new Vector2(a.x, a.z), new Vector2(b.x, b.z)) * pixelsPerM));
                    for (int n = 0; n <= steps; n++)
                    {
                        float t = n / (float)steps;
                        Stamp(Mathf.Lerp(a.x, b.x, t), Mathf.Lerp(a.z, b.z, t), Mathf.Lerp(a.halfWidth, b.halfWidth, t), deck);
                    }
                }
        }


        /// <summary>Persistent spawn IDs stay the same; Blender moved these props/enemies out of the new channel.</summary>
        public static void ApplySpawnPositions(IList<SpawnPoint> spawns)
        {
            if (!Active || layout.movedSpawns == null) return;
            foreach (var move in layout.movedSpawns)
                for (int i = 0; i < spawns.Count; i++)
                    if (spawns[i].id == move.id)
                    {
                        spawns[i].pos = new Vector3(move.x, move.y, move.z);
                        break;
                    }
            KeepBridgeApproachesClear(spawns);
        }

        // The Blender river pass moved props from the water, but its new timber bridge also reaches dry ground.
        // Keep that full lane clear of the original procedural props, including their physical body radius.
        static void KeepBridgeApproachesClear(IList<SpawnPoint> spawns)
        {
            Physics.SyncTransforms();
            int moved = 0;
            foreach (var spawn in spawns)
            {
                if (spawn.zone.index != 0 || spawn.spec.kind != TargetKind.Prop || spawn.pos.y < -0.1f) continue;
                float radius = Mathf.Max(0.6f, spawn.spec.radius * spawn.scale);
                if (!NearBridge(spawn.pos, radius + 0.9f, out var center, out var right, out float halfWidth)) continue;
                var forward = new Vector3(-right.z, 0f, right.x);
                float side = Vector3.Dot(spawn.pos - center, right) < 0f ? -1f : 1f;
                bool found = false;
                for (int ring = 0; ring < 10 && !found; ring++)
                    for (int direction = 0; direction < 2 && !found; direction++)
                        for (int along = 0; along < 3 && !found; along++)
                        {
                            float shift = along == 0 ? 0f : along == 1 ? -3f : 3f;
                            var candidate = center + right * ((direction == 0 ? side : -side) * (halfWidth + radius + 2f + ring * 1.5f)) + forward * shift;
                            if (!ContainsBoundary(candidate.x, candidate.z) || Structures.Excluded(candidate, radius + 0.8f)) continue;
                            if (NearBridge(candidate, radius + 0.9f, out _, out _, out _)) continue;
                            var floor = Ground.Sample(candidate.x, candidate.z, 0.5f);
                            if (!floor.valid || floor.h < -0.02f || floor.h > 0.3f) continue;
                            candidate.y = floor.h;
                            if (World.SpawnBlocked(candidate, radius * 0.85f)) continue;
                            bool occupied = false;
                            foreach (var other in spawns)
                            {
                                if (other == spawn || other.zone.index != 0 || Mathf.Abs(other.pos.y - candidate.y) > Ground.LevelGap) continue;
                                float clearance = radius + other.spec.radius * other.scale + 0.7f;
                                float dx = candidate.x - other.pos.x, dz = candidate.z - other.pos.z;
                                if (dx * dx + dz * dz < clearance * clearance) { occupied = true; break; }
                            }
                            if (occupied) continue;
                            spawn.pos = candidate;
                            found = true;
                            moved++;
                        }
                if (!found) Debug.LogWarning("RoadGame: no clear bridge-side position for prop " + spawn.id);
            }
            if (moved > 0) Debug.Log("RoadGame: moved " + moved + " props clear of the new bridge approaches.");
        }

        static bool NearBridge(Vector3 point, float padding, out Vector3 center, out Vector3 right, out float halfWidth)
        {
            center = Vector3.zero; right = Vector3.right; halfWidth = 0f;
            foreach (var bridge in layout.bridges)
            {
                float nearest = float.PositiveInfinity;
                Vector3 projection = Vector3.zero, normal = Vector3.right;
                float width = 0f;
                for (int i = 0; i < bridge.samples.Length - 1; i++)
                {
                    var a = bridge.samples[i]; var b = bridge.samples[i + 1];
                    var direction = new Vector3(b.x - a.x, 0f, b.z - a.z);
                    float length = direction.magnitude;
                    if (length < 1e-5f) continue;
                    var start = new Vector3(a.x, 0f, a.z);
                    float t = Vector3.Dot(point - start, direction) / (length * length);
                    // Include a car-length of clear approach beyond each foot of the bridge.
                    t = Mathf.Clamp(t, i == 0 ? -6f / length : 0f,
                        i == bridge.samples.Length - 2 ? 1f + 6f / length : 1f);
                    var q = start + direction * t;
                    float distance = (new Vector2(point.x - q.x, point.z - q.z)).sqrMagnitude;
                    if (distance >= nearest) continue;
                    nearest = distance; projection = q;
                    normal = new Vector3(direction.z, 0f, -direction.x) / length;
                    width = Mathf.Lerp(a.halfWidth, b.halfWidth, Mathf.Clamp01(t));
                }
                if (nearest <= (width + padding) * (width + padding))
                {
                    center = projection; right = normal; halfWidth = width;
                    return true;
                }
            }
            return false;
        }

        /// <summary>
        /// Build only after importing/binding the art: these extra children must not alter the original snapshot IDs.
        /// Old first-zone cliff blockers are disabled by ImportedLevel. The imported boulder dam supplies its exact
        /// mesh collider; the outline below also closes both river gaps so the car cannot leave along the water.
        /// </summary>
        public static void BuildBridgeColliders(Transform parent)
        {
            if (!Active) return;
            var root = new GameObject("DustFlats_v13_DrivingColliders").transform;
            root.SetParent(parent, false);
            BuildBoundaryColliders(root);
            foreach (var bridge in bridgeFloors) BuildBridgeColliders(root, bridge);
        }

        static void BuildBoundaryColliders(Transform parent)
        {
            var points = layout.outline;
            float area = 0f;
            for (int i = 0; i < points.Length; i++)
            {
                var a = points[i]; var b = points[(i + 1) % points.Length];
                area += a.x * b.z - b.x * a.z;
            }
            for (int i = 0; i < points.Length; i++)
            {
                var a = points[i]; var b = points[(i + 1) % points.Length];
                float x = (a.x + b.x) * 0.5f, z = (a.z + b.z) * 0.5f;
                if (z > 95f && x >= 15f && x <= 31f) continue;
                var direction = new Vector3(b.x - a.x, 0f, b.z - a.z);
                if (direction.sqrMagnitude < 1e-6f) continue;
                var outward = (area > 0f ? new Vector3(direction.z, 0f, -direction.x) :
                    new Vector3(-direction.z, 0f, direction.x)).normalized;
                MakeBox(parent, "Boundary_" + i, new Vector3(x, 1.6f, z) + outward * 0.38f,
                    Quaternion.LookRotation(direction), new Vector3(0.8f, 4.4f, direction.magnitude + 0.1f));
            }
        }

        static void BuildBridgeColliders(Transform parent, RibbonFloorPiece owner)
        {
            var bridge = owner.bridge;
            var samples = bridge.samples;
            float station = 0f;
            for (int i = 0; i < samples.Length - 1; i++)
            {
                var a = samples[i]; var b = samples[i + 1];
                var direction = new Vector3(b.x - a.x, 0f, b.z - a.z);
                float length = direction.magnitude;
                if (length < 1e-5f) continue;
                var rotation = Quaternion.LookRotation(direction);
                float top = Mathf.Min(a.y, b.y) - 0.12f;
                const float bottom = -0.65f;
                float halfWidth = Mathf.Min(a.halfWidth, b.halfWidth);
                // The visual girders have too little headroom for the car. This solid underside prevents entering
                // them from the river, but the deck's owner ignores it while driving above or flying off the bridge.
                var ledge = MakeBox(parent, bridge.name + "_Underside_" + i,
                    new Vector3((a.x + b.x) * 0.5f, (bottom + top) * 0.5f, (a.z + b.z) * 0.5f),
                    rotation, new Vector3(halfWidth * 2f, top - bottom, length + 0.05f));
                Ground.AddLedge(ledge, owner, Mathf.Max(a.y, b.y) - 0.1f);
                float midS = station + length * 0.5f;
                if (midS >= bridge.rampLength && midS <= bridge.totalLength - bridge.rampLength)
                {
                    var right = rotation * Vector3.right;
                    foreach (int sign in new[] { -1, 1 })
                        MakeBox(parent, bridge.name + "_Rail_" + i + "_" + sign,
                            new Vector3((a.x + b.x) * 0.5f, (a.y + b.y) * 0.5f + 0.62f, (a.z + b.z) * 0.5f) +
                                right * (sign * (halfWidth + 0.28f)),
                            rotation, new Vector3(0.2f, 0.92f, length + 0.05f));
                }
                station += length;
            }
        }

        static BoxCollider MakeBox(Transform parent, string name, Vector3 center, Quaternion rotation, Vector3 size)
        {
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            go.transform.position = center;
            go.transform.rotation = rotation;
            var box = go.AddComponent<BoxCollider>();
            box.size = size;
            return box;
        }

        sealed class RibbonFloorPiece : FloorPiece
        {
            public readonly Bridge bridge;
            float cachedX = float.NaN, cachedZ, cachedHeight;
            Vector3 cachedNormal;
            bool cachedContains;

            public RibbonFloorPiece(Bridge source)
            {
                bridge = source;
                name = source.name + "_DriveSurface";
                surface = source.name == "AP_Bridge_Road0" ? SurfaceKind.Asphalt : SurfaceKind.Metal;
                float x0 = float.PositiveInfinity, x1 = float.NegativeInfinity;
                float z0 = float.PositiveInfinity, z1 = float.NegativeInfinity;
                h0 = float.PositiveInfinity; h1 = float.NegativeInfinity;
                foreach (var p in source.samples)
                {
                    x0 = Mathf.Min(x0, p.x - p.halfWidth); x1 = Mathf.Max(x1, p.x + p.halfWidth);
                    z0 = Mathf.Min(z0, p.z - p.halfWidth); z1 = Mathf.Max(z1, p.z + p.halfWidth);
                    h0 = Mathf.Min(h0, p.y); h1 = Mathf.Max(h1, p.y);
                }
                rect = ORect.FromMinMax(x0, z0, x1, z1);
            }

            void Query(Vector2 local)
            {
                float x = local.x + rect.c.x, z = local.y + rect.c.y;
                if (x == cachedX && z == cachedZ) return;
                cachedX = x; cachedZ = z; cachedContains = false;
                cachedHeight = Ground.Void; cachedNormal = Vector3.up;
                float best = float.PositiveInfinity;
                int closest = -1;
                float closestT = 0f, closestRaw = 0f;
                var samples = bridge.samples;
                for (int i = 0; i < samples.Length - 1; i++)
                {
                    var a = samples[i]; var b = samples[i + 1];
                    float vx = b.x - a.x, vz = b.z - a.z;
                    float raw = ((x - a.x) * vx + (z - a.z) * vz) / Mathf.Max(1e-8f, vx * vx + vz * vz);
                    float t = Mathf.Clamp01(raw), dx = x - a.x - t * vx, dz = z - a.z - t * vz;
                    float distance = dx * dx + dz * dz;
                    if (distance >= best) continue;
                    best = distance; closest = i; closestT = t; closestRaw = raw;
                }
                if (closest < 0 || (closest == 0 && closestRaw < 0f) ||
                    (closest == samples.Length - 2 && closestRaw > 1f)) return;
                var p = samples[closest]; var q = samples[closest + 1];
                float width = Mathf.Lerp(p.halfWidth, q.halfWidth, closestT);
                if (best > width * width) return;
                cachedContains = true;
                cachedHeight = Mathf.Lerp(p.y, q.y, closestT);
                float lengthSq = (q.x - p.x) * (q.x - p.x) + (q.z - p.z) * (q.z - p.z);
                float gradient = (q.y - p.y) / Mathf.Max(1e-8f, lengthSq);
                cachedNormal = new Vector3(-(q.x - p.x) * gradient, 1f, -(q.z - p.z) * gradient).normalized;
            }

            public override bool Contains(Vector2 local) { Query(local); return cachedContains; }
            public override float Height(Vector2 local) { Query(local); return cachedHeight; }
            public override Vector3 Normal(Vector2 local) { Query(local); return cachedNormal; }
        }
    }
}
