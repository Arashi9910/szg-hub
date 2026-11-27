"""公倉自動補給：背包低於 X 個自動從公倉領到 Y 個。
預設關閉 → 設規則後自動領到 Y → 夠了不再領 → 公倉不夠照順序分配、只領能領的 → 副本戰鬥中略過 → 楓幣、點數不會被動到 → 關掉就不領 → 面板卡片"""
import asyncio, json, os, sys, time
os.environ.update({'SZG_RESTOCK_TICK_MS': '3000', 'SZG_RESTOCK_CD_MS': '8000'})
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
KEY = 'i2000001'  # 橘色藥水（角色身上一開始都沒有）
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def inv(acct, cid, key=KEY): return mock_state()['accounts'][acct]['chars'][cid]['inventory'].get(key, 0)
def gitems(): return mock_state()['guild']['items']
def data(): return hub_json('GET', '/api/data')
def wjobs(): return [j for j in data()['jobs'] if j['kind'] == 'guildWithdraw']
def rlog(): return hub_json('GET', '/api/guild').get('restock', {}).get('log', [])
def snapqty(cid, key=KEY): return sum(i['qty'] for i in (data()['chars'].get(cid) or {}).get('items', []) if i['loc'] == '背包' and i['key'] == key)
def setitem(acct, cid, qty, key=KEY): http('GET', MOCK + f'/__mock/setitem?acct={acct}&char={cid}&key={key}&qty={qty}')
def rule(**kw): return {'id': 'r1', 'on': True, 'key': KEY, 'name': '橘色藥水', 'below': 50, 'target': 200, 'charSpec': {'mode': 'all'}, 'chars': None, **kw}
async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None
async def fresh_guild():
    """請遊戲分頁讀公倉，等中控拿到新的內容"""
    at0 = hub_json('GET', '/api/guild').get('at') or 0
    hub_json('POST', '/api/guild/refresh', {})
    return await wait(lambda: (hub_json('GET', '/api/guild').get('at') or 0) > at0, 30)
