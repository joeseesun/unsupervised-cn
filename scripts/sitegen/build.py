#!/usr/bin/env python3
"""四个 AI 播客中文站的静态站生成器（与 lex.qiaomu.ai 同一套能力，视觉各自独立）。

用法：python3 scripts/sitegen/build.py [slug ...]   不带参数构建全部四站

输入：data/<slug>/episodes.json、transcripts/NNN.json、zh/NNN.html
输出：sites/<slug>/（首页、单集页、单集目录、404 / 离线页、RSS、sitemap、robots、llms.txt、
      每篇精读的 Markdown、分享卡片、图标、manifest、Service Worker）
"""
import hashlib
import html as H
import json
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / 'data'
SITES = ROOT / 'sites'
STATIC = HERE / 'static'
sys.path.insert(0, str(HERE))
from themes import SHOWS  # noqa: E402

V = '2'  # 静态资源版本号，改样式 / 脚本时递增


# ---------------------------------------------------------------- 数据
def slugify(s, maxlen=60):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s[:maxlen].rstrip('-') or 'episode'


def ep_file(ep, seq):
    """沿用旧站的文件名，已被收录的链接不失效。"""
    key = ep.get('ytId') or hashlib.md5(ep['id'].encode()).hexdigest()[:10]
    return f"{seq:03d}-{slugify(ep['title'])}-{key[:6]}.html"


def esc(s):
    return H.escape(s or '', quote=True)


def strip_tags(s):
    return H.unescape(re.sub(r'<[^>]+>', '', s or ''))


def para(s):
    s = esc((s or '').strip())
    parts = [p.strip() for p in re.split(r'\n\s*\n', s) if p.strip()]
    return '\n'.join(f'<p>{re.sub(chr(10) + "+", "<br>", p)}</p>' for p in parts)


def fmt_date(d):
    if not d:
        return ''
    y, m, *_ = d.split('-') + ['']
    return f'{y} 年 {int(m)} 月' if m else y


def fmt_dur(sec):
    m = round((sec or 0) / 60)
    if not m:
        return ''
    return f'{m // 60} 小时 {m % 60} 分' if m >= 60 else f'{m} 分钟'


def load_show(slug):
    raw = json.loads((DATA / slug / 'episodes.json').read_text())['episodes']
    tp_ = DATA / slug / 'translations.json'
    trans = json.loads(tp_.read_text()) if tp_.exists() else {}
    n = len(raw)
    eps = []
    for i, e in enumerate(raw):
        seq = n - i
        f = ep_file(e, seq)
        zp = DATA / slug / 'zh' / f'{seq:03d}.html'
        zh_raw = zp.read_text().strip() if zp.exists() else ''
        if len(re.sub(r'\s+', '', strip_tags(zh_raw))) < 500:  # 生成失败的残片不算精读
            zh_raw = ''
        zh_title, zh_body = '', zh_raw
        m = re.match(r'\s*<h2[^>]*>(.*?)</h2>\s*', zh_raw, flags=re.S)
        if m:  # 精读第一行的 h2 是中文大标题，提出来做文章标题
            zh_title, zh_body = strip_tags(m.group(1)).strip(), zh_raw[m.end():]
            while zh_title.startswith('《') and zh_title.endswith('》'):
                zh_title = zh_title[1:-1].strip()  # 标题外层的书名号（可能不止一层）去掉
            zh_title = zh_title.lstrip('《') if zh_title.count('《') > zh_title.count('》') else zh_title
        tp = DATA / slug / 'transcripts' / f'{seq:03d}.json'
        tr = None
        if tp.exists():
            try:
                tr = json.loads(tp.read_text())
                if not (tr or {}).get('text'):
                    tr = None
            except Exception:
                tr = None
        try:
            dur = int(float(e.get('duration') or e.get('ytDuration') or 0))
        except ValueError:
            dur = 0
        eps.append({
            'seq': seq, 'file': f, 'url': f'/ep/{f}', 'title': e['title'].strip(), 'date': e.get('date') or '',
            'dur': dur, 'desc': (e.get('description') or '').strip(), 'yt': e.get('ytId') or '',
            'audio': e.get('audio') or '', 'link': e.get('link') or '',
            'zh_title': zh_title, 'zh_body': zh_body,
            'zh_t': (zh_title if re.search(r'[\u4e00-\u9fff]', zh_title) else '') or (trans.get(e['id']) or {}).get('zh', '') or zh_title,
            'zh_desc': (trans.get(e['id']) or {}).get('desc', ''), 'zh_mtime': date.fromtimestamp(zp.stat().st_mtime).isoformat() if zh_raw else None,
            'tr': tr,
        })
    return eps


