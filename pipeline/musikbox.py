"""Beide wahr – Musikbox: kleiner Synthesizer + 10 Stücke in beliebten Reel-Stilen (13.11.2026).

Alle Klänge werden mathematisch erzeugt (keine Samples, keine Rechte Dritter).
Orientierung an Genres, die in Reels beliebt sind – keine Kopie bestehender Lieder.
Länge 12,8 s (= Reel-Länge). Aufruf: python3 musikbox.py out_ordner/ [nummer ...]
"""
import sys, pathlib, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, lfilter, fftconvolve

SR = 44100
DUR = 12.8
RNG = np.random.default_rng(7)
TRANSPOSE = 0      # Halbtöne, für Varianten
TEMPO = 1.0        # Tempofaktor, für Varianten


# ---------------------------------------------------------------- Grundlagen
def hz(m):
    return 440.0 * 2 ** ((m + TRANSPOSE - 69) / 12)


def tt(dur):
    return np.arange(int(dur * SR)) / SR


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 100), "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def adsr(n, a=0.005, d=0.1, s=0.7, r=0.1):
    e = np.full(n, s, float)
    A, D, R = max(1, int(a * SR)), max(1, int(d * SR)), max(1, int(r * SR))
    A = min(A, n); e[:A] = np.linspace(0, 1, A)
    D = min(D, n - A); e[A:A + D] = np.linspace(1, s, D)
    R = min(R, n); e[-R:] *= np.linspace(1, 0, R)
    return e


def saw(f, t, detune=0.0):
    ph = (f * (1 + detune) * t + RNG.random()) % 1.0
    return 2 * ph - 1


def square(f, t, duty=0.5):
    return np.where((f * t) % 1.0 < duty, 1.0, -1.0)


# ---------------------------------------------------------------- Instrumente (mono)
def piano(f, dur=1.5, vel=1.0):
    t = tt(dur)
    x = sum(a * np.sin(2 * np.pi * f * k * (1 + 0.0004 * k * k) * t) * np.exp(-t * (1.2 + 0.9 * k + f / 900))
            for k, a in ((1, 1), (2, .5), (3, .25), (4, .12), (5, .06)))
    x *= np.minimum(1, t / 0.003)
    return vel * x * adsr(len(t), 0.002, 0.05, 1, 0.08)


def epiano(f, dur=1.5, vel=1.0):
    t = tt(dur)
    idx = 1.8 * np.exp(-t * 6)
    x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) * np.exp(-t * 1.6)
    x += 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 4)
    x *= 1 + 0.12 * np.sin(2 * np.pi * 5 * t)  # Tremolo
    return vel * x * adsr(len(t), 0.003, 0.05, 1, 0.12)


def pluck(f, dur=1.2, vel=1.0, bright=0.6, decay=0.996):
    """Karplus-Strong (Gitarre/Ukulele)."""
    n = int(dur * SR); N = max(2, int(round(SR / f - 0.5)))
    exc = RNG.uniform(-1, 1, N)
    exc = lp(exc, 1500 + 7000 * bright, 1) if N > 8 else exc
    x = np.zeros(n); x[:N] = exc[:min(N, n)]
    a = np.zeros(N + 2); a[0] = 1; a[N] = -decay / 2; a[N + 1] = -decay / 2
    y = lfilter([1.0], a, x)
    return vel * y * adsr(n, 0.001, 0.01, 1, 0.05) * 0.7


def marimba(f, dur=0.8, vel=1.0):
    t = tt(dur)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 7) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 22) \
        + 0.12 * np.sin(2 * np.pi * 9.9 * f * t) * np.exp(-t * 45)
    return vel * x * np.minimum(1, t / 0.002)


def bell(f, dur=1.6, vel=1.0):
    t = tt(dur)
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d) for k, a, d in ((1, 1, 2.2), (2.76, .4, 4), (5.4, .2, 7), (8.9, .08, 11)))
    return vel * x * np.minimum(1, t / 0.002)


def whistle(f, dur=0.5, vel=1.0):
    t = tt(dur)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.25)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    x = np.sin(ph) + 0.04 * hp(RNG.normal(0, 1, len(t)), 3000)
    return vel * x * adsr(len(t), 0.04, 0.05, 0.85, 0.06)


def pad(freqs, dur, vel=1.0, cutoff=2500, attack=0.4):
    t = tt(dur)
    x = sum(saw(f, t, d) for f in freqs for d in (-0.004, 0, 0.0045)) / (3 * len(freqs))
    return vel * lp(x, cutoff, 2) * adsr(len(t), attack, 0.3, 0.85, 0.5)


