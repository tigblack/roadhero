using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// The hero car, styled for a top-down phone camera: a low graphite muscle car turned into a pickup (ute) - long
    /// hood with two cream racing stripes and an oversized blower, four round headlights, a short cab, an open bed with
    /// rails, a plank floor and a tailgate with upright tail lights, chunky side pipes, wide tires on cream deep-dish
    /// rims. A small machine gun turns on a low base on the right half of the hood; the harpoon turret and its operator
    /// stand in the bed (ModelsActors). Wheels are NOT children of the body so the suspension can move the body over them.
    /// </summary>
    public static partial class Models
    {
        // geometry shared with the vehicle physics / attachments
        public const float CarFrontAxleZ = 1.45f, CarRearAxleZ = -1.42f;
        public const float CarFrontWheelR = 0.38f, CarRearWheelR = 0.44f;
        public const float CarFrontWheelW = 0.31f, CarRearWheelW = 0.45f;
        /// <summary>x of the wheel centers. The rear track is wide so the rear wells stay outside the bed's walls.</summary>
        public const float CarFrontTrack = 0.86f, CarRearTrack = 0.97f;
        public static readonly Vector3[] CarPipeTips =
        {
            new Vector3(1.08f, 0.37f, -0.84f), new Vector3(-1.08f, 0.37f, -0.84f)
        };

        /// <summary>
        /// The pickup bed (car-body space): inner faces of its front wall (under the cab's back) and of the tailgate,
        /// the plank floor, the rail / tailgate top and the widest inner half width (the walls follow the body's plan,
        /// so the bed narrows a little at its rounded rear corners).
        /// </summary>
        public const float BedFrontZ = -0.70f, BedRearZ = -2.17f, BedFloorY = 0.60f, BedRailY = 0.99f, BedInnerX = 0.70f;
        /// <summary>Base plate of the harpoon turret on the bed floor, in the middle of the bed: its operator walks round
        /// the column with the turret and stays inside the bed in every direction.</summary>
        public static readonly Vector3 HarpoonMount = new Vector3(0f, BedFloorY, -1.55f);

        // hero palette: graphite paint, cream stripes, a single teal accent, light steel equipment
        static readonly Color CarPaintC = Hex("#3B4049"), CarPaintLow = Hex("#2C3037"), CarStripe = Hex("#EFE4CC");
        static readonly Color CarAccent = Hex("#34B4A2"), CarGlass = Hex("#45616F"), CarChrome = Hex("#DCE1E6");
        static readonly Color CarTrim = Hex("#1F2125"), CarRubber = Hex("#302C2C"), CarSteel = Hex("#AEB6BE");
        static readonly Color CarAlu = Hex("#C9CED4"), CarUnder = Hex("#1B1C1F"), CarPipe = Hex("#BDB6AC");
        static readonly Color CarRope = Hex("#E6D6B0"), CarRim = Hex("#E2D5BC");
        // the bed: darker painted inner walls, grey weathered planks (the operator's brown cloak stands out on them)
        static readonly Color BedWall = Hex("#30343B"), BedWoodA = Hex("#6C665E"), BedWoodB = Hex("#605A53"), BedWoodEdge = Hex("#3A3632");

        const float CarZFront = 2.37f, CarZRear = -2.38f;
        const float StripeIn = 0.3f, StripeOut = 0.44f;   // racing stripes over the hood and the roof
        const float BodyShoulderR = 0.12f;

        // ------------------------------------------------------------------ body shape functions
        static float CarT(float z) => (z - (CarZFront + CarZRear) * 0.5f) / ((CarZFront - CarZRear) * 0.5f);

        static float Flare(float z, float axle, float half)
        {
            float d = Mathf.Abs(z - axle) / half;
            if (d >= 1f) return 0f;
            float k = 1f - d * d;
            return k * k;
        }

        /// <summary>Plan view half width: rounded nose, square pickup tail, narrow waist, strong rear haunches.</summary>
        static float CarHalfWidth(float z)
        {
            float t = CarT(z);
            float a = Mathf.Min(Mathf.Abs(t), 0.999f);
            float w = t >= 0f ? 0.86f * Mathf.Pow(1f - Mathf.Pow(a, 8f), 0.12f) : 0.86f * Mathf.Pow(1f - Mathf.Pow(a, 16f), 0.1f);
            return w + 0.075f * Flare(z, CarFrontAxleZ, 0.7f) + 0.19f * Flare(z, CarRearAxleZ, 0.82f);
        }

        /// <summary>Top of the body: the hood falls to the nose; behind it one flat beltline under the cab, along the
        /// bed rails and over the tailgate.</summary>
        static float CarTop(float z)
        {
            if (z > 0.55f)
            {
                float u = (z - 0.55f) / (CarZFront - 0.55f);
                float top = Mathf.Lerp(0.99f, 0.87f, u);
                if (z > 2.05f) top -= (z - 2.05f) * (z - 2.05f) * 1.2f;
                return top;
            }
            float t2 = BedRailY;
            if (z < -2.28f) t2 -= (-2.28f - z) * (-2.28f - z) * 3f;   // rounded top edge of the tailgate
            return t2;
        }

        static float CarBottom(float z)
        {
            float y = 0.3f;
            if (z > 2.0f) y += (z - 2.0f) * 0.55f;
            if (z < -2.05f) y += (-2.05f - z) * 0.5f;
            return y;
        }

        static float CarCrown(float z) => z > 0.55f ? 0.05f : 0.01f;

        /// <summary>Inner edge of the shoulder (where the body's flat top begins) at z.</summary>
        static float BodyTopEdge(float z) => SideX(CarHalfWidth(z), 1f) - BodyShoulderR;

        /// <summary>Half width inside the bed at z (the rails keep at least 6 cm of flat top).</summary>
        public static float BedInnerHalf(float z) => Mathf.Min(BedInnerX, BodyTopEdge(z) - 0.06f);

        /// <summary>Wheel arch: height of the arch opening at z (yBot when no wheel is near) and the x of the well's
        /// inner wall (the rear one sits just inside the wide rear tires, outside the bed).</summary>
        static float CarArchCut(float z, float yBot, out float wellX)
        {
            wellX = 0.6f;
            float best = yBot;
            for (int i = 0; i < 2; i++)
            {
                float zw = i == 0 ? CarFrontAxleZ : CarRearAxleZ;
                float r = i == 0 ? CarFrontWheelR : CarRearWheelR;
                float ra = r + 0.07f;
                float d = z - zw;
                if (Mathf.Abs(d) >= ra) continue;
                if (i == 1) wellX = CarRearTrack - CarRearWheelW * 0.5f - 0.025f;
                float y = r + Mathf.Sqrt(ra * ra - d * d);
                if (y > best) best = y;
            }
            return best;
        }

        static float SideX(float w, float s) => w * (0.92f + 0.08f * Mathf.Sin(Mathf.PI * (0.12f + 0.72f * s)));

        // top points of a closed section (deck); the stripe runs between TopX[2] and TopX[3]
        static readonly float[] TopX = { 0.62f, 0.53f, StripeOut, StripeIn, 0.225f, 0.15f, 0.075f, 0f };
        static readonly float[] TopF = { 0.95f, 0.85f, 0.75f, 0.55f, 0.42f, 0.3f, 0.15f, 0f };
        // plank seams of the bed floor (an open section's top points after the inner wall)
        static readonly float[] PlankX = { 0.585f, 0.468f, 0.351f, 0.234f, 0.117f, 0f };
        const int BodyK = 6, BodyArc = 5;
        const int TopStart = 4 + BodyK + BodyArc;    // index of the first top point in a section's right half
        const int BodyRight = TopStart + 8;          // points in the right half

        /// <summary>
        /// One closed body cross-section at z: right half (bottom center .. top center), then mirrored. The point count
        /// is constant so the sections can be lofted; stripe edges are explicit points. An open section (inside the bed)
        /// uses its top points for the rail's inner edge, the inner wall and the plank floor instead of the deck.
        /// </summary>
        static Vector3[] BodySection(float z, bool open)
        {
            const float rS = BodyShoulderR;
            float w = CarHalfWidth(z);
            float yBot = CarBottom(z);
            float top = CarTop(z);
            float crown = CarCrown(z);
            float yTop = top - rS;
            float cut = Mathf.Min(CarArchCut(z, yBot, out float wellX), yTop - 0.03f);
            float sCut = Mathf.Clamp01((cut - yBot) / Mathf.Max(0.01f, yTop - yBot));
            float wx = Mathf.Min(wellX, w * 0.7f);
            var right = new List<Vector2>(BodyRight)
            {
                new Vector2(0f, yBot), new Vector2(wx, yBot), new Vector2(wx, cut), new Vector2(SideX(w, sCut), cut)
            };
            for (int k = 1; k <= BodyK; k++)
            {
                float s = sCut + (1f - sCut) * k / BodyK;
                right.Add(new Vector2(SideX(w, s), Mathf.Lerp(yBot, yTop, s)));
            }
            float xt = SideX(w, 1f) - rS;
            for (int a = 1; a <= BodyArc; a++)
            {
                float ang = a * 90f / BodyArc * Mathf.Deg2Rad;
                right.Add(new Vector2(xt + rS * Mathf.Cos(ang), yTop + rS * Mathf.Sin(ang)));
            }
            if (!open)
            {
                for (int i = 0; i < TopX.Length; i++)
                {
                    float tx = Mathf.Min(TopX[i], xt * TopF[i]);
                    float u = xt > 0.01f ? tx / xt : 0f;
                    right.Add(new Vector2(tx, top + crown * (1f - u * u)));
                }
            }
            else
            {
                float xi = Mathf.Min(BedInnerX, xt - 0.06f);
                right.Add(new Vector2(xi, top));            // inner edge of the rail
                right.Add(new Vector2(xi, BedFloorY));      // foot of the inner wall
                foreach (float px in PlankX) right.Add(new Vector2(Mathf.Min(px, xi - 0.025f), BedFloorY));
            }
            var loop = new List<Vector3>(right.Count * 2);
            foreach (var p in right) loop.Add(new Vector3(p.x, p.y, z));
            for (int i = right.Count - 2; i >= 1; i--) loop.Add(new Vector3(-right[i].x, right[i].y, z));
            return loop.ToArray();
        }

        /// <summary>Short cab: a fairly upright windshield, a flat roof, a rounded rear edge down to the back wall.</summary>
        const float RoofFrontZ = 0.12f;
        static float CabinRoofY(float z)
        {
            if (z > RoofFrontZ) return Mathf.Lerp(1.31f, 0.99f, Mathf.Pow(Mathf.Clamp01((z - RoofFrontZ) / (0.6f - RoofFrontZ)), 0.95f));
            if (z > -0.5f) return 1.31f + 0.008f * Mathf.Sin((z + 0.5f) / (RoofFrontZ + 0.5f) * Mathf.PI);
            float u = Mathf.Clamp01((-0.5f - z) / (-0.5f - BedFrontZ));
            return 1.31f - 0.045f * u * u;
        }

        // ------------------------------------------------------------------ the car
        /// <summary>The player's graphite V8 pickup: smooth body with an open bed, blower, side pipes.</summary>
        public static GameObject PlayerCar(out Rig rig)
        {
            var root = new GameObject("PlayerCar");
            rig = root.AddComponent<Rig>();
            var mesh = Cached("playercar_pickup1", BuildCarBody);
            var body = MeshGO("Body", mesh, Mats.CarPaint, root.transform);
            rig.body = body.transform;
            var extras = Cached("playercar_pickup1_extras", BuildCarExtras);
            MeshGO("Details", extras, Mats.Toon, body.transform);
            // wheels belong to the root (the suspension moves the body over them)
            CarWheel(root.transform, new Vector3(-CarFrontTrack, CarFrontWheelR, CarFrontAxleZ), CarFrontWheelR, CarFrontWheelW, -1, rig, true);
            CarWheel(root.transform, new Vector3(CarFrontTrack, CarFrontWheelR, CarFrontAxleZ), CarFrontWheelR, CarFrontWheelW, 1, rig, true);
            CarWheel(root.transform, new Vector3(-CarRearTrack, CarRearWheelR, CarRearAxleZ), CarRearWheelR, CarRearWheelW, -1, rig, false);
            CarWheel(root.transform, new Vector3(CarRearTrack, CarRearWheelR, CarRearAxleZ), CarRearWheelR, CarRearWheelW, 1, rig, false);
            rig.wheelRadius = CarRearWheelR;
            rig.height = 2.4f;
            return root;
        }

        static void CarWheel(Transform parent, Vector3 pos, float r, float w, int side, Rig rig, bool steer)
        {
            var steerT = new GameObject(steer ? "WheelSteer" : "Wheel").transform;
            steerT.SetParent(parent, false);
            steerT.localPosition = pos;
            var spin = MeshGO("Wheel", CarWheelMesh(r, w, side), Mats.Toon, steerT).transform;
            rig.wheels.Add(spin);
            if (steer) rig.steer.Add(steerT);
        }

        static void BuildCarBody(MeshBuilder b)
        {
            // ---------------- lower body (lofted cross-sections). From the cab's back to the tailgate the sections are
            //                  open (rails, inner walls, plank floor); a closed and an open section at the same z make the
            //                  bed's front wall and the tailgate's inner face.
            var zs = new List<float>();
            var open = new List<bool>();
            void Add(float z, bool o) { zs.Add(z); open.Add(o); }
            float zEndF = CarZFront - 0.02f, zEndR = CarZRear + 0.02f;
            for (float z = zEndR; z < BedRearZ - 0.02f; z += 0.065f) Add(z, false);
            Add(BedRearZ, false); Add(BedRearZ, true);
            int nb = Mathf.CeilToInt((BedFrontZ - BedRearZ) / 0.065f);
            for (int k = 1; k < nb; k++) Add(Mathf.Lerp(BedRearZ, BedFrontZ, k / (float)nb), true);
            Add(BedFrontZ, true); Add(BedFrontZ, false);
            for (float z = BedFrontZ + 0.065f; z < zEndF - 0.02f; z += 0.065f) Add(z, false);
            Add(zEndF, false);
            int ns = zs.Count;
            var grid = new Vector3[ns][];
            for (int i = 0; i < ns; i++) grid[i] = BodySection(zs[i], open[i]);
            int np = grid[0].Length;
            const int stripeJ = TopStart + 2;            // quad from TopX[2] (stripe outer) to TopX[3] (stripe inner)
            b.Loft(grid, (i, j) =>
            {
                bool left = j > BodyRight - 2;
                int jj = left ? np - 1 - j : j;           // the quad mirrored onto the right half
                bool o0 = open[i], o1 = open[i + 1];
                if (o0 != o1)
                {
                    // the bed's end walls: the cab's back (painted like the cab above it), the tailgate's inner face
                    b.Material(0.4f, 0f);
                    return zs[i] > (BedFrontZ + BedRearZ) * 0.5f ? CarPaintC : BedWall;
                }
                if (o0 && jj >= TopStart)
                {
                    if (jj == TopStart) { b.Material(0.4f, 0f); return BedWall; }          // inner side walls
                    b.Material(0.12f, 0f);                                               // matte planks
                    if (jj == TopStart + 1) return BedWoodEdge;
                    return ((jj - TopStart) + (left ? 1 : 0)) % 2 == 0 ? BedWoodA : BedWoodB;
                }
                b.Material(0.78f, 0f);
                if (jj == stripeJ && !o0 && zs[i] > BedFrontZ) return CarStripe;
                if (jj < 3) return CarUnder;                                             // underside, wheel wells, arch roofs
                var a = grid[i][j]; var c = grid[i + 1][(j + 1) % np];
                if ((a.y + c.y) * 0.5f < 0.5f) return CarPaintLow;                       // darker sills: a clear lower body line
                return CarPaintC;
            }, true, i => new Vector3(0, (CarBottom(zs[i]) + (open[i] ? BedFloorY : CarTop(zs[i]))) * 0.5f, zs[i]),
               (i, j) => zs[i + 1] - zs[i] > 0.01f && j >= 4 && j <= 3 + BodyK);   // decide the winding on the body's sides
            b.Material(0.78f, 0f);
            CapSection(b, grid[ns - 1], new Vector3(0, 0.6f, zEndF - 1f), CarPaintC);
            CapSection(b, grid[0], new Vector3(0, 0.6f, zEndR + 1f), CarPaintC);

            // ---------------- cab / greenhouse: windshield, short roof, a flat back wall with a wide rear window
            var cz = new List<float>();
            for (float z = 0.6f; z > BedFrontZ + 0.03f; z -= 0.055f) cz.Add(z);
            cz.Add(BedFrontZ);
            int nc = cz.Count;
            var cg = new Vector3[nc][];
            const float yb = 0.95f;
            for (int i = 0; i < nc; i++)
            {
                float z = cz[i];
                float roof = Mathf.Max(CabinRoofY(z), yb + 0.004f);
                float wb = Mathf.Min(0.8f, CarHalfWidth(z) - 0.12f);
                float wt = Mathf.Min(wb - 0.1f, 0.6f);
                float h = roof - yb;
                float rc = Mathf.Min(0.12f, h * 0.45f);
                var right = new List<Vector2>
                {
                    new Vector2(0, yb), new Vector2(wb, yb), new Vector2(Mathf.Lerp(wb, wt, 0.35f), yb + (h - rc) * 0.35f),
                    new Vector2(Mathf.Lerp(wb, wt, 0.7f), yb + (h - rc) * 0.7f), new Vector2(wt, roof - rc)
                };
                for (int a = 1; a <= 3; a++)
                {
                    float ang = a * 30f * Mathf.Deg2Rad;
                    right.Add(new Vector2(wt - rc + rc * Mathf.Cos(ang), roof - rc + rc * Mathf.Sin(ang)));
                }
                float flat = wt - rc;
                right.Add(new Vector2(Mathf.Min(StripeOut, flat * 0.92f), roof + 0.01f));
                right.Add(new Vector2(Mathf.Min(StripeIn, flat * 0.62f), roof + 0.014f));
                right.Add(new Vector2(Mathf.Min(0.15f, flat * 0.32f), roof + 0.017f));
                right.Add(new Vector2(0, roof + 0.018f));
                var loop = new List<Vector3>();
                foreach (var p in right) loop.Add(new Vector3(p.x, p.y, z));
                for (int k = right.Count - 2; k >= 1; k--) loop.Add(new Vector3(-right[k].x, right[k].y, z));
                cg[i] = loop.ToArray();
            }
            int cnp = cg[0].Length;
            const int cStripeR = 8;
            int cStripeL = cnp - 1 - cStripeR;
            b.Material(0.82f, 0f);
            b.Loft(cg, (i, j) =>
            {
                var a = cg[i][j]; var c = cg[i + 1][(j + 1) % cnp];
                var center = (a + c) * 0.5f;
                var col = CabinColor(center, cg[i], j);
                if ((j == cStripeR || j == cStripeL) && col != CarGlass) return CarStripe;
                return col;
            }, true, i => new Vector3(0, yb, cz[i]));
            CapSection(b, cg[nc - 1], new Vector3(0, 1.1f, BedFrontZ + 0.5f), CarPaintC);
            // rear window in the back wall, looking into the bed
            b.Material(0.9f, 0f);
            b.BevelBox(new Vector3(0f, 1.155f, BedFrontZ - 0.004f), new Vector3(0.9f, 0.17f, 0.012f), 0.005f, CarGlass);
            b.Material(0.4f, 0.3f);
            b.BevelBox(new Vector3(0f, 1.155f, BedFrontZ - 0.002f), new Vector3(0.96f, 0.22f, 0.006f), 0.003f, CarTrim);
            b.Matte();
        }

        static Color CabinColor(Vector3 c, Vector3[] s0, int j)
        {
            float z = c.z;
            float roof = CabinRoofY(z);
            const float yb = 0.95f;
            if (roof - yb < 0.05f) return CarPaintC;
            int np = s0.Length;
            var a = s0[j]; var bb = s0[(j + 1) % np];
            var tangent = bb - a;
            var nrm = new Vector3(tangent.y, -tangent.x, 0f);
            if (Vector3.Dot(nrm, new Vector3(a.x, a.y - yb, 0)) < 0) nrm = -nrm;
            nrm.Normalize();
            float u = Mathf.Clamp01((c.y - yb) / (roof - yb));
            float wb = Mathf.Min(0.8f, CarHalfWidth(z) - 0.12f), wt = Mathf.Min(wb - 0.1f, 0.6f);
            float localW = Mathf.Lerp(wb, wt, u);
            if (Mathf.Abs(nrm.x) > 0.6f)
            {
                // side glass from the A-pillar back to the B-pillar (a short cab)
                if (z < 0.48f && z > -0.52f && c.y > yb + 0.06f && c.y < roof - 0.06f) return CarGlass;
                return CarPaintC;
            }
            if (z > RoofFrontZ + 0.02f && z < 0.56f && Mathf.Abs(c.x) < localW - 0.1f && c.y > yb + 0.03f) return CarGlass;   // windshield
            return CarPaintC;
        }

        static void CapSection(MeshBuilder b, Vector3[] loop, Vector3 inside, Color col)
        {
            var center = Vector3.zero;
            foreach (var p in loop) center += p;
            center /= loop.Length;
            for (int i = 0; i < loop.Length; i++)
            {
                var p0 = loop[i]; var p1 = loop[(i + 1) % loop.Length];
                if ((p0 - p1).sqrMagnitude < 1e-10f) continue;
                b.PolyOut(col, inside, center, p0, p1);
            }
        }

        /// <summary>Lights, bumpers, blower, pipes, bed ribs (stylized material per vertex).</summary>
        static void BuildCarExtras(MeshBuilder b)
        {
            // ---------------- front: dark fascia, two big round lamps per side, chrome bumper, chin spoiler
            float zf = CarZFront;
            b.Material(0.35f, 0f);
            b.BevelBox(new Vector3(0, 0.62f, zf - 0.03f), new Vector3(1.16f, 0.24f, 0.1f), 0.04f, CarTrim);
            b.Material(0.85f, 1f);
            for (int i = 0; i < 3; i++) b.BevelBox(new Vector3(0, 0.56f + i * 0.06f, zf + 0.025f), new Vector3(0.5f, 0.026f, 0.03f), 0.01f, CarChrome);
            foreach (float x in new[] { -0.44f, -0.25f, 0.25f, 0.44f })
            {
                b.Push(new Vector3(x, 0.63f, zf + 0.01f), Quaternion.Euler(90, 0, 0));
                b.Material(0.95f, 1f);
                b.Lathe(new[] { new Vector2(0.09f, -0.03f), new Vector2(0.095f, 0.0f), new Vector2(0.078f, 0.018f) }, 18, CarChrome);
                b.Material(0.7f, 0f);
                b.Lathe(new[] { new Vector2(0.078f, 0.0f), new Vector2(0.05f, 0.024f), new Vector2(0f, 0.03f) }, 18, Glow("#FFF1C8", 0.3f));
                b.Pop();
            }
            b.Material(0.9f, 1f);
            var bumperF = new List<Vector3>();
            for (int i = 0; i <= 12; i++)
            {
                float t = i / 12f * 2f - 1f;
                bumperF.Add(new Vector3(t * 0.86f, 0.42f, zf + 0.07f - Mathf.Pow(Mathf.Abs(t), 5f) * 0.3f));
            }
            b.Sweep(bumperF, MeshBuilder.RoundRectProfile(0.1f, 0.13f, 0.045f), CarChrome);
            b.Material(0.3f, 0f);
            b.BevelBox(new Vector3(0, 0.32f, zf - 0.02f), new Vector3(1.6f, 0.07f, 0.24f), Quaternion.Euler(-12, 0, 0), 0.025f, CarTrim);

            // ---------------- rear: tailgate with two pairs of upright tail lights in dark bezels, a round badge, a seam
            //                  under its top edge, chrome bumper
            float zr = CarZRear + 0.02f;   // the body's rear face
            b.Material(0.35f, 0f);
            foreach (float sx in new[] { -1f, 1f })
                b.BevelBox(new Vector3(sx * 0.47f, 0.79f, zr - 0.012f), new Vector3(0.27f, 0.23f, 0.04f), 0.025f, CarTrim);
            b.Material(0.7f, 0f);
            foreach (float x in new[] { -0.53f, -0.41f, 0.41f, 0.53f })
                b.BevelBox(new Vector3(x, 0.79f, zr - 0.034f), new Vector3(0.075f, 0.175f, 0.024f), 0.012f, Glow("#F0412E", 0.4f));
            b.Push(new Vector3(0f, 0.8f, zr - 0.006f), Quaternion.Euler(-90f, 0f, 0f));
            b.Material(0.95f, 1f);
            b.Cylinder(Vector3.zero, 0.058f, 0.02f, 18, CarChrome);
            b.Material(0.3f, 0f);
            b.Cylinder(new Vector3(0f, 0.02f, 0f), 0.034f, 0.004f, 14, CarTrim);
            b.Pop();
            b.Material(0.2f, 0f);
            b.SharpBox(new Vector3(0f, 0.925f, zr - 0.003f), new Vector3(1.0f, 0.012f, 0.008f), CarTrim);
            b.Material(0.9f, 1f);
            var bumperR = new List<Vector3>();
            for (int i = 0; i <= 12; i++)
            {
                float t = i / 12f * 2f - 1f;
                bumperR.Add(new Vector3(t * 0.86f, 0.48f, CarZRear - 0.06f + Mathf.Pow(Mathf.Abs(t), 5f) * 0.28f));
            }
            b.Sweep(bumperR, MeshBuilder.RoundRectProfile(0.1f, 0.12f, 0.045f), CarChrome);

            // ---------------- blower through the front of the hood (scoop top ~1.31 m); the machine gun turns beside it
            float hoodY = CarTop(1.78f) + CarCrown(1.78f) - 0.02f;
            b.Push(new Vector3(0, hoodY, 1.78f));
            b.Material(0.35f, 0.5f);
            b.BevelBox(new Vector3(0, 0.04f, 0), new Vector3(0.56f, 0.08f, 0.66f), 0.03f, Hex("#2A2E34"));
            b.Material(0.6f, 0.75f);
            b.Sweep(new List<Vector3> { new Vector3(0, 0.19f, -0.24f), new Vector3(0, 0.19f, 0.24f) }, MeshBuilder.RoundRectProfile(0.46f, 0.24f, 0.09f, 4), CarAlu);
            for (int i = 0; i < 3; i++)
            {
                float z = -0.18f + i * 0.18f;
                b.Sweep(new List<Vector3> { new Vector3(0, 0.19f, z - 0.02f), new Vector3(0, 0.19f, z + 0.02f) }, MeshBuilder.RoundRectProfile(0.5f, 0.28f, 0.11f, 4), Shade(CarAlu, 0.86f));
            }
            b.Material(0.7f, 0.25f);
            b.BevelBox(new Vector3(0, 0.18f, 0.27f), new Vector3(0.42f, 0.24f, 0.05f), 0.03f, CarAccent);
            b.Material(0.9f, 1f);
            b.Push(new Vector3(0, 0.2f, 0.3f), Quaternion.Euler(90, 0, 0));
            b.Cylinder(Vector3.zero, 0.08f, 0.05f, 12, CarChrome);
            b.Pop();
            b.Material(0.15f, 0f);
            b.BevelBox(new Vector3(0, 0.09f, 0.32f), new Vector3(0.07f, 0.24f, 0.03f), 0.01f, CarRubber);
            // low injector scoop with two dark intakes and butterflies
            b.Material(0.9f, 1f);
            b.BevelBox(new Vector3(0, 0.315f, 0.02f), new Vector3(0.26f, 0.1f, 0.3f), 0.04f, CarChrome);
            b.Material(0.1f, 0f);
            foreach (float x in new[] { -0.06f, 0.06f })
                b.BevelBox(new Vector3(x, 0.365f, 0.05f), new Vector3(0.09f, 0.02f, 0.13f), 0.008f, Hex("#111214"));
            b.Material(0.6f, 0.9f);
            foreach (float x in new[] { -0.06f, 0.06f })
                b.Box(new Vector3(x, 0.372f, 0.05f), new Vector3(0.08f, 0.01f, 0.016f), Quaternion.Euler(0, 0, 20f), Hex("#9AA3AB"));
            b.Pop();

            // ---------------- chunky side pipes with heat shields
            for (int s = -1; s <= 1; s += 2)
            {
                b.Material(0.6f, 0.85f);
                var path = new List<Vector3>
                {
                    new Vector3(s * 0.84f, 0.64f, 1.06f), new Vector3(s * 0.97f, 0.57f, 0.96f), new Vector3(s * 1.05f, 0.46f, 0.8f),
                    new Vector3(s * 1.075f, 0.37f, 0.6f), new Vector3(s * 1.075f, 0.37f, 0f), new Vector3(s * 1.08f, 0.37f, -0.84f)
                };
                b.Sweep(path, MeshBuilder.CircleProfile(0.07f, 14), CarPipe, false, true);
                b.Material(0.1f, 0f);
                b.Push(new Vector3(s * 1.08f, 0.37f, -0.845f), Quaternion.Euler(-90, 0, 0));
                b.Disc(Vector3.zero, 0.05f, 12, Hex("#0E0D0D"));
                b.Pop();
                b.Material(0.45f, 0.7f);
                b.BevelBox(new Vector3(s * 1.1f, 0.4f, -0.05f), new Vector3(0.06f, 0.12f, 0.86f), 0.03f, Hex("#7E868E"));
            }

            // ---------------- bed: upright stakes on the inner walls
            b.Material(0.45f, 0.1f);
            foreach (float z in new[] { -0.98f, -1.3f, -1.62f, -1.94f })
                for (int s = -1; s <= 1; s += 2)
                {
                    float xi = BedInnerHalf(z);
                    b.BevelBox(new Vector3(s * (xi - 0.012f), (BedFloorY + BedRailY) * 0.5f - 0.01f, z), new Vector3(0.026f, BedRailY - BedFloorY - 0.04f, 0.045f), 0.008f, CarPaintC);
                }
            b.Matte();
        }

        /// <summary>Wheel: fat tire with rounded shoulders and chunky lugs, cream deep-dish rim with five holes and a
        /// teal center cap. side = +1 for right wheels (rim face toward +X), -1 for left wheels.</summary>
        public static Mesh CarWheelMesh(float R, float W, int side)
        {
            return Cached("carwheel4_" + R.ToString("0.000") + "_" + W.ToString("0.000") + "_" + side, b =>
            {
                b.Push(Vector3.zero, Quaternion.Euler(0, 0, -90f * side)); // lathe axis Y -> +X / -X
                float hw = W * 0.5f;
                float rIn = R * 0.62f;
                b.Material(0.14f, 0f);
                b.Lathe(new[]
                {
                    new Vector2(rIn, -hw + 0.02f), new Vector2(R * 0.8f, -hw - 0.01f), new Vector2(R * 0.93f, -hw + 0.008f),
                    new Vector2(R, -hw + 0.07f), new Vector2(R, hw - 0.07f),
                    new Vector2(R * 0.93f, hw - 0.008f), new Vector2(R * 0.8f, hw + 0.01f), new Vector2(rIn, hw - 0.02f)
                }, 28, CarRubber);
                // chunky lugs in two staggered rows
                int lugs = 12;
                for (int i = 0; i < lugs; i++)
                    for (int row = -1; row <= 1; row += 2)
                    {
                        float a = i * 360f / lugs + (row > 0 ? 180f / lugs : 0f);
                        b.Push(Vector3.zero, Quaternion.Euler(0, -a, 0));
                        b.Box(new Vector3(R + 0.012f, row * hw * 0.27f, 0), new Vector3(0.028f, hw * 0.62f, R * 0.26f), Hex("#3B3636"));
                        b.Pop();
                    }
                // rim: chrome lip, cream deep dish, teal cap
                b.Material(0.95f, 1f);
                b.Lathe(new[] { new Vector2(rIn - 0.004f, hw - 0.035f), new Vector2(rIn + 0.008f, hw - 0.008f), new Vector2(rIn - 0.015f, hw + 0.002f) }, 28, CarChrome);
                b.Material(0.55f, 0.3f);
                b.Lathe(new[]
                {
                    new Vector2(rIn - 0.015f, hw + 0.002f), new Vector2(rIn - 0.035f, hw - 0.04f), new Vector2(rIn * 0.7f, hw - 0.07f),
                    new Vector2(rIn * 0.36f, hw - 0.06f), new Vector2(rIn * 0.28f, hw - 0.035f)
                }, 28, CarRim);
                b.Material(0.7f, 0.2f);
                b.Lathe(new[] { new Vector2(rIn * 0.28f, hw - 0.035f), new Vector2(rIn * 0.22f, hw - 0.012f), new Vector2(0f, hw - 0.004f) }, 18, CarAccent);
                b.Material(0.1f, 0f);
                for (int i = 0; i < 5; i++)
                {
                    float a = (i * 72f + 36f) * Mathf.Deg2Rad;
                    var c = new Vector3(Mathf.Cos(a) * rIn * 0.56f, hw - 0.062f, Mathf.Sin(a) * rIn * 0.56f);
                    var pts = new Vector3[12];
                    for (int k = 0; k < 12; k++)
                    {
                        float u = k / 12f * Mathf.PI * 2f;
                        pts[k] = c + new Vector3(Mathf.Cos(u), 0, Mathf.Sin(u)) * rIn * 0.15f + Vector3.up * 0.002f;
                    }
                    b.PolyOut(Hex("#121112"), c - Vector3.up, pts);
                }
                b.Material(0f, 0f);
                b.Push(new Vector3(0, -hw + 0.025f, 0), Quaternion.Euler(180, 0, 0));
                b.Disc(Vector3.zero, rIn, 12, Hex("#141213"));
                b.Pop();
                b.Pop();
            });
        }

        // ------------------------------------------------------------------ hood machine gun
        /// <summary>Hood height (with the crown) at (x, z), for parts sitting on the hood.</summary>
        static float HoodY(float x, float z)
        {
            float u = Mathf.Clamp01(Mathf.Abs(x) / 0.72f);
            return CarTop(z) + CarCrown(z) * (1f - u * u);
        }

        // gun palette: mid-grey metal (it reads on the dark hood), black polymer stock and grip, light steel details;
        // the tier color only as thin bands
        static readonly Color GunMetal = Hex("#646C74"), GunPolymer = Hex("#222527"), GunBarrel = Hex("#7A838B");
        static readonly Color GunSteel = Hex("#D2D8DD"), GunBore = Hex("#0B0B0C"), GunPlate = Hex("#8A939B");

        /// <summary>Gun accent per tier (level 1 / 5 / 10 / 20): hero teal, steel blue, violet, gold.</summary>
        static Color TurretAccent(int tier) => tier >= 3 ? Hex("#F2C14E") : tier == 2 ? Hex("#A77BEA") : tier == 1 ? Hex("#5FAEE8") : CarAccent;

        const float GunX = 0.56f, GunZ = 1.05f;
        /// <summary>
        /// Hood machine gun: top of its bolted base plate on the right half of the hood (the car's right in the driving
        /// direction), beside the blower and a little behind it. The yaw axis stands upright; the plate takes up the
        /// hood's slope.
        /// </summary>
        public static readonly Vector3 GunMount = new Vector3(GunX, HoodY(GunX, GunZ) + 0.025f, GunZ);
        public const float GunPivotY = 0.12f;    // trunnion pin above the plate top (the yaw part's base)
        public const float GunBoreY = 0.035f;    // barrel axis above the trunnion
        public const float GunMuzzleZ = 0.53f;   // end of the flash hider ahead of the trunnion
        public const float GunButtZ = -0.246f;   // butt plate behind the trunnion (a short stock: room to lift the gun)
        /// <summary>Muzzle distance along the gun's z (older name, still read by the art-direction capture tool).</summary>
        public const float TurretBarrelLength = GunMuzzleZ;

        /// <summary>Bolted base plate (fixed to the hood, root space: the plate top is y = 0). Gold bolts at level 20.</summary>
        public static Mesh GunBaseMesh(int tier)
        {
            return Cached("hoodmg_base1_" + tier, b =>
            {
                b.Material(0.45f, 0.6f);
                b.Lathe(new[] { new Vector2(0.126f, -0.05f), new Vector2(0.126f, -0.009f), new Vector2(0.117f, 0f), new Vector2(0f, 0f) }, 28, GunPlate);
                b.Material(0.85f, 1f);
                var bolt = tier >= 3 ? TurretAccent(3) : GunSteel;
                for (int i = 0; i < 6; i++)
                {
                    float a = (30f + i * 60f) * Mathf.Deg2Rad;
                    b.Cylinder(new Vector3(Mathf.Cos(a) * 0.104f, 0f, Mathf.Sin(a) * 0.104f), 0.011f, 0.009f, 6, bolt);
                }
                b.Matte();
            });
        }

        /// <summary>The turning part of the mount: a low turntable with a thin band in the tier color, the short upright
        /// yoke and the trunnion pin the gun pitches on.</summary>
        public static Mesh GunTurntableMesh(int tier)
        {
            var accent = TurretAccent(tier);
            return Cached("hoodmg_turn1_" + tier, b =>
            {
                b.Material(0.5f, 0.6f);
                b.Lathe(new[] { new Vector2(0.09f, 0f), new Vector2(0.09f, 0.03f), new Vector2(0.083f, 0.037f), new Vector2(0f, 0.037f) }, 24, GunMetal);
                b.Material(0.6f, 0.3f);
                b.Lathe(new[] { new Vector2(0.0925f, 0.009f), new Vector2(0.0925f, tier >= 2 ? 0.026f : 0.02f) }, 24, accent);
                b.Material(0.45f, 0.6f);
                b.BevelBox(new Vector3(0f, 0.075f, 0f), new Vector3(0.05f, 0.08f, 0.075f), 0.012f, GunMetal);
                b.BevelBox(new Vector3(0f, GunPivotY, 0f), new Vector3(0.05f, 0.042f, 0.056f), 0.016f, GunMetal);
                b.Material(0.85f, 1f);
                b.CylinderBetween(new Vector3(-0.043f, GunPivotY, 0f), new Vector3(0.043f, GunPivotY, 0f), 0.015f, 10, tier >= 3 ? accent : GunSteel);
                b.Matte();
            });
        }

        /// <summary>
        /// The light machine gun (pitch part, trunnion at the origin, +Z forward): a long low receiver with a flat feed
        /// cover, a small dark stock and pistol grip, the carry handle on top, a slim ventilated fore-end, a thin barrel
        /// with a gas tube and a small flash hider. Upgrades stay in the same silhouette: a slotted muzzle brake and
        /// light rivets (level 5), a ribbed heat shield and an ammo box (10), polished metal with gold trim (20).
        /// </summary>
        public static Mesh MachineGunMesh(int tier)
        {
            var accent = TurretAccent(tier);
            return Cached("hoodmg_gun1_" + tier, b =>
            {
                var metal = tier >= 3 ? Hex("#4C535A") : GunMetal;
                var steel = tier >= 3 ? accent : GunSteel;
                float gm = tier >= 3 ? 0.7f : 0.45f;
                const float by = GunBoreY;
                // receiver, feed cover, rear sight
                b.Material(gm, 0.6f);
                b.BevelBox(new Vector3(0f, 0.04f, 0.03f), new Vector3(0.072f, 0.095f, 0.3f), 0.014f, metal);
                b.BevelBox(new Vector3(0f, 0.094f, 0.005f), new Vector3(0.066f, 0.018f, 0.22f), 0.007f, Shade(metal, 1.18f));
                b.BevelBox(new Vector3(0f, 0.108f, -0.07f), new Vector3(0.022f, 0.016f, 0.03f), 0.005f, metal);
                // cradle cheeks round the yoke's pin
                b.BevelBox(new Vector3(0.034f, 0f, 0f), new Vector3(0.016f, 0.052f, 0.07f), 0.006f, metal);
                b.BevelBox(new Vector3(-0.034f, 0f, 0f), new Vector3(0.016f, 0.052f, 0.07f), 0.006f, metal);
                // small stock (tapers down to the butt), pistol grip, trigger guard: black polymer
                b.Material(0.25f, 0f);
                var stock = new[]
                {
                    new Vector2(-0.12f, 0.072f), new Vector2(-0.228f, 0.066f), new Vector2(-0.232f, -0.034f), new Vector2(-0.18f, -0.026f), new Vector2(-0.12f, 0.0f)
                };
                ExtrudeX(b, stock, 0.025f, GunPolymer);
                b.BevelBox(new Vector3(0f, 0.017f, GunButtZ + 0.008f), new Vector3(0.056f, 0.108f, 0.016f), 0.006f, Shade(GunPolymer, 0.8f));
                b.BevelBox(new Vector3(0f, -0.04f, -0.075f), new Vector3(0.032f, 0.07f, 0.042f), Quaternion.Euler(18f, 0f, 0f), 0.01f, GunPolymer);
                b.SharpBox(new Vector3(0f, -0.028f, -0.03f), new Vector3(0.01f, 0.006f, 0.052f), GunPolymer);
                // fore-end with ventilation slots and a thin tier band at its back
                b.Material(gm, 0.6f);
                b.BevelBox(new Vector3(0f, 0.022f, 0.27f), new Vector3(0.066f, 0.058f, 0.18f), 0.012f, metal);
                b.Material(0.1f, 0f);
                for (int s = -1; s <= 1; s += 2)
                    for (int row = 0; row < 2; row++)
                        for (int k = 0; k < 5; k++)
                            b.SharpBox(new Vector3(s * 0.0335f, 0.008f + row * 0.025f, 0.205f + k * 0.032f), new Vector3(0.003f, 0.011f, 0.017f), GunBore);
                b.Material(0.6f, 0.3f);
                b.BevelBox(new Vector3(0f, 0.022f, 0.185f), new Vector3(0.07f, 0.062f, tier >= 2 ? 0.02f : 0.012f), 0.004f, accent);
                // barrel, gas tube, front sight post
                b.Material(tier >= 3 ? 0.75f : 0.55f, 0.85f);
                b.CylinderBetween(new Vector3(0f, by, 0.17f), new Vector3(0f, by, GunMuzzleZ - 0.03f), 0.0135f, 10, GunBarrel);
                b.CylinderBetween(new Vector3(0f, 0.004f, 0.355f), new Vector3(0f, 0.004f, 0.45f), 0.008f, 8, GunBarrel);
                b.BevelBox(new Vector3(0f, 0.06f, 0.455f), new Vector3(0.012f, 0.036f, 0.016f), 0.004f, metal);
                if (tier >= 2)
                {
                    // ribbed heat shield over the barrel
                    b.Material(0.5f, 0.6f);
                    b.CylinderBetween(new Vector3(0f, by, 0.36f), new Vector3(0f, by, 0.44f), 0.02f, 12, metal);
                    b.Material(0.8f, 0.9f);
                    foreach (float z in new[] { 0.37f, 0.4f, 0.43f })
                        b.CylinderBetween(new Vector3(0f, by, z), new Vector3(0f, by, z + 0.008f), 0.0225f, 12, steel);
                    // ammo box on the left side
                    b.Material(0.3f, 0.2f);
                    b.BevelBox(new Vector3(-0.067f, 0.01f, 0.02f), new Vector3(0.05f, 0.075f, 0.1f), 0.01f, Hex("#55573F"));
                    b.SharpBox(new Vector3(-0.067f, 0.049f, 0.02f), new Vector3(0.03f, 0.006f, 0.05f), Shade(Hex("#55573F"), 0.7f));
                }
                // muzzle: a small flash hider (level 1), a slotted brake (5+)
                float mr = tier >= 1 ? 0.022f : 0.019f, ml = tier >= 1 ? 0.05f : 0.04f;
                b.Material(tier >= 1 ? 0.82f : 0.5f, tier >= 1 ? 1f : 0.6f);
                b.CylinderBetween(new Vector3(0f, by, GunMuzzleZ - ml), new Vector3(0f, by, GunMuzzleZ), mr, 12, tier >= 1 ? steel : metal);
                b.Material(0.1f, 0f);
                b.Push(new Vector3(0f, by, GunMuzzleZ + 0.001f), Quaternion.Euler(90f, 0f, 0f));
                b.Disc(Vector3.zero, mr * 0.5f, 10, GunBore);
                b.Pop();
                foreach (float s in new[] { -1f, 1f })
                    b.SharpBox(new Vector3(s * mr * 0.9f, by, GunMuzzleZ - ml * 0.5f), new Vector3(0.006f, mr * 0.9f, ml * 0.55f), GunBore);
                // carry handle: two light posts and a dark bar
                b.Material(0.85f, 1f);
                foreach (float z in new[] { 0.14f, 0.25f })
                    b.BevelBox(new Vector3(0f, 0.118f, z), new Vector3(0.012f, 0.04f, 0.014f), 0.003f, steel);
                b.Material(0.3f, 0f);
                b.CylinderBetween(new Vector3(0f, 0.142f, 0.12f), new Vector3(0f, 0.142f, 0.27f), 0.012f, 8, GunPolymer);
                if (tier >= 1)
                {
                    // light rivets along the receiver
                    b.Material(0.85f, 1f);
                    for (int s = -1; s <= 1; s += 2)
                        foreach (float z in new[] { -0.08f, 0.0f, 0.1f })
                            b.Sphere(new Vector3(s * 0.037f, 0.065f, z), Vector3.one * 0.006f, steel, 0);
                }
                b.Matte();
            });
        }

        /// <summary>A convex flat polygon given as (z, y) points, extruded across x (both sides + the rim): profiled parts
        /// like the stock.</summary>
        static void ExtrudeX(MeshBuilder b, Vector2[] zy, float halfW, Color c)
        {
            int n = zy.Length;
            var l = new Vector3[n]; var r = new Vector3[n];
            var mid = Vector3.zero;
            for (int i = 0; i < n; i++)
            {
                l[i] = new Vector3(-halfW, zy[i].y, zy[i].x);
                r[i] = new Vector3(halfW, zy[i].y, zy[i].x);
                mid += new Vector3(0f, zy[i].y, zy[i].x);
            }
            mid /= n;
            b.PolyOut(c, mid + Vector3.right, l);
            b.PolyOut(c, mid - Vector3.right, r);
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                b.PolyOut(c, mid, l[i], r[i], r[j], l[j]);
            }
        }

        /// <summary>Transforms and meshes of the hood machine gun as built on a car body (the game's Turret and the icon
        /// studio share it). gun = the recoiling part (child of the pitch pivot).</summary>
        public class HoodGunRig
        {
            public Transform root, yaw, pitch, gun, flash;
            public MeshFilter mount, turntable, gunMesh;
        }

        /// <summary>Builds the machine gun on a car body: the bolted plate on the hood, the turntable with its yoke (yaw),
        /// the pitch pivot and the gun ("Gun", with its "Flash" when a flash material is given). Aimed straight ahead.</summary>
        public static HoodGunRig HoodGun(Transform carBody, int tier, Material flashMat)
        {
            var r = new HoodGunRig();
            r.root = new GameObject("TurretBase").transform;
            r.root.SetParent(carBody, false);
            r.root.localPosition = GunMount;
            r.mount = MeshGO("HoodMount", GunBaseMesh(tier), Mats.Toon, r.root).GetComponent<MeshFilter>();
            r.yaw = new GameObject("TurretYaw").transform;
            r.yaw.SetParent(r.root, false);
            r.turntable = MeshGO("Turntable", GunTurntableMesh(tier), Mats.Toon, r.yaw).GetComponent<MeshFilter>();
            r.pitch = new GameObject("TurretPitch").transform;
            r.pitch.SetParent(r.yaw, false);
            r.pitch.localPosition = new Vector3(0f, GunPivotY, 0f);
            r.gun = new GameObject("Barrel0").transform;   // the recoiling gun (name kept for the art-direction capture tool)
            r.gun.SetParent(r.pitch, false);
            r.gunMesh = MeshGO("GunMesh", MachineGunMesh(tier), Mats.Toon, r.gun).GetComponent<MeshFilter>();
            if (flashMat != null)
            {
                var f = MeshGO("Flash", MgFlashMesh(), flashMat, r.gun, false);
                f.transform.localPosition = new Vector3(0f, GunBoreY, GunMuzzleZ + 0.004f);
                f.SetActive(false);
                r.flash = f.transform;
            }
            return r;
        }

        /// <summary>Small muzzle flash of the machine gun: a short four-pointed star along the bore and a little burst.</summary>
        public static Mesh MgFlashMesh()
        {
            return Cached("hoodmg_flash1", b =>
            {
                b.smoothAngle = 0f;
                var c = new Color(1f, 0.85f, 0.45f, 1f);
                for (int k = 0; k < 2; k++)
                {
                    b.Push(Vector3.zero, Quaternion.Euler(0, 0, 45f + k * 90f));
                    b.Poly(c, new Vector3(-0.022f, 0, 0), new Vector3(0, 0, 0.13f), new Vector3(0.022f, 0, 0), new Vector3(0, 0, -0.01f));
                    b.Poly(c, new Vector3(0, 0, -0.01f), new Vector3(0.022f, 0, 0), new Vector3(0, 0, 0.13f), new Vector3(-0.022f, 0, 0));
                    b.Pop();
                }
                for (int k = 0; k < 4; k++)
                {
                    b.Push(Vector3.zero, Quaternion.Euler(0, 0, k * 45f));
                    b.Poly(c, new Vector3(-0.03f, 0, 0.012f), new Vector3(0, 0, 0.04f), new Vector3(0.03f, 0, 0.012f), new Vector3(0, 0, 0.002f));
                    b.Poly(c, new Vector3(0, 0, 0.002f), new Vector3(0.03f, 0, 0.012f), new Vector3(0, 0, 0.04f), new Vector3(-0.03f, 0, 0.012f));
                    b.Pop();
                }
            });
        }

        /// <summary>Spent brass casing.</summary>
        public static Mesh CasingMesh()
        {
            return Cached("casing", b =>
            {
                b.Material(0.9f, 1f);
                b.Cylinder(new Vector3(0, -0.06f, 0), 0.026f, 0.12f, 6, Hex("#D8A23C"));
            });
        }
    }
}
