using UnityEditor;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>Loading illustrations are screen UI: no mipmaps, alpha, or CPU-readable copy.</summary>
    public class LoadingArtImport : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            if (!assetPath.Replace('\\', '/').Contains("RoadGame/Resources/Loading/")) return;
            var texture = (TextureImporter)assetImporter;
            texture.textureType = TextureImporterType.Default;
            texture.npotScale = TextureImporterNPOTScale.None;
            texture.mipmapEnabled = false;
            texture.isReadable = false;
            texture.alphaSource = TextureImporterAlphaSource.None;
            texture.wrapMode = TextureWrapMode.Clamp;
            texture.filterMode = FilterMode.Bilinear;
            texture.maxTextureSize = 2048;
            texture.textureCompression = TextureImporterCompression.Compressed;
            texture.compressionQuality = 70;
        }
    }
}
