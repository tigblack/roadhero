using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;
using UnityEngine.Profiling;

namespace RoadGame
{
    /// <summary>
    /// Read-only state reports for automated browser checks of the WebGL build (muted headless Chrome). Exists only when
    /// the test page defined window.RoadGameQA before the game started; players never get it. Once a second it reports
    /// the game state (zone, position, HP, kills, gems, Dev speed, time scale), Unity's memory split (allocated vs
    /// reserved, the managed heap, the graphics driver) and the screen rectangles of the buttons the test taps with real
    /// touch events. A few commands (SendMessage "RoadGameWebQA" / "Command") set up test states: "save",
    /// "heal", "zone1" (open the second zone and drive there as if the Mammoth fell), "tp x z yaw".
    /// </summary>
    public sealed class WebQA : MonoBehaviour
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] static extern int RoadGameQAEnabled();
        [DllImport("__Internal")] static extern void RoadGameQAReport(string json);

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (RoadGameQAEnabled() != 1) return;
            var go = new GameObject("RoadGameWebQA");
            DontDestroyOnLoad(go);
            go.AddComponent<WebQA>();
        }
#endif

        float next;
        float worstDt, sumDt;
        int frames;
        readonly StringBuilder sb = new StringBuilder(1024);

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            worstDt = Mathf.Max(worstDt, dt); sumDt += dt; frames++;
            // while the session is being built: a compact memory sample every frame (where the heap grows)
            var g0 = Game.I;
            if (g0 == null || !g0.Ready)
            {
                Send("{\"load\":1,\"phase\":\"" + World.LoadPhase + "\",\"frame\":" + Time.frameCount + ",\"t\":" + Time.realtimeSinceStartup.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture) +
                     ",\"managedHeapMiB\":" + (Profiler.GetMonoHeapSizeLong() / 1048576f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture) +
                     ",\"managedUsedMiB\":" + (Profiler.GetMonoUsedSizeLong() / 1048576f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture) +
                     ",\"reservedMiB\":" + (Profiler.GetTotalReservedMemoryLong() / 1048576f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture) +
                     ",\"allocatedMiB\":" + (Profiler.GetTotalAllocatedMemoryLong() / 1048576f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture) + "}");
                return;
            }
            if (Time.unscaledTime < next) return;
            next = Time.unscaledTime + 1f;
            Send(Build());
            worstDt = 0f; sumDt = 0f; frames = 0;
        }

        static void Send(string json)
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            RoadGameQAReport(json);
#else
            Debug.Log("RoadGame WEBQA " + json);
