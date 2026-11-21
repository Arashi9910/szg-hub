#!/usr/bin/env python3
"""把私人版（szg-hub）轉成公開版（szg-hub-public）：拿掉遠端模式（REMOTE=1、共用通行碼、遠端腳本），更新來源改成公開 repo。
手機版（/m，經 tailscale serve、每支手機各自的通行碼）公開版也有。
用法：python3 tools/make-public.py <私人版資料夾> <公開版資料夾>
公開版的 README.md、.gitignore 不會被覆蓋（公開版自己維護）。任何一個替換對不上就中止，避免默默漏掉。"""
import sys, os, shutil, json

src, dst = sys.argv[1], sys.argv[2]
FILES = ['server.js', 'market.js', 'extdb.js', 'update.js', 'agent.js', 'dashboard.html', 'm.html', 'szg-hub.user.js', 'version.json', 'quiz-bank.json', 'start.bat']

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
# 共享題庫的 Apps Script（讓別人自己架一份）
os.makedirs(os.path.join(dst, 'tools'), exist_ok=True)
shutil.copyfile(os.path.join(src, 'tools', 'quiz-share.gs'), os.path.join(dst, 'tools', 'quiz-share.gs'))

# 只在私人版的功能：程式裡用 <private:名稱> … </private:名稱> 包起來（整行標記，JS 用 // 、HTML 用 <!-- -->），公開版整段拿掉
import re
PRIV = re.compile(r'^[^\n]*<private:(\w+)>[^\n]*\n[\s\S]*?^[^\n]*</private:\1>[^\n]*\n', re.M)
for f in FILES:
    if not f.endswith(('.js', '.html')): continue
    p = os.path.join(dst, f); s = open(p, encoding='utf-8').read()
    s2 = PRIV.sub('', s)
    if '<private:' in s2 or '</private:' in s2: sys.exit(f'[中止] {f} 的私人區塊標記沒有成對')
    if s2 != s: open(p, 'w', encoding='utf-8').write(s2)

p = os.path.join(dst, 'server.js'); s = open(p, encoding='utf-8').read()
# 遠端版腳本（REMOTE=1 給別台電腦的遊戲分頁用）只在私人版；isLocal／tokenOk 留著給手機版
s = cut(s, "// 依連進來的位址，產生已填好連線位址與通行碼的遠端版腳本", "let db = { chars:", 'server.js')
s = edit(s, [
    ("// REMOTE=1 時開放外部連線（例如 Tailscale）；外部連線一律要帶通行碼，本機連線不用。\nconst REMOTE = process.env.REMOTE === '1';\nconst HOST = REMOTE ? '0.0.0.0' : '127.0.0.1';", "// 只接受本機連線\nconst HOST = '127.0.0.1';"),
    ("const TOKEN_FILE = path.join(DATA_DIR, 'token.txt');\n", ""),
    ("let TOKEN = '';\ntry { TOKEN = fs.readFileSync(TOKEN_FILE, 'utf8').trim(); } catch (_) {}\nif (!TOKEN) {\n  TOKEN = crypto.randomBytes(12).toString('hex');\n  try { fs.writeFileSync(TOKEN_FILE, TOKEN); } catch (_) { console.warn('[警告] 通行碼無法存檔，重開伺服器後會換一組。'); }\n}\n", ""),
    # 公開版沒有共用通行碼：只認配對過的手機
    ("  const a = Buffer.from(String(t)), b = Buffer.from(TOKEN);\n  if (a.length === b.length && crypto.timingSafeEqual(a, b)) return true;\n", "  const a = Buffer.from(String(t));\n"),
    ("const info = { remote: REMOTE,", "const info = { remote: false,"),
    ("    if (req.method === 'GET' && url.pathname === '/remote.user.js') {\n      return send(res, 200, remoteUserscript(req.headers.host), 'text/javascript; charset=utf-8');\n    }\n", ""),
    ("      if (!isLocal(req)) return send(res, 403, { error: '只能在家裡電腦上更新' });\n", ""),
], 'server.js')
s = cut(s, "  if (REMOTE) {", "  console.log('');\n  console.log('保持這個視窗開著", 'server.js')
for bad in ['REMOTE', 'TOKEN', 'remote.user.js', 'remoteUserscript']:
    if bad in s: sys.exit(f'[中止] server.js 還留有 {bad}')
open(p, 'w', encoding='utf-8').write(s)

p = os.path.join(dst, 'dashboard.html'); s = open(p, encoding='utf-8').read()
# 面板的 ?token=（手機「開電腦版面板」用）公開版也保留
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
# 私人版的更新說明可能提到私人功能：有 notesPublic 就用它當公開版的說明
if 'notesPublic' in v: v['notes'] = v.pop('notesPublic')

json.dump(v, open(os.path.join(dst, 'version.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
# 私人功能不能漏到公開版：私人區塊的關鍵字放這裡（目前沒有私人功能；公會倉庫已在 v0.32.0 公開）
PRIVATE_WORDS = []
for f in FILES:
    if not f.endswith(('.js', '.html', '.json')): continue
    t = open(os.path.join(dst, f), encoding='utf-8').read()
    for bad in PRIVATE_WORDS:
        if bad in t and f != 'quiz-bank.json': sys.exit(f'[中止] 公開版 {f} 還有私人功能字樣：{bad}')
print('公開版已產生：', v['version'])
