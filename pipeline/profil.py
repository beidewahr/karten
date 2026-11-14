"""Beide wahr – Erklär-Karussell «So funktioniert's» (angepinnter Beitrag) + Story-Fassung für das Highlight.
Aufruf: python3 profil.py <beispiel_dm_karte.png> out/
Erzeugt sofunktionierts_1..5.png (1080x1350, Karussell) und sogehts_story_1..5.png (1080x1920, Highlight).
"""
import sys, pathlib
from playwright.sync_api import sync_playwright
from render import DARK, LIGHT, MUTED_D, MUTED_L, ACCENT, sun, rain, MIRROR_JS, BASE_CSS
from reel import logo, img_uri

LOGO_CSS = f"""
.logo{{position:relative;border-radius:50%;overflow:hidden;box-shadow:0 0 0 8px {LIGHT},0 0 0 10px {DARK}}}
.lg-l,.lg-r{{position:absolute;top:0;bottom:0;width:50%}} .lg-l{{left:0;background:{LIGHT}}} .lg-r{{right:0;background:{DARK}}}
.lg-t{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
  font-family:'Inter Display';font-weight:800;line-height:.86;letter-spacing:-.035em;padding-bottom:.06em}}
.ml{{position:absolute;left:0;right:0;text-align:center;white-space:nowrap}}
.big{{font-family:'Inter Display';font-weight:800;letter-spacing:-.03em;line-height:1}}
.sm{{font-family:'Inter';font-weight:600}}
.split{{position:absolute;inset:0;display:flex}} .split div{{flex:1}}
.nr{{position:absolute;top:56px;right:64px;font:700 26px Inter;letter-spacing:.12em}}
.btn{{display:inline-flex;align-items:center;gap:18px;padding:26px 40px;border-radius:999px;font:700 44px Inter}}
"""


def nr(i, color):
    return f'<div class="nr" style="color:{color}">{i}/5</div>'


def slides(dm_png, h):
    off = (h - 1350) // 2  # Story-Fassung: Inhalt vertikal mittig
    S = []
    # 1 – Einstieg
    S.append(f"""<div class="split"><div style="background:{LIGHT}"></div><div style="background:{DARK}"></div></div>
      <div style="position:absolute;left:0;right:0;top:{off + 170}px;display:flex;justify-content:center">{logo(300)}</div>
      <div class="ml big" style="top:{off + 610}px;font-size:96px">Jeden Tag</div>
      <div class="ml big" style="top:{off + 715}px;font-size:96px">zwei Nachrichten.</div>
      <div class="ml big" style="top:{off + 860}px;font-size:132px">Beide wahr.</div>
      <div class="ml sm" style="top:{off + 1180}px;font-size:34px">So funktioniert's  →</div>{nr(1, LIGHT)}""")
    # 2 – gut + schlecht
    S.append(f"""<div class="split"><div style="background:{LIGHT}"></div><div style="background:{DARK}"></div></div>
      <div style="position:absolute;left:0;width:540px;top:{off + 260}px;text-align:center">{sun(190, DARK)}
        <div class="big" style="font-size:78px;color:{DARK};margin-top:30px">Eine<br>gute</div></div>
      <div style="position:absolute;left:540px;width:540px;top:{off + 260}px;text-align:center">{rain(190, LIGHT)}
        <div class="big" style="font-size:78px;color:{LIGHT};margin-top:30px">Eine<br>schlechte</div></div>
      <div class="ml big" style="top:{off + 760}px;font-size:66px">Zum selben Thema.</div>
      <div class="ml sm" style="top:{off + 880}px;font-size:38px">Natur · Tiere · Gesundheit · Wissenschaft</div>
      <div class="ml sm" style="top:{off + 940}px;font-size:38px">Gesellschaft · Technik</div>
      <div class="ml sm" style="top:{off + 1060}px;font-size:36px">Geprüft, mit Quelle. Unpolitisch.</div>{nr(2, LIGHT)}""")
    # 3 – Wahl
    S.append(f"""<div style="position:absolute;inset:0;background:{LIGHT}"></div>
      <div class="big" style="position:absolute;left:0;right:0;top:{off + 170}px;text-align:center;font-size:88px;color:{DARK}">Du wählst,<br>welche du liest.</div>
      <div style="position:absolute;left:0;right:0;top:{off + 470}px;text-align:center;font:600 40px Inter;color:{MUTED_L}">Schreib uns per DM:</div>
      <div style="position:absolute;left:0;right:0;top:{off + 545}px;display:flex;justify-content:center">
        <div class="big" style="background:{ACCENT};color:{LIGHT};font-size:150px;padding:20px 64px 34px;border-radius:56px;letter-spacing:-4px">WAHL</div></div>
      <div style="position:absolute;left:0;right:0;top:{off + 850}px;display:flex;flex-direction:column;align-items:center;gap:26px">
        <div class="btn" style="background:#fff;color:{DARK};border:3px solid {DARK}">{sun(52, DARK)} Die gute</div>
        <div class="btn" style="background:{DARK};color:{LIGHT}">{rain(56, LIGHT)} Die schlechte</div></div>
      <div style="position:absolute;left:0;right:0;top:{off + 1200}px;text-align:center;font:600 32px Inter;color:{MUTED_L}">… oder kommentiere WAHL unter dem Reel.</div>{nr(3, DARK)}""")
    # 4 – DM-Karte
    S.append(f"""<div style="position:absolute;inset:0;background:{DARK}"></div>
      <div class="big" style="position:absolute;left:0;right:0;top:{off + 110}px;text-align:center;font-size:80px;color:{LIGHT}">Deine Nachricht<br>kommt per DM.</div>
      <div style="position:absolute;left:50%;top:{off + 370}px;width:560px;transform:translateX(-50%) rotate(-3deg);border-radius:34px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.5)">
        <img src="{img_uri(dm_png)}" style="width:100%;display:block"></div>
      <div style="position:absolute;left:0;right:0;top:{off + 1215}px;text-align:center;font:600 34px Inter;color:{MUTED_D}">Und wenn du magst: auch die andere.</div>{nr(4, LIGHT)}""")
    # 5 – Folgen
    S.append(f"""<div class="split"><div style="background:{LIGHT}"></div><div style="background:{DARK}"></div></div>
      <div class="ml sm" style="top:{off + 200}px;font-size:40px">Worauf du deine Aufmerksamkeit</div>
      <div class="ml sm" style="top:{off + 254}px;font-size:40px">richtest, entscheidest du.</div>
      <div class="ml big" style="top:{off + 470}px;font-size:120px">Jeden Morgen</div>
      <div class="ml big" style="top:{off + 600}px;font-size:120px">eine neue Wahl.</div>
      <div class="ml big" style="top:{off + 860}px;font-size:76px">Folge @beidewahr</div>
      <div class="ml sm" style="top:{off + 990}px;font-size:36px">und schick's jemandem, der gern mitwählt.</div>{nr(5, LIGHT)}""")
    return S


def doc(body, w, h):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}{LOGO_CSS}
    .canvas{{width:{w}px;height:{h}px}}</style></head><body><div class="canvas">{body}</div></body></html>"""


def main(dm_png, out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, h in (("sofunktionierts", 1350), ("sogehts_story", 1920)):
            for i, body in enumerate(slides(dm_png, h), 1):
                pg = b.new_page(viewport={"width": 1080, "height": h})
                pg.set_content(doc(body, 1080, h)); pg.wait_for_timeout(200)
                pg.evaluate(MIRROR_JS); pg.wait_for_timeout(50)
                pg.screenshot(path=str(out / f"{name}_{i}.png")); pg.close()
        b.close()
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
