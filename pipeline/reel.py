"""Beide wahr – animiertes Reel v9 (seit 13.11.2026, ersetzt die zwei Standbilder reel_s3/reel_s4).

Umsetzung der Recherche (Mosseri / Instagram Creators, Stand 2025/26):
- Einstieg in den ersten 0,3 s sichtbar (Thema + beide Fotos), lesbar ohne Ton  -> Skip-Rate
- Bewegung in jeder Szene (Foto-Zoom, Text baut sich auf)                     -> Wiedergabezeit
- kurz (ca. 13 s), Schluss läuft in den Anfang zurück                          -> Wiederholungen
- Aufforderung zum Weiterschicken                                              -> «Sends per reach»
- Ton: eigene, lizenzfreie Musik (musik.py) + leise Akzente                    -> Instagram: «Amplify with audio»
- Texte in der Safe Zone (oben 250 px, unten 420 px, rechts 150 px frei)

Aufruf: python3 reel.py pair.json out/reel.mp4 [--variante A|B]
pair.json-Felder: thema, gut.headline, schlecht.headline, gut.bild, schlecht.bild (+ bild_pos),
optional: hook (Einstiegszeile), teilen (Weiterschick-Zeile), gestern (Statistik-Zeile).
"""
import base64, html, json, pathlib, subprocess, sys
from playwright.sync_api import sync_playwright

DARK, LIGHT, ACCENT = "#15171E", "#F3EEE4", "#4A9A94"
MUTED_D, MUTED_L = "#8C909B", "#6E685D"
W, H, FPS = 1080, 1920, 30
DUR = 12.8
# Szenen: Einstieg | gute Schlagzeile | schlechte Schlagzeile | Aufruf
T_HOOK, T_GUT, T_SCHLECHT, T_CTA = 0.0, 2.8, 5.3, 8.6


def esc(t):
    return html.escape(t.replace(" – ", " – "))


def img_uri(p):
    p = pathlib.Path(p)
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def sun(size, color):
    rays = "".join(f'<rect x="47" y="6" width="6" height="16" rx="3" transform="rotate({a} 50 50)"/>'
                   for a in range(0, 360, 45))
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><g fill="{color}"><circle cx="50" cy="50" r="19"/>{rays}</g></svg>'


def rain(size, color):
    drops = "".join(f'<line x1="{x}" y1="74" x2="{x - 5}" y2="90" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
                    for x in (34, 52, 70))
    return (f'<svg viewBox="0 0 100 100" width="{size}" height="{size}"><g fill="{color}">'
            f'<circle cx="34" cy="46" r="15"/><circle cx="55" cy="36" r="20"/><circle cx="74" cy="49" r="13"/>'
            f'<rect x="19" y="44" width="68" height="18" rx="9"/></g>{drops}</svg>')


def logo(size):
    """Logo «beide wahr» wie Profilbild: links hell, rechts dunkel, Schrift an der Mittellinie zweifarbig."""
    fs = round(size * 0.265)
    t = 'beide<br>wahr'
    return (f'<div class="logo" style="width:{size}px;height:{size}px">'
            f'<div class="lg-l"></div><div class="lg-r"></div>'
            f'<div class="lg-t" style="font-size:{fs}px;color:{DARK};clip-path:inset(0 50% 0 0)">{t}</div>'
            f'<div class="lg-t" style="font-size:{fs}px;color:{LIGHT};clip-path:inset(0 0 0 50%)">{t}</div></div>')


def split_lines(t, maxlen=30):
    """Text in höchstens zwei etwa gleich lange Zeilen teilen (für die Spiegel-Färbung pro Zeile)."""
    if len(t) <= maxlen or " " not in t:
        return [t]
    mid = len(t) / 2
    i = min((k for k, ch in enumerate(t) if ch == " "), key=lambda k: abs(k - mid))
    return [t[:i], t[i + 1:]]


def words(text, cls):
    # Jedes Wort einzeln, damit es nacheinander einblenden kann
    return " ".join(f'<span class="{cls}">{esc(w)}</span>' for w in text.split(" "))


