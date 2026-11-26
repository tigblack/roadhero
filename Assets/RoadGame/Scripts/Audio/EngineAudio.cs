using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Plays the V8 synth using the audio thread on native platforms. Web uses buffered clips baked from
    /// the same synth, with RPM pitch and load crossfades, because Web Audio has no DSP callbacks.
    /// </summary>
    [RequireComponent(typeof(AudioSource))]
    public class EngineAudio : MonoBehaviour
    {
        Player player;
        EngineSynth synth;
        AudioSource src;
        int popsSeen;
        float lastFlame;
        float vol;
        public float masterVolume = 0.2f;   // background layer: the engine should colour the mix, not lead it
#if UNITY_WEBGL && !UNITY_EDITOR
        static readonly float[] WebRpm = { CarTuning.IdleRpm, 2400f, 4800f };
        readonly AudioSource[] webSources = new AudioSource[6];
        readonly AudioClip[] webClips = new AudioClip[7];
        AudioSource webPop;
        float webLoad, webRpm = CarTuning.IdleRpm;
#endif

        public static EngineAudio Create(Player p)
        {
            var go = new GameObject("EngineAudio");
            go.transform.SetParent(p.transform, false);
            var src = go.AddComponent<AudioSource>();
            var e = go.AddComponent<EngineAudio>();
            e.player = p;
            e.src = src;
            int sr = AudioSettings.outputSampleRate > 0 ? AudioSettings.outputSampleRate : 48000;
            e.synth = new EngineSynth(sr);
#if UNITY_WEBGL && !UNITY_EDITOR
            e.CreateWebAudio();
#else
            // silent looping carrier clip: OnAudioFilterRead overwrites its samples with the synthesized engine
            var clip = AudioClip.Create("EngineCarrier", sr, 1, sr, false);
            clip.SetData(new float[sr], 0);
            src.clip = clip;
            src.loop = true;
            src.playOnAwake = false;
            src.spatialBlend = 0f;
            src.volume = 1f;
            src.priority = 10;
            src.Play();
#endif
            return e;
        }

        void Update()
        {
            if (synth == null || player == null) return;
            var g = Game.I;
            bool on = g != null && g.sfx != null && g.sfx.on;
            bool paused = g != null && g.paused;
            float target = on && player.Alive ? masterVolume * (paused ? 0.35f : 1f) : 0f;
            vol = Mathf.MoveTowards(vol, target, Time.unscaledDeltaTime * (target > vol ? 0.8f : 2.5f));
            synth.targetVolume = vol;
            synth.targetRpm = paused ? CarTuning.IdleRpm : player.Rpm;
            synth.targetLoad = paused ? 0f : Mathf.Clamp01(player.Load);
            synth.limiter = player.Rpm > CarTuning.RedlineRpm - 40f && player.Load > 0.5f;
#if UNITY_WEBGL && !UNITY_EDITOR
            UpdateWebAudio(paused);
#else
            if (!src.isPlaying && vol > 0.001f) src.Play();

            int pops = synth.popCount;
            if (pops != popsSeen)
            {
                popsSeen = pops;
                if (Time.time - lastFlame > 0.09f && player.Alive) { lastFlame = Time.time; player.Backfire(); }
            }
#endif
        }

#if UNITY_WEBGL && !UNITY_EDITOR
        // Unity Web supports non-streaming AudioClip.Create, whole-clip SetData, pitch and volume.
        // Bake once at startup, leaving playback and mixing to the browser without continuous PCM work.
        void CreateWebAudio()
        {
            for (int band = 0; band < WebRpm.Length; band++)
            {
                for (int load = 0; load < 2; load++)
                {
                    int i = band * 2 + load;
                    var a = i == 0 ? src : gameObject.AddComponent<AudioSource>();
                    webSources[i] = a;
                    webClips[i] = BakeWebClip("EngineWeb" + i, WebRpm[band], load == 0 ? 0.14f : 0.85f, true);
                    a.clip = webClips[i];
                    a.loop = true;
                    a.playOnAwake = false;
                    a.spatialBlend = 0f;
                    a.dopplerLevel = 0f;
                    a.volume = 0f;
                    a.priority = 10;
                }
            }
            webPop = gameObject.AddComponent<AudioSource>();
            webClips[6] = BakeWebClip("EngineWebOverrun", 4200f, 0f, false);
            webPop.clip = webClips[6];
            webPop.playOnAwake = false;
            webPop.spatialBlend = 0f;
            webPop.priority = 10;
        }

        static AudioClip BakeWebClip(string name, float rpm, float load, bool loop)
        {
            const int sampleRate = 22050;
            const int overlap = 2205;
            int frames = loop ? sampleRate : sampleRate / 4;
            var generator = new EngineSynth(sampleRate)
            {
                targetRpm = rpm,
                targetLoad = load,
                targetVolume = 1f
            };
            generator.Render(new float[sampleRate / 3 * 2], 2);
            var raw = new float[(frames + (loop ? overlap : 0)) * 2];
            if (loop) generator.Render(raw, 2);
            else
            {
                // The current synth has rare, soft crackles. Select a short recording with a real pop
                // instead of assuming one occurs within the first quarter-second of overrun.
                var probe = new float[882]; // 20 ms, stereo
                bool foundPop = false;
                for (int attempt = 0; attempt < 200; attempt++)
                {
                    int before = generator.popCount;
                    generator.Render(probe, 2);
                    if (generator.popCount == before) continue;
                    System.Array.Copy(probe, raw, probe.Length);
                    var tail = new float[raw.Length - probe.Length];
                    generator.Render(tail, 2);
                    System.Array.Copy(tail, 0, raw, probe.Length, tail.Length);
                    foundPop = true;
                    break;
                }
                if (!foundPop) generator.Render(raw, 2);
            }
            var data = new float[frames * 2];
            if (loop)
            {
                System.Array.Copy(raw, overlap * 2, data, 0, data.Length);
                // Crossfade the tail into the omitted lead-in for a continuous loop boundary.
                for (int i = 0; i < overlap; i++)
                {
                    float blend = (float)i / (overlap - 1);
                    for (int ch = 0; ch < 2; ch++)
                        data[(frames - overlap + i) * 2 + ch] = Mathf.Lerp(raw[(frames + i) * 2 + ch], raw[i * 2 + ch], blend);
                }
            }
            else
            {
                System.Array.Copy(raw, data, data.Length);
                for (int i = 0; i < frames; i++)
                {
                    float envelope = Mathf.Min(1f, i / 110f) * Mathf.Clamp01((frames - 1 - i) / 1100f);
                    data[i * 2] *= envelope;
                    data[i * 2 + 1] *= envelope;
                }
            }
            var clip = AudioClip.Create(name, frames, 2, sampleRate, false);
            clip.SetData(data, 0);
            return clip;
        }

        void UpdateWebAudio(bool paused)
        {
            float dt = Time.unscaledDeltaTime;
            webRpm = Mathf.Lerp(webRpm, synth.targetRpm, 1f - Mathf.Exp(-dt * 18f));
            webLoad = Mathf.MoveTowards(webLoad, synth.targetLoad, dt * 6f);
            int lower = webRpm < WebRpm[1] ? 0 : 1;
            float bandBlend = Mathf.InverseLerp(WebRpm[lower], WebRpm[lower + 1], webRpm);
            float loadBlend = Mathf.Clamp01((webLoad - 0.05f) / 0.8f);
            float limiterGain = synth.limiter ? 0.68f + 0.32f * Mathf.PingPong(Time.unscaledTime * 32f, 1f) : 1f;
            for (int band = 0; band < WebRpm.Length; band++)
            {
                float weight = band == lower ? 1f - bandBlend : band == lower + 1 ? bandBlend : 0f;
                for (int load = 0; load < 2; load++)
                {
                    var a = webSources[band * 2 + load];
                    a.pitch = Mathf.Clamp(webRpm / WebRpm[band], 0.25f, 3f);
                    a.volume = vol * limiterGain * Mathf.Sqrt(weight * (load == 0 ? 1f - loadBlend : loadBlend));
                    if (!a.isPlaying && a.volume > 0.001f && a.clip.loadState == AudioDataLoadState.Loaded) a.Play();
                }
            }

            // Match the native synth's current, deliberately sparse soft-crackle probability per firing.
            if (!paused && player.Alive && synth.targetLoad < 0.12f && webRpm > 2300f)
            {
                float rpmN = Mathf.Clamp01((webRpm - 700f) / 6000f);
                float popsPerSecond = webRpm / 60f * 4f * (0.006f + 0.008f * rpmN);
                if (Time.time - lastFlame > 0.09f && Random.value < 1f - Mathf.Exp(-popsPerSecond * dt))
                {
                    lastFlame = Time.time;
                    webPop.volume = vol * 0.9f;
                    webPop.pitch = Random.Range(0.88f, 1.12f);
                    if (webPop.clip.loadState == AudioDataLoadState.Loaded && vol > 0.001f) webPop.Play();
                    player.Backfire();
                }
            }
        }

        void OnDestroy()
        {
            foreach (var clip in webClips) if (clip != null) Destroy(clip);
        }
#else
        void OnAudioFilterRead(float[] data, int channels)
        {
            var s = synth;
            if (s == null) { System.Array.Clear(data, 0, data.Length); return; }
            s.Render(data, channels);
        }
#endif
    }
}
