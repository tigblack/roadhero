using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Profiling;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Actual Game.Start/World.GenerateRoutine memory and integration diagnostic in Editor Play Mode.
    /// Unity -batchmode -disableaudio -executeMethod RoadGame.EditorTools.WebMemoryCheck.Run
    ///       -devMemoryOut /absolute/unique/output -devMemoryLabel candidate
    /// Do not pass -quit. This runner stops Play, removes its isolated save and exits with 0/1.
    /// These are observed EDITOR samples, not measurements of an iPhone browser or of the WebAssembly heap.
    /// </summary>
    [InitializeOnLoad]
    public static class WebMemoryCheck
    {
        const string Key = "RoadGame.WebMemoryCheck.Config";
        const string FinishKey = "RoadGame.WebMemoryCheck.Finish";
        const string SaveSuffix = "_webmemory20261123";
        const BindingFlags InstanceAny = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static readonly FieldInfo LoadingField = typeof(Game).GetField("loading", InstanceAny);
        static readonly FieldInfo ProgressField = typeof(LoadingScreen).GetField("progress", InstanceAny);
        static Config cfg;
        static Report report;
        static double deadline, idleSince = -1, gameStart = -1, lastDetailed = -1;
        static int lastFrame = -1;
        static float lastProgress = -1;
        static Stack<IEnumerator> steps;

        [Serializable] class Config { public string output, label; }
        [Serializable] class Fingerprint { public string path, sha256; }
        [Serializable] class Memory
        {
            public long totalAllocatedBytes, totalReservedBytes, totalUnusedReservedBytes, monoUsedBytes, monoHeapBytes;
        }
        [Serializable] class ObjectMemory
        {
            public string name, type;
            public long bytes, vertices, triangles;
            public bool readable;
        }
        [Serializable] class Objects
        {
            public int allLoadedMeshCount, allLoadedTextureCount, readableMeshCount, readableTexture2DCount;
            public long allLoadedMeshBytes, allLoadedTextureBytes, readableMeshBytes, vertices, triangles;
            public int sceneMeshFilters, sceneMeshColliders, sceneUniqueMeshCount;
            public long sceneUniqueMeshBytes;
            public List<ObjectMemory> largestMeshes = new List<ObjectMemory>();
            public List<ObjectMemory> largestTextures = new List<ObjectMemory>();
        }
        [Serializable] class Sample
        {
            public string phase;
            public double editorSeconds, playSeconds;
            public int frame, worldRootChildren;
            public float loadingProgress, gameSeconds;
            public bool ready;
            public Memory memory;
            public Objects objects;
        }
        [Serializable] class Check { public string name, details; public bool passed; }
        [Serializable] class Metric { public string name, value; }
        [Serializable] class Bundle
        {
            public string name, sourceFile;
            public bool applied;
            public List<Metric> metrics = new List<Metric>();
        }
        [Serializable] class Mutant
        {
            public int spawnId, visibleRenderers;
            public string logicalModel, creature, animator;
            public bool newlyCreated, hasMutantVisual, targetable;
            public long renderedVertices, renderedTriangles;
        }
        [Serializable] class Report
        {
            public string version = "WebMemoryCheck/1", label, createdUtc, unityVersion, platform;
            public string saveSuffix = SaveSuffix;
            public string measurementScope = "Unity Editor Play Mode, actual production Game.Start and World.GenerateRoutine. Memory totals include the Editor. Object totals include all loaded Editor/assets; scene mesh totals are reported separately. These are NOT iPhone/Safari/WebAssembly/GPU-process measurements.";
            public string peakScope = "Per-counter maxima of samples observed between game frames; not an exact intra-frame allocation peak. No forced GC, UnloadUnusedAssets or altered production loading path is used by this harness.";
            public string compilationScope = "UNITY_EDITOR is defined: WebGL-only player code guarded by !UNITY_EDITOR (including the buffered engine path) is not exercised.";
            public string baselineScope = "A label is metadata only. Source hashes identify the tested revision. Historical baseline claims require a separately preserved original source/build.";
            public bool passed, sourceChangedDuringRun;
            public string exception;
            public double readySeconds;
            public Memory observedPeaks = new Memory();
            public List<Fingerprint> sourceBefore = new List<Fingerprint>(), sourceAfter = new List<Fingerprint>();
            public List<Sample> samples = new List<Sample>();
            public List<Check> checks = new List<Check>();
            public List<Bundle> bundles = new List<Bundle>();
            public List<Mutant> mutants = new List<Mutant>();
        }

        static WebMemoryCheck()
        {
            var json = SessionState.GetString(Key, "");
            if (string.IsNullOrEmpty(json)) return;
            cfg = JsonUtility.FromJson<Config>(json);
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
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("WebMemoryCheck needs stopped Play Mode.");
            cfg = new Config
            {
                output = Path.GetFullPath(Arg("-devMemoryOut", "Docs/screenshots/web-memory-2026-11-23/" + DateTime.UtcNow.ToString("HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 6))),
                label = Arg("-devMemoryLabel", "current-source; not a historical baseline"),
            };
            Directory.CreateDirectory(cfg.output);
            if (File.Exists(Path.Combine(cfg.output, "web-memory-check.json")))
                throw new IOException("Choose a unique -devMemoryOut; an existing memory report will not be overwritten.");
            PlayerPrefs.DeleteKey("roadgame_save_v1" + SaveSuffix);
            PlayerPrefs.Save();
            SessionState.SetString(Key, JsonUtility.ToJson(cfg));
            SessionState.EraseString(Key + ".initial-report");
            SessionState.SetBool(FinishKey, false);
            SessionState.SetInt(FinishKey + ".exit", 1);
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
            p.d.introPending = false;
            p.d.tutorialDone = true;
            p.d.nextBonusAt = Progress.NowMs + 3600000;
            Game.ScriptedInput = t => Vector2.zero;
            UnityEngine.Random.InitState(17421);
        }

        static void StartReport()
        {
            if (report != null) return;
            var initial = SessionState.GetString(Key + ".initial-report", "");
            if (!string.IsNullOrEmpty(initial))
            {
                report = JsonUtility.FromJson<Report>(initial);
                if (report != null) return;
            }
            report = new Report
            {
                label = cfg.label,
                createdUtc = DateTime.UtcNow.ToString("o"),
                unityVersion = Application.unityVersion,
                platform = Application.platform.ToString(),
                sourceBefore = Fingerprints(),
            };
            TakeSample("editor-before-play", true);
            // Keep the genuine pre-Play sample and source revision through the normal Play domain reload.
            SessionState.SetString(Key + ".initial-report", JsonUtility.ToJson(report));
        }

        static void Tick()
        {
            try
            {
                StartReport();
                if (EditorApplication.timeSinceStartup > deadline) throw new TimeoutException("WebMemoryCheck: Game.Ready/integration checks exceeded 240 real seconds.");
                if (!EditorApplication.isPlaying)
                {
                    if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isUpdating || EditorApplication.isCompiling) return;
                    if (idleSince < 0) idleSince = EditorApplication.timeSinceStartup;
                    if (EditorApplication.timeSinceStartup - idleSince < 2) return;
                    EditorApplication.EnterPlaymode();
                    return;
                }
                if (gameStart < 0) gameStart = EditorApplication.timeSinceStartup;
                if (Time.frameCount != lastFrame)
                {
                    float progress = LoadingProgress();
                    bool detailed = Mathf.Abs(progress - lastProgress) > 0.0001f || EditorApplication.timeSinceStartup - lastDetailed > 0.5;
                    TakeSample(Game.I != null && Game.I.Ready ? "runtime-ready-frame" : "loading-" + Mathf.RoundToInt(progress * 100), detailed);
                    lastFrame = Time.frameCount;
                    lastProgress = progress;
                }
                if (steps == null)
                {
                    if (Game.I == null || !Game.I.Ready) return;
                    report.readySeconds = EditorApplication.timeSinceStartup - gameStart;
                    steps = new Stack<IEnumerator>();
                    steps.Push(IntegrationChecks());
                }
                while (steps.Count > 0)
                {
                    var step = steps.Peek();
                    if (!step.MoveNext()) { steps.Pop(); continue; }
                    if (step.Current is IEnumerator nested) { steps.Push(nested); continue; }
                    return;
                }
                TakeSample("complete", true);
                report.passed = true;
                WriteReport();
                Debug.Log("WEB_MEMORY_CHECK SUCCESS readySeconds=" + report.readySeconds.ToString("0.00") + " samples=" + report.samples.Count + " checks=" + report.checks.Count + " observedAllocatedPeakMiB=" + MiB(report.observedPeaks.totalAllocatedBytes) + " output=" + cfg.output);
                Finish(0);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                StartReport();
                report.passed = false;
                report.exception = error.ToString();
                try { TakeSample("failure", true); } catch (Exception sampleError) { Debug.LogWarning(sampleError.Message); }
                WriteReport();
                Finish(1);
            }
        }

        static IEnumerator IntegrationChecks()
        {
            var g = Game.I;
            TakeSample("game-ready", true);
            Require("ready_within_240_seconds", report.readySeconds <= 240, "Actual production Game.Ready reached in " + report.readySeconds.ToString("0.00") + " real seconds after Play started.");
            Require("work_audio_muted", WorkAudioMute.Apply(), "Editor master mute is active; no Sound/Music save settings were changed.");
            Require("both_imported_bundles", ImportedLevel.Active != null && ImportedLevel.Active.Applied && ImportedLevel.Wetlands != null && ImportedLevel.Wetlands.Applied,
                "Dust Flats and Toxic Wetlands both report Applied after production World.GenerateRoutine.");
            Require("both_driving_surfaces", DustFlatsSurfaces.Active && WetlandSurfaces.Active, "Both edited maps retain their matching gameplay surfaces.");
            report.bundles.Add(BundleMetrics("Dust Flats", ImportedLevel.Active));
            report.bundles.Add(BundleMetrics("Toxic Wetlands", ImportedLevel.Wetlands));
            g.player.turret.enabled = false;
            g.player.harpooner.enabled = false;
            foreach (var arm in g.player.arms) if (arm != null) arm.enabled = false;
            yield return Frames(15);
            TakeSample("ready-after-15-frames", true);

            // An explicit post-startup stress/integration phase: construct one actual spawn of every zone1 creature.
            // This is not presented as the natural first-load population or as a novice playthrough.
            g.world.enabled = false;
            int builtBefore = Mutants.Built, newlyCreated = 0;
            var tested = new HashSet<ModelId>();
            Target firstFoot = null;
            foreach (var spawn in g.world.zoneSpawns[1])
            {
                if (spawn.spec.kind == TargetKind.Prop || !tested.Add(spawn.spec.model)) continue;
                bool created = spawn.target == null;
                var target = spawn.target;
                if (target == null)
                {
                    var create = typeof(World).GetMethod("CreateTarget", InstanceAny);
                    if (create == null) throw new MissingMethodException("World.CreateTarget");
                    target = (Target)create.Invoke(g.world, new object[] { spawn });
                    newlyCreated++;
                }
                target.ResetForSpawn(false);
                target.enabled = false;
                if (!g.world.activeTargets.Contains(target)) g.world.activeTargets.Add(target);
                var visual = target.GetComponentInChildren<MutantVisual>(true);
                var animator = target.GetComponent<MutantAnimator>();
                var info = Mutants.InfoFor(spawn.spec.model);
                var mutant = new Mutant
                {
                    spawnId = spawn.id, logicalModel = spawn.spec.model.ToString(), creature = info != null ? info.name : "",
                    animator = animator != null ? animator.GetType().Name : "", newlyCreated = created,
                    hasMutantVisual = visual != null, targetable = target.Targetable,
                };
                foreach (var renderer in target.GetComponentsInChildren<MeshRenderer>(true))
                {
                    if (!renderer.enabled || !renderer.gameObject.activeInHierarchy) continue;
                    var mf = renderer.GetComponent<MeshFilter>();
                    if (mf == null || mf.sharedMesh == null) continue;
                    mutant.visibleRenderers++;
                    mutant.renderedVertices += mf.sharedMesh.vertexCount;
                    mutant.renderedTriangles += TriangleCount(mf.sharedMesh);
                }
                report.mutants.Add(mutant);
                Require("mutant_" + spawn.spec.model, visual != null && animator != null && info != null && target.Targetable && mutant.visibleRenderers > 0 && mutant.renderedVertices > 0,
                    "Production World.CreateTarget spawn=" + spawn.id + " model=" + spawn.spec.model + " creature=" + mutant.creature + " animator=" + mutant.animator + " visibleRenderers=" + mutant.visibleRenderers);
                if (firstFoot == null && spawn.spec.kind == TargetKind.Foot) firstFoot = target;
                yield return Frames(1);
            }
            Require("all_seven_mutants", tested.Count == 7 && Mutants.Built >= builtBefore + newlyCreated,
                "One real logical spawn of all seven creatures: count=" + tested.Count + " new=" + newlyCreated + " Mutants.Built=" + Mutants.Built);
            yield return Frames(3); // Let deferred destruction of the superseded generated bodies finish.
            TakeSample("all-seven-mutants-materialized", true);
            if (firstFoot == null) throw new InvalidOperationException("No foot mutant available for death-path check.");
            bool previousWick = DevOptions.JohnWick;
            DevOptions.SetJohnWick(true);
            firstFoot.Hit(1, false, g.player.Pos);
            DevOptions.SetJohnWick(previousWick);
            Require("mutant_production_death_path", firstFoot.dead && firstFoot.hp == 0 && firstFoot.spawn.Kills == 1,
                "A production Target.Hit killed " + firstFoot.spec.model + " and persisted its first spawn kill. Boss/gate/drive/reload acceptance is covered separately by DevGameplayCheck.");
            yield return Frames(15);
            TakeSample("mutant-kill-after-15-frames", true);
            g.world.enabled = true;
        }

        static float LoadingProgress()
        {
            var g = Game.I;
            if (g == null) return 0;
            if (g.Ready) return 1;
            var loading = LoadingField != null ? LoadingField.GetValue(g) as LoadingScreen : null;
            return loading != null && ProgressField != null ? (float)ProgressField.GetValue(loading) : 0;
        }

        static void TakeSample(string phase, bool detailed)
        {
            var g = Game.I;
            var memory = new Memory
            {
                totalAllocatedBytes = Profiler.GetTotalAllocatedMemoryLong(),
                totalReservedBytes = Profiler.GetTotalReservedMemoryLong(),
                totalUnusedReservedBytes = Profiler.GetTotalUnusedReservedMemoryLong(),
                monoUsedBytes = Profiler.GetMonoUsedSizeLong(),
                monoHeapBytes = Profiler.GetMonoHeapSizeLong(),
            };
            var sample = new Sample
            {
                phase = phase,
                editorSeconds = EditorApplication.timeSinceStartup,
                playSeconds = gameStart >= 0 ? EditorApplication.timeSinceStartup - gameStart : 0,
                frame = Application.isPlaying ? Time.frameCount : -1,
                loadingProgress = LoadingProgress(),
                ready = g != null && g.Ready,
                gameSeconds = g != null ? g.SessionTime : 0,
                worldRootChildren = World.I != null ? World.I.transform.childCount : 0,
                memory = memory,
            };
            // Read the totals before enumerating objects: the diagnostic's own short-lived lists are not in this sample.
            if (detailed) { sample.objects = ObjectMetrics(); lastDetailed = EditorApplication.timeSinceStartup; }
            report.samples.Add(sample);
            var peak = report.observedPeaks;
            peak.totalAllocatedBytes = Math.Max(peak.totalAllocatedBytes, memory.totalAllocatedBytes);
            peak.totalReservedBytes = Math.Max(peak.totalReservedBytes, memory.totalReservedBytes);
            peak.totalUnusedReservedBytes = Math.Max(peak.totalUnusedReservedBytes, memory.totalUnusedReservedBytes);
            peak.monoUsedBytes = Math.Max(peak.monoUsedBytes, memory.monoUsedBytes);
            peak.monoHeapBytes = Math.Max(peak.monoHeapBytes, memory.monoHeapBytes);
            if (detailed) Debug.Log("WEB_MEMORY_SAMPLE phase=" + phase + " frame=" + sample.frame + " progress=" + sample.loadingProgress.ToString("0.000") + " allocatedMiB=" + MiB(memory.totalAllocatedBytes) + " reservedMiB=" + MiB(memory.totalReservedBytes) + " managedUsedMiB=" + MiB(memory.monoUsedBytes) + " meshMiB=" + MiB(sample.objects.allLoadedMeshBytes) + " textureMiB=" + MiB(sample.objects.allLoadedTextureBytes));
        }

        static Objects ObjectMetrics()
        {
            var result = new Objects();
            foreach (var mesh in Resources.FindObjectsOfTypeAll<Mesh>())
            {
                if (mesh == null) continue;
                long bytes = Profiler.GetRuntimeMemorySizeLong(mesh);
                long triangles = TriangleCount(mesh);
                result.allLoadedMeshCount++;
                result.allLoadedMeshBytes += bytes;
                result.vertices += mesh.vertexCount;
                result.triangles += triangles;
                if (mesh.isReadable) { result.readableMeshCount++; result.readableMeshBytes += bytes; }
                result.largestMeshes.Add(new ObjectMemory { name = mesh.name, type = "Mesh", bytes = bytes, vertices = mesh.vertexCount, triangles = triangles, readable = mesh.isReadable });
            }
            foreach (var texture in Resources.FindObjectsOfTypeAll<Texture>())
            {
                if (texture == null) continue;
                long bytes = Profiler.GetRuntimeMemorySizeLong(texture);
                bool readable = texture is Texture2D t && t.isReadable;
                result.allLoadedTextureCount++;
                result.allLoadedTextureBytes += bytes;
                if (readable) result.readableTexture2DCount++;
                result.largestTextures.Add(new ObjectMemory { name = texture.name, type = texture.GetType().Name, bytes = bytes, readable = readable });
            }
            var referenced = new HashSet<Mesh>();
            foreach (var mf in UnityEngine.Object.FindObjectsByType<MeshFilter>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            { result.sceneMeshFilters++; if (mf.sharedMesh != null) referenced.Add(mf.sharedMesh); }
            foreach (var collider in UnityEngine.Object.FindObjectsByType<MeshCollider>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            { result.sceneMeshColliders++; if (collider.sharedMesh != null) referenced.Add(collider.sharedMesh); }
            result.sceneUniqueMeshCount = referenced.Count;
            foreach (var mesh in referenced) result.sceneUniqueMeshBytes += Profiler.GetRuntimeMemorySizeLong(mesh);
            KeepLargest(result.largestMeshes);
            KeepLargest(result.largestTextures);
            return result;
        }

        static long TriangleCount(Mesh mesh)
        {
            long count = 0;
            for (int s = 0; s < mesh.subMeshCount; s++) if (mesh.GetTopology(s) == MeshTopology.Triangles) count += (long)mesh.GetIndexCount(s) / 3;
            return count;
        }
        static void KeepLargest(List<ObjectMemory> values)
        { values.Sort((a, b) => b.bytes.CompareTo(a.bytes)); if (values.Count > 12) values.RemoveRange(12, values.Count - 12); }

        static Bundle BundleMetrics(string name, ImportedLevel level)
        {
            var bundle = new Bundle { name = name, applied = level != null && level.Applied, sourceFile = level != null ? level.SourceFile : "" };
            if (level == null) return bundle;
            foreach (var property in typeof(ImportedLevel).GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                if (!property.CanRead || property.GetIndexParameters().Length != 0) continue;
                var type = property.PropertyType;
                if (type != typeof(int) && type != typeof(long) && type != typeof(float) && type != typeof(double)) continue;
                try { bundle.metrics.Add(new Metric { name = property.Name, value = Convert.ToString(property.GetValue(level), CultureInfo.InvariantCulture) }); }
                catch (Exception error) { bundle.metrics.Add(new Metric { name = property.Name, value = "unavailable: " + error.Message }); }
            }
            return bundle;
        }

        static List<Fingerprint> Fingerprints()
        {
            var list = new List<Fingerprint>();
            foreach (string path in new[]
            {
                "Assets/RoadGame/Scripts/Game.cs", "Assets/RoadGame/Scripts/World/World.cs",
                "Assets/RoadGame/Scripts/World/ImportedLevel.cs", "Assets/RoadGame/Scripts/World/Mutants.cs",
                "Assets/RoadGame/Scripts/Rendering/MeshBuilder.cs", "Assets/RoadGame/Scripts/Rendering/ModelsProps.cs",
                "Assets/RoadGame/Scripts/Rendering/Mats.cs", "Assets/RoadGame/Scripts/Rendering/Tex.cs",
                "Assets/RoadGame/Scripts/Fx/Sfx.cs", "Assets/RoadGame/Scripts/Audio/EngineAudio.cs",
                "Assets/RoadGame/Editor/AudioImport.cs", "Assets/RoadGame/Resources/Levels/DustFlatsV13/manifest.json",
                "Assets/RoadGame/Resources/Levels/ToxicWetlandsZ1/manifest.json", "Assets/RoadGame/Resources/Creatures/WetlandsMutants/manifest.json",
            })
            {
                if (!File.Exists(path)) continue;
                using (var hash = SHA256.Create())
                    list.Add(new Fingerprint { path = path, sha256 = BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant() });
            }
            return list;
        }

        static void WriteReport()
        {
            report.sourceAfter = Fingerprints();
            report.sourceChangedDuringRun = report.sourceBefore.Count != report.sourceAfter.Count;
            for (int i = 0; i < Math.Min(report.sourceBefore.Count, report.sourceAfter.Count); i++)
                if (report.sourceBefore[i].path != report.sourceAfter[i].path || report.sourceBefore[i].sha256 != report.sourceAfter[i].sha256) report.sourceChangedDuringRun = true;
            File.WriteAllText(Path.Combine(cfg.output, "web-memory-check.json"), JsonUtility.ToJson(report, true));
        }
        static string MiB(long bytes) => (bytes / 1048576.0).ToString("0.00", CultureInfo.InvariantCulture);
        static void Require(string name, bool passed, string details)
        {
            report.checks.Add(new Check { name = name, passed = passed, details = details });
            Debug.Log("WEB_MEMORY_CHECK " + (passed ? "PASS " : "FAIL ") + name + " | " + details);
            if (!passed) throw new InvalidOperationException("WEB_MEMORY_CHECK failed: " + name + " | " + details);
        }
        static IEnumerator Frames(int count)
        { int frame = Time.frameCount + count; while (Time.frameCount < frame) yield return null; }
        static void Finish(int code)
        {
            SessionState.SetInt(FinishKey + ".exit", code);
            SessionState.SetBool(FinishKey, true);
            EditorApplication.update -= Tick;
            if (EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.isPlaying = false;
            else CleanAndExit();
        }
        static void OnPlayState(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.ExitingEditMode || state == PlayModeStateChange.EnteredPlayMode)
            { WorkAudioMute.Apply(); SaveSystem.KeySuffix = SaveSuffix; Game.TestSetup = SetupFresh; }
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
            SessionState.EraseString(Key + ".initial-report");
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
