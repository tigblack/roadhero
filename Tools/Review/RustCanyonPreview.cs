using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;

namespace RoadGame.EditorTools
{
    // Temporary review tool. Copy into Assets/RoadGame/Editor only for this batch run, then remove it.
    [InitializeOnLoad]
    public static class RustCanyonPreview
    {
        const string Key = "RoadGame.RustCanyonPreview.Output";
        const string Finishing = "RoadGame.RustCanyonPreview.Finishing";
        const string Suffix = "_rustpreview20261120";
        static string output;
        static double idleSince = -1, deadline;
        static bool captured;
        static int exitCode;

        static RustCanyonPreview()
        {
            output = SessionState.GetString(Key, "");
            if (string.IsNullOrEmpty(output)) return;
            WorkAudioMute.Apply();
            if (SessionState.GetBool(Finishing, false))
            {
                EditorApplication.playModeStateChanged += OnPlayState;
                if (!EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.delayCall += CleanAndExit;
                return;
            }
            Arm();
        }

        public static void Run()
        {
            WorkAudioMute.Apply();
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Requires stopped Play Mode.");
            output = Path.GetFullPath(Arg("-previewOut", "Docs/screenshots/rust-canyon-review-2026-11-20"));
            Directory.CreateDirectory(output);
            PlayerPrefs.DeleteKey("roadgame_save_v1" + Suffix);
            SessionState.SetString(Key, output);
            SessionState.SetBool(Finishing, false);
            SessionState.SetInt(Finishing + ".exit", 0);
            EditorSceneManager.OpenScene(ProjectSetup.ScenePath, OpenSceneMode.Single);
            Arm();
        }

        static void Arm()
        {
            SaveSystem.KeySuffix = Suffix;
            Game.Autopilot = false;
            Game.AutopilotBoss = false;
            Game.TestSetup = Setup;
            deadline = EditorApplication.timeSinceStartup + 150;
            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;
            EditorApplication.playModeStateChanged -= OnPlayState;
            EditorApplication.playModeStateChanged += OnPlayState;
        }

        static void Setup(Progress progress)
        {
            var d = progress.d;
            d.introPending = false;
            d.tutorialDone = true;
            d.unlockedZone = 1;
            d.bossKills[0] = 1;
            d.px = -15.6f; d.py = 0; d.pz = 240;
            d.maxHp = d.hp = 1000000;
            d.regen = 0;
            d.nextBonusAt = Progress.NowMs + 3600000;
            Game.ScriptedInput = t => Vector2.zero;
            UnityEngine.Random.InitState(17421);
        }

        static void Tick()
        {
            try
            {
                if (EditorApplication.timeSinceStartup > deadline) throw new TimeoutException("Rust Canyon preview timed out.");
                if (!EditorApplication.isPlaying)
                {
                    if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || EditorApplication.isUpdating) return;
                    if (idleSince < 0) idleSince = EditorApplication.timeSinceStartup;
                    if (EditorApplication.timeSinceStartup - idleSince < 2) return;
                    WorkAudioMute.Apply();
                    EditorApplication.EnterPlaymode();
                    return;
                }
                if (captured || Game.I == null || !Game.I.Ready) return;
                captured = true;
                CaptureAll();
                Finish(0);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                Finish(1);
            }
        }

