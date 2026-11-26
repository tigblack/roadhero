#!/usr/bin/env python3
"""Measurements for Scarbound music files (no listening involved; numbers only).

    python measure.py <file.wav> [more.wav ...] [--loop] [--gain-db G] [--json out.json]

Per file:
- integrated loudness (ITU-R BS.1770-4: K-weighting, 400 ms blocks, absolute -70 LUFS and relative -10 LU gates),
  loudness range (EBU Tech 3342: 3 s short-term, -20 LU relative gate, 10th-95th percentile),
  true peak (4x oversampled), sample peak;
- mono: left/right correlation and how much the level changes when the channels are summed (a phone speaker or a
  mono Bluetooth speaker plays L+R);
- phone: the loudness of the mono sum through a small-speaker model (4th-order high-pass at 350 Hz, 2nd-order
  low-pass at 9 kHz) and how much loudness that model removes ("phone loss"), plus the share of power per band;
- with --loop: the seam (last sample -> first sample) against the local sample-to-sample steps, the level of the
  50 ms windows on both sides of the seam, and the quietest 200 ms anywhere (a loop must never fade to silence).
--gain-db applies a playback gain first (e.g. the in-game AudioSource volume) so in-game levels can be compared.
"""
import json
import sys

import numpy as np
import soundfile as sf
from scipy import signal


def k_weight(x, sr):
    """BS.1770 K-weighting (pre-filter shelf + RLB high-pass), designed for any sample rate (as pyloudnorm does)."""
    # stage 1: high shelf
    G, Q, fc = 3.999843853973347, 0.7071752369554196, 1681.974450955533
    K = np.tan(np.pi * fc / sr)
    Vh, Vb = 10 ** (G / 20), (10 ** (G / 20)) ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    # stage 2: high-pass
    Q2, fc2 = 0.5003270373238773, 38.13547087602444
    K2 = np.tan(np.pi * fc2 / sr)
    a02 = 1 + K2 / Q2 + K2 * K2
    b2 = [1, -2, 1]
    a2 = [1, 2 * (K2 * K2 - 1) / a02, (1 - K2 / Q2 + K2 * K2) / a02]
    y = signal.lfilter(b1, a1, x, axis=0)
    return signal.lfilter(b2, a2, y, axis=0)


def block_powers(x, sr, win, hop):
    """Mean-square per channel summed over channels (BS.1770 channel weights 1.0 for L/R/C)."""
    y = k_weight(x, sr)
    if y.ndim == 1:
        y = y[:, None]
    n, w, h = len(y), int(win * sr), int(hop * sr)
    if n < w:
        return np.array([np.sum(np.mean(y ** 2, axis=0))])
    cs = np.cumsum(np.concatenate([np.zeros((1, y.shape[1])), y ** 2]), axis=0)
    starts = np.arange(0, n - w + 1, h)
    ms = (cs[starts + w] - cs[starts]) / w
    return np.sum(ms, axis=1)


def lufs(p):
    return -0.691 + 10 * np.log10(np.maximum(p, 1e-20))


def integrated(x, sr):
    p = block_powers(x, sr, 0.4, 0.1)
    p = p[lufs(p) > -70]
    if len(p) == 0:
        return -np.inf
    rel = lufs(np.mean(p)) - 10
    p = p[lufs(p) > rel]
    return float(lufs(np.mean(p)))


def loudness_range(x, sr):
    p = block_powers(x, sr, 3.0, 0.1)
    p = p[lufs(p) > -70]
    if len(p) == 0:
        return 0.0
    rel = lufs(np.mean(p)) - 20
    l = np.sort(lufs(p[lufs(p) > rel]))
    return float(np.percentile(l, 95) - np.percentile(l, 10))


def true_peak(x):
    y = signal.resample_poly(x, 4, 1, axis=0)
    return float(20 * np.log10(np.max(np.abs(y)) + 1e-20))


def phone(x, sr):
    m = np.mean(x, axis=1) if x.ndim > 1 else x
    hp = signal.butter(4, 350, 'highpass', fs=sr, output='sos')
    lp = signal.butter(2, 9000, 'lowpass', fs=sr, output='sos')
    return signal.sosfilt(lp, signal.sosfilt(hp, m))


BANDS = [(20, 60), (60, 250), (250, 800), (800, 2500), (2500, 6000), (6000, 16000)]


def band_shares(x, sr):
    m = np.mean(x, axis=1) if x.ndim > 1 else x
    f, pxx = signal.welch(m, fs=sr, nperseg=8192)
    tot = np.sum(pxx[(f >= 20) & (f < 16000)])
    return [round(100 * float(np.sum(pxx[(f >= a) & (f < b)]) / tot), 1) for a, b in BANDS]