# ---------------------------------------------------------------- 共用片段
def head_script(cfg):
    """主题 / 阅读偏好在首屏前应用；全站通用点击处理；PWA 注册。"""
    bg = json.dumps(cfg['bg'])
    return f"""<script>
(function () {{
  var d = document.documentElement, g = function (k) {{ try {{ return localStorage.getItem(k); }} catch (e) {{ return null; }} }};
  var t = g('lex-theme'), f = g('lex-font'), z = g('lex-size'), lh = g('lex-lh'), w = g('lex-measure');
  var BG = {bg};
  if (!BG[t]) t = '{cfg['default_theme']}';
  d.setAttribute('data-theme', t);
  var FONTS = {{
    sans: 'https://fonts.googleapis.cn/css2?family=Noto+Sans+SC:wght@400;600&display=swap',
    serif: 'https://fonts.googleapis.cn/css2?family=Noto+Serif+SC:wght@400;600&display=swap',
    kai: 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaiscreen.css',
    wei: 'https://fonts.googleapis.cn/css2?family=ZCOOL+XiaoWei&display=swap',
    song: 'https://cdn.jsdelivr.net/npm/@chinese-fonts/jhlst@3.0.0/dist/%E4%BA%AC%E8%8F%AF%E8%80%81%E5%AE%8B%E4%BD%93v2_002/result.css'
  }};
  window.__lexLoadFont = function (k) {{
    if (!FONTS[k] || document.getElementById('lexfont-' + k)) return;
    var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = FONTS[k]; l.id = 'lexfont-' + k;
    document.head.appendChild(l);
  }};
  if (!f) f = '{cfg['default_font']}';
  if (FONTS[f]) {{ d.setAttribute('data-font', f); window.__lexLoadFont(f); }}
  if (z && /^(1[5-9]|2[0-2])$/.test(z)) d.style.setProperty('--read-size', z + 'px');
  if (lh && /^(1\\.\\d+|2(\\.\\d+)?)$/.test(lh)) d.style.setProperty('--read-lh', lh);
  if (w && /^\\d{{3}}$/.test(w)) d.style.setProperty('--measure', w + 'px');
  var meta = document.querySelector('meta[name="theme-color"]');
  function syncMeta() {{ if (meta) meta.content = BG[t]; }}
  syncMeta();
  window.__lexSetTheme = function (n) {{
    if (!BG[n]) return;
    t = n;
    try {{ localStorage.setItem('lex-theme', t); if (t !== 'dark') localStorage.setItem('lex-light', t); }} catch (e) {{}}
    d.classList.add('theme-anim'); d.setAttribute('data-theme', t); syncMeta();
    setTimeout(function () {{ d.classList.remove('theme-anim'); }}, 320);
    document.dispatchEvent(new CustomEvent('lex-theme', {{ detail: t }}));
  }};
  window.__lexThemeToggle = function () {{ window.__lexSetTheme(t === 'dark' ? (g('lex-light') || 'light') : 'dark'); }};
  document.addEventListener('load', function (e) {{ var x = e.target; if (x.tagName === 'IMG') x.classList.add('ok'); }}, true);
  document.addEventListener('error', function (e) {{ var x = e.target; if (x.tagName === 'IMG' && !x.getAttribute('onerror')) x.classList.add('ok'); }}, true);
  var deferred = null;
  function showInstall() {{ Array.prototype.forEach.call(document.querySelectorAll('[data-install]'), function (b) {{ b.hidden = false; }}); }}
  window.addEventListener('beforeinstallprompt', function (e) {{ e.preventDefault(); deferred = e; showInstall(); }});
  var standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone;
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone) document.addEventListener('DOMContentLoaded', showInstall);
  document.addEventListener('click', function (e) {{
    var el = e.target.closest ? e.target : e.target.parentNode;
    if (el.closest('[data-theme-toggle]')) return window.__lexThemeToggle();
    var ins = el.closest('[data-install]');
    if (ins) {{ if (deferred) {{ deferred.prompt(); deferred.userChoice.finally(function () {{ deferred = null; ins.hidden = true; }}); }} else {{ var im = document.getElementById('installModal'); if (im) im.hidden = false; }} return; }}
    var o = el.closest('[data-open]');
    if (o) {{ var m = document.getElementById(o.getAttribute('data-open')); if (m) {{ m.hidden = false; var c = m.querySelector('.modal-close'); if (c) c.focus(); }} if (window.umami) window.umami.track('open-' + o.getAttribute('data-open')); return; }}
    var mm = el.closest('.modal');
    if (mm && (el === mm || el.closest('.modal-close'))) {{ mm.hidden = true; return; }}
    var sh = el.closest('[data-share]');
    if (sh) {{
      var data = {{ title: document.title, url: location.href.split('#')[0] }};
      if (navigator.share) navigator.share(data).catch(function () {{}});
      else if (navigator.clipboard) navigator.clipboard.writeText(data.title + ' ' + data.url).then(function () {{ var x = sh.textContent; sh.textContent = '链接已复制'; setTimeout(function () {{ sh.textContent = x; }}, 1600); }});
      return;
    }}
    var cf = el.closest('[data-copy-feed]');
    if (cf) {{
      var url = location.origin + '/feed.xml', label = cf.textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () {{ cf.textContent = '已复制'; setTimeout(function () {{ cf.textContent = label; }}, 1600); }}, function () {{ location.href = '/feed.xml'; }});
      else location.href = '/feed.xml';
    }}
  }});
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') Array.prototype.forEach.call(document.querySelectorAll('.modal'), function (m) {{ m.hidden = true; }});
  }});
  if ('serviceWorker' in navigator && location.protocol === 'https:') {{
    window.addEventListener('load', function () {{ navigator.serviceWorker.register('/sw.js').catch(function () {{}}); }});
  }}
}})();
</script>"""


def head(cfg, *, title, desc, url, og_img, og_type='website', extra='', ld=None, robots='index, follow, max-image-preview:large, max-snippet:-1'):
    d = cfg['domain']
    ldj = ('<script type="application/ld+json">' + json.dumps(prune(ld), ensure_ascii=False).replace('<', '\\u003c') + '</script>') if ld else ''
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="{cfg['bg'][cfg['default_theme']]}">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="{robots}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta property="og:site_name" content="{esc(cfg['name'])} 中文精读">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{og_img}">
{extra}
{ldj}
{head_script(cfg)}
<link rel="preconnect" href="https://fonts.googleapis.cn"><link rel="preconnect" href="https://fonts.gstatic.cn" crossorigin><link rel="preconnect" href="https://i.ytimg.com">
<link rel="stylesheet" href="{cfg['fonts']}">
<link rel="icon" href="/favicon.ico" sizes="32x32"><link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest">
<meta name="apple-mobile-web-app-title" content="{esc(cfg['name'])}"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="format-detection" content="telephone=no">
<link rel="alternate" type="application/rss+xml" title="{esc(cfg['name'])} 中文精读 · RSS 全文" href="https://{d}/feed.xml">
<noscript><style>.thumb img,.cont-thumb img,.hero-media img{{opacity:1}}</style></noscript>
<link rel="stylesheet" href="/style.css?v={V}">
<script>window.SITE = {json.dumps({'ep': cfg['ep_label'], 'zhTag': cfg['kicker_zh'], 'name': cfg['name'], 'font': cfg['default_font']}, ensure_ascii=False)};</script>
</head>
<body class="s-{cfg['style']}">
<a class="skip-link" href="#main">跳到主要内容</a>"""


THEME_BTN = ('<button class="theme-toggle" type="button" data-theme-toggle aria-label="切换浅色 / 深色模式" title="切换浅色 / 深色模式">'
             '<svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
             '<path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/></svg>'
             '<svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z"/></svg></button>')
ICON_SEARCH = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>'
ICON_PLAY = '<svg class="i-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.6-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>'
ICON_PAUSE = '<svg class="i-pause" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4.2" height="14" rx="1.2"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.2"/></svg>'
ICON_ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'


def mark(cfg):
    """字标里的小图形，每站一个，与图标同源。"""
    return f'<span class="mark" aria-hidden="true"><img src="/icon.svg" alt="" width="28" height="28"></span>'


def slim_header(cfg):
    return f"""<header class="site-header slim">
  <div class="wrap header-inner">
    <a class="hdr-back" href="/">← 全部单集</a>
    <a class="wordmark" href="/" aria-label="{esc(cfg['name'])} 中文精读 · 首页">{mark(cfg)}<span class="wm-name">{esc(cfg['name'])}</span><span class="wm-cn">{esc(cfg['cn'])}</span></a>
    <div class="header-actions"><a class="hdr-icon" href="/#search" aria-label="搜索全部单集" title="搜索">{ICON_SEARCH}</a>{THEME_BTN}</div>
  </div>
