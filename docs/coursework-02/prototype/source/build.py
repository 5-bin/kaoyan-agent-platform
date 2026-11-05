"""Build self-contained Modao HTML using bundled snapshots and Python's standard library."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
SNAPSHOTS = HERE / 'snapshots'
OUT = HERE.parent / 'html'
OUT.mkdir(parents=True, exist_ok=True)
templates = json.loads((SNAPSHOTS/'templates.json').read_text(encoding='utf-8'))
styles = (SNAPSHOTS/'styles.css').read_text(encoding='utf-8') + '\n' + (HERE/'prototype.css').read_text(encoding='utf-8')
script = (HERE/'prototype.js').read_text(encoding='utf-8')
data = json.dumps(templates, ensure_ascii=False).replace('</', '<\\/')
page_map = {
    '00_交互演示入口': 'index', 'A01_登录': 'login', 'A02_注册': 'register',
    'A03_首页': 'home', 'A04_个人中心': 'profile', 'A05_院校列表': 'schools',
    'A06_备考资料': 'documents', 'A07_个人笔记': 'notes', 'A08_院校详情': 'school-detail',
    'L01_练习首页': 'practice', 'L02_答题未判分': 'practice-session',
    'L03_答题已判分': 'practice-session-answered', 'L04_错题本': 'wrong',
    'L05_收藏': 'favorite', 'L06_Agent助手': 'assistant', 'L07_学习统计': 'stat',
    'M01_题目录入与审核': 'admin-questions', 'M02_资料审核': 'admin-documents',
    'L08_单选诊断': 'diagnostic', 'L09_批次结果': 'result',
}
for name, route in page_map.items():
    markup = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} · 考研Agent交互原型</title><style>{styles}</style></head>
<body><div id="prototype-root">{templates['home']}</div><div id="proto-modal-root"></div><div id="proto-toast" role="status"></div>
<script>const SNAPSHOTS={data};const INITIAL_ROUTE={json.dumps(route)};</script>
<script>{script}</script></body></html>'''
    (OUT/(name+'.html')).write_text(markup, encoding='utf-8')
manifest = {'baseline':'94b8a9fbcba2ae7ad6a9895a9623a0572ca18bf4',
            'mode':'offline HTML interactive prototype; no business API or model requests',
            'pages':[{'file':name+'.html','route':route} for name,route in page_map.items()]}
(HERE.parent/'page-map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
release = HERE.parent/'release'
release.mkdir(parents=True, exist_ok=True)
(release/'00_交互验收版_v2.html').write_bytes((OUT/'00_交互演示入口.html').read_bytes())
print(json.dumps({'pages':len(page_map),'css_bytes':len(styles),'template_bytes':len(data),'output':str(OUT)},ensure_ascii=False))
