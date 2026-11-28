"""背景執行的「直連模式」（profile direct:true）：agent.js 在 Node 裡跑（direct.js），用帳號的登入 cookie 直接打遊戲 API；
Chrome 只用來登入、用 CDP 抓 cookie。模擬遊戲開 MOCK_STRICT_ORIGIN（Origin 不對回 403）、MOCK_VIEW_DELTA（sync 省略沒變的大欄位）。
1. 新增帳號、登入（測試用無頭登入視窗）→ 一般（Chrome）背景執行；viewDelta 合併後背包正確
2. 切換成直連 → 這個帳號的 Chrome 關掉、cookie 存在 data/bg/<id>/direct-cookies.json、分頁照常回報、中控快照會更新
3. 直連執行掛機指令（暫停／開始、換圖）→ 遊戲狀態有變
4. 遊戲改版（/__mock/version）→ 直連自己重新抓 client-update.js，指令照常執行
5. 全程沒有「來源不符」（Origin 都對）
6. 登入失效（/__mock/logout）→ 顯示需要登入；重新登入後回到直連
7. 中控重新啟動 → 直連照常接續，不開 Chrome
8. 切回 Chrome 模式 → 背景 Chrome 分頁又在跑、指令照常
9. 停止
需要的中控 API（子任務 B）：POST /api/bg {action:'mode', id|ids, direct}；GET /api/bg 的 profiles[].direct／mode／cookieExp／state／needLogin／live[]
"""
import asyncio, json, os, signal, subprocess, sys, time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    CHROMIUM = p.chromium.executable_path
from harness import Env, hub_json, http, HUB, MOCK, HUB_DIR, wait_url

os.environ.update({'MOCK_REQUIRE_LOGIN': '1', 'MOCK_STRICT_ORIGIN': '1', 'MOCK_VIEW_DELTA': '1',
                   'SZG_BG_GAME': MOCK, 'SZG_BG_LOGIN_PATH': '/__mock/login?acct={name}',
                   'SZG_BG_LOGIN_HEADLESS': '1', 'SZG_BG_RELOAD_GAP_MS': '5000', 'SZG_CHROME': CHROMIUM, 'SZG_BG_TICK_MS': '2000'})

ok_all = True
def check(cond, msg):
    global ok_all
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    if not cond:
        ok_all = False
        try:
            for x in hub_json('GET', '/api/bg')['profiles']:
                print('    prof:', {k: x.get(k) for k in ('id', 'state', 'msg', 'direct', 'mode', 'needLogin', 'cookieExp')})
                print('    live:', x.get('live'), '\n    logs:', (x.get('logs') or [])[-6:])
            print('    tabs:', hub_json('GET', '/api/data')['tabs'])
            print('    hits:', mock_get('/__mock/hits'))
            jobs = hub_json('GET', '/api/data').get('jobs') or []
            print('    jobs:', [(j.get('kind'), j.get('status'), j.get('fromCharId'), (j.get('log') or [])[-2:]) for j in jobs[-4:]])
        except Exception as e: print('    (debug 失敗)', e)
    return cond

def prof(pid):
    return next((x for x in hub_json('GET', '/api/bg')['profiles'] if x['id'] == pid), None)

def mock_get(path):
    return json.loads(http('GET', MOCK + path, headers={'x-acct': 'A1'})[1])

def mock_char(acct, cid):
    return mock_get('/__mock/state')['accounts'][acct]['chars'][cid]

def set_mode(direct, pid=None, ids=None):
    body = {'direct': direct, **({'ids': ids} if ids else {'id': pid})}
    s, t = http('POST', HUB + '/api/bg/mode', body)
    return s, (json.loads(t) if t and t.strip().startswith('{') else t)

def item_qty(d, cid, key, loc='背包'):
    c = (d.get('chars') or {}).get(cid) or {}
    return sum(i.get('qty', 0) for i in c.get('items') or [] if i.get('key') == key and i.get('loc', '背包') == loc)

def now_ms(): return time.time() * 1000

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

def cookie_file(pid): return os.path.join(HUB_DIR, 'data', 'bg', pid, 'direct-cookies.json')

