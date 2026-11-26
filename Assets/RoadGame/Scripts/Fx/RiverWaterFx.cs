using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// World-space water responses driven by the four real tire contacts, rather than proximity to the river.
    /// A bounded particle system and one reusable foam mesh cover entry, exit, spray and the expanding wake.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public sealed class RiverWaterFx : MonoBehaviour
    {
        const int RingCount = 16, Segments = 24, VerticesPerSegment = 6;
        const float SurfaceLift = 0.028f, MeshInterval = 1f / 24f;
        struct Ripple
        {
            public Vector3 center, flow;
            public float age, life, startRadius, expansion, strength;
        }
        public int SplashBursts { get; private set; }
        public int SprayParticles { get; private set; }
        public int RipplesEmitted { get; private set; }
        public int ActiveRipples { get; private set; }
        public int ActiveDroplets => spray != null ? spray.particleCount : 0;

        readonly Ripple[] ripples = new Ripple[RingCount];
        readonly bool[] wet = new bool[4], touched = new bool[4];
        readonly Vector3[] contactPositions = new Vector3[4], lastWetPositions = new Vector3[4];
        readonly WaterPhysics.Contact[] contacts = new WaterPhysics.Contact[4];
        readonly float[] sprayBudget = new float[4];
        readonly Vector3[] directions = new Vector3[Segments + 1];
        readonly Vector3[] vertices = new Vector3[RingCount * Segments * VerticesPerSegment];
        readonly Color[] colors = new Color[RingCount * Segments * VerticesPerSegment];
        Player player;
        GameObject effectsRoot;
        ParticleSystem spray;
        Mesh foamMesh;
        MeshRenderer foamRenderer;
        Material foamMaterial;
        Vector3 lastPosition;
        bool initialized, previouslyWet;
        int nextRipple, lastLandings;
        float wakeTimer, meshTimer, lastLandingTime = -10f;

        /// <summary>Load through Resources so the WebGL build retains this shader.</summary>
        public static Material CreateSurfaceMaterial(string name, Color artTint, float opacity)
        {
            var shader = Resources.Load<Shader>("Shaders/RiverWater");
            Material result = shader != null ? new Material(shader) : new Material(Mats.Toon);
            result.name = name;
            result.SetColor("_BaseColor", artTint);
            result.SetFloat("_Alpha", Mathf.Clamp(opacity < 0.99f ? opacity : 0.62f, 0.45f, 0.84f));
            result.renderQueue = (int)RenderQueue.Transparent - 80;
            if (shader == null) Debug.LogError("RoadGame: missing river water shader.");
            return result;
        }

        void Start()
        {
            player = GetComponent<Player>();
            if (player == null) { enabled = false; return; }
            Mats.Init();
            effectsRoot = new GameObject("RiverWaterEffects");
            var droplets = new GameObject("WheelSplashes");
            droplets.transform.SetParent(effectsRoot.transform, false);
            spray = droplets.AddComponent<ParticleSystem>();
            spray.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = spray.main;
            main.playOnAwake = false;
            main.loop = true;
            main.maxParticles = 256;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = 0.9f;
            main.startSpeed = 0f;
            main.startLifetime = 0.45f;
            var emission = spray.emission; emission.enabled = false;
            var shape = spray.shape; shape.enabled = false;
            var overColor = spray.colorOverLifetime; overColor.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(new Color(0.65f,0.84f,0.85f), 1f) },
                new[] { new GradientAlphaKey(0.85f, 0f), new GradientAlphaKey(0.8f, 0.45f), new GradientAlphaKey(0f, 1f) });
            overColor.color = gradient;
            var overSize = spray.sizeOverLifetime; overSize.enabled = true;
            overSize.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, 0.35f));
            var particleRenderer = droplets.GetComponent<ParticleSystemRenderer>();
            particleRenderer.sharedMaterial = Mats.UnlitAlpha;
            particleRenderer.renderMode = ParticleSystemRenderMode.Stretch;
            particleRenderer.velocityScale = 0.045f;
            particleRenderer.lengthScale = 1.4f;
            particleRenderer.shadowCastingMode = ShadowCastingMode.Off;
            particleRenderer.receiveShadows = false;
            spray.Play();

            var foam = new GameObject("RiverWake");
            foam.transform.SetParent(effectsRoot.transform, false);
            foamMesh = new Mesh { name = "PooledRiverRipples" };
            foamMesh.MarkDynamic();
            foam.AddComponent<MeshFilter>().sharedMesh = foamMesh;
            foamRenderer = foam.AddComponent<MeshRenderer>();
            foamMaterial = Mats.NewUnlit("RiverFoam", null, false);
            foamMaterial.renderQueue = (int)RenderQueue.Transparent - 65;
            foamRenderer.sharedMaterial = foamMaterial;
            foamRenderer.shadowCastingMode = ShadowCastingMode.Off;
            foamRenderer.receiveShadows = false;
            foamRenderer.lightProbeUsage = LightProbeUsage.Off;
            foamRenderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
            for (int i = 0; i <= Segments; i++)
            {
                float a = i * Mathf.PI * 2f / Segments;
                directions[i] = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
            }
            var indices = new int[RingCount * Segments * 12];
            for (int i = 0; i < RingCount * Segments; i++)
            {
                int v = i * VerticesPerSegment, t = i * 12;
                indices[t] = v; indices[t+1] = v+1; indices[t+2] = v+3;
                indices[t+3] = v+1; indices[t+4] = v+4; indices[t+5] = v+3;
                indices[t+6] = v+1; indices[t+7] = v+2; indices[t+8] = v+4;
                indices[t+9] = v+2; indices[t+10] = v+5; indices[t+11] = v+4;
            }
            foamMesh.vertices = vertices;
            foamMesh.colors = colors;
            foamMesh.triangles = indices;
            foamRenderer.enabled = false;
            lastPosition = player.Pos;
        }

        void LateUpdate()
        {
            if (player == null || spray == null) return;
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            bool landedNow = player.Landings != lastLandings;
            if (landedNow) { lastLandings = player.Landings; lastLandingTime = Time.time; }
            Vector3 position = player.Pos;
            bool teleported = (position - lastPosition).sqrMagnitude > 36f;
            lastPosition = position;
            if (teleported || (!DustFlatsSurfaces.Active && !WetlandSurfaces.Active))
            {
                Clear();
                initialized = false;
                return;
            }
            bool anyWet = false;
            int count = player.rig != null ? Mathf.Min(4, player.rig.wheels.Count) : 0;
            for (int i = 0; i < 4; i++)
            {
                wet[i] = false;
                if (i >= count) continue;
                Vector3 bottom = player.rig.wheels[i].position - Vector3.up * (i < 2 ? Models.CarFrontWheelR : Models.CarRearWheelR);
                if (!WaterPhysics.TryContact(bottom, out contacts[i]) || contacts[i].depth <= 0.012f) continue;
                wet[i] = true;
                touched[i] = true;
                anyWet = true;
                contactPositions[i] = new Vector3(bottom.x, contacts[i].level + SurfaceLift, bottom.z);
                lastWetPositions[i] = contactPositions[i];
            }
            Vector3 relative = player.Velocity - player.WaterFlow;
            float speed = relative.magnitude;
            bool entryConsumedLanding = false;
            if (initialized && anyWet != previouslyWet)
            {
                float impact = anyWet ? Mathf.Max(speed, player.WaterEntrySpeed) : speed * 0.55f;
                if (anyWet && player.LastLandingImpact > 1f && Time.time - lastLandingTime < 0.18f)
                    impact = Mathf.Max(impact, Mathf.Min(player.LastLandingImpact, 12f));
                if (impact > 0.65f)
                {
                    SplashBursts++;
                    entryConsumedLanding = anyWet && landedNow && player.LastLandingImpact > 1f;
                    for (int i = 0; i < count; i++)
                    {
                        Vector3 p = anyWet ? contactPositions[i] : lastWetPositions[i];
                        if ((anyWet && !wet[i]) || !touched[i] || (p - position).sqrMagnitude > 30f || !SurfaceContains(p)) continue;
                        Burst(p, i, relative, impact, anyWet ? 1f : 0.48f);
                    }
                }
            }
            // A vertical drop can wet the tires before they touch the bed. The subsequent landing still
            // displaces water even at zero planar speed; do not repeat an impact already handled on entry.
            if (landedNow && anyWet && player.LastLandingImpact > 1f && !entryConsumedLanding)
            {
                SplashBursts++;
                float impact = Mathf.Max(speed, Mathf.Min(player.LastLandingImpact, 12f));
                for (int i = 0; i < count; i++)
                    if (wet[i] && SurfaceContains(contactPositions[i])) Burst(contactPositions[i], i, relative, impact, 1f);
            }
            initialized = true;
            previouslyWet = anyWet;
            for (int i = 0; i < count; i++)
            {
                if (!wet[i] || !player.Alive || speed < 0.65f) { sprayBudget[i] = 0f; continue; }
                float rate = Mathf.Lerp(6f, 24f, Mathf.Clamp01(speed / 9f)) * Mathf.Lerp(0.4f, 1f, contacts[i].wetness);
                sprayBudget[i] += rate * dt;
                int amount = Mathf.Min(5, Mathf.FloorToInt(sprayBudget[i]));
                sprayBudget[i] -= amount;
                for (int j = 0; j < amount; j++) EmitDrop(contactPositions[i], i, relative, speed, false);
            }
            wakeTimer -= dt;
            if (anyWet && player.Alive && wakeTimer <= 0f)
            {
                bool moving = speed > 0.7f;
                wakeTimer = moving ? Mathf.Lerp(0.32f, 0.17f, Mathf.Clamp01(speed / 8f)) : 1.8f;
                // The rear tires draw an expanding V-like chain. At rest only one gentle ripple is emitted.
                for (int i = moving ? 2 : 0; i < count; i++)
                {
                    if (!wet[i]) continue;
                    AddRipple(contactPositions[i], contacts[i].flow, moving ? 0.48f : 0.16f,
                        moving ? 0.65f + Mathf.Min(speed, 10f) * 0.09f : 0.45f);
                    if (!moving) break;
                }
            }
            for (int i = 0; i < RingCount; i++)
            {
                if (ripples[i].life <= 0f) continue;
                ripples[i].age += dt;
                ripples[i].center += ripples[i].flow * (dt * 0.42f);
                if (ripples[i].age >= ripples[i].life) ripples[i].life = 0f;
            }
            meshTimer -= dt;
            if (meshTimer <= 0f) { meshTimer = MeshInterval; UpdateFoam(); }
        }

        void Burst(Vector3 p, int wheel, Vector3 relative, float impact, float amount)
        {
            int drops = Mathf.Clamp(Mathf.RoundToInt((6f + impact * 1.4f) * amount), 3, 22);
            for (int i = 0; i < drops; i++) EmitDrop(p, wheel, relative, impact, true);
            AddRipple(p, player.WaterFlow, 0.72f * amount, 1.1f + Mathf.Min(impact, 10f) * 0.10f);
        }

        void EmitDrop(Vector3 p, int wheel, Vector3 relative, float speed, bool burst)
        {
            float side = (wheel & 1) == 0 ? -1f : 1f;
            Vector3 outward = transform.right * side;
            float power = Mathf.Clamp(speed * 0.14f, 0.35f, 1.7f);
            var ep = new ParticleSystem.EmitParams
            {
                position = p + outward * Random.Range(0f, 0.12f),
                velocity = outward * Random.Range(0.7f, 1.6f) * power - relative * Random.Range(0.10f, 0.24f)
                    + Vector3.up * Random.Range(burst ? 1.1f : 0.65f, burst ? 2.6f : 1.7f) * power,
                startSize = Random.Range(0.07f, burst ? 0.17f : 0.13f),
                startColor = new Color(0.73f, 0.91f, 0.91f, 0.9f),
                startLifetime = Random.Range(0.24f, burst ? 0.62f : 0.45f),
                applyShapeToPosition = false
            };
            spray.Emit(ep, 1);
            SprayParticles++;
        }

        void AddRipple(Vector3 p, Vector3 flow, float strength, float expansion)
        {
            ripples[nextRipple] = new Ripple { center = p, flow = flow, age = 0f, life = 1.25f,
                startRadius = 0.16f, expansion = expansion, strength = strength };
            nextRipple = (nextRipple + 1) % RingCount;
            RipplesEmitted++;
        }

        static bool SurfaceContains(Vector3 p)
        {
            float lvl = WaterPhysics.LevelAt(p.x, p.z);
            if (float.IsNaN(lvl)) return false;
            p.y = lvl - 0.03f;
            return WaterPhysics.TryContact(p, out var contact) && contact.depth > 0.008f;
        }

        void UpdateFoam()
        {
            ActiveRipples = 0;
            for (int r = 0; r < RingCount; r++)
            {
                var ring = ripples[r];
                if (ring.life <= 0f)
                {
                    int end = (r + 1) * Segments * VerticesPerSegment;
                    for (int i = r * Segments * VerticesPerSegment; i < end; i++) colors[i] = Color.clear;
                    continue;
                }
                ActiveRipples++;
                float t = ring.age / ring.life;
                float radius = ring.startRadius + ring.age * ring.expansion;
                float halfWidth = Mathf.Lerp(0.065f, 0.11f, t);
                float alpha = ring.strength * (1f - t) * Mathf.Min(1f, ring.age * 12f);
                for (int s = 0; s < Segments; s++)
                {
                    int v = (r * Segments + s) * VerticesPerSegment;
                    Vector3 a = directions[s], b = directions[s + 1];
                    vertices[v] = ring.center + a * (radius - halfWidth);
                    vertices[v+1] = ring.center + a * radius;
                    vertices[v+2] = ring.center + a * (radius + halfWidth);
                    vertices[v+3] = ring.center + b * (radius - halfWidth);
                    vertices[v+4] = ring.center + b * radius;
                    vertices[v+5] = ring.center + b * (radius + halfWidth);
                    // Reject a whole segment if a corner leaves the actual wetted bed: no painted rings on the bank.
                    bool valid = SurfaceContains(vertices[v]) && SurfaceContains(vertices[v+2])
                        && SurfaceContains(vertices[v+3]) && SurfaceContains(vertices[v+5]);
                    var c = new Color(0.75f, 0.92f, 0.91f, valid ? alpha : 0f);
                    colors[v] = colors[v+2] = colors[v+3] = colors[v+5] = Color.clear;
                    colors[v+1] = colors[v+4] = c;
                }
            }
            foamRenderer.enabled = ActiveRipples > 0;
            if (ActiveRipples == 0) return;
            foamMesh.vertices = vertices;
            foamMesh.colors = colors;
            foamMesh.bounds = new Bounds(player.Pos, new Vector3(50f, 6f, 50f));
        }

        void Clear()
        {
            for (int i = 0; i < RingCount; i++) ripples[i].life = 0f;
            for (int i = 0; i < 4; i++) { sprayBudget[i] = 0f; touched[i] = false; }
            previouslyWet = false;
            ActiveRipples = 0;
            wakeTimer = 0f;
            if (spray != null) spray.Clear();
            if (foamRenderer != null) foamRenderer.enabled = false;
        }

        void OnDisable() { Clear(); }
        void OnDestroy()
        {
            if (effectsRoot != null) Destroy(effectsRoot);
            if (foamMesh != null) Destroy(foamMesh);
            if (foamMaterial != null) Destroy(foamMaterial);
        }
    }
}
