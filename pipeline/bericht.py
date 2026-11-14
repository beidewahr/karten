"""Beide wahr – Tagesreport als HTML-Seite (seit 14.11.2026, Wunsch Timo).

Aufruf: python3 bericht.py pair.json out/ bericht.json bericht.html

- pair.json  : Tagespaar (wie für render.py)
- out/       : Ordner mit dm_gut.png, dm_schlecht.png, story.png, reel.mp4
- bericht.json: Angaben zum Lauf (siehe BEISPIEL unten)
Ergebnis: bericht.html (nur Seiteninhalt, ohne <html>/<head>; wird mit dem
Artifact-Werkzeug als Seite «Beide wahr Tagesreport» veröffentlicht).
Bilder werden verkleinert als data:-URI eingebettet (externe Hosts sind gesperrt).

BEISPIEL bericht.json:
{
 "status": "eingeplant",               # oder "abgebrochen"
 "bereich": "Gesundheit & Medizin",
 "zeiten": {"reel": "07:30", "story": "07:32"},
 "metricool": {"reel": 427755822, "story": 427755829},
 "statistik": "2 Personen, 100 % gut – unter 30, darum nicht angezeigt",
 "musik": "03 Klavier, +2 Halbtöne, Tempo 0,967",
 "quellen": [{"fuer": "gut", "titel": "WHO-Medienmitteilung 12.11.2026", "url": "https://…"}],
 "kommentare": {"reel_0.5": "…", "reel_4": "…", "reel_7": "…", "reel_11": "…",
                "story": "…", "dm_gut": "…", "dm_schlecht": "…"},
 "bewertung": {"reel_0.5": "ok"},       # ok | hinweis | problem (optional, Standard ok)
 "bildunterschrift": "…",
 "reflexion": ["…"], "probleme": ["…"], "notizen": ["…"]
}
"""
import sys, json, base64, html, subprocess, tempfile, pathlib
from PIL import Image
import io

FRAMES = [("reel_0.5", 0.5, "Reel · 0,5 s", "Einstieg"),
          ("reel_4", 4, "Reel · 4 s", "Gute Nachricht"),
          ("reel_7", 7, "Reel · 7 s", "Beide Nachrichten"),
          ("reel_11", 11, "Reel · 11 s", "Schluss / Aufruf")]
STATUS_TXT = {"ok": "OK", "hinweis": "Hinweis", "problem": "Problem"}


def e(s):
    return html.escape(str(s or ""))


def thumb(path, width=360):
    im = Image.open(path).convert("RGB")
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def frame(video, t, tmp):
    p = pathlib.Path(tmp) / f"f_{t}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(video),
                    "-frames:v", "1", str(p)], check=True)
    return p


