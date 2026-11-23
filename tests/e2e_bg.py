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

os.environ.update({'MOCK_REQUIRE_LOGIN': '1', 'SZG_BG_GAME': MOCK, 'SZG_BG_LOGIN_PATH': '/__mock/login?acct=A1',
                   'SZG_BG_LOGIN_HEADLESS': '1', 'SZG_CHROME': CHROMIUM, 'SZG_BG_TICK_MS': '2000'})

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
        r = hub_json('POST', '/api/bg/add', {'name': '測試帳號'}); pid = r['id']
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
        live = prof(pid)['live']
        check(len(live) == 1 and live[0]['injected'], '背景分頁有注入中控腳本')
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

        print('4b. 面板')
        dash = await env.browser.new_page(); derr = []
        dash.on('pageerror', lambda e: derr.append(str(e)))
        await dash.goto(HUB + '/')
        await dash.click('#bgSum')
        await dash.wait_for_selector('#bgPop .bg-prof', timeout=10000)
        txt = await dash.inner_text('#bgPop')
        check('測試帳號' in txt and '執行中' in txt, '面板「🖥 背景」顯示帳號和執行中')
        rows = await dash.query_selector_all('#bgPop label.bg-ch')
        check(len(rows) == 2, f'每隻角色一列（{len(rows)} 列）')
        await dash.click('#bgPop label.bg-ch:nth-of-type(2) .nm')  # 點整列（名字）就能取消勾選
        ok = await until(lambda: prof(pid)['pages'] == ['c1'], 10)
        check(ok, f"點整列取消 c2（pages={prof(pid)['pages']}）")
        await asyncio.sleep(3.5)
        await dash.click('#bgPop label.bg-ch:nth-of-type(2) .nm')
        ok = await until(lambda: prof(pid)['pages'] == ['c1', 'c2'], 10)
        check(ok, '再點一次勾回來')
        if os.environ.get('SZG_BG_SHOT'):  # 教學／回報用截圖
            await dash.set_viewport_size({'width': 1280, 'height': 900}); await asyncio.sleep(3.5)
            await (await dash.query_selector('#bgPop')).screenshot(path=os.environ['SZG_BG_SHOT'])
        summ = await dash.inner_text('#bgSum')
        check('背景' in summ, f'標題按鈕顯示狀態（{summ}）')
        check(not derr, '面板沒有 JS 錯誤' + ('：' + derr[0] if derr else ''))
        await dash.close()
        await until(lambda: len(prof(pid)['live']) == 2, 20)

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
        hub_json('POST', '/api/bg/stop', {'id': pid})
        gone = await until(lambda: not chrome_procs(pid), 20)
        check(gone, '背景 Chrome 關掉了')
        check(prof(pid)['state'] == 'off' and not prof(pid)['on'], '狀態是停止，重開中控也不會自動開')
        errs = [l for l in env.logs if 'pageerror' in l]
        check(not errs, '你自己的遊戲分頁沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

    print('\n全部通過' if ok_all else '\n有失敗')
    sys.exit(0 if ok_all else 1)

asyncio.run(main())
