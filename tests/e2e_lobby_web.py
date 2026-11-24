"""組隊大廳網頁版（lobby.html）：沒裝中控的人用網頁公布、申請
- 中控（8787）：A1（c1 隊長）、A2（c3）
- 網頁使用者：A3 c4（倉庫分身 Lv20）當網頁隊長；A4 c5（第四隻 Lv30）、A5 c6（第五隻 Lv30）用網頁申請
1. 網頁公布（貼上遊戲隊伍代碼）→ 中控的 c3 申請 → 自動同意 → 中控用代碼自動加入
2. 中控 c1 公布 → 網頁用 c5 申請 → 通過後網頁顯示代碼 → 在遊戲輸入代碼加入 → 中控核對相符
3. 網頁用 c6 謊報 Lv60 → 自動同意 → 加入 → 中控核對不符踢出 → 網頁顯示「資料不符被踢出」
4. 網頁的手動審核：網頁隊長收到不符自動同意的申請，按同意
"""
import asyncio, json, os, shutil, subprocess, sys, time
os.environ.update({'MOCK_MORE_ACCTS': '1', 'SZG_LOBBY_URL': 'http://127.0.0.1:8790', 'SZG_LOBBY_POLL_MS': '2000', 'SZG_LOBBY_PUB_MS': '4000'})
from harness import Env, hub_json, http, HUB, MOCK, REPO, wait_url

LOBBY = 'http://127.0.0.1:8790'
ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)
def mock(): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts']
def char(acc, cid): return mock()[acc]['chars'][cid]
def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http('POST', MOCK + '/api/game', body, {'x-acct': acct, 'X-Game-Version': '1'})
    return json.loads(t)
