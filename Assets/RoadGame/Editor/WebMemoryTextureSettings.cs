using System;
using UnityEditor;

namespace RoadGame.EditorTools
{
    /// <summary>Web-only GPU compression and useful car resolution; source/native textures stay unchanged.</summary>
    public sealed class WebMemoryTextureSettings : AssetPostprocessor
    {
        public override int GetPostprocessOrder() => 500;

        static bool IsTarget(string path) => path.StartsWith("Assets/RoadGame/Art/Cars/ScarboundDetailed/Textures/", StringComparison.Ordinal)
            || path.StartsWith("Assets/RoadGame/Resources/Levels/", StringComparison.Ordinal)
            || path.StartsWith("Assets/RoadGame/Resources/Creatures/", StringComparison.Ordinal);

        void OnPreprocessTexture()
        {
            if (IsTarget(assetPath)) Configure((TextureImporter)assetImporter);
        }

        static bool Configure(TextureImporter importer)
        {
            var settings = importer.GetPlatformTextureSettings("WebGL");
            int maxSize = importer.assetPath.StartsWith("Assets/RoadGame/Art/Cars/", StringComparison.Ordinal) ? 1024 : Math.Min(2048, importer.maxTextureSize);
            bool changed = !settings.overridden || settings.maxTextureSize != maxSize
                || settings.format != TextureImporterFormat.ASTC_6x6 || settings.crunchedCompression;
            settings.name = "WebGL";
            settings.overridden = true;
            settings.maxTextureSize = maxSize;
            settings.format = TextureImporterFormat.ASTC_6x6;
            settings.crunchedCompression = false;
            importer.SetPlatformTextureSettings(settings);
            return changed;
        }

        public static void ApplyExisting()
        {
            foreach (string guid in AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets/RoadGame" }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (!IsTarget(path)) continue;
                var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                if (importer != null && Configure(importer)) importer.SaveAndReimport();
            }
        }
    }
}