def cookie_names(pid):
    try: raw = json.load(open(cookie_file(pid), encoding='utf-8'))
    except Exception: return {}
    arr = raw if isinstance(raw, list) else (raw.get('cookies') or [])
    return {c.get('name'): c.get('value') for c in arr if isinstance(c, dict)}

def fresh_live(pid, t0, chars=('c1', 'c2')):
    """這個帳號的 live 有每隻角色、而且 at 都在 t0 之後"""
    p = prof(pid)
    if not p: return None
    live = p.get('live') or []
    got = sorted(l.get('char') or l.get('key') for l in live)
    return p if got == sorted(chars) and all((l.get('at') or 0) > t0 for l in live) else None

def tab_fresh(cid, t0):
    d = hub_json('GET', '/api/data')
    t = d['tabs'].get(cid) or {}
    return d if t.get('bg') and (t.get('at') or 0) > t0 else None

async def run_cmd(cid, action, expect, sec=40, **extra):
    hub_json('POST', '/api/idle', {'targets': [{'charId': cid, 'action': action, **extra}]})
    return await until(lambda: expect(mock_char('A1', cid)), sec)

async def main():
    async with Env() as env:
        hub_json('GET', '/api/settings')
        code1 = mock_get('/__mock/state')['accounts']['A1']['code']

        print('1. 登入 → 一般（Chrome）背景執行')
        pid = hub_json('POST', '/api/bg/add', {'name': 'A1'})['id']
        p = prof(pid)
        check(p and not p.get('direct'), f"新增的帳號預設不是直連（direct={p and p.get('direct')} mode={p and p.get('mode')}）")
        hub_json('POST', '/api/bg/start', {'id': pid})
        await until(lambda: prof(pid)['needLogin'], 30)
        hub_json('POST', '/api/bg/login', {'id': pid}); await asyncio.sleep(4)
        hub_json('POST', '/api/bg/login-done', {'id': pid})
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and x['code'] and not x['needLogin'] else None)(prof(pid)), 60)
        check(p is not None and p['code'] == code1, f'登入後在背景 Chrome 執行、認得帳號（{p and p["code"]}）')
        p = await until(lambda: (lambda x: x if len(x['live']) == 2 and all(l.get('injected') for l in x['live']) else None)(prof(pid)), 60)
        check(p is not None, '背景 Chrome 兩個分頁（c1、c2）都注入中控腳本')
        check(chrome_procs(pid), 'Chrome 模式：有這個帳號的 Chrome 程序')
        d = await until(lambda: tab_fresh('c1', 0), 40)
        check(d is not None, 'c1 回報到中控、分頁標記背景')
        h = await until(lambda: (lambda h: h if h['omitted'] > 0 else None)(mock_get('/__mock/hits')), 30)
        check(h is not None, f"Chrome 模式的遊戲頁面有用 viewDelta（省略欄位 {h and h['omitted']} 次）")
        http('GET', MOCK + '/__mock/additem?acct=A1&char=c1&key=i2000001&qty=5')
        d = await until(lambda: (lambda d: d if item_qty(d, 'c1', 'i2000001') == 5 else None)(hub_json('GET', '/api/data')), 75)
        check(d is not None, 'viewDelta 合併後：新撿到的道具出現在快照（橘色藥水 ×5）')
        check(d and item_qty(d, 'c1', 'i2000000') == 300 and item_qty(d, 'c1', 'i2040801') == 12, '沒變的道具照舊（紅色藥水 300、手套攻擊卷軸 60% 12）')

        check(mock_get('/__mock/hits')['origin403'] == 0, 'Chrome 模式沒有「來源不符」')

        print('2. 切換成直連')
        mock_get('/__mock/hits?reset=1')
        t0 = now_ms()
        s, r = set_mode(True, pid=pid)
        check(s == 200 and not (isinstance(r, dict) and r.get('error')), f'POST /api/bg {{action:"mode", direct:true}}（{s} {str(r)[:120]}）')
        p = await until(lambda: (lambda x: x if x.get('direct') and x['state'] == 'running' else None)(prof(pid)), 60)
        check(p is not None, f"帳號標成直連、執行中（mode={prof(pid).get('mode')} state={prof(pid)['state']}）")
        gone = await until(lambda: not chrome_procs(pid), 40)
        check(gone, f'這個帳號的 Chrome 關掉了（剩 {len(chrome_procs(pid))} 個）')
        ck = cookie_names(pid)
        check(os.path.exists(cookie_file(pid)) and ck.get('sid') == 'A1.0', f'登入 cookie 存在 direct-cookies.json（{sorted(ck)}）')
        p = prof(pid)
        check(p and p.get('cookieExp') and p['cookieExp'] > now_ms(), f"顯示 cookie 到期時間（cookieExp={p and p.get('cookieExp')}）")
        p = await until(lambda: fresh_live(pid, t0), 60)
        check(p is not None, f"直連的 live 有 c1、c2，at 是剛剛的（{[(l.get('char'), l.get('at')) for l in prof(pid)['live']]}）")
        check(p and not any(l.get('standby') for l in p['live']), '直連的分頁都沒有讓位')
        d = await until(lambda: tab_fresh('c1', t0) and tab_fresh('c2', t0), 60)
        check(d is not None, '中控的 tabs：c1、c2 是背景（bg）而且一直有回報')
        http('GET', MOCK + '/__mock/additem?acct=A1&char=c1&key=i2000001&qty=3')
        d = await until(lambda: (lambda d: d if item_qty(d, 'c1', 'i2000001') == 8 else None)(hub_json('GET', '/api/data')), 75)
        check(d is not None, '直連時中控快照會更新（橘色藥水 5 → 8）')
        check(d and item_qty(d, 'c1', 'i2000000') == 300 and item_qty(d, 'c1', 'i2040801') == 12, '直連快照裡沒變的道具也正確')
        h = mock_get('/__mock/hits')
        check(h['game'].get('A1', 0) > 0 and h['sync'].get('A1', 0) > 0, f"遊戲 API 有收到直連的請求（game {h['game']}、sync {h['sync']}）")
        print(f"    （直連 viewDelta：{h['viewDelta']} 次回應、省略 {h['omitted']} 個欄位）")
        await asyncio.sleep(4)
        check(not chrome_procs(pid), '直連執行中沒有再開 Chrome')

        print('3. 直連執行掛機指令')
        ok = await run_cmd('c1', 'start', lambda c: c['auto'])
        check(ok, '「開始掛機」')
        ok = await run_cmd('c1', 'stop', lambda c: not c['auto'])
        check(ok, '「暫停掛機」')
        ok = await run_cmd('c2', 'map', lambda c: c['map'] == 'gms104000400', map='gms104000400', mapName='海岸草叢3')
        check(ok, f"c2「換圖」到海岸草叢3（{mock_char('A1', 'c2')['map']}）")
        d = await until(lambda: (lambda d: d if ((d['chars'].get('c2') or {}).get('char') or {}).get('map') == 'gms104000400' else None)(hub_json('GET', '/api/data')), 30)
        check(d is not None, '中控快照的 c2 地圖跟著變')
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j.get('kind') == 'idle']
        check(jobs and not any(j.get('status') == 'failed' for j in jobs), f"掛機工作沒有失敗（{[j.get('status') for j in jobs]}）")

        print('4. 遊戲改版 → 直連自己重新抓版本')
        v2 = 'b7e1d9c3a5f20468ce13579bdf02468ace13579b'
        check(mock_get('/__mock/version?v=' + v2)['version'] == v2, '模擬遊戲換成新版本')
        t1 = now_ms()
        ok = await run_cmd('c1', 'start', lambda c: c['auto'], sec=60)
        check(ok, '改版後「開始掛機」照常執行（不用手動處理）')
        h = mock_get('/__mock/hits')
        print(f"    （改版後 409 {h['version409']} 次）")
        p = await until(lambda: fresh_live(pid, t1), 60)
        check(p is not None, '改版後 c1、c2 照常回報')
        ok = await run_cmd('c1', 'stop', lambda c: not c['auto'], sec=40)
        check(ok, '改版後「暫停掛機」')
        check(not chrome_procs(pid), '改版處理沒有開 Chrome')

        print('5. 來源檢查')
        h = mock_get('/__mock/hits')
        check(h['origin403'] == 0, f"沒有「來源不符」（origin403={h['origin403']}）")

        print('6. 登入失效 → 需要登入；重新登入回到直連')
        http('GET', MOCK + '/__mock/logout?acct=A1')
        p = await until(lambda: (lambda x: x if x['needLogin'] else None)(prof(pid)), 60)
        check(p is not None, f"cookie 失效後顯示需要登入（state={prof(pid)['state']} msg={prof(pid).get('msg')}）")
        check(prof(pid).get('direct'), '還是直連帳號（沒有被改回 Chrome 模式）')
        hub_json('POST', '/api/bg/login', {'id': pid}); await asyncio.sleep(4)
        hub_json('POST', '/api/bg/login-done', {'id': pid})
        t2 = now_ms()
        p = await until(lambda: (lambda x: x if x['state'] == 'running' and not x['needLogin'] and x.get('direct') else None)(prof(pid)), 90)
        check(p is not None, '重新登入後回到直連執行')
        ck = await until(lambda: (lambda c: c if c.get('sid') == 'A1.1' else None)(cookie_names(pid)), 30)
        check(ck is not None, f'抓到新的登入 cookie（{cookie_names(pid).get("sid")}）')
        p = await until(lambda: fresh_live(pid, t2), 60)
        check(p is not None, '重新登入後 c1、c2 照常回報')
        gone = await until(lambda: not chrome_procs(pid), 40)
        check(gone, '登入完 Chrome 關掉（直連不需要 Chrome）')

        print('7. 中控重新啟動 → 直連照常接續')
        hub = env.procs[1]; hub.send_signal(signal.SIGKILL); hub.wait()
        newhub = subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787', 'SZG_QUIZ_SHARE_URL': 'http://127.0.0.1:9/', 'SZG_LOBBY_URL': 'http://127.0.0.1:9'},
                                  stdout=open('/tmp/hub2.log', 'w'), stderr=subprocess.STDOUT)
        env.procs[1] = newhub
        wait_url(HUB + '/api/settings')
        t3 = now_ms()
        p = await until(lambda: (lambda x: x if x.get('direct') and x['state'] == 'running' else None)(prof(pid)), 40)
        check(p is not None, f"中控重啟後還是直連、執行中（{prof(pid)['state']}）")
        p = await until(lambda: fresh_live(pid, t3), 60)
        check(p is not None, '重啟後 c1、c2 照常回報')
        d = await until(lambda: tab_fresh('c1', t3), 40)
        check(d is not None, '重啟後中控快照照常更新')
        check(not chrome_procs(pid), '重啟後沒有開 Chrome')
        ok = await run_cmd('c1', 'start', lambda c: c['auto'])
        check(ok, '重啟後指令照常執行')

        print('8. 切回 Chrome 模式')
        s, r = set_mode(False, ids=[pid])
        check(s == 200 and not (isinstance(r, dict) and r.get('error')), f'POST /api/bg {{action:"mode", ids:[…], direct:false}}（{s}）')
        p = await until(lambda: (lambda x: x if not x.get('direct') and x['state'] == 'running' and chrome_procs(pid) else None)(prof(pid)), 60)
        check(p is not None, f"切回 Chrome：背景 Chrome 又開起來（mode={prof(pid).get('mode')}）")
        check(chrome_procs(pid) and all('--headless' in l for l in chrome_procs(pid)), '是無頭的背景 Chrome')
        p = await until(lambda: (lambda x: x if len(x['live']) == 2 and all(l.get('injected') for l in x['live']) else None)(prof(pid)), 60)
        check(p is not None, 'Chrome 的兩個分頁都注入中控腳本')
        t4 = now_ms()
        d = await until(lambda: tab_fresh('c1', t4) and tab_fresh('c2', t4), 60)
        check(d is not None, 'Chrome 分頁照常回報')
        ok = await run_cmd('c1', 'stop', lambda c: not c['auto'])
        check(ok, 'Chrome 模式的指令照常執行')

        print('9. 停止')
        hub_json('POST', '/api/bg/stop', {'id': pid})
        gone = await until(lambda: not chrome_procs(pid), 40)
        check(gone and prof(pid)['state'] == 'off', '停止後 Chrome 關掉、狀態是停止')
        h = mock_get('/__mock/hits')
        check(h['origin403'] == 0, f"直連之後都沒有「來源不符」（origin403={h['origin403']}）")

    print('\n全部通過' if ok_all else '\n有失敗')
    sys.exit(0 if ok_all else 1)

asyncio.run(main())
