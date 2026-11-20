"""攤位逾時下架：放太久沒賣出的商品自動下架回背包；賣掉一部分會重新計時；下架過的東西不再自動上架，可以恢復"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, http_raw, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

def listings():
    st = next((x for x in hub_json('GET', '/api/market')['stalls'] if x['charId'] == 'c1'), None)
    return {l['name']: l for l in (st or {}).get('listings', [])}

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        # 36 秒沒賣出就下架；另外設一條會上架紅色藥水的規則（試跑），用來確認下架後不再自動上架
        hub_json('POST', '/api/settings', {'market': {'delistMode': 'auto', 'delistHours': 0.01, 'mode': 'preview', 'chars': {'c1': True}, 'autoClaim': False,
            'rules': [{'on': True, 'name': '紅藥', 'target': 'item', 'ff': {'kinds': [], 'incKeys': ['i2000000'], 'excKeys': []}, 'keepQty': 0, 'perListing': 9999, 'price': {'base': 'fixed', 'fixed': 100, 'floor': 50}}]}})
        http('GET', MOCK + '/__mock/stall?acct=A1&char=c1')
        inv0 = mock_char('A1', 'c1')['inventory']
        game('A1', {'type': 'marketList', 'kind': 'item', 'item': 'i2000000', 'qty': 10, 'price': 100, 'characterId': 'c1'})
        game('A1', {'type': 'marketList', 'kind': 'item', 'item': 'i2000003', 'qty': 5, 'price': 100, 'characterId': 'c1'})
        pages = await env.open_accounts(['A1'])
        await pages[0].evaluate("localStorage.setItem('__gm:testStallMs', '15000')")
        await env.wait_chars(1)
        print('1. 攤位回報、開始計時')
        ls = await wait(lambda: listings() if len(listings()) == 2 else None, 70)
        check(ls, '中控看到攤位上的 2 件商品')
        age = hub_json('GET', '/api/market')['age'].get('c1', {})
        check(len(age) == 2, '兩件都開始計時')
        print('2. 紅色藥水被買走一部分 → 重新計時')
        lid = ls['紅色藥水']['id']
        http('GET', MOCK + f'/__mock/stall?acct=A1&char=c1&sell={lid}&qty=3')
        first0 = age[lid]
        await wait(lambda: hub_json('GET', '/api/market')['age'].get('c1', {}).get(lid, 0) > first0, 40)
        check(hub_json('GET', '/api/market')['age']['c1'][lid] > first0, '紅色藥水的計時重設了')
        print('3. 藍色藥水先逾時下架、紅色藥水還在')
        gone = await wait(lambda: '藍色藥水' not in listings(), 90)
        check(gone, '藍色藥水已下架')
        check('紅色藥水' in listings(), '紅色藥水（剛賣出一部分）還在架上')
        check(mock_char('A1', 'c1')['inventory'].get('i2000003', 0) == inv0.get('i2000003', 0), '藍色藥水 5 個回到背包')
        print('4. 紅色藥水之後也下架')
        gone = await wait(lambda: '紅色藥水' not in listings(), 90)
        check(gone, '紅色藥水已下架')
        check(mock_char('A1', 'c1')['inventory'].get('i2000000', 0) == inv0.get('i2000000', 0) - 3, '剩下的 7 個回到背包')
        mk = hub_json('GET', '/api/market')
        check({b['k'] for b in mk['blocked']} >= {'i:i2000000', 'i:i2000003'}, '兩樣都列入「不再自動上架」')
        check(any('逾時下架' in l['msg'] for l in mk['log']), '紀錄有「逾時下架」')
        print('5. 不再自動上架，可以恢復')
        plan = hub_json('GET', '/api/market/plan?charId=c1')
        check(any(x['name'] == '紅色藥水' and '逾時下架' in x['why'] for x in plan['skipped']) and not plan['entries'], '自動上架計畫略過紅色藥水')
        hub_json('POST', '/api/market/unblock', {'k': 'i:i2000000'})
        plan = hub_json('GET', '/api/market/plan?charId=c1')
        why = [x['why'] for x in plan['skipped'] if x['name'] == '紅色藥水'] + (['會上架'] if any(e['name'] == '紅色藥水' for e in plan['entries']) else [])
        check(why and not any('逾時下架' in w for w in why), '恢復後不再因為逾時下架被略過（現在：' + '、'.join(why) + '）')
        print('6. 面板')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto('http://127.0.0.1:8787/'); await dash.wait_for_timeout(1500)
        await dash.click('nav button[data-tab="market"]'); await dash.wait_for_timeout(2500)
        await dash.click('#mkBlockedBox summary'); await dash.wait_for_timeout(300)
        txt = await dash.inner_text('#mkBlocked')
        check('藍色藥水' in txt and '紅色藥水' not in txt, '面板的清單只剩藍色藥水')
        await dash.screenshot(path='/tmp/delist.png', full_page=False)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