def seam(x, sr):
    """The jump from the last frame to the first, as a loop plays it."""
    m = x if x.ndim > 1 else x[:, None]
    wrap = np.concatenate([m[-sr:], m[:sr]])
    d = np.abs(np.diff(wrap, axis=0)).max(axis=1)
    jump = float(d[sr - 1])                     # last -> first
    local = float(np.percentile(d, 99.9))
    w = int(0.05 * sr)
    rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-20)
    before, after = rms(m[-w:]), rms(m[:w])
    # quietest 200 ms anywhere (sliding, hop 50 ms), including across the seam
    ext = np.concatenate([m, m[:int(0.2 * sr)]])
    e = np.mean(ext ** 2, axis=1)
    cs = np.concatenate([[0], np.cumsum(e)])
    n200, hop = int(0.2 * sr), int(0.05 * sr)
    st = np.arange(0, len(e) - n200, hop)
    win = 10 * np.log10((cs[st + n200] - cs[st]) / n200 + 1e-20)
    # level steps between neighbouring 50 ms windows anywhere vs at the seam
    e50 = 10 * np.log10(np.add.reduceat(e[:len(e) // w * w], np.arange(0, len(e) // w * w, w)) / w + 1e-20)
    steps = np.abs(np.diff(e50))
    return {'jump': round(jump, 5), 'local_p999_step': round(local, 5), 'jump_vs_local': round(jump / (local + 1e-12), 3),
            'rms_last_50ms_db': round(before, 2), 'rms_first_50ms_db': round(after, 2),
            'step_db_at_seam': round(abs(after - before), 2), 'p99_step_db_50ms': round(float(np.percentile(steps, 99)), 2),
            'quietest_200ms_db': round(float(win.min()), 1), 'first_frame': [round(float(v), 5) for v in m[0]],
            'last_frame': [round(float(v), 5) for v in m[-1]]}


def measure(path, gain_db=0.0, loop=False):
    x, sr = sf.read(path, always_2d=True)
    x = x * 10 ** (gain_db / 20)
    info = sf.info(path)
    L, R = x[:, 0], x[:, 1] if x.shape[1] > 1 else x[:, 0]
    corr = float(np.sum(L * R) / np.sqrt(np.sum(L * L) * np.sum(R * R) + 1e-20))
    rms = lambda a: np.sqrt(np.mean(a ** 2) + 1e-20)
    mono_fold = float(20 * np.log10(rms((L + R) / 2) / rms(x)))
    full = integrated(x, sr)
    ph = phone(x, sr)
    ph_lufs = integrated(ph[:, None], sr)
    out = {
        'file': path, 'sample_rate': sr, 'channels': info.channels, 'subtype': info.subtype, 'frames': info.frames,
        'seconds': round(info.frames / sr, 4), 'gain_db': gain_db,
        'lufs_i': round(full, 2), 'lra_lu': round(loudness_range(x, sr), 2), 'true_peak_dbtp': round(true_peak(x), 2),
        'sample_peak_dbfs': round(float(20 * np.log10(np.max(np.abs(x)) + 1e-20)), 2),
        'lr_correlation': round(corr, 3), 'mono_fold_db': round(mono_fold, 2),
        'phone_lufs': round(ph_lufs, 2), 'phone_loss_db': round(full - ph_lufs, 2),
        'band_share_pct': dict(zip(['20-60', '60-250', '250-800', '800-2.5k', '2.5-6k', '6-16k'], band_shares(x, sr))),
    }
    if loop:
        out['seam'] = seam(x, sr)
    return out


def main(argv):
    files, loop, gain, js = [], False, 0.0, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--loop':
            loop = True
        elif a == '--gain-db':
            gain = float(argv[i + 1]); i += 1
        elif a == '--json':
            js = argv[i + 1]; i += 1
        else:
            files.append(a)
        i += 1
    res = [measure(f, gain, loop) for f in files]
    for r in res:
        print(f"{r['file'].split('/')[-1]}: {r['seconds']} s, {r['sample_rate']} Hz {r['subtype']}, {r['frames']} frames"
              f"{' (gain %+.1f dB)' % r['gain_db'] if r['gain_db'] else ''}")
        print(f"  LUFS-I {r['lufs_i']}  LRA {r['lra_lu']} LU  true peak {r['true_peak_dbtp']} dBTP  sample peak {r['sample_peak_dbfs']}")
        print(f"  L/R corr {r['lr_correlation']}  mono fold {r['mono_fold_db']} dB  phone LUFS {r['phone_lufs']} (loss {r['phone_loss_db']} dB)")
        print(f"  bands % {r['band_share_pct']}")
        if 'seam' in r:
            s = r['seam']
            print(f"  seam: jump {s['jump']} vs local p99.9 step {s['local_p999_step']} (x{s['jump_vs_local']}); 50 ms RMS "
                  f"{s['rms_last_50ms_db']} -> {s['rms_first_50ms_db']} dB (step {s['step_db_at_seam']}, p99 elsewhere "
                  f"{s['p99_step_db_50ms']}); quietest 200 ms {s['quietest_200ms_db']} dB")
    if js:
        with open(js, 'w') as f:
            json.dump(res, f, indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
