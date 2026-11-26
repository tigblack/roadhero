using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// DEV «Локации» with the real game, its HUD buttons and an isolated test save (-captureSaveKey):
    ///  devtravel       a new save: the intro runs, every gate is closed; the DEV panel's "Зона 3" button takes the car
    ///                  to the Ashen Winter pad (intro set aside without completion, no unlock, speed and John Wick kept),
    ///                  autosave / minimize keep the save's position, a repeated tap moves once, back to zone 1;
    ///  devtravelsave   a save with the tutorial done and only the first zone open: the visit, autosave, minimize, a death
    ///                  in the visited zone (respawn on its pad), the way back, and the save left for the reload run;
    ///  devtravelreload the same save after a restart (-captureKeepSave start): the car is at the allowed checkpoint.
    /// Run: -captureScenario devtravel -captureSaveKey _devtravel -captureTimes 2.4,4.2,9,15,18 [-captureSize 1170x540]
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class DevTravelReport
        {
            public string mode;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> notes = new List<string>();
        }

        static DevTravelReport dtReport;
        static string dtMode = "";
        static readonly HashSet<string> dtDone = new HashSet<string>();
        static float dtPx, dtPz;
        static bool dtDied;
        static Vector3? dtRespawnPos;     // where the car stood the moment it came back after the death

        static void DevTravelSetup(Progress p, string mode)
        {
            dtMode = mode;
            dtReport = new DevTravelReport { mode = mode };
            dtDone.Clear();
            dtDied = false;
            dtRespawnPos = null;
            var d = p.d;
            if (mode == "devtravelsave")
            {
                d.introPending = false; d.tutorialDone = true; d.unlockedZone = 0;
                d.px = 10f; d.pz = -75f; d.py = 0f; d.heading = 0f;
                d.maxHp = d.hp = 4000; d.dmg[0] = 40;
            }
            // a new save opens with the intro run (the capture's common setup turns it off for other scenarios)
            if (mode == "devtravel") { d.introPending = true; d.tutorialDone = false; d.unlockedZone = 0; }
            Game.ScriptedInput = null;
        }

        static void DtCheck(bool ok, string message)
        {
            if (ok) dtReport.checks.Add(message); else dtReport.failures.Add(message);
            Debug.Log("RoadGame DEVTRAVEL_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static bool DtOnce(string key, float t, float at)
        {
            if (t < at || dtDone.Contains(key)) return false;
            dtDone.Add(key);
            return true;
        }

        static Button DtButton(string name)
        {
            var panel = Game.I.hud != null ? Game.I.hud.devPanel : null;
            if (panel == null) return null;
            foreach (var b in panel.GetComponentsInChildren<Button>(true)) if (b.name == name) return b;
            return null;
        }

        static void DtShot(string label)
        {
            var g = Game.I;
            g.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, $"{dtMode}_{label}.png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            dtReport.notes.Add("shot " + label + " t=" + g.SessionTime.ToString("0.00"));
        }

        static SaveData DtStoredSave()
        {
            string raw = SaveSystem.RawJson();
            return string.IsNullOrEmpty(raw) ? null : JsonUtility.FromJson<SaveData>(raw);
        }

        static void DevTravelTick(Player pl)
        {
            var g = Game.I;
            float t = g.SessionTime;
            var d = g.progress.d;
            if (dtMode == "devtravelreload")
            {
                if (DtOnce("reload", t, 1.5f))
                {
                    DtCheck(Content.ZoneIndexAt(pl.Pos.z) <= d.unlockedZone, $"after a restart the car starts in an unlocked zone (zone {Content.ZoneIndexAt(pl.Pos.z)}, unlocked {d.unlockedZone}, at {pl.Pos})");
                    DtCheck(d.unlockedZone == 0 && d.bossKills[2] == 0, "the test visit left no unlock and no boss win in the save");
                    DtCheck(DevTravel.TestZone == -1, "test access does not survive a restart (session only)");
                }
                return;
            }
            if (DtOnce("start", t, 1.0f))
            {
                if (dtMode == "devtravel")
                    DtCheck(d.introPending && Intro.Active != null && d.unlockedZone == 0, $"a new save: the intro runs, every gate closed (car at {pl.Pos})");
                else
                    DtCheck(!d.introPending && d.unlockedZone == 0 && Content.ZoneIndexAt(pl.Pos.z) == 0, $"a save with only the first zone open, car in zone 0 at {pl.Pos}");
                g.SaveNow();
                var st = DtStoredSave();
                dtPx = st != null ? st.px : float.NaN; dtPz = st != null ? st.pz : float.NaN;
                dtReport.notes.Add($"checkpoint at start: {dtPx:0.0}, {dtPz:0.0}");
                DevOptions.SetSpeed(2f);
                DevOptions.SetJohnWick(true);
            }
            if (DtOnce("open", t, 2.0f))
            {
                g.hud.devPanel.Open();
                DtCheck(g.hud.devPanel.IsOpen && g.paused, "the DEV panel opens and pauses the game");
                var b = DtButton("TravelZone3");
                DtCheck(b != null && b.gameObject.activeInHierarchy && b.interactable, "«Зона 3 — Пепельная зима» is available at once (closed story gate)");
                var card = g.hud.devPanel.transform.Find("Modal/Safe/Card") as RectTransform;
                if (card != null)
                {
                    var corners = new Vector3[4];
                    card.GetWorldCorners(corners);
                    var canvas = card.GetComponentInParent<Canvas>().rootCanvas;
                    var cam = canvas.renderMode == RenderMode.ScreenSpaceOverlay ? null : canvas.worldCamera;
                    Vector2 a = RectTransformUtility.WorldToScreenPoint(cam, corners[0]), c = RectTransformUtility.WorldToScreenPoint(cam, corners[2]);
                    var px = canvas.pixelRect;
                    DtCheck(a.x >= px.xMin - 1f && a.y >= px.yMin - 1f && c.x <= px.xMax + 1f && c.y <= px.yMax + 1f,
                        $"the DEV card fits the screen ({px.width}x{px.height}: {a} .. {c})");
                }
                DtShot("dev_panel");
                // the open panel pauses the game (session time stops): the tap follows in the same step
            }
            if (DtOnce("go3", t, 2.0f))
            {
                int movesBefore = DevTravel.Moves;
                var b = DtButton("TravelZone3");
                // a double tap in the same frame: one move only
                b.onClick.Invoke();
                b.onClick.Invoke();
                var st = World.I.stations.Find(s => s.zone == 2);
                DtCheck(DevTravel.Moves == movesBefore + 1, $"a repeated tap moves the car once ({DevTravel.Moves - movesBefore})");
                DtCheck(!g.hud.devPanel.IsOpen && !g.paused, "the panel closes and the game runs again");
                DtCheck(st != null && Vector2.Distance(new Vector2(pl.Pos.x, pl.Pos.z), new Vector2(st.pos.x, st.pos.z)) < 0.5f && Mathf.Abs(pl.Heading) < 1f,
                    $"the car stands on the Ashen Winter pad heading north ({pl.Pos}, heading {pl.Heading:0.0})");
                var gr = Ground.Sample(pl.Pos.x, pl.Pos.z, pl.Pos.y + 1f);
                DtCheck(gr.valid && Mathf.Abs(gr.h - pl.Pos.y) < 0.05f && !pl.Airborne && pl.Speed < 0.1f, $"on the floor (y {pl.Pos.y:0.00}), at rest, not flying");
                DtCheck(d.unlockedZone == 0 && d.bossKills[2] == 0 && DevTravel.TestZone == 2, $"no unlock, no boss win; test access in session memory (unlocked {d.unlockedZone}, test {DevTravel.TestZone})");
                DtCheck(Mathf.Approximately(DevOptions.Speed, 2f) && DevOptions.JohnWick, "the game speed (2x) and John Wick are kept");
                DtCheck(g.focusTarget == null && DevTravel.InputHeld, "aim cleared, input held for a moment after the move");
                if (dtMode == "devtravel")
                    DtCheck(Intro.Active == null && d.introPending, "the unfinished intro is set aside: no intro jump, the save keeps the intro ahead");
                var cam = g.cameraRig.transform.position;
                DtCheck(Mathf.Abs(cam.x - pl.Pos.x) < 30f && cam.z < pl.Pos.z && pl.Pos.z - cam.z < 80f, $"the camera follows to the new place ({cam})");
            }
            if (DtOnce("arrivedShot", t, 2.6f)) DtShot("arrived_zone3");
            if (DtOnce("goal", t, 4.0f))
            {
                var goal = Goals.Evaluate(g);
                DtCheck(goal.kind == Goals.Kind.Boss && goal.zone == 2 && goal.sub != null && goal.sub.Contains("Тестовый визит"),
                    $"the goal widget shows this zone's boss as a test visit ({goal.kind}, zone {goal.zone}: {goal.sub})");
            }
            if (DtOnce("autosave", t, 8.6f))
            {
                // the 5 s autosave has run in zone 2; minimize saves too
                g.SaveNow();
                typeof(Game).GetMethod("OnApplicationPause", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                    .Invoke(g, new object[] { true });
                var st = DtStoredSave();
                bool kept = st != null && Content.ZoneIndexAt(st.pz) <= st.unlockedZone && Mathf.Abs(st.px - dtPx) < 0.01f && Mathf.Abs(st.pz - dtPz) < 0.01f;
                DtCheck(kept, $"autosave and minimize keep the allowed checkpoint ({(st != null ? st.px + ", " + st.pz : "-")}; unlocked {(st != null ? st.unlockedZone : -1)})");
                if (dtMode == "devtravel") DtCheck(st != null && st.introPending, "the save still has the intro ahead");
            }
            if (dtMode == "devtravelsave")
            {
                // the respawn moment: the car may drive off the pad afterwards (autopilot, hits), so its place is taken here
                if (dtDied && dtRespawnPos == null && pl.Alive) dtRespawnPos = pl.Pos;
                if (DtOnce("die", t, 9.5f))
                {
                    pl.TakeDamage(d.maxHp * 10, pl.Pos + Vector3.forward);
                    dtDied = !pl.Alive;
                    DtCheck(dtDied, "the car can die in the visited zone");
                }
                if (DtOnce("respawned", t, 14.5f))
                {
                    var st = World.I.stations.Find(s => s.zone == 2);
                    var rp = dtRespawnPos ?? new Vector3(1e4f, 0f, 1e4f);
                    DtCheck(pl.Alive && st != null && Vector2.Distance(new Vector2(rp.x, rp.z), new Vector2(st.pos.x, st.pos.z)) < 1f,
                        $"after a death in the test zone the car comes back on its pad (respawned at {rp}, now {pl.Pos})");
                    var sv = DtStoredSave();
                    DtCheck(sv != null && Content.ZoneIndexAt(sv.pz) == 0 && sv.unlockedZone == 0, "the save still holds the zone-0 checkpoint after the death");
                }
            }
            if (DtOnce("back1", t, 15.5f))
            {
                g.hud.devPanel.Open();
                DtButton("TravelZone1").onClick.Invoke();
                var st = World.I.stations.Find(s => s.zone == 0);
                DtCheck(st != null && Vector2.Distance(new Vector2(pl.Pos.x, pl.Pos.z), new Vector2(st.pos.x, st.pos.z)) < 0.5f && Content.ZoneIndexAt(pl.Pos.z) == 0,
                    $"«Зона 1» takes the car back to the Dust Flats pad ({pl.Pos})");
                DtCheck(Mathf.Approximately(DevOptions.Speed, 2f) && DevOptions.JohnWick, "speed and John Wick still kept");
            }
            if (DtOnce("back1Shot", t, 16.2f)) DtShot("back_zone1");
            if (DtOnce("back2", t, 17.0f))
            {
                g.hud.devPanel.Open();
                DtButton("TravelZone2").onClick.Invoke();
                DtCheck(Content.ZoneIndexAt(pl.Pos.z) == 1, $"«Зона 2» takes the car to the Toxic Wetlands pad ({pl.Pos})");
            }
            if (DtOnce("final", t, 18.5f))
            {
                g.hud.devPanel.Open();
                DtButton("TravelZone1").onClick.Invoke();
                g.SaveNow();
                var sv = DtStoredSave();
                if (dtMode == "devtravelsave")
                    DtCheck(sv != null && Content.ZoneIndexAt(sv.pz) == 0 && !sv.introPending, $"back in an open zone the save takes the new position ({sv?.px:0.0}, {sv?.pz:0.0})");
                DevOptions.SetSpeed(1f);
                DevOptions.SetJohnWick(false);
            }
        }

        static void DevTravelFinish()
        {
            if (dtReport == null) return;
            File.WriteAllText(Path.Combine(cfg.outDir, dtMode + "-checks.json"), JsonUtility.ToJson(dtReport, true));
            Debug.Log($"RoadGame DEVTRAVEL_RESULT mode={dtMode} checks={dtReport.checks.Count} failures={dtReport.failures.Count}");
        }
    }
}