</header>"""


def footer(cfg):
    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="ft-top">
      <a class="ft-mark" href="/">{mark(cfg)}<span>{esc(cfg['name'])}</span><small>{esc(cfg['cn'])} · 中文精读</small></a>
      <p class="ft-tag">{esc(cfg['motto'])}</p>
    </div>
    <div class="ft-cols">
      <nav class="ft-col" aria-label="浏览"><h2>浏览</h2>
        <a href="/">全部单集</a><a href="/?f=zh">中文精读</a><a href="/archive/">单集目录</a><a href="/#search">搜索</a>
        <button type="button" data-install hidden>安装为应用</button></nav>
      <nav class="ft-col" aria-label="订阅"><h2>订阅</h2>
        <a href="/feed.xml">RSS 全文订阅</a><button type="button" data-copy-feed>复制 RSS 地址</button>
        <a href="{esc(cfg['youtube'])}" target="_blank" rel="noopener">YouTube 频道</a><a href="{esc(cfg['official'])}" target="_blank" rel="noopener">节目官网</a></nav>
      <nav class="ft-col" aria-label="姊妹站"><h2>姊妹站</h2>
        {''.join(f'<a href="https://{c["domain"]}/">{esc(c["name"])}</a>' for k, c in SHOWS.items() if c is not cfg)}
        <a href="https://lex.qiaomu.ai/">Lex Fridman</a><a href="https://tuijian.qiaomu.ai/" target="_blank" rel="noopener">乔木推荐</a></nav>
      <div class="ft-col ft-support"><h2>支持这个项目</h2>
        <p>一个人独立制作，没有广告，也不收费。如果这里的某篇精读让你有所收获，欢迎请作者喝杯咖啡，让它一直做下去。</p>
        <div class="ft-actions"><button type="button" class="ft-btn" data-open="rewardModal">打赏支持</button><button type="button" class="ft-btn ghost" data-open="followModal">关注公众号</button></div>
        <p class="ft-social"><a href="https://github.com/joeseesun/{next(k for k, c in SHOWS.items() if c is cfg)}-cn" target="_blank" rel="noopener">开源代码</a><a href="https://x.com/vista8" target="_blank" rel="noopener">X @vista8</a><a href="/llms.txt">llms.txt</a></p></div>
    </div>
    <div class="ft-bottom">
      <span>© 2026 向阳乔木 · 非官方粉丝站点，与 {esc(cfg['name'])} 及节目制作方无隶属关系</span>
      <span>音视频与原始文稿版权归原权利方所有 · 中文精读由 AI 改写，仅供学习参考，以原节目为准</span>
    </div>
  </div>
</footer>
<div id="rewardModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="rewardT">
  <div class="modal-card"><button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="rewardT">谢谢你的支持</h3><p class="modal-sub">每一份打赏都会变成更多认真校过的精读</p>
    <img src="/assets/reward.png" alt="打赏二维码" width="220" height="220" loading="lazy"><p class="modal-links">微信扫一扫</p></div>
</div>
<div id="followModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="followT">
  <div class="modal-card"><button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="followT">关注向阳乔木</h3><p class="modal-sub">微信公众号：向阳乔木推荐看</p>
    <img src="/assets/wechat.jpg" alt="公众号二维码" width="220" height="220" loading="lazy">
    <p class="modal-links"><a href="https://github.com/joeseesun/" target="_blank" rel="noopener">GitHub</a> · <a href="https://x.com/vista8" target="_blank" rel="noopener">X</a></p></div>
</div>
<div id="installModal" class="modal" hidden role="dialog" aria-modal="true" aria-labelledby="installT">
  <div class="modal-card"><button type="button" class="modal-close" aria-label="关闭">×</button>
    <h3 id="installT">添加到主屏幕</h3><p class="modal-sub">像应用一样打开，读过的文章离线也能看</p>
    <ol class="install-steps"><li>点 Safari 底部的「分享」按钮</li><li>向下滑，选择「添加到主屏幕」</li><li>点右上角「添加」</li></ol></div>
</div>
<script defer src="https://umami.qiaomu.ai/script.js" data-website-id="{cfg['umami']}" data-domains="{cfg['domain']}"></script>"""


def prune(o):
    if isinstance(o, dict):
        return {k: prune(v) for k, v in o.items() if v not in (None, '', [], {})}
    if isinstance(o, list):
        return [prune(v) for v in o]
    return o


STOP_EN = set("""the and for with from that this are was were you your our their about into how why what when who will can not but its it's
has have had more most than then them they his her him she he out over all any new one two now just like also very podcast episode
ai show talk talks discuss discusses joins join host hosts conversation interview ceo founder cofounder co-founder""".split())


def related_index(eps, k=3):
    """延伸阅读：TF-IDF 余弦相似度。特征 = 中文标题 / 简介 / 小节标题的二字词 + 英文标题与简介里的实词；
    全站常见的词（AI、模型…）权重自然很低，嘉宾、公司、领域词权重高。不含自身与紧邻的上下期。"""
    import math
    from collections import Counter

    def feats(e):
        c = Counter()
        heads = ' '.join(strip_tags(x) for x in re.findall(r'<h2[^>]*>(.*?)</h2>', e['zh_body'] or '', flags=re.S))
        zh = re.sub(r'[^\u4e00-\u9fff]+', ' ', f"{e['zh_t']} {e['zh_desc']} {heads}")
        for w in zh.split():
            c.update(w[i:i + 2] for i in range(len(w) - 1))
        en = re.findall(r"[a-z][a-z0-9\-']+", f"{e['title']} {e['title']} {e['desc'][:600]}".lower())
        c.update(w for w in en if len(w) > 2 and w not in STOP_EN)
        return c

    F = [feats(e) for e in eps]
    n = len(F)
    df = Counter(t for f in F for t in f)
    vecs = []
    for f in F:
        v = {t: (1 + math.log(c)) * math.log(n / df[t]) for t, c in f.items() if df[t] > 1}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        vecs.append({t: x / norm for t, x in v.items()})
    rel = []
    for i, vi in enumerate(vecs):
        scored = []
        for j, vj in enumerate(vecs):
            if abs(i - j) <= 1:
                continue
            small, big = (vi, vj) if len(vi) < len(vj) else (vj, vi)
            sim = sum(x * big.get(t, 0) for t, x in small.items())
            if sim > 0:
                scored.append((sim, j))
        scored.sort(reverse=True)
        rel.append([j for _, j in scored[:k]])
    return rel


def zh_stats(body):
    chars = len(re.sub(r'\s+', '', strip_tags(body)))
    return chars, max(1, round(chars / 450)) if chars else 0


def card_title(e):
    return e['zh_t'] or e['title']


