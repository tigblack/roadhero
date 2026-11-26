using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>Oriented rectangle on the XZ plane (yaw like a Unity Y rotation: local +Z = (sin yaw, cos yaw)).</summary>
    public struct ORect
    {
        public Vector2 c;
        public float cos, sin;
        public Vector2 half;

        public ORect(Vector3 center, float yawDeg, float halfX, float halfZ)
        {
            c = new Vector2(center.x, center.z);
            float a = yawDeg * Mathf.Deg2Rad;
            cos = Mathf.Cos(a); sin = Mathf.Sin(a);
            half = new Vector2(halfX, halfZ);
        }

        /// <summary>Axis-aligned rectangle from world min / max corners.</summary>
        public static ORect FromMinMax(float x0, float z0, float x1, float z1)
            => new ORect(new Vector3((x0 + x1) * 0.5f, 0, (z0 + z1) * 0.5f), 0f, Mathf.Abs(x1 - x0) * 0.5f, Mathf.Abs(z1 - z0) * 0.5f);

        public float Yaw => Mathf.Atan2(sin, cos) * Mathf.Rad2Deg;
        public Vector3 Center => new Vector3(c.x, 0, c.y);
        public Vector3 Forward => new Vector3(sin, 0, cos);
        public Vector3 Right => new Vector3(cos, 0, -sin);

        public Vector2 Local(float x, float z)
        {
            float dx = x - c.x, dz = z - c.y;
            return new Vector2(dx * cos - dz * sin, dx * sin + dz * cos);
        }

        public Vector3 World(float lx, float lz, float y)
            => new Vector3(c.x + lx * cos + lz * sin, y, c.y - lx * sin + lz * cos);

        public bool Contains(float x, float z, float pad = 0f)
        {
            var l = Local(x, z);
            return Mathf.Abs(l.x) <= half.x + pad && Mathf.Abs(l.y) <= half.y + pad;
        }

        /// <summary>Signed distance from a point to the rectangle edge (negative inside).</summary>
        public float Distance(float x, float z)
        {
            var l = Local(x, z);
            float dx = Mathf.Abs(l.x) - half.x, dz = Mathf.Abs(l.y) - half.y;
            float outside = new Vector2(Mathf.Max(dx, 0f), Mathf.Max(dz, 0f)).magnitude;
            return outside + Mathf.Min(Mathf.Max(dx, dz), 0f);
        }

        /// <summary>World-space AABB of the rectangle (xMin, zMin, xMax, zMax).</summary>
        public Vector4 Aabb
        {
            get
            {
                float ex = Mathf.Abs(cos) * half.x + Mathf.Abs(sin) * half.y;
                float ez = Mathf.Abs(sin) * half.x + Mathf.Abs(cos) * half.y;
                return new Vector4(c.x - ex, c.y - ez, c.x + ex, c.y + ez);
            }
        }
    }

    public enum SurfaceKind { Sand, Asphalt, Concrete, Metal }

    /// <summary>
    /// A drivable floor over an oriented rectangle: flat (h0 == h1) or a slope along local +Z with rounded ends.
    /// Floors can overlap (a tunnel under the surface, a plateau, a jump ramp): a body uses the highest floor
    /// that is not above it by more than a step, so every level keeps its own ground.
    /// </summary>
    public class FloorPiece
    {
        public string name;
        public ORect rect;
        public float h0, h1;               // height at local z = -half.z and +half.z
        public float easeIn = 0.2f;        // fraction of the length used to round into the slope (low end)
        public float easeOut = 0.2f;       // ... and out of it (high end); a jump ramp ends sharp at its lip
        public bool launch;                // jump ramp: the car flies off its high end
        public bool steady;                // jump ramp that never rolls the car (the first jump of the game)
        public float boost;                // jump ramp: minimum take-off speed (m/s) along the ramp
        public SurfaceKind surface = SurfaceKind.Concrete;
        public bool underground;           // part of an underground level (for targeting / AI / look)
        public bool enemyWalkable = true;
        /// <summary>Natural terrain (hills, bumps, mountain slopes): a fast car leaves the ground where the surface
        /// curves down faster than gravity can pull it (crests), instead of being glued to it.</summary>
        public bool crestAir;

        public float Length => rect.half.y * 2f;
        public float MaxH => Mathf.Max(h0, h1);
        public float MinH => Mathf.Min(h0, h1);

        /// <summary>Normalized position along the slope (0 at the low local -Z end).</summary>
        public float U(float lz) => Mathf.Clamp01((lz + rect.half.y) / Mathf.Max(0.01f, rect.half.y * 2f));

        public float Profile(float u)
        {
            float a = Mathf.Clamp(easeIn, 0f, 0.45f), b = Mathf.Clamp(easeOut, 0f, 0.45f);
            float m = 1f - 0.5f * a - 0.5f * b;             // area under the slope curve (normalizes to 1)
            float s;
            if (u < a) s = u * u / (2f * a);
            else if (u > 1f - b) s = (1f - 0.5f * a - 0.5f * b) - (1f - u) * (1f - u) / (2f * b);
            else s = u - 0.5f * a;
            return Mathf.Clamp01(s / m);
        }

        public float HeightLocal(float lz) => Mathf.Approximately(h0, h1) ? h0 : Mathf.Lerp(h0, h1, Profile(U(lz)));

        /// <summary>Slope dh / d(local z) at a local position.</summary>
        public float SlopeLocal(float lz)
        {
            if (Mathf.Approximately(h0, h1)) return 0f;
            const float e = 0.05f;
            return (HeightLocal(lz + e) - HeightLocal(lz - e)) / (2f * e);
        }

        public Vector3 NormalAt(float lz)
        {
            float s = SlopeLocal(lz);
            var g = rect.Forward * s;                        // world gradient of h
            return new Vector3(-g.x, 1f, -g.z).normalized;
        }

        /// <summary>Height at a local position (x across, y = local z along the slope). Terrain pieces vary in both.</summary>
        public virtual float Height(Vector2 l) => HeightLocal(l.y);

        /// <summary>Curved imported floors can refine the enclosing rectangle.</summary>
        public virtual bool Contains(Vector2 l) => Mathf.Abs(l.x) <= rect.half.x && Mathf.Abs(l.y) <= rect.half.y;

        /// <summary>Surface normal at a local position.</summary>
        public virtual Vector3 Normal(Vector2 l) => NormalAt(l.y);
    }

    /// <summary>
    /// A hill: a smooth elliptical mound over its rectangle (height 0 with zero slope at the rim, an optional flat
    /// top). Small ones make quick hops at speed, big ones are climbs with a view and a crest to fly off.
    /// </summary>
    public class MoundPiece : FloorPiece
    {
        public float top;              // height of the summit
        public float plateau;          // 0..0.8: fraction of the radius that is flat on top

        /// <summary>Normalized elliptical radius (0 at the centre, 1 at the rim).</summary>
        float Rho(Vector2 l) => Mathf.Sqrt((l.x * l.x) / (rect.half.x * rect.half.x) + (l.y * l.y) / (rect.half.y * rect.half.y));

        public override float Height(Vector2 l)
        {
            float rho = Rho(l);
            if (rho >= 1f) return 0f;
            float t = Mathf.Clamp01((rho - plateau) / (1f - plateau));
            float k = 1f - t * t;
            return top * k * k;
        }

        public override Vector3 Normal(Vector2 l)
        {
            float rho = Rho(l);
            if (rho >= 1f || rho <= plateau + 1e-4f) return Vector3.up;
            float t = (rho - plateau) / (1f - plateau);
            float dhdrho = top * -4f * t * (1f - t * t) / (1f - plateau);
            // d rho / d l = (lx / hx^2, lz / hz^2) / rho
            float gx = dhdrho * l.x / (rect.half.x * rect.half.x) / rho;
            float gz = dhdrho * l.y / (rect.half.y * rect.half.y) / rho;
            var g = rect.Right * gx + rect.Forward * gz;
            return new Vector3(-g.x, 1f, -g.z).normalized;
        }
    }

    /// <summary>
    /// The layered ground of the world: the flat surface (y = 0) with holes cut into it, plus any number of extra
    /// floors (ramps, tunnels, garages, plateaus). Used by the car, enemies, projectiles, effects and the shader
    /// (dust / contact occlusion are measured from the floor, not from y = 0).
    /// </summary>
    public static class Ground
    {
        public const float StepUp = 0.6f;          // a floor this much above a body is still "its" floor (curbs, slopes)
        public const float LevelGap = 2.6f;        // bodies further apart vertically are on different levels
        public const float Void = -60f;

        static readonly List<FloorPiece> pieces = new List<FloorPiece>();
        static readonly List<Vector4> pieceAabb = new List<Vector4>();
        static readonly List<ORect> holes = new List<ORect>();
        static readonly List<Vector4> holeAabb = new List<Vector4>();
        public static IReadOnlyList<FloorPiece> Pieces => pieces;
        public static IReadOnlyList<ORect> Holes => holes;

        /// <summary>Colliders of walls / ceilings / lids that block sight and shots (physics layer).</summary>
        public const int BlockerLayer = 29;

        /// <summary>
        /// Walls along the edge of a raised floor (their owner), their top just under it: they stop a car down below.
        /// A car on the owner floor - or on any floor at least as high as a ledge's top - ignores it: it drives off the
        /// edge, its long body overhanging the edge never snags on a ledge's top, and it keeps ignoring the ledges of the
        /// floor it took off from while it falls past them, until it is clear of them again.
        /// </summary>
        public static readonly List<(Collider c, FloorPiece owner, float top)> Ledges = new List<(Collider, FloorPiece, float)>();
        public static void AddLedge(Collider c, FloorPiece owner, float top) { if (c != null && owner != null) Ledges.Add((c, owner, top)); }
        public static int BlockerMask => 1 << BlockerLayer;

        public struct Hit
        {
            public float h;
            public Vector3 normal;
            public FloorPiece piece;
            public bool valid;
            public bool Underground => piece != null && piece.underground;
            public SurfaceKind Surface => piece != null ? piece.surface : SurfaceKind.Sand;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Clear(); }

        public static void Clear()
        {
            DustFlatsSurfaces.Reset();
            WetlandSurfaces.Reset();
            AshenSurfaces.Reset();
            pieces.Clear(); pieceAabb.Clear(); holes.Clear(); holeAabb.Clear(); Ledges.Clear();
            ShaderRegions.Clear();
        }

        public static FloorPiece Add(FloorPiece p)
        {
            pieces.Add(p);
            pieceAabb.Add(p.rect.Aabb);
            return p;
        }

        public static void AddHole(ORect r)
        {
            holes.Add(r);
            holeAabb.Add(r.Aabb);
        }

        static bool InAabb(Vector4 a, float x, float z, float pad = 0f) => x >= a.x - pad && x <= a.z + pad && z >= a.y - pad && z <= a.w + pad;

        public static bool InHole(float x, float z)
        {
            for (int i = 0; i < holes.Count; i++)
                if (InAabb(holeAabb[i], x, z) && holes[i].Contains(x, z)) return true;
            return false;
        }

        /// <summary>The floor under (x, z) for a body at height refY: the highest floor not above refY + stepUp.</summary>
        public static Hit Sample(float x, float z, float refY, float stepUp = StepUp)
        {
            var hit = new Hit { h = Void, normal = Vector3.up, valid = false };
            float limit = refY + stepUp;
            float baseHeight = 0f;
            Vector3 baseNormal = Vector3.up;
            if (!DustFlatsSurfaces.TrySampleBase(x, z, out baseHeight, out baseNormal)
                && !WetlandSurfaces.TrySampleBase(x, z, out baseHeight, out baseNormal))
                AshenSurfaces.TrySampleBase(x, z, out baseHeight, out baseNormal);
            if (baseHeight <= limit && !InHole(x, z))
            {
                hit.h = baseHeight; hit.normal = baseNormal; hit.valid = true;
            }
            for (int i = 0; i < pieces.Count; i++)
            {
                if (!InAabb(pieceAabb[i], x, z)) continue;
                var p = pieces[i];
                var l = p.rect.Local(x, z);
                if (!p.Contains(l)) continue;
                float h = p.Height(l);
                if (h > limit) continue;
                if (!hit.valid || h > hit.h + 1e-4f)
                {
                    hit.h = h; hit.valid = true; hit.piece = p;
                    hit.normal = p.Normal(l);
                }
            }
            return hit;
        }

        public static float HeightAt(Vector3 p) => Sample(p.x, p.z, p.y).h;

        /// <summary>True when a floor stands more than margin above y at (x, z): the point is inside a hill or a massif.</summary>
        public static bool CoveredAbove(float x, float z, float y, float margin = 1f)
        {
            for (int i = 0; i < pieces.Count; i++)
            {
                if (!InAabb(pieceAabb[i], x, z)) continue;
                var p = pieces[i];
                var l = p.rect.Local(x, z);
                if (!p.Contains(l)) continue;
                if (p.Height(l) > y + margin) return true;
            }
            return false;
        }

        /// <summary>Height of the floor a body standing at p uses (falls back to p.y when there is no floor).</summary>
        public static float FloorY(Vector3 p)
        {
            var h = Sample(p.x, p.z, p.y);
            return h.valid ? h.h : p.y;
        }

        public static bool SameLevel(Vector3 a, Vector3 b) => Mathf.Abs(a.y - b.y) < LevelGap;

        /// <summary>True when a segment is blocked by a wall / ceiling / lid (sight lines, shots).</summary>
        public static bool Blocked(Vector3 from, Vector3 to)
        {
            return Physics.Linecast(from, to, out _, BlockerMask, QueryTriggerInteraction.Ignore);
        }

        public static bool Blocked(Vector3 from, Vector3 to, out RaycastHit hit)
        {
            return Physics.Linecast(from, to, out hit, BlockerMask, QueryTriggerInteraction.Ignore);
        }

        // ------------------------------------------------------------------ shader: floor regions for dust / contact AO
        /// <summary>Underground floors handed to the stylized shader so dust and contact occlusion are measured from them.</summary>
        public static class ShaderRegions
        {
            public const int Max = 12;
            static readonly Vector4[] a = new Vector4[Max];
            static readonly Vector4[] b = new Vector4[Max];
            static int count;

            public static void Clear() { count = 0; }

            public static void Add(FloorPiece p)
            {
                if (count >= Max) { Debug.LogWarning("RoadGame: too many shader floor regions"); return; }
                a[count] = new Vector4(p.rect.c.x, p.rect.c.y, p.rect.cos, p.rect.sin);
                b[count] = new Vector4(p.rect.half.x, p.rect.half.y, p.h0, p.h1);
                count++;
            }

            public static void Upload()
            {
                Shader.SetGlobalVectorArray("_RGFloorA", a);
                Shader.SetGlobalVectorArray("_RGFloorB", b);
                Shader.SetGlobalFloat("_RGFloorCount", count);
            }
        }
    }
}
