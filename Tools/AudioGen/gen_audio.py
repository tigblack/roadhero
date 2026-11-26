#!/usr/bin/env python3
"""
ROAD GAME - procedural sound design + music generator.

Renders every sound effect (several variations each) and the ambience / tire loops into
Assets/RoadGame/Resources/Audio as 16-bit WAV files.

The game's music (music_theme.wav) is NOT made here any more: since 2026-11-19 it is the Scarbound loop from
Tools/MusicGen (see its README). This script writes its old calm G-major theme only when asked with --legacy-theme
(it would replace the current music_theme.wav). Everything is synthesized from
scratch (modal synthesis for metal/wood/rock, filtered noise for blasts, Karplus-Strong strings,
FM bells, drum synthesis, additive band-limited saws), so there are no third-party samples or licenses.

Usage:  python3 gen_audio.py [out_dir] [--legacy-theme]          (needs numpy + scipy)
The engine sound is NOT here: it is synthesized in real time in the game (EngineSynth.cs).
"""
import os
import sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LEGACY_THEME = "--legacy-theme" in sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.normpath(os.path.join(HERE, "..", "..", "Assets", "RoadGame", "Resources", "Audio"))
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(1234)


# ---------------------------------------------------------------------------------------------- helpers
def secs(n):
    return np.arange(int(n * SR)) / SR


def zeros(sec):
    return np.zeros(int(sec * SR))


def noise(n, rng=None):
    rng = rng or RNG
    return rng.standard_normal(n)


def sos(kind, f, order=2):
    nyq = SR * 0.5
    if isinstance(f, (list, tuple)):
        w = [min(max(x / nyq, 1e-4), 0.999) for x in f]
    else:
        w = min(max(f / nyq, 1e-4), 0.999)
    return signal.butter(order, w, btype=kind, output="sos")


def lp(x, f, order=2):
    return signal.sosfilt(sos("lowpass", f, order), x)


def hp(x, f, order=2):
    return signal.sosfilt(sos("highpass", f, order), x)


def bp(x, f1, f2, order=2):
    return signal.sosfilt(sos("bandpass", [f1, f2], order), x)


def peak_eq(x, f0, gain_db, q=1.0):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a]
    aa = [1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a]
    return signal.lfilter(np.array(b) / aa[0], np.array(aa) / aa[0], x)


def svf_sweep(x, fc, q=0.7, mode="lp"):
    """Time-varying state-variable filter (TPT). fc = array of cutoffs (Hz) per sample."""
    y = np.zeros_like(x)
    ic1 = ic2 = 0.0
    k = 1.0 / q
    fc = np.clip(fc, 20, SR * 0.45)
    gs = np.tan(np.pi * fc / SR)
    for i in range(len(x)):
        g = gs[i]
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        if mode == "lp":
            y[i] = v2
        elif mode == "bp":
            y[i] = v1
        else:
            y[i] = x[i] - k * v1 - v2
    return y


def env_exp(n, tau, attack=0.001):
    t = np.arange(n) / SR
    e = np.exp(-t / max(tau, 1e-5))
    if attack > 0:
        e *= np.clip(t / attack, 0, 1)
    return e


def sine_sweep(n, f0, f1, tau):
    """Exponential pitch glide from f0 to f1 with time constant tau."""
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph)


def modal(n, freqs, decays, amps, rng=None, jitter=0.0):
    rng = rng or RNG
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f, d, a in zip(freqs, decays, amps):
        f = f * (1 + jitter * rng.uniform(-1, 1))
        if f >= SR * 0.45:
            continue
        y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    return y


def end_fade(sig, sec=0.008):
    """Short fade at the end of a rendered component so truncated decays never click."""
    k = min(len(sig), int(sec * SR))
    if k > 1 and abs(sig[-1]) > 1e-4:
        sig = sig.copy()
        sig[-k:] *= np.linspace(1, 0, k)
    return sig


