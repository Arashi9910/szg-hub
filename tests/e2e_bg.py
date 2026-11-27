"""背景執行（bg.js）：中控自己開無頭 Chrome 跑遊戲分頁＋中控腳本，不用開 Chrome 視窗
1. 還沒登入 → 顯示「需要登入」
2. 登入（測試用無頭的登入視窗＋模擬登入頁）→ 登入完成 → 自動開始背景，角色回報到中控、分頁標記 bg
3. 從中控下掛機指令，背景分頁執行
4. 加第二隻角色的分頁
5. 你自己的 Chrome（harness 分頁）也開同一隻 → 背景那頁讓位
6. 中控重新啟動 → 接回執行中的背景 Chrome（不重開），分頁繼續回報
7. 停止 → 背景 Chrome 關掉
"""
import asyncio, os, signal, subprocess, sys, time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    CHROMIUM = p.chromium.executable_path
from harness import Env, hub_json, http, HUB, MOCK, HUB_DIR, wait_url

XVFB = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1280x900x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.environ['DISPLAY'] = ':99'
os.environ.update({'MOCK_REQUIRE_LOGIN': '1', 'SZG_BG_GAME': MOCK, 'SZG_BG_LOGIN_PATH': '/__mock/login?acct={name}',
                   'SZG_BG_LOGIN_HEADLESS': '1', 'SZG_BG_RELOAD_GAP_MS': '5000', 'SZG_CHROME': CHROMIUM, 'SZG_BG_TICK_MS': '2000',
                   'SZG_GOOGLE_LOGIN_RE': '/__mock/google'})

ok_all = True
def check(cond, msg):
    global ok_all
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    if not cond:
        ok_all = False
        try:
            for x in hub_json('GET', '/api/bg')['profiles']: print('    live:', x['live'], '\n    logs:', x['logs'][-5:])
            print('    tabs:', hub_json('GET', '/api/data')['tabs'])
        except Exception as e: print('    (debug 失敗)', e)
    return cond

def prof(pid):
    s = hub_json('GET', '/api/bg')
    return next((x for x in s['profiles'] if x['id'] == pid), None)

async def until(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception:
            pass
        await asyncio.sleep(step)
    return None

def chrome_procs(pid):
    out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if f'data/bg/{pid}' in l and '--type=' not in l]

