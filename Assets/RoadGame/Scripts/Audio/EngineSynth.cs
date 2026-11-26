using System;

namespace RoadGame
{
    /// <summary>
    /// Real-time supercharged V8 engine synthesizer (no samples). Pure C#, allocation-free in Render(), safe to run
    /// on the audio thread.
    ///  - Crossplane V8 firing order (1-8-4-3-6-5-7-2) split into two banks feeding separate side pipes: the uneven
    ///    per-bank pulse spacing gives the classic V8 burble.
    ///  - Each firing = exhaust blowdown pulse whose width is fixed in crank degrees (gets shorter / brighter with rpm)
    ///    plus a turbulent noise burst; amplitude follows load with cycle-to-cycle variation (lumpy cammed idle).
    ///  - Exhaust: waveguide pipe per bank (delay line with lossy inverted reflection) -> pipe resonances, then a
    ///    muffler low-pass that opens with load and a low "body" resonance.
    ///  - Supercharger whine (rotor lobe frequency), intake roar, valvetrain ticks.
    ///  - Overrun crackle: on throttle lift at high rpm some firings become loud pops (counted for visual flames).
    ///  - Rev limiter cuts ignition in bursts.
    /// </summary>
    public sealed class EngineSynth
    {
        // ---- parameters (written by the main thread, read per block)
        public volatile float targetRpm = 850f;
        public volatile float targetLoad;
        public volatile float targetVolume;
        public volatile bool limiter;
        /// <summary>Incremented on every overrun pop (main thread spawns backfire flames).</summary>
        public volatile int popCount;

        readonly float fs;
        // cylinder firing slots -> bank (0 = right, 1 = left) for firing order 1-8-4-3-6-5-7-2 (Ford: 1-4 right, 5-8 left)
        static readonly int[] SlotBank = { 0, 1, 0, 0, 1, 1, 1, 0 };

        double crank;            // total crank revolutions (monotonic)
        double nextFireAt = 0.25;
        int nextSlot;
        float rpm = 850f, load, vol, rpmSm = 850f;
        float prevLoad;
        uint rng = 0x9E3779B9u;

        // active exhaust pulses per bank
        const int MaxPulses = 4;
        readonly float[,] pulseEnvD = new float[2, MaxPulses];   // decay envelope (1 -> 0)
        readonly float[,] pulseEnvR = new float[2, MaxPulses];   // attack envelope (shape = (1 - envR) * envD)
        readonly float[,] pulseEnvN = new float[2, MaxPulses];   // blowdown noise envelope
        readonly float[,] pulseAmp = new float[2, MaxPulses];
        readonly float[,] pulseNoise = new float[2, MaxPulses];
        readonly int[] pulseNext = new int[2];

        // waveguides
        readonly float[][] wg = { new float[4096], new float[4096] };
        readonly int[] wgLen = new int[2];
        int wgPos;
        readonly float[] wgLp = new float[2];

        // filters (per bank muffler + body resonance), intake band-pass, DC blockers
        readonly Biquad[] muffler = { new Biquad(), new Biquad() };
        readonly Biquad[] body = { new Biquad(), new Biquad() };
        readonly Biquad[] presence = { new Biquad(), new Biquad() };
        readonly Biquad intakeBp = new Biquad();
        readonly Biquad popBp = new Biquad();
        float dcX0, dcY0, dcX1, dcY1;
        double whinePhase;
        float tickEnv;
        float popEnv; int popBank;
        float limiterCut;
        int limiterCounter;
        float shimmer;

        public EngineSynth(int sampleRate)
        {
            fs = sampleRate;
            // pipe lengths (round trip): right / left banks slightly different for a richer sound
            wgLen[0] = Math.Min(4000, (int)(2.0 * 1.85 / 343.0 * fs));
            wgLen[1] = Math.Min(4000, (int)(2.0 * 2.05 / 343.0 * fs));
            intakeBp.BandPass(fs, 650f, 0.9f);
            popBp.BandPass(fs, 1400f, 0.8f);
        }

        float Rand() // -1..1
        {
            rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
            return (rng & 0xFFFFFF) / (float)0x800000 - 1f;
        }

        float Rand01() => Rand() * 0.5f + 0.5f;