def supersaw(freqs, dur, vel=1.0, cutoff=7000):
    t = tt(dur)
    x = sum(saw(f, t, d) for f in freqs for d in (-0.012, -0.007, -0.003, 0, 0.003, 0.007, 0.012)) / (7 * len(freqs))
    return vel * lp(x, cutoff, 2) * adsr(len(t), 0.01, 0.2, 0.75, 0.15)


def lead_saw(f, dur, vel=1.0, cutoff=3500):
    t = tt(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.8 * t) * np.minimum(1, t / 0.3)
    ph = (np.cumsum(f * vib) / SR) % 1.0
    x = (2 * ph - 1) * 0.6 + 0.4 * (2 * ((ph + 0.5) % 1.0) - 1) * 0.5
    return vel * lp(x, cutoff) * adsr(len(t), 0.01, 0.1, 0.8, 0.08)


def chip(f, dur, vel=1.0, duty=0.25):
    t = tt(dur)
    return vel * 0.5 * square(f, t, duty) * adsr(len(t), 0.002, 0.05, 0.7, 0.02)


def tri(f, dur, vel=1.0):
    t = tt(dur)
    x = 2 * np.abs(2 * ((f * t) % 1.0) - 1) - 1
    return vel * x * adsr(len(t), 0.002, 0.02, 0.9, 0.02)


def bass_sub(f, dur, vel=1.0):
    t = tt(dur)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    return vel * x * adsr(len(t), 0.005, 0.1, 0.8, 0.06)


def bass_pluck(f, dur, vel=1.0, cutoff=900):
    t = tt(dur)
    x = 0.6 * saw(f, t) + 0.6 * np.sin(2 * np.pi * f * t)
    x = lp(x, cutoff) * np.exp(-t * 3)
    return vel * x * adsr(len(t), 0.003, 0.05, 1, 0.04)


def slap(f, dur, vel=1.0):
    t = tt(dur)
    x = 0.7 * saw(f, t) * np.exp(-t * 4) + 0.7 * np.sin(2 * np.pi * f * t) * np.exp(-t * 2.5)
    x = lp(x, 2500) + 0.15 * hp(RNG.normal(0, 1, len(t)), 2000) * np.exp(-t * 80)
    return vel * x * adsr(len(t), 0.001, 0.05, 1, 0.03)


def clav(f, dur=0.18, vel=1.0):
    t = tt(dur)
    x = square(f, t, 0.3) * 0.5 + saw(f * 2, t) * 0.2
    return vel * hp(lp(x, 4500), 300) * np.exp(-t * 14)


def stab(freqs, dur=0.25, vel=1.0):
    t = tt(dur)
    x = sum(saw(f, t, d) for f in freqs for d in (-0.003, 0.003)) / (2 * len(freqs))
    return vel * lp(x, 3200) * adsr(len(t), 0.005, 0.08, 0.6, 0.06)


# ---------------------------------------------------------------- Schlagzeug
def kick(vel=1.0, tone=1.0, dur=0.4):
    t = tt(dur)
    f = 45 + 110 * tone * np.exp(-t * 32)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    x += 0.15 * hp(RNG.normal(0, 1, len(t)), 3000) * np.exp(-t * 300)
    return vel * x


def snare(vel=1.0, dur=0.25):
    t = tt(dur)
    x = 0.7 * bp(RNG.normal(0, 1, len(t)), 1200, 8000) * np.exp(-t * 18) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    return vel * x


def clap(vel=1.0):
    t = tt(0.3)
    nz = bp(RNG.normal(0, 1, len(t)), 900, 5000)
    env = np.zeros(len(t))
    for o in (0, 0.009, 0.018):
        i = int(o * SR); env[i:] += np.exp(-(t[: len(t) - i]) * 90)
    env += 0.5 * np.exp(-t * 14) * (t > 0.02)
    return vel * nz * env * 0.6


def hat(vel=1.0, open_=False):
    t = tt(0.25 if open_ else 0.05)
    return vel * 0.4 * hp(RNG.normal(0, 1, len(t)), 7000) * np.exp(-t * (12 if open_ else 70))


def shaker(vel=1.0):
    t = tt(0.09)
    return vel * 0.3 * hp(RNG.normal(0, 1, len(t)), 5000) * np.minimum(1, t / 0.012) * np.exp(-t * 40)


def snap(vel=1.0):
    t = tt(0.12)
    return vel * 0.8 * bp(RNG.normal(0, 1, len(t)), 1500, 4500) * np.exp(-t * 60)


def tom(f=110, vel=1.0):
    t = tt(0.5)
    return vel * np.sin(2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-t * 20))) / SR) * np.exp(-t * 6)


