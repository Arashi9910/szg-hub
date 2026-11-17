#!/usr/bin/env python3
"""把私人版（szg-hub）轉成公開版（szg-hub-public）：拿掉遠端模式／通行碼／Tailscale，更新來源改成公開 repo。
用法：python3 tools/make-public.py <私人版資料夾> <公開版資料夾>
公開版的 README.md、.gitignore 不會被覆蓋（公開版自己維護）。任何一個替換對不上就中止，避免默默漏掉。"""
import sys, os, shutil, json

src, dst = sys.argv[1], sys.argv[2]
FILES = ['server.js', 'market.js', 'extdb.js', 'update.js', 'agent.js', 'dashboard.html', 'szg-hub.user.js', 'version.json', 'quiz-bank.json', 'start.bat']

def edit(text, pairs, name):
    for a, b in pairs:
        if a not in text:
            sys.exit(f'[中止] {name} 找不到要替換的片段：{a[:80]!r}')
        text = text.replace(a, b, 1)
    return text

def cut(text, start, end, name, keep_end=True):
    if start not in text or end not in text:
        sys.exit(f'[中止] {name} 找不到區塊：{start[:60]!r}')
    i = text.index(start); j = text.index(end, i)
    return text[:i] + (text[j:] if keep_end else text[j + len(end):])

for f in FILES:
    shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))

p = os.path.join(dst, 'server.js'); s = open(p, encoding='utf-8').read()
s = cut(s, "function isLocal(req) {", "let db = { chars:", 'server.js')
s = edit(s, [
    ("// REMOTE=1 時開放外部連線（例如 Tailscale）；外部連線一律要帶通行碼，本機連線不用。\nconst REMOTE = process.env.REMOTE === '1';\nconst HOST = REMOTE ? '0.0.0.0' : '127.0.0.1';", "// 只接受本機連線\nconst HOST = '127.0.0.1';"),
    ("const TOKEN_FILE = path.join(DATA_DIR, 'token.txt');\n", ""),
    ("let TOKEN = '';\ntry { TOKEN = fs.readFileSync(TOKEN_FILE, 'utf8').trim(); } catch (_) {}\nif (!TOKEN) {\n  TOKEN = crypto.randomBytes(12).toString('hex');\n  try { fs.writeFileSync(TOKEN_FILE, TOKEN); } catch (_) { console.warn('[警告] 通行碼無法存檔，重開伺服器後會換一組。'); }\n}\n", ""),
    ("    if (!isLocal(req) && !tokenOk(req, url)) return send(res, 401, { error: '需要通行碼' });\n", ""),
    ("    if (req.method === 'GET' && url.pathname === '/remote.user.js') {\n      return send(res, 200, remoteUserscript(req.headers.host), 'text/javascript; charset=utf-8');\n    }\n", ""),
    ("      if (!isLocal(req)) return send(res, 403, { error: '只能在家裡電腦上更新' });\n", ""),
    ("const os = require('os');\n", ""),
    ("'Access-Control-Allow-Headers': 'Content-Type, X-Hub-Token',", "'Access-Control-Allow-Headers': 'Content-Type',"),
], 'server.js')
s = cut(s, "  if (REMOTE) {", "  console.log('');\n  console.log('保持這個視窗開著", 'server.js')
for bad in ['REMOTE', 'TOKEN', 'isLocal', 'tokenOk', 'Tailscale', 'remote.user.js']:
    if bad in s: sys.exit(f'[中止] server.js 還留有 {bad}')
open(p, 'w', encoding='utf-8').write(s)

p = os.path.join(dst, 'dashboard.html'); s = open(p, encoding='utf-8').read()
s = edit(s, [("// 遠端開啟面板時（網址帶 ?token=），所有 API 請求都附上通行碼\nconst HUB_TOKEN = new URLSearchParams(location.search).get('token') || '';\nconst _fetch = window.fetch.bind(window);\nwindow.fetch = (u, o = {}) => HUB_TOKEN ? _fetch(u, { ...o, headers: { ...(o.headers || {}), 'X-Hub-Token': HUB_TOKEN } }) : _fetch(u, o);\n", "")], 'dashboard.html')
open(p, 'w', encoding='utf-8').write(s)

p = os.path.join(dst, 'szg-hub.user.js'); s = open(p, encoding='utf-8').read()
s = edit(s, [("const TOKEN = ''; // 只有遠端版需要；家裡本機用不到", "const TOKEN = ''; // 保留欄位，不需要填")], 'szg-hub.user.js')
open(p, 'w', encoding='utf-8').write(s)

p = os.path.join(dst, 'agent.js'); s = open(p, encoding='utf-8').read()
s = edit(s, [("el.textContent = '中控：通行碼錯誤，請重裝遠端腳本'", "el.textContent = '中控：伺服器拒絕連線'")], 'agent.js')
open(p, 'w', encoding='utf-8').write(s)

p = os.path.join(dst, 'update.js'); s = open(p, encoding='utf-8').read()
s = edit(s, [("const OWNER_REPO = 'Arashi9910/szg-hub';", "const OWNER_REPO = 'Arashi9910/szg-hub-public';"),
             ("new Set(['start.bat', 'start-remote.bat'])", "new Set(['start.bat'])")], 'update.js')
open(p, 'w', encoding='utf-8').write(s)

v = json.load(open(os.path.join(dst, 'version.json'), encoding='utf-8'))
v['files'] = [f for f in v['files'] if f != 'start-remote.bat']
json.dump(v, open(os.path.join(dst, 'version.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('公開版已產生：', v['version'])
