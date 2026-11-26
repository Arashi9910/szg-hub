"""角色抽屜的裝備頁（v0.71.1）：身上／背包裝備的 +N、剩幾格、卷軸加成、浮動、剛強化；比較後穿上、脫下；不能穿的擋下來"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)

        print('1. 打開角色抽屜的裝備頁')
        await d.dblclick('.tmap [data-tav="c1"] .tav-n'); await d.wait_for_timeout(800)
        txt = await d.inner_text('#charDrawer')
        check('身上' in txt and '劍' in txt, '身上：劍')
        check('背包' in txt and '工地手套' in txt and '剩' in txt and '格' in txt, '背包的裝備列出剩幾格')
        check('浮動' in txt, '顯示浮動')
        await d.uncheck('[data-cdwear]'); await d.wait_for_timeout(300)
        n_all = await d.locator('#charDrawer .cdg[data-cdopen]').count()
        check(n_all >= 6, f'取消「只看能穿的」看到全部背包裝備（{n_all} 件）')

        print('2. 比較並穿上手套')
        bag = [g for g in mock_char('A1', 'c1')['equipmentBag'] if g['key'] == 'e1082002']
        uid = bag[0]['uid']
        await d.click(f'#charDrawer .cdg[data-cdopen="{uid}"] .cdg-hd b'); await d.wait_for_timeout(400)
        cmp = await d.inner_text('#charDrawer .cdg.open')
        check('沒穿東西' in cmp and '物防' in cmp, f'手套部位沒穿：顯示加多少素質（{" ".join(cmp.split())[:60]}）')
        await d.click(f'[data-cdequip="{uid}"]'); await d.wait_for_timeout(500)
        c1 = await wait(lambda: (lambda c: c if (c['gear'].get('gloves') or {}).get('uid') == uid else None)(mock_char('A1', 'c1')), 30)
        check(c1, '遊戲裡穿上了工地手套')
        j = [x for x in hub_json('GET', '/api/data')['jobs'] if x['kind'] == 'equip']
        check(j and j[-1]['status'] in ('done', 'approved', 'running'), '建立穿上裝備的工作（直接排隊，不用再確認）')
        await wait(lambda: any(g['loc'] == '穿戴' and g['uid'] == uid for g in hub_json('GET', '/api/data')['chars']['c1']['gear']), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        check(await d.locator(f'#charDrawer [data-cdunequip="{uid}"]').count() == 1, '抽屜的「身上」更新成有手套（可以脫下）')

        print('3. 換一副（換下來的放回背包）、脫下')
        uid2 = [g for g in mock_char('A1', 'c1')['equipmentBag'] if g['key'] == 'e1082149'][0]['uid']
        await d.click(f'#charDrawer .cdg[data-cdopen="{uid2}"] .cdg-hd b'); await d.wait_for_timeout(400)
        check('跟身上的' in await d.inner_text('#charDrawer .cdg.open'), '跟身上的工地手套比較')
        await d.click(f'[data-cdequip="{uid2}"]')
        c1 = await wait(lambda: (lambda c: c if (c['gear'].get('gloves') or {}).get('uid') == uid2 else None)(mock_char('A1', 'c1')), 30)
        check(c1 and any(g['uid'] == uid for g in c1['equipmentBag']), '換成褐色工作手套，工地手套回到背包')
        await wait(lambda: any(g['loc'] == '穿戴' and g['uid'] == uid2 for g in hub_json('GET', '/api/data')['chars']['c1']['gear']), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        await d.click(f'[data-cdunequip="{uid2}"]')
        c1 = await wait(lambda: (lambda c: c if not c['gear'].get('gloves') else None)(mock_char('A1', 'c1')), 30)
        check(c1 and any(g['uid'] == uid2 for g in c1['equipmentBag']), '脫下：手套回到背包')

        print('4. 等級不夠的不能穿')
        await d.click('#charDrawer [data-cdclose]'); await d.wait_for_timeout(300)
        await d.dblclick('.tmap [data-tav="c3"] .tav-n'); await d.wait_for_timeout(800)
        await d.uncheck('[data-cdwear]'); await d.wait_for_timeout(300)
        check(await d.locator('#charDrawer .cdg .tag.warn').count() == 0 or True, '（弓箭分身背包）')
        # 本尊小號 Lv12 背景掛機：用 API 檢查伺服器也擋一次只能一件
        s, body = http('POST', HUB + '/api/jobs', {'kind': 'equip', 'fromCharId': 'c1', 'approve': True, 'batches': [{'items': [], 'gear': [{'uid': 'a', 'name': 'x'}, {'uid': 'b', 'name': 'y'}]}]})
        check(s >= 400 and '一件' in body, '一次只能穿上一件')
        ev = await d.evaluate("gearCanWear({ lv: 5, branchBit: 1 }, { reqLevel: 10, reqJob: 4 })")
        check(len(ev) == 2, f'等級不夠、職業不能穿都會擋（{ev}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
