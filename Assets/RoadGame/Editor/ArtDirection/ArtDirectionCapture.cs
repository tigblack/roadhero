using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;

namespace RoadGame.EditorTools
{
    /// <summary>Temporary art-direction experiment. No scene, shared mesh or gameplay material is saved.</summary>
    [InitializeOnLoad]
    public static class ArtDirectionCapture
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
        const string ShaderPath = "Assets/RoadGame/Editor/ArtDirection/ArtDirectionSurface.shader";
        public const int Width = 540, Height = 1170;
        public static string ManifestPath = "ArtDirectionScreenshots/capture-manifest.txt";
        static bool preparing, staged, frozen;
        static int stageFrame;
        static double deadline;
        static bool oldOptionsEnabled;
        static EnterPlayModeOptions oldOptions;
        static string oldSaveSuffix;
        static RenderPipelineAsset oldQualityPipeline;
        static UniversalRenderPipelineAsset pipeline;
        static Volume grade;
        static Enemy enemy;
        static EditorWindow captureView;
        static Material inkMaterial;
        static string baseline;
        static List<Transform> lockedTransforms;
        static List<Text> lockedTexts;
        static readonly Dictionary<Renderer, Material[]> originals = new Dictionary<Renderer, Material[]>();
        static readonly Dictionary<MeshFilter, Mesh> originalMeshes = new Dictionary<MeshFilter, Mesh>();
        static readonly Dictionary<Mesh, Mesh> lowMeshes = new Dictionary<Mesh, Mesh>();
        static readonly Dictionary<Mesh, Mesh> roundedMeshes = new Dictionary<Mesh, Mesh>();
        static readonly Dictionary<Material, Material> previewMaterials = new Dictionary<Material, Material>();
        static readonly List<UnityEngine.Object> temporary = new List<UnityEngine.Object>();
        public static string State { get; private set; } = "idle";
        public static int Style { get; private set; } = -1;

        static ArtDirectionCapture() { }

