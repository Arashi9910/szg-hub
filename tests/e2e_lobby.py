"""組隊大廳（lobby.js＋lobbyhub.js）：一個大廳、兩台中控
中控 1（8787）：A1（c1 本尊劍士 Lv45、c2）— c1 當隊長公布
中控 2（8788）：A2（c3 弓箭分身 Lv32）、A3（c4 倉庫分身 Lv20）、A4（c5 第四隻 Lv30）— 申請加入
1. 公布：c1 沒有隊伍 → 中控自動建立 → 大廳看得到（不含隊伍代碼）
2. 自動同意：c3 符合 Lv25 以上 → 直接核准 → 自動加入、核對相符
3. 手動：c4 Lv20 不符 → 等隊長；從面板按申請、隊長在面板按同意 → 加入並換到 c1 的地圖
4. 謊報：c5 回報 Lv60（實際 30）→ 自動核准加入 → 隊長的中控核對不符踢出；第二次再被踢 → 大廳封鎖
5. 關掉大廳 → 公告馬上下架
"""
import asyncio, json, os, shutil, subprocess, sys, time
os.environ.update({'MOCK_APPEARANCE': '1', 'SZG_PARTY_TICK_MS': '2000', 'MOCK_MORE_ACCTS': '1', 'SZG_LOBBY_URL': 'http://127.0.0.1:8790', 'SZG_LOBBY_POLL_MS': '2000', 'SZG_LOBBY_PUB_MS': '4000'})
from harness import Env, hub_json, http, HUB, MOCK, REPO, wait_url

HUB2 = 'http://127.0.0.1:8788'
LOBBY = 'http://127.0.0.1:8790'
ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def j2(method, path, body=None):
    s, t = http(method, HUB2 + path, body)
    return json.loads(t) if t else None

def mock(): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts']
def char(acc, cid): return mock()[acc]['chars'][cid]

