using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;
using Unity.Collections;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Batch-mode visual test: enters Play Mode on the Game scene with the autopilot driving,
    /// renders the camera + UI into a portrait render texture and saves PNG screenshots, then quits.
    /// Usage: Unity -batchmode -projectPath P -executeMethod RoadGame.EditorTools.AutoCapture.Run
    ///        -captureOut /abs/dir -captureTimes 2,6,12 -captureScenario start
    /// </summary>
    [InitializeOnLoad]
    public static partial class AutoCapture
    {
        const string Key = "RoadGame.AutoCapture.Config";

        [Serializable]
        class Config
        {
            public string outDir;
            public float[] times;
            public string scenario;
            public int width = 540, height = 1170;
            public int quality = -1;          // -captureQuality: QualitySettings level (0 = Mobile, the phone path)
            public float zoom = -1f;          // -captureZoom: camera zoom override (1 = the normal game camera)
            public int[] levels;              // -captureLevels w0,w1,w2,w3,a0,a1: weapon / armor levels
            public bool perf;                 // -capturePerf: time 60 synchronous renders after every shot
            public string layout;             // -captureLayout /abs/file.json: dump the generated world layout once it is built
            public float videoFrom = -1f, videoTo = -1f;   // -captureVideo a,b: every frame between session seconds a..b -> JPG
            public int fps = 30;              // -captureFps: fixed game step per rendered frame while recording
            public string saveKey = "_capture";   // -captureSaveKey: suffix of the test save (never the player's own save)
            public string keepSave = "";          // -captureKeepSave start|end|both: keep the test save at the start / at the end
        }

        static Config cfg;
        static int nextShot;
        static double startTime = -1;
        static RenderTexture rt;
        static bool prepared;
        static int frames;
        static bool panelOpened;
        static bool snapped;

        static bool armed;

        static AutoCapture()
        {
            // only relevant when domain reload on Play is enabled: re-arm from SessionState
            var json = SessionState.GetString(Key, "");
            if (string.IsNullOrEmpty(json)) return;
            cfg = JsonUtility.FromJson<Config>(json);
            if (cfg == null) return;
            if (EditorApplication.isPlayingOrWillChangePlaymode) Arm();
            else WaitThenPlay();
        }

        static double idleSince = -1;
        static void WaitThenPlay()
        {
            idleSince = -1;
            EditorApplication.update -= WaitTick;
            EditorApplication.update += WaitTick;
        }

        static void WaitTick()
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating) { idleSince = -1; return; }
            if (idleSince < 0) { idleSince = EditorApplication.timeSinceStartup; return; }
            if (EditorApplication.timeSinceStartup - idleSince < 3.0) return;
            EditorApplication.update -= WaitTick;
            Arm();
            EditorApplication.EnterPlaymode();
        }

        static void Arm()
        {
            if (armed) return;
            armed = true;
            SaveSystem.KeySuffix = string.IsNullOrEmpty(cfg.saveKey) ? "_capture" : cfg.saveKey;
            Game.Autopilot = true;
            Game.TestSetup = ApplyScenario;
            EditorApplication.update += Tick;
        }

        public static void Run()
        {
            var args = Environment.GetCommandLineArgs();
            string Arg(string name, string def)
            {
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == name) return args[i + 1];
                return def;
            }
            var c = new Config
            {
                outDir = Arg("-captureOut", Path.GetFullPath("Captures")),
                scenario = Arg("-captureScenario", "start"),
            };
            var ts = Arg("-captureTimes", "2,6,12").Split(',');
            c.times = Array.ConvertAll(ts, s => float.Parse(s, System.Globalization.CultureInfo.InvariantCulture));
            var size = Arg("-captureSize", "540x1170").Split('x');
            c.width = int.Parse(size[0]); c.height = int.Parse(size[1]);
            c.quality = int.Parse(Arg("-captureQuality", "-1"));
            c.zoom = float.Parse(Arg("-captureZoom", "-1"), System.Globalization.CultureInfo.InvariantCulture);
            var lv = Arg("-captureLevels", "");
            if (lv.Length > 0) c.levels = Array.ConvertAll(lv.Split(','), int.Parse);
            c.perf = Arg("-capturePerf", "0") == "1";
            c.layout = Arg("-captureLayout", "");
            var vid = Arg("-captureVideo", "");
            if (vid.Length > 0)
            {
                var vv = vid.Split(',');
                c.videoFrom = float.Parse(vv[0], System.Globalization.CultureInfo.InvariantCulture);
                c.videoTo = float.Parse(vv[1], System.Globalization.CultureInfo.InvariantCulture);
            }
            c.fps = int.Parse(Arg("-captureFps", "30"));
            c.saveKey = Arg("-captureSaveKey", "_capture");
            if (!c.saveKey.StartsWith("_")) c.saveKey = "_" + c.saveKey;
            c.keepSave = Arg("-captureKeepSave", "");
            if (c.scenario == "rocksview") c.times = RockViewTimes();
            if (c.scenario == "terraintour")
            {
                c.times = new float[TerrainStops.Length];
                for (int i = 0; i < c.times.Length; i++) c.times[i] = TourStart + i * TourStep + TourSettle;
            }
            if (c.scenario == "tour")
            {
                // one shot per structure stop: teleport, let the see-through fades settle, shoot
                c.times = new float[TourStops.Length];
                for (int i = 0; i < c.times.Length; i++) c.times[i] = TourStart + i * TourStep + TourSettle;
            }
            WorkAudioMute.Apply();   // work runs are silent (also re-applied on every Play Mode entry)
            if (c.quality >= 0) QualitySettings.SetQualityLevel(c.quality, true);
            Directory.CreateDirectory(c.outDir);
            ProjectSetup.EnsureSetup();
            string testKey = "roadgame_save_v1" + c.saveKey;
            if (c.keepSave != "start" && c.keepSave != "both") PlayerPrefs.DeleteKey(testKey);
            // -captureSave file.json: start from an existing save (e.g. one written by an older version of the game)
            var savePath = Arg("-captureSave", "");
            if (savePath.Length > 0 && File.Exists(savePath))
            {
                PlayerPrefs.SetString(testKey, File.ReadAllText(savePath));
                PlayerPrefs.Save();
                Debug.Log("RoadGame AutoCapture: loaded save file " + savePath);
            }
            SessionState.SetString(Key, JsonUtility.ToJson(c));
            cfg = c;
            EditorSceneManager.OpenScene(ProjectSetup.ScenePath, OpenSceneMode.Single);
            WaitThenPlay();
        }

        /// <summary>Offline render of the engine synth over a scripted drive (idle, launch, shifts, overrun, idle) to a WAV.
        /// Usage: -executeMethod RoadGame.EditorTools.AutoCapture.EngineTest -captureOut /abs/dir</summary>
        public static void EngineTest()
        {
            var args = Environment.GetCommandLineArgs();
            string outDir = Path.GetFullPath("Captures");
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "-captureOut") outDir = args[i + 1];
            Directory.CreateDirectory(outDir);
            const int sr = 48000;
            var synth = new EngineSynth(sr);
            synth.targetVolume = 0.62f;
            // (time, rpm, load) keyframes: idle -> launch (clutch slip) -> shifts -> lift-off overrun -> blip -> idle
            float[,] keys =
            {
                { 0f, 850f, 0f }, { 2.0f, 850f, 0f }, { 2.1f, 3400f, 1f }, { 2.9f, 6150f, 1f }, { 3.05f, 3600f, 0.1f }, { 3.2f, 3600f, 1f },
                { 4.3f, 6150f, 1f }, { 4.45f, 4300f, 0.1f }, { 4.6f, 4300f, 1f }, { 5.9f, 6150f, 1f }, { 6.05f, 4700f, 0.1f }, { 6.2f, 4700f, 1f },
                { 8.0f, 5400f, 1f }, { 8.1f, 5300f, 0f }, { 10.5f, 2200f, 0f }, { 11.5f, 900f, 0f }, { 13.0f, 850f, 0f },
                { 13.1f, 4200f, 0.8f }, { 13.5f, 4500f, 0.8f }, { 13.6f, 4000f, 0f }, { 15.0f, 900f, 0f }, { 16.0f, 850f, 0f }
            };
            int total = (int)(16f * sr);
            var outBuf = new float[total * 2];
            var block = new float[512 * 2];
            int written = 0, k = 0;
            while (written < total)
            {
                float t = written / (float)sr;
                while (k < keys.GetLength(0) - 2 && t > keys[k + 1, 0]) k++;
                float u = Mathf.InverseLerp(keys[k, 0], keys[k + 1, 0], t);
                synth.targetRpm = Mathf.Lerp(keys[k, 1], keys[k + 1, 1], u);
                synth.targetLoad = Mathf.Lerp(keys[k, 2], keys[k + 1, 2], u);
                synth.limiter = false;
                synth.Render(block, 2);
                int n = Math.Min(512, total - written);
                Array.Copy(block, 0, outBuf, written * 2, n * 2);
                written += n;
            }
            var path = Path.Combine(outDir, "engine_test.wav");
            WriteWav(path, outBuf, 2, sr);
            Debug.Log("RoadGame EngineTest: wrote " + path + " pops=" + synth.popCount);
            EditorApplication.Exit(0);
        }

        public static void WriteWav(string path, float[] data, int channels, int sr)
        {
            using (var fs = new FileStream(path, FileMode.Create))
            using (var w = new BinaryWriter(fs))
            {
                int bytes = data.Length * 2;
                w.Write(System.Text.Encoding.ASCII.GetBytes("RIFF")); w.Write(36 + bytes);
                w.Write(System.Text.Encoding.ASCII.GetBytes("WAVE"));
                w.Write(System.Text.Encoding.ASCII.GetBytes("fmt ")); w.Write(16); w.Write((short)1); w.Write((short)channels);
                w.Write(sr); w.Write(sr * channels * 2); w.Write((short)(channels * 2)); w.Write((short)16);
                w.Write(System.Text.Encoding.ASCII.GetBytes("data")); w.Write(bytes);
                foreach (var f in data) w.Write((short)Mathf.Clamp(Mathf.RoundToInt(f * 32767f), -32768, 32767));
            }
        }

        static bool scenarioApplied;

        static void ApplyScenario(Progress p)
        {
            if (scenarioApplied) return;   // a progress reset reloads the scene: the new game must stay new
            scenarioApplied = true;
            Player.DampRebounds = HArg("-reboundDamp") != "0";   // A/B against the raw contact solver
            var d = p.d;
            // a fresh capture save is a new game: only the intro scenarios keep the opening run
            // (a loaded save keeps exactly what it had)
            if (cfg.scenario != "loadsave" && cfg.scenario != "resetcheck") d.introPending = cfg.scenario.StartsWith("intro");
            switch (cfg.scenario)
            {
                case "mid":
                    d.maxHp = d.hp = 900; d.regen = 6; d.dmg[0] = 60; d.weaponLevel[0] = 3;
                    d.tutorialDone = true;
                    break;
                case "death":
                    d.maxHp = 40; d.hp = 12; d.regen = 0; d.dmg[0] = 6; d.tutorialDone = true;
                    d.px = -48f; d.pz = -30f;
                    break;
                case "lowhp":
                    d.maxHp = 300; d.hp = 60; d.regen = 0.5; d.dmg[0] = 20; d.tutorialDone = true;
                    d.px = -60f; d.pz = 10f;
                    break;
                case "garage":
                case "garagefocus":
                case "shop":
                    d.maxHp = d.hp = 640; d.regen = 4.2; d.dmg[0] = 48; d.dmg[1] = 30; d.weaponLevel[0] = 3; d.weaponCopies[0] = 2; d.weaponLevel[1] = 1;
                    d.gems = 380; d.unlockedZone = 1; d.bossKills[0] = 1; d.tutorialDone = true; d.totalKills = 214;
                    break;
                case "zone2":
                    d.maxHp = d.hp = 5000; d.regen = 40; d.dmg[0] = 420; d.dmg[1] = 380; d.weaponLevel[0] = 4; d.weaponLevel[1] = 2;
                    d.unlockedZone = 1; d.bossKills[0] = 1; d.tutorialDone = true;
                    d.px = 22f; d.pz = 112f; d.gems = 120;
                    break;
                case "zone3":
                    d.maxHp = d.hp = 60000; d.regen = 300; d.dmg[0] = 4000; d.dmg[1] = 3500; d.dmg[2] = 3000; d.weaponLevel[0] = 6; d.weaponLevel[1] = 4; d.weaponLevel[2] = 2;
                    d.unlockedZone = 2; d.bossKills[0] = 1; d.bossKills[1] = 1; d.armorLevel[0] = 2; d.tutorialDone = true;
                    d.px = -26f; d.pz = 312f;
                    break;
                case "zone4":
                    d.maxHp = d.hp = 600000; d.regen = 3000; d.dmg[0] = 40000; d.dmg[1] = 35000; d.dmg[2] = 30000; d.dmg[3] = 30000;
                    d.weaponLevel[0] = 9; d.weaponLevel[1] = 6; d.weaponLevel[2] = 4; d.weaponLevel[3] = 2;
                    d.unlockedZone = 3; d.bossKills[0] = d.bossKills[1] = d.bossKills[2] = 1; d.armorLevel[0] = 3; d.armorLevel[1] = 2; d.tutorialDone = true;
                    d.px = 14f; d.pz = 512f;
                    break;
                case "fight":
                case "fightbuggy":
                    d.maxHp = d.hp = 2000; d.regen = 2; d.dmg[0] = 12; d.tutorialDone = true;
                    d.px = -48f; d.pz = -52f;
                    break;
                case "drive":
                case "drivezoom":
                    d.maxHp = d.hp = 5000; d.regen = 10; d.tutorialDone = true;
                    Game.ScriptedInput = t => { var v = DriveScript(t); return Quaternion.Euler(0, 0, -driveBase) * v; };
                    break;
                case "car":
                case "carlow":
                    d.maxHp = d.hp = 900; d.regen = 6; d.dmg[0] = 40; d.dmg[1] = 30; d.weaponLevel[0] = 3; d.weaponLevel[1] = 1; d.tutorialDone = true;
                    break;
                case "boss1":
                    d.maxHp = d.hp = 1500; d.regen = 10; d.dmg[0] = 120; d.weaponLevel[0] = 4; d.tutorialDone = true;
                    d.px = 13f; d.pz = 30f;
                    Game.AutopilotBoss = true;
                    break;
                case "hudstates":
                    // HUD states: rewarded bonus bubble ready, a "new weapon" popup, owned / locked slots
                    d.maxHp = d.hp = 900; d.regen = 6; d.dmg[0] = 40; d.dmg[1] = 30; d.weaponLevel[1] = 1; d.armorLevel[0] = 1; d.tutorialDone = true;
                    d.nextBonusAt = 1; d.gems = 120;
                    Game.ScriptedInput = t => t < 1.2f ? Vector2.zero : (Vector2)(Quaternion.Euler(0, 0, -driveBase) * new Vector2(0f, 0.55f));
                    break;
                case "calm":
                    // a quiet cruise along the main road: no autopilot targets, nothing engaged yet
                    d.maxHp = d.hp = 900; d.regen = 6; d.dmg[0] = 40; d.tutorialDone = true;
                    Game.ScriptedInput = t => t < 1.2f ? Vector2.zero : (Vector2)(Quaternion.Euler(0, 0, -driveBase) * new Vector2(0f, 0.55f));
                    break;
                case "bossfight":
                    d.maxHp = d.hp = 2400; d.regen = 12; d.dmg[0] = 90; d.weaponLevel[0] = 4; d.tutorialDone = true;
                    d.px = 13f; d.pz = 30f;
                    break;
                case "levels":
                    d.maxHp = d.hp = 5000; d.regen = 0; d.dmg[0] = 20; d.tutorialDone = true;
                    Game.ScriptedInput = t => Vector2.zero;
                    break;
                case "loadsave":
                case "resetcheck":
                    Game.ScriptedInput = t => Vector2.zero;
                    break;
                case "introplay":
                case "routetest":
                    GuideSetup(d);
                    break;
                case "reset":
                    // a game well under way on the test save, with settings that differ from the defaults
                    d.maxHp = d.hp = 2600; d.regen = 9; d.dmg[0] = 80; d.dmg[1] = 40;
                    d.weaponLevel[0] = 6; d.weaponLevel[1] = 2; d.weaponCopies[0] = 3; d.weaponCopies[1] = 1;
                    d.armorLevel[0] = 1; d.armorCopies[0] = 1; d.unlockedZone = 1; d.bossKills[0] = 1; d.gems = 777;
                    d.chestsOpened.Add(9001); d.totalKills = 321; d.playTime = 1234; d.tutorialDone = true; d.introPending = false;
                    d.px = 30f; d.pz = 20f; d.heading = 90f;
                    d.freeGemsAt = Progress.NowMs + 3600000L; d.nextBonusAt = Progress.NowMs + 999999L;
                    p.GetOrCreateSpawn(5).kills = 3;
                    d.soundOn = false; d.musicOn = true; d.vibrationOn = false;
                    Game.ScriptedInput = t => Vector2.zero;
                    break;
                case "tour":
                    d.maxHp = d.hp = 1e7; d.regen = 1e5; d.dmg[0] = 6; d.tutorialDone = true; d.unlockedZone = 3;
                    Game.ScriptedInput = t => Vector2.zero;
                    break;
                case "wetlands":
                    WetlandsSetup(p);
                    break;
                case "ashenlevel":
                    AshenLevelSetup(p);
                    break;
                case "devtravel":
                case "devtravelsave":
                case "devtravelreload":
                    DevTravelSetup(p, cfg.scenario);
                    break;
                case "mutants":
                case "ashen":
                    MutantsSetup(p, cfg.scenario == "ashen" ? 2 : 1);
                    break;
                case "handling":
                    HandlingSetup(p);
                    break;
                case "occlusion":
                    OcclusionSetup(p);
                    break;
                case "blenderlevel":
                    BlenderLevelSetup(p);
                    break;
                case "water":
                    WaterSetup(p);
                    break;
                case "waterdrop":
                    WaterDropSetup(p);
                    break;
                case "intro":
                    // a brand-new game, played like a person would: look for a moment, then full stick north
                    Game.ScriptedInput = t => t < 0.9f ? Vector2.zero : (t < 17f ? new Vector2(0f, 1f) : new Vector2(0.15f, 0.7f));
                    break;
                case "jumps":
                    d.maxHp = d.hp = 1e6; d.regen = 1e4; d.dmg[0] = 6; d.tutorialDone = true; d.unlockedZone = 3;
                    Game.ScriptedInput = JumpInput;
                    break;
                case "rocks":
                case "rocksview":
                    d.maxHp = d.hp = 1e7; d.regen = 1e5; d.dmg[0] = 6; d.tutorialDone = true; d.unlockedZone = 3;
                    Game.ScriptedInput = cfg.scenario == "rocks" ? (System.Func<float, Vector2>)RocksInput : (t => Vector2.zero);
                    break;
                case "flip":
                case "terrain":
                case "mesa":
                case "terraintour":
                    // a fixed HP pool without regeneration: a flip must not change it
                    d.maxHp = d.hp = 500; d.regen = 0; d.dmg[0] = 6; d.tutorialDone = true; d.unlockedZone = 3;
                    Game.ScriptedInput = cfg.scenario == "mesa" ? (System.Func<float, Vector2>)MesaInput : (cfg.scenario == "terraintour" ? (t => Vector2.zero) : TerrainInput);
                    break;
                case "underground":
                    d.maxHp = d.hp = 3000; d.regen = 14; d.dmg[0] = 95; d.weaponLevel[0] = 4; d.tutorialDone = true;
                    d.px = 13.6f; d.pz = 30f; d.py = 0f; d.heading = 10f;
                    Game.ScriptedInput = UndergroundInput;
                    break;
                case "pickup":
                case "turns":
                case "lineup":
                case "quasimodo":
                case "cannon":
                case "cannongame":
                case "cannoncheck":
                    d.maxHp = d.hp = 900; d.tutorialDone = true;
                    Game.ScriptedInput = t => Vector2.zero;
                    break;
            }
            if (cfg.levels != null && cfg.levels.Length >= 6)
            {
                for (int i = 0; i < 4; i++) d.weaponLevel[i] = Mathf.Max(i == 0 ? 1 : 0, cfg.levels[i]);
                for (int i = 0; i < 4; i++) if (d.weaponLevel[i] > 0 && d.dmg[i] <= 0) d.dmg[i] = d.dmg[0];
                d.armorLevel[0] = cfg.levels[4]; d.armorLevel[1] = cfg.levels[5];
            }
        }

        /// <summary>Scripted stick for the "drive" test: launch north, hard right, the stick pulled behind the car at
        /// speed (it brakes, then backs up straight), release, a rear diagonal in reverse, then a half-stick cruise.</summary>
        static Vector2 DriveScript(float t)
        {
            if (t < 1.0f) return Vector2.zero;                       // idle
            if (t < 5.0f) return new Vector2(0, 1);                  // full throttle north
            if (t < 7.0f) return new Vector2(1, 0);                  // hard right (east)
            if (t < 11.0f) return new Vector2(-1, 0);                // stick west, behind the car: brake, then straight reverse
            if (t < 12.0f) return Vector2.zero;                      // release: stop and hold
            if (t < 15.0f) return new Vector2(-0.7f, 0.7f) * 0.8f;    // rear diagonal: back up swinging the tail north-west
            if (t < 18.0f) return new Vector2(0.7f, 0.7f) * 0.6f;     // half stick cruise north-east
            return Vector2.zero;
        }

        static float driveBase;
        static bool drivePlaced;
        static AudioTap tap;
        static float nextTelemetry;

        static void PrepareCapture()
        {
            var g = Game.I;
            rt = new RenderTexture(cfg.width, cfg.height, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
            rt.Create();
            g.cam.targetTexture = rt;
            ConvertCanvases();
            prepared = true;
            Debug.Log($"RoadGame AUDIO editorMasterMuted={WorkAudioMute.Apply()} soundSetting={g.progress?.d.soundOn} musicSetting={g.progress?.d.musicOn}");
            if (cfg.scenario.StartsWith("drive") || cfg.scenario == "fight")
            {
                tap = g.cam.gameObject.AddComponent<AudioTap>();
                tap.Begin(40f);
            }
        }

        // ------------------------------------------------------------------ level separation: enemies on the lid above a tunnel
        static int levelsStep;
        static Enemy levelBolter, levelRaider;
        static int levelShots0;
        static double levelHp0;

        static void LevelsTick(Player pl)
        {
            var g = Game.I;
            float t = g.SessionTime;
            if (levelsStep == 0 && t > 1f)
            {
                levelsStep = 1;
                pl.Teleport(new Vector3(46f, Structures.WorksFloor, 42f), 90f);
                g.cameraRig.Snap();
                var z0 = Content.Zones[0];
                SpawnSpec Find(ModelId m) { foreach (var s in z0.specs) if (s.model == m) return s; return null; }
                var b = g.world.AddIntroSpawn(9700, Find(ModelId.Crossbow), new Vector3(44f, 0f, 40.5f), 180f);
                var r = g.world.AddIntroSpawn(9701, Find(ModelId.Raider), new Vector3(49f, 0f, 43.5f), 180f);
                g.world.Tick();
                levelBolter = b.target as Enemy; levelRaider = r.target as Enemy;
                levelShots0 = Projectile.Fired; levelHp0 = g.progress.d.hp;
                Debug.Log($"RoadGame LEVELS car in the tunnel at {pl.Pos}; bolter on the lid at {b.pos}, raider at {r.pos}");
            }
            if (levelsStep == 1 && t > 6f)
            {
                levelsStep = 2;
                var tgt = pl.turret.CurrentTarget;
                Debug.Log($"RoadGame LEVELS underground: bolterEngaged={levelBolter?.Engaged} raiderEngaged={levelRaider?.Engaged} enemyShots={Projectile.Fired - levelShots0} " +
                          $"hpLost={levelHp0 - g.progress.d.hp:0.0} turretTarget={(tgt != null ? tgt.spec.name : "none")}");
                pl.Teleport(new Vector3(47f, 0f, 37.5f), 0f);
                g.cameraRig.Snap();
                levelShots0 = Projectile.Fired; levelHp0 = g.progress.d.hp;
            }
            if (levelsStep == 2 && t > 11f)
            {
                levelsStep = 3;
                var tgt = pl.turret.CurrentTarget;
                Debug.Log($"RoadGame LEVELS surface: bolterEngaged={levelBolter?.Engaged} raiderEngaged={levelRaider?.Engaged} enemyShots={Projectile.Fired - levelShots0} " +
                          $"hpLost={levelHp0 - g.progress.d.hp:0.0} turretTarget={(tgt != null ? tgt.spec.name : "none")} bolterHp={levelBolter?.hp:0}/{levelBolter?.maxHp:0}");
            }
        }

        static bool loadLogged;
        static void LogLoadedSave()
        {
            var g = Game.I;
            if (loadLogged || g == null || !g.Ready || g.progress == null || g.player == null) return;
            loadLogged = true;
            {
                var d = g.progress.d;
                string gates = "";
                foreach (var gt in g.world.gates) gates += gt.boundary + (gt.open ? ":open " : ":closed ");
                var boss = g.world.bossSpawns[0];
                Debug.Log($"RoadGame LOADSAVE car={g.player.Pos} heading={g.player.Heading:0} introPending={d.introPending} introActive={Intro.Active != null} " +
                          $"unlockedZone={d.unlockedZone} bossKills0={d.bossKills[0]} bossDead={boss.IsDead(Progress.NowMs)} bossAt={boss.pos} gates=[{gates}] " +
                          $"hp={d.hp}/{d.maxHp} dmg0={d.dmg[0]} lvl={string.Join(",", d.weaponLevel)} gems={d.gems} spawns={d.spawns.Count} tutorialDone={d.tutorialDone}");
            }
        }

        static void ConvertCanvases()
        {
            var g = Game.I;
            foreach (var canvas in UnityEngine.Object.FindObjectsByType<Canvas>())
            {
                if (!canvas.isRootCanvas || canvas.renderMode != RenderMode.ScreenSpaceOverlay) continue;
                canvas.renderMode = RenderMode.ScreenSpaceCamera;
                canvas.worldCamera = g.cam;
                canvas.planeDistance = g.cam.nearClipPlane + 0.3f + (120 - canvas.sortingOrder) * 0.004f;
            }
        }

        static Game lastGame;

        static void Tick()
        {
            if (!EditorApplication.isPlaying) return;
            if (Game.I == null || Game.I.cam == null) return;
            frames++;
            if (!prepared) { PrepareCapture(); startTime = EditorApplication.timeSinceStartup; lastGame = Game.I; return; }
            if (Game.I != lastGame)
            {
                // the progress reset rebuilt the session: render the new camera into the capture texture
                lastGame = Game.I;
                Game.I.cam.targetTexture = rt;
                snapped = false;
            }
            ConvertCanvases();
            if (!snapped && Game.I.cameraRig != null) { snapped = true; Game.I.cameraRig.Snap(); }
            if (!layoutDumped && !string.IsNullOrEmpty(cfg.layout) && World.I != null && Game.I.Ready) { layoutDumped = true; DumpLayout(cfg.layout); }
            if (cfg.scenario == "loadsave") LogLoadedSave();
            if (cfg.scenario == "reset" || cfg.scenario == "resetcheck") { ResetTick(); return; }
            var pl = Game.I.player;
            if (cfg.scenario == "blenderlevel" && pl != null && Game.I.Ready) BlenderLevelTick(pl);
            if (cfg.scenario == "wetlands" && pl != null && Game.I.Ready) WetlandsTick(pl);
            if ((cfg.scenario == "mutants" || cfg.scenario == "ashen") && pl != null && Game.I.Ready) MutantsTick(pl);
            if (cfg.scenario == "ashenlevel" && pl != null && Game.I.Ready) AshenLevelTick(pl);
            if (cfg.scenario.StartsWith("devtravel", StringComparison.Ordinal) && pl != null && Game.I.Ready) DevTravelTick(pl);
            if (cfg.scenario == "handling" && pl != null && Game.I.Ready) HandlingTick(pl);
            if (cfg.scenario == "occlusion" && pl != null && Game.I.Ready) { OcclusionTick(pl); if (oDone) nextShot = cfg.times.Length; }
            if (pl != null && Game.I.Ready) DriveCsvTick(pl);
            if (cfg.scenario == "water" && pl != null && Game.I.Ready) WaterTick(pl);
            if (cfg.scenario == "waterdrop" && pl != null && Game.I.Ready) WaterDropTick(pl);
            if (cfg.scenario == "levels" && pl != null && Game.I.Ready) LevelsTick(pl);
            if (cfg.scenario == "fightbuggy" && pl != null && !drivePlaced && World.I != null)
            {
                drivePlaced = true;
                foreach (var sp in World.I.zoneSpawns[0])
                {
                    if (sp.spec.model != ModelId.Buggy) continue;
                    pl.Teleport(sp.pos + new Vector3(9f, 0, -6f), 0f);
                    Game.I.cameraRig.Snap();
                    Game.AutopilotEnemiesOnly = true;
                    Debug.Log("RoadGame AutoCapture: fight placed near buggy " + sp.pos);
                    break;
                }
            }
            if (cfg.scenario == "fight" && pl != null && !drivePlaced && World.I != null && World.I.camps[0].Count > 0)
            {
                // park next to the first camp's gate: raiders sprint out, the others shoot
                drivePlaced = true;
                var cp = World.I.camps[0][0];
                var toRoad = (Vector3.zero - cp); toRoad.y = 0; toRoad.Normalize();
                pl.Teleport(cp + toRoad * 15f, Mathf.Atan2(-toRoad.x, -toRoad.z) * Mathf.Rad2Deg);
                Game.I.cameraRig.Snap();
                Game.AutopilotEnemiesOnly = true;
                Debug.Log("RoadGame AutoCapture: fight placed near camp " + cp);
            }
            if (cfg.scenario == "bossfight" && pl != null && !drivePlaced && World.I != null && World.I.bossSpawns[0] != null)
            {
                // start right at the edge of the Mammoth's arena, facing it: the fight begins within a second or two
                drivePlaced = true;
                var bp = World.I.bossSpawns[0].pos;
                var p = bp + new Vector3(6f, 0, -12f);
                var d = bp - p; d.y = 0;
                pl.Teleport(p, Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg);
                Game.I.cameraRig.Snap();
                Game.AutopilotBoss = true;
                Debug.Log("RoadGame AutoCapture: boss fight placed at " + p + " boss " + bp);
            }
            if (cfg.scenario == "lineup" && pl != null && !drivePlaced && World.I != null)
            {
                // every enemy and boss model in two rows in front of the parked car (visual models only, no AI)
                drivePlaced = true;
                Player.AllowOutOfBounds = true;
                var z0 = Content.Zones[0];
                var basePos = new Vector3(-134f, 0, -40f);   // beyond the west cliff: clean ground, no spawns on camera
                pl.Teleport(basePos + new Vector3(0, 0, -7f), 0f);
                var foot = new[] { ModelId.Scav, ModelId.Raider, ModelId.Spearman, ModelId.Crossbow, ModelId.Brute };
                for (int i = 0; i < foot.Length; i++)
                {
                    var go = Models.Create(foot[i], 0, z0, foot[i] == ModelId.Brute ? 1.45f : 1f);
                    go.transform.SetPositionAndRotation(basePos + new Vector3(-6f + i * 3f, 0, 0), Quaternion.Euler(0, 180f, 0));
                }
                var buggy = Models.Create(ModelId.Buggy, 0, z0);
                buggy.transform.SetPositionAndRotation(basePos + new Vector3(9.5f, 0, 0.5f), Quaternion.Euler(0, 200f, 0));
                var bosses = new[] { ModelId.BossMammoth, ModelId.BossBaron, ModelId.BossColossus, ModelId.BossWarlord };
                for (int i = 0; i < bosses.Length; i++)
                {
                    var go = Models.Create(bosses[i], 0, Content.Zones[i]);
                    go.transform.SetPositionAndRotation(basePos + new Vector3(-9.75f + i * 6.5f, 0, 13f), Quaternion.Euler(0, 180f, 0));
                }
                Game.I.cameraRig.target = new GameObject("LineupFocus").transform;
                Game.I.cameraRig.target.position = basePos + new Vector3(0, 0, 0.5f);
                Game.I.cameraRig.Snap();
                Debug.Log("RoadGame AutoCapture: lineup at " + basePos);
            }
            if ((cfg.scenario == "quasimodo" || cfg.scenario == "cannon" || cfg.scenario == "cannoncheck" || cfg.scenario == "pickup" || cfg.scenario == "turns") && pl != null && !drivePlaced && World.I != null)
            {
                Player.AllowOutOfBounds = true;
                // The old west-cliff studio (-134,-40) is under v13's visible
                // terrain. Use the level road, where visual and driving floors agree.
                drivePlaced = true;
                pl.Teleport(new Vector3(0f, 0, -90f), 0f);
                Game.I.cameraRig.Snap();
                Debug.Log("RoadGame AutoCapture: harpooner close-ups");
            }
            if (cfg.scenario == "cannongame" && pl != null && World.I != null && Game.I.Ready) CannonGameTick(pl);
            if (cfg.scenario == "cannoncheck" && pl != null && World.I != null && Game.I.Ready && drivePlaced) CannonCheckTick(pl);
            if ((cfg.scenario.StartsWith("drive") || cfg.scenario == "calm" || cfg.scenario == "hudstates") && pl != null && !drivePlaced && World.I != null)
            {
                // put the car on a long straight piece of the main road (no obstacles), pointing along it
                drivePlaced = true;
                var road = World.I.roads[0][0];
                int i0 = cfg.scenario == "calm" || cfg.scenario == "hudstates" ? road.Count / 9 : road.Count / 3;   // calm: near the start, away from the buggy patrols
                var a = road[i0]; var b2 = road[Mathf.Min(road.Count - 1, i0 + 6)];
                var dir = b2 - a; dir.y = 0;
                driveBase = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                pl.Teleport(new Vector3(a.x, 0, a.z), driveBase);
                Game.I.cameraRig.Snap();
                Debug.Log("RoadGame AutoCapture: drive test placed at " + a + " heading " + driveBase);
            }
            if (cfg.scenario == "intro" && pl != null && Game.ScriptedInput != null && Game.ScriptedInput(Game.I.SessionTime).sqrMagnitude > 0.01f)
                Game.I.OnFirstInput();    // a real thumb on the stick hides the tutorial hint
            if (cfg.scenario == "jumps" && pl != null) JumpTick(pl);
            if (IsGuideScenario(cfg.scenario) && pl != null) GuideTick();
            if (cfg.scenario == "underground" && pl != null) UndergroundTick(pl);
            if (cfg.scenario == "rocks" && pl != null && World.I != null && Game.I.Ready) RocksTick(pl);
            if (IsTerrainScenario(cfg.scenario) && cfg.scenario != "terraintour" && pl != null && World.I != null && Game.I.Ready) TerrainTick(pl);
            if ((cfg.scenario == "intro" || cfg.scenario == "jumps" || cfg.scenario == "underground") && pl != null && Game.I.SessionTime >= nextTelemetry)
            {
                nextTelemetry = Game.I.SessionTime + 0.25f;
                var intro = Intro.Active;
                string fade = "";
                if (OcclusionFader.I != null)
                    foreach (var o in OcclusionFader.I.All) if (o.alpha < 0.99f) fade += $" {o.name}:{o.alpha:0.00}";
                Debug.Log($"RoadGame TELEMETRY t={Game.I.SessionTime:0.00} pos={pl.Pos} v={pl.Speed:0.0} vy={pl.VerticalSpeed:0.0} air={pl.Airborne} ground={pl.GroundY:0.00} under={pl.Underground} hp={Game.I.progress.d.hp:0} " +
                          $"intro={(intro != null ? intro.phase.ToString() : "-")} turret={(pl.turret != null ? pl.turret.Yaw.ToString("0") : "-")} gunShots={Turret.ShotsFired} " +
                          $"gunTarget={(pl.turret != null && pl.turret.CurrentTarget != null ? pl.turret.CurrentTarget.spec.name + "@" + Vector3.Distance(pl.turret.CurrentTarget.Pos, pl.Pos).ToString("0.0") : "-")} fade=[{fade} ]");
            }
            if (cfg.videoFrom >= 0f && pl != null) VideoTick();
            if (cfg.scenario.StartsWith("drive") && pl != null && Game.I.SessionTime >= nextTelemetry)
            {
                nextTelemetry = Game.I.SessionTime + 0.25f;
                var e = pl.rig.body.localEulerAngles;
                Debug.Log($"RoadGame TELEMETRY t={Game.I.SessionTime:0.00} in={Game.ScriptedInput?.Invoke(Game.I.SessionTime)} v={pl.Speed:0.0} u={pl.ForwardSpeed:0.0} rpm={pl.Rpm:0} gear={pl.Gear} thr={pl.Throttle:0.00} load={pl.Load:0.00} slide={pl.Slide:0.00} spin={pl.WheelSpin:0.00} hdg={pl.Heading:0} pitch={Mathf.DeltaAngle(0, e.x):0.0} roll={Mathf.DeltaAngle(0, e.z):0.0} asphalt={pl.OnAsphalt} pos={pl.Pos}");
            }
            if (frames < 5) return;
            double t = EditorApplication.timeSinceStartup - startTime;
            if (cfg.scenario == "blenderlevel" || cfg.scenario == "water" || cfg.scenario == "waterdrop" || cfg.scenario == "wetlands" || cfg.scenario == "mutants" || cfg.scenario == "ashen" || cfg.scenario == "ashenlevel" || cfg.scenario.StartsWith("devtravel", StringComparison.Ordinal) || cfg.scenario == "handling" || cfg.scenario == "occlusion") t = Game.I.SessionTime;
            if (cfg.scenario == "tour" && pl != null && World.I != null)
            {
                int want = (int)((t - TourStart) / TourStep);
                if (want > tourIndex && want < TourStops.Length)
                {
                    tourIndex = want;
                    var st = TourStops[want];
                    pl.Teleport(st.p, st.yaw);
                    Game.I.cameraRig.zoom = st.zoom;
                    Game.I.cameraRig.Snap();
                    World.I.Tick();
                    Debug.Log($"RoadGame TOUR stop={want} {st.name} at {pl.Pos} underground={pl.Underground}");
                }
            }
            if (cfg.scenario == "terraintour" && pl != null && World.I != null) TerrainTourTick(pl, t);
            if (cfg.scenario == "rocksview" && pl != null && World.I != null) RockViewTick(pl, t);
            if (cfg.scenario.StartsWith("drive") || cfg.scenario == "intro" || cfg.scenario == "jumps" || cfg.scenario == "underground" || cfg.scenario == "cannongame"
                || cfg.scenario == "rocks" || (IsTerrainScenario(cfg.scenario) && cfg.scenario != "terraintour") || IsGuideScenario(cfg.scenario)) t = Game.I.SessionTime;
            if (!panelOpened && t > 2.0 && Game.I.hud != null)
            {
                panelOpened = true;
                if (cfg.scenario == "garagefocus") Game.I.hud.panels.ShowGarage(1);
                else if (cfg.scenario.StartsWith("garage")) Game.I.hud.panels.ShowGarage();
                if (cfg.scenario.StartsWith("shop")) Game.I.hud.panels.ShowShop();
                if (cfg.scenario.StartsWith("settings")) Game.I.hud.panels.ShowSettings();
                if (cfg.scenario.StartsWith("death")) Game.I.player.TakeDamage(1e9, Game.I.player.Pos + Vector3.forward);
                if (cfg.scenario.StartsWith("icon")) IconMaker.Render(Path.GetFullPath("Assets/RoadGame/Art/AppIcon.png"));
                if (cfg.scenario == "hudstates") Game.I.hud.ShowPopup(Tex.DamageIcon(DamageType.Smash), "NEW WEAPON!", Content.Weapons[1].name);
                if (cfg.scenario == "drivezoom" || cfg.scenario.StartsWith("fight")) Game.I.cameraRig.zoom = 0.55f;
                if (cfg.scenario.StartsWith("carlow")) { Game.I.cameraRig.zoom = 0.36f; Game.I.cameraRig.pitch = 26f; }
                else if (cfg.scenario.StartsWith("car")) Game.I.cameraRig.zoom = 0.33f;
                if (cfg.zoom > 0f) Game.I.cameraRig.zoom = cfg.zoom;
            }
            if (nextShot < cfg.times.Length && t >= cfg.times[nextShot])
            {
                Shoot(nextShot);
                nextShot++;
            }
            if (nextShot >= cfg.times.Length)
            {
                EditorApplication.update -= Tick;
                if (tap != null)
                {
                    var rec = tap.Take();
                    WriteWav(Path.Combine(cfg.outDir, cfg.scenario + "_audio.wav"), rec, tap.channels, tap.SampleRate);
                    Debug.Log("RoadGame AutoCapture: audio " + rec.Length / Mathf.Max(1, tap.channels) + " frames @" + tap.SampleRate + " ch=" + tap.channels);
                }
                SessionState.EraseString(Key);
                if (cfg.scenario == "blenderlevel") BlenderLevelFinish();
                if (cfg.scenario == "wetlands") WetlandsFinish();
                if (cfg.scenario == "mutants" || cfg.scenario == "ashen") MutantsFinish();
                if (cfg.scenario == "ashenlevel") AshenLevelFinish();
                if (cfg.scenario.StartsWith("devtravel", StringComparison.Ordinal)) DevTravelFinish();
                if (cfg.scenario == "handling") HandlingFinish();
                if (cfg.scenario == "occlusion") OcclusionFinish();
                DriveCsvFinish();
                if (cfg.scenario == "water") WaterFinish();
                if (cfg.scenario == "waterdrop") WaterDropFinish();
                if (cfg.keepSave != "end" && cfg.keepSave != "both") PlayerPrefs.DeleteKey("roadgame_save_v1" + cfg.saveKey);
                PlayerPrefs.Save();
                Debug.Log("RoadGame AutoCapture: done, " + cfg.times.Length + " shots in " + cfg.outDir);
                EditorApplication.Exit(0);
            }
        }

        // close-up views of the harpoon operator: (turret yaw on the car, recoil, camera azimuth from his facing, camera
        // elevation, distance in m, field of view). Azimuth 0 = in front of his face (he faces the turret's column).
        static readonly float[,] CloseViews =
        {
            { 0f, 0f, 24f, 8f, 2.2f, 28f },       // portrait, 3/4 front: the face in the hood, hands on the handles
            { 0f, 0f, 90f, 6f, 2.6f, 28f },       // profile: hunch, hood, arms to the handles
            { 20f, 1f, 32f, 14f, 2.7f, 28f },     // firing: recoil, body kicked back, hands still on the handles
            { 0f, 0f, 165f, 38f, 3.0f, 28f },     // from behind and above: hood, cloak, holes, frayed hem
            { 90f, 0f, 130f, 34f, 4.2f, 30f },    // turret to the side: he stands by the other bed wall
            { 180f, 0f, 35f, 30f, 4.2f, 30f },    // turret aiming back: he stands at the cab's back wall
        };
        static Camera closeCam;

        // the whole pickup at the concept sheet's angles: (harpoon turret yaw, gun yaw, gun recoil, camera azimuth from
        // the car's nose, elevation, distance, fov); focus = the middle of the car. 6 views per gun tier.
        static readonly float[,] PickupViews =
        {
            { 0f, -12f, 0f, 38f, 28f, 7.0f, 30f },        // three quarters from the front right (the gun's side)
            { 0f, -12f, 0f, 148f, 30f, 7.0f, 30f },       // three quarters from behind: tailgate, bed, turret, operator
            { 0f, 0f, 0f, 0f, 89.5f, 10.5f, 30f },        // straight from above, nose up
            { 0f, 0f, 0f, 90f, 6f, 9.0f, 30f },           // right profile
            { 110f, 70f, 1f, -40f, 34f, 9.0f, 30f },      // both turned: operator at the bed's side wall, the gun firing right
            { 180f, -155f, 1f, -150f, 30f, 9.0f, 30f },   // the harpoon aiming back, the gun firing back over the cab
        };

        // turning: the gun at several yaws in its firing pose (camera over the hood), then the harpoon turret at several
        // yaws (camera over the bed): (what: 0 = gun / 1 = harpoon, yaw, camera azimuth from the nose, elevation, distance)
        static readonly float[,] TurnViews =
        {
            { 0f, -150f, 20f, 58f, 3.4f }, { 0f, -90f, 20f, 58f, 3.4f }, { 0f, -40f, 20f, 58f, 3.4f }, { 0f, 0f, 20f, 58f, 3.4f },
            { 0f, 45f, 20f, 58f, 3.4f }, { 0f, 100f, 20f, 58f, 3.4f }, { 0f, 160f, 20f, 58f, 3.4f },
            { 1f, 0f, 170f, 52f, 5.2f }, { 1f, 60f, 170f, 52f, 5.2f }, { 1f, 120f, 170f, 52f, 5.2f }, { 1f, 180f, 170f, 52f, 5.2f },
            { 1f, -120f, 170f, 52f, 5.2f }, { 1f, -60f, 170f, 52f, 5.2f },
        };

        static void RenderTurn(int index)
        {
            var g = Game.I;
            int v = Mathf.Min(index, TurnViews.GetLength(0) - 1);
            bool gun = TurnViews[v, 0] < 0.5f;
            if (gun) { g.player.turret.PoseForCapture(0, TurnViews[v, 1], 0f, 1f); g.player.harpooner.PoseForCapture(0f, 0f); }
            else { g.player.turret.PoseForCapture(0, 0f, 0f, 0f); g.player.harpooner.PoseForCapture(TurnViews[v, 1], 0f); }
            EnsureCloseCam(g);
            closeCam.fieldOfView = 30f;
            var focus = g.player.rig.body.TransformPoint(gun ? Models.GunMount + new Vector3(-0.2f, 0.1f, 0.15f) : new Vector3(0f, 1.0f, -1.45f));
            var fwd = g.player.transform.forward; fwd.y = 0; fwd.Normalize();
            var dir = Quaternion.AngleAxis(TurnViews[v, 2], Vector3.up) * fwd;
            dir = Quaternion.AngleAxis(TurnViews[v, 3], Vector3.Cross(dir, Vector3.up)) * dir;
            closeCam.transform.position = focus + dir * TurnViews[v, 4];
            closeCam.transform.LookAt(focus);
            closeCam.Render();
            Debug.Log($"RoadGame TURN shot={index} {(gun ? "gun" : "harpoon")} yaw={TurnViews[v, 1]:0} gunPitch={g.player.turret.Pitch:0.0} fireLimit={Turret.FireLimit(TurnViews[v, 1]):0.0}");
        }

        static void RenderPickup(int index)
        {
            var g = Game.I;
            int n = PickupViews.GetLength(0);
            int v = index % n, tier = Mathf.Clamp(index / n, 0, 3);
            g.player.turret.PoseForCapture(tier, PickupViews[v, 1], 0f, PickupViews[v, 2]);
            g.player.harpooner.PoseForCapture(PickupViews[v, 0], 0f);
            EnsureCloseCam(g);
            closeCam.fieldOfView = PickupViews[v, 6];
            var focus = g.player.rig.body.TransformPoint(new Vector3(0f, 0.95f, 0f));
            var fwd = g.player.transform.forward; fwd.y = 0; fwd.Normalize();
            var dir = Quaternion.AngleAxis(PickupViews[v, 3], Vector3.up) * fwd;
            dir = Quaternion.AngleAxis(PickupViews[v, 4], Vector3.Cross(dir, Vector3.up)) * dir;
            closeCam.transform.position = focus + dir * PickupViews[v, 5];
            closeCam.transform.LookAt(focus, PickupViews[v, 4] > 85f ? fwd : Vector3.up);
            closeCam.Render();
            Debug.Log($"RoadGame PICKUP shot={index} tier={tier} view={v} gunYaw={g.player.turret.Yaw:0} gunPitch={g.player.turret.Pitch:0.0} harpoonYaw={g.player.harpooner.Yaw:0}");
        }

        // hood machine gun close-ups: (gun yaw, pitch (+ = down, clamped like the real aim), recoil, camera azimuth from
        // the car's nose, elevation, distance, fov). Every view is rendered for the 4 upgrade tiers (shot / views = tier).
        // The focus is a fixed point over the gun's base, so the views compare across tiers.
        static readonly float[,] CannonViews =
        {
            { -10f, 0f, 0f, 35f, 26f, 2.4f, 30f },      // 3/4 front right: the gun beside the blower
            { 0f, 0f, 0f, 90f, 6f, 2.4f, 30f },         // right profile: low base, long receiver, small stock
            { -55f, 0f, 1f, -25f, 30f, 2.8f, 30f },     // firing to the left over the blower (flash, kick)
            { 165f, 0f, 1f, 140f, 28f, 3.2f, 30f },     // firing back over the cab
            { 25f, 0f, 0f, 60f, 16f, 1.3f, 30f },       // tight close-up of the gun
            { 0f, 0f, 0f, 0f, 88f, 2.6f, 30f },         // from above
        };

        static void RenderCannon(int index)
        {
            var g = Game.I;
            int v = index % CannonViews.GetLength(0), tier = Mathf.Clamp(index / CannonViews.GetLength(0), 0, 3);
            g.player.turret.PoseForCapture(tier, CannonViews[v, 0], CannonViews[v, 1], CannonViews[v, 2]);
            g.player.harpooner.PoseForCapture(0f, 0f);
            EnsureCloseCam(g);
            closeCam.fieldOfView = CannonViews[v, 6];
            var focus = g.player.rig.body.TransformPoint(Models.GunMount + new Vector3(-0.08f, 0.13f, 0.06f));
            var fwd = g.player.transform.forward; fwd.y = 0; fwd.Normalize();
            var dir = Quaternion.AngleAxis(CannonViews[v, 3], Vector3.up) * fwd;
            dir = Quaternion.AngleAxis(CannonViews[v, 4], Vector3.Cross(dir, Vector3.up)) * dir;
            closeCam.transform.position = focus + dir * CannonViews[v, 5];
            closeCam.transform.LookAt(focus, CannonViews[v, 4] > 85f ? fwd : Vector3.up);
            closeCam.Render();
            Debug.Log($"RoadGame CANNON shot={index} tier={tier} view={v} yaw={g.player.turret.Yaw:0} pitch={g.player.turret.Pitch:0.0}");
        }

        // the pickup from the normal game camera: (car heading, camera zoom (1 = the game's), tier, gun yaw, gun pitch,
        // recoil, harpoon turret yaw). The car is parked on the straight canyon road south of the Dust Flats (no enemies
        // there without the intro).
        static readonly float[,] GameViews =
        {
            { 0f, 1f, 0f, 0f, 0f, 0f, 0f },            // driving up the screen, gun and harpoon ahead
            { 0f, 1f, 3f, 0f, 0f, 0f, 0f },
            { 0f, 0.45f, 0f, 0f, 0f, 0f, 0f },         // closer zoom, same pose
            { 0f, 0.45f, 3f, 0f, 0f, 0f, 0f },
            { 90f, 0.45f, 0f, -35f, 0f, 1f, -40f },    // facing right, the gun firing ahead-left, the harpoon turned
            { 90f, 0.45f, 3f, -35f, 0f, 1f, -40f },
            { 205f, 0.45f, 0f, 25f, 0f, 0f, 160f },    // coming toward the camera, the harpoon aiming back
            { 205f, 0.45f, 3f, 25f, 0f, 0f, 160f },
            { 315f, 1f, 0f, 60f, 0f, 1f, 90f },        // normal zoom, firing to the side
            { 315f, 1f, 3f, 60f, 0f, 1f, 90f },
        };
        static int cannonGamePlaced = -1;

        static void CannonGameTick(Player pl)
        {
            float now = Game.I.SessionTime;
            int next = cannonGamePlaced + 1;
            if (next >= cfg.times.Length || next >= GameViews.GetLength(0) || now < cfg.times[next] - 0.9f) return;
            cannonGamePlaced = next;
            Player.AllowOutOfBounds = true;
            pl.Teleport(new Vector3(0f, 0f, -212f), GameViews[next, 0]);
            Game.I.cameraRig.zoom = GameViews[next, 1];
            Game.I.cameraRig.Snap();
        }

        static void RenderCannonGame(int index)
        {
            var g = Game.I;
            int v = Mathf.Min(index, GameViews.GetLength(0) - 1);
            g.player.turret.PoseForCapture((int)GameViews[v, 2], GameViews[v, 3], GameViews[v, 4], GameViews[v, 5]);
            g.player.harpooner.PoseForCapture(GameViews[v, 6], 0f);
            g.cam.Render();
            Debug.Log($"RoadGame CANNONGAME shot={index} heading={g.player.Heading:0} zoom={GameViews[v, 1]} tier={GameViews[v, 2]} yaw={g.player.turret.Yaw:0} pitch={g.player.turret.Pitch:0.0} harpoonYaw={g.player.harpooner.Yaw:0}");
        }

        // ------------------------------------------------------------------ clearance of the hood gun and the harpoon turret ("cannoncheck")
        // Collision copies of the car's own meshes (body, details, wheels on one layer; the harpoon turret and its operator
        // on another), then
        // 1) for every yaw (-180..180 every 2 deg: the gun sits on the right, so the sides differ) the lowest pitch at which
        //    all gun / cradle parts (resting), the muzzle flash and a round's adaptive straight launch run (firing)
        //    clear the car and the harpoon operator, and the highest raise the moving parts allow; compared with the implemented limits
        //    (Turret.MaxDownBarrel / Turret.FireLimit / Turret.MaxUp); one GUNCHECK line per yaw,
        // 2) the resting pose at every degree of yaw,
        // 3) the real aim at targets all round the car (3..9.5 m, low and high): gun parts, launch run and the rest of the
        //    round's path against the car, and separately against the harpoon turret / operator,
        // 4) the harpoon turret and its operator against the car (bed floor and walls, cab, roof): every edge of their
        //    meshes is line-cast against the car's surfaces at every 3 deg of the turret's yaw (and recoiling every 15).
        const int CheckBodyLayer = 30, CheckCrewLayer = 31;
        static bool cannonChecked;

        static void CannonCheckTick(Player pl)
        {
            if (cannonChecked || Game.I.SessionTime < 2.5f) return;
            cannonChecked = true;
            try { CannonClearance(pl); }
            catch (Exception e) { Debug.LogException(e); }
        }

        // DetailedCar: conservative convex envelopes of parts_gun.py, in Unity metres (+Y up, +Z forward).
        // Every polygon of the authored GunMesh (10,808) and GunCradle (1,704) is wholly inside at least one
        // primitive below. Boxes keep the rectangular receiver / spade grips / ammo can tighter than capsules.
        // The recoiling envelopes include the complete 0.05 m stroke, even while measuring a resting pose.
        const float CheckGunRecoil = 0.05f;
        readonly struct GunCapsule
        {
            public readonly Vector3 a, b;
            public readonly float radius;
            public GunCapsule(Vector3 a, Vector3 b, float radius) { this.a = a; this.b = b; this.radius = radius; }
        }
        readonly struct GunBox
        {
            public readonly Vector3 centre, half;
            public GunBox(Vector3 centre, Vector3 half) { this.centre = centre; this.half = half; }
        }

        static readonly GunCapsule[] GunFront =
        {
            new GunCapsule(new Vector3(0f, .055f, .165f), new Vector3(0f, .055f, .259f), .079f), // collar / notched nut
            new GunCapsule(new Vector3(0f, .055f, .257f), new Vector3(0f, .055f, .652f), .063f), // jacket / clamp rings
            new GunCapsule(new Vector3(0f, .055f, .644f), new Vector3(0f, .055f, .919f), .039f), // exposed barrel
            new GunCapsule(new Vector3(0f, .055f, .740f), new Vector3(0f, .055f, .790f), .049f), // gas block
            new GunCapsule(new Vector3(0f, .055f, .901f), new Vector3(0f, .055f, 1.020f), .053f), // muzzle brake
        };
        static readonly GunBox[] GunFrontBoxes =
        {
            new GunBox(new Vector3(.0115f, .0555f, -.0775f), new Vector3(.1045f, .1195f, .2495f)), // receiver, cover, rear sight, handles, back plate
            new GunBox(new Vector3(0f, .0545f, .522f), new Vector3(.023f, .0855f, .264f)), // gas tube, underside lug, front sight
        };
        static readonly GunBox[] GunRearBoxes =
        {
            new GunBox(new Vector3(0f, .018f, -.3705f), new Vector3(.080f, .092f, .0575f)), // spade grips, braces, buffer, trigger
        };
        static readonly GunCapsule[] GunCradleCapsules =
        {
            new GunCapsule(new Vector3(-.141f, 0f, 0f), new Vector3(.141f, 0f, 0f), .029f), // pin and end nuts
        };
        static readonly GunBox[] GunCradleBoxes =
        {
            new GunBox(new Vector3(0f, -.020f, -.020f), new Vector3(.088f, .063f, .164f)), // cheeks and tray
            new GunBox(new Vector3(-.193f, -.0055f, -.030f), new Vector3(.062f, .098f, .115f)), // ammo can, lid, ribs, handle
            new GunBox(new Vector3(-.1275f, .094f, -.055f), new Vector3(.058f, .054f, .041f)), // curved belt chute
        };

        static Vector3 AbsScale(Transform t)
        {
            var s = t.lossyScale;
            return new Vector3(Mathf.Abs(s.x), Mathf.Abs(s.y), Mathf.Abs(s.z));
        }

        static bool Capsules(Transform t, GunCapsule[] parts, int mask, float recoil = 0f)
        {
            var scale = AbsScale(t);
            float radiusScale = Mathf.Max(scale.x, Mathf.Max(scale.y, scale.z));
            foreach (var part in parts)
            {
                var a = part.a; var b = part.b;
                // Recoiling capsules are parallel to the bore. Extending the rear endpoint encloses every
                // intermediate position of the stroke exactly; the non-recoiling cradle's pin needs no sweep.
                if (recoil > 0f) { if (a.z <= b.z) a.z -= recoil; else b.z -= recoil; }
                if (Physics.CheckCapsule(t.TransformPoint(a), t.TransformPoint(b), part.radius * radiusScale, mask, QueryTriggerInteraction.Ignore)) return true;
            }
            return false;
        }

        static bool Boxes(Transform t, GunBox[] parts, int mask, float recoil = 0f)
        {
            var scale = AbsScale(t);
            foreach (var part in parts)
            {
                var centre = part.centre; var half = part.half;
                centre.z -= recoil * .5f; half.z += recoil * .5f;
                if (Physics.CheckBox(t.TransformPoint(centre), Vector3.Scale(half, scale), t.rotation, mask, QueryTriggerInteraction.Ignore)) return true;
            }
            return false;
        }

        static bool GunRearHit(Turret tur, int mask) => Boxes(tur.Barrel, GunRearBoxes, mask, CheckGunRecoil);
        static bool GunCradleHit(Turret tur, int mask) => Capsules(tur.Barrel.parent, GunCradleCapsules, mask)
            || Boxes(tur.Barrel.parent, GunCradleBoxes, mask);
        static bool GunPartsHit(Turret tur, int mask) => Capsules(tur.Barrel, GunFront, mask, CheckGunRecoil)
            || Boxes(tur.Barrel, GunFrontBoxes, mask, CheckGunRecoil) || GunRearHit(tur, mask) || GunCradleHit(tur, mask);

        static bool FlashHits(Turret tur, int mask)
        {
            var g = tur.Barrel;
            var fwd = g.forward;
            var m = g.TransformPoint(new Vector3(0f, Models.GunBoreY, Models.GunMuzzleZ + 0.004f));
            const QueryTriggerInteraction Q = QueryTriggerInteraction.Ignore;
            // the flash at its largest (x1.15): a star 0.15 long and 0.025 wide, a burst 0.035 round the bore
            // Swept flash: the rear endpoint also covers maximum recoil, while its forward extent is at rest.
            return Physics.CheckCapsule(m - fwd * CheckGunRecoil, m + fwd * 0.15f, 0.03f, mask, Q)
                || Physics.CheckCapsule(m - fwd * CheckGunRecoil, m + fwd * 0.046f, 0.04f, mask, Q);
        }

        static bool RunHits(Turret tur, int mask, out Vector3 muzzle, out Vector3 kink)
        {
            muzzle = tur.Muzzle;
            kink = muzzle + tur.Barrel.forward * tur.StraightRun;
            return Physics.CheckCapsule(muzzle - tur.Barrel.forward * CheckGunRecoil, kink, 0.02f, mask, QueryTriggerInteraction.Ignore);
        }

        /// <summary>Lowest safe pitch (+ = down) at a yaw: scans from level-ish raised downward until the test fails.</summary>
        static float SafeDown(Turret tur, float yawDeg, Func<bool> blocked)
        {
            float last = -99f;
            for (float p = -30f; p <= 20.001f; p += 0.5f)
            {
                tur.PoseForCapture(3, yawDeg, p, 0f, false);
                if (blocked())
                {
                    // A raised spade grip / ammo can can touch before the first safe pitch. Find the safe
                    // interval before measuring its downward edge; SafeUp independently checks the raise limit.
                    if (last > -90f) return last;
                }
                else last = p;
            }
            return last;
        }

        /// <summary>Highest safe raise (most negative pitch): includes the receiver, spade grips and fixed cradle.</summary>
        static float SafeUp(Turret tur, float yawDeg, Func<bool> blocked)
        {
            float last = 99f;
            for (float p = 0f; p >= -40.001f; p -= 0.5f)
            {
                tur.PoseForCapture(3, yawDeg, p, 0f, false);
                if (blocked()) return last;
                last = p;
            }
            return -40f;
        }

        static void CannonClearance(Player pl)
        {
            var tur = pl.turret;
            // the sprung body at rest (no heave, tilt or squash from the suspension): exact collision copies
            pl.rig.body.localPosition = Vector3.zero;
            pl.rig.body.localRotation = Quaternion.identity;
            pl.rig.body.localScale = Vector3.one;
            Physics.SyncTransforms();
            var colRoot = new GameObject("ClearanceColliders");
            int nBody = 0, nCrew = 0;
            var crewRoot = pl.harpooner != null ? pl.harpooner.Rig.root : null;
            foreach (var mf in pl.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null || !mf.gameObject.activeInHierarchy || mf.name == "LOD1" || mf.name == "LOD2") continue; // full authored LOD0 only
                var rend = mf.GetComponent<Renderer>();
                if (rend == null || !rend.enabled) continue;
                if (mf.transform.IsChildOf(tur.transform)) continue;   // the gun itself, its base plate too
                bool crew = crewRoot != null && mf.transform.IsChildOf(crewRoot);
                var go = new GameObject("C_" + mf.name);
                go.layer = crew ? CheckCrewLayer : CheckBodyLayer;
                go.transform.SetPositionAndRotation(mf.transform.position, mf.transform.rotation);
                go.transform.localScale = mf.transform.lossyScale;
                go.transform.SetParent(colRoot.transform, true);
                go.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                if (crew) nCrew++; else nBody++;
            }
            Physics.SyncTransforms();
            int bodyMask = 1 << CheckBodyLayer, crewMask = 1 << CheckCrewLayer;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            Debug.Log($"RoadGame CANNONCHECK colliders body={nBody} crew={nCrew} mount={Models.GunMount} pivotY={Models.GunPivotY} boreY={Models.GunBoreY} muzzleZ={Models.GunMuzzleZ} buttZ={Models.GunButtZ} proxies=DetailedCarV10 recoilSweep={CheckGunRecoil}");

            // 1) per-yaw safe dip / raise vs the implemented limits
            float worst = 99f, worstRest = 99f, worstUp = 99f; string worstAt = "", worstRestAt = "", worstUpAt = "";
            var sb = new System.Text.StringBuilder("RoadGame CANNONCHECK table (yaw: gun/flash/run -> safe | fire limit margin | gun limit margin | raise limit | crewGun/crewSafe)");
            for (int yi = -90; yi <= 90; yi++)
            {
                float ya = yi * 2f;
                float sBar = SafeDown(tur, ya, () => GunPartsHit(tur, bodyMask));
                float sFl = SafeDown(tur, ya, () => FlashHits(tur, bodyMask));
                float sRun = SafeDown(tur, ya, () => RunHits(tur, bodyMask, out _, out _));
                float sUp = SafeUp(tur, ya, () => GunPartsHit(tur, bodyMask) || GunPartsHit(tur, crewMask));
                float sCrewGun = SafeDown(tur, ya, () => GunPartsHit(tur, crewMask));
                float sCrew = SafeDown(tur, ya, () => GunPartsHit(tur, crewMask) || FlashHits(tur, crewMask) || RunHits(tur, crewMask, out _, out _));
                float safeGun = Mathf.Min(sBar, sCrewGun);
                float safe = Mathf.Min(safeGun, Mathf.Min(sCrew, Mathf.Min(sFl, sRun)));
                float lim = Turret.FireLimit(ya), limRest = Turret.MaxDownBarrel(ya);
                float margin = safe - lim, marginRest = safeGun - limRest, marginUp = Turret.MaxUp - sUp;
                if (margin < worst) { worst = margin; worstAt = $"yaw {ya:0}"; }
                if (marginRest < worstRest) { worstRest = marginRest; worstRestAt = $"yaw {ya:0}"; }
                if (marginUp < worstUp) { worstUp = marginUp; worstUpAt = $"yaw {ya:0}"; }
                Debug.Log(string.Format(inv, "RoadGame GUNCHECK yaw={0:0} gun={1:0.0} flash={2:0.0} run={3:0.0} up={4:0.0} crewGun={5:0.0} crew={6:0.0}", ya, sBar, sFl, sRun, sUp, sCrewGun, sCrew));
                if (yi % 5 == 0 || margin < 0f || marginRest < 0f || marginUp < 0f)
                    sb.Append($"\n  {ya,5:0}: {sBar,6:0.0}/{sFl,6:0.0}/{sRun,6:0.0} -> {safe,6:0.0} | {lim,6:0.0} {(margin < 0f ? "BLOCKED " : "ok ")}{margin,5:0.0} | {limRest,6:0.0} {(marginRest < 0f ? "BLOCKED " : "ok ")}{marginRest,5:0.0} | {sUp,6:0.0} {(marginUp < 0f ? "BLOCKED " : "ok ")}{marginUp,5:0.0} | {sCrewGun,6:0.0}/{sCrew,6:0.0}");
            }
            Debug.Log(sb.ToString());
            Debug.Log($"RoadGame CANNONCHECK limits fire worstMargin={worst:0.0} deg at {worstAt}, gun worstMargin={worstRest:0.0} deg at {worstRestAt}, raise worstMargin={worstUp:0.0} deg at {worstUpAt} (negative = the gun could touch the car)");

            // 2) resting pose (level, kept clear of the car) at every degree of yaw
            int restHits = 0;
            for (int yd = 0; yd < 360; yd++)
            {
                float yawDeg = yd;
                tur.PoseForCapture(3, yawDeg, Mathf.Clamp(0f, Turret.MaxUp, Turret.MaxDownBarrel(yawDeg)), 0f, false);
                if (GunPartsHit(tur, bodyMask) || GunPartsHit(tur, crewMask)) restHits++;
            }
            Debug.Log($"RoadGame CANNONCHECK rest poses=360 touching={restHits}");

            // 3) the real aim at targets round the car
            int cases = 0, partHits = 0, runHits = 0, pathHits = 0, crewHits = 0;
            var pathList = new System.Text.StringBuilder();
            var crewList = new System.Text.StringBuilder();
            float minPitch = 99f, maxPitch = -99f, minRun = float.PositiveInfinity, maxRun = 0f;
            for (int bi = 0; bi < 72; bi++)
            {
                float bearing = bi * 5f;
                var dir = Quaternion.Euler(0f, bearing, 0f) * pl.transform.forward;
                dir.y = 0f; dir.Normalize();
                foreach (float dist in new[] { 3f, 5f, 7.5f, 9.5f })
                    foreach (float h in new[] { 0.5f, 1.1f })
                    {
                        var aim = pl.Pos + dir * dist;
                        aim.y = pl.GroundY + h;
                        Turret.SolveAim(tur.transform.InverseTransformPoint(aim), out float y, out float p);
                        p = Mathf.Clamp(p, Turret.MaxUp, Turret.FireLimit(y));
                        minPitch = Mathf.Min(minPitch, p); maxPitch = Mathf.Max(maxPitch, p);
                        tur.PoseForCapture(3, y, p, 0f, false);
                        cases++;
                        bool parts = GunPartsHit(tur, bodyMask) || FlashHits(tur, bodyMask);
                        bool run = RunHits(tur, bodyMask, out var muzzle, out var kink);
                        float straightRun = tur.StraightRun;
                        minRun = Mathf.Min(minRun, straightRun); maxRun = Mathf.Max(maxRun, straightRun);
                        bool path = Physics.CheckCapsule(kink, aim, 0.02f, bodyMask, QueryTriggerInteraction.Ignore);
                        bool crew = GunPartsHit(tur, crewMask) || FlashHits(tur, crewMask) || RunHits(tur, crewMask, out _, out _)
                                    || Physics.CheckCapsule(kink, aim, 0.02f, crewMask, QueryTriggerInteraction.Ignore);
                        if (parts) { partHits++; Debug.Log($"RoadGame CANNONCHECK touch bearing={bearing:0} dist={dist} h={h} yaw={y:0.0} pitch={p:0.0} limit={Turret.FireLimit(y):0.0} parts={GunPartsHit(tur, bodyMask)} rear={GunRearHit(tur, bodyMask)} cradle={GunCradleHit(tur, bodyMask)} flash={FlashHits(tur, bodyMask)}"); }
                        if (run) { runHits++; Debug.Log($"RoadGame CANNONCHECK run touch bearing={bearing:0} dist={dist} h={h} yaw={y:0.0} pitch={p:0.0} limit={Turret.FireLimit(y):0.0}"); }
                        if (path) { pathHits++; pathList.Append($" {bearing:0}deg/{dist:0.#}m/h{h:0.#}/run{straightRun:0.00}"); }
                        if (crew) { crewHits++; crewList.Append($" {bearing:0}/{dist:0.#}/{h:0.#}/run{straightRun:0.00}"); }
                    }
            }
            Debug.Log($"RoadGame CANNONCHECK aim cases={cases} gunPartsOrFlashTouchCar={partHits} launchRunTouchesCar={runHits} restOfPathThroughCar={pathHits} throughHarpooner={crewHits} pitchRange={minPitch:0.0}..{maxPitch:0.0} straightRunRange={minRun:0.00}..{maxRun:0.00}m");
            if (pathHits > 0) Debug.Log("RoadGame CANNONCHECK path through car (bearing/dist/height):" + pathList);
            if (crewHits > 0) Debug.Log("RoadGame CANNONCHECK path through harpooner (bearing/dist/height):" + crewList);
            tur.PoseForCapture(0, 0f, 0f, 0f);

            // 4) the harpoon turret and its operator against the car
            if (pl.harpooner != null) HarpoonClearance(pl.harpooner, bodyMask);
            UnityEngine.Object.Destroy(colRoot);
        }

        static void HarpoonClearance(Harpooner h, int bodyMask)
        {
            var parts = new System.Collections.Generic.List<(MeshFilter mf, Vector3[] v, int[] e)>();
            foreach (var mf in h.Rig.root.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null || mf.name == "TurretBase" || mf.name == "LOD1" || mf.name == "LOD2") continue;   // LOD0; the base plate is bolted to the floor
                var m = mf.sharedMesh;
                var tris = m.triangles;
                var seen = new System.Collections.Generic.HashSet<long>();
                var edges = new System.Collections.Generic.List<int>();
                for (int i = 0; i < tris.Length; i += 3)
                    for (int k = 0; k < 3; k++)
                    {
                        int a = tris[i + k], b = tris[i + (k + 1) % 3];
                        long key = a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
                        if (seen.Add(key)) { edges.Add(a); edges.Add(b); }
                    }
                parts.Add((mf, m.vertices, edges.ToArray()));
            }
            bool oldBack = Physics.queriesHitBackfaces;
            Physics.queriesHitBackfaces = true;
            var hitsByPart = new System.Collections.Generic.Dictionary<string, System.Text.StringBuilder>();
            int poses = 0, posesHit = 0;
            long casts = 0;
            var world = new Vector3[0];
            void Check(float yaw, float recoil, float leanPitch = 0f, float leanRoll = 0f, int stepLeg = -1)
            {
                h.PoseForCapture(yaw, recoil);
                if (leanPitch != 0f || leanRoll != 0f) h.Rig.body.localRotation = Quaternion.Euler(leanPitch, 0f, leanRoll);
                if (stepLeg >= 0) h.Rig.leg[stepLeg].localRotation = Quaternion.Euler(-22f, 0f, 0f);
                Models.SolveHarpoonerArms(h.Rig);
                poses++;
                bool any = false;
                foreach (var (mf, v, e) in parts)
                {
                    if (world.Length < v.Length) world = new Vector3[v.Length];
                    var m = mf.transform.localToWorldMatrix;
                    for (int i = 0; i < v.Length; i++) world[i] = m.MultiplyPoint3x4(v[i]);
                    for (int i = 0; i < e.Length; i += 2)
                    {
                        casts++;
                        if (!Physics.Linecast(world[e[i]], world[e[i + 1]], out var hit, bodyMask, QueryTriggerInteraction.Ignore)) continue;
                        any = true;
                        if (!hitsByPart.TryGetValue(mf.name, out var sbp)) hitsByPart[mf.name] = sbp = new System.Text.StringBuilder();
                        var local = h.transform.parent.InverseTransformPoint(hit.point);   // car-body space
                        sbp.Append($" [{hit.collider.name} at {local.x:0.00},{local.y:0.00},{local.z:0.00}]");
                        sbp.Append($" {yaw:0}{(recoil > 0f ? "r" : "")}{(leanPitch != 0f || leanRoll != 0f ? $"(lean {leanPitch:0}/{leanRoll:0})" : "")}{(stepLeg >= 0 ? "(step)" : "")}");
                        break;
                    }
                }
                if (any) posesHit++;
            }
            for (int yd = 0; yd < 360; yd += 3) Check(yd, 0f);
            for (int yd = 0; yd < 360; yd += 15) Check(yd, 1f);
            // the body leans against the car's acceleration (up to 8 deg pitch / 7 deg roll) and the legs step while turning
            for (int yd = 0; yd < 360; yd += 10)
            {
                Check(yd, 0f, 8f, 0f); Check(yd, 0f, -8f, 0f); Check(yd, 0f, 0f, 7f); Check(yd, 0f, 0f, -7f);
                Check(yd, 0f, 0f, 0f, 0); Check(yd, 0f, 0f, 0f, 1);
            }
            Physics.queriesHitBackfaces = oldBack;
            h.PoseForCapture(0f, 0f);
            Debug.Log($"RoadGame HARPOONCHECK poses={poses} touchingCar={posesHit} edgeCasts={casts} parts={parts.Count}");
            foreach (var kv in hitsByPart) Debug.Log("RoadGame HARPOONCHECK " + kv.Key + " touches at yaw:" + kv.Value);
        }

        // ------------------------------------------------------------------ progress reset ("reset", then "resetcheck" after a restart)
        // reset: a game well under way on its own test save (-captureSaveKey) with non-default settings. Settings are opened,
        // "Reset progress" is pressed and the dialog cancelled (nothing may change), then pressed again and confirmed: the
        // save must at once be a new game with the same settings, and the rebuilt session must start the intro run. The
        // test save is kept (-captureKeepSave end) for "resetcheck": a new process (= a restart) that loads it
        // (-captureKeepSave start) and deletes it at the end.
        static int resetStep;
        static double resetStepAt;
        static string resetSigBefore, resetRawBefore;
        static int resetShots;
        static Game resetGame;

        static int CountUsed(SaveData d)
        {
            int n = 0;
            foreach (var s in d.spawns) if (s.kills > 0 || s.respawnAt > 0) n++;
            return n;
        }

        static string ProgressSig(SaveData d) =>
            $"gems={d.gems} weaponLevels={string.Join(",", d.weaponLevel)} copies={string.Join(",", d.weaponCopies)} armor={string.Join(",", d.armorLevel)} " +
            $"maxHp={d.maxHp:0} dmg0={d.dmg[0]:0.##} unlockedZone={d.unlockedZone} bossKills={string.Join(",", d.bossKills)} stashes={d.chestsOpened.Count} " +
            $"spawnsUsed={CountUsed(d)} kills={d.totalKills} bonusTimers={(d.freeGemsAt > 0 || d.nextBonusAt > Progress.NowMs + 60000 ? "set" : "fresh")} " +
            $"tutorialDone={d.tutorialDone} introPending={d.introPending} | sound={d.soundOn} music={d.musicOn} vibration={d.vibrationOn}";

        static bool Press(string name)
        {
            var go = GameObject.Find(name);
            var b = go != null ? go.GetComponent<Button>() : null;
            if (b == null) { Debug.LogError("RoadGame RESET: button not found: " + name); return false; }
            b.onClick.Invoke();
            return true;
        }

        static void Step(int s) { resetStep = s; resetStepAt = EditorApplication.timeSinceStartup; }

        static void ResetTick()
        {
            var g = Game.I;
            if (g == null || !g.Ready || g.progress == null || g.player == null) return;
            double now = EditorApplication.timeSinceStartup;
            if (cfg.scenario == "resetcheck")
            {
                if (resetStep == 0 && g.SessionTime > 2.5f)
                {
                    resetStep = 1;
                    Debug.Log($"RoadGame RESETCHECK loaded after a restart: {ProgressSig(g.progress.d)} introActive={Intro.Active != null} car={g.player.Pos} sfxOn={g.sfx.on} musicOn={g.sfx.musicOn}");
                    Shoot(resetShots++);
                    Finish();
                }
                return;
            }
            switch (resetStep)
            {
                case 0:
                    if (g.SessionTime < 2.5f) return;
                    g.SaveNow();
                    resetSigBefore = ProgressSig(g.progress.d);
                    resetRawBefore = SaveSystem.RawJson();
                    Debug.Log("RoadGame RESET before: " + resetSigBefore);
                    g.hud.panels.ShowSettings();
                    Step(1);
                    return;
                case 1:
                    if (now < resetStepAt + 0.6) return;
                    Shoot(resetShots++);                       // the settings with the new button
                    Press("ResetProgress");
                    Step(2);
                    return;
                case 2:
                    if (now < resetStepAt + 0.6) return;
                    Debug.Log($"RoadGame RESET dialog open={g.hud.panels.ConfirmOpen}");
                    Shoot(resetShots++);                       // the confirmation dialog
                    Press("ResetCancel");
                    Step(3);
                    return;
                case 3:
                    if (now < resetStepAt + 0.5) return;
                    Debug.Log($"RoadGame RESET cancel: dialogClosed={!g.hud.panels.ConfirmOpen} settingsStillOpen={g.hud.panels.IsOpen} " +
                              $"progressUnchanged={ProgressSig(g.progress.d) == resetSigBefore} saveUnchanged={SaveSystem.RawJson() == resetRawBefore}");
                    Shoot(resetShots++);                       // back in the settings, nothing changed
                    Press("ResetProgress");
                    Step(4);
                    return;
                case 4:
                    if (now < resetStepAt + 0.5) return;
                    Debug.Log($"RoadGame RESET dialog open again={g.hud.panels.ConfirmOpen}");
                    resetGame = g;
                    Press("ResetConfirm");
                    var saved = JsonUtility.FromJson<SaveData>(SaveSystem.RawJson() ?? "{}");
                    Debug.Log("RoadGame RESET saved at once: " + ProgressSig(saved));
                    Step(5);
                    return;
                case 5:
                    if (g == resetGame || g.SessionTime < 2.5f) return;   // wait for the rebuilt session
                    Debug.Log($"RoadGame RESET new session: {ProgressSig(g.progress.d)} introActive={Intro.Active != null} car={g.player.Pos} heading={g.player.Heading:0} " +
                              $"sfxOn={g.sfx.on} musicOn={g.sfx.musicOn} paused={g.paused} panelsOpen={g.hud.panels.IsOpen}");
                    Shoot(resetShots++);                       // the new game: the intro canyon
                    Step(6);
                    return;
                case 6:
                    if (now < resetStepAt + 1.0) return;
                    g.SaveNow();
                    Debug.Log("RoadGame RESET saved for the restart: " + ProgressSig(JsonUtility.FromJson<SaveData>(SaveSystem.RawJson() ?? "{}")));
                    Finish();
                    return;
            }
        }

        static void Finish()
        {
            EditorApplication.update -= Tick;
            SessionState.EraseString(Key);
            if (cfg.keepSave != "end" && cfg.keepSave != "both") PlayerPrefs.DeleteKey("roadgame_save_v1" + cfg.saveKey);
            PlayerPrefs.Save();
            Debug.Log("RoadGame AutoCapture: done, " + resetShots + " shots in " + cfg.outDir);
            EditorApplication.Exit(0);
        }

        static void EnsureCloseCam(Game g)
        {
            if (closeCam == null)
            {
                closeCam = new GameObject("CloseupCam").AddComponent<Camera>();
                closeCam.CopyFrom(g.cam);
                var data = closeCam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
                if (data == null) data = closeCam.gameObject.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
                data.renderPostProcessing = true;
                closeCam.enabled = false;
            }
            closeCam.targetTexture = rt;
            closeCam.nearClipPlane = 0.1f;
        }

        static void RenderCloseup(int index)
        {
            var g = Game.I;
            var h = g.player.harpooner;
            int v = index % CloseViews.GetLength(0);
            h.PoseForCapture(CloseViews[v, 0], CloseViews[v, 1]);
            if (closeCam == null)
            {
                closeCam = new GameObject("CloseupCam").AddComponent<Camera>();
                closeCam.CopyFrom(g.cam);
                var data = closeCam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
                if (data == null) data = closeCam.gameObject.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
                data.renderPostProcessing = true;
                closeCam.enabled = false;
            }
            closeCam.targetTexture = rt;
            closeCam.fieldOfView = CloseViews[v, 5];
            closeCam.nearClipPlane = 0.1f;
            var rig = h.Rig;
            var focus = Vector3.Lerp(rig.head.position, rig.body.position, 0.45f);
            if (v >= 4) focus = g.player.rig.body.TransformPoint(new Vector3(0f, 1.2f, -1.45f));   // the whole bed
            var face = rig.yaw.forward; face.y = 0; face.Normalize();
            var dir = Quaternion.AngleAxis(CloseViews[v, 2], Vector3.up) * face;
            dir = Quaternion.AngleAxis(CloseViews[v, 3], Vector3.Cross(dir, Vector3.up)) * dir;
            closeCam.transform.position = focus + dir * CloseViews[v, 4];
            closeCam.transform.LookAt(focus);
            closeCam.Render();
        }

        static bool layoutDumped;

        // ------------------------------------------------------------------ video: every rendered frame as a JPG (ffmpeg joins them)
        static int lastVideoFrame = -1, videoIndex;

        static void VideoTick()
        {
            float st = Game.I.SessionTime;
            if (Time.captureFramerate != cfg.fps) Time.captureFramerate = cfg.fps;   // fixed game step per frame: smooth video
            if (st < cfg.videoFrom || st > cfg.videoTo || Time.frameCount == lastVideoFrame) return;
            lastVideoFrame = Time.frameCount;
            var dir = Path.Combine(cfg.outDir, "video");
            Directory.CreateDirectory(dir);
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(dir, $"f_{videoIndex++:00000}.jpg"), tex.EncodeToJPG(92));
            UnityEngine.Object.DestroyImmediate(tex);
        }

        // ------------------------------------------------------------------ jumps at several speeds + a side approach
        // (start, heading, approach speed m/s, label): each run starts every 6.5 s of game time
        static readonly (Vector3 p, float yaw, float speed, string name)[] JumpRuns =
        {
            (new Vector3(0f, 0f, -125f), 0f, 4f, "intro_ramp_slow"),
            (new Vector3(0f, 0f, -150f), 0f, 9f, "intro_ramp_mid"),
            (new Vector3(0f, 0f, -150f), 0f, 13.6f, "intro_ramp_full"),
            (new Vector3(44f, 0f, -33f), 90f, 7f, "plateau0_onto_top"),
            (new Vector3(44f, 0f, -33f), 90f, 13.6f, "plateau0_full"),
            (new Vector3(-8f, 0f, 198.6f), 90f, 10f, "pipeline_jump"),
            (new Vector3(26.5f, 0f, 30f), 117.8f, 11f, "bus_jump"),
            (new Vector3(-8f, 0f, -114f), 90f, 8f, "intro_ramp_from_side"),
            (new Vector3(0f, -30f, -60f), 0f, 0f, "recovery_below_world"),
        };
        const float JumpRunSecs = 6.5f;
        static int jumpRun = -1;
        static float jumpTakeoffT, jumpMaxY;
        static Vector3 jumpTakeoffP;
        static bool jumpWasAir;

        static Vector2 JumpInput(float t)
        {
            int i = Mathf.Clamp((int)((t - 1f) / JumpRunSecs), 0, JumpRuns.Length - 1);
            if (t < 1f) return Vector2.zero;
            var r = JumpRuns[i];
            float m = Mathf.Clamp01(StickFilter.LengthForSpeed(r.speed) + 0.02f);
            float local = (t - 1f) - i * JumpRunSecs;
            if (local > 4.6f) m = 0f;   // coast out after the landing
            var dir = new Vector2(Mathf.Sin(r.yaw * Mathf.Deg2Rad), Mathf.Cos(r.yaw * Mathf.Deg2Rad));
            return dir * m;
        }

        static void JumpTick(Player pl)
        {
            float t = Game.I.SessionTime;
            int want = t < 1f ? -1 : (int)((t - 1f) / JumpRunSecs);
            if (want != jumpRun && want < JumpRuns.Length && want >= 0)
            {
                jumpRun = want;
                var r = JumpRuns[want];
                pl.Teleport(r.p, r.yaw);
                pl.SetSpeed(r.speed);
                Game.I.cameraRig.Snap();
                jumpWasAir = false;
                Debug.Log($"RoadGame JUMP run={want} {r.name} start={r.p} v={r.speed}");
            }
            if (pl.Airborne && !jumpWasAir) { jumpWasAir = true; jumpTakeoffT = t; jumpTakeoffP = pl.Pos; jumpMaxY = pl.Pos.y; Debug.Log($"RoadGame JUMP takeoff run={jumpRun} v={pl.Speed:0.0} vy={pl.VerticalSpeed:0.0} at={pl.Pos}"); }
            if (pl.Airborne) jumpMaxY = Mathf.Max(jumpMaxY, pl.Pos.y);
            if (!pl.Airborne && jumpWasAir)
            {
                jumpWasAir = false;
                var d = pl.Pos - jumpTakeoffP; d.y = 0;
                Debug.Log($"RoadGame JUMP land run={jumpRun} air={t - jumpTakeoffT:0.00}s apex={jumpMaxY:0.00} dist={d.magnitude:0.0} impact={pl.LastLandingImpact:0.0} at={pl.Pos}");
            }
        }

        // ------------------------------------------------------------------ underground: drive in, fight the Mammoth, drive out
        static readonly Vector3[] WorksIn = { new Vector3(15f, 0f, 40f), new Vector3(23f, 0f, 42f), new Vector3(40f, 0f, 42f), new Vector3(52f, 0f, 42f), new Vector3(55f, 0f, 47f), new Vector3(55f, 0f, 58f) };
        static readonly Vector3[] WorksOut = { new Vector3(40f, 0f, 58f), new Vector3(32f, 0f, 58f), new Vector3(32f, 0f, 70f), new Vector3(32f, 0f, 84f), new Vector3(22f, 0f, 84f), new Vector3(14f, 0f, 92f) };
        static int ugStage, ugWaypoint;     // 0 = drive in, 1 = boss fight (autopilot), 2 = wait for the reward, 3 = drive out, 4 = done
        static float ugStageT;

        static Vector2 ugStick;
        static int ugStickFrame = -1;

        /// <summary>The bot's stick, worked out once per game frame in UndergroundTick (this delegate runs every physics step).</summary>
        static Vector2 UndergroundInput(float t) => t < 1f ? Vector2.zero : ugStick;

        /// <summary>Towards the next waypoint like a player (three-point turn, easing off before tight turns); wedged
        /// against something (after the boss fight the car can stand anywhere in the hangar) it backs off and swings
        /// out the way the route bot does.</summary>
        static void UndergroundStick(Player pl)
        {
            if (Time.frameCount == ugStickFrame) return;
            ugStickFrame = Time.frameCount;
            Vector3[] route = ugStage == 0 ? WorksIn : ugStage == 3 ? WorksOut : null;
            if (route == null || ugWaypoint >= route.Length || Game.I.SessionTime < 1f) { ugStick = Vector2.zero; return; }
            var to = route[ugWaypoint] - pl.Pos; to.y = 0;
            var want = CarDriver.TowardTarget(new Vector2(to.x, to.z).normalized * SpeedStick(ugStage == 0 ? 0.75f : 0.62f), pl.Heading, pl.ForwardSpeed, pl.GearDirection, to.magnitude);
            ugStick = Unstick(pl, want);
        }

        /// <summary>
        /// Stick length for a cruise speed written the old way (the driver used to aim at TopSpeed * 1.15 * length with
        /// no dead zone): the same speed through today's dead zone and response curve, so a scripted run keeps its pace.
        /// </summary>
        static float SpeedStick(float legacyLength)
        {
            if (legacyLength <= 0f) return 0f;
            return StickFilter.LengthForSpeed(CarTuning.TopSpeed * Mathf.Clamp01(legacyLength * 1.15f));
        }

        static void UndergroundTick(Player pl)
        {
            UndergroundStick(pl);
            var g = Game.I;
            Vector3[] route = ugStage == 0 ? WorksIn : ugStage == 3 ? WorksOut : null;
            if (route != null && ugWaypoint < route.Length)
            {
                var d = route[ugWaypoint] - pl.Pos; d.y = 0;
                if (d.magnitude < 3.2f) { ugWaypoint++; Debug.Log($"RoadGame UG waypoint {ugStage}/{ugWaypoint} pos={pl.Pos} under={pl.Underground}"); }
            }
            if (ugStage == 0 && ugWaypoint >= WorksIn.Length)
            {
                ugStage = 1; ugStageT = g.SessionTime;
                Game.ScriptedInput = null; Game.Autopilot = true; Game.AutopilotBoss = true;
                Debug.Log("RoadGame UG in the hangar, fight starts t=" + g.SessionTime.ToString("0.0"));
            }
            if (ugStage == 1 && g.progress.d.bossKills[0] > 0)
            {
                ugStage = 2; ugStageT = g.SessionTime;
                Debug.Log($"RoadGame UG boss killed t={g.SessionTime:0.0} unlockedZone={g.progress.d.unlockedZone} hammer={g.progress.d.weaponLevel[1]}");
            }
            if (ugStage == 2 && g.SessionTime - ugStageT > 4f && pl.harpooner.Pending == 0)
            {
                ugStage = 3; ugWaypoint = 0;
                Game.Autopilot = false; Game.AutopilotBoss = false; Game.ScriptedInput = UndergroundInput;
                Debug.Log($"RoadGame UG reward in, driving out t={g.SessionTime:0.0} maxHp={g.progress.d.maxHp:0} dmg={g.progress.d.dmg[0]:0.0} gems={g.progress.d.gems}");
            }
            if (ugStage == 3 && ugWaypoint >= WorksOut.Length)
            {
                ugStage = 4;
                Debug.Log($"RoadGame UG out on the surface t={g.SessionTime:0.0} pos={pl.Pos} under={pl.Underground}");
            }
        }

        // ------------------------------------------------------------------ structures tour (visual check of every new place)
        const float TourStart = 1.5f, TourStep = 1.9f, TourSettle = 1.5f;
        static int tourIndex = -1;
        static readonly (Vector3 p, float yaw, float zoom, string name)[] TourStops =
        {
            (new Vector3(0f, 0f, -222f), 0f, 1f, "intro_start"),
            (new Vector3(0f, 0f, -132f), 0f, 1f, "intro_ramp"),
            (new Vector3(0f, 0f, -92f), 180f, 1f, "intro_barricade_from_zone"),
            (new Vector3(14f, 0f, 36f), 20f, 1f, "works_from_road"),
            (new Vector3(29f, 0f, 42f), 90f, 1f, "works_ramp"),
            (new Vector3(46f, -4.5f, 42f), 90f, 1f, "works_tunnel"),
            (new Vector3(55f, -4.5f, 49f), 0f, 1f, "works_link"),
            (new Vector3(52f, -4.5f, 64f), 20f, 1f, "works_hangar"),
            (new Vector3(32f, -2f, 70f), 0f, 1f, "works_loadramp"),
            (new Vector3(22f, 0f, 84f), 270f, 1f, "works_door"),
            (new Vector3(60f, 0f, 62f), 0f, 1.7f, "works_overview"),
            (new Vector3(56f, 0f, -33f), 90f, 1f, "plateau0_ramp"),
            (new Vector3(80f, 2f, -33f), 0f, 1f, "plateau0_top"),
            (new Vector3(36f, 0f, 24.5f), 117.8f, 1f, "busjump"),
            (new Vector3(-37.8f, 0f, -36.9f), 258.7f, 1f, "garage_outside"),
            (new Vector3(-47.5f, 0f, -38.9f), 78.7f, 1f, "garage"),
            (new Vector3(53f, 0f, 41.5f), 90f, 1f, "tunnel_lid_from_above"),
            (new Vector3(50f, 0f, 30f), 0f, 1.6f, "works_overview_surface"),
            (new Vector3(-14.8f, 0f, 186f), 0f, 1f, "rocktunnel"),
            (new Vector3(20f, -3.4f, 208.5f), 90f, 1f, "underpass"),
            (new Vector3(5f, 0f, 198.6f), 90f, 1f, "pipejump"),
            (new Vector3(3f, 0f, 376f), 0f, 1f, "canopy"),
            (new Vector3(66f, 0f, 377f), 90f, 1f, "plateau2_ramp"),
            (new Vector3(-22f, 0f, 622.8f), 90f, 1f, "pipetunnel"),
            (new Vector3(4.5f, 0f, 599f), -17f, 1f, "drumjump"),
        };

        /// <summary>Writes the generated world (roads, camps, pads, spawns, structures) as JSON for map planning / checks.</summary>
        static void DumpLayout(string path)
        {
            var w = World.I;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            string V(Vector3 p) => string.Format(inv, "[{0:0.##},{1:0.##},{2:0.##}]", p.x, p.y, p.z);
            var sb = new System.Text.StringBuilder();
            sb.Append("{\"zones\":[");
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                if (zi > 0) sb.Append(',');
                sb.Append("{\"roads\":[");
                for (int r = 0; r < w.roads[zi].Count; r++)
                {
                    if (r > 0) sb.Append(',');
                    sb.Append(string.Format(inv, "{{\"w\":{0:0.##},\"pts\":[", w.roadWidths[zi][r]));
                    var pl = w.roads[zi][r];
                    for (int i = 0; i < pl.Count; i++) { if (i > 0) sb.Append(','); sb.Append(V(pl[i])); }
                    sb.Append("]}");
                }
                sb.Append("],\"camps\":[");
                for (int i = 0; i < w.camps[zi].Count; i++) { if (i > 0) sb.Append(','); sb.Append(V(w.camps[zi][i])); }
                sb.Append("],\"arena\":").Append(V(w.arenaCenters[zi]));
                sb.Append(",\"boss\":").Append(V(w.bossSpawns[zi] != null ? w.bossSpawns[zi].pos : Vector3.zero));
                sb.Append(",\"spawns\":[");
                bool first = true;
                foreach (var sp in w.zoneSpawns[zi])
                {
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append(string.Format(inv, "{{\"id\":{0},\"m\":\"{1}\",\"k\":\"{2}\",\"r\":{3:0.##},\"p\":{4}}}", sp.id, sp.spec.model, sp.spec.kind, sp.spec.radius * sp.scale, V(sp.pos)));
                }
                sb.Append("]}");
            }
            sb.Append("],\"stations\":[");
            for (int i = 0; i < w.stations.Count; i++) { if (i > 0) sb.Append(','); sb.Append(V(w.stations[i].pos)); }
            sb.Append("],\"start\":").Append(V(w.startPos));
            sb.Append(",\"player\":").Append(V(Game.I.player.Pos));
            sb.Append(",\"colliders\":[");
            bool firstC = true;
            foreach (var c in UnityEngine.Object.FindObjectsByType<Collider>())
            {
                if (c.attachedRigidbody != null) continue;
                var b = c.bounds;
                if (!firstC) sb.Append(',');
                firstC = false;
                sb.Append("{\"n\":\"").Append(c.gameObject.name).Append("\",\"min\":").Append(V(b.min)).Append(",\"max\":").Append(V(b.max)).Append('}');
            }
            sb.Append("]}");
            File.WriteAllText(path, sb.ToString());
            Debug.Log("RoadGame AutoCapture: layout written to " + path);
            // triangle budget per world object (structures, ground, cliffs...) to keep the scene light
            var tri = new System.Collections.Generic.Dictionary<string, long>();
            foreach (var mf in UnityEngine.Object.FindObjectsByType<MeshFilter>())
            {
                if (mf.sharedMesh == null) continue;
                var t = mf.transform;
                while (t.parent != null && t.parent.parent != null && t.parent.name != "Structures") t = t.parent;
                string key = t.name;
                tri.TryGetValue(key, out long n);
                tri[key] = n + mf.sharedMesh.GetIndexCount(0) / 3;
            }
            var keys = new System.Collections.Generic.List<string>(tri.Keys);
            keys.Sort((a, b) => tri[b].CompareTo(tri[a]));
            var line = new System.Text.StringBuilder("RoadGame TRIS");
            for (int i = 0; i < keys.Count && i < 30; i++) line.Append(' ').Append(keys[i]).Append('=').Append(tri[keys[i]]);
            Debug.Log(line.ToString());
        }

        static void Shoot(int index)
        {
            var g = Game.I;
            if (cfg.scenario == "quasimodo" && g.player != null && g.player.harpooner != null) RenderCloseup(index);
            else if (cfg.scenario == "pickup" && g.player != null) RenderPickup(index);
            else if (cfg.scenario == "turns" && g.player != null) RenderTurn(index);
            else if (cfg.scenario == "cannon" && g.player != null) RenderCannon(index);
            else if (cfg.scenario == "cannongame" && g.player != null) RenderCannonGame(index);
            else g.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            var path = Path.Combine(cfg.outDir, $"{cfg.scenario}_{index:00}.png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            if (g.progress == null || g.player == null || World.I == null || g.overlay == null || g.player.turret == null || g.player.harpooner == null) { Debug.Log("RoadGame AutoCapture: " + path + " (loading)"); return; }
            var d = g.progress.d;
            Debug.Log($"RoadGame AutoCapture: {path} | fps~{1f / Mathf.Max(0.0001f, Time.smoothDeltaTime):0} hp={d.hp:0}/{d.maxHp:0} dmg={d.dmg[0]:0.0} kills={d.totalKills} pos={g.player.Pos} active={World.I.activeTargets.Count} draws={UnityEditor.UnityStats.drawCalls} setpass={UnityEditor.UnityStats.setPassCalls} tris={UnityEditor.UnityStats.triangles} enemyShots={Projectile.Fired} gunShots={Turret.ShotsFired} gunHits={Turret.ShellHits} " +
                      $"gunYaw={g.player.turret.Yaw:0} harpoonYaw={g.player.harpooner.Yaw:0} harpoons={Harpooner.Fired} reeled={Harpooner.Reeled} harpoonAimErrMax={Harpooner.WorstFireError:0.0} " +
                      $"labels full={g.overlay.LabelsFull} thin={g.overlay.LabelsCompact} hiddenByHud={g.overlay.LabelsHiddenByHud} goal={g.hud?.Goal?.kind}");
            if (cfg.perf) Perf(index);
        }

        /// <summary>
        /// Renders the current frame 60 times, each followed by a 1-pixel readback so CPU submit + GPU work are both
        /// inside the measured time (editor numbers are only comparable to each other, not to a phone).
        /// Also logs the frame's render stats and the vertex count of the player car meshes.
        /// </summary>
        static long perfMoveTicks; static int perfFrame;

        static void Perf(int index)
        {
            var g = Game.I;
            var one = new Texture2D(1, 1, TextureFormat.RGB24, false);
            var prev = RenderTexture.active;
            var ms = new System.Collections.Generic.List<double>();
            var sw = new System.Diagnostics.Stopwatch();
            for (int i = 0; i < 70; i++)
            {
                sw.Restart();
                g.cam.Render();
                RenderTexture.active = rt;
                one.ReadPixels(new Rect(0, 0, 1, 1), 0, 0);
                one.Apply();
                RenderTexture.active = prev;
                sw.Stop();
                if (i >= 10) ms.Add(sw.Elapsed.TotalMilliseconds);
            }
            UnityEngine.Object.DestroyImmediate(one);
            ms.Sort();
            double median = ms[ms.Count / 2], p90 = ms[(int)(ms.Count * 0.9)];
            int carVerts = 0, carTris = 0;
            foreach (var mf in g.player.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null) continue;
                carVerts += mf.sharedMesh.vertexCount;
                carTris += (int)(mf.sharedMesh.GetIndexCount(0) / 3);
            }
            long mv = Enemy.MoveTicks - perfMoveTicks; int fr = Time.frameCount - perfFrame;
            perfMoveTicks = Enemy.MoveTicks; perfFrame = Time.frameCount;
            double moveMs = fr > 0 ? mv * 1000.0 / System.Diagnostics.Stopwatch.Frequency / fr : 0.0;
            Debug.Log($"RoadGame PERF shot={index} quality={QualitySettings.names[QualitySettings.GetQualityLevel()]} renderMs median={median:0.00} p90={p90:0.00} enemyMoveMsPerFrame={moveMs:0.000} enemies={World.I.activeTargets.Count} " +
                      $"draws={UnityEditor.UnityStats.drawCalls} setpass={UnityEditor.UnityStats.setPassCalls} " +
                      $"tris={UnityEditor.UnityStats.triangles} verts={UnityEditor.UnityStats.vertices} shadowCasters={UnityEditor.UnityStats.shadowCasters} " +
                      $"carVerts={carVerts} carTris={carTris}");
        }
    }
}
