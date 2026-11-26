using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    public enum Icon
    {
        Heart, Regen, Gun, Smash, Pierce, Blast, Gem, Skull, Gear, Wrench, Lock, Shield, Ad, Chest,
        Zoom, Arrow, Plus, Star, Harpoon, Close, Car, Flag,
        BullBar, RoofPlates, ChestBig, ChestArmor, GemPile, Crit, EnemyDot
    }

    /// <summary>Procedural textures and UI sprites; UI icons are baked 3D renders loaded from Resources/Icons.</summary>
    public static class Tex
    {
        static readonly Dictionary<string, Texture2D> texCache = new Dictionary<string, Texture2D>();
        static readonly Dictionary<string, Sprite> spriteCache = new Dictionary<string, Sprite>();
        static readonly Dictionary<Icon, Sprite> iconCache = new Dictionary<Icon, Sprite>();

        public static void Reset()
        {
            texCache.Clear();
            spriteCache.Clear();
            iconCache.Clear();
            lockedCache.Clear();
        }

        // ------------------------------------------------------------------ noise
        static float Hash(int x, int y, int seed)
        {
            unchecked
            {
                int h = x * 374761393 + y * 668265263 + seed * 2147483647;
                h = (h ^ (h >> 13)) * 1274126177;
                h ^= h >> 16;
                return (h & 0xffffff) / (float)0xffffff;
            }
        }

        static float ValueNoise(float x, float y, int period, int seed)
        {
            int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
            float fx = x - x0, fy = y - y0;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            int X0 = ((x0 % period) + period) % period, Y0 = ((y0 % period) + period) % period;
            int X1 = (X0 + 1) % period, Y1 = (Y0 + 1) % period;
            float a = Hash(X0, Y0, seed), b = Hash(X1, Y0, seed), c = Hash(X0, Y1, seed), d = Hash(X1, Y1, seed);
            return Mathf.Lerp(Mathf.Lerp(a, b, fx), Mathf.Lerp(c, d, fx), fy);
        }

        static float Fbm(float u, float v, int baseFreq, int octaves, int seed)
        {
            float sum = 0, amp = 0.5f, norm = 0;
            int f = baseFreq;
            for (int o = 0; o < octaves; o++)
            {
                sum += ValueNoise(u * f, v * f, f, seed + o * 17) * amp;
                norm += amp; amp *= 0.5f; f *= 2;
            }
            return sum / norm;
        }

        static Texture2D NewTex(int w, int h, bool mips = true, TextureWrapMode wrap = TextureWrapMode.Repeat, bool linear = false)
        {
            var t = new Texture2D(w, h, TextureFormat.RGBA32, mips, linear);
            t.wrapMode = wrap;
            t.filterMode = FilterMode.Bilinear;
            t.anisoLevel = 2;
            return t;
        }

        /// <summary>World size of one ground detail tile (meters).</summary>
        public const float GroundTileMeters = 26f;

        /// <summary>
        /// Clean near-white ground detail (multiplied by the vertex colors that carry the zone palette):
        /// only large, quiet shapes - broad tone variation, big wind-swept lighter areas, darker compacted patches
        /// and, inside some of them, a few large dry-mud crack networks. No ripples, grain or speckle.
        /// </summary>
        public static Texture2D GroundDetail(int seed)
        {
            string key = "ground2_" + seed;
            if (texCache.TryGetValue(key, out var cached)) return cached;
            int n = 512;
            var t = NewTex(n, n);
            t.anisoLevel = 4;
            var val = new float[n * n];
            const int Cells = 14;                  // crack cell grid per tile (~1.9 m cells)
            var cellPts = new Vector2[Cells * Cells];
            for (int j = 0; j < Cells; j++)
                for (int i = 0; i < Cells; i++)
                    cellPts[j * Cells + i] = new Vector2(i + 0.2f + 0.6f * Hash(i, j, seed + 21), j + 0.2f + 0.6f * Hash(i, j, seed + 22));
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float u = x / (float)n, v = y / (float)n;
                    float broad = Fbm(u, v, 2, 2, seed);
                    float wearN = Fbm(u, v, 3, 2, seed + 3);
                    float packN = Fbm(u, v, 3, 2, seed + 7);
                    float wear = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.57f, 0.7f, wearN));     // wind-swept, lighter
                    float packed = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.655f, 0.76f, packN)); // compacted, darker (rare)
                    float value = 0.955f + (broad - 0.5f) * 0.06f + wear * 0.035f - packed * 0.045f;
                    if (packed > 0.02f)
                    {
                        // dry-mud cracks: Voronoi cell borders (F2 - F1), tileable over the cell grid
                        float cx = u * Cells, cy = v * Cells;
                        int ix = Mathf.FloorToInt(cx), iy = Mathf.FloorToInt(cy);
                        float f1 = 9f, f2 = 9f;
                        for (int oy = -1; oy <= 1; oy++)
                            for (int ox = -1; ox <= 1; ox++)
                            {
                                int gx = ix + ox, gy = iy + oy;
                                int wx = ((gx % Cells) + Cells) % Cells, wy = ((gy % Cells) + Cells) % Cells;
                                var p = cellPts[wy * Cells + wx] + new Vector2(gx - wx, gy - wy);
                                float d = (p - new Vector2(cx, cy)).magnitude;
                                if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) f2 = d;
                            }
                        float edge = f2 - f1;                                       // 0 on the border
                        float crack = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.03f, 0.075f, edge));
                        float lip = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.075f, 0.13f, edge));
                        float k = Mathf.InverseLerp(0.35f, 1f, packed);
                        value -= crack * 0.13f * k;
                        value += (lip - crack) * 0.03f * k;                         // slightly raised, lighter crack lips
                    }
                    val[y * n + x] = value;
                }
            var px = new Color32[n * n];
            for (int i = 0; i < px.Length; i++)
            {
                byte b = (byte)Mathf.Clamp(val[i] * 255f, 0, 255);
                px[i] = new Color32(b, b, b, 255);
            }
            t.SetPixels32(px);
            t.Apply(true, false);
            texCache[key] = t;
            return t;
        }

        /// <summary>Tileable grime / wear map (linear, ~0.5 average) used triplanar by the toon shader.</summary>
        public static Texture2D Grime()
        {
            if (texCache.TryGetValue("grime", out var cached)) return cached;
            int n = 256;
            var t = NewTex(n, n, true, TextureWrapMode.Repeat, true);
            var px = new Color32[n * n];
            var rnd = new System.Random(77);
            var val = new float[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float u = x / (float)n, v = y / (float)n;
                    float blot = Fbm(u, v, 4, 4, 41);
                    float mid = Fbm(u, v, 16, 2, 43);
                    float speck = Hash(x, y, 47);
                    float g = 0.5f + (blot - 0.5f) * 0.9f + (mid - 0.5f) * 0.35f + (speck - 0.5f) * 0.12f;
                    val[y * n + x] = g;
                }
            // scratches
            for (int i = 0; i < 70; i++)
            {
                float x0 = (float)rnd.NextDouble() * n, y0 = (float)rnd.NextDouble() * n;
                float a = (float)rnd.NextDouble() * Mathf.PI;
                float len = 6f + (float)rnd.NextDouble() * 26f;
                float k = (float)rnd.NextDouble() < 0.5f ? 0.22f : -0.18f;
                for (float s = 0; s < len; s += 0.5f)
                {
                    int X = ((int)(x0 + Mathf.Cos(a) * s) % n + n) % n, Y = ((int)(y0 + Mathf.Sin(a) * s) % n + n) % n;
                    val[Y * n + X] += k;
                }
            }
            for (int i = 0; i < px.Length; i++)
            {
                byte b = (byte)Mathf.Clamp(val[i] * 255f, 0, 255);
                px[i] = new Color32(b, b, b, 255);
            }
            t.SetPixels32(px);
            t.Apply(true, false);
            texCache["grime"] = t;
            return t;
        }

        /// <summary>
        /// Road texture: u across the road (0..1), v along (tiles). Clean stylized asphalt: flat muted base,
        /// big faded wear areas and wheel tracks, one dark repair patch, a few long cracks, crisp cream edge lines,
        /// clean center dashes and broad wavy sand drifts on the shoulders. No fine noise.
        /// </summary>
        public static Texture2D Road(Color asphalt, Color line, Color edge, int seed)
        {
            string key = "road2_" + ColorUtility.ToHtmlStringRGB(asphalt) + seed;
            if (texCache.TryGetValue(key, out var cached)) return cached;
            int w = 256, h = 512;
            var t = NewTex(w, h);
            t.anisoLevel = 4;
            var rnd = new System.Random(seed);
            float Rf() => (float)rnd.NextDouble();
            var faded = Color.Lerp(asphalt, Color.white, 0.14f);
            var dark = asphalt * 0.9f; dark.a = 1f;
            var edgeLine = Color.Lerp(edge, Color.white, 0.55f);
            // long cracks: random walks along the road, stored as a distance field
            var crackD = new float[w * h];
            for (int i = 0; i < crackD.Length; i++) crackD[i] = 99f;
            void Stamp(float px0, float py0, float rad)
            {
                int r = Mathf.CeilToInt(rad + 2f);
                int cx0 = Mathf.RoundToInt(px0), cy0 = Mathf.RoundToInt(py0);
                for (int dy = -r; dy <= r; dy++)
                    for (int dx = -r; dx <= r; dx++)
                    {
                        int X = cx0 + dx, Y = cy0 + dy;
                        if (X < 0 || X >= w) continue;
                        float fx = X - px0, fy = Y - py0;
                        float d = Mathf.Sqrt(fx * fx + fy * fy) - rad;
                        Y = ((Y % h) + h) % h;
                        int k = Y * w + X;
                        if (d < crackD[k]) crackD[k] = d;
                    }
            }
            for (int c = 0; c < 2; c++)
            {
                float x = w * (0.2f + 0.6f * Rf()), y = h * Rf();
                float ang = (Rf() - 0.5f) * 1.2f;
                int len = 90 + rnd.Next(150);
                for (int s = 0; s < len; s++)
                {
                    ang += (Rf() - 0.5f) * 0.5f;
                    ang = Mathf.Clamp(ang, -1.1f, 1.1f);
                    x += Mathf.Sin(ang) * 1.2f; y += Mathf.Cos(ang) * 1.2f;
                    if (x < w * 0.12f || x > w * 0.88f) ang = -ang;
                    Stamp(x, y, s % 37 < 30 ? 1.1f : 0.6f);
                    if (rnd.Next(70) == 0)
                    {
                        // short side branch
                        float bx = x, by = y, ba = ang + (Rf() < 0.5f ? 1f : -1f) * (0.8f + Rf() * 0.5f);
                        for (int b = 0; b < 18 + rnd.Next(20); b++) { ba += (Rf() - 0.5f) * 0.4f; bx += Mathf.Sin(ba) * 1.2f; by += Mathf.Cos(ba) * 1.2f; Stamp(bx, by, 0.7f); }
                    }
                }
            }
            // one dark repair patch (rounded rectangle) per tile
            float patchU = 0.28f + 0.4f * Rf(), patchV = Rf(), patchW = 0.16f + 0.08f * Rf(), patchH = 0.07f + 0.04f * Rf();
            var px = new Color[w * h];
            // low-frequency noise on a coarse grid (bilinear), 1D noise once per row: same look, ~3x cheaper to build
            const int GW = 17, GH = 65;
            var wearGrid = new float[GW * GH];
            for (int gy = 0; gy < GH; gy++)
                for (int gx = 0; gx < GW; gx++)
                    wearGrid[gy * GW + gx] = Fbm(gx / (GW - 1f) * 0.5f, gy / (GH - 1f), 2, 2, seed);
            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5f) / h;
                float gap = Fbm(0.5f, v, 3, 1, seed + 5);
                float waveL = (Fbm(0.1f, v, 4, 2, seed + 9) - 0.5f) * 0.09f, waveR = (Fbm(0.9f, v, 4, 2, seed + 9) - 0.5f) * 0.09f;
                float fy = v * (GH - 1); int y0 = Mathf.Min(GH - 2, (int)fy); float ty = fy - y0;
                for (int x = 0; x < w; x++)
                {
                    float u = (x + 0.5f) / w;
                    float eu = Mathf.Min(u, 1 - u);
                    // large faded areas + wheel tracks
                    float fx = u * (GW - 1); int x0 = Mathf.Min(GW - 2, (int)fx); float tx = fx - x0;
                    float wearN = Mathf.Lerp(Mathf.Lerp(wearGrid[y0 * GW + x0], wearGrid[y0 * GW + x0 + 1], tx),
                                             Mathf.Lerp(wearGrid[(y0 + 1) * GW + x0], wearGrid[(y0 + 1) * GW + x0 + 1], tx), ty);
                    float wear = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.5f, 0.66f, wearN));
                    float tracks = Mathf.Exp(-Mathf.Pow((Mathf.Abs(u - 0.5f) - 0.22f) / 0.07f, 2f)) * 0.35f;
                    var c = Color.Lerp(asphalt, faded, Mathf.Clamp01(wear * 0.75f + tracks));
                    // repair patch
                    float pdv = Mathf.Abs(Mathf.Repeat(v - patchV + 0.5f, 1f) - 0.5f);
                    // rounded-rectangle distance (in road-width units) for a soft patched area
                    float qx = Mathf.Max(Mathf.Abs(u - patchU) - patchW * 0.5f + 0.03f, 0f), qy = Mathf.Max(pdv - patchH * 0.5f + 0.03f, 0f);
                    float pd = Mathf.Sqrt(qx * qx + qy * qy) - 0.03f;
                    c = Color.Lerp(c, dark, 0.85f * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-0.006f, 0.006f, pd))));
                    // cracks (dark core, soft edge)
                    float cd = crackD[y * w + x];
                    c = Color.Lerp(c, asphalt * 0.55f, 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-0.3f, 1.2f, cd)));
                    // edge lines with a few long worn gaps
                    float lineE = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.009f, 0.013f, Mathf.Abs(eu - 0.075f)));
                    c = Color.Lerp(c, edgeLine, lineE * (gap > 0.36f ? 0.85f : 0.25f));
                    // center dashes: rounded ends, an occasional worn dash
                    float dv = Mathf.Repeat(v, 0.5f);
                    float dash = Mathf.Max(Mathf.Abs(u - 0.5f) / 0.019f, Mathf.Abs(dv - 0.14f) / 0.14f);
                    float dashA = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.88f, 1.02f, dash));
                    float worn = Mathf.Floor(v * 2f) % 3 == 2 ? 0.55f : 0.95f;
                    c = Color.Lerp(c, line, dashA * worn);
                    // sand drifts: broad and wavy, soft edge
                    float wave = u < 0.5f ? waveL : waveR;
                    float drift = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.075f + wave, 0.02f + wave, eu));
                    c = Color.Lerp(c, edge, drift);
                    c.a = 1;
                    px[y * w + x] = c;
                }
            }
            t.SetPixels(px);
            t.Apply(true, false);
            texCache[key] = t;
            return t;
        }

        /// <summary>Dashed range ring (edge at uv radius ~0.975) with a faint gradient fill toward the edge.</summary>
        public static Texture2D DashedRing()
        {
            if (texCache.TryGetValue("dashring", out var c)) return c;
            int n = 512;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            t.anisoLevel = 4;
            var px = new Color[n * n];
            const int Dashes = 72;
            float px1 = 2f / n;
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2 - 1, dy = (y + 0.5f) / n * 2 - 1;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    float ang = Mathf.Atan2(dy, dx) / (2 * Mathf.PI) + 0.5f;
                    float ph = ang * Dashes - Mathf.Floor(ang * Dashes);
                    float dash = Mathf.Clamp01(Mathf.Min(ph, 0.62f - ph) / (px1 * Dashes * 2f) + 0.5f) * (ph < 0.62f ? 1f : 0f);
                    float band = (1f - Mathf.Clamp01((Mathf.Abs(r - 0.972f) - 0.009f) / (px1 * 1.5f))) * dash;
                    float halo = (1f - Mathf.Clamp01((Mathf.Abs(r - 0.972f) - 0.016f) / (px1 * 2f))) * 0.55f;   // dark track: readable on light sand
                    float fill = r < 0.95f ? Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.7f, 0.95f, r)) * 0.16f + 0.03f : 0f;
                    // composite: fill (white) <- halo (dark) <- dashes (white)
                    float aA = fill, cA = 1f;
                    float a2 = halo + aA * (1f - halo); float c2 = a2 > 1e-4f ? (0.08f * halo + cA * aA * (1f - halo)) / a2 : 1f;
                    float a3 = band + a2 * (1f - band); float c3 = a3 > 1e-4f ? (1f * band + c2 * a2 * (1f - band)) / a3 : 1f;
                    px[y * n + x] = new Color(c3, c3, c3, a3);
                }
            t.SetPixels(px); t.Apply(true, false);
            texCache["dashring"] = t;
            return t;
        }

        public static Texture2D SoftCircle()
        {
            if (texCache.TryGetValue("soft", out var c)) return c;
            int n = 64;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2 - 1, dy = (y + 0.5f) / n * 2 - 1;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(1 - d);
                    a = a * a * (3 - 2 * a);
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(true, false);
            texCache["soft"] = t;
            return t;
        }

        /// <summary>Transparent center, opaque edges (screen-edge damage vignette).</summary>
        public static Texture2D Vignette()
        {
            if (texCache.TryGetValue("vignette", out var c)) return c;
            int n = 128;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2 - 1, dy = (y + 0.5f) / n * 2 - 1;
                    float d = Mathf.Sqrt(dx * dx * 0.8f + dy * dy * 0.8f);
                    float a = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((d - 0.55f) / 0.6f));
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(true, false);
            texCache["vignette"] = t;
            return t;
        }

        public static Texture2D HardCircle()
        {
            if (texCache.TryGetValue("hard", out var c)) return c;
            int n = 64;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2 - 1, dy = (y + 0.5f) / n * 2 - 1;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01((1 - d) * n * 0.5f);
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(true, false);
            texCache["hard"] = t;
            return t;
        }

        public static Texture2D RingTex(float thickness = 0.16f)
        {
            string key = "ring" + thickness;
            if (texCache.TryGetValue(key, out var c)) return c;
            int n = 128;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = (x + 0.5f) / n * 2 - 1, dy = (y + 0.5f) / n * 2 - 1;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float dist = Mathf.Abs(d - (1 - thickness)) - thickness * 0.85f;
                    float a = Mathf.Clamp01(-dist * n * 0.5f);
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(true, false);
            texCache[key] = t;
            return t;
        }

        // ------------------------------------------------------------------ UI sprites
        public static Sprite RoundRect(int radius = 22)
        {
            string key = "rr" + radius;
            if (spriteCache.TryGetValue(key, out var s)) return s;
            int n = radius * 2 + 4;
            var t = NewTex(n, n, false, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float cx = Mathf.Clamp(x + 0.5f, radius, n - radius), cy = Mathf.Clamp(y + 0.5f, radius, n - radius);
                    float d = Mathf.Sqrt((x + 0.5f - cx) * (x + 0.5f - cx) + (y + 0.5f - cy) * (y + 0.5f - cy));
                    float a = Mathf.Clamp01(radius - d + 0.5f);
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(false, false);
            s = Sprite.Create(t, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect, new Vector4(radius + 1, radius + 1, radius + 1, radius + 1));
            spriteCache[key] = s;
            return s;
        }

        public static Sprite Circle()
        {
            if (spriteCache.TryGetValue("circle", out var s)) return s;
            int n = 128;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = x + 0.5f - n * 0.5f, dy = y + 0.5f - n * 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    px[y * n + x] = new Color(1, 1, 1, Mathf.Clamp01(n * 0.5f - 1 - d + 0.5f));
                }
            t.SetPixels(px); t.Apply(true, false);
            s = Sprite.Create(t, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f);
            spriteCache["circle"] = s;
            return s;
        }

        public static Sprite Ring(float thicknessFrac = 0.14f)
        {
            string key = "ringS" + thicknessFrac;
            if (spriteCache.TryGetValue(key, out var s)) return s;
            int n = 128;
            var t = NewTex(n, n, true, TextureWrapMode.Clamp);
            var px = new Color[n * n];
            float R = n * 0.5f - 1, th = n * 0.5f * thicknessFrac;
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float dx = x + 0.5f - n * 0.5f, dy = y + 0.5f - n * 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy);
                    float a = Mathf.Clamp01(Mathf.Min(R - d + 0.5f, d - (R - th) + 0.5f));
                    px[y * n + x] = new Color(1, 1, 1, a);
                }
            t.SetPixels(px); t.Apply(true, false);
            s = Sprite.Create(t, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f);
            spriteCache[key] = s;
            return s;
        }

        public static Sprite FromTexture(Texture2D t)
        {
            return Sprite.Create(t, new Rect(0, 0, t.width, t.height), new Vector2(0.5f, 0.5f), 100f);
        }

        // ------------------------------------------------------------------ icons
        // The UI icons are renders of small toy-like 3D models (Editor/Icons/IconModels.cs), baked by IconStudio into
        // Resources/Icons/<Icon>.png (+ <Icon>_Locked.png for weapons / armor). One studio for all of them: same
        // light, camera angle, padding and drop shadow. Nothing is painted at runtime any more.
        static readonly Dictionary<Icon, Sprite> lockedCache = new Dictionary<Icon, Sprite>();
        static readonly HashSet<string> missingIcons = new HashSet<string>();

        static Color H(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return c; }

        public static Sprite Get(Icon icon)
        {
            if (iconCache.TryGetValue(icon, out var s) && s != null) return s;
            s = Resources.Load<Sprite>("Icons/" + icon);
            if (s == null)
            {
                if (missingIcons.Add(icon.ToString())) Debug.LogError("RoadGame: icon sprite missing: Resources/Icons/" + icon + ".png (bake with RoadGame > Icons > Bake UI Icons)");
                s = Circle();
            }
            iconCache[icon] = s;
            return s;
        }

        /// <summary>Dimmed, desaturated version for locked weapon / armor slots (falls back to the normal icon).</summary>
        public static Sprite GetLocked(Icon icon)
        {
            if (lockedCache.TryGetValue(icon, out var s) && s != null) return s;
            s = Resources.Load<Sprite>("Icons/" + icon + "_Locked");
            if (s == null) s = Get(icon);
            lockedCache[icon] = s;
            return s;
        }

        /// <summary>Armor piece icon: 0 = Bull Bar (spiked ram), 1 = Roof Plates.</summary>
        public static Icon ArmorIcon(int armorId) => armorId == 0 ? Icon.BullBar : armorId == 1 ? Icon.RoofPlates : Icon.Shield;

        public static Icon DamageIcon(DamageType t)
        {
            switch (t)
            {
                case DamageType.Smash: return Icon.Smash;
                case DamageType.Pierce: return Icon.Pierce;
                case DamageType.Blast: return Icon.Blast;
                default: return Icon.Gun;
            }
        }

        public static Icon RewardIcon(Reward r)
        {
            switch (r.kind)
            {
                case RewardKind.MaxHP: return Icon.Heart;
                case RewardKind.Regen: return Icon.Regen;
                case RewardKind.Damage: return DamageIcon(r.dmgType);
                case RewardKind.WeaponCopy: return DamageIcon(Content.Weapons[r.itemId].type);
                case RewardKind.ArmorCopy: return ArmorIcon(r.itemId);
                case RewardKind.Gems: return Icon.Gem;
            }
            return Icon.Star;
        }

        public static Color RewardColor(Reward r)
        {
            switch (r.kind)
            {
                case RewardKind.MaxHP: return H("#FF5A6A");
                case RewardKind.Regen: return H("#5BEA84");
                case RewardKind.Damage: return H("#9FD8FF");
                case RewardKind.WeaponCopy: return H("#FFB443");
                case RewardKind.ArmorCopy: return H("#8FC3FF");
                case RewardKind.Gems: return H("#D9A6FF");
            }
            return Color.white;
        }
    }
}
