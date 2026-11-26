"""派工（v0.70 保留的修正）：套用派工換圖後開始掛機 → 同步自動放上來的空地圖會移除、自己加的不會、📌 留著 → 匯出／匯入設定檔"""
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
        TRAIN, MAN, AUTO = 'gms104040000', 'gms100010000', 'gms104000400'
        bd = {'lanes': {'train': [TRAIN], 'scroll': [MAN], 'gear': []}, 'assign': {'c4': TRAIN}, 'sell': {}, 'goals': {}}
        hub_json('POST', '/api/settings', {'board': bd, 'boards': {'A': bd}, 'boardSync': False, 'boardPruneMin': 0.1})
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 1000}, accept_downloads=True); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.evaluate("ui.board.group = 'A'; renderBoard()")
        check(await d.evaluate('ui.board.view') == 'factory', '派工預設還是工廠圖（v0.70.2 改回原本的畫面）')
        await d.click('#bdViewSeg [data-bview2=list]'); await d.wait_for_timeout(800)
        check(await d.locator('#bdPool').count() == 1, '清單檢視：左邊角色池、拖曳派工（原本的樣子）')

        print('1. 套用派工：換圖後開始掛機')
        await wait(lambda: 'c4' in (hub_json('GET', '/api/data').get('tabs') or {}), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(1500)
        await d.click('#bdApply'); await d.wait_for_timeout(1000)
        ok1 = await wait(lambda: (lambda c: c['map'] == TRAIN and c['auto'])(mock_char('A3', 'c4')), 60)
        check(ok1, 'c4 換到射手訓練場，而且有開始掛機（真實遊戲換圖會停止掛機）')

        print('2. 地圖不會亂消失')
        hub_json('POST', '/api/settings', {'boardSync': True}); await d.evaluate('poll(true)')
        game('A3', {'type': 'map', 'map': AUTO, 'characterId': 'c4'})
        check(await wait(lambda: AUTO in lanes() and (board().get('auto') or {}).get(AUTO), 40), '同步把 c4 所在的地圖放上看板，標成自動放上來的')
        game('A3', {'type': 'map', 'map': TRAIN, 'characterId': 'c4'})
        check(await wait(lambda: AUTO not in lanes(), 60, 2), '自動放上來的地圖沒人後被移除')
        check(MAN in lanes(), '自己加的空地圖一直留著')
        game('A3', {'type': 'map', 'map': AUTO, 'characterId': 'c4'})
        await wait(lambda: AUTO in lanes(), 40)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        await d.click(f'[data-bdpin="A|{AUTO}"]'); await d.wait_for_timeout(800)
        check(not (board().get('auto') or {}).get(AUTO), '清單的地圖卡片按 📌 留著：不再是自動的')
        game('A3', {'type': 'map', 'map': TRAIN, 'characterId': 'c4'})
        await asyncio.sleep(25)
        check(AUTO in lanes(), '📌 過的地圖沒人也不會被移除')

        print('3. 匯出／匯入')
        async with d.expect_download() as dl:
            await d.click('#bdExport')
        data = json.load(open(await (await dl.value).path(), encoding='utf-8'))
        check(data['kind'] == 'board' and TRAIN in data['groups']['A']['lanes']['train'] and 'assign' not in data['groups']['A'], '匯出：A 組的地圖、路線（不含角色指派）')
        data['groups']['B'] = {'lanes': {'train': [], 'scroll': [], 'gear': [TRAIN]}, 'sell': {TRAIN: {'enabled': True, 'itemIds': [1082149]}}, 'goals': {}}
        data['groups']['A']['lanes']['train'].append('gms_not_exist')
        check(isinstance(data.get('dest'), dict) and 'rule' in data['dest'], '匯出：包含去處規則')
        data['dest']['over'] = {TRAIN: {'items': {'1082149': 'keep'}}}
        f = '/tmp/board_import.json'; json.dump(data, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
        await d.set_input_files('#bdImportFile', f); await d.wait_for_timeout(1500)
        bb = board('B')
        check(TRAIN in bb.get('lanes', {}).get('gear', []) and bb.get('sell', {}).get(TRAIN, {}).get('itemIds') == [1082149], '匯入：B 組加了地圖和販售範本')
        check(MAN in lanes() and 'gms_not_exist' not in lanes(), '原本的地圖保留，不存在的地圖略過')
        dov = (hub_json('GET', '/api/data')['settings'].get('dest') or {}).get('over', {}).get(TRAIN)
        check(dov == {'items': {'1082149': 'keep'}}, f'匯入：去處規則的地圖自訂設定（{dov}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
