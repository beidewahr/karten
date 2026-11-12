"""Beide wahr – Asset-Generator.

Erzeugt aus pair.json die Bilder für einen Tag:
reel_s1..s4.png (1080x1920), story.png (1080x1920, ein Bild ohne Sticker) und die Highlight-Cover.
DM-Karten kommen aus dm_karte.py (mit Symbolbild).
Symbolik: Sonne = gute Nachricht, Regenwolke = schlechte Nachricht (seit 11.11.2026).
Aufruf: python3 render.py pair.json out/
"""
import json, sys, html, pathlib
from playwright.sync_api import sync_playwright

DARK = "#15171E"
LIGHT = "#F3EEE4"
MUTED_D = "#8C909B"   # Sekundärtext auf Dunkel
MUTED_L = "#6E685D"   # Sekundärtext auf Hell

SUN = """<svg viewBox="0 0 100 100" width="{s}" height="{s}"><g fill="{c}">
<circle cx="50" cy="50" r="19"/>{rays}</g></svg>"""


def sun(size, color):
    rays = "".join(
        f'<rect x="47" y="6" width="6" height="16" rx="3" transform="rotate({a} 50 50)"/>'
        for a in range(0, 360, 45))
    return SUN.format(s=size, c=color, rays=rays)


def rain(size, color):
    """Regenwolke – Symbol für die schlechte Nachricht (ersetzt den Halbmond)."""
    drops = "".join(
        f'<line x1="{x}" y1="74" x2="{x - 5}" y2="90" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
        for x in (34, 52, 70))
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><g fill="{color}">'
            f'<circle cx="34" cy="46" r="15"/><circle cx="55" cy="36" r="20"/><circle cx="74" cy="49" r="13"/>'
            f'<rect x="19" y="44" width="68" height="18" rx="9"/></g>{drops}</svg>')


BASE_CSS = f"""
@page {{ margin:0 }}
html,body {{ margin:0; padding:0; }}
* {{ box-sizing:border-box; }}
body {{ font-family:'Inter'; -webkit-font-smoothing:antialiased; }}
.canvas {{ position:relative; overflow:hidden; }}
.disp {{ font-family:'Inter Display'; font-weight:800; }}
.label {{ font-family:'Inter'; font-weight:700; letter-spacing:.18em; text-transform:uppercase; }}
.abs {{ position:absolute; inset:0; }}
.vsplit {{ display:flex; }} .vsplit div {{ flex:1; }}
.d {{ background:{DARK}; }} .l {{ background:{LIGHT}; }}
"""


def page(w, h, body, extra_css=""):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}{extra_css}
.canvas{{width:{w}px;height:{h}px}}</style></head><body><div class="canvas">{body}</div></body></html>"""


ACCENT = "#4A9A94"   # nur für das Schlüsselwort WAHL (Petrol)

# Regel: Ein Buchstabe ist nie zweifarbig. Jede Zeile (.ml) wird so verschoben,
# dass die Mittellinie zwischen zwei Zeichen liegt; dann wird jeder Buchstabe
# nach seiner Seite eingefärbt (links hell -> dunkle Schrift, rechts dunkel -> helle Schrift).
MIRROR_JS = """
(() => {
  const C = 540, DARKC = '%s', LIGHTC = '%s';
  document.querySelectorAll('.ml').forEach(el => {
    const text = el.textContent; el.textContent = '';
    const sp = [...text].map(ch => { const s = document.createElement('span'); s.textContent = ch; el.appendChild(s); return s; });
    let r = sp.map(s => s.getBoundingClientRect());
    const cross = sp.some((s, i) => s.textContent.trim() && r[i].left < C - 1 && r[i].right > C + 1);
    if (cross) {
      let best = null;
      for (let i = 0; i < sp.length - 1; i++) {
        const g = (r[i].right + r[i + 1].left) / 2, dx = C - g;
        if (best === null || Math.abs(dx) < Math.abs(best)) best = dx;
      }
      el.style.transform = 'translateX(' + best + 'px)';
      r = sp.map(s => s.getBoundingClientRect());
    }
    sp.forEach((s, i) => { s.style.color = ((r[i].left + r[i].right) / 2 < C) ? DARKC : LIGHTC; });
  });
})();
""" % (DARK, LIGHT)


def mirrored(inner, css_class):
    """Vertikal geteilter Hintergrund (links hell = gut, rechts dunkel = schlecht).
    Text in Zeilen mit Klasse .ml; Färbung pro Buchstabe via MIRROR_JS."""
    return f"""<div class="abs vsplit"><div class="l"></div><div class="d"></div></div>
