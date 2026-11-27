"""派工城鎮圖（v0.73）：A、B 組合在一起，一張圖一個節點；同隊（遊戲裡的隊伍）用隊伍框包起來、拖隊伍框整隊走，沒組隊的單隻走；
A／B 篩選；點兩下開角色抽屜；去處規則（共用規則、地圖自訂設定、公倉／強化）；套用派工時送出去處規則算好的自動販售"""
import os
os.environ['MOCK_PARTY'] = 'c2,c3'  # 弓箭分身（A 組）＋本尊小號（B 組）同隊
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK, game_sell

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def settings(): return hub_json('GET', '/api/data')['settings']

async def drag(d, src, dst):
    a = await d.locator(src).first.bounding_box(); b = await d.locator(dst).first.bounding_box()
    await d.mouse.move(a['x'] + a['width'] / 2, a['y'] + a['height'] / 2); await d.mouse.down()
    for i in range(1, 9): await d.mouse.move(a['x'] + (b['x'] + b['width'] / 2 - a['x']) * i / 8, a['y'] + (b['y'] + b['height'] / 2 - a['y']) * i / 8); await d.wait_for_timeout(30)
    await d.mouse.up(); await d.wait_for_timeout(1500)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        end = time.time() + 30
        while time.time() < end and not (hub_json('GET', '/api/world') or {}).get('maps'): await asyncio.sleep(1)
        # 舊版的設定（A 組：射手訓練場；B 組：北邊山丘），沒有販售範本 → 轉換後是「沿用遊戲設定」
        hub_json('POST', '/api/settings', {'boards': {'A': {'lanes': {'train': ['gms104040000'], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {}, 'goals': {}},
                                                       'B': {'lanes': {'train': ['gms100010000'], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {}, 'goals': {}}}, 'boardSync': False, 'boardPrune': False})
        ctx = await env.browser.new_context(viewport={'width': 1600, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        mode = {'accept': True}; msgs = []
        async def on_dialog(dl):
            msgs.append(dl.message)
            await (dl.accept() if mode['accept'] else dl.dismiss())
        d.on('dialog', lambda dl: asyncio.ensure_future(on_dialog(dl)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)

        print('1. 城鎮圖：A、B 組合在一起，一張圖一個節點；隊伍框')
        ma, mb = '.tmap[data-fn="m:gms104040000"]', '.tmap[data-fn="m:gms100010000"]'
        check(await d.locator(ma).count() == 1 and await d.locator(mb).count() == 1 and await d.locator('.tmap').count() == 2, 'A 組、B 組原本的地圖都畫出來（各一個節點）')
        lanes = lambda g: sum((settings()['boards'][g]['lanes'] or {}).values(), [])
        await asyncio.sleep(1)
        check(all([await d.locator(f'.tbuild[data-fn="{k}"]').count() == 1 for k in ['bag', 'shop', 'guild', 'forge']]), '城鎮有背包、商店、公倉、強化')
        check(await d.locator(f'{ma} [data-tav="c1"]').count() == 1 and await d.locator(f'{ma} [data-tav="c3"]').count() == 1, '射手訓練場上站著本尊劍士、弓箭分身')
        check(await d.locator(f'{ma} .tparty [data-tav="c3"]').count() == 1 and await d.locator(f'{ma} .tparty [data-tav="c1"]').count() == 0, '弓箭分身在隊伍框裡，本尊劍士（沒組隊）不在')
        check(await d.locator('[data-tpool] .tparty [data-tav="c2"].bgc').count() == 1, 'B 組的本尊小號（同隊、背景掛機）在「未派遣」的隊伍框裡')
        check('1/2' in await d.inner_text(f'{ma} .tparty .tp-hd'), '隊伍框標出這裡只有 1/2 人')
        check(await d.locator('.tav .grp.gB').count() >= 1, '頭像上有 A／B 標籤')
        check(await d.locator(f'#facWires path[data-w="m:gms104040000>bag"]').count() == 1, '有人的地圖拉線到城鎮')
        check('沿用遊戲' in await d.inner_text(ma) or '沒開' in await d.inner_text(ma), '舊設定沒有販售範本 → 不動遊戲設定')
        await d.click('[data-tgf="B"]'); await d.wait_for_timeout(400)
        check(await d.locator(f'{ma} [data-tav="c1"].tdim').count() == 1 and await d.locator('[data-tav="c2"].tdim').count() == 0, '只看 B 組：A 組的角色變淡')
        await d.click('[data-tgf=""]'); await d.wait_for_timeout(400)

        print('2. 開新地圖、沒組隊的單隻走、隊伍框整隊走（A、B 混合）')
        await d.select_option('[data-taddmap]', 'gms104000400'); await d.wait_for_timeout(1200)
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        mn = '.tmap[data-fn="m:gms104000400"]'
        check(await d.locator(f'{mn}.tm-empty').count() == 1, '新地圖（沒有角色，排在外圈）')
        check('gms104000400' in lanes('A') and 'gms104000400' in lanes('B'), '新地圖兩組都有')
        await drag(d, f'{ma} [data-tav="c1"] .tav-n', mn)
        a = settings()['boards']['A']['assign']
        check(a.get('c1') == 'gms104000400' and a.get('c3') != 'gms104000400', f'拖本尊劍士：只有它過去（{a}）')
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        await drag(d, f'{ma} .tparty .tp-hd', mn)
        a, b = settings()['boards']['A']['assign'], settings()['boards']['B']['assign']
        check(a.get('c3') == 'gms104000400' and b.get('c2') == 'gms104000400', f'拖隊伍框：弓箭分身（A）和本尊小號（B）一起過去（A {a}、B {b}）')
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        check(await d.locator(f'{mn} .tparty [data-tav="c2"]').count() == 1 and await d.locator(f'{mn} .tparty [data-tav="c3"]').count() == 1, '新地圖上同一個隊伍框有兩隻')
        await drag(d, f'{mn} [data-tav="c3"] .tav-n', '[data-tpool]')
        a, b = settings()['boards']['A']['assign'], settings()['boards']['B']['assign']
        check(a.get('c3') != 'gms104000400' and b.get('c2') != 'gms104000400', '拖隊伍裡的一隻回「未派遣」：整隊一起回去')
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        await d.click('[data-tpool] .tparty .tp-hd'); await d.wait_for_timeout(400)
        check(await d.locator('.tav.sel').count() == 2, '點一下隊伍框：整隊選起來')
        await drag(d, '[data-tpool] [data-tav="c2"] .tav-n', mn)
        check(settings()['boards']['B']['assign'].get('c2') == 'gms104000400' and settings()['boards']['A']['assign'].get('c3') == 'gms104000400', '拖回新地圖')

        print('3. 點兩下開角色抽屜')
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        await d.dblclick('.tmap [data-tav="c1"] .tav-n'); await d.wait_for_timeout(600)
        check(await d.locator('#charDrawer').count() == 1 and '本尊劍士' in await d.inner_text('#charDrawer'), '角色抽屜打開，顯示本尊劍士')
        await d.click('#charDrawer [data-cdclose]'); await d.wait_for_timeout(300)
        await d.click('.tmap [data-tav="c3"] [data-tinfo]'); await d.wait_for_timeout(400)
        check('弓箭分身' in await d.inner_text('#charDrawer'), '按頭像的 i 也能打開')
        await d.click('#charDrawer [data-cdclose]'); await d.wait_for_timeout(300)

        print('4. 共用規則、地圖自訂設定、公倉、強化')
        await d.click('.fac-hud [data-trules]'); await d.wait_for_timeout(500)
        await d.check('[data-dscope="board"]'); await d.wait_for_timeout(800)
        check(settings()['dest']['board'] is True, '打開「派工地圖套用」')
        await d.click('[data-drule="scroll|shop"]'); await d.wait_for_timeout(800)
        check(settings()['dest']['rule']['scroll'] == 'shop', '共用規則：卷軸改成賣')
        await d.click('[data-drule="scroll|bag"]'); await d.wait_for_timeout(800)
        await d.click(f'{mn} [data-tmcfg]'); await d.wait_for_timeout(500)
        txt = await d.inner_text('#bdSell')
        check('海岸草叢3' in txt and '照共用規則' in txt, '新地圖照共用規則')
        await d.click('[data-dset="1082149|bag"]'); await d.wait_for_timeout(800)
        ov = settings()['dest']['over'].get('gms104000400') or {}
        check((ov.get('items') or {}).get('1082149') == 'keep', f'這張圖把手套改成留著：{ov}')
        check('這張圖改過' in await d.inner_text('#bdSell'), '標成這張圖改過')
        await d.click('[data-dset="2040805|guild"]'); await d.wait_for_timeout(800)
        check(2040805 in (settings().get('guildDep') or {}).get('ids', []), '卷軸選「公倉」→ 加進公倉的存入規則')
        await d.click('[data-dset="4000016|forge"]'); await d.wait_for_timeout(800)
        check(4000016 in settings()['dest'].get('forge', []), '紅寶殼選「強化」→ 送去強化')
        sell = hub_json('GET', '/api/data')['destSell'].get('gms104000400')
        check(sell and sell['itemIds'] == [], f'這張圖現在什麼都不賣（手套留著、王的掉落留著、卷軸存公倉、紅寶殼送強化）：{sell}')
        await d.click('[data-dset="4000016|shop"]'); await d.wait_for_timeout(800)
        check(4000016 not in settings()['dest'].get('forge', []), '改回商店就不送強化')
        await d.click('[data-dclose]'); await d.wait_for_timeout(300)

        print('5. 套用派工：換圖並設定去處規則算好的自動販售')
        sell = hub_json('GET', '/api/data')['destSell'].get('gms104000400')
        check(sell and sell['enabled'] and sell['itemIds'] == [4000016], f'算好的：只賣紅寶殼（{sell}）')
        mode['accept'] = True; msgs.clear()
        await d.click('#bdApply'); await d.wait_for_timeout(800)
        check(any('本尊劍士' in m and '海岸草叢3' in m for m in msgs) and any('本尊小號' in m or '背景' in m for m in msgs) is not None, '確認視窗列出要移動的角色')
        end = time.time() + 40
        while time.time() < end and mock_state()['accounts']['A1']['chars']['c1']['map'] != 'gms104000400': await asyncio.sleep(1)
        c1 = mock_state()['accounts']['A1']['chars']['c1']
        check(c1['map'] == 'gms104000400', '本尊劍士換到海岸草叢3')
        end = time.time() + 20
        while time.time() < end and not ((mock_state()['accounts']['A1']['chars']['c1'].get('autoSell') or {}).get('maps') or {}).get('gms104000400'): await asyncio.sleep(1)
        c1 = mock_state()['accounts']['A1']['chars']['c1']
        asell = game_sell(c1, 'gms104000400')
        check(asell.get('enabled') and asell.get('itemIds') == [4000016], f'遊戲的自動販售照去處規則：{asell}')

        print('6. 重新排列、清單檢視')
        await d.click('[data-fzoom="layout"]'); await d.wait_for_timeout(800)
        check(not (settings()['boards']['A'].get('tpos') or {}) and not (settings()['boards']['B'].get('tpos') or {}), '重新排列清掉自己拖過的位置')
        await d.click('[data-bview2="list"]'); await d.wait_for_timeout(800)
        check(await d.locator('#bdLanes .lane').count() == 1, '清單檢視只剩一欄地圖（沒有三條線）')
        await d.click('[data-bview2="factory"]'); await d.wait_for_timeout(500)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
