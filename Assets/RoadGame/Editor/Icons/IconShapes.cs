using System.Collections.Generic;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Toy-like solids for the icon models, on top of <see cref="MeshBuilder"/>: inflated "pillow" extrusions of 2D
    /// outlines, rounded boxes, tori, tubes and capsules, plus outline generators with rounded corners.
    /// Convention: X right, Y up, the front of an icon faces -Z (towards the studio camera).
    /// </summary>
    public static class IconShapes
    {
        // ------------------------------------------------------------------ solids
        /// <summary>
        /// Inflated solid from a closed 2D outline that is star-shaped around <paramref name="center"/>. The cross
        /// section is a superellipse (exponent <paramref name="p"/>: 2 = round balloon, 4 = flat badge with rounded rim),
        /// so the silhouette edge is perfectly smooth and the front is softly domed. Front bulge = <paramref name="front"/>
        /// towards -Z, back bulge = <paramref name="back"/> towards +Z, both from the plane z = <paramref name="z0"/>.
        /// </summary>
        public static void Pillow(MeshBuilder b, IList<Vector2> outline, Vector2 center, float front, float back, float p,
                                  Color col, Color? backCol = null, float z0 = 0f, int rings = 14, int backRings = 8)
        {
            int m = outline.Count;
            var inside = new Vector3(center.x, center.y, z0);
            Vector3 P(int j, float s, float z)
            {
                var o = outline[j % m];
                return new Vector3(center.x + (o.x - center.x) * s, center.y + (o.y - center.y) * s, z0 + z);
            }
            float e = 2f / Mathf.Max(1.01f, p);
            for (int side = -1; side <= 1; side += 2)
            {
                float depth = side < 0 ? front : back;
                int K = side < 0 ? rings : backRings;
                var c = side < 0 ? col : (backCol ?? col);
                if (depth <= 0.0001f)
                {
                    // flat back
                    for (int j = 0; j < m; j++) b.PolyOut(c, inside + new Vector3(0, 0, -1f), new Vector3(center.x, center.y, z0), P(j, 1f, 0f), P(j + 1, 1f, 0f));
                    continue;
                }
                for (int k = 0; k < K; k++)
                {
                    float phA = Mathf.PI * 0.5f * (1f - k / (float)K), phB = Mathf.PI * 0.5f * (1f - (k + 1) / (float)K);
                    float sA = Mathf.Pow(Mathf.Max(0f, Mathf.Cos(phA)), e), zA = side * depth * Mathf.Pow(Mathf.Max(0f, Mathf.Sin(phA)), e);
                    float sB = Mathf.Pow(Mathf.Max(0f, Mathf.Cos(phB)), e), zB = side * depth * Mathf.Pow(Mathf.Max(0f, Mathf.Sin(phB)), e);
                    for (int j = 0; j < m; j++)
                    {
                        if (k == 0) b.PolyOut(c, inside, new Vector3(center.x, center.y, z0 + zA), P(j, sB, zB), P(j + 1, sB, zB));
                        else b.PolyOut(c, inside, P(j, sA, zA), P(j + 1, sA, zA), P(j + 1, sB, zB), P(j, sB, zB));
                    }
                }
            }
        }

        /// <summary>Box with fully rounded edges and corners (radius r), flat faces. seg = steps per 45° of rounding.</summary>
        public static void RoundBox(MeshBuilder b, Vector3 c, Vector3 size, float r, Color col, Color? top = null, int seg = 4)
        {
            var h = size * 0.5f;
            r = Mathf.Clamp(r, 0.001f, Mathf.Min(h.x, Mathf.Min(h.y, h.z)) * 0.999f);
            var inner = h - Vector3.one * r;
            float[] Coords(float inn)
            {
                var l = new List<float>();
                for (int i = seg; i >= 1; i--) l.Add(-inn - r * Mathf.Tan(Mathf.PI * 0.25f * i / seg));
                if (inn < 1e-4f) l.Add(0f);
                else
                {
                    int mid = Mathf.Max(1, Mathf.CeilToInt(inn * 2f / Mathf.Max(0.05f, r)));
                    for (int i = 0; i <= mid; i++) l.Add(Mathf.Lerp(-inn, inn, i / (float)mid));
                }
                for (int i = 1; i <= seg; i++) l.Add(inn + r * Mathf.Tan(Mathf.PI * 0.25f * i / seg));
                return l.ToArray();
            }
            float[] cx = Coords(inner.x), cy = Coords(inner.y), cz = Coords(inner.z);
            Vector3 Map(Vector3 p)
            {
                var q = new Vector3(Mathf.Clamp(p.x, -inner.x, inner.x), Mathf.Clamp(p.y, -inner.y, inner.y), Mathf.Clamp(p.z, -inner.z, inner.z));
                var d = p - q;
                return c + q + (d.sqrMagnitude > 1e-12f ? d.normalized * r : Vector3.zero);
            }
            // each face: fixed axis at +/- (inner + r), grid over the other two
            for (int axis = 0; axis < 3; axis++)
                for (int s = -1; s <= 1; s += 2)
                {
                    float[] ua = axis == 0 ? cy : cx, va = axis == 2 ? cy : cz;
                    float fixedV = s * ((axis == 0 ? inner.x : axis == 1 ? inner.y : inner.z) + r);
                    for (int i = 0; i < ua.Length - 1; i++)
                        for (int j = 0; j < va.Length - 1; j++)
                        {
                            Vector3 G(float u, float v) => axis == 0 ? new Vector3(fixedV, u, v) : axis == 1 ? new Vector3(u, fixedV, v) : new Vector3(u, v, fixedV);
                            var p0 = Map(G(ua[i], va[j])); var p1 = Map(G(ua[i + 1], va[j])); var p2 = Map(G(ua[i + 1], va[j + 1])); var p3 = Map(G(ua[i], va[j + 1]));
                            var ctr = (p0 + p1 + p2 + p3) * 0.25f;
                            var nrm = ctr - c - new Vector3(Mathf.Clamp(ctr.x - c.x, -inner.x, inner.x), Mathf.Clamp(ctr.y - c.y, -inner.y, inner.y), Mathf.Clamp(ctr.z - c.z, -inner.z, inner.z));
                            var colr = top.HasValue && nrm.normalized.y > 0.5f ? top.Value : col;
                            b.PolyOut(colr, ctr - nrm, p0, p1, p2, p3);
                        }
                }
        }

        public static void RoundBox(MeshBuilder b, Vector3 c, Vector3 size, float r, Quaternion rot, Color col, Color? top = null, int seg = 4)
        {
            b.Push(c, rot);
            RoundBox(b, Vector3.zero, size, r, col, top, seg);
            b.Pop();
        }

        /// <summary>Torus around local Y (ring in the XZ plane). sweepDeg &lt; 360 makes an open arc with rounded ends.</summary>
        public static void Torus(MeshBuilder b, Vector3 c, Quaternion rot, float R, float r, Color col, int segMajor = 48, int segMinor = 16, float startDeg = 0f, float sweepDeg = 360f)
        {
            b.Push(c, rot);
            bool full = sweepDeg >= 359.9f;
            for (int i = 0; i < segMajor; i++)
            {
                float a0 = (startDeg + sweepDeg * i / segMajor) * Mathf.Deg2Rad, a1 = (startDeg + sweepDeg * (i + 1) / segMajor) * Mathf.Deg2Rad;
                var d0 = new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0)); var d1 = new Vector3(Mathf.Cos(a1), 0, Mathf.Sin(a1));
                var mid = (d0 + d1).normalized * R;
                for (int j = 0; j < segMinor; j++)
                {
                    float b0 = j / (float)segMinor * Mathf.PI * 2f, b1 = (j + 1) / (float)segMinor * Mathf.PI * 2f;
                    Vector3 Q(Vector3 d, float bb) => d * (R + r * Mathf.Cos(bb)) + Vector3.up * (r * Mathf.Sin(bb));
                    b.PolyOut(col, mid, Q(d0, b0), Q(d1, b0), Q(d1, b1), Q(d0, b1));
                }
            }
            if (!full)
            {
                float aS = startDeg * Mathf.Deg2Rad, aE = (startDeg + sweepDeg) * Mathf.Deg2Rad;
                b.Sphere(new Vector3(Mathf.Cos(aS), 0, Mathf.Sin(aS)) * R, Vector3.one * r, col, 3);
                b.Sphere(new Vector3(Mathf.Cos(aE), 0, Mathf.Sin(aE)) * R, Vector3.one * r, col, 3);
            }
            b.Pop();
        }

        /// <summary>Round tube along a path with spherical (rounded) ends.</summary>
        public static void Tube(MeshBuilder b, IList<Vector3> path, float r, Color col, int segs = 20, bool roundEnds = true)
        {
            b.Sweep(path, MeshBuilder.CircleProfile(r, segs), col, !roundEnds, !roundEnds);
            if (roundEnds)
            {
                b.Sphere(path[0], Vector3.one * r, col, 3);
                b.Sphere(path[path.Count - 1], Vector3.one * r, col, 3);
            }
        }

        /// <summary>Capsule between two points.</summary>
        public static void Capsule(MeshBuilder b, Vector3 a, Vector3 c, float r, Color col)
        {
            Tube(b, new[] { a, Vector3.Lerp(a, c, 0.5f), c }, r, col, 24, true);
        }

        /// <summary>Quadratic Bezier path sampled with n points.</summary>
        public static Vector3[] Bezier(Vector3 a, Vector3 ctrl, Vector3 c, int n)
        {
            var pts = new Vector3[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)(n - 1);
                pts[i] = (1 - t) * (1 - t) * a + 2 * (1 - t) * t * ctrl + t * t * c;
            }
            return pts;
        }

        // ------------------------------------------------------------------ outlines (closed, any winding)
        /// <summary>Rounds every corner of a polygon with a quadratic fillet of the given radius (clamped to half the edges).</summary>
        public static Vector2[] RoundCorners(IList<Vector2> poly, float radius, int seg = 8, float[] perCorner = null)
        {
            var o = new List<Vector2>();
            int n = poly.Count;
            for (int i = 0; i < n; i++)
            {
                var v = poly[i]; var a = poly[(i + n - 1) % n]; var c = poly[(i + 1) % n];
                float rr = perCorner != null && i < perCorner.Length ? perCorner[i] : radius;
                if (rr <= 0.0001f) { o.Add(v); continue; }
                var t1 = v + (a - v).normalized * Mathf.Min(rr, (a - v).magnitude * 0.5f);
                var t2 = v + (c - v).normalized * Mathf.Min(rr, (c - v).magnitude * 0.5f);
                for (int k = 0; k <= seg; k++)
                {
                    float t = k / (float)seg;
                    o.Add((1 - t) * (1 - t) * t1 + 2 * (1 - t) * t * v + t * t * t2);
                }
            }
            return Resample(o, Mathf.Max(96, o.Count));
        }

        /// <summary>Resamples a closed polyline to n points evenly spaced by arc length.</summary>
        public static Vector2[] Resample(IList<Vector2> poly, int n)
        {
            int m = poly.Count;
            var cum = new float[m + 1];
            for (int i = 0; i < m; i++) cum[i + 1] = cum[i] + (poly[(i + 1) % m] - poly[i]).magnitude;
            float total = cum[m];
            var o = new Vector2[n];
            int seg = 0;
            for (int k = 0; k < n; k++)
            {
                float d = total * k / n;
                while (seg < m - 1 && cum[seg + 1] < d) seg++;
                float len = Mathf.Max(1e-6f, cum[seg + 1] - cum[seg]);
                o[k] = Vector2.Lerp(poly[seg], poly[(seg + 1) % m], (d - cum[seg]) / len);
            }
            return o;
        }

        public static Vector2[] Circle(float r, int n = 160, Vector2 c = default)
        {
            var o = new Vector2[n];
            for (int i = 0; i < n; i++) { float a = i / (float)n * Mathf.PI * 2f; o[i] = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r; }
            return o;
        }

        public static Vector2[] Ellipse(float rx, float ry, int n = 160, Vector2 c = default)
        {
            var o = new Vector2[n];
            for (int i = 0; i < n; i++) { float a = i / (float)n * Mathf.PI * 2f; o[i] = c + new Vector2(Mathf.Cos(a) * rx, Mathf.Sin(a) * ry); }
            return o;
        }

        public static Vector2[] RoundRect(float w, float h, float r, Vector2 c = default)
        {
            float x = w * 0.5f, y = h * 0.5f;
            return RoundCorners(new[] { c + new Vector2(-x, -y), c + new Vector2(x, -y), c + new Vector2(x, y), c + new Vector2(-x, y) }, r, 10);
        }

        /// <summary>Classic plump heart, about 2 units wide, tip at y = -0.95.</summary>
        public static Vector2[] Heart(int n = 200)
        {
            var o = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)n * Mathf.PI * 2f;
                float x = 16f * Mathf.Pow(Mathf.Sin(t), 3);
                float y = 13f * Mathf.Cos(t) - 5f * Mathf.Cos(2 * t) - 2f * Mathf.Cos(3 * t) - Mathf.Cos(4 * t);
                o[i] = new Vector2(x / 16.5f, (y + 1.5f) / 16.5f);
            }
            // soften the bottom tip a little (toy look)
            return RoundCorners(Resample(o, 64), 0.05f, 6);
        }

        public static Vector2[] Star(int points, float rOut, float rIn, float round, float rotDeg = 90f)
        {
            var p = new Vector2[points * 2];
            for (int i = 0; i < points * 2; i++)
            {
                float a = (rotDeg + i * 180f / points) * Mathf.Deg2Rad;
                p[i] = new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * (i % 2 == 0 ? rOut : rIn);
            }
            var rc = new float[points * 2];
            for (int i = 0; i < rc.Length; i++) rc[i] = i % 2 == 0 ? round : round * 0.6f;
            return RoundCorners(p, round, 10, rc);
        }

        /// <summary>Plus / cross with rounded ends; arm = half length, t = half thickness.</summary>
        public static Vector2[] Plus(float arm, float t, float round)
        {
            var p = new[]
            {
                new Vector2(t, t), new Vector2(t, arm), new Vector2(-t, arm), new Vector2(-t, t), new Vector2(-arm, t), new Vector2(-arm, -t),
                new Vector2(-t, -t), new Vector2(-t, -arm), new Vector2(t, -arm), new Vector2(t, -t), new Vector2(arm, -t), new Vector2(arm, t)
            };
            var rc = new float[12];
            for (int i = 0; i < 12; i++) rc[i] = (i % 3 == 0) ? round * 0.35f : round;
            return RoundCorners(p, round, 10, rc);
        }

        public static Vector2[] Rotate(IList<Vector2> poly, float deg, Vector2 pivot = default)
        {
            var o = new Vector2[poly.Count];
            float a = deg * Mathf.Deg2Rad, cs = Mathf.Cos(a), sn = Mathf.Sin(a);
            for (int i = 0; i < o.Length; i++)
            {
                var q = poly[i] - pivot;
                o[i] = pivot + new Vector2(q.x * cs - q.y * sn, q.x * sn + q.y * cs);
            }
            return o;
        }

        public static Vector2[] Transform(IList<Vector2> poly, Vector2 scale, Vector2 offset)
        {
            var o = new Vector2[poly.Count];
            for (int i = 0; i < o.Length; i++) o[i] = Vector2.Scale(poly[i], scale) + offset;
            return o;
        }
    }
}
