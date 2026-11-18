"""總覽升級時間：記錄精確經驗表、升級還要、目標等級（含估計）"""
import asyncio, json, sys, time
from harness import Env, hub_json, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2']); await env.wait_chars(2)
        d0 = hub_json('GET', '/api/data')
        print('1. 經驗表')
        et = d0.get('expTable', {})
        check(et.get('45') == 2025000 and et.get('32') == 1024000, f'中控記下精確經驗：{et}')
        c1 = d0['chars']['c1']['char']
        check(c1.get('nextXpExact') and c1.get('nextXp') == 2025000, '快照帶 nextXp')
        ctx = await env.browser.new_context(viewport={'width': 1600, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2500)
        print('2. 升級還要')
        row = d.locator('tr:has([data-isel="c1"])')
        txt = await row.inner_text()
        hrs = (2025000 - c1['xp']) / c1['hourlyExp']
        check('小時' in txt, f'c1 顯示升級時間（約 {hrs:.1f} 小時）：' + txt.replace('\n', ' ')[:160])
        print('3. 目標等級')
        await d.fill('#ovTarget', '47'); await d.wait_for_timeout(500)
        heads = await d.inner_text('table.ov thead')
        check('到 Lv47' in heads, '多一欄「到 Lv47」')
        txt = await row.inner_text()
        check('估計' in txt, 'Lv46 沒收集到 → 標「估計」')
        r3 = d.locator('tr:has([data-isel="c3"])')
        await d.fill('#ovTarget', '33'); await d.wait_for_timeout(500)
        t3 = await r3.inner_text()
        check('估計' not in t3 and '小時' in t3, 'c3 Lv32→33 用精確值：' + t3.replace('\n', ' ')[:120])
        t1 = await row.inner_text()
        check('已達成' in t1, 'c1 已超過 Lv33 → 已達成')
        await d.reload(); await d.wait_for_timeout(2000)
        check(await d.input_value('#ovTarget') == '33', '目標等級重新整理後保留')
        await d.click('#ovExpBox summary'); await d.wait_for_timeout(400)
        et_txt = await d.inner_text('#ovExpOut')
        check('Lv45' in et_txt and '×' in et_txt, '經驗表顯示已收集等級與倍率')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
