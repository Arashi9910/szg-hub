"""副本前補給：副本計畫的全隊每隻補到 N 個（從公倉領，只動道具）。
面板設定清單 → 立即補給（確認視窗列出每隻要領幾個、公倉不夠）→ 公倉沒讀過先讀再分配 → 公倉不夠照背包最少先分 → 結果寫進紀錄、面板顯示領到多少
→ 楓幣、點數沒動、沒從商店買 → 戰鬥中不補 → 存副本計畫不會清掉補給設定 → 建立隊伍時自動補給（只補一次）"""
import asyncio, json, os, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
BLUE, ELIX = 'i2000003', 'i2050004'  # 藍色藥水、萬能療傷藥
CH = [('A1', 'c1'), ('A2', 'c3'), ('A3', 'c4')]
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def inv(acct, cid, key=BLUE): return mock_state()['accounts'][acct]['chars'][cid]['inventory'].get(key, 0)
def gitems(): return mock_state()['guild']['items']
def data(): return hub_json('GET', '/api/data')
def wjobs(): return [j for j in data()['jobs'] if j['kind'] == 'guildWithdraw']
def sup(): return hub_json('GET', '/api/raid/supply')
def setitem(acct, cid, qty, key=BLUE): http('GET', MOCK + f'/__mock/setitem?acct={acct}&char={cid}&key={key}&qty={qty}')
async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception:
            pass
        await asyncio.sleep(step)
    return None
async def fresh_guild():
    at0 = hub_json('GET', '/api/guild').get('at') or 0
    hub_json('POST', '/api/guild/refresh', {})
    return await wait(lambda: (hub_json('GET', '/api/guild').get('at') or 0) > at0, 30)
def all_done(js): return js and all(j['status'] in ('done', 'failed', 'cancelled') for j in js)

