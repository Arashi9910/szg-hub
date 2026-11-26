"""照表操課（v0.74）：開著時中控每分鐘把角色所在地圖的自動販售對齊去處規則，不用按套用；沒開不動；改規則後自動再對齊；
在遊戲裡改的會被改回來；沿用遊戲設定的圖不動"""
import asyncio, json, os, sys, time
os.environ['SZG_ENFORCE_MS'] = '3000'
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
def game_sell(a, c, m): return ((mock_char(a, c).get('autoSell') or {}).get('maps') or {}).get(m) or {}
def norm(x): return (bool(x.get('enabled')), sorted(int(i) for i in (x.get('itemIds') or [])))
async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None
MAP = 'gms104040000'  # 射手訓練場：本尊劍士（A1 c1）、弓箭分身（A2 c3）都在這裡

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        await wait(lambda: (hub_json('GET', '/api/world') or {}).get('maps'), 30)
        hub_json('POST', '/api/settings', {'boards': {'A': {'lanes': {'train': [MAP], 'scroll': [], 'gear': []}, 'assign': {}}, 'B': {'lanes': {'train': [], 'scroll': [], 'gear': []}, 'assign': {}}},
                                           'boardSync': False, 'dest': {'board': True, 'boss': False, 'rule': {'gear': 'shop', 'scroll': 'keep', 'book': 'keep', 'other': 'keep', 'boss': 'keep'}, 'over': {}, 'forge': []}})
        want = lambda: norm(hub_json('GET', '/api/data')['destSell'][MAP])
        print('1. 沒開照表操課：不動遊戲')
        w0 = want()
        check(w0[0] and w0[1], f'去處規則算出來要賣小怪的裝備（{w0}）')
        await asyncio.sleep(8)
        check(norm(game_sell('A1', 'c1', MAP)) != w0, '8 秒後遊戲裡還是原本的設定')

        print('2. 從面板打開照表操課 → 自動對齊（兩隻都是，不用按套用）')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.click('.fac-hud [data-trules]'); await d.wait_for_timeout(600)
        await d.check('[data-denforce]'); await d.wait_for_timeout(800)
        check(msgs and '照表操課' in msgs[-1], '開啟前先確認')
        check(hub_json('GET', '/api/data')['settings']['dest'].get('enforce') is True, '存進設定')
        r1 = await wait(lambda: norm(game_sell('A1', 'c1', MAP)) == w0 and norm(game_sell('A2', 'c3', MAP)) == w0)
        check(r1, '本尊劍士、弓箭分身的自動販售都自動改成規則的結果')
        lg = (hub_json('GET', '/api/data').get('destEnforce') or {}).get('log') or []
        check(any(l['charId'] == 'c1' for l in lg) and any(l['charId'] == 'c3' for l in lg), f'有自動套用紀錄（{len(lg)} 筆）')
        await wait(lambda: (hub_json('GET', '/api/data').get('destEnforce') or {}).get('todo') == 0, 20)
        await d.evaluate('poll(true)'); await d.click('.fac-hud [data-trules]'); await d.wait_for_timeout(800)
        txt = await d.inner_text('#bdSell')
        check('目前全部一致' in txt and '最近自動套用' in txt, '面板顯示全部一致和最近紀錄')

        print('3. 改規則 → 自動再對齊')
        hub_json('POST', '/api/settings', {'dest': {'rule': {'gear': 'shop', 'scroll': 'shop', 'book': 'keep', 'other': 'keep', 'boss': 'keep'}}})
        w1 = want()
        check(w1 != w0, f'規則改成卷軸也賣（{w1}）')
        check(await wait(lambda: norm(game_sell('A1', 'c1', MAP)) == w1), '遊戲裡自動跟著改')

        print('4. 在遊戲裡手動改 → 被改回來')
        http('GET', MOCK + f'/__mock/autosell?acct=A1&char=c1&map={MAP}&enabled=0')
        check(norm(game_sell('A1', 'c1', MAP)) == (False, []), '遊戲裡關掉自動販售')
        check(await wait(lambda: norm(game_sell('A1', 'c1', MAP)) == w1), '照表操課改回規則的結果')

        print('5. 沿用遊戲設定的圖不動、關掉照表操課就停')
        hub_json('POST', '/api/settings', {'dest': {'over': {MAP: {'game': True}}, 'rule': {'gear': 'keep', 'scroll': 'keep', 'book': 'keep', 'other': 'keep', 'boss': 'keep'}}})
        await asyncio.sleep(8)
        check(norm(game_sell('A1', 'c1', MAP)) == w1, '這張圖改成沿用遊戲設定：遊戲裡的設定不動')
        hub_json('POST', '/api/settings', {'dest': {'over': {}, 'enforce': False}})
        await asyncio.sleep(8)
        check(norm(game_sell('A1', 'c1', MAP)) == w1, '關掉照表操課：規則變了也不自動改')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
