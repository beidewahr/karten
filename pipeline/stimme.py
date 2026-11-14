"""Beide wahr – findet Gesang in einem Titel (MDX-Net «Kim_Vocal_2», ONNX, CPU).

Ergebnis: Kurve der Gesangslautheit (dB, 0,5-s-Raster) relativ zur Gesamtlautheit.
Aufruf: python3 stimme.py titel.mp4 out.npz
"""
import subprocess, sys, tempfile, pathlib
import numpy as np, librosa, onnxruntime as ort
from scipy.io import wavfile

SR, NFFT, HOP, DIM_F, DIM_T = 44100, 7680, 1024, 3072, 256
MODELL = pathlib.Path(__file__).with_name("modelle") / "Kim_Vocal_2.onnx"


def lade(pfad):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "x.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(pfad), "-ac", "2", "-ar", str(SR), str(tmp)], check=True)
    _, x = wavfile.read(tmp)
    return (x.astype(np.float32) / 32768.0).T  # (2, n)


def trenne(x, sess):
    chunk = HOP * (DIM_T - 1)
    trim = NFFT // 2
    gen = chunk - 2 * trim
    n = x.shape[1]
    pad = gen - n % gen
    mix = np.concatenate([np.zeros((2, trim)), x, np.zeros((2, pad)), np.zeros((2, trim))], 1)
    out = np.zeros_like(mix)
    for i in range(0, n + pad, gen):
        seg = mix[:, i:i + chunk]
        S = librosa.stft(seg, n_fft=NFFT, hop_length=HOP, window="hann", center=True, pad_mode="reflect")  # (2, F, T)
        S = S[:, :DIM_F, :DIM_T]
        inp = np.stack([S[0].real, S[0].imag, S[1].real, S[1].imag])[None].astype(np.float32)
        o = sess.run(None, {"input": inp})[0][0]
        V = np.zeros((2, NFFT // 2 + 1, DIM_T), complex)
        V[0, :DIM_F] = o[0] + 1j * o[1]
        V[1, :DIM_F] = o[2] + 1j * o[3]
        y = librosa.istft(V, hop_length=HOP, window="hann", center=True, length=chunk)
        out[:, i + trim:i + trim + gen] = y[:, trim:trim + gen]
    return out[:, trim:trim + n] * 1.009


def kurve(sig, hop_s=0.5):
    m = sig.mean(0)
    h = int(hop_s * SR)
    return np.array([np.sqrt(np.mean(m[i:i + h] ** 2)) + 1e-9 for i in range(0, len(m) - h + 1, h)])


def main(src, out):
    so = ort.SessionOptions(); so.intra_op_num_threads = 2
    sess = ort.InferenceSession(str(MODELL), so, providers=["CPUExecutionProvider"])
    x = lade(src)
    v = trenne(x, sess)
    kv, km = kurve(v), kurve(x)
    np.savez_compressed(out, vocal_db=20 * np.log10(kv), mix_db=20 * np.log10(km))
    rel = 20 * np.log10(kv) - 20 * np.log10(km)
    print(f"ok {pathlib.Path(src).name}: Anteil Gesang>-12dB rel: {np.mean(rel > -12):.0%}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
