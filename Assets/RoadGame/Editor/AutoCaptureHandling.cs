using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.EventSystems;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Car handling through the real input path: synthetic touches on the HUD joystick -> Game.MoveInput -> CarDriver ->
    /// the vehicle simulation (no ScriptedInput, no autopilot). Straight reverse from four headings, braking into
    /// reverse, rear diagonals, backing off a wall, a slope, water, a landing, small deflections and release, focus loss /
    /// a menu / a second finger, 30/60 FPS x Dev 1x/4x, the rigid body and its suspension, wheel spin against motion,
    /// the car's materials from the game camera. Telemetry: handling_telemetry.csv (longitudinal speed, wheel angle,
    /// gear direction, heading change, pedals, body pitch / roll / heave per frame).
    /// Feel cases (feel_*) in the straight intro canyon log HANDLING_METRIC lines for before/after comparisons: launch and
    /// roll-out, step-and-back turns at 6 and 10 m/s, slaloms, small corrections, a nudge at top speed, release.
    /// Run: -captureScenario handling -captureTimes 260 [-handlingCases a,b,...] [-captureVideo a,b -captureFps 30]
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class HandlingReport
        {
            public bool editorMasterMuted;
            public string area;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> cases = new List<string>();
            public List<string> metrics = new List<string>();
        }

        struct HSample
        {
            public float t, u, steer, heading, throttle, brake, amount, pitch, roll, heave, stickLen;
            public int gear;
            public bool back, water, air;
            public Vector3 pos;
        }

        class HCase
        {
            public string name;
            public float secs;
            public Action<HCase, Player> setup;
            public Func<HCase, float, Player, Vector2?> stick;     // wanted stick in world XZ; null = finger up
            public Action<HCase, Player, float> custom;            // frame logic instead of the stick (finger tests)
            public Action<HCase, Player> finish;
            public int fps = 60;
            public float devSpeed = 1f;
            public readonly List<HSample> s = new List<HSample>();
            public Vector3 startPos;
            public float startYaw;
            public int landings0, recoveries0, gearChanges0;
            public readonly Dictionary<string, float> f = new Dictionary<string, float>();
            // wheel spin: summed measured roll (deg about the car's right axis) and the roll the ground speed asks for
            public readonly float[] spinMeasured = new float[4], spinExpected = new float[4];
            public float spinFrom = -1f, spinTo = -1f;
        }

        static HandlingReport hReport;
        static readonly List<HCase> hCases = new List<HCase>();
        static int hIndex = -1, hFrame = -1, hRecoveries;
        static float hT0;
        static bool hReady, hDone, hFingerDown;
        static Joystick hJoy;
        static Vector3 hC;
        static Vector2 hTouch = new Vector2(0f, 300f);     // joystick-local touch point of finger A
        const int FingerA = 3, FingerB = 7;
        static readonly Quaternion[] hWheelPrev = new Quaternion[4];
        static float hMaxScaleErr;
        static readonly StringBuilder hCsv = new StringBuilder();
        static readonly Dictionary<string, (Vector3 pos, float yaw)> hFpsEnds = new Dictionary<string, (Vector3, float)>();

        static void HandlingSetup(Progress p)
        {
            var d = p.d;
            d.maxHp = d.hp = 1e7; d.regen = 1e5; d.dmg[0] = 6; d.tutorialDone = true; d.introPending = false; d.unlockedZone = 3;
            Game.ScriptedInput = null;       // the real input path: HUD joystick -> Game.MoveInput
            Game.Autopilot = false;
            hReport = new HandlingReport();
            Player.CollisionProbe = null;
            hCases.Clear(); hIndex = -1; hReady = hDone = hFingerDown = false; hJoy = null; hMaxScaleErr = 0f; hRecoveries = 0;
            hCsv.Clear();
            hCsv.AppendLine("case,t,u,steer_deg,gear,heading_deg,dheading_deg,throttle,brake,stick_len,amount,backward,pitch_deg,roll_deg,heave_m,in_water,airborne,x,z");
            hFpsEnds.Clear();
        }

        static void HCheck(bool ok, string message)
        {
            if (ok) hReport.checks.Add(message); else hReport.failures.Add(message);
            Debug.Log("RoadGame HANDLING_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static void HMetric(string key, float v)
        {
            hReport.metrics.Add(key + "=" + F(v));
            Debug.Log("RoadGame HANDLING_METRIC " + key + "=" + F(v));
        }

        static string HArg(string key)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == key) return args[i + 1];
            return "";
        }

        /// <summary>A frame of the game camera (with the HUD) into the output folder.</summary>
        static void HShot(string label)
        {
            Game.I.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, label + ".png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            Debug.Log("RoadGame HANDLING_SHOT " + label);
        }

        static Vector2 HDir(float deg) => new Vector2(Mathf.Sin(deg * Mathf.Deg2Rad), Mathf.Cos(deg * Mathf.Deg2Rad));
        static Vector3 HFwd(float deg) => new Vector3(Mathf.Sin(deg * Mathf.Deg2Rad), 0f, Mathf.Cos(deg * Mathf.Deg2Rad));
        static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

        // ------------------------------------------------------------------ touches on the real joystick
        static Vector2 HJoyScreen(Vector2 jl)
        {
            var area = (RectTransform)hJoy.transform;
            var anchorRef = new Vector2((0.5f - area.pivot.x) * area.rect.width, (0f - area.pivot.y) * area.rect.height);
            var world = area.TransformPoint(jl + anchorRef);
            var canvas = hJoy.GetComponentInParent<Canvas>().rootCanvas;
            var cam = canvas.renderMode == RenderMode.ScreenSpaceOverlay ? null : canvas.worldCamera;
            return RectTransformUtility.WorldToScreenPoint(cam, world);
        }

        static PointerEventData HEv(int id, Vector2 jl) =>
            new PointerEventData(EventSystem.current) { pointerId = id, position = HJoyScreen(jl), button = PointerEventData.InputButton.Left };

        static void HDown(int id, Vector2 jl)
        {
            var e = HEv(id, jl);
            hJoy.OnPointerDown(e);
            hJoy.OnInitializePotentialDrag(e);
        }

        /// <summary>World stick -> finger A on the screen (camera yaw undone), or the finger lifts (null).</summary>
        static void HFinger(Vector2? world)
        {
            if (world == null)
            {
                if (hFingerDown) { hJoy.OnPointerUp(HEv(FingerA, hTouch)); hFingerDown = false; }
                return;
            }
            float yaw = Game.I.cam.transform.eulerAngles.y;
            var sv = Quaternion.Euler(0f, -yaw, 0f) * new Vector3(world.Value.x, 0f, world.Value.y);
            if (!hFingerDown) { HDown(FingerA, hTouch); hFingerDown = true; }
            hJoy.OnDrag(HEv(FingerA, hTouch + new Vector2(sv.x, sv.z) * Joystick.Radius));
        }

        // ------------------------------------------------------------------ test ground
        static readonly int[] hReject = new int[6];

        static bool HAreaOk(float x, float z, float half, float tol, float minNy, out float h0)
        {
            h0 = 0f;
            var g0 = Ground.Sample(x, z, 3f);
            if (!g0.valid || g0.h < -0.5f || g0.h > 1.5f) { hReject[0]++; return false; }
            h0 = g0.h;
            for (int i = -4; i <= 4; i++)
                for (int k = -4; k <= 4; k++)
                {
                    float px = x + i * half / 4f, pz = z + k * half / 4f;
                    var g = Ground.Sample(px, pz, h0 + 2f);
                    if (!g.valid || Mathf.Abs(g.h - h0) > tol || g.normal.y < minNy || (g.piece != null && g.piece.launch)) { hReject[1]++; return false; }
                    if (WaterPhysics.TryContact(new Vector3(px, g.h, pz), out _)) { hReject[2]++; return false; }
                    bool inside = DustFlatsSurfaces.Active ? DustFlatsSurfaces.ContainsBoundary(px, pz) : Mathf.Abs(px) < Content.ZoneHalfWidth - 6f;
                    if (!inside) { hReject[3]++; return false; }
                }
            if (Physics.CheckBox(new Vector3(x, h0 + 1.2f, z), new Vector3(half, 0.6f, half), Quaternion.identity, Player.ObstacleMask, QueryTriggerInteraction.Ignore)) { hReject[4]++; return false; }
            return true;
        }

        static bool HFindArea(out Vector3 c)
        {
            c = Vector3.zero;
            // the flattest clear square of open ground away from the camps; relaxed step by step on the bumpy flats
            var tries = new[] { (18f, 0.3f, 0.99f), (16f, 0.4f, 0.985f), (15f, 0.45f, 0.98f) };
            foreach (var (half, tol, ny) in tries)
            {
                float best = -1f;
                System.Array.Clear(hReject, 0, hReject.Length);
                for (float z = -110f; z <= 170f; z += 4f)
                    for (float x = -80f; x <= 80f; x += 4f)
                    {
                        if (Content.ZoneIndexAt(z) != 0 || !HAreaOk(x, z, half, tol, ny, out float h)) continue;
                        float clear = 200f;
                        foreach (var sp in World.I.zoneSpawns[0])
                        {
                            if (sp.spec.kind == TargetKind.Prop) continue;
                            var dd = sp.pos - new Vector3(x, h, z); dd.y = 0f;
                            clear = Mathf.Min(clear, dd.magnitude);
                        }
                        if (clear > best) { best = clear; c = new Vector3(x, h, z); }
                    }
                Debug.Log($"RoadGame HANDLING area search half={half} tol={tol} ny={ny}: rejects floor={hReject[0]} flat={hReject[1]} water={hReject[2]} bounds={hReject[3]} blocked={hReject[4]} props={hReject[5]} best={best:0}");
                if (best > 0f)
                {
                    hReport.area = $"{F(c.x)},{F(c.z)} ({half * 2f:0}x{half * 2f:0} m within {tol:0.00} m of level, dry, clear; nearest camp spawn {best:0} m)";
                    return true;
                }
            }
            return false;
        }

        // ------------------------------------------------------------------ the cases
        static bool HWants(string name)
        {
            var list = HArg("-handlingCases");
            if (string.IsNullOrEmpty(list)) return true;
            foreach (var n in list.Split(',')) if (name.StartsWith(n.Trim(), StringComparison.Ordinal)) return true;
            return false;
        }

        static void HAdd(HCase c) { if (HWants(c.name)) hCases.Add(c); }

        static void HBuildCases()
        {
            // 1) straight back from a standstill, four headings: >= 5 s of reverse, the wheel stays straight
            foreach (float h in new[] { 0f, 90f, 180f, 270f })
            {
                float yaw = h;
                HAdd(new HCase
                {
                    name = "reverse_straight_h" + (int)h, secs = 7.5f,
                    setup = (c, pl) => { pl.Teleport(hC + HFwd(yaw) * 12.5f, yaw); c.spinFrom = 2.2f; c.spinTo = 5.6f; },
                    stick = (c, t, pl) => t >= 0.4f && t < 5.55f ? HDir(yaw + 180f) : (Vector2?)null,
                    finish = HFinishStraightReverse,
                });
            }
            // 2) rolling forward fast, stick pulled behind: brake first, reverse near the stop, back up straight
            HAdd(new HCase
            {
                name = "brake_then_reverse", secs = 8.0f,
                setup = (c, pl) => { pl.Teleport(hC + HFwd(0f) * 2f, 0f); pl.SetSpeed(11f); },
                stick = (c, t, pl) => t < 5.8f ? HDir(180f) : (Vector2?)null,
                finish = HFinishBrakeReverse,
            });
            // 3) rear diagonals: back up while the tail swings towards the stick
            foreach (float side in new[] { 1f, -1f })
            {
                float s = side;
                HAdd(new HCase
                {
                    name = side > 0f ? "rear_diagonal_right" : "rear_diagonal_left", secs = 7.6f,
                    setup = (c, pl) => pl.Teleport(hC + HFwd(0f) * 8f, 0f),
                    stick = (c, t, pl) => t >= 0.3f && t < 6.5f ? HDir(135f * s) * 0.8f : (Vector2?)null,
                    finish = (c, pl) => HFinishDiagonal(c, pl, s),
                });
            }
            // 4) nose against the mesa wall, then back off it
            HAdd(new HCase
            {
                name = "wall_exit", secs = 8.4f,
                setup = (c, pl) =>
                {
                    pl.Teleport(new Vector3(-82f, 0f, 44f), 0f); pl.SetSpeed(5f);
                    bool wall = Physics.Raycast(pl.Pos + Vector3.up * 0.8f, Vector3.forward, out var hit, 30f, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                    c.f["wallDist"] = wall ? hit.distance : -1f;
                },
                stick = (c, t, pl) => t < 3.2f ? HDir(0f) : t < 7.4f ? HDir(180f) : (Vector2?)null,
                finish = HFinishWall,
            });
            // 5) a hill on the main road: hold on the slope, back down it, then drive up again
            HAdd(new HCase
            {
                name = "slope", secs = 10.5f,
                setup = HSetupSlope,
                stick = (c, t, pl) => t < 1.5f ? (Vector2?)null : t < 5f ? HDir(c.startYaw + 180f) : t < 9.2f ? HDir(c.startYaw) : (Vector2?)null,
                finish = HFinishSlope,
            });
            // 6) the river channel: straight back while the wheels are submerged
            HAdd(new HCase
            {
                name = "water_reverse", secs = 6.8f,
                setup = (c, pl) =>
                {
                    var along = new Vector3(-0.5684f, 0f, 0.8228f);
                    pl.Teleport(WaterChannel + along * 6f, Mathf.Atan2(along.x, along.z) * Mathf.Rad2Deg);
                },
                stick = (c, t, pl) => t >= 0.5f && t < 5.8f ? HDir(c.startYaw + 180f) : (Vector2?)null,
                finish = HFinishWater,
            });
            // 7) off the intro ramp; right after the touch-down the stick goes behind the car
            HAdd(new HCase
            {
                name = "landing_reverse", secs = 10f,
                setup = (c, pl) => { pl.Teleport(new Vector3(0f, 0f, -150f), 0f); pl.SetSpeed(11f); c.f["landedAt"] = -1f; c.f["tookOff"] = 0f; },
                stick = (c, t, pl) =>
                {
                    if (pl.Airborne) c.f["tookOff"] = 1f;
                    if (c.f["landedAt"] < 0f && c.f["tookOff"] > 0f && pl.Landings > c.landings0 && !pl.Airborne) c.f["landedAt"] = t;
                    float la = c.f["landedAt"];
                    if (la < 0f) return HDir(0f) * StickFilter.LengthForSpeed(11.5f);
                    return t < la + 0.15f ? HDir(0f) * StickFilter.LengthForSpeed(11.5f) : t < la + 5.2f ? HDir(180f) : (Vector2?)null;
                },
                finish = HFinishLanding,
            });
            // 8) a deflection inside the dead zone, a small one (creep), then the finger lifts
            HAdd(new HCase
            {
                name = "small_stick_release", secs = 7.6f,
                setup = (c, pl) => pl.Teleport(hC, 0f),
                stick = (c, t, pl) => t >= 0.3f && t < 2.3f ? HDir(0f) * 0.06f : t >= 2.3f && t < 5.3f ? HDir(0f) * 0.2f : (Vector2?)null,
                finish = HFinishSmall,
            });
            // 9) focus loss, a menu, a second finger
            HAdd(new HCase { name = "focus_menu_fingers", secs = 4.5f, setup = (c, pl) => { pl.Teleport(hC, 0f); c.f["step"] = 0f; }, custom = HFingersFrame, finish = HFinishFingers });
            // 10) the same manoeuvre at 30 / 60 FPS and Dev speed 1x / 4x
            foreach (var (fps, sp) in new[] { (60, 1f), (30, 1f), (60, 2f), (30, 2f), (60, 4f), (30, 4f) })
            {
                int fpsV = fps; float spV = sp;
                HAdd(new HCase
                {
                    name = $"rate_{fpsV}fps_{spV:0}x", secs = 8f, fps = fpsV, devSpeed = spV,
                    setup = (c, pl) => { pl.Teleport(hC - HFwd(0f) * 14f + HFwd(90f) * -6f, 0f); c.f["h4"] = -999f; if (fpsV == 60 && spV == 1f) { c.spinFrom = 0.8f; c.spinTo = 2.3f; } },
                    stick = (c, t, pl) =>
                    {
                        if (t < 2.4f) return HDir(0f);
                        if (t < 4f) return HDir(90f);
                        if (c.f["h4"] < -900f) c.f["h4"] = pl.Heading;
                        return t < 7.2f ? HDir(c.f["h4"] + 180f) : (Vector2?)null;
                    },
                    finish = HFinishRate,
                });
            }
            // 10a) feel: the same stick through the joystick on the straight intro canyon (flat road, walls at about
            // +-14 m, 100 m clear) for before/after comparisons (HANDLING_METRIC) and checks against the risks of a quicker
            // car: launch and roll-out, step-and-back turns, slaloms, small corrections, a nudge at top speed, release
            HAdd(new HCase
            {
                name = "feel_launch", secs = 7.5f,
                setup = (c, pl) => pl.Teleport(new Vector3(0f, 0f, -246f), 0f),
                stick = (c, t, pl) => t >= 0.3f && t < 4.3f ? HDir(0f) : (Vector2?)null,
                finish = HFinishLaunch,
            });
            foreach (var (nm, v, ang, x0) in new[] { ("feel_turn_low", 6f, 45f, -7f), ("feel_turn_mid", 10f, 35f, -9f) })
            {
                float vV = v, aV = ang, xV = x0;
                HAdd(new HCase
                {
                    name = nm, secs = 6.2f,
                    setup = (c, pl) => { pl.Teleport(new Vector3(xV, 0f, -246f), 0f); pl.SetSpeed(vV); },
                    stick = (c, t, pl) =>
                    {
                        float len = StickFilter.LengthForSpeed(vV);
                        if (t < 1f) return HDir(0f) * len;
                        if (t < 2.8f) return HDir(aV) * len;
                        if (t < 4.8f) return HDir(0f) * len;
                        return null;
                    },
                    finish = (c, pl) => HFinishTurn(c, pl, aV),
                });
            }
            foreach (var (nm, v) in new[] { ("feel_slalom_low", 6f), ("feel_slalom_mid", 9f) })
            {
                float vV = v;
                HAdd(new HCase
                {
                    name = nm, secs = 7.4f,
                    setup = (c, pl) => { pl.Teleport(new Vector3(0f, 0f, -248f), 0f); pl.SetSpeed(vV); },
                    stick = (c, t, pl) =>
                    {
                        float len = StickFilter.LengthForSpeed(vV);
                        if (t < 1f) return HDir(0f) * len;
                        if (t < 6.6f) return HDir(HSlalomDeg(t)) * len;
                        return null;
                    },
                    finish = HFinishSlalom,
                });
            }
            HAdd(new HCase
            {
                name = "feel_small_corrections", secs = 6.6f,
                setup = (c, pl) => { pl.Teleport(new Vector3(0f, 0f, -248f), 0f); pl.SetSpeed(7f); },
                stick = (c, t, pl) =>
                {
                    float len = StickFilter.LengthForSpeed(7f);
                    float a = t < 1f ? 0f : t < 2f ? 6f : t < 3f ? 0f : t < 4f ? -6f : 0f;
                    return t < 5.6f ? HDir(a) * len : (Vector2?)null;
                },
                finish = HFinishSmallCorrections,
            });
            HAdd(new HCase
            {
                name = "feel_top_speed", secs = 7.6f,
                setup = (c, pl) => { pl.Teleport(new Vector3(0f, 0f, -248f), 0f); pl.SetSpeed(13f); },
                stick = (c, t, pl) =>
                {
                    float a = t < 1.5f ? 0f : t < 2f ? 10f : t < 3.6f ? 0f : t < 4.1f ? -10f : 0f;
                    return t < 5.4f ? HDir(a) : (Vector2?)null;
                },
                finish = HFinishTopSpeed,
            });
            HAdd(new HCase
            {
                name = "feel_release", secs = 5f,
                setup = (c, pl) => { pl.Teleport(new Vector3(0f, 0f, -246f), 0f); pl.SetSpeed(10f); },
                stick = (c, t, pl) => t < 1.2f ? HDir(0f) * StickFilter.LengthForSpeed(10f) : (Vector2?)null,
                finish = HFinishRelease,
            });
            // 10b) ramps at speed: a kicker must launch the car, a big jump's landing must let it roll on
            foreach (var kn in new[] { "Kicker0a", "Kicker0b" })
            {
                var kp = Terrain.Kickers.Find(x => x.p.name == kn);
                if (kp == null) continue;
                var k = kp.p;
                HAdd(new HCase
                {
                    name = "ramp_" + kn, secs = 5.5f,
                    setup = (c, pl) => { pl.Teleport(k.rect.Center - k.rect.Forward * 16f, k.rect.Yaw); pl.SetSpeed(11f); c.f["caps"] = Player.ReboundCaps; },
                    stick = (c, t, pl) => t < 3f ? HDir(k.rect.Yaw) : (Vector2?)null,
                    finish = (c, pl) =>
                    {
                        // the bumper touches the kicker's low front block (KickerBack) on the way up - the old car did
                        // too; the ramp's boost still throws it off the lip at speed
                        bool flew = false; float takeoff = 0f; bool wasAir = false;
                        foreach (var s in c.s) { if (s.air && !wasAir) takeoff = s.u; if (s.air) flew = true; wasAir = s.air; }
                        var last = c.s[c.s.Count - 1];
                        HCheck(flew && takeoff > 9.5f && !last.air && pl.WheelsDown,
                            $"{c.name}: launches off the lip at {takeoff:0.0} m/s and lands on its wheels (wall caps {Player.ReboundCaps - c.f["caps"]:0})");
                    },
                });
            }
            {
                var bj = Terrain.BigJumps.Find(j => j.name == "BigJump0");
                if (bj != null)
                    HAdd(new HCase
                    {
                        name = "bigjump_rollout", secs = 6.5f,
                        setup = (c, pl) => { pl.Teleport(bj.lip - HFwd(bj.yaw) * (12f + bj.runUp), bj.yaw); pl.SetSpeed(13.6f); c.f["la"] = -1f; c.f["air"] = 0f; c.f["caps"] = Player.ReboundCaps; },
                        stick = (c, t, pl) =>
                        {
                            if (pl.Airborne) c.f["air"] = 1f;
                            if (c.f["la"] < 0f && c.f["air"] > 0f && !pl.Airborne) c.f["la"] = t;
                            return t < 4f ? HDir(bj.yaw) : (Vector2?)null;
                        },
                        finish = (c, pl) =>
                        {
                            float la = c.f["la"];
                            int i = HFirst(c, s => s.t >= la + 0.5f);
                            float u = i >= 0 ? c.s[i].u : 0f;
                            HCheck(la > 0f && u > 7f, $"bigjump_rollout: rolls on after the landing ({u:0.0} m/s half a second later; wall caps {Player.ReboundCaps - c.f["caps"]:0})");
                        },
                    });
            }
            // 11) scrap absorbed: the body settles on its springs and keeps its shape
            HAdd(new HCase
            {
                name = "absorb_rigid", secs = 2.4f,
                setup = (c, pl) => { pl.Teleport(hC, 0f); c.f["jolt"] = 0f; },
                custom = (c, pl, t) => { if (t >= 0.5f && c.f["jolt"] == 0f) { c.f["jolt"] = 1f; pl.AbsorbJolt(); } },
                finish = HFinishAbsorb,
            });
            // 12) the car's materials from the game camera (a normal and a closer zoom) and a low side view
            HAdd(new HCase
            {
                name = "materials", secs = 2.2f,
                setup = (c, pl) => { pl.Teleport(hC, 35f); c.f["shot"] = 0f; },
                custom = (c, pl, t) =>
                {
                    if (t >= 0.6f && c.f["shot"] == 0f) { c.f["shot"] = 1f; HShot("handling_car_game"); Game.I.cameraRig.zoom = 0.42f; }
                    if (t >= 1.5f && c.f["shot"] == 1f) { c.f["shot"] = 2f; HShot("handling_car_close"); HSideShot(pl, "handling_car_side"); Game.I.cameraRig.zoom = 1f; }
                },
                finish = (c, pl) => HCheck(c.f["shot"] >= 2f, "materials: game-camera frames of the car written (handling_car_game / _close / _side)"),
            });
        }

        // ------------------------------------------------------------------ frame loop
        static void HandlingTick(Player pl)
        {
            if (Time.frameCount == hFrame || hDone) return;
            hFrame = Time.frameCount;
            if (hJoy == null) hJoy = Game.I.hud != null ? Game.I.hud.joystick : null;
            if (hJoy == null || World.I == null) return;
            if (!hReady)
            {
                if (Game.I.SessionTime < 1.2f) return;
                hReady = true;
                hReport.editorMasterMuted = WorkAudioMute.Apply();
                HCheck(hReport.editorMasterMuted, "work run is muted");
                HCheck(Game.ScriptedInput == null && !Game.Autopilot, "input comes from the HUD joystick (no script, no autopilot)");
                if (!HFindArea(out hC)) { HCheck(false, "a flat clear test area exists"); hDone = true; return; }
                Debug.Log("RoadGame HANDLING area " + hReport.area);
                // props get their obstacle colliders only once the car is near, so the search above cannot see them:
                // the ones standing on the test ground are taken off it for the run (on the capture save only)
                int cleared = 0;
                foreach (var sp in World.I.zoneSpawns[0])
                {
                    if (sp.spec.kind != TargetKind.Prop || Mathf.Abs(sp.pos.x - hC.x) > 21f || Mathf.Abs(sp.pos.z - hC.z) > 21f) continue;
                    var sv = Game.I.progress.GetOrCreateSpawn(sp.id);
                    sv.respawnAt = Progress.NowMs + 3600000L;
                    sp.save = sv;
                    if (sp.target != null) { sp.target.gameObject.SetActive(false); World.I.activeTargets.Remove(sp.target); }
                    cleared++;
                }
                hReport.area += $"; {cleared} props cleared off it for the run";
                // the feel cases drive the straight intro canyon: nothing may stand on it
                int canyon = 0;
                foreach (var a in World.I.activeTargets.ToArray())
                    if (a != null && a.transform.position.z < Structures.IntroZoneZ && Mathf.Abs(a.transform.position.x) < 22f)
                    { a.gameObject.SetActive(false); World.I.activeTargets.Remove(a); canyon++; }
                Debug.Log($"RoadGame HANDLING intro canyon clear for the feel cases ({canyon} targets taken off it)");
                Debug.Log($"RoadGame HANDLING cleared {cleared} props off the test ground");
                // a still world around the test ground: the car's guns and harpoon stay quiet (they are tested elsewhere),
                // so nothing is shot, wrecked or reeled across the lanes
                if (pl.turret != null) pl.turret.enabled = false;
                if (pl.harpooner != null) pl.harpooner.enabled = false;
                foreach (var arm in pl.arms) if (arm != null) arm.enabled = false;
                Debug.Log($"RoadGame HANDLING wheel radii from the meshes FL={pl.WheelRadius(0):0.000} FR={pl.WheelRadius(1):0.000} RL={pl.WheelRadius(2):0.000} RR={pl.WheelRadius(3):0.000} " +
                          $"(old constants {Models.CarFrontWheelR:0.00} / {Models.CarRearWheelR:0.00})");
                pl.Recovered += () => hRecoveries++;
                HBuildCases();
                HStart(pl, 0);
                return;
            }
            var c = hCases[hIndex];
            float t = Game.I.SessionTime - hT0;
            if (t >= c.secs)
            {
                HFinger(null);
                c.finish?.Invoke(c, pl);
                HSummary(c);
                if (hIndex + 1 >= hCases.Count) { HEnd(); return; }
                HStart(pl, hIndex + 1);
                return;
            }
            if (c.custom != null) c.custom(c, pl, t);
            else HFinger(c.stick(c, t, pl));
            HRecord(c, pl, t);
            if (cfg.videoFrom >= 0f) HSideVideo(pl);
        }

        static void HStart(Player pl, int i)
        {
            hIndex = i;
            var c = hCases[i];
            HFinger(null);
            hJoy.Release();
            if (Mathf.Abs(DevOptions.Speed - c.devSpeed) > 0.01f) DevOptions.SetSpeed(c.devSpeed);
            Game.I.RefreshTimeScale();
            if (cfg.videoFrom < 0f) Time.captureFramerate = c.fps;
            c.setup(c, pl);
            Game.I.cameraRig.Snap();
            int logged = 0;
            Player.CollisionProbe = c.name.StartsWith("ramp_", StringComparison.Ordinal) || c.name.StartsWith("bigjump", StringComparison.Ordinal) || c.name == "wall_exit"
                ? (Action<Collision>)(col =>
                {
                    if (logged++ >= 24 || col.contactCount == 0) return;
                    var cp = col.GetContact(0);
                    Debug.Log($"RoadGame HANDLING contact case={c.name} t={Game.I.SessionTime - hT0:0.00} with={col.collider.name} layer={col.collider.gameObject.layer} " +
                              $"normal=({cp.normal.x:0.00},{cp.normal.y:0.00},{cp.normal.z:0.00}) rel={col.relativeVelocity.magnitude:0.0} at=({cp.point.x:0.0},{cp.point.y:0.00},{cp.point.z:0.0}) u={pl.ForwardSpeed:0.0}");
                })
                : null;
            c.startPos = pl.Pos;
            c.startYaw = pl.Heading;
            c.landings0 = pl.Landings;
            c.recoveries0 = hRecoveries;
            c.gearChanges0 = pl.GearChanges;
            for (int w = 0; w < 4 && w < pl.rig.wheels.Count; w++) hWheelPrev[w] = Quaternion.Inverse(pl.transform.rotation) * pl.rig.wheels[w].rotation;
            hT0 = Game.I.SessionTime;
            Debug.Log($"RoadGame HANDLING case={c.name} start={pl.Pos} yaw={pl.Heading:0} fps={(cfg.videoFrom < 0f ? c.fps : cfg.fps)} dev={DevOptions.Speed:0}x");
        }

        static void HEnd()
        {
            hDone = true;
            HFinger(null);
            if (DevOptions.Speed != 1f) DevOptions.SetSpeed(1f);
            Game.I.RefreshTimeScale();
            HCheck(hMaxScaleErr < 1e-4f, $"the body never changes its shape (max scale deviation {hMaxScaleErr:0.00000})");
            File.WriteAllText(Path.Combine(cfg.outDir, "handling_telemetry.csv"), hCsv.ToString());
            File.WriteAllText(Path.Combine(cfg.outDir, "handling-checks.json"), JsonUtility.ToJson(hReport, true));
            Debug.Log($"RoadGame HANDLING_RESULT checks={hReport.checks.Count + hReport.failures.Count} failures={hReport.failures.Count}");
        }

        static void HandlingFinish()
        {
            if (hReport == null) return;
            if (!hDone)
            {
                HCheck(false, $"all cases ran in the capture time (stopped in {(hIndex >= 0 && hIndex < hCases.Count ? hCases[hIndex].name : "-")})");
                HEnd();
            }
        }

        static void HRecord(HCase c, Player pl, float t)
        {
            var s = new HSample
            {
                t = t, u = pl.ForwardSpeed, steer = pl.SteerAngle, heading = pl.Heading, throttle = pl.Commands.throttle, brake = pl.Commands.brake,
                amount = pl.Intent.amount, back = pl.Intent.backward, pitch = pl.BodyPitchDeg, roll = pl.BodyRollDeg, heave = pl.BodyHeave,
                gear = (int)pl.GearDirection, water = pl.InWater, air = pl.Airborne, pos = pl.Pos, stickLen = Game.I.MoveInput.magnitude,
            };
            c.s.Add(s);
            var sc = pl.rig.body.localScale;
            hMaxScaleErr = Mathf.Max(hMaxScaleErr, Mathf.Abs(sc.x - 1f), Mathf.Abs(sc.y - 1f), Mathf.Abs(sc.z - 1f));
            // wheel spin about the car's right axis against the ground speed
            float dt = Time.deltaTime;
            for (int w = 0; w < 4 && w < pl.rig.wheels.Count; w++)
            {
                var q = Quaternion.Inverse(pl.transform.rotation) * pl.rig.wheels[w].rotation;
                var dq = q * Quaternion.Inverse(hWheelPrev[w]);
                hWheelPrev[w] = q;
                dq.ToAngleAxis(out float ang, out Vector3 axis);
                if (ang > 180f) ang -= 360f;
                if (c.spinFrom >= 0f && t >= c.spinFrom && t <= c.spinTo && !float.IsNaN(axis.x))
                {
                    c.spinMeasured[w] += ang * axis.x;
                    c.spinExpected[w] += pl.ForwardSpeed * dt / pl.WheelRadius(w) * Mathf.Rad2Deg;
                }
            }
            float dh = Mathf.DeltaAngle(c.startYaw, s.heading);
            hCsv.Append(c.name).Append(',').Append(F(t)).Append(',').Append(F(s.u)).Append(',').Append(F(s.steer)).Append(',').Append(s.gear).Append(',')
                .Append(F(s.heading)).Append(',').Append(F(dh)).Append(',').Append(F(s.throttle)).Append(',').Append(F(s.brake)).Append(',')
                .Append(F(s.stickLen)).Append(',').Append(F(s.amount)).Append(',').Append(s.back ? 1 : 0).Append(',').Append(F(s.pitch)).Append(',')
                .Append(F(s.roll)).Append(',').Append(F(s.heave)).Append(',').Append(s.water ? 1 : 0).Append(',').Append(s.air ? 1 : 0).Append(',')
                .Append(F(s.pos.x)).Append(',').Append(F(s.pos.z)).AppendLine();
        }

        static void HSummary(HCase c)
        {
            if (c.s.Count == 0) return;
            float minU = float.MaxValue, maxU = float.MinValue, maxSteer = 0f, minPitch = 0f, maxPitch = 0f, maxRoll = 0f, minHeave = 0f;
            foreach (var s in c.s)
            {
                minU = Mathf.Min(minU, s.u); maxU = Mathf.Max(maxU, s.u); maxSteer = Mathf.Max(maxSteer, Mathf.Abs(s.steer));
                minPitch = Mathf.Min(minPitch, s.pitch); maxPitch = Mathf.Max(maxPitch, s.pitch); maxRoll = Mathf.Max(maxRoll, Mathf.Abs(s.roll)); minHeave = Mathf.Min(minHeave, s.heave);
            }
            var last = c.s[c.s.Count - 1];
            string line = $"{c.name}: u {minU:0.0}..{maxU:0.0} m/s, |steer| max {maxSteer:0.0} deg, heading change {Mathf.DeltaAngle(c.startYaw, last.heading):0.0} deg, " +
                          $"pitch {minPitch:0.00}..{maxPitch:0.00} deg, |roll| max {maxRoll:0.00} deg, heave min {minHeave * 100f:0.0} cm, gear changes {Game.I.player.GearChanges - c.gearChanges0}";
            hReport.cases.Add(line);
            Debug.Log("RoadGame HANDLING " + line);
        }

        // ------------------------------------------------------------------ checks
        static int HFirst(HCase c, Func<HSample, bool> p, float from = 0f)
        {
            for (int i = 0; i < c.s.Count; i++) if (c.s[i].t >= from && p(c.s[i])) return i;
            return -1;
        }

        static void HWheelCheck(HCase c, string what, float sign)
        {
            for (int w = 0; w < 4; w++)
            {
                float m = c.spinMeasured[w], e = c.spinExpected[w];
                float ratio = Mathf.Abs(e) > 1f ? m / e : 0f;
                bool rear = w >= 2;
                bool ok = Mathf.Sign(m) == sign && Mathf.Sign(e) == sign && ratio > (rear ? 0.8f : 0.9f) && ratio < (rear ? 1.45f : 1.1f);
                HCheck(ok, $"{what}: wheel {(new[] { "FL", "FR", "RL", "RR" })[w]} rolls {(sign > 0 ? "forward" : "backward")} with the car (turned {m:0} deg, ground asks {e:0} deg, ratio {ratio:0.00})");
            }
        }

        static void HFinishStraightReverse(HCase c, Player pl)
        {
            int eng = HFirst(c, s => s.gear < 0);
            float engT = eng >= 0 ? c.s[eng].t : 99f;
            HCheck(eng >= 0 && engT <= 1.0f, $"{c.name}: reverse goes in {engT - 0.4f:0.00} s after the stick is pulled straight back");
            int flick = 0; float maxSteer = 0f, sumSteer = 0f; int n = 0; float meanU = 0f; int nu = 0;
            for (int i = Mathf.Max(0, eng); i < c.s.Count; i++)
            {
                var s = c.s[i];
                if (s.t > 5.55f) break;
                if (s.gear > 0) flick++;
                if (s.t >= 1.0f) { maxSteer = Mathf.Max(maxSteer, Mathf.Abs(s.steer)); sumSteer += Mathf.Abs(s.steer); n++; }
                if (s.t >= 3f) { meanU += s.u; nu++; }
            }
            meanU = nu > 0 ? meanU / nu : 0f;
            float held = eng >= 0 ? 5.55f - engT : 0f;
            HCheck(eng >= 0 && flick == 0 && held >= 5f, $"{c.name}: reverse holds {held:0.0} s while the stick stays back (no drop-out, no gear flicker)");
            HCheck(meanU < -0.85f * CarTuning.ReverseTopSpeed && meanU > -1.1f * CarTuning.ReverseTopSpeed, $"{c.name}: backs up at {-meanU:0.00} m/s (reverse top speed {CarTuning.ReverseTopSpeed})");
            HCheck(maxSteer <= 3f && (n == 0 || sumSteer / n <= 1f), $"{c.name}: the wheel stays straight (|steer| max {maxSteer:0.00} deg, mean {(n > 0 ? sumSteer / n : 0f):0.00} deg)");
            int iRel = HFirst(c, s => s.t >= 5.55f);
            float dh = iRel > 0 ? Mathf.Abs(Mathf.DeltaAngle(c.startYaw, c.s[iRel].heading)) : 999f;
            HCheck(dh <= 4f, $"{c.name}: no turning round: heading changes {dh:0.00} deg in {held:0.0} s of straight reverse");
            var disp = (iRel > 0 ? c.s[iRel].pos : pl.Pos) - c.startPos; disp.y = 0f;
            var back = -HFwd(c.startYaw);
            float along = Vector3.Dot(disp, back), side = Vector3.Cross(back, disp).y;
            HCheck(along > 16f && Mathf.Abs(side) < 1.5f, $"{c.name}: travels straight back {along:0.0} m (sideways {side:0.00} m)");
            var last = c.s[c.s.Count - 1];
            HCheck(Mathf.Abs(last.u) < 0.3f, $"{c.name}: finger up: the car stops and holds ({last.u:0.00} m/s after {c.secs - 5.55f:0.0} s)");
            if (c.name.EndsWith("_h0")) HWheelCheck(c, "reverse", -1f);
        }

        static void HFinishBrakeReverse(HCase c, Player pl)
        {
            int stop = HFirst(c, s => s.u <= CarDriver.ShiftSpeed);
            int eng = HFirst(c, s => s.gear < 0);
            bool noEarly = true;
            foreach (var s in c.s) if (s.gear < 0 && s.u > CarDriver.ShiftSpeed + 0.05f) noEarly = false;
            float stopT = stop >= 0 ? c.s[stop].t : 99f, engT = eng >= 0 ? c.s[eng].t : 99f;
            HCheck(stop >= 0 && stopT <= 2.4f, $"brake_then_reverse: brakes from 11 m/s to a stop in {stopT:0.00} s (stays in forward gear meanwhile: {noEarly})");
            HCheck(noEarly && eng >= 0 && engT - stopT <= 0.4f && engT >= stopT, $"brake_then_reverse: reverse goes in only at the stop ({engT:0.00} s), never while rolling forward");
            int i10 = HFirst(c, s => s.u <= 10f), i2 = HFirst(c, s => s.u <= 2f);
            float decel = i10 >= 0 && i2 > i10 ? (c.s[i10].u - c.s[i2].u) / Mathf.Max(0.01f, c.s[i2].t - c.s[i10].t) : 0f;
            HCheck(decel > 5f && decel < 10.5f, $"brake_then_reverse: firm, progressive braking {decel:0.0} m/s^2 (10 -> 2 m/s)");
            int r25 = HFirst(c, s => s.t >= engT + 2.5f);
            float uR = r25 >= 0 ? c.s[r25].u : 0f;
            HCheck(uR < -3.5f, $"brake_then_reverse: then backs up ({-uR:0.0} m/s 2.5 s after the reverse went in)");
            float maxDh = 0f;
            foreach (var s in c.s) if (s.t <= 5.8f) maxDh = Mathf.Max(maxDh, Mathf.Abs(Mathf.DeltaAngle(c.startYaw, s.heading)));
            HCheck(maxDh <= 6f, $"brake_then_reverse: no U-turn: heading stays within {maxDh:0.0} deg");
            HCheck(pl.GearChanges - c.gearChanges0 == 1, $"brake_then_reverse: one gear change forward -> reverse ({pl.GearChanges - c.gearChanges0})");
            float dive = 0f;
            foreach (var s in c.s) if (s.t <= stopT) dive = Mathf.Min(dive, s.pitch);
            HCheck(dive < -0.8f && dive > -3.5f, $"brake_then_reverse: moderate nose dive under the brakes ({dive:0.00} deg)");
        }

        static void HFinishDiagonal(HCase c, Player pl, float side)
        {
            int eng = HFirst(c, s => s.gear < 0);
            float engT = eng >= 0 ? c.s[eng].t : 99f;
            HCheck(eng >= 0 && engT <= 1.0f, $"{c.name}: reverse goes in ({engT - 0.3f:0.00} s)");
            bool forward = false;
            foreach (var s in c.s) if (s.t > engT + 0.3f && s.t < 6.5f && s.u > 0.3f) forward = true;
            HCheck(!forward, $"{c.name}: keeps backing up, never drives forward");
            float early = 0f;
            foreach (var s in c.s) if (s.t >= engT && s.t <= engT + 0.8f) early = s.steer;
            // backing up, a wheel turned right swings the tail left (counter-clockwise from above), so a rear-right
            // stick (+135) asks for a right wheel at first; the measured heading must then turn counter-clockwise
            HCheck(Mathf.Sign(early) == Mathf.Sign(side) && Mathf.Abs(early) > 15f, $"{c.name}: steering sign on the real physics: wheel {early:0.0} deg");
            int iEnd = HFirst(c, s => s.t >= 6.4f);
            var e = iEnd >= 0 ? c.s[iEnd] : c.s[c.s.Count - 1];
            float dh = Mathf.DeltaAngle(c.startYaw, e.heading);
            HCheck(Mathf.Sign(dh) == -Mathf.Sign(side) && Mathf.Abs(dh) > 30f && Mathf.Abs(dh) < 62f,
                $"{c.name}: the tail swings towards the stick: heading {dh:0.0} deg (the stick is 45 deg off the tail)");
            int iPrev = HFirst(c, s => s.t >= 5.9f);
            var travel = iPrev >= 0 ? e.pos - c.s[iPrev].pos : Vector3.zero; travel.y = 0f;
            float want = c.startYaw + 135f * side;
            float travelDeg = Mathf.Atan2(travel.x, travel.z) * Mathf.Rad2Deg;
            float off = Mathf.Abs(Mathf.DeltaAngle(want, travelDeg));
            HCheck(travel.magnitude > 0.5f && off < 20f, $"{c.name}: ends up travelling along the stick ({off:0.0} deg off)");
            HCheck(Mathf.Abs(e.steer) < 10f, $"{c.name}: the wheel comes back as the tail lines up ({e.steer:0.0} deg)");
        }

        static void HFinishWall(HCase c, Player pl)
        {
            float wallDist = c.f["wallDist"];
            HCheck(wallDist > 0f && wallDist < 25f, $"wall_exit: the mesa wall is ahead ({wallDist:0.0} m)");
            int a = HFirst(c, s => s.t >= 2.2f), b = HFirst(c, s => s.t >= 3.1f);
            float push = a >= 0 && b >= 0 ? Vector3.Distance(c.s[a].pos, c.s[b].pos) : 99f;
            float uPush = b >= 0 ? c.s[b].u : 99f;
            HCheck(push < 0.8f && Mathf.Abs(uPush) < 1.2f, $"wall_exit: pinned against the wall (moved {push:0.00} m in the last second, {uPush:0.00} m/s)");
            int eng = HFirst(c, s => s.gear < 0, 3.2f);
            float engT = eng >= 0 ? c.s[eng].t - 3.2f : 99f;
            HCheck(eng >= 0 && engT <= 1.0f, $"wall_exit: reverse goes in {engT:0.00} s after the stick goes back");
            int iEnd = HFirst(c, s => s.t >= 7.35f);
            var pinned = b >= 0 ? c.s[b].pos : c.startPos;
            var endPos = iEnd >= 0 ? c.s[iEnd].pos : pl.Pos;
            float away = Vector3.Dot(endPos - pinned, -HFwd(c.startYaw));
            float dh = Mathf.Abs(Mathf.DeltaAngle(b >= 0 ? c.s[b].heading : c.startYaw, iEnd >= 0 ? c.s[iEnd].heading : pl.Heading));
            HCheck(away > 6f && dh < 10f, $"wall_exit: backs calmly off the wall: {away:0.0} m straight back, heading change {dh:0.0} deg");
            HCheck(hRecoveries == c.recoveries0 && pl.WheelsDown, "wall_exit: stays on its wheels, no recovery teleport");
        }

        static void HSetupSlope(HCase c, Player pl)
        {
            var rh = Terrain.Hills.Find(h => h.p.name == "RoadHill0a").p;
            Vector3 best = rh.rect.Center; float bestN = 1f;
            for (float d = 4f; d <= 16f; d += 1f)
            {
                var p = rh.rect.Center - rh.rect.Forward * d;
                var g = Ground.Sample(p.x, p.z, 30f);
                if (g.valid && g.normal.y < bestN) { bestN = g.normal.y; best = new Vector3(p.x, g.h, p.z); }
            }
            c.f["slopeDeg"] = Mathf.Acos(Mathf.Clamp01(bestN)) * Mathf.Rad2Deg;
            pl.Teleport(best, rh.rect.Yaw);
        }

        static void HFinishSlope(HCase c, Player pl)
        {
            HCheck(c.f["slopeDeg"] > 3f, $"slope: the car stands on a {c.f["slopeDeg"]:0.0} deg slope of the road hill, nose uphill");
            int h = HFirst(c, s => s.t >= 1.45f);
            float drift = h >= 0 ? Vector3.Distance(c.s[h].pos, c.startPos) : 99f;
            HCheck(h >= 0 && drift < 0.5f && Mathf.Abs(c.s[h].u) < 0.3f, $"slope: hands off, the car holds on the slope (drift {drift:0.00} m)");
            int eng = HFirst(c, s => s.gear < 0, 1.5f);
            float maxBack = 0f, maxDh = 0f;
            foreach (var s in c.s)
                if (s.t >= 1.5f && s.t < 5f) { maxBack = Mathf.Max(maxBack, -s.u); maxDh = Mathf.Max(maxDh, Mathf.Abs(Mathf.DeltaAngle(c.startYaw, s.heading))); }
            HCheck(eng >= 0 && c.s[eng].t < 2.6f, "slope: reverse goes in on the slope");
            HCheck(maxBack > 2f && maxBack < CarTuning.ReverseTopSpeed + 1.2f, $"slope: backs down under control (max {maxBack:0.0} m/s)");
            HCheck(maxDh < 10f, $"slope: straight down the hill (heading within {maxDh:0.0} deg)");
            int fw = HFirst(c, s => s.gear > 0, 5f);
            int iEnd = HFirst(c, s => s.t >= 9.1f);
            float uEnd = iEnd >= 0 ? c.s[iEnd].u : 0f;
            bool noEarly = true;
            foreach (var s in c.s) if (s.t >= 5f && s.gear > 0 && s.u < -CarDriver.ShiftSpeed - 0.05f) noEarly = false;
            HCheck(fw >= 0 && noEarly && uEnd > 1f, $"slope: stick ahead again: brakes, forward gear at the stop, drives up the hill ({uEnd:0.0} m/s)");
        }

        static void HFinishWater(HCase c, Player pl)
        {
            int wet = 0, n = 0; float maxBack = 0f, maxDh = 0f;
            foreach (var s in c.s)
            {
                if (s.t < 0.5f || s.t > 5.8f) continue;
                n++; if (s.water) wet++;
                maxBack = Mathf.Max(maxBack, -s.u);
                maxDh = Mathf.Max(maxDh, Mathf.Abs(Mathf.DeltaAngle(c.startYaw, s.heading)));
            }
            int eng = HFirst(c, s => s.gear < 0);
            HCheck(n > 0 && wet > n / 2, $"water_reverse: the wheels are in the river ({wet}/{n} frames wet)");
            HCheck(eng >= 0 && c.s[eng].t < 1.7f && maxBack > 0.8f, $"water_reverse: reverse goes in and backs up through the water ({maxBack:0.0} m/s)");
            HCheck(maxDh < 12f, $"water_reverse: stays straight in the current (heading within {maxDh:0.0} deg)");
            HCheck(hRecoveries == c.recoveries0, "water_reverse: no recovery teleport");
        }

        static void HFinishLanding(HCase c, Player pl)
        {
            float la = c.f["landedAt"];
            HCheck(c.f["tookOff"] > 0f && la > 0f, $"landing_reverse: off the ramp and down again (touch-down at {la:0.00} s)");
            if (la <= 0f) return;
            bool noEarly = true; int eng = -1;
            for (int i = 0; i < c.s.Count; i++)
            {
                var s = c.s[i];
                if (s.t < la) continue;
                if (s.gear < 0 && s.u > CarDriver.ShiftSpeed + 0.05f) noEarly = false;
                if (eng < 0 && s.gear < 0) eng = i;
            }
            HCheck(noEarly && eng >= 0, $"landing_reverse: after the touch-down it brakes, reverse only at the stop ({(eng >= 0 ? c.s[eng].t - la : -1f):0.00} s)");
            float minU = 0f, maxDh = 0f;
            float h0 = 0f;
            int il = HFirst(c, s => s.t >= la);
            if (il >= 0) h0 = c.s[il].heading;
            foreach (var s in c.s) if (s.t >= la && s.t < la + 5.2f) { minU = Mathf.Min(minU, s.u); maxDh = Mathf.Max(maxDh, Mathf.Abs(Mathf.DeltaAngle(h0, s.heading))); }
            HCheck(minU < -2f && maxDh < 12f, $"landing_reverse: backs up straight after the landing ({-minU:0.0} m/s, heading within {maxDh:0.0} deg)");
            // the springs: one compression, a small rebound, settled
            float minHeave = 0f; int crossings = 0; float prev = 0f; float settleAt = -1f;
            foreach (var s in c.s)
            {
                if (s.t < la || s.t > la + 1.5f) continue;
                minHeave = Mathf.Min(minHeave, s.heave);
                if (prev != 0f && Mathf.Sign(prev) != Mathf.Sign(s.heave) && Mathf.Abs(s.heave) > 0.002f) crossings++;
                if (Mathf.Abs(s.heave) > 0.002f) prev = s.heave;
                if (Mathf.Abs(s.heave) > 0.008f) settleAt = s.t - la;
            }
            HCheck(minHeave < -0.015f && minHeave > -0.08f, $"landing_reverse: the suspension takes the landing ({minHeave * 100f:0.0} cm)");
            HCheck(settleAt < 0.9f && crossings <= 2, $"landing_reverse: short, damped response (settled after {settleAt:0.00} s, {crossings} swings)");
        }

        static void HFinishSmall(HCase c, Player pl)
        {
            float maxU = 0f; bool throttle = false, amount = false;
            foreach (var s in c.s) if (s.t >= 0.4f && s.t < 2.3f) { maxU = Mathf.Max(maxU, Mathf.Abs(s.u)); if (s.throttle > 0.001f) throttle = true; if (s.amount > 0f) amount = true; }
            HCheck(maxU < 0.05f && !throttle && !amount, $"small_stick_release: a 6% deflection is inside the dead zone (no throttle, {maxU:0.000} m/s)");
            float mean = 0f; int n = 0;
            foreach (var s in c.s) if (s.t >= 3.6f && s.t < 5.3f) { mean += s.u; n++; }
            mean = n > 0 ? mean / n : 0f;
            HCheck(mean > 0.8f && mean < 2.6f, $"small_stick_release: a 20% deflection creeps forward ({mean:0.00} m/s)");
            int rel = HFirst(c, s => s.t >= 5.35f);
            HCheck(rel >= 0 && c.s[rel].stickLen < 1e-4f && !hJoy.Active && hJoy.Value == Vector2.zero, "small_stick_release: finger up: the stick reads zero at once");
            int stop = HFirst(c, s => s.t >= 5.3f && Mathf.Abs(s.u) < 0.3f);
            HCheck(stop >= 0 && c.s[stop].t - 5.3f < 1.5f, $"small_stick_release: the car stops after the release ({(stop >= 0 ? c.s[stop].t - 5.3f : -1f):0.00} s)");
        }

        // focus loss, a menu, a second finger (frames: the menu pauses the game time)
        static int hFingerFrame;
        static Vector2 hValueA;

        static void HFingersFrame(HCase c, Player pl, float t)
        {
            int step = (int)c.f["step"];
            switch (step)
            {
                case 0:
                    if (t < 0.3f) return;
                    HFinger(HDir(0f) * 0.8f); c.f["step"] = 1; return;
                case 1:
                    if (t < 1.0f) { HFinger(HDir(0f) * 0.8f); return; }
                    bool wasActive = hJoy.Active && Mathf.Abs(hJoy.Value.magnitude - 0.8f) < 0.02f;
                    int forced0 = hJoy.ForcedReleases;
                    hJoy.SendMessage("OnApplicationFocus", false, SendMessageOptions.DontRequireReceiver);
                    hFingerDown = false;
                    HCheck(wasActive && !hJoy.Active && hJoy.Value == Vector2.zero && Game.I.MoveInput == Vector2.zero && hJoy.ForcedReleases == forced0 + 1,
                        "focus_menu_fingers: losing the app focus lets go of the stick");
                    c.f["step"] = 2; return;
                case 2:
                    if (t < 1.3f) return;
                    HFinger(HDir(0f) * 0.8f); c.f["step"] = 3; return;
                case 3:
                    if (t < 2.0f) { HFinger(HDir(0f) * 0.8f); return; }
                    Game.I.hud.panels.ShowSettings();
                    hFingerFrame = Time.frameCount; c.f["step"] = 4; return;
                case 4:
                    if (Time.frameCount < hFingerFrame + 8) return;
                    HCheck(Game.I.paused && !hJoy.Active && hJoy.Value == Vector2.zero && Game.I.MoveInput == Vector2.zero,
                        "focus_menu_fingers: opening a menu lets go of the stick (paused, no input)");
                    Game.I.hud.panels.Close();
                    hFingerDown = false;
                    hFingerFrame = Time.frameCount; c.f["step"] = 5; return;
                case 5:
                    if (Time.frameCount < hFingerFrame + 3) return;
                    HCheck(!Game.I.paused && !hJoy.Active && Game.I.MoveInput == Vector2.zero, "focus_menu_fingers: after the menu closes there is no stale input");
                    HFinger(HDir(0f) * 0.6f);
                    hValueA = hJoy.Value;
                    c.f["step"] = 6; c.f["t6"] = t; return;
                case 6:
                    if (t < c.f["t6"] + 0.3f) { HFinger(HDir(0f) * 0.6f); return; }
                    var bAt = new Vector2(-220f, 520f);
                    HDown(FingerB, bAt);
                    hJoy.OnDrag(HEv(FingerB, bAt + new Vector2(90f, -60f)));
                    bool kept = hJoy.Active && hJoy.PointerId == FingerA && (hJoy.Value - hValueA).magnitude < 0.01f;
                    hJoy.OnPointerUp(HEv(FingerB, bAt));
                    bool still = hJoy.Active && hJoy.PointerId == FingerA && (hJoy.Value - hValueA).magnitude < 0.01f;
                    HCheck(kept && still, "focus_menu_fingers: a second finger on the stick area does not take it over");
                    HFinger(null);
                    HCheck(!hJoy.Active && hJoy.Value == Vector2.zero, "focus_menu_fingers: finger A up lets go");
                    c.f["step"] = 7; return;
            }
        }

        static void HFinishFingers(HCase c, Player pl) => HCheck(c.f["step"] >= 7f, "focus_menu_fingers: all finger steps ran");

        static void HFinishRate(HCase c, Player pl)
        {
            var last = c.s[c.s.Count - 1];
            var rel = last.pos - c.startPos; rel.y = 0f;
            hFpsEnds[c.name] = (rel, Mathf.DeltaAngle(c.startYaw, last.heading));
            bool finite = true; float maxPitch = 0f, maxRoll = 0f;
            foreach (var s in c.s)
            {
                if (float.IsNaN(s.u) || float.IsNaN(s.pos.x) || float.IsNaN(s.pitch)) finite = false;
                maxPitch = Mathf.Max(maxPitch, Mathf.Abs(s.pitch)); maxRoll = Mathf.Max(maxRoll, Mathf.Abs(s.roll));
            }
            int eng = HFirst(c, s => s.gear < 0, 4f);
            HCheck(finite && eng >= 0 && maxPitch < 3.6f && maxRoll < 3.6f,
                $"{c.name}: stable (reverse at {(eng >= 0 ? c.s[eng].t : -1f):0.0} s, |pitch| max {maxPitch:0.00}, |roll| max {maxRoll:0.00} deg)");
            if (c.spinFrom >= 0f) HWheelCheck(c, "forward", 1f);
            if (c.name == "rate_60fps_1x")
            {
                // the 60 FPS 1x run: squat on the throttle, a limited lean in the right turn
                float squat = 0f, lean = 0f;
                foreach (var s in c.s) { if (s.t < 2.4f) squat = Mathf.Max(squat, s.pitch); if (s.t >= 2.4f && s.t < 4f) lean = Mathf.Min(lean, s.roll); }
                HCheck(squat > 0.3f && squat < 2.2f, $"suspension: squat under full throttle {squat:0.00} deg (nose up, smaller than the brake dive)");
                HCheck(lean < -0.8f && lean > -3.2f, $"suspension: body lean in the hard right turn {lean:0.00} deg (left side down, limited)");
            }
            if (hFpsEnds.ContainsKey("rate_60fps_1x") && c.name != "rate_60fps_1x")
            {
                var r = hFpsEnds["rate_60fps_1x"];
                float dp = Vector3.Distance(r.pos, rel), dh = Mathf.Abs(Mathf.DeltaAngle(r.yaw, Mathf.DeltaAngle(c.startYaw, last.heading)));
                HCheck(dp < 1.5f && dh < 5f, $"{c.name}: the same path as 60 FPS 1x (end {dp:0.00} m and {dh:0.0} deg apart)");
            }
        }

        // ------------------------------------------------------------------ feel cases (metrics + risk checks)
        static float HRel(HCase c, HSample s) => Mathf.DeltaAngle(c.startYaw, s.heading);

        static float HYawRate(HCase c, int i)
        {
            if (i <= 0 || i >= c.s.Count) return 0f;
            float dt = c.s[i].t - c.s[i - 1].t;
            return dt > 1e-4f ? Mathf.DeltaAngle(c.s[i - 1].heading, c.s[i].heading) / dt : 0f;
        }

        static void HFinishLaunch(HCase c, Player pl)
        {
            const float t0 = 0.3f, tRel = 4.3f;
            float T(float v) { int i = HFirst(c, s => s.t >= t0 && s.u >= v); return i >= 0 ? c.s[i].t - t0 : 99f; }
            int th = HFirst(c, s => s.t >= t0 && s.throttle >= 0.9f);
            float thT = th >= 0 ? c.s[th].t - t0 : 99f;
            int i2 = HFirst(c, s => s.t >= t0 + 2f);
            float d2 = i2 >= 0 ? Vector3.Distance(c.s[i2].pos, c.startPos) : 0f;
            int iRel = HFirst(c, s => s.t >= tRel);
            float uRel = iRel >= 0 ? c.s[iRel].u : 0f;
            int stop = HFirst(c, s => s.t >= tRel && Mathf.Abs(s.u) < 0.3f);
            float stopT = stop >= 0 ? c.s[stop].t - tRel : 99f;
            float coast = stop >= 0 && iRel >= 0 ? Vector3.Distance(c.s[stop].pos, c.s[iRel].pos) : 99f;
            float squat = 0f;
            foreach (var s in c.s) if (s.t >= t0 && s.t < tRel) squat = Mathf.Max(squat, s.pitch);
            HMetric("launch_throttle_to_90pct_s", thT); HMetric("launch_to_3ms_s", T(3f)); HMetric("launch_to_6ms_s", T(6f)); HMetric("launch_to_9ms_s", T(9f));
            HMetric("launch_dist_in_2s_m", d2); HMetric("launch_speed_at_release_ms", uRel); HMetric("launch_squat_deg", squat);
            HMetric("launch_rollout_s", stopT); HMetric("launch_rollout_m", coast);
            HCheck(T(3f) < 1.5f && T(9f) < 4f, $"feel_launch: full stick from a standstill: 3 m/s in {T(3f):0.00} s, 9 m/s in {T(9f):0.00} s");
            HCheck(stop >= 0 && coast > 3f && coast < 26f, $"feel_launch: finger up at {uRel:0.0} m/s: it slows down clearly and rolls out {coast:0.0} m in {stopT:0.00} s");
        }

        static void HFinishTurn(HCase c, Player pl, float A)
        {
            int s5 = HFirst(c, s => s.t >= 1f && s.steer >= 5f);
            float steerT = s5 >= 0 ? c.s[s5].t - 1f : 99f;
            int h50 = HFirst(c, s => s.t >= 1f && HRel(c, s) >= A * 0.5f), h90 = HFirst(c, s => s.t >= 1f && HRel(c, s) >= A * 0.9f);
            float t50 = h50 >= 0 ? c.s[h50].t - 1f : 99f, t90 = h90 >= 0 ? c.s[h90].t - 1f : 99f;
            float peak = -999f, back = 999f, yawPeak = 0f;
            for (int i = 1; i < c.s.Count; i++)
            {
                var s = c.s[i];
                if (s.t >= 1f && s.t < 2.8f) peak = Mathf.Max(peak, HRel(c, s));
                if (s.t >= 2.8f && s.t < 4.8f) back = Mathf.Min(back, HRel(c, s));
                if (s.t >= 1f && s.t < 4.8f) yawPeak = Mathf.Max(yawPeak, Mathf.Abs(HYawRate(c, i)));
            }
            int r5 = HFirst(c, s => s.t >= 2.8f && Mathf.Abs(HRel(c, s)) <= 5f);
            float backT = r5 >= 0 ? c.s[r5].t - 2.8f : 99f;
            float over = Mathf.Max(0f, peak - A), past = Mathf.Max(0f, -back);
            int iEnd = HFirst(c, s => s.t >= 4.75f);
            float uEnd = iEnd >= 0 ? c.s[iEnd].u : 0f;
            string k = c.name.Substring(5);
            HMetric(k + "_wheel_5deg_s", steerT); HMetric(k + "_heading_50pct_s", t50); HMetric(k + "_heading_90pct_s", t90);
            HMetric(k + "_overshoot_deg", over); HMetric(k + "_return_within_5deg_s", backT); HMetric(k + "_return_swing_past_deg", past);
            HMetric(k + "_yaw_rate_peak_dps", yawPeak); HMetric(k + "_speed_after_ms", uEnd);
            HCheck(t90 < 2f && over < A * 0.25f, $"{c.name}: the nose follows a {A:0} deg stick step ({t50:0.00} s to half, {t90:0.00} s to 90 %, overshoot {over:0.0} deg)");
            HCheck(backT < 2f && past < 8f, $"{c.name}: back on the old line without a weave ({backT:0.00} s to within 5 deg, swing past it {past:0.0} deg)");
        }

        // half a slalom period: 0.825 s is not a multiple of the 0.1 s common period of the 50 Hz physics and the 60 FPS
        // frames, so consecutive stick switches land 5 ms apart in the physics step (a 0.8 s half period put every switch
        // of a run on the same phase, and runs differed by a whole step)
        const float SlalomHalf = 0.825f;
        static float HSlalomDeg(float t) => ((int)((t - 1f) / SlalomHalf)) % 2 == 0 ? 30f : -30f;

        static void HFinishSlalom(HCase c, Player pl)
        {
            float hi = -999f, lo = 999f, xHi = -999f, xLo = 999f, lagSum = 0f, lagMax = 0f, turnSum = 0f;
            int lagN = 0, turnN = 0;
            for (int k = 2; k <= 6; k++)
            {
                float ts = 1f + SlalomHalf * k;      // a stick switch (the first two are the run-in)
                if (ts > 6.5f) break;
                float sign = HSlalomDeg(ts + 0.01f) > 0f ? 1f : -1f;
                bool rev = false;
                for (int i = 1; i < c.s.Count; i++)
                {
                    if (c.s[i].t < ts) continue;
                    if (c.s[i].t > ts + SlalomHalf) break;
                    float r = HYawRate(c, i) * sign;
                    if (!rev && r > 2f) { float lag = c.s[i].t - ts; lagSum += lag; lagMax = Mathf.Max(lagMax, lag); lagN++; rev = true; }
                    if (r >= 20f) { turnSum += c.s[i].t - ts; turnN++; break; }     // the new turn is under way
                }
            }
            foreach (var s in c.s)
                if (s.t >= 2.6f && s.t < 6.6f) { hi = Mathf.Max(hi, HRel(c, s)); lo = Mathf.Min(lo, HRel(c, s)); xHi = Mathf.Max(xHi, s.pos.x); xLo = Mathf.Min(xLo, s.pos.x); }
            float lagMean = lagN > 0 ? lagSum / lagN : 99f;
            string k2 = c.name.Substring(5);
            HMetric(k2 + "_reaction_mean_s", lagMean); HMetric(k2 + "_reaction_max_s", lagMax);
            HMetric(k2 + "_new_turn_20dps_s", turnN > 0 ? turnSum / turnN : 99f);
            // yaw rate against the stick at the slalom's fundamental over two whole periods of the steady part: phase lag
            // (s) and gain - a measure that does not hang on single frames like the times above
            const float f0 = 1f / (2f * SlalomHalf), w0 = 2.6f, w1 = 2.6f + 4f * SlalomHalf;
            double sRe = 0, sIm = 0, yRe = 0, yIm = 0;
            for (int i = 1; i < c.s.Count; i++)
            {
                float t = c.s[i].t;
                if (t < w0 || t > w1) continue;
                float dt = t - c.s[i - 1].t, w = 2f * Mathf.PI * f0 * t;
                float st = HSlalomDeg(t), yr = HYawRate(c, i);
                sRe += st * Mathf.Cos(w) * dt; sIm += st * Mathf.Sin(w) * dt;
                yRe += yr * Mathf.Cos(w) * dt; yIm += yr * Mathf.Sin(w) * dt;
            }
            float lagDeg = Mathf.DeltaAngle((float)(System.Math.Atan2(sIm, sRe) * Mathf.Rad2Deg), (float)(System.Math.Atan2(yIm, yRe) * Mathf.Rad2Deg));
            float gain = (float)(System.Math.Sqrt(yRe * yRe + yIm * yIm) / System.Math.Max(1e-6, System.Math.Sqrt(sRe * sRe + sIm * sIm)));
            HMetric(k2 + "_yaw_lag_s", lagDeg / 360f / f0);
            HMetric(k2 + "_yaw_gain", gain);
            HMetric(k2 + "_heading_swing_deg", hi - lo); HMetric(k2 + "_lateral_swing_m", xHi - xLo);
            HCheck(lagN >= 3 && lagMax < 0.6f, $"{c.name}: the body answers every stick switch ({lagN} switches, reaction mean {lagMean:0.00} s, max {lagMax:0.00} s)");
            HCheck(hi < 40f && lo > -40f, $"{c.name}: the nose stays within the stick's +-30 deg plus a margin (heading {lo:0.0}..{hi:0.0} deg)");
        }

        static void HFinishSmallCorrections(HCase c, Player pl)
        {
            float maxSteer = 0f, maxSteerRate = 0f, errSum = 0f, over = 0f;
            int n = 0;
            for (int i = 1; i < c.s.Count; i++)
            {
                var s = c.s[i];
                if (s.t < 1f || s.t >= 5.6f) continue;
                maxSteer = Mathf.Max(maxSteer, Mathf.Abs(s.steer));
                float dt = s.t - c.s[i - 1].t;
                if (dt > 1e-4f) maxSteerRate = Mathf.Max(maxSteerRate, Mathf.Abs(s.steer - c.s[i - 1].steer) / dt);
                float want = s.t < 2f ? 6f : s.t < 3f ? 0f : s.t < 4f ? -6f : 0f;
                if ((s.t > 1.6f && s.t < 2f) || (s.t > 2.6f && s.t < 3f) || (s.t > 3.6f && s.t < 4f) || (s.t > 5.2f && s.t < 5.6f)) { errSum += Mathf.Abs(HRel(c, s) - want); n++; }
                if (s.t >= 1f && s.t < 2f) over = Mathf.Max(over, HRel(c, s) - 6f);
                if (s.t >= 3f && s.t < 4f) over = Mathf.Max(over, -6f - HRel(c, s));
            }
            float err = n > 0 ? errSum / n : 99f;
            HMetric("small_wheel_max_deg", maxSteer); HMetric("small_wheel_rate_max_dps", maxSteerRate); HMetric("small_tracking_error_deg", err); HMetric("small_overshoot_deg", over);
            HCheck(maxSteer < 12f && err < 2.5f && over < 2.5f, $"feel_small_corrections: +-6 deg nudges stay small and smooth (wheel max {maxSteer:0.0} deg, tracking error {err:0.00} deg, overshoot {over:0.0} deg)");
        }

        static void HFinishTopSpeed(HCase c, Player pl)
        {
            float peak = 0f, past = 0f, yawPeak = 0f, settle = -1f, uMin = 99f;
            int flips = 0; float prevSign = 0f;
            for (int i = 1; i < c.s.Count; i++)
            {
                var s = c.s[i];
                if (s.t < 1.5f || s.t >= 5.4f) continue;
                float h = HRel(c, s), r = HYawRate(c, i);
                uMin = Mathf.Min(uMin, s.u);
                yawPeak = Mathf.Max(yawPeak, Mathf.Abs(r));
                if (s.t < 3.6f) { peak = Mathf.Max(peak, h); if (s.t >= 2f) past = Mathf.Max(past, -h); if (s.t >= 2f && Mathf.Abs(h) > 1.5f) settle = s.t - 2f; }
                if (s.t >= 2f && s.t < 3.6f && Mathf.Abs(r) > 3f) { float sg = Mathf.Sign(r); if (prevSign != 0f && sg != prevSign) flips++; prevSign = sg; }
            }
            HMetric("top_nudge_heading_peak_deg", peak); HMetric("top_return_swing_past_deg", past); HMetric("top_return_settle_s", settle);
            HMetric("top_yaw_rate_peak_dps", yawPeak); HMetric("top_yaw_reversals", flips); HMetric("top_speed_min_ms", uMin);
            HCheck(flips <= 2 && past < 3f && settle < 1.4f, $"feel_top_speed: a 10 deg nudge at {uMin:0.0}+ m/s and back: calm, no weave (swing past {past:0.0} deg, settled in {settle:0.00} s, {flips} yaw reversals)");
        }

        static void HFinishRelease(HCase c, Player pl)
        {
            const float tRel = 1.2f;
            int iRel = HFirst(c, s => s.t >= tRel);
            float u0 = iRel >= 0 ? c.s[iRel].u : 0f;
            int i05 = HFirst(c, s => s.t >= tRel + 0.5f), i10 = HFirst(c, s => s.t >= tRel + 1f);
            int stop = HFirst(c, s => s.t >= tRel && Mathf.Abs(s.u) < 0.3f);
            float stopT = stop >= 0 ? c.s[stop].t - tRel : 99f;
            float dist = stop >= 0 && iRel >= 0 ? Vector3.Distance(c.s[stop].pos, c.s[iRel].pos) : 99f;
            float dive = 0f;
            foreach (var s in c.s) if (s.t >= tRel && s.t < tRel + 1.5f) dive = Mathf.Min(dive, s.pitch);
            float u05 = i05 >= 0 ? c.s[i05].u : 0f, u10 = i10 >= 0 ? c.s[i10].u : 0f;
            HMetric("release_from_ms", u0); HMetric("release_speed_after_0.5s_ms", u05); HMetric("release_speed_after_1s_ms", u10);
            HMetric("release_to_stop_s", stopT); HMetric("release_rollout_m", dist); HMetric("release_dive_deg", dive);
            HCheck(stop >= 0 && dist > 3f && dist < 24f && u05 < u0 - 1f, $"feel_release: finger up at {u0:0.0} m/s: a clear slow-down ({u05:0.0} m/s after 0.5 s) and a short roll-out ({dist:0.0} m, {stopT:0.00} s)");
        }

        static void HFinishAbsorb(HCase c, Player pl)
        {
            float minHeave = 0f, settle = -1f;
            foreach (var s in c.s)
            {
                if (s.t < 0.5f) continue;
                minHeave = Mathf.Min(minHeave, s.heave);
                if (Mathf.Abs(s.heave) > 0.003f) settle = s.t - 0.5f;
            }
            HCheck(minHeave < -0.005f && minHeave > -0.04f, $"absorb_rigid: scrap absorbed: the car settles {minHeave * 100f:0.0} cm on its springs");
            HCheck(settle < 1.0f, $"absorb_rigid: and is still again after {settle:0.00} s");
        }

        // ------------------------------------------------------------------ any scenario: per-frame driving telemetry (-driveCsv 1)
        static StringBuilder dCsv;
        static int dFrame = -1;

        static void DriveCsvTick(Player pl)
        {
            if (HArg("-driveCsv") != "1" || Time.frameCount == dFrame || pl == null) return;
            dFrame = Time.frameCount;
            if (dCsv == null)
            {
                dCsv = new StringBuilder(); dCsv.AppendLine("t,u,vy,y,heading,steer,gear,throttle,brake,amount,backward,airborne,wheels_down,x,z,stick_x,stick_y,rebound_caps");
                // what the car touches (one line per obstacle and second): name, layer, normal, impact speed
                var lastLog = new Dictionary<Collider, float>();
                Player.CollisionProbe = col =>
                {
                    if (col.contactCount == 0 || (lastLog.TryGetValue(col.collider, out float at) && Time.time - at < 1f)) return;
                    lastLog[col.collider] = Time.time;
                    var cp = col.GetContact(0);
                    Debug.Log($"RoadGame DRIVE contact t={Game.I.SessionTime:0.00} with={col.collider.name} layer={col.collider.gameObject.layer} normal=({cp.normal.x:0.00},{cp.normal.y:0.00},{cp.normal.z:0.00}) at=({cp.point.x:0.0},{cp.point.y:0.00},{cp.point.z:0.0}) rel={col.relativeVelocity.magnitude:0.0}");
                };
            }
            var st = Game.I.MoveInput;
            dCsv.Append(F(Game.I.SessionTime)).Append(',').Append(F(pl.ForwardSpeed)).Append(',').Append(F(pl.VerticalSpeed)).Append(',').Append(F(pl.Pos.y)).Append(',')
                .Append(F(pl.Heading)).Append(',').Append(F(pl.SteerAngle)).Append(',').Append((int)pl.GearDirection).Append(',').Append(F(pl.Commands.throttle)).Append(',')
                .Append(F(pl.Commands.brake)).Append(',').Append(F(pl.Intent.amount)).Append(',').Append(pl.Intent.backward ? 1 : 0).Append(',').Append(pl.Airborne ? 1 : 0).Append(',')
                .Append(pl.WheelsDown ? 1 : 0).Append(',').Append(F(pl.Pos.x)).Append(',').Append(F(pl.Pos.z)).Append(',').Append(F(st.x)).Append(',').Append(F(st.y)).Append(',')
                .Append(Player.ReboundCaps).AppendLine();
        }

        static void DriveCsvFinish()
        {
            if (dCsv != null) File.WriteAllText(Path.Combine(cfg.outDir, "drive_telemetry.csv"), dCsv.ToString());
        }

        // ------------------------------------------------------------------ side camera: suspension close-ups
        static int hSideIndex;

        static void HPlaceSide(Player pl, Camera cam)
        {
            var focus = pl.Pos + Vector3.up * 0.85f;
            var fwd = pl.transform.forward; fwd.y = 0f; fwd.Normalize();
            var dir = Quaternion.AngleAxis(62f, Vector3.up) * fwd;
            dir = dir * Mathf.Cos(9f * Mathf.Deg2Rad) + Vector3.up * Mathf.Sin(9f * Mathf.Deg2Rad);
            cam.transform.position = focus + dir * 10.5f;
            cam.transform.LookAt(focus);
            cam.fieldOfView = 30f;
            cam.nearClipPlane = 0.1f;
        }

        static void HSideShot(Player pl, string label)
        {
            MutEnsureCam();
            var target = MutRT(ref mutVideoRT, 1280, 720);
            mutCam.targetTexture = target;
            mutCam.ResetAspect();
            HPlaceSide(pl, mutCam);
            mutCam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = target;
            var tex = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, label + ".png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
        }

        static void HSideVideo(Player pl)
        {
            float st = Game.I.SessionTime;
            if (st < cfg.videoFrom || st > cfg.videoTo) return;
            MutEnsureCam();
            var target = MutRT(ref mutVideoRT, 1280, 720);
            mutCam.targetTexture = target;
            mutCam.ResetAspect();
            HPlaceSide(pl, mutCam);
            mutCam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = target;
            var tex = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            var dir = Path.Combine(cfg.outDir, "video_side");
            Directory.CreateDirectory(dir);
            File.WriteAllBytes(Path.Combine(dir, $"f{hSideIndex++:00000}.jpg"), tex.EncodeToJPG(90));
            UnityEngine.Object.DestroyImmediate(tex);
        }
    }
}