def main(pair_p, out_d, ber_p, html_p):
    p = json.load(open(pair_p))
    b = json.load(open(ber_p))
    out = pathlib.Path(out_d)
    kom, bew = b.get("kommentare", {}), b.get("bewertung", {})
    g, s = p["gut"], p["schlecht"]
    abgebrochen = b.get("status") == "abgebrochen"

    rows = []
    if not abgebrochen:
        with tempfile.TemporaryDirectory() as tmp:
            inhalt = {
                "reel_0.5": e(f"Titel «{p.get('hook', p['thema']).replace(chr(173), '')}» · «Eine gute und eine schlechte Nachricht»"),
                "reel_4": f"☀ {e(g['headline'])}",
                "reel_7": f"☀ {e(g['headline'])}<br>🌧 {e(s['headline'])}",
                "reel_11": "«Gut oder Schlecht? Kommentiere WAHL»" + (f"<br>{e(p['gestern'])}" if p.get("gestern") else ""),
            }
            for key, t, titel, art in FRAMES:
                rows.append((key, titel, art, thumb(frame(out / "reel.mp4", t, tmp)), inhalt[key], "hoch"))
        rows.append(("story", "Story", f"{b.get('zeiten', {}).get('story', '')} Uhr",
                     thumb(out / "story.png"),
                     f"☀ {e(g['headline'])} → «Antworte: GUT»<br>🌧 {e(s['headline'])} → «Antworte: SCHLECHT»", "hoch"))
        for k, n, sym in (("gut", g, "☀"), ("schlecht", s, "🌧")):
            rows.append((f"dm_{k}", f"DM-Karte {k}", f"{len(n['text'])} Zeichen", thumb(out / f"dm_{k}.png"),
                         f"<b>{sym} {e(n['headline'])}</b><br>{e(n['text'])}<br><span class='q'>Quelle: {e(n['quelle'])} · Bild: {e(n.get('bild_quelle', ''))}</span>",
                         "karte"))

    def row_html(r):
        key, titel, art, img, inh, form = r
        st = bew.get(key, "ok")
        return f"""<tr class="st-{st}">
  <td class="el"><span class="pill {st}">{STATUS_TXT.get(st, st)}</span><strong>{e(titel)}</strong><span class="sub">{e(art)}</span></td>
  <td class="img"><img class="{form}" src="{img}" alt="{e(titel)}"></td>
  <td class="inh">{inh}</td>
  <td class="kom">{e(kom.get(key, ''))}</td>
</tr>"""

    z = b.get("zeiten", {})
    mc = b.get("metricool", {})
    status_lbl = "Abgebrochen – nichts gepostet" if abgebrochen else "Eingeplant in Metricool"
    eck = [("Datum", p.get("datum", "")), ("Status", status_lbl), ("Bereich", b.get("bereich", "")),
           ("Thema", p.get("thema", ""))]
    if not abgebrochen:
        eck += [("Reel", f"{z.get('reel', '')} Uhr" + (f" · Metricool #{mc['reel']}" if mc.get("reel") else "")),
                ("Story", f"{z.get('story', '')} Uhr" + (f" · Metricool #{mc['story']}" if mc.get("story") else "")),
                ("Gut", g["headline"]), ("Schlecht", s["headline"])]
    eck += [("Statistik gestern", b.get("statistik", "–")), ("Musik", b.get("musik", "–"))]
    eck_html = "\n".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in eck)

    def liste(xs):
        return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in xs) + "</ul>" if xs else "<p class='leer'>Keine.</p>"

    quellen = "<ul>" + "".join(
        f"<li><span class='tag {e(q.get('fuer', ''))}'>{e(q.get('fuer', ''))}</span> <a href=\"{e(q['url'])}\" target=\"_blank\" rel=\"noopener\">{e(q['titel'])}</a></li>"
        for q in b.get("quellen", [])) + "</ul>"

    tabelle = "" if abgebrochen else f"""
<section>
<h2>Vorschau &amp; Prüfung</h2>
<div class="scroll"><table class="vor">
<thead><tr><th>Element</th><th>Vorschau</th><th>Inhalt</th><th>Kommentar</th></tr></thead>
<tbody>
{chr(10).join(row_html(r) for r in rows)}
</tbody></table></div>
</section>"""

    cap = f"""<section><h2>Bildunterschrift Reel</h2><pre class="cap">{e(b['bildunterschrift'])}</pre></section>""" if b.get("bildunterschrift") else ""

    doc = f"""<title>Beide wahr Tagesreport</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
<style>
/* Layout: ein Bericht pro Tag – Eckdaten oben, Prüftabelle mit Bildern, darunter Reflexion & Quellen */
:root {{
  --bg: #f4f2ee; --panel: #ffffff; --fg: #15171e; --muted: #5d6170; --line: #dedbd3;
  --sun: #e9a52b; --rain: #3c4a63; --accent: #2f8f83;
  --ok: #2f8f5b; --ok-bg: #e2f2e8; --warn: #a86b00; --warn-bg: #fbefd5; --bad: #b3382c; --bad-bg: #f8e1de;
  --sans: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #121419; --panel: #1b1e25; --fg: #ecebe7; --muted: #a1a5b2; --line: #2e323c;
  --sun: #f0b445; --rain: #9fb1d1; --accent: #5cc0b2;
  --ok: #6fd39a; --ok-bg: #173325; --warn: #f0b445; --warn-bg: #3a2c10; --bad: #f08a7e; --bad-bg: #3d1c19; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #121419; --panel: #1b1e25; --fg: #ecebe7; --muted: #a1a5b2; --line: #2e323c;
  --sun: #f0b445; --rain: #9fb1d1; --accent: #5cc0b2;
  --ok: #6fd39a; --ok-bg: #173325; --warn: #f0b445; --warn-bg: #3a2c10; --bad: #f08a7e; --bad-bg: #3d1c19; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--sans); font-size: 15px; line-height: 1.5; }}
.wrap {{ max-width: 1120px; margin: 0 auto; padding-block: 28px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 28px; }}
header h1 {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; margin: 0; text-wrap: balance; }}
header p {{ margin: 4px 0 0; color: var(--muted); }}
h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin: 0 0 10px; font-weight: 700; }}
section {{ min-width: 0; }}
table {{ border-collapse: collapse; width: 100%; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
th, td {{ text-align: left; vertical-align: top; padding: 10px 14px; border-bottom: 1px solid var(--line); }}
tr:last-child > * {{ border-bottom: 0; }}
.eck th {{ width: 170px; color: var(--muted); font-weight: 600; }}
.eck td {{ font-variant-numeric: tabular-nums; }}
.scroll {{ overflow-x: auto; }}
.vor {{ min-width: 760px; }}
.vor thead th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); background: var(--bg); }}
.vor td.el {{ width: 150px; }}
.vor td.el strong {{ display: block; margin-top: 6px; }}
.vor td.el .sub {{ display: block; color: var(--muted); font-size: 13px; }}
.vor td.img {{ width: 190px; }}
.vor img {{ display: block; border-radius: 8px; border: 1px solid var(--line); }}
.vor img.hoch {{ width: 160px; }}
.vor img.karte {{ width: 180px; }}
.vor td.inh {{ width: 34%; }}
.vor td.kom {{ color: var(--fg); }}
.q {{ color: var(--muted); font-size: 13px; }}
.pill {{ display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; padding: 2px 8px; border-radius: 999px; }}
.pill.ok {{ color: var(--ok); background: var(--ok-bg); }}
.pill.hinweis {{ color: var(--warn); background: var(--warn-bg); }}
.pill.problem {{ color: var(--bad); background: var(--bad-bg); }}
.st-hinweis td.el {{ box-shadow: inset 3px 0 0 var(--warn); }}
.st-problem td.el {{ box-shadow: inset 3px 0 0 var(--bad); }}
.cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 28px; }}
.box {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px; }}
.box ul {{ margin: 0; padding-left: 18px; display: grid; gap: 6px; }}
.leer {{ margin: 0; color: var(--muted); }}
a {{ color: var(--accent); }}
.tag {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; padding: 1px 6px; border-radius: 4px; background: var(--bg); }}
.tag.gut {{ color: var(--sun); }} .tag.schlecht {{ color: var(--rain); }}
pre.cap {{ margin: 0; white-space: pre-wrap; font-family: var(--sans); background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px; }}
@media (max-width: 640px) {{
  .eck th {{ width: 110px; }}
}}
</style>
<div class="wrap">
<header><h1>Beide wahr · Tagesreport {e(p.get('datum', ''))}</h1>
<p>{e(p.get('thema', ''))} · {e(b.get('bereich', ''))}</p></header>
<section><h2>Eckdaten</h2><table class="eck"><tbody>{eck_html}</tbody></table></section>
{tabelle}
<div class="cols">
<section><h2>Reflexion</h2><div class="box">{liste(b.get('reflexion', []))}</div></section>
<section><h2>Probleme</h2><div class="box">{liste(b.get('probleme', []))}</div></section>
</div>
<div class="cols">
<section><h2>Quellen</h2><div class="box">{quellen}</div></section>
<section><h2>Notizen</h2><div class="box">{liste(b.get('notizen', []))}</div></section>
</div>
{cap}
</div>
"""
    pathlib.Path(html_p).write_text(doc)
    print("ok", html_p, len(doc) // 1024, "KB")


if __name__ == "__main__":
    main(*sys.argv[1:5])
