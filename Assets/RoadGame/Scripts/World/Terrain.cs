using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Natural terrain over the flat zones: rolling hills (a few right across the main road), rows of bumps for quick
    /// hops, packed-earth kickers, big jumps with a marked run-up, a low barrier to clear and a clear landing, rock
    /// ridges with a narrow pass through them, and the Lookout Mesa - a massif in the north-west of the Dust Flats with
    /// a switchback road (three ramps, two hairpins) up to a summit with a stash and a jump back down.
    /// Hills are smooth 2D floors (a fast car flies off their crests); every rock gets a collider of its own shape and
    /// every cliff a wall that stops cars below but lets a car above drive off; every feature keeps spawns and decor away.
    /// </summary>
    public static class Terrain
    {
        public class Hill { public MoundPiece p; public int zone; public bool road; }
        public class Kicker { public FloorPiece p; public int zone; }
        public class BigJump { public string name; public FloorPiece ramp; public Vector3 lip; public float yaw; public int zone; public float runUp; }
        public class Ridge { public string name; public Vector3 a, b; public float rockR, height; public int zone; public int seed; public Vector2[] gaps; }

        public static readonly List<Hill> Hills = new List<Hill>();
        public static readonly List<Kicker> Kickers = new List<Kicker>();
        public static readonly List<BigJump> BigJumps = new List<BigJump>();
        public static readonly List<Ridge> Ridges = new List<Ridge>();
        public static readonly List<FloorPiece> MesaFloors = new List<FloorPiece>();
        public static FloorPiece MesaJump;
        public static Vector3 MesaChest;

        // ---- Lookout Mesa (zone 0, north-west corner): levels and outline
        public const float MesaH1 = 2.7f, MesaH2 = 5.4f, MesaTop = 8f;
        /// <summary>Waypoints from the foot of the mesa up the switchback road to the summit (autopilot / tests).</summary>
        public static readonly Vector3[] MesaRoute =
        {
            new Vector3(-46.5f, 0f, 44f), new Vector3(-46.5f, 0f, 54f), new Vector3(-46.5f, MesaH1, 82f), new Vector3(-48f, MesaH1, 89.5f),
            new Vector3(-54.5f, MesaH1, 89f), new Vector3(-54.5f, MesaH1, 82f), new Vector3(-54.5f, MesaH2, 56f), new Vector3(-55f, MesaH2, 48f),
            new Vector3(-60f, MesaH2, 46.5f), new Vector3(-64f, MesaH2, 50f), new Vector3(-63.5f, MesaH2, 57f), new Vector3(-63.5f, MesaTop, 84f), new Vector3(-66f, MesaTop, 89f),
            new Vector3(-76f, MesaTop, 86f)
        };
        /// <summary>The summit's south edge (an 8 m drop onto open ground).</summary>
        public const float MesaTopSouthZ = 62f;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            Hills.Clear(); Kickers.Clear(); BigJumps.Clear(); Ridges.Clear(); MesaFloors.Clear();
            MesaJump = null; shadeMat = null;
        }

        static Vector3 Fwd(float yaw) => new Vector3(Mathf.Sin(yaw * Mathf.Deg2Rad), 0f, Mathf.Cos(yaw * Mathf.Deg2Rad));
        static Color H(string h) => Models.Hex(h);
        static Color Gl(string h, float a) { var c = H(h); c.a = a; return c; }
        static Color Sh(Color c, float k) => new Color(c.r * k, c.g * k, c.b * k, c.a);

        /// <summary>Height of the natural ground (hills) at a point: roads drape over it.</summary>
        public static float HeightAt(float x, float z)
        {
            float h = 0f;
            for (int i = 0; i < Hills.Count; i++)
            {
                var p = Hills[i].p;
                if (!p.rect.Contains(x, z)) continue;
                h = Mathf.Max(h, p.Height(p.rect.Local(x, z)));
            }
            return h;
        }

        // ================================================================== planning (floors, keep-out areas, map marks)
        /// <summary>Registers every terrain floor and keep-out area. Called right after Structures.Plan, before the zones generate.</summary>
        public static void Plan()
        {
            ResetStatics();
            // ---- zone 0: Dust Flats
            // hills across the main road: climbs and descents on the way, a little air at full speed
            AddHill("RoadHill0a", new Vector3(-20f, 0f, -53f), -38f, 9.5f, 11f, 1.5f, 0.2f, 0, true);
            AddHill("RoadHill0b", new Vector3(-28.5f, 0f, -12f), 9f, 9.5f, 11f, 1.6f, 0.2f, 0, true);
            AddHill("RoadHill0c", new Vector3(14f, 0f, 66f), -5f, 8.5f, 10f, 1.4f, 0.2f, 0, true);
            // open-ground hills: a climb with a view, a crest to fly off
            AddHill("Hill0a", new Vector3(77f, 0f, -77f), 20f, 14f, 13f, 3.0f, 0.1f, 0);
            AddHill("Hill0b", new Vector3(-68f, 0f, -80f), -15f, 12f, 12f, 2.4f, 0.1f, 0);
            AddHill("Hill0c", new Vector3(-12f, 0f, 61f), 30f, 10f, 10f, 2.0f, 0.1f, 0);
            AddHill("Hill0d", new Vector3(45f, 0f, -8f), 0f, 12f, 12f, 2.5f, 0.1f, 0);
            // rows of bumps: a hop over each one at speed
            BumpRow("Bumps0a", new Vector3(57f, 0f, -88f), 0f, 5, 6.2f, 0.65f, 0);
            BumpRow("Bumps0b", new Vector3(-4f, 0f, 39f), 0f, 4, 6.5f, 0.6f, 0);
            // kickers: short jumps off the road
            AddKicker("Kicker0a", new Vector3(22f, 0f, -79f), 20f, 0.9f, 0);
            AddKicker("Kicker0b", new Vector3(-42f, 0f, -61f), 45f, 0.85f, 0);
            AddKicker("Kicker0c", new Vector3(-46f, 0f, -6f), 0f, 0.9f, 0);
            AddKicker("Kicker0d", new Vector3(22f, 0f, -3f), 60f, 0.8f, 0);
            // the rock ridge south-east: a narrow pass through it, a jump over its low scrap barrier, or the long way round
            AddBigJump("BigJump0", new Vector3(38f, 0f, -62f), 0f, 2.8f, 22f, 0);
            AddRidge("Ridge0", new Vector3(20f, 0f, -53f), new Vector3(78f, 0f, -55f), 2.5f, 4.4f, 0, 811, new Vector2(10f, 26f), new Vector2(33f, 41f));
            PlanMesa();

            // ---- zone 1: Rust Canyon
            AddHill("RoadHill1a", new Vector3(-4f, 0f, 146f), -36f, 9.5f, 10f, 1.5f, 0.2f, 1, true);
            AddHill("Hill1a", new Vector3(65f, 0f, 150f), 10f, 14f, 13f, 3.0f, 0.1f, 1);
            AddHill("Hill1b", new Vector3(-76f, 0f, 280f), 0f, 11f, 11f, 2.2f, 0.1f, 1);
            AddHill("Hill1c", new Vector3(72f, 0f, 278f), -20f, 12f, 11f, 2.4f, 0.1f, 1);
            BumpRow("Bumps1a", new Vector3(-75f, 0f, 106f), 0f, 5, 6.5f, 0.65f, 1);
            AddKicker("Kicker1a", new Vector3(40f, 0f, 175f), -20f, 0.9f, 1);
            AddKicker("Kicker1b", new Vector3(-80f, 0f, 200f), 0f, 0.9f, 1);
            AddKicker("Kicker1c", new Vector3(55f, 0f, 262f), 0f, 0.85f, 1);
            AddBigJump("BigJump1", new Vector3(36f, 0f, 245f), 90f, 2.8f, 14f, 1);

            // ---- zone 2: Salt Flats
            AddHill("RoadHill2a", new Vector3(0f, 0f, 352f), 20f, 9f, 9f, 1.4f, 0.2f, 2, true);
            AddHill("Hill2a", new Vector3(62f, 0f, 322f), 0f, 14f, 13f, 3.0f, 0.1f, 2);
            AddHill("Hill2b", new Vector3(-76f, 0f, 470f), 15f, 12f, 12f, 2.4f, 0.1f, 2);
            AddHill("Hill2c", new Vector3(66f, 0f, 452f), -10f, 11f, 11f, 2.2f, 0.1f, 2);
            BumpRow("Bumps2a", new Vector3(-80f, 0f, 306f), 0f, 4, 6.5f, 0.6f, 2);
            AddKicker("Kicker2a", new Vector3(45f, 0f, 425f), 0f, 0.9f, 2);
            AddKicker("Kicker2b", new Vector3(-40f, 0f, 470f), 45f, 0.85f, 2);
            AddKicker("Kicker2c", new Vector3(-80f, 0f, 396f), 0f, 0.9f, 2);
            AddRidge("Ridge2", new Vector3(30f, 0f, 420f), new Vector3(76f, 0f, 410f), 2.3f, 4.0f, 2, 821, new Vector2(20f, 28f));

            // ---- zone 3: Toxic Marsh
            AddHill("RoadHill3a", new Vector3(19f, 0f, 550f), 0f, 9.5f, 10f, 1.5f, 0.2f, 3, true);
            AddHill("Hill3a", new Vector3(60f, 0f, 530f), 0f, 14f, 13f, 3.0f, 0.1f, 3);
            AddHill("Hill3b", new Vector3(-62f, 0f, 662f), 10f, 12f, 12f, 2.5f, 0.1f, 3);
            AddHill("Hill3c", new Vector3(-76f, 0f, 520f), 0f, 11f, 11f, 2.2f, 0.1f, 3);
            BumpRow("Bumps3a", new Vector3(55f, 0f, 630f), 0f, 5, 6.5f, 0.65f, 3);
            AddKicker("Kicker3a", new Vector3(-40f, 0f, 530f), 30f, 0.9f, 3);
            AddKicker("Kicker3b", new Vector3(65f, 0f, 676f), -30f, 0.85f, 3);
            AddBigJump("BigJump3", new Vector3(-30f, 0f, 545f), 0f, 2.8f, 18f, 3);
        }

        static MoundPiece AddHill(string name, Vector3 c, float yaw, float rx, float rz, float h, float plateau, int zone, bool road = false)
        {
            var p = new MoundPiece { name = name, rect = new ORect(c, yaw, rx, rz), top = h, plateau = plateau, h0 = 0f, h1 = 0f, surface = SurfaceKind.Sand, crestAir = true };
            Ground.Add(p);
            Hills.Add(new Hill { p = p, zone = zone, road = road });
            Structures.Exclusions.Add(new ORect(c, yaw, rx + (road ? 0f : 1.5f), rz + (road ? 0f : 1.5f)));
            return p;
        }

        static void BumpRow(string name, Vector3 start, float yaw, int count, float spacing, float h, int zone)
        {
            var f = Fwd(yaw);
            for (int i = 0; i < count; i++)
                AddHill(name + i, start + f * (i * spacing), yaw + (i % 2 == 0 ? 4f : -4f), 4.6f, 2.9f, h * (i % 2 == 0 ? 1f : 0.88f), 0f, zone);
        }

        static FloorPiece AddKicker(string name, Vector3 lip, float yaw, float h, int zone, float len = 4.2f, float halfW = 2.4f)
        {
            var f = Fwd(yaw);
            var p = Ground.Add(new FloorPiece
            {
                name = name, rect = new ORect(lip - f * (len * 0.5f), yaw, halfW, len * 0.5f), h0 = 0f, h1 = h, surface = SurfaceKind.Sand,
                easeIn = 0.35f, easeOut = 0f, launch = true, boost = 9.5f + h * 1.5f, enemyWalkable = false
            });
            Kickers.Add(new Kicker { p = p, zone = zone });
            // keep-out: a run-up, the kicker and the landing stay clear
            Structures.Exclusions.Add(new ORect(lip + f * -1.5f, yaw, halfW + 2.5f, len * 0.5f + 12f));
            Structures.Marks.Add(new Structures.MapMark { r = p.rect, c = new Color(0.95f, 0.75f, 0.25f) });
            return p;
        }

        static void AddBigJump(string name, Vector3 lip, float yaw, float h, float runUp, int zone)
        {
            var f = Fwd(yaw);
            const float len = 12f, halfW = 4.5f;
            var ramp = Structures.Ramp(name, new ORect(lip - f * (len * 0.5f), yaw, halfW, len * 0.5f), h, 14f);
            BigJumps.Add(new BigJump { name = name, ramp = ramp, lip = lip, yaw = yaw, zone = zone, runUp = runUp });
            // run-up lane, ramp, barrier and landing stay clear
            Structures.Exclusions.Add(new ORect(lip + f * ((24f - len - runUp) * 0.5f), yaw, halfW + 3f, (len + runUp + 24f) * 0.5f));
            Structures.Marks.Add(new Structures.MapMark { r = ramp.rect, c = new Color(0.95f, 0.75f, 0.25f) });
        }

        static void AddRidge(string name, Vector3 a, Vector3 b, float rockR, float height, int zone, int seed, params Vector2[] gaps)
        {
            Ridges.Add(new Ridge { name = name, a = a, b = b, rockR = rockR, height = height, zone = zone, seed = seed, gaps = gaps });
            var d = b - a; float len = d.magnitude; var dir = d / len;
            float yaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
            var r = new ORect((a + b) * 0.5f, yaw, rockR * 2.4f, len * 0.5f + rockR);
            Structures.Exclusions.Add(r);
            var zd = Content.Zones[zone];
            Structures.Marks.Add(new Structures.MapMark { r = new ORect((a + b) * 0.5f, yaw, rockR * 1.3f, len * 0.5f), c = Color.Lerp(zd.cliff, zd.cliffDark, 0.4f) });
        }

        static FloorPiece MesaFloor(string name, ORect r, float h0, float h1, SurfaceKind s)
        {
            var p = Ground.Add(new FloorPiece { name = name, rect = r, h0 = h0, h1 = h1, surface = s, easeIn = 0f, easeOut = 0f });
            MesaFloors.Add(p);
            return p;
        }

        static void PlanMesa()
        {
            // three ramps and two hairpins up the east face, a landing at the top of the last ramp, the summit to the west
            MesaFloor("MesaS1", ORect.FromMinMax(-50f, 52f, -43f, 84f), 0f, MesaH1, SurfaceKind.Asphalt);
            MesaFloor("MesaH1", ORect.FromMinMax(-59f, 84f, -43f, 94f), MesaH1, MesaH1, SurfaceKind.Asphalt);
            MesaFloor("MesaS2", new ORect(new Vector3(-54.5f, 0f, 69f), 180f, 4.5f, 15f), MesaH1, MesaH2, SurfaceKind.Asphalt);
            MesaFloor("MesaH2", ORect.FromMinMax(-68f, 44f, -50f, 54f), MesaH2, MesaH2, SurfaceKind.Asphalt);
            MesaFloor("MesaS3", ORect.FromMinMax(-68f, 54f, -59f, 84f), MesaH2, MesaTop, SurfaceKind.Asphalt);
            MesaFloor("MesaL3", ORect.FromMinMax(-68f, 84f, -59f, 94f), MesaTop, MesaTop, SurfaceKind.Asphalt);
            MesaFloor("MesaTop", ORect.FromMinMax(-96f, MesaTopSouthZ, -68f, 94f), MesaTop, MesaTop, SurfaceKind.Sand);
            // the quick way down: a steel ramp on the summit's south edge, over the drop onto the open ground
            MesaJump = Ground.Add(new FloorPiece
            {
                name = "MesaJump", rect = new ORect(new Vector3(-86f, 0f, 67.6f), 180f, 3.6f, 5f), h0 = MesaTop, h1 = MesaTop + 1.1f,
                surface = SurfaceKind.Metal, easeIn = 0.3f, easeOut = 0f, launch = true, boost = 12.5f, enemyWalkable = false
            });
            Structures.JumpRamps.Add(MesaJump);
            MesaChest = new Vector3(-84f, MesaTop, 86f);
            // the massif and the open ground under its big south face stay clear of spawns and decor
            Structures.Exclusions.Add(ORect.FromMinMax(-100f, 43f, -41f, 100f));
            Structures.Exclusions.Add(ORect.FromMinMax(-100f, 36f, -64f, 62f));
            var zd = Content.Zones[0];
            Structures.Marks.Add(new Structures.MapMark { r = ORect.FromMinMax(-96f, MesaTopSouthZ, -59f, 94f), c = Color.Lerp(zd.cliff, Color.white, 0.1f) });
            Structures.Marks.Add(new Structures.MapMark { r = ORect.FromMinMax(-68f, 44f, -43f, 94f), c = Color.Lerp(zd.cliff, zd.cliffDark, 0.5f) });
            foreach (var p in MesaFloors)
                if (p.surface == SurfaceKind.Asphalt) Structures.Marks.Add(new Structures.MapMark { r = new ORect(p.rect.Center, p.rect.Yaw, p.rect.half.x - 1f, p.rect.half.y), c = new Color(0.42f, 0.4f, 0.4f) });
        }

        // ================================================================== building (meshes, colliders)
        static Transform root;

        public static void Build(Transform parent)
        {
            root = new GameObject("Terrain").transform;
            root.SetParent(parent, false);
            float q = MeshBuilder.Quality;
            MeshBuilder.Quality = 1f;
            try
            {
                foreach (var h in Hills) BuildHill(h);
                foreach (var k in Kickers) BuildKicker(k);
                foreach (var j in BigJumps) BuildBigJump(j);
                foreach (var r in Ridges) BuildRidge(r);
                BuildMesa();
            }
            finally { MeshBuilder.Quality = q; }
        }

        static Transform Group(string name)
        {
            var t = new GameObject(name).transform;
            t.SetParent(root, false);
            return t;
        }

        static GameObject Emit(string name, MeshBuilder b, Transform parent, bool shadows = true, Material mat = null)
            => Models.MeshGO(name, b.Build(name), mat ?? Mats.Toon, parent, shadows);

        static void Box(Transform parent, string name, Vector3 min, Vector3 max)
        {
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            var c = go.AddComponent<BoxCollider>();
            c.center = (min + max) * 0.5f;
            c.size = max - min;
        }

        static BoxCollider BoxO(Transform parent, string name, Vector3 center, Vector3 size, float yaw)
        {
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(center, Quaternion.Euler(0f, yaw, 0f));
            var c = go.AddComponent<BoxCollider>();
            c.size = size;
            return c;
        }

        /// <summary>A thin ledge wall whose top runs from (a, topA) to (b, topB) 15 cm under the floor it borders, reaching below the ground.</summary>
        static void SlopedWall(Transform parent, string name, Vector3 a, Vector3 b, float topA, float topB, float thick, FloorPiece owner)
        {
            var ta = new Vector3(a.x, topA - 0.15f, a.z);
            var tb = new Vector3(b.x, topB - 0.15f, b.z);
            var along = tb - ta;
            float len = along.magnitude;
            var rot = Quaternion.LookRotation(along / len, Vector3.up);
            float h = Mathf.Max(topA, topB) + 1.4f;
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation((ta + tb) * 0.5f - (rot * Vector3.up) * (h * 0.5f), rot);
            var c = go.AddComponent<BoxCollider>();
            c.size = new Vector3(thick, h, len);
            Ground.AddLedge(c, owner, Mathf.Max(topA, topB) - 0.15f);
        }

        /// <summary>Axis-aligned ledge wall (top 15 cm under the floor it borders).</summary>
        static void Ledge(Transform parent, string name, Vector3 min, Vector3 max, FloorPiece owner)
        {
            var go = new GameObject(name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(parent, false);
            var c = go.AddComponent<BoxCollider>();
            c.center = (min + max) * 0.5f;
            c.size = max - min;
            Ground.AddLedge(c, owner, max.y);
        }

        // ------------------------------------------------------------------ hills
        static void BuildHill(Hill hl)
        {
            var p = hl.p;
            var r = p.rect;
            var zd = Content.Zones[hl.zone];
            float cell = Mathf.Clamp(Mathf.Min(r.half.x, r.half.y) / 5f, 0.7f, 1.5f);
            int nx = Mathf.Max(4, Mathf.CeilToInt(r.half.x * 2f / cell)), nz = Mathf.Max(4, Mathf.CeilToInt(r.half.y * 2f / cell));
            var verts = new List<Vector3>((nx + 1) * (nz + 1));
            var cols = new List<Color>(verts.Capacity);
            var norms = new List<Vector3>(verts.Capacity);
            var tris = new List<int>(nx * nz * 6);
            var inside = new bool[(nx + 1) * (nz + 1)];
            bool lin = QualitySettings.activeColorSpace == ColorSpace.Linear;
            var topTint = Color.Lerp(zd.ground, Color.white, 0.12f);
            var side = Color.Lerp(zd.groundAlt, zd.cliff, 0.18f);
            for (int j = 0; j <= nz; j++)
                for (int i = 0; i <= nx; i++)
                {
                    float lx = -r.half.x + i * (r.half.x * 2f / nx), lz = -r.half.y + j * (r.half.y * 2f / nz);
                    var l = new Vector2(lx, lz);
                    float rho = Mathf.Sqrt((lx * lx) / (r.half.x * r.half.x) + (lz * lz) / (r.half.y * r.half.y));
                    inside[j * (nx + 1) + i] = rho < 1.0f;
                    float h = p.Height(l);
                    // the mesh sits 4 cm low: where the hill fades into the flat ground the ground plane covers its rim
                    var w = r.World(lx, lz, h - 0.04f);
                    verts.Add(w);
                    var n = p.Normal(l);
                    norms.Add(n);
                    var c = Models.GroundColorAt(w.x, w.z);
                    float k = Mathf.Clamp01(h / Mathf.Max(0.1f, p.top));
                    c = Color.Lerp(c, topTint, k * k * 0.25f);
                    // relief shading: sunlit slopes lighter and warmer, the far side darker
                    float rs = Models.ReliefShade(n);
                    if (rs >= 0f) c = Color.Lerp(c, Color.Lerp(c, Color.white, 0.5f), rs / 0.22f * 0.5f);
                    else c = Color.Lerp(c, Color.Lerp(c * 0.6f, side, 0.3f), -rs / 0.32f);
                    c.a = 1f;
                    cols.Add(lin ? c.linear : c);
                }
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < nx; i++)
                {
                    int a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
                    if (!inside[a] && !inside[b] && !inside[c] && !inside[d]) continue;
                    tris.Add(a); tris.Add(c); tris.Add(b);
                    tris.Add(b); tris.Add(c); tris.Add(d);
                }
            var mesh = new Mesh { name = p.name };
            mesh.SetVertices(verts); mesh.SetNormals(norms); mesh.SetColors(cols); mesh.SetTriangles(tris, 0);
            mesh.SetUVs(1, new Vector2[verts.Count]);
            mesh.RecalculateBounds();
            var go = Models.MeshGO(p.name, mesh, Mats.Ground, root, p.top >= 1.8f);
            go.GetComponent<MeshRenderer>().receiveShadows = true;
            if (!hl.road && p.top >= 1.8f) HillDecor(p, zd);
        }

        /// <summary>A few stones and scrub on a hill's slopes and a cairn on top: depth cues for the high camera.</summary>
        static void HillDecor(MoundPiece p, ZoneDef zd)
        {
            var b = new MeshBuilder();
            var rnd = new System.Random(p.name.GetHashCode());
            float R() => (float)rnd.NextDouble();
            var stone = Color.Lerp(zd.cliff, zd.ground, 0.35f);
            var stoneTop = Color.Lerp(stone, Color.white, 0.18f);
            var scrub = zd.index == 3 ? H("#7E8C55") : (zd.index == 2 ? H("#C8C3B4") : (zd.index == 1 ? H("#B98A5E") : H("#BFA066")));
            var r = p.rect;
            int stones = 5 + rnd.Next(3), bushes = 3 + rnd.Next(3);
            for (int i = 0; i < stones + bushes; i++)
            {
                float a = R() * Mathf.PI * 2f, rho = Mathf.Lerp(0.3f, 0.85f, R());
                float lx = Mathf.Cos(a) * rho * r.half.x, lz = Mathf.Sin(a) * rho * r.half.y;
                var w = r.World(lx, lz, p.Height(new Vector2(lx, lz)) - 0.05f);
                if (i < stones)
                {
                    float s = 0.3f + R() * 0.35f;
                    b.Rock(w, new Vector3(s * 1.2f, s * 0.6f, s), stone, rnd.Next(), stoneTop, 0.16f, 1);
                }
                else
                {
                    float s = 0.38f + R() * 0.25f;
                    var top = Color.Lerp(scrub, Color.white, 0.12f);
                    b.Sphere(w + new Vector3(0, s * 0.35f, 0), new Vector3(s, s * 0.62f, s * 0.9f), scrub, 1, 0.12f, rnd.Next(), top);
                    b.Sphere(w + new Vector3(s * 0.7f, s * 0.2f, -s * 0.3f), new Vector3(s * 0.6f, s * 0.42f, s * 0.6f), scrub, 1, 0.12f, rnd.Next(), top);
                }
            }
            // cairn on the crest
            var c0 = r.World(0f, 0f, p.top - 0.05f);
            b.Rock(c0 + new Vector3(0f, 0.2f, 0f), new Vector3(0.55f, 0.3f, 0.5f), stone, rnd.Next(), stoneTop, 0.14f, 1);
            b.Rock(c0 + new Vector3(0.05f, 0.55f, 0f), new Vector3(0.38f, 0.24f, 0.34f), stone, rnd.Next(), stoneTop, 0.14f, 1);
            b.Rock(c0 + new Vector3(0f, 0.82f, 0.02f), new Vector3(0.24f, 0.18f, 0.22f), stoneTop, rnd.Next(), stoneTop, 0.14f, 1);
            Emit(p.name + "Decor", b, root);
        }

        // ------------------------------------------------------------------ kickers
        static void BuildKicker(Kicker k)
        {
            var p = k.p;
            var r = p.rect;
            var zd = Content.Zones[k.zone];
            var g = Group(p.name);
            var b = new MeshBuilder();
            var dirt = Color.Lerp(zd.groundAlt, H("#7A5236"), 0.45f);
            var dirtDark = Sh(dirt, 0.82f);
            var wood = H("#A8703F");
            int n = 8;
            for (int i = 0; i < n; i++)
            {
                float z0 = Mathf.Lerp(-r.half.y, r.half.y, i / (float)n), z1 = Mathf.Lerp(-r.half.y, r.half.y, (i + 1) / (float)n);
                float h0 = p.HeightLocal(z0), h1 = p.HeightLocal(z1);
                // deck in three strips: packed dirt with two darker wheel ruts
                float[] xs = { -r.half.x, -r.half.x * 0.55f, -r.half.x * 0.2f, r.half.x * 0.2f, r.half.x * 0.55f, r.half.x };
                for (int s = 0; s < xs.Length - 1; s++)
                {
                    var col = (s == 1 || s == 3) ? Sh(dirt, 0.9f) : dirt;
                    var a = r.World(xs[s], z0, h0 + 0.01f); var c = r.World(xs[s + 1], z0, h0 + 0.01f);
                    var d = r.World(xs[s + 1], z1, h1 + 0.01f); var e = r.World(xs[s], z1, h1 + 0.01f);
                    b.PolyOut(col, (a + d) * 0.5f - Vector3.up, a, e, d, c);
                }
                foreach (int s in new[] { -1, 1 })
                {
                    var a = r.World(s * r.half.x, z0, -0.02f); var c = r.World(s * r.half.x, z1, -0.02f);
                    var d = r.World(s * r.half.x, z1, h1); var e = r.World(s * r.half.x, z0, h0);
                    b.PolyOut(dirtDark, r.Center + Vector3.up * 0.3f, a, c, d, e);
                }
            }
            // the lip: a face of planks and a timber beam with a painted edge
            var bl = r.World(-r.half.x, r.half.y, -0.02f); var br = r.World(r.half.x, r.half.y, -0.02f);
            var tl = r.World(-r.half.x, r.half.y, p.h1); var tr = r.World(r.half.x, r.half.y, p.h1);
            b.PolyOut(Sh(wood, 0.85f), r.Center, bl, br, tr, tl);
            for (int i = 1; i < 4; i++)
            {
                float y = p.h1 * i / 4f;
                b.Box(r.World(0f, r.half.y + 0.02f, y), new Vector3(r.half.x * 2f, 0.04f, 0.03f), Quaternion.Euler(0f, r.Yaw, 0f), Sh(wood, 0.7f));
            }
            b.Box(r.World(0f, r.half.y - 0.15f, p.h1 + 0.04f), new Vector3(r.half.x * 2f + 0.1f, 0.1f, 0.3f), Quaternion.Euler(0f, r.Yaw, 0f), wood);
            Structures.HazardStripe(b, r.World(-r.half.x, r.half.y - 0.15f, 0f), r.World(r.half.x, r.half.y - 0.15f, 0f), 0.31f, 0.03f, p.h1 + 0.1f, 6);
            float slopeDeg = Mathf.Atan(p.SlopeLocal(0f)) * Mathf.Rad2Deg;
            Structures.Chevron(b, r.World(0f, -r.half.y * 0.15f, p.HeightLocal(-r.half.y * 0.15f) + 0.04f), r.Yaw, Mathf.Min(2.6f, r.half.x * 1.1f), Gl("#FFD24A", 0.6f), -slopeDeg);
            // a tire half-buried at each front corner (readable from the camera as "a jump")
            foreach (int s in new[] { -1, 1 })
            {
                b.Push(r.World(s * (r.half.x + 0.5f), r.half.y - 0.5f, 0f), Quaternion.Euler(0f, r.Yaw, 0f));
                b.Cylinder(new Vector3(0f, 0f, 0f), 0.42f, 0.32f, 10, H("#2E2A2A"), -1, H("#1A1818"));
                b.Pop();
            }
            Emit(p.name, b, g);
            // sides: ledges under the deck's edge where it is higher than a step (a car beside the kicker is stopped, a car
            // on it can drive off the side); behind the lip a low wall
            float zStart = -r.half.y;
            for (int i = 0; i <= 40; i++)
            {
                float lz = Mathf.Lerp(-r.half.y, r.half.y, i / 40f);
                if (p.HeightLocal(lz) > 0.5f) { zStart = lz; break; }
            }
            foreach (int s in new[] { -1, 1 })
                SlopedWall(g, "KickerSide", r.World(s * (r.half.x + 0.15f), zStart, 0f), r.World(s * (r.half.x + 0.15f), r.half.y, 0f), p.HeightLocal(zStart), p.h1, 0.3f, p);
            // the low wall behind the lip stops a car coming from behind; a car on the kicker itself ignores it like the side
            // ledges (its level hull overhangs the lip before the centre gets there and must not snag on the wall's top)
            var back = BoxO(g, "KickerBack", r.World(0f, r.half.y + 0.25f, p.h1 * 0.275f), new Vector3(r.half.x * 2f, p.h1 * 0.55f, 0.4f), r.Yaw);
            Ground.AddLedge(back, p, p.h1 * 0.55f);
        }

        // ------------------------------------------------------------------ big jumps
        static void BuildBigJump(BigJump j)
        {
            var g = Group(j.name + "Course");
            var zd = Content.Zones[j.zone];
            var f = Fwd(j.yaw);
            var right = new Vector3(f.z, 0f, -f.x);
            var rot = Quaternion.Euler(0f, j.yaw, 0f);
            var b = new MeshBuilder();
            // run-up lane: painted chevrons and tire stacks along both edges
            float rampLen = j.ramp.rect.half.y * 2f;
            var laneStart = j.lip - f * (rampLen + j.runUp);
            for (float d = 2f; d < j.runUp - 1f; d += 5f)
                Structures.Chevron(b, laneStart + f * d + Vector3.up * 0.05f, j.yaw, 3.4f, Gl("#FFD24A", 0.5f));
            for (float d = 0f; d <= j.runUp; d += 7f)
                foreach (int s in new[] { -1, 1 })
                {
                    var p = laneStart + f * d + right * (s * 5.6f);
                    for (int k = 0; k < 2; k++) b.Cylinder(p + Vector3.up * (k * 0.26f), 0.42f, 0.25f, 10, H("#2E2A2A"), -1, (k == 1 && ((int)(d / 7f)) % 2 == 0) ? H("#E9B23B") : H("#1A1818"));
                }
            // the barrier the jump clears: a row of wrecked cars and scrap, 1.3 m tall (too tall to drive over)
            var bc = j.lip + f * 8.5f;
            var rnd = new System.Random(j.name.GetHashCode());
            float R() => (float)rnd.NextDouble();
            for (int i = -3; i <= 3; i++)
            {
                var p = bc + right * (i * 2.15f) + f * ((R() - 0.5f) * 0.6f);
                var col = i % 3 == 0 ? H("#A9552C") : i % 3 == 1 ? H("#6F8592") : H("#9A7A42");
                b.Push(p, rot * Quaternion.Euler(R() * 6f - 3f, 90f + R() * 14f - 7f, R() * 8f - 4f));
                b.Material(0.3f, 0.25f);
                b.BevelBox(new Vector3(0f, 0.55f, 0f), new Vector3(1.8f, 1.05f, 2.1f), 0.12f, col, Sh(col, 1.1f));
                b.Matte();
                b.Box(new Vector3(0f, 1.1f, 0.1f), new Vector3(1.4f, 0.12f, 1.2f), Sh(col, 0.85f));
                b.Pop();
                if (i % 2 == 0) b.Cylinder(p + f * 0.9f + Vector3.up * 0.0f, 0.42f, 0.3f, 10, H("#2E2A2A"), -1, H("#1A1818"));
            }
            Structures.HazardStripe(b, bc - right * 7.6f - f * 1.25f, bc + right * 7.6f - f * 1.25f, 0.12f, 0.25f, 1.2f, 12);
            // landing: two painted bars
            foreach (float d in new[] { 15f, 22f })
                b.Box(j.lip + f * d + Vector3.up * 0.03f, new Vector3(7f, 0.02f, 0.5f), rot, Gl("#ECE5D8", 0.55f));
            Emit(j.name + "Course", b, g);
            BoxO(g, "JumpBarrier", bc + Vector3.up * 0.65f, new Vector3(15.2f, 1.3f, 2.4f), j.yaw);
        }

        // ------------------------------------------------------------------ rock ridges (with a pass)
        static void BuildRidge(Ridge rg)
        {
            var g = Group(rg.name);
            var zd = Content.Zones[rg.zone];
            var d = rg.b - rg.a; float len = d.magnitude; var dir = d / len;
            var right = new Vector3(dir.z, 0f, -dir.x);
            var b = new MeshBuilder();
            var hulls = new List<Vector3[]>();
            var rnd = new System.Random(rg.seed);
            float R() => (float)rnd.NextDouble();
            var top = Color.Lerp(zd.cliff, Color.white, 0.18f);
            float step = rg.rockR * 1.5f;
            for (float t = 0f; t <= len; t += step)
                for (int row = 0; row < 2; row++)
                {
                    float tt = t + (row == 1 ? step * 0.5f : 0f) + (R() - 0.5f) * 1.2f;
                    float r = rg.rockR * (0.85f + R() * 0.4f) * (row == 1 ? 0.85f : 1f);
                    // keep the passes clear: no rock reaches into a gap
                    bool blocked = false;
                    foreach (var gap in rg.gaps) if (tt + r * 1.25f > gap.x && tt - r * 1.25f < gap.y) { blocked = true; break; }
                    if (blocked || tt < -0.5f || tt > len + 0.5f) continue;
                    float h = rg.height * (0.75f + R() * 0.45f) * (row == 1 ? 0.8f : 1f);
                    var p = rg.a + dir * tt + right * ((row - 0.5f) * rg.rockR * 1.1f + (R() - 0.5f) * 0.8f);
                    b.Push(p, Quaternion.Euler(0f, R() * 360f, 0f));
                    b.rockHulls = hulls;
                    b.Rock(new Vector3(0f, h * 0.36f, 0f), new Vector3(r, h * 0.62f, r * 0.85f), R() > 0.5f ? zd.cliff : zd.cliffDark, rnd.Next(), top, 0.24f, 2);
                    b.rockHulls = null;
                    b.Pop();
                }
            // pass markers: a pair of cairns with a painted post at each end of a pass
            foreach (var gap in rg.gaps)
                foreach (float t in new[] { gap.x, gap.y })
                    foreach (int s in new[] { -1, 1 })
                    {
                        var p = rg.a + dir * t + right * (s * rg.rockR * 1.6f);
                        b.Cylinder(p, 0.1f, 1.8f, 6, H("#5A3D2B"));
                        b.Box(p + Vector3.up * 1.7f, new Vector3(0.26f, 0.32f, 0.26f), H("#E9B23B"));
                    }
            Emit(rg.name, b, g);
            Models.RockColliders(g, rg.name + "Rocks", hulls);
        }

        // ------------------------------------------------------------------ Lookout Mesa
        static FloorPiece Mesa(string name) => MesaFloors.Find(p => p.name == name);

        static void BuildMesa()
        {
            var g = Group("LookoutMesa");
            var zd = Content.Zones[0];
            var s1 = Mesa("MesaS1"); var h1 = Mesa("MesaH1"); var s2 = Mesa("MesaS2"); var h2 = Mesa("MesaH2");
            var s3 = Mesa("MesaS3"); var l3 = Mesa("MesaL3"); var top = Mesa("MesaTop");
            // heights along the north-south ramps as functions of z
            float S1(float z) => Mathf.Lerp(0f, MesaH1, Mathf.InverseLerp(52f, 84f, z));
            float S2(float z) => Mathf.Lerp(MesaH2, MesaH1, Mathf.InverseLerp(54f, 84f, z));
            float S3(float z) => Mathf.Lerp(MesaH2, MesaTop, Mathf.InverseLerp(54f, 84f, z));

            // ---- colliders: walls just inside an upper floor's edge (a car above drives off it, a car below is stopped),
            //      thin walls just outside the open edges, rims where the massif meets the map's walls
            SlopedWall(g, "MesaWallS2", new Vector3(-50.15f, 0f, 54f), new Vector3(-50.15f, 0f, 84f), MesaH2, MesaH1, 0.3f, s2);
            Ledge(g, "MesaWallH2", new Vector3(-50.3f, -1f, 43.7f), new Vector3(-50f, MesaH2 - 0.15f, 54f), h2);
            SlopedWall(g, "MesaWallS3", new Vector3(-59.15f, 0f, 54f), new Vector3(-59.15f, 0f, 84f), MesaH2, MesaTop, 0.3f, s3);
            Ledge(g, "MesaWallL3", new Vector3(-59.3f, -1f, 84f), new Vector3(-59f, MesaTop - 0.15f, 94f), l3);
            Ledge(g, "MesaWallTop", new Vector3(-68.3f, -1f, MesaTopSouthZ), new Vector3(-68f, MesaTop - 0.15f, 84f), top);
            SlopedWall(g, "MesaEdgeS1", new Vector3(-43.15f, 0f, 52f), new Vector3(-43.15f, 0f, 84f), 0f, MesaH1, 0.3f, s1);
            Ledge(g, "MesaEdgeH1", new Vector3(-43.3f, -1f, 84f), new Vector3(-43f, MesaH1 - 0.15f, 94f), h1);
            Ledge(g, "MesaEdgeH2S", new Vector3(-68f, -1f, 44f), new Vector3(-50f, MesaH2 - 0.15f, 44.3f), h2);
            Ledge(g, "MesaEdgeH2W", new Vector3(-68f, -1f, 44f), new Vector3(-67.7f, MesaH2 - 0.15f, 54f), h2);
            SlopedWall(g, "MesaEdgeS3", new Vector3(-67.85f, 0f, 54f), new Vector3(-67.85f, 0f, MesaTopSouthZ), MesaH2, S3(MesaTopSouthZ), 0.3f, s3);
            Ledge(g, "MesaEdgeTop", new Vector3(-96f, -1f, MesaTopSouthZ), new Vector3(-68f, MesaTop - 0.15f, MesaTopSouthZ + 0.3f), top);
            Box(g, "MesaRimH1", new Vector3(-59f, -1f, 94f), new Vector3(-42.7f, MesaH1 + 1.3f, 94.6f));
            Box(g, "MesaRimTop", new Vector3(-96.6f, -1f, 94f), new Vector3(-59f, MesaTop + 1.3f, 94.6f));
            Box(g, "MesaRimWest", new Vector3(-96.6f, -1f, MesaTopSouthZ), new Vector3(-96f, MesaTop + 1.3f, 94f));

            // ---- rock faces, each with a soft shadow band at its foot (reads as a step from the high camera)
            var rock = new MeshBuilder();
            bandV.Clear(); bandC.Clear(); bandT.Clear();
            int seed = 900;
            // separators (seen from the lower road) and open edges (seen from the ground); a face looks to the right of a->c
            Face(rock, new Vector3(-50f, 0f, 54f), new Vector3(-50f, 0f, 84f), t => S2(Mathf.Lerp(54f, 84f, t)), zd, seed++, false, t => S1(Mathf.Lerp(54f, 84f, t)));     // S2 -> S1 (east)
            Face(rock, new Vector3(-50f, 0f, 44f), new Vector3(-50f, 0f, 54f), t => MesaH2, zd, seed++, false, t => 0f);                                                       // H2 -> ground (east)
            Face(rock, new Vector3(-59f, 0f, 84f), new Vector3(-59f, 0f, 94f), t => MesaTop, zd, seed++, false, t => MesaH1);                                                  // L3 -> H1 (east)
            Face(rock, new Vector3(-59f, 0f, 54f), new Vector3(-59f, 0f, 84f), t => S3(Mathf.Lerp(54f, 84f, t)), zd, seed++, false, t => S2(Mathf.Lerp(54f, 84f, t)));     // S3 -> S2 (east)
            Face(rock, new Vector3(-68f, 0f, MesaTopSouthZ), new Vector3(-68f, 0f, 84f), t => MesaTop, zd, seed++, true, t => S3(Mathf.Lerp(MesaTopSouthZ, 84f, t)));      // summit -> S3 (east)
            Face(rock, new Vector3(-43f, 0f, 52f), new Vector3(-43f, 0f, 94f), t => t < 32f / 42f ? S1(Mathf.Lerp(52f, 94f, t)) : MesaH1, zd, seed++, false, t => 0f);   // S1 / H1 (east)
            Face(rock, new Vector3(-68f, 0f, 44f), new Vector3(-50f, 0f, 44f), t => MesaH2, zd, seed++, false, t => 0f);                                                       // H2 (south)
            Face(rock, new Vector3(-68f, 0f, 54f), new Vector3(-68f, 0f, 44f), t => MesaH2, zd, seed++, false, t => 0f);                                                       // H2 (west)
            Face(rock, new Vector3(-68f, 0f, MesaTopSouthZ), new Vector3(-68f, 0f, 54f), t => S3(Mathf.Lerp(MesaTopSouthZ, 54f, t)), zd, seed++, false, t => 0f);           // S3 (west, open part)
            Face(rock, new Vector3(-96f, 0f, MesaTopSouthZ), new Vector3(-68f, 0f, MesaTopSouthZ), t => MesaTop, zd, seed++, false, t => 0f);                                // summit (south): the big face
            Face(rock, new Vector3(-43f, 0f, 94f), new Vector3(-59f, 0f, 94f), t => MesaH1 + 0.2f, zd, seed++);                                                                 // backs (north, west)
            Face(rock, new Vector3(-59f, 0f, 94f), new Vector3(-96f, 0f, 94f), t => MesaTop + 0.2f, zd, seed++);
            Face(rock, new Vector3(-96f, 0f, 94f), new Vector3(-96f, 0f, MesaTopSouthZ), t => MesaTop + 0.2f, zd, seed++);
            var bandMesh = new Mesh { name = "MesaShadowBands" };
            bandMesh.SetVertices(bandV); bandMesh.SetColors(bandC); bandMesh.SetTriangles(bandT, 0);
            bandMesh.RecalculateBounds();
            if (shadeMat == null)
            {
                shadeMat = Mats.NewUnlit("MesaShade", null, false);
                shadeMat.SetColor("_BaseColor", Color.white);
                shadeMat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent - 30;
            }
            Models.MeshGO("MesaShadowBands", bandMesh, shadeMat, g, false);
            // stones along the open edges up top: where the road ends and the drop begins
            var edge = new MeshBuilder();
            var ernd = new System.Random(91);
            float ER() => (float)ernd.NextDouble();
            var estone = Color.Lerp(zd.cliff, Color.white, 0.35f);
            void EdgeRow(Vector3 a, Vector3 c, System.Func<Vector3, float> hAt, float skipX0 = 1f, float skipX1 = 0f)
            {
                float len = Vector3.Distance(new Vector3(a.x, 0f, a.z), new Vector3(c.x, 0f, c.z));
                for (float d = 0.8f; d < len - 0.5f; d += 1.7f + ER() * 0.6f)
                {
                    var p = Vector3.Lerp(a, c, d / len);
                    if (p.x > skipX0 && p.x < skipX1) continue;
                    p.y = hAt(p);
                    float sz = 0.2f + ER() * 0.14f;
                    edge.Rock(p + Vector3.up * 0.08f, new Vector3(sz * 1.2f, sz * 0.7f, sz), estone, ernd.Next(), Color.Lerp(estone, Color.white, 0.2f), 0.16f, 1);
                }
            }
            EdgeRow(new Vector3(-43.45f, 0f, 58f), new Vector3(-43.45f, 0f, 93.5f), q => q.z < 84f ? S1(q.z) : MesaH1);
            EdgeRow(new Vector3(-67f, 0f, 44.45f), new Vector3(-50.6f, 0f, 44.45f), q => MesaH2);
            EdgeRow(new Vector3(-67.55f, 0f, 44.6f), new Vector3(-67.55f, 0f, 61.5f), q => q.z < 54f ? MesaH2 : S3(q.z));
            EdgeRow(new Vector3(-95.5f, 0f, MesaTopSouthZ + 0.45f), new Vector3(-68.5f, 0f, MesaTopSouthZ + 0.45f), q => MesaTop, -91f, -81f);
            Emit("MesaEdgeStones", edge, g);

            // rim stones along the north and west edges, boulders at the corners of the big face (shaped colliders)
            var hulls = new List<Vector3[]>();
            var rnd = new System.Random(77);
            float R() => (float)rnd.NextDouble();
            var rockTop = Color.Lerp(zd.cliff, Color.white, 0.18f);
            rock.rockHulls = hulls;
            for (float x = -58f; x < -43.5f; x += 2.6f)
                rock.Rock(new Vector3(x + R() * 0.6f, MesaH1 + 0.35f, 93.6f), new Vector3(0.9f + R() * 0.3f, 0.6f, 0.7f), R() > 0.5f ? zd.cliff : zd.cliffDark, rnd.Next(), rockTop, 0.2f, 1);
            for (float x = -95f; x < -59.5f; x += 2.8f)
                rock.Rock(new Vector3(x + R() * 0.6f, MesaTop + 0.35f, 93.6f), new Vector3(1.0f + R() * 0.3f, 0.65f, 0.75f), R() > 0.5f ? zd.cliff : zd.cliffDark, rnd.Next(), rockTop, 0.2f, 1);
            for (float z = 64f; z < 93f; z += 2.8f)
                rock.Rock(new Vector3(-95.6f, MesaTop + 0.35f, z + R() * 0.6f), new Vector3(0.75f, 0.65f, 1.0f + R() * 0.3f), R() > 0.5f ? zd.cliff : zd.cliffDark, rnd.Next(), rockTop, 0.2f, 1);
            foreach (var c in new[] { new Vector3(-97.5f, 0f, 60.5f), new Vector3(-41.6f, 0f, 49f), new Vector3(-41.2f, 0f, 92f) })
                rock.Rock(c + Vector3.up * 1.3f, new Vector3(2.4f, 2.2f, 2.1f), zd.cliffDark, rnd.Next(), rockTop, 0.24f, 2);
            rock.rockHulls = null;
            Emit("MesaRock", rock, g);
            Models.RockColliders(g, "MesaRocks", hulls);

            // ---- floors: the summit and the hairpins in ground colours, the ramps as a road with its markings
            var deck = new MeshBuilder();
            Deck(deck, top, zd, 0f, 1f, 0.28f);
            Deck(deck, h1, zd, 0.35f, 0f);
            Deck(deck, h2, zd, 0.35f, 0f);
            Deck(deck, l3, zd, 0.35f, 0f);
            foreach (var p in new[] { s1, s2, s3 }) Deck(deck, p, zd, 0.35f, 0f);
            // hairpin arrows: which way the road turns
            Structures.Chevron(deck, new Vector3(-51f, MesaH1 + 0.05f, 89f), -90f, 3.0f, Gl("#FFD24A", 0.55f));
            Structures.Chevron(deck, new Vector3(-59f, MesaH2 + 0.05f, 49f), -90f, 3.0f, Gl("#FFD24A", 0.55f));
            Structures.Chevron(deck, new Vector3(-63.5f, MesaTop + 0.05f, 89f), -90f, 3.0f, Gl("#FFD24A", 0.55f));
            var deckGo = Models.MeshGO("MesaDecks", deck.Build("MesaDecks"), Mats.Ground, g, false);
            deckGo.GetComponent<MeshRenderer>().receiveShadows = true;
            Models.RoadRibbon(new List<Vector3> { new Vector3(-46.5f, 0f, 50f), new Vector3(-46.5f, MesaH1, 84f) }, 6f, zd, g, 0.04f, (x, z) => z < 52f ? 0f : S1(z));
            Models.RoadRibbon(new List<Vector3> { new Vector3(-54.5f, MesaH1, 84f), new Vector3(-54.5f, MesaH2, 54f) }, 6.5f, zd, g, 0.04f, (x, z) => S2(z));
            Models.RoadRibbon(new List<Vector3> { new Vector3(-63.5f, MesaH2, 54f), new Vector3(-63.5f, MesaTop, 84f) }, 6.5f, zd, g, 0.04f, (x, z) => S3(z));

            // ---- summit dressing: a lookout post with a flag, a tarp, stones
            var deco = new MeshBuilder();
            var post = new Vector3(-90f, MesaTop, 90f);
            deco.Cylinder(post, 0.12f, 5.2f, 6, H("#5A3D2B"));
            deco.Box(post + new Vector3(0.75f, 4.7f, 0f), new Vector3(1.4f, 0.8f, 0.04f), H("#C9412E"));
            deco.Box(post + new Vector3(0f, 2.6f, 0f), new Vector3(1.6f, 0.12f, 1.6f), H("#A8703F"));
            deco.Box(new Vector3(-80f, MesaTop + 0.9f, 90.5f), new Vector3(3.2f, 0.08f, 2.4f), Quaternion.Euler(-12f, 0f, 0f), H("#7E8C55"));
            foreach (var c in new[] { new Vector3(-82f, MesaTop + 0.45f, 90.8f), new Vector3(-78f, MesaTop + 0.45f, 90.8f) })
                deco.Cylinder(c - Vector3.up * 0.45f, 0.08f, 1.1f, 6, H("#5A3D2B"));
            Emit("MesaSummit", deco, g);
        }

        /// <summary>
        /// Vertical rock face from a to c (world xz) up to top(t) (t = 0..1 along), facing to the right of a->c. Layered
        /// colours with a pale crown, gently jittered so it reads as rock; the top edge meets the deck above exactly.
        /// </summary>
        static readonly List<Vector3> bandV = new List<Vector3>();
        static readonly List<Color> bandC = new List<Color>();
        static readonly List<int> bandT = new List<int>();
        static Material shadeMat;

        static void Face(MeshBuilder b, Vector3 a, Vector3 c, System.Func<float, float> top, ZoneDef zd, int seed, bool lowHidden = false, System.Func<float, float> low = null)
        {
            var d = c - a; d.y = 0f;
            float len = d.magnitude;
            var dir = d / len;
            var outward = new Vector3(dir.z, 0f, -dir.x);
            int nx = Mathf.Max(2, Mathf.CeilToInt(len / 1.6f));
            float maxTop = 0f;
            for (int i = 0; i <= nx; i++) maxTop = Mathf.Max(maxTop, top(i / (float)nx));
            int ny = Mathf.Max(2, Mathf.CeilToInt((maxTop + 0.1f) / 1.3f));
            var light = zd.cliff; var dark = zd.cliffDark;
            var crown = Color.Lerp(zd.cliff, Color.white, 0.2f);
            Vector3 P(int i, int j)
            {
                float t = i / (float)nx;
                float ht = top(t);
                float y = Mathf.Lerp(-0.1f, ht - 0.02f, j / (float)ny);
                var p = a + dir * (t * len);
                // jitter in and out of the face (not at the top row or the ends, so edges stay clean)
                float jit = (j == ny || i == 0 || i == nx) ? 0f : (MeshBuilder.Noise3(new Vector3(p.x * 0.6f, y * 0.7f, p.z * 0.6f), seed) - 0.5f) * 0.3f;
                return new Vector3(p.x, y, p.z) + outward * jit;
            }
            for (int i = 0; i < nx; i++)
                for (int j = 0; j < ny; j++)
                {
                    var p00 = P(i, j); var p10 = P(i + 1, j); var p11 = P(i + 1, j + 1); var p01 = P(i, j + 1);
                    float midY = (p00.y + p11.y) * 0.5f;
                    float n = MeshBuilder.Noise3(new Vector3(p00.x * 0.3f, midY * 0.5f, p00.z * 0.3f), seed + 3);
                    // horizontal strata: alternating bands, softened by noise
                    int band = Mathf.FloorToInt((midY + n * 0.6f) / 1.1f);
                    var col = Color.Lerp(light, dark, (band % 2 == 0 ? 0.25f : 0.65f) + (n - 0.5f) * 0.3f);
                    if (j == ny - 1) col = Color.Lerp(col, crown, 0.55f);
                    if (lowHidden && j < ny / 3) col = dark;
                    var inside = (p00 + p11) * 0.5f - outward;
                    b.PolyOut(col, inside, p00, p10, p11, p01);
                }
            if (low == null) return;
            // shadow band on the surface at the face's foot: dark at the face, fading out 1.6 m away
            var foot = new Color(0.16f, 0.08f, 0.05f, 0.4f);
            if (QualitySettings.activeColorSpace == ColorSpace.Linear) { var l = foot.linear; foot = new Color(l.r, l.g, l.b, foot.a); }
            var clear = new Color(foot.r, foot.g, foot.b, 0f);
            for (int i = 0; i <= nx; i++)
            {
                float t = i / (float)nx;
                var p = a + dir * (t * len);
                float y = low(t) + 0.07f;
                bandV.Add(new Vector3(p.x, y, p.z) + outward * 0.03f);
                bandV.Add(new Vector3(p.x, y, p.z) + outward * 1.6f);
                bandC.Add(foot); bandC.Add(clear);
                if (i > 0)
                {
                    int k = bandV.Count - 4;
                    bandT.Add(k); bandT.Add(k + 1); bandT.Add(k + 2);
                    bandT.Add(k + 1); bandT.Add(k + 3); bandT.Add(k + 2);
                }
            }
        }

        /// <summary>Deck of a mesa floor in ground colours (with a pale rim along its edges), following its height.</summary>
        static void Deck(MeshBuilder b, FloorPiece p, ZoneDef zd, float darken, float stones, float pale = 0f)
        {
            var r = p.rect;
            int nz = Mathf.Max(1, Mathf.CeilToInt(r.half.y * 2f / 2f)), nx = Mathf.Max(1, Mathf.CeilToInt(r.half.x * 2f / 2f));
            var gravel = Color.Lerp(zd.groundAlt, zd.cliffDark, darken);
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < nx; i++)
                {
                    float lx0 = -r.half.x + i * (r.half.x * 2f / nx), lx1 = lx0 + r.half.x * 2f / nx;
                    float lz0 = -r.half.y + j * (r.half.y * 2f / nz), lz1 = lz0 + r.half.y * 2f / nz;
                    var a = r.World(lx0, lz0, p.Height(new Vector2(lx0, lz0)) + 0.01f);
                    var c = r.World(lx1, lz0, p.Height(new Vector2(lx1, lz0)) + 0.01f);
                    var d = r.World(lx1, lz1, p.Height(new Vector2(lx1, lz1)) + 0.01f);
                    var e = r.World(lx0, lz1, p.Height(new Vector2(lx0, lz1)) + 0.01f);
                    var mid = (a + d) * 0.5f;
                    var col = Color.Lerp(Models.GroundColorAt(mid.x, mid.z), gravel, darken);
                    if (pale > 0f) col = Color.Lerp(col, Color.Lerp(zd.cliff, Color.white, 0.45f), pale);
                    bool rim = i == 0 || j == 0 || i == nx - 1 || j == nz - 1;
                    if (rim) col = Color.Lerp(col, Color.Lerp(zd.cliff, Color.white, 0.25f), 0.25f);
                    b.PolyOut(col, mid - Vector3.up, a, e, d, c);
                }
            if (stones <= 0f) return;
            var rnd = new System.Random(p.name.GetHashCode());
            int count = Mathf.RoundToInt(r.half.x * r.half.y * 0.02f * stones);
            var stone = Color.Lerp(zd.cliff, zd.ground, 0.35f);
            for (int k = 0; k < count; k++)
            {
                float lx = ((float)rnd.NextDouble() * 2f - 1f) * (r.half.x - 2f), lz = ((float)rnd.NextDouble() * 2f - 1f) * (r.half.y - 2f);
                float s = 0.25f + (float)rnd.NextDouble() * 0.3f;
                b.Rock(r.World(lx, lz, p.Height(new Vector2(lx, lz))), new Vector3(s * 1.2f, s * 0.55f, s), stone, rnd.Next(), Color.Lerp(stone, Color.white, 0.18f), 0.16f, 1);
            }
        }
    }
}