# ---------------------------------------------------------------- 首页
def ssr_card(cfg, e):
    thumb = (f'<img loading="lazy" decoding="async" src="https://i.ytimg.com/vi/{e["yt"]}/mqdefault.jpg" alt="" width="320" height="180">'
             if e['yt'] else f'<div class="no-img">{esc(cfg["ep_label"])} {e["seq"]}</div>')
    dt = e['date'][:7].replace('-', '.')
    tag = f'<span class="zh-tag">{esc(cfg["kicker_zh"])}</span>' if e['zh_body'] else ''
    rm = zh_stats(e['zh_body'])[1] if e['zh_body'] else 0
    dur = (f'<span class="dur">精读 {rm} 分钟</span>' if rm else
           f'<span class="dur">{fmt_dur(e["dur"])}</span>' if e['dur'] else '')
    en = f'<div class="card-title-en" lang="en">{esc(e["title"])}</div>' if e['zh_t'] else ''
    desc = (f'<div class="card-desc">{esc(e["zh_desc"])}</div>' if e['zh_desc'] else
            f'<div class="card-desc" lang="en">{esc(e["desc"][:200])}</div>' if e['desc'] else '')
    return (f'<a class="card" href="{e["url"]}"><div class="thumb">{thumb}</div><div class="card-body">'
            f'<div class="card-kicker"><span class="ep-n">{esc(cfg["ep_label"])} {e["seq"]}</span><span>{dt}</span>{dur}{tag}</div>'
            f'<div class="card-title">{esc(card_title(e))}</div>{en}{desc}</div></a>')


def ssr_hero(cfg, e):
    when = fmt_date(e['date'])
    by = ' · '.join(x for x in [when, fmt_dur(e['dur']), f'{cfg["ep_label"]} {e["seq"]}'] if x)
    img = (f'<img src="https://i.ytimg.com/vi/{e["yt"]}/maxresdefault.jpg" alt="" '
           f'onerror="this.onerror=null;this.src=\'https://i.ytimg.com/vi/{e["yt"]}/hqdefault.jpg\'">' if e['yt'] else '')
    first = re.search(r'<p>(.*?)</p>', e['zh_body'], flags=re.S)
    lede = strip_tags(first.group(1))[:120] + '…' if first else ''
    return (f'<a class="hero-media" href="{e["url"]}" tabindex="-1" aria-hidden="true">{img}</a>'
            f'<div class="hero-text"><div class="hero-kicker">最新精读</div>'
            f'<h2 class="hero-title"><a href="{e["url"]}">{esc(card_title(e))}</a></h2>'
            f'<p class="hero-en" lang="en">{esc(e["title"])}</p>'
            + (f'<p class="hero-desc">{esc(lede)}</p>' if lede else '') +
            f'<p class="hero-by">{esc(by)}</p>'
            f'<a class="hero-cta" href="{e["url"]}">阅读全文{ICON_ARROW}</a></div>')


# 热门话题候选：(显示名, 搜索词)。计数与站内搜索同一口径（同样的归一化与字段），点开后结果数与芯片上的数字一致
TOPICS = [('OpenAI', 'OpenAI'), ('Anthropic', 'Anthropic'), ('谷歌', '谷歌'), ('英伟达', '英伟达'), ('DeepMind', 'DeepMind'),
          ('Agent', 'Agent'), ('编程', '编程'), ('芯片', '芯片'), ('机器人', '机器人'), ('医疗', '医疗'), ('药物', '药物'),
          ('国防', '国防'), ('开源', '开源'), ('强化学习', '强化学习'), ('安全', '安全'), ('对齐', '对齐'), ('投资', '投资'),
          ('推理', '推理'), ('中国', '中国'), ('视频', '视频'), ('教育', '教育'), ('能源', '能源')]


def _norm(t):
    t = unicodedata.normalize('NFKD', t or '').lower()
    return re.sub(r"[\s·•・\-–—_'’\"“”:：,，.。!！?？()（）\[\]【】#&/、|]+", '', t)


def topic_chips(eps):
    hay = [_norm(f"{e['zh_t']} {e['title']} {e['file']} {e['zh_desc'] or e['desc'][:200]}") for e in eps]
    counts = []
    for label, q in TOPICS:
        n = sum(1 for h in hay if _norm(q) in h)
        if n >= 4:
            counts.append((n, label, q))
    counts.sort(reverse=True)
    return ''.join(f'<button type="button" class="topic" data-q="{esc(q)}">{esc(label)}<span>{n}</span></button>' for n, label, q in counts[:10])


def build_index(cfg, eps, out):
    d = cfg['domain']
    n_zh = sum(1 for e in eps if e['zh_body'])
    since = min((e['date'] for e in eps if e['date']), default='')[:4]
    hours = round(sum(e['dur'] for e in eps) / 3600)
    latest = next((e for e in eps if e['zh_body']), None)
    data = [{'n': e['seq'], 't': e['title'], 's': e['file'], 'u': e['url'], 'd': e['date'], 'y': e['yt'],
             'zh': e['zh_t'] or None, 'tr': 'tr' if e['tr'] else None, 'au': bool(e['audio']),
             'r': 1 if e['zh_body'] else 0, 'ds': e['zh_desc'] or e['desc'][:200], 'du': e['dur'],
             'rm': zh_stats(e['zh_body'])[1] if e['zh_body'] else 0} for e in eps]
    (out / 'data').mkdir(exist_ok=True)
    (out / 'data' / 'episodes.json').write_text(json.dumps({'updated': date.today().isoformat(), 'episodes': data},
                                                           ensure_ascii=False, separators=(',', ':')))
    title = f'{cfg["name"]} 中文精读 · {cfg["cn"]} · 全部 {len(eps)} 期'
    desc = f'{cfg["name"]}（{cfg["hosts"]}）全部 {len(eps)} 期节目中文导航与 {n_zh} 篇中文精读：{cfg["tagline"]}。含视频、音频、英文文稿，支持搜索与 RSS 全文订阅。'
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": f'https://{d}/#website', "name": f'{cfg["name"]} 中文精读', "url": f'https://{d}/',
         "description": desc, "inLanguage": "zh-CN", "publisher": {"@id": f'https://{d}/#org'},
         "potentialAction": {"@type": "SearchAction", "target": f'https://{d}/?q={{search_term_string}}',
                             "query-input": "required name=search_term_string"}},
        {"@type": "Organization", "@id": f'https://{d}/#org', "name": f'{cfg["name"]} 中文精读', "url": f'https://{d}/',
         "logo": f'https://{d}/icon-512.png',
         "founder": {"@type": "Person", "name": "向阳乔木", "url": "https://x.com/vista8"}},
        {"@type": "PodcastSeries", "name": cfg['full_name'], "url": cfg['official'], "author": cfg['hosts']},
        {"@type": "ItemList", "name": "最新单集", "numberOfItems": len(eps),
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f'https://{d}{e["url"]}', "name": card_title(e)}
                             for i, e in enumerate(eps[:30])]},
    ]}
    page = head(cfg, title=title, desc=desc, url=f'https://{d}/', og_img=f'https://{d}/og/default.jpg', ld=ld)
    page += f"""
<header class="masthead">
  <div class="wrap">
    <div class="mast-top"><span class="mast-date" id="mastDate"></span>
      <span class="mast-actions"><a class="mast-link" href="/archive/">单集目录</a><a class="mast-link" href="/feed.xml">RSS 订阅</a>{THEME_BTN}</span></div>
    <div class="mast-brand">
      <div class="mast-kicker">{esc(cfg['cn'])} · 中文精读</div>
      <h1 class="mast-title"><a href="/">{esc(cfg['name'])}</a></h1>
      <p class="mast-tagline">{esc(cfg['tagline'])}</p>
    </div>
    <div class="mast-facts">
      <div><b>{len(eps)}</b><span>期节目</span></div>
      <div><b>{n_zh}</b><span>篇中文精读</span></div>
      <div><b>{hours}</b><span>小时对话</span></div>
      <div><b>{since}</b><span>年开播</span></div>
    </div>
    <p class="mast-intro">{esc(cfg['intro'])}<span class="mast-hosts">主持：{esc(cfg['hosts'])}</span></p>
  </div>
</header>

<div class="toolbar">
  <div class="wrap toolbar-inner" role="search">
    <div class="search-box">
      <svg class="i-search" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
      <input id="search" type="search" enterkeyhint="search" placeholder="搜索嘉宾、公司、话题、期数…" autocomplete="off" spellcheck="false" aria-label="搜索单集">
      <kbd class="search-kbd" aria-hidden="true">/</kbd>
      <button type="button" class="search-clear" aria-label="清除搜索">清除</button>
    </div>
    <div class="filters" id="filters" role="group" aria-label="筛选">
      <button type="button" data-f="all" class="on" aria-pressed="true">全部</button>
      <button type="button" data-f="zh" aria-pressed="false">中文精读<span class="n" data-n="zh"></span></button>
      <button type="button" data-f="tr" aria-pressed="false" hidden>有文稿<span class="n" data-n="tr"></span></button>
      <button type="button" data-f="hist" aria-pressed="false" hidden>看过<span class="n" data-n="hist"></span></button>
    </div>
    <button type="button" class="sort-btn" id="sort" data-dir="desc" aria-label="切换排序">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4v16M3.5 16.5L7 20l3.5-3.5M13 6h8M13 11h6M13 16h4"/></svg><span>最新</span>
    </button>
  </div>
</div>

<main class="wrap" id="main">
  <section class="hero" id="hero"{f' data-s="{latest["file"]}"' if latest else ' hidden'} aria-label="最新精读">{ssr_hero(cfg, latest) if latest else ''}</section>
  <section class="continue" id="continue" hidden aria-labelledby="cont-h">
    <div class="sec-h"><h2 id="cont-h">继续</h2><button type="button" id="contClear">清除记录</button></div>
    <div class="continue-row" id="contRow"></div>
  </section>
  <nav class="topics" aria-label="热门话题"><span class="topics-k">热门话题</span>{topic_chips(eps)}</nav>
  <div class="result-line" id="resultLine" aria-live="polite"><h2>全部单集<small>最新在前</small></h2></div>
  <div id="grid" class="grid">{''.join(ssr_card(cfg, e) for e in eps[:30])}</div>
  <div id="sentinel" class="sentinel"></div>
</main>
{footer(cfg)}
<script src="/site.js?v={V}"></script>
</body>
</html>
"""
    (out / 'index.html').write_text(page)


