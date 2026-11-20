"""派工空地圖自動移除：沒有角色的地圖超過設定時間就從看板移除（販售範本保留）；有角色、有派工的不動；可以關掉"""
import asyncio, sys, time
from harness import Env, hub_json

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def board():
    st = hub_json('GET', '/api/data')['settings']
    return (st.get('boards') or {}).get('A') or st.get('board') or {}, st

async def until(d, fn, sec=60):
    end = time.time() + sec
    while time.time() < end:
        await d.evaluate('poll(true)')
        v = fn()
        if v: return v
        await asyncio.sleep(2)
    return None

async def main():
    async with Env() as env:
        # 射手訓練場：本尊劍士在那裡；弓箭手村北邊山丘：有派工（本尊小號要去）；傷害測試場：沒人 → 應該被移除
        bd = {'lanes': {'train': ['gms104040000', 'gms100010000', 'gms990040001'], 'scroll': [], 'gear': []}, 'assign': {'c2': 'gms100010000'},
              'sell': {'gms990040001': {'enabled': True, 'itemIds': [4000000]}}, 'goals': {}}
        hub_json('POST', '/api/settings', {'board': bd, 'boards': {'A': bd}, 'boardPruneMin': 0.3, 'boardSync': False})
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        ctx = await env.browser.new_context(viewport={'width': 1300, 'height': 800}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1000)
        print('1. 沒有角色的地圖過了時間就移除')
        b = await until(d, lambda: (lambda b: b if 'gms990040001' not in b[0]['lanes']['train'] else None)(board()))
        check(b, '傷害測試場 1（沒人）已從看板移除')
        check(b and {'gms104040000', 'gms100010000'} <= set(b[0]['lanes']['train']), '有人的、有派工的地圖還在')
        check(b and (b[0].get('sell') or {}).get('gms990040001'), '它的販售範本保留著')
        check(b and any('沒有角色' in l['msg'] for l in b[1].get('boardSyncLog', [])), '紀錄有寫')
        print('2. 關掉 → 不移除')
        await d.click('#bdPrune'); await d.wait_for_timeout(500)
        bd2, _ = board(); bd2 = {**bd2, 'lanes': {**bd2['lanes'], 'train': bd2['lanes']['train'] + ['gms990040001']}}
        hub_json('POST', '/api/settings', {'board': bd2, 'boards': {'A': bd2}})
        for _ in range(12): await d.evaluate('poll(true)'); await asyncio.sleep(2)
        check('gms990040001' in board()[0]['lanes']['train'], '關掉後空地圖留著')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
