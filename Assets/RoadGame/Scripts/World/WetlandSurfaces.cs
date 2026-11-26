using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Driving data of the second zone (Toxic Wetlands): shallow pools, channels and the arena moat as one 0.5 m
    /// height grid (ArtSource/Levels/ToxicWetlands/scripts/tw_layout.py). The same grid built the Blender ground and
    /// water meshes, so the visible banks, the physics surface and the water volume agree. Every gameplay object of
    /// the zone (roads, spawns, structures, camps, the arena island) stands on dry, flat ground outside it.
    /// Water: surface at WaterLevel, bed down to 0.24 m below it; wheels ford it (WaterPhysics drag, no current).
    /// </summary>
    public static class WetlandSurfaces
    {
        const string ResourcePath = "Levels/ToxicWetlands_surfaces";
        static int nx, nz;
        static float x0, z0, step, level = -0.08f;
        static short[] heights;
        static byte[] toxicity;
        public static bool Active { get; private set; }
        public static float WaterLevel => level;
        public static float MinX => x0;
        public static float MinZ => z0;
        public static float MaxX => x0 + (nx - 1) * step;
        public static float MaxZ => z0 + (nz - 1) * step;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void Reset() { Active = false; }

        /// <summary>Call with DustFlatsSurfaces.Plan: active only with the Toxic Wetlands art bundle.</summary>
        public static void Plan()
        {
            Reset();
            if (ImportedLevel.SuppressIntegration || Resources.Load<TextAsset>(ImportedLevel.WetlandsManifestResource) == null) return;
            if (heights == null && !Load()) return;
            Active = true;
        }

        static bool Load()
        {
            var asset = Resources.Load<TextAsset>(ResourcePath);
            if (asset == null) return false;
            var b = asset.bytes;
            try
            {
                if (b.Length < 28 || b[0] != 'T' || b[1] != 'W' || b[2] != 'S' || b[3] != 'F') throw new System.IO.InvalidDataException("header");
                nx = System.BitConverter.ToInt32(b, 4); nz = System.BitConverter.ToInt32(b, 8);
                x0 = System.BitConverter.ToSingle(b, 12); z0 = System.BitConverter.ToSingle(b, 16);
                step = System.BitConverter.ToSingle(b, 20); level = System.BitConverter.ToSingle(b, 24);
                int n = nx * nz;
                if (nx < 2 || nz < 2 || step <= 0f || b.Length != 28 + n * 3) throw new System.IO.InvalidDataException("size");
                heights = new short[n];
                System.Buffer.BlockCopy(b, 28, heights, 0, n * 2);
                toxicity = new byte[n];
                System.Buffer.BlockCopy(b, 28 + n * 2, toxicity, 0, n);
                return true;
            }
            catch (System.Exception e)
            {
                heights = null;
                Debug.LogError("RoadGame: invalid Toxic Wetlands surface data: " + e.Message);
                return false;
            }
            finally { Resources.UnloadAsset(asset); }
        }

        /// <summary>Bilinear height of the swamp ground (0 = the zone's flat ground) at x, z.</summary>
        public static float Height(float x, float z)
        {
            if (heights == null) return 0f;
            float fx = (x - x0) / step, fz = (z - z0) / step;
            if (fx < 0f || fz < 0f || fx > nx - 1 || fz > nz - 1) return 0f;
            int ix = Mathf.Min((int)fx, nx - 2), iz = Mathf.Min((int)fz, nz - 2);
            float tx = fx - ix, tz = fz - iz;
            int i = iz * nx + ix;
            float a = heights[i], c = heights[i + 1], d = heights[i + nx], e = heights[i + nx + 1];
            return ((a * (1f - tx) + c * tx) * (1f - tz) + (d * (1f - tx) + e * tx) * tz) * 0.001f;
        }

        /// <summary>Base ground height and normal inside the zone's pools and banks; false (0, up) elsewhere.</summary>
        public static bool TrySampleBase(float x, float z, out float h, out Vector3 normal)
        {
            h = 0f; normal = Vector3.up;
            if (!Active || z < z0 || z > MaxZ || x < x0 || x > MaxX) return false;
            h = Height(x, z);
            if (h >= -0.00001f) { h = 0f; return false; }
            const float e = 0.25f;
            float dx = (Height(x + e, z) - Height(x - e, z)) / (2f * e);
            float dz = (Height(x, z + e) - Height(x, z - e)) / (2f * e);
            normal = new Vector3(-dx, 1f, -dz).normalized;
            return true;
        }

        /// <summary>The water volume above the bed (still water: no current).</summary>
        public static bool TrySampleWater(float x, float z, out float bed)
        {
            bed = 0f;
            if (!Active || z < z0 || z > MaxZ || x < x0 || x > MaxX) return false;
            bed = Height(x, z);
            return bed < level - 0.002f;
        }

        /// <summary>0..1 toxicity of the water at x, z (leaking drums and outfall pipes nearby).</summary>
        public static float Toxicity(float x, float z)
        {
            if (!Active || toxicity == null) return 0f;
            int ix = Mathf.RoundToInt((x - x0) / step), iz = Mathf.RoundToInt((z - z0) / step);
            if (ix < 0 || iz < 0 || ix >= nx || iz >= nz) return 0f;
            return toxicity[iz * nx + ix] / 255f;
        }

        /// <summary>Paints the zone's water on the minimap (murky olive, toxic spots brighter).</summary>
        public static void PaintMinimapOverlay(Color32[] pixels, int width, int height, float xMin, float zMin, float pixelsPerM)
        {
            if (!Active || pixels == null || pixels.Length != width * height || pixelsPerM <= 0f) return;
            var water = new Color32(78, 96, 52, 255);
            var bank = new Color32(92, 86, 58, 255);
            var toxic = new Color32(150, 186, 64, 255);
            int r0 = Mathf.Max(0, Mathf.FloorToInt((z0 - zMin) * pixelsPerM));
            int r1 = Mathf.Min(height - 1, Mathf.CeilToInt((MaxZ - zMin) * pixelsPerM));
            int c0 = Mathf.Max(0, Mathf.FloorToInt((x0 - xMin) * pixelsPerM));
            int c1 = Mathf.Min(width - 1, Mathf.CeilToInt((MaxX - xMin) * pixelsPerM));
            for (int row = r0; row <= r1; row++)
            {
                float z = zMin + (row + 0.5f) / pixelsPerM;
                for (int col = c0; col <= c1; col++)
                {
                    float x = xMin + (col + 0.5f) / pixelsPerM;
                    float h = Height(x, z);
                    if (h >= level * 0.5f) continue;
                    int p = row * width + col;
                    if (h >= level) { pixels[p] = Color32.Lerp(pixels[p], bank, 0.5f); continue; }
                    pixels[p] = Toxicity(x, z) > 0.45f ? toxic : water;
                }
            }
        }
    }
}