# ---------------------------------------------------------------- 单集页
COLOPHON = ('<aside class="colophon" aria-label="致读者"><div class="colo-k">致读者</div>'
            '<p>这篇精读来自一个人独立维护的非营利项目：从官方音频与文稿出发，经转写、AI 改写与逐篇校验，'
            '尽量把一两个小时的对话，压缩成一篇值得静心读完的中文长文。这里没有广告，也不设付费墙。'
            '如果它让你有所收获，欢迎请作者喝杯咖啡。</p>'
            '<div class="colo-actions"><button type="button" class="ft-btn" data-open="rewardModal">打赏支持</button>'
            '<button type="button" class="ft-btn ghost" data-open="followModal">关注公众号</button>'
            '<button type="button" class="colo-link" data-share>分享这篇</button>'
            '<a class="colo-link" href="/feed.xml">RSS 订阅更新</a></div></aside>')


def build_episode(cfg, eps, i, out, rel=()):
    e = eps[i]
    d = cfg['domain']
    url = f'https://{d}{e["url"]}'
    has_zh = bool(e['zh_body'])
    chars, read_min = zh_stats(e['zh_body']) if has_zh else (0, 0)
    h1 = card_title(e)
    label = f'{cfg["ep_label"]} {e["seq"]}'
    title = f'{h1} | {cfg["name"]} {label} 中文精读' if has_zh else f'{e["title"]} | {cfg["name"]} {label}'
    first = re.search(r'<p>(.*?)</p>', e['zh_body'], flags=re.S)
    desc = (e['zh_desc'] or (strip_tags(first.group(1))[:150] if first else e['desc'][:160])) or f'{cfg["name"]} {label}'

    kicker = [label] + ([f'<span class="k-zh">{esc(cfg["kicker_zh"])}</span>'] if has_zh else [])
    by = [x for x in [f'<time datetime="{e["date"]}">{fmt_date(e["date"])}</time>' if e['date'] else '',
                      f'<span>{fmt_dur(e["dur"])}</span>' if e['dur'] else '',
                      f'<span>主持 {esc(cfg["hosts"])}</span>'] if x]
    if read_min:
        wan = f'{chars / 10000:.1f} 万字' if chars >= 10000 else f'{chars} 字'
        by.append(f'<span>精读约 {wan} · 阅读 {read_min} 分钟</span>')

    audio_html = ''
    if e['audio']:
        audio_html = (f'<div class="audio-player" data-slug="{esc(e["file"])}" data-title="{esc(h1)}">'
                      f'<audio src="{esc(e["audio"])}" preload="none"></audio>'
                      f'<button class="ap-play" type="button" aria-label="播放">{ICON_PLAY}{ICON_PAUSE}</button>'
                      f'<div class="ap-mid"><div class="ap-line1"><span class="ap-label">节目音频</span>'
                      f'<span class="ap-time"><span class="ap-cur">00:00</span> / <span class="ap-dur">{fmt_clock(e["dur"])}</span></span></div>'
                      f'<div class="ap-bar" role="slider" aria-label="播放进度" tabindex="0"><div class="ap-buf"></div><div class="ap-fill"></div></div>'
                      f'<div class="ap-line2"><button type="button" class="ap-skip" data-s="-15" aria-label="后退 15 秒">−15s</button>'
                      f'<button type="button" class="ap-skip" data-s="15" aria-label="前进 15 秒">+15s</button>'
                      f'<button type="button" class="ap-rate" aria-label="播放速度">1×</button>'
                      f'<span class="ap-resume" hidden>已从上次位置继续 · <button type="button" class="ap-restart">从头听</button></span></div></div></div>')
    video_html = ''
    if e['yt']:
        video_html = (f'<button type="button" class="video-facade" data-yt="{esc(e["yt"])}" aria-label="播放 YouTube 视频">'
                      f'<img src="https://i.ytimg.com/vi/{e["yt"]}/mqdefault.jpg" alt="" width="320" height="180">'
                      f'<span class="vf-play">{ICON_PLAY}<span>看视频</span></span></button>')
    media = f'<div class="media{" has-audio" if audio_html else ""}">{video_html}{audio_html}</div>' if (audio_html or video_html) else ''

    tabs, panels = [], []
    if has_zh:
        tabs.append('<button class="tab-btn" type="button" data-tab="zh" role="tab" aria-controls="panel-zh">中文精读</button>')
        panels.append(f'<div class="tab-panel" id="panel-zh" data-panel="zh">'
                      f'<div class="zh-note">中文精读由 AI 基于原始访谈改写，非官方翻译，可能存在偏差或错误；表述以原节目为准。</div>'
                      f'<div class="zh-article">{e["zh_body"]}</div>{COLOPHON}</div>')
    if e['tr']:
        src = e['tr'].get('source_label') or (urlparse(e['tr'].get('source') or '').netloc.replace('www.', '') or '公开文稿')
        tabs.append('<button class="tab-btn" type="button" data-tab="tr" role="tab" aria-controls="panel-tr">英文文稿</button>')
        panels.append(f'<div class="tab-panel" id="panel-tr" data-panel="tr"><div class="tr-note">文稿来源：{esc(src)}；机器转写可能有识别错误，人名与数字请以音频为准。</div>'
                      f'<div class="transcript-text" lang="en">{esc(e["tr"]["text"])}</div></div>')
    if e['desc']:
        tabs.append('<button class="tab-btn" type="button" data-tab="desc" role="tab" aria-controls="panel-desc">节目简介</button>')
        panels.append(f'<div class="tab-panel" id="panel-desc" data-panel="desc"><div class="desc-body" lang="en">{para(e["desc"])}</div></div>')
    tabs_html = f'<div class="tabs" role="tablist">{"".join(tabs)}</div>' if tabs else ''

    res = ['<section class="ep-resources"><h2>本集资源与出处</h2><ul>']
    if e['yt']:
        res.append(f'<li><span class="res-k">视频</span><a href="https://www.youtube.com/watch?v={esc(e["yt"])}" target="_blank" rel="noopener">在 YouTube 收看</a></li>')
    if e['audio']:
        res.append(f'<li><span class="res-k">音频</span><a href="{esc(e["audio"])}" target="_blank" rel="noopener">节目 MP3 直链</a><span class="res-sub">来自官方播客 RSS</span></li>')
    if cfg.get('apple_id'):
        res.append(f'<li><span class="res-k">订阅</span><a href="https://podcasts.apple.com/us/podcast/id{cfg["apple_id"]}" target="_blank" rel="noopener">Apple Podcasts</a></li>')
    if e['link']:
        res.append(f'<li><span class="res-k">官网</span><a href="{esc(e["link"])}" target="_blank" rel="noopener">节目官方页面</a></li>')
    if has_zh:
        res.append(f'<li><span class="res-k">文本</span><a href="{e["url"][:-5]}.md" target="_blank" rel="noopener">精读 Markdown 版</a><span class="res-sub">便于引用与 AI 读取</span></li>')
    res.append('</ul></section>')

    def pn(x, k):
        if not x:
            return '<span></span>'
        return (f'<a href="{x["url"]}" rel="{k}"><span class="pn-k">{"← 上一期" if k == "prev" else "下一期 →"}</span>'
                f'<span class="pn-t">{esc(card_title(x))}</span></a>')
    prevnext = pn(eps[i + 1] if i + 1 < len(eps) else None, 'prev') + pn(eps[i - 1] if i > 0 else None, 'next')

    related = ''
    if rel:
        items = []
        for j in rel:
            x = eps[j]
            img = f'<img loading="lazy" src="https://i.ytimg.com/vi/{x["yt"]}/mqdefault.jpg" alt="" width="320" height="180">' if x['yt'] else ''
            _, rm = zh_stats(x['zh_body']) if x['zh_body'] else (0, 0)
            meta = f'{esc(cfg["ep_label"])} {x["seq"]}' + (f' · 精读 {rm} 分钟' if rm else '')
            items.append(f'<a class="rel-item" href="{x["url"]}"><span class="rel-thumb">{img}</span>'
                         f'<span class="rel-meta">{meta}</span><span class="rel-title">{esc(card_title(x))}</span></a>')
        related = f'<section class="related" aria-label="延伸阅读"><h2>延伸阅读</h2><div class="rel-grid">{"".join(items)}</div></section>'

    sections = [strip_tags(x).strip() for x in re.findall(r'<h2[^>]*>(.*?)</h2>', e['zh_body'], flags=re.S)]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "PodcastEpisode", "@id": f'{url}#episode', "url": url, "name": e['title'], "alternativeHeadline": e['zh_t'],
         "description": e['desc'][:500], "datePublished": e['date'], "episodeNumber": e['seq'], "inLanguage": "en",
         "timeRequired": f'PT{e["dur"]}S' if e['dur'] else None,
         "partOfSeries": {"@type": "PodcastSeries", "name": cfg['full_name'], "url": cfg['official']},
         "associatedMedia": [m for m in [
             {"@type": "AudioObject", "contentUrl": e['audio'], "encodingFormat": "audio/mpeg"} if e['audio'] else None,
             {"@type": "VideoObject", "embedUrl": f'https://www.youtube.com/embed/{e["yt"]}', "name": e['title'],
              "thumbnailUrl": f'https://i.ytimg.com/vi/{e["yt"]}/hqdefault.jpg', "uploadDate": e['date']} if e['yt'] else None] if m]},
        *([{"@type": "Article", "@id": f'{url}#article', "url": url, "headline": h1[:110], "alternativeHeadline": e['title'],
            "description": desc, "inLanguage": "zh-CN", "datePublished": e['zh_mtime'], "dateModified": e['zh_mtime'],
            "wordCount": chars, "timeRequired": f'PT{read_min}M', "image": f'https://{d}/og/{e["file"][:-5]}.jpg',
            "articleSection": sections[:30], "isBasedOn": {"@id": f'{url}#episode'}, "about": {"@id": f'{url}#episode'},
            "author": {"@type": "Person", "name": "向阳乔木", "url": "https://x.com/vista8"},
            "publisher": {"@type": "Organization", "name": f'{cfg["name"]} 中文精读', "url": f'https://{d}/',
                          "logo": {"@type": "ImageObject", "url": f'https://{d}/icon-512.png'}},
            "isAccessibleForFree": True, "mainEntityOfPage": url}] if has_zh else []),
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": f'{cfg["name"]} 中文精读', "item": f'https://{d}/'},
            {"@type": "ListItem", "position": 2, "name": h1[:60], "item": url}]},
    ]}
    extra = (f'<meta property="article:published_time" content="{e["date"]}">' if e['date'] else '')
    if has_zh:
        extra += (f'<meta property="article:modified_time" content="{e["zh_mtime"]}">'
                  f'<link rel="alternate" type="text/markdown" title="中文精读 Markdown" href="{e["url"][:-5]}.md">')
    page = head(cfg, title=title, desc=desc, url=url, og_img=f'https://{d}/og/{e["file"][:-5]}.jpg', og_type='article', extra=extra, ld=ld)
    page += f"""
{slim_header(cfg)}
<main class="wrap ep-main{' has-toc' if has_zh else ''}" id="main">
  <article class="ep">
    <header class="ep-head">
      <div class="ep-kicker">{'<span class="k-sep">·</span>'.join(kicker)}</div>
      <h1 class="ep-title">{esc(h1)}</h1>
      {f'<p class="ep-title-en" lang="en">{esc(e["title"])}</p>' if e['zh_t'] else ''}
      {f'<p class="ep-dek">{esc(e["zh_desc"])}</p>' if e['zh_desc'] else ''}
      <div class="ep-byline">{'<span class="k-sep">·</span>'.join(by)}</div>
    </header>
    {media}
    <section class="content-tabs">{tabs_html}{''.join(panels)}</section>
    {related}
    {''.join(res)}
    <nav class="ep-prevnext" aria-label="上一期 / 下一期">{prevnext}</nav>
  </article>
  <aside class="ep-toc" aria-label="精读目录"></aside>
</main>
{footer(cfg)}
<script src="/read.js?v={V}"></script>
</body>
</html>
"""
    dest = out / 'ep' / e['file']
    dest.write_text(page)
    if has_zh:
        md = [f'# {h1}', '', f'> {cfg["name"]} {label} 中文精读', '',
              f'- 原标题：{e["title"]}', f'- 发布日期：{e["date"]}', f'- 主持：{cfg["hosts"]}',
              f'- 网页版：{url}', f'- 精读字数：约 {chars} 字（阅读约 {read_min} 分钟）', '',
              f'> 本文为 {d} 基于原始访谈的 AI 改写中文精读，非官方翻译；引用请注明出处并链接网页版。', '']
        (out / 'ep' / (e['file'][:-5] + '.md')).write_text('\n'.join(md) + '\n' + html_to_md(e['zh_body']))