def noise_hit(vel=1.0, dur=0.06):
    t = tt(dur)
    return vel * 0.4 * np.sign(RNG.normal(0, 1, len(t))) * np.exp(-t * 50)


def swell(dur=1.5, vel=1.0):
    t = tt(dur)
    return vel * 0.25 * hp(RNG.normal(0, 1, len(t)), 3000) * (t / dur) ** 2


def crackle(dur):
    n = int(dur * SR); x = np.zeros(n)
    idx = RNG.integers(0, n, int(dur * 25)); x[idx] = RNG.uniform(-1, 1, len(idx))
    return lp(hp(x, 1000), 6000) * 0.5 + 0.004 * lp(RNG.normal(0, 1, n), 3000)


# ---------------------------------------------------------------- Mischpult
class Mix:
    def __init__(self, bpm, swing=0.0):
        self.n = int(DUR * SR)
        self.bus = {}
        bpm = bpm * TEMPO
        self.bpm, self.swing = bpm, swing
        self.beat = 60 / bpm

    def t(self, bar, beat):
        b = bar * 4 + beat
        frac = b % 1
        if self.swing and abs(frac - 0.5) < 1e-6:  # Achtel-Swing
            b += self.swing * 0.5 - 0.0
        return b * self.beat

    def add(self, bus, x, sec, pan=0.0, gain=1.0):
        if bus not in self.bus:
            self.bus[bus] = np.zeros((self.n, 2))
        i = int(sec * SR)
        if i >= self.n:
            return
        j = min(self.n, i + len(x))
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.bus[bus][i:j, 0] += x[: j - i] * l * gain * 1.414
        self.bus[bus][i:j, 1] += x[: j - i] * r * gain * 1.414

    def bars(self):
        return int(np.ceil(DUR / (4 * self.beat)))

    def render(self, levels, reverb=0.15, sends=None, duck=None, master_lp=None):
        out = np.zeros((self.n, 2))
        rev_in = np.zeros((self.n, 2))
        sends = sends or {}
        for name, buf in self.bus.items():
            b = buf * levels.get(name, 1.0)
            if duck and name in duck["busse"]:
                b = b * duck["env"][:, None]
            out += b
            rev_in += b * sends.get(name, 0.3)
        if reverb:
            ln = int(1.8 * SR)
            for ch in range(2):
                ir = RNG.normal(0, 1, ln) * np.exp(-np.arange(ln) / SR * 3.0); ir[: int(0.02 * SR)] = 0
                out[:, ch] += fftconvolve(rev_in[:, ch], ir)[: self.n] * reverb * 0.02
        if master_lp:
            out = np.stack([lp(out[:, 0], master_lp), lp(out[:, 1], master_lp)], 1)
        out = handy_balance(out)
        fo = int(0.5 * SR); out[-fo:] *= np.linspace(1, 0, fo)[:, None]
        fi = int(0.01 * SR); out[:fi] *= np.linspace(0, 1, fi)[:, None]
        rms = np.sqrt(np.mean(out ** 2))
        out *= 10 ** (-15 / 20) / max(rms, 1e-9)
        out = np.tanh(out * 1.2) / 1.2
        pk = np.max(np.abs(out))
        if pk > 0.95:
            out *= 0.95 / pk
        return out

    def duck_env(self, kick_beats, depth=0.6, rel=0.18):
        env = np.ones(self.n)
        t = np.arange(self.n) / SR
        for s in kick_beats:
            m = t >= s
            env[m] = np.minimum(env[m], 1 - depth * np.exp(-(t[m] - s) / rel))
        return env


def handy_balance(out, ziel_bass=0.33):
    """Für Handy-Lautsprecher: Gleichanteil weg, Bass (<150 Hz) auf ca. 45 % der Energie begrenzen,
    Präsenz (2–6 kHz) leicht anheben, damit Melodie und Rhythmus auch auf kleinen Lautsprechern hörbar sind."""
    res = []
    for ch in range(2):
        x = hp(out[:, ch], 35, 2)
        low = lp(lp(x, 150, 2), 150, 2); rest = hp(hp(x, 150, 2), 150, 2)  # Linkwitz-Riley-Weiche
        el, er = np.sum(low ** 2), np.sum(rest ** 2)
        if el / (el + er) > ziel_bass:
            g = np.sqrt(ziel_bass * er / ((1 - ziel_bass) * el))
            low *= g
        rest = rest + 0.45 * bp(rest, 2000, 6000) + 0.2 * hp(rest, 6000)
        res.append(low + rest)
    return np.stack(res, 1)


