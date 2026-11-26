"""角色抽屜的能力點、技能、掛機設定頁（v0.72）：先在草稿上加減、確認才送出；自動配點／技能計畫；Buff、攻擊技能、掛機開關"""
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
        await wait(lambda: (hub_json('GET', '/api/data')['chars'].get('c1') or {}).get('char', {}).get('prog'), 30)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        await d.dblclick('.tmap [data-tav="c1"] .tav-n'); await d.wait_for_timeout(800)

        print('1. 能力點：草稿加減，確認才送出')
        await d.click('#charDrawer [data-cdtab="stat"]'); await d.wait_for_timeout(400)
        txt = await d.inner_text('#charDrawer')
        check('可以分配的能力點' in txt and '5' in txt and '力量' in txt and '幸運' in txt, '顯示 5 點可分配、四種能力')
        await d.click('[data-cdst="str|1"]'); await d.click('[data-cdst="str|1"]'); await d.click('[data-cdst="luk|5"]'); await d.wait_for_timeout(200)
        check(await d.locator('[data-cdst="dex|1"]').is_disabled(), '點數用完後「＋」不能按（力量 +2、幸運 +3，因為只剩 3 點）')
        await d.click('[data-cdst="luk|-1"]'); await d.wait_for_timeout(200)
        check(mock_char('A1', 'c1')['ap'] == 5, '還沒確認：遊戲裡的點數沒動')
        await d.click('[data-cdstok]'); await d.wait_for_timeout(500)
        check(msgs and '退不回來' in msgs[-1] and '力量 +2' in msgs[-1] and '幸運 +2' in msgs[-1], f'確認視窗列出分配內容（{msgs[-1] if msgs else ""}）')
        c1 = await wait(lambda: (lambda c: c if c['ap'] == 1 else None)(mock_char('A1', 'c1')), 40)
        check(c1 and c1['stats']['str'] == 42 and c1['stats']['luk'] == 6, '遊戲裡：力量 40→42、幸運 4→6、剩 1 點')
        await wait(lambda: hub_json('GET', '/api/data')['chars']['c1']['char']['prog']['ap'] == 1, 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        check('42' in await d.inner_text('#charDrawer .cd-stat'), '抽屜更新成新的數值')

        print('2. 自動配點計畫')
        await d.click('[data-cdpladd="sp"]'); await d.wait_for_timeout(200)
        await d.fill('[data-cdpl="sp|0|target"]', '60'); await d.dispatch_event('[data-cdpl="sp|0|target"]', 'change')
        await d.check('[data-cdauto="autoStats"]'); await d.wait_for_timeout(300)
        c1 = await wait(lambda: (lambda c: c if c['autoStats'] else None)(mock_char('A1', 'c1')), 40)
        check(c1, '勾「升級時自動分配」→ 遊戲裡開啟自動配點')
        await wait(lambda: hub_json('GET', '/api/data')['chars']['c1']['char']['prog']['auto']['autoStats'], 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(500)
        await d.click('[data-cdplsave="sp"]'); await d.wait_for_timeout(300)
        c1 = await wait(lambda: (lambda c: c if c['statPlan'] else None)(mock_char('A1', 'c1')), 40)
        check(c1 and c1['statPlan'][0] == {'stat': 'str', 'target': 60} and c1['autoStats'], f'計畫存進遊戲：力量到 60，自動配點維持開啟（{c1 and c1["statPlan"]}）')

        print('3. 技能：前置條件、草稿、確認')
        await d.click('#charDrawer [data-cdtab="skill"]'); await d.wait_for_timeout(400)
        txt = await d.inner_text('#charDrawer')
        check('強力攻擊' in txt and '鐵壁' in txt and '憤怒之火' in txt, '列出這個職業一路上來的技能（1 轉、2 轉）')
        check('還不能學' in txt and '61' in txt, '2 轉技能顯示還不能學（前面要先點 61 點）')
        check(await d.locator('[data-cdsk="s1101006|1"]').is_disabled(), '還不能學的「＋」不能按')
        await d.click('[data-cdsk="s1001003|max"]'); await d.wait_for_timeout(200)
        check('→ 3' in await d.inner_text('#charDrawer'), '點滿：鐵壁草稿 0 → 3（只有 3 點）')
        await d.click('[data-cdsk="s1001003|-1"]'); await d.wait_for_timeout(200)
        await d.click('[data-cdskok]'); await d.wait_for_timeout(500)
        check(msgs and '鐵壁 +2' in msgs[-1], '確認視窗：鐵壁 +2')
        c1 = await wait(lambda: (lambda c: c if c['skills'].get('s1001003') == 2 else None)(mock_char('A1', 'c1')), 40)
        check(c1 and c1['sp'] == 1, '遊戲裡：鐵壁 Lv2、剩 1 點')

        print('4. Buff 自動施放、掛機用的攻擊技能、掛機開關')
        await wait(lambda: any(x['id'] == 's1001003' and x['lv'] == 2 for x in hub_json('GET', '/api/data')['chars']['c1']['char']['prog']['skills']), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        check('掛機使用中' in await d.inner_text('#charDrawer'), '強力攻擊顯示「掛機使用中」')
        await d.check('[data-cdbuff="s1001003"]'); await d.wait_for_timeout(300)
        c1 = await wait(lambda: (lambda c: c if 's1001003' in c['autoBuffs'] else None)(mock_char('A1', 'c1')), 40)
        check(c1, '鐵壁開啟自動施放')
        await d.click('#charDrawer [data-cdtab="idle"]'); await d.wait_for_timeout(400)
        check(await d.locator('[data-cdauto="autoPotion"]').is_checked(), '掛機設定：自動喝水目前是開的')
        await d.uncheck('[data-cdauto="autoPotion"]'); await d.wait_for_timeout(300)
        c1 = await wait(lambda: (lambda c: c if not c['autoPotion'] else None)(mock_char('A1', 'c1')), 40)
        check(c1, '關掉自動喝水 → 遊戲裡關閉')

        print('5. 伺服器擋掉不正確的設定')
        for bad, why in [({'type': 'setting', 'key': 'hideMedal', 'value': True}, '不在白名單的設定'), ({'type': 'statBatch', 'allocations': [{'stat': 'hp', 'amount': 1, 'from': 1}]}, '不存在的能力'),
                         ({'type': 'learnBatch', 'allocations': [{'skill': 's1', 'amount': 99, 'from': 0}]}, '技能點超過上限'), ({'type': 'gift'}, '不認得的指令')]:
            s, body = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': bad, 'label': 'x'}]})
            check(s >= 400, f'擋掉{why}（{s}）')
        s, body = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': {'type': 'statBatch', 'allocations': [{'stat': 'str', 'amount': 1, 'from': 0}]}, 'label': '舊的數值'}]})
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] in ('done', 'failed') else None)([x for x in hub_json('GET', '/api/data')['jobs'] if x['kind'] == 'idle']), 40)
        check(j and mock_char('A1', 'c1')['stats']['str'] == 42 and mock_char('A1', 'c1')['ap'] == 1, '數值已經變了的分配，遊戲拒絕、點數不會被用掉')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
