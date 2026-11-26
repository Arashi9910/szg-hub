"""角色全身照上傳，總覽／派工工廠圖／清單／組隊卡片顯示全身照；組隊套用帶派工看板的自動販售範本"""
import asyncio, json, os, sys, time
os.environ['MOCK_APPEARANCE'] = '1'
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

MAP = 'gms104040000'

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)

        print('1. 全身照上傳')
        av = await wait(lambda: (lambda a: a if {'c1', 'c3'} <= set(a) else None)(hub_json('GET', '/api/data').get('avatars') or {}), 60, 2)
        check(av, f"c1、c3 上傳全身照：{sorted((av or {}).keys())}")
        s, body = http('GET', 'http://127.0.0.1:8787/api/avatar/c1')
        check(s == 200 and body.startswith('GIF8'), 'GET /api/avatar/c1 回傳 GIF')
        s, _ = http('GET', 'http://127.0.0.1:8787/api/avatar/nobody')
        check(s == 404, '沒有的角色回 404')

        print('2. 組隊卡片顯示全身照、套用時帶自動販售範本')
        # v0.71：自動販售來自去處規則（這張圖只賣紅寶殼）
        sell = {'enabled': True, 'itemIds': [4000016]}
        hub_json('POST', '/api/settings', {'parties': [{'id': 'pA', 'name': '測試隊', 'members': ['c1', 'c3'], 'map': MAP}],
                                           'boards': {'A': {'lanes': {'train': [MAP], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {}, 'goals': {}}, 'B': {}},
                                           'dest': {'board': True, 'over': {MAP: {'items': {'4000016': 'shop'}, 'rest': 'keep'}}}})
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=party]'); await d.wait_for_timeout(1200)
        n = await d.locator('#ptCards .pt-mem img.ava').count()
        check(n == 2, f'組隊卡片有 {n} 張全身照')
        await d.click('#ptApplyAll'); await d.wait_for_timeout(1500)
        jobs = await wait(lambda: (lambda js: js if js and all(j['status'] in ('done', 'failed') for j in js) else None)([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party']), 120)
        check(jobs and all(j['status'] == 'done' for j in jobs), '組隊工作完成' + ('' if jobs and all(j['status'] == 'done' for j in jobs) else '：' + '；'.join(f"{j['fromName']} {j['status']} {j['lastMsg']}" for j in (jobs or []))))
        for a, c in (('A1', 'c1'), ('A2', 'c3')):
            mc = mock_char(a, c); ms = (mc.get('autoSell') or {}).get('maps', {}).get(MAP)
            check(mc['map'] == MAP and ms and ms['enabled'] and sorted(ms['itemIds']) == sell['itemIds'], f'{c} 換到 {MAP} 並套用看板的自動販售（{ms}）')

        print('3. 總覽、派工顯示全身照（2D）')
        await d.evaluate("localStorage.setItem('boardView', 'pipe')")
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(2000)
        n = await d.locator('#overview table.ov img.ava.ov').count()
        check(n >= 2, f'總覽角色欄有 {n} 張全身照')
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        check(await d.evaluate('ui.board.view') == 'factory', '舊的「流水線」設定自動改回城鎮圖')
        check(await d.locator('[data-bview2=pipe]').count() == 0, '沒有 3D 流水線按鈕')
        n = await d.locator('#bdFactory .tav img.ava.tv').count()
        check(n >= 2, f'城鎮圖的角色有 {n} 張全身照')
        await d.click('#bdViewSeg [data-bview2=list]'); await d.wait_for_timeout(800)
        await d.click('#bdViewSeg [data-bview2=factory]'); await d.wait_for_timeout(800)
        await d.screenshot(path='/tmp/fac_ava.png')
        s3, _ = http('GET', 'http://127.0.0.1:8787/three-bundle.mjs')
        check(s3 == 404, '3D 檔案已移除')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