def chord_midi(name):
    """Akkordtöne als MIDI (Grundlage)."""
    roots = {"C": 60, "D": 62, "E": 64, "F": 65, "G": 67, "A": 69, "B": 71}
    r = roots[name[0]]; q = name[1:]
    shapes = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11],
              "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14], "add9": [0, 4, 7, 14], "sus2": [0, 2, 7], "6": [0, 4, 7, 9]}
    return r, [r + i for i in shapes[q]]


# ---------------------------------------------------------------- 10 Stücke
def t01_sonnenschein():
    """Ukulele-Pop mit Pfeifmelodie und Klatschen – der Klassiker für fröhliche Reels (110 BPM, C–G–Am–F)."""
    m = Mix(110)
    prog = ["C", "G", "Am", "F"]
    voic = {"C": [67, 72, 76, 79], "G": [67, 71, 74, 79], "Am": [69, 72, 76, 81], "F": [65, 69, 72, 77]}
    strum = [0, 1, 1.5, 2.5, 3, 3.5]
    mel = {"C": [(0, 76, .5), (.5, 79, .5), (1, 79, 1), (2, 81, .5), (2.5, 79, .5), (3, 76, 1)],
           "G": [(0, 74, .5), (.5, 79, .5), (1, 79, 1), (2, 77, .5), (2.5, 76, .5), (3, 74, 1)],
           "Am": [(0, 72, .5), (.5, 76, .5), (1, 76, 1), (2, 79, .5), (2.5, 76, .5), (3, 72, 1)],
           "F": [(0, 72, .5), (.5, 74, .5), (1, 76, .5), (1.5, 77, .5), (2, 76, 1), (3, 74, 1)]}
    for bar in range(m.bars()):
        c = prog[bar % 4]; root, _ = chord_midi(c)
        for k, b in enumerate(strum):
            up = b % 1 != 0
            for j, n in enumerate(voic[c][::-1] if up else voic[c]):
                m.add("uke", pluck(hz(n), 0.9, 0.5 if up else 0.7, 0.8), m.t(bar, b) + j * 0.012, pan=0.25)
        for b in (0, 1.5, 2):
            m.add("kick", kick(0.9), m.t(bar, b))
        for b in (1, 3):
            m.add("clap", clap(), m.t(bar, b))
        for b in np.arange(0, 4, 0.5):
            m.add("shaker", shaker(0.8 if b % 1 else 0.5), m.t(bar, b), pan=-0.3)
        m.add("bass", bass_sub(hz(root - 24), 0.9 * m.beat * 2), m.t(bar, 0))
        m.add("bass", bass_sub(hz(root - 24 + 7), 0.9 * m.beat * 2), m.t(bar, 2))
        if bar >= 1:
            for b, n, d in mel[c]:
                m.add("lead", whistle(hz(n + 12), d * m.beat * 0.95), m.t(bar, b), pan=-0.1)
    return m.render({"uke": .55, "kick": .9, "clap": .5, "shaker": .45, "bass": .7, "lead": .32}, reverb=0.12)


def t02_lofi():
    """Lo-Fi Hip-Hop: E-Piano-Septakkorde, geswingte Hi-Hats, Knistern (82 BPM)."""
    m = Mix(82, swing=0.33)
    prog = [("F", [53, 57, 60, 64, 67]), ("E", [52, 55, 59, 62, 67]), ("D", [50, 53, 57, 60, 64]), ("C", [48, 55, 59, 62, 64])]
    mel = [(0.5, 76), (1.5, 74), (2, 72), (3, 69)], [(0.5, 74), (1, 71), (2.5, 67)], [(0, 72), (0.5, 74), (1.5, 77), (2.5, 76)], [(0.5, 71), (2, 72)]
    for bar in range(m.bars()):
        name, v = prog[bar % 4]
        for b in (0, 1.5):
            for n in v:
                m.add("keys", epiano(hz(n), 1.6, 0.35), m.t(bar, b) + RNG.uniform(0, 0.01), pan=RNG.uniform(-0.2, 0.2))
        m.add("bass", bass_sub(hz(v[0] - 12), m.beat * 1.4), m.t(bar, 0))
        m.add("bass", bass_sub(hz(v[0] - 12), m.beat * 0.9), m.t(bar, 2.5))
        for b in (0, 2.5):
            m.add("kick", kick(0.85, tone=0.8), m.t(bar, b))
        m.add("kick", kick(0.5, tone=0.8), m.t(bar, 2.75))
        for b in (1, 3):
            m.add("snare", snare(0.6), m.t(bar, b))
        for b in np.arange(0, 4, 0.5):
            m.add("hat", hat(0.5 if b % 1 else 0.8), m.t(bar, b), pan=0.3)
        if bar >= 1:
            for b, n in mel[bar % 4]:
                m.add("lead", bell(hz(n + 12), 1.2, 0.35), m.t(bar, b), pan=-0.25)
    m.add("vinyl", crackle(DUR), 0)
    return m.render({"keys": .6, "bass": .6, "kick": .8, "snare": .5, "hat": .3, "lead": .3, "vinyl": .5}, reverb=0.18, master_lp=6500)