<div class="abs {css_class}">{inner}</div>"""


def plus_minus(size, color, minus=False):
    t = max(8, size // 6)
    bars = f'<rect x="0" y="{(size-t)//2}" width="{size}" height="{t}" rx="{t//2}"/>'
    if not minus:
        bars += f'<rect x="{(size-t)//2}" y="0" width="{t}" height="{size}" rx="{t//2}"/>'
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"><g fill="{color}">{bars}</g></svg>'


def image_slot(src, kind, size, pos="50% 50%", base_dir=pathlib.Path(".")):
    """Kleines Symbolbild. Ohne Bild: neutraler Platzhalter."""
    good = kind == "gut"
    if src:
        import base64
        uri = "data:image/jpeg;base64," + base64.b64encode((base_dir / src).read_bytes()).decode()
        inner = f'<img src="{uri}" style="width:100%;height:100%;object-fit:cover;object-position:{pos}">'
    else:
        g = "linear-gradient(135deg,#d9d1c2,#b9c4b0)" if good else "linear-gradient(135deg,#2c3140,#4a4f5c)"
        ic = sun(size // 3, DARK) if good else rain(size // 3, LIGHT)
        inner = f'<div style="width:100%;height:100%;background:{g};display:flex;align-items:center;justify-content:center">{ic}</div>'
    return f"""<div style="position:relative;width:{size}px;height:{size}px;border-radius:28px;overflow:hidden;flex:none">{inner}
