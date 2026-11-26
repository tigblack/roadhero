using UnityEditor;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Work runs are silent. The editor's master audio is muted before anything can play: when the editor loads
    /// (batch captures, previews, tests), right before Play Mode starts and again once it has started.
    /// Only the Unity Editor is affected: player builds (Android, WebGL, macOS), the game's own Sound / Music
    /// settings in the save and the computer's system volume stay untouched.
    /// Menu: RoadGame ▸ Audio ▸ Mute Work Runs (on by default). Batch mode is always muted.
    /// The browser counterpart lives in Assets/WebGLTemplates/RoadGame/index.html (?mute, automated browsers).
    /// </summary>
    [InitializeOnLoad]
    public static class WorkAudioMute
    {
        const string PrefKey = "RoadGame.WorkAudioMute";
        const string MenuPath = "RoadGame/Audio/Mute Work Runs";

        /// <summary>On unless the user switched it off in the menu; always on in batch mode (automated runs).</summary>
        public static bool Enabled
        {
            get => Application.isBatchMode || EditorPrefs.GetBool(PrefKey, true);
            set => EditorPrefs.SetBool(PrefKey, value);
        }

        static WorkAudioMute()
        {
            Apply();
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        static void OnPlayModeChanged(PlayModeStateChange state)
        {
            // ExitingEditMode runs before any scene object wakes up, so the first sound of the session is already muted;
            // EnteredPlayMode re-asserts it in case something toggled the mute during the transition.
            if (state == PlayModeStateChange.ExitingEditMode || state == PlayModeStateChange.EnteredPlayMode) Apply();
        }

        /// <summary>Mutes the editor's master audio if work-run muting is enabled. Returns the resulting mute state.</summary>
        public static bool Apply()
        {
            if (Enabled && !EditorUtility.audioMasterMute) EditorUtility.audioMasterMute = true;
            return EditorUtility.audioMasterMute;
        }

        [MenuItem(MenuPath, priority = 300)]
        static void Toggle()
        {
            bool on = !EditorPrefs.GetBool(PrefKey, true);
            Enabled = on;
            EditorUtility.audioMasterMute = on;
            Debug.Log(on
                ? "RoadGame: work runs are muted (editor master audio off on every Play Mode entry). Builds are not affected."
                : "RoadGame: work-run muting is off - Play Mode in this editor will play sound.");
        }

        [MenuItem(MenuPath, true)]
        static bool ToggleValidate()
        {
            Menu.SetChecked(MenuPath, EditorPrefs.GetBool(PrefKey, true));
            return true;
        }
    }
}