        /// <summary>Fills an interleaved buffer (overwrites).</summary>
        public void Render(float[] data, int channels)
        {
            int frames = data.Length / channels;
            float tRpm = targetRpm, tLoad = targetLoad, tVol = targetVolume;
            // per-block filter updates
            float rpmN = Clamp01((rpmSm - 700f) / 6000f);
            float open = Clamp01(load * 0.8f + rpmN * 0.4f);
            for (int b = 0; b < 2; b++)
            {
                muffler[b].LowPass(fs, 1000f + 1500f * open, 0.75f);
                body[b].Peak(fs, 95f + 25f * rpmN, 0.8f, 3f);
                presence[b].Peak(fs, 720f, 0.7f, 2.5f);   // keeps the engine audible on phone speakers
            }
            float kSm = 1f - (float)Math.Exp(-1.0 / (0.025 * fs));   // 25 ms parameter smoothing
            float kRpm = 1f - (float)Math.Exp(-1.0 / (0.012 * fs));
            float lpA = 1f - (float)Math.Exp(-2.0 * Math.PI * 3200.0 / fs);
            const float Refl = -0.5f;
            // blowdown pulse: sharp onset, decay partly fixed in time (gas dynamics), shorter at high rpm
            double tauD = 0.0034 - 0.0021 * rpmN;
            float kD = (float)Math.Exp(-1.0 / (tauD * fs));
            float kR = (float)Math.Exp(-1.0 / (0.00018 * fs));
            float kN = (float)Math.Exp(-1.0 / (0.0022 * fs));
            float whineAmpBlock = 0.035f * (float)Math.Pow(rpmN, 1.4);

            for (int i = 0; i < frames; i++)
            {
                rpm += (tRpm - rpm) * kRpm;
                rpmSm += (tRpm - rpmSm) * kSm * 0.2f;
                load += (tLoad - load) * kSm;
                vol += (tVol - vol) * kSm;
                float rpmClamped = rpm < 300f ? 300f : rpm;

                // ---- crank / firing: one cylinder every 90 degrees of crank rotation
                double dRev = rpmClamped / 60.0 / fs;
                crank += dRev;
                if (crank >= nextFireAt)
                {
                    Fire(SlotBank[nextSlot], rpmClamped);
                    nextSlot = (nextSlot + 1) & 7;
                    float idle = Clamp01(1.3f - rpmClamped / 1400f);
                    nextFireAt += 0.25 * (1.0 + Rand() * (0.012 + 0.03 * idle));
                    if (nextFireAt < crank) nextFireAt = crank + 0.25;
                }

                // ---- exhaust excitation per bank
                float outL = 0f, outR = 0f;
                for (int b = 0; b < 2; b++)
                {
                    float e = 0f;
                    for (int p = 0; p < MaxPulses; p++)
                    {
                        float envD = pulseEnvD[b, p];
                        if (envD < 0.0005f) continue;
                        float envR = pulseEnvR[b, p];
                        float envN = pulseEnvN[b, p];
                        e += pulseAmp[b, p] * ((1f - envR) * envD + envN * pulseNoise[b, p] * Rand());
                        pulseEnvD[b, p] = envD * kD;
                        pulseEnvR[b, p] = envR * kR;
                        pulseEnvN[b, p] = envN * kN;
                    }
                    if (popEnv > 0f && popBank == b) e += popBp.Process(Rand()) * popEnv * 6f;
                    // waveguide: y = e + R * lowpass(y[n - D])
                    var buf = wg[b];
                    int len = wgLen[b];
                    int readIdx = (wgPos - len) & 4095;
                    wgLp[b] += (buf[readIdx] - wgLp[b]) * lpA;
                    float y = e + Refl * wgLp[b];
                    buf[wgPos & 4095] = y;
                    // muffler + body
                    float s = muffler[b].Process(y);
                    s = body[b].Process(s);
                    s = presence[b].Process(s);
                    if (b == 0) { outR += s * 0.62f; outL += s * 0.38f; }
                    else { outL += s * 0.62f; outR += s * 0.38f; }
                }
                wgPos = (wgPos + 1) & 4095;
                if (popEnv > 0f) popEnv -= 1f / (0.012f * fs);

                // ---- supercharger whine (rotor lobes) + intake roar + valvetrain ticks
                double whineHz = rpmClamped * 0.142;
                whinePhase += whineHz / fs;
                if (whinePhase > 1.0) whinePhase -= 1.0;
                float wph = (float)(whinePhase * Math.PI * 2.0);
                shimmer += (Rand() - shimmer) * 0.002f;
                float whine = ((float)Math.Sin(wph) + 0.35f * (float)Math.Sin(2f * wph + 0.7f)) * (1f + shimmer * 2f);
                float whineAmp = whineAmpBlock * (0.35f + 0.65f * load);
                float intake = intakeBp.Process(Rand()) * (0.03f + 0.1f * load) * (0.3f + 0.7f * rpmN);
                tickEnv *= 0.985f;
                float tick = Rand() * tickEnv * 0.02f;
                float common = whine * whineAmp + intake + tick;
                outL += common; outR += common;

                // ---- master: soft saturation, DC block, volume
                float drive = 1.6f + load * 1.2f;
                outL = (float)Math.Tanh(outL * drive) * 0.75f;
                outR = (float)Math.Tanh(outR * drive) * 0.75f;
                float yl = outL - dcX0 + 0.995f * dcY0; dcX0 = outL; dcY0 = yl;
                float yr = outR - dcX1 + 0.995f * dcY1; dcX1 = outR; dcY1 = yr;
                float g = vol * (0.88f + 0.12f * load) * (0.9f + 0.1f * rpmN);   // narrow range: steady background bed
                if (channels == 1) data[i] = (yl + yr) * 0.5f * g;
                else
                {
                    data[i * channels] = yl * g;
                    data[i * channels + 1] = yr * g;
                    for (int c = 2; c < channels; c++) data[i * channels + c] = 0f;
                }
            }
            prevLoad = load;
        }

