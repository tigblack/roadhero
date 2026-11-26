using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// Procedural mesh builder. Geometry is written as flat polygons with vertex colors (sRGB in, converted to linear);
    /// Build() then applies "weighted auto-smooth" normals: faces meeting at less than <see cref="smoothAngle"/> are
    /// shaded smoothly (curved surfaces look round), sharper edges stay crisp, and large faces dominate small bevels
    /// (like Blender's Weighted Normal modifier) so chamfered boxes keep flat faces with soft highlighted edges.
    /// Per-vertex material params go to UV1: x = gloss (0..1), y = metal (0..1).
    /// Vertex color alpha &lt; 1 marks emissive (glowing) parts for the toon shader.
    /// </summary>
    public class MeshBuilder
    {
        readonly List<Vector3> verts = new List<Vector3>(1024);
        readonly List<Vector3> norms = new List<Vector3>(1024);
        readonly List<Color> cols = new List<Color>(1024);
        readonly List<Vector2> uvs = new List<Vector2>(1024);
        readonly List<Vector2> mats = new List<Vector2>(1024);
        readonly List<float> weights = new List<float>(1024);
        readonly List<float> smoothCos = new List<float>(1024);
        readonly List<int> tris = new List<int>(2048);
        readonly Stack<Matrix4x4> stack = new Stack<Matrix4x4>();
        Matrix4x4 m = Matrix4x4.identity;

        /// <summary>Current surface gloss (0 = matte, 1 = mirror-like clear coat). Applies to polygons added afterwards.</summary>
        public float gloss;
        /// <summary>Current metalness (reflections tinted by the albedo, e.g. chrome / brass).</summary>
        public float metal;
        /// <summary>Faces meeting below this angle are shaded smoothly (0 = flat shading everywhere).</summary>
        public float smoothAngle = 50f;
        /// <summary>Multiplies the segment count of round primitives (cylinders &gt;= 6 sides, spheres).</summary>
        public static float Quality = 2f;
        /// <summary>Boxes bigger than ~8 cm get small chamfers (soft highlighted edges instead of razor-sharp ones).</summary>
        public static bool AutoBevel = true;

        public int VertexCount => verts.Count;

        /// <summary>
        /// When set, every <see cref="Rock"/> also records its collision hull here: the first 42 points of its sphere
        /// (the 80-face level), pushed out 6% to cover the faceting and the finer bumps in between, in the builder's output space.
        /// </summary>
        public List<Vector3[]> rockHulls;

        /// <summary>Triangles of the 42-point icosphere (indices into a recorded rock hull).</summary>
        public static List<int> HullFaces => Ico(1).Item2;

        public void Push(Vector3 pos, Quaternion rot, Vector3 scale)
        {
            stack.Push(m);
            m = m * Matrix4x4.TRS(pos, rot, scale);
        }
        public void Push(Vector3 pos, Quaternion rot) => Push(pos, rot, Vector3.one);
        public void Push(Vector3 pos) => Push(pos, Quaternion.identity, Vector3.one);
        public void Pop() { if (stack.Count > 0) m = stack.Pop(); }

        public void Material(float gloss, float metal = 0f) { this.gloss = gloss; this.metal = metal; }
        public void Matte() { gloss = 0f; metal = 0f; }

        static Color Lin(Color c)
        {
            if (QualitySettings.activeColorSpace == ColorSpace.Linear)
            {
                var l = c.linear;
                l.a = c.a;
                return l;
            }
            return c;
        }

        /// <summary>Round primitives get more segments (smooth silhouettes); 3..5-sided shapes stay faceted on purpose.</summary>
        public static int Segs(int segs)
        {
            if (segs < 6) return segs;
            return Mathf.Clamp(Mathf.RoundToInt(segs * Quality), 12, 64);
        }

        /// <summary>Adds a flat polygon (convex, clockwise seen from the front) with a single color.</summary>
        public void Poly(Color col, params Vector3[] p)
        {
            if (p.Length < 3) return;
            var a = m.MultiplyPoint3x4(p[0]);
            var b = m.MultiplyPoint3x4(p[1]);
            var c = m.MultiplyPoint3x4(p[2]);
            var n = Vector3.Cross(b - a, c - a);
            if (n.sqrMagnitude < 1e-12f)
            {
                // try another triple for degenerate first triangle
                for (int k = 3; k < p.Length && n.sqrMagnitude < 1e-12f; k++)
                    n = Vector3.Cross(b - a, m.MultiplyPoint3x4(p[k]) - a);
            }
            // polygon area (for weighted normals)
            float area = 0f;
            for (int i = 1; i < p.Length - 1; i++)
                area += Vector3.Cross(m.MultiplyPoint3x4(p[i]) - a, m.MultiplyPoint3x4(p[i + 1]) - a).magnitude * 0.5f;
            n = n.normalized;
            var lc = Lin(col);
            var mp = new Vector2(gloss, metal);
            float sc = smoothAngle > 0.1f ? Mathf.Cos(smoothAngle * Mathf.Deg2Rad) : 2f;
            int start = verts.Count;
            for (int i = 0; i < p.Length; i++)
            {
                var w = m.MultiplyPoint3x4(p[i]);
                verts.Add(w);
                norms.Add(n);
                cols.Add(lc);
                uvs.Add(new Vector2(w.x, w.z));
                mats.Add(mp);
                weights.Add(Mathf.Max(area, 1e-6f));
                smoothCos.Add(sc);
            }
            for (int i = 1; i < p.Length - 1; i++)
            {
                tris.Add(start); tris.Add(start + i); tris.Add(start + i + 1);
            }
        }

        /// <summary>Polygon whose winding is fixed so that its normal points away from <paramref name="inside"/> (in local space).</summary>
        public void PolyOut(Color col, Vector3 inside, params Vector3[] p)
        {
            if (p.Length < 3) return;
            var n = Vector3.zero;
            for (int i = 1; i < p.Length - 1; i++) n += Vector3.Cross(p[i] - p[0], p[i + 1] - p[0]);
            var center = Vector3.zero;
            foreach (var q in p) center += q;
            center /= p.Length;
            if (Vector3.Dot(n, center - inside) < 0) System.Array.Reverse(p);
            Poly(col, p);
        }

        public void Tri(Color col, Vector3 a, Vector3 b, Vector3 c) => Poly(col, a, b, c);
        public void Quad(Color col, Vector3 a, Vector3 b, Vector3 c, Vector3 d) => Poly(col, a, b, c, d);

        /// <summary>Axis aligned box (in current transform space). Chamfered automatically when large enough.</summary>
        public void Box(Vector3 center, Vector3 size, Color col, Color? top = null)
        {
            float minDim = Mathf.Min(Mathf.Abs(size.x), Mathf.Min(Mathf.Abs(size.y), Mathf.Abs(size.z)));
            if (AutoBevel && minDim >= 0.08f) { BevelBox(center, size, Mathf.Min(0.035f, minDim * 0.1f), col, top); return; }
            SharpBox(center, size, col, top);
        }

        /// <summary>Plain 6-quad box.</summary>
        public void SharpBox(Vector3 center, Vector3 size, Color col, Color? top = null)
        {
            var h = size * 0.5f;
            var c = center;
            Vector3 p000 = c + new Vector3(-h.x, -h.y, -h.z), p100 = c + new Vector3(h.x, -h.y, -h.z);
            Vector3 p010 = c + new Vector3(-h.x, h.y, -h.z), p110 = c + new Vector3(h.x, h.y, -h.z);
            Vector3 p001 = c + new Vector3(-h.x, -h.y, h.z), p101 = c + new Vector3(h.x, -h.y, h.z);
            Vector3 p011 = c + new Vector3(-h.x, h.y, h.z), p111 = c + new Vector3(h.x, h.y, h.z);
            var tc = top ?? col;
            Quad(col, p000, p010, p110, p100); // -z
            Quad(col, p101, p111, p011, p001); // +z
            Quad(col, p001, p011, p010, p000); // -x
            Quad(col, p100, p110, p111, p101); // +x
            Quad(tc, p010, p011, p111, p110);  // +y
            Quad(col, p000, p100, p101, p001); // -y
        }

        public void Box(Vector3 center, Vector3 size, Quaternion rot, Color col, Color? top = null)
        {
            Push(center, rot);
            Box(Vector3.zero, size, col, top);
            Pop();
        }

        /// <summary>
        /// Box with chamfered edges and corners. With weighted auto-smooth normals the chamfers read as soft rounded
        /// edges catching the light, while the faces stay flat (the classic "hard-surface" look).
        /// </summary>
        public void BevelBox(Vector3 center, Vector3 size, float bevel, Color col, Color? top = null)
        {
            var h = size * 0.5f;
            float bv = Mathf.Min(bevel, Mathf.Min(h.x, Mathf.Min(h.y, h.z)) * 0.45f);
            if (bv <= 0.002f) { SharpBox(center, size, col, top); return; }
            var tc = top ?? col;
            float ix = h.x - bv, iy = h.y - bv, iz = h.z - bv;
            Vector3 P(float x, float y, float z) => center + new Vector3(x, y, z);
            // faces
            Quad(col, P(-ix, -iy, -h.z), P(-ix, iy, -h.z), P(ix, iy, -h.z), P(ix, -iy, -h.z));     // -z
            Quad(col, P(ix, -iy, h.z), P(ix, iy, h.z), P(-ix, iy, h.z), P(-ix, -iy, h.z));         // +z
            Quad(col, P(-h.x, -iy, iz), P(-h.x, iy, iz), P(-h.x, iy, -iz), P(-h.x, -iy, -iz));     // -x
            Quad(col, P(h.x, -iy, -iz), P(h.x, iy, -iz), P(h.x, iy, iz), P(h.x, -iy, iz));         // +x
            Quad(tc, P(-ix, h.y, -iz), P(-ix, h.y, iz), P(ix, h.y, iz), P(ix, h.y, -iz));          // +y
            Quad(col, P(-ix, -h.y, -iz), P(ix, -h.y, -iz), P(ix, -h.y, iz), P(-ix, -h.y, iz));     // -y
            // edges (12)
            var inside = center;
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sz = -1; sz <= 1; sz += 2) // vertical edges
                    PolyOut(col, inside, P(sx * ix, -iy, sz * h.z), P(sx * h.x, -iy, sz * iz), P(sx * h.x, iy, sz * iz), P(sx * ix, iy, sz * h.z));
            for (int sy = -1; sy <= 1; sy += 2)
            {
                var ec = sy > 0 ? tc : col;
                for (int sz = -1; sz <= 1; sz += 2) // edges along x
                    PolyOut(ec, inside, P(-ix, sy * iy, sz * h.z), P(ix, sy * iy, sz * h.z), P(ix, sy * h.y, sz * iz), P(-ix, sy * h.y, sz * iz));
                for (int sx = -1; sx <= 1; sx += 2) // edges along z
                    PolyOut(ec, inside, P(sx * h.x, sy * iy, -iz), P(sx * h.x, sy * iy, iz), P(sx * ix, sy * h.y, iz), P(sx * ix, sy * h.y, -iz));
            }
            // corners (8)
            for (int sx = -1; sx <= 1; sx += 2)
                for (int sy = -1; sy <= 1; sy += 2)
                    for (int sz = -1; sz <= 1; sz += 2)
                        PolyOut(sy > 0 ? tc : col, inside, P(sx * h.x, sy * iy, sz * iz), P(sx * ix, sy * h.y, sz * iz), P(sx * ix, sy * iy, sz * h.z));
        }

        public void BevelBox(Vector3 center, Vector3 size, Quaternion rot, float bevel, Color col, Color? top = null)
        {
            Push(center, rot);
            BevelBox(Vector3.zero, size, bevel, col, top);
            Pop();
        }

        /// <summary>Box whose top face is scaled (tapered), bottom at y=0 relative to center bottom.</summary>
        public void Tapered(Vector3 bottomCenter, Vector2 bottomSize, Vector2 topSize, float height, Color col, Color? top = null, Vector2 topOffset = default)
        {
            var b = bottomCenter;
            float bx = bottomSize.x * 0.5f, bz = bottomSize.y * 0.5f, tx = topSize.x * 0.5f, tz = topSize.y * 0.5f;
            var to = new Vector3(topOffset.x, height, topOffset.y);
            Vector3 b0 = b + new Vector3(-bx, 0, -bz), b1 = b + new Vector3(bx, 0, -bz), b2 = b + new Vector3(bx, 0, bz), b3 = b + new Vector3(-bx, 0, bz);
            Vector3 t0 = b + to + new Vector3(-tx, 0, -tz), t1 = b + to + new Vector3(tx, 0, -tz), t2 = b + to + new Vector3(tx, 0, tz), t3 = b + to + new Vector3(-tx, 0, tz);
            Quad(col, b0, t0, t1, b1);
            Quad(col, b1, t1, t2, b2);
            Quad(col, b2, t2, t3, b3);
            Quad(col, b3, t3, t0, b0);
            Quad(top ?? col, t0, t3, t2, t1);
            Quad(col, b0, b1, b2, b3);
        }

        /// <summary>Cylinder along local Y from base center, optional different top radius (cone frustum).</summary>
        public void Cylinder(Vector3 baseCenter, float radius, float height, int segs, Color col, float topRadius = -1f, Color? capCol = null, bool caps = true)
        {
            if (topRadius < 0) topRadius = radius;
            segs = Segs(Mathf.Max(3, segs));
            var cap = capCol ?? col;
            var top = baseCenter + Vector3.up * height;
            for (int i = 0; i < segs; i++)
            {
                float a0 = (i / (float)segs) * Mathf.PI * 2f, a1 = ((i + 1) / (float)segs) * Mathf.PI * 2f;
                var d0 = new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0));
                var d1 = new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1));
                Quad(col, baseCenter + d0 * radius, top + d0 * topRadius, top + d1 * topRadius, baseCenter + d1 * radius);
                if (caps)
                {
                    if (topRadius > 0.001f) Tri(cap, top, top + d1 * topRadius, top + d0 * topRadius);
                    if (radius > 0.001f) Tri(cap, baseCenter, baseCenter + d0 * radius, baseCenter + d1 * radius);
                }
            }
        }

        /// <summary>Cylinder between two points.</summary>
        public void CylinderBetween(Vector3 a, Vector3 b, float radius, int segs, Color col, float radiusB = -1f, Color? capCol = null)
        {
            var dir = b - a;
            float len = dir.magnitude;
            if (len < 1e-4f) return;
            var rot = Quaternion.FromToRotation(Vector3.up, dir / len);
            Push(a, rot);
            Cylinder(Vector3.zero, radius, len, segs, col, radiusB, capCol);
            Pop();
        }

        public void Cone(Vector3 baseCenter, float radius, float height, int segs, Color col, Color? capCol = null)
            => Cylinder(baseCenter, radius, height, segs, col, 0f, capCol);

        /// <summary>
        /// Surface of revolution around local +Y. profile = (radius, height) points from bottom to top.
        /// colors (optional) = one color per profile segment. A zero radius at an end closes the shape.
        /// </summary>
        public void Lathe(Vector2[] profile, int segs, Color col, Color[] colors = null, float startAngle = 0f, float sweepDeg = 360f)
        {
            bool full = sweepDeg >= 359.9f;
            int n = full ? segs : segs + 1;
            var ring = new Vector3[n * profile.Length];
            for (int s = 0; s < n; s++)
            {
                float a = (startAngle + sweepDeg * s / segs) * Mathf.Deg2Rad;
                float ca = Mathf.Cos(a), sa = Mathf.Sin(a);
                for (int j = 0; j < profile.Length; j++)
                    ring[s * profile.Length + j] = new Vector3(ca * profile[j].x, profile[j].y, sa * profile[j].x);
            }
            int steps = full ? segs : segs;
            for (int s = 0; s < steps; s++)
            {
                int s1 = full ? (s + 1) % segs : s + 1;
                for (int j = 0; j < profile.Length - 1; j++)
                {
                    var c = colors != null && j < colors.Length ? colors[j] : col;
                    var a0 = ring[s * profile.Length + j];
                    var a1 = ring[s * profile.Length + j + 1];
                    var b0 = ring[s1 * profile.Length + j];
                    var b1 = ring[s1 * profile.Length + j + 1];
                    bool degA = profile[j].x < 1e-5f, degB = profile[j + 1].x < 1e-5f;
                    if (degA && degB) continue;
                    if (degA) Poly(c, a0, a1, b1);
                    else if (degB) Poly(c, a0, a1, b0);
                    else Poly(c, a0, a1, b1, b0);
                }
            }
        }

        /// <summary>
        /// Sweeps a closed 2D profile (x = right, y = up in the path frame) along a 3D path.
        /// Rotation-minimizing frames; optional end caps.
        /// </summary>
        public void Sweep(IList<Vector3> path, Vector2[] profile, Color col, bool capStart = true, bool capEnd = true, Vector3? upHint = null)
        {
            int n = path.Count;
            if (n < 2) return;
            var frames = new (Vector3 t, Vector3 r, Vector3 u)[n];
            Vector3 up0 = upHint ?? Vector3.up;
            for (int i = 0; i < n; i++)
            {
                Vector3 t = (i == 0) ? path[1] - path[0] : (i == n - 1) ? path[n - 1] - path[n - 2] : (path[i + 1] - path[i - 1]);
                t.Normalize();
                Vector3 u;
                if (i == 0)
                {
                    u = up0 - Vector3.Dot(up0, t) * t;
                    if (u.sqrMagnitude < 1e-6f) u = Vector3.Cross(t, Vector3.right);
                    u.Normalize();
                }
                else
                {
                    var pu = frames[i - 1].u;
                    u = (pu - Vector3.Dot(pu, t) * t).normalized;
                }
                var r = Vector3.Cross(u, t).normalized;
                frames[i] = (t, r, u);
            }
            int pc = profile.Length;
            var pts = new Vector3[n * pc];
            for (int i = 0; i < n; i++)
                for (int j = 0; j < pc; j++)
                    pts[i * pc + j] = path[i] + frames[i].r * profile[j].x + frames[i].u * profile[j].y;
            for (int i = 0; i < n - 1; i++)
            {
                var center = (path[i] + path[i + 1]) * 0.5f;
                for (int j = 0; j < pc; j++)
                {
                    int j1 = (j + 1) % pc;
                    PolyOut(col, center, pts[i * pc + j], pts[(i + 1) * pc + j], pts[(i + 1) * pc + j1], pts[i * pc + j1]);
                }
            }
            if (capStart)
            {
                var cap = new Vector3[pc];
                for (int j = 0; j < pc; j++) cap[j] = pts[j];
                PolyOut(col, path[0] + frames[0].t, cap);
            }
            if (capEnd)
            {
                var cap = new Vector3[pc];
                for (int j = 0; j < pc; j++) cap[j] = pts[(n - 1) * pc + j];
                PolyOut(col, path[n - 1] - frames[n - 1].t, cap);
            }
        }

        /// <summary>Circle profile helper for Sweep.</summary>
        public static Vector2[] CircleProfile(float r, int segs)
        {
            var p = new Vector2[segs];
            for (int i = 0; i < segs; i++)
            {
                float a = i / (float)segs * Mathf.PI * 2f;
                p[i] = new Vector2(Mathf.Cos(a) * r, Mathf.Sin(a) * r);
            }
            return p;
        }

        /// <summary>Rounded rectangle profile helper for Sweep (w, h = full size).</summary>
        public static Vector2[] RoundRectProfile(float w, float h, float r, int cornerSegs = 3)
        {
            var list = new List<Vector2>();
            float hx = w * 0.5f - r, hy = h * 0.5f - r;
            Vector2[] centers = { new Vector2(hx, hy), new Vector2(-hx, hy), new Vector2(-hx, -hy), new Vector2(hx, -hy) };
            for (int c = 0; c < 4; c++)
                for (int k = 0; k <= cornerSegs; k++)
                {
                    float a = (c * 90f + 90f * k / cornerSegs) * Mathf.Deg2Rad;
                    list.Add(centers[c] + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r);
                }
            return list.ToArray();
        }

        /// <summary>
        /// Lofted surface through a grid of points: grid[i][j], i = section (along the length), j = point in the section.
        /// All sections must be ordered the same way; the winding is chosen once (using the largest quad and axis(i),
        /// a point inside the shape for section i) so every face points outward. color(i, j) colors quad (i..i+1, j..j+1).
        /// closed = sections are closed loops. decideWith (optional) limits the quads that may decide the winding, for
        /// shapes whose largest quads are not a good test (e.g. walls lying in a section's plane).
        /// </summary>
        public void Loft(Vector3[][] grid, System.Func<int, int, Color> color, bool closed, System.Func<int, Vector3> axis, System.Func<int, int, bool> decideWith = null)
        {
            int ns = grid.Length;
            if (ns < 2) return;
            int np = grid[0].Length;
            int jm = closed ? np : np - 1;
            // decide the winding from the largest quad
            float best = -1f; bool flip = false;
            for (int i = 0; i < ns - 1; i++)
                for (int j = 0; j < jm; j++)
                {
                    if (decideWith != null && !decideWith(i, j)) continue;
                    int j1 = (j + 1) % np;
                    var a = grid[i][j]; var b = grid[i + 1][j]; var c = grid[i + 1][j1]; var d = grid[i][j1];
                    var n = Vector3.Cross(c - a, d - b);
                    float area = n.sqrMagnitude;
                    if (area <= best) continue;
                    best = area;
                    var ctr = (a + b + c + d) * 0.25f;
                    var inside = (axis(i) + axis(i + 1)) * 0.5f;
                    // Poly(a, b, c, d) normal = cross(b - a, c - a)
                    var pn = Vector3.Cross(b - a, c - a);
                    if (pn.sqrMagnitude < 1e-14f) pn = Vector3.Cross(c - a, d - a);
                    flip = Vector3.Dot(pn, ctr - inside) < 0f;
                }
            var q = new List<Vector3>(4);
            for (int i = 0; i < ns - 1; i++)
            {
                for (int j = 0; j < jm; j++)
                {
                    int j1 = (j + 1) % np;
                    var a = grid[i][j]; var b = grid[i + 1][j]; var c = grid[i + 1][j1]; var d = grid[i][j1];
                    q.Clear();
                    if (flip) { AddUnique(q, a); AddUnique(q, d); AddUnique(q, c); AddUnique(q, b); }
                    else { AddUnique(q, a); AddUnique(q, b); AddUnique(q, c); AddUnique(q, d); }
                    if (q.Count >= 3 && (q[0] - q[q.Count - 1]).sqrMagnitude < 1e-10f) q.RemoveAt(q.Count - 1);
                    if (q.Count < 3) continue;
                    Poly(color(i, j), q.ToArray());
                }
            }
        }

        static void AddUnique(List<Vector3> q, Vector3 p)
        {
            if (q.Count > 0 && (q[q.Count - 1] - p).sqrMagnitude < 1e-10f) return;
            q.Add(p);
        }

        static readonly Dictionary<int, (List<Vector3>, List<int>)> icoCache = new Dictionary<int, (List<Vector3>, List<int>)>();

        static (List<Vector3>, List<int>) Ico(int detail)
        {
            if (icoCache.TryGetValue(detail, out var c)) return c;
            float t = (1f + Mathf.Sqrt(5f)) / 2f;
            var v = new List<Vector3>
            {
                new Vector3(-1, t, 0), new Vector3(1, t, 0), new Vector3(-1, -t, 0), new Vector3(1, -t, 0),
                new Vector3(0, -1, t), new Vector3(0, 1, t), new Vector3(0, -1, -t), new Vector3(0, 1, -t),
                new Vector3(t, 0, -1), new Vector3(t, 0, 1), new Vector3(-t, 0, -1), new Vector3(-t, 0, 1)
            };
            for (int i = 0; i < v.Count; i++) v[i] = v[i].normalized;
            var f = new List<int>
            {
                0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11, 1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
                3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9, 4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1
            };
            for (int d = 0; d < detail; d++)
            {
                var nf = new List<int>();
                var mid = new Dictionary<long, int>();
                int Mid(int a, int b)
                {
                    long key = a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
                    if (mid.TryGetValue(key, out int idx)) return idx;
                    v.Add(((v[a] + v[b]) * 0.5f).normalized);
                    mid[key] = v.Count - 1;
                    return v.Count - 1;
                }
                for (int i = 0; i < f.Count; i += 3)
                {
                    int a = f[i], b = f[i + 1], cc = f[i + 2];
                    int ab = Mid(a, b), bc = Mid(b, cc), ca = Mid(cc, a);
                    nf.AddRange(new[] { a, ab, ca, b, bc, ab, cc, ca, bc, ab, bc, ca });
                }
                f = nf;
            }
            c = (v, f);
            icoCache[detail] = c;
            return c;
        }

        /// <summary>Sphere / blob. jitter displaces vertices (deterministic by seed). detail is raised automatically for smooth spheres.</summary>
        public void Sphere(Vector3 center, Vector3 radii, Color col, int detail = 1, float jitter = 0f, int seed = 0, Color? topCol = null)
        {
            // smooth (un-jittered) spheres get one more subdivision so they read as round, not as icosahedra
            float maxR = Mathf.Max(radii.x, Mathf.Max(radii.y, radii.z));
            if (Quality > 1.5f)
            {
                if (jitter <= 0.0001f) { if (detail < 3 && maxR > 0.04f) detail++; }
                else if (detail < 2 && maxR > 0.25f) detail++;   // bigger blobs (bushes, canopies, caps) get smoother too
            }
            var (v, f) = Ico(detail);
            var rnd = new System.Random(seed);
            var pts = new Vector3[v.Count];
            for (int i = 0; i < v.Count; i++)
            {
                float j = 1f;
                if (jitter > 0)
                {
                    // smooth, coherent displacement (value noise on the unit sphere) instead of per-vertex random spikes
                    float nz = Noise3(v[i] * 1.7f, seed) * 0.75f + Noise3(v[i] * 3.9f, seed + 7) * 0.25f;
                    j = 1f + (nz * 2f - 1f) * jitter * 1.6f;
                }
                pts[i] = center + Vector3.Scale(v[i] * j, radii);
            }
            for (int i = 0; i < f.Count; i += 3)
            {
                var a = pts[f[i]]; var b = pts[f[i + 1]]; var c = pts[f[i + 2]];
                var colr = col;
                var n = Vector3.Cross(b - a, c - a);
                if (topCol.HasValue)
                {
                    var nn = n.normalized;
                    if (nn.y > 0.55f) colr = topCol.Value;
                }
                var centroid = (a + b + c) / 3f - center;
                if (Vector3.Dot(n, centroid) < 0) Tri(colr, a, c, b); else Tri(colr, a, b, c);
            }
        }

        /// <summary>Weathered rock: subdivided, noise-displaced, flattened bottom.</summary>
        public void Rock(Vector3 center, Vector3 radii, Color col, int seed, Color? topCol = null, float jitter = 0.22f, int detail = 2)
        {
            var (v, f) = Ico(detail);
            var pts = new Vector3[v.Count];
            for (int i = 0; i < v.Count; i++)
            {
                var d = v[i];
                float nz = Noise3(d * 1.4f, seed) * 0.72f + Noise3(d * 3.0f, seed + 11) * 0.28f;
                float k = 1f + (nz * 2f - 1f) * jitter * 1.5f;
                var p = Vector3.Scale(d * k, radii);
                if (p.y < -radii.y * 0.55f) p.y = -radii.y * 0.55f - (p.y + radii.y * 0.55f) * 0.15f; // sits flat on the ground
                pts[i] = center + p;
            }
            if (rockHulls != null)
            {
                int n = Mathf.Min(pts.Length, 42);
                if (n == 42)
                {
                    var hull = new Vector3[n];
                    for (int i = 0; i < n; i++) hull[i] = m.MultiplyPoint3x4(center + (pts[i] - center) * 1.06f);
                    rockHulls.Add(hull);
                }
            }
            float oldAngle = smoothAngle;
            smoothAngle = 64f;
            for (int i = 0; i < f.Count; i += 3)
            {
                var a = pts[f[i]]; var b = pts[f[i + 1]]; var c = pts[f[i + 2]];
                var n = Vector3.Cross(b - a, c - a);
                var colr = col;
                if (topCol.HasValue && n.normalized.y > 0.5f) colr = topCol.Value;
                var centroid = (a + b + c) / 3f - center;
                if (Vector3.Dot(n, centroid) < 0) Tri(colr, a, c, b); else Tri(colr, a, b, c);
            }
            smoothAngle = oldAngle;
        }

        static float Hash3(int x, int y, int z, int seed)
        {
            unchecked
            {
                int h = x * 374761393 + y * 668265263 + z * 1440662683 + seed * 2147483629;
                h = (h ^ (h >> 13)) * 1274126177;
                h ^= h >> 16;
                return (h & 0xffffff) / (float)0xffffff;
            }
        }

        /// <summary>3D value noise in 0..1.</summary>
        public static float Noise3(Vector3 p, int seed)
        {
            int x0 = Mathf.FloorToInt(p.x), y0 = Mathf.FloorToInt(p.y), z0 = Mathf.FloorToInt(p.z);
            float fx = p.x - x0, fy = p.y - y0, fz = p.z - z0;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
            float L(int dx, int dy, int dz) => Hash3(x0 + dx, y0 + dy, z0 + dz, seed);
            float x00 = Mathf.Lerp(L(0, 0, 0), L(1, 0, 0), fx), x10 = Mathf.Lerp(L(0, 1, 0), L(1, 1, 0), fx);
            float x01 = Mathf.Lerp(L(0, 0, 1), L(1, 0, 1), fx), x11 = Mathf.Lerp(L(0, 1, 1), L(1, 1, 1), fx);
            return Mathf.Lerp(Mathf.Lerp(x00, x10, fy), Mathf.Lerp(x01, x11, fy), fz);
        }

        /// <summary>Triangular prism (tent / roof) along Z: width along X, ridge height.</summary>
        public void Prism(Vector3 baseCenter, float width, float height, float length, Color col, Color? endCol = null)
        {
            float w = width * 0.5f, l = length * 0.5f;
            var c = baseCenter;
            Vector3 a0 = c + new Vector3(-w, 0, -l), b0 = c + new Vector3(w, 0, -l), t0 = c + new Vector3(0, height, -l);
            Vector3 a1 = c + new Vector3(-w, 0, l), b1 = c + new Vector3(w, 0, l), t1 = c + new Vector3(0, height, l);
            var e = endCol ?? col;
            Tri(e, a0, t0, b0);
            Tri(e, b1, t1, a1);
            Quad(col, a0, a1, t1, t0);
            Quad(col, b0, t0, t1, b1);
            Quad(col, a0, b0, b1, a1);
        }

        /// <summary>Flat ring (annulus) on XZ plane.</summary>
        public void Ring(Vector3 center, float r0, float r1, int segs, Color col, float y = 0f)
        {
            segs = Segs(segs);
            for (int i = 0; i < segs; i++)
            {
                float a0 = i / (float)segs * Mathf.PI * 2f, a1 = (i + 1) / (float)segs * Mathf.PI * 2f;
                var d0 = new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0));
                var d1 = new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1));
                Quad(col, center + d0 * r1 + Vector3.up * y, center + d0 * r0 + Vector3.up * y, center + d1 * r0 + Vector3.up * y, center + d1 * r1 + Vector3.up * y);
            }
        }

        /// <summary>Flat disc on XZ plane facing up.</summary>
        public void Disc(Vector3 center, float r, int segs, Color col)
        {
            segs = Segs(segs);
            for (int i = 0; i < segs; i++)
            {
                float a0 = i / (float)segs * Mathf.PI * 2f, a1 = (i + 1) / (float)segs * Mathf.PI * 2f;
                Tri(col, center, center + new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1)) * r, center + new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0)) * r);
            }
        }

        // scratch buffers reused between builds (meshes are built one at a time on the main thread)
        static int[] sNext = new int[0];
        static Vector3[] sOut = new Vector3[0];
        static readonly Dictionary<Vector3Int, int> sHead = new Dictionary<Vector3Int, int>(4096);
        static readonly List<int> sGroup = new List<int>(32);

        static int[] sRemap = new int[0];

        bool SameVertex(int a, int b)
        {
            var na = sOut[a]; var nb = sOut[b];
            if (Mathf.Abs(na.x - nb.x) > 0.002f || Mathf.Abs(na.y - nb.y) > 0.002f || Mathf.Abs(na.z - nb.z) > 0.002f) return false;
            if (mats[a] != mats[b]) return false;
            var ca = cols[a]; var cb = cols[b];
            return Mathf.Abs(ca.r - cb.r) < 0.002f && Mathf.Abs(ca.g - cb.g) < 0.002f && Mathf.Abs(ca.b - cb.b) < 0.002f && Mathf.Abs(ca.a - cb.a) < 0.002f;
        }

        /// <param name="smoothOutlineNormals">Unused since the outlines were removed; kept for source compatibility.</param>
        public Mesh Build(string name = "mesh", bool smoothOutlineNormals = true)
        {
            var mesh = new Mesh { name = name };
            int n = verts.Count;
            bool anySmooth = false;
            for (int i = 0; i < smoothCos.Count && !anySmooth; i++) anySmooth = smoothCos[i] <= 1f;
            if (sNext.Length < n) { sNext = new int[n * 2]; sOut = new Vector3[n * 2]; sRemap = new int[n * 2]; }
            var wv = new List<Vector3>(n / 2); var wn = new List<Vector3>(n / 2); var wc = new List<Color>(n / 2);
            var wu = new List<Vector2>(n / 2); var wm = new List<Vector2>(n / 2);

            // group coincident vertices: head[key] -> first index, next[i] -> following index (no per-group allocations)
            sHead.Clear();
            for (int i = 0; i < n; i++)
            {
                var k = Key(verts[i]);
                if (sHead.TryGetValue(k, out int h)) { sNext[i] = h; sHead[k] = i; }
                else { sNext[i] = -1; sHead[k] = i; }
            }
            foreach (var head in sHead.Values)
            {
                sGroup.Clear();
                for (int i = head; i >= 0; i = sNext[i]) sGroup.Add(i);
                // weighted auto-smooth normals inside the group
                for (int a = 0; a < sGroup.Count; a++)
                {
                    int i = sGroup[a];
                    var ni = norms[i];
                    float cosT = smoothCos[i];
                    if (!anySmooth || cosT > 1f || sGroup.Count == 1) { sOut[i] = ni; continue; }
                    var acc = Vector3.zero;
                    for (int c = 0; c < sGroup.Count; c++)
                    {
                        int j = sGroup[c];
                        var nj = norms[j];
                        if (Vector3.Dot(ni, nj) >= cosT) acc += nj * weights[j];
                    }
                    sOut[i] = acc.sqrMagnitude > 1e-12f ? acc.normalized : ni;
                }
                // weld group members that ended up identical (normal, color, material): smooth surfaces built from
                // separate polygons share their vertices again -> ~3x fewer vertices, better vertex cache use
                for (int a = 0; a < sGroup.Count; a++)
                {
                    int i = sGroup[a];
                    int idx = -1;
                    for (int c = 0; c < a && idx < 0; c++)
                        if (SameVertex(i, sGroup[c])) idx = sRemap[sGroup[c]];
                    if (idx < 0)
                    {
                        idx = wv.Count;
                        wv.Add(verts[i]); wn.Add(sOut[i]); wc.Add(cols[i]); wu.Add(uvs[i]); wm.Add(mats[i]);
                    }
                    sRemap[i] = idx;
                }
            }
            var wt = new int[tris.Count];
            for (int i = 0; i < wt.Length; i++) wt[i] = sRemap[tris[i]];
            if (wv.Count > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.SetVertices(wv);
            mesh.SetNormals(wn);
            mesh.SetColors(wc);
            mesh.SetUVs(0, wu);
            mesh.SetUVs(1, wm);
            mesh.SetTriangles(wt, 0);
            mesh.RecalculateBounds();
            return mesh;
        }

        static Vector3Int Key(Vector3 p) => new Vector3Int(Mathf.RoundToInt(p.x * 1000f), Mathf.RoundToInt(p.y * 1000f), Mathf.RoundToInt(p.z * 1000f));

        public void Clear()
        {
            verts.Clear(); norms.Clear(); cols.Clear(); uvs.Clear(); mats.Clear(); weights.Clear(); smoothCos.Clear(); tris.Clear(); stack.Clear();
            m = Matrix4x4.identity;
            gloss = 0f; metal = 0f;
            smoothAngle = 50f;
        }
    }
}