def t03_inspiration():
    """Inspirierendes Klavier mit Streicherfläche und Klatschen – typischer «Motivations»-Sound (120 BPM)."""
    m = Mix(120)
    prog = ["C", "Am", "F", "G"]
    for bar in range(m.bars()):
        c = prog[bar % 4]; root, notes = chord_midi(c)
        arp = [root, root + 7, root + 12, notes[1] + 12, root + 12, root + 7, notes[1] + 12, root + 19]
        for k, n in enumerate(arp):
            m.add("piano", piano(hz(n), 1.2, 0.55 if k % 2 else 0.75), m.t(bar, k * 0.5), pan=0.15)
        m.add("pad", pad([hz(n - 12) for n in notes] + [hz(root - 24)], 4 * m.beat + 0.3, 0.9, 1800, 0.25), m.t(bar, 0))
        for b in np.arange(0, 4, 0.5):
            m.add("bass", bass_pluck(hz(root - 24), 0.25, 0.8), m.t(bar, b))
        if bar >= 1:
            for b in range(4):
                m.add("kick", kick(0.8), m.t(bar, b))
        if bar >= 2:
            for b in (1, 3):
                m.add("clap", clap(), m.t(bar, b))
            for b in np.arange(0.5, 4, 1):
                m.add("hat", hat(0.6), m.t(bar, b), pan=0.3)
            m.add("lead", bell(hz([76, 72, 72, 74][bar % 4] + 12), 2.0, 0.6), m.t(bar, 0), pan=-0.2)
    return m.render({"piano": .6, "pad": .35, "bass": .45, "kick": .75, "clap": .45, "hat": .3, "lead": .3}, reverb=0.22)


def t04_tropisch():
    """Tropical House: Marimba-Melodie im 3-3-2-Rhythmus, pumpende Akkorde (105 BPM, F–C–G–Am)."""
    m = Mix(105)
    prog = ["F", "C", "G", "Am"]
    rhythm = [0, 0.75, 1.5, 2, 2.75, 3.5]
    kicks = []
    for bar in range(m.bars()):
        c = prog[bar % 4]; root, notes = chord_midi(c)
        m.add("pad", pad([hz(n) for n in notes], 4 * m.beat + 0.2, 1.0, 3000, 0.02), m.t(bar, 0))
        top = sorted(n + 12 for n in notes)
        mel = [top[2], top[1], top[2], top[0] + 12, top[2], top[1]] if bar % 2 == 0 else [top[1], top[2], top[0] + 12, top[2], top[1], top[0]]
        if bar >= 1:
            for b, n in zip(rhythm, mel):
                m.add("marimba", marimba(hz(n), 0.7, 0.8), m.t(bar, b), pan=-0.15)
        for b in range(4):
            m.add("kick", kick(0.85, tone=0.9), m.t(bar, b)); kicks.append(m.t(bar, b))
            m.add("hat", hat(0.7, open_=True), m.t(bar, b + 0.5), pan=0.3)
        for b in (1, 3):
            m.add("snare", snap(), m.t(bar, b))
        for b in (0.5, 1.5, 2.5, 3.5):
            m.add("bass", bass_pluck(hz(root - 24), 0.3, 0.9, 700), m.t(bar, b))
    duck = {"busse": ["pad", "bass"], "env": m.duck_env(kicks, 0.65, 0.16)}
    return m.render({"pad": .45, "marimba": .55, "kick": .8, "hat": .25, "snare": .4, "bass": .6}, reverb=0.15, duck=duck)


