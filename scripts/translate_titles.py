#!/usr/bin/env python3
"""给四个播客的每一期生成中文标题与一句话中文简介。

输出 data/<slug>/translations.json：{episode_id: {"zh": 中文标题, "desc": 一句话简介}}
增量保存、断点续跑；新增单集重跑即可只翻新的。走 Magpie 网关（密钥在 macOS 钥匙串）。

用法：python3 scripts/translate_titles.py [slug ...]
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
API = 'https://magpie.qiaomu.ai/v1/chat/completions'
MODELS = ['trae-cn/deepseek-v4.1-flash', 'opencode-go/deepseek-v4.1-flash', 'workbuddy/deepseek-v4.1-flash']
BATCH = 12
KEY = subprocess.run(['security', 'find-generic-password', '-s', 'qiaomu-llm', '-a', 'magpie', '-w'],
                     capture_output=True, text=True).stdout.strip()
assert KEY, 'keychain key not found'

SHOW = {
    'nopriors': 'No Priors（Sarah Guo 与 Elad Gil 主持的 AI 创投播客）',
    'cogrev': 'The Cognitive Revolution（Nathan Labenz 主持的 AI 深度研究播客）',
    'trainingdata': 'Training Data（红杉资本的 AI 播客）',
    'unsupervised': 'Unsupervised Learning（红点创投 Jacob Effron 主持的 AI 播客）',
}

PROMPT = """你是资深科技播客中文编辑。下面是 {show} 若干期节目（JSON 数组，项含 id / title / desc：英文标题与英文简介开头）。
为每一项生成两个字段：
- zh：中文标题，18-36 字，准确传达这期的核心内容，像一篇中文科技长文的标题那样有信息量、读起来顺；
  嘉宾与公司名：知名的用通行中文译名（OpenAI、Anthropic、英伟达、红杉等），人名首次出现可写「中文名（英文名）」或直接保留英文；
  技术术语用中文圈通行说法，AI / Agent / RL / GPU 等可保留；不要书名号，不要感叹号，不要「本期」「对话」这类空词开头。
- desc：一句话中文简介（30-60 字），说清楚聊了什么、谁来聊；不要营销腔。
只输出 JSON 对象：{{"items":[{{"id":"...","zh":"...","desc":"..."}}]}}，不要输出其他任何文字。"""


def post(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        content = json.load(r)['choices'][0]['message']['content']
    content = content.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    return {it['id']: {'zh': it['zh'].strip().strip('《》'), 'desc': it['desc'].strip()}
            for it in json.loads(content).get('items', []) if it.get('id') and it.get('zh') and it.get('desc')}


def call(slug, items, attempt):
    body = {'model': MODELS[(attempt - 1) % len(MODELS)], 'temperature': 0.3, 'max_tokens': 6000,
            'messages': [{'role': 'user', 'content': PROMPT.format(show=SHOW[slug]) + '\n\n输入：\n' + json.dumps(items, ensure_ascii=False)}]}
    try:
        return post({**body, 'response_format': {'type': 'json_object'}})
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return post(body)
        raise


def run(slug):
    out = DATA / slug / 'translations.json'
    done = json.loads(out.read_text()) if out.exists() else {}
    eps = json.loads((DATA / slug / 'episodes.json').read_text())['episodes']
    todo = [e for e in eps if e['id'] not in done]
    print(f'{slug}: total {len(eps)}, done {len(done)}, todo {len(todo)}', flush=True)
    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]

    def work(chunk):
        items = [{'id': e['id'], 'title': e['title'], 'desc': (e.get('description') or '')[:400]} for e in chunk]
        for attempt in range(1, 5):
            try:
                got = call(slug, items, attempt)
                if got:
                    return got
            except Exception as ex:  # noqa: BLE001
                print(f'  {slug} retry {attempt}: {type(ex).__name__} {str(ex)[:80]}', flush=True)
            time.sleep(2 * attempt)
        return {}

    with ThreadPoolExecutor(4) as ex:
        for got in ex.map(work, chunks):
            done.update(got)
            out.write_text(json.dumps(done, ensure_ascii=False, indent=0))
    miss = [e['id'] for e in eps if e['id'] not in done]
    print(f'{slug}: FINISHED {len(done)}/{len(eps)} missing={len(miss)}', flush=True)


if __name__ == '__main__':
    slugs = sys.argv[1:] or list(SHOW)
    with ThreadPoolExecutor(len(slugs)) as ex:
        list(ex.map(run, slugs))