        void Fire(int bank, float rpmNow)
        {
            float rpmN = Clamp01((rpmNow - 700f) / 6000f);
            // rev limiter: cut ignition in bursts
            if (limiter)
            {
                limiterCounter++;
                if ((limiterCounter & 7) < 4) return;
            }
            float idleness = Clamp01(1.3f - rpmNow / 1400f);
            float jitter = 0.08f + 0.3f * idleness;
            float amp = (0.6f + 0.4f * load) * (0.8f + 0.2f * rpmN);
            amp *= 1f + Rand() * jitter;
            // lumpy cam: occasional lazy cycle at idle
            if (idleness > 0.3f && Rand01() < 0.05f) amp *= 0.35f;
            // overrun: lifted throttle at speed -> pops and crackles
            bool overrun = load < 0.12f && rpmNow > 2300f;
            if (overrun && Rand01() < 0.006f + 0.008f * rpmN)
            {
                float r = Rand01();
                popEnv = 0.2f + r * r * 0.5f;       // soft crackles only
                popBank = bank;
                popCount++;
            }
            int slot = pulseNext[bank];
            pulseNext[bank] = (slot + 1) % MaxPulses;
            pulseEnvD[bank, slot] = 1f;
            pulseEnvR[bank, slot] = 1f;
            pulseEnvN[bank, slot] = 1f;
            pulseAmp[bank, slot] = amp;
            pulseNoise[bank, slot] = 0.45f + 0.3f * load;
            tickEnv = Math.Max(tickEnv, 0.3f + 0.7f * idleness);
        }

        static float Clamp01(float x) => x < 0f ? 0f : (x > 1f ? 1f : x);

        /// <summary>RBJ biquad (direct form I).</summary>
        sealed class Biquad
        {
            float b0 = 1, b1, b2, a1, a2, x1, x2, y1, y2;

            public float Process(float x)
            {
                float y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
                x2 = x1; x1 = x; y2 = y1; y1 = y;
                if (y > 1e6f || y < -1e6f || float.IsNaN(y)) { x1 = x2 = y1 = y2 = 0f; return 0f; }
                return y;
            }

            void Set(double nb0, double nb1, double nb2, double na0, double na1, double na2)
            {
                b0 = (float)(nb0 / na0); b1 = (float)(nb1 / na0); b2 = (float)(nb2 / na0);
                a1 = (float)(na1 / na0); a2 = (float)(na2 / na0);
            }

            public void LowPass(float fs, float f, float q)
            {
                double w = 2 * Math.PI * Math.Min(f, fs * 0.45) / fs, c = Math.Cos(w), al = Math.Sin(w) / (2 * q);
                Set((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + al, -2 * c, 1 - al);
            }

            public void BandPass(float fs, float f, float q)
            {
                double w = 2 * Math.PI * f / fs, c = Math.Cos(w), al = Math.Sin(w) / (2 * q);
                Set(al, 0, -al, 1 + al, -2 * c, 1 - al);
            }

            public void Peak(float fs, float f, float q, float gainDb)
            {
                double A = Math.Pow(10, gainDb / 40), w = 2 * Math.PI * f / fs, c = Math.Cos(w), al = Math.Sin(w) / (2 * q);
                Set(1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A);
            }
        }
    }
}