async def main():
    async with Env() as env:
        mock = hub_json('GET', '/api/settings')  # 暖身
        st = http('GET', MOCK + '/__mock/state', headers={'x-acct': 'A1'})
        import json
        accts = json.loads(st[1])['accounts']
        code1 = accts['A1']['code']

        print('1. 還沒登入')
        r = hub_json('POST', '/api/bg/add', {'name': 'A1'}); pid = r['id']
        check(prof(pid)['state'] == 'off', '新增後是停止狀態')
        hub_json('POST', '/api/bg/start', {'id': pid})
        p = await until(lambda: (lambda x: x if x['needLogin'] else None)(prof(pid)), 30)
        check(p is not None, '沒登入時顯示「需要登入」')
        check(p and p['state'] == 'running', f"背景 Chrome 有開起來（{p and p['state']} {p and p['msg']}）")

        print('2. 登入 → 自動開始背景')
        hub_json('POST', '/api/bg/login', {'id': pid})
        check(prof(pid)['state'] == 'login', '登入視窗開啟中（state=login）')
        await asyncio.sleep(5)
        hub_json('POST', '/api/bg/login-done', {'id': pid})
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and x['code'] and not x['needLogin'] else None)(prof(pid)), 40)
        check(p is not None, f'登入完成後自動在背景開始、已登入（{prof(pid)}）')
        check(p and p['code'] == code1, '認得是哪個帳號（遊戲 ID）')
        d = await until(lambda: (lambda d: d if 'c1' in d['chars'] and d['tabs'].get('c1', {}).get('bg') else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, '背景分頁的角色回報到中控，分頁標記為背景（tabs.bg）')
        p = await until(lambda: (lambda x: x if x['pages'] == ['c1', 'c2'] and sorted(l['key'] for l in x['live']) == ['c1', 'c2'] else None)(prof(pid)), 40)
        check(p is not None, f"登入後「帳號目前的角色」自動改成帳號的兩隻角色（pages={prof(pid)['pages']}，分頁 {[l['key'] for l in prof(pid)['live']]}）")
        live = await until(lambda: (lambda l: l if len(l) == 2 and all(x['injected'] for x in l) else None)(prof(pid)['live']), 20)
        check(live, '背景分頁有注入中控腳本')
        r_ = http('POST', HUB + '/api/bg/pages', {'id': pid, 'pages': ['']})
        check(r_[0] != 200 and '至少要勾一隻' in r_[1], '知道角色後不能只勾「帳號目前的角色」或全部取消')
        check(chrome_procs(pid) and all('--headless' in l for l in chrome_procs(pid)), '背景 Chrome 是無頭模式')

        print('3. 從中控下指令')
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'stop'}]})
        ok = await until(lambda: not json.loads(http('GET', MOCK + '/__mock/state', headers={'x-acct': 'A1'})[1])['accounts']['A1']['chars']['c1']['auto'], 30)
        check(ok, '背景分頁執行了「暫停掛機」')
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'start'}]})
        ok = await until(lambda: json.loads(http('GET', MOCK + '/__mock/state', headers={'x-acct': 'A1'})[1])['accounts']['A1']['chars']['c1']['auto'], 30)
        check(ok, '背景分頁執行了「開始掛機」')

        print('4. 第二隻角色的分頁')
        check(set(prof(pid)['charIds']) >= {'c1', 'c2'}, f"知道帳號裡的角色（{prof(pid)['charIds']}）")
        hub_json('POST', '/api/bg/pages', {'id': pid, 'pages': ['c1', 'c2']})
        d = await until(lambda: (lambda d: d if d['tabs'].get('c2', {}).get('bg') and d['tabs'].get('c1', {}).get('bg') else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, 'c1、c2 都有自己的背景分頁')
        check(len(prof(pid)['live']) == 2, '背景 Chrome 裡兩個分頁')

        print('4a. 省資源')
        procs = chrome_procs(pid)
        check(procs and all('--process-per-site' in l and '--disable-gpu' in l for l in procs), '背景 Chrome 用省記憶體參數（同網站共用程序、關掉繪圖程序）')
        st = await until(lambda: (lambda x: x if x['mem']['total'] > 0 and prof(pid)['mem'] else None)(hub_json('GET', '/api/bg')), 70, 3)
        check(st is not None, f"讀得到背景 Chrome 的記憶體（共 {st and st['mem']['total']} MB，A1 {prof(pid)['mem']}）")
        check(all(prof(pid)['live'][i]['injected'] for i in range(2)) and hub_json('GET', '/api/bg')['lite'], '省資源模式預設開啟')
        h0 = json.loads(http('GET', MOCK + '/__mock/pnghits')[1])['n']
        hub_json('POST', '/api/bg/reload', {'id': pid}); await asyncio.sleep(6)
        h1 = json.loads(http('GET', MOCK + '/__mock/pnghits')[1])['n']
        check(h1 == h0, f'省資源模式：背景分頁不下載遊戲圖片（重整後圖片請求 {h0} → {h1}）')
        d = await until(lambda: (lambda d: d if d['tabs'].get('c1', {}).get('bg') and d['tabs'].get('c2', {}).get('bg') else None)(hub_json('GET', '/api/data')), 30)
        check(d is not None, '省資源模式下中控腳本照常回報')
        hub_json('POST', '/api/bg/config', {'lite': False}); await asyncio.sleep(6)
        h2 = json.loads(http('GET', MOCK + '/__mock/pnghits')[1])['n']
        check(h2 > h1, f'關掉省資源模式：分頁重整、圖片照常下載（{h1} → {h2}）')
        hub_json('POST', '/api/bg/config', {'lite': True}); await asyncio.sleep(4)
        la = [l for l in prof(pid)['live']]
        t0 = time.time() * 1000
        hub_json('POST', '/api/bg/config', {'reloadHours': 0.001})  # 3.6 秒
        ok = await until(lambda: prof(pid)['reloads'] >= 2, 60, 2)
        check(ok, f"定時重新整理：一次一頁、錯開（重整 {prof(pid)['reloads']} 次）")
        hub_json('POST', '/api/bg/config', {'reloadHours': 6})
        heaps = await until(lambda: (lambda l: l if l and all(x['heap'] > 0 for x in l) else None)(prof(pid)['live']), 30)
        check(heaps, f"讀得到每個背景分頁的 JS 記憶體（{[x['heap'] for x in (heaps or [])]} MB）")
        st = hub_json('POST', '/api/bg/trim', {})
        check(prof(pid)['trimAt'] > 0, '「立刻整理」對背景 Chrome 執行記憶體整理')
        d = await until(lambda: (lambda d: d if d['tabs'].get('c1', {}).get('at', 0) > time.time() * 1000 - 8000 else None)(hub_json('GET', '/api/data')), 30)
        check(d is not None, '整理後分頁照常回報')
        d = await until(lambda: (lambda d: d if d['tabs'].get('c1', {}).get('at', 0) > t0 and d['tabs'].get('c2', {}).get('at', 0) > t0 else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, '重整後腳本照常回報')

        print('4b. 帳號分頁')
        dash = await env.browser.new_page(viewport={'width': 1400, 'height': 900}); derr = []
        dash.on('pageerror', lambda e: derr.append(str(e)))
        await dash.goto(HUB + '/')
        await dash.click('#bgSum')  # 右上角「🖥 背景」帶到帳號分頁
        await dash.wait_for_selector('#accts.on #acTable tr[data-acrow]', timeout=10000)
        txt = await dash.inner_text('#acTable')
        check('A1' in txt and '執行中' in txt and code1 in txt, '帳號分頁顯示帳號、執行中、遊戲 ID')
        perf = await dash.inner_text('#acPerf')
        check('省資源模式' in perf and 'MB' in perf or 'GB' in perf, f'帳號分頁顯示省資源開關、記憶體（{perf.strip()[:60]}）')
        chips = await dash.query_selector_all('#acTable .ac-ch')
        check(len(chips) == 2, f'每隻角色一個小卡（{len(chips)}）')
        check('帳號目前的角色' not in await dash.inner_text('#acTable'), '登入過的帳號不再顯示「帳號目前的角色」')
        w = await dash.evaluate("[document.querySelector('#acTable table').scrollWidth, document.documentElement.clientWidth]")
        check(w[0] <= w[1], f'帳號表格沒有撐出畫面（{w[0]} ≤ {w[1]}）')
        await dash.click(f'#acTable tr[data-acrow="{pid}"] td:nth-child(5)')  # 點整列（遊戲 ID 那格）勾選
        check(await dash.is_checked(f'input[data-acpick="{pid}"]'), '點整列就能勾選帳號')
        check('已勾選 1' in await dash.inner_text('#acSelInfo'), '顯示已勾選幾個')
        await dash.fill(f'input[data-acf="email"][data-id="{pid}"]', 'a1@example.com'); await dash.press(f'input[data-acf="email"][data-id="{pid}"]', 'Enter')
        ok = await until(lambda: prof(pid)['email'] == 'a1@example.com', 10)
        check(ok, '直接在表格改 Email')
        await dash.click(f'#acTable .ac-ch:nth-child(2) label')  # 取消 c2 背景分頁
        ok = await until(lambda: prof(pid)['pages'] == ['c1'], 10)
        check(ok, f"勾選框取消 c2 的背景分頁（pages={prof(pid)['pages']}）")
        await asyncio.sleep(1)
        await dash.click(f'#acTable .ac-ch:nth-child(2) label')
        ok = await until(lambda: prof(pid)['pages'] == ['c1', 'c2'], 10)
        check(ok, '再勾回來')
        await dash.fill('#acNewName', 'A2'); await dash.fill('#acNewEmail', 'a2@example.com'); await dash.click('[data-acact="add"]')
        p2 = await until(lambda: next((x for x in hub_json('GET', '/api/bg')['profiles'] if x['name'] == 'A2'), None), 10)
        check(p2 and p2['email'] == 'a2@example.com', '新增帳號（含 Email）')
        pid2 = p2['id']
        await dash.wait_for_selector(f'tr[data-acrow="{pid2}"]')
        await dash.drag_and_drop(f'tr[data-acrow="{pid2}"] .drag-h', f'tr[data-acrow="{pid}"] td:nth-child(3)', target_position={'x': 5, 'y': 3})
        ok = await until(lambda: [x['id'] for x in hub_json('GET', '/api/bg')['profiles']] == [pid2, pid], 10)
        check(ok, f"拖曳 ⠿ 調整帳號順序（{[x['name'] for x in hub_json('GET', '/api/bg')['profiles']]}）")

        print('4c. CSV、批次登入')
        s_, csv = http('GET', HUB + '/api/bg/export.csv')
        check(s_ == 200 and 'a1@example.com' in csv and 'Email' in csv.splitlines()[0], '匯出 CSV（有 Email 欄）')
        lines = csv.lstrip('﻿').strip().splitlines()
        new_csv = '\n'.join([lines[0], next(l for l in lines if l.startswith('A1')), next(l for l in lines if l.startswith('A2')), 'A3,a3@example.com,,,,否,第三個'])
        d = hub_json('POST', '/api/bg/import', {'csv': new_csv, 'dry': True})
        check(d['import']['added'] == 1 and d['import']['updated'] == 2, f"匯入預覽：新增 1、更新 2（{d['import']}）")
        check(len(hub_json('GET', '/api/bg')['profiles']) == 2, '預覽不會真的改')
        hub_json('POST', '/api/bg/import', {'csv': new_csv})
        names = [x['name'] for x in hub_json('GET', '/api/bg')['profiles']]
        check(names == ['A1', 'A2', 'A3'], f'匯入後順序照檔案、多一個 A3（{names}）')
        p3 = next(x for x in hub_json('GET', '/api/bg')['profiles'] if x['name'] == 'A3')
        check(p3['note'] == '第三個' and p3['email'] == 'a3@example.com', '匯入的備註、Email')
        hub_json('POST', '/api/bg/remove', {'id': p3['id']})
        hub_json('POST', '/api/bg/login-batch', {'ids': [pid2]})
        ok = await until(lambda: hub_json('GET', '/api/bg')['batch']['cur'] == pid2 and prof(pid2)['state'] == 'login', 15)
        check(ok, '批次登入：跳出 A2 的登入視窗')
        await dash.wait_for_selector('#acBatch .ac-batch', timeout=8000)
        check('a2@example.com' in await dash.inner_text('#acBatch'), '批次登入列顯示目前帳號和 Email（可複製）')
        await asyncio.sleep(4)
        hub_json('POST', '/api/bg/login-done', {'id': pid2})
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and x['code'] and not x['needLogin'] else None)(prof(pid2)), 40)
        check(p and p['code'] == accts['A2']['code'], '登入完成後 A2 自動在背景開始')
        b = hub_json('GET', '/api/bg')['batch']
        check(not b['cur'] and not b['queue'], '批次登入結束')
        await until(lambda: (lambda d: d if d['tabs'].get('c3', {}).get('bg') else None)(hub_json('GET', '/api/data')), 30)

        if os.environ.get('SZG_BG_SHOT'):  # 教學／回報用截圖
            await asyncio.sleep(3.5); await (await dash.query_selector('#accts .card')).screenshot(path=os.environ['SZG_BG_SHOT'])
        print('4d. 總覽自訂順序')
        await dash.click('nav button[data-tab="overview"]')
        await dash.wait_for_selector('#ovTable tr[data-ovrow]')
        await dash.click('#ovCustom')
        await dash.wait_for_selector('#ovTable .drag-h')
        before_ = [await r.get_attribute('data-ovrow') for r in await dash.query_selector_all('#ovTable tr[data-ovrow]')]
        await dash.drag_and_drop(f'#ovTable tr[data-ovrow="{before_[1]}"] .drag-h', f'#ovTable tr[data-ovrow="{before_[0]}"] td:nth-child(4)', target_position={'x': 5, 'y': 3})
        ok = await until(lambda: (hub_json('GET', '/api/data')['settings'].get('ovOrder') or [None])[0] == before_[1], 10)
        check(ok, f'總覽拖曳 ⠿ 自訂順序（{before_[:3]} → {(hub_json("GET", "/api/data")["settings"].get("ovOrder") or [])[:3]}）')
        await dash.reload(); await dash.wait_for_selector('#ovTable tr[data-ovrow]')
        first = await (await dash.query_selector('#ovTable tr[data-ovrow]')).get_attribute('data-ovrow')
        check(first == before_[1], '重新整理後順序還在（記住自訂排序）')
        dash.once('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await dash.click('#ovFromAcct')
        ok = await until(lambda: (hub_json('GET', '/api/data')['settings'].get('ovOrder') or [])[:3] == ['c1', 'c2', 'c3'], 10)
        check(ok, f'照帳號頁順序（A1 的 c1、c2，再 A2 的 c3）：{(hub_json("GET", "/api/data")["settings"].get("ovOrder") or [])[:4]}')

        print('4e. 點角色＝顯示視窗')
        await dash.click('nav button[data-tab="accts"]')
        await dash.wait_for_selector(f'button[data-acshow="{pid}"][data-char="c2"]')
        await dash.click(f'button[data-acshow="{pid}"][data-char="c2"]')
        p = await until(lambda: (lambda x: x if x['visible'] == 'c2' and x['state'] == 'running' and len(x['live']) == 2 else None)(prof(pid)), 40)
        check(p is not None, '點 c2 → A1 換成看得到的視窗（visible=c2）')
        procs = chrome_procs(pid)
        check(procs and not any('--headless' in l for l in procs), '看得到的視窗：不是無頭模式')
        port = open(os.path.join(HUB_DIR, 'data', 'bg', pid, 'DevToolsActivePort')).read().split()[0]
        import json as _j, urllib.request as _u
        await until(lambda: all(l['char'] for l in prof(pid)['live']), 30)
        await asyncio.sleep(3)
        tl = [t for t in _j.loads(_u.urlopen(f'http://127.0.0.1:{port}/json/list').read()) if t['type'] == 'page']
        check(len(tl) == 2 and not any(t['url'].startswith('about:blank') for t in tl), f"顯示的視窗只有兩個遊戲分頁，沒有空白頁（{[t['url'][-20:] for t in tl]}）")
        await asyncio.sleep(8)
        ch = sorted(l['char'] for l in prof(pid)['live'])
        check(ch == ['c1', 'c2'] and not any('另一個分頁開著' in (l.get('badge') or '') for l in prof(pid)['live']), f'兩個分頁是兩隻不同的角色、都沒有暫停（{ch}）')
        t0 = time.time() * 1000
        d = await until(lambda: (lambda d: d if d['tabs'].get('c2', {}).get('at', 0) > t0 and d['tabs']['c2'].get('bg') else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, '顯示視窗時中控腳本照跑')
        await dash.wait_for_selector(f'button[data-bgact="hide"][data-id="{pid}"]', timeout=8000)
        await dash.click(f'button[data-bgact="hide"][data-id="{pid}"]')
        p = await until(lambda: (lambda x: x if not x['visible'] and x['state'] == 'running' and chrome_procs(pid) and all('--headless' in l for l in chrome_procs(pid)) else None)(prof(pid)), 40)
        check(p is not None, '按「隱藏」回到無頭背景')
        hub_json('POST', '/api/bg/show', {'id': pid, 'char': 'c1'})
        await until(lambda: prof(pid)['visible'] == 'c1' and prof(pid)['state'] == 'running', 40)
        port = open(os.path.join(HUB_DIR, 'data', 'bg', pid, 'DevToolsActivePort')).read().split()[0]
        subprocess.run(['node', '-e', f"(async()=>{{const j=await (await fetch('http://127.0.0.1:{port}/json/version')).json();const w=new WebSocket(j.webSocketDebuggerUrl);w.onopen=()=>w.send(JSON.stringify({{id:1,method:'Browser.close'}}));w.onmessage=()=>process.exit(0);}})()"], timeout=15)
        p = await until(lambda: (lambda x: x if not x['visible'] and x['state'] == 'running' and chrome_procs(pid) and all('--headless' in l for l in chrome_procs(pid)) else None)(prof(pid)), 45)
        check(p is not None, '直接關掉看得到的視窗 → 自動回到無頭背景')
        check(not derr, '面板沒有 JS 錯誤' + ('：' + derr[0] if derr else ''))
        await dash.close()
        await until(lambda: len(prof(pid)['live']) == 2, 20)

        print('4g. 背景分頁顯示的角色跑掉（兩頁都是同一隻）→ 自動換回；面板按「切換」也是換背景分頁')
        def drift(src, dst):
            port = open(os.path.join(HUB_DIR, 'data', 'bg', pid, 'DevToolsActivePort')).read().split()[0]
            js = (f"(async()=>{{const j=await (await fetch('http://127.0.0.1:{port}/json/version')).json();const w=new WebSocket(j.webSocketDebuggerUrl);let n=0;const P={{}};"
                  "const send=(m,p,s)=>new Promise(r=>{const id=++n;P[id]=r;w.send(JSON.stringify({id,method:m,params:p||{},sessionId:s}));});"
                  "w.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&P[m.id])P[m.id](m.result||{});};"
                  "w.onopen=async()=>{const t=await send('Target.getTargets');for(const x of t.targetInfos){if(x.type!=='page')continue;const a=await send('Target.attachToTarget',{targetId:x.targetId,flatten:true});"
                  "const v=await send('Runtime.evaluate',{expression:\"sessionStorage.getItem('mapleCharacter')\",returnByValue:true},a.sessionId);"
                  f"if(v.result&&v.result.value==='{src}'){{await send('Runtime.evaluate',{{expression:\"location.href='/game/?szgChar={dst}'\"}},a.sessionId);console.log('ok');process.exit(0);}}}}process.exit(1);}};}})()")
            return subprocess.run(['node', '-e', js], timeout=20, capture_output=True, text=True).stdout.strip() == 'ok'
        await until(lambda: len(prof(pid)['live']) == 2 and all(l['char'] for l in prof(pid)['live']), 30)
        check(drift('c2', 'c1'), '讓 c2 那一頁跑成 c1（模擬遊戲把分頁換掉）')
        p = await until(lambda: (lambda x: x if sorted(l['char'] for l in x['live']) == ['c1', 'c1'] else None)(prof(pid)), 30, 0.5)
        print('    （兩頁都顯示 c1）' if p else '    （沒看到兩頁同一隻的狀態，可能已經換回）')
        p = await until(lambda: (lambda x: x if sorted(l['char'] for l in x['live']) == ['c1', 'c2'] else None)(prof(pid)), 60)
        check(p is not None and any('換回' in l['msg'] for l in p['logs']), f"自動把多出來的那頁換回 c2（{[l['char'] for l in prof(pid)['live']]}）")
        t0 = time.time() * 1000
        d = await until(lambda: (lambda d: d if d['tabs'].get('c2', {}).get('at', 0) > t0 and d['tabs']['c2'].get('bg') else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, 'c2 又有自己的背景分頁（會自動續掛）')
        await until(lambda: all(l['char'] for l in prof(pid)['live']), 30)
        await asyncio.sleep(3)
        check(drift('c2', 'c1'), '再跑掉一次')
        p = await until(lambda: (lambda x: x if sorted(l['char'] for l in x['live']) == ['c1', 'c1'] else None)(prof(pid)), 30, 0.5)
        r = hub_json('POST', '/api/idle', {'targets': [{'charId': 'c2', 'action': 'switch'}]})
        check(not r.get('jobs') and r.get('skipped') and '背景' in r['skipped'][0], f"面板按 c2 的「切換」：不送遊戲的切換，改換背景分頁（{r.get('skipped') or r}）")
        p = await until(lambda: (lambda x: x if sorted(l['char'] for l in x['live']) == ['c1', 'c2'] else None)(prof(pid)), 40)
        check(p is not None, 'c2 的背景分頁換回來了')
        await until(lambda: all(l['char'] for l in prof(pid)['live']), 30)

        print('4f. 顯示的視窗打開 Google 登入 → 自動換成一般的登入視窗（Google 會擋自動化的瀏覽器）')
        hub_json('POST', '/api/bg/show', {'id': pid, 'char': 'c1'})
        await until(lambda: prof(pid)['visible'] == 'c1' and prof(pid)['state'] == 'running', 40)
        port = open(os.path.join(HUB_DIR, 'data', 'bg', pid, 'DevToolsActivePort')).read().split()[0]
        subprocess.run(['node', '-e', f"(async()=>{{const j=await (await fetch('http://127.0.0.1:{port}/json/version')).json();const w=new WebSocket(j.webSocketDebuggerUrl);w.onopen=()=>w.send(JSON.stringify({{id:1,method:'Target.createTarget',params:{{url:'{MOCK}/__mock/google?continue=x'}}}}));w.onmessage=()=>process.exit(0);}})()"], timeout=15)
        p = await until(lambda: (lambda x: x if x['state'] == 'login' else None)(prof(pid)), 30)
        check(p is not None and any('Google 登入' in l['msg'] for l in p['logs']), f"跳出 Google 登入的分頁 → 自動關掉顯示的視窗、改開登入視窗（{prof(pid)['state']}）")
        hub_json('POST', '/api/bg/login-done', {'id': pid})
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and not x['visible'] and len(x['live']) == 2 else None)(prof(pid)), 60)
        check(p is not None, '登入視窗關掉後回到背景執行')

        print('5. 你自己的 Chrome 也開著同一隻 → 背景讓位')
        page = await env.open_account('A1', 'c1')
        d = await until(lambda: (lambda d: d if d['tabs'].get('c1') and not d['tabs']['c1'].get('bg') else None)(hub_json('GET', '/api/data')), 30)
        check(d is not None, 'c1 的分頁改成你自己的（不是背景）')
        sb = await until(lambda: next((x for x in prof(pid)['live'] if x['char'] == 'c1' and x['standby']), None), 40)
        check(sb is not None, '背景的 c1 分頁讓位（standby）')
        c2 = next((x for x in prof(pid)['live'] if x['char'] == 'c2'), None)
        check(c2 and not c2['standby'], '背景的 c2 分頁照常')
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'stop'}]})
        ok = await until(lambda: not json.loads(http('GET', MOCK + '/__mock/state', headers={'x-acct': 'A1'})[1])['accounts']['A1']['chars']['c1']['auto'], 30)
        check(ok, '讓位時，c1 的指令由你自己的分頁執行')
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j.get('kind') == 'idle']
        check(not any(j.get('status') == 'failed' for j in jobs), '沒有失敗的掛機工作')
        await page.context.close(); env.contexts.remove(page.context); env.acct_ctx.pop('A1', None)
        back = await until(lambda: (lambda d: d if d['tabs'].get('c1', {}).get('bg') and next((x for x in prof(pid)['live'] if x['char'] == 'c1' and not x['standby']), None) else None)(hub_json('GET', '/api/data')), 150, 3)
        check(back is not None, '關掉你自己的分頁後，背景的 c1 分頁接手（約 90 秒內）')

        print('6. 中控重新啟動 → 接回背景 Chrome')
        before = chrome_procs(pid)
        hub = env.procs[1]; hub.send_signal(signal.SIGKILL); hub.wait()
        newhub = subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787', 'SZG_QUIZ_SHARE_URL': 'http://127.0.0.1:9/'}, stdout=open('/tmp/hub2.log', 'w'), stderr=subprocess.STDOUT)
        env.procs[1] = newhub
        wait_url(HUB + '/api/settings')
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and len(x['live']) == 2 else None)(prof(pid)), 30)
        check(p is not None, '中控重新啟動後背景分頁接回來')
        check(chrome_procs(pid) == before, '沒有重開 Chrome（同一個程序）')
        check(await until(lambda: prof(pid2)['state'] == 'running', 30), '第二個帳號也接回來')
        check('接上執行中的' in open('/tmp/hub2.log', encoding='utf-8').read(), '紀錄寫「接上執行中的背景 Chrome」')
        t0 = time.time() * 1000
        d = await until(lambda: (lambda d: d if d['tabs'].get('c2', {}).get('at', 0) > t0 and d['tabs']['c2'].get('bg') else None)(hub_json('GET', '/api/data')), 30)
        check(d is not None, '接回後分頁照常和中控溝通')
        hub_json('POST', '/api/bg/reload', {'id': pid})
        await asyncio.sleep(3)
        t1 = time.time() * 1000
        d = await until(lambda: (lambda d: d if d['tabs'].get('c2', {}).get('at', 0) > t1 else None)(hub_json('GET', '/api/data')), 40)
        check(d is not None, '接回後重新整理分頁，腳本一樣會注入')

        print('7. 停止')
        dash = await env.browser.new_page(viewport={'width': 1400, 'height': 900})
        dash.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await dash.goto(HUB + '/'); await dash.click('nav button[data-tab="accts"]'); await dash.wait_for_selector('#acTable tr[data-acrow]')
        t0 = time.time()
        await dash.click('[data-acact="start-all"]')  # 全部本來就在跑：略過
        ok = await until(lambda: (lambda a: a if a and a['end'] else None)(hub_json('GET', '/api/bg')['all']), 15)
        check(ok and ok['skipped'] == 2, f'全部「開始」：本來就在跑的略過（{ok}）')
        await asyncio.sleep(1)
        await dash.click('[data-acact="stop-all"]')
        check(time.time() - t0 < 10, '按下去馬上有回應（背景依序進行）')
        await dash.wait_for_selector('#acBatch:has-text("依序停止")', timeout=5000)
        check(True, '上方顯示「■ 依序停止 n/2」進度')
        gone = await until(lambda: not chrome_procs(pid) and not chrome_procs(pid2), 40)
        try: await dash.wait_for_selector('#acBatch:has-text("完成")', timeout=15000); done_ = True
        except Exception: done_ = False
        check(done_, f"做完顯示「完成」（{(await dash.inner_text('#acBatch'))[:80]}）")
        await dash.close()
        check(gone, '背景 Chrome 關掉了')
        check(prof(pid)['state'] == 'off' and not prof(pid)['on'], '狀態是停止，重開中控也不會自動開')
        print('8. 有殘留的 Chrome 佔著資料夾（登入視窗關了但程式沒結束）')
        d1 = prof(pid)['dir']
        stale = subprocess.Popen([CHROMIUM, '--headless=new', '--no-sandbox', f'--user-data-dir={d1}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(3)
        check(stale.poll() is None and chrome_procs(pid), '殘留的 Chrome 在跑（沒有接 DevTools）')
        hub_json('POST', '/api/bg/start', {'id': pid})
        ok = await until(lambda: prof(pid)['state'] == 'running', 60)
        check(ok, f"開始時自動結束殘留的 Chrome，背景照常啟動（{prof(pid)['state']} {prof(pid)['msg']}）")
        check(stale.poll() is not None, '殘留的那個 Chrome 已被結束')
        hub_json('POST', '/api/bg/stop', {'id': pid}); await until(lambda: not chrome_procs(pid), 20)
        print('8b. 自動開始（中控重開、定時檢查）時有不是中控開的 Chrome 開著（例如登入視窗）→ 不關掉，等它關了才開')
        win = subprocess.Popen([CHROMIUM, '--headless=new', '--no-sandbox', f'--user-data-dir={d1}', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(3)
        bgc = hub_json('GET', '/api/data')['settings']['bg']
        bgc['profiles'] = [{**x, 'on': True} if x['id'] == pid else x for x in bgc['profiles']]
        hub_json('POST', '/api/settings', {'bg': bgc})
        w = await until(lambda: prof(pid)['state'] == 'wait' or None, 40)
        check(w and win.poll() is None, f"那個視窗沒被關掉，狀態顯示等它關掉（{prof(pid)['state']} {prof(pid)['msg'][:40]}）")
        win.terminate(); win.wait()
        ok = await until(lambda: prof(pid)['state'] == 'running', 60)
        check(ok, '視窗關掉後自動開始背景執行')
        hub_json('POST', '/api/bg/stop', {'id': pid}); await until(lambda: not chrome_procs(pid), 20)
        print('9. Chrome 一啟動就結束 → 錯誤寫出原因')
        bad = '/tmp/_szg_badchrome.sh'
        open(bad, 'w').write('#!/bin/sh\necho "fake chrome: profile is broken" >&2\nexit 21\n'); os.chmod(bad, 0o755)
        hub_json('POST', '/api/bg/config', {'chromePath': bad})
        hub_json('POST', '/api/bg/start', {'id': pid})
        ok = await until(lambda: prof(pid)['state'] == 'error' or None, 20)
        m = prof(pid)['msg']
        check(ok and '一啟動就結束' in m and '21' in m and 'profile is broken' in m, f'錯誤訊息寫出結束碼和 Chrome 的訊息（{m[:160]}）')
        hub_json('POST', '/api/bg/stop', {'id': pid}); hub_json('POST', '/api/bg/config', {'chromePath': ''}); os.remove(bad)
        errs = [l for l in env.logs if 'pageerror' in l]
        check(not errs, '你自己的遊戲分頁沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

    XVFB.terminate()
    print('\n全部通過' if ok_all else '\n有失敗')
    sys.exit(0 if ok_all else 1)

asyncio.run(main())
