"""背包分頁（私人版）：選取道具／裝備 →「存進公倉」→ 直接執行（不用到工作確認）；補給中的略過"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1'])
        await pages[0].evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(1); await asyncio.sleep(11)
        c0 = mock_state()['accounts']['A1']['chars']['c1']
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(1000)
        await d.fill('#bSearch', '手套'); await d.wait_for_timeout(500)
        await d.click('[data-bquick="all"]'); await d.wait_for_timeout(300)
        await d.fill('#bSearch', '紅色藥水'); await d.wait_for_timeout(500)
        await d.locator('tr', has_text='紅色藥水').locator('[data-bpick]').first.click(); await d.wait_for_timeout(300)
        bar = await d.inner_text('#bagBar')
        check('存進公倉' in bar, '背包動作列有「🏦 存進公倉」')
        await d.click('[data-bact="guild"]'); await d.wait_for_timeout(1500)
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        check(jobs and all(j['status'] in ('approved', 'running', 'done') for j in jobs), '建立後直接執行，不用到「工作」確認')
        end = time.time() + 40
        while time.time() < end and not all(j['status'] in ('done', 'failed') for j in jobs):
            await asyncio.sleep(1); jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        g = mock_state()['guild']
        gloves = [x for x in c0['equipmentBag'] if '手套' in x['name'] and not x['locked']]
        check(jobs[-1]['status'] == 'done' and {x['uid'] for x in g['gear']} == {x['uid'] for x in gloves}, f'{len(gloves)} 件手套存進公倉')
        check(g['items'].get('i2040801') == c0['inventory']['i2040801'] and g['items'].get('i2040899') == c0['inventory']['i2040899'], '搜尋「手套」選到的卷軸全部存進公倉')
        check('i2000000' not in g['items'] and mock_state()['accounts']['A1']['chars']['c1']['inventory']['i2000000'] == c0['inventory']['i2000000'], '補給中的紅色藥水沒有被存走')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