def t05_neon():
    """Synthwave: Sägezahn-Arpeggio, pumpender Oktavbass, Snare mit Hall (100 BPM, C–G–Am–F)."""
    m = Mix(100)
    prog = ["C", "G", "Am", "F"]
    for bar in range(m.bars()):
        c = prog[bar % 4]; root, notes = chord_midi(c)
        arp = [notes[0], notes[1], notes[2], notes[1] + 12, notes[2], notes[1], notes[0] + 12, notes[2]] * 2
        for k, n in enumerate(arp):
            m.add("arp", lead_saw(hz(n), m.beat / 4 * 0.9, 0.6, 2800 + 1200 * (k % 4 == 0)), m.t(bar, k * 0.25), pan=0.2 * (-1) ** k)
        m.add("pad", pad([hz(n - 12) for n in notes], 4 * m.beat + 0.3, 1.0, 1600, 0.2), m.t(bar, 0))
        for k in range(8):
            m.add("bass", bass_pluck(hz(root - 24 + (12 if k % 2 else 0)), m.beat / 2 * 0.9, 0.9, 1200), m.t(bar, k * 0.5))
        for b in (0, 2):
            m.add("kick", kick(0.95), m.t(bar, b))
        for b in (1, 3):
            m.add("snare", snare(0.9, 0.35), m.t(bar, b))
        for b in np.arange(0, 4, 0.5):
            m.add("hat", hat(0.5), m.t(bar, b), pan=0.35)
        if bar >= 2:
            lead = {"C": 79, "G": 74, "Am": 76, "F": 72}[c]
            m.add("lead", lead_saw(hz(lead), 3.6 * m.beat, 0.6, 4000), m.t(bar, 0), pan=-0.1)
    return m.render({"arp": .32, "pad": .3, "bass": .55, "kick": .85, "snare": .45, "hat": .22, "lead": .25}, reverb=0.3,
                    sends={"snare": 0.9, "lead": 0.5, "arp": 0.3})


def t06_funk():
    """Funk/Disco: Slap-Bass, Clavinet, Bläser-Stabs, Four-on-the-Floor (115 BPM, Dm7–G7)."""
    m = Mix(115)
    prog = [("D", [62, 65, 69, 72]), ("D", [62, 65, 69, 72]), ("G", [67, 71, 74, 77]), ("G", [67, 71, 74, 77])]
    bl = [(0, 0), (0.75, 12), (1.5, 0), (2, 3), (2.5, 5), (3, 7), (3.5, 10), (3.75, 12)]
    for bar in range(m.bars()):
        name, v = prog[bar % 4]; root = v[0] - 24
        for b, iv in bl:
            m.add("bass", slap(hz(root + iv), 0.22, 0.9), m.t(bar, b))
        for b in (0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75):
            if RNG.random() > 0.25:
                m.add("clav", sum(clav(hz(n)) for n in v[1:]) / 2, m.t(bar, b), pan=0.3)
        for b in range(4):
            m.add("kick", kick(0.9), m.t(bar, b))
            m.add("hat", hat(0.7, open_=True), m.t(bar, b + 0.5), pan=-0.3)
        for b in (1, 3):
            m.add("snare", snare(0.85), m.t(bar, b))
        if bar % 2 == 1:
            m.add("stab", stab([hz(n + 12) for n in v], 0.3, 0.9), m.t(bar, 3.5), pan=-0.1)
            m.add("stab", stab([hz(n + 12) for n in v], 0.2, 0.8), m.t(bar, 3.0), pan=-0.1)
    return m.render({"bass": .6, "clav": .35, "kick": .8, "hat": .25, "snare": .5, "stab": .4}, reverb=0.12)


def t07_pixel():
    """Chiptune / 8-Bit: fröhliche Rechteck-Melodie, Dreieck-Bass, Rausch-Schlagzeug (140 BPM, C–F–G–C)."""
    m = Mix(140)
    prog = ["C", "F", "G", "C"]
    mel = [[72, 76, 79, 76, 84, 79, 76, 79], [77, 81, 84, 81, 77, 76, 74, 72], [74, 79, 83, 79, 86, 83, 79, 83], [84, 79, 76, 72, 76, 79, 84, 0]]
    for bar in range(m.bars()):
        c = prog[bar % 4]; root, notes = chord_midi(c)
        for k in range(16):
            n = notes[k % 3] + 12
            m.add("arp", chip(hz(n), m.beat / 4 * 0.8, 0.35, 0.125), m.t(bar, k * 0.25), pan=0.25)
        for k in range(8):
            m.add("bass", tri(hz(root - 24 + (7 if k % 2 else 0)), m.beat / 2 * 0.85, 0.9), m.t(bar, k * 0.5))
        if bar >= 1:
            for k, n in enumerate(mel[bar % 4]):
                if n:
                    m.add("lead", chip(hz(n), m.beat / 2 * 0.9, 0.6, 0.5), m.t(bar, k * 0.5), pan=-0.15)
        for b in (0, 2):
            m.add("kick", kick(0.8, tone=1.3, dur=0.2), m.t(bar, b))
        for b in (1, 3):
            m.add("snare", noise_hit(0.9, 0.12), m.t(bar, b))
        for b in np.arange(0, 4, 0.5):
            m.add("hat", noise_hit(0.25, 0.03), m.t(bar, b))
    return m.render({"arp": .3, "bass": .5, "lead": .4, "kick": .7, "snare": .45, "hat": .4}, reverb=0.08, master_lp=9000)


