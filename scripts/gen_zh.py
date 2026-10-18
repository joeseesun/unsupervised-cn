#!/usr/bin/env python3
"""Generate 中文精读 articles for podcast episodes via Magpie (deepseek-flash).

Input:  data/<slug>/transcripts/{seq:03d}.json
Output: data/<slug>/zh/{seq:03d}.html  (HTML fragment: h2/p/strong/ul/blockquote)

Usage: python3 scripts/gen_zh.py <slug> <seq> [more_seq ...]
       python3 scripts/gen_zh.py cogrev 387 386 385
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://magpie.qiaomu.ai/v1/chat/completions"
MODEL = __import__("os").environ.get("ZH_MODEL", "bigmodel-preview/glm-x-preview-f")
MAX_TOKENS = 24576
# glm-x-preview-f 的思考链无法通过请求参数关闭（thinking disabled 与
# chat_template_kwargs.enable_thinking=false 均被路由忽略），长文会先烧数万 token
# 思考才出正文，因此 glm 必须用大预算兜住（实测 40960 放行且 finish=stop）。
GLM_MAX_TOKENS = 40960
TEMPERATURE = 0.7

STYLE_PROMPT = """你是向阳乔木，中文科技内容作者，为英文播客单集写一篇中文精读文章。

写作风格（必须遵守）：
- 口语化对话感、短段落多留白、生活化类比、第三人称、真诚不装、数据案例支撑、直接陈述事实不贴标签。
- 开头必须有靠信息量的钩子（用具体数字、事件或反差事实切入，禁止空洞渲染）。
- 结尾给可操作的行动结论（读者明天就能用上的东西）。
- 重要观点加粗（用 <strong>）。
- 全程中文标点。
- 忠实度：保留关键数据和结论；合理还原 ASR 错误的人名术语（按公开资料写对）。

禁用句式（出现即算失败）：
- 「不是……而是……」
- 「想象一下」「你有没有想过」「值得注意的是」「不难理解」「毋庸置疑」
- 「随着……的发展」「对于……来说」「在……方面」
- 贴标签式开场（如「这是一个反直觉的数字」）
- 预告式渲染（如「最让我吃惊的是」）
- 机械的「这说明」总结句式

禁用词汇：精准打击、赋能、落地、深度融合、全面布局、强势崛起。

格式禁令：
- 禁止中英文破折号（—— 和 —），需要停顿就拆句或用逗号。
- 禁止水平分隔线（--- 或 ***）。
- 禁止 emoji。

