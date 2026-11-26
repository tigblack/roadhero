using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>How an icon model is turned towards the studio camera and how much of the frame it fills.</summary>
    public struct IconPose
    {
        public float tilt, yaw, roll;   // rotation = Euler(tilt,0,0) * Euler(0,yaw,0) * Euler(0,0,roll) (roll first, in the image plane)
        public float fill;              // size of the larger projected side as a fraction of the frame
        public IconPose(float tilt, float yaw, float roll, float fill) { this.tilt = tilt; this.yaw = yaw; this.roll = roll; this.fill = fill; }
        public Quaternion Rotation => Quaternion.Euler(tilt, 0, 0) * Quaternion.Euler(0, yaw, 0) * Quaternion.Euler(0, 0, roll);
    }

    /// <summary>
    /// Toy-like 3D models made only for the UI icons: big readable silhouettes, round chunky forms, few large details.
    /// Each model is built facing -Z (the studio camera) and posed by <see cref="IconPose"/>. Colors are sRGB.
    /// Weapons and resources differ by shape and by color family: gun = brass shell, smash = red sledgehammer,
    /// pierce = ice-blue spear, blast = navy bomb, HP = red heart, regen = green heart, gems = purple,
    /// armor = blue steel, chests = wood / crimson / steel.
    /// </summary>
    public static class IconModels
    {
        static Color H(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return c; }
        static Color Glow(string hex, float a) { var c = H(hex); c.a = a; return c; }

        // palette
        static readonly Color Red = H("#F2374A"), Green = H("#35C759"), GreenDeep = H("#2DB552"), Cream = H("#FFF7EA");
        static readonly Color Gold = H("#FFC23D"), GoldDeep = H("#F0A92E"), Brass = H("#EBAE3F"), Copper = H("#E26F3E");
        static readonly Color SteelL = H("#D7DEE6"), SteelM = H("#A9B5C2"), SteelD = H("#5E6976");
        static readonly Color Wood = H("#B8703A"), WoodL = H("#CD8445"), WoodD = H("#7C4524");
        static readonly Color Navy = H("#2F3C5C"), Purple = H("#A54DFF"), Bone = H("#F3EBDD"), Dark = H("#3B2421");
        static readonly Color ArmorBlue = H("#4D84CF"), ArmorBlueL = H("#7EA6DA"), Teal = H("#34B4A2"), Orange = H("#FF8A2E");
        static readonly Color Rope = H("#EAD9AE");

        public static Mesh Build(Icon icon, out IconPose pose)
        {
            var b = new MeshBuilder();
            pose = new IconPose(8f, 16f, 0f, 0.8f);
            switch (icon)
            {
                case Icon.Heart: HeartModel(b, Red); pose = new IconPose(8f, 16f, 0f, 0.8f); break;
                case Icon.Regen: HeartModel(b, Green); PlusEmblem(b, new Vector2(0f, 0.04f), 0.4f, -0.44f); pose = new IconPose(8f, 16f, 0f, 0.8f); break;
                case Icon.Plus: PlusButton(b); pose = new IconPose(10f, 12f, 0f, 0.78f); break;
                case Icon.Star: StarModel(b); pose = new IconPose(8f, 14f, 0f, 0.82f); break;
                case Icon.Shield: ShieldModel(b, ArmorBlue); pose = new IconPose(8f, 16f, 0f, 0.8f); break;
                case Icon.Gem: GemModel(b, Vector3.zero, 1f, 0f); pose = new IconPose(-6f, 0f, 0f, 0.8f); break;
                case Icon.GemPile: GemPile(b); pose = new IconPose(-4f, 0f, 0f, 0.86f); break;
                case Icon.Gun: ShellModel(b); pose = new IconPose(4f, 22f, -38f, 0.84f); break;
                case Icon.Smash: HammerModel(b); pose = new IconPose(6f, 24f, -40f, 0.84f); break;
                case Icon.Pierce: SpearModel(b); pose = new IconPose(4f, 22f, -40f, 0.86f); break;
                case Icon.Blast: BombModel(b); pose = new IconPose(6f, 18f, 0f, 0.8f); break;
                case Icon.Skull: SkullModel(b); pose = new IconPose(6f, 14f, 0f, 0.78f); break;
                case Icon.Gear: GearModel(b); pose = new IconPose(10f, 16f, 0f, 0.82f); break;
                case Icon.Wrench: WrenchModel(b); pose = new IconPose(4f, 22f, -42f, 0.84f); break;
                case Icon.Lock: LockModel(b); pose = new IconPose(4f, 22f, 0f, 0.8f); break;
                case Icon.Ad: AdModel(b); pose = new IconPose(8f, 14f, 0f, 0.82f); break;
                case Icon.Chest: ChestModel(b, Wood, WoodL, GoldDeep, false); pose = new IconPose(6f, 24f, 0f, 0.84f); break;
                case Icon.ChestBig: ChestModel(b, H("#C9333E"), H("#DE4650"), Gold, true); pose = new IconPose(6f, 24f, 0f, 0.88f); break;
                case Icon.ChestArmor: ArmorCrate(b); pose = new IconPose(6f, 24f, 0f, 0.84f); break;
                case Icon.Zoom: ZoomModel(b); pose = new IconPose(8f, 16f, 0f, 0.82f); break;
                case Icon.Arrow: ArrowModel(b); pose = new IconPose(16f, 0f, 0f, 0.8f); break;
                case Icon.Close: CloseModel(b); pose = new IconPose(10f, 12f, 0f, 0.78f); break;
                case Icon.Harpoon: HarpoonModel(b); pose = new IconPose(4f, 22f, -40f, 0.86f); break;
                case Icon.Flag: FlagModel(b); pose = new IconPose(4f, 32f, 0f, 0.82f); break;
                case Icon.Crit: TargetModel(b); pose = new IconPose(10f, 16f, 0f, 0.82f); break;
                case Icon.EnemyDot: b.Material(0.8f, 0f); b.Sphere(Vector3.zero, Vector3.one, H("#F0453B"), 5); pose = new IconPose(0f, 0f, 0f, 0.72f); break;
                case Icon.BullBar: BullBarModel(b); pose = new IconPose(2f, 16f, 0f, 0.86f); break;
                case Icon.RoofPlates: RoofPlatesModel(b); pose = new IconPose(10f, 20f, 0f, 0.82f); break;
                case Icon.Car: return null;   // rendered from the real player car (IconStudio)
                default: throw new ArgumentOutOfRangeException(nameof(icon), icon, "no icon model");
            }
            return b.Build("icon_" + icon);
        }

        // ------------------------------------------------------------------ hearts, plus, star, shield, X, arrow
        static void HeartModel(MeshBuilder b, Color c)
        {
            b.Material(0.72f, 0f);
            IconShapes.Pillow(b, IconShapes.Heart(), new Vector2(0f, 0.02f), 0.5f, 0.3f, 2.3f, c);
        }

        static void PlusEmblem(MeshBuilder b, Vector2 at, float size, float z0)
        {
            b.Material(0.55f, 0f);
            var plus = IconShapes.Transform(IconShapes.Plus(1f, 0.33f, 0.2f), new Vector2(size, size), at);
            IconShapes.Pillow(b, plus, at, 0.15f, 0f, 2.6f, Cream, null, z0);
        }

        static void PlusButton(MeshBuilder b)
        {
            b.Material(0.72f, 0f);
            IconShapes.Pillow(b, IconShapes.Circle(1f), Vector2.zero, 0.42f, 0.24f, 3.0f, Green);
            PlusEmblem(b, Vector2.zero, 0.62f, -0.36f);
        }

        static void StarModel(MeshBuilder b)
        {
            b.Material(0.78f, 0.22f);
            IconShapes.Pillow(b, IconShapes.Star(5, 1f, 0.5f, 0.11f), new Vector2(0f, 0.02f), 0.44f, 0.22f, 2.1f, Gold);
        }

        static Vector2[] ShieldOutline()
        {
            var pts = new List<Vector2>();
            // top edge (gently arched), right side, curved bottom to the point, left side
            foreach (var p in IconShapes.Bezier(new Vector3(-0.84f, 0.8f), new Vector3(0f, 0.92f), new Vector3(0.84f, 0.8f), 14)) pts.Add(p);
            foreach (var p in IconShapes.Bezier(new Vector3(0.84f, 0.8f), new Vector3(0.86f, 0.2f), new Vector3(0.8f, 0.05f), 8)) pts.Add(p);
            foreach (var p in IconShapes.Bezier(new Vector3(0.8f, 0.05f), new Vector3(0.7f, -0.62f), new Vector3(0f, -1f), 16)) pts.Add(p);
            foreach (var p in IconShapes.Bezier(new Vector3(0f, -1f), new Vector3(-0.7f, -0.62f), new Vector3(-0.8f, 0.05f), 16)) pts.Add(p);
            foreach (var p in IconShapes.Bezier(new Vector3(-0.8f, 0.05f), new Vector3(-0.86f, 0.2f), new Vector3(-0.84f, 0.8f), 8)) pts.Add(p);
            return IconShapes.RoundCorners(pts, 0.1f, 8);
        }

        static void ShieldModel(MeshBuilder b, Color face)
        {
            var outline = ShieldOutline();
            var c = new Vector2(0f, 0.02f);
            b.Material(0.72f, 0.6f);
            IconShapes.Pillow(b, outline, c, 0.3f, 0.2f, 3.6f, SteelL);
            b.Material(0.68f, 0f);
            IconShapes.Pillow(b, IconShapes.Transform(outline, new Vector2(0.8f, 0.8f), c * 0.2f), c, 0.2f, 0f, 3.0f, face, null, -0.24f);
            b.Material(0.8f, 0.6f);
            b.Sphere(new Vector3(0f, 0.08f, -0.42f), new Vector3(0.15f, 0.15f, 0.08f), Gold, 4);
        }

        static void CloseModel(MeshBuilder b)
        {
            b.Material(0.6f, 0f);
            IconShapes.Pillow(b, IconShapes.Rotate(IconShapes.Plus(0.98f, 0.25f, 0.17f), 45f), Vector2.zero, 0.3f, 0.18f, 2.6f, Cream);
        }

        static void ArrowModel(MeshBuilder b)
        {
            var pts = new[] { new Vector2(0f, 1f), new Vector2(0.8f, -0.8f), new Vector2(0f, -0.38f), new Vector2(-0.8f, -0.8f) };
            var outline = IconShapes.RoundCorners(pts, 0.16f, 10, new[] { 0.1f, 0.14f, 0.18f, 0.14f });
            b.Material(0.72f, 0f);
            IconShapes.Pillow(b, outline, new Vector2(0f, 0.02f), 0.3f, 0.16f, 2.1f, H("#FFC83A"));
        }

        // ------------------------------------------------------------------ gems
        static void GemModel(MeshBuilder b, Vector3 at, float s, float rollDeg)
        {
            float old = b.smoothAngle;
            b.smoothAngle = 1f;   // crisp facets
            b.Material(0.92f, 0.08f);
            b.Push(at, Quaternion.Euler(0, 0, rollDeg) * Quaternion.Euler(0, 22.5f, 0), Vector3.one * s);
            b.Lathe(new[]
            {
                new Vector2(0f, -1f), new Vector2(0.52f, -0.42f), new Vector2(1f, 0f), new Vector2(1f, 0.09f), new Vector2(0.66f, 0.42f), new Vector2(0f, 0.42f)
            }, 8, Purple, new[] { H("#7330D2"), H("#9343F0"), H("#B36CFF"), Glow("#C990FF", 0.9f), Glow("#E6C4FF", 0.86f) });
            b.Pop();
            b.smoothAngle = old;
        }

        static void GemPile(MeshBuilder b)
        {
            GemModel(b, new Vector3(-0.92f, -0.42f, 0.25f), 0.62f, 18f);
            GemModel(b, new Vector3(0.95f, -0.45f, 0.2f), 0.66f, -16f);
            GemModel(b, new Vector3(0f, 0.08f, -0.1f), 0.95f, 0f);
        }

        // ------------------------------------------------------------------ weapons (all diagonal, bottom-left to top-right)
        static void ShellModel(MeshBuilder b)
        {
            b.Material(0.85f, 0.75f);
            b.Lathe(new[]
            {
                new Vector2(0f, -0.9f), new Vector2(0.35f, -0.9f), new Vector2(0.37f, -0.86f), new Vector2(0.37f, -0.78f), new Vector2(0.32f, -0.76f),
                new Vector2(0.32f, -0.72f), new Vector2(0.35f, -0.69f), new Vector2(0.35f, 0.12f), new Vector2(0.33f, 0.2f), new Vector2(0.32f, 0.22f)
            }, 48, Brass);
            b.Material(0.8f, 0.55f);
            b.Lathe(new[]
            {
                new Vector2(0.32f, 0.18f), new Vector2(0.325f, 0.36f), new Vector2(0.3f, 0.58f), new Vector2(0.24f, 0.78f), new Vector2(0.15f, 0.92f),
                new Vector2(0.06f, 0.99f), new Vector2(0f, 1f)
            }, 48, Copper);
            b.Material(0.4f, 0.3f);
            b.Lathe(new[] { new Vector2(0.33f, 0.3f), new Vector2(0.335f, 0.34f), new Vector2(0.33f, 0.38f) }, 48, H("#B9532A"));
        }

        static void HammerModel(MeshBuilder b)
        {
            // pipe handle with an orange tape grip
            b.Material(0.6f, 0.65f);
            b.CylinderBetween(new Vector3(0, -1.0f, 0), new Vector3(0, 0.55f, 0), 0.1f, 24, SteelD);
            b.Material(0.3f, 0f);
            b.CylinderBetween(new Vector3(0, -1.02f, 0), new Vector3(0, -0.36f, 0), 0.135f, 24, Orange);
            for (int i = 0; i < 3; i++) b.CylinderBetween(new Vector3(0, -0.9f + i * 0.2f, 0), new Vector3(0, -0.86f + i * 0.2f, 0), 0.142f, 24, H("#D96F1E"));
            b.Material(0.6f, 0.6f);
            b.Sphere(new Vector3(0, -1.03f, 0), new Vector3(0.15f, 0.08f, 0.15f), SteelD, 4);
            // red sledge head with steel striking faces
            b.Material(0.62f, 0.05f);
            IconShapes.RoundBox(b, new Vector3(0, 0.72f, 0), new Vector3(1.0f, 0.56f, 0.56f), 0.12f, H("#DA4537"));
            b.Material(0.82f, 0.8f);
            foreach (int s in new[] { -1, 1 })
                IconShapes.RoundBox(b, new Vector3(s * 0.56f, 0.72f, 0), new Vector3(0.18f, 0.64f, 0.64f), 0.07f, SteelL);
        }

        static void SpearModel(MeshBuilder b)
        {
            // ice-blue leaf blade with a ridge, brass collar, wooden shaft with cream wraps
            var blade = new[] { new Vector2(0f, 1.16f), new Vector2(0.37f, 0.5f), new Vector2(0.2f, 0.07f), new Vector2(0f, -0.02f), new Vector2(-0.2f, 0.07f), new Vector2(-0.37f, 0.5f) };
            b.Material(0.86f, 0.55f);
            IconShapes.Pillow(b, IconShapes.RoundCorners(blade, 0.06f, 8, new[] { 0.03f, 0.14f, 0.06f, 0.05f, 0.06f, 0.14f }), new Vector2(0f, 0.42f), 0.18f, 0.18f, 1.7f, H("#9CD6F4"));
            b.Material(0.8f, 0.7f);
            b.CylinderBetween(new Vector3(0, -0.14f, 0), new Vector3(0, 0.08f, 0), 0.14f, 24, Brass);
            b.Sphere(new Vector3(0, 0.08f, 0), new Vector3(0.14f, 0.06f, 0.14f), Brass, 4);
            b.Material(0.32f, 0f);
            b.CylinderBetween(new Vector3(0, -1.12f, 0), new Vector3(0, -0.1f, 0), 0.1f, 24, Wood);
            b.Sphere(new Vector3(0, -1.12f, 0), new Vector3(0.1f, 0.06f, 0.1f), Wood, 3);
            b.Material(0.2f, 0f);
            foreach (float y in new[] { -0.38f, -0.56f })
                b.CylinderBetween(new Vector3(0, y, 0), new Vector3(0, y + 0.11f, 0), 0.118f, 24, Rope);
        }

        static void BombModel(MeshBuilder b)
        {
            var c = new Vector3(0f, -0.12f, 0f);
            b.Material(0.78f, 0.08f);
            b.Sphere(c, Vector3.one * 0.82f, Navy, 5);
            var dir = new Vector3(Mathf.Sin(35f * Mathf.Deg2Rad), Mathf.Cos(35f * Mathf.Deg2Rad), 0f);
            b.Material(0.82f, 0.7f);
            b.CylinderBetween(c + dir * 0.7f, c + dir * 0.98f, 0.25f, 32, Brass);
            b.Sphere(c + dir * 0.98f, new Vector3(0.25f, 0.04f, 0.25f), Brass, 3);
            var f0 = c + dir * 0.98f;
            var fuse = IconShapes.Bezier(f0, f0 + new Vector3(0.05f, 0.32f, 0f), f0 + new Vector3(0.36f, 0.34f, -0.02f), 12);
            b.Material(0.25f, 0f);
            IconShapes.Tube(b, fuse, 0.065f, H("#D8C49A"), 14);
            // spark: glowing star facing the camera
            var tip = fuse[fuse.Length - 1];
            b.Material(0.3f, 0f);
            IconShapes.Pillow(b, IconShapes.Transform(IconShapes.Star(8, 1f, 0.45f, 0.06f, 0f), new Vector2(0.3f, 0.3f), new Vector2(tip.x, tip.y)), new Vector2(tip.x, tip.y), 0.08f, 0.08f, 2.2f, Glow("#FF9E2C", 0.25f), null, tip.z - 0.02f);
            IconShapes.Pillow(b, IconShapes.Transform(IconShapes.Star(8, 1f, 0.5f, 0.05f, 22f), new Vector2(0.17f, 0.17f), new Vector2(tip.x, tip.y)), new Vector2(tip.x, tip.y), 0.07f, 0f, 2.2f, Glow("#FFF2A8", 0.1f), null, tip.z - 0.09f);
        }

        // ------------------------------------------------------------------ skull, gear, wrench, lock
        static void SkullModel(MeshBuilder b)
        {
            b.Material(0.38f, 0f);
            b.Sphere(new Vector3(0f, 0.15f, 0f), new Vector3(0.95f, 0.88f, 0.85f), Bone, 5);
            IconShapes.RoundBox(b, new Vector3(0f, -0.56f, -0.1f), new Vector3(1.0f, 0.52f, 0.8f), 0.24f, H("#E9DFCD"));
            // eye sockets: dark soft ovals sitting in the surface
            b.Material(0.15f, 0f);
            foreach (int s in new[] { -1, 1 })
                b.Sphere(new Vector3(s * 0.35f, 0.02f, -0.69f), new Vector3(0.26f, 0.29f, 0.12f), Dark, 4);
            // nose
            var nose = IconShapes.RoundCorners(new[] { new Vector2(0f, -0.18f), new Vector2(0.11f, -0.38f), new Vector2(-0.11f, -0.38f) }, 0.04f, 6);
            IconShapes.Pillow(b, nose, new Vector2(0f, -0.31f), 0.05f, 0f, 2.5f, Dark, null, -0.72f);
            // teeth gaps
            foreach (float x in new[] { -0.2f, 0f, 0.2f })
                IconShapes.RoundBox(b, new Vector3(x, -0.68f, -0.5f), new Vector3(0.05f, 0.2f, 0.04f), 0.02f, H("#8A7766"));
        }

        static void GearModel(MeshBuilder b)
        {
            var pts = new List<Vector2>();
            const int teeth = 8;
            for (int i = 0; i < teeth; i++)
            {
                float a0 = i * 360f / teeth;
                foreach (var (da, r) in new[] { (-15f, 0.76f), (-8.5f, 1f), (8.5f, 1f), (15f, 0.76f) })
                {
                    float a = (a0 + da) * Mathf.Deg2Rad;
                    pts.Add(new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r);
                }
            }
            b.Material(0.76f, 0.7f);
            IconShapes.Pillow(b, IconShapes.RoundCorners(pts, 0.06f, 6), Vector2.zero, 0.26f, 0.2f, 4.5f, SteelL);
            b.Material(0.7f, 0.6f);
            IconShapes.Pillow(b, IconShapes.Circle(0.4f), Vector2.zero, 0.1f, 0f, 3f, SteelM, null, -0.2f);
            b.Material(0.4f, 0.3f);
            IconShapes.Pillow(b, IconShapes.Circle(0.19f), Vector2.zero, 0.03f, 0f, 3f, H("#465260"), null, -0.29f);
        }

        static void WrenchModel(MeshBuilder b)
        {
            // open C head (round tube), flat handle, orange rubber grip
            b.Material(0.8f, 0.75f);
            var arc = new List<Vector3>();
            for (int i = 0; i <= 40; i++)
            {
                float a = (122f + 296f * i / 40f) * Mathf.Deg2Rad;
                arc.Add(new Vector3(Mathf.Cos(a) * 0.37f, 0.6f + Mathf.Sin(a) * 0.37f, 0f));
            }
            b.Sweep(arc, MeshBuilder.RoundRectProfile(0.36f, 0.22f, 0.09f, 4), SteelL, true, true, new Vector3(0f, 0f, -1f));
            IconShapes.RoundBox(b, new Vector3(0f, -0.08f, 0f), new Vector3(0.3f, 1.0f, 0.2f), 0.09f, SteelL);
            b.Material(0.35f, 0f);
            IconShapes.RoundBox(b, new Vector3(0f, -0.72f, 0f), new Vector3(0.38f, 0.62f, 0.28f), 0.13f, Orange);
            b.Material(0.3f, 0f);
            for (int i = 0; i < 3; i++) IconShapes.RoundBox(b, new Vector3(0f, -0.88f + i * 0.16f, 0f), new Vector3(0.4f, 0.04f, 0.3f), 0.02f, H("#DD6E1D"));
        }

        static void LockModel(MeshBuilder b)
        {
            // steel shackle
            var path = new List<Vector3>();
            for (int i = 0; i <= 4; i++) path.Add(new Vector3(-0.38f, 0.12f + i * 0.1f, 0f));
            for (int i = 1; i < 20; i++) { float a = Mathf.PI - Mathf.PI * i / 20f; path.Add(new Vector3(Mathf.Cos(a) * 0.38f, 0.52f + Mathf.Sin(a) * 0.38f, 0f)); }
            for (int i = 4; i >= 0; i--) path.Add(new Vector3(0.38f, 0.12f + i * 0.1f, 0f));
            b.Material(0.86f, 0.85f);
            IconShapes.Tube(b, path, 0.12f, SteelL, 20);
            // golden body + keyhole plate
            b.Material(0.82f, 0.5f);
            IconShapes.RoundBox(b, new Vector3(0f, -0.3f, 0f), new Vector3(1.32f, 1.04f, 0.62f), 0.22f, Gold, H("#FFD25E"));
            b.Material(0.7f, 0.5f);
            IconShapes.Pillow(b, IconShapes.Circle(0.25f, 96, new Vector2(0f, -0.28f)), new Vector2(0f, -0.28f), 0.05f, 0f, 3f, H("#FFD873"), null, -0.3f);
            b.Material(0.2f, 0f);
            IconShapes.Pillow(b, IconShapes.Circle(0.1f, 64, new Vector2(0f, -0.22f)), new Vector2(0f, -0.22f), 0.02f, 0f, 3f, H("#5A3511"), null, -0.345f);
            IconShapes.Pillow(b, IconShapes.RoundCorners(new[] { new Vector2(-0.05f, -0.24f), new Vector2(0.05f, -0.24f), new Vector2(0.09f, -0.44f), new Vector2(-0.09f, -0.44f) }, 0.03f, 4), new Vector2(0f, -0.33f), 0.02f, 0f, 3f, H("#5A3511"), null, -0.345f);
        }

        // ------------------------------------------------------------------ badges and boxes
        static void AdModel(MeshBuilder b)
        {
            b.Material(0.78f, 0f);
            IconShapes.Pillow(b, IconShapes.RoundRect(1.9f, 1.36f, 0.42f), Vector2.zero, 0.36f, 0.2f, 3.2f, H("#EF3E4A"));
            var tri = IconShapes.RoundCorners(new[] { new Vector2(-0.26f, 0.38f), new Vector2(0.44f, 0f), new Vector2(-0.26f, -0.38f) }, 0.1f, 8);
            b.Material(0.55f, 0f);
            IconShapes.Pillow(b, tri, new Vector2(-0.03f, 0f), 0.13f, 0f, 2.4f, Cream, null, -0.3f);
        }

        static void ChestModel(MeshBuilder b, Color body, Color lid, Color trim, bool big)
        {
            float w = big ? 1.8f : 1.7f, lidH = big ? 0.6f : 0.52f;
            b.Material(0.4f, 0f);
            IconShapes.RoundBox(b, new Vector3(0f, -0.32f, 0f), new Vector3(w, 0.92f, 1.06f), 0.12f, body);
            b.Material(0.5f, 0f);
            IconShapes.RoundBox(b, new Vector3(0f, 0.12f + lidH * 0.5f, 0f), new Vector3(w + 0.06f, lidH, 1.12f), 0.25f, lid);
            // dark seam between lid and body
            b.Material(0.2f, 0f);
            IconShapes.RoundBox(b, new Vector3(0f, 0.13f, 0f), new Vector3(w + 0.02f, 0.08f, 1.08f), 0.03f, Color.Lerp(body, Dark, 0.6f));
            // metal bands wrapping body and lid
            b.Material(0.82f, 0.6f);
            foreach (int s in new[] { -1, 1 })
            {
                IconShapes.RoundBox(b, new Vector3(s * w * 0.32f, 0.12f + lidH * 0.5f, 0f), new Vector3(0.2f, lidH + 0.04f, 1.17f), 0.26f, trim);
                IconShapes.RoundBox(b, new Vector3(s * w * 0.32f, -0.32f, 0f), new Vector3(0.2f, 0.94f, 1.1f), 0.08f, trim);
            }
            // lock plate + keyhole
            IconShapes.RoundBox(b, new Vector3(0f, 0.04f, -0.56f), new Vector3(big ? 0.42f : 0.36f, big ? 0.5f : 0.44f, 0.12f), 0.06f, trim);
            if (big)
            {
                // a gem on the lock: the premium crate
                b.Push(new Vector3(0f, 0.08f, -0.66f), Quaternion.Euler(-90f, 0, 0), Vector3.one * 0.15f);
                GemModel(b, Vector3.zero, 1f, 0f);
                b.Pop();
            }
            else
            {
                b.Material(0.2f, 0f);
                IconShapes.Pillow(b, IconShapes.Circle(0.06f, 48, new Vector2(0f, 0.08f)), new Vector2(0f, 0.08f), 0.015f, 0f, 3f, H("#4A2A10"), null, -0.625f);
                IconShapes.Pillow(b, IconShapes.RoundRect(0.06f, 0.14f, 0.02f, new Vector2(0f, -0.02f)), new Vector2(0f, -0.02f), 0.015f, 0f, 3f, H("#4A2A10"), null, -0.625f);
            }
        }

        static void ArmorCrate(MeshBuilder b)
        {
            b.Material(0.62f, 0.4f);
            IconShapes.RoundBox(b, new Vector3(0f, -0.15f, 0f), new Vector3(1.66f, 1.2f, 1.06f), 0.16f, ArmorBlue, ArmorBlueL);
            b.Material(0.5f, 0.5f);
            IconShapes.RoundBox(b, new Vector3(0f, 0.2f, 0f), new Vector3(1.72f, 0.12f, 1.12f), 0.05f, H("#33598F"));
            // steel corner guards
            b.Material(0.82f, 0.8f);
            foreach (int sx in new[] { -1, 1 })
                foreach (int sy in new[] { -1, 1 })
                    IconShapes.RoundBox(b, new Vector3(sx * 0.74f, -0.15f + sy * 0.5f, -0.4f), new Vector3(0.3f, 0.3f, 0.36f), 0.1f, SteelL);
            // shield emblem
            var sh = IconShapes.Transform(ShieldOutline(), new Vector2(0.3f, 0.3f), new Vector2(0f, -0.2f));
            b.Material(0.8f, 0.65f);
            IconShapes.Pillow(b, sh, new Vector2(0f, -0.2f), 0.1f, 0f, 3.2f, SteelL, null, -0.53f);
        }

        static void BullBarModel(MeshBuilder b)
        {
            // wide ram plate with a steel hoop and three big spikes
            var plate = IconShapes.RoundCorners(new[] { new Vector2(-1.04f, 0.42f), new Vector2(1.04f, 0.42f), new Vector2(0.78f, -0.56f), new Vector2(-0.78f, -0.56f) }, 0.16f, 8);
            b.Material(0.66f, 0.42f);
            IconShapes.Pillow(b, plate, new Vector2(0f, -0.06f), 0.24f, 0.16f, 4.2f, ArmorBlue);
            // lower lip in a darker steel, top bar in light steel
            b.Material(0.6f, 0.5f);
            IconShapes.Capsule(b, new Vector3(-0.8f, -0.5f, -0.1f), new Vector3(0.8f, -0.5f, -0.1f), 0.09f, H("#33598F"));
            b.Material(0.84f, 0.8f);
            IconShapes.Capsule(b, new Vector3(-1.08f, 0.44f, -0.06f), new Vector3(1.08f, 0.44f, -0.06f), 0.12f, SteelL);
            b.Material(0.9f, 0.85f);
            foreach (float x in new[] { -0.56f, 0f, 0.56f })
            {
                var dir = new Vector3(0f, 0.86f, -0.5f).normalized;
                var basePos = new Vector3(x, 0.3f, -0.18f);
                b.Push(basePos, Quaternion.FromToRotation(Vector3.up, dir));
                b.Lathe(new[] { new Vector2(0f, -0.02f), new Vector2(0.2f, 0f), new Vector2(0.18f, 0.12f), new Vector2(0.09f, 0.48f), new Vector2(0.025f, 0.7f), new Vector2(0f, 0.72f) }, 32, H("#EEF2F6"));
                b.Pop();
            }
        }

        static void RoofPlatesModel(MeshBuilder b)
        {
            b.Material(0.6f, 0.4f);
            IconShapes.RoundBox(b, new Vector3(0.24f, 0.2f, 0.16f), new Vector3(1.3f, 1.3f, 0.16f), 0.07f, Quaternion.Euler(0, 0, 12f), ArmorBlueL);
            b.Material(0.68f, 0.45f);
            IconShapes.RoundBox(b, new Vector3(-0.16f, -0.14f, -0.04f), new Vector3(1.34f, 1.34f, 0.2f), 0.08f, Quaternion.Euler(0, 0, -6f), ArmorBlue);
            b.Material(0.85f, 0.6f);
            var rot = Quaternion.Euler(0, 0, -6f);
            foreach (int sx in new[] { -1, 1 })
                foreach (int sy in new[] { -1, 1 })
                {
                    var p = new Vector3(-0.16f, -0.14f, -0.15f) + rot * new Vector3(sx * 0.46f, sy * 0.46f, 0f);
                    b.Sphere(p, new Vector3(0.1f, 0.1f, 0.07f), Gold, 4);
                }
        }

        // ------------------------------------------------------------------ misc
        static void ZoomModel(MeshBuilder b)
        {
            var c = new Vector3(-0.14f, 0.2f, 0f);
            b.Material(0.95f, 0f);
            IconShapes.Pillow(b, IconShapes.Circle(0.56f, 128, new Vector2(c.x, c.y)), new Vector2(c.x, c.y), 0.1f, 0.08f, 2.2f, H("#BDEBFF"));
            b.Material(0.84f, 0.85f);
            IconShapes.Torus(b, c, Quaternion.Euler(-90f, 0, 0), 0.58f, 0.13f, SteelL);
            var d = new Vector3(Mathf.Cos(-50f * Mathf.Deg2Rad), Mathf.Sin(-50f * Mathf.Deg2Rad), 0f);
            b.CylinderBetween(c + d * 0.66f, c + d * 0.86f, 0.15f, 32, SteelM);
            b.Material(0.45f, 0f);
            IconShapes.Capsule(b, c + d * 0.86f, c + d * 1.5f, 0.15f, H("#6E4A33"));
        }

        static void HarpoonModel(MeshBuilder b)
        {
            var head = new[]
            {
                new Vector2(0f, 1.22f), new Vector2(0.22f, 0.74f), new Vector2(0.54f, 0.36f), new Vector2(0.19f, 0.5f),
                new Vector2(0.15f, 0.26f), new Vector2(-0.15f, 0.26f), new Vector2(-0.19f, 0.5f), new Vector2(-0.54f, 0.36f), new Vector2(-0.22f, 0.74f)
            };
            b.Material(0.86f, 0.6f);
            IconShapes.Pillow(b, IconShapes.RoundCorners(head, 0.04f, 6, new[] { 0.03f, 0.05f, 0.04f, 0.03f, 0.03f, 0.03f, 0.03f, 0.04f, 0.05f }), new Vector2(0f, 0.6f), 0.17f, 0.17f, 1.8f, SteelL);
            b.Material(0.7f, 0.4f);
            b.CylinderBetween(new Vector3(0, 0.12f, 0), new Vector3(0, 0.32f, 0), 0.15f, 24, Teal);
            b.Material(0.35f, 0f);
            b.CylinderBetween(new Vector3(0, -1.05f, 0), new Vector3(0, 0.16f, 0), 0.1f, 24, H("#6E4B33"));
            b.Sphere(new Vector3(0, -1.05f, 0), new Vector3(0.1f, 0.06f, 0.1f), H("#6E4B33"), 3);
            // rope tied around the shaft, trailing loop
            b.Material(0.25f, 0f);
            IconShapes.Torus(b, new Vector3(0, -0.6f, 0), Quaternion.identity, 0.135f, 0.065f, Rope, 32, 12);
            IconShapes.Torus(b, new Vector3(0, -0.46f, 0), Quaternion.identity, 0.135f, 0.065f, Rope, 32, 12);
            var loop = IconShapes.Bezier(new Vector3(0.12f, -0.6f, -0.02f), new Vector3(0.8f, -0.88f, -0.05f), new Vector3(0.3f, -1.1f, -0.02f), 16);
            IconShapes.Tube(b, loop, 0.065f, Rope, 14);
        }

        static void FlagModel(MeshBuilder b)
        {
            b.Material(0.35f, 0f);
            b.CylinderBetween(new Vector3(-0.62f, -1.05f, 0f), new Vector3(-0.62f, 0.98f, 0f), 0.09f, 24, WoodD);
            b.Material(0.8f, 0.6f);
            b.Sphere(new Vector3(-0.62f, 1.04f, 0f), Vector3.one * 0.15f, Gold, 4);
            // waving cloth: two thin surfaces with a closed rim
            int nu = 22, nv = 10;
            float th = 0.035f;
            Vector3 Cloth(float u, float v)
            {
                float x = Mathf.Lerp(-0.56f, 0.82f, u);
                float y = Mathf.Lerp(0.06f, 0.94f, v) - 0.12f * u * u + Mathf.Sin(u * 4.4f) * 0.04f;
                float z = Mathf.Sin(u * 4.6f - 0.4f) * 0.22f * Mathf.Sqrt(u);
                return new Vector3(x, y, z);
            }
            b.Material(0.4f, 0f);
            var clMain = H("#FF6A3C"); var clBand = Cream;
            var inside = new Vector3(0.1f, 0.5f, 0f);
            for (int i = 0; i < nu; i++)
                for (int j = 0; j < nv; j++)
                {
                    float u0 = i / (float)nu, u1 = (i + 1) / (float)nu, v0 = j / (float)nv, v1 = (j + 1) / (float)nv;
                    var a = Cloth(u0, v0); var c1 = Cloth(u1, v0); var c2 = Cloth(u1, v1); var d = Cloth(u0, v1);
                    var cl = (j == 4 || j == 5) ? clBand : clMain;
                    var n = Vector3.Cross(c1 - a, d - a).normalized;
                    var off = n * th;
                    b.Quad(cl, a - off, d - off, c2 - off, c1 - off);    // front (facing the camera side)
                    b.Quad(cl, a + off, c1 + off, c2 + off, d + off);    // back
                    if (j == 0) b.Quad(cl, a - off, c1 - off, c1 + off, a + off);
                    if (j == nv - 1) b.Quad(cl, d - off, d + off, c2 + off, c2 - off);
                    if (i == nu - 1) b.Quad(cl, c1 - off, c2 - off, c2 + off, c1 + off);
                }
        }

        static void TargetModel(MeshBuilder b)
        {
            var red = H("#E8413B");
            b.Material(0.62f, 0f);
            IconShapes.Pillow(b, IconShapes.Circle(1f), Vector2.zero, 0.22f, 0.2f, 4.2f, red);
            IconShapes.Pillow(b, IconShapes.Circle(0.72f), Vector2.zero, 0.07f, 0f, 4f, Cream, null, -0.18f);
            IconShapes.Pillow(b, IconShapes.Circle(0.46f), Vector2.zero, 0.07f, 0f, 4f, red, null, -0.23f);
            IconShapes.Pillow(b, IconShapes.Circle(0.21f), Vector2.zero, 0.06f, 0f, 4f, Cream, null, -0.28f);
            // dart in the bullseye
            var tip = new Vector3(0.02f, 0.02f, -0.3f);
            var tail = tip + new Vector3(0.5f, 0.58f, -0.62f);
            b.Material(0.75f, 0.5f);
            b.CylinderBetween(tip, tail, 0.055f, 20, Gold);
            b.Material(0.5f, 0f);
            var dir = (tail - tip).normalized;
            for (int k = 0; k < 3; k++)
            {
                b.Push(tail - dir * 0.12f, Quaternion.LookRotation(dir) * Quaternion.Euler(0, 0, k * 120f));
                b.PolyOut(Teal, new Vector3(-0.05f, 0, 0), new Vector3(0f, 0f, -0.12f), new Vector3(0f, 0.17f, -0.2f), new Vector3(0f, 0.17f, 0.04f), new Vector3(0f, 0f, 0.1f));
                b.PolyOut(Teal, new Vector3(0.05f, 0, 0), new Vector3(0f, 0f, -0.12f), new Vector3(0f, 0.17f, -0.2f), new Vector3(0f, 0.17f, 0.04f), new Vector3(0f, 0f, 0.1f));
                b.Pop();
            }
        }
    }
}
