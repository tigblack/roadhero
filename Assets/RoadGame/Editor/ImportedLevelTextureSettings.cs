using System;
using UnityEditor;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>The Blender bundles (Dust Flats v13, Toxic Wetlands, Ashen Winter, the creatures of both zones) contain only colour maps; keep their artwork and useful mip levels.</summary>
    public sealed class ImportedLevelTextureSettings : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith("Assets/RoadGame/Resources/Levels/DustFlatsV13/Textures/", StringComparison.Ordinal)
                && !assetPath.StartsWith("Assets/RoadGame/Resources/Levels/ToxicWetlandsZ1/Textures/", StringComparison.Ordinal)
                && !assetPath.StartsWith("Assets/RoadGame/Resources/Levels/AshenWinterZ2/Textures/", StringComparison.Ordinal)
                && !assetPath.StartsWith("Assets/RoadGame/Resources/Creatures/", StringComparison.Ordinal)) return;
            var importer = (TextureImporter)assetImporter;
            importer.textureType = TextureImporterType.Default;
            importer.sRGBTexture = true;
            importer.mipmapEnabled = true;
            importer.filterMode = FilterMode.Trilinear;
            importer.wrapMode = assetPath.Contains("material_") ? TextureWrapMode.Clamp : TextureWrapMode.Repeat;
            importer.maxTextureSize = 2048;
            importer.isReadable = false;
            importer.textureCompression = TextureImporterCompression.Compressed;
            importer.alphaIsTransparency = assetPath.Contains("material_");
            if (assetPath.StartsWith("Assets/RoadGame/Resources/Creatures/", StringComparison.Ordinal))
            {
                // creature strip atlas: strips tile along u only
                importer.wrapModeU = TextureWrapMode.Repeat;
                importer.wrapModeV = TextureWrapMode.Clamp;
                importer.maxTextureSize = 1024;
            }
        }
    }
}