async def main():
    async with Env() as env:
        # 一開始：本尊劍士 50、弓箭分身 10、倉庫分身 200 瓶藍色藥水；公倉藍色藥水 200（不夠）、沒有萬能療傷藥
        setitem('A1', 'c1', 50); setitem('A2', 'c3', 10); setitem('A3', 'c4', 200)
        http('GET', MOCK + f'/__mock/guild?key={BLUE}&qty=200&mesos=1000000&cash=500')
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        for pg in pages:  # 掛機會用藥水，測試期間先停
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(3)
        st0 = mock_state(); money0 = {c: st0['accounts'][a]['chars'][c]['money'] for a, c in CH}; cash0 = {a: st0['accounts'][a].get('cashPoints') for a, _ in CH}
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4']}})
        await asyncio.sleep(3)

        print('1. 面板：副本分頁的「副本前補給」清單')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        dlg = []; d.on('dialog', lambda dg: (dlg.append(dg.message), asyncio.ensure_future(dg.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1200)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(2500)
        check(await d.is_visible('#rdSupply #rsAdd'), '有「＋ 新增道具」')
        check(not await d.is_checked('#rsAuto'), '「建立隊伍時自動補給」預設關')
        await d.click('#rsAdd'); await d.wait_for_timeout(800)
        await d.click('#rsAdd'); await d.wait_for_timeout(800)
        check(await d.locator('#rsCfg .rs-item').count() == 2, '新增兩列')
        opts = await d.eval_on_selector('#rsCfg .rs-item:nth-child(2) select', 'e => [...e.options].map(o => o.value)')
        check(BLUE in opts and ELIX in opts and 'i2000002' in opts, '道具下拉有藍色藥水、萬能療傷藥、白色藥水（公倉還沒讀也能選）')
        await d.select_option('#rsCfg .rs-item:nth-child(2) select', BLUE); await d.wait_for_timeout(800)
        await d.fill('#rsCfg .rs-item:nth-child(2) input[data-rsf=target]', '150'); await d.press('#rsCfg .rs-item:nth-child(2) input[data-rsf=target]', 'Tab'); await d.wait_for_timeout(800)
        await d.select_option('#rsCfg .rs-item:nth-child(3) select', ELIX); await d.wait_for_timeout(800)
        await d.fill('#rsCfg .rs-item:nth-child(3) input[data-rsf=target]', '5'); await d.press('#rsCfg .rs-item:nth-child(3) input[data-rsf=target]', 'Tab'); await d.wait_for_timeout(800)
        cfg = (data()['settings'].get('raid') or {}).get('supply') or {}
        check([(x['key'], x['target']) for x in cfg.get('items', [])] == [(BLUE, 150), (ELIX, 5)] and cfg.get('auto') is False, f'存進 settings.raid.supply：{cfg}')
        check(cfg['items'][0]['name'] == '藍色藥水' and cfg['items'][1]['name'] == '萬能療傷藥', '道具名稱一起存')
        await d.wait_for_timeout(2500)
        prev = await d.inner_text('#rsPrev')
        check('本尊劍士' in prev and '弓箭分身' in prev and '倉庫分身' in prev and '夠了' in prev, '試算表列出全隊每隻現在有幾個（倉庫分身 200 夠了）')
        check('還沒讀過公倉' in await d.inner_text('#rsBar'), '提示還沒讀過公倉（補給前會先讀取）')

        print('2. 立即補給：確認 → 公倉沒讀過先讀 → 公倉不夠照背包最少先分')
        n0 = len(wjobs())
        await d.click('#rsRun')
        js = await wait(lambda: (lambda x: x if len(x) >= 2 and all_done(x) else None)(wjobs()[n0:]), 60)
        cm = next((m for m in dlg if '副本前補給' in m), '')
        check('藍色藥水' in cm and '萬能療傷藥' in cm and '弓箭分身：有 10' in cm and '不花楓幣' in cm, '確認視窗列出每隻現在有幾個、不花楓幣')
        check('先讀取' in cm, '確認視窗說會先讀公倉')
        js = js or wjobs()[n0:]
        check(len(js) == 2 and {j['fromCharId'] for j in js} == {'c1', 'c3'} and all(j.get('restock') for j in js), f'建立 2 個公倉領取工作（本尊劍士、弓箭分身；倉庫分身夠了）：{[j["fromName"] for j in js]}')
        check(all(not (j['batches'][0].get('gear') or []) and all(it['key'].startswith('i') for it in j['batches'][0]['items']) for j in js), '工作只有道具')
        check(inv('A2', 'c3') == 150, f'弓箭分身（最少）先分：10 → {inv("A2", "c3")}（補到 150）')
        check(inv('A1', 'c1') == 110, f'本尊劍士只分到剩下的 60：50 → {inv("A1", "c1")}')
        check(inv('A3', 'c4') == 200 and not gitems().get(BLUE), f'倉庫分身沒領（{inv("A3", "c4")}），公倉藍色藥水領完')
        check(all(inv(a, c, ELIX) == 0 for a, c in CH), '公倉沒有萬能療傷藥：沒有人領到')
        await wait(lambda: all(x.get('status') in ('done', 'failed') for x in sup()['log'] if x['kind'] == 'take'), 15)
        s = sup(); notes = [x['msg'] for x in s['log'] if x['kind'] == 'note']; takes = [x for x in s['log'] if x['kind'] == 'take']
        check(any('公倉不夠' in m and '萬能療傷藥' in m for m in notes), '紀錄：萬能療傷藥公倉不夠：' + next((m for m in notes if '萬能療傷藥' in m), '（沒有）'))
        check(any('公倉不夠' in m and '藍色藥水' in m and '弓箭分身' in m and '本尊劍士' in m for m in notes), '紀錄：藍色藥水公倉不夠、照背包最少先分')
        check(any('讀取' in m for m in notes), '紀錄：先讀公倉再分配')
        got = {x['charId']: x.get('got') for x in takes}
        check(got == {'c3': 140, 'c1': 60} and all(x['status'] == 'done' for x in takes), f'紀錄：每隻領到多少（{got}）')
        await d.wait_for_timeout(2500)
        lt = await d.inner_text('#rsLog')
        check('上次補給' in lt and '弓箭分身' in lt and '140' in lt and '完成' in lt, '面板顯示上次補給每隻領到多少、完成')
        check('公倉不夠' in await d.inner_text('#rsPrev'), '試算表標出公倉不夠')

        print('3. 楓幣、點數沒被動到，沒從商店買')
        st = mock_state()
        check(st['guild']['mesos'] == 1000000 and st['guild']['cashPoints'] == 500, '公倉楓幣、點數沒變')
        check(all(st['accounts'][a]['chars'][c]['money'] == money0[c] for a, c in CH), '角色楓幣沒變（沒有從商店買）')
        check(all(st['accounts'][a].get('cashPoints') == cash0[a] for a, _ in CH), '帳號點數沒變')
        check(not [x for x in data()['jobs'] if x['kind'] in ('guildMoney', 'buy', 'shop')], '沒有楓幣／購買工作')

        print('4. 戰鬥中不補')
        http('GET', MOCK + f'/__mock/guild?key={BLUE}&qty=500')
        check(await fresh_guild(), '公倉補回 500 瓶藍色藥水')
        await asyncio.sleep(3)
        n0 = len(wjobs())
        hub_json('POST', '/api/raid/live', {'charId': 'c3', 'inRaid': True, 'team': {'code': 'T9'}, 'battle': {'code': 'T9', 'raid': 'papulatus', 'phase': 1}})
        r = hub_json('POST', '/api/raid/supply/run', {})
        check(not r.get('ok') and '戰鬥中' in r.get('msg', ''), f'回「在副本戰鬥中，不補給」：{r.get("msg")}')
        await asyncio.sleep(2)
        check(len(wjobs()) == n0, '沒有建立工作')
        hub_json('POST', '/api/raid/live', {'charId': 'c3', 'inRaid': False})

        print('5. 存副本計畫不會清掉補給設定')
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4'], 'lock': False, 'password': ''}})
        check(len(((data()['settings'].get('raid') or {}).get('supply') or {}).get('items', [])) == 2, '補給清單還在')

        print('6. 建立隊伍時自動補給')
        await d.click('#rsAuto'); await d.wait_for_timeout(1000)
        check(((data()['settings'].get('raid') or {}).get('supply') or {}).get('auto') is True, '面板打開「建立隊伍時自動補給」')
        n0 = len(wjobs())
        hub_json('POST', '/api/raid/act', {'targets': [{'charId': 'c1', 'cmd': {'type': 'raidCreate', 'raid': 'papulatus'}, 'label': '建立副本隊伍'}]})
        team = await wait(lambda: (hub_json('GET', '/api/raid')['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        check(team and team.get('isLeader'), f'隊長建立了隊伍（{team and team.get("code")}）')
        j = await wait(lambda: (lambda x: x if x and all_done(x) else None)(wjobs()[n0:]), 40)
        check(j and len(j) == 1 and j[0]['fromCharId'] == 'c1', f'自動建立本尊劍士的領取工作（{[x["fromName"] for x in (j or [])]}）')
        check(inv('A1', 'c1') == 150 and inv('A2', 'c3') == 150, f'本尊劍士 110 → {inv("A1", "c1")}，弓箭分身夠了不領')
        check(any('建立隊伍後自動' in x['msg'] for x in sup()['log']), '紀錄寫「建立隊伍後自動」')
        n1 = len(wjobs()); setitem('A1', 'c1', 20)
        await asyncio.sleep(8)
        check(len(wjobs()) == n1, '同一個隊伍只自動補一次')
        await d.screenshot(path='/tmp/raid_supply.png', full_page=True)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
