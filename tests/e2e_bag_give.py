"""背包「給…」抽屜（取代交易頁的分發）：改數量、加楓幣、只轉楓幣、自己給自己擋下；總覽自動化總表"""
import asyncio, json, sys
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2']); await env.wait_chars(2)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2500)

        print('1. 總覽自動化總表')
        auto = ' '.join((await d.inner_text('#ovAuto')).split())
        check('自動化' in auto and '掛機續掛' in auto and '公倉自動存入' in auto and '知識王自動作答' in auto, '列出各自動功能：' + auto[:100])
        await d.click('[data-autotog="quiz"]'); await d.wait_for_timeout(800)
        check(hub_json('GET', '/api/data')['settings'].get('quizAuto') is True, '知識王開關一按就開（存到設定）')
        await d.click('[data-autotog="gear"]'); await d.wait_for_timeout(800)
        check(hub_json('GET', '/api/data')['settings'].get('autoSell', {}).get('mode', 'off') == 'off' and await d.locator('#gViewSeg').is_visible(), '撿到自動處理還沒選角色：不會開，直接帶到設定')
        await d.click('nav button[data-tab=overview]'); await d.wait_for_timeout(400)
        check(await d.locator('#ovAuto input.sw').count() == 7 and await d.is_checked('[data-autotog="quiz"]'), '7 個可以直接切換的開關，狀態正確')
        await d.click('[data-autogo="guild"]'); await d.wait_for_timeout(600)
        check(await d.is_visible('#gRulesDrawer .mode-seg'), '點「公倉自動存入」跳到公倉、打開存入規則抽屜')
        await d.keyboard.press('Escape')
        await d.click('nav button[data-tab=overview]'); await d.wait_for_timeout(400)
        await d.click('[data-autogo="gear"]'); await d.wait_for_timeout(600)
        check('on' in (await d.get_attribute('#gViewSeg button[data-gv="auto"]', 'class') or ''), '點「撿到裝備自動處理」跳到裝備頁的那個畫面')

        print('2. 交易頁只剩收集')
        await d.click('nav button[data-tab=trade]'); await d.wait_for_timeout(400)
        t = await d.inner_text('#trade')
        check('收集' in t and '建立分發工作' not in t and await d.locator('#gFrom').count() == 0, '分發已移除，留下指到背包的說明')

        print('3. 背包選東西 →「給…」')
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(500)
        await d.click('[data-bview="list"]'); await d.wait_for_timeout(800)
        check(await d.locator('#bGuild').count() == 0, '背包「含公倉」已移除')
        await d.click('tr[data-bpick="c1|i:i2040801"]'); await d.wait_for_timeout(200)
        g = await d.get_attribute('#bagOut tr[data-bpick^="c1|g:"]', 'data-bpick')
        await d.click(f'tr[data-bpick="{g}"]'); await d.wait_for_timeout(300)
        await d.click('[data-bact="give"]'); await d.wait_for_timeout(500)
        check(await d.is_visible('#bGiveDrawer'), '打開「給角色」抽屜')
        await d.select_option('#bgTo', 'c3'); await d.wait_for_timeout(300)
        await d.fill('[data-bgqty="c1|i2040801"]', '3')
        await d.fill('[data-bgmoney="c1"]', '50000'); await d.wait_for_timeout(300)
        summ = await d.inner_text('#bgSum')
        check('弓箭分身' in summ and '楓幣 50,000' in summ, '摘要：' + summ)
        await d.click('#bgCreate'); await d.wait_for_timeout(1200)
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'give']
        b = js[-1]['batches'] if js else []
        items = [x for bt in b for x in bt['items']]; gear = [x for bt in b for x in bt['gear']]; money = sum(bt.get('money') or 0 for bt in b)
        check(js and js[-1]['fromCharId'] == 'c1' and js[-1]['toCharId'] == 'c3', '建立交易工作 本尊劍士 → 弓箭分身')
        check(items == [{'key': 'i2040801', 'name': '手套攻擊卷軸 60%', 'cat': items[0].get('cat') if items else None, 'qty': 3}] and len(gear) == 1 and money == 50000, f'數量照改的 3 張、1 件裝備、楓幣 5 萬：{items} {len(gear)} {money}')
        await d.keyboard.press('Escape')

        print('4. 只轉楓幣；同帳號擋下')
        await d.click('#bGiveMoney'); await d.wait_for_timeout(400)
        await d.select_option('#bgTo', 'c1'); await d.select_option('#bgAdd', 'c1'); await d.wait_for_timeout(300)
        check('就是收的人' in await d.inner_text('#bgOut') and await d.is_disabled('#bgCreate'), '收的人自己被加進來時標出來、不能建立')
        await d.select_option('#bgAdd', 'c3'); await d.wait_for_timeout(300)
        await d.fill('[data-bgmoney="c3"]', '1000'); await d.wait_for_timeout(300)
        n0 = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'give'])
        await d.click('#bgCreate'); await d.wait_for_timeout(1200)
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'give']
        check(len(js) == n0 + 1 and js[-1]['fromCharId'] == 'c3' and js[-1]['batches'][0]['money'] == 1000, '只轉楓幣：弓箭分身 → 本尊劍士 1,000（收的人自己略過）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