        static void CaptureAll()
        {
            var g = Game.I;
            var zone = Content.Zones[1];
            var center = g.world.arenaCenters[1];
            var bossSpawn = g.world.bossSpawns[1];
            if (bossSpawn == null || bossSpawn.id != 19500) throw new InvalidOperationException("Rust Canyon boss 19500 missing.");
            g.player.Teleport(center + new Vector3(0, 0, -24), 0);
            g.world.Tick();
            if (bossSpawn.target == null) throw new InvalidOperationException("World.Tick did not instantiate Oil Baron.");

            // Freeze a genuine runtime snapshot. No attacks, movement, culling or camera follow during renders.
            g.paused = true;
            g.enabled = false;
            g.world.enabled = false;
            g.cameraRig.enabled = false;
            foreach (var target in g.world.activeTargets)
                if (target != null)
                    foreach (var behaviour in target.GetComponentsInChildren<MonoBehaviour>(true)) behaviour.enabled = false;
            bossSpawn.target.ResetForSpawn(false);
            g.player.gameObject.SetActive(false);
            foreach (var canvas in UnityEngine.Object.FindObjectsByType<Canvas>(FindObjectsInactive.Include, FindObjectsSortMode.None)) canvas.enabled = false;
            Mats.ApplyZone(zone, zone, 1f);
            if (g.sun != null) { g.sun.color = zone.sun; g.sun.intensity = zone.sunIntensity; }

            var cameraObject = new GameObject("RustPreviewCamera");
            var camera = cameraObject.AddComponent<Camera>();
            camera.CopyFrom(g.cam);
            camera.enabled = false;
            camera.nearClipPlane = 0.1f;
            camera.farClipPlane = 250;
            var data = cameraObject.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.renderShadows = true;
            camera.backgroundColor = zone.sky;
            camera.transform.position = center + new Vector3(0, 34, -39);
            camera.transform.LookAt(center + Vector3.up);
            camera.fieldOfView = 44;
            Render(camera, "arena-wide.png", 1600, 1000);

            var bossPosition = bossSpawn.target.transform.position;
            camera.transform.position = bossPosition + new Vector3(10, 8, -14);
            camera.transform.LookAt(bossPosition + Vector3.up * 4.8f);
            camera.fieldOfView = 48;
            Render(camera, "boss-close.png", 1000, 1000);

            // This is deliberately a model roster outside the world, not invented boss-room guards.
            var studio = new Vector3(8000, 0, 0);
            var floor = new MeshBuilder();
            floor.Box(new Vector3(0, -0.1f, 0), new Vector3(60, 0.2f, 40), Quaternion.identity, Models.Hex("#B5AAA1"));
            var floorObject = Models.MeshGO("ReviewStudioFloor", floor.Build("ReviewStudioFloor"), Mats.ToonFlat, null);
            floorObject.transform.position = studio;
            var roster = new List<SpawnSpec>();
            var rosterObjects = new List<GameObject>();
            foreach (var spec in zone.specs) if (spec.kind == TargetKind.Foot || spec.kind == TargetKind.Vehicle) roster.Add(spec);
            if (roster.Count != 6) throw new InvalidOperationException("Expected six Rust Canyon enemy types, got " + roster.Count);
            RenderSettings.fog = false;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Models.Hex("#B5AAA1");
            camera.orthographic = true;
            for (int i = 0; i < roster.Count; i++)
            {
                var spec = roster[i];
                var model = Models.Create(spec.model, 0, zone, spec.scale);
                rosterObjects.Add(model);
                model.name = "ReviewRoster_" + spec.name;
                model.transform.position = studio + new Vector3((i - 2.5f) * 5.3f, 0, 0);
                model.transform.rotation = Quaternion.Euler(0, 165f, 0);
                foreach (var behaviour in model.GetComponentsInChildren<MonoBehaviour>(true)) behaviour.enabled = false;
                var renderers = model.GetComponentsInChildren<Renderer>();
                var bounds = renderers[0].bounds;
                foreach (var renderer in renderers) bounds.Encapsulate(renderer.bounds);
                camera.orthographicSize = Mathf.Max(1.65f, Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z)) * 0.68f);
                camera.transform.position = bounds.center + new Vector3(5f, 3.5f, -9f);
                camera.transform.LookAt(bounds.center);
                Render(camera, "enemy-" + (i + 1).ToString("00") + ".png", 640, 640);
                model.SetActive(false);
                Debug.Log("RustPreview ROSTER slot=" + i + " name=" + spec.name + " model=" + spec.model + " scale=" + spec.scale + " hp=" + spec.hp);
            }
            foreach (var model in rosterObjects) model.SetActive(true);
            RenderSettings.fog = false;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Models.Hex("#B5AAA1");
            camera.orthographic = true;
            camera.orthographicSize = 9.3f;
            camera.transform.position = studio + new Vector3(0, 9, -23);
            camera.transform.LookAt(studio + Vector3.up * 1.2f);
            Render(camera, "enemy-lineup.png", 1600, 900);
            Debug.Log("RustPreview SUCCESS arena=" + center + " boss=" + bossSpawn.id + " " + bossSpawn.spec.name + " roster=" + roster.Count + " editorMasterMuted=" + WorkAudioMute.Apply() + " output=" + output);
        }

        static void Render(Camera camera, string filename, int width, int height)
        {
            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { antiAliasing = 4 };
            rt.Create();
            var previous = RenderTexture.active;
            camera.targetTexture = rt;
            camera.aspect = width / (float)height;
            camera.Render();
            RenderTexture.active = rt;
            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            image.Apply();
            File.WriteAllBytes(Path.Combine(output, filename), image.EncodeToPNG());
            camera.targetTexture = null;
            RenderTexture.active = previous;
            UnityEngine.Object.DestroyImmediate(image);
            rt.Release();
            UnityEngine.Object.DestroyImmediate(rt);
            Debug.Log("RustPreview wrote " + filename + " " + width + "x" + height);
        }

        static void Finish(int result)
        {
            exitCode = result;
            SessionState.SetInt(Finishing + ".exit", result);
            SessionState.SetBool(Finishing, true);
            EditorApplication.update -= Tick;
            if (EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.isPlaying = false;
            else CleanAndExit();
        }

        static void OnPlayState(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.ExitingEditMode || state == PlayModeStateChange.EnteredPlayMode)
            {
                WorkAudioMute.Apply();
                SaveSystem.KeySuffix = Suffix;
                Game.TestSetup = Setup;
            }
            if (state == PlayModeStateChange.EnteredEditMode && SessionState.GetBool(Finishing, false)) CleanAndExit();
        }

        static void CleanAndExit()
        {
            exitCode = SessionState.GetInt(Finishing + ".exit", exitCode);
            EditorApplication.update -= Tick;
            EditorApplication.playModeStateChanged -= OnPlayState;
            PlayerPrefs.DeleteKey("roadgame_save_v1" + Suffix);
            PlayerPrefs.Save();
            SaveSystem.KeySuffix = "";
            Game.TestSetup = null;
            Game.ScriptedInput = null;
            SessionState.EraseString(Key);
            SessionState.EraseBool(Finishing);
            SessionState.EraseInt(Finishing + ".exit");
            Time.timeScale = 1f;
            EditorApplication.Exit(exitCode);
        }

        static string Arg(string name, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == name) return args[i + 1];
            return fallback;
        }
    }
}
