using System.Collections.Generic;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// "rocks": do the car and the enemies stop where a rock is seen? Every visible rock mesh (cliff walls, rock masses,
    /// ridges, the mesa, the plateau skirt) gets a hidden exact copy (non-convex MeshCollider on layer 30, colliding with
    /// nothing); the car's boxes and each enemy's footprint are measured against those copies every frame
    /// (Physics.ComputePenetration): the depth they reach into what the player sees. Also: the gap left in front of the
    /// visible rock when the car is stopped (an invisible wall would show up there) and how much of each rock's surface at
    /// car height is backed by a real collider. Uses only APIs that the previous version of the game has too, so the
    /// same test runs on the old build for a before / after comparison.
    /// </summary>
    public static partial class AutoCapture
    {
        const int VisualLayer = 30, ProbeLayer = 31;
        static readonly string[] RockMeshNames = { "Cliff", "RockMassW", "RockMassE", "Plateau", "Ridge0", "Ridge2", "MesaRock" };

        // (label, start, heading, steer: x/z joystick, seconds) for the car; start null = computed along a wall
        struct CarCase { public string name; public Vector3 start; public float yaw; public Vector2 stick; public float secs; public float speed; }
        struct AiCase { public string name; public Vector3 carStart; public float carYaw; public Vector2 carStick; public Vector3[] enemies; public bool[] foot; public float secs; }

        static readonly List<CarCase> carCases = new List<CarCase>();
        static readonly List<AiCase> aiCases = new List<AiCase>();
        static bool rocksReady;
        static int rocksCase = -1;
        static float rocksCaseT0;
        static float carMaxPen, carMaxGap, carNoseDepth;
        static string carMaxPenOn = "";
        static readonly List<SpawnPoint> testSpawns = new List<SpawnPoint>();
        static readonly Dictionary<Enemy, float> enemyMaxPen = new Dictionary<Enemy, float>();
        static readonly Dictionary<Enemy, Vector3> enemyStart = new Dictionary<Enemy, Vector3>();
        static SphereCollider probe;
        static readonly Collider[] rockBuf = new Collider[32];
        static Vector2 rocksStick;
        static int rocksStartFrameCase = -1;
        static float RocksCaseStart(int i) => 1.5f + i * 10f;

        static Vector2 RocksInput(float t) => rocksStick;

        /// <summary>Hidden exact copies of every visible rock mesh (layer 30, no collisions).</summary>
        static void BuildVisualRockCopies()
        {
            for (int l = 0; l < 32; l++) { Physics.IgnoreLayerCollision(VisualLayer, l, true); Physics.IgnoreLayerCollision(ProbeLayer, l, true); }
            int n = 0;
            foreach (var mr in Object.FindObjectsByType<MeshRenderer>())
            {
                var name = mr.gameObject.name;
                bool rock = System.Array.IndexOf(RockMeshNames, name) >= 0;
                if (!rock) continue;
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var go = new GameObject("VisualCopy_" + name) { layer = VisualLayer };
                go.transform.SetParent(mr.transform, false);
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
                n++;
            }
            var pg = new GameObject("RockProbe") { layer = ProbeLayer };
            probe = pg.AddComponent<SphereCollider>();
            probe.radius = 1f;
            Physics.SyncTransforms();
            Debug.Log($"RoadGame ROCKS visual copies={n}");
        }

        /// <summary>The x of the visible rock face of the wall nearest to a point, measured toward +x or -x at car height.</summary>
        static float RockFaceX(Vector3 from, float dirX)
        {
            float best = float.MaxValue;
            foreach (float y in new[] { 0.5f, 1.0f })
                for (float dz = -2f; dz <= 2f; dz += 1f)
                {
                    var o = new Vector3(from.x, y, from.z + dz);
                    if (Physics.Raycast(o, new Vector3(dirX, 0f, 0f), out var hit, 80f, 1 << VisualLayer, QueryTriggerInteraction.Collide))
                        best = Mathf.Min(best, Mathf.Abs(hit.point.x - from.x));
                }
            return best < float.MaxValue ? from.x + dirX * best : float.NaN;
        }

        static void SetupRocksCases()
        {
            carCases.Clear(); aiCases.Clear();
            // the canyon at the start: face x of both walls at the scouts' fight
            float eastFace = RockFaceX(new Vector3(0f, 0f, -190f), 1f), westFace = RockFaceX(new Vector3(0f, 0f, -170f), -1f);
            Debug.Log($"RoadGame ROCKS canyon faces east={eastFace:0.0} west={westFace:0.0}");
            carCases.Add(new CarCase { name = "car_canyon_east_45", start = new Vector3(0f, 0f, -205f), yaw = 45f, stick = new Vector2(0.71f, 0.71f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_canyon_west_90", start = new Vector3(0f, 0f, -170f), yaw = 270f, stick = new Vector2(-1f, 0f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_canyon_scrape", start = new Vector3(eastFace - 3.2f, 0f, -230f), yaw = 0f, stick = new Vector2(0.25f, 0.95f), secs = 5f, speed = 9f });
            carCases.Add(new CarCase { name = "car_boundary_east", start = new Vector3(80f, 0f, -20f), yaw = 90f, stick = new Vector2(1f, 0f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_boundary_west", start = new Vector3(-80f, 0f, -60f), yaw = 270f, stick = new Vector2(-1f, 0f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_south_wall", start = new Vector3(40f, 0f, -90f), yaw = 180f, stick = new Vector2(0f, -1f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_rocktunnel_side", start = new Vector3(14f, 0f, 186f), yaw = 270f, stick = new Vector2(-1f, 0f), secs = 4f, speed = 10f });
            carCases.Add(new CarCase { name = "car_plateau_skirt", start = new Vector3(84f, 0f, -11f), yaw = 180f, stick = new Vector2(0f, -1f), secs = 4f, speed = 10f });
            if (GameObject.Find("Ridge0") != null)
            {
                carCases.Add(new CarCase { name = "car_ridge0", start = new Vector3(24f, 0f, -70f), yaw = 0f, stick = new Vector2(0f, 1f), secs = 4f, speed = 10f });
                carCases.Add(new CarCase { name = "car_ridge0_pass", start = new Vector3(56f, 0f, -70f), yaw = 0f, stick = new Vector2(0f, 1f), secs = 4f, speed = 9f });
                carCases.Add(new CarCase { name = "car_mesa_face", start = new Vector3(-82f, 0f, 44f), yaw = 0f, stick = new Vector2(0f, 1f), secs = 4f, speed = 10f });
                carCases.Add(new CarCase { name = "car_mesa_s1_side", start = new Vector3(-32f, 0f, 70f), yaw = 270f, stick = new Vector2(-1f, 0f), secs = 4f, speed = 10f });
            }
            // enemies chasing / circling a car that drives along a rock wall: their goals keep landing inside the rock
            float bEast = RockFaceX(new Vector3(80f, 0f, -60f), 1f);
            aiCases.Add(new AiCase
            {
                name = "ai_canyon_wall", carStart = new Vector3(eastFace - 3.5f, 0f, -236f), carYaw = 0f, carStick = new Vector2(0.06f, 0.42f), secs = 9.5f,
                enemies = new[] { new Vector3(eastFace - 3f, 0f, -212f), new Vector3(eastFace - 8f, 0f, -200f), new Vector3(eastFace - 2f, 0f, -222f), new Vector3(eastFace - 6f, 0f, -216f) },
                foot = new[] { false, false, true, true }
            });
            aiCases.Add(new AiCase
            {
                name = "ai_boundary_wall", carStart = new Vector3(bEast - 3.5f, 0f, -70f), carYaw = 0f, carStick = new Vector2(0.06f, 0.42f), secs = 9.5f,
                enemies = new[] { new Vector3(bEast - 3f, 0f, -46f), new Vector3(bEast - 8f, 0f, -36f), new Vector3(bEast - 2f, 0f, -56f), new Vector3(bEast - 6f, 0f, -50f) },
                foot = new[] { false, false, true, true }
            });
            aiCases.Add(new AiCase
            {
                name = "ai_rock_tunnel", carStart = new Vector3(-14.8f, 0f, 166f), carYaw = 0f, carStick = new Vector2(0f, 0.42f), secs = 9.5f,
                enemies = new[] { new Vector3(-12f, 0f, 200f), new Vector3(-18f, 0f, 205f), new Vector3(-10f, 0f, 194f), new Vector3(-19f, 0f, 196f) },
                foot = new[] { false, false, true, true }
            });
            aiCases.Add(new AiCase
            {
                name = "ai_behind_plateau", carStart = new Vector3(81f, 0f, -14f), carYaw = 180f, carStick = Vector2.zero, secs = 9.5f,
                enemies = new[] { new Vector3(81f, 0f, -52f), new Vector3(77f, 0f, -50f), new Vector3(84f, 0f, -48f) },
                foot = new[] { false, true, true }
            });
            if (GameObject.Find("Ridge0") != null)
                aiCases.Add(new AiCase
                {
                    name = "ai_ridge_pass", carStart = new Vector3(48f, 0f, -44f), carYaw = 180f, carStick = Vector2.zero, secs = 9.5f,
                    enemies = new[] { new Vector3(56f, 0f, -68f), new Vector3(44f, 0f, -66f), new Vector3(30f, 0f, -64f), new Vector3(60f, 0f, -64f) },
                    foot = new[] { false, false, true, true }
                });
        }

        static SpawnSpec TestEnemy(bool foot) => foot
            ? new SpawnSpec { model = ModelId.Raider, kind = TargetKind.Foot, name = "Test Raider", count = 1, hp = 1e7, reward = Reward.HP(0), respawn = 1e9f, oneTime = true, damage = 0.01, attackInterval = 3f, attackRange = 1.6f, speed = 4.5f, aggro = 70f, radius = 0.55f, height = 2.55f, placement = Placement.Road }
            : new SpawnSpec { model = ModelId.Buggy, kind = TargetKind.Vehicle, name = "Test Buggy", count = 1, hp = 1e7, reward = Reward.HP(0), respawn = 1e9f, oneTime = true, damage = 0.01, attackInterval = 2.2f, attackRange = 8.5f, speed = 7.5f, aggro = 70f, ranged = true, proj = ProjKind.Bullet, burst = 2, windupTime = 0.45f, radius = 1.5f, height = 2.4f, placement = Placement.Road, pace = true };

        static void RocksTick(Player pl)
        {
            if (!rocksReady) { rocksReady = true; BuildVisualRockCopies(); SetupRocksCases(); CoverageReport(); }
            float t = Game.I.SessionTime;
            int total = carCases.Count + aiCases.Count;
            int want = t < RocksCaseStart(0) ? -1 : Mathf.Min(total, (int)((t - RocksCaseStart(0)) / 10f));
            if (want != rocksCase)
            {
                EndRocksCase(pl);
                rocksCase = want;
                if (rocksCase >= 0 && rocksCase < total) StartRocksCase(pl, rocksCase);
                else rocksStick = Vector2.zero;
            }
            if (rocksCase < 0 || rocksCase >= total) return;
            float local = t - RocksCaseStart(rocksCase);
            bool isCar = rocksCase < carCases.Count;
            float secs = isCar ? carCases[rocksCase].secs : aiCases[rocksCase - carCases.Count].secs;
            if (local > secs) rocksStick = Vector2.zero;
            // the car's two boxes against the visible rocks
            foreach (var bc in pl.GetComponents<BoxCollider>())
            {
                var center = bc.transform.TransformPoint(bc.center);
                var half = Vector3.Scale(bc.size * 0.5f, bc.transform.lossyScale);
                int n = Physics.OverlapBoxNonAlloc(center, half + Vector3.one * 0.05f, rockBuf, bc.transform.rotation, 1 << VisualLayer, QueryTriggerInteraction.Collide);
                for (int i = 0; i < n; i++)
                {
                    var c = rockBuf[i];
                    if (Physics.ComputePenetration(bc, bc.transform.position, bc.transform.rotation, c, c.transform.position, c.transform.rotation, out _, out float dist) && dist > carMaxPen)
                    {
                        carMaxPen = dist;
                        carMaxPenOn = c.transform.parent != null ? c.transform.parent.name : c.name;
                    }
                }
            }
            if (isCar && local > 2.5f && local < secs)
            {
                // pressed against something: the free gap ahead to the visible rock (an invisible wall would leave one)
                var fwd = pl.transform.forward;
                float gap = float.MaxValue;
                for (int k = -2; k <= 2; k++)
                {
                    var o = pl.Pos + pl.transform.right * (k * 0.45f) + Vector3.up * 0.7f + fwd * 2.3f;
                    if (Physics.Raycast(o, fwd, out var hit, 3f, 1 << VisualLayer, QueryTriggerInteraction.Collide)) gap = Mathf.Min(gap, hit.distance);
                }
                if (pl.Speed < 0.6f && gap < float.MaxValue) carMaxGap = Mathf.Max(carMaxGap, gap);
                // how far the nose went into the rock along its path: rays from 6 m behind the front face to it
                for (int k = -2; k <= 2; k++)
                    foreach (float h in new[] { 0.45f, 0.95f })
                    {
                        var front = pl.Pos + pl.transform.right * (k * 0.5f) + Vector3.up * h + fwd * 2.37f;
                        if (Physics.Raycast(front - fwd * 6f, fwd, out var hit, 6f, 1 << VisualLayer, QueryTriggerInteraction.Collide))
                            carNoseDepth = Mathf.Max(carNoseDepth, 6f - hit.distance);
                    }
            }
            // each enemy's footprint against the visible rocks
            foreach (var sp in testSpawns)
            {
                if (!(sp.target is Enemy e) || !e.gameObject.activeInHierarchy) continue;
                float r = sp.spec.kind == TargetKind.Vehicle ? Mathf.Max(0.9f, sp.spec.radius * 0.72f) : Mathf.Max(0.32f, sp.spec.radius * 0.75f);
                probe.radius = r;
                var pc = e.Pos + Vector3.up * (0.3f + Mathf.Min(r, 1.1f));
                int n = Physics.OverlapSphereNonAlloc(pc, r, rockBuf, 1 << VisualLayer, QueryTriggerInteraction.Collide);
                float worst = 0f;
                for (int i = 0; i < n; i++)
                {
                    var c = rockBuf[i];
                    if (Physics.ComputePenetration(probe, pc, Quaternion.identity, c, c.transform.position, c.transform.rotation, out _, out float dist)) worst = Mathf.Max(worst, dist);
                }
                if (!enemyMaxPen.TryGetValue(e, out float was) || worst > was) enemyMaxPen[e] = worst;
            }
        }

        static void StartRocksCase(Player pl, int i)
        {
            carMaxPen = 0f; carMaxGap = 0f; carMaxPenOn = ""; carNoseDepth = 0f;
            if (i < carCases.Count)
            {
                var c = carCases[i];
                pl.Teleport(c.start, c.yaw);
                pl.SetSpeed(c.speed);
                rocksStick = c.stick;
                Debug.Log($"RoadGame ROCKS start {c.name} at={c.start} yaw={c.yaw}");
            }
            else
            {
                var c = aiCases[i - carCases.Count];
                pl.Teleport(c.carStart, c.carYaw);
                rocksStick = c.carStick;
                enemyMaxPen.Clear(); enemyStart.Clear();
                for (int k = 0; k < c.enemies.Length; k++)
                {
                    var sp = World.I.AddIntroSpawn(97000 + i * 10 + k, TestEnemy(c.foot[k]), c.enemies[k], 180f);
                    testSpawns.Add(sp);
                }
                World.I.Tick();
                foreach (var sp in testSpawns) if (sp.target != null) enemyStart[(Enemy)sp.target] = sp.target.Pos;
                Debug.Log($"RoadGame ROCKS start {c.name} car={c.carStart} enemies={c.enemies.Length}");
            }
            Game.I.cameraRig.Snap();
        }

        static void EndRocksCase(Player pl)
        {
            if (rocksCase < 0 || rocksCase >= carCases.Count + aiCases.Count) return;
            if (rocksCase < carCases.Count)
            {
                var c = carCases[rocksCase];
                var moved = pl.Pos - c.start; moved.y = 0f;
                Debug.Log($"RoadGame ROCKS car {c.name} maxPenetration={carMaxPen:0.00}m noseDepth={carNoseDepth:0.00}m on={carMaxPenOn} gapWhenStopped={(carMaxGap > 0f ? carMaxGap.ToString("0.00") : "-")}m moved={moved.magnitude:0.0}m end={pl.Pos}");
            }
            else
            {
                var c = aiCases[rocksCase - carCases.Count];
                Debug.Log($"RoadGame ROCKS ai {c.name} carMaxPenetration={carMaxPen:0.00}m");
                foreach (var sp in testSpawns)
                {
                    if (!(sp.target is Enemy e)) continue;
                    enemyMaxPen.TryGetValue(e, out float pen);
                    enemyStart.TryGetValue(e, out var st);
                    var to = pl.Pos - e.Pos; to.y = 0f;
                    var mv = e.Pos - st; mv.y = 0f;
                    Debug.Log($"RoadGame ROCKS ai {c.name} enemy={sp.spec.name} maxPenetration={pen:0.00}m moved={mv.magnitude:0.0}m toCar={to.magnitude:0.0}m end={e.Pos}");
                    sp.save = Game.I.progress.GetOrCreateSpawn(sp.id);
                    sp.save.respawnAt = Progress.NowMs + 1000L * 3600 * 24 * 365;
                    e.gameObject.SetActive(false);
                    World.I.OnTargetGone(e);
                }
                testSpawns.Clear();
            }
        }

        // ------------------------------------------------------------------ rocksview: the collision shapes drawn over the rocks
        /// <summary>(car position, heading, zoom, face): each viewpoint is shot twice, as it is and with the colliders over it.
        /// face +1 / -1: the car stands 4.5 m in front of the visible rock face to the east / west (found at the run's start).</summary>
        static readonly (Vector3 p, float yaw, float zoom, string name, int face)[] RockViews =
        {
            (new Vector3(0f, 0f, -196f), 0f, 0.62f, "canyon_east_wall", 1),
            (new Vector3(0f, 0f, -176f), 0f, 0.62f, "canyon_west_wall", -1),
            (new Vector3(80f, 0f, -60f), 0f, 0.62f, "boundary_east_wall", 1),
            (new Vector3(-6f, 0f, 176f), 0f, 0.62f, "rock_tunnel", 0),
            (new Vector3(84f, 0f, -16f), 0f, 0.62f, "plateau_skirt", 0),
            (new Vector3(52f, 0f, -62f), 0f, 0.62f, "ridge0_pass", 0),
            (new Vector3(-46f, 0f, 46f), 0f, 0.8f, "mesa_foot", 0),
        };
        public const float RockViewStep = 2.2f;
        static int rockViewIndex = -1;
        static readonly List<GameObject> overlay = new List<GameObject>();
        static Material overlayMat;

        /// <summary>Shot times for rocksview: per viewpoint one plain shot and one with the colliders drawn.</summary>
        public static float[] RockViewTimes()
        {
            var t = new float[RockViews.Length * 2];
            for (int i = 0; i < RockViews.Length; i++) { t[i * 2] = 2.5f + i * RockViewStep * 2f + 1.2f; t[i * 2 + 1] = t[i * 2] + RockViewStep; }
            return t;
        }

        static void RockViewTick(Player pl, double t)
        {
            int slot = (int)((t - 2.5) / RockViewStep);
            int view = slot / 2;
            if (slot < 0 || view >= RockViews.Length) return;
            if (!rocksReady) { rocksReady = true; BuildVisualRockCopies(); }
            if (view != rockViewIndex)
            {
                rockViewIndex = view;
                ClearOverlay();
                var v = RockViews[view];
                if (v.name.StartsWith("ridge") || v.name.StartsWith("mesa"))
                    if (GameObject.Find(v.name.StartsWith("ridge") ? "Ridge0" : "LookoutMesa") == null) { Debug.Log("RoadGame ROCKVIEW " + v.name + " not in this version"); return; }
                var at = v.p;
                if (v.face != 0)
                {
                    float fx = RockFaceX(at, v.face);
                    if (!float.IsNaN(fx)) at.x = fx - v.face * 4.5f;
                }
                pl.Teleport(at, v.yaw);
                Game.I.cameraRig.zoom = v.zoom;
                Game.I.cameraRig.Snap();
                Debug.Log($"RoadGame ROCKVIEW {view} {v.name} at {at}");
            }
            if (slot % 2 == 1 && overlay.Count == 0) DrawColliders(pl.Pos, 34f);
        }

        static void ClearOverlay()
        {
            foreach (var go in overlay) if (go != null) Object.DestroyImmediate(go);
            overlay.Clear();
        }

        /// <summary>Every collider that stops cars near a point, drawn as a translucent green shape (boxes as boxes, hulls as hulls).</summary>
        static void DrawColliders(Vector3 at, float radius)
        {
            if (overlayMat == null)
            {
                overlayMat = Mats.NewUnlit("ColliderOverlay", null, false);
                overlayMat.SetColor("_BaseColor", new Color(0.1f, 1f, 0.35f, 0.42f));
                overlayMat.renderQueue = 3500;
            }
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var cubeMesh = cube.GetComponent<MeshFilter>().sharedMesh;
            Object.DestroyImmediate(cube);
            int n = 0;
            foreach (var c in Physics.OverlapSphere(at, radius, (1 << 0) | Ground.BlockerMask, QueryTriggerInteraction.Ignore))
            {
                if (c.attachedRigidbody != null) continue;
                Mesh mesh = null; Matrix4x4 m;
                if (c is BoxCollider bc) { mesh = cubeMesh; m = c.transform.localToWorldMatrix * Matrix4x4.TRS(bc.center, Quaternion.identity, bc.size); }
                else if (c is MeshCollider mc && mc.sharedMesh != null) { mesh = mc.sharedMesh; m = c.transform.localToWorldMatrix; }
                else continue;
                var go = new GameObject("ColliderView");
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = overlayMat;
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                go.transform.position = m.GetColumn(3);
                go.transform.rotation = m.rotation;
                go.transform.localScale = m.lossyScale;
                overlay.Add(go);
                n++;
            }
            Debug.Log($"RoadGame ROCKVIEW colliders drawn={n}");
        }

        /// <summary>How much of each visible rock's surface at car height (0.3..1.3 m) is backed by a collider that stops cars.</summary>
        static void CoverageReport()
        {
            int mask = (1 << 0) | Ground.BlockerMask;
            var tally = new Dictionary<string, (int pts, int solid)>();
            foreach (var mr in Object.FindObjectsByType<MeshRenderer>())
            {
                var name = mr.gameObject.name;
                if (System.Array.IndexOf(RockMeshNames, name) < 0) continue;
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mesh = mf.sharedMesh;
                var v = mesh.vertices; var nrm = mesh.normals;
                var m = mr.transform.localToWorldMatrix;
                tally.TryGetValue(name, out var tl);
                for (int i = 0; i < v.Length; i += 3)
                {
                    var p = m.MultiplyPoint3x4(v[i]);
                    float floor = Ground.Sample(p.x, p.z, p.y).valid ? Ground.Sample(p.x, p.z, p.y).h : 0f;
                    if (p.y - floor < 0.3f || p.y - floor > 1.3f) continue;
                    var n = m.MultiplyVector(nrm[i]).normalized;
                    if (n.y > 0.7f || n.y < -0.7f) continue;            // tops and undersides: not where a car meets the rock
                    tl.pts++;
                    // 15 cm inside the visible surface: is there something solid?
                    if (Physics.CheckSphere(p - n * 0.15f, 0.05f, mask, QueryTriggerInteraction.Ignore)) tl.solid++;
                }
                tally[name] = tl;
            }
            foreach (var kv in tally)
                Debug.Log($"RoadGame ROCKS coverage {kv.Key}: {kv.Value.solid}/{kv.Value.pts} = {(kv.Value.pts > 0 ? 100f * kv.Value.solid / kv.Value.pts : 0f):0.0}% of the surface at car height is solid");
        }
    }
}
