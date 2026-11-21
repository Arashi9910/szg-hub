"""手機版（私人版）：配對／撤銷、經轉送的請求要通行碼、手機頁面操作掛機、換圖、工作、打王勾選、組隊套用；電腦面板配對 QR"""
import asyncio, json, os, sys, time
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
from harness import Env, hub_json, http

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

HUB = 'http://127.0.0.1:8787'
XFF = {'X-Forwarded-For': '100.64.0.9'}   # 模擬 tailscale serve 轉送進來的請求

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

def jobs(kind=None):
    return [j for j in hub_json('GET', '/api/data')['jobs'] if not kind or j['kind'] == kind]

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        print('1. 配對與權限')
        s, _ = http('GET', HUB + '/api/m/summary', None, XFF)
        check(s == 401, f'轉送進來、沒有通行碼 → 401（{s}）')
        s, body = http('GET', HUB + '/m', None, XFF)
        check(s == 200 and '上漲谷中控' in body, '手機頁面本身不用通行碼')
        d = hub_json('POST', '/api/m/pair', {'name': '測試手機'})
        tok = d['token']
        s, body = http('GET', HUB + '/api/m/summary', None, {**XFF, 'X-Hub-Token': tok})
        summ = json.loads(body) if s == 200 else {}
        check(s == 200 and len(summ.get('chars', [])) >= 2, f'帶裝置通行碼 → 精簡資料（{len(summ.get("chars", []))} 隻）')
        s, _ = http('POST', HUB + '/api/m/pair', {'name': 'x'}, {**XFF, 'X-Hub-Token': tok})
        check(s == 403, '手機不能幫別的裝置配對（403）')
        d2 = hub_json('POST', '/api/m/pair', {'name': '要撤銷的'})
        hub_json('POST', '/api/m/revoke', {'id': d2['id']})
        s, _ = http('GET', HUB + '/api/m/summary', None, {**XFF, 'X-Hub-Token': d2['token']})
        check(s == 401, '撤銷後 → 401')
        devs = json.loads(http('GET', HUB + '/api/m/devices')[1])['devices']
        check([x['name'] for x in devs] == ['測試手機'] and devs[0]['seenAt'] > 0, f'裝置清單：{devs}')

        print('2. 手機頁面')
        ctx = await env.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, extra_http_headers=XFF)
        env.contexts.append(ctx)
        p = await ctx.new_page(); errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        p.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await p.goto(HUB + '/m'); await p.wait_for_timeout(1200)
        check('還沒有配對' in await p.inner_text('main'), '沒配對 → 顯示請掃 QR')
        await p.goto(HUB + f'/m#t={tok}'); await p.wait_for_timeout(1800)
        check(p.url.endswith('#t=' + tok), '網址保留通行碼（加到主畫面時帶過去）')
        mh = await p.get_attribute('link[rel=manifest]', 'href')
        man = json.loads(http('GET', HUB + mh, None, XFF)[1])
        check(man['start_url'] == '/m#t=' + tok, f'manifest 啟動網址帶通行碼（{man["start_url"][:12]}…）')
        n = await p.locator('#chars [data-ch]').count()
        check(n >= 2, f'角色卡片 {n} 張')
        await p.screenshot(path='/tmp/m_chars.png')
        await p.click('#chars [data-ch="c1"]'); await p.wait_for_timeout(400)
        check(await p.is_visible('#sheet.on') and '開始掛機' in await p.inner_text('#sheet'), '點角色 → 操作面板')
        before = len(jobs('idle'))
        await p.click('#sheet [data-one="start|c1"]'); await p.wait_for_timeout(1200)
        js = jobs('idle')
        check(len(js) > before and any(t.get('action') == 'start' and t['charId'] == 'c1' for j in js for t in j['batches'][0].get('targets', [])), '送出「開始掛機」')
        await p.click('#chars [data-ch="c3"]'); await p.wait_for_timeout(300)
        await p.click('#sheet [data-one="map|c3"]'); await p.wait_for_timeout(1200)
        check(await p.locator('#mapList [data-pickmap]').count() > 0, '換圖清單')
        mid = await p.get_attribute('#mapList [data-pickmap]', 'data-pickmap')
        await p.click('#mapList [data-pickmap]'); await p.wait_for_timeout(1200)
        check(any(t.get('action') == 'map' and t['charId'] == 'c3' and t.get('map') == mid for j in jobs('idle') for t in j['batches'][0].get('targets', [])), f'送出換圖到 {mid}')
        print('3. 多選')
        await p.click('#selMode'); await p.click('#chars [data-ch="c1"]'); await p.click('#chars [data-ch="c3"]')
        check(await p.is_visible('#actbar.on'), '多選操作列')
        before = len(jobs('idle'))
        await p.click('#actbar [data-act="stop"]'); await p.wait_for_timeout(1200)
        check(len(jobs('idle')) > before, '多選暫停送出')
        await p.click('#selMode')
        print('4. 工作')
        await p.click('nav [data-v="jobs"]'); await p.wait_for_timeout(600)
        check('掛機' in await p.inner_text('#jobs'), '工作清單有掛機工作')
        print('4b. 升級時間、目標等級、全部重試')
        await p.click('nav [data-v="chars"]'); await p.wait_for_timeout(300)
        txt = await p.inner_text('#chars')
        check('升級' in txt, '角色卡片有「升級」預計時間')
        await p.fill('#tgt', '50'); await p.wait_for_timeout(300)
        txt = await p.inner_text('#chars')
        check('到 Lv50' in txt, '填目標等級 → 卡片顯示「到 Lv50」')
        await p.select_option('#sortBy', 'tgt'); await p.wait_for_timeout(300)
        await p.screenshot(path='/tmp/m_lv.png')
        await p.click('#chars [data-ch]'); await p.wait_for_timeout(300)
        await p.screenshot(path='/tmp/m_sheet.png')
        check('到 Lv50' in await p.inner_text('#sheet') and '升到 Lv' in await p.inner_text('#sheet'), '角色面板有升級與目標的預計時間')
        await p.evaluate('closeSheet()')
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'map', 'map': 'gms000000', 'mapName': '不存在'}]})
        f = await wait(lambda: [j for j in jobs('idle') if j['status'] == 'failed'], 40)
        check(f, '做出一個失敗的工作')
        await p.click('nav [data-v="jobs"]'); await p.click('#refresh'); await p.wait_for_timeout(1000)
        before = len([j for j in jobs() if j['status'] == 'failed'])
        await p.click('#retryAll'); await p.wait_for_timeout(800)
        after = [j for j in jobs() if any('重試全部' in (l.get('msg') or '') for l in j.get('log', []))]
        check(before >= 1 and len(after) == before, f'全部重試：{before} 個失敗的都重新排隊')
        print('5. 打王勾選')
        await p.click('nav [data-v="boss"]')
        await wait(lambda: True, 0)
        for _ in range(20):
            await p.wait_for_timeout(500)
            if await p.locator('#bossCards [data-bkm]').count(): break
        await p.click('#bossCards [data-bkm^="c3|"]'); await p.wait_for_timeout(800)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(len(cm.get('c3', [])) == 1, f'點王 → c3 勾一隻（{cm}）')
        await p.click('#bossMode [data-bm="preview"]'); await p.wait_for_timeout(800)
        check(hub_json('GET', '/api/boss')['cfg']['mode'] == 'preview', '打王改成試跑')
        print('6. 組隊套用')
        hub_json('POST', '/api/settings', {'parties': [{'id': 'pM', 'name': '手機隊', 'members': ['c1', 'c3'], 'map': 'gms104040000'}]})
        await p.click('nav [data-v="party"]'); await p.click('#refresh'); await p.wait_for_timeout(1200)
        check('手機隊' in await p.inner_text('#parties'), '隊伍卡片')
        await p.click('#parties [data-pt="pM"]'); await p.wait_for_timeout(1200)
        check(len(jobs('party')) == 2, f'送出組隊工作 {len(jobs("party"))} 個')
        await p.click('nav [data-v="more"]'); await p.wait_for_timeout(300)
        print('6b. 主畫面 App 沒有通行碼 → 貼網址配對')
        ctx2 = await env.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, extra_http_headers=XFF); env.contexts.append(ctx2)
        p2 = await ctx2.new_page()
        await p2.goto(HUB + '/m'); await p2.wait_for_timeout(1000)
        await p2.fill('#pairIn', f'http://100.64.0.1:8787/m#t={tok}'); await p2.click('#pairGo'); await p2.wait_for_timeout(2000)
        check(await p2.locator('#chars [data-ch]').count() >= 2, '貼上網址後配對成功、看到角色')
        check(not errs, '手機頁面沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

        print('7. 電腦面板配對')
        dctx = await env.browser.new_context(viewport={'width': 1300, 'height': 900}); env.contexts.append(dctx)
        d = await dctx.new_page(); derr = []
        d.on('pageerror', lambda e: derr.append(str(e)))
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1200)
        await d.click('#mBox > summary'); await d.wait_for_timeout(800)
        check('已配對的裝置' in await d.inner_text('#mPop') and '測試手機' in await d.inner_text('#mPop'), '面板列出已配對的裝置')
        await d.fill('#mBase', 'https://pc.example.ts.net'); await d.fill('#mName', '新手機'); await d.click('#mPair'); await d.wait_for_timeout(800)
        check(await d.locator('#mPop .qr svg').count() == 1 and 'https://pc.example.ts.net/m#t=' in await d.inner_text('#mPop'), '產生 QR code 與網址')
        await d.screenshot(path='/tmp/m_pair.png')
        await d.click('#mPop [data-mrevoke]'); await d.wait_for_timeout(800)
        check(len(json.loads(http('GET', HUB + '/api/m/devices')[1])['devices']) == 1, '面板移除一支')
        check(not derr, '面板沒有 JS 錯誤' + ('：' + derr[0] if derr else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
