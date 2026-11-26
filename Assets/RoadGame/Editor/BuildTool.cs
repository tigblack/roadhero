using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>One-click builds (menu) and batch builds:
    /// Unity -batchmode -quit -projectPath P -buildTarget Android -executeMethod RoadGame.EditorTools.BuildTool.BuildAndroid -buildOut /abs/RoadGame.apk</summary>
    public static class BuildTool
    {
        static string Arg(string name, string def)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == name) return args[i + 1];
            return def;
        }

        [MenuItem("RoadGame/Build/Android APK (ARM64)")]
        public static void BuildAndroid()
        {
            ProjectSetup.EnsureSetup();
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            EditorUserBuildSettings.buildAppBundle = false;
            var outPath = Arg("-buildOut", Path.GetFullPath("Builds/Android/RoadGame.apk"));
            Build(BuildTarget.Android, outPath);
        }

        [MenuItem("RoadGame/Build/macOS App")]
        public static void BuildMac()
        {
            ProjectSetup.EnsureSetup();
            var outPath = Arg("-buildOut", Path.GetFullPath("Builds/macOS/RoadGame.app"));
            Build(BuildTarget.StandaloneOSX, outPath);
        }

        [MenuItem("RoadGame/Build/WebGL (Sites)")]
        public static void BuildWebGL()
        {
            ProjectSetup.EnsureSetup();
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.WebGL, ScriptingImplementation.IL2CPP);
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = true;
            PlayerSettings.WebGL.dataCaching = true;
            PlayerSettings.WebGL.nameFilesAsHashes = true;
            PlayerSettings.WebGL.threadsSupport = false;
            // Keep growth bounded on mobile rather than reserving geometric overshoot during mesh import.
            PlayerSettings.WebGL.initialMemorySize = 256;
            PlayerSettings.WebGL.maximumMemorySize = 512;
            PlayerSettings.WebGL.memoryGrowthMode = WebGLMemoryGrowthMode.Linear;
            PlayerSettings.WebGL.linearMemoryGrowthStep = 16;
            EditorUserBuildSettings.webGLBuildSubtarget = WebGLTextureSubtarget.ASTC;
            WebMemoryTextureSettings.ApplyExisting();
            PlayerSettings.WebGL.template = "PROJECT:RoadGame";
            PlayerSettings.defaultWebScreenWidth = 540;
            PlayerSettings.defaultWebScreenHeight = 1170;
            foreach (var path in Directory.GetFiles("Assets/RoadGame/Resources/Audio", "music_*.wav"))
                AssetDatabase.ImportAsset(path.Replace('\\', '/'), ImportAssetOptions.ForceUpdate);
            var outPath = Arg("-buildOut", Path.GetFullPath("Sites/roadgame-webgl/dist"));
            Build(BuildTarget.WebGL, outPath);
        }

        static void Build(BuildTarget target, string outPath)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(outPath));
            var opts = new BuildPlayerOptions
            {
                scenes = new[] { ProjectSetup.ScenePath },
                locationPathName = outPath,
                target = target,
                targetGroup = BuildPipeline.GetBuildTargetGroup(target),
                options = BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(opts);
            var s = report.summary;
            Debug.Log($"RoadGame BuildTool: {s.result} {target} -> {outPath} size={s.totalSize / (1024f * 1024f):0.0}MB time={s.totalTime} errors={s.totalErrors} warnings={s.totalWarnings}");
            if (Application.isBatchMode) EditorApplication.Exit(s.result == BuildResult.Succeeded ? 0 : 1);
        }
    }
}