def fmt_clock(sec):
    if not sec:
        return '--:--'
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def html_to_md(h):
    h = re.sub(r'\s*<h2[^>]*>(.*?)</h2>\s*', lambda m: f'\n\n## {m.group(1)}\n\n', h, flags=re.S)
    h = re.sub(r'\s*<h3[^>]*>(.*?)</h3>\s*', lambda m: f'\n\n### {m.group(1)}\n\n', h, flags=re.S)
    h = re.sub(r'\s*<blockquote>(.*?)</blockquote>\s*',
               lambda m: '\n\n' + '\n'.join('> ' + ln for ln in re.sub(r'</?p>', '\n', m.group(1)).strip().splitlines() if ln.strip()) + '\n\n',
               h, flags=re.S)
    h = re.sub(r'\s*<li>(.*?)</li>\s*', lambda m: f'\n- {m.group(1).strip()}', h, flags=re.S)
    h = re.sub(r'</?(ul|ol)>', '\n', h)
    h = re.sub(r'<(strong|b)>(.*?)</\1>', r'**\2**', h, flags=re.S)
    h = re.sub(r'<(em|i)>(.*?)</\1>', r'*\2*', h, flags=re.S)
    h = re.sub(r'\s*<p>(.*?)</p>\s*', lambda m: f'\n\n{m.group(1).strip()}\n\n', h, flags=re.S)
    h = H.unescape(re.sub(r'<[^>]+>', '', h))
    return re.sub(r'\n{3,}', '\n\n', h).strip() + '\n'