def place(buf, sig, t0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= len(buf):
        return
    m = min(len(sig), len(buf) - i0)
    seg = end_fade(sig[:m])
    buf[i0:i0 + m] += seg * gain


def reverb_ir(rt60, sec=None, lp_hz=5000, seed=0, stereo=False, predelay=0.0):
    sec = sec or rt60 * 1.1
    n = int(sec * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    decay = np.exp(-6.9 * t / rt60)
    chans = []
    for c in range(2 if stereo else 1):
        ir = rng.standard_normal(n) * decay
        ir = lp(ir, lp_hz)
        ir[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
        if predelay > 0:
            ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        chans.append(ir)
    return chans if stereo else chans[0]


def reverb(x, rt60=0.8, mix=0.2, lp_hz=4000, seed=0, predelay=0.012):
    ir = reverb_ir(rt60, lp_hz=lp_hz, seed=seed, predelay=predelay)
    wet = signal.fftconvolve(x, ir)[: len(x)]
    return x * (1 - mix * 0.5) + wet * mix


def saturate(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def fade_out(x, sec=0.02):
    n = min(len(x), int(sec * SR))
    if n > 0:
        x[-n:] *= np.linspace(1, 0, n) ** 2
    return x


def norm(x, peak_db=-1.0):
    p = np.max(np.abs(x)) + 1e-9
    return x * (10 ** (peak_db / 20) / p)


def trim_tail(x, thresh_db=-62):
    a = np.abs(x)
    th = np.max(a) * 10 ** (thresh_db / 20)
    idx = np.where(a > th)[0]
    if len(idx) == 0:
        return x
    end = min(len(x), idx[-1] + int(0.02 * SR))
    return fade_out(x[:end].copy(), 0.015)


def loudest_window_db(x, win=0.1):
    w = int(win * SR)
    if len(x) <= w:
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    c = np.convolve(x ** 2, np.ones(w) / w, mode="valid")
    return 10 * np.log10(c.max() + 1e-12)


def soft_limit(x, knee=0.7):
    a = np.abs(x)
    over = a > knee
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (1 - knee) * np.tanh((a[over] - knee) / (1 - knee)))
    return y


def write(name, x, peak_db=-1.0, stereo=None, trim=True, loud_db=None):
    """loud_db: normalize the loudest 100 ms window to this level (soft-limiting peaks) instead of peak normalizing."""
    if stereo is not None:
        l, r = stereo
        m = max(np.max(np.abs(l)), np.max(np.abs(r))) + 1e-9
        g = 10 ** (peak_db / 20) / m
        data = np.stack([l * g, r * g], axis=1)
    else:
        x = hp(x, 20)  # DC blocker (asymmetric saturation creates offset)
        x = trim_tail(x) if trim else x
        if loud_db is not None:
            g = 10 ** ((loud_db - loudest_window_db(x)) / 20)
            # never push the peak more than ~5 dB into the soft limiter
            g = min(g, 10 ** (5 / 20) / (np.max(np.abs(x)) + 1e-9))
            data = soft_limit(x * g) * 10 ** (peak_db / 20)
        else:
            data = norm(x, peak_db)
    data = np.clip(data, -1, 1)
    wavfile.write(os.path.join(OUT, name + ".wav"), SR, (data * 32767).astype(np.int16))
    return data


def ks_string(n, f0, decay=0.996, bright=0.5, rng=None):
    """Karplus-Strong plucked string."""
    rng = rng or RNG
    p = max(2, int(round(SR / f0)))
    buf = rng.uniform(-1, 1, p)
    buf = lp(buf, 800 + bright * 6000)
    y = np.zeros(n)
    idx = 0
    prev = 0.0
    for i in range(n):
        cur = buf[idx]
        avg = decay * (0.5 * cur + 0.5 * prev)
        prev = cur
        buf[idx] = avg
        y[i] = cur
        idx = (idx + 1) % p
    return y


def fm_bell(n, f, index=3.0, ratio=3.5, tau=0.6, rng=None):
    t = np.arange(n) / SR
    idx = index * np.exp(-t / (tau * 0.35))
    mod = np.sin(2 * np.pi * f * ratio * t)
    return np.sin(2 * np.pi * f * t + idx * mod) * np.exp(-t / tau)


def add_saw(n, f, harm_cut=9000, detune_cents=0.0, rng=None, phase=None, lpf=None):
    """Band-limited sawtooth (additive)."""
    rng = rng or RNG
    t = np.arange(n) / SR
    f = f * 2 ** (detune_cents / 1200)
    y = np.zeros(n)
    kmax = int(min(harm_cut, SR * 0.45) / f)
    ph = rng.uniform(0, 6.28) if phase is None else phase
    for k in range(1, max(2, kmax + 1)):
        w = 1.0 / k
        if lpf:
            w /= (1 + (k * f / lpf) ** 4)
        y += w * np.sin(2 * np.pi * f * k * t + ph * k)
    return y * 0.55


def shell_pop(n, rng):
    """Small explosive shell detonation layered under every cannon impact."""
    x = noise(n, rng)
    e = env_exp(n, 0.018, 0.0005)
    pop = bp(x, 250, 3500) * e
    thump = sine_sweep(n, 160, 60, 0.02) * env_exp(n, 0.06, 0.001)
    crack = hp(x, 2500) * env_exp(n, 0.003, 0.0002)
    return pop * 0.9 + thump * 0.8 + crack * 0.5


# ---------------------------------------------------------------------------------------------- weapons
def cannon(seed):
    rng = np.random.default_rng(100 + seed)
    n = int(1.15 * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    crack = hp(x, 900, 2) * env_exp(n, 0.0028, 0.0002)
    f_hi = 115 * rng.uniform(0.92, 1.08)
    boom = sine_sweep(n, f_hi * 2.2, f_hi * 0.48, 0.035) * env_exp(n, 0.1, 0.0012)
    boom = saturate(boom * 1.8, 1.5)
    fc = 350 + 4800 * np.exp(-t / 0.05)
    blast = svf_sweep(x, fc, 0.8) * (env_exp(n, 0.07, 0.0008) + 0.25 * env_exp(n, 0.22, 0.002))
    t0 = rng.uniform(0.065, 0.09)
    clack = np.zeros(n)
    m = modal(int(0.12 * SR), [1150, 2730, 4310, 6120], [0.03, 0.022, 0.016, 0.01], [1, 0.7, 0.45, 0.3], rng, 0.04)
    m += hp(noise(len(m), rng), 2000) * env_exp(len(m), 0.002) * 0.6
    place(clack, m, t0)
    dry = crack * 0.55 + boom * 1.0 + blast * 0.75 + clack * 0.16
    # outdoor slap-back + diffuse tail
    echo = np.zeros(n)
    place(echo, lp(crack * 0.6 + blast, 1300), rng.uniform(0.11, 0.15))
    tail = reverb(dry, rt60=0.9, mix=0.22, lp_hz=2200, seed=seed)
    y = tail + echo * 0.14
    y = hp(y, 35)
    return saturate(norm(y, -1) * 1.3, 1.2)


def casing(seed):
    rng = np.random.default_rng(200 + seed)
    n = int(0.55 * SR)
    y = np.zeros(n)
    times = [0.0, rng.uniform(0.11, 0.14), rng.uniform(0.2, 0.24)]
    amps = [1.0, 0.5, 0.25]
    for tt, a in zip(times, amps):
        m = modal(int(0.2 * SR), [3400, 5650, 7900, 9800], [0.08, 0.05, 0.035, 0.025], [1, 0.6, 0.35, 0.2], rng, 0.03)
        m += hp(noise(len(m), rng), 3000) * env_exp(len(m), 0.001) * 0.8
        place(y, m, tt, a)
    return y


def impact(material, seed):
    rng = np.random.default_rng(300 + seed * 7 + sum(map(ord, material)))
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    y = shell_pop(n, rng) * 0.85
    x = noise(n, rng)
    if material == "metal":
        f0 = rng.uniform(380, 620)
        ratios = [1, 1.47, 2.09, 2.56, 3.13, 3.78, 4.48, 5.22]
        decays = [0.26, 0.21, 0.16, 0.12, 0.1, 0.08, 0.06, 0.045]
        amps = [1, 0.8, 0.7, 0.55, 0.45, 0.35, 0.25, 0.2]
        y += modal(n, [f0 * r for r in ratios], decays, amps, rng, 0.02) * 0.55
        y += sine_sweep(n, 120, 80, 0.03) * env_exp(n, 0.05) * 0.5
        y += hp(x, 3000) * env_exp(n, 0.004) * 0.5
    elif material == "wood":
        f0 = rng.uniform(180, 260)
        y += modal(n, [f0, f0 * 2.31, f0 * 3.9, f0 * 5.6, f0 * 7.3], [0.07, 0.05, 0.035, 0.025, 0.018], [1, 0.7, 0.5, 0.3, 0.2], rng, 0.03) * 0.8
        y += bp(x, 1000, 4000) * env_exp(n, 0.025) * 0.6
        crackle = np.zeros(n)
        for _ in range(int(rng.integers(5, 10))):
            c = bp(noise(int(0.004 * SR), rng), 2000, 6000) * env_exp(int(0.004 * SR), 0.0015)
            place(crackle, c, rng.uniform(0.01, 0.12), rng.uniform(0.2, 0.6))
        y += crackle
    elif material == "rock":
        y += hp(x, 1500) * env_exp(n, 0.005) * 0.7
        y += lp(x, 420) * env_exp(n, 0.09, 0.002) * 1.0
        rattle = np.zeros(n)
        for _ in range(int(rng.integers(14, 26))):
            ln = int(0.02 * SR)
            f = rng.uniform(1500, 4200)
            c = np.sin(2 * np.pi * f * np.arange(ln) / SR) * env_exp(ln, 0.004)
            place(rattle, c, rng.uniform(0.02, 0.32) ** 1.3, rng.uniform(0.05, 0.25) * (1.2 - rng.uniform(0, 1)))
        y += rattle
    elif material == "flesh":
        y += sine_sweep(n, 115, 62, 0.04) * env_exp(n, 0.08, 0.002) * 1.0
        y += lp(x, 1200) * env_exp(n, 0.035, 0.001) * 0.8
        y += bp(x, 300, 900) * env_exp(n, 0.05) * 0.3
    else:  # soft: cactus, tents, bushes, tires
        y += lp(x, 700) * env_exp(n, 0.06, 0.002) * 0.9
        rust = bp(x, 1800, 6500) * env_exp(n, 0.14, 0.01)
        am = lp(np.abs(noise(n, rng)), 30)
        y += rust * am * 3.0
        y += sine_sweep(n, 130, 70, 0.05) * env_exp(n, 0.07) * 0.6
    y = reverb(y, 0.6, 0.15, 3000, seed)
    return y


def crit(seed):
    rng = np.random.default_rng(400 + seed)
    n = int(0.6 * SR)
    y = modal(n, [2400, 3650, 5100, 7200], [0.26, 0.2, 0.14, 0.09], [1, 0.7, 0.5, 0.3], rng, 0.02) * 0.5
    y += sine_sweep(n, 180, 50, 0.04) * env_exp(n, 0.12, 0.001) * 0.9
    y += hp(noise(n, rng), 4000) * env_exp(n, 0.01) * 0.4
    return reverb(y, 0.7, 0.18, 6000, seed)


def smash(seed):
    rng = np.random.default_rng(500 + seed)
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    y = sine_sweep(n, 120, 38, 0.05) * env_exp(n, 0.2, 0.002) * 1.2
    y += svf_sweep(x, 200 + 3000 * np.exp(-t / 0.04), 0.8) * env_exp(n, 0.12) * 0.8
    f0 = rng.uniform(200, 260)
    y += modal(n, [f0, f0 * 1.52, f0 * 2.4, f0 * 3.3, f0 * 4.6], [0.35, 0.25, 0.18, 0.12, 0.08], [1, 0.7, 0.5, 0.3, 0.2], rng, 0.02) * 0.35
    deb = np.zeros(n)
    for _ in range(18):
        ln = int(0.02 * SR)
        c = np.sin(2 * np.pi * rng.uniform(1200, 3600) * np.arange(ln) / SR) * env_exp(ln, 0.005)
        place(deb, c, rng.uniform(0.05, 0.45), rng.uniform(0.05, 0.2))
    y += deb
    return reverb(saturate(y, 1.4), 1.0, 0.22, 2500, seed)


def explosion(seed, big=False):
    rng = np.random.default_rng(600 + seed + (50 if big else 0))
    dur = 3.2 if big else 1.8
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    sub = sine_sweep(n, 95 if big else 75, 26 if big else 34, 0.12) * env_exp(n, 0.55 if big else 0.32, 0.004)
    fc = 280 + (7000 if big else 5500) * np.exp(-t / (0.28 if big else 0.18))
    blast = svf_sweep(x, fc, 0.75) * (env_exp(n, 0.25 if big else 0.14, 0.002) + 0.35 * env_exp(n, 0.9 if big else 0.5, 0.01))
    crack = hp(x, 1500) * env_exp(n, 0.006, 0.0003)
    crackle = np.zeros(n)
    for _ in range(int(60 if big else 35)):
        ln = int(0.006 * SR)
        c = hp(noise(ln, rng), 1500) * env_exp(ln, 0.0015)
        tt = rng.uniform(0.04, 1.6 if big else 0.9) ** 1.4
        place(crackle, c, tt, rng.uniform(0.1, 0.5) * np.exp(-tt / 0.8))
    debris = np.zeros(n)
    for _ in range(int(9 if big else 5)):
        f0 = rng.uniform(500, 1400)
        m = modal(int(0.4 * SR), [f0, f0 * 1.5, f0 * 2.3, f0 * 3.4], [0.18, 0.12, 0.08, 0.05], [1, 0.6, 0.4, 0.2], rng, 0.03)
        place(debris, m, rng.uniform(0.35, 1.6 if big else 1.1), rng.uniform(0.05, 0.16))
    y = sub * 1.2 + blast * 1.0 + crack * 0.5 + crackle * 0.6 + debris
    y = saturate(y * 1.2, 1.6)
    y = reverb(y, 2.0 if big else 1.3, 0.25, 1800, seed)
    return hp(y, 25)


def breakage(material, seed):
    rng = np.random.default_rng(700 + seed * 11 + sum(map(ord, material)))
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    y = np.zeros(n)
    if material == "wood":
        y += sine_sweep(n, 110, 50, 0.05) * env_exp(n, 0.12, 0.002) * 0.9
        for k in range(int(rng.integers(4, 7))):
            tt = rng.uniform(0, 0.35) ** 1.2
            ln = int(0.25 * SR)
            f0 = rng.uniform(150, 320)
            c = modal(ln, [f0, f0 * 2.3, f0 * 3.9], [0.06, 0.04, 0.03], [1, 0.6, 0.4], rng, 0.04)
            c += bp(noise(ln, rng), 900, 4500) * env_exp(ln, 0.03, 0.0005) * 1.2
            place(y, c, tt, rng.uniform(0.4, 1.0))
        spl = np.zeros(n)
        for _ in range(40):
            c = bp(noise(int(0.005 * SR), rng), 2000, 7000) * env_exp(int(0.005 * SR), 0.0015)
            place(spl, c, rng.uniform(0, 0.6) ** 1.5, rng.uniform(0.1, 0.4))
        y += spl
    elif material == "metal":
        y += sine_sweep(n, 100, 45, 0.06) * env_exp(n, 0.15, 0.002) * 0.8
        crumple = bp(x, 300, 2500) * env_exp(n, 0.18, 0.003)
        comb = signal.lfilter([1], np.concatenate([[1], np.zeros(int(SR / 410) - 1), [-0.6]]), crumple)
        y += comb * 0.5
        for k, tt in enumerate([0.0, rng.uniform(0.06, 0.1), rng.uniform(0.18, 0.26), rng.uniform(0.32, 0.45)]):
            f0 = rng.uniform(300, 750)
            m = modal(int(0.7 * SR), [f0, f0 * 1.47, f0 * 2.09, f0 * 2.56, f0 * 3.13, f0 * 4.1], [0.4, 0.3, 0.22, 0.16, 0.12, 0.08], [1, 0.8, 0.6, 0.5, 0.35, 0.25], rng, 0.02)
            place(y, m, tt, 0.45 / (1 + k * 0.6))
    elif material == "rock":
        y += sine_sweep(n, 90, 40, 0.06) * env_exp(n, 0.2, 0.003) * 1.0
        y += lp(x, 600) * env_exp(n, 0.16, 0.002) * 0.9
        y += hp(x, 2000) * env_exp(n, 0.006) * 0.6
        gravel = np.zeros(n)
        for _ in range(60):
            ln = int(0.015 * SR)
            c = np.sin(2 * np.pi * rng.uniform(900, 4000) * np.arange(ln) / SR) * env_exp(ln, 0.003)
            tt = rng.uniform(0.02, 0.9) ** 1.5
            place(gravel, c, tt, rng.uniform(0.04, 0.2) * np.exp(-tt / 0.5))
        y += gravel
    elif material == "body":
        y += sine_sweep(n, 100, 55, 0.05) * env_exp(n, 0.1, 0.002) * 1.0
        y += lp(x, 900) * env_exp(n, 0.05, 0.002) * 0.7
        for _ in range(5):
            f0 = rng.uniform(900, 2400)
            m = modal(int(0.2 * SR), [f0, f0 * 1.6, f0 * 2.7], [0.05, 0.035, 0.02], [1, 0.5, 0.3], rng, 0.05)
            place(y, m, rng.uniform(0.04, 0.3), rng.uniform(0.06, 0.15))
    else:  # soft
        y += lp(x, 600) * env_exp(n, 0.1, 0.003) * 0.9
        rust = bp(x, 1500, 7000) * env_exp(n, 0.3, 0.01)
        am = lp(np.abs(noise(n, rng)), 22)
        y += rust * am * 3.2
        y += sine_sweep(n, 120, 60, 0.06) * env_exp(n, 0.1) * 0.6
    y = reverb(y, 0.8, 0.2, 2800, seed)
    return y


# ---------------------------------------------------------------------------------------------- harpoon
def harpoon_fire(seed):
    rng = np.random.default_rng(800 + seed)
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    chunk = sine_sweep(n, 160, 75, 0.025) * env_exp(n, 0.05, 0.001)
    air = bp(x, 900, 5000) * env_exp(n, 0.07, 0.0015)
    twang = ks_string(n, rng.uniform(88, 104), 0.995, 0.5, rng) * env_exp(n, 0.35) * 0.35
    whoosh = svf_sweep(x, 3200 * np.exp(-t / 0.18) + 500, 2.0, "bp") * np.sin(np.clip(t / 0.3, 0, 1) * np.pi) * 0.5
    y = chunk * 0.9 + air * 0.7 + twang + whoosh
    return reverb(y, 0.6, 0.12, 4000, seed)


def harpoon_hit(seed):
    rng = np.random.default_rng(850 + seed)
    n = int(0.45 * SR)
    x = noise(n, rng)
    y = hp(x, 1800) * env_exp(n, 0.003) * 0.8
    y += modal(n, [1800, 3100, 4700, 6400], [0.07, 0.05, 0.035, 0.02], [1, 0.6, 0.4, 0.25], rng, 0.05) * 0.5
    y += sine_sweep(n, 140, 70, 0.03) * env_exp(n, 0.05) * 0.8
    return reverb(y, 0.5, 0.12, 4000, seed)


def reel(seed):
    rng = np.random.default_rng(900 + seed)
    dur = 0.42
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    tt = 0.0
    while tt < dur - 0.02:
        rate = 18 + 22 * (tt / dur)
        m = modal(int(0.03 * SR), [2100, 3500, 5200], [0.008, 0.006, 0.004], [1, 0.6, 0.3], rng, 0.05)
        place(y, m, tt, 0.5)
        tt += 1.0 / rate
    f = 320 + 300 * t / dur
    whine = np.sin(2 * np.pi * np.cumsum(f) / SR)
    whine = bp(whine + 0.3 * np.sign(whine), 400, 2000) * 0.12
    whir = bp(noise(n, rng), 600, 2200) * 0.25
    envl = np.sin(np.clip(t / dur, 0, 1) * np.pi) ** 0.5
    return (y + (whine + whir) * envl) * 1.0


# ---------------------------------------------------------------------------------------------- rewards / ui
NOTES = {"C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.0, "C6": 1046.5, "D6": 1174.7}


def absorb(note):
    rng = np.random.default_rng(int(NOTES[note]))
    n = int(0.9 * SR)
    x = noise(n, rng)
    clunk = modal(n, [190, 310, 470, 690], [0.05, 0.04, 0.03, 0.02], [1, 0.6, 0.4, 0.2], rng, 0.05) * 0.6
    clunk += sine_sweep(n, 120, 70, 0.02) * env_exp(n, 0.05) * 0.7
    clunk += lp(x, 1500) * env_exp(n, 0.012) * 0.4
    f = NOTES[note]
    chime = np.zeros(n)
    place(chime, fm_bell(int(0.8 * SR), f, 2.0, 3.5, 0.32, rng) * 0.32 + fm_bell(int(0.8 * SR), f * 2, 1.2, 2.0, 0.2, rng) * 0.12, 0.055)
    y = clunk + chime
    return reverb(y, 0.7, 0.16, 6000, 3)


def hurt(seed):
    rng = np.random.default_rng(1000 + seed)
    n = int(0.6 * SR)
    x = noise(n, rng)
    y = sine_sweep(n, 110, 55, 0.03) * env_exp(n, 0.08, 0.001) * 1.0
    y += lp(x, 1800) * env_exp(n, 0.04, 0.0008) * 0.8
    f0 = rng.uniform(230, 300)
    y += modal(n, [f0, f0 * 1.6, f0 * 2.3, f0 * 3.7], [0.09, 0.06, 0.045, 0.03], [1, 0.7, 0.5, 0.3], rng, 0.03) * 0.4
    return reverb(saturate(y, 1.3), 0.6, 0.12, 3000, seed)


def crash(seed):
    rng = np.random.default_rng(1050 + seed)
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    y = sine_sweep(n, 90, 40, 0.05) * env_exp(n, 0.12, 0.002) * 1.0
    y += svf_sweep(x, 300 + 2500 * np.exp(-t / 0.06), 0.9) * env_exp(n, 0.1) * 0.9
    f0 = rng.uniform(260, 420)
    y += modal(n, [f0, f0 * 1.47, f0 * 2.09, f0 * 2.9], [0.2, 0.15, 0.1, 0.07], [1, 0.7, 0.5, 0.3], rng, 0.03) * 0.3
    scrape = bp(x, 1500, 5000) * env_exp(n, 0.15, 0.01) * lp(np.abs(noise(n, rng)), 60) * 2.0
    y += scrape * 0.5
    return reverb(saturate(y, 1.3), 0.7, 0.15, 3000, seed)


def crossbow(seed):
    rng = np.random.default_rng(1100 + seed)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    y = ks_string(n, rng.uniform(205, 235), 0.99, 0.75, rng) * env_exp(n, 0.12) * 0.7
    y += modal(n, [420, 980], [0.03, 0.02], [1, 0.5], rng, 0.05) * 0.4
    y += svf_sweep(noise(n, rng), 2500 * np.exp(-t / 0.12) + 600, 2.0, "bp") * env_exp(n, 0.12, 0.01) * 0.4
    return y


def horn():
    """War-rig air horn (boss charge warning): two detuned saw voices a minor third apart, formant filtered."""
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    bend = 1 - 0.04 * np.exp(-t / 0.06)
    y = np.zeros(n)
    for f, a in ((233.1, 1.0), (277.2, 0.85), (116.5, 0.5)):
        ph = 2 * np.pi * np.cumsum(f * bend) / SR
        saw = np.zeros(n)
        for k in range(1, 30):
            saw += np.sin(k * ph) / k
        y += saw * a
    y = bp(y, 300, 3000)
    y = peak_eq(y, 650, 8, 2.0)
    y = peak_eq(y, 1500, 5, 2.5)
    env = np.clip(t / 0.03, 0, 1) * np.clip((1.15 - t) / 0.2, 0, 1)
    y = saturate(y * env * 0.6, 2.0)
    return reverb(y, 1.4, 0.3, 2500, 5)


def rumble():
    """Boss slam telegraph: low rising rumble."""
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    x = lp(noise(n), 160, 4)
    y = x * (t / 1.2) ** 1.5 * 3.0
    y += np.sin(2 * np.pi * np.cumsum(38 + 14 * t) / SR) * (t / 1.2) ** 2 * 0.6
    return fade_out(y, 0.05)


def click():
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * 1700 * t) * env_exp(n, 0.006, 0.0003)
    y += hp(noise(n), 3000) * env_exp(n, 0.0015) * 0.4
    y += np.sin(2 * np.pi * 420 * t) * env_exp(n, 0.012) * 0.5
    return y


def ui_open():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    y = svf_sweep(noise(n), 600 + 3500 * (t / 0.3), 1.5, "bp") * np.sin(np.clip(t / 0.3, 0, 1) * np.pi) * 0.6
    return y


def gem():
    rng = np.random.default_rng(1400)
    n = int(1.0 * SR)
    y = np.zeros(n)
    for i, f in enumerate([1568, 2093, 2637]):
        place(y, fm_bell(int(0.8 * SR), f, 1.5, 2.0, 0.28, rng) * 0.3, i * 0.06)
    return reverb(y, 0.9, 0.2, 8000, 9)


def repair(seed):
    """Air impact wrench burst at the repair station."""
    rng = np.random.default_rng(1500 + seed)
    dur = rng.uniform(0.3, 0.45)
    n = int((dur + 0.3) * SR)
    y = np.zeros(n)
    tt = 0.0
    while tt < dur:
        m = modal(int(0.03 * SR), [1900, 3200, 4600], [0.01, 0.007, 0.005], [1, 0.6, 0.35], rng, 0.04)
        m += lp(noise(len(m), rng), 1200) * env_exp(len(m), 0.004) * 0.6
        place(y, m, tt, 0.6)
        tt += 1 / rng.uniform(40, 48)
    hiss = bp(noise(n, rng), 3000, 9000) * env_exp(n, 0.15, 0.01) * 0.15
    return reverb(y + hiss, 0.5, 0.15, 5000, seed)


def glass():
    rng = np.random.default_rng(1600)
    n = int(1.0 * SR)
    y = hp(noise(n, rng), 3000) * env_exp(n, 0.02) * 0.5
    for _ in range(40):
        ln = int(0.12 * SR)
        f = rng.uniform(3500, 9500)
        c = modal(ln, [f, f * 1.37, f * 1.81], [0.04, 0.03, 0.02], [1, 0.5, 0.3], rng, 0.02)
        place(y, c, rng.uniform(0.0, 0.5) ** 1.4, rng.uniform(0.05, 0.25))
    return reverb(y, 0.8, 0.2, 9000, 10)


def ignition():
    """Starter motor cranking (respawn)."""
    rng = np.random.default_rng(1700)
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    tt = 0.0
    while tt < 0.75:
        ln = int(0.09 * SR)
        f = 95 + 20 * rng.uniform(-1, 1)
        c = np.sin(2 * np.pi * f * np.arange(ln) / SR) * np.sin(np.linspace(0, np.pi, ln)) ** 2
        c += bp(noise(ln, rng), 400, 2500) * np.sin(np.linspace(0, np.pi, ln)) * 0.35
        place(y, c, tt, 0.6)
        tt += 1 / 7.5
    whine = np.sin(2 * np.pi * np.cumsum(np.full(n, 420.0)) / SR) * 0.06
    return reverb(y + whine * np.clip((0.8 - t) / 0.1, 0, 1), 0.4, 0.1, 4000, 11)


def gate_open():
    rng = np.random.default_rng(1800)
    n = int(2.4 * SR)
    t = np.arange(n) / SR
    y = lp(noise(n, rng), 200, 4) * np.clip(t / 0.3, 0, 1) * np.clip((2.0 - t) / 0.3, 0, 1) * 2.0
    for i in range(14):
        m = modal(int(0.3 * SR), [800, 1300, 2100], [0.06, 0.04, 0.03], [1, 0.6, 0.4], rng, 0.08)
        place(y, m, 0.1 + i * 0.13 + rng.uniform(-0.02, 0.02), 0.25)
    thud = sine_sweep(int(0.6 * SR), 110, 40, 0.05) * env_exp(int(0.6 * SR), 0.2)
    place(y, thud * 1.2, 1.95)
    return reverb(y, 1.2, 0.25, 3000, 12)


def chest_open():
    rng = np.random.default_rng(1900)
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    creak = np.zeros(n)
    ln = int(0.5 * SR)
    f = 180 + 60 * np.sin(np.linspace(0, 3, ln))
    pulses = np.sin(2 * np.pi * np.cumsum(f) / SR)
    pulses = np.sign(pulses) * np.abs(pulses) ** 8
    creak[:ln] = bp(pulses, 400, 2500) * np.sin(np.linspace(0, np.pi, ln))
    y = creak * 0.5
    for i in range(10):
        f0 = rng.uniform(2800, 5200)
        place(y, modal(int(0.3 * SR), [f0, f0 * 1.5, f0 * 2.2], [0.08, 0.05, 0.03], [1, 0.5, 0.3], rng, 0.02), 0.45 + i * rng.uniform(0.03, 0.07), 0.25)
    return reverb(y, 0.9, 0.2, 7000, 13)


# ---------------------------------------------------------------------------------------------- loops
def seamless(fn_long, sec, xfade=0.5):
    """Render sec + xfade seconds and crossfade the end into the start -> seamless loop of length sec."""
    total = fn_long(sec + xfade + 0.05)
    n = int(sec * SR)
    m = int(xfade * SR)
    y = total[:n].copy()
    ramp = np.linspace(0, 1, m)
    y[:m] = y[:m] * np.sqrt(ramp) + total[n:n + m] * np.sqrt(1 - ramp)
    return y


def wind(sec):
    rng = np.random.default_rng(2000)
    n = int(sec * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    gust = lp(np.abs(noise(n, rng)), 0.4, 1)
    gust = (gust - gust.min()) / (gust.max() - gust.min() + 1e-9)
    body = lp(x, 500) * (0.35 + gust * 0.9)
    fc = 700 + 1600 * gust
    whistle = svf_sweep(noise(n, rng) * 0.3, fc, 6.0, "bp") * gust ** 2 * 0.6
    sand = hp(x, 4000) * (0.1 + gust * 0.25) * 0.25
    return body + whistle + sand


def skid_asphalt(sec):
    rng = np.random.default_rng(2100)
    n = int(sec * SR)
    t = np.arange(n) / SR
    x = noise(n, rng)
    jit = lp(noise(n, rng), 8) * 120
    sq = svf_sweep(x, 1050 + jit, 18.0, "bp") * 1.0 + svf_sweep(x, 2150 + jit * 2, 14.0, "bp") * 0.5
    am = 0.7 + 0.3 * lp(np.abs(noise(n, rng)), 30) * 3
    return sq * am + bp(x, 400, 3000) * 0.08


def skid_dirt(sec):
    rng = np.random.default_rng(2200)
    n = int(sec * SR)
    y = bp(noise(n, rng), 300, 2000) * 0.25
    for _ in range(int(sec * 220)):
        ln = int(0.006 * SR)
        c = bp(noise(ln, rng), 1500, 7000) * env_exp(ln, 0.0015)
        place(y, c, rng.uniform(0, sec), rng.uniform(0.05, 0.35))
    y += lp(noise(n, rng), 120) * 0.6
    return y


def rolling(sec):
    """Tires rolling over sand / gravel (quiet crunchy bed)."""
    rng = np.random.default_rng(2300)
    n = int(sec * SR)
    y = lp(noise(n, rng), 300) * 0.5 + bp(noise(n, rng), 800, 3000) * 0.08
    for _ in range(int(sec * 120)):
        ln = int(0.004 * SR)
        c = bp(noise(ln, rng), 1200, 5000) * env_exp(ln, 0.001)
        place(y, c, rng.uniform(0, sec), rng.uniform(0.02, 0.12))
    return y


# ---------------------------------------------------------------------------------------------- music
_NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def nf(name):
    """'F#5' -> Hz"""
    import re
    m = re.match(r"([A-G][#b]?)(-?\d)", name)
    midi = _NOTE[m.group(1)] + 12 * (int(m.group(2)) + 1)
    return 440.0 * 2 ** ((midi - 69) / 12)


def marimba(f, dur=1.0, rng=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.4)
    y += 0.3 * np.sin(2 * np.pi * 3.93 * f * t) * np.exp(-t / 0.07)
    y += 0.07 * np.sin(2 * np.pi * 9.3 * f * t) * np.exp(-t / 0.02)
    y += bp(noise(n, rng), 1500, 5000) * env_exp(n, 0.003) * 0.06
    return y * np.clip(t / 0.002, 0, 1)


def soft_bell(f, dur=1.4, rng=None):
    return fm_bell(int(dur * SR), f, 1.1, 3.0, 0.6, rng) * 0.8


class CasualTheme:
    """Light, unobtrusive casual-game theme in G major (marimba, nylon pluck, whistle, pad, soft drums).
    48 bars @ 104 BPM (~111 s), rendered as one seamless stereo loop (tails wrap to the start)."""

    PROG = (["G", "Em", "C", "D"] +                                   # intro
            ["G", "D", "Em", "C", "G", "D", "C", "D"] +               # A
            ["C", "G", "Am", "D", "C", "G", "Am", "D"] +              # B
            ["G", "D", "Em", "C", "G", "D", "C", "G"] +               # A2
            ["Em", "C", "G", "D", "Em", "C", "Am", "D"] +             # C (breakdown)
            ["C", "G", "Am", "D", "C", "G", "Am", "D"] +              # B2
            ["G", "Em", "C", "D"])                                    # outro -> loops to the intro
    CHORD = {"G": ["G2", "G3", "B3", "D4"], "D": ["D2", "D3", "F#3", "A3"], "Em": ["E2", "E3", "G3", "B3"],
             "C": ["C2", "C3", "E3", "G3"], "Am": ["A1", "A2", "C3", "E3"]}
    MEL_A = [[("D5", 1), ("B4", .5), ("D5", .5), ("G5", 1.5), (None, .5)],
             [("F#5", 1), ("E5", .5), ("D5", .5), ("A4", 2)],
             [("G5", 1), ("E5", .5), ("G5", .5), ("B5", 1.5), (None, .5)],
             [("A5", 1), ("G5", .5), ("E5", .5), ("G5", 2)],
             [("D5", 1), ("B4", .5), ("D5", .5), ("G5", 1), ("A5", 1)],
             [("F#5", 1.5), ("E5", .5), ("D5", 1), ("E5", 1)],
             [("G5", 1), ("E5", 1), ("C5", 1), ("E5", 1)],
             [("D5", 2), (None, 1), ("A4", .5), ("B4", .5)]]
    MEL_A2_END = [[("E5", 1), ("G5", 1), ("C6", 1), ("B5", .5), ("A5", .5)],
                  [("G5", 3), (None, 1)]]
    MEL_B = [[("G5", 1.5), ("E5", .5), ("C5", 1), ("E5", 1)],
             [("D5", 1.5), ("B4", .5), ("G4", 2)],
             [("A4", 1), ("C5", 1), ("E5", 1), ("A5", 1)],
             [("F#5", 1.5), ("E5", .5), ("D5", 2)],
             [("G5", 1.5), ("A5", .5), ("G5", 1), ("E5", 1)],
             [("D5", 1), ("G5", 1), ("B5", 2)],
             [("A5", 1), ("G5", .5), ("E5", .5), ("C5", 1), ("E5", 1)],
             [("D5", 3), (None, 1)]]

    def __init__(self):
        self.bpm = 104
        self.beat = 60 / self.bpm
        self.bars = len(self.PROG)
        self.n = int(round(self.bars * 4 * self.beat * SR))
        self.rng = np.random.default_rng(7)
        self.L = np.zeros(self.n); self.R = np.zeros(self.n)
        self.sL = np.zeros(self.n); self.sR = np.zeros(self.n)
        self.cache = {}

    def t(self, bar, beat=0.0):
        return ((bar - 1) * 4 + beat) * self.beat

    def add(self, sig, t0, gain=1.0, pan=0.0, send=0.25):
        sig = end_fade(sig)
        l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
        i0 = int(round(t0 * SR)) % self.n
        m = min(len(sig), self.n)
        first = min(m, self.n - i0)
        for buf, g in ((self.L, l * gain), (self.R, r * gain), (self.sL, l * gain * send), (self.sR, r * gain * send)):
            buf[i0:i0 + first] += sig[:first] * g
            if m > first:
                buf[:m - first] += sig[first:m] * g

    # ---- instruments (cached per pitch where possible)
    def _c(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def pluck(self, f):
        def mk():
            n = int(1.1 * SR)
            y = ks_string(n, f, 0.9962, 0.25, self.rng)
            return lp(y, 3000) * env_exp(n, 0.55, 0.002)
        return self._c(("pluck", round(f, 2)), mk)

    def mar(self, f):
        return self._c(("mar", round(f, 2)), lambda: marimba(f, 1.1, self.rng))

    def bell(self, f):
        return self._c(("bell", round(f, 2)), lambda: soft_bell(f, 1.4, self.rng))

    def bass(self, f, dur):
        n = int((dur + 0.08) * SR)
        t = np.arange(n) / SR
        y = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t) + 0.06 * np.sin(6 * np.pi * f * t)
        env = np.clip(t / 0.005, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.25)) * np.clip((dur + 0.06 - t) / 0.06, 0, 1)
        return y * env

    def pad(self, names, dur):
        n = int((dur + 0.9) * SR)
        t = np.arange(n) / SR
        y = np.zeros(n)
        for nm in names[1:]:
            f = nf(nm)
            for det in (-4, 4):
                ff = f * 2 ** (det / 1200)
                ph = self.rng.uniform(0, 6.28)
                y += np.sin(2 * np.pi * ff * t + ph) + 0.18 * np.sin(4 * np.pi * ff * t + ph)
        env = np.clip(t / 0.6, 0, 1) * np.clip((dur + 0.85 - t) / 0.85, 0, 1)
        return lp(y * env, 1400) * 0.25

    def whistle(self, f, dur):
        n = int((dur + 0.12) * SR)
        t = np.arange(n) / SR
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.4 * t) * np.clip((t - 0.15) / 0.2, 0, 1)
        scoop = 1 - 0.03 * np.exp(-t / 0.04)
        ph = 2 * np.pi * np.cumsum(f * vib * scoop) / SR
        y = np.sin(ph) + 0.04 * np.sin(2 * ph)
        y += bp(noise(n, self.rng), f * 0.8, f * 1.4) * 0.05
        env = np.clip(t / 0.05, 0, 1) * np.clip((dur + 0.1 - t) / 0.1, 0, 1)
        return y * env

    def kick(self):
        def mk():
            n = int(0.35 * SR)
            y = sine_sweep(n, 120, 50, 0.025) * env_exp(n, 0.11, 0.002)
            return y + hp(noise(n, self.rng), 3000) * env_exp(n, 0.0015) * 0.15
        return self._c("kick", mk)

    def clap(self):
        def mk():
            n = int(0.25 * SR)
            y = np.zeros(n)
            for k in range(3):
                place(y, bp(noise(int(0.04 * SR), self.rng), 1000, 3500) * env_exp(int(0.04 * SR), 0.012 if k < 2 else 0.05), k * 0.008)
            return y
        return self._c("clap", mk)

    def shaker(self):
        def mk():
            n = int(0.09 * SR)
            return hp(noise(n, self.rng), 5000) * env_exp(n, 0.022, 0.004)
        return self._c("shaker", mk)

    def tamb(self):
        def mk():
            n = int(0.25 * SR)
            y = hp(noise(n, self.rng), 6500) * env_exp(n, 0.05, 0.001) * 0.6
            return y + modal(n, [5600, 7900, 9400], [0.05, 0.04, 0.03], [1, 0.7, 0.4], self.rng, 0.02) * 0.25
        return self._c("tamb", mk)

    # ---- arrangement
    def play_melody(self, bar0, mel, instr, gain, pan, send=0.3, octave_mul=1.0):
        for i, barnotes in enumerate(mel):
            beat = 0.0
            for name, ln in barnotes:
                if name is not None:
                    f = nf(name) * octave_mul
                    t0 = self.t(bar0 + i, beat)
                    if instr == "mar":
                        self.add(self.mar(f), t0, gain, pan, send)
                    elif instr == "whistle":
                        self.add(self.whistle(f, ln * self.beat * 0.95), t0, gain, pan, send + 0.1)
                    elif instr == "pluck":
                        self.add(self.pluck(f), t0, gain, pan, send)
                beat += ln

    def compose(self):
        b = self.beat
        for bar, ch in enumerate(self.PROG, start=1):
            notes = self.CHORD[ch]
            sec = "intro" if bar <= 4 else "A" if bar <= 12 else "B" if bar <= 20 else "A2" if bar <= 28 else "C" if bar <= 36 else "B2" if bar <= 44 else "outro"
            # pad (all bars)
            self.add(self.pad(notes, 4 * b), self.t(bar), 0.55 if sec == "C" else 0.42, 0.0, 0.35)
            # nylon arpeggio (8ths) - everywhere but the breakdown
            arp = [nf(notes[1]), nf(notes[2]), nf(notes[3]), nf(notes[1]) * 2]   # octave 3-4, under the melody
            if sec != "C":
                for i, idx in enumerate([0, 2, 1, 2, 3, 2, 1, 2]):
                    if sec == "intro" and bar <= 2 and i % 2 == 1:
                        continue
                    self.add(self.pluck(arp[idx]), self.t(bar, i * 0.5), 0.2 if i % 2 == 0 else 0.15, -0.35, 0.25)
            else:
                # breakdown: slow bell arpeggio instead
                for i, idx in enumerate([0, 1, 2, 3]):
                    self.add(self.bell(arp[idx] * 4), self.t(bar, i), 0.11, 0.3, 0.45)
            # bass
            root = nf(notes[0])
            if sec in ("A", "B", "A2", "B2"):
                for beat, f, ln in ((0, root, 1.4), (1.5, root * 1.5, 0.45), (2, root, 0.9), (3, root * 2 if bar % 2 else root * 1.5, 0.9)):
                    self.add(self.bass(f, ln * b), self.t(bar, beat), 0.32, 0.0, 0.05)
            elif sec in ("C", "outro") or bar >= 3:
                self.add(self.bass(root, 3.6 * b), self.t(bar), 0.26, 0.0, 0.05)
            # drums
            if sec in ("A", "B", "A2", "B2"):
                kicks = (0, 2) if sec in ("A", "A2") else (0, 1.5, 2)
                for beat in kicks:
                    self.add(self.kick(), self.t(bar, beat), 0.42, 0.0, 0.05)
                for beat in (1, 3):
                    self.add(self.clap(), self.t(bar, beat), 0.13, 0.1, 0.35)
                step = 0.25 if sec in ("B", "B2") else 0.5
                k = 0
                while k * step < 4:
                    self.add(self.shaker(), self.t(bar, k * step), 0.06 if k % 2 == 0 else 0.04, 0.4, 0.1)
                    k += 1
                if sec in ("B", "B2"):
                    for beat in (1.5, 3.5):
                        self.add(self.tamb(), self.t(bar, beat), 0.07, -0.45, 0.2)
            elif sec in ("C", "outro") or bar >= 3:
                for k in range(8):
                    self.add(self.shaker(), self.t(bar, k * 0.5), 0.035, 0.4, 0.15)
        # melodies
        self.play_melody(5, self.MEL_A, "mar", 0.36, 0.15)
        self.play_melody(13, self.MEL_B, "whistle", 0.2, -0.05)
        self.play_melody(21, self.MEL_A[:6] + self.MEL_A2_END, "mar", 0.36, 0.15)
        self.play_melody(21, self.MEL_A[:6] + self.MEL_A2_END, "pluck", 0.1, -0.2, octave_mul=0.5)
        self.play_melody(37, self.MEL_B, "whistle", 0.2, -0.05)
        self.play_melody(37, self.MEL_B, "mar", 0.12, 0.25, octave_mul=0.5)
        self.play_melody(45, self.MEL_A[:2], "mar", 0.26, 0.15)

    def render(self):
        self.compose()
        irL, irR = reverb_ir(1.8, 2.2, 5000, 31, stereo=True, predelay=0.025)
        out = []
        for dry, send, ir in ((self.L, self.sL, irL), (self.R, self.sR, irR)):
            wet = signal.fftconvolve(np.concatenate([send, send]), ir)[self.n: 2 * self.n]
            y = hp(dry + wet * 0.6, 35)
            out.append(y)
        peak = max(np.max(np.abs(out[0])), np.max(np.abs(out[1])))
        g = 0.8 / peak
        return [soft_limit(ch * g) for ch in out]


def casual_levelup():
    rng = np.random.default_rng(1210)
    n = int(1.6 * SR)
    y = np.zeros(n)
    for i, nm in enumerate(["G5", "B5", "D6", "G6"]):
        place(y, marimba(nf(nm), 1.0, rng) * 0.5, i * 0.07)
    for nm in ("G5", "B5", "D6"):
        place(y, soft_bell(nf(nm), 1.3, rng) * 0.18, 0.3)
    k = sine_sweep(int(0.3 * SR), 120, 55, 0.025) * env_exp(int(0.3 * SR), 0.1)
    place(y, k * 0.4, 0.0)
    t = np.arange(int(0.5 * SR)) / SR
    shimmer = hp(noise(len(t), rng), 6000) * (t / 0.5) ** 2 * 0.08
    place(y, shimmer, 0.0)
    return reverb(y, 1.2, 0.22, 7000, 21)


def casual_unlock():
    rng = np.random.default_rng(1310)
    n = int(2.6 * SR)
    y = np.zeros(n)
    for i, nm in enumerate(["G4", "B4", "D5", "G5", "B5", "D6"]):
        place(y, marimba(nf(nm), 1.2, rng) * 0.45, i * 0.06)
    for nm in ("G4", "D5", "G5", "B5", "D6"):
        place(y, soft_bell(nf(nm), 2.0, rng) * 0.16, 0.42)
    for i in range(8):
        tm = hp(noise(int(0.2 * SR), rng), 6500) * env_exp(int(0.2 * SR), 0.05) * 0.12
        place(y, tm, 0.42 + i * 0.07)
    k = sine_sweep(int(0.4 * SR), 120, 50, 0.025) * env_exp(int(0.4 * SR), 0.14)
    place(y, k * 0.5, 0.42)
    t = np.arange(int(0.42 * SR)) / SR
    place(y, bp(noise(len(t), rng), 2000, 9000) * (t / 0.42) ** 2 * 0.12, 0.0)
    return reverb(y, 1.6, 0.25, 7000, 22)


def enemy_gun(seed):
    """Scrap pipe-gun / buggy machine gun: lighter and drier than the player's cannon."""
    rng = np.random.default_rng(1700 + seed)
    n = int(0.55 * SR)
    x = noise(n, rng)
    crack = hp(x, 2200) * env_exp(n, 0.0022, 0.0002)
    body = bp(x, 500, 3500) * env_exp(n, 0.026, 0.0005)
    thump = sine_sweep(n, 230 * rng.uniform(0.9, 1.1), 90, 0.015) * env_exp(n, 0.035, 0.001)
    y = crack * 0.7 + body * 0.9 + thump * 0.6
    y = saturate(y * 1.5, 1.3)
    return reverb(y, 0.5, 0.18, 3000, seed + 40)


def spear_throw(seed):
    rng = np.random.default_rng(1750 + seed)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    y = svf_sweep(noise(n, rng), 2600 * np.exp(-t / 0.15) + 500, 1.8, "bp") * np.sin(np.clip(t / 0.4, 0, 1) * np.pi) * 0.8
    y += sine_sweep(n, 140, 90, 0.05) * env_exp(n, 0.04, 0.003) * 0.2
    return y


# ---------------------------------------------------------------------------------------------- main
def main():
    made = []

    def w(name, x, **kw):
        write(name, x, **kw)
        made.append(name)

    for i in range(4):
        w(f"sfx_cannon_{i + 1}", cannon(i), loud_db=-9)
    for i in range(3):
        w(f"sfx_casing_{i + 1}", casing(i), peak_db=-6)
    for mat in ("metal", "wood", "rock", "flesh", "soft"):
        for i in range(4):
            w(f"sfx_impact_{mat}_{i + 1}", impact(mat, i), loud_db=-13)
    for i in range(2):
        w(f"sfx_crit_{i + 1}", crit(i), loud_db=-14)
    for i in range(2):
        w(f"sfx_smash_{i + 1}", smash(i))
    for i in range(3):
        w(f"sfx_explode_{i + 1}", explosion(i), loud_db=-9)
    for i in range(2):
        w(f"sfx_explodebig_{i + 1}", explosion(i, True), loud_db=-8)
    for mat in ("wood", "metal", "rock", "body", "soft"):
        for i in range(3):
            w(f"sfx_break_{mat}_{i + 1}", breakage(mat, i), loud_db=-12)
    for i in range(3):
        w(f"sfx_harpoon_{i + 1}", harpoon_fire(i), loud_db=-13)
    for i in range(3):
        w(f"sfx_hook_{i + 1}", harpoon_hit(i), loud_db=-15)
    for i in range(3):
        w(f"sfx_reel_{i + 1}", reel(i), peak_db=-5)
    for k, note in enumerate(["C5", "D5", "E5", "G5", "A5", "C6"]):
        w(f"sfx_absorb_{k + 1}", absorb(note), loud_db=-13)
    for i in range(3):
        w(f"sfx_hurt_{i + 1}", hurt(i), loud_db=-11)
    for i in range(3):
        w(f"sfx_crash_{i + 1}", crash(i), loud_db=-11)
    for i in range(2):
        w(f"sfx_shoot_{i + 1}", crossbow(i), peak_db=-3)
    w("sfx_warn_1", horn(), peak_db=-2)
    w("sfx_rumble_1", rumble(), peak_db=-3)
    w("sfx_levelup_1", casual_levelup(), peak_db=-2)
    w("sfx_unlock_1", casual_unlock(), peak_db=-1.5)
    for i in range(4):
        w(f"sfx_enemygun_{i + 1}", enemy_gun(i), loud_db=-12)
    for i in range(2):
        w(f"sfx_throw_{i + 1}", spear_throw(i), peak_db=-4)
    w("sfx_click_1", click(), peak_db=-6)
    w("sfx_open_1", ui_open(), peak_db=-8)
    w("sfx_gem_1", gem(), peak_db=-4)
    for i in range(2):
        w(f"sfx_repair_{i + 1}", repair(i), peak_db=-5)
    w("sfx_glass_1", glass(), peak_db=-4)
    w("sfx_ignition_1", ignition(), peak_db=-4)
    w("sfx_gate_1", gate_open(), peak_db=-2)
    w("sfx_chest_1", chest_open(), peak_db=-3)
    # loops (no tail trimming)
    w("loop_wind", seamless(wind, 24.0, 1.5), peak_db=-6, trim=False)
    w("loop_skid_asphalt", seamless(skid_asphalt, 2.0, 0.3), peak_db=-4, trim=False)
    w("loop_skid_dirt", seamless(skid_dirt, 2.0, 0.3), peak_db=-4, trim=False)
    w("loop_rolling", seamless(rolling, 2.0, 0.3), peak_db=-6, trim=False)
    # music: the old calm casual theme, only on request (the game's theme comes from Tools/MusicGen now)
    if LEGACY_THEME:
        theme = CasualTheme()
        l, r = theme.render()
        data = np.clip(np.stack([l, r], axis=1), -1, 1)
        wavfile.write(os.path.join(OUT, "music_theme.wav"), SR, (data * 32767).astype(np.int16))
        made.append("music_theme")
    else:
        print("music_theme.wav left as it is (Tools/MusicGen makes it; --legacy-theme writes the old one)")
    print(f"{len(made)} files -> {OUT}")


if __name__ == "__main__":
    main()