async def idle_jobs_done():
    return await wait(lambda: all(j['status'] in ('done', 'failed', 'cancelled') for j in wjobs()), 40)

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages:  # 掛機會撿東西，測試期間先暫停
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2)
        http('GET', MOCK + f'/__mock/guild?key={KEY}&qty=500&mesos=1000000&cash=500')
        st0 = mock_state(); money0 = {c: st0['accounts'][a]['chars'][c]['money'] for a, c in [('A1', 'c1'), ('A2', 'c3')]}; cash0 = {a: st0['accounts'][a].get('cashPoints') for a in ('A1', 'A2')}
        check(await fresh_guild(), '讀到公倉內容（橘色藥水 500、楓幣 100 萬、點數 500）')
        await asyncio.sleep(4)

        print('1. 預設關閉')
        check(not (data()['settings'].get('guildRestock') or {}).get('on'), '設定裡預設沒有開')
        hub_json('POST', '/api/guild/restock/run', {})
        check(any('關閉' in x['msg'] for x in rlog()), '立即檢查一次：紀錄寫「關閉，沒有檢查」')
        await asyncio.sleep(4)
        check(not wjobs(), '關閉時不會建立領取工作')

        print('2. 規則：只套用本尊劍士，低於 50 補到 200')
        hub_json('POST', '/api/settings', {'guildRestock': {'on': True, 'rules': [rule(charSpec={'mode': 'custom', 'ids': ['c1']}, chars=['c1'])]}})
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] == 'done' else None)(wjobs()), 40)
        check(j and j['fromCharId'] == 'c1' and j.get('restock') and j['status'] == 'done', '自動建立本尊劍士的領取工作並完成（不用確認）')
        check(j and not (j['batches'][0].get('gear') or []) and all(it['key'].startswith('i') for it in j['batches'][0]['items']), '工作只有道具，沒有裝備、楓幣')
        check(inv('A1', 'c1') == 200, f'本尊劍士背包：0 → {inv("A1", "c1")}（補到 200）')
        check(gitems().get(KEY) == 300, f'公倉剩 {gitems().get(KEY)}（500 − 200）')
        check(inv('A2', 'c3') == 0, '弓箭分身沒有勾，不會領')
        await wait(lambda: any(x.get('kind') == 'take' and x.get('status') == 'done' for x in rlog()), 10)
        t = [x for x in rlog() if x.get('kind') == 'take']
        check(t and t[-1]['status'] == 'done' and t[-1].get('got') == 200 and t[-1]['qty'] == 200, '紀錄：本尊劍士 橘色藥水 領 200，完成' + (('：' + t[-1]['msg']) if t else ''))

        print('3. 夠了就不再領')
        n0 = len(wjobs())
        await asyncio.sleep(10)  # 跨過冷卻（8 秒）和好幾次自動檢查
        check(len(wjobs()) == n0, '背包 200 ≥ 50：不會再建立工作')

        print('4. 公倉不夠：照順序分配，只領能領的')
        hub_json('POST', '/api/settings', {'guildRestock': {'on': False, 'rules': [rule()]}})
        http('GET', MOCK + f'/__mock/guild?key={KEY}&qty=30')
        setitem('A1', 'c1', 10)
        check(await fresh_guild(), '公倉改成只剩 30 個，中控重新讀到')
        await asyncio.sleep(5)  # 等兩隻角色回報新的背包
        n0 = len(wjobs())
        hub_json('POST', '/api/settings', {'guildRestock': {'on': True, 'rules': [rule()]}})
        hub_json('POST', '/api/guild/restock/run', {})
        await asyncio.sleep(1); await idle_jobs_done()
        new = wjobs()[n0:]
        check(len(new) == 1 and new[0]['fromCharId'] == 'c3', f'只建立 1 個工作，給背包最少的弓箭分身（{[x["fromName"] for x in new]}）')
        check(inv('A2', 'c3') == 30 and inv('A1', 'c1') == 10, f'弓箭分身領到能領的 30 個（{inv("A2", "c3")}），本尊劍士分不到（{inv("A1", "c1")}）')
        check(not gitems().get(KEY), '公倉的橘色藥水領完了')
        msgs = [x['msg'] for x in rlog()]
        check(any('不夠' in m and '弓箭分身' in m and '本尊劍士' in m and '分不到' in m for m in msgs), '紀錄寫清楚公倉不夠、誰分到多少：' + next((m for m in msgs if '不夠' in m), '（沒有）'))
        check(any('弓箭分身' in m and '公倉不夠' in m for m in msgs), '弓箭分身那筆寫「要 200，公倉不夠」')

        print('5. 副本戰鬥中略過')
        http('GET', MOCK + f'/__mock/guild?key={KEY}&qty=500')
        check(await fresh_guild(), '公倉補回 500')
        hub_json('POST', '/api/settings', {'guildRestock': {'on': True, 'rules': [rule(charSpec={'mode': 'custom', 'ids': ['c1']}, chars=['c1'])]}})
        n0 = len(wjobs())
        hub_json('POST', '/api/raid/live', {'charId': 'c1', 'inRaid': True, 'team': {'code': 'T1'}, 'battle': {'code': 'T1', 'raid': 'papulatus', 'phase': 1}})
        hub_json('POST', '/api/guild/restock/run', {})
        await asyncio.sleep(1)
        check(len(wjobs()) == n0, '本尊劍士在副本戰鬥中：不會領')
        check(any('副本戰鬥中' in x['msg'] for x in rlog()), '紀錄寫「在副本戰鬥中，這次略過」')
        hub_json('POST', '/api/raid/live', {'charId': 'c1', 'inRaid': False})
        j = await wait(lambda: (lambda js: js[-1] if len(js) > n0 and js[-1]['status'] == 'done' else None)(wjobs()), 30)
        check(j and j['fromCharId'] == 'c1' and inv('A1', 'c1') == 200, f'離開副本後自動補到 200（{inv("A1", "c1")}）')

        print('6. 楓幣、點數沒被動到')
        st = mock_state()
        check(st['guild']['mesos'] == 1000000 and st['guild']['cashPoints'] == 500, f"公倉楓幣 {st['guild']['mesos']:,}、點數 {st['guild']['cashPoints']}（沒變）")
        check(all(st['accounts'][a]['chars'][c]['money'] == money0[c] for a, c in [('A1', 'c1'), ('A2', 'c3')]), '角色身上的楓幣沒變')
        check(all(st['accounts'][a].get('cashPoints') == cash0[a] for a in ('A1', 'A2')), '帳號點數沒變')
        check(not [x for x in data()['jobs'] if x['kind'] == 'guildMoney'], '沒有建立任何楓幣／點數工作')

        print('7. 關掉就不領')
        hub_json('POST', '/api/settings', {'guildRestock': {'on': False, 'rules': [rule()]}})
        setitem('A1', 'c1', 0); setitem('A2', 'c3', 0)
        await asyncio.sleep(5)  # 中控的背包資料可能還是舊的（遊戲同步不帶背包，腳本約 45 秒自己讀一次）；領的時候腳本會照當下背包重算
        n0 = len(wjobs())
        hub_json('POST', '/api/guild/restock/run', {})
        await asyncio.sleep(8)
        check(len(wjobs()) == n0 and inv('A1', 'c1') == 0 and inv('A2', 'c3') == 0, '關閉後兩隻都是 0 個也不會領')

        print('8. 面板：公會分頁的「公倉自動補給」')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1200)
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(1500)
        check('自動補給：關閉' in await d.inner_text('#gsAuto'), '狀態列顯示「自動補給：關閉」')
        await d.click('#gRestockOpen'); await d.wait_for_timeout(800)
        check(await d.is_visible('#grCard'), '按「自動補給」打開卡片')
        check(not await d.is_checked('#grOn'), '開關是關的')
        check('讀的' in await d.inner_text('#grGuild'), '顯示公倉內容幾分鐘前讀的：' + (await d.inner_text('#grGuild')).strip())
        check(await d.locator('#grRules .gr-rule').count() == 1, '列出 1 條規則')
        opts = await d.eval_on_selector('#grRules select[data-grf=key]', 'e => [...e.options].map(o => o.textContent)')
        check(any('橘色藥水' in o and '310' in o for o in opts), '道具下拉：公倉裡的道具＋目前數量（' + '、'.join(opts[1:4]) + '）')
        logt = await d.inner_text('#grLog')
        check('弓箭分身' in logt and '完成' in logt, '最近紀錄有領取紀錄和完成狀態')
        await d.click('#grAdd'); await d.wait_for_timeout(800)
        check(len(data()['settings']['guildRestock']['rules']) == 2 and await d.locator('#grRules .gr-rule').count() == 2, '「＋ 新增規則」存進設定')
        await d.fill('#grRules .gr-rule:nth-child(2) input[data-grf=below]', '7'); await d.press('#grRules .gr-rule:nth-child(2) input[data-grf=below]', 'Tab'); await d.wait_for_timeout(600)
        check(data()['settings']['guildRestock']['rules'][1]['below'] == 7, '改「低於」會自動存檔')
        await d.click('#grRules .gr-rule:nth-child(2) [data-cp$="|custom"]'); await d.wait_for_timeout(600)
        await d.click('#grRules .gr-rule:nth-child(2) label:has-text("弓箭分身")'); await d.wait_for_timeout(600)
        r2 = data()['settings']['guildRestock']['rules'][1]
        check(r2['charSpec']['mode'] == 'custom' and r2['chars'] is not None and 'c3' not in r2['chars'] and 'c1' in r2['chars'], f'角色改成自訂、點整列取消弓箭分身（{r2["chars"]}）')
        await d.click('#grRules .gr-rule:nth-child(2) [data-grdel]'); await d.wait_for_timeout(600)
        check(len(data()['settings']['guildRestock']['rules']) == 1, '刪除規則')
        http('GET', MOCK + f'/__mock/guild?key={KEY}&qty=500'); await fresh_guild()
        n0 = len(wjobs())
        await d.click('#grOn'); await d.wait_for_timeout(800)
        check(data()['settings']['guildRestock'].get('on') is True, '面板打開開關（確認後）存進設定')
        await d.click('#grRun')
        j = await wait(lambda: inv('A1', 'c1') == 200 and inv('A2', 'c3') == 200, 40)
        if not j:
            for x in wjobs()[n0:]: print('    ', x['fromName'], x['status'], x['batches'][0]['items'], [l['msg'] for l in x['log']][-4:])
            print('     snap', snapqty('c1'), snapqty('c3'), [x['msg'] for x in rlog()][-5:])
        check(j and len(wjobs()) - n0 == 2 and inv('A1', 'c1') == 200 and inv('A2', 'c3') == 200, f'打開後兩隻都補到 200（{inv("A1", "c1")}、{inv("A2", "c3")}）')
        await d.wait_for_timeout(5000)
        check('自動補給：開' in await d.inner_text('#gsAuto'), '狀態列顯示「自動補給：開」')
        await d.click('#grOn'); await d.wait_for_timeout(800)
        check(data()['settings']['guildRestock'].get('on') is False, '面板關掉開關')
        await d.screenshot(path='/tmp/guild_restock.png')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
