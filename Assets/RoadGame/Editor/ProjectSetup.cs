using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Idempotent project setup: creates the Game scene (camera + light + bootstrap object), puts it first in
    /// Build Settings and switches the player to portrait. Runs automatically once after scripts compile.
    /// </summary>
    [InitializeOnLoad]
    public static class ProjectSetup
    {
        public const string ScenePath = "Assets/Scenes/Game.unity";
        const string OpenedKey = "RoadGame.OpenedGameSceneOnce";

        static ProjectSetup()
        {
            if (Application.isBatchMode) return; // batch tools call EnsureSetup explicitly
            EditorApplication.delayCall += () =>
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode) return;
                EnsureSetup();
                // open the game scene the first time so pressing Play just works
                if (!SessionState.GetBool(OpenedKey, false) && !EditorPrefs.GetBool(OpenedKey + Application.dataPath, false))
                {
                    SessionState.SetBool(OpenedKey, true);
                    EditorPrefs.SetBool(OpenedKey + Application.dataPath, true);
                    var active = SceneManager.GetActiveScene();
                    if (active.path != ScenePath && !active.isDirty)
                        EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
                }
            };
        }

        [MenuItem("RoadGame/Setup Project (scene, build settings, portrait)")]
        public static void EnsureSetup()
        {
            if (!File.Exists(ScenePath)) CreateScene();

            var scenes = EditorBuildSettings.scenes.ToList();
            if (scenes.Count == 0 || scenes[0].path != ScenePath)
            {
                scenes.RemoveAll(s => s.path == ScenePath);
                scenes.Insert(0, new EditorBuildSettingsScene(ScenePath, true));
                EditorBuildSettings.scenes = scenes.ToArray();
            }

            if (PlayerSettings.defaultInterfaceOrientation != UIOrientation.Portrait)
            {
                PlayerSettings.defaultInterfaceOrientation = UIOrientation.Portrait;
                PlayerSettings.allowedAutorotateToPortrait = true;
                PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
                PlayerSettings.allowedAutorotateToLandscapeLeft = false;
                PlayerSettings.allowedAutorotateToLandscapeRight = false;
            }
            // mobile build defaults: Android needs IL2CPP + ARM64 for modern 64-bit-only phones
            if (PlayerSettings.GetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android) != ScriptingImplementation.IL2CPP)
            {
                PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
                PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            }
            // URP settings the top-down camera needs (shadows reach the far edge of the view, crisp outlines)
            for (int q = 0; q < QualitySettings.names.Length; q++)
            {
                if (QualitySettings.GetRenderPipelineAssetAt(q) is UniversalRenderPipelineAsset urp)
                {
                    bool dirty = false;
                    if (urp.shadowDistance < 115f) { urp.shadowDistance = 115f; dirty = true; }
                    if (urp.shadowCascadeCount != 1) { urp.shadowCascadeCount = 1; dirty = true; }
                    if (urp.mainLightShadowmapResolution < 2048) { urp.mainLightShadowmapResolution = 2048; dirty = true; }
                    if (urp.msaaSampleCount < 4) { urp.msaaSampleCount = 4; dirty = true; }
                    if (urp.renderScale < 1f) { urp.renderScale = 1f; dirty = true; }
                    // soft (filtered) shadow edges for the more realistic cel look (setter is internal -> serialized field)
                    var so = new SerializedObject(urp);
                    var soft = so.FindProperty("m_SoftShadowsSupported");
                    if (soft != null && !soft.boolValue) { soft.boolValue = true; so.ApplyModifiedPropertiesWithoutUndo(); dirty = true; }
                    if (dirty) { EditorUtility.SetDirty(urp); AssetDatabase.SaveAssetIfDirty(urp); }
                }
            }
            // app icon (rendered from the game's own car model by the capture tool)
            const string iconPath = "Assets/RoadGame/Art/AppIcon.png";
            var icons = PlayerSettings.GetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, IconKind.Any);
            if ((icons == null || icons.Length == 0 || icons[0] == null) && File.Exists(iconPath))
            {
                var icon = AssetDatabase.LoadAssetAtPath<Texture2D>(iconPath);
                if (icon != null) PlayerSettings.SetIcons(UnityEditor.Build.NamedBuildTarget.Unknown, new[] { icon }, IconKind.Any);
            }
            // standalone preview window in phone proportions
            if (PlayerSettings.defaultScreenWidth != 540 || PlayerSettings.defaultScreenHeight != 1170)
            {
                PlayerSettings.defaultScreenWidth = 540;
                PlayerSettings.defaultScreenHeight = 1170;
                PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
                PlayerSettings.resizableWindow = true;
            }
        }

        static void CreateScene()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.95f, 0.82f, 0.62f);
            cam.fieldOfView = 46f;
            camGo.AddComponent<AudioListener>();
            camGo.AddComponent<UniversalAdditionalCameraData>();
            camGo.transform.SetPositionAndRotation(new Vector3(0, 50, -110), Quaternion.Euler(54, 0, 0));

            var lightGo = new GameObject("Sun");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.shadows = LightShadows.Hard;
            lightGo.transform.rotation = Quaternion.Euler(52f, 142f, 0f);

            var game = new GameObject("Game");
            game.AddComponent<RoadGame.Game>();

            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.Refresh();
        }

        [MenuItem("RoadGame/Open Game Scene")]
        static void OpenGameScene()
        {
            EnsureSetup();
            if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        }

        [MenuItem("RoadGame/Delete Save (PlayerPrefs)")]
        static void DeleteSave()
        {
            SaveSystem.Wipe();
            Debug.Log("RoadGame: save deleted.");
        }
    }
}
