using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    public static partial class Models
    {
        static Mesh flatQuad;
        /// <summary>Unit quad on XZ (-1..1) with 0..1 UVs, for decals / glows / telegraphs / blob shadows.</summary>
        public static Mesh FlatQuad()
        {
            if (flatQuad != null) return flatQuad;
            flatQuad = new Mesh { name = "FlatQuad" };
            flatQuad.SetVertices(new List<Vector3> { new Vector3(-1, 0, -1), new Vector3(-1, 0, 1), new Vector3(1, 0, 1), new Vector3(1, 0, -1) });
            flatQuad.SetUVs(0, new List<Vector2> { new Vector2(0, 0), new Vector2(0, 1), new Vector2(1, 1), new Vector2(1, 0) });
            flatQuad.SetNormals(new List<Vector3> { Vector3.up, Vector3.up, Vector3.up, Vector3.up });
            flatQuad.SetColors(new List<Color> { Color.white, Color.white, Color.white, Color.white });
            flatQuad.SetTriangles(new[] { 0, 1, 2, 0, 2, 3 }, 0);
            flatQuad.SetUVs(1, new Vector2[4]);
            flatQuad.RecalculateBounds();
            return flatQuad;
        }

        // ------------------------------------------------------------------ ground
        static float GNoise(float x, float z, int seed)
        {
            return Mathf.PerlinNoise(x * 0.018f + seed * 13.1f, z * 0.018f + seed * 7.7f) * 0.65f
                 + Mathf.PerlinNoise(x * 0.07f + seed * 3.3f, z * 0.07f - seed * 5.1f) * 0.35f;
        }

        public static Color GroundColorAt(float x, float z)
        {
            int zi = Content.ZoneIndexAt(z);
            var zd = Content.Zones[zi];
            float n = GNoise(x, z, zi);
            var c = Color.Lerp(zd.groundAlt, zd.ground, Mathf.SmoothStep(0.25f, 0.75f, n));
            // blend across zone borders
            float local = z - Content.ZoneMinZ(zi);
            if (local < 12f && zi > 0)
            {
                var prev = Content.Zones[zi - 1];
                var pc = Color.Lerp(prev.groundAlt, prev.ground, Mathf.SmoothStep(0.25f, 0.75f, GNoise(x, z, zi - 1)));
                c = Color.Lerp(pc, c, 0.5f + local / 24f);
            }
            float toEnd = Content.ZoneMaxZ(zi) - z;
            if (toEnd < 12f && zi < Content.ZoneCount - 1)
            {
                var next = Content.Zones[zi + 1];
                var nc = Color.Lerp(next.groundAlt, next.ground, Mathf.SmoothStep(0.25f, 0.75f, GNoise(x, z, zi + 1)));
                c = Color.Lerp(nc, c, 0.5f + toEnd / 24f);
            }
            // darker outside the playable width
            float ax = Mathf.Abs(x);
            if (ax > Content.ZoneHalfWidth) c = Color.Lerp(c, c * 0.82f, Mathf.Clamp01((ax - Content.ZoneHalfWidth) / 30f));
            c.a = 1f;
            return c;
        }

        /// <param name="cut">Optional: cells for which it returns true are left out (structures cut into the ground
        /// build their own ground there: lids over tunnels, openings, buildings).</param>
        public static GameObject GroundChunk(float zMin, float zMax, Transform parent, System.Func<float, float, float, float, bool> cut = null)
        {
            const float xMin = -175f, xMax = 175f, cell = 5f;
            int nx = Mathf.CeilToInt((xMax - xMin) / cell), nz = Mathf.CeilToInt((zMax - zMin) / cell);
            var verts = new List<Vector3>((nx + 1) * (nz + 1));
            var cols = new List<Color>(verts.Capacity);
            var norms = new List<Vector3>(verts.Capacity);
            var tris = new List<int>(nx * nz * 6);
            bool lin = QualitySettings.activeColorSpace == ColorSpace.Linear;
            for (int j = 0; j <= nz; j++)
                for (int i = 0; i <= nx; i++)
                {
                    float x = xMin + i * cell, z = Mathf.Min(zMin + j * cell, zMax);
                    verts.Add(new Vector3(x, 0, z));
                    norms.Add(Vector3.up);
                    var c = GroundColorAt(x, z);
                    cols.Add(lin ? c.linear : c);
                }
            for (int j = 0; j < nz; j++)
                for (int i = 0; i < nx; i++)
                {
                    if (cut != null)
                    {
                        float x0 = xMin + i * cell, z0 = Mathf.Min(zMin + j * cell, zMax);
                        float x1 = xMin + (i + 1) * cell, z1 = Mathf.Min(zMin + (j + 1) * cell, zMax);
                        if (cut(x0, z0, x1, z1)) continue;
                    }
                    int a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
                    tris.Add(a); tris.Add(c); tris.Add(b);
                    tris.Add(b); tris.Add(c); tris.Add(d);
                }
            var mesh = new Mesh { name = "Ground" };
            if (verts.Count > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.SetVertices(verts); mesh.SetNormals(norms); mesh.SetColors(cols); mesh.SetTriangles(tris, 0);
            mesh.SetUVs(1, new Vector2[verts.Count]); // explicit "no gloss" material params for the toon shader
            mesh.RecalculateBounds();
            var go = MeshGO("Ground", mesh, Mats.Ground, parent, false);
            return go;
        }

        // ------------------------------------------------------------------ roads
        /// <summary>Direction toward the sun (Game sets the light to Euler(56, 118, 0): from the upper left of the screen).</summary>
        public static readonly Vector3 SunDir = new Vector3(-0.494f, 0.829f, 0.262f).normalized;

        /// <summary>
        /// Relief shading for terrain seen from the high camera: the light's own falloff on gentle slopes is too subtle,
        /// so slopes facing the sun are baked a little lighter and the ones turned away darker (0 on flat ground).
        /// </summary>
        public static float ReliefShade(Vector3 n) => Mathf.Clamp((Vector3.Dot(n, SunDir) - SunDir.y) * 1.9f, -0.32f, 0.22f);

        /// <param name="heightAt">Optional ground height under the road (hills, a mountain road): the ribbon drapes over it,
        /// split across its width and resampled every 1.25 m where the ground is not flat.</param>
        public static GameObject RoadRibbon(List<Vector3> pts, float width, ZoneDef zone, Transform parent, float y = 0.03f, System.Func<float, float, float> heightAt = null)
        {
            if (pts.Count < 2) return null;
            int across = 1;
            if (heightAt != null)
            {
                var dense = new List<Vector3>();
                bool any = false;
                for (int i = 0; i < pts.Count; i++)
                {
                    if (i > 0)
                    {
                        var a = pts[i - 1]; var b = pts[i];
                        float segLen = new Vector2(b.x - a.x, b.z - a.z).magnitude;
                        int n = Mathf.Max(1, Mathf.CeilToInt(segLen / 1.25f));
                        for (int k = 1; k < n; k++) dense.Add(Vector3.Lerp(a, b, k / (float)n));
                    }
                    dense.Add(pts[i]);
                }
                for (int i = 0; i < dense.Count && !any; i++)
                {
                    var q = dense[i];
                    var dq = (i < dense.Count - 1 ? dense[i + 1] : q) - (i > 0 ? dense[i - 1] : q); dq.y = 0f;
                    var rq = dq.sqrMagnitude > 1e-6f ? new Vector3(dq.z, 0f, -dq.x).normalized : Vector3.right;
                    for (int s = -1; s <= 1; s++)
                    {
                        var e = q + rq * (s * width * 0.5f);
                        if (heightAt(e.x, e.z) > 0.005f) { any = true; break; }
                    }
                }
                if (any) { pts = dense; across = 4; }
                else heightAt = null;
            }
            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var cols = new List<Color>(); var norms = new List<Vector3>(); var tris = new List<int>();
            float dist = 0;
            int row = across + 1;
            for (int i = 0; i < pts.Count; i++)
            {
                Vector3 dir;
                if (i == 0) dir = pts[1] - pts[0];
                else if (i == pts.Count - 1) dir = pts[i] - pts[i - 1];
                else dir = (pts[i + 1] - pts[i - 1]);
                dir.y = 0; dir.Normalize();
                var right = new Vector3(dir.z, 0, -dir.x);
                if (i > 0) dist += new Vector2(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z).magnitude;
                var p = new Vector3(pts[i].x, y, pts[i].z);
                float v = dist / (width * 1.6f);
                for (int k = 0; k <= across; k++)
                {
                    float u = k / (float)across;
                    var w = p + right * ((u - 0.5f) * width);
                    var col = Color.white;
                    if (heightAt != null)
                    {
                        w.y = y + heightAt(w.x, w.z);
                        // relief shading over the hills (the same light / shade as the ground around)
                        const float e = 0.4f;
                        var n = new Vector3(heightAt(w.x - e, w.z) - heightAt(w.x + e, w.z), 2f * e, heightAt(w.x, w.z - e) - heightAt(w.x, w.z + e)).normalized;
                        float rs = ReliefShade(n);
                        float f = rs >= 0f ? 1f + rs * 0.55f : 1f + rs * 1.1f;
                        col = new Color(f, f, f, 1f);
                    }
                    verts.Add(w);
                    uvs.Add(new Vector2(u, v));
                    cols.Add(col);
                    norms.Add(Vector3.up);
                }
                if (i > 0)
                {
                    for (int k = 0; k < across; k++)
                    {
                        int a = (i - 1) * row + k, b = a + 1, c = a + row, d = c + 1;
                        tris.Add(a); tris.Add(c); tris.Add(b);
                        tris.Add(b); tris.Add(c); tris.Add(d);
                    }
                }
            }
            var mesh = new Mesh { name = "Road" };
            if (verts.Count > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.SetVertices(verts); mesh.SetUVs(0, uvs); mesh.SetColors(cols); mesh.SetNormals(norms); mesh.SetTriangles(tris, 0);
            if (heightAt != null) mesh.RecalculateNormals();
            mesh.SetUVs(1, new Vector2[verts.Count]); // explicit "no gloss" material params for the toon shader
            mesh.RecalculateBounds();
            return MeshGO("Road", mesh, Mats.Road(zone), parent, false);
        }

        // ------------------------------------------------------------------ cliffs
        public static GameObject CliffWall(Vector3 from, Vector3 to, ZoneDef z, int seed, Transform parent, float thickness = 9f, float height = 7f, float rockRadius = 4.2f)
        {
            var dir = (to - from); float len = dir.magnitude; dir /= len;
            var right = new Vector3(dir.z, 0, -dir.x);
            var b = new MeshBuilder();
            var hulls = new List<Vector3[]>();
            var rnd = new System.Random(seed);
            float R() => (float)rnd.NextDouble();
            var top = Color.Lerp(z.cliff, Color.white, 0.18f);
            float stepD = Mathf.Max(2.5f, rockRadius * 1.75f);
            for (float d = 0; d <= len; d += stepD)
            {
                for (int row = 0; row < 2; row++)
                {
                    var p = from + dir * (d + (row == 1 ? stepD * 0.5f : 0) + (R() - 0.5f) * 2f) + right * ((row - 0.5f) * thickness * 0.6f + (R() - 0.5f) * 2.5f);
                    float h = height * (0.7f + R() * 0.6f) * (row == 0 ? 1f : 0.85f);
                    float r = rockRadius * (1f + R() * 0.6f);
                    var col = R() > 0.5f ? z.cliff : z.cliffDark;
                    b.Push(p, Quaternion.Euler(0, R() * 360f, 0));
                    b.rockHulls = hulls;                  // the big rocks get colliders of their own shape
                    b.Rock(new Vector3(0, h * 0.36f, 0), new Vector3(r, h * 0.62f, r * 0.85f), col, rnd.Next(), top, 0.26f, 2);
                    b.rockHulls = null;
                    if (R() > 0.6f) b.Rock(new Vector3(r * 0.5f, h * 0.9f, 0), new Vector3(r * 0.45f, h * 0.32f, r * 0.4f), col, rnd.Next(), top, 0.3f, 1);
                    b.Pop();
                }
            }
            var go = MeshGO("Cliff", b.Build("Cliff"), Mats.Toon, parent);
            go.layer = Ground.BlockerLayer;   // rock walls block sight and shots, and enemies slide along them
            go.transform.position = Vector3.zero;
            if (height < 4f) go.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            // collision follows the rocks themselves (no invisible wall in front of them), plus a core strip along the
            // middle of the wall - always inside the rocks - that closes the seams between them and keeps a jumping car
            // from crossing a low wall
            RockColliders(go.transform, "CliffRocks", hulls);
            var core = go.AddComponent<BoxCollider>();
            var center = (from + to) * 0.5f;
            core.center = center + Vector3.up * 3f;
            float across = thickness * 0.5f;
            core.size = new Vector3(Mathf.Abs(dir.x) * len + Mathf.Abs(right.x) * across, 8f, Mathf.Abs(dir.z) * len + Mathf.Abs(right.z) * across);
            return go;
        }

        /// <summary>
        /// Convex colliders shaped like the rocks themselves (each rock's hull, recorded by MeshBuilder.rockHulls) on the
        /// blocker layer: they stop the car and the enemies and block sight and shots exactly where a rock is seen.
        /// Rocks that start higher than <paramref name="maxBaseY"/> above the ground are out of everyone's reach and skipped.
        /// The hulls are in the parent's space.
        /// </summary>
        public static GameObject RockColliders(Transform parent, string name, List<Vector3[]> hulls, float maxBaseY = 3.5f)
        {
            long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
            var go = new GameObject(name);
            go.layer = Ground.BlockerLayer;
            go.transform.SetParent(parent, false);
            var faces = MeshBuilder.HullFaces;
            foreach (var h in hulls)
            {
                float lo = float.MaxValue;
                for (int i = 0; i < h.Length; i++) lo = Mathf.Min(lo, h[i].y);
                if (lo > maxBaseY) continue;
                var mesh = new Mesh { name = name + "Hull" };
                mesh.SetVertices(h);
                mesh.SetTriangles(faces, 0);
                var mc = go.AddComponent<MeshCollider>();
                mc.cookingOptions = MeshColliderCookingOptions.CookForFasterSimulation | MeshColliderCookingOptions.EnableMeshCleaning | MeshColliderCookingOptions.WeldColocatedVertices;
                mc.convex = true;
                mc.sharedMesh = mesh;
                RockColliderCount++;
            }
            RockColliderMs += (System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1000.0 / System.Diagnostics.Stopwatch.Frequency;
            return go;
        }

        /// <summary>Rock hull colliders created so far and the time spent cooking them (load stats / tests).</summary>
        public static int RockColliderCount;
        public static double RockColliderMs;

        // ------------------------------------------------------------------ repair station
        public static GameObject RepairStation(Transform parent, out Transform glow)
        {
            var root = new GameObject("RepairStation");
            root.transform.SetParent(parent, false);
            var pad = Cached("repairpad", b =>
            {
                b.Cylinder(Vector3.zero, 4.6f, 0.12f, 20, Hex("#9C9A94"), -1, Hex("#B4B2AA"));
                b.Ring(Vector3.zero, 3.7f, 4.1f, 24, Hex("#E8C23A"), 0.125f);
                b.Box(new Vector3(0, 0.13f, 0), new Vector3(0.7f, 0.01f, 2.6f), Hex("#5BD46A"));
                b.Box(new Vector3(0, 0.13f, 0), new Vector3(2.6f, 0.01f, 0.7f), Hex("#5BD46A"));
                // garage shed behind (north)
                b.Box(new Vector3(0, 1.7f, 6.4f), new Vector3(6.4f, 3.4f, 2.6f), Hex("#8E8678"));
                b.Box(new Vector3(0, 1.45f, 5.08f), new Vector3(3.6f, 2.9f, 0.06f), Hex("#5A6A70"));
                for (int i = 0; i < 6; i++) b.Box(new Vector3(0, 0.3f + i * 0.45f, 5.04f), new Vector3(3.6f, 0.04f, 0.04f), Hex("#46545A"));
                b.Box(new Vector3(0, 3.55f, 6.3f), new Vector3(7.0f, 0.18f, 3.2f), Quaternion.Euler(-6, 0, 0), RustDark, Rust);
                b.Box(new Vector3(0, 4.3f, 5.1f), new Vector3(2.8f, 0.9f, 0.1f), Hex("#2E8A3E"));
                b.Box(new Vector3(0, 4.3f, 5.04f), new Vector3(0.5f, 0.6f, 0.02f), Hex("#FFFFFF"));
                b.Box(new Vector3(0, 4.3f, 5.03f), new Vector3(0.18f, 0.6f, 0.02f), Hex("#2E8A3E"));
                // fuel pumps
                for (int s = -1; s <= 1; s += 2)
                {
                    b.Box(new Vector3(s * 5.6f, 0.9f, 2.2f), new Vector3(0.8f, 1.8f, 0.6f), Hex("#C9412E"), Hex("#E05A40"));
                    b.Box(new Vector3(s * 5.6f, 1.35f, 1.88f), new Vector3(0.5f, 0.4f, 0.04f), Glow("#FFF1C2", 0.5f));
                    b.Cylinder(new Vector3(s * 5.6f, 1.8f, 2.2f), 0.25f, 0.3f, 8, Hex("#F2F2F2"));
                }
                b.Box(new Vector3(-3.8f, 0.4f, 4.8f), new Vector3(0.8f, 0.8f, 0.8f), Wood);
                TireFlat(b, new Vector3(3.6f, 0, 4.6f), 0.45f, 0.26f);
                TireFlat(b, new Vector3(3.6f, 0.27f, 4.6f), 0.45f, 0.26f);
            });
            MeshGO("Pad", pad, Mats.Toon, root.transform);
            var g = MeshGO("Glow", FlatQuad(), Mats.RingAdd, root.transform, false);
            g.transform.localPosition = new Vector3(0, 0.16f, 0);
            g.transform.localScale = new Vector3(4.4f, 1, 4.4f);
            g.GetComponent<MeshRenderer>().sharedMaterial = Mats.NewUnlit("RepairGlow", Tex.RingTex(0.08f), true);
            g.GetComponent<MeshRenderer>().sharedMaterial.SetColor("_BaseColor", new Color(0.35f, 1f, 0.45f, 0.75f));
            glow = g.transform;
            var shed = new GameObject("ShedCollider");
            shed.transform.SetParent(root.transform, false);
            var bc = shed.AddComponent<BoxCollider>();
            bc.center = new Vector3(0, 1.7f, 6.4f);
            bc.size = new Vector3(6.4f, 3.4f, 2.6f);
            return root;
        }

        // ------------------------------------------------------------------ gate
        public static GameObject GateTowers(Transform parent, ZoneDef z, float gapWidth)
        {
            float hw = gapWidth * 0.5f;
            var mesh = Cached("gatetowers_" + z.index + "_" + gapWidth, b =>
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    float x = s * (hw + 2.2f);
                    b.Box(new Vector3(x, 2.6f, 0), new Vector3(3.6f, 5.2f, 3.6f), Shade(z.cliffDark, 0.9f), z.cliff);
                    b.Box(new Vector3(x, 5.5f, 0), new Vector3(4.4f, 0.6f, 4.4f), RustDark, Rust);
                    for (int i = -1; i <= 1; i++) b.Cone(new Vector3(x + i * 1.4f, 5.8f, -1.6f), 0.25f, 1.1f, 4, Chrome);
                    b.Box(new Vector3(x, 3.4f, -1.83f), new Vector3(2.2f, 1.4f, 0.08f), Rust);
                    b.Sphere(new Vector3(x, 3.4f, -1.95f), new Vector3(0.5f, 0.45f, 0.3f), Bone, 1, 0.05f, 3);
                    b.Cylinder(new Vector3(x, 5.8f, 1.2f), 0.06f, 2.6f, 4, WoodDark);
                    b.Box(new Vector3(x + 0.6f, 7.8f, 1.2f), new Vector3(1.2f, 0.8f, 0.04f), ClothRed);
                }
            });
            var go = MeshGO("GateTowers", mesh, Mats.Toon, parent);
            for (int s = -1; s <= 1; s += 2)
            {
                var c = go.AddComponent<BoxCollider>();
                c.center = new Vector3(s * (hw + 2.2f), 2.6f, 0);
                c.size = new Vector3(3.6f, 5.2f, 3.6f);
            }
            return go;
        }

        public static GameObject GateBarrier(Transform parent, float gapWidth)
        {
            var mesh = Cached("gatebarrier_" + gapWidth, b =>
            {
                int n = Mathf.RoundToInt(gapWidth / 1.2f);
                for (int i = 0; i < n; i++)
                {
                    float x = -gapWidth * 0.5f + (i + 0.5f) * gapWidth / n;
                    var c = i % 2 == 0 ? Rust : Hex("#6E7880");
                    b.Box(new Vector3(x, 1.6f, 0), new Vector3(gapWidth / n * 0.95f, 3.2f, 0.5f), c, Shade(c, 1.1f));
                    b.Cone(new Vector3(x, 3.2f, 0), 0.3f, 0.9f, 4, Chrome);
                }
                b.Box(new Vector3(0, 0.9f, -0.3f), new Vector3(gapWidth, 0.25f, 0.2f), MetalDark);
                b.Box(new Vector3(0, 2.4f, -0.3f), new Vector3(gapWidth, 0.25f, 0.2f), MetalDark);
                b.Box(new Vector3(0, 1.6f, -0.33f), new Vector3(1.4f, 1.4f, 0.1f), Hex("#C9412E"));
            });
            var go = MeshGO("GateBarrier", mesh, Mats.Toon, parent);
            var col = go.AddComponent<BoxCollider>();
            col.center = new Vector3(0, 1.6f, 0);
            col.size = new Vector3(gapWidth, 3.2f, 1.2f);
            return go;
        }

        // ------------------------------------------------------------------ arena (tire wall ring)
        public static GameObject ArenaRing(Transform parent, float radius, float gapAngleDeg, ZoneDef z)
        {
            var b = new MeshBuilder();
            int n = Mathf.RoundToInt(2 * Mathf.PI * radius / 1.3f);
            for (int i = 0; i < n; i++)
            {
                float a = i / (float)n * 360f;
                // gaps toward -z (south, angle 270) and +z (north, angle 90) where the road passes
                if (Mathf.Abs(Mathf.DeltaAngle(a, 270f)) < gapAngleDeg * 0.5f || Mathf.Abs(Mathf.DeltaAngle(a, 90f)) < gapAngleDeg * 0.5f) continue;
                var p = new Vector3(Mathf.Cos(a * Mathf.Deg2Rad), 0, Mathf.Sin(a * Mathf.Deg2Rad)) * radius;
                int h = (i % 3 == 0) ? 3 : 2;
                for (int k = 0; k < h; k++) TireFlat(b, p + Vector3.up * k * 0.3f, 0.55f, 0.29f);
                if (i % 6 == 0)
                {
                    b.Cylinder(p, 0.07f, 3.2f, 4, WoodDark);
                    b.Sphere(p + Vector3.up * 3.3f, new Vector3(0.3f, 0.28f, 0.3f), Bone, 0);
                }
            }
            var go = MeshGO("Arena", b.Build("Arena"), Mats.Toon, parent);
            return go;
        }

        // ------------------------------------------------------------------ small decor (non interactive)
        /// <summary>
        /// Quiet ground decor: a few separate, readable shapes (stones, low scrub clumps, bleached bones, broad
        /// stains) instead of dense pebbles and grass speckle. Non-interactive, one mesh per zone.
        /// </summary>
        public static GameObject Decor(ZoneDef z, Rect area, int count, int seed, System.Func<Vector2, bool> allowed, Transform parent)
        {
            var b = new MeshBuilder();
            var rnd = new System.Random(seed);
            float R() => (float)rnd.NextDouble();
            float quality = MeshBuilder.Quality;
            MeshBuilder.Quality = 1f;   // small decor: no extra subdivision (it is one big mesh per zone, shadows included)
            var scrub = z.index == 3 ? Hex("#7E8C55") : (z.index == 2 ? Hex("#C8C3B4") : (z.index == 1 ? Hex("#B98A5E") : Hex("#BFA066")));
            var stone = Color.Lerp(z.cliff, z.ground, 0.35f);
            var stoneTop = Color.Lerp(stone, Color.white, 0.18f);
            for (int i = 0; i < count; i++)
            {
                var p2 = new Vector2(area.xMin + R() * area.width, area.yMin + R() * area.height);
                if (!allowed(p2)) continue;
                var p = new Vector3(p2.x, 0, p2.y);
                float kind = R();
                if (kind < 0.42f)
                {
                    // a separate stone, sometimes with a small companion
                    float s = 0.32f + R() * 0.45f;
                    b.Rock(p, new Vector3(s * 1.25f, s * 0.62f, s), stone, rnd.Next(), stoneTop, 0.16f, 1);
                    if (R() < 0.35f) b.Rock(p + new Vector3(s * 1.3f, 0, s * 0.4f), new Vector3(s * 0.55f, s * 0.32f, s * 0.5f), stone, rnd.Next(), stoneTop, 0.16f, 1);
                }
                else if (kind < 0.72f)
                {
                    // low scrub clump: three soft rounded masses
                    float s = 0.38f + R() * 0.3f;
                    var top = Color.Lerp(scrub, Color.white, 0.12f);
                    b.Sphere(p + new Vector3(0, s * 0.35f, 0), new Vector3(s, s * 0.62f, s * 0.9f), scrub, 1, 0.12f, rnd.Next(), top);
                    b.Sphere(p + new Vector3(s * 0.75f, s * 0.22f, -s * 0.3f), new Vector3(s * 0.6f, s * 0.42f, s * 0.6f), scrub, 1, 0.12f, rnd.Next(), top);
                    b.Sphere(p + new Vector3(-s * 0.6f, s * 0.2f, s * 0.35f), new Vector3(s * 0.5f, s * 0.36f, s * 0.5f), scrub, 1, 0.12f, rnd.Next(), top);
                }
                else if (kind < 0.84f && z.index != 3)
                {
                    // bleached bones: a long bone and a round skull-like knob
                    var dir = new Vector3(Mathf.Cos(R() * 6.28f), 0, Mathf.Sin(R() * 6.28f));
                    b.CylinderBetween(p - dir * 0.45f + Vector3.up * 0.07f, p + dir * 0.45f + Vector3.up * 0.07f, 0.075f, 8, Bone);
                    b.Sphere(p + dir * 0.5f + Vector3.up * 0.08f, Vector3.one * 0.12f, Bone, 1);
                    b.Sphere(p - dir * 0.5f + Vector3.up * 0.08f, Vector3.one * 0.11f, Bone, 1);
                }
                else
                {
                    // broad stain: dark oil in the desert, faintly glowing goo in the marsh
                    var stain = z.index == 3 ? Glow("#8FE05A", 0.7f) : Color.Lerp(z.groundAlt, new Color(0.42f, 0.32f, 0.28f), 0.3f);
                    float r = 0.8f + R() * 0.9f;
                    b.Push(p + Vector3.up * 0.012f, Quaternion.Euler(0, R() * 360f, 0), new Vector3(1f, 1f, 0.7f + R() * 0.3f));
                    b.Disc(Vector3.zero, r, 14, stain);
                    b.Pop();
                }
            }
            MeshBuilder.Quality = quality;
            var go = MeshGO("Decor", b.Build("Decor", false), Mats.ToonFlat, parent, true);
            return go;
        }

        /// <summary>Spiked palisade ring around a raider camp with openings (roadAngle = direction of the camp's road, degrees).</summary>
        public static GameObject Palisade(Vector3 center, float radius, float roadAngleDeg, ZoneDef z, int seed, Transform parent)
        {
            var b = new MeshBuilder();
            var rnd = new System.Random(seed);
            var wood = z.index == 2 ? Hex("#D8CCB4") : (z.index == 3 ? Hex("#5E4A36") : Hex("#9A6232"));
            var woodTop = Shade(wood, 1.15f);
            var go = new GameObject("Palisade");
            go.transform.SetParent(parent, false);
            go.transform.position = center;
            int n = Mathf.RoundToInt(2f * Mathf.PI * radius / 0.62f);
            Vector3? arcStart = null; Vector3 last = Vector3.zero;
            System.Action<Vector3, Vector3> addCollider = (a, c) =>
            {
                var mid = (a + c) * 0.5f; var d = c - a;
                if (d.magnitude < 0.5f) return;
                var bc = new GameObject("Col").AddComponent<BoxCollider>();
                bc.transform.SetParent(go.transform, false);
                bc.transform.localPosition = mid + Vector3.up * 1.1f;
                bc.transform.localRotation = Quaternion.LookRotation(d.normalized, Vector3.up);
                bc.size = new Vector3(0.5f, 2.2f, d.magnitude);
            };
            for (int i = 0; i < n; i++)
            {
                float a = i / (float)n * 360f;
                // compass angle: 0 = +z, 90 = +x
                bool gap = Mathf.Abs(Mathf.DeltaAngle(a, roadAngleDeg)) < 24f || Mathf.Abs(Mathf.DeltaAngle(a, roadAngleDeg + 180f)) < 16f;
                var p = new Vector3(Mathf.Sin(a * Mathf.Deg2Rad), 0, Mathf.Cos(a * Mathf.Deg2Rad)) * radius;
                if (gap)
                {
                    if (arcStart.HasValue) { addCollider(arcStart.Value, last); arcStart = null; }
                    continue;
                }
                float h = 1.8f + (float)rnd.NextDouble() * 0.7f;
                b.Push(p, Quaternion.Euler(((float)rnd.NextDouble() - 0.5f) * 10f, a, ((float)rnd.NextDouble() - 0.5f) * 8f));
                b.Cylinder(Vector3.zero, 0.24f, h, 5, wood, -1, woodTop, false);
                b.Cone(new Vector3(0, h, 0), 0.24f, 0.45f, 5, woodTop);
                b.Pop();
                if (i % 4 == 0) b.Box(p + Vector3.up * 1.1f, new Vector3(0.12f, 0.14f, 2.4f), Quaternion.Euler(0, a + 90f, 0), Shade(wood, 0.75f));
                if (!arcStart.HasValue) arcStart = p;
                last = p;
                if ((p - arcStart.Value).magnitude > 4.5f) { addCollider(arcStart.Value, p); arcStart = p; }
            }
            if (arcStart.HasValue) addCollider(arcStart.Value, last);
            var mesh = b.Build("Palisade");
            var mf = go.AddComponent<MeshFilter>(); mf.sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>(); mr.sharedMaterial = Mats.Toon;
            // mesh was built around the origin: positions are local to the camp center
            return go;
        }

        public static GameObject Billboard(Transform parent, ZoneDef z)
        {
            var mesh = Cached("billboard_" + z.index, b =>
            {
                b.Cylinder(new Vector3(-2.2f, 0, 0), 0.15f, 4.2f, 5, WoodDark);
                b.Cylinder(new Vector3(2.2f, 0, 0), 0.15f, 4.2f, 5, WoodDark);
                b.Box(new Vector3(0, 4.4f, 0), new Vector3(6f, 2.6f, 0.15f), Hex("#D8C9A6"));
                b.Box(new Vector3(0, 4.4f, -0.09f), new Vector3(5.4f, 2.0f, 0.02f), z.cliffDark);
                b.Box(new Vector3(-1.2f, 4.6f, -0.11f), new Vector3(1.6f, 0.4f, 0.02f), Hex("#F2E6C8"));
                b.Box(new Vector3(1.2f, 4.0f, -0.11f), new Vector3(2.2f, 0.3f, 0.02f), Hex("#F2E6C8"));
            });
            return MeshGO("Billboard", mesh, Mats.Toon, parent);
        }
    }
}