        public static string Begin()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new Exception("Begin requires stopped Play Mode.");
            if (AssetDatabase.LoadAssetAtPath<Shader>(ShaderPath) == null) throw new Exception("Preview shader has not imported.");
            foreach (var item in temporary) if (item != null) UnityEngine.Object.DestroyImmediate(item);
            temporary.Clear(); originals.Clear(); originalMeshes.Clear(); lowMeshes.Clear(); roundedMeshes.Clear(); previewMaterials.Clear();
            Directory.CreateDirectory(Path.GetFullPath("ArtDirectionScreenshots"));
            oldOptionsEnabled = EditorSettings.enterPlayModeOptionsEnabled;
            oldOptions = EditorSettings.enterPlayModeOptions;
            EditorSettings.enterPlayModeOptionsEnabled = true;
            EditorSettings.enterPlayModeOptions = EnterPlayModeOptions.DisableDomainReload;
            oldQualityPipeline = QualitySettings.renderPipeline;
            oldSaveSuffix = SaveSystem.KeySuffix;
            SaveSystem.KeySuffix = "_art_direction_preview";
            Game.Autopilot = Game.AutopilotBoss = Game.AutopilotEnemiesOnly = false;
            Game.TestSetup = SetupProgress;
            EditorSceneManager.OpenScene(ProjectSetup.ScenePath, OpenSceneMode.Single);
            SetGameViewSize();
            State = "starting";
            preparing = true; staged = frozen = false;
            deadline = EditorApplication.timeSinceStartup + 90;
            EditorApplication.update -= Tick;
            EditorApplication.update += Tick;
            EditorApplication.EnterPlaymode();
            return State;
        }

        static void SetupProgress(Progress p)
        {
            UnityEngine.Random.InitState(17421);
            Application.runInBackground = true;
            var d = p.d;
            d.tutorialDone = true;
            d.maxHp = 1600; d.hp = 1420; d.regen = 0;
            d.dmg[0] = 144; d.weaponLevel[0] = 4; d.weaponCopies[0] = 2;
            d.gems = 245; d.unlockedZone = 0;
            d.px = 18f; d.pz = 57f; d.heading = 145f;
            d.soundOn = d.musicOn = false;
            d.nextBonusAt = Progress.NowMs + 3600000;
            pipeline = UnityEngine.Object.Instantiate((UniversalRenderPipelineAsset)GraphicsSettings.currentRenderPipeline);
            pipeline.name = "Art Direction Temporary URP";
            QualitySettings.renderPipeline = pipeline;
            temporary.Add(pipeline);
        }

        static void Tick()
        {
            if (!preparing) return;
            try
            {
                if (EditorApplication.timeSinceStartup > deadline) throw new Exception("Timed out preparing fixed art-direction scene.");
                if (!EditorApplication.isPlaying || Game.I == null || !Game.I.Ready) return;
                if (!staged)
                {
                    StageEncounter();
                    staged = true;
                    stageFrame = Time.frameCount;
                    State = "settling HUD";
                    return;
                }
                // Allow real Hud.Update and Overlay.LateUpdate to lay out the staged state once.
                if (Time.frameCount <= stageFrame + 1) return;
                FreezeAndRecord();
                preparing = false;
                State = "frozen";
                EditorApplication.update -= Tick;
                Apply(0);
            }
            catch (Exception error)
            {
                preparing = false;
                EditorApplication.update -= Tick;
                State = "failed: " + error;
                Debug.LogException(error);
            }
        }

        static void StageEncounter()
        {
            var g = Game.I;
            Time.timeScale = 0f;
            g.enabled = false;
            g.cameraRig.enabled = false;
            g.player.enabled = false;
            foreach (var m in UnityEngine.Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (m != null && m.GetType().Assembly == typeof(Game).Assembly &&
                    !(m is Hud) && !(m is Overlay) && !(m is Minimap) && !(m is SafeArea)) m.enabled = false;
            var arena = g.world.bossSpawns[0].pos;
            g.player.Teleport(arena + new Vector3(4.2f, 0f, -7.5f), 145f);
            g.world.Tick();
            var sp = g.world.bossSpawns[0];
            enemy = (Enemy)sp.target;
            if (enemy == null) throw new Exception("Actual Mammoth spawn was not activated.");
            enemy.ResetForSpawn(false);
            enemy.transform.SetPositionAndRotation(arena + new Vector3(-1.7f, 0f, 3f), Quaternion.Euler(0f, 150f, 0f));
            enemy.hp = 2860; enemy.enabled = false;
            foreach (var t in g.world.activeTargets)
                if (t != null && t != enemy && t.IsEnemy) t.gameObject.SetActive(false);
            g.world.activeTargets.RemoveAll(t => t == null || !t.gameObject.activeInHierarchy);
            if (!g.world.activeTargets.Contains(enemy)) g.world.activeTargets.Add(enemy);
            var focus = new GameObject("Art Direction Fixed Camera Focus").transform;
            focus.position = arena + new Vector3(1f, 0f, -1.8f);
            g.cameraRig.target = focus;
            g.cameraRig.pitch = 48f;
            g.cameraRig.zoom = 0.69f;
            g.cameraRig.Snap();
            g.cameraRig.enabled = false;
            g.cam.targetTexture = null;
            g.cam.allowDynamicResolution = false;
            g.cam.aspect = Width / (float)Height;
            var fixedProjection = Matrix4x4.Perspective(g.cam.fieldOfView, g.cam.aspect, g.cam.nearClipPlane, g.cam.farClipPlane);
            g.cam.projectionMatrix = g.cam.nonJitteredProjectionMatrix = fixedProjection;
            g.cam.GetUniversalAdditionalCameraData().antialiasing = AntialiasingMode.None;
            // Aim the actual roof cannon back towards the approaching boss while the car turns away.
            var yaw = g.player.transform.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "TurretYaw");
            if (yaw != null)
            {
                var direction = enemy.Pos - yaw.position; direction.y = 0;
                yaw.rotation = Quaternion.LookRotation(direction);
            }
            var muzzleTransform = g.player.transform.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "Barrel0");
            Vector3 muzzle = muzzleTransform != null ? muzzleTransform.TransformPoint(new Vector3(0f, 0f, Models.TurretBarrelLength)) : g.player.Pos + Vector3.up * 2f;
            Vector3 impact = enemy.Pos + new Vector3(1.8f, 2f, -1.2f);
            if (muzzleTransform != null)
            {
                var flash = muzzleTransform.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "Flash");
                if (flash != null) { flash.gameObject.SetActive(true); flash.localScale = Vector3.one * 1.3f; }
            }
            var tracerObject = new GameObject("Art Direction Frozen Cannon Tracer");
            var line = tracerObject.AddComponent<LineRenderer>();
            line.sharedMaterial = Mats.NewUnlit("ArtDirectionTracer", null, true);
            line.positionCount = 2; line.useWorldSpace = true;
            line.SetPositions(new[] { Vector3.Lerp(muzzle, impact, 0.25f), Vector3.Lerp(muzzle, impact, 0.78f) });
            line.startWidth = 0.075f; line.endWidth = 0.04f;
            line.startColor = new Color(1f, 0.84f, 0.2f); line.endColor = new Color(1f, 0.45f, 0.03f);
            line.numCapVertices = 2;
            g.fx.MuzzleSmoke(muzzle, (impact - muzzle).normalized);
            g.fx.ShellImpact(impact, (muzzle - impact).normalized, true);
            g.overlay.DamageNumber(impact + new Vector3(3.1f, 1.4f, 1f), 144, true);
            foreach (var ps in UnityEngine.Object.FindObjectsByType<ParticleSystem>(FindObjectsSortMode.None))
            {
                ps.Simulate(0.035f, false, false, false);
                ps.Pause(false);
            }
            // A title banner would mask the scene; keep the genuine HUD and boss bar instead.
            var banner = g.hud.transform.Find("SafeArea/Banner");
            foreach (var rt in g.hud.GetComponentsInChildren<RectTransform>(true))
                if (rt.name == "Banner" || rt.name == "Popup") rt.gameObject.SetActive(false);
            foreach (var audio in UnityEngine.Object.FindObjectsByType<AudioSource>(FindObjectsSortMode.None)) audio.Stop();
        }

        static void FreezeAndRecord()
        {
            var g = Game.I;
            foreach (var m in UnityEngine.Object.FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (m != null && m.GetType().Assembly == typeof(Game).Assembly && !(m is Graphic)) m.enabled = false;
            foreach (var anim in UnityEngine.Object.FindObjectsByType<Animator>(FindObjectsSortMode.None)) anim.speed = 0;
            foreach (var body in UnityEngine.Object.FindObjectsByType<Rigidbody>(FindObjectsSortMode.None)) body.isKinematic = true;
            foreach (var ps in UnityEngine.Object.FindObjectsByType<ParticleSystem>(FindObjectsSortMode.None)) ps.Pause(false);
            foreach (var volume in UnityEngine.Object.FindObjectsByType<Volume>(FindObjectsSortMode.None)) volume.weight = 0f;
            grade = new GameObject("Art Direction Preview Grade").AddComponent<Volume>();
            grade.isGlobal = true; grade.priority = 1000;
            grade.sharedProfile = ScriptableObject.CreateInstance<VolumeProfile>();
            temporary.Add(grade.sharedProfile);
            var frustum = GeometryUtility.CalculateFrustumPlanes(g.cam);
            foreach (var renderer in UnityEngine.Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None))
            {
                if (!renderer.gameObject.activeInHierarchy || !GeometryUtility.TestPlanesAABB(frustum, renderer.bounds)) continue;
                if (!renderer.sharedMaterials.Any(m => m != null && m.shader.name == "RoadGame/Toon")) continue;
                originals[renderer] = renderer.sharedMaterials;
                var filter = renderer.GetComponent<MeshFilter>();
                if (filter != null && filter.sharedMesh != null &&
                    !renderer.sharedMaterials.Any(m => m != null && (m.name == "Ground" || m.name.StartsWith("Road")))) originalMeshes[filter] = filter.sharedMesh;
            }
            lockedTransforms = UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsSortMode.None).Where(t => t.GetComponent<Light>() == null).OrderBy(t => t.GetEntityId().ToString()).ToList();
            lockedTexts = UnityEngine.Object.FindObjectsByType<Text>(FindObjectsSortMode.None).OrderBy(t => t.GetEntityId().ToString()).ToList();
            frozen = true;
            baseline = Fingerprint();
            WriteManifest();
            Debug.Log("ArtDirection: frozen actual Game scene. Mesh renderers=" + originals.Count + ", GameView=" + GameViewTargetSize());
        }

        public static string Apply(int style)
        {
            if (!frozen) throw new Exception("Scene is not frozen: " + State);
            if (style < 0 || style > 4) throw new ArgumentOutOfRangeException(nameof(style));
            AssertUnchanged();
            Style = style;
            var shader = AssetDatabase.LoadAssetAtPath<Shader>(ShaderPath);
            if (inkMaterial == null)
            {
                inkMaterial = new Material(AssetDatabase.LoadAssetAtPath<Shader>("Assets/RoadGame/Editor/ArtDirection/ArtDirectionInk.shader"));
                inkMaterial.SetFloat("_OutlineWidth", 3.5f);
                inkMaterial.renderQueue = (int)RenderQueue.Geometry + 1;
                temporary.Add(inkMaterial);
            }
            foreach (var pair in originalMeshes)
            {
                var source = pair.Value;
                if (style == 2)
                {
                    if (!lowMeshes.TryGetValue(source, out var low)) { low = ArtDirectionMeshes.LowPoly(source); lowMeshes.Add(source, low); temporary.Add(low); }
                    pair.Key.sharedMesh = low;
                }
                else if (style == 0)
                {
                    if (!roundedMeshes.TryGetValue(source, out var rounded)) { rounded = ArtDirectionMeshes.Rounded(source); roundedMeshes.Add(source, rounded); temporary.Add(rounded); }
                    pair.Key.sharedMesh = rounded;
                }
                else pair.Key.sharedMesh = source;
            }
            foreach (var pair in originals)
            {
                bool outline = style == 3 && pair.Value.Any(m => m != null && m.name != "Ground" && !m.name.StartsWith("Road"));
                var replacements = new Material[pair.Value.Length + (outline ? 1 : 0)];
                for (int i = 0; i < pair.Value.Length; i++)
                {
                    var original = pair.Value[i];
                    if (original == null || original.shader.name != "RoadGame/Toon") { replacements[i] = original; continue; }
                    if (!previewMaterials.TryGetValue(original, out var material))
                    {
                        material = new Material(shader) { name = "Art Direction / " + original.name };
                        material.CopyMatchingPropertiesFromMaterial(original);
                        material.SetTexture("_DetailMap", Tex.Grime());
                        material.SetFloat("_Ground", original.name == "Ground" ? 1f : original.name.StartsWith("Road") ? 2f : 0f);
                        previewMaterials.Add(original, material); temporary.Add(material);
                    }
                    material.SetFloat("_Style", style);
                    material.SetFloat("_OutlineWidth", style == 3 ? 2.5f : 0f);
                    material.SetColor("_OutlineColor", new Color(0.03f, 0.03f, 0.055f));
                    material.SetShaderPassEnabled("SRPDefaultUnlit", false);
                    replacements[i] = material;
                }
                if (outline) replacements[replacements.Length - 1] = inkMaterial;
                pair.Key.sharedMaterials = replacements;
            }
            ConfigureLightAndGrade(style);
            EditorApplication.QueuePlayerLoopUpdate();
            foreach (var view in Resources.FindObjectsOfTypeAll<EditorWindow>()) if (view.GetType().Name == "GameView") view.Repaint();
            AssertUnchanged();
            return "style=" + style + "; fixed scene=" + baseline + "; GameView=" + GameViewTargetSize();
        }

        static void ConfigureLightAndGrade(int style)
        {
            var g = Game.I;
            pipeline.renderScale = style == 4 ? 1f / 3f : 1f;
#pragma warning disable CS0618
            pipeline.upscalingFilter = style == 4 ? UpscalingFilterSelection.Point : UpscalingFilterSelection.Linear;
#pragma warning restore CS0618
            pipeline.msaaSampleCount = style == 4 ? 1 : 4;
            pipeline.shadowDistance = 130f;
            pipeline.shadowCascadeCount = 2;
            pipeline.mainLightShadowmapResolution = 4096;
            g.sun.transform.rotation = Quaternion.Euler(style == 1 ? 34f : 52f, 135f, 0);
            g.sun.intensity = style == 1 ? 1.45f : 1.1f;
            g.sun.color = style == 1 ? new Color(1f, 0.9f, 0.76f) : new Color(1f, 0.97f, 0.9f);
            g.sun.shadows = style == 0 || style == 1 ? LightShadows.Soft : LightShadows.Hard;
            g.sun.shadowStrength = style == 0 ? 0.5f : style == 1 ? 0.85f : 0.8f;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = style == 1 ? new Color(0.43f, 0.52f, 0.65f) : new Color(0.64f, 0.72f, 0.9f);
            RenderSettings.ambientEquatorColor = new Color(0.35f, 0.34f, 0.32f);
            RenderSettings.ambientGroundColor = new Color(0.25f, 0.2f, 0.15f);
            RenderSettings.fog = false;
            Mats.SetEnvironment(Content.Zones[0]);
            grade.sharedProfile.components.Clear();
            var colors = grade.sharedProfile.Add<ColorAdjustments>(true);
            colors.saturation.Override(style == 0 ? 28 : style == 1 ? -18 : style == 2 ? 8 : style == 3 ? 5 : 15);
            colors.contrast.Override(style == 1 ? 15 : style == 3 ? 18 : 5);
            colors.postExposure.Override(style == 1 ? 0.1f : 0f);
            var tone = grade.sharedProfile.Add<Tonemapping>(true);
            tone.mode.Override(style == 1 ? TonemappingMode.ACES : TonemappingMode.Neutral);
            if (style == 0 || style == 1)
            {
                var bloom = grade.sharedProfile.Add<Bloom>(true);
                bloom.threshold.Override(1.1f); bloom.intensity.Override(style == 0 ? 0.35f : 0.12f);
            }
            g.cam.GetUniversalAdditionalCameraData().renderPostProcessing = style != 4;
        }

        public static string Verify()
        {
            AssertUnchanged();
            var size = GameViewTargetSize();
            if (Mathf.RoundToInt(size.x) != Width || Mathf.RoundToInt(size.y) != Height) throw new Exception("Incorrect actual GameView: " + size);
            var playViewType = typeof(Editor).Assembly.GetType("UnityEditor.PlayModeView");
            var actualMain = playViewType.GetMethod("GetMainPlayModeView", Any).Invoke(null, null);
            if (!ReferenceEquals(actualMain, captureView)) throw new Exception("The pinned GameView is not the live main play view.");
            var texture = playViewType.GetField("m_TargetTexture", Any).GetValue(captureView) as RenderTexture;
            if (texture == null || !texture.IsCreated() || texture.width != Width || texture.height != Height)
                throw new Exception("GameView render target is missing or incorrect: " + texture);
            return "PASS fixed transforms/camera projection/HP/HUD, style=" + Style + ", actual GameView RT=" + texture.width + "x" + texture.height + ", fingerprint=" + baseline;
        }

        static string Fingerprint()
        {
            var b = new StringBuilder();
            foreach (var t in lockedTransforms)
            {
                if (t == null) throw new Exception("A frozen transform was destroyed.");
                b.Append(t.GetEntityId().ToString()).Append(':').Append(t.localPosition.ToString("F5")).Append(t.localRotation.ToString("F5")).Append(t.localScale.ToString("F5"));
            }
            foreach (var t in lockedTexts) b.Append(t.GetEntityId().ToString()).Append(':').Append(t.text);
            var g = Game.I;
            b.Append(g.cam.transform.position.ToString("F5")).Append(g.cam.transform.rotation.ToString("F5")).Append(g.cam.fieldOfView).Append(g.progress.d.hp).Append(enemy.hp);
            b.Append(g.cam.aspect.ToString("F6")).Append(g.cam.rect.ToString("F5")).Append(g.cam.projectionMatrix.ToString("F6")).Append(g.cam.nonJitteredProjectionMatrix.ToString("F6")).Append(g.cam.nearClipPlane).Append(g.cam.farClipPlane);
            b.Append(g.cam.pixelRect.ToString("F5")).Append(g.cam.WorldToScreenPoint(g.player.Pos).ToString("F5")).Append(g.cam.WorldToScreenPoint(enemy.Pos).ToString("F5"));
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(b.ToString()))).Replace("-", "").ToLowerInvariant();
        }

        static void AssertUnchanged()
        {
            if (Fingerprint() != baseline) throw new Exception("Fixed scene or HUD changed between styles.");
        }

        static void WriteManifest()
        {
            var g = Game.I;
            var report = new StringBuilder();
            report.AppendLine("Scene: " + ProjectSetup.ScenePath).AppendLine("Actual GameView: " + GameViewTargetSize());
            report.AppendLine("One staged combat moment using actual player, Mammoth, zone0 world geometry and live HUD.");
            report.AppendLine("Camera position: " + g.cam.transform.position.ToString("F6")).AppendLine("Camera rotation: " + g.cam.transform.rotation.eulerAngles.ToString("F6"));
            report.AppendLine("Camera FOV: " + g.cam.fieldOfView).AppendLine("Player: " + g.player.Pos.ToString("F6")).AppendLine("Mammoth: " + enemy.Pos.ToString("F6"));
            report.AppendLine("HP player: " + g.progress.d.hp + "; Mammoth: " + enemy.hp).AppendLine("Fixed state SHA256: " + baseline);
            report.AppendLine("Pixel variant: URP renderScale1/3, Point upscaling, 180x390 world at540x1170; identical full-resolution HUD for readability.");
            File.WriteAllText(Path.GetFullPath(ManifestPath), report.ToString());
        }

        static void SetGameViewSize()
        {
            var assembly = typeof(Editor).Assembly;
            var sizesType = assembly.GetType("UnityEditor.GameViewSizes");
            var sizes = sizesType.GetProperty("instance", Any | BindingFlags.FlattenHierarchy).GetValue(null);
            var groupType = sizesType.GetProperty("currentGroupType", Any)?.GetValue(sizes)
                ?? Enum.Parse(assembly.GetType("UnityEditor.GameViewSizeGroupType"), "Standalone");
            var group = sizesType.GetMethod("GetGroup", Any).Invoke(sizes, new[] { groupType });
            int count = (int)group.GetType().GetMethod("GetTotalCount", Any).Invoke(group, null);
            var sizeType = assembly.GetType("UnityEditor.GameViewSize");
            var kind = Enum.Parse(assembly.GetType("UnityEditor.GameViewSizeType"), "FixedResolution");
            var size = Activator.CreateInstance(sizeType, Any, null, new object[] { kind, Width, Height, "Scarbound Art Direction" }, null);
            group.GetType().GetMethod("AddCustomSize", Any).Invoke(group, new[] { size });
            captureView = EditorWindow.GetWindow(assembly.GetType("UnityEditor.GameView"));
            captureView.GetType().GetProperty("selectedSizeIndex", Any).SetValue(captureView, count);
            captureView.Show(); captureView.Focus(); captureView.Repaint();
        }

        static Vector2 GameViewTargetSize()
        {
            if (captureView == null) SetGameViewSize();
            return (Vector2)captureView.GetType().GetProperty("targetSize", Any).GetValue(captureView);
        }

        public static string Finish()
        {
            if (frozen) Verify();
            EditorApplication.update -= Tick;
            preparing = frozen = false;
            QualitySettings.renderPipeline = oldQualityPipeline;
            Time.timeScale = 1f;
            Game.TestSetup = null;
            Game.ScriptedInput = null;
            Game.Autopilot = Game.AutopilotBoss = Game.AutopilotEnemiesOnly = false;
            EditorApplication.playModeStateChanged += AfterStop;
            EditorApplication.ExitPlaymode();
            State = "finished";
            return "Temporary Play Mode experiment finished; original scene and shared assets were not saved.";
        }

        static void AfterStop(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredEditMode) return;
            EditorApplication.playModeStateChanged -= AfterStop;
            // Unity calls OnApplicationQuit while leaving Play Mode; keep the isolated save suffix until then.
            SaveSystem.KeySuffix = oldSaveSuffix;
            EditorSettings.enterPlayModeOptionsEnabled = oldOptionsEnabled;
            EditorSettings.enterPlayModeOptions = oldOptions;
            foreach (var item in temporary) if (item != null) UnityEngine.Object.DestroyImmediate(item);
            temporary.Clear(); inkMaterial = null;
        }
    }
}