# ---------------------------------------------------------------- 其他页面与资产
def build_archive(cfg, eps, out):
    d = cfg['domain']
    years = {}
    for e in eps:
        years.setdefault(e['date'][:4] or '0000', []).append(e)
    nav = ''.join(f'<a href="#y{y}">{y}</a>' for y in sorted(years, reverse=True))
    secs = []
    for y in sorted(years, reverse=True):
        rows = ''.join(
            f'<li><a href="{e["url"]}"><span class="ar-n">{e["seq"]}</span><span class="ar-t"><b>{esc(card_title(e))}</b>'
            f'{"<i lang=en>" + esc(e["title"]) + "</i>" if e["zh_t"] else ""}</span>'
            f'<span class="ar-d">{e["date"][5:10].replace("-", ".")}{"<span class=ar-zh>精读</span>" if e["zh_body"] else ""}</span></a></li>'
            for e in years[y])
        secs.append(f'<section class="ar-year" id="y{y}"><h2>{y}<small>{len(years[y])} 期</small></h2><ol>{rows}</ol></section>')
    title = f'单集目录 · 全部 {len(eps)} 期 · {cfg["name"]} 中文精读'
    desc = f'{cfg["name"]} 全部 {len(eps)} 期按年份排列的目录，含中文精读、音频、视频与英文文稿。'
    page = head(cfg, title=title, desc=desc, url=f'https://{d}/archive/', og_img=f'https://{d}/og/default.jpg',
                ld={"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": f'https://{d}/archive/', "inLanguage": "zh-CN"})
    page += f"""
{slim_header(cfg)}
<main class="wrap ar-main" id="main">
  <header class="ep-head"><div class="ep-kicker">单集目录</div><h1 class="ep-title">全部 {len(eps)} 期</h1>
    <p class="ep-dek">按年份排列；标有「精读」的单集附中文长文。</p></header>
  <nav class="ar-nav" aria-label="按年份跳转">{nav}</nav>
  {''.join(secs)}
</main>
{footer(cfg)}
</body>
</html>
"""
    (out / 'archive').mkdir(exist_ok=True)
    (out / 'archive' / 'index.html').write_text(page)


def build_special(cfg, eps, out):
    d = cfg['domain']
    picks = [e for e in eps if e['zh_body']][:4] or eps[:4]
    links = ''.join(f'<li><a href="{e["url"]}"><b>{esc(card_title(e))}</b><i>{esc(cfg["ep_label"])} {e["seq"]}</i></a></li>' for e in picks)
    for fn, (t, h1, dek, show) in {
        '404.html': ('页面不存在', '这一页没有找到', '链接可能写错了，或者那一期换了地址。试试搜索，或者从最新的几篇读起。', True),
        'offline.html': ('离线', '现在没有网络', '读过的文章已为你离线保存，可以返回上一页继续阅读；联网后会自动恢复。', False),
    }.items():
        page = head(cfg, title=f'{t} · {cfg["name"]} 中文精读', desc=dek, url=f'https://{d}/', og_img=f'https://{d}/og/default.jpg', robots='noindex')
        page += f"""
{slim_header(cfg)}
<main class="wrap ep-main special" id="main">
  <header class="ep-head"><div class="ep-kicker">{t}</div><h1 class="ep-title">{h1}</h1><p class="ep-dek">{dek}</p>
  <p class="special-actions"><a class="more-btn" href="/">回到首页</a><a class="more-btn ghost" href="/#search">搜索单集</a></p></header>
  {f'<section class="special-list"><h2>最新精读</h2><ol>{links}</ol></section>' if show else ''}
</main>
{footer(cfg)}
</body>
</html>
"""
        (out / fn).write_text(page)


