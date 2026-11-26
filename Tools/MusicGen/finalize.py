#!/usr/bin/env python3
"""Turn the renderer's 48 kHz / 24-bit loop into the game's file: 44.1 kHz, 16-bit PCM, stereo, same loop.

    python finalize.py <loop.wav> <out.wav> [--bars N --bpm B] [--ceiling -1.0] [--mp3 preview.mp3 --master master.wav]

- The loop is resampled as one period of a periodic signal (FFT resampling over the whole loop), so the last frame
  still runs into the first exactly as before: no padding, no edge filter transient, no fractional length. At 100 BPM
  every bar is 2.4 s, so the loop's frame count is an integer at both rates (48 bars: 5,529,600 -> 5,080,320).
- The true peak is measured again at 44.1 kHz (4x oversampled); if it is above the ceiling the whole loop is turned
  down by the difference (one gain, no limiter, so the seam is untouched).
- 16-bit with TPDF dither (fixed seed: the file is reproducible).
- --mp3 also writes a listening preview from the unfolded master (the loop once plus a 3 s natural tail with a fade).
"""
import argparse
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy import fft as sfft
from scipy import signal

OUT_RATE = 44100


def periodic_resample(x, n_out):
    """Resample one period of a periodic signal (frames x channels) to n_out frames via the real FFT."""
    n_in = x.shape[0]
    X = sfft.rfft(x, axis=0)
    k = min(X.shape[0], n_out // 2 + 1)
    Y = np.zeros((n_out // 2 + 1, x.shape[1]), dtype=complex)
    Y[:k] = X[:k]
    if n_out % 2 == 0 and k == n_out // 2 + 1:
        Y[-1] = Y[-1].real            # the new Nyquist bin of a real signal is real
    return sfft.irfft(Y, n=n_out, axis=0) * (n_out / n_in)


def true_peak_db(x):
    y = signal.resample_poly(x, 4, 1, axis=0)
    # the loop is periodic: also oversample across the seam
    w = np.concatenate([x[-64:], x[:64]])
    yw = signal.resample_poly(w, 4, 1, axis=0)[64:-64]
    return float(20 * np.log10(max(np.max(np.abs(y)), np.max(np.abs(yw))) + 1e-20))


def tpdf_16(x, seed=20261119):
    rng = np.random.default_rng(seed)
    lsb = 1.0 / 32768.0
    d = (rng.random(x.shape) - rng.random(x.shape)) * lsb
    q = np.round((x + d) * 32767.0)
    return np.clip(q, -32768, 32767).astype(np.int16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('loop')
    ap.add_argument('out')
    ap.add_argument('--bars', type=int)
    ap.add_argument('--bpm', type=float, default=100.0)
    ap.add_argument('--ceiling', type=float, default=-1.0)
    ap.add_argument('--mp3')
    ap.add_argument('--master')
    ap.add_argument('--hi24', help='also write the 44.1 kHz loop as 24-bit PCM here (no dither)')
    a = ap.parse_args()

    x, sr = sf.read(a.loop, always_2d=True, dtype='float64')
    n_out = round(x.shape[0] * OUT_RATE / sr)
    if x.shape[0] * OUT_RATE % sr:
        sys.exit(f'{a.loop}: {x.shape[0]} frames at {sr} Hz is not a whole number of frames at {OUT_RATE} Hz')
    if a.bars:
        expect = a.bars * 4 * 60.0 / a.bpm * OUT_RATE
        if abs(expect - n_out) > 1e-6:
            sys.exit(f'loop length {n_out} frames != {a.bars} bars at {a.bpm} BPM ({expect})')
    y = periodic_resample(x, n_out)
    tp = true_peak_db(y)
    gain_db = 0.0
    if tp > a.ceiling - 0.05:
        gain_db = a.ceiling - 0.05 - tp
        y *= 10 ** (gain_db / 20)
    if a.hi24:
        sf.write(a.hi24, y, OUT_RATE, subtype='PCM_24')
    q = tpdf_16(y)
    sf.write(a.out, q, OUT_RATE, subtype='PCM_16')
    tp_after = true_peak_db(q.astype(np.float64) / 32768.0)
    print(f'{a.out}: {n_out} frames ({n_out / OUT_RATE:.4f} s) at {OUT_RATE} Hz, 16-bit PCM stereo; true peak '
          f'{tp:.2f} -> {tp_after:.2f} dBTP (gain {gain_db:+.2f} dB)')

    if a.mp3:
        src = a.master or a.loop
        m, msr = sf.read(src, always_2d=True, dtype='float64')
        n = min(len(m), x.shape[0] + 3 * msr)
        m = m[:n].copy()
        fade = int(2.0 * msr)
        m[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
        m *= 10 ** (gain_db / 20)
        tmp = a.mp3 + '.tmp.wav'
        sf.write(tmp, m, msr, subtype='PCM_24')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', tmp, '-ar', str(OUT_RATE),
                        '-c:a', 'libmp3lame', '-b:a', '256k', a.mp3], check=True)
        import os
        os.remove(tmp)
        print(f'{a.mp3}: listening preview (the loop once and a 3 s tail, faded)')


if __name__ == '__main__':
    main()
