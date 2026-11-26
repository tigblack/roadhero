using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Hand-placed level structures on top of the procedural zones: the intro canyon with the first jump, the
    /// underground "Mammoth Works" (entrance ramp, tunnel, boss hangar, loading ramp out), jump ramps, a stash plateau,
    /// a drive-through garage, a rock tunnel, a pipeline underpass, a canopy and a pipe tunnel.
    /// Each structure registers its floors (Ground), holes in the surface, blocking colliders (sight / shots / car),
    /// see-through occluders (roofs, lids, walls in the way), minimap marks and keep-out areas for spawns and decor.
    /// Geometry is axis-aligned where it is cut into the ground, so ground chunks can leave exact 5 m holes for it.
    /// </summary>
    public static class Structures
    {
        // ------------------------------------------------------------------ public layout
        public const float WorksFloor = -4.5f;          // Mammoth Works floor level
        public const float LidBottom = -0.4f;           // underside of the ground lid over tunnels
        public const float HangarTop = 3.0f;            // hangar walls rise this much above the ground
        public const float UnderpassFloor = -3.4f;

        // intro canyon: a wide straight (rock walls at +-20 m, a 16 m road), the scouts ahead, a clear run-up, the ramp
        public static readonly Vector3 IntroStart = new Vector3(0f, 0f, -238f);
        public static readonly Vector3 IntroScoutA = new Vector3(-6f, 0f, -196f);
        public static readonly Vector3 IntroScoutB = new Vector3(7f, 0f, -184f);
        public static readonly Vector3 IntroRampStart = new Vector3(0f, 0f, -119f);
        public static readonly Vector3 IntroRampLip = new Vector3(0f, 2.2f, -109f);
        public const float IntroRampHeight = 2.2f;
        public const float IntroRampHalfWidth = 7f;
        public const float IntroWallX = 20f;             // canyon walls (rock line); their faces are at about +-14 m
        public const float IntroRoadWidth = 16f;
        public const float IntroSouthZ = -254f;          // the canyon's south end wall
        /// <summary>The scouts never drive past this line: the run-up to the ramp (and their wrecks) stay clear.</summary>
        public const float IntroScoutLimitZ = -152f;
        public const float IntroZoneZ = -100.5f;         // past this line the car is in the playable zone

        public static readonly ORect WorksHangar = ORect.FromMinMax(28f, 54f, 76f, 88f);
        public static readonly ORect WorksArena = ORect.FromMinMax(37.5f, 55f, 75f, 87f);   // floor the boss may use
        public static readonly Vector3 WorksBossHome = new Vector3(56.5f, WorksFloor, 71f);
        public static readonly Vector3 WorksEntrance = new Vector3(21f, 0f, 42f);
        public static readonly Vector3 WorksExitDoor = new Vector3(26f, 0f, 84f);
        /// <summary>Waypoints from the main road down into the hangar (autopilot / tests).</summary>
        public static readonly Vector3[] WorksRoute =
        {
            new Vector3(16f, 0f, 42f), new Vector3(24f, 0f, 42f), new Vector3(36f, -3.3f, 42f), new Vector3(47f, WorksFloor, 42f),
            new Vector3(55f, WorksFloor, 44f), new Vector3(55f, WorksFloor, 52f), new Vector3(55f, WorksFloor, 60f)
        };

        public struct MapMark { public ORect r; public Color c; public bool underground; }

        public static readonly List<ORect> Exclusions = new List<ORect>();
        public static readonly List<Vector4> Cutouts = new List<Vector4>();   // xMin, zMin, xMax, zMax (5 m aligned)
        public static readonly List<MapMark> Marks = new List<MapMark>();
        public static readonly List<FloorPiece> JumpRamps = new List<FloorPiece>();
        /// <summary>Where road ribbons are not drawn (the road dips into an underpass there and gets its own deck).</summary>
        public static readonly List<Rect> RoadGaps = new List<Rect>();

        public static GameObject IntroGuide;            // floating arrow + painted chevrons (shown during the intro)
        public static Vector3 PlateauChest0, PlateauChest2;

        static Transform root;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            Exclusions.Clear(); Cutouts.Clear(); Marks.Clear(); JumpRamps.Clear();
            IntroGuide = null; root = null; lampMat = null; guideArrowMesh = null;
            obstacleJumps.Clear(); RoadGaps.Clear();
        }

        public static bool Excluded(Vector3 p, float radius)
        {
            for (int i = 0; i < Exclusions.Count; i++)
                if (Exclusions[i].Distance(p.x, p.z) < radius) return true;
            return false;
        }

        public static bool CellCut(float x0, float z0, float x1, float z1)
        {
            for (int i = 0; i < Cutouts.Count; i++)
            {
                var c = Cutouts[i];
                if (x1 > c.x + 0.01f && x0 < c.z - 0.01f && z1 > c.y + 0.01f && z0 < c.w - 0.01f) return true;
            }
            return false;
        }

        // ------------------------------------------------------------------ palette
        static Color H(string h) => Models.Hex(h);
        static Color Gl(string h, float a = 0.3f) { var c = H(h); c.a = a; return c; }
        static Color Sh(Color c, float k) => new Color(c.r * k, c.g * k, c.b * k, c.a);
        static readonly Color Concrete = H("#A39B90"), ConcreteTop = H("#B9B1A5"), ConcreteDark = H("#857D74");
        static readonly Color FloorC = H("#938B81"), FloorDark = H("#7C756C"), Paint = H("#E7BE4C"), PaintWhite = H("#ECE5D8");
        static readonly Color Hazard = H("#E9B23B"), HazardDark = H("#2F2C2B"), Steel = H("#8C949C"), SteelDark = H("#5C636B");
        static readonly Color RustC = H("#A9552C"), RustD = H("#7E3E20"), Tin = H("#9A958C"), TinDark = H("#7D786F");
        static readonly Color WoodC = H("#A8703F"), Tire = H("#2E2A2A"), Bone = H("#EFE6D1"), SignRed = H("#C9412E");
        static readonly Color Lamp = Gl("#FFE3A6", 0.25f);

        // ------------------------------------------------------------------ planning (data only, before the zones)
        /// <summary>Registers every floor, hole, cut-out and keep-out area. Called before the zones generate.</summary>
        public static void Plan()
        {
            ResetStatics();
            PlanIntro();
            PlanWorks();
            PlanPlateau(0, new Vector3(81f, 0f, -33f), 90f, new Vector3(64f, 0f, -33f));
            PlanObstacleJump("BusJump", new Vector3(43.6f, 0f, 19.5f), 117.8f, 2.2f, 0);
            PlanGarage(new Vector3(-47.5f, 0f, -38.9f), 78.7f);
            PlanRockTunnel(new Vector3(-14.8f, 0f, 186f));
            PlanUnderpass();
            PlanPipelineJump();
            PlanCanopy(new Vector3(3f, 0f, 376f));
            PlanPlateau(2, new Vector3(84f, 0f, 377f), 90f, new Vector3(67f, 0f, 377f));
            PlanPipeTunnel(new Vector3(-22f, 0f, 622.8f));
            PlanObstacleJump("DrumJump", new Vector3(2.6f, 0f, 606f), -17f, 2.0f, 3);
            foreach (var p in Ground.Pieces) if (p.underground) Ground.ShaderRegions.Add(p);
            Ground.ShaderRegions.Upload();
        }

        static FloorPiece Floor(string name, ORect r, float h0, float h1, SurfaceKind s, bool underground, float easeIn = 0.25f, float easeOut = 0.25f)
            => Ground.Add(new FloorPiece { name = name, rect = r, h0 = h0, h1 = h1, surface = s, underground = underground, easeIn = easeIn, easeOut = easeOut });

        internal static FloorPiece Ramp(string name, ORect r, float height, float boost)
        {
            var p = Ground.Add(new FloorPiece { name = name, rect = r, h0 = 0f, h1 = height, surface = SurfaceKind.Metal, easeIn = 0.3f, easeOut = 0f, launch = true, boost = boost, enemyWalkable = false });
            JumpRamps.Add(p);
            return p;
        }

        static void Mark(ORect r, Color c, bool underground = false) => Marks.Add(new MapMark { r = r, c = c, underground = underground });

        // ---- intro canyon (south of the map, outside the zone): straight road, two scouts, a launch ramp over the barricade
        static void PlanIntro()
        {
            // the launch ramp: 10 m long, 14 m wide, 2.2 m lip, always a clean straight jump (minimum take-off speed, no roll)
            var ramp = Ramp("IntroRamp", new ORect(new Vector3(0f, 0f, -114f), 0f, IntroRampHalfWidth, 5f), IntroRampHeight, 13f);
            ramp.steady = true;
            Exclusions.Add(ORect.FromMinMax(-16f, -101f, 16f, -80f));                  // landing area inside the zone
            Mark(ORect.FromMinMax(-IntroRampHalfWidth, -119f, IntroRampHalfWidth, -109f), new Color(0.95f, 0.75f, 0.25f));
        }

        // ---- Mammoth Works: entrance ramp (east) -> covered tunnel -> turn north -> hangar; loading ramp + west door out
        static void PlanWorks()
        {
            Cutouts.Add(new Vector4(20f, 35f, 80f, 90f));
            Exclusions.Add(ORect.FromMinMax(14f, 32f, 84f, 93f));
            const float F = WorksFloor;
            // entrance ramp: 20 m east, 0 -> -4.5 m (open cut for its first 13 m, then under the lid)
            Floor("WorksRamp", new ORect(new Vector3(32f, 0f, 42f), 90f, 5f, 10f), 0f, F, SurfaceKind.Concrete, true);
            Floor("WorksTunnel", ORect.FromMinMax(41.5f, 37f, 60.6f, 47f), F, F, SurfaceKind.Concrete, true);
            Floor("WorksLink", ORect.FromMinMax(49.4f, 46.5f, 60.6f, 54.5f), F, F, SurfaceKind.Concrete, true);
            Floor("WorksHangar", WorksHangar, F, F, SurfaceKind.Concrete, true);
            // loading ramp inside the hangar along its west wall (solid block), up to the west door at ground level
            Floor("WorksLoadRamp", ORect.FromMinMax(28f, 60f, 36f, 80f), F, 0f, SurfaceKind.Concrete, true);
            Floor("WorksPlatform", ORect.FromMinMax(28f, 80f, 36f, 88f), 0f, 0f, SurfaceKind.Concrete, false);
            Floor("WorksDoorSill", ORect.FromMinMax(26.6f, 80f, 28.2f, 88f), 0f, 0f, SurfaceKind.Concrete, false);
            // the surface is open over the cut and missing where the hangar stands
            Ground.AddHole(ORect.FromMinMax(22f, 37f, 35f, 47f));
            Ground.AddHole(ORect.FromMinMax(27f, 53f, 77f, 89f));
            Mark(ORect.FromMinMax(22f, 37f, 60.6f, 47f), new Color(0.42f, 0.38f, 0.36f), true);
            Mark(ORect.FromMinMax(49.4f, 47f, 60.6f, 54f), new Color(0.42f, 0.38f, 0.36f), true);
            Mark(ORect.FromMinMax(27f, 53f, 77f, 89f), new Color(0.36f, 0.3f, 0.3f));
        }

        /// <summary>A rock plateau with a stash on top, reached by a jump ramp; a gap in its rim lets the car drop back down.</summary>
        static void PlanPlateau(int zone, Vector3 center, float rampYaw, Vector3 rampCenter)
        {
            const float top = 2.0f, half = 7f;
            var r = new ORect(center, 0f, half, half);
            Floor("Plateau" + zone, r, top, top, SurfaceKind.Sand, false);
            Ramp("PlateauRamp" + zone, new ORect(rampCenter, rampYaw, 4f, 5f), 2.5f, 12.5f);
            Exclusions.Add(new ORect(center, 0f, half + 4f, half + 4f));
            Exclusions.Add(new ORect(rampCenter, rampYaw, 6f, 9f));
            Mark(r, new Color(0.62f, 0.45f, 0.35f));
            if (zone == 0) PlateauChest0 = new Vector3(center.x + 3f, top, center.z + 3f);
            else PlateauChest2 = new Vector3(center.x + 3f, top, center.z + 3f);
        }

        static readonly List<(string name, Vector3 lip, float yaw, float height, int zone)> obstacleJumps = new List<(string, Vector3, float, float, int)>();

        /// <summary>Jump ramp on a side road with a wreck across the road behind it (the sand around is the slow way).</summary>
        static void PlanObstacleJump(string name, Vector3 lip, float yaw, float height, int zone)
        {
            var fwd = new Vector3(Mathf.Sin(yaw * Mathf.Deg2Rad), 0f, Mathf.Cos(yaw * Mathf.Deg2Rad));
            Ramp(name, new ORect(lip - fwd * 4f, yaw, 4f, 4f), height, 12.5f);
            Exclusions.Add(new ORect(lip + fwd * 3f, yaw, 7f, 13f));
            Mark(new ORect(lip - fwd * 4f, yaw, 4f, 4f), new Color(0.95f, 0.75f, 0.25f));
            if (obstacleJumps.Count == 0 || obstacleJumps.FindIndex(o => o.name == name) < 0) obstacleJumps.Add((name, lip, yaw, height, zone));
        }

        static Vector3 garagePos; static float garageYaw;
        static void PlanGarage(Vector3 c, float yaw)
        {
            garagePos = c; garageYaw = yaw;
            Exclusions.Add(new ORect(c, yaw, 7.5f, 9f));
            Mark(new ORect(c, yaw, 5.2f, 6.5f), new Color(0.45f, 0.38f, 0.34f));
        }

        static Vector3 rockTunnel;
        static void PlanRockTunnel(Vector3 c)
        {
            rockTunnel = c;
            Exclusions.Add(ORect.FromMinMax(c.x - 19f, c.z - 12f, c.x + 19f, c.z + 12f));
            Mark(ORect.FromMinMax(c.x - 17f, c.z - 9f, c.x - 5.5f, c.z + 9f), new Color(0.5f, 0.3f, 0.25f));
            Mark(ORect.FromMinMax(c.x + 5.5f, c.z - 9f, c.x + 17f, c.z + 9f), new Color(0.5f, 0.3f, 0.25f));
        }

        // zone 1: the east camp road dips under a pipeline (open ramp, covered middle, open ramp)
        const float UpX0 = 4f, UpX1 = 15f, UpX2 = 25f, UpX3 = 36f, UpZ0 = 203.5f, UpZ1 = 213.5f, UpLid0 = 12.7f, UpLid1 = 27.3f;
        static void PlanUnderpass()
        {
            Cutouts.Add(new Vector4(0f, 200f, 40f, 215f));
            RoadGaps.Add(Rect.MinMaxRect(0f, 200f, 40f, 215f));
            const float F = UnderpassFloor;
            float zc = (UpZ0 + UpZ1) * 0.5f, hz = (UpZ1 - UpZ0) * 0.5f;
            Floor("UnderpassDown", new ORect(new Vector3((UpX0 + UpX1) * 0.5f, 0f, zc), 90f, hz, (UpX1 - UpX0) * 0.5f), 0f, F, SurfaceKind.Asphalt, true);
            Floor("UnderpassMid", ORect.FromMinMax(UpX1 - 0.3f, UpZ0, UpX2 + 0.3f, UpZ1), F, F, SurfaceKind.Asphalt, true);
            Floor("UnderpassUp", new ORect(new Vector3((UpX2 + UpX3) * 0.5f, 0f, zc), 90f, hz, (UpX3 - UpX2) * 0.5f), F, 0f, SurfaceKind.Asphalt, true);
            Ground.AddHole(ORect.FromMinMax(UpX0, UpZ0, UpLid0, UpZ1));
            Ground.AddHole(ORect.FromMinMax(UpLid1, UpZ0, UpX3, UpZ1));
            Exclusions.Add(ORect.FromMinMax(-1f, 199f, 41f, 217f));
            Exclusions.Add(ORect.FromMinMax(17.5f, 184f, 22.5f, 234f));                  // the pipeline itself
            Mark(ORect.FromMinMax(UpX0, UpZ0, UpX3, UpZ1), new Color(0.42f, 0.38f, 0.36f), true);
            Mark(ORect.FromMinMax(19f, 186f, 21f, 232f), new Color(0.55f, 0.55f, 0.58f));
        }

        static void PlanPipelineJump()
        {
            // a ramp over the pipeline next to the underpass: over or under, both get across
            // approached across the sand from the main road, north of the rock tunnel
            Ramp("PipeJump", new ORect(new Vector3(11f, 0f, 198.6f), 90f, 4f, 4f), 2.6f, 12.5f);
            Exclusions.Add(ORect.FromMinMax(4f, 193f, 31f, 203f));
            Mark(new ORect(new Vector3(11f, 0f, 198.6f), 90f, 4f, 4f), new Color(0.95f, 0.75f, 0.25f));
        }

        static Vector3 canopy;
        static void PlanCanopy(Vector3 c)
        {
            canopy = c;
            Exclusions.Add(ORect.FromMinMax(c.x - 11f, c.z - 13f, c.x + 11f, c.z + 13f));
            Mark(ORect.FromMinMax(c.x - 7f, c.z - 10f, c.x + 7f, c.z + 10f), new Color(0.75f, 0.74f, 0.7f));
        }

        static Vector3 pipeTunnel;
        static void PlanPipeTunnel(Vector3 c)
        {
            pipeTunnel = c;
            Exclusions.Add(ORect.FromMinMax(c.x - 11f, c.z - 9f, c.x + 11f, c.z + 9f));
            Mark(ORect.FromMinMax(c.x - 8f, c.z - 6f, c.x + 8f, c.z + 6f), new Color(0.48f, 0.36f, 0.28f));
        }

        // ------------------------------------------------------------------ building (geometry, colliders, occluders)
        public static void Build(Transform parent)
        {
            var it = BuildRoutine(parent);
            while (it.MoveNext()) { }
        }

        /// <summary>The structures, a few per frame (the web player only collects mesh-building scratch data between
        /// frames: all of them in one frame grew its managed heap by ~43 MiB for good). Same order as before.</summary>
        public static System.Collections.IEnumerator BuildRoutine(Transform parent)
        {
            root = new GameObject("Structures").transform;
            root.SetParent(parent, false);
            var steps = new System.Collections.Generic.List<System.Action>
            {
                BuildIntro,
                BuildWorks,
                () => { BuildPlateau(0, new Vector3(81f, 0f, -33f)); BuildPlateau(2, new Vector3(84f, 0f, 377f)); },
                () => { foreach (var j in obstacleJumps) BuildObstacleJump(j.name, j.lip, j.yaw, j.height, j.zone); },
                () => { BuildGarage(); BuildRockTunnel(); },
                () => { BuildUnderpass(); BuildCanopy(); BuildPipeTunnel(); },
                () => { foreach (var p in JumpRamps) BuildJumpRamp(p); },
            };
            foreach (var step in steps)
            {
                float q = MeshBuilder.Quality;
                MeshBuilder.Quality = 1f;     // big simple shapes: no extra subdivision
                try { step(); }
                finally { MeshBuilder.Quality = q; }
                yield return null;
            }
        }

        static Transform Group(string name)
        {
            var t = new GameObject(name).transform;
            t.SetParent(root, false);
            return t;
        }

        static GameObject Emit(string name, MeshBuilder b, Transform parent, bool shadows = true, Material mat = null)
        {
            var go = Models.MeshGO(name, b.Build(name), mat ?? Mats.Toon, parent, shadows);
            return go;
        }

        /// <summary>World-space axis-aligned blocker (walls, rims, lids): stops the car, sight lines and shots.</summary>
        static void Block(Transform parent, string name, Vector3 min, Vector3 max)
        {
            var go = new GameObject(name);
            go.layer = Ground.BlockerLayer;
            go.transform.SetParent(parent, false);
            var c = go.AddComponent<BoxCollider>();
            c.center = (min + max) * 0.5f;
            c.size = max - min;
        }

        static void BlockO(Transform parent, string name, Vector3 center, Vector3 size, float yaw)
        {
            var go = new GameObject(name);
            go.layer = Ground.BlockerLayer;
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(center, Quaternion.Euler(0f, yaw, 0f));
            go.AddComponent<BoxCollider>().size = size;
        }

        static void WallBox(MeshBuilder b, Vector3 min, Vector3 max, Color side, Color? top = null)
            => b.Box((min + max) * 0.5f, max - min, side, top ?? side);

        static Material lampMat;
        static Material LampPoolMat()
        {
            if (lampMat != null) return lampMat;
            lampMat = Mats.NewUnlit("LampPool", Tex.SoftCircle(), true);
            lampMat.SetColor("_BaseColor", new Color(1f, 0.82f, 0.5f, 0.2f));
            lampMat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent - 40;
            return lampMat;
        }

        static void LampPool(Transform parent, Vector3 p, float radius)
        {
            var g = Models.MeshGO("LampPool", Models.FlatQuad(), LampPoolMat(), parent, false);
            g.transform.position = p + Vector3.up * 0.03f;
            g.transform.localScale = new Vector3(radius, 1f, radius);
            g.GetComponent<MeshRenderer>().receiveShadows = false;
        }

        /// <summary>Flat ground patch (same colors and texture as the ground chunks): fills and see-through lids.</summary>
        static GameObject GroundPatch(string name, Transform parent, float x0, float z0, float x1, float z1, bool shadows)
        {
            const float cell = 2.5f;
            int nx = Mathf.Max(1, Mathf.CeilToInt((x1 - x0) / cell)), nz = Mathf.Max(1, Mathf.CeilToInt((z1 - z0) / cell));
            var verts = new List<Vector3>(); var cols = new List<Color>(); var norms = new List<Vector3>(); var tris = new List<int>();
            bool lin = QualitySettings.activeColorSpace == ColorSpace.Linear;
            for (int j = 0; j <= nz; j++)
                for (int i = 0; i <= nx; i++)
                {
                    float x = Mathf.Lerp(x0, x1, i / (float)nx), z = Mathf.Lerp(z0, z1, j / (float)nz);
                    verts.Add(new Vector3(x, 0f, z));
                    norms.Add(Vector3.up);
                    var c = Models.GroundColorAt(x, z);
                    cols.Add(lin ? c.linear : c);
                }
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < nx; i++)
                {
                    int a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
                    tris.Add(a); tris.Add(c); tris.Add(b);
                    tris.Add(b); tris.Add(c); tris.Add(d);
                }
            var mesh = new Mesh { name = name };
            mesh.SetVertices(verts); mesh.SetNormals(norms); mesh.SetColors(cols); mesh.SetTriangles(tris, 0);
            mesh.SetUVs(1, new Vector2[verts.Count]);
            mesh.RecalculateBounds();
            return Models.MeshGO(name, mesh, Mats.Ground, parent, shadows);
        }

        /// <summary>Fills a 5 m cut-out with ground patches except the given rectangles (lids / openings / buildings).</summary>
        static void FillCutout(Transform parent, Vector4 cut, List<Rect> skip)
        {
            var xs = new List<float> { cut.x, cut.z }; var zs = new List<float> { cut.y, cut.w };
            foreach (var r in skip) { xs.Add(r.xMin); xs.Add(r.xMax); zs.Add(r.yMin); zs.Add(r.yMax); }
            xs.Sort(); zs.Sort();
            for (int i = 0; i < xs.Count - 1; i++)
                for (int j = 0; j < zs.Count - 1; j++)
                {
                    float x0 = xs[i], x1 = xs[i + 1], z0 = zs[j], z1 = zs[j + 1];
                    if (x1 - x0 < 0.01f || z1 - z0 < 0.01f || x0 < cut.x - 0.01f || x1 > cut.z + 0.01f || z0 < cut.y - 0.01f || z1 > cut.w + 0.01f) continue;
                    var c = new Vector2((x0 + x1) * 0.5f, (z0 + z1) * 0.5f);
                    bool covered = false;
                    foreach (var r in skip) if (r.Contains(c)) { covered = true; break; }
                    if (!covered) GroundPatch("GroundFill", parent, x0, z0, x1, z1, false);
                }
        }

        internal static void HazardStripe(MeshBuilder b, Vector3 a, Vector3 c, float width, float height, float y, int count)
        {
            // alternating yellow / dark blocks along a line (edges of ramps, portals)
            var d = c - a; float len = d.magnitude; d /= len;
            float seg = len / count;
            var rot = Quaternion.LookRotation(d, Vector3.up);
            for (int i = 0; i < count; i++)
            {
                var p = a + d * (seg * (i + 0.5f));
                b.Push(new Vector3(p.x, y, p.z), rot);
                b.Box(Vector3.zero, new Vector3(width, height, seg * 0.98f), i % 2 == 0 ? Hazard : HazardDark);
                b.Pop();
            }
        }

        internal static void Chevron(MeshBuilder b, Vector3 p, float yaw, float size, Color c, float tilt = 0f)
        {
            b.Push(p, Quaternion.Euler(tilt, yaw, 0f));
            for (int s = -1; s <= 1; s += 2)
                b.Box(new Vector3(s * size * 0.3f, 0f, 0f), new Vector3(size * 0.22f, 0.03f, size * 0.75f), Quaternion.Euler(0f, -s * 45f, 0f), c);
            b.Pop();
        }

        // ------------------------------------------------------------------ intro canyon
        static void BuildIntro()
        {
            var g = Group("IntroCanyon");
            var z0 = Content.Zones[0];
            Models.RoadRibbon(new List<Vector3> { new Vector3(0, 0, IntroSouthZ + 4f), new Vector3(0, 0, -120f), new Vector3(0, 0, -100.5f) }, IntroRoadWidth, z0, g, 0.035f);
            Models.CliffWall(new Vector3(-IntroWallX, 0, IntroSouthZ + 1f), new Vector3(-IntroWallX, 0, -104f), z0, 611, g, 7f, 5.5f, 3.2f);
            Models.CliffWall(new Vector3(IntroWallX, 0, IntroSouthZ + 1f), new Vector3(IntroWallX, 0, -104f), z0, 612, g, 7f, 5.5f, 3.2f);
            Models.CliffWall(new Vector3(-IntroWallX - 4f, 0, IntroSouthZ), new Vector3(IntroWallX + 4f, 0, IntroSouthZ), z0, 613, g, 6f, 5f, 3f);

            // the barricade the first jump clears, across the whole canyon (it also keeps the canyon one-way)
            var b = new MeshBuilder();
            var rnd = new System.Random(77);
            float R() => (float)rnd.NextDouble();
            for (int i = 0; i < 13; i++)
            {
                float x = -16.8f + i * 2.8f;
                var c = i % 3 == 0 ? RustC : i % 3 == 1 ? Tin : RustD;
                b.Material(0.3f, 0.3f);
                b.BevelBox(new Vector3(x, 0.62f, -104.8f), new Vector3(2.5f, 1.24f, 1.8f), Quaternion.Euler(R() * 6f - 3f, R() * 16f - 8f, R() * 6f - 3f), 0.08f, c, Sh(c, 1.12f));
                b.Matte();
                if (i % 2 == 0) for (int k = 0; k < 2; k++) b.Cylinder(new Vector3(x + 0.6f, 1.24f + k * 0.26f, -104.4f), 0.42f, 0.25f, 10, Tire, -1, H("#1A1818"));
                b.Material(0.85f, 1f);
                b.Cone(new Vector3(x - 0.6f, 1.2f, -105.2f), 0.09f, 0.55f, 6, H("#D5DAE0"));
                b.Matte();
            }
            HazardStripe(b, new Vector3(-18f, 0, -105.85f), new Vector3(18f, 0, -105.85f), 0.1f, 0.3f, 1.05f, 18);
            Emit("Barricade", b, g);
            Block(g, "BarricadeCol", new Vector3(-19f, -0.5f, -106f), new Vector3(19f, 1.45f, -103.5f));

            // funnel barriers from the canyon walls onto the ramp: past the fight the canyon narrows to the ramp's width
            b = new MeshBuilder();
            foreach (int s in new[] { -1, 1 })
            {
                var a0 = new Vector3(s * 17f, 0, -150f); var a1 = new Vector3(s * (IntroRampHalfWidth + 0.6f), 0, -134f); var a2 = new Vector3(s * (IntroRampHalfWidth + 0.6f), 0, -119.4f);
                foreach (var (p0, p1) in new[] { (a0, a1), (a1, a2) })
                {
                    var d = p1 - p0; float len = d.magnitude; var dir = d / len;
                    float yaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                    int n = Mathf.Max(1, Mathf.RoundToInt(len / 2f));
                    for (int k = 0; k < n; k++)
                    {
                        var p = Vector3.Lerp(p0, p1, (k + 0.5f) / n);
                        b.Push(p, Quaternion.Euler(0, yaw, 0));
                        b.Tapered(Vector3.zero, new Vector2(0.62f, len / n - 0.08f), new Vector2(0.3f, len / n - 0.08f), 0.85f, k % 2 == 0 ? H("#D8D2C6") : SignRed, H("#E9E4DA"));
                        b.Pop();
                    }
                    BlockO(g, "FunnelCol", (p0 + p1) * 0.5f + Vector3.up * 0.5f, new Vector3(0.6f, 1.6f, len), yaw);
                }
            }
            Emit("Funnel", b, g);

            // guide (shown by the intro): painted chevrons up the middle of the road, and three floating arrows on the
            // centre line - at the funnel, at the foot of the ramp and over its lip - that lead straight over the jump
            IntroGuide = new GameObject("IntroGuide");
            IntroGuide.transform.SetParent(g, false);
            b = new MeshBuilder();
            for (float z = -172f; z <= -124f; z += 6f) Chevron(b, new Vector3(0, 0.05f, z), 0f, 4.2f, Gl("#FFD24A", 0.55f));
            // and the landing past the barricade (a 13 m/s take-off lands at about z -98): two bigger chevrons on the road
            // there, so the run-up already shows where the car comes down and that the way goes on straight
            foreach (float z in new[] { -97f, -90.5f }) Chevron(b, new Vector3(0, 0.05f, z), 0f, 5.4f, Gl("#FFD24A", 0.62f));
            Emit("GuideChevrons", b, IntroGuide.transform, false);
            var arrowMesh = GuideArrowMesh();
            int idx = 0;
            foreach (var (pos, scale) in new[] { (new Vector3(0f, 3.6f, -147f), 1f), (new Vector3(0f, 4.4f, -126f), 1.1f), (new Vector3(0f, 5.4f, -110.5f), 1.25f) })
            {
                var arrow = new GameObject("GuideArrow" + idx);
                arrow.transform.SetParent(IntroGuide.transform, false);
                arrow.transform.position = pos;
                arrow.transform.localScale = Vector3.one * scale;
                Models.MeshGO("Arrow", arrowMesh, Mats.Toon, arrow.transform, false);
                arrow.AddComponent<GuideArrowBob>().phase = idx * 0.9f;
                idx++;
            }
            IntroGuide.SetActive(false);
        }

        static Mesh guideArrowMesh;
        internal static Mesh GuideArrowMesh()
        {
            if (guideArrowMesh != null) return guideArrowMesh;
            var b = new MeshBuilder();
            b.Material(0.6f, 0f);
            var ac = Gl("#FFC93A", 0.55f);
            b.Box(new Vector3(0, 0, -0.9f), new Vector3(1.0f, 0.45f, 2.2f), ac);
            b.Push(new Vector3(0, 0, 0.2f));
            b.Poly(ac, new Vector3(-1.4f, 0.22f, 0), new Vector3(0, 0.22f, 1.9f), new Vector3(1.4f, 0.22f, 0));
            b.Poly(ac, new Vector3(1.4f, -0.22f, 0), new Vector3(0, -0.22f, 1.9f), new Vector3(-1.4f, -0.22f, 0));
            b.Poly(ac, new Vector3(-1.4f, -0.22f, 0), new Vector3(0, -0.22f, 1.9f), new Vector3(0, 0.22f, 1.9f), new Vector3(-1.4f, 0.22f, 0));
            b.Poly(ac, new Vector3(1.4f, 0.22f, 0), new Vector3(0, 0.22f, 1.9f), new Vector3(0, -0.22f, 1.9f), new Vector3(1.4f, -0.22f, 0));
            b.Poly(Sh(ac, 0.8f), new Vector3(-1.4f, 0.22f, 0), new Vector3(1.4f, 0.22f, 0), new Vector3(1.4f, -0.22f, 0), new Vector3(-1.4f, -0.22f, 0));
            b.Pop();
            guideArrowMesh = b.Build("GuideArrow");
            return guideArrowMesh;
        }

        // ------------------------------------------------------------------ Mammoth Works
        static void BuildWorks()
        {
            var g = Group("MammothWorks");
            const float F = WorksFloor;
            var cut = new Vector4(20f, 35f, 80f, 90f);
            var z0 = Content.Zones[0];

            // ---- surface: ground around the openings, lids over the tunnel (see-through pieces), short roads
            var lids = new List<Rect>
            {
                Rect.MinMaxRect(35f, 36.4f, 47f, 47.6f), Rect.MinMaxRect(47f, 36.4f, 60.6f, 47.6f), Rect.MinMaxRect(49.4f, 47.6f, 60.6f, 53f)
            };
            var skip = new List<Rect>(lids) { Rect.MinMaxRect(22f, 36.4f, 35f, 47.6f), Rect.MinMaxRect(27f, 53f, 77f, 89f) };
            FillCutout(g, cut, skip);
            for (int i = 0; i < lids.Count; i++)
            {
                var r = lids[i];
                var lid = GroundPatch("TunnelLid" + i, g, r.xMin, r.yMin, r.xMax, r.yMax, true);
                OcclusionFader.Register("TunnelLid" + i, lid, true, 0.2f, new Bounds(new Vector3(r.center.x, -0.2f, r.center.y), new Vector3(r.width, 0.4f, r.height)));
                Block(g, "LidCol" + i, new Vector3(r.xMin, LidBottom, r.yMin), new Vector3(r.xMax, 0f, r.yMax));
            }
            Models.RoadRibbon(new List<Vector3> { new Vector3(14.5f, 0, 42f), new Vector3(22.5f, 0, 42f) }, 10f, z0, g, 0.028f);
            Models.RoadRibbon(new List<Vector3> { new Vector3(13.5f, 0, 84f), new Vector3(27.2f, 0, 84f) }, 8f, z0, g, 0.028f);
            // the turn-off is easy to spot from the road: painted arrows and a skull signpost at the junction
            var sb = new MeshBuilder();
            for (int i = 0; i < 2; i++) Chevron(sb, new Vector3(18.3f + i * 2.4f, 0.06f, 42f), 90f, 3.2f, Paint);
            sb.Cylinder(new Vector3(21f, 0f, 35.6f), 0.12f, 4.6f, 6, H("#5A3D2B"));
            sb.Material(0.5f, 0.2f);
            sb.Box(new Vector3(21f, 4.3f, 35.6f), new Vector3(2.6f, 1.2f, 0.18f), SignRed, Sh(SignRed, 1.1f));
            sb.Matte();
            Skull(sb, new Vector3(21f, 4.35f, 35.45f), 0.5f, 180f);
            sb.Box(new Vector3(22.7f, 3.55f, 35.5f), new Vector3(0.9f, 0.32f, 0.08f), Hazard);
            Emit("WorksSign", sb, g);
            Block(g, "WorksSignPost", new Vector3(20.8f, 0f, 35.4f), new Vector3(21.2f, 4.2f, 35.8f));
            // vent shafts over the tunnel: they show where it runs from the surface
            var b = new MeshBuilder();
            foreach (var v in new[] { new Vector3(44f, 0, 46.3f), new Vector3(58.8f, 0, 38f), new Vector3(58.8f, 0, 51.5f) })
            {
                b.Material(0.4f, 0.5f);
                b.Box(v + Vector3.up * 0.35f, new Vector3(1.2f, 0.7f, 1.2f), Concrete, ConcreteTop);
                b.Box(v + Vector3.up * 0.75f, new Vector3(1.0f, 0.12f, 1.0f), SteelDark);
                b.Matte();
            }
            Emit("Vents", b, g);

            // ---- entrance ramp (open cut), its retaining walls with parapets, painted arrows down
            var ramp = Ground.Pieces[FindPiece("WorksRamp")];
            b = new MeshBuilder();
            RampDeck(b, ramp, FloorC, 0.02f);
            for (float x = 24f; x < 41f; x += 4.5f)
            {
                float lz = ramp.rect.Local(x, 42f).y;
                Chevron(b, new Vector3(x, ramp.HeightLocal(lz) + 0.04f, 42f), 90f, 3.4f, Paint, -Mathf.Atan(ramp.SlopeLocal(lz)) * Mathf.Rad2Deg);
            }
            foreach (float zw in new[] { 36.7f, 47.3f })
            {
                WallBox(b, new Vector3(22f, F - 0.2f, zw - 0.3f), new Vector3(35f, 0.85f, zw + 0.3f), Concrete, ConcreteTop);
                HazardStripe(b, new Vector3(22f, 0, zw), new Vector3(35f, 0, zw), 0.64f, 0.1f, 0.9f, 8);
            }
            // portal: pillars + lintel with the Mammoth sign, lamps
            WallBox(b, new Vector3(34.6f, LidBottom, 36.4f), new Vector3(35.4f, 1.7f, 47.6f), Concrete, ConcreteTop);
            HazardStripe(b, new Vector3(34.55f, 0, 36.6f), new Vector3(34.55f, 0, 47.4f), 0.06f, 0.5f, -0.1f, 9);
            b.Material(0.5f, 0.2f);
            b.Box(new Vector3(34.9f, 2.5f, 42f), new Vector3(0.4f, 1.6f, 7.5f), SignRed, Sh(SignRed, 1.1f));
            b.Matte();
            Skull(b, new Vector3(34.6f, 2.55f, 42f), 0.9f, -90f);
            foreach (float z in new[] { 37.8f, 46.2f }) b.Box(new Vector3(34.5f, -0.75f, z), new Vector3(0.18f, 0.25f, 0.5f), Lamp);
            Emit("WorksEntrance", b, g);
            Block(g, "CutWallS", new Vector3(22f, F - 0.2f, 36.4f), new Vector3(35f, 0.85f, 37f));
            Block(g, "CutWallN", new Vector3(22f, F - 0.2f, 47f), new Vector3(35f, 0.85f, 47.6f));
            Block(g, "PortalCol", new Vector3(34.6f, LidBottom, 36.4f), new Vector3(35.4f, 1.7f, 47.6f));

            // ---- covered tunnel (east) and link (north): floors, walls, lamps, pipes
            b = new MeshBuilder();
            b.Box(new Vector3(51.05f, F - 0.1f, 42f), new Vector3(19.1f, 0.2f, 10f), FloorC);
            b.Box(new Vector3(55f, F - 0.1f, 50.5f), new Vector3(11.2f, 0.2f, 8f), FloorC);
            for (float x = 44f; x < 58f; x += 3f) b.Box(new Vector3(x, F + 0.012f, 42f), new Vector3(1.6f, 0.02f, 0.22f), Paint);
            b.Box(new Vector3(55f, F + 0.012f, 47.5f), new Vector3(0.22f, 0.02f, 9f), Paint);
            // walls (inner faces + tops at ground level)
            WallBox(b, new Vector3(35f, F, 36.4f), new Vector3(60.6f, -0.02f, 37f), Concrete, ConcreteDark);
            WallBox(b, new Vector3(35f, F, 47f), new Vector3(49.4f, -0.02f, 47.6f), Concrete, ConcreteDark);
            WallBox(b, new Vector3(60f, F, 36.4f), new Vector3(60.6f, -0.02f, 53f), Concrete, ConcreteDark);
            WallBox(b, new Vector3(49.4f, F, 47f), new Vector3(50f, -0.02f, 53f), Concrete, ConcreteDark);
            // corner chamfer guides the turn north (visual + collider)
            b.Push(new Vector3(59f, F + 1.6f, 38.2f), Quaternion.Euler(0, 45f, 0));
            b.Box(Vector3.zero, new Vector3(3.2f, 3.2f, 0.6f), ConcreteDark, Concrete);
            b.Pop();
            HazardStripe(b, new Vector3(57.9f, 0, 37.2f), new Vector3(60.0f, 0, 39.3f), 0.1f, 0.5f, F + 0.6f, 4);
            for (float x = 38f; x < 60f; x += 6f)
            {
                b.Box(new Vector3(x, F + 3.1f, 37.15f), new Vector3(0.6f, 0.22f, 0.3f), Lamp);
                b.Box(new Vector3(x + 3f, F + 3.1f, 46.85f), new Vector3(0.6f, 0.22f, 0.3f), Lamp);
            }
            b.Material(0.5f, 0.6f);
            b.CylinderBetween(new Vector3(36f, F + 3.6f, 37.25f), new Vector3(59.4f, F + 3.6f, 37.25f), 0.16f, 8, RustC);
            b.CylinderBetween(new Vector3(36f, F + 3.25f, 37.3f), new Vector3(59.4f, F + 3.25f, 37.3f), 0.1f, 8, Steel);
            b.Matte();
            Emit("WorksTunnel", b, g);
            Block(g, "TunnelWallS", new Vector3(35f, F, 36.4f), new Vector3(60.6f, 0f, 37f));
            Block(g, "TunnelWallN", new Vector3(35f, F, 47f), new Vector3(49.4f, 0f, 47.6f));
            Block(g, "TunnelWallE", new Vector3(60f, F, 36.4f), new Vector3(60.6f, 0f, 53f));
            Block(g, "LinkWallW", new Vector3(49.4f, F, 47f), new Vector3(50f, 0f, 53f));
            BlockO(g, "CornerCol", new Vector3(59f, F + 1.6f, 38.2f), new Vector3(3.2f, 3.2f, 0.6f), 45f);
            foreach (var p in new[] { new Vector3(41f, F, 42f), new Vector3(53f, F, 42f), new Vector3(55f, F, 49f) }) LampPool(g, p, 3.4f);

            // ---- hangar: sunken floor, concrete walls below ground, tin walls above, roof with the skull sign
            b = new MeshBuilder();
            b.Box(new Vector3(52f, F - 0.1f, 71f), new Vector3(48f, 0.2f, 34f), FloorC);
            // arena markings: big hazard ring and parking lines
            b.Ring(new Vector3(56.5f, F + 0.012f, 71f), 9.2f, 9.8f, 40, Paint);
            b.Ring(new Vector3(56.5f, F + 0.014f, 71f), 3.2f, 3.6f, 24, SignRed);
            for (float x = 40f; x < 75f; x += 5f) b.Box(new Vector3(x, F + 0.012f, 86.2f), new Vector3(0.18f, 0.02f, 3.2f), PaintWhite);
            b.Disc(new Vector3(47f, F + 0.01f, 61f), 1.6f, 14, FloorDark);
            b.Disc(new Vector3(68f, F + 0.01f, 79f), 2.1f, 14, FloorDark);
            // walls below ground (inner faces), with pillars and lamps
            const float T = HangarTop;
            WallBox(b, new Vector3(27f, F, 53f), new Vector3(50f, 0f, 54f), Concrete, ConcreteTop);
            WallBox(b, new Vector3(60f, F, 53f), new Vector3(77f, 0f, 54f), Concrete, ConcreteTop);
            WallBox(b, new Vector3(50f, LidBottom, 53f), new Vector3(60f, 0f, 54f), Concrete, ConcreteTop);
            WallBox(b, new Vector3(27f, F, 88f), new Vector3(77f, 0f, 89f), Concrete, ConcreteTop);
            WallBox(b, new Vector3(76f, F, 54f), new Vector3(77f, 0f, 88f), Concrete, ConcreteTop);
            WallBox(b, new Vector3(27f, F, 54f), new Vector3(28f, 0f, 88f), Concrete, ConcreteTop);
            for (float x = 33f; x < 76f; x += 8f)
            {
                b.Box(new Vector3(x, F + 2.25f, 87.6f), new Vector3(0.8f, 4.5f, 0.8f), ConcreteDark);
                b.Box(new Vector3(x, F + 3.4f, 87.1f), new Vector3(0.7f, 0.25f, 0.3f), Lamp);
                b.Box(new Vector3(x + 4f, F + 2.25f, 54.4f), new Vector3(0.8f, 4.5f, 0.8f), ConcreteDark);
            }
            for (float z = 58f; z < 88f; z += 8f) b.Box(new Vector3(75.6f, F + 2.25f, z), new Vector3(0.8f, 4.5f, 0.8f), ConcreteDark);
            HazardStripe(b, new Vector3(50f, 0, 54.05f), new Vector3(60f, 0, 54.05f), 0.08f, 0.4f, LidBottom - 0.2f, 8);
            // tire stacks and drums in the corners (against the walls, out of the way)
            foreach (var p in new[] { new Vector3(74.5f, F, 56f), new Vector3(74.5f, F, 86f), new Vector3(39f, F, 86.5f) })
                for (int k = 0; k < 3; k++) b.Cylinder(p + Vector3.up * (k * 0.26f), 0.48f, 0.25f, 10, Tire, -1, H("#1A1818"));
            b.Material(0.4f, 0.3f);
            foreach (var p in new[] { new Vector3(73.8f, F, 59f), new Vector3(72.6f, F, 59.2f) }) b.Cylinder(p, 0.42f, 1.1f, 10, SignRed, -1, Sh(SignRed, 0.8f));
            b.Matte();
            // loading ramp block with a railing on its open side
            var load = Ground.Pieces[FindPiece("WorksLoadRamp")];
            RampDeck(b, load, FloorC, 0.02f);
            for (float z = 63f; z < 80f; z += 4f)
            {
                float h = load.HeightLocal(load.rect.Local(32f, z).y);
                float slope = Mathf.Atan(load.SlopeLocal(load.rect.Local(32f, z).y)) * Mathf.Rad2Deg;
                Chevron(b, new Vector3(32f, h + 0.04f, z), 0f, 3f, Paint, -slope);
            }
            b.Box(new Vector3(32f, -0.1f, 84f), new Vector3(8f, 0.2f, 8f), FloorC);
            b.Box(new Vector3(32f, (F - 0.2f) * 0.5f, 84f), new Vector3(8f, -F, 8f), ConcreteDark);
            for (float z = 60f; z < 88f; z += 2f)
            {
                float h1 = load.HeightLocal(load.rect.Local(32f, Mathf.Min(z + 2f, 80f)).y);
                if (z >= 80f) h1 = 0f;
                WallBox(b, new Vector3(36f, F, z), new Vector3(36.6f, h1, z + 2f), Concrete, ConcreteTop);
                b.Box(new Vector3(36.3f, h1 + 0.5f, z + 1f), new Vector3(0.08f, 1.0f, 0.08f), Hazard);
                b.Box(new Vector3(36.3f, h1 + 1.0f, z + 1f), new Vector3(0.1f, 0.1f, 2f), Hazard);
                Block(g, "LoadRail", new Vector3(36f, F, z), new Vector3(36.6f, h1 + 1.0f, z + 2f));
            }
            Emit("WorksHangar", b, g);
            foreach (var p in new[] { new Vector3(44f, F, 64f), new Vector3(66f, F, 64f), new Vector3(44f, F, 79f), new Vector3(66f, F, 79f), new Vector3(56f, F, 71f) }) LampPool(g, p, 5f);
            // hangar wall colliders (openings: tunnel link in the south wall, the door in the west wall)
            Block(g, "HangarS1", new Vector3(27f, F, 53f), new Vector3(50f, T, 54f));
            Block(g, "HangarS2", new Vector3(60f, F, 53f), new Vector3(77f, T, 54f));
            Block(g, "HangarS3", new Vector3(50f, LidBottom, 53f), new Vector3(60f, T, 54f));
            Block(g, "HangarN", new Vector3(27f, F, 88f), new Vector3(77f, T, 89f));
            Block(g, "HangarE", new Vector3(76f, F, 53f), new Vector3(77f, T, 89f));
            Block(g, "HangarW1", new Vector3(27f, F, 53f), new Vector3(28f, T, 80f));
            Block(g, "HangarW2", new Vector3(27f, F, 88f), new Vector3(28f, T, 89f));
            Block(g, "HangarW3", new Vector3(27f, F, 80f), new Vector3(28f, -0.02f, 88f));
            Block(g, "HangarRoof", new Vector3(26.5f, T, 52.5f), new Vector3(77.5f, T + 0.45f, 89.5f));

            // above-ground walls: tin on a concrete plinth; the south one faces the camera and fades when it hides the car
            BuildHangarWall(g, "HangarWallS", new Vector3(27f, 0f, 53f), new Vector3(77f, T, 54f), true, 0f, 0f);
            BuildHangarWall(g, "HangarWallN", new Vector3(27f, 0f, 88f), new Vector3(77f, T, 89f), false, 0f, 0f);
            BuildHangarWall(g, "HangarWallE", new Vector3(76f, 0f, 54f), new Vector3(77f, T, 88f), false, 0f, 0f);
            BuildHangarWall(g, "HangarWallW", new Vector3(27f, 0f, 54f), new Vector3(28f, T, 80f), false, 0f, 0f);
            BuildHangarWall(g, "HangarWallW2", new Vector3(27f, 0f, 88f), new Vector3(28f, T, 89f), false, 0f, 0f);
            b = new MeshBuilder();
            // rolled-up door above the west opening + hazard frame
            b.Material(0.4f, 0.6f);
            b.CylinderBetween(new Vector3(27.5f, T - 0.25f, 80f), new Vector3(27.5f, T - 0.25f, 88f), 0.35f, 10, TinDark);
            b.Matte();
            HazardStripe(b, new Vector3(27.5f, 0, 80.1f), new Vector3(27.5f, 0, 87.9f), 1.05f, 0.12f, 0.05f, 8);
            Emit("HangarDoor", b, g);

            // roof: corrugated sheets, skylights, vents, big red skull - the landmark seen from the road
            b = new MeshBuilder();
            b.Box(new Vector3(52f, T + 0.2f, 71f), new Vector3(51f, 0.4f, 37f), Tin, H("#A7A298"));
            for (float x = 28f; x < 76.5f; x += 1.5f) b.Box(new Vector3(x, T + 0.43f, 71f), new Vector3(0.5f, 0.05f, 36.4f), H("#A9A49A"));
            for (int i = 0; i < 3; i++)
            {
                b.Material(0.85f, 0f);
                b.Box(new Vector3(36f + i * 16f, T + 0.5f, 60f), new Vector3(5f, 0.12f, 3f), H("#6F8C99"));
                b.Matte();
                b.Box(new Vector3(36f + i * 16f, T + 0.45f, 60f), new Vector3(5.4f, 0.1f, 3.4f), SteelDark);
            }
            b.Material(0.5f, 0.6f);
            foreach (var p in new[] { new Vector3(72f, 0, 84f), new Vector3(31f, 0, 58f), new Vector3(72f, 0, 58f) })
            {
                b.Cylinder(new Vector3(p.x, T + 0.4f, p.z), 0.6f, 0.9f, 10, Steel, -1, SteelDark);
                b.Cylinder(new Vector3(p.x, T + 1.3f, p.z), 0.75f, 0.18f, 10, SteelDark);
            }
            b.Matte();
            b.Material(0.4f, 0f);
            b.Box(new Vector3(56f, T + 0.47f, 75f), new Vector3(22f, 0.04f, 9f), SignRed);
            b.Matte();
            Skull(b, new Vector3(56f, T + 0.5f, 75.2f), 2.6f, 0f, true);
            HazardStripe(b, new Vector3(26.6f, 0, 52.55f), new Vector3(77.4f, 0, 52.55f), 0.18f, 0.18f, T + 0.32f, 26);
            var roof = Emit("HangarRoof", b, g);
            OcclusionFader.Register("HangarRoof", roof, true, 0.08f, new Bounds(new Vector3(52f, T + 0.4f, 71f), new Vector3(51f, 1.0f, 37f)));
        }

        static int FindPiece(string name)
        {
            for (int i = 0; i < Ground.Pieces.Count; i++) if (Ground.Pieces[i].name == name) return i;
            return -1;
        }

        static void BuildHangarWall(Transform g, string name, Vector3 min, Vector3 max, bool fades, float a, float b2)
        {
            var b = new MeshBuilder();
            var size = max - min;
            bool alongX = size.x > size.z;
            WallBox(b, min, new Vector3(max.x, 0.7f, max.z), Concrete, ConcreteTop);
            WallBox(b, new Vector3(min.x, 0.7f, min.z), max, Tin, H("#A7A298"));
            float len = alongX ? size.x : size.z;
            int n = Mathf.Max(2, Mathf.RoundToInt(len / 1.2f));
            for (int i = 0; i < n; i++)
            {
                float t = (i + 0.5f) / n;
                var p = alongX ? new Vector3(Mathf.Lerp(min.x, max.x, t), 0, min.z - 0.02f) : new Vector3(min.x - 0.02f, 0, Mathf.Lerp(min.z, max.z, t));
                var s = alongX ? new Vector3(0.36f, 2.2f, 0.06f) : new Vector3(0.06f, 2.2f, 0.36f);
                b.Box(p + Vector3.up * 1.85f, s, i % 7 == 3 ? RustC : TinDark);
            }
            var go = Emit(name, b, g);
            if (fades) OcclusionFader.Register(name, go, false, 0.22f, null, 0.55f);
        }

        /// <summary>The Mammoth sign: a big stylized bull skull with horns (seen from above or from the front).</summary>
        static void Skull(MeshBuilder b, Vector3 p, float s, float yaw, bool flat = false)
        {
            b.Push(p, flat ? Quaternion.Euler(-90f, yaw, 0f) : Quaternion.Euler(0f, yaw, 0f), Vector3.one * s);
            b.Material(0.35f, 0f);
            b.Sphere(new Vector3(0, 0.15f, 0), new Vector3(0.62f, 0.55f, 0.3f), Bone, 1);
            b.Box(new Vector3(0, -0.38f, 0), new Vector3(0.5f, 0.42f, 0.36f), Bone);
            b.Sphere(new Vector3(-0.22f, 0.12f, -0.22f), new Vector3(0.15f, 0.15f, 0.1f), H("#2A1E1A"), 0);
            b.Sphere(new Vector3(0.22f, 0.12f, -0.22f), new Vector3(0.15f, 0.15f, 0.1f), H("#2A1E1A"), 0);
            for (int sd = -1; sd <= 1; sd += 2)
            {
                b.CylinderBetween(new Vector3(sd * 0.5f, 0.32f, 0), new Vector3(sd * 0.95f, 0.55f, 0), 0.12f, 6, Bone, 0.09f);
                b.CylinderBetween(new Vector3(sd * 0.95f, 0.55f, 0), new Vector3(sd * 1.05f, 0.95f, 0), 0.09f, 6, Bone, 0.02f);
            }
            b.Matte();
            b.Pop();
        }

        /// <summary>Strip mesh following a sloped floor piece (its local Z profile), plus a skirt down to its low end.</summary>
        static void RampDeck(MeshBuilder b, FloorPiece p, Color col, float lift)
        {
            var r = p.rect;
            int n = Mathf.Max(4, Mathf.CeilToInt(r.half.y * 2f / 0.8f));
            for (int i = 0; i < n; i++)
            {
                float z0 = Mathf.Lerp(-r.half.y, r.half.y, i / (float)n), z1 = Mathf.Lerp(-r.half.y, r.half.y, (i + 1) / (float)n);
                float h0 = p.HeightLocal(z0) + lift, h1 = p.HeightLocal(z1) + lift;
                var a = r.World(-r.half.x, z0, h0); var c = r.World(r.half.x, z0, h0);
                var d = r.World(r.half.x, z1, h1); var e = r.World(-r.half.x, z1, h1);
                b.PolyOut(col, (a + d) * 0.5f - Vector3.up, a, e, d, c);
            }
        }

        // ------------------------------------------------------------------ jump ramps
        /// <summary>Steel launch ramp: deck with yellow chevrons, side skirts, struts, a hazard-striped lip and side colliders.</summary>
        static void BuildJumpRamp(FloorPiece p)
        {
            var g = Group(p.name);
            var r = p.rect;
            float baseY = p.h0;                 // a ramp on a summit stands on it (0 for ramps on the ground)
            var b = new MeshBuilder();
            b.Material(0.45f, 0.55f);
            RampDeck(b, p, H("#7C838A"), 0.0f);
            b.Matte();
            int n = 8;
            for (int i = 0; i < n; i++)
            {
                float z0 = Mathf.Lerp(-r.half.y, r.half.y, i / (float)n), z1 = Mathf.Lerp(-r.half.y, r.half.y, (i + 1) / (float)n);
                float h0 = p.HeightLocal(z0), h1 = p.HeightLocal(z1);
                foreach (int s in new[] { -1, 1 })
                {
                    var a = r.World(s * r.half.x, z0, baseY); var c = r.World(s * r.half.x, z1, baseY);
                    var d = r.World(s * r.half.x, z1, h1); var e = r.World(s * r.half.x, z0, h0);
                    b.PolyOut(i % 2 == 0 ? RustD : RustC, r.Center + Vector3.up * 0.5f, a, c, d, e);
                }
            }
            // back face (the lip drops straight down)
            var bl = r.World(-r.half.x, r.half.y, baseY); var br = r.World(r.half.x, r.half.y, baseY);
            var tl = r.World(-r.half.x, r.half.y, p.h1); var tr = r.World(r.half.x, r.half.y, p.h1);
            b.PolyOut(RustD, r.Center, bl, br, tr, tl);
            // chevrons up the deck + hazard lip
            float slopeDeg = Mathf.Atan(p.SlopeLocal(0f)) * Mathf.Rad2Deg;
            for (int i = 0; i < 3; i++)
            {
                float lz = Mathf.Lerp(-r.half.y * 0.55f, r.half.y * 0.55f, i / 2f);
                Chevron(b, r.World(0f, lz, p.HeightLocal(lz) + 0.04f), r.Yaw, Mathf.Min(3.2f, r.half.x * 1.3f), Gl("#FFD24A", 0.6f), -slopeDeg);
            }
            HazardStripe(b, r.World(-r.half.x, r.half.y - 0.15f, 0f), r.World(r.half.x, r.half.y - 0.15f, 0f), 0.3f, 0.14f, p.h1 + 0.02f, 8);
            for (int s = -1; s <= 1; s += 2)
                b.CylinderBetween(r.World(s * (r.half.x - 0.5f), r.half.y - 0.3f, baseY), r.World(s * (r.half.x - 0.5f), r.half.y - 2.2f, p.HeightLocal(r.half.y - 2.2f) - 0.1f), 0.08f, 6, SteelDark);
            Emit("Ramp", b, g);
            // the sides are walls once the deck is higher than a curb
            float zStart = -r.half.y;
            for (int i = 0; i <= 20; i++)
            {
                float lz = Mathf.Lerp(-r.half.y, r.half.y, i / 20f);
                if (p.HeightLocal(lz) - baseY > 0.35f) { zStart = lz; break; }
            }
            float len = r.half.y - zStart, rise = p.h1 - baseY;
            foreach (int s in new[] { -1, 1 })
                BlockO(g, "RampSide", r.World(s * (r.half.x + 0.15f), (zStart + r.half.y) * 0.5f, baseY + rise * 0.5f), new Vector3(0.3f, rise, len), r.Yaw);
            // the drop behind the lip: a wall for cars on the ground, low enough that a car still on the deck (its box
            // reaches 2.4 m ahead of its centre) passes over it
            BlockO(g, "RampBack", r.World(0f, r.half.y + 0.25f, baseY + rise * 0.275f), new Vector3(r.half.x * 2f, rise * 0.55f, 0.4f), r.Yaw);
        }

        static void BuildObstacleJump(string name, Vector3 lip, float yaw, float height, int zone)
        {
            var g = Group(name + "Wreck");
            var fwd = new Vector3(Mathf.Sin(yaw * Mathf.Deg2Rad), 0f, Mathf.Cos(yaw * Mathf.Deg2Rad));
            var wreckPos = lip + fwd * 5.6f;
            var b = new MeshBuilder();
            if (zone == 0)
            {
                // a rusted bus on its side across the road (flattened, 1.6 m)
                b.Push(wreckPos, Quaternion.Euler(0f, yaw + 90f, 0f));
                b.Material(0.25f, 0.3f);
                b.BevelBox(new Vector3(0, 0.8f, 0), new Vector3(2.5f, 1.6f, 9.5f), 0.25f, H("#C99A3B"), H("#D8AE52"));
                for (int i = -3; i <= 3; i++) b.Box(new Vector3(-1.27f, 0.95f, i * 1.25f), new Vector3(0.05f, 0.6f, 0.9f), H("#3D4A50"));
                b.Box(new Vector3(0, 1.62f, 0), new Vector3(2.2f, 0.06f, 9f), RustC);
                b.Matte();
                for (int i = -1; i <= 1; i += 2) b.Cylinder(new Vector3(1.3f, 0.5f, i * 3.2f), 0.5f, 0.3f, 10, Tire);
                b.Pop();
                BlockO(g, "WreckCol", wreckPos + Vector3.up * 0.8f, new Vector3(9.5f, 1.6f, 2.5f), yaw);
            }
            else
            {
                // a wall of toxic drums and scrap (1.5 m)
                b.Push(wreckPos, Quaternion.Euler(0f, yaw, 0f));
                for (int i = -4; i <= 4; i++)
                    for (int k = 0; k < (i % 2 == 0 ? 2 : 1); k++)
                    {
                        b.Material(0.4f, 0.3f);
                        b.Cylinder(new Vector3(i * 0.95f, k * 0.78f, (i % 3) * 0.15f), 0.42f, 0.76f, 10, i % 2 == 0 ? H("#C9B23A") : H("#5E7A3C"), -1, Sh(H("#C9B23A"), 0.85f));
                        b.Matte();
                    }
                b.Disc(new Vector3(0, 0.02f, 1.8f), 1.6f, 14, Gl("#8FE05A", 0.6f));
                b.Pop();
                BlockO(g, "WreckCol", wreckPos + Vector3.up * 0.75f, new Vector3(9f, 1.5f, 1.4f), yaw);
            }
            Emit("Wreck", b, g);
        }

        // ------------------------------------------------------------------ stash plateau
        static void BuildPlateau(int zone, Vector3 center)
        {
            var g = Group("Plateau" + zone);
            var z = Content.Zones[zone];
            const float top = 2.0f, half = 7f;
            var b = new MeshBuilder();
            var rock = z.cliff; var rockTop = Color.Lerp(z.cliff, Color.white, 0.18f);
            b.Box(center + Vector3.up * (top * 0.5f), new Vector3(half * 2f, top, half * 2f), rock, Color.Lerp(z.ground, z.groundAlt, 0.5f));
            var rnd = new System.Random(500 + zone);
            float R() => (float)rnd.NextDouble();
            // rocky skirt around the sides (the rim stays clear where the car flies in and where it drops off); the rocks
            // stop cars with colliders of their own shape - except on the ramp side, where a car flies in over them
            var hulls = new List<Vector3[]>();
            for (int side = 0; side < 4; side++)
                for (int i = 0; i < 6; i++)
                {
                    float t = -half + (i + 0.5f) * (half * 2f / 6f);
                    Vector3 p = side == 0 ? new Vector3(t, 0, -half) : side == 1 ? new Vector3(t, 0, half) : side == 2 ? new Vector3(-half, 0, t) : new Vector3(half, 0, t);
                    var outward = side == 0 ? Vector3.back : side == 1 ? Vector3.forward : side == 2 ? Vector3.left : Vector3.right;
                    var radii = new Vector3(1.5f + R() * 0.6f, 1.2f + R() * 0.5f, 1.3f);
                    var col = R() > 0.5f ? rock : z.cliffDark;
                    int seedR = rnd.Next();
                    if (side == 0 && t > -3.5f && t < 4.5f) continue;            // the drop-off gap in the south rim
                    b.rockHulls = side == 2 ? null : hulls;
                    b.Rock(center + p + outward * 0.6f + Vector3.up * 0.8f, radii, col, seedR, rockTop, 0.22f, 1);
                    b.rockHulls = null;
                }
            // rim stones on the top edge (north and east), a drop-off gap in the south rim
            for (int i = 0; i < 7; i++)
            {
                b.Rock(center + new Vector3(-half + 1f + i * 2f, top + 0.15f, half - 0.4f), new Vector3(0.6f, 0.35f, 0.4f), z.cliffDark, rnd.Next(), rockTop, 0.2f, 1);
                b.Rock(center + new Vector3(half - 0.4f, top + 0.15f, -half + 1f + i * 2f), new Vector3(0.4f, 0.35f, 0.6f), z.cliffDark, rnd.Next(), rockTop, 0.2f, 1);
            }
            // a little camp on top: lamp post + flag + tarp
            b.Cylinder(center + new Vector3(-4.8f, top, 4.8f), 0.08f, 2.8f, 6, H("#5A3D2B"));
            b.Box(center + new Vector3(-4.3f, top + 2.5f, 4.8f), new Vector3(1.0f, 0.6f, 0.04f), SignRed);
            Emit("Plateau", b, g);
            Models.RockColliders(g, "PlateauRocks", hulls);
            Block(g, "RimW", center + new Vector3(-half - 0.6f, -0.5f, -half), center + new Vector3(-half, top + 0.3f, half));
            Block(g, "RimN", center + new Vector3(-half, -0.5f, half), center + new Vector3(half, top + 0.3f, half + 0.6f));
            Block(g, "RimE", center + new Vector3(half, -0.5f, -half), center + new Vector3(half + 0.6f, top + 0.3f, half));
            Block(g, "RimS1", center + new Vector3(-half, -0.5f, -half - 0.6f), center + new Vector3(-2.5f, top + 0.3f, -half));
            Block(g, "RimS2", center + new Vector3(3.5f, -0.5f, -half - 0.6f), center + new Vector3(half, top + 0.3f, -half));
            // the drop-off gap: no rim on top, but the face still blocks a car on the ground below
            Block(g, "DropFace", center + new Vector3(-2.5f, -0.5f, -half - 0.4f), center + new Vector3(3.5f, top - 0.05f, -half));
            var drop = g.Find("DropFace");
            var plateau = Ground.Pieces[FindPiece("Plateau" + zone)];
            if (drop != null) Ground.AddLedge(drop.GetComponent<Collider>(), plateau, top - 0.05f);
        }

        // ------------------------------------------------------------------ drive-through garage (zone 0)
        static void BuildGarage()
        {
            var g = Group("Garage");
            var c = garagePos; float yaw = garageYaw;
            var rot = Quaternion.Euler(0f, yaw, 0f);
            const float hw = 4.7f, hl = 6f, h = 3.6f;
            var b = new MeshBuilder();
            b.Push(c, rot);
            // floor slab with oil stains
            b.Box(new Vector3(0, 0.03f, 0), new Vector3(hw * 2f, 0.06f, hl * 2f + 0.6f), FloorC);
            b.Disc(new Vector3(-1.5f, 0.065f, 1.2f), 1.1f, 12, FloorDark);
            // workbench, tire rack, hanging lamp, tool board (inside along the north wall: local -x)
            b.Box(new Vector3(-hw + 0.7f, 0.5f, -2.5f), new Vector3(0.9f, 1.0f, 3f), WoodC);
            for (int k = 0; k < 3; k++) b.Cylinder(new Vector3(-hw + 0.7f, 0.06f + k * 0.26f, 3.2f), 0.45f, 0.25f, 10, Tire);
            b.Box(new Vector3(0, h - 0.5f, 0), new Vector3(0.7f, 0.18f, 0.7f), Lamp);
            b.Pop();
            var floor = Emit("GarageFloor", b, g);
            // the north wall (away from the camera) stays solid
            b = new MeshBuilder();
            b.Push(c, rot);
            GarageWall(b, -hw, hl, h);
            b.Pop();
            Emit("GarageWallN", b, g);
            // the south wall faces the camera: it fades while the car is inside or behind it
            b = new MeshBuilder();
            b.Push(c, rot);
            GarageWall(b, hw, hl, h);
            b.Pop();
            var wallS = Emit("GarageWallS", b, g);
            OcclusionFader.Register("GarageWallS", wallS, false, 0.22f, null, 0.55f);
            // roof with a big painted sign
            b = new MeshBuilder();
            b.Push(c, rot);
            b.Box(new Vector3(0, h + 0.15f, 0), new Vector3(hw * 2f + 0.8f, 0.3f, hl * 2f + 0.8f), RustD, RustC);
            for (int i = -4; i <= 4; i++) b.Box(new Vector3(i * 1.1f, h + 0.33f, 0), new Vector3(0.45f, 0.05f, hl * 2f + 0.6f), i % 3 == 0 ? Tin : RustC);
            b.Box(new Vector3(0, h + 0.38f, 0), new Vector3(3.6f, 0.05f, 6f), H("#E9E1CF"));
            b.Material(0.6f, 0.3f);
            b.Box(new Vector3(0, h + 0.42f, -1.1f), new Vector3(1.6f, 0.05f, 2.6f), SignRed);
            b.Box(new Vector3(0, h + 0.42f, 1.4f), new Vector3(0.5f, 0.05f, 1.6f), SignRed);
            b.Matte();
            b.Pop();
            var roof = Emit("GarageRoof", b, g);
            var bounds = new Bounds(c + Vector3.up * (h + 0.2f), new Vector3(13f, 0.8f, 13f));
            OcclusionFader.Register("GarageRoof", roof, true, 0.2f, bounds);
            foreach (int s in new[] { -1, 1 })
                BlockO(g, "GarageWall", c + rot * new Vector3(s * (hw + 0.2f), h * 0.5f, 0f), new Vector3(0.4f, h, hl * 2f), yaw);
            BlockO(g, "GarageRoofCol", c + Vector3.up * (h + 0.15f), new Vector3(hw * 2f + 0.8f, 0.3f, hl * 2f + 0.8f), yaw);
            LampPool(g, c, 3.6f);
        }

        static void GarageWall(MeshBuilder b, float x, float hl, float h)
        {
            b.Box(new Vector3(x, h * 0.5f, 0), new Vector3(0.4f, h, hl * 2f), Tin, H("#A7A298"));
            int n = 9;
            for (int i = 0; i < n; i++)
                b.Box(new Vector3(x + Mathf.Sign(x) * 0.22f, h * 0.5f, -hl + (i + 0.5f) * (hl * 2f / n)), new Vector3(0.05f, h - 0.4f, 0.5f), i % 4 == 1 ? RustC : TinDark);
            for (int e = -1; e <= 1; e += 2)
                for (int k = 0; k < 4; k++)
                    b.Box(new Vector3(x, (k + 0.5f) * h / 4f, e * hl), new Vector3(0.5f, h / 4f - 0.02f, 0.5f), k % 2 == 0 ? Hazard : HazardDark);
        }

        // ------------------------------------------------------------------ rock tunnel (zone 1)
        static void BuildRockTunnel()
        {
            var g = Group("RockTunnel");
            var c = rockTunnel;
            var z = Content.Zones[1];
            const float hw = 5.5f, hl = 9f, h = 4.6f;
            var rnd = new System.Random(1701);
            float R() => (float)rnd.NextDouble();
            var top = Color.Lerp(z.cliff, Color.white, 0.18f);
            // two rock masses beside the road
            for (int s = -1; s <= 1; s += 2)
            {
                var b = new MeshBuilder();
                var hulls = new List<Vector3[]>();
                b.rockHulls = hulls;
                for (int i = 0; i < 5; i++)
                    for (int row = 0; row < 2; row++)
                    {
                        var p = c + new Vector3(s * (hw + 3.6f + row * 4.6f + R()), 0f, -hl + 1.5f + i * 3.8f + R());
                        b.Rock(p + Vector3.up * 2.6f, new Vector3(3.2f + R(), 3.4f + R() * 1.2f, 2.9f), R() > 0.5f ? z.cliff : z.cliffDark, rnd.Next(), top, 0.24f, 2);
                    }
                b.rockHulls = null;
                var go = Emit("RockMass" + (s < 0 ? "W" : "E"), b, g);
                var mn = c + new Vector3(s < 0 ? -hw - 12f : hw, -0.5f, -hl);
                var mx = c + new Vector3(s < 0 ? -hw : hw + 12f, 6.5f, hl);
                // the rock's solid core (not the loose bounds of the boulders) decides when it is in the way
                var core = new Bounds((mn + mx) * 0.5f, mx - mn);
                OcclusionFader.Register("RockMass" + s, go, false, 0.3f, core, 0.35f);
                // collision: each boulder's own shape, plus a core block well inside the mass that closes the seams
                Models.RockColliders(g, "RockMassRocks" + s, hulls);
                Block(g, "RockCore" + s, c + new Vector3(s < 0 ? -hw - 10f : hw + 1.5f, -0.5f, -hl), c + new Vector3(s < 0 ? -hw - 1.5f : hw + 10f, 6.5f, hl));
            }
            // the bridge of rock over the road (fades while the car is under it)
            var rb = new MeshBuilder();
            for (int i = 0; i < 5; i++)
                rb.Rock(c + new Vector3(R() * 2f - 1f, h + 1.0f, -hl + 1.8f + i * 3.6f), new Vector3(hw + 1.6f, 1.5f + R() * 0.4f, 2.6f), R() > 0.5f ? z.cliff : z.cliffDark, rnd.Next(), top, 0.2f, 2);
            // timber portal frames with lamps at both mouths
            foreach (int e in new[] { -1, 1 })
            {
                rb.Box(c + new Vector3(0, h - 0.1f, e * hl), new Vector3(hw * 2f + 0.6f, 0.5f, 0.5f), H("#6E4A30"));
                rb.Box(c + new Vector3(0, h - 0.45f, e * (hl + 0.28f)), new Vector3(0.8f, 0.25f, 0.06f), Lamp);
                HazardStripe(rb, c + new Vector3(-hw, 0, e * (hl + 0.27f)), c + new Vector3(hw, 0, e * (hl + 0.27f)), 0.05f, 0.25f, h - 0.1f, 8);
            }
            var bridge = Emit("RockBridge", rb, g);
            OcclusionFader.Register("RockBridge", bridge, true, 0.2f, new Bounds(c + Vector3.up * (h + 1.2f), new Vector3(hw * 2f + 4f, 2.8f, hl * 2f + 1f)));
            var pb = new MeshBuilder();
            foreach (int s in new[] { -1, 1 })
                for (int e = -1; e <= 1; e += 2)
                    pb.Box(c + new Vector3(s * (hw - 0.2f), h * 0.5f, e * hl), new Vector3(0.5f, h, 0.5f), H("#6E4A30"));
            Emit("TunnelPosts", pb, g);
            Block(g, "RockRoof", c + new Vector3(-hw, h, -hl), c + new Vector3(hw, h + 2.2f, hl));
            LampPool(g, c + new Vector3(0, 0, -hl + 3f), 3.4f);
            LampPool(g, c + new Vector3(0, 0, hl - 3f), 3.4f);
        }

        // ------------------------------------------------------------------ pipeline underpass + pipeline (zone 1)
        static void BuildUnderpass()
        {
            var g = Group("Underpass");
            const float F = UnderpassFloor;
            var cut = new Vector4(0f, 200f, 40f, 215f);
            var lid = Rect.MinMaxRect(UpLid0, UpZ0 - 0.6f, UpLid1, UpZ1 + 0.6f);
            FillCutout(g, cut, new List<Rect> { lid, Rect.MinMaxRect(UpX0, UpZ0 - 0.6f, UpLid0, UpZ1 + 0.6f), Rect.MinMaxRect(UpLid1, UpZ0 - 0.6f, UpX3, UpZ1 + 0.6f) });
            var lidGo = GroundPatch("UnderpassLid", g, lid.xMin, lid.yMin, lid.xMax, lid.yMax, true);
            Block(g, "UnderpassLidCol", new Vector3(lid.xMin, LidBottom, lid.yMin), new Vector3(lid.xMax, 0f, lid.yMax));
            var z1 = Content.Zones[1];
            var b = new MeshBuilder();
            var down = Ground.Pieces[FindPiece("UnderpassDown")];
            var up = Ground.Pieces[FindPiece("UnderpassUp")];
            RampDeck(b, down, H("#7F767C"), 0.02f);
            RampDeck(b, up, H("#7F767C"), 0.02f);
            b.Box(new Vector3((UpX1 + UpX2) * 0.5f, F - 0.1f, (UpZ0 + UpZ1) * 0.5f), new Vector3(UpX2 - UpX1 + 0.6f, 0.2f, UpZ1 - UpZ0), H("#7F767C"));
            for (float x = UpX0 + 1f; x < UpX3; x += 3f)
            {
                var p = x < UpX1 ? down : x > UpX2 ? up : null;
                float hh = p != null ? p.HeightLocal(p.rect.Local(x, 208.5f).y) : F;
                b.Box(new Vector3(x, hh + 0.04f, 208.5f), new Vector3(1.4f, 0.02f, 0.2f), z1.roadLine);
            }
            foreach (float zw in new[] { UpZ0 - 0.3f, UpZ1 + 0.3f })
            {
                WallBox(b, new Vector3(UpX0, F - 0.2f, zw - 0.3f), new Vector3(UpLid0, 0.85f, zw + 0.3f), Concrete, ConcreteTop);
                WallBox(b, new Vector3(UpLid1, F - 0.2f, zw - 0.3f), new Vector3(UpX3, 0.85f, zw + 0.3f), Concrete, ConcreteTop);
                WallBox(b, new Vector3(UpLid0, F - 0.2f, zw - 0.3f), new Vector3(UpLid1, -0.02f, zw + 0.3f), Concrete, ConcreteDark);
                HazardStripe(b, new Vector3(UpX0, 0, zw), new Vector3(UpLid0, 0, zw), 0.62f, 0.1f, 0.9f, 6);
                HazardStripe(b, new Vector3(UpLid1, 0, zw), new Vector3(UpX3, 0, zw), 0.62f, 0.1f, 0.9f, 6);
                // parapets only where the cut is open; under the lid the wall stops at the ground (cars drive over it)
                Block(g, "UnderpassWallW", new Vector3(UpX0, F - 0.2f, zw - 0.3f), new Vector3(UpLid0, 0.85f, zw + 0.3f));
                Block(g, "UnderpassWallE", new Vector3(UpLid1, F - 0.2f, zw - 0.3f), new Vector3(UpX3, 0.85f, zw + 0.3f));
                Block(g, "UnderpassWallC", new Vector3(UpLid0, F - 0.2f, zw - 0.3f), new Vector3(UpLid1, LidBottom, zw + 0.3f));
            }
            for (float x = UpLid0 + 2f; x < UpLid1; x += 5f)
            {
                b.Box(new Vector3(x, F + 2.6f, UpZ0 + 0.05f), new Vector3(0.6f, 0.2f, 0.2f), Lamp);
                b.Box(new Vector3(x + 2.5f, F + 2.6f, UpZ1 - 0.05f), new Vector3(0.6f, 0.2f, 0.2f), Lamp);
            }
            Emit("UnderpassBody", b, g);
            // portals (above-ground faces over each mouth) fade like the lid
            foreach (float xp in new[] { UpLid0, UpLid1 })
            {
                var pb = new MeshBuilder();
                float dx = xp < 20f ? -0.4f : 0.4f;
                WallBox(pb, new Vector3(xp - 0.4f, LidBottom, UpZ0 - 0.6f), new Vector3(xp + 0.4f, 1.3f, UpZ1 + 0.6f), Concrete, ConcreteTop);
                HazardStripe(pb, new Vector3(xp + dx * 1.05f, 0, UpZ0 - 0.4f), new Vector3(xp + dx * 1.05f, 0, UpZ1 + 0.4f), 0.06f, 0.45f, -0.15f, 8);
                var portal = Emit("UnderpassPortal", pb, g);
                OcclusionFader.Register("UnderpassPortal" + xp, portal, false, 0.24f, null, 0.5f);
                Block(g, "UnderpassPortalCol", new Vector3(xp - 0.4f, LidBottom, UpZ0 - 0.6f), new Vector3(xp + 0.4f, 1.3f, UpZ1 + 0.6f));
            }
            OcclusionFader.Register("UnderpassLid", lidGo, true, 0.2f, new Bounds(new Vector3(lid.center.x, -0.2f, lid.center.y), new Vector3(lid.width, 0.4f, lid.height)));
            LampPool(g, new Vector3(18f, F, 208.5f), 3.6f);
            LampPool(g, new Vector3(23f, F, 208.5f), 3.6f);
            Models.RoadRibbon(new List<Vector3> { new Vector3(0f, 0, 208.5f), new Vector3(UpX0 + 0.1f, 0, 208.5f) }, World.BranchRoadWidth, z1, g, 0.025f);
            Models.RoadRibbon(new List<Vector3> { new Vector3(UpX3 - 0.1f, 0, 208.5f), new Vector3(40f, 0, 208.4f) }, World.BranchRoadWidth, z1, g, 0.025f);

            // the pipeline across the camp road: blocks the surface, crosses over the underpass lid
            const float px = 20f;
            var pipeSeg = new MeshBuilder();
            var pipeOver = new MeshBuilder();
            for (float zz = 186f; zz < 232f; zz += 6f)
            {
                bool over = zz + 6f > UpZ0 - 1f && zz < UpZ1 + 1f;
                var pbld = over ? pipeOver : pipeSeg;
                pbld.Material(0.45f, 0.65f);
                pbld.CylinderBetween(new Vector3(px, 1.55f, zz), new Vector3(px, 1.55f, Mathf.Min(zz + 6f, 232f)), 1.0f, 14, H("#8F969C"));
                pbld.Cylinder(new Vector3(px, 1.55f, zz), 1.12f, 0.25f, 14, SteelDark);
                pbld.Matte();
                pbld.Box(new Vector3(px, 0.3f, zz + 3f), new Vector3(2.4f, 0.6f, 0.5f), Concrete, ConcreteTop);
            }
            Emit("Pipeline", pipeSeg, g);
            var overGo = Emit("PipelineOver", pipeOver, g);
            // only for the car in the underpass below it (a car jumping over the pipe keeps it solid)
            OcclusionFader.Register("PipelineOver", overGo, true, 0.24f, null, 0.6f);
            Block(g, "PipelineCol", new Vector3(px - 1.1f, -0.2f, 186f), new Vector3(px + 1.1f, 2.6f, 232f));
        }

        // ------------------------------------------------------------------ salt works canopy (zone 2)
        static void BuildCanopy()
        {
            var g = Group("Canopy");
            var c = canopy;
            const float hw = 7f, hl = 10f, h = 4.8f;
            var b = new MeshBuilder();
            foreach (int s in new[] { -1, 1 })
                for (int e = -1; e <= 1; e++)
                {
                    var p = c + new Vector3(s * hw, 0, e * hl);
                    b.Box(p + Vector3.up * (h * 0.5f), new Vector3(0.4f, h, 0.4f), Steel, SteelDark);
                    BlockO(g, "CanopyPost", p + Vector3.up * (h * 0.5f), new Vector3(0.45f, h, 0.45f), 0f);
                }
            // salt piles + a conveyor beside the road
            var salt = H("#EDEAE2");
            b.Sphere(c + new Vector3(-hw - 3.5f, 0.6f, -4f), new Vector3(2.6f, 1.6f, 2.4f), salt, 1, 0.08f, 3);
            b.Sphere(c + new Vector3(hw + 3.2f, 0.5f, 5f), new Vector3(2.2f, 1.3f, 2.2f), salt, 1, 0.08f, 5);
            b.Material(0.4f, 0.5f);
            b.BevelBox(c + new Vector3(hw + 3f, 1.4f, -2f), new Vector3(1.2f, 0.25f, 9f), Quaternion.Euler(-12f, 0, 0), 0.05f, SteelDark);
            b.Matte();
            Emit("CanopyPosts", b, g);
            b = new MeshBuilder();
            b.Box(c + Vector3.up * (h + 0.12f), new Vector3(hw * 2f + 1.2f, 0.24f, hl * 2f + 1.2f), H("#C9C6BE"), H("#E4E1DA"));
            for (int i = -6; i <= 6; i++) b.Box(c + new Vector3(i * 1.15f, h + 0.27f, 0), new Vector3(0.4f, 0.05f, hl * 2f + 1f), i % 4 == 0 ? RustC : H("#D7D4CC"));
            b.Box(c + new Vector3(0, h + 0.3f, 0), new Vector3(0.3f, 0.06f, hl * 2f + 1.2f), Hazard);
            var roof = Emit("CanopyRoof", b, g);
            OcclusionFader.Register("CanopyRoof", roof, true, 0.2f, new Bounds(c + Vector3.up * (h + 0.2f), new Vector3(hw * 2f + 1.2f, 0.6f, hl * 2f + 1.2f)));
            LampPool(g, c, 4f);
        }

        // ------------------------------------------------------------------ rusted pipe tunnel (zone 3)
        static void BuildPipeTunnel()
        {
            var g = Group("PipeTunnel");
            var c = pipeTunnel;
            const float r = 5.6f, hl = 8f;
            var b = new MeshBuilder();
            b.Push(c, Quaternion.Euler(0f, 90f, 0f));   // tunnel axis along world X (the camp road)
            int segs = 14;
            for (int i = 0; i < segs; i++)
            {
                float a0 = Mathf.PI * i / segs, a1 = Mathf.PI * (i + 1) / segs;
                var d0 = new Vector3(Mathf.Cos(a0), Mathf.Sin(a0), 0f); var d1 = new Vector3(Mathf.Cos(a1), Mathf.Sin(a1), 0f);
                var col = i % 3 == 1 ? RustD : RustC;
                var mid = (d0 + d1).normalized;
                b.PolyOut(col, Vector3.zero, d0 * r + Vector3.forward * -hl, d1 * r + Vector3.forward * -hl, d1 * r + Vector3.forward * hl, d0 * r + Vector3.forward * hl);
                b.PolyOut(Sh(col, 0.7f), mid * (r * 3f), d0 * (r - 0.3f) + Vector3.forward * hl, d1 * (r - 0.3f) + Vector3.forward * hl, d1 * (r - 0.3f) + Vector3.forward * -hl, d0 * (r - 0.3f) + Vector3.forward * -hl);
            }
            foreach (float zz in new[] { -hl, -hl * 0.33f, hl * 0.33f, hl })
                for (int i = 0; i < segs; i++)
                {
                    float a0 = Mathf.PI * i / segs, a1 = Mathf.PI * (i + 1) / segs;
                    var d0 = new Vector3(Mathf.Cos(a0), Mathf.Sin(a0), 0f); var d1 = new Vector3(Mathf.Cos(a1), Mathf.Sin(a1), 0f);
                    b.Push(Vector3.forward * zz);
                    b.PolyOut(SteelDark, Vector3.zero, d0 * (r + 0.18f) + Vector3.forward * -0.25f, d1 * (r + 0.18f) + Vector3.forward * -0.25f, d1 * (r + 0.18f) + Vector3.forward * 0.25f, d0 * (r + 0.18f) + Vector3.forward * 0.25f);
                    b.Pop();
                }
            b.Pop();
            var arch = Emit("PipeArch", b, g);
            OcclusionFader.Register("PipeArch", arch, true, 0.2f, new Bounds(c + Vector3.up * (r * 0.6f), new Vector3(hl * 2f, r * 1.2f, r * 2f)));
            foreach (int s in new[] { -1, 1 })
                Block(g, "PipeSide", c + new Vector3(-hl, -0.5f, s > 0 ? r - 0.3f : -r - 0.2f), c + new Vector3(hl, 3.2f, s > 0 ? r + 0.2f : -r + 0.3f));
            Block(g, "PipeTop", c + new Vector3(-hl, r - 0.6f, -r), c + new Vector3(hl, r + 0.2f, r));
            LampPool(g, c, 3.6f);
            var lb = new MeshBuilder();
            lb.Box(c + new Vector3(0, r - 0.7f, 0), new Vector3(0.7f, 0.2f, 0.7f), Gl("#C8FF8A", 0.3f));
            Emit("PipeLamp", lb, g, false);
        }
    }

    /// <summary>Gentle bob + pulse for the intro's floating guide arrow; it shrinks away as the car arrives, so it
    /// never covers the car at the moment of the jump.</summary>
    public class GuideArrowBob : MonoBehaviour
    {
        public float phase;
        Vector3 basePos, baseScale = Vector3.one;
        float show = 1f;
        void Start() { basePos = transform.position; baseScale = transform.localScale; }
        void Update()
        {
            float t = Time.time + phase;
            var pl = Game.I != null ? Game.I.player : null;
            float want = 1f;
            if (pl != null)
            {
                var d = pl.Pos - basePos; d.y = 0f;
                want = Mathf.Clamp01((d.magnitude - 9f) / 7f);
            }
            show = Mathf.MoveTowards(show, want, Time.deltaTime * 3f);
            transform.position = basePos + Vector3.up * Mathf.Sin(t * 3.2f) * 0.35f + Vector3.forward * Mathf.Sin(t * 3.2f + 1f) * 0.25f;
            transform.rotation = Quaternion.Euler(-22f, 0f, 0f);
            transform.localScale = baseScale * Mathf.Max(0.001f, show * (1f + Mathf.Sin(t * 6.4f) * 0.06f));
        }
    }
}
