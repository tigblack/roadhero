using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// Shared materials. Almost everything uses one stylized lit material + vertex colors (SRP Batcher friendly).
    /// The look is clean stylized 3D: soft wrapped light, zone-tinted soft shadows, broad highlights chosen per
    /// vertex (UV1 = gloss, metal), no outlines and no noise textures on objects.
    /// </summary>
    public static class Mats
    {
        public static Shader ToonShader { get; private set; }
        public static Shader UnlitShader { get; private set; }

        public static Material Toon;          // props, characters, car details
        public static Material CarPaint;      // player car body: cleaner, less dust
        public static Material Flash;         // hit flash
        public static Material Burnt;         // destroyed wreck look
        public static Material ToonFlat;      // small ground decor (no rim, no dust)
        public static Material Ground;        // sand with the clean detail texture
        public static Material UnlitAlpha;    // soft particles
        public static Material UnlitAdd;      // additive glow
        public static Material RingAdd;       // additive ring
        public static Material RingAlpha;     // alpha ring (telegraphs)
        public static Material Rope;          // harpoon rope
        public static Material Shadow;        // soft contact shadow decal under actors
        public static Material TireTrack;

        static readonly Dictionary<int, Material> roadMats = new Dictionary<int, Material>();
        static bool inited;

        public static void Reset()
        {
            inited = false;
            roadMats.Clear();
        }

        public static void Init()
        {
            if (inited && Toon != null) return;
            inited = true;
            ToonShader = Resources.Load<Shader>("Shaders/RoadToon");
            UnlitShader = Resources.Load<Shader>("Shaders/RoadUnlit");
            if (ToonShader == null) ToonShader = Shader.Find("RoadGame/Toon");
            if (UnlitShader == null) UnlitShader = Shader.Find("RoadGame/Unlit");
            if (ToonShader == null) { Debug.LogError("RoadGame: stylized shader missing, falling back to URP Lit"); ToonShader = Shader.Find("Universal Render Pipeline/Lit"); }

            Toon = NewLit("Toon");
            Surface(Toon, 0.38f, 0.74f, 0.75f);

            CarPaint = NewLit("CarPaint");
            Surface(CarPaint, 0.06f, 0.86f, 0.55f);
            CarPaint.SetFloat("_SpecStrength", 1.15f);
            CarPaint.SetColor("_RimColor", new Color(0.86f, 0.93f, 1f, 0.16f));

            Flash = NewLit("Flash");
            Surface(Flash, 0.38f, 0.74f, 0.75f);
            Flash.SetColor("_FlashColor", new Color(1f, 0.96f, 0.86f, 0.6f));   // short warm flash: brightens the colors, keeps them

            Burnt = NewLit("Burnt");
            Surface(Burnt, 0.5f, 0.7f, 0.75f);
            Burnt.SetColor("_BaseColor", new Color(0.5f, 0.46f, 0.44f, 1f));
            Burnt.SetFloat("_Saturation", 0.35f);
            Burnt.SetFloat("_GlossMul", 0.25f);

            ToonFlat = NewLit("ToonFlat");
            Surface(ToonFlat, 0f, 0.8f, 0.45f);
            ToonFlat.SetColor("_RimColor", new Color(1, 1, 1, 0));
            ToonFlat.SetFloat("_SpecStrength", 0.4f);

            Ground = NewLit("Ground");
            Ground.SetTexture("_BaseMap", Tex.GroundDetail(7));
            Ground.SetFloat("_WorldUV", 1f / Tex.GroundTileMeters);
            FlatSurface(Ground);

            UnlitAlpha = NewUnlit("UnlitAlpha", Tex.SoftCircle(), false);
            UnlitAdd = NewUnlit("UnlitAdd", Tex.SoftCircle(), true);
            RingAdd = NewUnlit("RingAdd", Tex.RingTex(0.12f), true);
            RingAlpha = NewUnlit("RingAlpha", Tex.RingTex(0.1f), false);
            Rope = NewUnlit("Rope", null, false);
            Rope.SetFloat("_ZWrite", 1f);
            Rope.renderQueue = (int)RenderQueue.Geometry + 10;
            Shadow = NewUnlit("ContactShadow", Tex.SoftCircle(), false);
            Shadow.SetColor("_BaseColor", new Color(0.24f, 0.17f, 0.2f, 0.32f));
            Shadow.renderQueue = (int)RenderQueue.Transparent - 50;
            TireTrack = NewUnlit("TireTrack", null, false);
            TireTrack.renderQueue = (int)RenderQueue.Transparent - 60;
        }

        /// <summary>Object surface params: painted dust gradient near the ground, soft ground contact occlusion.</summary>
        static void Surface(Material m, float dust, float aoFloor, float aoHeight)
        {
            m.SetFloat("_DustAmount", dust);
            m.SetFloat("_AOFloor", aoFloor);
            m.SetFloat("_AOHeight", aoHeight);
            m.SetFloat("_ShadowStrength", 0.82f);
        }

        /// <summary>Ground / road: flat, matte, no highlight, no rim; only soft received shadows.</summary>
        static void FlatSurface(Material m)
        {
            m.SetColor("_RimColor", new Color(1, 1, 1, 0));
            m.SetFloat("_SpecStrength", 0f);
            m.SetFloat("_ReflStrength", 0f);
            m.SetFloat("_DustAmount", 0f);
            m.SetFloat("_AOFloor", 1f);
            m.SetFloat("_ShadowStrength", 0.72f);
        }

        static Material NewLit(string name)
        {
            var m = new Material(ToonShader) { name = name, enableInstancing = true };
            return m;
        }

        public static Material NewUnlit(string name, Texture tex, bool additive)
        {
            var m = new Material(UnlitShader) { name = name };
            if (tex != null) m.SetTexture("_BaseMap", tex);
            m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            m.SetFloat("_DstBlend", additive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat("_ZWrite", 0f);
            m.SetFloat("_Cull", (float)CullMode.Off);
            m.renderQueue = (int)RenderQueue.Transparent;
            return m;
        }

        public static Material Road(ZoneDef z)
        {
            if (roadMats.TryGetValue(z.index, out var m)) return m;
            m = NewLit("Road" + z.index);
            m.SetTexture("_BaseMap", Tex.Road(z.road, z.roadLine, z.roadEdge, 11 + z.index));
            FlatSurface(m);
            m.SetFloat("_ShadowStrength", 0.78f);
            roadMats[z.index] = m;
            return m;
        }

        /// <summary>Outlines were removed with the cel look; kept as a no-op for callers that still scale them.</summary>
        public static void ScaleOutlines(float screenHeightPx) { }

        static IEnumerable<Material> LitMaterials()
        {
            foreach (var m in new[] { Toon, CarPaint, Flash, Burnt, ToonFlat, Ground }) if (m != null) yield return m;
            foreach (var m in roadMats.Values) if (m != null) yield return m;
        }

        /// <summary>Zone shade tint (the color of soft shadows) + hemisphere fill multipliers.</summary>
        public static void SetMood(Color shade, Color fillSky, Color fillGround)
        {
            foreach (var m in LitMaterials()) m.SetColor("_ShadeColor", shade);
            Shader.SetGlobalColor("_ToonAmbientSky", fillSky);
            Shader.SetGlobalColor("_ToonAmbientGround", fillGround);
        }

        /// <summary>Procedural environment seen in reflections (sky gradient, horizon haze, ground) + dust tint.</summary>
        public static void SetEnvironment(Color zenith, Color horizon, Color ground, Color dust)
        {
            Shader.SetGlobalColor("_EnvZenith", zenith);
            Shader.SetGlobalColor("_EnvHorizon", horizon);
            Shader.SetGlobalColor("_EnvGround", ground);
            Shader.SetGlobalColor("_DustColor", dust);
        }

        public static void SetEnvironment(ZoneDef z) => ApplyZone(z, z, 1f);

        /// <summary>
        /// Whole zone look, blended between two zones (crossing a border): shadow tint, fill light, reflections,
        /// dust, haze and the sun tint. Every zone keeps its own consistent palette.
        /// </summary>
        public static void ApplyZone(ZoneDef a, ZoneDef b, float t)
        {
            Color L(Color x, Color y) => Color.Lerp(x, y, t);
            var shade = L(a.shade, b.shade);
            var ground = L(a.ground, b.ground);
            var sky = L(a.sky, b.sky);
            // fill: a little cool light from above, warm bounce from the sand below
            var fillSky = Color.Lerp(new Color(1.02f, 1.04f, 1.1f), sky, 0.18f); fillSky.a = 1f;
            var fillGround = Color.Lerp(new Color(1f, 0.94f, 0.86f), ground, 0.3f) * 1.04f; fillGround.a = 1f;
            SetMood(shade, fillSky, fillGround);
            var zen = Color.Lerp(new Color(0.56f, 0.66f, 0.8f), sky, 0.3f);
            var hor = Color.Lerp(sky, Color.white, 0.35f);
            var gnd = ground * 0.7f; gnd.a = 1f;
            var dust = Color.Lerp(ground, new Color(0.86f, 0.78f, 0.66f), 0.35f); dust.a = 1f;
            SetEnvironment(zen, hor, gnd, dust);
        }

        public static void SetShadowStrength(float s)
        {
            foreach (var m in LitMaterials()) m.SetFloat("_ShadowStrength", s);
        }
    }
}
