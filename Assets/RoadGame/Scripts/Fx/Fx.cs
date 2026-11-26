using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>All particle effects: a handful of world-space systems fed with Emit() calls.</summary>
    public class Fx : MonoBehaviour
    {
        ParticleSystem sparks, puffs, flashes, debris, fire, smoke, heal, rings;

        public static Fx Create()
        {
            var go = new GameObject("Fx");
            var f = go.AddComponent<Fx>();
            f.Build();
            return f;
        }

        static Gradient Fade(Color a, Color b, float startAlpha = 1f)
        {
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(a, 0), new GradientColorKey(b, 1) },
                      new[] { new GradientAlphaKey(startAlpha, 0), new GradientAlphaKey(startAlpha * 0.8f, 0.4f), new GradientAlphaKey(0, 1) });
            return g;
        }

        ParticleSystem NewSystem(string name, Material mat, int max, float gravity, bool stretch = false, Mesh mesh = null)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = true;
            main.maxParticles = max;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = gravity;
            main.startSpeed = 0;
            main.startLifetime = 1f;
            var em = ps.emission; em.rateOverTime = 0;
            var sh = ps.shape; sh.enabled = false;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            if (mesh != null) { r.renderMode = ParticleSystemRenderMode.Mesh; r.mesh = mesh; r.alignment = ParticleSystemRenderSpace.World; }
            else if (stretch) { r.renderMode = ParticleSystemRenderMode.Stretch; r.velocityScale = 0.05f; r.lengthScale = 1.6f; }
            else r.renderMode = ParticleSystemRenderMode.Billboard;
            ps.Play();
            return ps;
        }

        void Build()
        {
            sparks = NewSystem("Sparks", Mats.UnlitAdd, 300, 1.4f, true);
            var col = sparks.colorOverLifetime; col.enabled = true; col.color = Fade(new Color(1f, 0.95f, 0.6f), new Color(1f, 0.45f, 0.1f));
            var sz = sparks.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0, 1, 1, 0.2f));

            flashes = NewSystem("Flashes", Mats.UnlitAdd, 40, 0f);
            col = flashes.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, new Color(1f, 0.8f, 0.4f));
            sz = flashes.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.4f, 1, 1.3f));

            puffs = NewSystem("Puffs", Mats.UnlitAlpha, 400, -0.05f);
            col = puffs.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, Color.white, 0.55f);
            sz = puffs.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.5f, 1, 1.4f));
            var vel = puffs.limitVelocityOverLifetime; vel.enabled = true; vel.dampen = 0.12f; vel.limit = 0.5f;

            debris = NewSystem("Debris", Mats.NewUnlit("Chips", ChipTexture(), false), 300, 2.2f);
            sz = debris.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0.6f, 1, 1, 0));
            var rot = debris.rotationOverLifetime; rot.enabled = true; rot.z = new ParticleSystem.MinMaxCurve(-6f, 6f);
            var coll = debris.collision; coll.enabled = true; coll.type = ParticleSystemCollisionType.Planes; coll.SetPlane(0, MakePlane()); coll.bounce = 0.35f; coll.dampen = 0.4f; coll.lifetimeLoss = 0f;

            fire = NewSystem("Fire", Mats.UnlitAdd, 200, -0.2f);
            col = fire.colorOverLifetime; col.enabled = true; col.color = Fade(new Color(1f, 0.85f, 0.35f), new Color(0.9f, 0.25f, 0.05f));
            sz = fire.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.6f, 1, 1.2f));

            // light warm smoke that clears quickly: effects never hide the car or the targets for long
            smoke = NewSystem("Smoke", Mats.UnlitAlpha, 200, -0.25f);
            col = smoke.colorOverLifetime; col.enabled = true; col.color = Fade(new Color(0.42f, 0.38f, 0.36f), new Color(0.66f, 0.62f, 0.58f), 0.5f);
            sz = smoke.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.5f, 1, 1.4f));

            var plusTex = new Material(Mats.UnlitAdd);
            plusTex.SetTexture("_BaseMap", Tex.Get(Icon.Plus).texture);
            heal = NewSystem("Heal", plusTex, 80, -0.6f);
            col = heal.colorOverLifetime; col.enabled = true; col.color = Fade(new Color(0.6f, 1f, 0.6f), new Color(0.3f, 1f, 0.4f));

            rings = NewSystem("Rings", Mats.RingAdd, 30, 0f);
            var rr = rings.GetComponent<ParticleSystemRenderer>(); rr.renderMode = ParticleSystemRenderMode.HorizontalBillboard;
            col = rings.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, Color.white);
            sz = rings.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.2f, 1, 1f));
        }

        static Texture2D ChipTexture()
        {
            // small chunky square chip with a dark outline and a lit top edge
            int n = 32;
            var t = new Texture2D(n, n, TextureFormat.RGBA32, true) { wrapMode = TextureWrapMode.Clamp };
            var px = new Color[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float u = (x + 0.5f) / n * 2f - 1f, v = (y + 0.5f) / n * 2f - 1f;
                    float d = Mathf.Max(Mathf.Abs(u), Mathf.Abs(v));
                    Color c;
                    if (d > 0.92f) c = new Color(1, 1, 1, 0);
                    else if (d > 0.7f) c = new Color(0.25f, 0.2f, 0.18f, 1f);
                    else c = v > 0.25f ? new Color(1f, 1f, 1f, 1f) : new Color(0.8f, 0.8f, 0.8f, 1f);
                    px[y * n + x] = c;
                }
            t.SetPixels(px); t.Apply(true);
            return t;
        }

        Transform groundPlane;
        Transform MakePlane()
        {
            if (groundPlane != null) return groundPlane;
            groundPlane = new GameObject("FxGround").transform;
            groundPlane.SetParent(transform, false);
            groundPlane.position = Vector3.zero;
            groundPlane.rotation = Quaternion.identity;
            return groundPlane;
        }

        static void Emit(ParticleSystem ps, Vector3 pos, Vector3 vel, float size, Color c, float life, Vector3? rot3 = null)
        {
            var ep = new ParticleSystem.EmitParams { position = pos, velocity = vel, startSize = size, startColor = c, startLifetime = life, applyShapeToPosition = false };
            if (rot3.HasValue) ep.rotation3D = rot3.Value;
            ps.Emit(ep, 1);
        }

        public void Sparks(Vector3 p, bool crit)
        {
            int n = crit ? 14 : 8;
            for (int i = 0; i < n; i++)
            {
                var v = Random.onUnitSphere; v.y = Mathf.Abs(v.y) * 0.8f + 0.2f;
                Emit(sparks, p, v * Random.Range(5f, crit ? 12f : 8f), Random.Range(0.12f, 0.22f), Color.white, Random.Range(0.18f, 0.35f));
            }
            Emit(flashes, p, Vector3.zero, crit ? 2.4f : 1.5f, crit ? new Color(1f, 0.9f, 0.5f) : Color.white, 0.12f);
        }

        /// <summary>Cannon shot: muzzle flash sprite + gray smoke drifting out of the barrel.</summary>
        /// <summary>Muzzle glow + two smoke puffs; scale &lt; 1 for a small gun.</summary>
        public void MuzzleSmoke(Vector3 p, Vector3 dir, float scale = 1f)
        {
            Emit(flashes, p, Vector3.zero, Random.Range(1.2f, 1.6f) * scale, new Color(1f, 0.84f, 0.5f), 0.06f);
            for (int i = 0; i < 2; i++)
            {
                var v = dir * Random.Range(1.5f, 3.5f) + Random.insideUnitSphere * 0.4f + Vector3.up * 0.4f;
                Emit(puffs, p + dir * (0.15f + i * 0.14f) * scale, v, Random.Range(0.3f, 0.5f) * scale, new Color(0.86f, 0.84f, 0.8f), Random.Range(0.22f, 0.36f));
            }
        }

        /// <summary>Explosive shell hitting a target: flash, sparks spraying back, fireball, smoke.</summary>
        public void ShellImpact(Vector3 p, Vector3 back, bool crit)
        {
            Sparks(p, crit);
            Emit(fire, p, back * 1.2f + Vector3.up * 0.5f, crit ? 1.3f : 0.9f, Color.white, crit ? 0.18f : 0.13f);
            Emit(smoke, p, (back + Random.insideUnitSphere * 0.6f) * Random.Range(0.5f, 1.2f) + Vector3.up * 0.6f, Random.Range(0.45f, 0.75f), Color.white, Random.Range(0.28f, 0.45f));
            for (int i = 0; i < 3; i++)
            {
                var v = (back + Random.insideUnitSphere * 0.8f).normalized * Random.Range(3f, 6f) + Vector3.up * 2f;
                Emit(debris, p, v, Random.Range(0.12f, 0.22f), new Color(0.45f, 0.4f, 0.36f), Random.Range(0.5f, 0.9f), new Vector3(0, 0, Random.Range(0, 360f)));
            }
        }

        /// <summary>Overrun backfire: a short flame tongue out of a side pipe.</summary>
        public void Backfire(Vector3 p, Vector3 dir)
        {
            Emit(fire, p, dir * Random.Range(3f, 5.5f) + Vector3.up * 0.2f, Random.Range(0.32f, 0.5f), Color.white, Random.Range(0.08f, 0.13f));
            Emit(fire, p + dir * 0.2f, dir * Random.Range(2f, 3.5f), Random.Range(0.25f, 0.35f), Color.white, 0.1f);
            Emit(flashes, p, Vector3.zero, 0.8f, new Color(1f, 0.55f, 0.2f), 0.05f);
        }

        public void Puff(Vector3 p, float size)
        {
            // big puffs (slams, respawns, large wrecks) become a thin dust ring rolling outward: it reads as a
            // shockwave and keeps the middle - the boss, the car, the target - visible
            var c = new Color(0.86f, 0.74f, 0.58f, Mathf.Lerp(1f, 0.6f, Mathf.Clamp01((size - 1f) / 2.5f)));
            int n = Mathf.Clamp(Mathf.RoundToInt(5 + size * 3), 4, 18);
            bool ring = size > 1.6f;
            for (int i = 0; i < n; i++)
            {
                Vector2 d;
                if (ring) { float a = (i + Random.Range(-0.3f, 0.3f)) * Mathf.PI * 2f / n; d = new Vector2(Mathf.Cos(a), Mathf.Sin(a)); }
                else d = Random.insideUnitCircle;
                float r0 = ring ? size * 0.8f : size * 0.4f;
                var v = new Vector3(d.x, ring ? Random.Range(0.15f, 0.45f) : Random.Range(0.3f, 1f), d.y) * Random.Range(1.2f, 3f) * Mathf.Sqrt(size);
                Emit(puffs, p + new Vector3(d.x * r0, 0.3f, d.y * r0), v, Random.Range(0.6f, 1.1f) * Mathf.Sqrt(size) * (ring ? 0.85f : 1.2f), c, Random.Range(0.35f, 0.6f));
            }
        }

        public void Debris(Vector3 p, Color c, float size, int count)
        {
            for (int i = 0; i < count; i++)
            {
                var d = Random.insideUnitCircle;
                var v = new Vector3(d.x * 4f, Random.Range(4f, 8f), d.y * 4f) * Mathf.Sqrt(size);
                Emit(debris, p + Vector3.up * 0.5f, v, Random.Range(0.3f, 0.6f) * Mathf.Sqrt(size), Color.Lerp(c, Color.white, Random.Range(0f, 0.25f)), Random.Range(0.9f, 1.4f),
                    new Vector3(0, 0, Random.Range(0, 360f)));
            }
        }

        public void Explosion(Vector3 p, float size)
        {
            int n = Mathf.RoundToInt(10 * size);
            for (int i = 0; i < n; i++)
            {
                var v = Random.onUnitSphere; v.y = Mathf.Abs(v.y);
                Emit(fire, p + Vector3.up * 0.6f + v * 0.4f * size, v * Random.Range(2f, 5f) * size, Random.Range(0.8f, 1.6f) * size, Color.white, Random.Range(0.35f, 0.6f));
            }
            for (int i = 0; i < n * 0.45f; i++)
            {
                var v = Random.onUnitSphere; v.y = Mathf.Abs(v.y) + 0.4f;
                Emit(smoke, p + Vector3.up * 0.8f, v * Random.Range(1f, 2.5f) * size, Random.Range(1f, 1.6f) * size, Color.white, Random.Range(0.55f, 0.9f));
            }
            Emit(flashes, p + Vector3.up, Vector3.zero, 4f * size, new Color(1f, 0.8f, 0.4f), 0.18f);
            Ring(p, 3.5f * size, new Color(1f, 0.6f, 0.3f, 0.8f), 0.35f);
        }

        /// <summary>Acid spit lands (Bile Toad gob, Flesh Engine spray): a green splash ring, droplets and a short glow.</summary>
        public void AcidSplash(Vector3 p, float size)
        {
            Ring(p, 1.3f * size, new Color(0.66f, 0.95f, 0.22f, 0.85f), 0.3f);
            int n = Mathf.Clamp(Mathf.RoundToInt(6 * size + 2), 3, 10);
            for (int i = 0; i < n; i++)
            {
                var d = Random.insideUnitCircle;
                var v = new Vector3(d.x * 2.6f, Random.Range(2f, 4.2f), d.y * 2.6f) * Mathf.Sqrt(size);
                Emit(puffs, p + Vector3.up * 0.2f, v, Random.Range(0.25f, 0.45f) * Mathf.Sqrt(size), new Color(0.68f, 0.92f, 0.24f, 0.9f), Random.Range(0.3f, 0.5f));
            }
            Emit(flashes, p + Vector3.up * 0.4f, Vector3.zero, 1.5f * size, new Color(0.72f, 1f, 0.3f), 0.08f);
        }

        public void Slam(Vector3 p, float radius, bool fireBurst = false)
        {
            Ring(p, radius, fireBurst ? new Color(1f, 0.55f, 0.2f, 0.9f) : new Color(1f, 0.95f, 0.8f, 0.8f), 0.35f);
            Puff(p, radius * 0.6f);
            if (fireBurst) Explosion(p, Mathf.Max(0.6f, radius * 0.35f));
        }

        public void Ring(Vector3 p, float radius, Color c, float life)
        {
            // on the floor under the point (tunnels, ramps): rings lie flat on whatever level the effect happens
            Emit(rings, new Vector3(p.x, Ground.FloorY(p + Vector3.up * 0.5f) + 0.12f, p.z), Vector3.zero, radius * 2f, c, life);
        }

        public void HealSparkle(Vector3 p)
        {
            var d = Random.insideUnitCircle * 1.6f;
            Emit(heal, p + new Vector3(d.x, 0.6f, d.y), Vector3.up * Random.Range(0.8f, 1.6f), Random.Range(0.35f, 0.6f), Color.white, 0.9f);
        }

        /// <summary>Reward taken in: a soft glow on the car, a crisp ring and sparkles rising in the reward's color.</summary>
        public void AbsorbPop(Vector3 p, Color c)
        {
            var bright = Color.Lerp(c, Color.white, 0.35f);
            Emit(flashes, p + Vector3.up * 1.4f, Vector3.zero, 2.6f, bright, 0.16f);
            Ring(p, 2.8f, c, 0.32f);
            for (int i = 0; i < 9; i++)
            {
                var d = Random.insideUnitCircle * 0.9f;
                var v = new Vector3(d.x * 2f, Random.Range(4f, 7f), d.y * 2f);
                Emit(sparks, p + new Vector3(d.x, 1.2f, d.y), v, 0.2f, bright, Random.Range(0.25f, 0.4f));
            }
        }

        /// <summary>Harpoon bites into a wreck: quick white ring + a few sparks (distinct from gun hits).</summary>
        public void HookHit(Vector3 p)
        {
            Ring(p, 1.5f, new Color(1f, 0.97f, 0.9f, 0.9f), 0.2f);
            Emit(flashes, p + Vector3.up * 0.6f, Vector3.zero, 1.2f, new Color(1f, 0.96f, 0.85f), 0.08f);
            for (int i = 0; i < 5; i++)
            {
                var v = Random.onUnitSphere; v.y = Mathf.Abs(v.y) * 0.7f + 0.3f;
                Emit(sparks, p + Vector3.up * 0.6f, v * Random.Range(3f, 6f), 0.14f, Color.white, Random.Range(0.12f, 0.22f));
            }
        }

        // ---------------------------------------------------------------- continuous emitters attached to the car
        public static ParticleSystem MakeDust(Transform parent, Vector3 localPos)
        {
            var go = new GameObject("Dust");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true; main.playOnAwake = true;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.4f, 0.7f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 1.5f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.5f, 1.05f);
            main.startColor = new Color(0.9f, 0.8f, 0.66f, 0.42f);
            main.maxParticles = 120;
            main.gravityModifier = -0.05f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(1.8f, 0.1f, 0.3f);
            var em = ps.emission; em.rateOverTime = 0;
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, Color.white, 0.8f);
            var sz = ps.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.5f, 1, 1.5f));
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = Mats.UnlitAlpha;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            ps.Play();
            return ps;
        }

        /// <summary>White-gray tire smoke for burnouts and slides (rate driven by the car).</summary>
        public static ParticleSystem MakeTireSmoke(Transform parent, Vector3 localPos)
        {
            var go = new GameObject("TireSmoke");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true; main.playOnAwake = true;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.5f, 0.9f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.3f, 1.2f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.7f, 1.3f);
            main.startColor = new Color(0.9f, 0.89f, 0.87f, 0.4f);
            main.maxParticles = 160;
            main.gravityModifier = -0.04f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(1.9f, 0.1f, 0.4f);
            var em = ps.emission; em.rateOverTime = 0;
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, Color.white, 0.7f);
            var sz = ps.sizeOverLifetime; sz.enabled = true; sz.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.EaseInOut(0, 0.5f, 1, 1.8f));
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = Mats.UnlitAlpha;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            ps.Play();
            return ps;
        }

        public static ParticleSystem MakeExhaust(Transform parent, Vector3 localPos)
        {
            var go = new GameObject("Exhaust");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true; main.playOnAwake = true;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = new ParticleSystem.MinMaxCurve(0.3f, 0.6f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.5f, 1.2f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.25f, 0.5f);
            main.startColor = new Color(0.3f, 0.28f, 0.27f, 0.6f);
            main.maxParticles = 60;
            main.gravityModifier = -0.2f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 12f; sh.radius = 0.05f;
            go.transform.localRotation = Quaternion.Euler(0, 180, 0);
            main.startSpeed = new ParticleSystem.MinMaxCurve(1.2f, 2.4f);
            var em = ps.emission; em.rateOverTime = 4;
            var col = ps.colorOverLifetime; col.enabled = true; col.color = Fade(Color.white, Color.white, 0.8f);
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = Mats.UnlitAlpha;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            ps.Play();
            return ps;
        }
    }
}
