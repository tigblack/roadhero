using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>Procedural low-poly model library. Props live here; actors / world pieces in the other partial files.</summary>
    public static partial class Models
    {
        static readonly Dictionary<string, Mesh> meshCache = new Dictionary<string, Mesh>();
        static readonly MeshBuilder mb = new MeshBuilder();

        public static Color Hex(string h) { ColorUtility.TryParseHtmlString(h, out var c); return c; }
        static Color Glow(string h, float a = 0.35f) { var c = Hex(h); c.a = a; return c; }
        static Color Shade(Color c, float k) => new Color(c.r * k, c.g * k, c.b * k, c.a);

        // palette
        static readonly Color Wood = Hex("#A8703F"), WoodDark = Hex("#7A4E2A"), WoodLight = Hex("#C48A52");
        static readonly Color Rust = Hex("#A9552C"), RustDark = Hex("#7E3E20"), RustLight = Hex("#C26A3A");
        static readonly Color Metal = Hex("#8C949C"), MetalDark = Hex("#5C636B"), Chrome = Hex("#D5DAE0");
        static readonly Color TireC = Hex("#2E2A2A"), TireHub = Hex("#191717");
        static readonly Color ClothBeige = Hex("#E3D3B0"), ClothRed = Hex("#B9442E");
        static readonly Color Bone = Hex("#EFE6D1"), BoneDark = Hex("#CFC3A8");

        public static void Reset()
        {
            meshCache.Clear();
            flatQuad = null;
        }

        public static Mesh Cached(string key, Action<MeshBuilder> build)
        {
            if (meshCache.TryGetValue(key, out var m) && m != null) return m;
            mb.Clear();
            build(mb);
            m = mb.Build(key);
            meshCache[key] = m;
            return m;
        }

        public static GameObject MeshGO(string name, Mesh mesh, Material mat, Transform parent, bool castShadows = true)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = castShadows ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = true;
            r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            r.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            return go;
        }

        /// <summary>Creates any spawnable model (props, enemies, bosses).</summary>
        public static GameObject Create(ModelId id, int variant, ZoneDef zone, float scale = 1f)
        {
            switch (id)
            {
                case ModelId.Scav: case ModelId.Raider: case ModelId.Spearman: case ModelId.Crossbow: case ModelId.Brute:
                    return Humanoid(id, zone, scale);
                case ModelId.Buggy: return Buggy(zone);
                case ModelId.BossMammoth: return Mammoth(zone);
                case ModelId.BossBaron: return Baron(zone);
                case ModelId.BossColossus: return Colossus(zone);
                case ModelId.BossWarlord: return Warlord(zone);
            }
            int v = Mathf.Abs(variant) % 3;
            string key = id + "_" + v + "_" + zone.index;
            var mesh = Cached(key, b => BuildProp(b, id, v, zone));
            var root = new GameObject(id.ToString());
            var rig = root.AddComponent<Rig>();
            var body = MeshGO("Body", mesh, Mats.Toon, root.transform);
            rig.body = body.transform;
            rig.height = mesh.bounds.max.y;
            rig.CollectRenderers();
            rig.enabled = false;
            return root;
        }

        static void BuildProp(MeshBuilder b, ModelId id, int v, ZoneDef z)
        {
            var rnd = new System.Random((int)id * 977 + v * 131 + z.index * 7);
            float R() => (float)rnd.NextDouble();
            switch (id)
            {
                case ModelId.Cactus:
                    {
                        var g = Hex("#62A44A"); var gd = Hex("#4C8A3C");
                        float h = 2.3f + v * 0.25f;
                        b.Cylinder(Vector3.zero, 0.34f, h, 7, g, 0.27f, gd);
                        b.Sphere(new Vector3(0, h, 0), new Vector3(0.27f, 0.22f, 0.27f), g, 0);
                        float ay = 0.9f + v * 0.15f;
                        b.CylinderBetween(new Vector3(0.2f, ay, 0), new Vector3(0.78f, ay + 0.05f, 0), 0.17f, 6, gd);
                        b.Cylinder(new Vector3(0.78f, ay, 0), 0.17f, 0.85f, 6, g, 0.15f, gd);
                        b.Sphere(new Vector3(0.78f, ay + 0.85f, 0), new Vector3(0.15f, 0.13f, 0.15f), g, 0);
                        if (v != 1)
                        {
                            float by = 1.35f;
                            b.CylinderBetween(new Vector3(-0.2f, by, 0), new Vector3(-0.66f, by + 0.05f, 0.1f), 0.15f, 6, gd);
                            b.Cylinder(new Vector3(-0.66f, by, 0.1f), 0.15f, 0.6f, 6, g, 0.13f, gd);
                            b.Sphere(new Vector3(-0.66f, by + 0.6f, 0.1f), new Vector3(0.13f, 0.11f, 0.13f), g, 0);
                        }
                        if (v == 2) b.Sphere(new Vector3(0, h + 0.18f, 0), new Vector3(0.12f, 0.1f, 0.12f), Hex("#FF7FA8"), 0);
                        b.Rock(new Vector3(0.45f, 0.05f, 0.35f), new Vector3(0.3f, 0.16f, 0.26f), Hex("#B9875A"), 3);
                        break;
                    }
                case ModelId.DeadTree:
                    {
                        var t = Hex("#73513A"); var td = Hex("#5A3D2B");
                        b.Cylinder(Vector3.zero, 0.3f, 2.2f, 6, t, 0.15f, td);
                        b.CylinderBetween(new Vector3(0, 1.3f, 0), new Vector3(0.9f, 2.5f, 0.2f), 0.1f, 5, t, 0.04f);
                        b.CylinderBetween(new Vector3(0, 1.8f, 0), new Vector3(-0.8f, 2.9f, -0.1f), 0.09f, 5, t, 0.035f);
                        b.CylinderBetween(new Vector3(0, 2.1f, 0), new Vector3(0.15f, 3.3f, -0.5f), 0.08f, 5, t, 0.03f);
                        if (v > 0) b.CylinderBetween(new Vector3(0.5f, 1.95f, 0.1f), new Vector3(0.95f, 2.2f, -0.45f), 0.05f, 4, t, 0.02f);
                        for (int i = 0; i < 3; i++)
                        {
                            float a = i * 2.1f + v;
                            b.CylinderBetween(new Vector3(0, 0.3f, 0), new Vector3(Mathf.Cos(a) * 0.65f, 0f, Mathf.Sin(a) * 0.65f), 0.12f, 4, td, 0.04f);
                        }
                        break;
                    }
                case ModelId.Crates:
                    {
                        Crate(b, new Vector3(0, 0.5f, 0), 1.0f, Quaternion.Euler(0, 8, 0));
                        Crate(b, new Vector3(0.95f, 0.4f, -0.35f), 0.8f, Quaternion.Euler(0, -14, 0));
                        if (v != 1) Crate(b, new Vector3(0.2f, 1.36f, 0.05f), 0.72f, Quaternion.Euler(0, 30, 0));
                        if (v == 2) b.Box(new Vector3(-0.7f, 0.55f, 0.1f), new Vector3(0.06f, 1.1f, 0.9f), Quaternion.Euler(0, 0, -18), Rust);
                        break;
                    }
                case ModelId.Tires:
                    {
                        int n = 3 + v % 2;
                        for (int i = 0; i < n; i++) TireFlat(b, new Vector3(R() * 0.1f, i * 0.3f, R() * 0.1f), 0.5f, 0.28f);
                        b.Push(new Vector3(0.75f, 0.45f, -0.25f), Quaternion.Euler(0, 30, 75));
                        TireFlat(b, Vector3.zero, 0.45f, 0.26f);
                        b.Pop();
                        break;
                    }
                case ModelId.JunkPile:
                    {
                        b.Rock(new Vector3(0, 0.15f, 0), new Vector3(1.4f, 0.7f, 1.2f), Hex("#8C6A4A"), 11 + v, Hex("#A07A55"));
                        b.Box(new Vector3(0.3f, 0.75f, 0.1f), new Vector3(0.9f, 0.35f, 0.6f), Quaternion.Euler(10, 25, 15), Rust);
                        b.Box(new Vector3(-0.5f, 0.7f, -0.2f), new Vector3(0.7f, 0.08f, 1.0f), Quaternion.Euler(0, -20, 30), Hex("#5E7F8F"));
                        b.CylinderBetween(new Vector3(-0.9f, 0.4f, 0.5f), new Vector3(0.6f, 0.9f, 0.6f), 0.12f, 6, Metal);
                        b.Push(new Vector3(0.6f, 0.55f, -0.6f), Quaternion.Euler(70, 0, 20));
                        TireFlat(b, Vector3.zero, 0.38f, 0.22f);
                        b.Pop();
                        b.Box(new Vector3(-0.2f, 1.05f, 0.2f), new Vector3(0.5f, 0.4f, 0.4f), Quaternion.Euler(20, 40, 0), Hex("#C9A04A"));
                        break;
                    }
                case ModelId.Barrels:
                case ModelId.ToxicBarrels:
                    {
                        bool toxic = id == ModelId.ToxicBarrels;
                        Color[] cs = toxic ? new[] { Hex("#D9C23A"), Hex("#C9B032"), Hex("#6F8F3A") } : new[] { Hex("#C9412E"), Hex("#3E6FA6"), Hex("#E0B23B") };
                        Drum(b, new Vector3(0, 0, 0), cs[v % 3], toxic);
                        Drum(b, new Vector3(0.78f, 0, 0.25f), cs[(v + 1) % 3], toxic);
                        if (v != 2) Drum(b, new Vector3(0.3f, 0, -0.68f), cs[(v + 2) % 3], toxic);
                        b.Push(new Vector3(-0.75f, 0.36f, -0.35f), Quaternion.Euler(0, 35, 90));
                        Drum(b, new Vector3(0, -0.47f, 0), cs[(v + 1) % 3], toxic);
                        b.Pop();
                        if (toxic) b.Disc(new Vector3(-0.2f, 0.02f, -0.9f), 0.7f, 9, Glow("#7CFF4A", 0.3f));
                        break;
                    }
                case ModelId.Boulder:
                case ModelId.SaltRock:
                case ModelId.ToxicRock:
                case ModelId.RedRock:
                    {
                        Color c = z.cliff, top = Color.Lerp(z.cliff, Color.white, 0.25f);
                        if (id == ModelId.SaltRock) { c = Hex("#B9C9D4"); top = Hex("#EEF4F6"); }
                        if (id == ModelId.ToxicRock) { c = Hex("#55584C"); top = Hex("#6E7262"); }
                        if (id == ModelId.RedRock)
                        {
                            c = Hex("#B85A3A"); top = Hex("#D27A52");
                            b.Rock(new Vector3(0, 0.9f, 0), new Vector3(1.1f, 1.1f, 1.0f), c, 21 + v, top, 0.18f);
                            b.Rock(new Vector3(0.1f, 1.95f, 0.05f), new Vector3(0.8f, 0.5f, 0.75f), c, 31 + v, top, 0.15f);
                            b.Rock(new Vector3(0.95f, 0.25f, -0.4f), new Vector3(0.45f, 0.35f, 0.4f), c, 41 + v, top);
                            break;
                        }
                        b.Rock(new Vector3(0, 1.1f, 0), new Vector3(2.0f, 1.55f, 1.8f), c, 51 + v, top);
                        b.Rock(new Vector3(1.7f, 0.3f, -0.9f), new Vector3(0.6f, 0.45f, 0.55f), c, 61 + v, top);
                        b.Rock(new Vector3(-1.5f, 0.25f, 0.8f), new Vector3(0.45f, 0.35f, 0.5f), c, 71 + v, top);
                        if (id == ModelId.ToxicRock)
                        {
                            b.Sphere(new Vector3(0.6f, 1.9f, -1.2f), new Vector3(0.35f, 0.25f, 0.2f), Glow("#7CFF4A", 0.25f), 0);
                            b.Sphere(new Vector3(-0.9f, 1.2f, -1.3f), new Vector3(0.25f, 0.3f, 0.2f), Glow("#7CFF4A", 0.25f), 0);
                        }
                        break;
                    }
                case ModelId.CarWreck:
                    {
                        var body = v == 0 ? Rust : (v == 1 ? Hex("#6F8592") : Hex("#9A7A42"));
                        b.Material(0.3f, 0.25f);
                        b.Push(Vector3.zero, Quaternion.Euler(0, 0, v == 2 ? 6 : -4));
                        b.Box(new Vector3(0, 0.55f, 0), new Vector3(1.9f, 0.6f, 4.1f), body, Shade(body, 1.08f));
                        b.Tapered(new Vector3(0, 0.85f, -0.3f), new Vector2(1.7f, 2.0f), new Vector2(1.35f, 1.2f), 0.55f, Hex("#2E343B"), Shade(body, 1.05f));
                        b.Box(new Vector3(0, 0.62f, 2.07f), new Vector3(1.6f, 0.3f, 0.06f), MetalDark);
                        b.Box(new Vector3(0, 0.42f, 2.12f), new Vector3(1.9f, 0.12f, 0.12f), Shade(Chrome, 0.75f));
                        b.Box(new Vector3(0.55f, 0.95f, 1.3f), new Vector3(0.6f, 0.1f, 0.9f), Quaternion.Euler(-25, 0, 0), Shade(body, 0.85f)); // popped hood
                        // flat tires
                        foreach (var p in new[] { new Vector3(-0.9f, 0.28f, 1.3f), new Vector3(0.9f, 0.28f, 1.3f), new Vector3(-0.9f, 0.28f, -1.3f) })
                        {
                            b.Push(p, Quaternion.Euler(0, 0, 90));
                            b.Cylinder(new Vector3(0, -0.14f, 0), 0.34f, 0.28f, 8, TireC, -1, TireHub);
                            b.Pop();
                        }
                        b.Pop();
                        b.Rock(new Vector3(-1.4f, 0.0f, -1.6f), new Vector3(0.5f, 0.2f, 0.4f), Shade(z.ground, 0.85f), 5);
                        break;
                    }
                case ModelId.Shack:
                    {
                        var wall = v == 1 ? Hex("#7E8A8E") : Hex("#9A8A78");
                        b.Box(new Vector3(0, 1.2f, 0), new Vector3(3.2f, 2.4f, 2.8f), wall);
                        b.Box(new Vector3(-0.9f, 1.0f, -1.42f), new Vector3(1.1f, 1.7f, 0.06f), Rust);
                        b.Box(new Vector3(1.2f, 1.4f, -1.42f), new Vector3(0.7f, 1.6f, 0.06f), Hex("#4F7F86"));
                        b.Box(new Vector3(1.62f, 1.0f, 0.3f), new Vector3(0.06f, 1.4f, 1.4f), RustLight);
                        b.Box(new Vector3(0.25f, 0.85f, -1.45f), new Vector3(0.85f, 1.7f, 0.06f), Hex("#3A2E28"));
                        b.Box(new Vector3(-0.85f, 1.65f, -1.46f), new Vector3(0.65f, 0.45f, 0.05f), Hex("#2B3A44"));
                        b.Box(new Vector3(0, 2.55f, 0.05f), new Vector3(3.7f, 0.14f, 3.4f), Quaternion.Euler(-9, 0, 0), RustDark, Rust);
                        b.Cylinder(new Vector3(1.0f, 2.4f, 0.9f), 0.14f, 1.0f, 6, MetalDark);
                        b.Box(new Vector3(-1.9f, 0.45f, -0.6f), new Vector3(0.6f, 0.9f, 0.6f), Quaternion.Euler(0, 15, 0), Wood);
                        if (v == 2) b.Box(new Vector3(0, 2.0f, -1.5f), new Vector3(1.4f, 0.35f, 0.05f), Hex("#D8C9A6"));
                        break;
                    }
                case ModelId.Hut:
                    {
                        foreach (var p in new[] { new Vector3(-1.1f, 0, -1.0f), new Vector3(1.1f, 0, -1.0f), new Vector3(-1.1f, 0, 1.0f), new Vector3(1.1f, 0, 1.0f) })
                            b.Box(p + new Vector3(0, 0.6f, 0), new Vector3(0.18f, 1.2f, 0.18f), WoodDark);
                        b.Box(new Vector3(0, 1.25f, 0), new Vector3(2.8f, 0.14f, 2.6f), Wood);
                        b.Box(new Vector3(0, 2.15f, 0), new Vector3(2.4f, 1.7f, 2.2f), Hex("#7A5A3E"));
                        b.Box(new Vector3(0.3f, 1.95f, -1.12f), new Vector3(0.7f, 1.3f, 0.05f), Hex("#2E241E"));
                        b.Tapered(new Vector3(0, 3.0f, 0), new Vector2(3.3f, 3.1f), new Vector2(0.2f, 0.2f), 1.5f, Hex("#8C7A4A"));
                        b.Box(new Vector3(-0.6f, 0.65f, -1.6f), new Vector3(0.6f, 0.08f, 1.2f), Quaternion.Euler(40, 0, 0), WoodLight);
                        b.Disc(new Vector3(1.6f, 0.03f, -0.4f), 0.8f, 9, Glow("#7CFF4A", 0.4f));
                        break;
                    }
                case ModelId.Tent:
                    {
                        var cloth = v == 1 ? Hex("#C9B48E") : ClothBeige;
                        b.Prism(Vector3.zero, 2.5f, 1.9f, 2.6f, cloth, ClothRed);
                        b.Box(new Vector3(0, 0.6f, -1.32f), new Vector3(0.7f, 1.2f, 0.04f), Hex("#3A2E28"));
                        b.Cylinder(new Vector3(0, 0, -1.4f), 0.05f, 2.15f, 4, WoodDark);
                        b.Cylinder(new Vector3(0, 0, 1.4f), 0.05f, 2.15f, 4, WoodDark);
                        if (v == 2) b.Box(new Vector3(0.9f, 0.3f, -1.6f), new Vector3(0.6f, 0.6f, 0.6f), Wood);
                        break;
                    }
                case ModelId.Tower:
                    {
                        float H = 4.2f;
                        foreach (var p in new[] { new Vector3(-1, 0, -1), new Vector3(1, 0, -1), new Vector3(-1, 0, 1), new Vector3(1, 0, 1) })
                            b.CylinderBetween(p, new Vector3(p.x * 0.8f, H, p.z * 0.8f), 0.11f, 4, WoodDark);
                        b.CylinderBetween(new Vector3(-1, 0.4f, -1), new Vector3(0.85f, 3.6f, -0.85f), 0.06f, 4, Wood);
                        b.CylinderBetween(new Vector3(1, 0.4f, -1), new Vector3(-0.85f, 3.6f, -0.85f), 0.06f, 4, Wood);
                        b.Box(new Vector3(0, H, 0), new Vector3(2.3f, 0.18f, 2.3f), Wood, WoodLight);
                        b.Box(new Vector3(0, H + 0.45f, -1.12f), new Vector3(2.3f, 0.6f, 0.08f), Rust);
                        b.Box(new Vector3(-1.12f, H + 0.45f, 0), new Vector3(0.08f, 0.6f, 2.3f), RustLight);
                        b.Box(new Vector3(1.12f, H + 0.45f, 0), new Vector3(0.08f, 0.6f, 2.3f), Rust);
                        foreach (var p in new[] { new Vector3(-1, 0, -1), new Vector3(1, 0, -1), new Vector3(-1, 0, 1), new Vector3(1, 0, 1) })
                            b.Box(new Vector3(p.x * 1.05f, H + 0.95f, p.z * 1.05f), new Vector3(0.1f, 1.1f, 0.1f), WoodDark);
                        b.Tapered(new Vector3(0, H + 1.5f, 0), new Vector2(2.7f, 2.7f), new Vector2(0.15f, 0.15f), 0.9f, RustDark);
                        for (int i = 0; i < 7; i++) b.Box(new Vector3(0.45f, 0.4f + i * 0.55f, -1.18f), new Vector3(0.6f, 0.07f, 0.07f), WoodLight);
                        b.Cylinder(new Vector3(-0.8f, H + 1.5f, -0.8f), 0.03f, 1.4f, 3, WoodDark);
                        b.Box(new Vector3(-0.55f, H + 2.6f, -0.8f), new Vector3(0.5f, 0.32f, 0.03f), ClothRed);
                        break;
                    }
                case ModelId.OilPump:
                    {
                        var red = Hex("#8C2F25"); var orange = Hex("#D07A2A");
                        b.Box(new Vector3(0, 0.15f, 0), new Vector3(1.2f, 0.3f, 4.2f), MetalDark);
                        b.CylinderBetween(new Vector3(-0.5f, 0.3f, -0.4f), new Vector3(0, 2.7f, 0), 0.1f, 5, red);
                        b.CylinderBetween(new Vector3(0.5f, 0.3f, -0.4f), new Vector3(0, 2.7f, 0), 0.1f, 5, red);
                        b.CylinderBetween(new Vector3(0, 0.3f, 0.6f), new Vector3(0, 2.7f, 0), 0.1f, 5, red);
                        b.Box(new Vector3(0, 2.85f, 0.2f), new Vector3(0.32f, 0.36f, 4.0f), Quaternion.Euler(-6, 0, 0), orange);
                        b.Box(new Vector3(0, 2.4f, 2.25f), new Vector3(0.42f, 1.3f, 0.5f), Quaternion.Euler(-6, 0, 0), orange);
                        b.Box(new Vector3(0, 1.3f, -1.55f), new Vector3(1.0f, 0.8f, 0.55f), MetalDark);
                        b.CylinderBetween(new Vector3(0, 1.3f, -1.55f), new Vector3(0, 2.6f, -1.5f), 0.08f, 4, Metal);
                        b.Cylinder(new Vector3(0, 0, 2.6f), 0.14f, 1.6f, 6, Metal);
                        b.Box(new Vector3(0.75f, 0.45f, -0.9f), new Vector3(0.6f, 0.6f, 0.9f), Hex("#5E7F8F"));
                        b.Disc(new Vector3(0.6f, 0.02f, 2.6f), 0.9f, 9, Hex("#2A2420"));
                        break;
                    }
                case ModelId.OilTank:
                    {
                        bool toxic = z.index == 3;
                        var c = toxic ? Hex("#8A9A3A") : Hex("#8E6E5C");
                        b.Material(0.45f, 0.3f);
                        b.Cylinder(Vector3.zero, 1.6f, 3.0f, 12, c, -1, Shade(c, 1.12f));
                        b.Cylinder(new Vector3(0, 0.7f, 0), 1.63f, 0.14f, 12, Shade(c, 0.75f));
                        b.Cylinder(new Vector3(0, 2.1f, 0), 1.63f, 0.14f, 12, Shade(c, 0.75f));
                        b.Cone(new Vector3(0, 3.0f, 0), 1.6f, 0.5f, 12, Shade(c, 1.08f));
                        for (int i = 0; i < 6; i++) b.Box(new Vector3(0.6f, 0.3f + i * 0.5f, -1.66f), new Vector3(0.5f, 0.06f, 0.06f), Metal);
                        b.CylinderBetween(new Vector3(1.4f, 0.4f, -0.6f), new Vector3(2.6f, 0.4f, -0.6f), 0.15f, 6, Metal);
                        b.Box(new Vector3(-0.3f, 1.6f, -1.62f), new Vector3(1.4f, 0.5f, 0.05f), toxic ? Hex("#E0C23A") : Hex("#D8C9A6"));
                        if (toxic) b.Disc(new Vector3(-1.4f, 0.03f, -1.2f), 1.1f, 10, Glow("#7CFF4A", 0.35f));
                        break;
                    }
                case ModelId.Pipes:
                    {
                        var c1 = z.index == 3 ? Hex("#6F7A5A") : Rust; var c2 = Metal;
                        b.Material(0.4f, 0.5f);
                        int[] row = { 3, 2, 1 };
                        for (int r = 0; r < 3; r++)
                            for (int i = 0; i < row[r]; i++)
                            {
                                float x = (i - (row[r] - 1) * 0.5f) * 0.6f;
                                float y = 0.3f + r * 0.5f;
                                var col = ((i + r + v) % 2 == 0) ? c1 : c2;
                                b.CylinderBetween(new Vector3(-1.4f, y, x), new Vector3(1.4f, y, x), 0.29f, 8, col, -1, Hex("#2A2420"));
                            }
                        break;
                    }
                case ModelId.DryBush:
                    {
                        var c = Hex("#B88A4A"); var top = Hex("#D3A762");
                        b.Sphere(new Vector3(0, 0.55f, 0), new Vector3(0.85f, 0.6f, 0.8f), c, 1, 0.35f, 81 + v, top);
                        b.Sphere(new Vector3(0.6f, 0.35f, -0.3f), new Vector3(0.45f, 0.35f, 0.45f), c, 1, 0.3f, 91 + v, top);
                        break;
                    }
                case ModelId.SaltCrystal:
                    {
                        var c1 = Glow("#E2F6FF", 0.85f); var c2 = Glow("#B4E4F6", 0.8f);
                        for (int i = 0; i < 5; i++)
                        {
                            float a = i * 72f + v * 20f + R() * 20f;
                            float tilt = i == 0 ? 0 : 25f + R() * 15f;
                            float h = i == 0 ? 2.2f : 1.0f + R() * 0.8f;
                            b.Push(new Vector3(Mathf.Cos(a * Mathf.Deg2Rad), 0, Mathf.Sin(a * Mathf.Deg2Rad)) * (i == 0 ? 0 : 0.35f), Quaternion.Euler(0, a, 0) * Quaternion.Euler(tilt, 0, 0));
                            float r0 = i == 0 ? 0.36f : 0.22f;
                            b.Cylinder(Vector3.zero, r0, h, 6, i % 2 == 0 ? c1 : c2);
                            b.Cone(new Vector3(0, h, 0), r0, r0 * 1.6f, 6, Glow("#F4FBFF", 0.8f));
                            b.Pop();
                        }
                        b.Rock(new Vector3(0, 0, 0), new Vector3(0.8f, 0.25f, 0.7f), Hex("#C9D4DA"), 7);
                        break;
                    }
                case ModelId.RibCage:
                    {
                        for (int i = 0; i < 6; i++)
                        {
                            float zz = -1.6f + i * 0.62f;
                            b.Box(new Vector3(0, 0.25f, zz), new Vector3(0.32f, 0.32f, 0.4f), BoneDark);
                            float s = 1f - Mathf.Abs(i - 2.5f) * 0.12f;
                            for (int side = -1; side <= 1; side += 2)
                            {
                                var p0 = new Vector3(side * 0.15f, 0.3f, zz);
                                var p1 = new Vector3(side * 1.1f * s, 1.3f * s, zz);
                                var p2 = new Vector3(side * 1.0f * s, 2.4f * s, zz - 0.1f);
                                var p3 = new Vector3(side * 0.35f * s, 2.9f * s, zz - 0.15f);
                                b.CylinderBetween(p0, p1, 0.1f, 5, Bone, 0.09f);
                                b.CylinderBetween(p1, p2, 0.09f, 5, Bone, 0.07f);
                                b.CylinderBetween(p2, p3, 0.07f, 5, Bone, 0.05f);
                            }
                        }
                        b.Sphere(new Vector3(0, 0.6f, 2.4f), new Vector3(0.7f, 0.55f, 0.9f), Bone, 1, 0.1f, 5);
                        b.Box(new Vector3(0, 0.4f, 3.2f), new Vector3(0.5f, 0.4f, 0.9f), BoneDark);
                        break;
                    }
                case ModelId.Skull:
                    {
                        b.Sphere(new Vector3(0, 0.55f, 0), new Vector3(0.75f, 0.55f, 0.8f), Bone, 1, 0.08f, 13 + v);
                        b.Box(new Vector3(0, 0.38f, -0.85f), new Vector3(0.6f, 0.45f, 0.8f), Bone);
                        b.Sphere(new Vector3(-0.32f, 0.62f, -0.55f), new Vector3(0.18f, 0.15f, 0.12f), Hex("#3A2A22"), 0);
                        b.Sphere(new Vector3(0.32f, 0.62f, -0.55f), new Vector3(0.18f, 0.15f, 0.12f), Hex("#3A2A22"), 0);
                        for (int side = -1; side <= 1; side += 2)
                        {
                            var a = new Vector3(side * 0.6f, 0.8f, 0.1f);
                            var bb = new Vector3(side * 1.3f, 1.1f, 0.0f);
                            var c = new Vector3(side * 1.6f, 1.6f, -0.3f);
                            b.CylinderBetween(a, bb, 0.14f, 5, BoneDark, 0.1f);
                            b.CylinderBetween(bb, c, 0.1f, 5, BoneDark, 0.03f);
                        }
                        break;
                    }
                case ModelId.Turbine:
                    {
                        var white = Hex("#D9DCDD");
                        b.Material(0.45f, 0.05f);
                        b.Box(new Vector3(0, 0.25f, 0), new Vector3(1.6f, 0.5f, 1.6f), Hex("#9A9A94"));
                        b.Cylinder(new Vector3(0, 0.5f, 0), 0.38f, 7.5f, 8, white, 0.22f);
                        b.Box(new Vector3(0, 8.15f, 0.1f), new Vector3(0.6f, 0.6f, 1.4f), white);
                        b.Push(new Vector3(0, 8.15f, -0.65f), Quaternion.Euler(0, 0, v * 25f));
                        for (int i = 0; i < 3; i++)
                        {
                            float len = (i == 1 && v != 2) ? 1.6f : 3.6f;
                            b.Push(Vector3.zero, Quaternion.Euler(0, 0, i * 120f));
                            b.Box(new Vector3(0, len * 0.5f + 0.2f, 0), new Vector3(0.36f, len, 0.08f), i == 1 ? Hex("#C9785A") : white);
                            b.Pop();
                        }
                        b.Sphere(Vector3.zero, new Vector3(0.28f, 0.28f, 0.28f), white, 0);
                        b.Pop();
                        break;
                    }
                case ModelId.SwampTree:
                    {
                        var t = Hex("#4A3B2E"); var leaf = Hex("#4E6B35"); var moss = Hex("#7D8F5A");
                        var p0 = Vector3.zero; var p1 = new Vector3(0.3f, 1.4f, 0.1f); var p2 = new Vector3(-0.1f, 2.6f, -0.1f); var p3 = new Vector3(0.2f, 3.4f, 0);
                        b.CylinderBetween(p0, p1, 0.36f, 6, t, 0.28f);
                        b.CylinderBetween(p1, p2, 0.28f, 6, t, 0.2f);
                        b.CylinderBetween(p2, p3, 0.2f, 6, t, 0.12f);
                        b.Sphere(new Vector3(0.2f, 3.7f, 0), new Vector3(1.5f, 0.9f, 1.4f), leaf, 1, 0.25f, 17 + v, Shade(leaf, 1.15f));
                        b.Sphere(new Vector3(-0.9f, 3.2f, 0.4f), new Vector3(0.9f, 0.6f, 0.9f), leaf, 1, 0.25f, 27 + v);
                        for (int i = 0; i < 5; i++)
                        {
                            float a = i * 1.3f;
                            var top = new Vector3(Mathf.Cos(a) * 1.0f, 3.3f, Mathf.Sin(a) * 1.0f);
                            b.CylinderBetween(top, top + Vector3.down * (0.8f + i * 0.12f), 0.12f, 4, moss, 0.02f);
                        }
                        for (int i = 0; i < 3; i++)
                        {
                            float a = i * 2.1f + 0.4f;
                            b.CylinderBetween(new Vector3(0, 0.5f, 0), new Vector3(Mathf.Cos(a) * 0.9f, 0f, Mathf.Sin(a) * 0.9f), 0.13f, 4, t, 0.05f);
                        }
                        break;
                    }
                case ModelId.Mushroom:
                    {
                        var stem = Hex("#E8E0C8");
                        var cap = v == 1 ? Hex("#3E8A8A") : Hex("#6A4AA8");
                        for (int i = 0; i < 3; i++)
                        {
                            var o = i == 0 ? Vector3.zero : new Vector3((i == 1 ? 0.7f : -0.55f), 0, (i == 1 ? -0.3f : 0.45f));
                            float s = i == 0 ? 1f : 0.55f;
                            b.Cylinder(o, 0.18f * s, 1.1f * s, 6, stem, 0.14f * s);
                            b.Sphere(o + new Vector3(0, 1.1f * s, 0), new Vector3(0.75f, 0.42f, 0.75f) * s, cap, 1, 0.08f, 3 + i, Shade(cap, 1.15f));
                            b.Sphere(o + new Vector3(0.25f, 1.42f, -0.2f) * s, Vector3.one * 0.12f * s, Glow("#B6FF7A", 0.3f), 0);
                            b.Sphere(o + new Vector3(-0.3f, 1.38f, 0.1f) * s, Vector3.one * 0.1f * s, Glow("#B6FF7A", 0.3f), 0);
                        }
                        break;
                    }
                case ModelId.Chest:
                    {
                        b.Box(new Vector3(0, 0.32f, 0), new Vector3(1.1f, 0.64f, 0.75f), Hex("#9A5A2C"));
                        b.Box(new Vector3(0, 0.75f, 0), new Vector3(1.12f, 0.24f, 0.77f), Hex("#B8703A"), Hex("#C98448"));
                        b.Material(0.85f, 1f);
                        b.Box(new Vector3(0, 0.45f, 0), new Vector3(1.14f, 0.1f, 0.79f), Hex("#E8B84A"));
                        b.Box(new Vector3(0, 0.55f, -0.4f), new Vector3(0.2f, 0.26f, 0.06f), Glow("#FFD24A", 0.5f));
                        break;
                    }
                default:
                    b.Box(new Vector3(0, 0.5f, 0), Vector3.one, Color.magenta);
                    break;
            }
        }

        static void Crate(MeshBuilder b, Vector3 c, float s, Quaternion rot)
        {
            b.Material(0.12f, 0f);
            b.Push(c, rot);
            b.Box(Vector3.zero, Vector3.one * s, Wood, WoodLight);
            b.Box(new Vector3(0, s * 0.3f, 0), new Vector3(s * 1.04f, s * 0.1f, s * 1.04f), WoodDark);
            b.Box(new Vector3(0, -s * 0.3f, 0), new Vector3(s * 1.04f, s * 0.1f, s * 1.04f), WoodDark);
            b.Box(new Vector3(0, 0, -s * 0.5f), new Vector3(s * 0.12f, s * 1.0f, s * 0.06f), WoodDark);
            b.Pop();
        }

        static void TireFlat(MeshBuilder b, Vector3 baseC, float r, float h)
        {
            b.Material(0.16f, 0f);
            b.Cylinder(baseC, r, h, 10, TireC, -1, Hex("#3A3535"));
            b.Disc(baseC + Vector3.up * (h + 0.005f), r * 0.45f, 10, TireHub);
        }

        static void Drum(MeshBuilder b, Vector3 baseC, Color c, bool toxic)
        {
            b.Material(0.55f, 0.15f);
            b.Cylinder(baseC, 0.36f, 0.95f, 10, c, -1, Shade(c, 0.8f));
            b.Cylinder(baseC + Vector3.up * 0.22f, 0.375f, 0.07f, 10, Shade(c, 0.7f), -1, null, false);
            b.Cylinder(baseC + Vector3.up * 0.68f, 0.375f, 0.07f, 10, Shade(c, 0.7f), -1, null, false);
            if (toxic)
            {
                b.Disc(baseC + Vector3.up * 0.96f, 0.3f, 10, Glow("#7CFF4A", 0.3f));
                b.Box(baseC + new Vector3(0, 0.45f, -0.37f), new Vector3(0.3f, 0.3f, 0.02f), Hex("#202020"));
            }
        }
    }
}
