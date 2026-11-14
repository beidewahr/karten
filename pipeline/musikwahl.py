"""Beide wahr – Musik fürs Reel aus der Meta Sound Collection (seit 14.11.2026).

Lizenz (Meta Sound Collection): Nutzung nur in Inhalten auf Facebook/Instagram, nicht separat verbreiten.
Darum liegen die Titel und katalog.json im PRIVATEN Repo beidewahr/musik; das fertige Reel kommt nur kurz
ins Repo beidewahr/medien (danach geleert).

katalog.json (erzeugt mit katalog.py + stimme.py, Stimmtrennung MDX-Net) enthält pro geeignetem Titel die
beste Stelle: KEIN Gesang (1 s Sicherheitsrand), nicht im Intro, nicht im Ausklang, gleichmässige Lautheit,
Einstieg auf einem Beat. Titel ohne solche Stelle haben «ungeeignet».

Aufruf:
  python3 musikwahl.py <musik-repo> --bereich "<Bereich>" --nicht "Titel A,Titel B" out.wav
      -> wählt einen passenden Titel (nicht in --nicht = zuletzt gespielte), schneidet 12,8 s, gibt JSON aus
  python3 musikwahl.py <musik-repo> --titel "<Titel>" out.wav       -> bestimmten Titel schneiden
"""
import json, random, subprocess, sys, tempfile, pathlib
import numpy as np
from scipy.io import wavfile

SR, DAUER = 44100, 12.8


def lade(pfad, start, dauer):
    tmp = pathlib.Path(tempfile.mkdtemp()) / "x.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dauer:.2f}", "-i", str(pfad),
                    "-ac", "2", "-ar", str(SR), str(tmp)], check=True)
    _, x = wavfile.read(tmp)
    return x.astype(float) / 32768.0


def schneide(pfad, start, out, dauer=DAUER):
    seg = lade(pfad, start, dauer)
    n = int(dauer * SR)
    if len(seg) < n:
        seg = np.pad(seg, ((0, n - len(seg)), (0, 0)))
    seg = seg[:n]
    fi, fo = int(0.35 * SR), int(0.9 * SR)  # weicher Einstieg (Stelle liegt mitten im Titel), sanftes Ende für die Schleife
    seg[:fi] *= np.linspace(0, 1, fi)[:, None] ** 0.7
    seg[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    rms = np.sqrt(np.mean(seg ** 2))
    seg *= 10 ** (-16 / 20) / max(rms, 1e-9)
    pk = np.max(np.abs(seg))
    if pk > 0.95:
        seg *= 0.95 / pk
    wavfile.write(out, SR, (seg * 32767).astype(np.int16))


def waehle(kat, bereich, nicht=(), seed=None):
    ok = {n: e for n, e in kat.items() if "start" in e and n not in nicht}
    passend = [n for n, e in ok.items() if bereich in e["bereiche"]]
    pool = passend or list(ok)  # notfalls irgendein geeigneter Titel
    if not pool:
        return None
    return random.Random(seed).choice(sorted(pool))


def main(a):
    repo = pathlib.Path(a[0])
    out = a[-1]
    kat = json.load(open(repo / "katalog.json"))
    if "--titel" in a:
        titel = a[a.index("--titel") + 1]
    else:
        bereich = a[a.index("--bereich") + 1]
        nicht = [t for t in (a[a.index("--nicht") + 1].split(",") if "--nicht" in a else []) if t]
        titel = waehle(kat, bereich, nicht, seed="".join(a))
        if titel is None:
            print(json.dumps({"fehler": "kein geeigneter Titel"}))
            sys.exit(2)
    e = kat[titel]
    schneide(repo / e["datei"], e["start"], out)
    print(json.dumps({"titel": titel, "start": e["start"], "stimmung": e["stimmung"]}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
