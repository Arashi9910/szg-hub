"""冒煙測試：3 個帳號連上中控、面板載入沒錯誤、模擬遊戲的公會倉庫與批次衝卷 API 可用"""
import asyncio, json, sys
from harness import Env, hub_json, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def game(page, action):
    return await page.evaluate("""async a => { a.requestId = a.requestId || crypto.randomUUID(); a.characterId = a.characterId || sessionStorage.getItem('mapleCharacter');
      const r = await fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(a) }); return await r.json(); }""", action)

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        print('1. 帳號回報')
        d = await env.wait_chars(3)
        chars = d['chars']
        check(set(chars) >= {'c1', 'c3', 'c4'}, '收到 c1、c3、c4：' + ', '.join(chars))
        c1 = chars.get('c1', {})
        check(c1.get('playerCode') == 'A1B2C3D4E5F6', '本尊帳號 ID 正確')
        check(any(g['name'] == '工地手套' for g in c1.get('gear', [])), '裝備清單有背包裝備')
        check(any(i['name'] == '手套攻擊卷軸 60%' for i in c1.get('items', [])), '道具清單有卷軸')

        print('2. 面板')
        ctx = await env.browser.new_context(); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto(HUB + '/'); await dash.wait_for_timeout(3000)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
        check('本尊劍士' in await dash.inner_text('body'), '面板顯示角色名稱')

        print('3. 模擬遊戲 API（下一階段開發用）')
        r = await game(pages[0], {'type': 'guildWarehouseBatch', 'op': 'deposit', 'items': [{'kind': 'item', 'item': 'i2040801', 'qty': 5}]})
        check(r.get('summary', {}).get('guildWarehouse', {}).get('items', {}).get('i2040801') == 5, '存 5 張卷軸到公會倉庫（summary.guildWarehouse.items）')
        r = await game(pages[2], {'type': 'guildWarehouseBatch', 'op': 'withdraw', 'items': [{'kind': 'item', 'item': 'i2040801', 'qty': 2}]})
        check(r.get('summary', {}).get('guildWarehouse', {}).get('items', {}).get('i2040801') == 3 and r['character']['inventory'].get('i2040801', 0) >= 2, '另一個帳號從公會倉庫領 2 張（倉庫剩 3）')
        bag = (await game(pages[0], {'type': 'sync'}))['character']['equipmentBag']
        glove = next(g for g in bag if g['name'] == '工地手套')
        r = await game(pages[0], {'type': 'guildWarehouseBatch', 'op': 'deposit', 'items': [{'kind': 'gear', 'uid': glove['uid']}]})
        check(len(r.get('summary', {}).get('guildWarehouse', {}).get('gear', [])) == 1, '裝備存入公會倉庫')
        r = await game(pages[0], {'type': 'guildWarehouseBatch', 'op': 'withdraw', 'items': [{'kind': 'gear', 'uid': glove['uid']}]})
        check(not r.get('summary', {}).get('guildWarehouse', {}).get('gear'), '裝備領回')
        money0 = r['character']['money']
        r = await game(pages[0], {'type': 'artisanScroll', 'uid': glove['uid'], 'item': 'i2040801', 'count': 5, 'stopAfterSuccesses': 3, 'expectedSlots': glove['slots']})
        res = r.get('character', {}).get('lastArtisan') or {}
        n = len(res.get('attempts') or [])
        check(n >= 1 and money0 - r['character']['money'] == n * 100000, f"神匠之魂：衝 {n} 次、成功 {res.get('successes')} 次，每次扣 10 萬")
        r = await game(pages[0], {'type': 'autoSell', 'map': 'gms100010000', 'config': {'enabled': True, 'itemIds': [4000000]}})
        check('所在地圖' in (r.get('error') or ''), '自動販售只接受目前地圖')

    errors = [l for l in env.logs if 'pageerror' in l]
    check(not errors, '遊戲頁沒有 JS 錯誤' + ('：' + errors[0] if errors else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

asyncio.run(main())