#endif
        }

        string Build()
        {
            var g = Game.I;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            sb.Clear();
            sb.Append('{');
            Num("t", Time.realtimeSinceStartup);
            Num("frameMsAvg", frames > 0 ? sumDt / frames * 1000f : 0f);
            Num("frameMsWorst", worstDt * 1000f);
            Num("timeScale", Time.timeScale);
            Num("devSpeed", DevOptions.Speed);
            Bool("johnWick", DevOptions.JohnWick);
            Num("allocatedMiB", Profiler.GetTotalAllocatedMemoryLong() / 1048576f);
            Num("reservedMiB", Profiler.GetTotalReservedMemoryLong() / 1048576f);
            Num("managedUsedMiB", Profiler.GetMonoUsedSizeLong() / 1048576f);
            Num("managedHeapMiB", Profiler.GetMonoHeapSizeLong() / 1048576f);
            Num("gfxMiB", Profiler.GetAllocatedMemoryForGraphicsDriver() / 1048576f);
            Num("screenW", Screen.width); Num("screenH", Screen.height);
            bool ready = g != null && g.Ready && g.player != null && g.progress != null;
            Bool("ready", ready);
            if (ready)
            {
                var d = g.progress.d; var p = g.player;
                Num("x", p.Pos.x); Num("y", p.Pos.y); Num("z", p.Pos.z); Num("heading", p.Heading); Num("speed", p.Speed);
                Num("zone", Content.ZoneIndexAt(p.Pos.z));
                Bool("alive", p.Alive);
                Num("hp", (float)d.hp); Num("maxHp", (float)d.maxHp); Num("dmg0", (float)d.dmg[0]); Num("regen", (float)d.regen);
                Num("kills", d.totalKills); Num("gems", d.gems); Num("unlockedZone", d.unlockedZone);
                Num("bossKills0", d.bossKills[0]); Num("bossKills1", d.bossKills[1]); Num("bossKills2", d.bossKills[2]);
                Bool("intro", d.introPending || Intro.Active != null);
                Bool("introRunning", DevTravel.IntroRunning(d));
                Num("testZone", DevTravel.TestZone);
                Num("devMoves", DevTravel.Moves);
                Bool("paused", g.paused);
                Bool("devOpen", g.hud != null && g.hud.devPanel != null && g.hud.devPanel.IsOpen);
                Bool("panelOpen", g.hud != null && g.hud.panels != null && g.hud.panels.IsOpen);
                Num("reeled", Harpooner.Reeled);
                Num("gunShots", Turret.ShotsFired);
                if (g.hud != null)
                {
                    sb.Append("\"rects\":{");
                    Rect("dev", g.hud.DevButton);
                    Rect("garage", g.hud.GarageButton);
                    Rect("shop", g.hud.ShopButton);
                    Rect("goal", g.hud.GoalPanel);
                    if (g.hud.devPanel != null)
                        foreach (var n in new[] { "Speed1", "Speed2", "Speed4", "JohnWickToggle", "TravelZone1", "TravelZone2", "TravelZone3", "Done" })
                        {
                            var t = FindDeep(g.hud.devPanel.transform, n);
                            if (t != null) Rect(n, (RectTransform)t);
                        }
                    if (sb[sb.Length - 1] == ',') sb.Length--;
                    sb.Append("},");
                }
            }
            if (sb[sb.Length - 1] == ',') sb.Length--;
            sb.Append('}');
            return sb.ToString();

            void Num(string k, float v) { sb.Append('"').Append(k).Append("\":").Append(float.IsFinite(v) ? v.ToString("0.###", inv) : "null").Append(','); }
            void Bool(string k, bool v) { sb.Append('"').Append(k).Append("\":").Append(v ? "true" : "false").Append(','); }
            void Rect(string k, RectTransform r)
            {
                if (r == null || !r.gameObject.activeInHierarchy) return;
                var c = r.GetComponentInParent<Canvas>();
                var cam = c != null && c.rootCanvas.renderMode != RenderMode.ScreenSpaceOverlay ? c.rootCanvas.worldCamera : null;
                var w = new Vector3[4];
                r.GetWorldCorners(w);
                Vector2 a = RectTransformUtility.WorldToScreenPoint(cam, w[0]), b = RectTransformUtility.WorldToScreenPoint(cam, w[2]);
                sb.Append('"').Append(k).Append("\":[").Append(a.x.ToString("0", inv)).Append(',').Append(a.y.ToString("0", inv)).Append(',')
                  .Append(b.x.ToString("0", inv)).Append(',').Append(b.y.ToString("0", inv)).Append("],");
            }
        }

        static Transform FindDeep(Transform root, string name)
        {
            if (root.name == name) return root;
            for (int i = 0; i < root.childCount; i++) { var f = FindDeep(root.GetChild(i), name); if (f != null) return f; }
            return null;
        }

        /// <summary>Test states (from the browser harness through SendMessage).</summary>
        public void Command(string cmd)
        {
            var g = Game.I;
            if (g == null || !g.Ready || g.player == null) return;
            var d = g.progress.d;
            var a = cmd.Split(' ');
            switch (a[0])
            {
                case "save": g.SaveNow(); break;
                case "heal": d.hp = d.maxHp; break;
                case "zone1":
                    // the state after the Mammoth fell: the gate is open; the car is put on the second zone's first pad
                    if (d.bossKills[0] < 1) d.bossKills[0] = 1;
                    g.progress.UnlockZone(1);
                    var st = World.I.NearestStation(new Vector3(0f, 0f, Content.ZoneMinZ(1) + 30f), 1);
                    if (st != null) { g.player.Teleport(st.pos, 0f); g.cameraRig.Snap(); }
                    g.SaveNow();
                    break;
                case "tp":
                    if (a.Length >= 3 && float.TryParse(a[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float x)
                        && float.TryParse(a[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float z))
                    {
                        float yaw = a.Length >= 4 && float.TryParse(a[3], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out float y) ? y : 0f;
                        g.player.Teleport(new Vector3(x, 0f, z), yaw);
                        g.cameraRig.Snap();
                    }
                    break;
            }
            Send("{\"command\":\"" + cmd + "\"}");
        }
    }
}
