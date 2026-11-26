using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    public class RepairStation
    {
        public Vector3 pos;
        public float radius = 4.3f;
        public int zone;
        public Transform glow;
    }

    public class Gate : MonoBehaviour
    {
        public int boundary;        // gate between zone boundary-1 and boundary
        public Transform barrier;
        public bool open;
        float anim = 1f;
        Collider[] barrierColliders;
        bool passageClear;

        public void SetOpen(bool o, bool animate)
        {
            barrierColliders = barrier.GetComponentsInChildren<Collider>(true);
            if (open == o && !animate) { Apply(open ? 1f : 0f); return; }
            open = o;
            anim = animate ? 0f : 1f;
            if (!animate) Apply(open ? 1f : 0f);
            if (!open) InvalidateNavigation();
            enabled = true;
        }

        void InvalidateNavigation()
        {
            Physics.SyncTransforms();
            NavGrid.Invalidate(boundary - 1);
            NavGrid.Invalidate(boundary);
        }

        void Apply(float k)
        {
            float y = open ? Mathf.Lerp(0, -4.6f, k) : 0f;
            barrier.localPosition = new Vector3(0, y, 0);
            bool clear = open && k >= 1f;
            if (barrierColliders != null)
                foreach (var c in barrierColliders) if (c != null) c.enabled = !clear;
            barrier.gameObject.SetActive(!clear);
            if (clear != passageClear)
            {
                passageClear = clear;
                InvalidateNavigation();
            }
        }

        void Update()
        {
            if (anim < 1f)
            {
                anim = Mathf.Min(1f, anim + Time.deltaTime / 1.6f);
                Apply(anim);
                barrier.localPosition += new Vector3(Mathf.Sin(Time.time * 60f) * 0.04f, 0, 0);
            }
            else enabled = false;
        }
    }

    /// <summary>Procedural world: 4 zones stacked to the north, roads, camps, props, enemies, bosses, gates, repair pads.</summary>
    public class World : MonoBehaviour
    {
        public static World I;

        public static readonly float[] GateX = { 0f, 22f, -26f, 14f };   // x of the gate on boundary b (b = 1..3)
        public const float MainRoadWidth = 9f;
        public const float BranchRoadWidth = 6f;
        public const float ActivateRadius = 72f;
        public const float DeactivateRadius = 86f;
        /// <summary>South end of the intro canyon (below it the car is out of the world).</summary>
        public const float SouthLimit = -258f;

        public readonly List<SpawnPoint> spawns = new List<SpawnPoint>();
        public readonly List<SpawnPoint>[] zoneSpawns = { new List<SpawnPoint>(), new List<SpawnPoint>(), new List<SpawnPoint>(), new List<SpawnPoint>() };
        public readonly List<Target> activeTargets = new List<Target>();
        public readonly List<RepairStation> stations = new List<RepairStation>();
        public readonly List<Gate> gates = new List<Gate>();
        public readonly List<List<Vector3>>[] roads = { new List<List<Vector3>>(), new List<List<Vector3>>(), new List<List<Vector3>>(), new List<List<Vector3>>() };
        public readonly List<float>[] roadWidths = { new List<float>(), new List<float>(), new List<float>(), new List<float>() };
        public readonly Vector3[] arenaCenters = new Vector3[4];
        public readonly SpawnPoint[] bossSpawns = new SpawnPoint[4];
        public readonly List<Vector3>[] camps = { new List<Vector3>(), new List<Vector3>(), new List<Vector3>(), new List<Vector3>() };
        public Vector3 startPos;

        Transform root;
        float tickTimer;
        readonly List<(Vector3 p, float r)> placed = new List<(Vector3, float)>();

        void Awake() { I = this; }

        // ------------------------------------------------------------------ generation
        public void Generate()
        {
            // Editor/export callers need to drain nested coroutines as well as the outer generator.
            var stack = new Stack<System.Collections.IEnumerator>();
            stack.Push(GenerateRoutine(null));
            while (stack.Count > 0)
            {
                var current = stack.Peek();
                if (!current.MoveNext()) { (current as System.IDisposable)?.Dispose(); stack.Pop(); }
                else if (current.Current is System.Collections.IEnumerator nested) stack.Push(nested);
            }
        }

        /// <summary>Which step of the world build is running (memory traces of the web build).</summary>
        public static string LoadPhase = "";

        public System.Collections.IEnumerator GenerateRoutine(System.Action<float> progress)
        {
            root = transform;
            var watch = System.Diagnostics.Stopwatch.StartNew();
            // hand-placed structures first (floors, holes, keep-out areas), so spawns and decor stay clear of them
            Ground.Clear();
            Models.RockColliderCount = 0; Models.RockColliderMs = 0;
            Structures.Plan();
            Terrain.Plan();
            DustFlatsSurfaces.Plan();
            WetlandSurfaces.Plan();
            AshenSurfaces.Plan();
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                LoadPhase = "zone" + zi;
                yield return GenerateZoneRoutine(zi);
                progress?.Invoke((zi + 1f) / (Content.ZoneCount + 1f));
                yield return null;
            }
            // ground (one chunk per zone, extended past the map edges; the intro canyon lies south of zone 1)
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                float zMin = Content.ZoneMinZ(zi) - (zi == 0 ? 160f : 0f);
                float zMax = Content.ZoneMaxZ(zi) + (zi == Content.ZoneCount - 1 ? 80f : 0f);
                LoadPhase = "ground" + zi;
                Models.GroundChunk(zMin, zMax, root, Structures.CellCut);
                progress?.Invoke(0.8f + 0.03f * (zi + 1f) / Content.ZoneCount);
                yield return null; // WebAssembly collects mesh-builder scratch data only between frames.
            }
            LoadPhase = "structures";
            yield return Structures.BuildRoutine(root);
            progress?.Invoke(0.84f);
            yield return null;
            var tTerrain = watch.ElapsedMilliseconds;
            LoadPhase = "terrain";
            Terrain.Build(root);
            tTerrain = watch.ElapsedMilliseconds - tTerrain;
            progress?.Invoke(0.85f);
            yield return null;
            // the intro road counts as asphalt (added after the zone's spawns were placed, so it does not move them)
            roads[0].Add(new List<Vector3> { new Vector3(0, 0, Structures.IntroSouthZ + 4f), new Vector3(0, 0, -100.5f) });
            roadWidths[0].Add(Structures.IntroRoadWidth);
            // outer walls
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                var z = Content.Zones[zi];
                LoadPhase = "walls" + zi;
                float zMin = Content.ZoneMinZ(zi), zMax = Content.ZoneMaxZ(zi);
                Models.CliffWall(new Vector3(-Content.ZoneHalfWidth - 4f, 0, zMin - 4f), new Vector3(-Content.ZoneHalfWidth - 4f, 0, zMax + 4f), z, 100 + zi, root, 10f, 9f);
                Models.CliffWall(new Vector3(Content.ZoneHalfWidth + 4f, 0, zMin - 4f), new Vector3(Content.ZoneHalfWidth + 4f, 0, zMax + 4f), z, 200 + zi, root, 10f, 9f);
                progress?.Invoke(0.85f + 0.02f * (zi + 1f) / Content.ZoneCount);
                yield return null;
            }
            var z0 = Content.Zones[0];
            // the south wall has a gap for the intro canyon; its barricade is cleared by the first jump
            // (these walls and the gates below are built a piece per frame: all in one frame grew the web player's
            // managed heap by 64 MiB, which it never gives back)
            LoadPhase = "wallsSouth";
            Models.CliffWall(new Vector3(-Content.ZoneHalfWidth - 6, 0, Content.ZoneMinZ(0) - 5f), new Vector3(-Structures.IntroWallX + 3f, 0, Content.ZoneMinZ(0) - 5f), z0, 300, root, 6f, 2.4f, 2.2f);
            Models.CliffWall(new Vector3(Structures.IntroWallX - 3f, 0, Content.ZoneMinZ(0) - 5f), new Vector3(Content.ZoneHalfWidth + 6, 0, Content.ZoneMinZ(0) - 5f), z0, 302, root, 6f, 2.4f, 2.2f);
            yield return null;
            LoadPhase = "wallsNorth";
            var zl = Content.Zones[Content.ZoneCount - 1];
            Models.CliffWall(new Vector3(-Content.ZoneHalfWidth - 6, 0, Content.ZoneMaxZ(Content.ZoneCount - 1) + 5f), new Vector3(Content.ZoneHalfWidth + 6, 0, Content.ZoneMaxZ(Content.ZoneCount - 1) + 5f), zl, 301, root, 10f, 9f);
            yield return null;
            // inner walls with gates
            for (int b = 1; b < Content.ZoneCount; b++)
            {
                var z = Content.Zones[b - 1];
                float zb = Content.ZoneMinZ(b);
                float gx = GateX[b];
                const float gap = 10f, tower = 4.6f;
                Models.CliffWall(new Vector3(-Content.ZoneHalfWidth - 6, 0, zb), new Vector3(gx - gap * 0.5f - tower + 0.6f, 0, zb), z, 400 + b, root, 5f, 2.6f, 2.0f);
                Models.CliffWall(new Vector3(gx + gap * 0.5f + tower - 0.6f, 0, zb), new Vector3(Content.ZoneHalfWidth + 6, 0, zb), z, 500 + b, root, 5f, 2.6f, 2.0f);
                var gateRoot = new GameObject("Gate" + b);
                gateRoot.transform.SetParent(root, false);
                gateRoot.transform.position = new Vector3(gx, 0, zb);
                Models.GateTowers(gateRoot.transform, z, gap);
                var barrierPivot = new GameObject("BarrierPivot").transform;
                barrierPivot.SetParent(gateRoot.transform, false);
                Models.GateBarrier(barrierPivot, gap);
                var gate = gateRoot.AddComponent<Gate>();
                gate.boundary = b;
                gate.barrier = barrierPivot;
                gates.Add(gate);
                LoadPhase = "gate" + b;
                yield return null;
            }
            // Graft the edited meshes before adding new collider objects: exported Unity IDs
            // refer to the original deterministic hierarchy, including animated gate parts.
            progress?.Invoke(0.88f);
            yield return null;
            LoadPhase = "import";
            yield return ImportedLevel.TryApplyRoutine(this, k => progress?.Invoke(0.88f + 0.10f * k));
            LoadPhase = "spawns";
            DustFlatsSurfaces.ApplySpawnPositions(spawns);
            DustFlatsSurfaces.BuildBridgeColliders(root);
            AshenSurfaces.ApplySpawnPositions(spawns);
            AshenSurfaces.BuildColliders(root);
            var tCheck = watch.ElapsedMilliseconds;
            ValidateSpawns();
            progress?.Invoke(1f);
            yield return null;
            Debug.Log($"RoadGame WORLD generated in {watch.ElapsedMilliseconds} ms (terrain {tTerrain} ms, spawn check {watch.ElapsedMilliseconds - tCheck} ms, rock colliders {Models.RockColliderCount} in {Models.RockColliderMs:0} ms)");
        }

        /// <summary>
        /// Every rock, wall and building now has a collider that matches it: a spawn whose body would stand inside one
        /// moves to the nearest free spot around (same zone, open ground); every other spawn keeps its exact place.
        /// </summary>
        void ValidateSpawns()
        {
            Physics.SyncTransforms();
            int moved = 0, stuck = 0;
            foreach (var sp in spawns)
            {
                if (sp.spec.kind == TargetKind.Boss) continue;
                float r = SpawnBodyRadius(sp);
                if (!SpawnBlocked(sp.pos, r)) continue;
                int zi = Content.ZoneIndexAt(sp.pos.z);
                float zMin = Content.ZoneMinZ(zi), zMax = Content.ZoneMaxZ(zi);
                var from = sp.pos;
                bool found = false;
                for (float d = 1.5f; d < 40f && !found; d += 1.5f)
                    for (int k = 0; k < 16 && !found; k++)
                    {
                        float a = (k / 16f + d * 0.017f) * Mathf.PI * 2f;
                        var p = from + new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a)) * d;
                        if (Mathf.Abs(p.x) > Content.ZoneHalfWidth - 6f || p.z < zMin + 6f || p.z > zMax - 6f) continue;
                        var g = Ground.Sample(p.x, p.z, from.y + 0.5f);
                        if (!g.valid || Mathf.Abs(g.h - from.y) > 0.3f) continue;
                        if (Structures.Excluded(p, r + 0.5f) && !Structures.Excluded(from, 0f)) continue;
                        if (SpawnBlocked(p, r)) continue;
                        sp.pos = new Vector3(p.x, g.h, p.z);
                        found = true;
                    }
                if (found) moved++; else stuck++;
            }
            Debug.Log($"RoadGame: spawns checked against obstacles: moved={moved} stuck={stuck} rockColliders={Models.RockColliderCount}");
        }

        static float SpawnBodyRadius(SpawnPoint sp) => Mathf.Max(0.4f, sp.spec.radius * sp.scale * (sp.spec.kind == TargetKind.Prop ? 0.85f : 0.75f));

        /// <summary>True when a body of radius r standing at p would overlap a rock, wall, building or gate.</summary>
        public static bool SpawnBlocked(Vector3 p, float r)
        {
            var a = p + Vector3.up * (0.3f + r);
            var b = p + Vector3.up * (0.3f + r + 1.0f);
            return Physics.CheckCapsule(a, b, r, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
        }

        /// <summary>One zone: roads, camps and the repair pad, then its spawns, then its decor. The parts run in separate
        /// frames: the web player collects the mesh-building scratch data only between frames, and one frame for the
        /// whole first zone grew its managed heap by ~40 MiB that it never gives back.</summary>
        System.Collections.IEnumerator GenerateZoneRoutine(int zi)
        {
            var zone = Content.Zones[zi];
            var rnd = new System.Random(1000 + zi * 31);
            float R() => (float)rnd.NextDouble();
            float zMin = Content.ZoneMinZ(zi), zMax = Content.ZoneMaxZ(zi);
            placed.Clear();

            // --- main road
            Vector3 start = zi == 0 ? new Vector3(0, 0, zMin + 6f) : new Vector3(GateX[zi], 0, zMin - 2f);
            Vector3 arena = zi < Content.ZoneCount - 1 ? new Vector3(GateX[zi + 1] * 0.6f, 0, zMax - 36f) : new Vector3(0, 0, zMax - 46f);
            arenaCenters[zi] = arena;
            var ctrl = new List<Vector3> { start, start + new Vector3(0, 0, 14f) };
            ctrl.Add(new Vector3(Mathf.Lerp(-40f, 40f, R()), 0, zMin + 62f));
            ctrl.Add(new Vector3(Mathf.Lerp(-40f, 40f, R()), 0, zMin + 112f));
            ctrl.Add(arena + new Vector3(0, 0, -28f));
            ctrl.Add(arena);
            if (zi < Content.ZoneCount - 1)
            {
                ctrl.Add(arena + new Vector3(0, 0, 22f));
                ctrl.Add(new Vector3(GateX[zi + 1], 0, zMax + 2f));
            }
            else ctrl.Add(arena + new Vector3(0, 0, 26f));
            var main = Spline(ctrl, 2.5f);
            roads[zi].Add(main);
            roadWidths[zi].Add(MainRoadWidth);

            // --- repair station near the zone entry
            Vector3 station = zi == 0 ? new Vector3(10f, 0, zMin + 24f) : new Vector3(GateX[zi] + 15f, 0, zMin + 22f);
            if (DistToRoads(zi, station) < 9.5f) station.x -= 30f;
            if (zi == 0) startPos = station + new Vector3(0, 0, 0.5f);
            var stGO = Models.RepairStation(root, out var glow);
            stGO.transform.position = station;
            stations.Add(new RepairStation { pos = station, zone = zi, glow = glow });
            Reserve(station, 9f);
            Reserve(arena, 21f);
            if (zi > 0) Reserve(new Vector3(GateX[zi], 0, zMin), 13f);
            Vector3 billboardPos = zi == 0 ? new Vector3(-12f, 0, zMin + 30f) : new Vector3(GateX[zi] - 13f, 0, zMin + 13f);
            Reserve(billboardPos, 4f);
            if (zi < Content.ZoneCount - 1) Reserve(new Vector3(GateX[zi + 1], 0, zMax), 13f);

            // --- arena decor (the first boss lives in the underground Mammoth Works instead)
            if (zi != 0)
            {
                var arenaGO = Models.ArenaRing(root, 18f, 40f, zone);
                arenaGO.transform.position = arena;
            }

            // --- camps
            int campCount = 3;
            for (int c = 0; c < campCount; c++)
            {
                for (int attempt = 0; attempt < 60; attempt++)
                {
                    float side = (c % 2 == 0) ? -1f : 1f;
                    if (attempt > 30) side = -side;
                    var p = new Vector3(side * Mathf.Lerp(38f, 74f, R()), 0, Mathf.Lerp(zMin + 40f, zMax - 52f, (c + R()) / campCount));
                    if (DistToRoads(zi, p) < 24f) continue;
                    if ((p - arena).magnitude < 40f || (p - station).magnitude < (zi == 0 ? 58f : 34f)) continue;
                    bool ok = true;
                    foreach (var other in camps[zi]) if ((other - p).magnitude < 42f) { ok = false; break; }
                    if (!ok) continue;
                    camps[zi].Add(p);
                    // branch road from camp to main road
                    var near = NearestOnPolyline(main, p);
                    var mid = Vector3.Lerp(p, near, 0.5f) + new Vector3(0, 0, (R() - 0.5f) * 10f);
                    var branch = Spline(new List<Vector3> { p, mid, near }, 2.5f);
                    roads[zi].Add(branch);
                    roadWidths[zi].Add(BranchRoadWidth);
                    break;
                }
            }
            foreach (var cp in camps[zi]) Reserve(cp, 3.5f);
            for (int c = 0; c < camps[zi].Count; c++)
            {
                var cp = camps[zi][c];
                var branch = roads[zi][c + 1];
                var dir = branch.Count > 3 ? branch[3] - cp : Vector3.forward;
                float ang = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                Models.Palisade(cp, 15.5f, ang, zone, 900 + zi * 10 + c, root);
            }

            // road meshes (not drawn where a road dips into an underpass: the structure builds its own deck there)
            for (int r = 0; r < roads[zi].Count; r++)
                foreach (var run in SplitAtGaps(roads[zi][r]))
                    Models.RoadRibbon(run, roadWidths[zi][r], zone, root, r == 0 ? 0.035f : 0.025f, Terrain.HeightAt);

            LoadPhase = "zone" + zi + "-spawns";
            yield return null;
            // --- spawn specs
            int idCounter = 0;
            foreach (var spec in zone.specs)
            {
                for (int k = 0; k < spec.count; k++)
                {
                    if (!FindSpot(zi, spec, k, rnd, main, out var pos)) continue;
                    var sp = new SpawnPoint
                    {
                        id = zi * 10000 + idCounter++,
                        spec = spec,
                        zone = zone,
                        pos = pos,
                        yaw = (spec.placement == Placement.Camp && spec.kind == TargetKind.Prop) ? FaceCampYaw(zi, pos, rnd) : (spec.kind == TargetKind.Prop && IsBuilding(spec.model) ? (R() - 0.5f) * 40f : R() * 360f),
                        variant = rnd.Next(3),
                        scale = spec.kind == TargetKind.Prop ? Mathf.Lerp(0.9f, 1.12f, R()) : 1f,
                    };
                    AddSpawn(zi, sp);
                }
            }
            // hidden stash chests (one-time gems)
            for (int c = 0; c < 2; c++)
            {
                var chestSpec = new SpawnSpec { model = ModelId.Chest, kind = TargetKind.Prop, name = "Hidden Stash", count = 1, hp = 30 * zone.mul, reward = Reward.Gem(25 * (zi + 1)), respawn = 1e9f, radius = 0.9f, height = 1.6f, oneTime = true };
                for (int attempt = 0; attempt < 80; attempt++)
                {
                    var p = new Vector3((c == 0 ? -1 : 1) * Mathf.Lerp(78f, 92f, R()), 0, Mathf.Lerp(zMin + 20f, zMax - 20f, R()));
                    if (!Free(p, 1.5f) || DistToRoads(zi, p) < 8f) continue;
                    Reserve(p, 1.5f);
                    AddSpawn(zi, new SpawnPoint { id = zi * 10000 + 9000 + c, spec = chestSpec, zone = zone, pos = p, yaw = R() * 60f - 30f, variant = 0 });
                    break;
                }
            }
            // boss (the Mammoth waits in the hangar of the Mammoth Works, under the ground)
            var bossSp = new SpawnPoint { id = zi * 10000 + 9500, spec = zone.boss, zone = zone, pos = arena, yaw = 180f, variant = 0 };
            if (zi == 0)
            {
                bossSp.pos = Structures.WorksBossHome;
                bossSp.arena = Structures.WorksArena;
                arenaCenters[0] = Structures.WorksBossHome;
            }
            AddSpawn(zi, bossSp);
            bossSpawns[zi] = bossSp;
            KeepClearOfStructures(zi);

            LoadPhase = "zone" + zi + "-decor";
            yield return null;
            // decor
            var area = new Rect(-Content.ZoneHalfWidth, zMin, Content.ZoneHalfWidth * 2f, zMax - zMin);
            Models.Decor(zone, area, 320, 77 + zi, p2 =>
            {
                var p = new Vector3(p2.x, 0, p2.y);
                if (Structures.Excluded(p, 1.5f)) return false;
                if (DistToRoads(zi, p) < 5.5f) return false;
                foreach (var st in stations) if ((st.pos - p).magnitude < 6.5f) return false;
                return true;
            }, root);
            // zone billboard near the entrance
            var bb = Models.Billboard(root, zone);
            bb.transform.position = billboardPos;
            bb.transform.rotation = Quaternion.Euler(0, 15f, 0);
        }

        static bool IsBuilding(ModelId m) => m == ModelId.Shack || m == ModelId.Tent || m == ModelId.Tower || m == ModelId.Hut;
        static bool IsRock(ModelId m) => m == ModelId.Boulder || m == ModelId.SaltRock || m == ModelId.ToxicRock || m == ModelId.RedRock;

        static readonly Dictionary<Mesh, float> rockRadius = new Dictionary<Mesh, float>();
        /// <summary>Collider radius that matches a rock prop as the car meets it: most of its outline at body height (0.25..1.4 m).</summary>
        static float FitRockRadius(GameObject go, float fallback)
        {
            var mf = go.GetComponentInChildren<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) return fallback;
            if (rockRadius.TryGetValue(mf.sharedMesh, out float r)) return r;
            var verts = mf.sharedMesh.vertices;
            var toRoot = go.transform.worldToLocalMatrix * mf.transform.localToWorldMatrix;
            var d = new List<float>();
            foreach (var v in verts)
            {
                var p = toRoot.MultiplyPoint3x4(v);
                if (p.y < 0.25f || p.y > 1.4f) continue;
                d.Add(new Vector2(p.x, p.z).magnitude);
            }
            if (d.Count < 8) { rockRadius[mf.sharedMesh] = fallback; return fallback; }
            d.Sort();
            r = d[Mathf.Clamp(Mathf.RoundToInt(d.Count * 0.85f), 0, d.Count - 1)];
            rockRadius[mf.sharedMesh] = r;
            return r;
        }

        /// <summary>Road polyline split into the runs that lie outside the structures' road gaps.</summary>
        static List<List<Vector3>> SplitAtGaps(List<Vector3> pts)
        {
            var runs = new List<List<Vector3>>();
            var cur = new List<Vector3>();
            foreach (var p in pts)
            {
                bool gap = false;
                foreach (var r in Structures.RoadGaps) if (r.Contains(new Vector2(p.x, p.z))) { gap = true; break; }
                if (gap) { if (cur.Count >= 2) runs.Add(cur); cur = new List<Vector3>(); }
                else cur.Add(p);
            }
            if (cur.Count >= 2) runs.Add(cur);
            return runs;
        }

        /// <summary>
        /// Spawns that ended up on a hand-placed structure (a ramp, the hangar, a tunnel) move to the nearest free
        /// spot; everything else keeps the exact place it always had. Two stashes move onto their plateaus.
        /// </summary>
        void KeepClearOfStructures(int zi)
        {
            float zMin = Content.ZoneMinZ(zi), zMax = Content.ZoneMaxZ(zi);
            foreach (var sp in zoneSpawns[zi])
            {
                if (sp.spec.kind == TargetKind.Boss) continue;
                if (sp.id == 9001) { sp.pos = Structures.PlateauChest0; continue; }
                if (sp.id == 9000) { sp.pos = Terrain.MesaChest; continue; }
                if (sp.id == 29001) { sp.pos = Structures.PlateauChest2; continue; }
                float r = sp.spec.radius * sp.scale;
                if (!Structures.Excluded(sp.pos, r + 0.8f)) continue;
                var from = sp.pos;
                bool found = false;
                for (float d = 4f; d < 70f && !found; d += 3f)
                    for (int k = 0; k < 16 && !found; k++)
                    {
                        float a = (k / 16f + d * 0.013f) * Mathf.PI * 2f;
                        var p = from + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * d;
                        if (Mathf.Abs(p.x) > Content.ZoneHalfWidth - 8f || p.z < zMin + 8f || p.z > zMax - 8f) continue;
                        if (Structures.Excluded(p, r + 1.2f)) continue;
                        if (sp.spec.kind != TargetKind.Vehicle && DistToRoads(zi, p) < r + (sp.spec.kind == TargetKind.Prop ? 2.5f : 1f)) continue;
                        if (!Free(p, r + 0.8f)) continue;
                        Reserve(p, r);
                        sp.pos = p;
                        found = true;
                    }
            }
        }

        /// <summary>One-time intro enemies (only for a new game): they live in the canyon south of zone 1.</summary>
        public SpawnPoint AddIntroSpawn(int id, SpawnSpec spec, Vector3 pos, float yaw)
        {
            var sp = new SpawnPoint { id = id, spec = spec, zone = Content.Zones[0], pos = pos, yaw = yaw, variant = 0 };
            AddSpawn(0, sp);
            return sp;
        }

        float FaceCampYaw(int zi, Vector3 pos, System.Random rnd)
        {
            // buildings keep their door side roughly toward the camera (south) with some jitter
            return ((float)rnd.NextDouble() - 0.5f) * 50f;
        }

        void AddSpawn(int zi, SpawnPoint sp)
        {
            sp.save = Game.I.progress.GetSpawn(sp.id);
            spawns.Add(sp);
            zoneSpawns[zi].Add(sp);
        }

        bool FindSpot(int zi, SpawnSpec spec, int k, System.Random rnd, List<Vector3> main, out Vector3 pos)
        {
            float R() => (float)rnd.NextDouble();
            float zMin = Content.ZoneMinZ(zi), zMax = Content.ZoneMaxZ(zi);
            float r = spec.radius * 1.1f;
            for (int attempt = 0; attempt < 60; attempt++)
            {
                Vector3 p;
                switch (spec.placement)
                {
                    case Placement.Camp:
                        {
                            if (camps[zi].Count == 0) goto default;
                            var c = camps[zi][(k + attempt) % camps[zi].Count];
                            if (spec.kind == TargetKind.Prop)
                            {
                                float a = R() * Mathf.PI * 2f;
                                float d = Mathf.Lerp(6f, 11.5f, R());
                                p = c + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * d;
                            }
                            else
                            {
                                var rr = Random2(rnd) * 6.5f;
                                p = c + new Vector3(rr.x, 0, rr.y);
                            }
                            break;
                        }
                    case Placement.Road:
                        {
                            int idx = Mathf.Clamp((int)(Mathf.Lerp(0.15f, 0.8f, R()) * main.Count), 1, main.Count - 2);
                            var dir = (main[idx + 1] - main[idx - 1]).normalized;
                            var right = new Vector3(dir.z, 0, -dir.x);
                            p = main[idx] + right * ((R() > 0.5f ? 1 : -1) * Mathf.Lerp(7f, 11f, R()));
                            break;
                        }
                    default:
                        p = new Vector3(Mathf.Lerp(-Content.ZoneHalfWidth + 8f, Content.ZoneHalfWidth - 8f, R()), 0, Mathf.Lerp(zMin + 8f, zMax - 8f, R()));
                        break;
                }
                if (zi == 0 && (p - startPos).magnitude < 12f) continue;
                if (spec.kind != TargetKind.Prop && spec.kind != TargetKind.Boss)
                {
                    // keep the area around repair pads calm (weak scavengers allowed a bit closer)
                    float calm = spec.kind == TargetKind.Vehicle ? 60f : (spec.model == ModelId.Scav ? 16f : 30f);
                    bool tooClose = false;
                    foreach (var st in stations) if ((st.pos - p).magnitude < calm) { tooClose = true; break; }
                    if (tooClose) continue;
                }
                if (spec.kind != TargetKind.Vehicle && DistToRoads(zi, p) < r + (spec.kind == TargetKind.Prop ? 2.5f : 1.0f)) continue;
                if (spec.placement != Placement.Camp && spec.kind == TargetKind.Prop)
                {
                    bool nearCamp = false;
                    foreach (var c in camps[zi]) if ((c - p).magnitude < 17f) { nearCamp = true; break; }
                    if (nearCamp) continue;
                }
                if (!Free(p, r + (spec.kind == TargetKind.Prop ? 1.2f : 0.6f))) continue;
                Reserve(p, r);
                pos = p;
                return true;
            }
            pos = Vector3.zero;
            return false;
        }

        static Vector2 Random2(System.Random rnd)
        {
            float a = (float)rnd.NextDouble() * Mathf.PI * 2f, d = Mathf.Sqrt((float)rnd.NextDouble());
            return new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * d;
        }

        bool Free(Vector3 p, float r)
        {
            foreach (var (q, qr) in placed)
            {
                float d = r + qr;
                if ((q - p).sqrMagnitude < d * d) return false;
            }
            return true;
        }

        void Reserve(Vector3 p, float r) => placed.Add((p, r));

        public float DistToRoads(int zi, Vector3 p)
        {
            float best = float.MaxValue;
            var list = roads[zi];
            for (int i = 0; i < list.Count; i++)
            {
                float d = DistToPolyline(list[i], p) - roadWidths[zi][i] * 0.5f;
                if (d < best) best = d;
            }
            return best;
        }

        public bool OnRoad(Vector3 p)
        {
            int zi = Content.ZoneIndexAt(p.z);
            return DistToRoads(zi, p) < 0f;
        }

        static float DistToPolyline(List<Vector3> pl, Vector3 p)
        {
            float best = float.MaxValue;
            for (int i = 0; i < pl.Count - 1; i++)
            {
                var a = pl[i]; var b = pl[i + 1];
                var ab = b - a; ab.y = 0;
                var ap = p - a; ap.y = 0;
                float t = Mathf.Clamp01(Vector3.Dot(ap, ab) / Mathf.Max(1e-4f, ab.sqrMagnitude));
                float d = (ap - ab * t).sqrMagnitude;
                if (d < best) best = d;
            }
            return Mathf.Sqrt(best);
        }

        static Vector3 NearestOnPolyline(List<Vector3> pl, Vector3 p)
        {
            float best = float.MaxValue; Vector3 res = pl[0];
            for (int i = 0; i < pl.Count - 1; i++)
            {
                var a = pl[i]; var b = pl[i + 1];
                var ab = b - a; var ap = p - a;
                float t = Mathf.Clamp01(Vector3.Dot(ap, ab) / Mathf.Max(1e-4f, ab.sqrMagnitude));
                var q = a + ab * t;
                float d = (q - p).sqrMagnitude;
                if (d < best) { best = d; res = q; }
            }
            return res;
        }

        static List<Vector3> Spline(List<Vector3> ctrl, float step)
        {
            var pts = new List<Vector3>();
            for (int i = 0; i < ctrl.Count - 1; i++)
            {
                var p0 = ctrl[Mathf.Max(0, i - 1)]; var p1 = ctrl[i]; var p2 = ctrl[i + 1]; var p3 = ctrl[Mathf.Min(ctrl.Count - 1, i + 2)];
                float len = (p2 - p1).magnitude;
                int n = Mathf.Max(2, Mathf.CeilToInt(len / step));
                for (int k = 0; k < n; k++)
                {
                    float t = k / (float)n;
                    pts.Add(CatmullRom(p0, p1, p2, p3, t));
                }
            }
            pts.Add(ctrl[ctrl.Count - 1]);
            return pts;
        }

        static Vector3 CatmullRom(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t)
        {
            float t2 = t * t, t3 = t2 * t;
            return 0.5f * ((2f * p1) + (-p0 + p2) * t + (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 + (-p0 + 3f * p1 - 3f * p2 + p3) * t3);
        }

        // ------------------------------------------------------------------ runtime
        public void ApplyGateStates(bool animate)
        {
            int unlocked = Game.I.progress.d.unlockedZone;
            foreach (var g in gates) g.SetOpen(unlocked >= g.boundary, animate && unlocked == g.boundary);
        }

        public RepairStation NearestStation(Vector3 p, int maxZone)
        {
            RepairStation best = null; float bd = float.MaxValue;
            foreach (var s in stations)
            {
                if (s.zone > maxZone) continue;
                float d = (s.pos - p).sqrMagnitude;
                if (d < bd) { bd = d; best = s; }
            }
            return best;
        }

        void Update()
        {
            if (Game.I == null || Game.I.player == null) return;
            // pulse repair glows
            float pulse = 1f + Mathf.Sin(Time.time * 3f) * 0.04f;
            foreach (var s in stations) if (s.glow) s.glow.localScale = new Vector3(4.4f * pulse, 1, 4.4f * pulse);

            tickTimer -= Time.deltaTime;
            if (tickTimer > 0) return;
            tickTimer = 0.2f;
            Tick();
        }

        public void Tick()
        {
            var p = Game.I.player.Pos;
            long now = Progress.NowMs;
            int pz = Content.ZoneIndexAt(p.z);
            for (int zi = Mathf.Max(0, pz - 1); zi <= Mathf.Min(Content.ZoneCount - 1, pz + 1); zi++)
            {
                var list = zoneSpawns[zi];
                for (int i = 0; i < list.Count; i++)
                {
                    var sp = list[i];
                    float d2 = (sp.pos - p).sqrMagnitude;
                    float act = sp.spec.kind == TargetKind.Boss ? ActivateRadius + 20f : ActivateRadius;
                    float deact = act + (DeactivateRadius - ActivateRadius);
                    bool deadNow = sp.IsDead(now);
                    var t = sp.target;
                    if (t != null && (t.dead || t.beingEaten) && t.gameObject.activeSelf)
                    {
                        // wreck waiting for / being harpooned: if it never gets eaten (player far away), hide it
                        if (!t.beingEaten && d2 > deact * deact) { t.beingEaten = false; t.gameObject.SetActive(false); activeTargets.Remove(t); }
                        continue;
                    }
                    if (deadNow)
                    {
                        if (t != null && t.gameObject.activeSelf) { t.gameObject.SetActive(false); activeTargets.Remove(t); }
                        continue;
                    }
                    if (d2 < act * act)
                    {
                        if (t == null) { t = CreateTarget(sp); }
                        if (!t.gameObject.activeSelf || t.dead)
                        {
                            bool anim = sp.pendingRespawnFx;
                            sp.pendingRespawnFx = false;
                            t.ResetForSpawn(anim);
                            if (anim) Game.I.fx.Puff(sp.pos, 1.2f + sp.spec.radius);
                            if (!activeTargets.Contains(t)) activeTargets.Add(t);
                        }
                    }
                    else if (t != null && t.gameObject.activeSelf && d2 > deact * deact)
                    {
                        t.gameObject.SetActive(false);
                        activeTargets.Remove(t);
                    }
                }
            }
            // deactivate far zones entirely
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                if (Mathf.Abs(zi - pz) <= 1) continue;
                foreach (var sp in zoneSpawns[zi])
                    if (sp.target != null && sp.target.gameObject.activeSelf && !sp.target.beingEaten)
                    {
                        sp.target.gameObject.SetActive(false);
                        activeTargets.Remove(sp.target);
                    }
            }
        }

        Target CreateTarget(SpawnPoint sp)
        {
            var go = Models.Create(sp.spec.model, sp.variant + sp.id, sp.zone, sp.spec.scale);
            go.transform.SetParent(root, false);
            ImportedLevel.ApplyTarget(sp, go);
            var rig = go.GetComponent<Rig>();
            Target t;
            if (sp.spec.kind == TargetKind.Prop)
            {
                t = go.AddComponent<Prop>();
                // obstacle collider for the car
                if (sp.spec.radius >= 0.6f)
                {
                    var c = go.AddComponent<CapsuleCollider>();
                    c.radius = IsRock(sp.spec.model) ? FitRockRadius(go, sp.spec.radius * 0.85f) : sp.spec.radius * 0.85f;
                    c.height = 4f;
                    c.center = new Vector3(0, 2f, 0);
                }
            }
            else
            {
                t = go.AddComponent<Enemy>();
            }
            t.Setup(sp, rig);
            sp.target = t;
            go.SetActive(false);
            return t;
        }

        public void OnTargetGone(Target t) { activeTargets.Remove(t); }

        /// <summary>Number of enemies currently fighting the player near p (drives the adaptive music).</summary>
        public int EnemiesEngaged(Vector3 p, float radius)
        {
            int n = 0;
            for (int i = 0; i < activeTargets.Count; i++)
            {
                if (!(activeTargets[i] is Enemy e) || !e.Engaged) continue;
                var d = e.Pos - p; d.y = 0;
                if (d.sqrMagnitude < radius * radius) n++;
            }
            return n;
        }

        /// <summary>
        /// Nearest targetable thing within range of a point (used by the car's weapons). Only targets on the same
        /// level and in plain sight count: nothing through the ground, a tunnel lid or a wall.
        /// </summary>
        public Target Nearest(Vector3 p, float range, Target prefer = null)
        {
            Target best = null; float bd = float.MaxValue;
            for (int i = 0; i < activeTargets.Count; i++)
            {
                var t = activeTargets[i];
                if (t == null || !t.Targetable) continue;
                var d = t.Pos - p;
                if (Mathf.Abs(d.y) > Ground.LevelGap) continue;
                d.y = 0;
                float dist = d.magnitude - t.Radius;
                if (dist > range) continue;
                // enemies that are attacking get a small priority boost
                float score = dist - (t.IsEnemy ? 0.75f : 0f) - (t == prefer ? 0.6f : 0f);
                if (score >= bd) continue;
                if (!InSight(p, t)) continue;
                bd = score; best = t;
            }
            return best;
        }

        /// <summary>Clear line between the car (gun height) and a target's body.</summary>
        public static bool InSight(Vector3 from, Target t)
        {
            var a = from + Vector3.up * 1.3f;
            var b = t.Pos + Vector3.up * Mathf.Clamp(t.BarHeight * 0.4f, 0.4f, 1.6f);
            return !Ground.Blocked(a, b);
        }

        public void ForEachInRadius(Vector3 p, float radius, System.Action<Target> a)
        {
            for (int i = activeTargets.Count - 1; i >= 0; i--)
            {
                var t = activeTargets[i];
                if (t == null || !t.Targetable) continue;
                var d = t.Pos - p;
                if (Mathf.Abs(d.y) > Ground.LevelGap) continue;
                d.y = 0;
                if (d.magnitude - t.Radius <= radius) a(t);
            }
        }
    }
}
