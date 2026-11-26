using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// One piece of geometry that can hide the car from the top-down camera: a garage roof, a canopy, the ground lid
    /// over a tunnel, the above-ground part of a wall. It fades as a unit, so a long structure is split into pieces
    /// and only the piece in the way turns see-through.
    /// </summary>
    public class Occluder
    {
        public string name;
        public Renderer[] renderers;
        public Bounds bounds;                  // occluding volume (world AABB)
        public float minAlpha = 0.24f;
        public bool onlyWhenBelow;             // lids / roofs: only hide things under them (a car driving on top keeps them solid)
        public float reach = 1f;               // scales the soft radius around the line of sight (walls: only when really in the way)
        public float alpha = 1f;
        public float target = 1f;
        public float weight;                   // 0..1 how much it is in the way this frame (debug / tests)
        public bool overCar;                   // on the camera's line to the car this frame

        Material[][] originals;
        Material[][] fadedSets;
        ShadowCastingMode[] shadowModes;
        bool shadowsOff;
        readonly List<Material> fadedMats = new List<Material>();
        readonly List<Material> fadedSources = new List<Material>();
        bool usingFaded;

        public bool Faded => usingFaded;

        public void Init()
        {
            originals = new Material[renderers.Length][];
            shadowModes = new ShadowCastingMode[renderers.Length];
            for (int i = 0; i < renderers.Length; i++)
            {
                originals[i] = renderers[i] != null ? renderers[i].sharedMaterials : new Material[0];
                shadowModes[i] = renderers[i] != null ? renderers[i].shadowCastingMode : ShadowCastingMode.On;
            }
            fadedSets = null;
            usingFaded = false;
            shadowsOff = false;
        }

        static readonly int SrcBlend = Shader.PropertyToID("_SrcBlend"), DstBlend = Shader.PropertyToID("_DstBlend"),
            ZWrite = Shader.PropertyToID("_ZWrite"), AlphaId = Shader.PropertyToID("_Alpha"), Shade = Shader.PropertyToID("_ShadeColor");

        Material FadedFor(Material src)
        {
            if (src == null || !src.HasProperty(AlphaId)) return src;      // not the stylized shader: stays as it is
            int i = fadedSources.IndexOf(src);
            if (i >= 0) return fadedMats[i];
            // a private copy: the shared material (used by every other object with it) never changes
            var m = new Material(src) { name = src.name + "_Fade_" + name };
            m.SetFloat(SrcBlend, (float)BlendMode.SrcAlpha);
            m.SetFloat(DstBlend, (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat(ZWrite, 0f);
            m.renderQueue = (int)RenderQueue.Transparent + 20;   // after floor decals, rings and particles under it
            fadedSources.Add(src);
            fadedMats.Add(m);
            return m;
        }

        public void Apply()
        {
            bool wantFaded = alpha < 0.995f;
            if (wantFaded != usingFaded)
            {
                usingFaded = wantFaded;
                if (wantFaded && fadedSets == null)
                {
                    fadedSets = new Material[renderers.Length][];
                    for (int r = 0; r < renderers.Length; r++)
                    {
                        var o = originals[r];
                        fadedSets[r] = new Material[o.Length];
                        for (int k = 0; k < o.Length; k++) fadedSets[r][k] = FadedFor(o[k]);
                    }
                }
                for (int r = 0; r < renderers.Length; r++)
                    if (renderers[r] != null) renderers[r].sharedMaterials = wantFaded ? fadedSets[r] : originals[r];
            }
            // a see-through roof no longer throws its shadow over what it shows (a car under a faded lid sat in the dark);
            // it is back as soon as the piece is solid enough to be a roof again
            bool wantShadowsOff = alpha < 0.6f;
            if (wantShadowsOff != shadowsOff)
            {
                shadowsOff = wantShadowsOff;
                for (int r = 0; r < renderers.Length; r++)
                    if (renderers[r] != null) renderers[r].shadowCastingMode = wantShadowsOff ? ShadowCastingMode.Off : shadowModes[r];
            }
            if (usingFaded)
            {
                for (int k = 0; k < fadedMats.Count; k++)
                {
                    fadedMats[k].SetFloat(AlphaId, alpha);
                    if (fadedSources[k].HasProperty(Shade)) fadedMats[k].SetColor(Shade, fadedSources[k].GetColor(Shade));   // zone mood follows
                }
            }
        }

        public void Dispose()
        {
            foreach (var m in fadedMats) if (m != null) Object.Destroy(m);
            fadedMats.Clear(); fadedSources.Clear();
        }
    }

    /// <summary>
    /// Isometric-style see-through: every frame each occluder near the car measures how close it comes to the camera's
    /// line of sight to the car (and to nearby threats); the closer, the more transparent it gets. Weights are smooth in
    /// distance and alpha eases over time, so there is no popping or flicker at the edges of a garage or a tunnel, and any
    /// number of overlapping occluders fade together. Floors are never registered, so they stay opaque.
    /// </summary>
    public class OcclusionFader : MonoBehaviour
    {
        public static OcclusionFader I;
        readonly List<Occluder> occluders = new List<Occluder>();
        public IReadOnlyList<Occluder> All => occluders;

        struct Focus { public Vector3 p; public float r0, r1; }
        /// <summary>Most the faded pieces right over the car may cover together (about one faded roof).</summary>
        public const float MaxCoverOverCar = 0.24f;
        readonly List<Focus> focus = new List<Focus>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { I = null; }

        public static OcclusionFader Ensure()
        {
            if (I != null) return I;
            I = new GameObject("OcclusionFader").AddComponent<OcclusionFader>();
            return I;
        }

        public static Occluder Register(string name, IList<Renderer> renderers, Bounds bounds, bool onlyWhenBelow, float minAlpha = 0.24f)
        {
            var f = Ensure();
            var o = new Occluder { name = name, renderers = new Renderer[renderers.Count], bounds = bounds, onlyWhenBelow = onlyWhenBelow, minAlpha = minAlpha };
            for (int i = 0; i < renderers.Count; i++) o.renderers[i] = renderers[i];
            o.Init();
            f.occluders.Add(o);
            return o;
        }

        public static Occluder Register(string name, GameObject go, bool onlyWhenBelow, float minAlpha = 0.24f, Bounds? volume = null, float reach = 1f)
        {
            var rs = go.GetComponentsInChildren<Renderer>(true);
            var b = volume ?? Encapsulate(rs);
            var o = Register(name, rs, b, onlyWhenBelow, minAlpha);
            o.reach = reach;
            return o;
        }

        public static Bounds Encapsulate(IList<Renderer> rs)
        {
            var b = new Bounds();
            bool first = true;
            foreach (var r in rs)
            {
                if (r == null) continue;
                if (first) { b = r.bounds; first = false; } else b.Encapsulate(r.bounds);
            }
            return b;
        }

        void OnDestroy()
        {
            foreach (var o in occluders) o.Dispose();
            if (I == this) I = null;
        }

        void LateUpdate()
        {
            var g = Game.I;
            if (g == null || g.player == null || g.cam == null) return;
            float dt = Time.deltaTime;
            var cam = g.cam.transform.position;
            var car = g.player.Pos;

            // what must stay visible: the car (with a generous soft radius), the boss in a fight, close threats
            focus.Clear();
            focus.Add(new Focus { p = car + Vector3.up * 1.0f, r0 = 2.6f, r1 = 6.5f });
            var boss = g.EngagedBoss;
            if (boss != null && Ground.SameLevel(boss.Pos, car))
            {
                // the boss is revealed once the fight is on (or right next to it), not from the far end of a tunnel
                var bd = boss.Pos - car; bd.y = 0f;
                // ...or when the car can actually see it (e.g. through the hangar's doorway): then its bar shows too
                if (boss.Engaged || bd.sqrMagnitude < 18f * 18f || (bd.sqrMagnitude < 38f * 38f && World.InSight(car, boss)))
                    focus.Add(new Focus { p = boss.Pos + Vector3.up * 2f, r0 = 3.5f, r1 = 7f });
            }
            if (World.I != null)
            {
                int added = 0;
                var list = World.I.activeTargets;
                for (int i = 0; i < list.Count && added < 3; i++)
                {
                    var t = list[i];
                    if (t == null || !t.IsEnemy || t.IsBoss || !t.Targetable) continue;
                    var d = t.Pos - car;
                    if (Mathf.Abs(d.y) > Ground.LevelGap || d.x * d.x + d.z * d.z > 14f * 14f) continue;
                    focus.Add(new Focus { p = t.Pos + Vector3.up * 1f, r0 = 1.2f, r1 = 3f });
                    added++;
                }
            }

            // pieces right over the car (on the camera's line to it): counted first, so that several of them together
            // (a lid under a pipeline, a roof over a beam) never veil the car more than one faded roof would
            var carFocus = focus[0].p;
            int over = 0;
            for (int i = 0; i < occluders.Count; i++)
            {
                var o = occluders[i];
                o.overCar = o.bounds.SqrDistance(car) < 60f * 60f && !(o.onlyWhenBelow && carFocus.y > o.bounds.max.y - 0.15f)
                            && SegmentBoxDistance(cam, carFocus, o.bounds) <= 0f;
                if (o.overCar) over++;
            }
            float stackCap = over >= 2 ? 1f - Mathf.Pow(1f - MaxCoverOverCar, 1f / over) : 1f;
            for (int i = 0; i < occluders.Count; i++)
            {
                var o = occluders[i];
                float w = 0f;
                var bd = o.bounds;
                // broad phase: only occluders around the car matter
                if (bd.SqrDistance(car) < 60f * 60f)
                {
                    for (int f = 0; f < focus.Count && w < 1f; f++)
                    {
                        var fc = focus[f];
                        if (o.onlyWhenBelow && fc.p.y > bd.max.y - 0.15f) continue;
                        float d = SegmentBoxDistance(cam, fc.p, bd);
                        float r0 = fc.r0 * o.reach, r1 = Mathf.Max(r0 + 0.5f, fc.r1 * o.reach);
                        w = Mathf.Max(w, 1f - Smooth01((d - r0) / (r1 - r0)));
                    }
                }
                o.weight = w;
                o.target = Mathf.Lerp(1f, o.minAlpha, w);
                if (o.overCar) o.target = Mathf.Min(o.target, Mathf.Max(0.04f, stackCap));
                float rate = o.target < o.alpha ? 7f : 4.5f;   // out quickly, back in a little slower
                o.alpha = Mathf.Lerp(o.alpha, o.target, 1f - Mathf.Exp(-rate * dt));
                if (Mathf.Abs(o.alpha - o.target) < 0.004f) o.alpha = o.target;
                o.Apply();
            }
        }

        static float Smooth01(float x) { x = Mathf.Clamp01(x); return x * x * (3f - 2f * x); }

        /// <summary>Distance between the camera-to-focus segment and a box (0 when the segment passes through it).</summary>
        public static float SegmentBoxDistance(Vector3 a, Vector3 b, Bounds box)
        {
            var dir = b - a;
            float len = dir.magnitude;
            if (len < 1e-4f) return Mathf.Sqrt(box.SqrDistance(a));
            if (box.IntersectRay(new Ray(a, dir / len), out float hitD) && hitD <= len) return 0f;
            // only the stretch near the focus can be close to an occluder around it: sample the last 24 m
            float best = float.MaxValue;
            float start = Mathf.Max(0f, 1f - 24f / len);
            const int N = 18;
            for (int k = 0; k <= N; k++)
            {
                float t = Mathf.Lerp(start, 1f, k / (float)N);
                float d2 = box.SqrDistance(a + dir * t);
                if (d2 < best) best = d2;
            }
            return Mathf.Sqrt(best);
        }
    }
}