输出格式（严格遵守，直接输出 HTML 片段，不要 markdown 代码块包裹）：
- 第一行：<h2>《文章标题》</h2>（标题要具体、有信息量，像「29胜0负的哈比布，把冠军这件事讲透了」，禁止标题党空话）
- 正文：若干 <p> 段落；可用 <h2> 小节标题（3 到 6 个）；重要观点用 <strong>；可少量使用 <ul><li>；引用嘉宾原话可用 <blockquote>。
- 只允许这些标签：h2, p, strong, ul, li, blockquote。
- 篇幅 4500 到 6500 中文字符。信息密度要高，优先覆盖：嘉宾是谁、核心论点、关键数据、具体案例、分歧与反直觉观点、可操作结论。"""

BANNED = [
    r"不是[^。]{0,30}而是",
    r"想象一下", r"你有没有想过", r"值得注意的是", r"不难理解", r"毋庸置疑",
    r"随着[^。]{0,20}的发展", r"对于[^。]{0,15}来说", r"在[^。]{0,12}方面",
    r"这说明",
    r"精准打击", r"赋能", r"落地", r"深度融合", r"全面布局", r"强势崛起",
    r"——", r"—", r"<hr", r"---",
]
ALLOWED_TAGS = {"h2", "p", "strong", "ul", "li", "blockquote"}


def get_key():
    return subprocess.run(
        ["security", "find-generic-password", "-s", "qiaomu-llm", "-a", "magpie", "-w"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def chat(messages, key, timeout=900, model=None):
    M = model or MODEL
    payload = {
        "model": M,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "stream": True,
    }
    if "glm" in M.lower():
        payload["stream"] = False
        payload["max_tokens"] = GLM_MAX_TOKENS
    body = json.dumps(payload).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    if "glm" in M.lower():
        stem = "<h2>《"
        content, finish = "", None
        tmo = max(timeout, 1500)  # 40960 预算 + 思考链，单次可能 500s+
        for _ in range(4):
            if content:
                msgs = list(messages) + [
                    {"role": "assistant", "content": stem + content},
                    {"role": "user", "content": "从被截断处继续输出剩余部分，不要重复已有内容，不要重新开头。"},
                ]
            else:
                msgs = list(messages) + [{"role": "assistant", "content": stem}]
            payload["messages"] = msgs
            body = json.dumps(payload).encode()
            req = urllib.request.Request(BASE, data=body, headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            })
            resp = json.loads(urllib.request.urlopen(req, timeout=tmo).read())
            ch = (resp.get("choices") or [{}])[0]
            piece = (ch.get("message") or {}).get("content") or ""
            finish = ch.get("finish_reason")
            content += piece
            if finish != "length" or not piece:
                break
        return stem + content, finish
    out = []
    finish = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            delta = (obj.get("choices") or [{}])[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                out.append(piece)
            fr = ((obj.get("choices") or [{}])[0].get("finish_reason"))
            if fr:
                finish = fr
    return "".join(out), finish


def check(text):
    problems = []
    plain = re.sub(r"<[^>]+>", "", text)
    n_cjk = len(re.findall(r"[\u4e00-\u9fff]", plain))
    if n_cjk < 2800:
        problems.append(f"too short ({n_cjk} cjk chars)")
    for pat in BANNED:
        m = re.search(pat, plain)
        if m:
            problems.append(f"banned pattern {pat!r} -> {plain[max(0,m.start()-12):m.end()+12]!r}")
    tags = set(re.findall(r"<\s*([a-z0-9]+)", text))
    bad_tags = tags - ALLOWED_TAGS
    if bad_tags:
        problems.append(f"bad tags: {bad_tags}")
    if text.strip().startswith("```"):
        problems.append("wrapped in code fence")
    return n_cjk, problems


SHOW_NAMES = {
    "nopriors": "No Priors(主持人 Sarah Guo 与 Elad Gil,投资人与连续创业者,访谈 AI 创业者和前沿实验室研究者)",
    "cogrev": "Cognitive Revolution(主持人 Nathan Labenz,创业者与 AI 投资人,深度讨论模型能力、安全与应用)",
    "trainingdata": "Training Data(Sequoia Capital 出品,采访 AI 公司创始人与研究者,偏产品与商业落地)",
    "unsupervised": "Unsupervised Learning(Redpoint Ventures 的 Jacob Effron 主持,访谈 AI 研究者与创业者)",
}


def gen_one(slug, seq, key, model=None, max_chars=120000):
    tr_p = ROOT / "data" / slug / "transcripts" / f"{seq:03d}.json"
    if not tr_p.exists():
        alt = Path("/tmp/pod_out") / slug / "transcripts" / f"{seq:03d}.json"
        if alt.exists():
            tr_p = alt
    ep_d = json.loads((ROOT / "data" / slug / "episodes.json").read_text())
    eps = ep_d["episodes"]
    n = len(eps)
    ep = eps[n - seq]
    if not tr_p.exists():
        print(f"[{slug} #{seq}] 文稿缺失,跳过: {tr_p.name}", flush=True)
        return None, "missing"
    tr = json.loads(tr_p.read_text())
    show = SHOW_NAMES.get(slug, slug)
    title = ep["title"]
    guest = title
    transcript = tr["text"]
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars]
    user_msg = (
        f"播客:{show}\n单集标题:{title}\n发布日期:{ep.get('date','')}\n\n"
        f"下面是这一集的英文原始文稿(可能含自动转写错误):\n\n{transcript}"
    )
    messages = [
        {"role": "system", "content": STYLE_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    text, finish = chat(messages, key, model=model)
    return text, finish


def main():
    slug = sys.argv[1]
    seqs = [int(x) for x in sys.argv[2:]]
    key = get_key()
    zh_dir = ROOT / "data" / slug / "zh"
    zh_dir.mkdir(exist_ok=True)
    for seq in seqs:
        out = zh_dir / f"{seq:03d}.html"
        if out.exists():
            print(f"{slug}/{seq}: exists, skip", flush=True)
            continue
        t0 = time.time()
        try:
            text, finish = gen_one(slug, seq, key)
        except Exception as e:
            print(f"{slug}/{seq}: ERROR {type(e).__name__}: {str(e)[:120]}", flush=True)
            continue
        if text is None:
            continue
        if not text.strip():
            print(f"{slug}/{seq}: EMPTY (finish={finish})", flush=True)
            continue
        n_cjk, problems = check(text)
        if problems:
            print(f"{slug}/{seq}: finish={finish} {n_cjk}字 PROBLEMS:", flush=True)
            for p in problems:
                print(f"   - {p}", flush=True)
        else:
            print(f"{slug}/{seq}: finish={finish} {n_cjk}字 OK", flush=True)
        text = re.sub(r"^```html\s*|\s*```$", "", text.strip())
        out.write_text(text.strip() + "\n")
        try:
            mirror = Path("/tmp/pod_out") / slug / "zh" / out.name
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_text(text.strip() + "\n")
        except OSError:
            pass
        print(f"{slug}/{seq}: saved in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
