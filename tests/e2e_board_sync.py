"""派工與遊戲同步：遊戲裡換地圖／改自動販售 → 看板自動跟著改；看板上還沒套用的派工，遊戲沒動就保留；可以關掉"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, http_raw, MOCK, game_sell

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)

def board():
    st = hub_json('GET', '/api/data')['settings']
    return (st.get('boards') or {}).get('A') or st.get('board') or {}, st

async def until(d, fn, sec=40):
    end = time.time() + sec
    while time.time() < end:
        await d.evaluate('poll(true)')
        v = fn()
        if v: return v
        await asyncio.sleep(2)
    return None

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'board': {'lanes': {'train': [], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {}, 'goals': {}}, 'boards': None, 'dest': {'board': True}})
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1000)

        print('1. 第一次同步：角色所在的地圖自動放上看板')
        b = await until(d, lambda: (lambda b: b if 'gms104040000' in (b[0].get('lanes') or {}).get('train', []) else None)(board()))
        check(b, '本尊劍士所在的射手訓練場已放上看板')
        check(b and b[1].get('boardSeen', {}).get('c1', {}).get('map') == 'gms104040000', '記下遊戲目前的狀態')

        print('2. 看板上排了派工（還沒套用），遊戲沒動 → 保留')
        bd, st = board(); bd = {**bd, 'assign': {'c1': 'gms100010000'}}
        bd['lanes']['train'].append('gms100010000')
        hub_json('POST', '/api/settings', {'boards': {'A': bd}, 'board': bd}); await d.evaluate('poll(true)')
        await asyncio.sleep(6); await d.evaluate('poll(true)')
        check(board()[0].get('assign', {}).get('c1') == 'gms100010000', '還沒套用的派工保留著')

        print('3. 在遊戲裡換到別張圖 → 看板以遊戲為準')
        game('A1', {'type': 'map', 'map': 'gms104000400', 'characterId': 'c1'})
        b = await until(d, lambda: (lambda b: b if 'gms104000400' in b[0]['lanes']['train'] else None)(board()))
        check(b, '新地圖（海岸草叢3）自動放上看板')
        check(b and 'c1' not in b[0].get('assign', {}), '看板上舊的派工（弓箭手村北邊山丘）取消')
        check(b and any('在遊戲裡換到' in l['msg'] for l in b[1].get('boardSyncLog', [])), '同步紀錄有寫')

        print('4. 在遊戲裡改自動販售 → 記成這張圖的自訂設定（去處規則）')
        dover = lambda: (hub_json('GET', '/api/data')['settings'].get('dest') or {}).get('over', {}).get('gms104000400')
        rows = hub_json('GET', '/api/world')['autoSellDrops']['gms104000400']
        game('A1', {'type': 'autoSell', 'characterId': 'c1', 'map': 'gms104000400', 'config': {'rule': 2, 'enabled': True, 'itemIds': [int(r[0]) for r in rows if r[4] and int(r[0]) not in (4000016, 2040805)]}})
        ov = await until(d, lambda: dover())
        check(ov and ov.get('rest') == 'keep' and sorted(ov.get('items', {}).keys()) == ['2040805', '4000016'], f'自訂設定＝遊戲的設定（{ov}）')
        sell = hub_json('GET', '/api/data')['destSell'].get('gms104000400')
        check(sell and sorted(sell['itemIds']) == [2040805, 4000016], f'算出來的自動販售跟遊戲一樣（{sell}）')

        print('5. 看板改自訂設定（遊戲沒動）→ 保留看板的')
        hub_json('POST', '/api/settings', {'dest': {'over': {'gms104000400': {'items': {'4000016': 'shop'}, 'rest': 'keep'}}}})
        await asyncio.sleep(6); await d.evaluate('poll(true)'); await asyncio.sleep(2)
        check(list((dover() or {}).get('items', {}).keys()) == ['4000016'], '看板改的設定沒被蓋掉（等套用時才送到遊戲）')

        print('6. 關掉同步 → 遊戲換圖不影響看板')
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        await d.click('#bdSync'); await d.wait_for_timeout(500)
        check(hub_json('GET', '/api/data')['settings'].get('boardSync') is False, '已關閉')
        game('A1', {'type': 'map', 'map': 'gms990040001', 'characterId': 'c1'})
        await asyncio.sleep(10); await d.evaluate('poll(true)'); await asyncio.sleep(2)
        check('gms990040001' not in board()[0]['lanes']['train'], '看板沒有變')
        await d.screenshot(path='/tmp/board_sync.png')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-20:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
