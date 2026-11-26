using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Characters, vehicles, bosses and the hero's equipment. Styled for the top-down phone camera: big heads and
    /// hands, one signature silhouette element per enemy (junk backpack, mohawk + spiked pads, spear quiver + round
    /// shield, wide crossbow, fuel tank + bell-mouth gun), enemies coded with warm reds, the hero group with
    /// graphite, cream and teal.
    /// </summary>
    public static partial class Models
    {
        public const float HumanScale = 1.38f;
        static readonly Color SkinPale = Hex("#E8D5C0"), SkinTan = Hex("#C8956C"), Pants = Hex("#3B3534"), Leather = Hex("#7A5236");
        static readonly Color EnemyRed = Hex("#D04A36"), EnemyDark = Hex("#2F2B2C"), BootC = Hex("#2E2622");

        struct Look
        {
            public Color skin, torso, pants, accent, head, cloth;
            public float bw, headK;
            public bool hood, mask, goggles, mohawk, pads, backpack, quiver, shield, belly, crystals, tophat, tank;
        }

        static Look LookFor(ModelId id, ZoneDef z)
        {
            var l = new Look { skin = SkinPale, torso = SkinPale, pants = Pants, accent = EnemyRed, head = SkinPale, cloth = ClothBeige, bw = 1f, headK = 1.15f };
            switch (id)
            {
                case ModelId.Scav:
                    l.skin = l.head = SkinTan; l.torso = Hex("#8C7055"); l.pants = Hex("#5B4A3B"); l.cloth = Hex("#B79C74");
                    l.accent = Hex("#C4643A"); l.hood = true; l.backpack = true; l.bw = 0.95f; l.headK = 1.2f; break;
                case ModelId.Raider:
                    l.torso = Hex("#3A3131"); l.pants = Hex("#4C3D36"); l.accent = EnemyRed; l.mohawk = true; l.pads = true; break;
                case ModelId.Spearman:
                    l.torso = Leather; l.pants = Hex("#4A3B33"); l.accent = Hex("#B9493A"); l.mask = true; l.quiver = true; l.shield = true; break;
                case ModelId.Crossbow:
                    l.torso = Hex("#6A4C34"); l.pants = Hex("#463A33"); l.accent = Hex("#DE9A3A"); l.goggles = true; l.cloth = Hex("#9C6A44"); break;
                case ModelId.Brute:
                    l.torso = Hex("#555C65"); l.pants = Hex("#3A3A3E"); l.accent = EnemyRed; l.mask = true; l.pads = true; l.tank = true; l.bw = 1.4f; l.headK = 1.05f; break;
                case ModelId.BossBaron:
                    l.torso = Hex("#3B3332"); l.skin = l.head = Hex("#D8B59C"); l.pants = Hex("#2E2A2A"); l.accent = Hex("#E4A637");
                    l.mask = true; l.belly = true; l.tophat = true; l.tank = true; l.bw = 1.35f; l.headK = 1.1f; break;
                case ModelId.BossColossus:
                    l.skin = l.torso = l.head = Hex("#BACCD8"); l.pants = Hex("#4C4E58"); l.accent = Hex("#6F8498");
                    l.crystals = true; l.pads = true; l.bw = 1.4f; l.headK = 0.95f; break;
            }
            // zone tint on cloth accents
            if (z != null && z.index == 3 && id != ModelId.BossColossus) { l.accent = Color.Lerp(l.accent, Hex("#7A8A3A"), 0.35f); l.goggles = l.goggles || id == ModelId.Raider; }
            if (z != null && z.index == 2 && id == ModelId.Scav) { l.torso = Hex("#9AA3A8"); l.cloth = Hex("#C9C4B6"); }
            return l;
        }

        /// <summary>Humanoid with animatable legs / arms (pivots at hips and shoulders).</summary>
        public static GameObject Humanoid(ModelId id, ZoneDef z, float scale = 1f)
        {
            var look = LookFor(id, z);
            string k = id + "_" + (z != null ? z.index : 0);
            float bw = look.bw;

            var root = new GameObject(id.ToString());
            var rig = root.AddComponent<Rig>();
            var scaler = new GameObject("Scale").transform;
            scaler.SetParent(root.transform, false);
            scaler.localScale = Vector3.one * scale * HumanScale;

            var torsoMesh = Cached("torso3_" + k, b =>
            {
                // pelvis + rounded torso (chest wider than the waist)
                b.Sphere(new Vector3(0, 1.0f, 0), new Vector3(0.24f * bw, 0.15f, 0.16f * bw), look.pants, 1);
                b.Push(Vector3.zero, Quaternion.identity, new Vector3(bw, 1f, 0.72f * bw));
                b.Material(0.12f, 0f);
                b.Lathe(new[]
                {
                    new Vector2(0f, 0.98f), new Vector2(0.21f, 1.0f), new Vector2(0.24f, 1.1f), new Vector2(0.28f, 1.32f),
                    new Vector2(0.29f, 1.45f), new Vector2(0.25f, 1.56f), new Vector2(0.12f, 1.64f), new Vector2(0f, 1.65f)
                }, 16, look.torso);
                b.Pop();
                if (look.belly)
                {
                    // round belly in a dark vest with a cream shirt front
                    b.Sphere(new Vector3(0, 1.24f, 0.08f), new Vector3(0.36f, 0.34f, 0.32f) * bw, look.torso, 2);
                    b.Sphere(new Vector3(0, 1.3f, 0.22f * bw), new Vector3(0.16f, 0.24f, 0.14f) * bw, Hex("#EFE4CC"), 2);
                }
                b.Material(0.35f, 0f);
                b.Lathe(new[] { new Vector2(0.245f * bw, 1.06f), new Vector2(0.25f * bw, 1.14f) }, 16, Hex("#2B2321"));
                b.Matte();
                if (id == ModelId.Raider || id == ModelId.Spearman || id == ModelId.Crossbow)
                    b.BevelBox(new Vector3(0, 1.33f, 0.0f), new Vector3(0.06f, 0.64f, 0.42f), Quaternion.Euler(0, 0, 38), 0.02f, Hex("#4A3426")); // strap
                if (look.pads)
                {
                    // big shoulder pads with spikes: reads from above as two wide knobs
                    b.Material(0.45f, 0.55f);
                    for (int sx = -1; sx <= 1; sx += 2)
                    {
                        b.Push(new Vector3(sx * 0.32f * bw, 1.57f, 0), Quaternion.Euler(0, 0, -sx * 20f));
                        b.Sphere(Vector3.zero, new Vector3(0.22f, 0.11f, 0.22f) * bw, look.accent, 1);
                        b.Material(0.85f, 1f);
                        b.Cone(new Vector3(0, 0.06f, 0), 0.05f * bw, 0.2f * bw, 8, Chrome);
                        b.Material(0.45f, 0.55f);
                        b.Pop();
                    }
                    b.Matte();
                }
                if (look.backpack)
                {
                    // scavenger's junk backpack: bigger than his torso
                    b.Material(0.25f, 0.2f);
                    b.BevelBox(new Vector3(0, 1.32f, -0.3f), new Vector3(0.5f, 0.56f, 0.34f), 0.07f, look.accent, Shade(look.accent, 1.12f));
                    b.BevelBox(new Vector3(0.05f, 1.72f, -0.32f), new Vector3(0.36f, 0.26f, 0.28f), Quaternion.Euler(0, 14, 6), 0.05f, Wood, WoodLight);
                    b.Material(0.5f, 0.7f);
                    b.CylinderBetween(new Vector3(-0.24f, 1.2f, -0.36f), new Vector3(-0.3f, 2.05f, -0.3f), 0.05f, 10, Metal);
                    b.Material(0.15f, 0f);
                    b.Push(new Vector3(0.28f, 1.05f, -0.32f), Quaternion.Euler(0, 0, 90));
                    b.Lathe(new[] { new Vector2(0.09f, -0.08f), new Vector2(0.17f, -0.07f), new Vector2(0.17f, 0.07f), new Vector2(0.09f, 0.08f) }, 16, TireC);
                    b.Pop();
                    b.Matte();
                }
                if (look.quiver)
                {
                    // spear quiver on the back: three shafts sticking up over the shoulder
                    b.Material(0.2f, 0f);
                    b.Push(new Vector3(-0.08f, 1.35f, -0.24f), Quaternion.Euler(-12, 0, 22));
                    b.Cylinder(new Vector3(0, -0.3f, 0), 0.11f, 0.62f, 12, Hex("#6A4630"), -1, Hex("#3A2618"));
                    for (int i = 0; i < 3; i++)
                    {
                        var o = new Vector3((i - 1) * 0.06f, 0f, (i % 2) * 0.04f);
                        b.CylinderBetween(o + Vector3.up * 0.2f, o + Vector3.up * 0.95f, 0.025f, 6, WoodDark);
                        b.Material(0.85f, 1f);
                        b.Cone(o + Vector3.up * 0.95f, 0.06f, 0.22f, 6, Chrome);
                        b.Material(0.2f, 0f);
                    }
                    b.Pop();
                    b.Matte();
                }
                if (look.tank)
                {
                    // fuel tank backpack with dark bands
                    float tk = id == ModelId.BossBaron ? 1.35f : 1f;
                    b.Material(0.55f, 0.35f);
                    b.Push(new Vector3(0, 1.32f, -0.32f * bw), Quaternion.identity, Vector3.one * tk);
                    b.Lathe(new[] { new Vector2(0f, -0.38f), new Vector2(0.16f, -0.36f), new Vector2(0.2f, -0.3f), new Vector2(0.2f, 0.3f), new Vector2(0.16f, 0.36f), new Vector2(0f, 0.38f) }, 16, id == ModelId.BossBaron ? Hex("#2E2C2E") : Hex("#B24834"));
                    b.Material(0.4f, 0.6f);
                    foreach (float y in new[] { -0.16f, 0.16f }) b.Lathe(new[] { new Vector2(0.205f, y - 0.03f), new Vector2(0.205f, y + 0.03f) }, 16, EnemyDark);
                    b.Pop();
                    b.Matte();
                }
                // neck + big stylized head (faces +z)
                float hy = 1.82f, hk = look.headK;
                b.CylinderBetween(new Vector3(0, 1.58f, 0), new Vector3(0, 1.7f, 0.01f), 0.075f, 10, look.skin);
                b.Sphere(new Vector3(0, hy, 0), new Vector3(0.17f, 0.18f, 0.17f) * hk, look.head, 2);
                b.Sphere(new Vector3(0, hy - 0.09f * hk, 0.07f * hk), new Vector3(0.12f, 0.085f, 0.11f) * hk, look.head, 1);
                if (look.hood)
                {
                    b.Push(new Vector3(0, 0, -0.035f));
                    b.Lathe(new[] { new Vector2(0.23f * hk, hy - 0.16f), new Vector2(0.22f * hk, hy + 0.02f), new Vector2(0.17f * hk, hy + 0.15f), new Vector2(0.06f * hk, hy + 0.23f), new Vector2(0f, hy + 0.24f) }, 16, look.cloth);
                    b.Pop();
                }
                if (look.mask)
                {
                    b.Material(0.55f, 0.7f);
                    b.BevelBox(new Vector3(0, hy - 0.02f, 0.14f * hk), new Vector3(0.32f, 0.27f, 0.08f) * hk, 0.035f, Hex("#69707A"));
                    b.Material(0.1f, 0f);
                    b.BevelBox(new Vector3(0, hy + 0.025f, 0.185f * hk), new Vector3(0.24f, 0.05f, 0.012f) * hk, 0.005f, Hex("#151515"));
                    if (look.bw > 1.2f)
                    {
                        b.Material(0.8f, 1f);
                        b.Cylinder(new Vector3(-0.11f, hy + 0.14f, 0), 0.05f, 0.24f, 10, Metal, 0.005f);
                        b.Cylinder(new Vector3(0.11f, hy + 0.14f, 0), 0.05f, 0.24f, 10, Metal, 0.005f);
                    }
                    b.Matte();
                }
                else
                {
                    b.Sphere(new Vector3(-0.065f, hy + 0.03f, 0.16f * hk), new Vector3(0.03f, 0.025f, 0.015f), Hex("#1E1A1A"), 0);
                    b.Sphere(new Vector3(0.065f, hy + 0.03f, 0.16f * hk), new Vector3(0.03f, 0.025f, 0.015f), Hex("#1E1A1A"), 0);
                }
                if (look.goggles)
                {
                    b.Material(0.9f, 0.2f);
                    for (int sx = -1; sx <= 1; sx += 2)
                    {
                        b.Push(new Vector3(sx * 0.07f, hy + 0.05f, 0.15f * hk), Quaternion.Euler(90, 0, 0));
                        b.Lathe(new[] { new Vector2(0.055f, 0f), new Vector2(0.055f, 0.035f), new Vector2(0.038f, 0.04f), new Vector2(0f, 0.044f) }, 14, Glow("#F2A33A", 0.55f));
                        b.Pop();
                    }
                    b.Matte();
                }
                if (look.mohawk)
                {
                    // red crest: a stripe on top of the head from the game camera
                    for (int i = 0; i < 5; i++)
                    {
                        float zz = 0.12f - i * 0.065f;
                        b.Push(new Vector3(0, hy + 0.16f * hk - Mathf.Abs(i - 2) * 0.012f, zz * hk));
                        b.Sphere(Vector3.zero, new Vector3(0.045f, 0.11f - Mathf.Abs(i - 2) * 0.015f, 0.04f), look.accent, 1);
                        b.Pop();
                    }
                }
                if (look.tophat)
                {
                    b.Material(0.45f, 0f);
                    b.Cylinder(new Vector3(0, hy + 0.14f, 0), 0.32f, 0.04f, 20, Hex("#262224"));
                    b.Cylinder(new Vector3(0, hy + 0.17f, 0), 0.2f, 0.36f, 20, Hex("#262224"), 0.21f);
                    b.Material(0.8f, 1f);
                    b.Cylinder(new Vector3(0, hy + 0.2f, 0), 0.205f, 0.06f, 20, look.accent, -1, null, false);
                    b.Matte();
                }
                if (id == ModelId.Raider && !look.goggles) b.Box(new Vector3(0, hy - 0.1f, 0.165f * hk), new Vector3(0.18f, 0.05f, 0.012f), Hex("#3A2A2A"));
                if (look.crystals)
                {
                    b.Material(0.9f, 0f);
                    for (int i = 0; i < 7; i++)
                    {
                        float x = -0.42f + i * 0.14f;
                        b.Push(new Vector3(x, 1.5f + (i % 2) * 0.12f, -0.12f), Quaternion.Euler(-30 + i * 6, 0, (i - 3) * 13));
                        b.Cylinder(Vector3.zero, 0.075f, 0.38f + (i % 3) * 0.12f, 6, Glow("#CFF2FF", 0.75f), 0.01f);
                        b.Pop();
                    }
                    b.Matte();
                }
                if (id == ModelId.BossBaron)
                {
                    // gold chain + oil stain bib
                    b.Material(0.85f, 1f);
                    b.Lathe(new[] { new Vector2(0.3f * bw, 1.5f), new Vector2(0.31f * bw, 1.53f) }, 18, look.accent);
                    b.Matte();
                }
            });
            var torso = MeshGO("Torso", torsoMesh, Mats.Toon, scaler);
            rig.body = torso.transform;

            var legMesh = Cached("leg3_" + k, b =>
            {
                b.Sphere(new Vector3(0, -0.02f, 0), Vector3.one * 0.11f * bw, look.pants, 1);
                b.CylinderBetween(new Vector3(0, 0f, 0), new Vector3(0, -0.45f, 0.01f), 0.1f * bw, 12, look.pants, 0.08f * bw);
                b.CylinderBetween(new Vector3(0, -0.45f, 0.01f), new Vector3(0, -0.8f, 0f), 0.08f * bw, 12, look.pants, 0.07f * bw);
                b.Material(0.3f, 0f);
                b.BevelBox(new Vector3(0, -0.86f, 0.05f), new Vector3(0.18f * bw, 0.16f, 0.32f * bw), 0.05f, BootC);
                b.Matte();
            });
            Mesh ArmMesh(bool left) => Cached("arm3_" + k + (left && look.shield ? "_shield" : ""), b =>
            {
                var sleeve = (id == ModelId.Crossbow || id == ModelId.Scav || id == ModelId.BossBaron) ? look.torso : look.skin;
                b.Sphere(Vector3.zero, Vector3.one * 0.09f * bw, sleeve, 1);
                b.CylinderBetween(Vector3.zero, new Vector3(0, -0.3f, 0), 0.08f * bw, 12, sleeve, 0.066f * bw);
                b.CylinderBetween(new Vector3(0, -0.3f, 0), new Vector3(0, -0.56f, -0.01f), 0.064f * bw, 12, look.skin, 0.054f * bw);
                b.Sphere(new Vector3(0, -0.63f, -0.01f), new Vector3(0.08f, 0.09f, 0.08f) * bw, look.skin, 1);
                if (left && look.shield)
                {
                    // round scrap shield on the forearm, facing forward: an oval disc from the game camera
                    b.Push(new Vector3(0f, -0.42f, 0.1f), Quaternion.Euler(90, 0, 0));
                    b.Material(0.45f, 0.5f);
                    b.Lathe(new[] { new Vector2(0f, -0.04f), new Vector2(0.3f, -0.04f), new Vector2(0.34f, -0.02f), new Vector2(0.3f, 0.02f), new Vector2(0f, 0.04f) }, 20, look.accent);
                    b.Material(0.85f, 1f);
                    b.Sphere(new Vector3(0, 0.05f, 0), new Vector3(0.08f, 0.04f, 0.08f), Chrome, 1);
                    b.Pop();
                    b.Matte();
                }
            });

            rig.legL = Pivot("LegL", scaler, new Vector3(-0.12f * bw, 0.98f, 0), legMesh);
            rig.legR = Pivot("LegR", scaler, new Vector3(0.12f * bw, 0.98f, 0), legMesh);
            rig.armL = Pivot("ArmL", scaler, new Vector3(-0.34f * bw, 1.52f, 0), ArmMesh(true));
            rig.armR = Pivot("ArmR", scaler, new Vector3(0.34f * bw, 1.52f, 0), ArmMesh(false));

            // held weapon (points along -Y of the arm, i.e. down when idle; forward when raised)
            Mesh wMesh = null;
            switch (id)
            {
                case ModelId.Scav:
                    wMesh = Cached("w_pipegun3", b =>
                    {
                        b.Material(0.35f, 0f);
                        b.BevelBox(new Vector3(0, 0.12f, 0.03f), new Vector3(0.09f, 0.28f, 0.14f), 0.03f, Wood);
                        b.Material(0.5f, 0.8f);
                        b.CylinderBetween(new Vector3(0, 0.05f, 0), new Vector3(0, -0.95f, 0), 0.05f, 12, Metal);
                        b.CylinderBetween(new Vector3(0, -0.3f, 0), new Vector3(0, -0.44f, 0), 0.07f, 12, Rust);
                        b.CylinderBetween(new Vector3(0, -0.86f, 0), new Vector3(0, -0.98f, 0), 0.07f, 12, Rust);
                        b.Matte();
                    }); break;
                case ModelId.Raider:
                    wMesh = Cached("w_club3", b =>
                    {
                        b.Material(0.2f, 0f);
                        b.CylinderBetween(new Vector3(0, 0.12f, 0), new Vector3(0, -0.95f, 0), 0.05f, 10, WoodDark, 0.12f);
                        b.Material(0.85f, 1f);
                        for (int i = 0; i < 6; i++)
                        {
                            float a = i * 60f;
                            b.Push(new Vector3(0, -0.55f - (i % 3) * 0.13f, 0), Quaternion.Euler(0, a, 0));
                            b.Push(new Vector3(0.09f, 0, 0), Quaternion.Euler(0, 0, -90));
                            b.Cone(Vector3.zero, 0.025f, 0.16f, 6, Chrome);
                            b.Pop(); b.Pop();
                        }
                        b.Matte();
                    }); break;
                case ModelId.Spearman:
                    wMesh = Cached("w_spear3", b =>
                    {
                        b.CylinderBetween(new Vector3(0, 0.5f, 0), new Vector3(0, -1.65f, 0), 0.04f, 8, WoodDark);
                        b.Material(0.85f, 1f);
                        b.Push(new Vector3(0, -1.62f, 0), Quaternion.Euler(180, 0, 0));
                        b.Push(Vector3.zero, Quaternion.identity, new Vector3(1f, 1f, 0.45f));
                        b.Lathe(new[] { new Vector2(0.03f, 0f), new Vector2(0.11f, 0.12f), new Vector2(0.06f, 0.32f), new Vector2(0f, 0.46f) }, 10, Chrome);
                        b.Pop(); b.Pop();
                        b.Material(0.2f, 0f);
                        b.Lathe(new[] { new Vector2(0.05f, -1.5f), new Vector2(0.05f, -1.38f) }, 10, look.accent);
                        b.Matte();
                    }); break;
                case ModelId.Crossbow:
                    wMesh = Cached("w_xbow3", b =>
                    {
                        // a wide crossbow: the bow arms read as a T shape from the camera
                        b.Material(0.3f, 0f);
                        b.BevelBox(new Vector3(0, -0.45f, 0), new Vector3(0.1f, 0.85f, 0.12f), 0.03f, Wood, WoodLight);
                        b.Material(0.5f, 0.6f);
                        b.Push(new Vector3(0, -0.76f, 0));
                        for (int s = -1; s <= 1; s += 2)
                        {
                            b.CylinderBetween(Vector3.zero, new Vector3(s * 0.32f, -0.03f, 0), 0.04f, 10, MetalDark, 0.03f);
                            b.CylinderBetween(new Vector3(s * 0.32f, -0.03f, 0), new Vector3(s * 0.52f, 0.1f, 0), 0.03f, 10, MetalDark, 0.022f);
                        }
                        b.Pop();
                        b.Material(0.1f, 0f);
                        b.Box(new Vector3(0, -0.6f, 0), new Vector3(1.02f, 0.016f, 0.016f), Hex("#EDE4D2"));
                        b.Material(0.8f, 1f);
                        b.Push(new Vector3(0, -0.92f, 0), Quaternion.Euler(180, 0, 0));
                        b.Cone(Vector3.zero, 0.05f, 0.16f, 8, look.accent);
                        b.Pop();
                        b.Matte();
                    }); break;
                case ModelId.Brute:
                    wMesh = Cached("w_blunderbuss3", b =>
                    {
                        b.Material(0.3f, 0f);
                        b.BevelBox(new Vector3(0, 0.15f, 0.04f), new Vector3(0.13f, 0.44f, 0.2f), 0.04f, WoodDark);
                        b.Material(0.55f, 0.85f);
                        b.CylinderBetween(new Vector3(0, -0.05f, 0), new Vector3(0, -0.95f, 0), 0.08f, 14, MetalDark);
                        b.Push(new Vector3(0, -0.95f, 0), Quaternion.Euler(180, 0, 0));
                        b.Lathe(new[] { new Vector2(0.08f, 0f), new Vector2(0.13f, 0.12f), new Vector2(0.21f, 0.24f), new Vector2(0.14f, 0.24f), new Vector2(0.08f, 0.12f) }, 18, Hex("#C0954E"));
                        b.Pop();
                        b.Material(0.75f, 1f);
                        foreach (float y in new[] { -0.25f, -0.6f })
                            b.CylinderBetween(new Vector3(0, y, 0), new Vector3(0, y - 0.06f, 0), 0.095f, 14, Hex("#C0954E"));
                        b.Matte();
                    }); break;
                case ModelId.BossColossus:
                    wMesh = Cached("w_boneclub3", b =>
                    {
                        b.Material(0.25f, 0f);
                        b.CylinderBetween(new Vector3(0, 0.2f, 0), new Vector3(0, -1.3f, 0), 0.07f, 10, Bone, 0.09f);
                        b.Sphere(new Vector3(0, -1.38f, 0), new Vector3(0.3f, 0.34f, 0.3f), Bone, 1, 0.08f, 4);
                        b.Material(0.9f, 0f);
                        for (int i = 0; i < 4; i++)
                        {
                            b.Push(new Vector3(0, -1.38f, 0), Quaternion.Euler(i * 90f + 20f, 0, 40f));
                            b.Cylinder(new Vector3(0, 0.2f, 0), 0.06f, 0.28f, 6, Glow("#CFF2FF", 0.75f), 0.01f);
                            b.Pop();
                        }
                        b.Matte();
                    }); break;
                case ModelId.BossBaron:
                    wMesh = Cached("w_flamer3", b =>
                    {
                        b.Material(0.55f, 0.8f);
                        b.CylinderBetween(new Vector3(0, 0.1f, 0), new Vector3(0, -1.15f, 0), 0.09f, 12, MetalDark);
                        b.CylinderBetween(new Vector3(0, -0.2f, 0.12f), new Vector3(0, -0.9f, 0.12f), 0.05f, 10, look.accent);
                        b.Material(0.75f, 1f);
                        b.Cylinder(new Vector3(0, -1.25f, 0), 0.14f, 0.14f, 12, Hex("#E06A2A"));
                        b.Material(0.9f, 0f);
                        b.Sphere(new Vector3(0, -1.3f, 0.1f), Vector3.one * 0.06f, Glow("#FFC34A", 0.3f), 1);
                        b.Matte();
                    }); break;
            }
            if (wMesh != null)
            {
                var w = MeshGO("Weapon", wMesh, Mats.Toon, rig.armR);
                w.transform.localPosition = new Vector3(0, -0.6f, 0);
                w.transform.localRotation = Quaternion.Euler(-80, 0, 0);
                rig.weapon = w.transform;
            }
            rig.height = 2.1f * scale * HumanScale;
            rig.CollectRenderers();
            rig.enabled = false;
            return root;
        }

        static Transform Pivot(string name, Transform parent, Vector3 pos, Mesh mesh)
        {
            var p = new GameObject(name).transform;
            p.SetParent(parent, false);
            p.localPosition = pos;
            MeshGO(name + "Mesh", mesh, Mats.Toon, p);
            return p;
        }

        /// <summary>Vehicle wheel: rounded fat tire with chunky lugs and a colored dish hub.</summary>
        static Transform Wheel(Transform parent, Vector3 pos, float r, float w, Rig rig, bool steer, Color tire, Color hub)
        {
            var key = "wheel3_" + r.ToString("0.00") + "_" + w.ToString("0.00") + ColorUtility.ToHtmlStringRGB(hub);
            var mesh = Cached(key, b =>
            {
                b.Push(Vector3.zero, Quaternion.Euler(0, 0, 90));
                float hw = w * 0.5f, rIn = r * 0.58f;
                b.Material(0.14f, 0f);
                b.Lathe(new[]
                {
                    new Vector2(rIn, -hw + 0.03f), new Vector2(r * 0.86f, -hw - 0.01f), new Vector2(r, -hw + r * 0.18f),
                    new Vector2(r, hw - r * 0.18f), new Vector2(r * 0.86f, hw + 0.01f), new Vector2(rIn, hw - 0.03f)
                }, 24, tire);
                for (int i = 0; i < 10; i++)
                    for (int row = -1; row <= 1; row += 2)
                    {
                        float a = i * 36f + (row > 0 ? 18f : 0f);
                        b.Push(Vector3.zero, Quaternion.Euler(0, -a, 0));
                        b.Box(new Vector3(r + r * 0.03f, row * hw * 0.26f, 0), new Vector3(r * 0.07f, hw * 0.62f, r * 0.3f), Shade(tire, 1.25f));
                        b.Pop();
                    }
                b.Material(0.55f, 0.75f);
                foreach (int s in new[] { -1, 1 })
                    b.Lathe(s > 0
                        ? new[] { new Vector2(rIn, hw - 0.03f), new Vector2(rIn * 0.8f, hw - 0.06f), new Vector2(rIn * 0.3f, hw - 0.05f), new Vector2(0f, hw - 0.02f) }
                        : new[] { new Vector2(0f, -hw + 0.02f), new Vector2(rIn * 0.3f, -hw + 0.05f), new Vector2(rIn * 0.8f, -hw + 0.06f), new Vector2(rIn, -hw + 0.03f) }, 18, hub);
                b.Pop();
            });
            var steerT = new GameObject("WheelSteer").transform;
            steerT.SetParent(parent, false);
            steerT.localPosition = pos;
            var spin = MeshGO("Wheel", mesh, Mats.Toon, steerT).transform;
            rig.wheels.Add(spin);
            if (steer) rig.steer.Add(steerT);
            rig.wheelRadius = r;
            return steerT;
        }

        // ------------------------------------------------------------------ vehicles
        /// <summary>Zone colored raider paint, chosen to contrast with that zone's ground.</summary>
        static Color RaiderPaint(ZoneDef z) => z.index == 1 ? Hex("#4F6E8A") : z.index == 2 ? Hex("#B8483A") : z.index == 3 ? Hex("#D4A23A") : Hex("#C4502F");

        public static GameObject Buggy(ZoneDef z)
        {
            var root = new GameObject("Buggy");
            var rig = root.AddComponent<Rig>();
            var bodyCol = RaiderPaint(z);
            var mesh = Cached("buggy3_" + z.index, b =>
            {
                // low rounded tub
                b.Material(0.55f, 0f);
                b.BevelBox(new Vector3(0, 0.62f, 0.05f), new Vector3(1.55f, 0.44f, 2.8f), 0.16f, bodyCol, Shade(bodyCol, 1.1f));
                b.BevelBox(new Vector3(0, 0.82f, 1.05f), new Vector3(1.3f, 0.2f, 0.8f), Quaternion.Euler(8, 0, 0), 0.08f, Shade(bodyCol, 0.88f));
                // engine block + upswept pipes at the back
                b.Material(0.4f, 0.5f);
                b.BevelBox(new Vector3(0, 0.95f, -1.12f), new Vector3(1.05f, 0.46f, 0.64f), 0.08f, MetalDark);
                b.Material(0.8f, 1f);
                foreach (int s in new[] { -1, 1 }) b.CylinderBetween(new Vector3(s * 0.38f, 1.12f, -1.32f), new Vector3(s * 0.5f, 1.72f, -1.55f), 0.075f, 10, Chrome);
                // spiked ram
                b.Material(0.4f, 0.55f);
                b.BevelBox(new Vector3(0, 0.5f, 1.5f), new Vector3(1.6f, 0.2f, 0.16f), 0.05f, MetalDark);
                b.Material(0.85f, 1f);
                for (int i = -2; i <= 2; i++)
                {
                    b.Push(new Vector3(i * 0.32f, 0.52f, 1.56f), Quaternion.Euler(90, 0, 0));
                    b.Cone(Vector3.zero, 0.075f, 0.38f, 8, Chrome);
                    b.Pop();
                }
                // thick roll cage
                var cage = Hex("#2C2C30");
                b.Material(0.45f, 0.6f);
                Vector3[] bot = { new Vector3(-0.66f, 0.8f, 0.5f), new Vector3(0.66f, 0.8f, 0.5f), new Vector3(-0.66f, 0.8f, -0.75f), new Vector3(0.66f, 0.8f, -0.75f) };
                Vector3[] top = { new Vector3(-0.52f, 1.78f, 0.22f), new Vector3(0.52f, 1.78f, 0.22f), new Vector3(-0.52f, 1.78f, -0.66f), new Vector3(0.52f, 1.78f, -0.66f) };
                for (int i = 0; i < 4; i++) b.CylinderBetween(bot[i], top[i], 0.065f, 10, cage);
                b.CylinderBetween(top[0], top[1], 0.065f, 10, cage); b.CylinderBetween(top[2], top[3], 0.065f, 10, cage);
                b.CylinderBetween(top[0], top[2], 0.065f, 10, cage); b.CylinderBetween(top[1], top[3], 0.065f, 10, cage);
                // driver: chunky body, big head with glowing goggles, red scarf
                b.Material(0.15f, 0f);
                b.BevelBox(new Vector3(0, 1.08f, -0.3f), new Vector3(0.46f, 0.5f, 0.32f), 0.12f, Hex("#4A3B34"));
                b.Sphere(new Vector3(0, 1.48f, -0.27f), new Vector3(0.2f, 0.21f, 0.2f), SkinPale, 2);
                b.Lathe(new[] { new Vector2(0.17f, 1.3f), new Vector2(0.19f, 1.36f) }, 14, EnemyRed);
                b.Material(0.9f, 0.2f);
                foreach (int s in new[] { -1, 1 })
                {
                    b.Push(new Vector3(s * 0.075f, 1.52f, -0.1f), Quaternion.Euler(90, 0, 0));
                    b.Lathe(new[] { new Vector2(0.06f, 0f), new Vector2(0.06f, 0.03f), new Vector2(0f, 0.04f) }, 12, Glow("#F2A33A", 0.6f));
                    b.Pop();
                }
                // flag
                b.Material(0.2f, 0f);
                b.Cylinder(new Vector3(0.48f, 1.8f, -0.66f), 0.025f, 0.7f, 8, cage);
                b.BevelBox(new Vector3(0.68f, 2.38f, -0.66f), new Vector3(0.38f, 0.24f, 0.03f), 0.01f, EnemyRed);
                b.Matte();
            });
            var body = MeshGO("Body", mesh, Mats.Toon, root.transform);
            rig.body = body.transform;
            var gunMesh = Cached("buggy_mg3", b =>
            {
                b.Material(0.45f, 0.7f);
                b.Cylinder(new Vector3(0, -0.25f, 0), 0.06f, 0.25f, 10, MetalDark);
                b.BevelBox(new Vector3(0, 0.06f, 0.05f), new Vector3(0.26f, 0.2f, 0.46f), 0.05f, Hex("#3A3D40"));
                b.Material(0.6f, 0.9f);
                foreach (float x in new[] { -0.06f, 0.06f })
                    b.CylinderBetween(new Vector3(x, 0.08f, 0.2f), new Vector3(x, 0.08f, 1.0f), 0.032f, 10, Hex("#2A2C2E"));
                b.Material(0.4f, 0.3f);
                b.BevelBox(new Vector3(0, 0.15f, 0.3f), new Vector3(0.6f, 0.34f, 0.04f), Quaternion.Euler(-10, 0, 0), 0.015f, EnemyRed);
                b.BevelBox(new Vector3(0.2f, 0.02f, -0.02f), new Vector3(0.12f, 0.15f, 0.22f), 0.03f, Hex("#5B5E3C"));
                b.Matte();
            });
            var gun = MeshGO("Gun", gunMesh, Mats.Toon, body.transform).transform;
            gun.localPosition = new Vector3(0, 2.0f, 0.22f);   // on the front cross bar of the roll cage
            rig.turret = gun;
            rig.muzzle = new GameObject("Muzzle").transform;
            rig.muzzle.SetParent(gun, false);
            rig.muzzle.localPosition = new Vector3(0, 0.08f, 1.03f);
            Wheel(body.transform, new Vector3(-0.86f, 0.5f, 1.0f), 0.5f, 0.38f, rig, true, TireC, MetalDark);
            Wheel(body.transform, new Vector3(0.86f, 0.5f, 1.0f), 0.5f, 0.38f, rig, true, TireC, MetalDark);
            Wheel(body.transform, new Vector3(-0.9f, 0.6f, -1.0f), 0.6f, 0.52f, rig, false, TireC, MetalDark);
            Wheel(body.transform, new Vector3(0.9f, 0.6f, -1.0f), 0.6f, 0.52f, rig, false, TireC, MetalDark);
            rig.height = 2.1f;
            rig.CollectRenderers();
            rig.enabled = false;
            return root;
        }

        // ------------------------------------------------------------------ harpoon turret + its operator ("Quasimodo")
        /// <summary>
        /// The harpoon turret in the bed and its hooded operator. root = the base plate bolted to the bed floor; yaw = the
        /// turning part (collar, column, yoke) that also carries the operator: he walks round the column with the turret,
        /// always behind it. gun = the launcher (pitch, recoil) with the rope reel, the two rear handles and the loaded
        /// harpoon (tip) at its muzzle. The legs step when the turret turns fast, the body leans from the hips, the head
        /// bobs and the arms are solved every frame (two-bone IK) so the hands never let go of the handles.
        /// </summary>
        public class HarpoonerRig
        {
            public Transform root, yaw, gun, muzzle, tip;
            public Transform crew, body, head;
            public readonly Transform[] leg = new Transform[2];
            public readonly Transform[] shoulder = new Transform[2], grip = new Transform[2];
            public readonly Transform[] upperArm = new Transform[2], foreArm = new Transform[2], glove = new Transform[2];
            public const float UpperLen = 0.28f, ForeLen = 0.27f;
            public Vector3 bodyRest, gunRest;
        }

        /// <summary>Launcher trunnions above the bed floor: pointing ahead, the harpoon clears the cab roof.</summary>
        public const float HarpoonPivotY = 0.80f;
        /// <summary>The operator's feet behind the column (he stays inside the bed in every direction).</summary>
        public const float HarpoonCrewBack = 0.54f;
        /// <summary>Launcher pitch at rest (negative = muzzle up).</summary>
        public const float HarpoonRestPitch = -6f;
        const float HarpoonMuzzleZ = 0.57f;
        // launcher space: the right and the left handle
        static readonly Vector3[] HGrip = { new Vector3(0.155f, 0f, -0.262f), new Vector3(-0.155f, 0f, -0.262f) };

        // the operator, crew space: feet on the floor round the origin, facing +Z (the column)
        static readonly Vector3 QBodyPivot = new Vector3(0f, 0.62f, -0.04f);    // hips
        static readonly Vector3 QNeckPivot = new Vector3(0f, 1.03f, 0.19f);
        static readonly Vector3 QHeadShift = new Vector3(0f, 0.02f, 0.035f);   // the head pushed forward out of the hunch
        static readonly Vector3[] QHip = { new Vector3(0.1f, 0.6f, -0.03f), new Vector3(-0.1f, 0.6f, -0.03f) };
        static readonly Vector3[] QShoulder = { new Vector3(0.215f, 1.03f, 0.1f), new Vector3(-0.2f, 0.975f, 0.1f) };   // the hump pulls the right one up

        // a grim wasteland outcast: dark tattered cloak with the hood up, pale weathered skin, grey stubble, brown boots
        static readonly Color QCloak = Hex("#5D4535"), QCloakDark = Hex("#4A372A"), QCloakLight = Hex("#73573F"), QHole = Hex("#2A1F18");
        static readonly Color QHoodIn = Hex("#1F1712"), QSkin = Hex("#C9A386"), QSkinLight = Hex("#D5B399"), QSkinShade = Hex("#A57E65");
        static readonly Color QSocket = Hex("#6E5242"), QStubble = Hex("#8E8780"), QBrow = Hex("#4A3B33"), QTeeth = Hex("#D7CB9C");
        static readonly Color QMouth = Hex("#3A1F1A"), QEyeWhite = Hex("#D6CBB0"), QPupil = Hex("#17110E"), QTrousers = Hex("#3C3732");
        static readonly Color QBoots = Hex("#6A4A33"), QSole = Hex("#33251C"), QWrap = Hex("#7B6B57");
        // the turret: steel, the hero teal on the reel flanges and the collar, cream rope, dark rubber grips
        static readonly Color HSteel = Hex("#59616A"), HSteelDark = Hex("#464D55"), HSteelLight = Hex("#8E979F"), HGripC = Hex("#2B2622");

        /// <summary>Closed torus around local Y (lathe of a circle): rims, rolled cuffs, rope belts.</summary>
        static void TorusY(MeshBuilder b, float R, float r, int segs, int minor, Color c)
        {
            var prof = new Vector2[minor + 1];
            for (int i = 0; i <= minor; i++)
            {
                float a = i / (float)minor * Mathf.PI * 2f;
                prof[i] = new Vector2(R + Mathf.Cos(a) * r, Mathf.Sin(a) * r);
            }
            b.Lathe(prof, segs, c);
        }

        /// <summary>Deterministic 0..1 value per integer (frayed hems, uneven folds).</summary>
        static float Hash01(int k)
        {
            float v = Mathf.Sin(k * 12.9898f + 78.233f) * 43758.5453f;
            return v - Mathf.Floor(v);
        }

        /// <summary>The harpoon turret with its operator on the car body (bed floor). The returned rig's yaw is the turning part.</summary>
        public static HarpoonerRig Harpooner(Transform carBody)
        {
            // explicit sphere detail below (no automatic bump)
            float quality = MeshBuilder.Quality;
            MeshBuilder.Quality = 1f;
            try { return BuildHarpooner(carBody); }
            finally { MeshBuilder.Quality = quality; }
        }

        static HarpoonerRig BuildHarpooner(Transform carBody)
        {
            var r = new HarpoonerRig();
            r.root = new GameObject("Harpooner").transform;
            r.root.SetParent(carBody, false);
            r.root.localPosition = HarpoonMount;
            MeshGO("TurretBase", Cached("harpoonturret_base_v8", HarpoonBaseMesh), Mats.Toon, r.root);
            r.yaw = new GameObject("TurretYaw").transform;
            r.yaw.SetParent(r.root, false);
            MeshGO("Column", Cached("harpoonturret_column_v8", HarpoonColumnMesh), Mats.Toon, r.yaw);

            // ---- launcher (pitch / recoil): body, rope reel, barrel, rear handles, the loaded harpoon
            r.gun = new GameObject("Launcher").transform;
            r.gun.SetParent(r.yaw, false);
            r.gun.localPosition = r.gunRest = new Vector3(0f, HarpoonPivotY, 0f);
            r.gun.localRotation = Quaternion.Euler(HarpoonRestPitch, 0f, 0f);
            MeshGO("LauncherMesh", Cached("harpoonturret_launcher_v8", HarpoonLauncherMesh), Mats.Toon, r.gun);
            r.muzzle = new GameObject("Muzzle").transform;
            r.muzzle.SetParent(r.gun, false);
            r.muzzle.localPosition = new Vector3(0f, 0f, HarpoonMuzzleZ);
            r.tip = MeshGO("HarpoonTip", HarpoonHeadMesh(), Mats.Toon, r.muzzle).transform;
            r.tip.localPosition = new Vector3(0f, 0f, 0.1f);   // shaft in the barrel, barbed head out front
            r.tip.localScale = Vector3.one * 1.05f;
            for (int i = 0; i < 2; i++)
            {
                r.grip[i] = new GameObject(i == 0 ? "GripR" : "GripL").transform;
                r.grip[i].SetParent(r.gun, false);
                r.grip[i].localPosition = HGrip[i];
            }

            // ---- the operator rides the turning part, behind the column
            r.crew = new GameObject("Quasimodo").transform;
            r.crew.SetParent(r.yaw, false);
            r.crew.localPosition = new Vector3(0f, 0f, -HarpoonCrewBack);
            BuildOperator(r);
            SolveHarpoonerArms(r);
            return r;
        }

        /// <summary>Base plate bolted to the bed floor (root space: the floor is y = 0).</summary>
        static void HarpoonBaseMesh(MeshBuilder b)
        {
            b.Material(0.4f, 0.6f);
            b.Lathe(new[] { new Vector2(0.23f, 0f), new Vector2(0.23f, 0.026f), new Vector2(0.214f, 0.036f), new Vector2(0f, 0.036f) }, 28, HSteelDark);
            b.Material(0.85f, 1f);
            for (int i = 0; i < 8; i++)
            {
                float a = (22.5f + i * 45f) * Mathf.Deg2Rad;
                b.Cylinder(new Vector3(Mathf.Cos(a) * 0.195f, 0.036f, Mathf.Sin(a) * 0.195f), 0.014f, 0.01f, 6, HSteelLight);
            }
            b.Matte();
        }

        /// <summary>The turning part (yaw space): collar with a teal band, flared column, the yoke and its trunnion caps.</summary>
        static void HarpoonColumnMesh(MeshBuilder b)
        {
            b.Material(0.45f, 0.6f);
            b.Lathe(new[] { new Vector2(0.165f, 0.036f), new Vector2(0.165f, 0.1f), new Vector2(0.15f, 0.115f), new Vector2(0f, 0.115f) }, 24, HSteel);
            b.Material(0.6f, 0.3f);
            b.Lathe(new[] { new Vector2(0.168f, 0.062f), new Vector2(0.168f, 0.088f) }, 24, CarAccent);
            b.Material(0.5f, 0.7f);
            b.Cylinder(new Vector3(0f, 0.115f, 0f), 0.11f, 0.09f, 18, HSteel, 0.075f);
            b.Cylinder(new Vector3(0f, 0.2f, 0f), 0.072f, 0.43f, 16, HSteel);
            b.Material(0.4f, 0.6f);
            b.BevelBox(new Vector3(0f, 0.652f, 0f), new Vector3(0.31f, 0.045f, 0.15f), 0.015f, HSteelDark);
            for (int s = -1; s <= 1; s += 2)
            {
                b.BevelBox(new Vector3(s * 0.137f, 0.735f, 0f), new Vector3(0.03f, 0.15f, 0.13f), 0.008f, HSteelDark);
                b.CylinderBetween(new Vector3(s * 0.122f, HarpoonPivotY, 0f), new Vector3(s * 0.152f, HarpoonPivotY, 0f), 0.065f, 16, HSteelDark);
                b.Material(0.85f, 1f);
                b.CylinderBetween(new Vector3(s * 0.152f, HarpoonPivotY, 0f), new Vector3(s * 0.168f, HarpoonPivotY, 0f), 0.034f, 12, HSteelLight);
                b.Material(0.4f, 0.6f);
            }
            b.Matte();
        }

        /// <summary>The launcher (pivot at the origin, +Z = forward): steel body, cream rope reel between teal flanges,
        /// a short barrel with a light muzzle ring, a T-handle with two rubber grips at the back.</summary>
        static void HarpoonLauncherMesh(MeshBuilder b)
        {
            b.Material(0.55f, 0.8f);
            b.CylinderBetween(new Vector3(0f, 0f, -0.2f), new Vector3(0f, 0f, 0.38f), 0.08f, 18, HSteel);
            b.Sphere(new Vector3(0f, 0f, -0.2f), new Vector3(0.08f, 0.08f, 0.05f), HSteel, 2);
            b.Material(0.4f, 0.6f);
            b.CylinderBetween(new Vector3(-0.122f, 0f, 0f), new Vector3(0.122f, 0f, 0f), 0.04f, 12, HSteelDark);
            // rope reel
            b.Material(0.2f, 0f);
            b.CylinderBetween(new Vector3(0f, 0f, 0.1f), new Vector3(0f, 0f, 0.28f), 0.115f, 20, CarRope);
            foreach (float z in new[] { 0.135f, 0.19f, 0.245f })
                b.CylinderBetween(new Vector3(0f, 0f, z), new Vector3(0f, 0f, z + 0.006f), 0.1165f, 20, Shade(CarRope, 0.8f));
            b.Material(0.6f, 0.35f);
            foreach (float z in new[] { 0.08f, 0.28f })
                b.CylinderBetween(new Vector3(0f, 0f, z), new Vector3(0f, 0f, z + 0.02f), 0.145f, 22, CarAccent);
            // barrel and muzzle ring
            b.Material(0.75f, 0.9f);
            b.CylinderBetween(new Vector3(0f, 0f, 0.38f), new Vector3(0f, 0f, 0.53f), 0.05f, 16, HSteelLight);
            b.Material(0.85f, 1f);
            b.CylinderBetween(new Vector3(0f, 0f, 0.52f), new Vector3(0f, 0f, HarpoonMuzzleZ), 0.062f, 18, CarSteel);
            b.Material(0.1f, 0f);
            b.Push(new Vector3(0f, 0f, HarpoonMuzzleZ + 0.001f), Quaternion.Euler(90f, 0f, 0f));
            b.Disc(Vector3.zero, 0.04f, 14, Hex("#121315"));
            b.Pop();
            // sight on top
            b.Material(0.4f, 0.6f);
            b.BevelBox(new Vector3(0f, 0.095f, 0.0f), new Vector3(0.022f, 0.035f, 0.06f), 0.006f, HSteelDark);
            // T-handle: stem, bar, rubber grips
            b.CylinderBetween(new Vector3(0f, 0f, -0.24f), new Vector3(0f, 0f, -0.262f), 0.03f, 12, HSteelDark);
            b.CylinderBetween(new Vector3(-0.115f, 0f, -0.262f), new Vector3(0.115f, 0f, -0.262f), 0.02f, 10, HSteelDark);
            b.Material(0.2f, 0f);
            foreach (int s in new[] { -1, 1 })
                b.CylinderBetween(new Vector3(s * 0.112f, 0f, -0.262f), new Vector3(s * 0.205f, 0f, -0.262f), 0.027f, 12, HGripC);
            b.Matte();
        }

        static void BuildOperator(HarpoonerRig r)
        {
            var crew = r.crew;
            // ---- legs (they step when the turret turns fast)
            for (int i = 0; i < 2; i++)
            {
                int s = i == 0 ? 1 : -1;
                r.leg[i] = new GameObject(i == 0 ? "LegR" : "LegL").transform;
                r.leg[i].SetParent(crew, false);
                r.leg[i].localPosition = QHip[i];
                MeshGO("LegMesh", Cached("quasimodo_leg_v8_" + s, b => QuasiLeg(b, s)), Mats.Toon, r.leg[i]);
            }
            // ---- body under the cloak (leans from the hips)
            r.body = new GameObject("Body").transform;
            r.body.SetParent(crew, false);
            r.body.localPosition = r.bodyRest = QBodyPivot;
            MeshGO("Cloak", Cached("quasimodo_body_v8", QuasiBody), Mats.Toon, r.body);
            // ---- head in the hood
            r.head = new GameObject("Head").transform;
            r.head.SetParent(r.body, false);
            r.head.localPosition = QNeckPivot - QBodyPivot;
            MeshGO("HeadMesh", Cached("quasimodo_head_v8", QuasiHead), Mats.Toon, r.head);
            // ---- arms in ragged sleeves, bare hands on the handles
            var upperMesh = Cached("quasimodo_upperarm_v8", b =>
            {
                b.Material(0.08f, 0f);
                b.Sphere(Vector3.zero, Vector3.one * 0.066f, QCloak, 2);
                b.CylinderBetween(Vector3.zero, new Vector3(0, 0, HarpoonerRig.UpperLen), 0.066f, 10, QCloak, 0.06f);
                b.Sphere(new Vector3(0, 0, HarpoonerRig.UpperLen), Vector3.one * 0.066f, QCloakDark, 2);
                b.Matte();
            });
            var foreMesh = Cached("quasimodo_forearm_v8", b =>
            {
                const float L = HarpoonerRig.ForeLen;
                b.Material(0.08f, 0f);
                b.CylinderBetween(Vector3.zero, new Vector3(0, 0, L - 0.085f), 0.063f, 10, QCloak, 0.06f);
                // ragged cuff: uneven flaps hanging off the sleeve's end
                for (int k = 0; k < 7; k++)
                {
                    float a = k / 7f * Mathf.PI * 2f, a1 = (k + 0.85f) / 7f * Mathf.PI * 2f;
                    float len = 0.03f + Hash01(k + 11) * 0.035f;
                    var p0 = new Vector3(Mathf.Cos(a) * 0.061f, Mathf.Sin(a) * 0.061f, L - 0.09f);
                    var p1 = new Vector3(Mathf.Cos(a1) * 0.061f, Mathf.Sin(a1) * 0.061f, L - 0.09f);
                    var tip = (p0 + p1) * 0.5f * 0.94f + new Vector3(0, 0, len);
                    b.PolyOut(QCloakDark, new Vector3(0, 0, L - 0.09f), p0, p1, tip);
                    b.PolyOut(QCloakDark, new Vector3(0, 0, L + 0.2f), p1, p0, tip);
                }
                b.Material(0.25f, 0f);
                b.CylinderBetween(new Vector3(0, 0, L - 0.1f), new Vector3(0, 0, L - 0.03f), 0.038f, 10, QSkin, 0.036f);
                b.Matte();
            });
            for (int i = 0; i < 2; i++)
            {
                int side = i == 0 ? 1 : -1;
                r.shoulder[i] = new GameObject(i == 0 ? "ShoulderR" : "ShoulderL").transform;
                r.shoulder[i].SetParent(r.body, false);
                r.shoulder[i].localPosition = QShoulder[i] - QBodyPivot;
                r.upperArm[i] = MeshGO(i == 0 ? "UpperArmR" : "UpperArmL", upperMesh, Mats.Toon, crew).transform;
                r.foreArm[i] = MeshGO(i == 0 ? "ForeArmR" : "ForeArmL", foreMesh, Mats.Toon, crew).transform;
                r.glove[i] = MeshGO(i == 0 ? "HandR" : "HandL", Cached("quasimodo_hand_v8_" + side, b => QuasiHand(b, side)), Mats.Toon, crew).transform;
            }
        }

        /// <summary>One leg in the hip joint's space: dark trousers, a cloth wrap round the shin, a worn brown boot.</summary>
        static void QuasiLeg(MeshBuilder b, int s)
        {
            var knee = new Vector3(s * 0.03f, -0.245f, 0.12f);
            var ankle = new Vector3(s * 0.02f, -0.49f, 0.05f);
            b.Material(0.12f, 0f);
            b.Sphere(Vector3.zero, Vector3.one * 0.076f, QTrousers, 2);
            b.CylinderBetween(Vector3.zero, knee, 0.073f, 10, QTrousers, 0.064f);
            b.Sphere(knee, Vector3.one * 0.066f, QTrousers, 2);
            b.CylinderBetween(knee, ankle, 0.061f, 10, QTrousers, 0.054f);
            // cloth wrap round the shin
            b.Material(0.05f, 0f);
            b.CylinderBetween(Vector3.Lerp(knee, ankle, 0.35f), Vector3.Lerp(knee, ankle, 0.5f), 0.064f, 10, QWrap, 0.06f);
            // boot: shaft to mid calf, rounded foot, toe cap, thick sole
            b.Material(0.35f, 0f);
            b.CylinderBetween(ankle + new Vector3(0, -0.03f, 0), ankle + new Vector3(s * 0.004f, 0.12f, 0.022f), 0.07f, 12, QBoots, 0.066f);
            b.Sphere(ankle + new Vector3(0, 0.12f, 0.022f), new Vector3(0.068f, 0.014f, 0.068f), Shade(QBoots, 0.85f), 1);
            b.Sphere(new Vector3(s * 0.02f, -0.545f, 0.11f), new Vector3(0.07f, 0.05f, 0.115f), QBoots, 2);
            b.Sphere(new Vector3(s * 0.02f, -0.552f, 0.19f), new Vector3(0.06f, 0.04f, 0.05f), Shade(QBoots, 1.1f), 2);
            b.Material(0.2f, 0f);
            b.BevelBox(new Vector3(s * 0.02f, -0.58f, 0.1f), new Vector3(0.12f, 0.03f, 0.25f), 0.012f, QSole);   // 5 mm over the floor
            b.Matte();
        }

        /// <summary>Hunched body (body space = hips pivot): a lumpy hump with the right shoulder higher, a rope belt and a
        /// long skirt with a frayed hem and torn strips; over it a ragged cape from the hood over the hump and shoulders.</summary>
        static void QuasiBody(MeshBuilder b)
        {
            b.Push(-QBodyPivot);
            b.Material(0.08f, 0f);
            b.Sphere(new Vector3(0f, 0.64f, -0.06f), new Vector3(0.19f, 0.13f, 0.16f), QTrousers, 2);
            b.Sphere(new Vector3(0f, 0.85f, 0.07f), new Vector3(0.22f, 0.19f, 0.19f), QCloak, 3);
            b.Sphere(new Vector3(0f, 0.98f, 0.1f), new Vector3(0.24f, 0.12f, 0.16f), QCloak, 3);
            b.Sphere(new Vector3(0.04f, 1.08f, -0.07f), new Vector3(0.26f, 0.2f, 0.235f), QCloak, 3, 0.05f, 7);   // the hump
            b.Sphere(new Vector3(-0.07f, 1.11f, -0.03f), new Vector3(0.16f, 0.13f, 0.16f), QCloak, 2, 0.04f, 9);
            b.Sphere(new Vector3(0.19f, 1.03f, 0.1f), new Vector3(0.1f, 0.095f, 0.1f), QCloak, 2);
            b.Sphere(new Vector3(-0.18f, 0.975f, 0.1f), new Vector3(0.095f, 0.09f, 0.095f), QCloak, 2);
            // rope belt
            b.Material(0.2f, 0f);
            b.Push(new Vector3(0f, 0.8f, -0.005f), Quaternion.Euler(-8f, 0f, 0f), new Vector3(1f, 1f, 0.92f));
            TorusY(b, 0.228f, 0.016f, 24, 6, QWrap);
            b.Pop();
            // skirt: from the waist to a frayed hem (above the bed rails when he stands at a side), fold strips
            const int N = 22;
            float[] ys = { 0.9f, 0.78f, 0.66f, 0.57f, 0.5f };
            float[] rxs = { 0.215f, 0.235f, 0.255f, 0.27f, 0.282f };
            float[] rzs = { 0.198f, 0.21f, 0.222f, 0.23f, 0.236f };
            float[] czs = { 0.02f, 0.005f, -0.01f, -0.018f, -0.022f };
            Drape(b, N, ys, rxs, rzs, czs, 0.07f, 1, QCloak, QCloakDark);   // no bulge low down: clear of the cab's back wall
            // ragged cape from the hood down over the hump and the shoulders (the arms come out under it)
            float[] cys = { 1.33f, 1.27f, 1.18f, 1.07f, 0.97f, 0.88f };
            float[] crx = { 0.09f, 0.19f, 0.27f, 0.315f, 0.33f, 0.335f };
            float[] crz = { 0.09f, 0.18f, 0.245f, 0.285f, 0.3f, 0.305f };
            float[] ccz = { -0.02f, -0.01f, 0.0f, 0.01f, 0.02f, 0.025f };
            Drape(b, 24, cys, crx, crz, ccz, 0.1f, 5, Shade(QCloak, 1.07f), QCloakDark, 1.3f);   // the hump bulges it out at the back
            // a few worn, darker patches on the back
            b.Material(0.05f, 0f);
            b.Sphere(new Vector3(0.13f, 1.12f, -0.22f), new Vector3(0.075f, 0.05f, 0.04f), QCloakDark, 1, 0.25f, 11);
            b.Sphere(new Vector3(-0.17f, 1.0f, -0.2f), new Vector3(0.06f, 0.07f, 0.04f), QCloakDark, 1, 0.25f, 12);
            b.Matte();
            b.Pop();
        }

        /// <summary>A hanging cloth tube: sections from the top down (deeper at the back by backBulge), the last one frayed
        /// (uneven hem), torn strips under the hem every third point, folds in uneven tones.</summary>
        static void Drape(MeshBuilder b, int n, float[] ys, float[] rxs, float[] rzs, float[] czs, float fray, int seed, Color c, Color dark, float backBulge = 1f)
        {
            int last = ys.Length - 1;
            var grid = new Vector3[ys.Length][];
            for (int i = 0; i < ys.Length; i++)
            {
                grid[i] = new Vector3[n];
                for (int k = 0; k < n; k++)
                {
                    float a = k / (float)n * Mathf.PI * 2f;
                    float wob = 1f + (Hash01(k * 7 + i + seed * 31) - 0.5f) * 0.07f * i / Mathf.Max(1, last);
                    float y = ys[i];
                    if (i == last) y += (Hash01(k * 3 + seed) - 0.35f) * fray;   // frayed hem
                    float cz = Mathf.Cos(a);
                    float rz = rzs[i] * (cz < 0f ? Mathf.Lerp(1f, backBulge, -cz) : 1f);
                    grid[i][k] = new Vector3(Mathf.Sin(a) * rxs[i] * wob, y, czs[i] + cz * rz * wob);
                }
            }
            b.Material(0.06f, 0f);
            b.Loft(grid, (i, k) =>
            {
                float h = Hash01(k * 13 + seed * 7);
                return h < 0.18f ? dark : Shade(c, 0.9f + Hash01(k * 5 + seed) * 0.16f);   // uneven folds, a few deep ones
            }, true, i => new Vector3(0f, ys[i], czs[i]));
            for (int k = 0; k < n; k += 3)
            {
                int k1 = (k + 1) % n;
                var p0 = grid[last][k]; var p1 = grid[last][k1];
                var mid = (p0 + p1) * 0.5f;
                var tip = new Vector3(mid.x * 1.04f, Mathf.Min(p0.y, p1.y) - 0.035f - Hash01(k + 40 + seed) * 0.03f, czs[last] + (mid.z - czs[last]) * 1.04f);
                var inside = new Vector3(0f, mid.y, czs[last]);
                b.PolyOut(dark, inside, p0, p1, tip);
                b.PolyOut(dark, mid * 2f - inside, p1, p0, tip);
            }
        }

        /// <summary>
        /// The head in its hood (head space = neck pivot): a deep hood with a pointed back, a lighter rim and a dark inside;
        /// in it a pale, bald, weathered face - a heavy uneven brow ridge, small deep-set eyes (the left one narrowed), a
        /// broad crooked nose, sunken cheeks, grey stubble and a lopsided grimace with a few crooked teeth.
        /// </summary>
        static void QuasiHead(MeshBuilder b)
        {
            b.Push(-QNeckPivot + QHeadShift);
            // neck (inside the hood)
            b.Material(0.2f, 0f);
            b.CylinderBetween(new Vector3(0f, 0.97f, 0.14f), new Vector3(0f, 1.05f, 0.22f), 0.06f, 10, QSkinShade);
            // hood: a deep cowl open at the front, tapering to a point at the back; dark inside, a lighter rim
            const int N = 22;
            float[] zs = { -0.07f, 0.0f, 0.07f, 0.14f, 0.21f, 0.27f, 0.315f };
            float[] cy = { 1.31f, 1.255f, 1.2f, 1.155f, 1.13f, 1.115f, 1.11f };
            float[] rx = { 0.012f, 0.085f, 0.145f, 0.178f, 0.186f, 0.178f, 0.166f };
            float[] ry = { 0.012f, 0.08f, 0.15f, 0.192f, 0.205f, 0.2f, 0.192f };
            float[] shear = { 0f, 0f, 0f, 0.03f, 0.08f, 0.14f, 0.176f };   // the opening leans back: its top overhangs the face
            var grid = new Vector3[zs.Length][];
            for (int i = 0; i < zs.Length; i++)
            {
                grid[i] = new Vector3[N];
                for (int k = 0; k < N; k++)
                {
                    float a = k / (float)N * Mathf.PI * 2f;
                    float wob = 1f + (Hash01(k * 5 + i * 3) - 0.5f) * 0.05f * Mathf.Min(1f, i / 3f);
                    float up = Mathf.Max(0f, Mathf.Sin(a));
                    float dy = Mathf.Sin(a) * ry[i] * wob + up * up * up * 0.035f * Mathf.Clamp01((i - 4) / 2f);   // pointed at the top near the opening
                    grid[i][k] = new Vector3(Mathf.Cos(a) * rx[i] * wob, cy[i] + dy, zs[i] + dy * shear[i]);
                }
            }
            b.Material(0.06f, 0f);
            b.Loft(grid, (i, k) => k % 4 == 0 ? QCloakDark : QCloak, true, i => new Vector3(0f, cy[i], zs[i]));
            b.Material(0.02f, 0f);
            b.Sphere(new Vector3(0f, 1.115f, 0.2f), new Vector3(0.148f, 0.172f, 0.1f), QHoodIn, 2);
            b.Material(0.06f, 0f);
            var lip = new List<Vector3>();
            for (int k = 0; k <= 28; k++)
            {
                float t = k / 28f * Mathf.PI * 2f;
                float up = Mathf.Max(0f, Mathf.Cos(t));
                float r = 1f + (Hash01(k % 28 + 50) - 0.5f) * 0.08f;
                float dy = (Mathf.Cos(t) * ry[6] + up * up * up * 0.035f) * r;    // a slightly pointed top
                lip.Add(new Vector3(Mathf.Sin(t) * (rx[6] - 0.004f) * r, cy[6] + dy, zs[6] + dy * shear[6] + 0.004f));
            }
            b.Sweep(lip, MeshBuilder.CircleProfile(0.016f, 8), Shade(QCloak, 1.12f), false, false);
            // face, set a little back in the opening
            b.Material(0.22f, 0f);
            b.Sphere(new Vector3(0f, 1.095f, 0.26f), new Vector3(0.1f, 0.13f, 0.09f), QSkin, 3);
            b.Sphere(new Vector3(0f, 1.165f, 0.27f), new Vector3(0.095f, 0.065f, 0.075f), QSkinLight, 2);   // bald pale forehead
            b.Sphere(new Vector3(0.104f, 1.1f, 0.243f), new Vector3(0.02f, 0.042f, 0.028f), QSkin, 1);      // ears in the hood
            b.Sphere(new Vector3(-0.104f, 1.095f, 0.243f), new Vector3(0.02f, 0.04f, 0.028f), QSkin, 1);
            // forehead creases
            b.Material(0.1f, 0f);
            for (int w = 0; w < 2; w++)
            {
                var crease = new List<Vector3>();
                for (int k = 0; k <= 6; k++)
                {
                    float t = k / 6f, x = Mathf.Lerp(-0.05f, 0.052f, t), y = 1.18f + w * 0.017f + Mathf.Sin(t * Mathf.PI * 2f + w) * 0.003f;
                    crease.Add(new Vector3(x, y, 0.341f - w * 0.003f - Mathf.Abs(x) * 0.12f));
                }
                b.Sweep(crease, MeshBuilder.CircleProfile(0.0035f, 5), QSkinShade);
            }
            // heavy uneven brow ridge (the left one lower: a glower), bristly brows on it
            b.Material(0.2f, 0f);
            b.Push(new Vector3(0.046f, 1.143f, 0.338f), Quaternion.Euler(0f, 0f, 14f));
            b.Sphere(Vector3.zero, new Vector3(0.052f, 0.022f, 0.028f), QSkinShade, 2);
            b.Sphere(new Vector3(0f, 0.01f, 0.014f), new Vector3(0.04f, 0.009f, 0.012f), QBrow, 1);
            b.Pop();
            b.Push(new Vector3(-0.048f, 1.134f, 0.338f), Quaternion.Euler(0f, 0f, -18f));
            b.Sphere(Vector3.zero, new Vector3(0.05f, 0.025f, 0.028f), QSkinShade, 2);
            b.Sphere(new Vector3(0f, 0.011f, 0.014f), new Vector3(0.039f, 0.011f, 0.012f), QBrow, 1);
            b.Pop();
            // small deep-set eyes under it: the right one open and staring, the left one narrowed
            b.Material(0.3f, 0f);
            b.Sphere(new Vector3(0.045f, 1.114f, 0.328f), new Vector3(0.026f, 0.017f, 0.012f), QSocket, 1);
            b.Sphere(new Vector3(-0.046f, 1.11f, 0.328f), new Vector3(0.025f, 0.013f, 0.012f), QSocket, 1);
            b.Material(0.6f, 0f);
            b.Sphere(new Vector3(0.045f, 1.114f, 0.335f), new Vector3(0.015f, 0.0105f, 0.008f), QEyeWhite, 1);
            b.Sphere(new Vector3(-0.046f, 1.11f, 0.335f), new Vector3(0.014f, 0.0055f, 0.008f), QEyeWhite, 1);
            b.Material(0.9f, 0f);
            b.Sphere(new Vector3(0.043f, 1.113f, 0.342f), new Vector3(0.0065f, 0.0065f, 0.003f), QPupil, 1);
            b.Sphere(new Vector3(-0.044f, 1.11f, 0.342f), new Vector3(0.006f, 0.0045f, 0.003f), QPupil, 1);
            // broad flattened crooked nose
            b.Material(0.25f, 0f);
            b.CylinderBetween(new Vector3(0.002f, 1.126f, 0.348f), new Vector3(0.012f, 1.092f, 0.37f), 0.013f, 8, QSkin);
            b.Push(new Vector3(0.011f, 1.08f, 0.364f), Quaternion.Euler(0f, 0f, 12f));
            b.Sphere(Vector3.zero, new Vector3(0.034f, 0.029f, 0.033f), QSkin, 2);
            b.Pop();
            b.Material(0.1f, 0f);
            b.Sphere(new Vector3(-0.002f, 1.068f, 0.377f), new Vector3(0.008f, 0.006f, 0.005f), QMouth, 0);
            b.Sphere(new Vector3(0.024f, 1.071f, 0.375f), new Vector3(0.008f, 0.006f, 0.005f), QMouth, 0);
            // hard cheekbones over sunken cheeks
            b.Material(0.22f, 0f);
            for (int s = -1; s <= 1; s += 2)
            {
                b.Sphere(new Vector3(s * 0.068f, 1.096f, 0.314f), new Vector3(0.03f, 0.021f, 0.024f), QSkin, 1);
                b.Sphere(new Vector3(s * 0.066f, 1.056f, 0.312f), new Vector3(0.025f, 0.027f, 0.015f), QSkinShade, 1);
            }
            // lopsided grimace: a dark mouth sloping to one side, a few crooked teeth with a gap
            b.Material(0.15f, 0f);
            b.Push(new Vector3(0.006f, 1.031f, 0.337f), Quaternion.Euler(0f, 0f, -8f));
            b.Sphere(Vector3.zero, new Vector3(0.043f, 0.012f, 0.014f), QMouth, 1);
            b.Pop();
            b.Material(0.5f, 0f);
            float[,] teeth = { { -0.025f, 0.012f, 4f }, { -0.009f, 0.016f, 10f }, { 0.013f, 0.011f, -3f }, { 0.029f, 0.015f, -12f } };
            for (int k = 0; k < 4; k++)
            {
                float h = teeth[k, 1];
                b.Push(new Vector3(teeth[k, 0], 1.038f - h * 0.5f - teeth[k, 0] * 0.12f, 0.348f), Quaternion.Euler(0f, 0f, teeth[k, 2]));
                b.SharpBox(Vector3.zero, new Vector3(0.0105f, h, 0.006f), QTeeth);
                b.Pop();
            }
            // grey stubble: chin, jaw, upper lip
            b.Material(0.05f, 0f);
            b.Sphere(new Vector3(0.004f, 1.0f, 0.308f), new Vector3(0.068f, 0.04f, 0.05f), QStubble, 2, 0.12f, 3);
            for (int s = -1; s <= 1; s += 2)
                b.Sphere(new Vector3(s * 0.068f, 1.035f, 0.278f), new Vector3(0.034f, 0.05f, 0.04f), QStubble, 1, 0.1f, 4 + s);
            b.Sphere(new Vector3(0.006f, 1.049f, 0.345f), new Vector3(0.04f, 0.009f, 0.01f), QStubble, 1);
            b.Matte();
            b.Pop();
        }

        /// <summary>A big bare hand closed round a horizontal handle (hand space: +Z along the forearm, +Y = the gun's up).</summary>
        static void QuasiHand(MeshBuilder b, int side)
        {
            b.Material(0.25f, 0f);
            b.Sphere(new Vector3(0f, 0.014f, -0.012f), new Vector3(0.05f, 0.042f, 0.058f), QSkin, 2);              // back of the hand
            b.Sphere(new Vector3(0f, -0.012f, 0.03f), new Vector3(0.05f, 0.04f, 0.036f), QSkin, 2);                // fingers round the grip
            b.Sphere(new Vector3(side * 0.043f, 0.02f, 0.004f), new Vector3(0.019f, 0.018f, 0.034f), QSkin, 1);    // thumb
            b.Material(0.2f, 0f);
            for (int k = 0; k < 4; k++)
                b.Sphere(new Vector3(-0.033f + k * 0.022f, 0.03f, 0.036f), Vector3.one * 0.013f, QSkinShade, 1);   // knuckles
            b.Matte();
        }

        /// <summary>Two-bone IK for both arms (shoulder on the body, hand on the launcher's handle), in the operator's
        /// space. Elbows bend outwards and down; the forearm stretches a little if the handle is just out of reach.</summary>
        public static void SolveHarpoonerArms(HarpoonerRig r)
        {
            const float L1 = HarpoonerRig.UpperLen, L2 = HarpoonerRig.ForeLen;
            var space = r.crew;
            var gunUp = space.InverseTransformDirection(r.gun.up);
            for (int i = 0; i < 2; i++)
            {
                var s = space.InverseTransformPoint(r.shoulder[i].position);
                var h = space.InverseTransformPoint(r.grip[i].position);
                var toH = h - s;
                float d = Mathf.Max(1e-4f, toH.magnitude);
                var dir = toH / d;
                float dc = Mathf.Clamp(d, Mathf.Abs(L1 - L2) + 0.02f, L1 + L2 - 0.002f);
                float cosA = Mathf.Clamp((L1 * L1 + dc * dc - L2 * L2) / (2f * L1 * dc), -1f, 1f);
                float sinA = Mathf.Sqrt(Mathf.Max(0f, 1f - cosA * cosA));
                var pole = new Vector3(i == 0 ? 1f : -1f, -0.3f, -0.3f);
                var pp = pole - Vector3.Dot(pole, dir) * dir;
                if (pp.sqrMagnitude < 1e-6f) pp = Vector3.down;
                pp.Normalize();
                var e = s + dir * (L1 * cosA) + pp * (L1 * sinA);
                r.upperArm[i].localPosition = s;
                r.upperArm[i].localRotation = Quaternion.LookRotation(e - s, pp);
                var fore = h - e;
                r.foreArm[i].localPosition = e;
                r.foreArm[i].localRotation = Quaternion.LookRotation(fore, pp);
                r.foreArm[i].localScale = new Vector3(1f, 1f, Mathf.Clamp(fore.magnitude / L2, 0.6f, 1.4f));
                r.glove[i].localPosition = h;
                r.glove[i].localRotation = Quaternion.LookRotation(fore, gunUp);
            }
        }

        /// <summary>Bright barbed harpoon head on a dark shaft (also used in flight, scaled up).</summary>
        public static Mesh HarpoonHeadMesh()
        {
            return Cached("harpoonhead3", b =>
            {
                b.Material(0.5f, 0.8f);
                b.CylinderBetween(new Vector3(0, 0, -0.36f), new Vector3(0, 0, 0.1f), 0.032f, 10, Hex("#3E444A"));
                b.Material(0.2f, 0f);
                b.CylinderBetween(new Vector3(0, 0, -0.36f), new Vector3(0, 0, -0.28f), 0.045f, 10, CarRope);
                b.Material(0.9f, 1f);
                b.Push(new Vector3(0, 0, 0.06f), Quaternion.Euler(90, 0, 0));
                b.Push(Vector3.zero, Quaternion.identity, new Vector3(1f, 1f, 0.5f));
                b.Lathe(new[] { new Vector2(0.035f, 0f), new Vector2(0.12f, 0.1f), new Vector2(0.07f, 0.26f), new Vector2(0f, 0.36f) }, 12, Hex("#E6EBEF"));
                b.Pop(); b.Pop();
                foreach (int s in new[] { -1, 1 })
                    b.CylinderBetween(new Vector3(s * 0.04f, 0, 0.1f), new Vector3(s * 0.15f, 0, -0.06f), 0.022f, 8, Hex("#E6EBEF"), 0.006f);
                b.Matte();
            });
        }

        // ------------------------------------------------------------------ hero armor
        static Color ArmorPlate(int tier) => tier >= 3 ? Hex("#E9B949") : tier >= 2 ? Hex("#9D7EDB") : tier >= 1 ? Hex("#6FA6D3") : Hex("#8D959C");

        /// <summary>Visible armor pieces on the player's car (tier 0..3 by level). Each tier changes the silhouette,
        /// not just the color: more and longer spikes, side wings, horns; thicker skirts, roof spikes, louvers.</summary>
        public static Mesh CarArmorMesh(int armorId, int tier)
        {
            var plate = ArmorPlate(tier);
            var dark = Shade(plate, 0.55f);
            return Cached("cararmor3_" + armorId + "_" + tier, b =>
            {
                b.Material(0.5f, 0.55f);
                if (armorId == 0)
                {
                    // spiked ram plow on the nose
                    float w = 1.9f + tier * 0.16f, h = 0.44f + tier * 0.05f;
                    b.Push(new Vector3(0, 0.52f, 2.68f), Quaternion.Euler(-16, 0, 0));
                    b.BevelBox(Vector3.zero, new Vector3(w, h, 0.14f), 0.06f, plate, Shade(plate, 1.12f));
                    b.BevelBox(new Vector3(0, -h * 0.46f, 0.06f), new Vector3(w + 0.1f, 0.13f, 0.24f), 0.05f, dark);
                    if (tier >= 2)
                        for (int s = -1; s <= 1; s += 2)
                            b.BevelBox(new Vector3(s * (w * 0.5f + 0.1f), 0, -0.14f), new Vector3(0.34f, h * 0.9f, 0.12f), Quaternion.Euler(0, s * 38f, 0), 0.04f, plate);
                    if (tier >= 2)
                    {
                        b.Sphere(new Vector3(0, 0.02f, 0.1f), new Vector3(0.2f, 0.17f, 0.12f), Bone, 1);
                        b.Sphere(new Vector3(-0.07f, 0.04f, 0.2f), new Vector3(0.04f, 0.035f, 0.02f), Hex("#2A1E1A"), 0);
                        b.Sphere(new Vector3(0.07f, 0.04f, 0.2f), new Vector3(0.04f, 0.035f, 0.02f), Hex("#2A1E1A"), 0);
                    }
                    int spikes = 3 + tier * 2;
                    b.Material(0.9f, 1f);
                    for (int i = 0; i < spikes; i++)
                    {
                        float x = (-0.5f + i / (float)(spikes - 1)) * (w - 0.3f);
                        if (tier >= 2 && Mathf.Abs(x) < 0.25f) continue;   // the skull sits in the middle
                        b.Push(new Vector3(x, h * 0.05f, 0.07f), Quaternion.Euler(90, 0, 0));
                        b.Cone(Vector3.zero, 0.07f + tier * 0.006f, 0.3f + tier * 0.07f, 10, tier >= 3 ? plate : Chrome);
                        b.Pop();
                    }
                    if (tier >= 3)
                    {
                        // two big curved horns from the wing tips
                        for (int s = -1; s <= 1; s += 2)
                        {
                            var p0 = new Vector3(s * (w * 0.5f + 0.2f), 0.05f, -0.2f);
                            var p1 = p0 + new Vector3(s * 0.22f, 0.25f, 0.3f);
                            var p2 = p1 + new Vector3(s * 0.05f, 0.32f, 0.3f);
                            b.Material(0.4f, 0f);
                            b.CylinderBetween(p0, p1, 0.11f, 12, Bone, 0.085f);
                            b.CylinderBetween(p1, p2, 0.085f, 12, Bone, 0.012f);
                        }
                    }
                    b.Pop();
                    b.Material(0.45f, 0.6f);
                    for (int s = -1; s <= 1; s += 2) b.CylinderBetween(new Vector3(s * 0.55f, 0.43f, 2.36f), new Vector3(s * 0.62f, 0.5f, 2.6f), 0.06f, 10, dark);
                }
                else
                {
                    // riveted plates along the short cab roof + side skirts between the wheel arches
                    float skirtT = tier >= 1 ? 0.085f : 0.06f;
                    for (int s = -1; s <= 1; s += 2)
                    {
                        b.BevelBox(new Vector3(s * 0.56f, 1.355f, -0.24f), new Vector3(0.22f, 0.06f, 0.6f), Quaternion.Euler(0, 0, s * -12f), 0.025f, plate, Shade(plate, 1.12f));
                        b.BevelBox(new Vector3(s * 0.95f, 0.62f, -0.02f), new Vector3(skirtT, 0.28f + tier * 0.03f, 1.5f), 0.03f, plate);
                        if (tier >= 1) b.BevelBox(new Vector3(s * 0.97f, 0.47f, -0.02f), new Vector3(skirtT + 0.03f, 0.07f, 1.56f), 0.025f, dark);
                    }
                    if (tier >= 2)
                    {
                        // a grille of bars over the cab's rear window (it looks into the bed) + roof spikes
                        b.BevelBox(new Vector3(0f, 1.262f, BedFrontZ - 0.02f), new Vector3(1.0f, 0.03f, 0.03f), 0.01f, dark);
                        b.BevelBox(new Vector3(0f, 1.05f, BedFrontZ - 0.02f), new Vector3(1.0f, 0.03f, 0.03f), 0.01f, dark);
                        for (int i = 0; i < 5; i++)
                            b.BevelBox(new Vector3(-0.4f + i * 0.2f, 1.155f, BedFrontZ - 0.026f), new Vector3(0.026f, 0.22f, 0.026f), 0.008f, plate);
                        b.Material(0.9f, 1f);
                        for (int s = -1; s <= 1; s += 2)
                            for (int i = 0; i < 3; i++)
                                b.Cone(new Vector3(s * 0.57f, 1.39f, -0.48f + i * 0.24f), 0.055f, 0.22f + tier * 0.03f, 8, tier >= 3 ? plate : Chrome);
                    }
                    if (tier >= 3)
                    {
                        b.Material(0.9f, 1f);
                        for (int s = -1; s <= 1; s += 2)
                            for (int i = 0; i < 4; i++)
                            {
                                b.Push(new Vector3(s * 1.0f, 0.66f, -0.6f + i * 0.4f), Quaternion.Euler(0, 0, -s * 90f));
                                b.Cone(Vector3.zero, 0.05f, 0.2f, 8, plate);
                                b.Pop();
                            }
                    }
                }
                b.Matte();
            });
        }

        // ------------------------------------------------------------------ car weapon arms
        /// <summary>Hydraulic arm boom along +Z (scaled for reach): dark sleeve + chrome piston.</summary>
        public static Mesh ArmBoomMesh()
        {
            return Cached("armboom3", b =>
            {
                b.Material(0.45f, 0.6f);
                b.CylinderBetween(new Vector3(0, 0, 0), new Vector3(0, 0, 0.58f), 0.085f, 12, Hex("#4B5158"));
                b.Material(0.9f, 1f);
                b.CylinderBetween(new Vector3(0, 0, 0.5f), new Vector3(0, 0, 1f), 0.06f, 12, CarChrome);
            });
        }

        public static Mesh ArmJointMesh()
        {
            return Cached("armjoint3", b =>
            {
                b.Material(0.4f, 0.5f);
                b.BevelBox(new Vector3(0, -0.12f, 0), new Vector3(0.28f, 0.12f, 0.28f), 0.04f, Hex("#3A3F46"));
                b.Material(0.6f, 0.7f);
                b.Sphere(Vector3.zero, Vector3.one * 0.17f, Hex("#7F8890"), 1);
                b.Material(0.6f, 0.3f);
                b.Lathe(new[] { new Vector2(0.175f, -0.03f), new Vector2(0.175f, 0.03f) }, 18, CarAccent);
            });
        }

        static Color TierColor(int level)
        {
            if (level >= 20) return Hex("#FFC94A");   // gold
            if (level >= 10) return Hex("#B57BFF");   // purple
            if (level >= 5) return Hex("#7FC8FF");    // blue steel
            return Hex("#C9D2DA");                    // plain steel
        }

        /// <summary>Weapon head mounted at the tip of an arm. Oriented along +Z (striking forward).
        /// Tiers (level 5 / 10 / 20) grow the head and add bands, spikes, barbs, extra charges and gold.</summary>
        public static Mesh WeaponMesh(int weaponId, int level)
        {
            int tier = level >= 20 ? 3 : level >= 10 ? 2 : level >= 5 ? 1 : 0;
            var steel = tier == 0 ? Hex("#9A6A4C") : Shade(TierColor(level), 0.85f);   // tier 0 = rusty scrap metal
            return Cached("weapon3_" + weaponId + "_" + tier, b =>
            {
                var handle = tier == 3 ? Hex("#8A5A1A") : WoodDark;
                switch (weaponId)
                {
                    case 1: // pipe hammer: steel pipe handle, forged head
                        {
                            float s = 1f + tier * 0.12f;
                            b.Material(0.5f, 0.8f);
                            b.CylinderBetween(new Vector3(0, 0, -0.1f), new Vector3(0, 0, 0.8f), 0.05f, 12, Metal);
                            b.Material(0.55f, 0.85f);
                            b.BevelBox(new Vector3(0, 0, 0.8f), new Vector3(0.6f, 0.32f, 0.32f) * s, 0.07f, steel, Shade(steel, 1.1f));
                            b.Material(0.4f, 0.6f);
                            foreach (float x in new[] { -0.2f, 0.2f })
                                b.BevelBox(new Vector3(x * s, 0, 0.8f), new Vector3(0.06f, 0.36f, 0.36f) * s, 0.02f, Shade(steel, 0.6f));
                            if (tier >= 2)
                            {
                                b.Material(0.9f, 1f);
                                foreach (float x in new[] { -0.36f, 0.36f })
                                {
                                    b.Push(new Vector3(x * s, 0, 0.8f), Quaternion.Euler(0, 0, x > 0 ? -90 : 90));
                                    b.Cone(Vector3.zero, 0.08f * s, 0.22f * s, 10, tier >= 3 ? Hex("#FFD35A") : Chrome);
                                    b.Pop();
                                }
                            }
                            break;
                        }
                    case 2: // scrap spear -> barbed -> golden trident
                        b.Material(0.25f, 0f);
                        b.CylinderBetween(new Vector3(0, 0, -0.2f), new Vector3(0, 0, 1.12f), 0.04f, 10, handle);
                        b.Material(0.85f, 1f);
                        int prongs = tier >= 3 ? 3 : 1;
                        for (int p = 0; p < prongs; p++)
                        {
                            float x = (p - (prongs - 1) * 0.5f) * 0.16f;
                            b.Push(new Vector3(x, 0, 1.1f), Quaternion.Euler(90, 0, 0));
                            b.Push(Vector3.zero, Quaternion.identity, new Vector3(1f, 1f, 0.5f));
                            b.Lathe(new[] { new Vector2(0.035f, 0f), new Vector2(0.11f + tier * 0.015f, 0.12f), new Vector2(0.06f, 0.34f), new Vector2(0f, 0.52f + tier * 0.06f) }, 10, steel);
                            b.Pop(); b.Pop();
                        }
                        if (tier >= 1 && tier < 3)
                            foreach (int s in new[] { -1, 1 })
                                b.CylinderBetween(new Vector3(s * 0.05f, 0, 1.22f), new Vector3(s * 0.17f, 0, 1.08f), 0.025f, 8, steel, 0.008f);
                        b.Material(0.45f, 0.6f);
                        b.BevelBox(new Vector3(0, 0, 1.08f), new Vector3(0.28f + (tier >= 3 ? 0.2f : 0f), 0.06f, 0.06f), 0.02f, Shade(steel, 0.7f));
                        break;
                    case 3: // thunder lance: shaft + explosive canisters + tip
                        b.Material(0.25f, 0f);
                        b.CylinderBetween(new Vector3(0, 0, -0.2f), new Vector3(0, 0, 1.08f), 0.045f, 10, handle);
                        int cans = 1 + Mathf.Min(tier, 2);
                        for (int c = 0; c < cans; c++)
                        {
                            float a = c * Mathf.PI * 2f / cans;
                            var o = cans == 1 ? Vector3.zero : new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0) * 0.1f;
                            b.Material(0.6f, 0.3f);
                            b.Push(o + new Vector3(0, 0, 0.66f), Quaternion.Euler(90, 0, 0));
                            b.Lathe(new[] { new Vector2(0f, 0f), new Vector2(0.11f, 0.01f), new Vector2(0.125f, 0.04f), new Vector2(0.125f, 0.32f), new Vector2(0.11f, 0.35f), new Vector2(0f, 0.36f) }, 16, tier >= 3 ? Hex("#E9B949") : Hex("#C23C2C"));
                            b.Material(0.85f, 1f);
                            b.Lathe(new[] { new Vector2(0.128f, 0.08f), new Vector2(0.128f, 0.12f) }, 16, Hex("#E0B23B"));
                            b.Pop();
                        }
                        if (tier >= 2)
                        {
                            b.Material(0.9f, 0f);
                            b.Push(new Vector3(0, 0, 1.0f), Quaternion.Euler(90, 0, 0));
                            b.Lathe(new[] { new Vector2(0.07f, 0f), new Vector2(0.09f, 0.04f), new Vector2(0.07f, 0.08f) }, 14, Glow("#7FE8FF", 0.4f));
                            b.Pop();
                        }
                        b.Material(0.85f, 1f);
                        b.Push(new Vector3(0, 0, 1.06f), Quaternion.Euler(90, 0, 0));
                        b.Lathe(new[] { new Vector2(0.07f, 0f), new Vector2(0f, 0.32f + tier * 0.04f) }, 12, steel);
                        b.Pop();
                        break;
                    default: // slot 0 is the roof turret; fallback blade
                        b.Material(0.8f, 1f);
                        b.CylinderBetween(new Vector3(0, 0, -0.1f), new Vector3(0, 0, 0.6f), 0.045f, 10, steel);
                        break;
                }
                b.Matte();
            });
        }

        // ------------------------------------------------------------------ bosses
        /// <summary>THE MAMMOTH: a huge rust-red armored semi with a massive spiked plow, stacks and a junk bed.</summary>
        public static GameObject Mammoth(ZoneDef z)
        {
            var root = new GameObject("Mammoth");
            var rig = root.AddComponent<Rig>();
            var red = Hex("#B0452F"); var redTop = Hex("#C65A3E"); var dark = Hex("#3A3533"); var steelP = Hex("#7A8288");
            var mesh = Cached("boss_mammoth3", b =>
            {
                b.Material(0.35f, 0.3f);
                b.BevelBox(new Vector3(0, 1.25f, 0), new Vector3(3.0f, 0.85f, 8.4f), 0.18f, dark);
                // cab + long hood
                b.Material(0.6f, 0f);
                b.BevelBox(new Vector3(0, 2.75f, 1.4f), new Vector3(3.0f, 2.1f, 2.5f), 0.32f, red, redTop);
                b.BevelBox(new Vector3(0, 2.15f, 3.85f), new Vector3(2.6f, 1.15f, 2.5f), 0.3f, red, redTop);
                b.Material(0.9f, 0f);
                b.BevelBox(new Vector3(0, 3.2f, 2.66f), new Vector3(2.5f, 0.62f, 0.08f), Quaternion.Euler(-12, 0, 0), 0.04f, Hex("#3C5562"));
                // grille + skull ornament with glowing eyes
                b.Material(0.4f, 0.4f);
                b.BevelBox(new Vector3(0, 2.0f, 5.1f), new Vector3(2.3f, 0.95f, 0.12f), 0.05f, Hex("#1E1E20"));
                b.Material(0.85f, 1f);
                for (int i = 0; i < 4; i++) b.BevelBox(new Vector3(0, 1.66f + i * 0.22f, 5.17f), new Vector3(2.1f, 0.06f, 0.05f), 0.02f, Chrome);
                b.Material(0.35f, 0f);
                b.Sphere(new Vector3(0, 2.15f, 5.32f), new Vector3(0.6f, 0.55f, 0.4f), Bone, 2);
                b.Sphere(new Vector3(-0.22f, 2.2f, 5.62f), new Vector3(0.13f, 0.13f, 0.08f), Glow("#FF3A2A", 0.3f), 1);
                b.Sphere(new Vector3(0.22f, 2.2f, 5.62f), new Vector3(0.13f, 0.13f, 0.08f), Glow("#FF3A2A", 0.3f), 1);
                // massive ram plow with spikes
                b.Material(0.5f, 0.6f);
                b.BevelBox(new Vector3(0, 1.15f, 5.75f), new Vector3(3.9f, 1.15f, 0.36f), Quaternion.Euler(-20, 0, 0), 0.12f, steelP, Shade(steelP, 1.15f));
                for (int s = -1; s <= 1; s += 2)
                    b.BevelBox(new Vector3(s * 2.05f, 1.1f, 5.45f), new Vector3(0.5f, 1.0f, 0.3f), Quaternion.Euler(-14, s * 35f, 0), 0.1f, steelP);
                b.Material(0.9f, 1f);
                for (int i = -3; i <= 3; i++)
                {
                    b.Push(new Vector3(i * 0.52f, 1.2f, 5.95f), Quaternion.Euler(90, 0, 0));
                    b.Cone(Vector3.zero, 0.16f, 0.8f, 12, Chrome);
                    b.Pop();
                }
                // exhaust stacks
                b.Material(0.85f, 1f);
                b.Cylinder(new Vector3(-1.35f, 2.0f, 0.15f), 0.2f, 3.3f, 14, Chrome);
                b.Cylinder(new Vector3(1.35f, 2.0f, 0.15f), 0.2f, 3.3f, 14, Chrome);
                // cargo bed + junk + flags
                b.Material(0.3f, 0.2f);
                b.BevelBox(new Vector3(0, 1.95f, -2.2f), new Vector3(2.9f, 0.6f, 3.7f), 0.12f, RustDark);
                b.BevelBox(new Vector3(-0.6f, 2.6f, -1.9f), new Vector3(1.0f, 0.75f, 1.0f), Quaternion.Euler(0, 20, 0), 0.08f, Wood, WoodLight);
                b.Cylinder(new Vector3(0.7f, 2.25f, -2.6f), 0.42f, 0.95f, 16, EnemyRed, -1, Shade(EnemyRed, 0.85f));
                b.BevelBox(new Vector3(0.2f, 2.45f, -3.55f), new Vector3(1.6f, 0.4f, 0.6f), Quaternion.Euler(0, -12, 4), 0.08f, steelP);
                b.Material(0.2f, 0f);
                b.Cylinder(new Vector3(1.3f, 2.2f, -3.8f), 0.06f, 2.8f, 8, WoodDark);
                b.BevelBox(new Vector3(1.75f, 4.6f, -3.8f), new Vector3(0.9f, 0.6f, 0.04f), 0.015f, EnemyRed);
                b.Cylinder(new Vector3(-1.3f, 2.2f, -3.8f), 0.06f, 2.8f, 8, WoodDark);
                b.BevelBox(new Vector3(-0.85f, 4.6f, -3.8f), new Vector3(0.9f, 0.6f, 0.04f), 0.015f, Hex("#2E2E30"));
                // spikes on the cab roof
                b.Material(0.9f, 1f);
                for (int i = -2; i <= 2; i++) b.Cone(new Vector3(i * 0.6f, 3.78f, 1.4f), 0.13f, 0.62f, 10, Chrome);
            });
            var body = MeshGO("Body", mesh, Mats.Toon, root.transform);
            rig.body = body.transform;
            foreach (var p in new[] { new Vector3(-1.75f, 1.0f, 3.4f), new Vector3(1.75f, 1.0f, 3.4f), new Vector3(-1.75f, 1.0f, -1.6f), new Vector3(1.75f, 1.0f, -1.6f), new Vector3(-1.75f, 1.0f, -3.4f), new Vector3(1.75f, 1.0f, -3.4f) })
                Wheel(body.transform, p, 1.0f, 0.8f, rig, p.z > 0, TireC, MetalDark);
            rig.height = 5.5f;
            rig.CollectRenderers();
            rig.enabled = false;
            return root;
        }

        /// <summary>THE WARLORD: a red monster truck on huge wheels with a chrome skull grille and yellow struts.</summary>
        public static GameObject Warlord(ZoneDef z)
        {
            var root = new GameObject("Warlord");
            var rig = root.AddComponent<Rig>();
            var red = Hex("#B3302A"); var chromeC = Chrome;
            var mesh = Cached("boss_warlord3", b =>
            {
                b.Material(0.65f, 0f);
                b.BevelBox(new Vector3(0, 2.35f, 0), new Vector3(3.0f, 0.85f, 5.4f), 0.24f, red, Shade(red, 1.15f));
                b.Material(0.9f, 0f);
                b.Tapered(new Vector3(0, 2.75f, -0.6f), new Vector2(2.6f, 2.6f), new Vector2(2.0f, 1.6f), 1.0f, Hex("#3C5562"), red);
                b.Material(0.9f, 1f);
                b.BevelBox(new Vector3(0, 2.15f, 2.8f), new Vector3(2.7f, 0.9f, 0.32f), 0.12f, chromeC);
                b.Sphere(new Vector3(0, 2.65f, 3.0f), new Vector3(0.72f, 0.62f, 0.42f), chromeC, 2);
                b.Sphere(new Vector3(-0.27f, 2.7f, 3.32f), new Vector3(0.15f, 0.15f, 0.08f), Glow("#FF3A2A", 0.25f), 1);
                b.Sphere(new Vector3(0.27f, 2.7f, 3.32f), new Vector3(0.15f, 0.15f, 0.08f), Glow("#FF3A2A", 0.25f), 1);
                // driver with a bone skull mask
                b.Material(0.2f, 0f);
                b.BevelBox(new Vector3(0, 4.0f, -0.5f), new Vector3(0.66f, 0.72f, 0.44f), 0.16f, Hex("#2E2A2A"));
                b.Sphere(new Vector3(0, 4.55f, -0.48f), new Vector3(0.28f, 0.3f, 0.28f), Bone, 2);
                b.Sphere(new Vector3(-0.1f, 4.58f, -0.24f), new Vector3(0.06f, 0.06f, 0.03f), Hex("#1A1A1A"), 0);
                b.Sphere(new Vector3(0.1f, 4.58f, -0.24f), new Vector3(0.06f, 0.06f, 0.03f), Hex("#1A1A1A"), 0);
                // exhausts and side spikes
                b.Material(0.9f, 1f);
                for (int s = -1; s <= 1; s += 2)
                {
                    b.Cylinder(new Vector3(s * 1.2f, 2.65f, 1.6f), 0.17f, 1.7f, 14, chromeC);
                    for (int i = 0; i < 4; i++)
                    {
                        b.Push(new Vector3(s * 1.55f, 2.35f, -2f + i * 1.3f), Quaternion.Euler(0, 0, -s * 90));
                        b.Cone(Vector3.zero, 0.13f, 0.65f, 10, chromeC);
                        b.Pop();
                    }
                }
                // suspension struts
                b.Material(0.6f, 0.3f);
                foreach (var p in new[] { new Vector3(-1.4f, 0, 1.9f), new Vector3(1.4f, 0, 1.9f), new Vector3(-1.4f, 0, -1.9f), new Vector3(1.4f, 0, -1.9f) })
                    b.CylinderBetween(p + new Vector3(0, 1.4f, 0), p + new Vector3(p.x > 0 ? -0.5f : 0.5f, 2.05f, 0), 0.12f, 10, Hex("#E0B23B"));
            });
            var body = MeshGO("Body", mesh, Mats.Toon, root.transform);
            rig.body = body.transform;
            foreach (var p in new[] { new Vector3(-1.9f, 1.35f, 1.9f), new Vector3(1.9f, 1.35f, 1.9f), new Vector3(-1.9f, 1.35f, -1.9f), new Vector3(1.9f, 1.35f, -1.9f) })
                Wheel(body.transform, p, 1.35f, 1.05f, rig, p.z > 0, TireC, chromeC);
            rig.height = 5.5f;
            rig.CollectRenderers();
            rig.enabled = false;
            return root;
        }

        public static GameObject Baron(ZoneDef z)
        {
            var go = Humanoid(ModelId.BossBaron, z, 3.0f);
            go.name = "OilBaron";
            return go;
        }

        public static GameObject Colossus(ZoneDef z)
        {
            var go = Humanoid(ModelId.BossColossus, z, 3.6f);
            go.name = "SaltColossus";
            return go;
        }
    }
}
