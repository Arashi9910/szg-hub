"""公倉自動存入（私人版）：整類勾選「所有卷軸」→ 試跑只記錄 → 自動存入建立工作並執行 → 沒東西時不建工作"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def scrolls_on_bag():
    st = mock_state(); n = 0
    for a in st['accounts'].values():
        c = a['chars'][a['active']]
        n += sum(q for k, q in c['inventory'].items() if k in ('i2040801', 'i2040805', 'i2043001', 'i2044501', 'i2040899'))
    return n

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        for pg in pages:  # 掛機會一直撿到新卷軸，測試期間先暫停
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(3); await asyncio.sleep(11)  # 等停掛後的資料回報
        before = scrolls_on_bag()
        hub_json('POST', '/api/settings', {'guildDep': {'names': [], 'cats': ['卷軸'], 'conds': [], 'keep': 0}, 'guildAuto': {'mode': 'preview', 'everyMin': 30}})

        print('1. 試跑')
        r = hub_json('POST', '/api/guild/auto-run', {})
        check(any('試跑' in l['msg'] for l in r['log']), '紀錄寫「試跑」：' + r['log'][-1]['msg'][:80])
        check(not [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit'], '試跑沒有建立工作')

        print('2. 自動存入（工廠圖開著，看存入動畫）')
        hub_json('POST', '/api/guild/refresh', {})
        await asyncio.sleep(6)
        fctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(fctx)
        fac = await fctx.new_page(); ferrs = []; fac.on('pageerror', lambda e: ferrs.append(str(e)))
        await fac.goto(HUB + '/'); await fac.wait_for_timeout(1200)
        await fac.click('nav button[data-tab=board]'); await fac.wait_for_timeout(2500)
        check(await fac.locator('.fnode[data-fn="guild"]').count() == 1, '工廠圖有公倉節點')
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'deposit', 'everyMin': 30}})
        hub_json('POST', '/api/guild/auto-run', {})
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        check(jobs and all(j['status'] == 'approved' and j.get('auto') for j in jobs), f'建立 {len(jobs)} 個自動工作，直接排隊（不用確認）')
        end = time.time() + 60
        while time.time() < end:
            js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
            if all(j['status'] in ('done', 'failed') for j in js): break
            await asyncio.sleep(1)
        check(all(j['status'] == 'done' for j in js), '工作全部完成')
        seen = 0
        for _ in range(40):
            seen = max(seen, await fac.locator('.loot').count())
            if seen: break
            await asyncio.sleep(0.25)
        check(seen > 0, '存入完成後，圖示沿著「背包→公倉」飛過去')
        await fac.wait_for_timeout(2500)
        await fac.click('[data-fzoom=fit]'); await fac.wait_for_timeout(600)
        await fac.screenshot(path='/tmp/fac_guild.png')
        await fac.wait_for_timeout(3000); txt = await fac.inner_text('.fnode[data-fn="guild"]')
        check(f'{before:,}' in txt or str(before) in txt, f'公倉節點的數字跟著更新（{before:,}）')
        check('自動存入：開' in txt and await fac.locator('#facWires path[data-w="bag>guild"]').count() == 1, '公倉節點顯示自動存入狀態、有背包→公倉的線')
        check(not ferrs, '工廠圖沒有 JS 錯誤' + ('：' + ferrs[0] if ferrs else ''))
        gw = mock_state()['guild']['items']
        check(scrolls_on_bag() == 0 and sum(gw.values()) == before, f'背包卷軸全部進公倉（{before} 張）')

        print('3. 沒東西時')
        # 不等新資料：剛存完、資料還是舊的也不能再建工作
        n0 = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit'])
        r = hub_json('POST', '/api/guild/auto-run', {})
        n1 = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit'])
        check(n1 == n0 and '沒有符合' in r['log'][-1]['msg'], f"沒有卷軸時不建立工作（{n0}→{n1}：{r['log'][-1]['msg'][:60]}）")

        print('4. 面板')
        ctx = await env.browser.new_context(); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1200); await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(1500)
        check(await d.eval_on_selector('#gaMode', 'e => e.value') == 'deposit', '面板顯示「自動存入」模式')
        await d.wait_for_timeout(400)
        check(await d.is_checked('[data-gdcat="卷軸"]'), '存入選單的「所有卷軸」是勾的')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
