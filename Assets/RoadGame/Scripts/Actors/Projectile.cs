using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Enemy projectiles aimed at where the car will be: crossbow bolts and thrown spears are lobbed (dodgeable),
    /// pipe-gun / machine-gun bullets are fast glowing tracers, blunderbuss slugs burst on impact.
    /// </summary>
    public class Projectile : MonoBehaviour
    {
        static readonly Dictionary<ProjKind, Stack<Projectile>> pools = new Dictionary<ProjKind, Stack<Projectile>>();
        ProjKind kind;
        Vector3 from, to;
        float t, dur, arc, hitRadius;
        double dmg;

        /// <summary>Shots fired since start (test telemetry).</summary>
        public static int Fired;

        public static void ResetPool() { pools.Clear(); Fired = 0; }

        static Mesh MeshFor(ProjKind k)
        {
            switch (k)
            {
                case ProjKind.Bullet:
                    return Models.Cached("proj_bullet", b =>
                    {
                        b.smoothAngle = 0f;
                        var hot = new Color(1f, 0.85f, 0.45f, 0.05f);   // alpha < 1 = self-lit tracer
                        b.CylinderBetween(new Vector3(0, 0, -0.55f), new Vector3(0, 0, 0.15f), 0.035f, 5, hot, 0.06f);
                    });
                case ProjKind.Spear:
                    return Models.Cached("proj_spear", b =>
                    {
                        b.CylinderBetween(new Vector3(0, 0, -0.9f), new Vector3(0, 0, 0.6f), 0.03f, 8, Models.Hex("#7A4E2A"));
                        b.Material(0.8f, 1f);
                        b.Push(new Vector3(0, 0, 0.58f), Quaternion.Euler(90, 0, 0));
                        b.Lathe(new[] { new Vector2(0.03f, 0f), new Vector2(0.07f, 0.08f), new Vector2(0f, 0.32f) }, 8, Models.Hex("#C9D2DA"));
                        b.Pop();
                        b.Matte();
                    });
                case ProjKind.Acid:
                    return Models.Cached("proj_acid", b =>
                    {
                        // a gob of glowing bile with a trailing drip (alpha < 1 = self-lit)
                        b.Material(0.7f, 0f);
                        b.Sphere(Vector3.zero, new Vector3(0.15f, 0.15f, 0.18f), new Color(0.74f, 0.93f, 0.22f, 0.25f), 1);
                        b.Sphere(new Vector3(0, 0.02f, -0.17f), Vector3.one * 0.09f, new Color(0.62f, 0.86f, 0.18f, 0.35f), 1);
                        b.Sphere(new Vector3(0, 0.03f, -0.29f), Vector3.one * 0.05f, new Color(0.55f, 0.80f, 0.16f, 0.45f), 0);
                        b.Matte();
                    });
                case ProjKind.Spit:
                    return Models.Cached("proj_spit", b =>
                    {
                        b.smoothAngle = 0f;
                        b.Sphere(Vector3.zero, new Vector3(0.06f, 0.06f, 0.16f), new Color(0.78f, 0.96f, 0.26f, 0.15f), 1);
                        b.CylinderBetween(new Vector3(0, 0, -0.45f), new Vector3(0, 0, -0.05f), 0.03f, 5, new Color(0.62f, 0.88f, 0.2f, 0.3f), 0.05f);
                    });
                case ProjKind.Slug:
                    return Models.Cached("proj_slug", b =>
                    {
                        b.Material(0.6f, 0.8f);
                        b.Sphere(Vector3.zero, Vector3.one * 0.14f, Models.Hex("#4A4440"), 1);
                        b.Sphere(new Vector3(0, 0, -0.12f), Vector3.one * 0.09f, new Color(1f, 0.6f, 0.2f, 0.3f), 1);
                        b.Matte();
                    });
                default:
                    return Models.Cached("bolt", b =>
                    {
                        b.CylinderBetween(new Vector3(0, 0, -0.45f), new Vector3(0, 0, 0.35f), 0.035f, 4, Models.Hex("#7A4E2A"));
                        b.Push(new Vector3(0, 0, 0.35f), Quaternion.Euler(90, 0, 0));
                        b.Cone(Vector3.zero, 0.07f, 0.2f, 4, Models.Hex("#D5DAE0"));
                        b.Pop();
                        b.Box(new Vector3(0, 0, -0.42f), new Vector3(0.16f, 0.02f, 0.14f), Models.Hex("#E8E0D0"));
                    });
            }
        }

        public static void Fire(Vector3 from, Vector3 to, double dmg, ZoneDef z, ProjKind kind = ProjKind.Bolt)
        {
            if (!pools.TryGetValue(kind, out var pool)) { pool = new Stack<Projectile>(); pools[kind] = pool; }
            Fired++;
            Projectile p;
            while (pool.Count > 0 && pool.Peek() == null) pool.Pop();
            if (pool.Count > 0) p = pool.Pop();
            else
            {
                var go = Models.MeshGO("Proj_" + kind, MeshFor(kind), Mats.Toon, null, false);
                go.transform.localScale = Vector3.one * (kind == ProjKind.Bolt || kind == ProjKind.Acid ? 1.6f : kind == ProjKind.Spear ? 1.3f : 1.4f);
                p = go.AddComponent<Projectile>();
            }
            p.kind = kind;
            p.from = from;
            // aim at the car's level (it may be on a ramp, in a tunnel or in the air)
            float floorY = Game.I != null && Game.I.player != null ? Game.I.player.GroundY : 0f;
            p.to = new Vector3(to.x, floorY + 0.7f, to.z);
            p.dmg = dmg;
            p.t = 0;
            float dist = (p.to - from).magnitude;
            switch (kind)
            {
                case ProjKind.Bullet:
                case ProjKind.Spit: p.dur = Mathf.Max(0.06f, dist / 48f); p.arc = 0f; p.hitRadius = 1.8f; break;
                case ProjKind.Spear: p.dur = Mathf.Max(0.3f, dist / 19f); p.arc = 1.8f; p.hitRadius = 2.0f; break;
                case ProjKind.Slug: p.dur = Mathf.Max(0.15f, dist / 28f); p.arc = 0.5f; p.hitRadius = 2.4f; break;
                default: p.dur = Mathf.Max(0.25f, dist / 24f); p.arc = 1.2f; p.hitRadius = 2.0f; break;
            }
            p.transform.position = from;
            p.transform.rotation = Quaternion.LookRotation((p.to - from).sqrMagnitude > 1e-4f ? (p.to - from).normalized : Vector3.forward);
            p.gameObject.SetActive(true);
        }

        void Update()
        {
            if (Game.I == null || Game.I.player == null) { gameObject.SetActive(false); return; }
            t += Time.deltaTime / dur;
            float k = Mathf.Clamp01(t);
            var pos = Vector3.Lerp(from, to, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * arc;
            var prev = transform.position;
            // walls, tunnel lids and roofs stop shots: no hits through the ground or into a tunnel
            if (t > 0.02f && Ground.Blocked(prev, pos, out var wall))
            {
                Game.I.fx.Puff(wall.point, 0.35f);
                if (kind == ProjKind.Slug) Game.I.fx.Explosion(wall.point, 0.45f);
                if (kind == ProjKind.Acid || kind == ProjKind.Spit) Game.I.fx.AcidSplash(wall.point, kind == ProjKind.Acid ? 0.8f : 0.45f);
                Recycle();
                return;
            }
            transform.position = pos;
            var v = pos - prev;
            if (v.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(v.normalized);
            if (k < 1f) return;

            var player = Game.I.player;
            var d = player.Pos - to;
            bool sameLevel = Mathf.Abs(d.y + 0.7f) < 2f;
            d.y = 0;
            bool hit = player.Alive && sameLevel && d.magnitude < hitRadius;
            var fx = Game.I.fx;
            switch (kind)
            {
                case ProjKind.Slug:
                    fx.Explosion(to, 0.55f);
                    Game.I.sfx.Play(Sfx.Kind.Explode, to, 0.45f);
                    break;
                case ProjKind.Bullet:
                    if (hit) fx.Sparks(player.Pos + Vector3.up * 0.9f + Random.insideUnitSphere * 0.5f, false);
                    else fx.Puff(new Vector3(to.x, to.y - 0.6f, to.z), 0.25f);
                    break;
                case ProjKind.Acid:
                case ProjKind.Spit:
                    fx.AcidSplash(hit ? player.Pos + Vector3.up * 0.6f : new Vector3(to.x, to.y - 0.6f, to.z), kind == ProjKind.Acid ? 1f : 0.5f);
                    break;
                default:
                    fx.Puff(to, 0.5f);
                    break;
            }
            if (hit) player.TakeDamage(dmg, from);
            Recycle();
        }

        void Recycle()
        {
            gameObject.SetActive(false);
            if (!pools.TryGetValue(kind, out var pool)) { pool = new Stack<Projectile>(); pools[kind] = pool; }
            pool.Push(this);
        }
    }
}