async def until(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        await asyncio.sleep(step)
    return None

async def web_page(browser):
    ctx = await browser.new_context(viewport={'width': 1200, 'height': 900})  # 每個網頁使用者一個獨立瀏覽器
    p = await ctx.new_page(); p._errs = []
    p.on('pageerror', lambda e: p._errs.append(str(e)))
    await p.goto(LOBBY + '/'); await p.wait_for_timeout(800)
    return p

async def set_me(p, name, lv, branch):
    await p.click('[data-tab="mine"]')
    await p.fill('#meName', name); await p.press('#meName', 'Tab')
    await p.fill('#meLv', str(lv)); await p.press('#meLv', 'Tab')
    await p.select_option('#meBranch', branch)
    await p.click('[data-tab="find"]')

async def apply(p, leader):
    await p.wait_for_selector(f'.lc:has-text("{leader}") [data-req]', timeout=20000)
    await p.click(f'.lc:has-text("{leader}") [data-req]')
    await p.fill('#dlgMsg', '網頁申請'); await p.click('#dlgOk')
    await p.wait_for_timeout(1500)

async def main():
    shutil.rmtree('/tmp/lobbydata', ignore_errors=True)
    lob = subprocess.Popen(['node', os.path.join(REPO, 'lobby.js')], env={**os.environ, 'LOBBY_DATA': '/tmp/lobbydata', 'LOBBY_PORT': '8790'}, stdout=open('/tmp/lobby.log', 'w'), stderr=subprocess.STDOUT)
    try:
        async with Env() as env:
            wait_url(LOBBY + '/api/ping')
            await env.open_accounts(['A1', 'A2'])
            await env.wait_chars(2)

            print('1. 網頁公布 → 中控加入')
            code4 = game('A3', {'type': 'partyCreate', 'characterId': 'c4'})['party']['code']
            w4 = await web_page(env.browser)
            await w4.click('[data-tab="recruit"]')
            for k, v in [('rName', '倉庫分身'), ('rLv', '20'), ('rMap', '射手訓練場'), ('rCode', code4), ('rNote', '網頁隊長'), ('rLvMax', '50')]: await w4.fill('#' + k, v)
            await w4.select_option('#rBranch', '劍士'); await w4.check('#rAuto')
            await w4.click('#rPub'); await w4.wait_for_timeout(1500)
            check('公布中' in await w4.inner_text('#rState'), '網頁隊長公布成功')
            ls = json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']
            l4 = next((l for l in ls if l['leader']['name'] == '倉庫分身'), None)
            check(l4 and l4['web'] and code4 not in json.dumps(ls), '大廳上有網頁的隊伍（標記網頁、代碼不公開）')
            v = await until(lambda: (lambda v: v if any(l['id'] == l4['id'] for l in v['listings']) else None)(hub_json('GET', '/api/lobby')), 20)
            r = hub_json('POST', '/api/lobby/request', {'listingId': l4['id'], 'charId': 'c3'})
            check(r['status'] == 'approved', f"中控的 c3 申請網頁隊伍：自動同意（{r['status']}）")
            check(await until(lambda: char('A2', 'c3').get('partyCode') == code4, 60), '中控用代碼自動加入網頁隊長的隊伍')
            await w4.click('[data-tab="recruit"]'); await w4.wait_for_timeout(6000)
            inc = await w4.inner_text('#incList')
            check('弓箭分身' in inc and '自動' in inc, '網頁隊長看到中控玩家的申請（自動通過）')

            print('2. 中控公布 → 網頁申請 → 輸入代碼加入 → 核對相符')
            hub_json('POST', '/api/lobby/pub', {'charId': 'c1', 'on': True, 'note': '中控隊伍', 'rules': {'auto': True, 'lvMin': 25}})
            code1 = await until(lambda: char('A1', 'c1').get('partyCode'), 40)
            await until(lambda: any(l['leader']['name'] == '本尊劍士' for l in json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']), 40)
            w5 = await web_page(env.browser)
            await set_me(w5, '第四隻', 30, '劍士')
            await w5.wait_for_timeout(5500)
            await apply(w5, '本尊劍士')
            await w5.wait_for_selector('#outList .code', timeout=15000)
            shown = (await w5.inner_text('#outList .code')).strip()
            check(shown == code1, f'網頁通過後顯示隊伍代碼（{shown}）')
            game('A4', {'type': 'partyJoin', 'code': shown, 'characterId': 'c5'})  # 玩家自己在遊戲輸入代碼
            await w5.click('[data-joined]'); await w5.wait_for_timeout(1500)
            check('已加入' in await w5.inner_text('#outList'), '網頁按「我已經加入了」→ 已加入')
            rid = next(x['id'] for x in hub_json('GET', '/api/lobby')['incoming'] if x['char']['name'] == '第四隻')
            chk = await until(lambda: (hub_json('GET', '/api/lobby')['chk'].get(rid) or {}).get('result'), 60)
            check(chk == 'ok', f'中控用遊戲資料核對網頁申請者：相符（{chk}）')

            print('3. 網頁謊報')
            w6 = await web_page(env.browser)
            await set_me(w6, '第五隻', 60, '劍士')
            await w6.wait_for_timeout(5500)
            await apply(w6, '本尊劍士')
            await w6.wait_for_selector('#outList .code', timeout=15000)
            game('A5', {'type': 'partyJoin', 'code': (await w6.inner_text('#outList .code')).strip(), 'characterId': 'c6'})
            kicked = await until(lambda: not char('A5', 'c6').get('partyCode'), 90)
            check(kicked, '回報 Lv60（實際 30）→ 中控核對不符踢出')
            await until(lambda: True, 6)
            await w6.wait_for_timeout(6000)
            check('資料不符被踢出' in await w6.inner_text('#outList'), '網頁顯示「資料不符被踢出」')
            check(char('A4', 'c5').get('partyCode') == code1, '老實的網頁玩家沒被影響')

            print('4. 網頁隊長手動審核')
            w7 = await web_page(env.browser)
            await set_me(w7, '路人', 70, '法師')  # 超過 Lv50 → 不符自動同意
            await w7.wait_for_timeout(5500)
            await apply(w7, '倉庫分身')
            check('等隊長決定' in await w7.inner_text('#outList'), '不符自動同意 → 等隊長決定')
            await w4.wait_for_timeout(6000)
            await w4.click('[data-tab="recruit"]')
            await w4.wait_for_selector('#incList [data-dec][data-ok="1"]', timeout=15000)
            check('網頁申請' in await w4.inner_text('#incList'), '網頁隊長看到申請和留言')
            await w4.click('#incList [data-dec][data-ok="1"]')
            await w7.wait_for_selector('#outList .code', timeout=15000)
            check((await w7.inner_text('#outList .code')).strip() == code4, '網頁隊長按同意 → 申請者拿到代碼')

            print('5. 停止公布、手機寬度')
            await w4.click('#rStop'); await w4.wait_for_timeout(1500)
            check(not any(l['leader']['name'] == '倉庫分身' for l in json.loads(http('GET', LOBBY + '/api/listings')[1])['listings']), '網頁按停止公布 → 下架')
            await w5.set_viewport_size({'width': 390, 'height': 800}); await w5.click('[data-tab="find"]'); await w5.wait_for_timeout(500)
            sw = await w5.evaluate('document.documentElement.scrollWidth')
            check(sw <= 395, f'手機寬度不撐破（{sw}）')
            errs = sum((p._errs for p in (w4, w5, w6, w7)), [])
            check(not errs, '網頁沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    finally:
        lob.terminate()
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