def t08_weite():
    """Filmisch-hoffnungsvoll: Klavier, grosse Streicherfläche, Trommeln, Glockenspiel (90 BPM, C–G/H–Am–F)."""
    m = Mix(90)
    prog = [("C", 48), ("G", 47), ("Am", 45), ("F", 41)]
    for bar in range(m.bars()):
        c, bassn = prog[bar % 4]; root, notes = chord_midi(c)
        for b in range(4):
            for n in sorted(notes)[:3]:
                m.add("piano", piano(hz(n + (12 if b % 2 else 0)), 1.6, 0.45), m.t(bar, b) + 0.004 * b, pan=0.1)
        m.add("piano", piano(hz(bassn), 2.5, 0.8), m.t(bar, 0))
        m.add("pad", pad([hz(n - 12) for n in notes] + [hz(bassn)], 4 * m.beat + 0.6, 1.0, 2200, 0.6), m.t(bar, 0))
        if bar >= 1:
            for b in (0, 1.5, 2, 3, 3.5):
                m.add("drums", tom(85 if b < 2 else 110, 0.9), m.t(bar, b))
        if bar >= 2:
            g = {"C": [79, 76], "G": [79, 74], "Am": [76, 72], "F": [77, 81]}[c]
            m.add("glock", bell(hz(g[0] + 12), 1.4, 0.6), m.t(bar, 0), pan=-0.2)
            m.add("glock", bell(hz(g[1] + 12), 1.4, 0.5), m.t(bar, 2), pan=-0.2)
    m.add("drums", swell(1.4, 1.0), DUR - 1.9)
    return m.render({"piano": .5, "pad": .45, "drums": .55, "glock": .3}, reverb=0.35, sends={"piano": .5, "glock": .6, "drums": .3})


def t09_future():
    """Future Bass: Supersaw-Akkorde mit Pump-Effekt, Trap-Hi-Hats, Glocken-«Vocal-Chop» (150 BPM halbiert)."""
    m = Mix(150)
    prog = [("F", [65, 69, 72, 76]), ("G", [67, 71, 74, 79]), ("E", [64, 67, 71, 74]), ("A", [69, 72, 76, 79])]
    hits = [0, 0.75, 1.5, 2.5, 3, 3.5]
    kicks = []
    for bar in range(m.bars()):
        name, v = prog[bar % 4]
        for b in hits:
            m.add("chords", supersaw([hz(n) for n in v] + [hz(v[0] - 12)], m.beat * 0.7, 0.9), m.t(bar, b))
        m.add("bass", bass_sub(hz(v[0] - 24), 4 * m.beat * 0.95, 0.9), m.t(bar, 0))
        for b in (0, 2.5):
            m.add("kick", kick(1.0), m.t(bar, b)); kicks.append(m.t(bar, b))
        m.add("snare", clap(1.0), m.t(bar, 2)); m.add("snare", snare(0.6), m.t(bar, 2))
        hs = list(np.arange(0, 4, 0.5)) + ([3.25, 3.375, 3.625, 3.75, 3.875] if bar % 2 else [])
        for b in hs:
            m.add("hat", hat(0.55), m.t(bar, b), pan=0.3)
        if bar >= 1:
            chop = [v[3] + 12, v[2] + 12, v[3] + 12, v[1] + 12 + 12]
            for b, n in zip((0.5, 1, 1.75, 3), chop):
                m.add("chop", bell(hz(n), 0.6, 0.7) * np.exp(-tt(0.6) * 3), m.t(bar, b), pan=-0.2)
    duck = {"busse": ["chords", "bass"], "env": m.duck_env(kicks, 0.75, 0.2)}
    return m.render({"chords": .4, "bass": .5, "kick": .85, "snare": .5, "hat": .25, "chop": .35}, reverb=0.22, duck=duck)


