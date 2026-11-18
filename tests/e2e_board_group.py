"""派工分組：A 組（第 1 隻）／B 組（第 2 隻）各一份設定；工廠圖放大時也能加地圖；背景掛機的略過；整組切成目前角色後套用"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        end = time.time() + 30
        while time.time() < end and not (hub_json('GET', '/api/world') or {}).get('maps'): await asyncio.sleep(1)
        hub_json('POST', '/api/settings', {'board': {'lanes': {'train': ['gms104040000'], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {}, 'goals': {}}})
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        mode = {'accept': True}; msgs = []
        async def on_dialog(dl):
            msgs.append(dl.message)
            await (dl.accept() if mode['accept'] else dl.dismiss())
        d.on('dialog', lambda dl: asyncio.ensure_future(on_dialog(dl)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        nodes = lambda: d.eval_on_selector_all('.fnode.fchar', 'ns => ns.map(n => n.dataset.fn)')

        print('1. 自動 → A 組（本尊劍士、弓箭分身）')
        n = await nodes()
        check(set(n) == {'c:c1', 'c:c3'}, f'工廠圖顯示 A 組：{n}')
        check(await d.locator('.fnode[data-fn="m:gms104040000"]').count() == 1, '原本的設定變成 A 組的')

        print('2. 切到 B 組、放大畫布後加地圖')
        await d.click('#facGroupBox [data-bdgroup="B"]'); await d.wait_for_timeout(800)
        n = await nodes()
        check(n == ['c:c2'] and await d.locator('.fnode[data-fn="c:c2"].bgc').count() == 1, 'B 組只有本尊小號，標成背景掛機')
        check(await d.locator('.fnode[data-fn="m:gms104040000"]').count() == 0, 'B 組是自己的空白看板')
        await d.click('[data-fzoom="max"]'); await d.wait_for_timeout(500)
        await d.select_option('#facAddMap', 'gms100010000'); await d.wait_for_timeout(1200)
        check(await d.locator('.fnode[data-fn="m:gms100010000"]').count() == 1, '放大畫布時用底部的「＋ 加入地圖」加上地圖')
        await d.click('[data-fzoom="max"]'); await d.wait_for_timeout(300)
        st = hub_json('GET', '/api/data')['settings']
        check(st['boards']['B']['lanes']['train'] == ['gms100010000'] and st['boards']['A']['lanes']['train'] == ['gms104040000'], 'A、B 兩組的地圖分開存')

        print('3. 背景掛機的先排、套用時略過')
        bd = st['boards']; bd['B']['assign'] = {'c2': 'gms104040000'}; bd['B']['lanes']['train'].append('gms104040000')
        hub_json('POST', '/api/settings', {'boards': bd}); await d.reload(); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1200)
        mode['accept'] = False; msgs.clear()
        await d.click('#bdApply'); await d.wait_for_timeout(800)
        check(any('背景掛機' in m for m in msgs), '套用時略過背景掛機的本尊小號：' + (msgs[-1][:60] if msgs else ''))

        print('4. 整組切成目前角色 → 自動跟到 B 組 → 套用')
        mode['accept'] = True; msgs.clear()
        await d.click('#facGroupBox [data-bdgswitch="B"]'); await d.wait_for_timeout(500)
        end = time.time() + 40
        while time.time() < end and mock_state()['accounts']['A1']['active'] != 'c2': await asyncio.sleep(1)
        check(mock_state()['accounts']['A1']['active'] == 'c2', '本尊小號切成目前角色')
        end = time.time() + 30
        while time.time() < end and (hub_json('GET', '/api/data')['chars'].get('c2') or {}).get('activeCharId') != 'c2': await asyncio.sleep(1)
        await d.click('#facGroupBox [data-bdgroup="auto"]')
        for _ in range(30):
            if await d.evaluate("() => boardGroup() === 'B' && boardChars().some(c => c.id === 'c2' && c.active)"): break
            await asyncio.sleep(0.5)
        await d.wait_for_timeout(500)
        check(await d.locator('#facGroupBox [data-bdgroup="B"].on').count() == 1 or await d.locator('.fnode[data-fn="c:c2"]').count() == 1, '「自動」跟著目前角色切到 B 組')
        check(await d.locator('.fnode[data-fn="c:c2"].bgc').count() == 0, '本尊小號不再是背景掛機')
        await d.click('#bdApply'); await d.wait_for_timeout(500)
        end = time.time() + 40
        while time.time() < end and mock_state()['accounts']['A1']['chars']['c2']['map'] != 'gms104040000': await asyncio.sleep(1)
        check(mock_state()['accounts']['A1']['chars']['c2']['map'] == 'gms104040000', '套用派工：本尊小號換到射手訓練場')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
