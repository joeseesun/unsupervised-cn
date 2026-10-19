"""品牌资产：图标（favicon / apple-touch / PWA / SVG）与每期分享卡片（Open Graph 1200×630）。

四站各一套视觉：
  terminal  No Priors              石墨黑 + 荧光青柠，等宽字体
  journal   Cognitive Revolution   象牙白 + 学术蓝，Newsreader / 思源宋体
  ledger    Training Data          奶油 + 森林绿 + 黄铜金，Cormorant / 思源宋体
  bauhaus   Unsupervised Learning  米白 + 黑 + 红，Archivo / 思源黑体

图标的 SVG 版由 icons_svg.py（需 fontTools）生成并入库到 brand_assets/<slug>/icon.svg；
PNG 图标与分享卡片在构建时用 Pillow 生成。分享卡片按内容哈希增量生成。
"""
import hashlib
import re
import io
import json
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / '.cache'
FONTS = CACHE / 'fonts'
ASSETS = HERE / 'brand_assets'
OG_W, OG_H = 1200, 630
OG_VERSION = 'v2'

_faces_p = HERE / 'og-faces.json'
FACES = json.loads(_faces_p.read_text()) if _faces_p.exists() else {}


GF = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
FONT_SRC = {  # 全部为 OFL 开源字体，首次构建时下载到 scripts/.cache/fonts/
    'NotoSansSC.ttf': 'notosanssc/NotoSansSC%5Bwght%5D.ttf',
    'NotoSerifSC.ttf': 'notoserifsc/NotoSerifSC%5Bwght%5D.ttf',
    'JetBrainsMono.ttf': 'jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf',
    'InterTight.ttf': 'intertight/InterTight%5Bwght%5D.ttf',
    'Newsreader.ttf': 'newsreader/Newsreader%5Bopsz,wght%5D.ttf',
    'Newsreader-Italic.ttf': 'newsreader/Newsreader-Italic%5Bopsz,wght%5D.ttf',
    'Cormorant.ttf': 'cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf',
    'Archivo.ttf': 'archivo/Archivo%5Bwdth,wght%5D.ttf',
}