def t10_akustik():
    """Akustik-Folk-Pop: gezupfte Gitarre, Stampfen und Klatschen, Shaker, Glockenspiel (96 BPM, G–D–Em–C)."""
    m = Mix(96)
    prog = [("G", [43, 47, 50, 55, 59, 67]), ("D", [50, 57, 62, 66, 69, 74]), ("E", [40, 47, 52, 55, 59, 64]), ("C", [48, 52, 55, 60, 64, 67])]
    pick = [0, 3, 2, 4, 1, 5, 3, 4]
    for bar in range(m.bars()):
        name, v = prog[bar % 4]
        for k, s in enumerate(pick):
            m.add("guitar", pluck(hz(v[s]), 1.4, 0.75, 0.5, 0.997), m.t(bar, k * 0.5), pan=0.2)
        for b in (0, 2):
            m.add("stomp", kick(0.9, tone=0.6, dur=0.3), m.t(bar, b))
        if bar >= 1:
            for b in (1, 3):
                m.add("clap", clap(1.0), m.t(bar, b))
        for b in np.arange(0, 4, 0.5):
            m.add("shaker", shaker(0.9 if b % 1 else 0.5), m.t(bar, b), pan=-0.35)
        m.add("bass", bass_sub(hz(v[0] - 12 if v[0] > 45 else v[0]), 2 * m.beat * 0.9, 0.8), m.t(bar, 0))
        if bar >= 2:
            g = {"G": [79, 83, 86], "D": [78, 81, 86], "E": [79, 83, 88], "C": [76, 79, 84]}[name]
            for b, n in zip((0, 1, 2.5), g):
                m.add("glock", bell(hz(n), 1.2, 0.5), m.t(bar, b), pan=-0.15)
    return m.render({"guitar": .6, "stomp": .75, "clap": .45, "shaker": .4, "bass": .45, "glock": .25}, reverb=0.16)


STUECKE = [
    ("01_sonnenschein_ukulele_pop", t01_sonnenschein),
    ("02_lofi_morgen", t02_lofi),
    ("03_inspiration_klavier", t03_inspiration),
    ("04_tropical_house", t04_tropisch),
    ("05_neon_synthwave", t05_neon),
    ("06_funk_disco", t06_funk),
    ("07_pixel_chiptune", t07_pixel),
    ("08_weite_filmisch", t08_weite),
    ("09_future_bass", t09_future),
    ("10_akustik_folk", t10_akustik),
]


def main(outdir, auswahl=None):
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    for k, (name, fn) in enumerate(STUECKE, 1):
        if auswahl and k not in auswahl:
            continue
        x = fn()
        wav = out / f"{name}.wav"
        wavfile.write(wav, SR, (x * 32767).astype(np.int16))
        mp3 = out / f"{name}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
        print(name, "peak", round(float(np.max(np.abs(x))), 2), "rms_db", round(20 * np.log10(np.sqrt(np.mean(x ** 2))), 1))


# Freigegebene Stile (Timo, 13.11.2026) und passende Themenbereiche
FREIGEGEBEN = {
    2: ("Lo-Fi, entspannt", ["Tiere", "Gesellschaft & Alltag"]),
    3: ("Klavier, inspirierend", ["Gesundheit & Medizin", "Gesellschaft & Alltag"]),
    5: ("Synthwave, energisch", ["Technik & Erfindungen", "Wissenschaft & Weltraum"]),
    8: ("Filmisch, hoffnungsvoll", ["Natur & Umwelt", "Wissenschaft & Weltraum", "Tiere"]),
}


def variante(nr, wav, seed):
    """Ein freigegebenes Stück als Variante: Tonart ±2 Halbtöne, Tempo ±5 %, andere Zufallsdetails."""
    global TRANSPOSE, TEMPO, RNG
    r = np.random.default_rng(seed)
    TRANSPOSE, TEMPO = int(r.integers(-2, 3)), float(r.uniform(0.95, 1.05))
    RNG = np.random.default_rng(seed)
    x = STUECKE[nr - 1][1]()
    wavfile.write(wav, SR, (x * 32767).astype(np.int16))
    return {"stil": nr, "name": STUECKE[nr - 1][0], "transpose": TRANSPOSE, "tempo": round(TEMPO, 3), "seed": seed}


def waehle(bereich, letzter=None, seed=0):
    """Stil passend zum Themenbereich; nicht zweimal hintereinander derselbe."""
    passend = [n for n, (_, b) in FREIGEGEBEN.items() if bereich in b] or list(FREIGEGEBEN)
    if letzter in passend and len(passend) > 1:
        passend.remove(letzter)
    return passend[seed % len(passend)]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--tag":  # python3 musikbox.py --tag "<Bereich>" <letzter_stil|0> <seed> out.wav
        bereich, letzter, seed, wav = a[1], int(a[2]) or None, int(a[3]), a[4]
        info = variante(waehle(bereich, letzter, seed), wav, seed)
        import json; print(json.dumps(info))
    else:
        main(a[0], [int(x) for x in a[1:]] or None)