def cdata(s):
    return '<![CDATA[' + (s or '').replace(']]>', ']]]]><![CDATA[>') + ']]>'


def build_feed(cfg, eps, out):
    """RSS 全文订阅：最新 30 期，有精读的输出中文全文，没有的输出节目简介；附音频 enclosure。"""
    d = cfg['domain']
    items = []
    for e in eps[:30]:
        url = f'https://{d}{e["url"]}'
        try:
            pub = format_datetime(datetime.fromisoformat(e['date']).replace(tzinfo=timezone.utc))
        except Exception:
            pub = ''
        if e['zh_body']:
            body = (f'<p><em>{esc(e["title"])}</em></p>' + e['zh_body'] +
                    f'<hr><p>原文链接：<a href="{url}">{url}</a> · 中文精读由 AI 改写，非官方翻译。</p>')
        else:
            body = para(e['desc']) + f'<p><a href="{url}">在 {d} 查看本期</a></p>'
        enc = f'<enclosure url="{esc(e["audio"])}" length="0" type="audio/mpeg"/>' if e['audio'] else ''
        items.append(f"""<item><title>{cdata(card_title(e))}</title><link>{url}</link><guid isPermaLink="true">{url}</guid>
<pubDate>{pub}</pubDate><description>{cdata(strip_tags(e['zh_body'] or e['desc'])[:300])}</description>
<content:encoded>{cdata(body)}</content:encoded>{enc}</item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{esc(cfg['name'])} 中文精读 · {esc(cfg['cn'])}</title>
<link>https://{d}/</link>
<atom:link href="https://{d}/feed.xml" rel="self" type="application/rss+xml"/>
<description>{esc(cfg['tagline'])}。每期中文精读全文 + 节目音频。非官方粉丝站点。</description>
<language>zh-cn</language>
<image><url>https://{d}/icon-512.png</url><title>{esc(cfg['name'])} 中文精读</title><link>https://{d}/</link></image>
<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
{''.join(items)}
</channel>
</rss>
"""
    (out / 'feed.xml').write_text(feed)


def build_seo(cfg, eps, out):
    d = cfg['domain']
    today = date.today().isoformat()
    urls = [(f'https://{d}/', today, '1.0'), (f'https://{d}/archive/', today, '0.7')]
    for e in eps:
        urls.append((f'https://{d}{e["url"]}', e['zh_mtime'] or e['date'] or today, '0.8' if e['zh_body'] else '0.6'))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f'<url><loc>{esc(u)}</loc><lastmod>{lm}</lastmod><priority>{p}</priority></url>' for u, lm, p in urls]
    sm.append('</urlset>')
    (out / 'sitemap.xml').write_text('\n'.join(sm))
    bots = ['GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'PerplexityBot', 'Google-Extended', 'Applebot-Extended', 'Bytespider']
    (out / 'robots.txt').write_text('# 欢迎搜索引擎与 AI 检索 / 问答引擎抓取。中文精读另有 Markdown 版本：把单集网址的 .html 换成 .md\n'
                                    'User-agent: *\nAllow: /\n\n' + ''.join(f'User-agent: {b}\nAllow: /\n' for b in bots) +
                                    f'\nSitemap: https://{d}/sitemap.xml\n')
    n_zh = sum(1 for e in eps if e['zh_body'])
    lines = [f'# {cfg["name"]} 中文精读（{d}）', '',
             f'> {cfg["full_name"]} 全部 {len(eps)} 期节目的中文导航站（非官方粉丝站点），主持：{cfg["hosts"]}。'
             f'每期独立页面，含节目音频、YouTube 视频、英文文稿与 AI 改写的中文精读（{n_zh} 篇）。内容版权归原节目所有。', '',
             '## 使用说明', '',
             f'- 每篇中文精读都有纯 Markdown 版本：把单集网址末尾的 .html 换成 .md',
             f'- 全部单集按年份的目录：https://{d}/archive/',
             f'- RSS 全文订阅：https://{d}/feed.xml',
             f'- 引用时请注明「{d} 中文精读（AI 改写，非官方翻译）」并链接对应网页。', '',
             '## 中文精读', '']
    lines += [f'- [{card_title(e)}](https://{d}{e["url"][:-5]}.md)：{e["title"]}' for e in eps if e['zh_body']]
    lines += ['', '## 全部单集', '']
    lines += [f'- [{e["title"]}](https://{d}{e["url"]})（{e["date"]}）' for e in eps]
    (out / 'llms.txt').write_text('\n'.join(lines) + '\n')


def build(slug):
    cfg = SHOWS[slug]
    eps = load_show(slug)
    out = SITES / slug
    keep = {'og'}  # 分享卡片增量生成，保留
    if out.exists():
        for p in out.iterdir():
            if p.name in keep:
                continue
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ep').mkdir(exist_ok=True)
    (out / 'assets').mkdir(exist_ok=True)
    for name in ('reward.png', 'wechat.jpg'):  # 打赏 / 公众号二维码
        shutil.copy(STATIC / 'assets' / name, out / 'assets' / name)
    if (DATA / slug / 'feed.xml').exists():  # 旧站链接过的官方 RSS 副本，保留以免失效
        shutil.copy(DATA / slug / 'feed.xml', out / 'assets' / 'feed.xml')
    css = (STATIC / 'base.css').read_text() + '\n' + (STATIC / 'themes' / f'{slug}.css').read_text()
    (out / 'style.css').write_text(css)
    for f in ('site.js', 'read.js'):
        shutil.copy(STATIC / f, out / f)
    (out / 'sw.js').write_text((STATIC / 'sw.js').read_text().replace("const VERSION = 'lex-v1'", f"const VERSION = '{slug}-v{V}'")
                               .replace("'/ep.js'", "'/read.js'").replace("'/app.js'", "'/site.js'"))
    rel = related_index(eps)
    for i in range(len(eps)):
        build_episode(cfg, eps, i, out, rel[i])
    build_index(cfg, eps, out)
    build_archive(cfg, eps, out)
    build_special(cfg, eps, out)
    build_feed(cfg, eps, out)
    build_seo(cfg, eps, out)
    import brand
    brand.build_assets(slug, cfg, eps, out)
    n_zh = sum(1 for e in eps if e['zh_body'])
    print(f'{slug}: {len(eps)} 期，精读 {n_zh} 篇 -> {out}')


if __name__ == '__main__':
    # 不带参数时构建所有有数据的站（单站开源仓库里只有自己那一份数据）
    for s in sys.argv[1:] or [k for k in SHOWS if (DATA / k / 'episodes.json').exists()]:
        build(s)