def build_html(p, base):
    g, s = p["gut"], p["schlecht"]
    hook = p.get("hook") or p["thema"]
    teilen = p.get("teilen") or "Kennst du jemanden, den das interessiert?"
    teilen = teilen.replace(" Schick's weiter.", "")
    gestern = p.get("gestern", "")
    zeilen = split_lines(teilen) + ["Schick's weiter."]
    share_html = "".join(
        f'<div class="shl ml{" b" if k == len(zeilen) - 1 else ""}" style="top:{1110 + 56 * k + (10 if k == len(zeilen) - 1 else 0)}px">{esc(z)}</div>'
        for k, z in enumerate(zeilen))
    gi, si = img_uri(base / g["bild"]), img_uri(base / s["bild"])
    gp, sp = g.get("bild_pos", "50% 50%"), s.get("bild_pos", "50% 50%")
    css = f"""
    *{{box-sizing:border-box;margin:0;padding:0}} body{{width:{W}px;height:{H}px;overflow:hidden;background:{DARK};
      font-family:'Inter';-webkit-font-smoothing:antialiased}}
    .abs{{position:absolute}} .disp{{font-family:'Inter Display';font-weight:800}}
    .half{{position:absolute;left:0;width:{W}px;height:{H//2}px;overflow:hidden}}
    #top{{top:0;background:{LIGHT}}} #bot{{top:{H//2}px;background:{DARK}}}
    .ph{{position:absolute;inset:0;background-size:cover;will-change:transform}}
    #topPh{{background-image:url({gi});background-position:{gp}}}
    #botPh{{background-image:url({si});background-position:{sp}}}
    .shade{{position:absolute;inset:0}}
    #topShade{{background:{LIGHT}}} #botShade{{background:{DARK}}}
    .panel{{position:absolute;left:90px;right:150px;display:flex;flex-direction:column;gap:28px}}
    #gutPanel{{bottom:70px;color:{DARK}}} #schlechtPanel{{top:60px;color:{LIGHT}}}
    .row{{display:flex;align-items:center;gap:18px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;font-size:30px}}
    .hl{{font-family:'Inter Display';font-weight:800;font-size:88px;line-height:1.02;letter-spacing:-2.5px}}
    .w{{display:inline-block;opacity:0}}
    #hook{{inset:0}}
    #hookStack{{position:absolute;inset:0}}
    #hookTitleWrap{{position:absolute;left:0;right:0;bottom:{H - 864}px;display:flex;justify-content:center}}
    #hookTitle{{background:rgba(21,23,30,.72);color:{LIGHT};padding:26px 50px 36px;border-radius:32px;font-size:var(--hs,150px);line-height:.98;
      letter-spacing:-4px;text-align:center;max-width:960px;overflow-wrap:normal;hyphens:manual}}
    #hookSubWrap{{position:absolute;left:0;right:0;top:1056px;display:flex;justify-content:center}}
    #hookSubBox{{position:relative}}
    #hookBothWrap{{position:absolute;right:-70px;top:-92px}}
    #hookSub{{background:{LIGHT};color:{DARK};padding:26px 44px 30px;border-radius:30px;font-size:66px;font-weight:700;line-height:1.16;
      letter-spacing:-1px;text-align:center}}
    #hookSub svg{{vertical-align:-8px;margin:0 4px}}
    .logo{{position:relative;border-radius:50%;overflow:hidden;box-shadow:0 0 0 7px {LIGHT}}}
    .lg-l,.lg-r{{position:absolute;top:0;bottom:0;width:50%}} .lg-l{{left:0;background:{LIGHT}}} .lg-r{{right:0;background:{DARK}}}
    .lg-t{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
      font-family:'Inter Display';font-weight:800;line-height:.86;letter-spacing:-.035em;padding-bottom:.06em}}
    #cta{{inset:0;opacity:0}}
    .vs{{position:absolute;top:0;bottom:0;width:{W//2}px}}
    #ctaQ{{position:absolute;left:0;right:0;top:400px;text-align:center;font-size:108px;letter-spacing:-3px;line-height:1;white-space:nowrap}}
    #ctaLine1{{position:absolute;left:0;right:0;top:640px;text-align:center;font-size:76px;letter-spacing:-1.5px;white-space:nowrap}}
    #bubble{{position:absolute;left:50%;top:760px;transform:translateX(-50%);background:{ACCENT};color:{LIGHT};
      font-family:'Inter Display';font-weight:800;font-size:210px;letter-spacing:-6px;line-height:1;padding:30px 72px 46px;border-radius:70px;
      white-space:nowrap}}
    #bubble:after{{content:'';position:absolute;left:96px;bottom:-46px;border-width:50px 0 0 58px;border-style:solid;
      border-color:{ACCENT} transparent transparent transparent}}
    .bl{{opacity:0}} #cursor{{display:inline-block;width:10px;height:170px;background:{LIGHT};margin-left:10px;vertical-align:-14px;border-radius:4px}}
    #ctaVia{{position:absolute;left:0;right:0;top:1150px;text-align:center;font-size:48px;font-weight:600;letter-spacing:-.5px;white-space:nowrap}}
    #stat{{position:absolute;left:0;right:0;top:1260px;text-align:center;font-size:34px;font-weight:500}}
    .ml span{{transition:none}}
    """
    body = f"""
    <div class="half" id="top"><div class="ph" id="topPh"></div><div class="shade" id="topShade"></div>
      <div class="panel" id="gutPanel"><div class="row" id="gutRow" style="color:{MUTED_L};opacity:0">{sun(56, DARK)}Gute Nachricht</div>
      <div class="hl">{words(g['headline'], 'w g')}</div></div></div>
    <div class="half" id="bot"><div class="ph" id="botPh"></div><div class="shade" id="botShade"></div>
      <div class="panel" id="schlechtPanel"><div class="row" id="schlechtRow" style="color:{MUTED_D};opacity:0">{rain(58, LIGHT)}Schlechte Nachricht</div>
      <div class="hl">{words(s['headline'], 'w s')}</div></div></div>
    <div class="abs" id="hook"><div id="hookStack">
      <div id="hookTitleWrap"><div class="disp" id="hookTitle">{esc(hook)}</div></div>
      <div id="hookSubWrap"><div id="hookSubBox"><div id="hookSub">Eine gute {sun(62, DARK)} und eine<br>schlechte {rain(66, DARK)} Nachricht</div>
        <div id="hookBothWrap">{logo(165)}</div></div></div>
    </div></div>
    <div class="abs" id="cta">
      <div class="vs" style="left:0;background:{LIGHT}"></div><div class="vs" style="left:{W//2}px;background:{DARK}"></div>
      <div id="ctaQ" class="disp ml">Gut oder Schlecht?</div>
      <div id="ctaLine1" class="disp ml">Kommentiere</div>
      <div id="bubble"><span class="bl">W</span><span class="bl">A</span><span class="bl">H</span><span class="bl">L</span><span id="cursor"></span></div>
      <div id="ctaVia" class="ml">Deine Nachricht kommt per DM.</div>
      {f'<div id="stat" class="ml">{esc(gestern)}</div>' if gestern else ''}
    </div>"""
    js = """
    const C=540, DARKC='%s', LIGHTC='%s';
    // Spiegel-Färbung: Buchstaben links der Mitte dunkel, rechts hell (wie Profilbild/Story)
    function mirror(){document.querySelectorAll('.ml').forEach(el=>{
      const text=el.textContent; el.textContent='';
      const sp=[...text].map(ch=>{const s=document.createElement('span');s.textContent=ch;el.appendChild(s);return s;});
      let r=sp.map(s=>s.getBoundingClientRect());
      const cross=sp.some((s,i)=>s.textContent.trim()&&r[i].left<C-1&&r[i].right>C+1);
      if(cross){let best=null;for(let i=0;i<sp.length-1;i++){const g=(r[i].right+r[i+1].left)/2,dx=C-g;
        if(best===null||Math.abs(dx)<Math.abs(best))best=dx;} el.style.transform='translateX('+best+'px)'; r=sp.map(s=>s.getBoundingClientRect());}
      sp.forEach((s,i)=>{s.style.color=((r[i].left+r[i].right)/2<C)?DARKC:LIGHTC;});});}
    // Titel: so gross wie möglich, höchstens zwei Zeilen, kein Wort darf überstehen
    (function(){const t=document.getElementById('hookTitle');let s=150;
      const bad=()=>{const r=t.getBoundingClientRect();return t.scrollWidth>t.clientWidth+1||r.width>960||r.height>2*s*0.98+70;};
      while(bad()&&s>64){s-=4;t.style.setProperty('--hs',s+'px');}})();
    (function(){const tb=document.getElementById('hookTitle').getBoundingClientRect().bottom;
      document.getElementById('hookSubWrap').style.top=(960+(960-tb))+'px';})();
    mirror();
    const clamp=(x)=>Math.max(0,Math.min(1,x));
    const ease=(x)=>{x=clamp(x);return 1-Math.pow(1-x,3);};
    const pop=(x)=>{x=clamp(x);const c=1.7;return 1+(c+1)*Math.pow(x-1,3)+c*Math.pow(x-1,2);};
    const $=(id)=>document.getElementById(id);
    const gw=[...document.querySelectorAll('.w.g')], sw=[...document.querySelectorAll('.w.s')];
    window.render=function(t){
      const TH=%f, TG=%f, TS=%f, TC=%f, D=%f;
      // Fotos: langsamer Zoom über die ganze Dauer
      $('topPh').style.transform='scale('+(1.06+0.10*t/D)+')';
      $('botPh').style.transform='scale('+(1.16-0.10*t/D)+')';
      // Einstieg: Titel sofort sichtbar (erstes Bild!), leichtes Einschnappen
      const hk=pop(t/0.35); const out=ease((t-(TG-0.3))/0.35);
      $('hook').style.opacity=1-out;
      $('hookTitleWrap').style.transform='scale('+(0.94+0.06*hk)*(1-0.05*out)+')';
      const hs=pop((t-0.12)/0.4); $('hookSubWrap').style.transform='scale('+(0.9+0.1*hs)+')';
      const hb=pop((t-0.45)/0.45); $('hookBothWrap').style.opacity=Math.min(1,Math.max(0,hb)); $('hookBothWrap').style.transform='scale('+(0.7+0.3*hb)+') rotate('+(12-10*(1-Math.min(1,hb)))+'deg)';
      // Oben: helles Feld schiebt sich über das Foto, Schlagzeile Wort für Wort
      const a=ease((t-TG)/0.45);
      $('topShade').style.opacity=0.0+0.92*a; $('topPh').style.filter='saturate('+(1-0.6*a)+')';
      $('gutRow').style.opacity=a; $('gutRow').style.transform='translateY('+(30*(1-a))+'px)';
      gw.forEach((w,i)=>{const k=ease((t-TG-0.25-i*0.12)/0.3); w.style.opacity=k; w.style.transform='translateY('+(24*(1-k))+'px)';});
      // Unten: dunkles Feld, Schlagzeile Wort für Wort
      const b=ease((t-TS)/0.45);
      $('botShade').style.opacity=0.35+0.55*b;
      $('schlechtRow').style.opacity=b; $('schlechtRow').style.transform='translateY('+(30*(1-b))+'px)';
      sw.forEach((w,i)=>{const k=ease((t-TS-0.25-i*0.12)/0.3); w.style.opacity=k; w.style.transform='translateY('+(24*(1-k))+'px)';});
      // Aufruf
      const c=ease((t-TC)/0.4); $('cta').style.opacity=c;
      const bb=pop((t-TC-0.35)/0.45); $('bubble').style.transform='translateX(-50%%) scale('+Math.max(0.01,bb)+')';
      // WAHL wird wie ein Kommentar getippt, danach pulsiert die Blase leicht
      document.querySelectorAll('.bl').forEach((l,i)=>{l.style.opacity=(t>=TC+0.75+i*0.16)?1:0;});
      $('cursor').style.opacity=(Math.floor((t-TC)*2.5)%%2===0)?1:0;
      const pulse=t>TC+1.5?1+0.03*Math.sin((t-TC-1.5)*Math.PI*2/1.1):1;
      $('bubble').style.transform='translateX(-50%%) scale('+Math.max(0.01,bb)*pulse+')';
      $('ctaLine1').style.opacity=ease((t-TC-0.3)/0.35);
      $('ctaVia').style.opacity=ease((t-TC-1.6)/0.4);
      if($('stat')){$('stat').style.opacity=ease((t-TC-1.7)/0.4);}
      // Schluss: zurück zum Einstieg (nahtlose Schleife). Unter dem deckenden Aufruf wird der Einstieg
      // wiederhergestellt; am Ende blendet nur der Aufruf aus.
      if(t>=TC+0.5){$('hook').style.opacity=1; ['hookTitleWrap','hookSubWrap'].forEach(i=>{$(i).style.transform='scale(1)';$(i).style.opacity=1;}); $('hookBothWrap').style.opacity=1; $('hookBothWrap').style.transform='rotate(12deg)';
        $('topShade').style.opacity=0; $('botShade').style.opacity=0.35; $('topPh').style.filter='saturate(1)';
        $('gutRow').style.opacity=0; $('schlechtRow').style.opacity=0; gw.concat(sw).forEach(w=>w.style.opacity=0);}
      const lo=ease((t-(D-0.6))/0.6);
      if(lo>0){$('cta').style.opacity=1-lo;}
    };
    """ % (DARK, LIGHT, T_HOOK, T_GUT, T_SCHLECHT, T_CTA, DUR)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}<script>{js}</script></body></html>'


def render_video(pair_path, out_mp4, audio=None):
    pair_path = pathlib.Path(pair_path)
    p = json.loads(pair_path.read_text(encoding="utf-8"))
    out_mp4 = pathlib.Path(out_mp4); out_mp4.parent.mkdir(parents=True, exist_ok=True)
    doc = build_html(p, pair_path.parent)
    n = int(DUR * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-movflags", "+faststart", str(out_mp4)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(doc); pg.wait_for_timeout(400)
        for i in range(n):
            pg.evaluate(f"render({i / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=95))
        # Titelbild (Cover) = erstes Bild
        pg.evaluate("render(0.4)")
        pg.screenshot(path=str(out_mp4.with_name("cover.jpg")), type="jpeg", quality=92)
        b.close()
    ff.stdin.close(); ff.wait()
    return out_mp4


if __name__ == "__main__":
    a = sys.argv[1:]
    audio = a[a.index("--audio") + 1] if "--audio" in a else None
    render_video(a[0], a[1], audio)
    print("ok", a[1])