def font(name, size, weight=None):
    path = FONTS / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f'  下载字体 {name} …')
        urllib.request.urlretrieve(GF + FONT_SRC[name], path)
    f = ImageFont.truetype(str(path), size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except Exception:
            try:
                f.set_variation_by_axes([weight] if isinstance(weight, (int, float)) else [])
            except Exception:
                pass
    return f


def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- 图标
def icon_master(style, s=1024):
    """1024 画布上画主图标，缩小得到各尺寸。"""
    if style == 'terminal':
        im = Image.new('RGB', (s, s), hexrgb('#0b0c0a'))
        d = ImageDraw.Draw(im)
        f = font('JetBrainsMono.ttf', int(s * .40), 'ExtraBold')
        lime = hexrgb('#c6f432')
        d.text((s * .5, s * .47), 'NP', font=f, fill=lime, anchor='mm')
        w = d.textlength('NP', font=f)
        # 终端光标
        d.rectangle([s * .5 + w / 2 - s * .02, s * .63, s * .5 + w / 2 + s * .07, s * .675], fill=lime)
    elif style == 'journal':
        im = Image.new('RGB', (s, s), hexrgb('#1d3fb8'))
        d = ImageDraw.Draw(im)
        f = font('Newsreader.ttf', int(s * .78), 'Regular')
        d.text((s * .5, s * .53), '§', font=f, fill=hexrgb('#fbfaf6'), anchor='mm')
    elif style == 'ledger':
        im = Image.new('RGB', (s, s), hexrgb('#12301f'))
        d = ImageDraw.Draw(im)
        gold, cream = hexrgb('#c5a467'), hexrgb('#f4efe4')
        m = s * .07
        d.rectangle([m, m, s - m, s - m], outline=gold, width=int(s * .012))
        f = font('Cormorant.ttf', int(s * .52), 'SemiBold')
        d.text((s * .5, s * .48), 'TD', font=f, fill=cream, anchor='mm')
        d.rectangle([s * .34, s * .72, s * .66, s * .728], fill=gold)
    else:  # bauhaus
        im = Image.new('RGB', (s, s), hexrgb('#f2eee6'))
        d = ImageDraw.Draw(im)
        d.ellipse([s * .08, s * .08, s * .62, s * .62], fill=hexrgb('#e0483e'))
        d.rectangle([s * .5, s * .5, s * .92, s * .92], fill=hexrgb('#111111'))
        f = font('Archivo.ttf', int(s * .58), 'Black')
        d.text((s * .56, s * .54), 'U', font=f, fill=hexrgb('#111111'), anchor='mm')
        d.text((s * .71, s * .71), 'L', font=font('Archivo.ttf', int(s * .3), 'Black'), fill=hexrgb('#f2eee6'), anchor='mm')
    return im


def build_icons(slug, cfg, out):
    m = icon_master(cfg['style'])
    sz = lambda n: m.resize((n, n), Image.LANCZOS)
    sz(180).save(out / 'apple-touch-icon.png', optimize=True)
    sz(192).save(out / 'icon-192.png', optimize=True)
    sz(512).save(out / 'icon-512.png', optimize=True)
    # maskable：四周留安全区
    bg = m.getpixel((4, 4)) if cfg['style'] != 'ledger' else hexrgb('#12301f')
    mk = Image.new('RGB', (512, 512), bg)
    mk.paste(m.resize((400, 400), Image.LANCZOS), (56, 56))
    mk.save(out / 'icon-maskable-512.png', optimize=True)
    ico = [sz(n) for n in (16, 32, 48)]
    ico[2].save(out / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico[:2])
    svg = ASSETS / slug / 'icon.svg'
    if svg.exists():
        shutil.copy(svg, out / 'icon.svg')
    else:  # 兜底：PNG 包进 SVG
        import base64
        b = io.BytesIO(); sz(128).save(b, 'PNG')
        (out / 'icon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><image href="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}" width="128" height="128"/></svg>')
    theme = cfg['bg'][cfg['default_theme']]
    (out / 'site.webmanifest').write_text(json.dumps({
        'name': f'{cfg["name"]} 中文精读', 'short_name': cfg['name'],
        'description': cfg['tagline'], 'lang': 'zh-CN', 'start_url': '/', 'scope': '/', 'display': 'standalone',
        'background_color': theme, 'theme_color': theme,
        'icons': [{'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                  {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
                  {'src': '/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}],
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 文字排版工具
CLOSE = set('，。、：；！？）」』”’》〉】,.;:!?)]}%')
BREAK = tuple('、，：；·》」』）') + (' ',)


def tokens(text):
    out, buf = [], ''
    for ch in text:
        if ord(ch) < 0x2E80 and not ch.isspace():
            buf += ch
            continue
        if buf:
            out.append(buf); buf = ''
        out.append(ch)
    if buf:
        out.append(buf)
    return out


def wrap(d, text, f, width, max_lines):
    lines, cur, toks, i = [], '', tokens(text), 0
    while i < len(toks):
        t = toks[i]
        if d.textlength(cur + t, font=f) <= width or not cur.strip() or t in CLOSE:
            cur += t; i += 1
        else:
            cut = max(cur.rfind(c) for c in '、，：；· ')
            if cut >= len(cur) * 0.5:
                lines.append(cur[:cut + 1].rstrip()); cur = cur[cut + 1:].lstrip()
            else:
                lines.append(cur.rstrip()); cur = ''
            if t.isspace():
                i += 1
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur.rstrip())
    if i < len(toks) and lines:
        last = lines[-1]
        while last and d.textlength(last + '…', font=f) > width:
            last = last[:-1]
        lines[-1] = last.rstrip('，、：；,') + '…'
    return lines


def wrap_balanced(d, text, f, width, max_lines):
    def score(ls):
        bad = sum(1 for ln in ls[:-1] if not ln.endswith(BREAK) and not ln[-1:].isascii())
        orphan = 2 if len(ls) > 1 and len(ls[-1].strip()) <= 2 else 0
        ws = [d.textlength(ln, font=f) for ln in ls]
        return (bad + orphan, len(ls), max(ws) - min(ws))
    base = wrap(d, text, f, width, max_lines)
    if len(base) < 2 or base[-1].endswith('…'):
        return base
    best, best_s, w = base, score(base), width
    while w > width * 0.55:
        w -= width * 0.02
        t = wrap(d, text, f, w, max_lines)
        if len(t) > max_lines or t[-1].endswith('…'):
            continue
        sc = score(t)
        if sc < best_s:
            best, best_s = t, sc
    return best


def yt_image(yid):
    p = CACHE / 'yt' / f'{yid}.jpg'
    if p.exists() and p.stat().st_size > 2000:
        return Image.open(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    for q in ('maxresdefault', 'hqdefault'):
        try:
            data = urllib.request.urlopen(f'https://i.ytimg.com/vi/{yid}/{q}.jpg', timeout=20).read()
            if len(data) > 2000:
                p.write_bytes(data)
                return Image.open(io.BytesIO(data))
        except Exception:
            continue
    return None


def photo(yid, w, h, zoom=1.3):
    im = yt_image(yid) if yid else None
    if im is None:
        return None
    im = im.convert('RGB')
    iw, ih = im.size
    if ih * 16 > iw * 9 + 8:
        ch = iw * 9 // 16
        im = im.crop((0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch)); iw, ih = im.size
    scale = max(h * zoom / ih, w / iw)
    im = im.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    cx, cy = FACES.get(yid) or (0.62, 0.42)
    cy = min(cy + 0.06, 0.6)
    x0 = min(max(0, int(im.width * cx - w / 2)), im.width - w)
    y0 = min(max(0, int(im.height * cy - h / 2)), im.height - h)
    return im.crop((x0, y0, x0 + w, y0 + h))


def tint(im, dark, light):
    """双色调：灰度后映射到两种颜色之间。"""
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
    return ImageOps.colorize(g, black=dark, white=light)


def fade_left(ph, color, width=110):
    grad = ImageOps.mirror(Image.linear_gradient('L').rotate(90)).resize((width, ph.height))
    ph.paste(Image.new('RGB', (width, ph.height), color), (0, 0), grad)
    return ph


# ---------------------------------------------------------------- 分享卡片：四种版式
def card_terminal(cfg, e):
    bg, lime, text, mut = hexrgb('#0b0c0a'), hexrgb('#c6f432'), hexrgb('#ecefe6'), hexrgb('#8b9182')
    im = Image.new('RGB', (OG_W, OG_H), bg)
    d = ImageDraw.Draw(im)
    for x in range(0, OG_W, 32):
        d.line([(x, 0), (x, OG_H)], fill=(20, 23, 17))
    for y in range(0, OG_H, 32):
        d.line([(0, y), (OG_W, y)], fill=(20, 23, 17))
    pw = 430
    ph = photo(e and e['yt'], pw, OG_H) if e else None
    tw = OG_W - (pw if ph else 0) - 140
    if ph:
        ph = fade_left(tint(ph, (8, 10, 6), (214, 245, 120)), bg, 120)
        im.paste(ph, (OG_W - pw, 0))
        d.line([(OG_W - pw, 0), (OG_W - pw, OG_H)], fill=lime, width=2)
    mono = lambda n, w='Bold': font('JetBrainsMono.ttf', n, w)
    L = 70
    if e is None:
        d.text((L, 120), '$ cat ~/nopriors.qiaomu.ai', font=mono(26, 'Regular'), fill=mut)
        d.text((L, 175), 'No Priors_', font=font('InterTight.ttf', 128, 'ExtraBold'), fill=text)
        d.text((L, 340), 'AI 创投前沿 · 中文精读', font=font('NotoSansSC.ttf', 52, 'Black'), fill=lime)
        d.text((L, 420), cfg['tagline'], font=font('NotoSansSC.ttf', 28, 'Medium'), fill=mut)
        d.text((L, OG_H - 70), f'● {cfg["hosts"]}', font=mono(22, 'Regular'), fill=mut)
        return im
    k = f'> EP {e["seq"]}' + ('  ·  中文精读' if e['zh_body'] else '') + f'  ·  {e["date"]}'
    d.text((L, 70), k, font=font('NotoSansSC.ttf', 24, 'Bold'), fill=lime)
    title = e.get('zh_t') or e['title']
    size = 58 if len(title) <= 28 else 50 if len(title) <= 40 else 44
    f = font('NotoSansSC.ttf', size, 'Black') if e.get('zh_t') else font('InterTight.ttf', size + 4, 'ExtraBold')
    y = 130
    for ln in wrap_balanced(d, title, f, tw, 4):
        d.text((L, y), ln, font=f, fill=text); y += int(size * 1.3)
    if e.get('zh_t'):
        for ln in wrap(d, e['title'], mono(20, 'Regular'), tw, 2):
            d.text((L, y + 14), ln, font=mono(20, 'Regular'), fill=mut); y += 30
    d.line([(L, OG_H - 96), (L + tw, OG_H - 96)], fill=lime, width=2)
    d.text((L, OG_H - 60), 'No Priors', font=font('InterTight.ttf', 30, 'ExtraBold'), fill=text, anchor='lm')
    d.text((L + 170, OG_H - 60), '中文精读', font=font('NotoSansSC.ttf', 24, 'Bold'), fill=lime, anchor='lm')
    d.text((L + tw, OG_H - 60), 'nopriors.qiaomu.ai', font=mono(20, 'Regular'), fill=mut, anchor='rm')
    return im


def card_journal(cfg, e):
    paper, ink, blue, mut = hexrgb('#fbfaf6'), hexrgb('#161616'), hexrgb('#1d3fb8'), hexrgb('#6b6a64')
    im = Image.new('RGB', (OG_W, OG_H), paper)
    d = ImageDraw.Draw(im)
    news = lambda n, w='Regular': font('Newsreader.ttf', n, w)
    L = 80
    if e is None:
        d.text((OG_W / 2, 150), '§  A Chinese companion journal', font=font('Newsreader-Italic.ttf', 30, 'Regular'), fill=blue, anchor='mm')
        d.text((OG_W / 2, 265), 'Cognitive Revolution', font=news(96, 'SemiBold'), fill=ink, anchor='mm')
        d.line([(260, 345), (OG_W - 260, 345)], fill=ink, width=2)
        d.text((OG_W / 2, 410), 'AI 深度研究 · 中文精读', font=font('NotoSerifSC.ttf', 48, 'Bold'), fill=ink, anchor='mm')
        d.text((OG_W / 2, 480), cfg['tagline'], font=font('NotoSerifSC.ttf', 26, 'Medium'), fill=mut, anchor='mm')
        d.text((OG_W / 2, OG_H - 56), 'cogrev.qiaomu.ai', font=news(24), fill=mut, anchor='mm')
        return im
    pw = 400
    ph = photo(e['yt'], 320, 320, zoom=1.6) if e['yt'] else None
    tw = OG_W - L * 2 - (pw if ph else 0)
    d.text((L, 70), f'§ No. {e["seq"]}', font=news(28, 'SemiBold'), fill=blue)
    d.text((L + 150, 74), 'Cognitive Revolution · 中文精读', font=font('NotoSerifSC.ttf', 22, 'Medium'), fill=mut)
    d.line([(L, 122), (OG_W - L, 122)], fill=ink, width=2)
    title = e.get('zh_t') or e['title']
    size = 54 if len(title) <= 30 else 46 if len(title) <= 44 else 40
    f = font('NotoSerifSC.ttf', size, 'Bold') if e.get('zh_t') else news(size + 6, 'SemiBold')
    y = 160
    for ln in wrap_balanced(d, title, f, tw, 4):
        d.text((L, y), ln, font=f, fill=ink); y += int(size * 1.38)
    if e.get('zh_t'):
        fi = font('Newsreader-Italic.ttf', 26, 'Regular')
        for ln in wrap(d, e['title'], fi, tw, 2):
            d.text((L, y + 12), ln, font=fi, fill=mut); y += 34
    if ph:
        g = ImageOps.grayscale(ph).convert('RGB')
        mask = Image.new('L', g.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, g.width - 1, g.height - 1], fill=255)
        x0, y0 = OG_W - L - 320, 170
        im.paste(g, (x0, y0), mask)
        d.ellipse([x0 - 8, y0 - 8, x0 + 328, y0 + 328], outline=blue, width=2)
        d.text((x0 + 160, y0 + 356), f'Fig. {e["seq"]}  ·  {e["date"]}', font=font('Newsreader-Italic.ttf', 20, 'Regular'), fill=mut, anchor='mm')
    d.line([(L, OG_H - 80), (OG_W - L, OG_H - 80)], fill=hexrgb('#d9d6cc'), width=1)
    d.text((L, OG_H - 48), 'cogrev.qiaomu.ai', font=news(22), fill=mut, anchor='lm')
    d.text((OG_W - L, OG_H - 48), 'AI 深度研究 · 中文精读', font=font('NotoSerifSC.ttf', 20, 'Medium'), fill=blue, anchor='rm')
    return im


def card_ledger(cfg, e):
    cream, green, gold, mut = hexrgb('#f4efe4'), hexrgb('#12301f'), hexrgb('#b08d57'), hexrgb('#6f6a58')
    im = Image.new('RGB', (OG_W, OG_H), cream)
    d = ImageDraw.Draw(im)
    d.rectangle([24, 24, OG_W - 24, OG_H - 24], outline=gold, width=2)
    d.rectangle([32, 32, OG_W - 32, OG_H - 32], outline=gold, width=1)
    corm = lambda n, w='SemiBold': font('Cormorant.ttf', n, w)
    if e is None:
        d.text((OG_W / 2, 140), 'S E Q U O I A   ·   T R A I N I N G   D A T A', font=corm(24, 'SemiBold'), fill=gold, anchor='mm')
        d.text((OG_W / 2, 250), 'Training Data', font=corm(118, 'SemiBold'), fill=green, anchor='mm')
        d.line([(480, 335), (720, 335)], fill=gold, width=2)
        d.text((OG_W / 2, 400), '红杉 AI 对话 · 中文精读', font=font('NotoSerifSC.ttf', 50, 'Bold'), fill=green, anchor='mm')
        d.text((OG_W / 2, 470), cfg['tagline'], font=font('NotoSerifSC.ttf', 25, 'Medium'), fill=mut, anchor='mm')
        d.text((OG_W / 2, OG_H - 70), 'trainingdata.qiaomu.ai', font=corm(26, 'Medium'), fill=mut, anchor='mm')
        return im
    pw = 380
    ph = photo(e['yt'], pw - 40, OG_H - 140, zoom=1.55) if e['yt'] else None
    L = 86
    tw = OG_W - L - 80 - (pw if ph else 0)
    d.text((L, 74), f'No. {e["seq"]}', font=corm(64, 'SemiBold'), fill=gold)
    d.text((L + 6, 158), ('中文精读  ·  ' if e['zh_body'] else '') + 'Training Data', font=font('NotoSerifSC.ttf', 22, 'Medium'), fill=mut)
    title = e.get('zh_t') or e['title']
    size = 52 if len(title) <= 28 else 44 if len(title) <= 42 else 40
    f = font('NotoSerifSC.ttf', size, 'Bold') if e.get('zh_t') else corm(size + 10, 'SemiBold')
    y = 215
    for ln in wrap_balanced(d, title, f, tw, 4):
        d.text((L, y), ln, font=f, fill=green); y += int(size * 1.4)
    if e.get('zh_t'):
        fi = font('Cormorant.ttf', 28, 'Medium')
        for ln in wrap(d, e['title'], fi, tw, 2):
            d.text((L, y + 8), ln, font=fi, fill=mut); y += 34
    if ph:
        sep = tint(ph, (18, 48, 31), (244, 239, 228))
        x0 = OG_W - pw - 30
        im.paste(sep, (x0, 70))
        d.rectangle([x0 - 10, 60, x0 + sep.width + 10, 70 + sep.height + 10], outline=gold, width=2)
    d.text((L, OG_H - 70), 'trainingdata.qiaomu.ai', font=corm(24, 'Medium'), fill=mut, anchor='lm')
    return im


def card_bauhaus(cfg, e):
    paper, ink, red = hexrgb('#f2eee6'), hexrgb('#111111'), hexrgb('#e0483e')
    im = Image.new('RGB', (OG_W, OG_H), paper)
    d = ImageDraw.Draw(im)
    arch = lambda n, w='Black': font('Archivo.ttf', n, w)
    if e is None:
        d.ellipse([-120, -120, 380, 380], fill=red)
        d.rectangle([OG_W - 230, OG_H - 230, OG_W, OG_H], fill=ink)
        d.text((90, 210), 'Unsupervised', font=arch(104), fill=ink)
        d.text((90, 322), 'Learning', font=arch(104), fill=ink)
        d.text((90, 490), 'AI 研究者访谈 · 中文精读', font=font('NotoSansSC.ttf', 40, 'Black'), fill=red)
        d.text((OG_W - 40, OG_H - 40), 'U/L', font=arch(64), fill=paper, anchor='rs')
        return im
    pw = 420
    ph = photo(e['yt'], pw, OG_H) if e['yt'] else None
    tw = OG_W - 80 - 60 - (pw if ph else 0)
    if ph:
        g = ImageOps.grayscale(ph)
        duo = ImageOps.colorize(ImageOps.autocontrast(g, cutoff=1), black=(17, 17, 17), white=(240, 120, 100))
        im.paste(duo, (OG_W - pw, 0))
        d.rectangle([OG_W - pw - 10, 0, OG_W - pw, OG_H], fill=ink)
    d.text((60, 30), f'#{e["seq"]}', font=arch(150), fill=red)
    if e['zh_body']:
        d.rectangle([62, 210, 62 + 150, 250], fill=ink)
        d.text((62 + 75, 230), '中文精读', font=font('NotoSansSC.ttf', 24, 'Black'), fill=paper, anchor='mm')
    title = e.get('zh_t') or e['title']
    size = 52 if len(title) <= 26 else 44 if len(title) <= 40 else 38
    f = font('NotoSansSC.ttf', size, 'Black') if e.get('zh_t') else arch(size + 4, 'ExtraBold')
    y = 275
    for ln in wrap_balanced(d, title, f, tw, 4):
        d.text((62, y), ln, font=f, fill=ink); y += int(size * 1.28)
    d.rectangle([0, OG_H - 64, OG_W - (pw + 10 if ph else 0), OG_H], fill=ink)
    d.text((62, OG_H - 32), 'UNSUPERVISED LEARNING', font=arch(24, 'ExtraBold'), fill=paper, anchor='lm')
    d.text((OG_W - (pw + 40 if ph else 40), OG_H - 32), 'unsupervised.qiaomu.ai', font=arch(20, 'Medium'), fill=paper, anchor='rm')
    return im


# ---------------------------------------------------------------- 无视频单集的封面（16:9，替代 YouTube 缩略图）
CW, CH = 960, 540


def _short_title(e):
    t = e.get('zh_t') or e['title']
    return re.split(r'[：:，,]', t)[0] if len(t) > 22 else t


def cover_terminal(cfg, e):
    bg, lime, text, mut = hexrgb('#0b0c0a'), hexrgb('#c6f432'), hexrgb('#ecefe6'), hexrgb('#8b9182')
    im = Image.new('RGB', (CW, CH), bg); d = ImageDraw.Draw(im)
    for x in range(0, CW, 32): d.line([(x, 0), (x, CH)], fill=(22, 25, 19))
    for y in range(0, CH, 32): d.line([(0, y), (CW, y)], fill=(22, 25, 19))
    d.text((56, 52), '$ nopriors --episode', font=font('JetBrainsMono.ttf', 24, 'Regular'), fill=mut)
    d.text((52, 92), f'EP {e["seq"]}', font=font('JetBrainsMono.ttf', 150, 'ExtraBold'), fill=lime)
    f = font('NotoSansSC.ttf', 40, 'Black')
    y = 300
    for ln in wrap_balanced(d, _short_title(e), f, CW - 120, 2):
        d.text((56, y), ln, font=f, fill=text); y += 56
    d.text((56, CH - 56), 'No Priors_', font=font('InterTight.ttf', 30, 'ExtraBold'), fill=mut)
    return im


def cover_journal(cfg, e):
    paper, ink, blue, mut = hexrgb('#fbfaf6'), hexrgb('#161616'), hexrgb('#1d3fb8'), hexrgb('#6b6a64')
    im = Image.new('RGB', (CW, CH), paper); d = ImageDraw.Draw(im)
    d.text((CW / 2, 150), f'§ {e["seq"]}', font=font('Newsreader.ttf', 150, 'SemiBold'), fill=blue, anchor='mm')
    d.line([(CW / 2 - 140, 250), (CW / 2 + 140, 250)], fill=ink, width=2)
    f = font('NotoSerifSC.ttf', 40, 'Bold')
    y = 290
    for ln in wrap_balanced(d, _short_title(e), f, CW - 200, 2):
        d.text((CW / 2, y), ln, font=f, fill=ink, anchor='ma'); y += 58
    d.text((CW / 2, CH - 50), 'Cognitive Revolution', font=font('Newsreader-Italic.ttf', 26, 'Regular'), fill=mut, anchor='mm')
    return im


def cover_ledger(cfg, e):
    green, gold, cream = hexrgb('#12301f'), hexrgb('#c5a467'), hexrgb('#f4efe4')
    im = Image.new('RGB', (CW, CH), green); d = ImageDraw.Draw(im)
    d.rectangle([22, 22, CW - 22, CH - 22], outline=gold, width=2)
    d.rectangle([30, 30, CW - 30, CH - 30], outline=gold, width=1)
    d.text((CW / 2, 150), f'No. {e["seq"]}', font=font('Cormorant.ttf', 130, 'SemiBold'), fill=gold, anchor='mm')
    d.line([(CW / 2 - 60, 245), (CW / 2 + 60, 245)], fill=gold, width=2)
    f = font('NotoSerifSC.ttf', 40, 'Bold')
    y = 285
    for ln in wrap_balanced(d, _short_title(e), f, CW - 220, 2):
        d.text((CW / 2, y), ln, font=f, fill=cream, anchor='ma'); y += 58
    d.text((CW / 2, CH - 70), 'T R A I N I N G   D A T A', font=font('Cormorant.ttf', 22, 'SemiBold'), fill=gold, anchor='mm')
    return im


def cover_bauhaus(cfg, e):
    paper, ink, red = hexrgb('#f2eee6'), hexrgb('#111111'), hexrgb('#e0483e')
    im = Image.new('RGB', (CW, CH), paper); d = ImageDraw.Draw(im)
    d.ellipse([CW - 380, -160, CW + 120, 340], fill=red)
    d.rectangle([CW - 170, CH - 170, CW, CH], fill=ink)
    d.text((48, 20), f'#{e["seq"]}', font=font('Archivo.ttf', 190, 'Black'), fill=ink)
    f = font('NotoSansSC.ttf', 42, 'Black')
    y = 300
    for ln in wrap_balanced(d, _short_title(e), f, CW - 260, 2):
        d.text((52, y), ln, font=f, fill=ink); y += 56
    d.rectangle([52, CH - 78, 52 + 330, CH - 40], fill=ink)
    d.text((64, CH - 59), 'UNSUPERVISED LEARNING', font=font('Archivo.ttf', 22, 'ExtraBold'), fill=paper, anchor='lm')
    return im


COVERS = {'terminal': cover_terminal, 'journal': cover_journal, 'ledger': cover_ledger, 'bauhaus': cover_bauhaus}


def build_covers(slug, cfg, eps, out):
    """没有 YouTube 视频的单集生成站点风格封面：/covers/<单集文件名>.jpg。"""
    cv = out / 'covers'
    cv.mkdir(exist_ok=True)
    draw, n = COVERS[cfg['style']], 0
    for e in eps:
        if e['yt']:
            continue
        p = cv / (e['file'][:-5] + '.jpg')
        draw(cfg, e).save(p, quality=86, optimize=True, progressive=True)
        n += 1
    return n


CARDS = {'terminal': card_terminal, 'journal': card_journal, 'ledger': card_ledger, 'bauhaus': card_bauhaus}


def build_og(slug, cfg, eps, out):
    og = out / 'og'
    og.mkdir(exist_ok=True)
    state_p = CACHE / f'og-state-{slug}.json'
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    draw = CARDS[cfg['style']]
    dkey = f'{OG_VERSION}-{cfg["style"]}'
    if state.get('__default') != dkey or not (og / 'default.jpg').exists():
        draw(cfg, None).save(og / 'default.jpg', quality=86, optimize=True, progressive=True)
        state['__default'] = dkey
    jobs = []
    for e in eps:
        name = e['file'][:-5] + '.jpg'
        key = hashlib.md5(json.dumps([OG_VERSION, cfg['style'], e.get('zh_t'), e['title'], e['seq'], e['yt'], bool(e['zh_body']),
                                      FACES.get(e['yt'])], ensure_ascii=False).encode()).hexdigest()
        if state.get(name) != key or not (og / name).exists():
            jobs.append((e, name, key))
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: j[0]['yt'] and yt_image(j[0]['yt']), jobs))
    for e, name, key in jobs:
        draw(cfg, e).save(og / name, quality=84, optimize=True, progressive=True)
        state[name] = key
    state_p.write_text(json.dumps(state))
    return len(jobs)


def build_assets(slug, cfg, eps, out):
    build_icons(slug, cfg, out)
    n = build_og(slug, cfg, eps, out)
    c = build_covers(slug, cfg, eps, out)
    print(f'  {slug}: icons ok, og cards {n} rendered, covers {c}')
