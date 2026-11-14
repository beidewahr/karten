"""Beide wahr – baut den Musikkatalog (katalog.json) aus Gesangs- und Merkmalsanalyse.

Pro Titel wird die beste Stelle für das 12,8-s-Reel gesucht:
- KEIN Gesang im ganzen Abschnitt (Stimmtrennung MDX-Net, 0,5-s-Raster, mit 1 s Sicherheitsrand)
- nicht am Anfang des Titels (Intro), sondern dort, wo der Titel «voll» läuft; nicht im Ausklang
- gleichmässige Lautheit (kein Abbruch/Break mitten im Reel)
- Beginn auf einem Takt-Einsatz (Beat-Tracking)
Aufruf: python3 katalog.py <musik-ordner> ana/ katalog.json
"""
import json, subprocess, sys, pathlib, warnings
import numpy as np, librosa

warnings.filterwarnings("ignore")
DAUER, RASTER = 12.8, 0.5
GESANG_REL, GESANG_ABS = -16.0, -40.0  # kalibriert an «Smile» vs. «Smile (Instrumental)»


def gesang_maske(d):
    rel = d["vocal_db"] - d["mix_db"]
    g = (rel > GESANG_REL) & (d["vocal_db"] > GESANG_ABS)
    # 1 s Sicherheitsrand um jeden Gesangsteil (Atmer, Einsätze)
    rand = np.convolve(g.astype(int), np.ones(5, int), "same") > 0
    return g, rand


def beats(pfad):
    y = np.frombuffer(subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(pfad), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    _, bt = librosa.beat.beat_track(y=y, sr=22050, units="time")
    return np.asarray(bt)


def beste_stelle(d, dauer_titel, bt):
    g, gr = gesang_maske(d)
    mix = d["mix_db"]
    n = int(round(DAUER / RASTER))
    voll = np.percentile(mix, 70)  # Lautheit, wenn der Titel «voll» läuft
    # Intro: erst ab dem Punkt, an dem der Titel erstmals 2 s lang nahe an «voll» ist, frühestens ab 6 s
    nah = np.convolve((mix > voll - 4).astype(int), np.ones(4, int), "valid") == 4
    intro_ende = max(6.0, (np.argmax(nah) * RASTER) if nah.any() else 6.0)
    kand = []
    for k in range(len(mix) - n):
        t0 = k * RASTER
        if t0 < intro_ende or t0 + DAUER > dauer_titel - 8:
            continue
        if gr[k:k + n].any():
            continue
        seg = mix[k:k + n]
        s = -abs(seg.mean() - voll) * 1.0 - seg.std() * 1.5 - 3.0 * max(0, voll - 8 - seg.min())
        kand.append((s, t0))
    if not kand:
        return None
    s, t0 = max(kand)
    # auf den nächsten Beat (bevorzugt Taktanfang: jeder 4. Beat) einrasten, max. ±1 s, Gesang erneut prüfen
    if len(bt):
        nahe = bt[(bt > t0 - 1) & (bt < t0 + 1)]
        if len(nahe):
            t0 = float(nahe[np.argmin(abs(nahe - t0))])
    k = int(round(t0 / RASTER))
    if gr[max(0, k):k + n].any():
        t0 = kand and max(kand)[1]
    return dict(start=round(t0, 2), guete=round(float(s), 1))


def stimmung(m):
    """Grobe Einordnung aus Merkmalen -> passende Themenbereiche."""
    t, hell, en, rh, dur = m["tempo"], m["hell"], m["energie"], m["rhythmus"], m["tonart"].endswith("Dur")
    if en < -15.5 and rh < 1.4:
        st = "ruhig"
    elif hell < 1500 and rh < 1.45:
        st = "filmisch"
    elif rh > 1.75 or (t >= 125 and en > -13):
        st = "energisch"
    else:
        st = "inspirierend"
    return st


BEREICHE = {
    "ruhig": ["Gesundheit & Medizin", "Natur & Umwelt", "Gesellschaft & Alltag"],
    "inspirierend": ["Natur & Umwelt", "Tiere", "Gesellschaft & Alltag", "Gesundheit & Medizin"],
    "filmisch": ["Wissenschaft & Weltraum", "Natur & Umwelt", "Tiere"],
    "energisch": ["Technik & Erfindungen", "Wissenschaft & Weltraum", "Gesellschaft & Alltag"],
}


def main(ordner, ana, out):
    ordner, ana = pathlib.Path(ordner), pathlib.Path(ana)
    merk = json.load(open(ana / "merkmale.json"))
    kat = {}
    for npz in sorted(ana.glob("*.npz")):
        name = npz.stem
        pfad = ordner / f"{name}.mp4"
        if not pfad.exists() or name not in merk:
            continue
        d = np.load(npz)
        m = merk[name]
        g, _ = gesang_maske(d)
        st = beste_stelle(d, m["dauer"], beats(pfad))
        e = dict(datei=pfad.name, gesang=round(float(g.mean()), 2), **{k: m[k] for k in ("dauer", "tempo", "tonart", "hell", "energie", "rhythmus")})
        e["stimmung"] = stimmung(m)
        e["bereiche"] = BEREICHE[e["stimmung"]]
        if st:
            e.update(st)
        else:
            e["ungeeignet"] = "keine 12,8 s ohne Gesang nach dem Intro"
        kat[name] = e
        print(name, e, flush=True)
    json.dump(kat, open(out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
