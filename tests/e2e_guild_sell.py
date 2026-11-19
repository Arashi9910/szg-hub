"""公倉整理（私人版）：裝備依浮動篩選 → 勾選目前列出的 → 由某角色領出後賣給商店（要確認）；工廠圖公倉→商店"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def game(page, action):
    return await page.evaluate("""async a => { a.requestId = crypto.randomUUID(); a.characterId = a.characterId || sessionStorage.getItem('mapleCharacter');
      const r = await fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(a) }); return await r.json(); }""", action)

async def wait_job(kind, sec=60):
    end = time.time() + sec
    while time.time() < end:
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == kind]
        if js and js[-1]['status'] in ('done', 'failed'): return js[-1]
        await asyncio.sleep(1)
    raise AssertionError(kind + ' 沒做完')

async def nsell(d):
    import re as _re
    m = _re.search(r'賣掉 (\d*) ?件', await d.inner_text('#gwSell'))
    return int(m.group(1)) if m and m.group(1) else 0

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages: await game(pg, {'type': 'stop'})
        await env.wait_chars(2)
        hub_json('POST', '/api/settings', {'mainCharId': 'c1'})
        # 兩個帳號的背包裝備全部存進公倉
        for pg in pages:
            c = (await game(pg, {'type': 'sync'}))['character']
            await game(pg, {'type': 'guildWarehouseBatch', 'op': 'deposit', 'items': [{'kind': 'gear', 'uid': g['uid']} for g in c['equipmentBag'] if not g['locked']]})
        hub_json('POST', '/api/guild/refresh', {}); await wait_job('guildView')
        gear = mock_state()['guild']['gear']
        bad = [g for g in gear if sum(g['cleanStats'].get(k, 0) - g['baseStats'].get(k, 0) for k in set(g['cleanStats']) | set(g['baseStats'])) <= -1]
        print(f'   公倉 {len(gear)} 件，其中浮動總和 ≤ -1 的 {len(bad)} 件')

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)  # 先開工廠圖，記住目前的工作
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(1500)
        await d.click('#gwTabs button[data-gwtab=gear]'); await d.wait_for_timeout(500)

        print('1. 篩選：浮動總和 ≤ -1')
        await d.click('#gwAddCond'); await d.wait_for_timeout(300)
        await d.fill('[data-gwcv="0"]', '-1'); await d.press('[data-gwcv="0"]', 'Tab'); await d.wait_for_timeout(400)
        n = await d.locator('[data-gwpick^="g:"]').count()
        check(n == len(bad), f'列出 {n} 件（應為 {len(bad)}）')
        rows = d.locator('#gwOut tr.pickrow')
        await rows.nth(0).locator('td').nth(1).click(); await d.wait_for_timeout(300)
        check(await nsell(d) == 1 and 'picked' in (await d.locator('#gwOut tr.pickrow').nth(0).get_attribute('class')), '點整列（不是點勾選框）就選起來，整列亮起')
        await d.locator('#gwOut tr.pickrow').nth(0).locator('td').nth(2).click(); await d.wait_for_timeout(300)
        check(await nsell(d) == 0, '再點一次取消')
        await d.locator('#gwOut tr.pickrow').nth(0).locator('td').nth(1).click(); await d.wait_for_timeout(200)
        await d.locator('#gwOut tr.pickrow').nth(n - 1).locator('td').nth(1).click(modifiers=['Shift']); await d.wait_for_timeout(400)
        check(await nsell(d) == len(bad), f'Shift＋點最後一列，一次選起 {len(bad)} 件')
        await d.click('#gwNone'); await d.wait_for_timeout(200)
        await d.click('#gwPickShown'); await d.wait_for_timeout(300)
        check(await nsell(d) == len(bad), '勾選目前列出的全部')
        # 列上的「給誰」選單照常可以操作，不會切換選取
        await d.click('#gwNone'); await d.wait_for_timeout(200)
        await d.locator('#gwOut tr.pickrow').nth(0).locator('select').click(); await d.wait_for_timeout(200)
        check(await nsell(d) == 0, '點列上的「給誰」選單不會選取整列')
        await d.click('#gwPickShown'); await d.wait_for_timeout(300)

        print('2. 賣掉（由本尊領出後賣）')
        money0 = mock_state()['accounts']['A1']['chars']['c1']['money']
        await d.click('#gwSell'); await d.wait_for_timeout(800)
        job = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildSell'][-1]
        check(job['status'] == 'pending' and job['fromCharId'] == 'c1' and len(job['batches'][0]['gear']) == len(bad), '建立賣出工作，等待確認')
        hub_json('POST', f"/api/jobs/{job['id']}/approve")
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(500)
        job = await wait_job('guildSell')
        st = mock_state(); c1 = st['accounts']['A1']['chars']['c1']
        left = {g['uid'] for g in st['guild']['gear']}
        check(job['status'] == 'done' and not any(g['uid'] in left for g in bad), '勾選的都已從公倉移除：' + job['lastMsg'])
        check(c1['money'] - money0 == len(bad) * 100 and not any(g['uid'] in {b['uid'] for b in bad} for g in c1['equipmentBag']), f'本尊拿到 {len(bad) * 100} 楓幣，背包沒有留下賣掉的裝備')
        check(len(left) == len(gear) - len(bad), '其他裝備還在公倉')
        seen = 0
        for _ in range(40):
            seen = max(seen, await d.locator('.loot').count())
            if seen: break
            await asyncio.sleep(0.25)
        check(seen > 0, '工廠圖：賣掉的裝備沿著「公倉→商店」飛過去')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
