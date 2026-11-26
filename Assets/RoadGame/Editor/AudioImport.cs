using System.IO;
using UnityEditor;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>Import settings for the generated audio (Resources/Audio): Vorbis everywhere, music streamed,
    /// short effects decompressed on load (no runtime decode cost), mono where stereo adds nothing.</summary>
    public class AudioImport : AssetPostprocessor
    {
        void OnPreprocessAudio()
        {
            if (!assetPath.Replace('\\', '/').Contains("RoadGame/Resources/Audio/")) return;
            var imp = (AudioImporter)assetImporter;
            var name = Path.GetFileNameWithoutExtension(assetPath);
            var s = imp.defaultSampleSettings;
            s.compressionFormat = AudioCompressionFormat.Vorbis;
            s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate;
            if (name.StartsWith("music_"))
            {
                s.loadType = AudioClipLoadType.Streaming;
                s.quality = 0.6f;
                imp.forceToMono = false;
                imp.loadInBackground = true;
            }
            else if (name.StartsWith("loop_"))
            {
                s.loadType = AudioClipLoadType.CompressedInMemory;
                s.quality = 0.55f;
                imp.forceToMono = false; // files are already mono (forceToMono would also peak-normalize them)
            }
            else
            {
                s.loadType = AudioClipLoadType.DecompressOnLoad;
                s.quality = 0.7f;
                imp.forceToMono = false; // files are already mono (forceToMono would also peak-normalize them)
            }
            imp.defaultSampleSettings = s;
            // Browser audio is buffered; preserve the native streaming music settings.
            var web = s;
            if (web.loadType == AudioClipLoadType.Streaming) web.loadType = AudioClipLoadType.CompressedInMemory;
            imp.SetOverrideSampleSettings("WebGL", web);
        }
    }
}