async def until(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        await asyncio.sleep(step)
    return None

async def main():
    shutil.rmtree('/tmp/lobbydata', ignore_errors=True)
    lob = subprocess.Popen(['node', os.path.join(REPO, 'lobby.js')], env={**os.environ, 'LOBBY_DATA': '/tmp/lobbydata', 'LOBBY_PORT': '8790'}, stdout=open('/tmp/lobby.log', 'w'), stderr=subprocess.STDOUT)
    shutil.rmtree('/tmp/hub2', ignore_errors=True)
    shutil.copytree(REPO, '/tmp/hub2', ignore=shutil.ignore_patterns('.git', 'data', 'backup', 'tests', '__pycache__'))
    hub2 = None
    try:
        async with Env() as env:
            hub2 = subprocess.Popen(['node', 'server.js'], cwd='/tmp/hub2', env={**os.environ, 'PORT': '8788', 'SZG_QUIZ_SHARE_URL': 'http://127.0.0.1:9/'}, stdout=open('/tmp/hub2.log', 'w'), stderr=subprocess.STDOUT)
            wait_url(HUB2 + '/api/settings'); wait_url(LOBBY + '/api/ping')
            j2('POST', '/api/settings', {'autoUpdate': False})
            await env.open_account('A1')
            # 中控 2 的遊戲分頁：載入中控 2 的腳本
            u1, a1 = env.userscript, env.agent
            env.userscript = http('GET', HUB2 + '/szg-hub.user.js')[1].replace('127.0.0.1:8787', '127.0.0.1:8788'); env.agent = http('GET', HUB2 + '/agent.js')[1]
            for a in ['A2', 'A3', 'A4']: await env.open_account(a)
            env.userscript, env.agent = u1, a1
            await env.wait_chars(1)
            await until(lambda: all(k in j2('GET', '/api/data')['chars'] for k in ['c3', 'c4', 'c5']), 40)

            print('1. 公布')
            check(not char('A1', 'c1').get('partyCode'), 'c1 一開始沒有隊伍')
            hub_json('POST', '/api/lobby/pub', {'charId': 'c1', 'on': True, 'note': '缺人一起練', 'rules': {'auto': True, 'lvMin': 25}})
            ok1 = await until(lambda: char('A1', 'c1').get('partyCode'), 40)
            check(ok1, f'中控自動幫 c1 建立隊伍（{ok1}）')
            ls = await until(lambda: json.loads(http('GET', LOBBY + '/api/listings')[1])['listings'], 40)
            check(ls and ls[0]['leader']['name'] == '本尊劍士' and ls[0]['note'] == '缺人一起練', f"大廳看得到 c1 的隊伍（{ls and ls[0]['leader']}）")
            raw = http('GET', LOBBY + '/api/listings')[1]
            check(ok1 not in raw, '公開清單裡沒有隊伍代碼')
            lid = ls[0]['id']
            v2 = j2('GET', '/api/lobby')
            check(any(l['id'] == lid for l in v2['listings']), '中控 2 看得到大廳的隊伍')

            print('2. 自動同意')
            r = j2('POST', '/api/lobby/request', {'listingId': lid, 'charId': 'c3', 'msg': '你好'})
            check(r['status'] == 'approved', f"c3（Lv32）符合 Lv25 以上：自動核准（{r['status']}）")
            joined = await until(lambda: char('A2', 'c3').get('partyCode') == ok1, 60)
            check(joined, 'c3 的中控自動加入 c1 的隊伍')
            st = await until(lambda: next((x for x in j2('GET', '/api/lobby')['outgoing'] if x['id'] == r['id'] and x['status'] == 'joined'), None), 40)
            check(st, '大廳上這筆申請變成「已加入」')
            chk = await until(lambda: (hub_json('GET', '/api/lobby')['chk'].get(r['id']) or {}).get('result'), 60)
            check(chk == 'ok', f'隊長的中控用遊戲隊伍資料核對：相符（{chk}）')

            print('3. 手動審核（面板）')
            ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
            d2 = await ctx.new_page(); d1 = await ctx.new_page(); errs = []
            for p in (d1, d2):
                p.on('pageerror', lambda e: errs.append(str(e)))
                p.on('dialog', lambda dl: asyncio.ensure_future(dl.accept('請讓我加入')))
            await d2.goto(HUB2 + '/'); await d2.wait_for_timeout(2000)
            await d2.click('nav button[data-tab=lobby]'); await d2.wait_for_selector('#lbList .lb-card', timeout=15000)
            await d2.select_option('#lbChar', 'c4'); await d2.wait_for_timeout(500)
            card = await d2.inner_text('#lbList')
            check('本尊劍士' in card and '自動同意：Lv 25' in card and '要 Lv25 以上' in card, '大廳卡片顯示隊長、自動同意條件、這隻不符合的原因')
            await d2.click('[data-lbreq]'); await d2.wait_for_timeout(2500)
            out = await d2.inner_text('#lbOut')
            check('等隊長決定' in out, 'c4（Lv20）不符合：等隊長決定')
            await d1.goto(HUB + '/'); await d1.wait_for_timeout(2000)
            await d1.click('nav button[data-tab=lobby]')
            await d1.wait_for_selector('[data-lbdec][data-ok="1"]', timeout=20000)
            pub = await d1.inner_text('#lbPubs')
            check('倉庫分身' in pub and '請讓我加入' in pub and '公布中' in pub, '隊長的面板：公布中、看到 c4 的申請和留言')
            await d1.click('[data-lbdec][data-ok="1"]')
            joined = await until(lambda: char('A3', 'c4').get('partyCode') == ok1, 60)
            check(joined, '隊長按同意 → c4 自動加入')
            check(await until(lambda: char('A3', 'c4')['map'] == char('A1', 'c1')['map'] and char('A3', 'c4')['auto'], 30), 'c4 換到 c1 的地圖並開始掛機')

            print('3b. 隊員顯示、全身照')
            l = await until(lambda: (lambda ls: ls[0] if ls and len(ls[0]['members']) == 3 and all(m.get('branch') for m in ls[0]['members']) else None)(json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']), 60)
            check(l and [m['leader'] for m in l['members']].count(True) == 1 and {m['branch'] for m in l['members']} == {'劍士', '弓箭手'}, f"大廳的隊員有職業、隊長標記（{l and [(m['name'], m['branch'], m['leader']) for m in l['members']]}）")
            ava3 = await until(lambda: next((m['ava'] for m in json.loads(http('GET', LOBBY + '/api/listings')[1])['listings'][0]['members'] if m['name'] == '弓箭分身' and m['ava']), None), 90, 3)
            check(ava3 and http('GET', LOBBY + ava3.split('?')[0])[0] == 200, '別台中控的隊員也有全身照（申請時送過來的）')
            await d1.click('nav button[data-tab=overview]'); await d1.click('nav button[data-tab=lobby]'); await d1.wait_for_timeout(2500)
            pt = await d1.inner_text('#lbParties')
            check('本尊劍士 的隊伍' in pt and '弓箭分身' in pt and '倉庫分身' in pt and pt.count('踢出') == 2, '隊長的「我的隊伍」列出隊員和踢出按鈕')
            imgs = []
            for _ in range(20):
                imgs = await d1.eval_on_selector_all('#lbList .lb-m img', 'es => es.map(e => e.getAttribute("src"))')
                if len(imgs) == 3: break
                await d1.wait_for_timeout(1000)
            check(len(imgs) == 3 and all(imgs), f'大廳卡片每個隊員都有圖（{len(imgs)}）')

            print('3c. 隊長換圖 → 隊員跟著換')
            hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'map', 'map': 'gms100010000'}]})
            moved = await until(lambda: char('A1', 'c1')['map'] == 'gms100010000', 40)
            check(moved, '隊長 c1 換到新地圖')
            fol = await until(lambda: char('A2', 'c3')['map'] == 'gms100010000' and char('A3', 'c4')['map'] == 'gms100010000', 90)
            check(fol, f"別台中控的隊員 c3、c4 自動跟著換圖（c3 {char('A2', 'c3')['map']}、c4 {char('A3', 'c4')['map']}）")
            check(await until(lambda: char('A2', 'c3')['auto'] and char('A3', 'c4')['auto'], 30), '跟過去後重新開始掛機')
            notes = await until(lambda: [n['msg'] for n in j2('GET', '/api/lobby')['notes'] if '跟著過去' in n['msg']], 20)
            check(notes and len(notes) >= 2, f'隊員的中控有通知（{notes[:2] if notes else notes}）')
            await d2.click('nav button[data-tab=overview]'); await d2.click('nav button[data-tab=lobby]'); await d2.wait_for_timeout(2500)
            check('跟著過去' in await d2.inner_text('#lbNotes'), '通知顯示在大廳分頁下方')

            print('4. 謊報')
            async def lie():
                snap = j2('GET', '/api/data')['chars']['c5']; snap['char']['lv'] = 60
                http('POST', HUB2 + '/api/push', snap)
                return j2('POST', '/api/lobby/request', {'listingId': lid, 'charId': 'c5'})
            r = await lie()
            check(r['status'] == 'approved', f"c5 回報 Lv60：自動核准（{r['status']}）")
            await until(lambda: char('A4', 'c5').get('partyCode') == ok1, 60)
            kicked = await until(lambda: char('A4', 'c5').get('partyCode') != ok1 and (hub_json('GET', '/api/lobby')['chk'].get(r['id']) or {}).get('result') == 'kicked', 90)
            check(kicked, f"加入後核對不符（實際 Lv30）→ 自動踢出（{(hub_json('GET', '/api/lobby')['chk'].get(r['id']) or {}).get('why')}）")
            st = await until(lambda: next((x for x in j2('GET', '/api/lobby')['outgoing'] if x['id'] == r['id'] and x['status'] == 'kicked'), None), 30)
            check(st, '申請者那邊顯示「資料不符被踢出」')
            r = await lie()
            await until(lambda: char('A4', 'c5').get('partyCode') == ok1, 60)
            await until(lambda: (hub_json('GET', '/api/lobby')['chk'].get(r['id']) or {}).get('result') == 'kicked', 90)
            s, t = http('POST', HUB2 + '/api/lobby/request', {'listingId': lid, 'charId': 'c5'})
            check(s != 200 and '封鎖' in t, f'被踢 2 次 → 大廳封鎖這台中控（{t[:60]}）')
            check(char('A2', 'c3').get('partyCode') == ok1 and char('A3', 'c4').get('partyCode') == ok1, '老實的隊員沒被影響')
            sz = await until(lambda: (lambda l: l if l and l[0]['size'] == 3 else None)(json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']), 75)
            if not sz:
                for j in hub_json('GET', '/api/data')['jobs']:
                    if j['kind'] == 'party': print('    hub1 job', j['fromName'], j['status'], j['lastMsg'][:80], j['batches'][0]['party'].get('role'))
                for j in j2('GET', '/api/data')['jobs']:
                    if j['kind'] == 'party': print('    hub2 job', j['fromName'], j['status'], j['lastMsg'][:80], j['batches'][0]['party'].get('role'))
            check(sz, f"大廳上隊伍人數跟著更新（3/6）：{[l['size'] for l in json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']]}，遊戲隊伍 {[k for a in mock().values() for k, c in a['chars'].items() if c.get('partyCode') == ok1]}，中控 c1 快照 {[m['name'] for m in (hub_json('GET', '/api/data')['chars']['c1'].get('party') or {}).get('party', {}).get('members', [])]}")

            print('4b. 踢人、退出（面板按鈕）')
            await d1.click('nav button[data-tab=overview]'); await d1.click('nav button[data-tab=lobby]'); await d1.wait_for_timeout(2500)
            await d1.click('[data-lbkick*="|c4|"]')
            check(await until(lambda: not char('A3', 'c4').get('partyCode'), 60), '隊長按「踢出」→ c4 離開隊伍')
            await d2.click('nav button[data-tab=overview]'); await d2.click('nav button[data-tab=lobby]'); await d2.wait_for_timeout(2500)
            await d2.wait_for_selector('[data-lbleave="c3"]', timeout=15000)
            await d2.click('[data-lbleave="c3"]')
            check(await until(lambda: not char('A2', 'c3').get('partyCode'), 60), '隊員按「退出隊伍」→ c3 離開')
            left = await until(lambda: (lambda x: x if len(x) >= 3 else None)([n['msg'] for n in hub_json('GET', '/api/lobby')['notes'] if '離開了' in n['msg']]), 60, 2)
            check(left and any('倉庫分身' in x for x in left) and any('弓箭分身' in x for x in left), f'隊長的中控通知誰離開（{left[:3] if left else left}）')

            print('5. 關掉大廳')
            hub_json('POST', '/api/lobby/cfg', {'on': False})
            gone = await until(lambda: not json.loads(http('GET', LOBBY + '/api/listings')[1])['listings'], 10)
            check(gone, '關掉後公告馬上下架')
            check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    finally:
        for p in (hub2, lob):
            if p: p.terminate()
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
