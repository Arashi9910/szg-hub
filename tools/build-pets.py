#!/usr/bin/env python3
"""把 tools/pets/<怪物>/<動作>_<n>.png 轉成 base64，寫進 dashboard.html 的 pets-data 區塊。
換圖或加新怪物：把 png 放進 tools/pets/<名字>/，重跑 python3 tools/build-pets.py。"""
import os, re, json, base64, glob, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pets = {}
for d in sorted(glob.glob(os.path.join(root, 'tools', 'pets', '*'))):
    if not os.path.isdir(d): continue
    acts = {}
    for f in glob.glob(os.path.join(d, '*.png')):
        m = re.match(r'(\w+?)_(\d+)\.png$', os.path.basename(f))
        if not m: continue
        acts.setdefault(m.group(1), []).append((int(m.group(2)), 'data:image/png;base64,' + base64.b64encode(open(f, 'rb').read()).decode()))
    pets[os.path.basename(d)] = {k: [u for _, u in sorted(v)] for k, v in acts.items()}
p = os.path.join(root, 'dashboard.html'); s = open(p, encoding='utf-8').read()
a, b = '// <pets-data>（tools/build-pets.py 產生，不要手改）\n', '// </pets-data>\n'
if a not in s or b not in s: sys.exit('[中止] dashboard.html 找不到 pets-data 區塊')
i = s.index(a) + len(a); j = s.index(b)
s = s[:i] + 'const PET_IMG = ' + json.dumps(pets, separators=(',', ':')) + ';\n' + s[j:]
open(p, 'w', encoding='utf-8').write(s)
print('寫入', {k: {a: len(v) for a, v in x.items()} for k, x in pets.items()})
