"""同一個帳號開兩個遊戲分頁（A、B 角色各一個）：右下角按鈕開第二個分頁、兩隻資料即時、工作各自執行、
切換被擋、重複開同一隻會暫停、市場只由一個分頁負責、面板各頁面顯示正確"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return fn()

def fresh(cid, ms=8000):
    s = hub_json('GET', '/api/data')['chars'].get(cid)
    return s and time.time() * 1000 - s['receivedAt'] < ms

async def main():
    async with Env() as env:
        p1 = await env.open_account('A1'); await env.open_account('A2')
        await env.wait_chars(2)
        print('1. 右下角「＋ 開 本尊小號 的分頁」')
        btn = p1.locator('#szg-hub-open [data-szgopen="c2"]')
        await btn.wait_for(timeout=15000)
        check('本尊小號' in await btn.inner_text(), '本尊劍士的分頁顯示「＋ 開 本尊小號 的分頁」')
        async with env.acct_ctx['A1'].expect_page() as pi:
            await btn.click()
        p2 = await pi.value
        p2.on('pageerror', lambda e: env.logs.append(f'[A1/c2] pageerror: {e}'))
        await p2.wait_for_load_state()
        check(await wait(lambda: fresh('c2'), 25), '新分頁開成本尊小號，中控收到它的資料')
        check('szgChar' not in p2.url and await p2.evaluate("sessionStorage.getItem('mapleCharacter')") == 'c2', '網址參數用完就拿掉，分頁記住自己是本尊小號')
        await asyncio.sleep(6)
        check(await p1.locator('#szg-hub-open').count() == 0, '另一隻有分頁了，按鈕自動消失')
        check(fresh('c1', 70000) and fresh('c2', 70000) and not hub_json('GET', '/api/data')['chars']['c1'].get('idleOffline'), '兩隻同時在線、資料都即時')
        tabs = hub_json('GET', '/api/data')['tabs']
        check({'c1', 'c2'} <= set(tabs), f'中控記得兩隻都有分頁：{sorted(tabs)}')

        print('2. 工作各自執行')
        def lockjob(cid, key):
            st = hub_json('GET', '/api/data')['chars'][cid]
            it = next(i for i in st['items'] if i['key'] == key and i['loc'] == '背包')
            j = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': cid, 'batches': [{'items': [{'key': key, 'name': it['name'], 'uids': [x['uid'] for x in it['stacks']]}], 'gear': []}]})['jobs'][0]
            hub_json('POST', f"/api/jobs/{j['id']}/approve"); return j['id']
        j2 = lockjob('c2', 'i2000000'); j1 = lockjob('c1', 'i2000003')
        done = await wait(lambda: all(j['status'] == 'done' for j in hub_json('GET', '/api/data')['jobs'] if j['id'] in (j1, j2)), 30)
        st = mock_state()['accounts']['A1']['chars']
        locked = lambda c, k: any(s['locked'] for s in c['inventoryStacks'] if s['key'] == k)
        check(done and locked(st['c2'], 'i2000000') and locked(st['c1'], 'i2000003'), '本尊小號、本尊劍士的鎖定工作都在自己的分頁完成')
        r = hub_json('POST', '/api/idle', {'targets': [{'charId': 'c2', 'action': 'start'}]})
        check(r['jobs'][0]['needChar'] == 'c2', '本尊小號的掛機指令交給它自己的分頁')
        check(await wait(lambda: mock_state()['accounts']['A1']['chars']['c2']['auto'], 15), '本尊小號開始掛機')
        s, t = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c2', 'action': 'switch'}]})
        check(s != 200 and '已經有自己的分頁' in t, '切換到已經有分頁的角色會被擋下（不然兩個分頁會變成同一隻）')

        print('3. 同一隻開兩個分頁')
        p3 = await env.open_account('A1', 'c1')
        await asyncio.sleep(4)
        badge = await p3.inner_text('#szg-hub-badge')
        check('另一個分頁' in badge, '後開的分頁暫停中控功能並提示：' + badge[:40])
        j3 = lockjob('c1', 'i2000000')
        check(await wait(lambda: next(j for j in hub_json('GET', '/api/data')['jobs'] if j['id'] == j3)['status'] == 'done', 20), '工作仍然只由原本的分頁做完')
        await p3.close(); await asyncio.sleep(1)

        print('4. 市場只由一個分頁負責')
        await asyncio.sleep(40)
        lead = await p1.evaluate("JSON.parse(localStorage.getItem('__gm:lead:A1B2C3D4E5F6') || 'null')")
        d = hub_json('GET', '/api/data')['chars']
        pages = {d['c1'].get('page'), d['c2'].get('page')}
        check(lead and lead['page'] in pages, f"帳號的市場負責分頁：{lead and lead['page']}（兩個分頁 {pages}）")

        print('5. 面板')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 900}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto(HUB + '/'); await dash.wait_for_timeout(2500)
        r1 = await dash.locator('tr:has([data-isel="c1"])').inner_text(); r2 = await dash.locator('tr:has([data-isel="c2"])').inner_text()
        check('分頁' not in r1 and '分頁' not in r2, '總覽：正常有分頁的不再每列都掛「分頁」標籤（只標例外）')
        check(await dash.locator('[data-switch="c1"],[data-switch="c2"]').count() == 0, '有分頁的不顯示「⇄ 切換」')
        check(await dash.locator('[data-switch="c4"]').count() == 0, '整個帳號都沒開分頁的角色也不顯示切換')
        bar = await dash.inner_text('#ovBar')
        check('A 組都有分頁' in bar or '都有分頁' in bar, '「全部切到 A／B 組」按鈕在兩組都有分頁時不顯示：' + bar[:80])
        summ = await dash.inner_text('#ovSummary')
        check('有遊戲分頁' in summ, '摘要顯示有遊戲分頁的角色數')
        for tab in ['bag', 'trade', 'board', 'maps', 'forge', 'guild', 'gear', 'market', 'quiz']:
            await dash.click(f'nav button[data-tab={tab}]'); await dash.wait_for_timeout(700)
        await dash.click('nav button[data-tab=bag]'); await dash.wait_for_timeout(800)
        card = await dash.locator('.ccard[data-bchar="c2"]').inner_text()
        check('在線' in card, '背包角色卡：本尊小號顯示在線（有分頁）')
        check(not errs, '面板各分頁都沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

        print('6. 關掉第二個分頁')
        await p2.close()
        await asyncio.sleep(2)
        # 伺服器 90 秒內還記得（背景分頁會被瀏覽器放慢），按鈕在下一輪就回來
        await asyncio.sleep(6)
        check(await p1.locator('#szg-hub-open [data-szgopen="c2"]').count() == 1, '本尊劍士的分頁重新顯示「＋ 開 本尊小號 的分頁」')
        print('6b. 本尊劍士的分頁按 F5（模擬離開時標記沒來得及清掉）')
        await p1.evaluate("""window.addEventListener('pagehide', () => localStorage.setItem('__gm:charTab:c1', JSON.stringify({ page: 'old', tab: sessionStorage.getItem('szgTabId'), at: Date.now(), hidden: false })))""")
        await p1.reload(); await asyncio.sleep(8)
        check(await p1.evaluate("sessionStorage.getItem('mapleCharacter')") == 'c1' and '另一個分頁' not in await p1.inner_text('#szg-hub-badge'), '重新整理後還是本尊劍士，不會被當成重複或自動換成本尊小號')
        print('7. 直接開新分頁（沒有用按鈕）')
        await asyncio.sleep(3)
        p4 = await env.open_account('A1')
        became = await wait(lambda: None, 0)
        for _ in range(25):
            await asyncio.sleep(1)
            try:
                if await p4.evaluate("sessionStorage.getItem('mapleCharacter')") == 'c2': became = True; break
            except Exception: pass
        check(became, '新分頁載入的是已經有分頁的本尊劍士 → 自動換成本尊小號')
        check(await wait(lambda: 'c2' in hub_json('GET', '/api/data')['tabs'] and fresh('c2', 20000), 20), '中控收到本尊小號的分頁')
        check('另一個分頁' not in (await p4.inner_text('#szg-hub-badge')), '換過去之後沒有重複警告')
        p5 = await env.open_account('A1')
        await asyncio.sleep(6)
        check(await p5.evaluate("sessionStorage.getItem('szgAutoOther')") is None and '另一個分頁' in await p5.inner_text('#szg-hub-badge'), '兩隻都有分頁時再開一個：不換、維持暫停提示')
        await p5.close()
        pe = [l for l in env.logs if 'pageerror' in l]
        check(not pe, '遊戲分頁沒有 JS 錯誤' + ('：' + pe[0] if pe else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
