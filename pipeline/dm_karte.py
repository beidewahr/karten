"""Beide wahr – DM-Karten mit Symbolbild (ersetzt dm_card aus render.py).

Erzeugt dm_gut.png und dm_schlecht.png (1080x1350) aus pair.json.
Oben: Foto über die ganze Breite (bild, bild_pos). KEIN Hinweis «Symbolbild» auf dem Bild (Entscheid Timo 12.11.2026).
Darunter: Label, Schlagzeile, Text, Quelle, Wortmarke.
Passt die Schriftgrösse automatisch an, falls der Text zu lang ist.
Aufruf: python3 dm_karte.py pair.json out/
"""
import base64, html, json, pathlib, sys
from playwright.sync_api import sync_playwright

DARK, LIGHT = "#15171E", "#F3EEE4"
MUTED_D, MUTED_L = "#8C909B", "#6E685D"
W, H, IMG_H = 1080, 1350, 440


def sun(size, color):
    rays = "".join(f'<rect x="47" y="6" width="6" height="16" rx="3" transform="rotate({a} 50 50)"/>'
                   for a in range(0, 360, 45))
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><g fill="{color}">'
            f'<circle cx="50" cy="50" r="19"/>{rays}</g></svg>')


def rain(size, color):
    """Regenwolke – Symbol für die schlechte Nachricht (ersetzt den Halbmond, Entscheid Timo 11.11.2026)."""
    drops = "".join(
        f'<line x1="{x}" y1="74" x2="{x - 5}" y2="90" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
        for x in (34, 52, 70))
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><g fill="{color}">'
            f'<circle cx="34" cy="46" r="15"/><circle cx="55" cy="36" r="20"/><circle cx="74" cy="49" r="13"/>'
            f'<rect x="19" y="44" width="68" height="18" rx="9"/></g>{drops}</svg>')


def esc(t):
    # Gedankenstrich nie am Zeilenanfang: geschütztes Leerzeichen davor.
    return html.escape(t.replace(" – ", " – "))


def img_uri(path):
    p = pathlib.Path(path)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def card(p, kind, base_dir):
    good = kind == "gut"
    bg, fg = (LIGHT, DARK) if good else (DARK, LIGHT)
    muted = MUTED_L if good else MUTED_D
    icon = sun(60, fg) if good else rain(62, fg)
    label = "Gute Nachricht" if good else "Schlechte Nachricht"
    d = p[kind]
    if d.get("bild"):
        src = img_uri(base_dir / d["bild"])
        photo = (f'<img src="{src}" style="width:100%;height:100%;object-fit:cover;'
                 f'object-position:{d.get("bild_pos", "50% 50%")}">')
    else:  # Platzhalter ohne Bild
        g = "linear-gradient(135deg,#d9d1c2,#b9c4b0)" if good else "linear-gradient(135deg,#2c3140,#4a4f5c)"
        photo = f'<div style="width:100%;height:100%;background:{g}"></div>'
    css = f"""
    @page{{margin:0}} html,body{{margin:0;padding:0}} *{{box-sizing:border-box}}
    body{{font-family:'Inter';-webkit-font-smoothing:antialiased}}
    .c{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:{bg};color:{fg}}}
    .ph{{position:absolute;left:0;top:0;width:{W}px;height:{IMG_H}px}}
    .fade{{position:absolute;left:0;right:0;top:{IMG_H - 120}px;height:121px;
      background:linear-gradient(to bottom,{bg}00,{bg})}}
    .body{{position:absolute;left:0;right:0;top:{IMG_H - 30}px;bottom:0;padding:0 92px 72px;
      display:flex;flex-direction:column}}
    .row{{display:flex;align-items:center;gap:18px;font-family:'Inter';font-weight:700;
      letter-spacing:.18em;text-transform:uppercase;font-size:27px;color:{muted}}}
    .hl{{margin-top:30px;font-family:'Inter Display';font-weight:800;font-size:var(--hl,80px);
      line-height:1.03;letter-spacing:-2px}}
    .tx{{margin-top:30px;font-size:var(--tx,37px);line-height:1.42;font-weight:450}}
    .foot{{margin-top:auto;padding-top:26px;display:flex;justify-content:space-between;align-items:flex-end;
      gap:40px;border-top:2px solid {muted}55}}
    .src{{font-size:22px;line-height:1.4;color:{muted};max-width:640px}}
    .wm{{font-family:'Inter Display';font-weight:800;font-size:38px;letter-spacing:-1px;white-space:nowrap}}
    """
    body = f"""<div class="c"><div class="ph">{photo}</div><div class="fade"></div>
    <div class="body" id="b"><div class="row">{icon}{label}</div>
    <div class="hl">{esc(d['headline'])}</div><div class="tx" id="t">{esc(d['text'])}</div>
    <div class="foot" id="f"><div class="src">Quelle: {esc(d['quelle'])}</div><div class="wm">beide wahr</div></div></div></div>"""
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'


# Schrift verkleinern, bis Text und Fusszeile Platz haben (min. 30 px Fliesstext).
FIT_JS = """
(() => {
  const b = document.getElementById('b'), t = document.getElementById('t'), f = document.getElementById('f');
  let hl = 80, tx = 37;
  const over = () => t.getBoundingClientRect().bottom + 30 > f.getBoundingClientRect().top;
  while (over() && tx > 30) { tx -= 1; hl = Math.max(66, hl - 2);
    b.style.setProperty('--tx', tx + 'px'); b.style.setProperty('--hl', hl + 'px'); }
  return {tx, hl, overflow: over()};
})()
"""


def main(pair_path, out_dir):
    pair_path = pathlib.Path(pair_path)
    p = json.loads(pair_path.read_text(encoding="utf-8"))
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for kind in ("gut", "schlecht"):
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.set_content(card(p, kind, pair_path.parent)); pg.wait_for_timeout(200)
            info = pg.evaluate(FIT_JS)
            pg.screenshot(path=str(out / f"dm_{kind}.png"))
            print(kind, info)
            pg.close()
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
