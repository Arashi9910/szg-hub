"""公倉新版面：狀態列、左邊背包 → 存入、右邊公倉 → 領取、抽屜（存入規則、楓幣點數）"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_state():
    return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def wait_kind(kind, n, sec=60):
    end = time.time() + sec
    while time.time() < end:
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == kind]
        if len(js) >= n and all(j['status'] in ('done', 'failed', 'cancelled') for j in js): return js
        await asyncio.sleep(1)
    raise AssertionError(f'{kind} 沒做完')

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages:
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2000)
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(500)

        print('1. 狀態列、讀公倉')
        await d.click('#gwRefresh'); await d.wait_for_timeout(6000)
        st = ' '.join((await d.inner_text('#gStatus')).split())
        check('測試公會' in st and '道具' in st and '裝備' in st and '楓幣' in st and '自動存入：關閉' in st, '狀態列：' + st[:90])
        check(await d.locator('#gStatus svg.ic').count() >= 3, '按鈕用 Lucide 圖示')
        check(await d.eval_on_selector('#gRulesDrawer', 'e => getComputedStyle(e).display') == 'none', '存入規則收在抽屜裡（預設關著）')

        print('2. 左邊背包選卷軸 → 存入（每隻留 1 張）')
        await d.click('#gwTabs button[data-gwtab=scroll]'); await d.wait_for_timeout(400)
        await d.fill('#gwQ', '手套攻擊卷軸 60%'); await d.wait_for_timeout(500)
        await d.click('#gxBagOut tr[data-gxpick="i:i2040801"]'); await d.wait_for_timeout(300)
        check('存入 1 項' in await d.inner_text('#gxDeposit'), '中間按鈕顯示選了幾項')
        await d.fill('#gxKeep', '1')
        before = {c: mock_state()['accounts'][a]['chars'][c]['inventory'].get('i2040801', 0) for a, c in (('A1', 'c1'), ('A2', 'c3'))}
        await d.click('#gxDeposit')
        await wait_kind('guildDeposit', 1)
        st = mock_state()
        want = sum(max(0, v - 1) for v in before.values())
        check(st['guild']['items'].get('i2040801', 0) == want, f'公倉多了 {want} 張（每隻留 1 張，直接執行不用確認）')
        check(st['accounts']['A1']['chars']['c1']['inventory'].get('i2040801') == 1, '本尊留 1 張')

        print('3. 右邊公倉選 → 領取給弓箭分身')
        await d.wait_for_timeout(4000)
        await d.click('#gwRefresh'); await d.wait_for_timeout(6000)
        await d.check('[data-gwpick="i:i2040801"]'); await d.wait_for_timeout(200)
        await d.fill('[data-gwqty="i:i2040801"]', '2'); await d.press('[data-gwqty="i:i2040801"]', 'Tab')
        await d.select_option('#gwAll', 'c3')
        c3 = mock_state()['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0)
        await d.click('#gwCreate')
        await wait_kind('guildWithdraw', 1)
        check(mock_state()['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0) == c3 + 2, '弓箭分身拿到 2 張（直接執行）')

        print('4. 裝備：選未達標的')
        await d.fill('#gwQ', ''); await d.click('#gwTabs button[data-gwtab=gear]'); await d.wait_for_timeout(500)
        n = await d.locator('#gxBagOut tr[data-gxpick]').count()
        await d.click('[data-gxsel="no"]'); await d.wait_for_timeout(300)
        picked = await d.locator('#gxBagOut tr.picked').count()
        check(n > 0 and picked == n, f'防具預設看四屬、測試裝備只有物防 → 全部未達標都選到（{picked}/{n}）')
        await d.click('[data-gxsel="none"]')

        print('5. 抽屜')
        await d.click('#gRulesOpen'); await d.wait_for_timeout(400)
        check(await d.is_visible('#gRulesDrawer .mode-seg') and await d.is_visible('[data-gdpreset="good"]'), '存入規則抽屜有自動存入、快速套用')
        await d.keyboard.press('Escape'); await d.wait_for_timeout(200)
        await d.click('#gMoneyOpen'); await d.wait_for_timeout(400)
        check(await d.is_visible('#gmOp') and not await d.is_visible('#gRulesDrawer .mode-seg'), '楓幣／點數抽屜，一次只開一個')
        await d.click('[data-gclose="gMoneyDrawer"]'); await d.wait_for_timeout(200)
        check(not await d.is_visible('#gmOp'), '按關閉收起來')

        print('背包直接存進公倉')
        g0 = len(mock_state()['guild'].get('gear', []))
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(500)
        await d.click('[data-bview="list"]'); await d.wait_for_timeout(400)
        await d.click('[data-bkind="裝備"]'); await d.wait_for_timeout(400)
        rows = d.locator('#bagOut tr[data-bpick]:not(:has-text("鎖定"))')
        check(await rows.count() >= 2, f'條列有可存的裝備（{await rows.count()}）')
        check(await d.is_disabled('[data-bact="guild"]') if await d.locator('[data-bact="guild"]').count() else True, '沒選東西時「存進公倉」不能按')
        await rows.nth(0).locator('td').nth(2).click(); await rows.nth(1).locator('td').nth(2).click(modifiers=['Shift']); await d.wait_for_timeout(300)
        btn = d.locator('#bagActions [data-bact="guild"], [data-bact="guild"]').first
        check(await btn.is_visible() and await btn.is_enabled(), '背包選了裝備後有「存進公倉」按鈕')
        await btn.click()
        await wait_kind('guildDeposit', 1, 60)
        g1 = len(mock_state()['guild'].get('gear', []))
        check(g1 == g0 + 2, f'背包選的 2 件裝備存進公倉（{g0} → {g1}）')

        await d.set_viewport_size({'width': 900, 'height': 900}); await d.wait_for_timeout(500)
        w = await d.evaluate('document.documentElement.scrollWidth')
        check(w <= 910, f'窄螢幕不撐破（{w}px）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
