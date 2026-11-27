"""角色抽屜「掛機設定」頁：從遊戲讀出補給／隊友 Buff／補血／自動購買，在中控改、套用回遊戲；切換第 1／2／3 套；複製到其他角色"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
def hub_ic(c): return ((hub_json('GET', '/api/data')['chars'].get(c) or {}).get('char') or {}).get('idleCfg')
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        try: v = fn()
        except Exception: v = None
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        ic = await wait(lambda: hub_ic('c1'), 40)
        check(ic and ic['slot'] == 1 and ic['supply']['hpItem'] == 'i2000000' and ic['supply']['hpPct'] == 60, f'agent 回報 idleCfg：第 1 套、HP 紅色藥水 60%（{ic and ic["supply"]}）')
        names = {x['id']: x for x in (ic or {}).get('items', [])}
        check(names.get('i2000002', {}).get('qty') == 50 and names.get('i2050004', {}).get('qty') == 0 and 'i2040801' not in names, '背包消耗品：白色藥水 50、萬能療傷藥 0（卷軸不算）')
        check(ic and len(ic['partyBuffs']) == 3 and ic['autoBuy'] == {'enabled': False, 'reserve': 0, 'rules': []}, '隊友 Buff 3 格、自動購買格式')
        await wait(lambda: hub_ic('c3') and hub_ic('c4'), 30)

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        await d.click('[data-fzoom="fit"]'); await d.wait_for_timeout(400)
        await d.dblclick('.tmap [data-tav="c1"] .tav-n'); await d.wait_for_timeout(800)
        await d.click('#charDrawer [data-cdtab="idle"]'); await d.wait_for_timeout(500)

        print('1. 讀取：顯示遊戲裡的設定')
        txt = await d.inner_text('#charDrawer')
        check('目前第 1 套' in txt and '補給' in txt and '隊友 Buff' in txt and '自動購買' in txt, '顯示目前第 1 套、補給、隊友 Buff、自動購買')
        check(await d.locator('[data-cdic="supply.hpItem"]').input_value() == 'i2000000', 'HP 藥水下拉＝紅色藥水')
        opts = await d.locator('[data-cdic="supply.hpItem"] option').all_inner_texts()
        check(any('白色藥水（50）' in o for o in opts) and any('紅色藥水（300）' in o for o in opts), f'下拉選項是背包的消耗品＋數量（{opts}）')
        check('萬能療傷藥 0 個' in txt, '顯示背包有幾個萬能療傷藥')
        check(await d.locator('[data-cdauto="autoPotion"]').is_checked(), '原本的掛機開關還在（自動喝水）')

        print('2. 改補給、隊友 Buff、補血、自動購買 → 套用')
        await d.select_option('[data-cdic="supply.hpItem"]', 'i2000002'); await d.wait_for_timeout(200)
        await d.fill('[data-cdic="supply.hpPct"]', '70'); await d.dispatch_event('[data-cdic="supply.hpPct"]', 'change')
        await d.locator('#charDrawer h3').click(); await d.wait_for_timeout(200)
        await d.check('[data-cdic="supply.autoCure"]'); await d.wait_for_timeout(300)
        check('勾了也不會用' in await d.inner_text('#cdicCure'), '勾自動解除異常、背包 0 個萬能療傷藥 → 警告')
        await d.check('[data-cdic="supply.buffPotion.enabled"]'); await d.wait_for_timeout(200)
        await d.select_option('[data-cdic="supply.buffPotion.item"]', 'i2002002'); await d.wait_for_timeout(200)
        await d.select_option('[data-cdic="supply.onEmpty"]', 'continue'); await d.wait_for_timeout(200)
        sk = await d.locator('[data-cdic="partyBuffs.0.skill"] option').all_inner_texts()
        check(any('群體激勵' in o for o in sk) and not any('強力攻擊' in o for o in sk), f'隊友 Buff 只列學過、可以給隊友的技能（{sk}）')
        await d.check('[data-cdic="partyBuffs.0.enabled"]'); await d.wait_for_timeout(200)
        await d.select_option('[data-cdic="partyBuffs.0.skill"]', 's1001005'); await d.wait_for_timeout(200)
        await d.check('[data-cdic="partyHeal.enabled"]'); await d.wait_for_timeout(200)
        await d.fill('[data-cdic="partyHeal.threshold"]', '40'); await d.dispatch_event('[data-cdic="partyHeal.threshold"]', 'change')
        await d.locator('#charDrawer h3').click(); await d.wait_for_timeout(200)
        await d.check('[data-cdic="autoBuy.enabled"]'); await d.wait_for_timeout(200)
        await d.click('[data-cdicbuyadd]'); await d.wait_for_timeout(200)
        await d.select_option('[data-cdic="autoBuy.rules.0.item"]', 'i2000002'); await d.wait_for_timeout(200)
        check('還沒套用' in await d.inner_text('#charDrawer'), '有改動時顯示「還沒套用」')
        check(mock_char('A1', 'c1')['supply']['hpItem'] == 'i2000000', '還沒按套用：遊戲裡沒變')
        await d.click('[data-cdicapply]'); await d.wait_for_timeout(600)
        m = msgs[-1] if msgs else ''
        check('白色藥水 70%' in m and '戰士藥水' in m and '隊友 Buff 第 1 格：群體激勵' in m and '隊友補血：HP 低於 40%' in m and '自動購買' in m and '用完繼續掛機' in m, f'套用前再問一次，列出要改的項目（{m!r}）')
        c1 = await wait(lambda: (lambda c: c if c['supply']['hpItem'] == 'i2000002' and c['autoBuy']['enabled'] else None)(mock_char('A1', 'c1')), 50)
        check(c1 and c1['supply']['hpPct'] == 70 and c1['supply']['mpItem'] == 'i2000003' and c1['supply']['autoCure'] and c1['supply']['onEmpty'] == 'continue', f'遊戲裡的補給變了（{c1 and c1["supply"]}）')
        check(c1 and c1['supply']['buffPotion'] == {'enabled': True, 'item': 'i2002002'} and 'extra' in c1['supply'], '遊戲裡 Buff 藥水 1＝戰士藥水，其他欄位保留（整份送）')
        check(c1 and c1['partyBuffs'][0] == {'enabled': True, 'skill': 's1001005'} and c1['partyHeal'] == {'enabled': True, 'threshold': 40}, '遊戲裡隊友 Buff 第 1 格、隊友補血 40%')
        check(c1 and c1['autoBuy']['rules'] == [{'item': 'i2000002', 'below': 10, 'target': 200}], f'遊戲裡自動購買規則（{c1 and c1["autoBuy"]}）')
        check(c1 and c1['autoPotion'], '自動喝水維持開啟')
        ic = await wait(lambda: (lambda x: x if x and x['supply']['hpItem'] == 'i2000002' else None)(hub_ic('c1')), 30)
        check(ic, '中控收到新的設定')
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        txt = await d.inner_text('#charDrawer')
        check('跟遊戲一樣' in txt and await d.locator('[data-cdic="supply.hpItem"]').input_value() == 'i2000002', '抽屜顯示遊戲裡新的設定（沒有未套用的修改）')

        print('3. 從遊戲重新讀取')
        await d.click('[data-cdicread]'); await d.wait_for_timeout(300)
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] == 'done' else None)([x for x in hub_json('GET', '/api/data')['jobs'] if x['kind'] == 'idle' and '重新讀取' in json.dumps(x, ensure_ascii=False)]), 40)
        check(j, '重新讀取的工作完成')

        print('4. 切換第 2 套（空白）再切回第 1 套')
        await d.evaluate('poll(true)'); await d.wait_for_timeout(500)
        await d.click('[data-cdpreset="2"]'); await d.wait_for_timeout(500)
        check(msgs and '空白' in msgs[-1], f'切換前提醒沒用過的那套是空白的（{msgs[-1] if msgs else ""}）')
        c1 = await wait(lambda: (lambda c: c if c.get('settingsSlot') == 2 else None)(mock_char('A1', 'c1')), 40)
        check(c1 and c1['supply']['hpItem'] is None and not c1['partyBuffs'][0]['enabled'] and not c1['autoBuy']['enabled'], '遊戲裡換成第 2 套：空白（沒藥水、沒隊友 Buff、沒自動購買）')
        ic = await wait(lambda: (lambda x: x if x and x['slot'] == 2 else None)(hub_ic('c1')), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        check(ic and '目前第 2 套' in await d.inner_text('#charDrawer') and await d.locator('[data-cdic="supply.hpItem"]').input_value() == '', '抽屜顯示目前第 2 套、HP 藥水空白')
        await d.click('[data-cdpreset="1"]'); await d.wait_for_timeout(500)
        c1 = await wait(lambda: (lambda c: c if c.get('settingsSlot') == 1 else None)(mock_char('A1', 'c1')), 40)
        check(c1 and c1['supply']['hpItem'] == 'i2000002' and c1['partyBuffs'][0]['enabled'], '切回第 1 套：原本的設定還在（三套各自獨立）')
        await wait(lambda: (lambda x: x and x['slot'] == 1 and x['supply']['hpItem'] == 'i2000002')(hub_ic('c1')), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)

        print('5. 複製到其他角色')
        await d.click('[data-cdcpopen]'); await d.wait_for_timeout(400)
        await d.click('#cdCopy [data-cdcprow="c3"] b'); await d.wait_for_timeout(200)  # 點整列（名字）就能選
        await d.click('#cdCopy [data-cdcprow="c4"]'); await d.wait_for_timeout(200)
        check(await d.locator('#cdCopy [data-cdcprow="c3"] input').is_checked() and 'on' in (await d.get_attribute('#cdCopy [data-cdcprow="c4"]', 'class')), '點整列選取兩隻')
        row = await d.inner_text('#cdCopy [data-cdcprow="c3"]')
        check('背包沒有 白色藥水' in row and '萬能療傷藥' in row and '沒學 群體激勵' in row, f'警告：藥水不在對方背包、沒有萬能療傷藥、沒學隊友 Buff（{row!r}）')
        await d.uncheck('[data-cdcppart="buy"]'); await d.wait_for_timeout(200)
        await d.click('[data-cdcpgo]'); await d.wait_for_timeout(600)
        m = msgs[-1] if msgs else ''
        check('2 隻' in m and '弓箭分身' in m and '倉庫分身' in m and '背包沒有 白色藥水' in m, f'套用前列出角色與警告（{m[:120]!r}）')
        c3 = await wait(lambda: (lambda c: c if c['supply']['hpItem'] == 'i2000002' and c['partyHeal']['enabled'] else None)(mock_char('A2', 'c3')), 50)
        check(c3 and c3['supply']['hpPct'] == 70 and c3['supply']['autoCure'] and c3['partyHeal']['threshold'] == 40, '弓箭分身：補給、隊友補血套上了')
        check(c3 and not c3['partyBuffs'][0]['enabled'] and not c3['autoBuy']['enabled'], '弓箭分身：沒學的隊友 Buff 不套、沒勾的自動購買不動')
        c4 = await wait(lambda: (lambda c: c if c['supply']['hpItem'] == 'i2000002' else None)(mock_char('A3', 'c4')), 50)
        check(c4 and c4['supply']['buffPotion']['item'] == 'i2002002', '倉庫分身：補給套上了')
        check(mock_char('A1', 'c1')['supply']['hpItem'] == 'i2000002', '來源角色不受影響')

        print('6. 伺服器擋掉不正確的設定')
        good = {'hpItem': 'i2000000', 'mpItem': None, 'hpPct': 50, 'mpPct': 30}
        for bad, why in [({'type': 'supply', 'supply': {**good, 'hpItem': 'x123'}}, '道具不是 i 開頭'), ({'type': 'supply', 'supply': {**good, 'hpPct': 0}}, '百分比 0'),
                         ({'type': 'supply', 'supply': {**good, 'mpPct': 101}}, '百分比 101'), ({'type': 'partyBuff', 'slot': 3, 'config': {'enabled': True, 'skill': 's1'}}, '隊友 Buff 第 4 格'),
                         ({'type': 'partyBuff', 'slot': 0, 'config': {'enabled': True}}, '開啟但沒技能'), ({'type': 'partyHeal', 'config': {'enabled': True, 'threshold': 0}}, '補血門檻 0'),
                         ({'type': 'lowHpSkill', 'config': {'enabled': True, 'threshold': 100, 'skill': 's1'}}, '低血門檻 100'), ({'type': 'settingsPreset', 'slot': 4}, '第 4 套'),
                         ({'type': 'autoBuy', 'config': {'enabled': True, 'rules': [{'item': 'i2000000', 'below': 50, 'target': 10}]}}, '買到比門檻少')]:
            s, body = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': bad, 'label': 'x'}]})
            check(s >= 400, f'擋掉{why}（{s}）')
        s, body = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': {'type': 'selfHeal', 'config': {'enabled': True, 'threshold': 35}}, 'label': '自己補血'}]})
        c1 = await wait(lambda: (lambda c: c if c['selfHeal']['enabled'] else None)(mock_char('A1', 'c1')), 40)
        check(s == 200 and c1 and c1['selfHeal']['threshold'] == 35, '正確的 selfHeal 送得到遊戲')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
