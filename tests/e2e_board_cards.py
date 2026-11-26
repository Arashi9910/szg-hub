"""派工卡片（v0.70）：預設卡片檢視 → 地圖卡片「＋ 加角色」派工、點角色取消 → 角色清單點整列＋Shift 多選「派過去」→ 套用派工（換圖後開始掛機）→
自己加的地圖不會被自動移除、同步自動放上來的會、📌 留著 → 匯出／匯入設定檔"""
import asyncio, os, sys, time, json
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'
from harness import Env, hub_json, http, http_raw, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)
def mock_char(acct, cid): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]
def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)
def board(g='A'): return (hub_json('GET', '/api/data')['settings'].get('boards') or {}).get(g) or {}
def lanes(g='A'): return [m for l in (board(g).get('lanes') or {}).values() for m in l]
async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boardSync': False, 'boardPruneMin': 0.1})
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 1000}, accept_downloads=True); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.evaluate("ui.board.group = 'A'; renderBoard()"); await d.wait_for_timeout(300)

        print('1. 預設是卡片；加地圖、＋加角色')
        check(await d.is_visible('#bdLanes') and not await d.is_visible('#bdFactory .fnode'), '預設顯示卡片（不是工廠圖）')
        TRAIN = 'gms104040000'
        await d.select_option('[data-bdadd="train"]', TRAIN); await d.wait_for_timeout(800)
        check(TRAIN in lanes() and not (board().get('auto') or {}).get(TRAIN), '自己加的地圖放上看板（不是自動的）')
        await d.click(f'.bd-card[data-bddrop="{TRAIN}"] [data-bdaddopen]'); await d.wait_for_timeout(400)
        check(await d.locator('[data-bdpk="c1|' + TRAIN + '"]').count() == 0, '已經在這張圖的 c1 不會出現在加角色清單')
        await d.click(f'[data-bdpk="c4|{TRAIN}"]'); await d.wait_for_timeout(800)
        check(board().get('assign', {}).get('c4') == TRAIN, '＋加角色：c4 派到射手訓練場')
        check('待套用' in await d.inner_text(f'.bd-card[data-bddrop="{TRAIN}"]'), '卡片上 c4 標「待套用」')
        await d.click(f'[data-bdrm="c4|{TRAIN}"]'); await d.wait_for_timeout(800)
        check('c4' not in board().get('assign', {}), '點卡片上的角色：取消派工')
        await d.click(f'[data-bdrm="c1|{TRAIN}"]'); await d.wait_for_timeout(800)
        check(board().get('assign', {}).get('c1') == '__pool', '人就在這張圖的 c1 點掉 → 標「不派工」')

        print('2. 角色清單：點整列＋Shift 多選，派過去')
        rows = d.locator('#bdChars tr.pickrow')
        n = await rows.count()
        ids = [await rows.nth(i).locator('[data-bdcpick]').get_attribute('data-bdcpick') for i in range(n)]
        check(set(ids) >= {'c1', 'c3', 'c4'}, f'A 組角色都在清單上（{ids}）')
        await rows.nth(0).locator('td').nth(1).click(); await rows.nth(n - 1).locator('td').nth(1).click(modifiers=['Shift']); await d.wait_for_timeout(300)
        check(await d.inner_text('#bdCN') == str(n), f'點第一列、Shift 點最後一列 → 選 {n} 隻')
        await d.select_option('#bdCTo', TRAIN); await d.click('#bdCGo'); await d.wait_for_timeout(800)
        a = board().get('assign', {})
        check(all(a.get(i) == TRAIN for i in ids if mock_char({'c1': 'A1', 'c3': 'A2', 'c4': 'A3'}[i], i)['map'] != TRAIN), f'勾選的都派到射手訓練場（{a}）')

        print('3. 套用派工：換圖後開始掛機')
        await d.click('#bdApply'); await d.wait_for_timeout(1000)
        ok3 = await wait(lambda: (lambda c: c['map'] == TRAIN and c['auto'])(mock_char('A3', 'c4')), 60)
        check(ok3, 'c4 換到射手訓練場，而且有開始掛機（真實遊戲換圖會停止掛機）')

        print('4. 地圖不會亂消失')
        MAN = 'gms100010000'
        await d.select_option('[data-bdadd="scroll"]', MAN); await d.wait_for_timeout(500)
        hub_json('POST', '/api/settings', {'boardSync': True}); await d.evaluate('poll(true)')
        AUTO = 'gms104000400'
        game('A3', {'type': 'map', 'map': AUTO, 'characterId': 'c4'})
        ok4 = await wait(lambda: AUTO in lanes() and (board().get('auto') or {}).get(AUTO), 40)
        check(ok4, '同步把 c4 所在的地圖放上看板，標成自動放上來的')
        game('A3', {'type': 'map', 'map': TRAIN, 'characterId': 'c4'})
        gone = await wait(lambda: AUTO not in lanes(), 60, 2)
        check(gone, '自動放上來的地圖沒人後被移除')
        await asyncio.sleep(8)
        check(MAN in lanes(), '自己加的空地圖一直留著')
        game('A3', {'type': 'map', 'map': AUTO, 'characterId': 'c4'})
        await wait(lambda: AUTO in lanes(), 40)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        await d.click(f'[data-bdpin="{AUTO}"]'); await d.wait_for_timeout(800)
        check(not (board().get('auto') or {}).get(AUTO), '📌 留著：不再是自動的')
        game('A3', {'type': 'map', 'map': TRAIN, 'characterId': 'c4'})
        await asyncio.sleep(25)
        check(AUTO in lanes(), '📌 過的地圖沒人也不會被移除')

        print('5. 匯出／匯入')
        async with d.expect_download() as dl:
            await d.click('#bdExport')
        path = await (await dl.value).path()
        data = json.load(open(path, encoding='utf-8'))
        check(data['kind'] == 'board' and TRAIN in data['groups']['A']['lanes']['train'] and 'assign' not in data['groups']['A'], '匯出：A 組的地圖、路線（不含角色指派）')
        data['groups']['B'] = {'lanes': {'train': [], 'scroll': [], 'gear': ['gms104040000']}, 'sell': {'gms104040000': {'enabled': True, 'itemIds': [1082149]}}, 'goals': {}}
        data['groups']['A']['lanes']['train'].append('gms_not_exist')
        f = '/tmp/board_import.json'; json.dump(data, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
        await d.set_input_files('#bdImportFile', f); await d.wait_for_timeout(1500)
        bb = board('B')
        check('gms104040000' in bb.get('lanes', {}).get('gear', []) and bb.get('sell', {}).get('gms104040000', {}).get('itemIds') == [1082149], '匯入：B 組加了地圖和販售範本')
        check(MAN in lanes() and 'gms_not_exist' not in lanes(), '原本的地圖保留，不存在的地圖略過')
        await d.screenshot(path='/tmp/board_cards.png', full_page=True)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
