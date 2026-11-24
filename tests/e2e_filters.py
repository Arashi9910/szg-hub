"""共用角色選擇器（自動處理、自動上架、公倉背包欄、背包）、裝備頁浮動篩選、類別順序統一"""
import asyncio, json, sys
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2']); await env.wait_chars(2)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2500)

        print('1. 撿到自動處理：套用角色用共用選擇器')
        await d.click('nav button[data-tab=gear]'); await d.click('#gViewSeg button[data-gv="auto"]'); await d.wait_for_timeout(500)
        check(await d.locator('#asChars [data-cp="as|A"]').count() == 1, '有 全部／A 組／B 組／有分頁的／自訂')
        await d.click('#asChars [data-cp="as|tab"]'); await d.wait_for_timeout(1200)
        a = hub_json('GET', '/api/data')['settings']['autoSell']
        check(a['charSpec'] == {'mode': 'tab'} and set(k for k, v in a['chars'].items() if v) == {'c1', 'c3'}, f"選「有分頁的」→ 存成目前有分頁的角色：{a['chars']}")
        await d.click('#asChars [data-cp="as|custom"]'); await d.wait_for_timeout(500)
        await d.click('#asChars [data-cpc="as|c3"]'); await d.wait_for_timeout(1200)
        a = hub_json('GET', '/api/data')['settings']['autoSell']
        check(a['charSpec']['mode'] == 'custom' and set(k for k, v in a['chars'].items() if v) == {'c1'}, f"自訂取消弓箭分身：{a['chars']}")

        print('2. 裝備頁：浮動篩選')
        await d.click('#gViewSeg button[data-gv="list"]'); await d.wait_for_timeout(500)
        n_all = await d.locator('#gearOut tbody tr').count()
        if not await d.eval_on_selector('#filterCard', 'e => e.open'): await d.click('#filterCard > summary'); await d.wait_for_timeout(300)
        await d.select_option('#fJudge', 'no'); await d.wait_for_timeout(600)
        n_no = await d.locator('#gearOut tbody tr').count()
        check(n_all > 0 and 0 < n_no <= n_all, f'篩「浮動未達標」：{n_all} → {n_no} 列')
        await d.select_option('#fJudge', 'all'); await d.wait_for_timeout(300)

        print('3. 市場自動上架：同一個選擇器')
        await d.click('nav button[data-tab=market]'); await d.wait_for_timeout(800)
        await d.click('#mkChars [data-cp="mk|A"]'); await d.wait_for_timeout(1200)
        m = hub_json('GET', '/api/data')['settings']['market']
        check(m['charSpec'] == {'mode': 'A'} and set(k for k, v in m['chars'].items() if v) == {'c1', 'c3'}, f"A 組：{m['chars']}")

        print('4. 公倉背包欄、背包：同一個選擇器')
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(800)
        await d.click('#gwTabs button[data-gwtab=scroll]'); await d.wait_for_timeout(300)
        n1 = await d.locator('#gxBagOut tr[data-gxpick]').count()
        await d.click('#gxChars [data-cp="gx|custom"]'); await d.wait_for_timeout(300)
        await d.click('#gxChars [data-cpc="gx|c3"]'); await d.wait_for_timeout(500)
        who = await d.inner_text('#gxBagOut')
        check('弓箭分身' not in who and '本尊劍士' in who, f'公倉背包欄只看本尊劍士（{n1} → {await d.locator("#gxBagOut tr[data-gxpick]").count()} 種）')
        check([await b.get_attribute('data-gwtab') for b in await d.locator('#gwTabs button').all()] == ['gear', 'scroll', 'use', 'book', 'etc'], '公倉類別順序：裝備、卷軸、消耗、技能書、其他（跟背包一樣）')
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(500)
        await d.click('#bCharPick [data-cp="bag|custom"]'); await d.wait_for_timeout(300)
        await d.click('#bCharPick [data-cpc="bag|c1"]'); await d.wait_for_timeout(500)
        await d.click('[data-bview="list"]'); await d.wait_for_timeout(500)
        txt = await d.inner_text('#bagOut')
        check('本尊劍士' not in txt and '弓箭分身' in txt, '背包只看弓箭分身')
        import re as _re
        kinds = [_re.sub(r'\d+', '', x).strip() for x in (await d.inner_text('#bKinds')).split('\n') if x.strip()]
        ORDER = ['全部', '裝備', '卷軸', '消耗', '其他', '裝飾', '點數']
        check(kinds == sorted(kinds, key=ORDER.index), f'背包類別順序跟公倉一致：{kinds}')
        # 條列：Shift 多選、表頭全選、顯示更多
        rows = d.locator('#bagOut tr[data-bpick]'); n = await rows.count()
        check(n >= 4, f'條列有足夠的列可以測（{n}）')
        await rows.nth(0).locator('td').nth(2).click()
        await rows.nth(3).locator('td').nth(2).click(modifiers=['Shift']); await d.wait_for_timeout(300)
        rows = d.locator('#bagOut tr[data-bpick]')
        picked = [await rows.nth(i).get_attribute('class') for i in range(n)]
        check(all('picked' in (picked[i] or '') for i in range(4)) and all('picked' not in (picked[i] or '') for i in range(4, n)), f'Shift＋點選一次選第 1～4 列（{sum("picked" in (c or "") for c in picked)} 列）')
        await rows.nth(2).locator('td').nth(2).click(); await d.wait_for_timeout(200)
        await rows.nth(0).locator('td').nth(2).click(modifiers=['Shift']); await d.wait_for_timeout(300)
        rows = d.locator('#bagOut tr[data-bpick]')
        picked = [await rows.nth(i).get_attribute('class') for i in range(n)]
        check(all('picked' not in (picked[i] or '') for i in range(3)) and 'picked' in (picked[3] or ''), 'Shift＋點選也能一次取消一段')
        await d.check('#bListAll'); await d.wait_for_timeout(300)
        check(await d.locator('#bagOut tr.picked[data-bpick]').count() == n, '表頭勾選框全選畫面上的列')
        await d.uncheck('#bListAll'); await d.wait_for_timeout(300)
        check(await d.locator('#bagOut tr.picked[data-bpick]').count() == 0, '表頭勾選框取消全部')
        await d.evaluate('ui.bag.listLimit = 2; renderBagList()')
        check(await d.locator('#bagOut tr[data-bpick]').count() == 2 and await d.locator('[data-blmore="all"]').count() == 1, '超過顯示上限時有「再顯示／全部顯示」')
        await d.click('[data-blmore="all"]'); await d.wait_for_timeout(300)
        check(await d.locator('#bagOut tr[data-bpick]').count() == n, '按「全部顯示」列出全部')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
