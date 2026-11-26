using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Runtime acceptance check for Dev speed/John Wick, a real Mammoth machine-gun impact and the north gate.
    /// Run with -batchmode -disableaudio -executeMethod RoadGame.EditorTools.DevGameplayCheck.Run
    ///          -devCheckOut /absolute/output. Do not pass -quit; this runner stops Play and exits itself.
    /// Only the isolated _devcheck20261121 save is read/written. No production save or audio setting is changed.
    /// </summary>
    [InitializeOnLoad]
    public static class DevGameplayCheck
    {
        const string Key = "RoadGame.DevGameplayCheck.Output";
        const string FinishKey = "RoadGame.DevGameplayCheck.Finish";
        const string SaveSuffix = "_devcheck20261121";
        const BindingFlags AnyInstance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static string output;
        static double idleSince = -1, deadline;
        static Stack<IEnumerator> steps;
        static Report report;
        static bool reloading;
        static Mouse smokeMouse, previousMouse;
        static InputSettings previousInputSettings, smokeInputSettings;
        static Vector2 playerMousePosition;
        static bool playerMousePressed;
        static int playerMouseVersion;
        static InputUpdateType playerMouseUpdateType;

        [Serializable] class Check
        {
            public string name, details;
            public bool passed;
            public float gameSeconds, timeScale, speed;
            public float[] playerPosition;
        }
        [Serializable] class DrivePoint
        {
            public float realSeconds, gameSeconds, speed;
            public float[] position;
            public int zone;
        }
        [Serializable] class Report
        {
            public string version = "DevGameplayCheck/1";
            public string createdUtc, saveSuffix = SaveSuffix, targetHitMethod = "Target.Hit(1,false,player.Pos); Mammoth uses a real Turret round";
            public bool passed;
            public string exception;
            public List<Check> checks = new List<Check>();
            public List<DrivePoint> northGateDrive = new List<DrivePoint>();
            public List<string> screenshots = new List<string>();
        }

        static DevGameplayCheck()
        {
            output = SessionState.GetString(Key, "");
            if (string.IsNullOrEmpty(output)) return;
            WorkAudioMute.Apply();
            EditorApplication.playModeStateChanged += OnPlayState;
            if (SessionState.GetBool(FinishKey, false))
            {
                if (!EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.delayCall += CleanAndExit;
                return;
            }
            Arm();
        }

        public static void Run()
        {
            WorkAudioMute.Apply();
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("DevGameplayCheck needs stopped Play Mode.");
            output = Path.GetFullPath(Arg("-devCheckOut", "Docs/screenshots/dev-webgl-2026-11-21"));
            Directory.CreateDirectory(output);
            PlayerPrefs.DeleteKey("roadgame_save_v1" + SaveSuffix);
            PlayerPrefs.Save();
            SessionState.SetString(Key, output);
            SessionState.SetBool(FinishKey, false);
            SessionState.SetInt(FinishKey + ".exit", 0);
            EditorSceneManager.OpenScene(ProjectSetup.ScenePath, OpenSceneMode.Single);
            Arm();
        }

        static void Arm()
        {
            WorkAudioMute.Apply();
            SaveSystem.KeySuffix = SaveSuffix;
            Game.Autopilot = Game.AutopilotBoss = Game.AutopilotEnemiesOnly = false;
            Game.TestSetup = SetupFresh;
            deadline = EditorApplication.timeSinceStartup + 240;
            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;
            EditorApplication.playModeStateChanged -= OnPlayState;
            EditorApplication.playModeStateChanged += OnPlayState;
        }

        static void SetupFresh(Progress p)
        {
            var d = p.d;
            d.introPending = false;
            d.tutorialDone = true;
            d.unlockedZone = 0;
            d.bossKills = new int[4];
            d.weaponLevel = new[] { 1, 0, 0, 0 };
            d.dmg = new double[] { 6.5, 0, 0, 0 };
            d.maxHp = d.hp = 1000000; // Keep hostile AI from interrupting an acceptance check.
            d.regen = 0;
            d.nextBonusAt = Progress.NowMs + 3600000;
            Game.ScriptedInput = t => Vector2.zero;
            UnityEngine.Random.InitState(17421);
        }

        static void Tick()
        {
            try
            {
                if (EditorApplication.timeSinceStartup > deadline) throw new TimeoutException("DevGameplayCheck exceeded 240 real seconds.");
                if (!EditorApplication.isPlaying)
                {
                    if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isUpdating || EditorApplication.isCompiling) return;
                    if (idleSince < 0) idleSince = EditorApplication.timeSinceStartup;
                    if (EditorApplication.timeSinceStartup - idleSince < 2) return;
                    EditorApplication.EnterPlaymode();
                    return;
                }
                if (steps == null)
                {
                    if (Game.I == null || !Game.I.Ready) return;
                    report = new Report { createdUtc = DateTime.UtcNow.ToString("o") };
                    steps = new Stack<IEnumerator>();
                    steps.Push(RunChecks());
                }
                // Small editor coroutine runner; yields still wait for actual game frames where necessary below.
                while (steps.Count > 0)
                {
                    var step = steps.Peek();
                    if (!step.MoveNext()) { steps.Pop(); continue; }
                    if (step.Current is IEnumerator nested) { steps.Push(nested); continue; }
                    return;
                }
                report.passed = true;
                WriteReport();
                Debug.Log("DEV_CHECK SUCCESS checks=" + report.checks.Count + " output=" + output);
                Finish(0);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                if (report == null) report = new Report { createdUtc = DateTime.UtcNow.ToString("o") };
                report.passed = false;
                report.exception = error.ToString();
                try { if (Game.I != null && Game.I.Ready) Capture("failure.png"); } catch (Exception screenshotError) { Debug.LogWarning(screenshotError.Message); }
                WriteReport();
                Finish(1);
            }
        }

        static IEnumerator RunChecks()
        {
            var g = Game.I;
            g.player.turret.enabled = false;
            g.player.harpooner.enabled = false;
            foreach (var arm in g.player.arms) if (arm != null) arm.enabled = false;
            Require("fresh_locked_gate", g.progress.d.bossKills[0] == 0 && g.progress.d.unlockedZone == 0 && !NorthGate().open, "New isolated game; Mammoth alive and second zone locked.");
            Require("work_audio_muted", WorkAudioMute.Apply(), "Editor master audio muted; Sound/Music save settings remain untouched.");

            DevOptions.SetJohnWick(false);
            DevOptions.SetSpeed(1f);
            RequireScale("speed_1", 1f);
            DevOptions.SetSpeed(2f);
            RequireScale("speed_2", 2f);
            yield return MeasureSpeed(2f);
            DevOptions.SetSpeed(4f);
            RequireScale("speed_4", 4f);
            yield return MeasureSpeed(4f);
            g.paused = true;
            RequireScale("pause_at_4", 0f);
            g.paused = false;
            RequireScale("resume_at_4", 4f);
            g.paused = true;
            DevOptions.SetSpeed(2f);
            RequireScale("speed_change_keeps_pause", 0f);
            g.paused = false;
            RequireScale("resume_changed_speed", 2f);
            DevOptions.SetSpeed(4f);

            var slowMo = typeof(Game).GetMethod("DemoSlowMo", AnyInstance);
            if (slowMo == null) throw new MissingMethodException("Game.DemoSlowMo");
            g.StartCoroutine((IEnumerator)slowMo.Invoke(g, null));
            yield return Frames(2);
            Require("slowmo_uses_modifier", Time.timeScale > 0f && Time.timeScale < 4f, "Slow motion temporarily lowers selected speed4; actual=" + Time.timeScale);
            yield return WaitReal(1f);
            RequireScale("slowmo_restores_4", 4f);

            // Exercise real input actions, GraphicRaycaster and EventSystem before the direct listener checks below.
            yield return PointerInputSmoke();

            // Open the actual user-facing panel and let its layout render, then confirm it resumes selected speed.
            DevOptions.SetJohnWick(false);
            g.hud.DevButton.GetComponent<Button>().onClick.Invoke();
            yield return Frames(2);
            Require("dev_panel_pauses", g.hud.devPanel.IsOpen && g.paused && Mathf.Abs(Time.timeScale) < 0.001f, "Real DevPanel is open and gameplay is paused.");
            var card = g.hud.devPanel.transform.Find("Modal/Safe/Card");
            if (card == null) throw new InvalidOperationException("DevPanel card missing.");
            card.Find("Speed2").GetComponent<Button>().onClick.Invoke();
            Require("dev_ui_speed_2", DevOptions.Speed == 2f && g.paused && Time.timeScale == 0f, "Real Speed2 button updates selected speed while keeping the modal paused.");
            card.Find("Speed4").GetComponent<Button>().onClick.Invoke();
            card.Find("JohnWick/JohnWickToggle").GetComponent<Button>().onClick.Invoke();
            Require("dev_ui_john_wick_toggle", DevOptions.JohnWick && DevOptions.Speed == 4f, "Real JohnWickToggle and Speed4 buttons update session settings.");
            yield return Frames(2);
            Capture("00-dev-panel.png");
            card.Find("Done").GetComponent<Button>().onClick.Invoke();
            Require("dev_ui_done_closes", !g.hud.devPanel.IsOpen, "Real Done button closes the Dev panel.");
            RequireScale("dev_panel_resume_4", 4f);
            DevOptions.SetSpeed(1f);

            // Use production World.CreateTarget, including imported meshes/colliders and Enemy.Setup.
            var prop = Materialize(FindSpawn(TargetKind.Prop));
            var foot = Materialize(FindSpawn(TargetKind.Foot));
            var vehicle = Materialize(FindSpawn(TargetKind.Vehicle));
            DevOptions.SetJohnWick(false);
            OrdinaryHit(prop, "ordinary_hit_prop");
            OrdinaryHit(foot, "ordinary_hit_enemy");
            DevOptions.SetJohnWick(true);
            OneHit(prop, "john_wick_prop");
            OneHit(foot, "john_wick_foot");
            OneHit(vehicle, "john_wick_vehicle");

            var bossSpawn = g.world.bossSpawns[0];
            var boss = Materialize(bossSpawn);
            NavGrid.Build(0, 1000);
            NavGrid.Build(1, 1000);
            var navCellsField = typeof(NavGrid).GetField("cells", BindingFlags.Static | BindingFlags.NonPublic);
            if (navCellsField == null) throw new MissingFieldException("NavGrid.cells");
            var navCells = (byte[][])navCellsField.GetValue(null);
            var previousZone0Grid = navCells[0];
            var previousZone1Grid = navCells[1];
            Require("navigation_built_before_boss", NavGrid.Ready(0) && NavGrid.Ready(1), "Both adjacent navigation grids exist while Gate1 is still closed.");
            Require("mammoth_before_real_shot", !boss.dead && boss.hp == boss.maxHp && g.progress.d.bossKills[0] == 0, "Boss id=" + bossSpawn.id + " hp=" + boss.hp + "; no direct Hit has been applied to it.");
            g.world.enabled = false;
            g.world.activeTargets.Clear();
            g.world.activeTargets.Add(boss);
            var firingPosition = bossSpawn.pos + new Vector3(0, 0, -9f);
            g.player.Teleport(firingPosition, 0f); // Reposition inside zone0 only; north-boundary test below never teleports.
            g.cameraRig.Snap();
            Game.ScriptedInput = t => Vector2.zero;
            g.focusTarget = boss;
            // Reset stale aim selection; acquisition/fire/flight/impact themselves run through the real Turret.Update.
            typeof(Turret).GetField("target", AnyInstance)?.SetValue(g.player.turret, null);
            int shotsBefore = Turret.ShotsFired, hitsBefore = Turret.ShellHits;
            g.player.turret.enabled = true;
            yield return WaitUntil(() => boss.dead, 8f, "A real hood machine-gun round must kill Mammoth with John Wick enabled.");
            g.player.turret.enabled = false;
            Require("john_wick_mammoth_real_turret", Turret.ShotsFired - shotsBefore == 1 && Turret.ShellHits - hitsBefore == 1 && boss.dead,
                "Real Turret round: shotsDelta=" + (Turret.ShotsFired - shotsBefore) + " hitsDelta=" + (Turret.ShellHits - hitsBefore) + " gunDamageStat=" + g.progress.d.dmg[0]);
            Require("boss_progression", g.progress.d.bossKills[0] == 1 && g.progress.d.unlockedZone == 1, "Mammoth first kill grants bossKills[0]=1 and unlockedZone=1 through OnBossKilled.");
            Require("gate_opens_on_boss_kill", NorthGate().open, "Gate1 receives its opening state from the real progression event; collision stays closed until the animation finishes.");
            yield return WaitReal(1.9f);
            Require("gate_animation_finishes", NorthGate().open && !NorthGate().barrier.gameObject.activeSelf && GateCollidersOff(), "Barrier lowered/hidden after its normal opening animation.");
            navCells = (byte[][])navCellsField.GetValue(null);
            Require("gate_invalidates_navigation", !ReferenceEquals(previousZone0Grid, navCells[0]) && !ReferenceEquals(previousZone1Grid, navCells[1]),
                "Both cached grid arrays were discarded/replaced after the gate cleared; independent of whether HUD already rebuilt them.");
            Capture("01-mammoth-one-shot.png");
            g.SaveNow();
            var loadedImmediately = SaveSystem.Load();
            Require("save_load_boss_unlock", loadedImmediately.bossKills[0] == 1 && loadedImmediately.unlockedZone == 1, "SaveSystem.Load returns the persisted Mammoth kill and zone unlock.");
            loadedImmediately.unlockedZone = 0;
            SaveSystem.Save(loadedImmediately);
            var repairedLegacySave = SaveSystem.Load();
            Require("legacy_boss_unlock_repaired_on_load", repairedLegacySave.bossKills[0] == 1 && repairedLegacySave.unlockedZone == 1,
                "A deliberately stale isolated save with bossKills[0]=1 and unlockedZone=0 is repaired by SaveSystem.Load/Sanitize.");
            g.SaveNow(); // Restore the live session's correct save before the physical gate-drive/reload checks.

            // Restore normal world activation. Start strictly south of the gate, then drive entirely with the car.
            DevOptions.SetJohnWick(false);
            g.world.enabled = true;
            var gate = NorthGate();
            float boundary = Content.ZoneMinZ(1);
            var driveStart = new Vector3(gate.transform.position.x, 0, boundary - 10f);
            var floor = Ground.Sample(driveStart.x, driveStart.z, 1f);
            if (floor.valid) driveStart.y = floor.h;
            g.player.Teleport(driveStart, 0);
            g.player.SetSpeed(0);
            g.cameraRig.Snap();
            yield return Frames(2);
            Require("drive_starts_zone_0", Content.ZoneIndexAt(g.player.Pos.z) == 0 && g.player.Pos.z < boundary - 5f, "Only setup teleport: " + g.player.Pos + "; no teleport is used from this point until after reload.");
            Capture("02-gate-open.png");
            g.player.SetSpeed(5f);
            Game.ScriptedInput = t => Vector2.up;
            double driveBegin = EditorApplication.timeSinceStartup;
            while (g.player.Pos.z < boundary + 24f)
            {
                if (EditorApplication.timeSinceStartup - driveBegin > 15f) throw new TimeoutException("Car did not pass through Gate1 into zone1. Last position " + g.player.Pos);
                report.northGateDrive.Add(new DrivePoint
                {
                    realSeconds = (float)(EditorApplication.timeSinceStartup - driveBegin),
                    gameSeconds = g.SessionTime,
                    position = Pos(g.player.Pos),
                    zone = Content.ZoneIndexAt(g.player.Pos.z),
                    speed = g.player.Speed,
                });
                yield return Frames(1);
            }
            Game.ScriptedInput = t => Vector2.zero;
            g.player.SetSpeed(0);
            g.world.Tick();
            Require("drive_crosses_gate_without_teleport", g.player.Pos.z >= boundary + 24f && Content.ZoneIndexAt(g.player.Pos.z) == 1 && Mathf.Abs(g.player.Pos.x - gate.transform.position.x) < 5f,
                "Physical car drive from " + driveStart + " to " + g.player.Pos + " in " + (EditorApplication.timeSinceStartup - driveBegin).ToString("0.00") + " real seconds; samples=" + report.northGateDrive.Count);
            int living = LivingZoneOne();
            Require("zone_1_live_spawns", living > 0, "Targetable living zone1 targets after actual arrival=" + living);
            Require("toxic_wetlands_bundle", ImportedLevel.Wetlands != null && ImportedLevel.Wetlands.Applied && WetlandSurfaces.Active, "Zone1 art bundle and matching driving surfaces are active.");
            yield return WaitReal(0.3f);
            Capture("03-toxic-wetlands-arrival.png");
            g.SaveNow();
            File.WriteAllText(Path.Combine(output, "isolated-save-before-reload.json"), SaveSystem.RawJson() ?? "{}");

            // Reload the real Game scene; TestSetup is removed so the new game must read the saved progression.
            var oldGame = g;
            Game.TestSetup = null;
            reloading = true;
            SceneManager.LoadScene(SceneManager.GetActiveScene().name);
            yield return WaitUntil(() => Game.I != null && Game.I != oldGame && Game.I.Ready, 90f, "Real Game scene reload must complete.");
            reloading = false;
            g = Game.I;
            g.player.turret.enabled = false;
            g.player.harpooner.enabled = false;
            foreach (var arm in g.player.arms) if (arm != null) arm.enabled = false;
            Game.ScriptedInput = t => Vector2.zero;
            Require("reload_keeps_boss_unlock", g.progress.d.bossKills[0] == 1 && g.progress.d.unlockedZone == 1 && g.world.bossSpawns[0].IsDead(Progress.NowMs), "A new Game instance loaded boss kill, zone unlock and Mammoth respawn timer from isolated save.");
            Require("reload_keeps_gate_open", NorthGate().open && !NorthGate().barrier.gameObject.activeSelf && GateCollidersOff(), "Freshly generated World applies the saved open Gate1 state.");
            Require("reload_keeps_zone_1_position", Content.ZoneIndexAt(g.player.Pos.z) == 1, "Reloaded player position=" + g.player.Pos);
            g.world.Tick();
            Require("reload_zone_1_live_spawns", LivingZoneOne() > 0, "Zone1 targets remain live after new World construction.");
            DevOptions.SetSpeed(1f);
            DevOptions.SetJohnWick(false);
            g.RefreshTimeScale();
            RequireScale("final_speed_1", 1f);
            yield return Frames(2);
            Capture("04-reloaded-zone.png");
            File.WriteAllText(Path.Combine(output, "isolated-save-after-reload.json"), SaveSystem.RawJson() ?? "{}");
        }

        static IEnumerator MeasureSpeed(float expected)
        {
            var g = Game.I;
            float t0 = Time.time, u0 = Time.unscaledTime;
            yield return WaitReal(0.4f);
            float elapsed = Time.unscaledTime - u0;
            float ratio = elapsed > 0.001f ? (Time.time - t0) / elapsed : 0;
            Require("scaled_clock_" + expected.ToString("0"), elapsed > 0.1f && Mathf.Abs(ratio - expected) < 0.15f,
                "Measured Time.time/Time.unscaledTime ratio=" + ratio.ToString("0.000") + " over " + elapsed.ToString("0.000") + " unscaled seconds.");
        }

        static IEnumerator PointerInputSmoke()
        {
            var g = Game.I;
            var events = EventSystem.current;
            Require("pointer_event_system", events != null && events.currentInputModule is InputSystemUIInputModule,
                "Production EventSystem uses InputSystemUIInputModule; mouse events below are queued, not direct onClick invocations.");
            // A batch editor has no focused Game View. Use a transient settings clone for this virtual-input test;
            // never edit or dirty the project's InputSettings asset, and restore the original immediately afterwards.
            previousInputSettings = InputSystem.settings;
            smokeInputSettings = UnityEngine.Object.Instantiate(previousInputSettings);
            smokeInputSettings.name = "DevGameplayCheck transient input settings";
            smokeInputSettings.hideFlags = HideFlags.HideAndDontSave;
            smokeInputSettings.editorInputBehaviorInPlayMode = InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;
            smokeInputSettings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            InputSystem.settings = smokeInputSettings;
            previousMouse = Mouse.current;
            smokeMouse = InputSystem.AddDevice<Mouse>("DevGameplayCheckMouse");
            smokeMouse.MakeCurrent();
            playerMouseVersion = 0;
            InputSystem.onAfterUpdate += CapturePlayerMouseState;
            DevOptions.SetJohnWick(false);
            DevOptions.SetSpeed(1f);
            yield return Frames(2);

            yield return PointerClick(g.hud.DevButton, "pointer_dev_button");
            Require("pointer_dev_opens_panel", g.hud.devPanel.IsOpen && g.paused && Time.timeScale == 0f,
                "A queued mouse press/release at the visible Dev button opens the actual modal and pauses gameplay.");
            var card = g.hud.devPanel.transform.Find("Modal/Safe/Card");
            if (card == null) throw new InvalidOperationException("Dev panel card missing after real pointer click.");
            yield return PointerClick((RectTransform)card.Find("Speed4"), "pointer_speed_4");
            Require("pointer_speed_4_selected", DevOptions.Speed == 4f && g.paused && Time.timeScale == 0f,
                "A queued mouse click on Speed4 changes selected speed through the real UI input module while the modal stays paused.");
            yield return PointerClick((RectTransform)card.Find("JohnWick/JohnWickToggle"), "pointer_john_wick");
            Require("pointer_john_wick_enabled", DevOptions.JohnWick, "A queued mouse click on JohnWickToggle enables one-hit mode through EventSystem.");
            yield return PointerClick((RectTransform)card.Find("Done"), "pointer_done");
            Require("pointer_done_closes_panel", !g.hud.devPanel.IsOpen && !g.paused && Mathf.Abs(Time.timeScale - 4f) < 0.001f,
                "A queued mouse click on Done closes the modal and resumes selected speed4.");
            RestorePointerInput();
            DevOptions.SetJohnWick(false);
            yield return Frames(2);
        }

        static IEnumerator PointerClick(RectTransform rect, string name)
        {
            if (rect == null) throw new InvalidOperationException("Pointer click target missing: " + name);
            Canvas.ForceUpdateCanvases();
            var canvas = rect.GetComponentInParent<Canvas>().rootCanvas;
            var eventCamera = canvas.renderMode == RenderMode.ScreenSpaceOverlay ? null : canvas.worldCamera;
            var point = RectTransformUtility.WorldToScreenPoint(eventCamera, rect.TransformPoint(rect.rect.center));
            var events = EventSystem.current;
            var raycasts = new List<RaycastResult>();
            events.RaycastAll(new PointerEventData(events) { position = point }, raycasts);
            var button = rect.GetComponent<Button>();
            var topButton = raycasts.Count > 0 ? raycasts[0].gameObject.GetComponentInParent<Button>() : null;
            Require(name + "_raycast", point.x >= 0 && point.x < Screen.width && point.y >= 0 && point.y < Screen.height && topButton == button,
                "Screen=" + Screen.width + "x" + Screen.height + " point=" + point + " topRaycast=" + (raycasts.Count > 0 ? raycasts[0].gameObject.name : "none") + " expectedButton=" + rect.name);

            InputSystem.QueueStateEvent(smokeMouse, new MouseState { position = point });
            yield return Frames(2);
            int versionBeforePress = playerMouseVersion;
            InputSystem.QueueStateEvent(smokeMouse, new MouseState { position = point }.WithButton(MouseButton.Left));
            yield return Frames(2);
            Require(name + "_press_received", playerMouseVersion > versionBeforePress && playerMousePressed && Vector2.Distance(playerMousePosition, point) < 0.1f,
                "Player input update consumed leftButton=1 at " + playerMousePosition + "; deviceId=" + smokeMouse.deviceId + " update=" + playerMouseUpdateType + " sample=" + playerMouseVersion);
            int versionBeforeRelease = playerMouseVersion;
            InputSystem.QueueStateEvent(smokeMouse, new MouseState { position = point });
            yield return Frames(2);
            Require(name + "_release_received", playerMouseVersion > versionBeforeRelease && !playerMousePressed && Vector2.Distance(playerMousePosition, point) < 0.1f,
                "Player input update consumed leftButton=0 at " + playerMousePosition + "; EventSystem processed a full pointer click; update=" + playerMouseUpdateType);
        }

        static void CapturePlayerMouseState()
        {
            if (smokeMouse == null || !smokeMouse.added) return;
            var update = InputState.currentUpdateType;
            if (update != InputUpdateType.Dynamic && update != InputUpdateType.Fixed && update != InputUpdateType.Manual) return;
            // EditorApplication.update reads the separate EDITOR state buffer (usually position0/buttonUp).
            // Snapshot inside a PLAYER input update, while that update's correct state buffer is selected.
            playerMousePosition = smokeMouse.position.ReadValue();
            playerMousePressed = smokeMouse.leftButton.isPressed;
            playerMouseUpdateType = update;
            playerMouseVersion++;
        }

        static void RestorePointerInput()
        {
            InputSystem.onAfterUpdate -= CapturePlayerMouseState;
            if (smokeMouse != null && smokeMouse.added) InputSystem.RemoveDevice(smokeMouse);
            smokeMouse = null;
            if (previousMouse != null && previousMouse.added) previousMouse.MakeCurrent();
            previousMouse = null;
            if (previousInputSettings != null) InputSystem.settings = previousInputSettings;
            previousInputSettings = null;
            if (smokeInputSettings != null) UnityEngine.Object.DestroyImmediate(smokeInputSettings);
            smokeInputSettings = null;
        }

        static Target Materialize(SpawnPoint spawn)
        {
            if (spawn == null) throw new InvalidOperationException("Required spawn type was not generated.");
            var target = spawn.target;
            if (target == null)
            {
                var create = typeof(World).GetMethod("CreateTarget", AnyInstance);
                if (create == null) throw new MissingMethodException("World.CreateTarget");
                target = (Target)create.Invoke(Game.I.world, new object[] { spawn });
            }
            target.ResetForSpawn(false);
            target.enabled = false; // Stationary test victim; the production Hit/Kill path remains unchanged.
            if (!Game.I.world.activeTargets.Contains(target)) Game.I.world.activeTargets.Add(target);
            return target;
        }

        static SpawnPoint FindSpawn(TargetKind kind)
        {
            foreach (var sp in Game.I.world.zoneSpawns[0]) if (sp.spec.kind == kind && sp.spec.hp > 2 && !sp.IsDead(Progress.NowMs)) return sp;
            return null;
        }
        static void OrdinaryHit(Target target, string name)
        {
            double before = target.hp;
            target.Hit(1, false, Game.I.player.Pos);
            Require(name, !target.dead && target.hp > 0 && Math.Abs(before - target.hp - 1) < 0.001,
                target.spec.name + ": before=" + before + " after=" + target.hp + "; normal hit damage1 with John Wick OFF.");
        }
        static void OneHit(Target target, string name)
        {
            double before = target.hp;
            target.Hit(1, false, Game.I.player.Pos);
            Require(name, target.dead && target.hp == 0 && target.spawn.Kills == 1,
                target.spec.name + ": before=" + before + " after=" + target.hp + "; one production Hit with damage1 and John Wick ON.");
        }
        static Gate NorthGate()
        {
            foreach (var gate in Game.I.world.gates) if (gate.boundary == 1) return gate;
            throw new InvalidOperationException("Gate1 missing.");
        }
        static bool GateCollidersOff()
        {
            foreach (var collider in NorthGate().barrier.GetComponentsInChildren<Collider>(true)) if (collider.enabled) return false;
            return true;
        }
        static int LivingZoneOne()
        {
            int count = 0;
            foreach (var sp in Game.I.world.zoneSpawns[1]) if (sp.target != null && sp.target.Targetable && sp.target.hp > 0) count++;
            return count;
        }
        static void RequireScale(string name, float expected) => Require(name, Mathf.Abs(Time.timeScale - expected) < 0.001f, "Expected Time.timeScale=" + expected + "; actual=" + Time.timeScale + "; selected=" + DevOptions.Speed);
        static void Require(string name, bool passed, string details)
        {
            var g = Game.I;
            report.checks.Add(new Check { name = name, passed = passed, details = details, gameSeconds = g != null ? g.SessionTime : 0,
                timeScale = Time.timeScale, speed = DevOptions.Speed, playerPosition = g != null && g.player != null ? Pos(g.player.Pos) : null });
            Debug.Log("DEV_CHECK " + (passed ? "PASS " : "FAIL ") + name + " | " + details);
            if (!passed) throw new InvalidOperationException("DEV_CHECK failed: " + name + " | " + details);
        }
        static IEnumerator Frames(int count)
        {
            int frame = Time.frameCount + count;
            while (Time.frameCount < frame) yield return null;
        }
        static IEnumerator WaitReal(float seconds)
        {
            double until = EditorApplication.timeSinceStartup + seconds;
            while (EditorApplication.timeSinceStartup < until) yield return null;
        }
        static IEnumerator WaitUntil(Func<bool> ready, float seconds, string reason)
        {
            double until = EditorApplication.timeSinceStartup + seconds;
            while (!ready()) { if (EditorApplication.timeSinceStartup > until) throw new TimeoutException(reason); yield return null; }
        }
        static float[] Pos(Vector3 v) => new[] { v.x, v.y, v.z };

        static void Capture(string filename)
        {
            var g = Game.I;
            var rt = new RenderTexture(540, 1170, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
            rt.Create();
            var previousTarget = g.cam.targetTexture;
            var previousActive = RenderTexture.active;
            foreach (var canvas in UnityEngine.Object.FindObjectsByType<Canvas>(FindObjectsSortMode.None))
            {
                if (!canvas.isRootCanvas || canvas.renderMode != RenderMode.ScreenSpaceOverlay) continue;
                canvas.renderMode = RenderMode.ScreenSpaceCamera;
                canvas.worldCamera = g.cam;
                canvas.planeDistance = g.cam.nearClipPlane + 0.3f + (120 - canvas.sortingOrder) * 0.004f;
            }
            g.cam.targetTexture = rt;
            g.cam.aspect = 540f / 1170f;
            g.cameraRig.Snap();
            Canvas.ForceUpdateCanvases();
            g.cam.Render();
            RenderTexture.active = rt;
            var image = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            image.Apply();
            File.WriteAllBytes(Path.Combine(output, filename), image.EncodeToPNG());
            g.cam.targetTexture = previousTarget;
            RenderTexture.active = previousActive;
            UnityEngine.Object.DestroyImmediate(image);
            rt.Release();
            UnityEngine.Object.DestroyImmediate(rt);
            report.screenshots.Add(filename);
        }
        static void WriteReport() => File.WriteAllText(Path.Combine(output, "dev-gameplay-check.json"), JsonUtility.ToJson(report, true));
        static void Finish(int code)
        {
            RestorePointerInput();
            SessionState.SetInt(FinishKey + ".exit", code);
            SessionState.SetBool(FinishKey, true);
            EditorApplication.update -= Tick;
            if (EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.isPlaying = false;
            else CleanAndExit();
        }
        static void OnPlayState(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.ExitingEditMode || state == PlayModeStateChange.EnteredPlayMode)
            {
                WorkAudioMute.Apply();
                SaveSystem.KeySuffix = SaveSuffix;
                if (!reloading) Game.TestSetup = SetupFresh;
            }
            if (state == PlayModeStateChange.EnteredEditMode && SessionState.GetBool(FinishKey, false)) CleanAndExit();
        }
        static void CleanAndExit()
        {
            int code = SessionState.GetInt(FinishKey + ".exit", 1);
            EditorApplication.update -= Tick;
            EditorApplication.playModeStateChanged -= OnPlayState;
            PlayerPrefs.DeleteKey("roadgame_save_v1" + SaveSuffix);
            PlayerPrefs.Save();
            SaveSystem.KeySuffix = "";
            Game.TestSetup = null;
            Game.ScriptedInput = null;
            Game.Autopilot = false;
            SessionState.EraseString(Key);
            SessionState.EraseBool(FinishKey);
            SessionState.EraseInt(FinishKey + ".exit");
            Time.timeScale = 1f;
            WorkAudioMute.Apply();
            EditorApplication.Exit(code);
        }
        static string Arg(string name, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == name) return args[i + 1];
            return fallback;
        }
    }
}
