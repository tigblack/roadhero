using UnityEngine;

namespace RoadGame
{
    /// <summary>Test utility: records the final audio mix (put it on the AudioListener's GameObject).</summary>
    public class AudioTap : MonoBehaviour
    {
        float[] buffer;
        volatile int written;
        public int channels = 2;
        public int SampleRate { get; private set; }

        public void Begin(float seconds)
        {
            SampleRate = AudioSettings.outputSampleRate;
            buffer = new float[(int)(seconds * SampleRate) * 2];
            written = 0;
        }

        void OnAudioFilterRead(float[] data, int ch)
        {
            var b = buffer;
            if (b == null) return;
            channels = ch;
            int w = written;
            int n = Mathf.Min(data.Length, b.Length - w);
            if (n <= 0) return;
            System.Array.Copy(data, 0, b, w, n);
            written = w + n;
        }

        public float[] Take()
        {
            var b = buffer;
            buffer = null;
            if (b == null) return new float[0];
            var r = new float[written];
            System.Array.Copy(b, r, written);
            return r;
        }
    }
}
