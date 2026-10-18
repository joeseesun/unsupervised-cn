"""四个站点的节目信息与视觉主题。

视觉差异集中在三处：themes/<slug>.css（版式与装饰）、这里的字体 / 配色 / 文案、brand.py 的图标与分享卡片。
能力（搜索、阅读设置、PWA、RSS、SEO…）全部共用 build.py 与 static/ 下的脚本。
"""

GF = 'https://fonts.googleapis.cn/css2?'

SHOWS = {
    'nopriors': {
        'domain': 'nopriors.qiaomu.ai',
        'name': 'No Priors',
        'cn': 'AI 创投前沿',
        'full_name': 'No Priors: Artificial Intelligence | Technology | Startups',
        'hosts': 'Sarah Guo & Elad Gil',
        'tagline': '从投资人视角聊 AI 创业和前沿实验室',
        'intro': ('No Priors 由 Conviction 创始人 Sarah Guo 与连续创业者、投资人 Elad Gil 共同主持。'
                  '两人都是深耕 AI 的投资人，每期与前沿实验室掌门人、明星创业者对话，讨论大模型走向、'
                  '创业机会与技术判断，信息密度高、观点直接。'),
        'apple_id': '1668002688',
        'youtube': 'https://www.youtube.com/@NoPriorsPodcast',
        'official': 'https://www.nopriors.video/',
        'umami': 'f0ed0886-b9e6-46b2-b0ba-b33e6451879d',
        # 视觉：深色终端 / 瑞士网格
        'style': 'terminal',
        'default_theme': 'dark',
        'default_font': 'sans',
        'bg': {'light': '#f6f7f2', 'sepia': '#f1ecdf', 'dark': '#0b0c0a'},
        'fonts': GF + 'family=JetBrains+Mono:wght@400;600;700&family=Inter+Tight:wght@500;700;800&family=Noto+Sans+SC:wght@500;700;900&display=swap',
        'ep_label': 'EP',
        'kicker_zh': '中文精读',
        'motto': '把最聪明的投资人和建造者的对话，翻成你能马上用上的判断。',
    },
    'cogrev': {
        'domain': 'cogrev.qiaomu.ai',
        'name': 'Cognitive Revolution',
        'cn': 'AI 深度研究',
        'full_name': '"The Cognitive Revolution" | AI Builders, Researchers, and Live Player Analysis',
        'hosts': 'Nathan Labenz',
        'tagline': '模型能力、安全与应用，聊得很细的 AI 深度访谈',
        'intro': ('Cognitive Revolution 由创业者、AI 投资人 Nathan Labenz 主持，聚焦 AI 研究者与建造者：'
                  '模型能力评测、AI 安全、Agent 与行业应用，每期都把技术细节聊透，并配有定期的 AI 前沿扫描。'),
        'apple_id': '1669813431',
        'youtube': 'https://www.youtube.com/channel/UCjNRVMBVI30Sak_p6HRWhIA',
        'official': 'https://www.cognitiverevolution.ai/',
        'umami': '5cdb2394-9301-433c-89b5-31ebe9af49c6',
        # 视觉：学术期刊（Distill）
        'style': 'journal',
        'default_theme': 'light',
        'default_font': 'serif',
        'bg': {'light': '#fbfaf6', 'sepia': '#f4ecd9', 'dark': '#14161b'},
        'fonts': GF + 'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;0,6..72,700;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&family=Noto+Serif+SC:wght@500;700&display=swap',
        'ep_label': 'No.',
        'kicker_zh': '精读',
        'motto': '把一线研究者讲到最细的地方，用中文认真写下来。',
    },
    'trainingdata': {
        'domain': 'trainingdata.qiaomu.ai',
        'name': 'Training Data',
        'cn': '红杉 AI 对话',
        'full_name': 'Training Data | Sequoia Capital',
        'hosts': 'Sonya Huang · Pat Grady · Konstantine Buhler 等',
        'tagline': '红杉资本对话 AI 公司创始人与研究者，偏产品与商业落地',
        'intro': ('Training Data 是红杉资本（Sequoia Capital）的官方播客。投资人 Sonya Huang、Pat Grady、'
                  'Konstantine Buhler 等与 AI 公司创始人和研究者对谈，覆盖从模型公司到应用层的商业落地、'
                  '产品策略与市场判断，是理解 AI 产业化的第一手视角。'),
        'apple_id': '1750736528',
        'youtube': 'https://www.youtube.com/playlist?list=PLOhHNjZItNnMm5tdW61JpnyxeYH5NDDx8',
        'official': 'https://www.sequoiacap.com/podcast/',
        'umami': '73191368-28a5-4630-9377-bafeff17261d',
        # 视觉：私人银行年报
        'style': 'ledger',
        'default_theme': 'light',
        'default_font': 'serif',
        'bg': {'light': '#f4efe4', 'sepia': '#efe5cf', 'dark': '#0f1a14'},
        'fonts': GF + 'family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Noto+Serif+SC:wght@500;700;900&display=swap',
        'ep_label': 'No.',
        'kicker_zh': '中文精读',
        'motto': '与创始人坐下来，慢慢谈一家 AI 公司的来龙去脉。',
    },
    'unsupervised': {
        'domain': 'unsupervised.qiaomu.ai',
        'name': 'Unsupervised Learning',
        'cn': 'AI 研究者访谈',
        'full_name': 'Unsupervised Learning with Jacob Effron | Redpoint',
        'hosts': 'Jacob Effron',
        'tagline': 'Redpoint 视角的 AI 研究者与创业者访谈',
        'intro': ('Unsupervised Learning 是红点创投（Redpoint）的 AI 播客，由合伙人 Jacob Effron 主持。'
                  '每期与 AI 研究者、创业者对谈前沿模型动态、开源生态与商业化路径，常有 OpenAI、DeepMind、Cohere 等一线人物出镜。'),
        'apple_id': '1672188924',
        'youtube': 'https://www.youtube.com/channel/UCUl-s_Vp-Kkk_XVyDylNwLA',
        'official': 'https://www.redpoint.com/unsupervised-learning/',
        'umami': 'b34ab290-873b-43c7-9fa6-e20762291a29',
        # 视觉：包豪斯海报
        'style': 'bauhaus',
        'default_theme': 'light',
        'default_font': 'sans',
        'bg': {'light': '#f2eee6', 'sepia': '#efe6d2', 'dark': '#121212'},
        'fonts': GF + 'family=Archivo:wght@500;700;800;900&family=Noto+Sans+SC:wght@500;700;900&display=swap',
        'ep_label': '#',
        'kicker_zh': '中文精读',
        'motto': '不预设答案，跟着研究者把问题推到底。',
    },
}