</div>"""


def esc(t):
    # Gedankenstrich nie am Zeilenanfang: geschütztes Leerzeichen davor.
    return html.escape(t.replace(" – ", " – "))


# ---------- Reel ----------
def reel_hook():
    """Einstieg / Cover: Titel oben, gestaffelter Satz, + im Hellen, − im Dunkeln."""
    css = """.hook{font-family:'Inter Display';font-weight:800}
    .ttl{position:absolute;top:290px;left:0;right:0;text-align:center;font-size:66px;letter-spacing:-1.5px}
    .ln{position:absolute;font-size:104px;line-height:1;letter-spacing:-3.5px;white-space:nowrap}
    .r{right:575px}.c{left:0;right:0;text-align:center}.lft{left:575px}
    .sym{position:absolute;top:1290px;width:540px;display:flex;justify-content:center}"""
    inner = """<div class="ttl ml">Zwei wahre Nachrichten</div>
    <div class="ln r ml" style="top:620px">Eine gute</div>
    <div class="ln c ml" style="top:735px">und eine</div>
    <div class="ln lft ml" style="top:850px">schlechte</div>
    <div class="ln c ml" style="top:965px">Nachricht.</div>"""
    syms = f"""<div class="sym" style="left:0">{plus_minus(190, DARK)}</div>
    <div class="sym" style="left:540px">{plus_minus(190, LIGHT, minus=True)}</div>"""
    return page(1080, 1920, mirrored(inner, "hook") + syms, css)


def reel_headlines(p, show_bad=True, base_dir=pathlib.Path(".")):
    css = f"""
    .half{{position:absolute;left:0;right:0;height:960px;padding:0 150px 0 90px;
      display:flex;flex-direction:column;justify-content:center;gap:34px}}
    .top{{top:0;background:{LIGHT};color:{DARK}}}
    .bot{{top:960px;background:{DARK};color:{LIGHT}}}
    .head{{display:flex;align-items:center;gap:30px}}
    .row{{display:flex;align-items:center;gap:20px;font-size:32px}}
    .hl{{font-size:94px;line-height:1.02;letter-spacing:-2.5px}}
    .ghost{{opacity:0}}
    """
    g, s = p['gut'], p['schlecht']
    top = f"""<div class="half top"><div class="head">{image_slot(g.get('bild'), 'gut', 200, g.get('bild_pos', '50% 50%'), base_dir)}
    <div class="row label" style="color:{MUTED_L}">{sun(56, DARK)}Gute<br>Nachricht</div></div>
    <div class="hl disp">{esc(g['headline'])}</div></div>"""
    bot = f"""<div class="half bot"><div class="head {'' if show_bad else 'ghost'}">{image_slot(s.get('bild'), 'schlecht', 200, s.get('bild_pos', '50% 50%'), base_dir)}
    <div class="row label" style="color:{MUTED_D}">{rain(58, LIGHT)}Schlechte<br>Nachricht</div></div>
    <div class="hl disp {'' if show_bad else 'ghost'}">{esc(s['headline'])}</div></div>"""
    return page(1080, 1920, top + bot, css)


def two_tone_q(size, top):
    """Zweifarbiges Fragezeichen auf der Mittellinie – einzige Ausnahme von der Buchstaben-Regel."""
    base = (f"position:absolute;top:{top}px;left:0;right:0;text-align:center;font-family:'Inter Display';"
            f"font-weight:800;font-size:{size}px;line-height:1")
    return (f'<div style="{base};color:{DARK};clip-path:inset(0 50% 0 0)">?</div>'
            f'<div style="{base};color:{LIGHT};clip-path:inset(0 0 0 50%)">?</div>')


def gut_schlecht_frage(top):
    """«Gut» (hell, links) und «Schlecht» (dunkel, rechts) nebeneinander, grosses zweifarbiges ? darunter."""
    w = ("position:absolute;width:540px;text-align:center;font-family:'Inter Display';font-weight:800;"
         f"font-size:120px;line-height:1;letter-spacing:-4px;top:{top}px")
    return (f'<div style="{w};left:0;color:{DARK}">Gut</div>'
            f'<div style="{w};left:540px;color:{LIGHT}">Schlecht</div>' + two_tone_q(300, top + 140))


def reel_cta(accent=None, stat=""):
    accent = accent or ACCENT
    css = f"""
    .cta{{font-family:'Inter Display';font-weight:800}}
    .x{{position:absolute;left:0;right:0;text-align:center;white-space:nowrap}}
    .hl2{{position:absolute;width:540px;text-align:center;font-size:100px;letter-spacing:-4px;line-height:1}}
    .oder{{top:405px;font-size:64px;font-weight:600;letter-spacing:-1px}}
    .q{{top:690px;font-size:100px;letter-spacing:-3.5px}}
    .k{{top:760px;font-size:76px;letter-spacing:-1.5px}}
    .sub{{font-size:74px;letter-spacing:-1.5px;line-height:1}}
    .or{{font-size:48px;font-weight:600;letter-spacing:-.5px;line-height:1}}
    .handle{{top:1470px;font-family:Inter;font-size:42px;font-weight:600;letter-spacing:.04em}}
    .bub{{position:absolute;left:50%;transform:translateX(-50%);top:870px;background:{accent};color:{LIGHT};
      font-family:'Inter Display';font-weight:800;font-size:200px;letter-spacing:-6px;line-height:1;padding:30px 70px 44px;border-radius:70px}}
    .bub:after{{content:'';position:absolute;left:90px;bottom:-46px;border-width:50px 0 0 56px;border-style:solid;
      border-color:{accent} transparent transparent transparent}}
    """
    # Aufruf seit 11.11.2026: DM zuerst (kommt auch bei privaten Konten sicher an), Kommentar als Alternative.
    inner = """<div class="x k ml">Schreib uns</div>
    <div class="x sub ml" style="top:1230px">per DM</div>
    <div class="x or ml" style="top:1322px">oder kommentiere es.</div>
    <div class="x handle ml">@beidewahr</div>"""
    if stat:  # z. B. «Gestern wählten 67 % die gute Nachricht.» (nur ab 30 Stimmen)
        inner += f'<div class="x or ml" style="top:1545px;font-size:36px;font-weight:500">{esc(stat)}</div>'
    return page(1080, 1920, mirrored(inner, "cta") + gut_schlecht_frage(280) + '<div class="bub">WAHL</div>', css)


# ---------- Story ----------
def story_tag(p, base_dir=pathlib.Path(".")):
    """Tages-Story (seit 12.11.2026, ersetzt story_1/story_2): ein Bild, beide Schlagzeilen,
    Aufruf «Antworte mit GUT oder SCHLECHT». Ohne Sticker, damit sie per Metricool automatisch gepostet werden kann.
    Safe Zones: oben ~250 px (Profilzeile), unten ~260 px (Antwortfeld)."""
    css = f"""
    .half{{position:absolute;left:0;right:0;height:960px;padding:0 90px;
      display:flex;flex-direction:column;justify-content:center;gap:26px}}
    .top{{top:0;background:{LIGHT};color:{DARK};padding-top:190px}}
    .bot{{top:960px;background:{DARK};color:{LIGHT};padding-bottom:300px}}
    .head{{display:flex;align-items:center;gap:26px}}
    .row{{display:flex;align-items:center;gap:18px;font-size:28px}}
    .hl{{font-size:76px;line-height:1.03;letter-spacing:-2px}}
    .pill{{align-self:flex-start;font-family:'Inter Display';font-weight:800;font-size:46px;padding:16px 38px;
      border-radius:999px;border:4px solid}}
    .foot{{position:absolute;left:0;right:0;top:1630px;text-align:center;font-size:36px;font-weight:500;color:{LIGHT}}}
    """
    g, s = p['gut'], p['schlecht']
    top = f"""<div class="half top"><div class="head">{image_slot(g.get('bild'), 'gut', 150, g.get('bild_pos', '50% 50%'), base_dir)}
    <div class="row label" style="color:{MUTED_L}">{sun(48, DARK)}Gute<br>Nachricht</div></div>
    <div class="hl disp">{esc(g['headline'])}</div>
    <div class="pill" style="border-color:{DARK}">Antworte: GUT</div></div>"""
    bot = f"""<div class="half bot"><div class="head">{image_slot(s.get('bild'), 'schlecht', 150, s.get('bild_pos', '50% 50%'), base_dir)}
    <div class="row label" style="color:{MUTED_D}">{rain(50, LIGHT)}Schlechte<br>Nachricht</div></div>
    <div class="hl disp">{esc(s['headline'])}</div>
    <div class="pill" style="border-color:{LIGHT}">Antworte: SCHLECHT</div></div>"""
    stat = p.get('gestern', '')
    foot = (f'<div class="foot" style="top:1580px;color:{MUTED_D}">{esc(stat)}</div>' if stat else '') + \
        '<div class="foot">Die ganze Nachricht kommt per DM.</div>'
    return page(1080, 1920, top + bot + foot, css)


def story_1():
    css = """.s{display:flex;flex-direction:column;align-items:stretch;text-align:center;padding-top:300px}
    .t{font-size:118px;line-height:.98;letter-spacing:-4px;white-space:nowrap}
    .hint{margin-top:620px;font-size:40px;font-weight:600}"""
    inner = """<div class="disp t ml">Eine gute</div><div class="disp t ml">und eine</div>
    <div class="disp t ml">schlechte</div><div class="disp t ml">Nachricht.</div>
    <div class="hint ml">Welche wählst du?</div>"""
    return page(1080, 1920, mirrored(inner, "s"), css)


def story_2():
    css = f""".s{{display:flex;flex-direction:column;align-items:stretch;text-align:center;padding-top:560px}}
    .t{{font-size:104px;line-height:1;letter-spacing:-3px;white-space:nowrap}}
    .pill{{position:absolute;top:880px;font-family:'Inter Display';font-weight:800;font-size:64px;padding:26px 50px;border-radius:999px;border:5px solid}}
    .sub{{position:absolute;left:0;right:0;top:1100px;font-size:40px;font-weight:500;white-space:nowrap}}"""
    inner = f"""<div class="disp t ml">Antworte auf</div><div class="disp t ml">diese Story mit</div>
    <div class="pill" style="left:270px;transform:translateX(-50%);color:{DARK};border-color:{DARK}">GUT</div>
    <div class="pill" style="left:810px;transform:translateX(-50%);color:{LIGHT};border-color:{LIGHT}">SCHLECHT</div>
    <div class="sub ml">Deine Nachricht kommt per DM.</div>"""
    return page(1080, 1920, mirrored(inner, "s"), css)


# ---------- Highlight-Cover ----------
def highlight(kind):
    if kind == "gut":
        body = f'<div class="abs l"></div><div class="abs c">{sun(420, DARK)}</div>'
    elif kind == "schlecht":
        body = f'<div class="abs d"></div><div class="abs c">{rain(440, LIGHT)}</div>'
    else:
        body = f"""<div class="abs vsplit"><div class="l"></div><div class="d"></div></div>
        <div style="position:absolute;left:0;width:540px;top:0;bottom:0;display:flex;align-items:center;justify-content:flex-end;padding-right:70px">{plus_minus(200, DARK)}</div>
        <div style="position:absolute;left:540px;width:540px;top:0;bottom:0;display:flex;align-items:center;padding-left:70px">{plus_minus(200, LIGHT, minus=True)}</div>"""
    css = ".c{display:flex;align-items:center;justify-content:center}"
    return page(1080, 1920, body, css)


def main(pair_path, out_dir):
    pair_path = pathlib.Path(pair_path)
    p = json.loads(pair_path.read_text(encoding="utf-8"))
    base = pair_path.parent
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    jobs = {
        "reel_s1.png": (reel_hook(), 1080, 1920),
        "reel_s2.png": (reel_headlines(p, show_bad=False, base_dir=base), 1080, 1920),
        "reel_s3.png": (reel_headlines(p, base_dir=base), 1080, 1920),
        "reel_s4.png": (reel_cta(stat=p.get("gestern", "")), 1080, 1920),
        "story.png": (story_tag(p, base_dir=base), 1080, 1920),
        "highlight_gut.png": (highlight("gut"), 1080, 1920),
        "highlight_schlecht.png": (highlight("schlecht"), 1080, 1920),
        "highlight_sogehts.png": (highlight("info"), 1080, 1920),
    }
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, (doc, w, h) in jobs.items():
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.set_content(doc); pg.wait_for_timeout(150); pg.evaluate(MIRROR_JS); pg.wait_for_timeout(50)
            pg.screenshot(path=str(out / name))
            pg.close()
        b.close()
    print("ok", len(jobs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
