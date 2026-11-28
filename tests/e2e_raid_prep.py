"""副本 A：戰前檢查（計畫裡每隻的藥水／萬能療傷藥／自動解除異常／自動喝水／補血／攻擊格，門檻存 settings.raid.prep）＋一鍵套用（cfg supply／setting，不碰自動買水）"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
def hub_ic(c): return ((hub_json('GET', '/api/data')['chars'].get(c) or {}).get('char') or {}).get('idleCfg')
def prep(): return hub_json('GET', '/api/raid/prep')
def row(c): return next((r for r in prep()['rows'] if r['id'] == c), None)
def iss(r, k): return [x for x in (r or {}).get('issues', []) if x['k'] == k]
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
        # 背包：c1 有 10 個萬能療傷藥；c3 沒有；c4 藍色藥水只剩 30 瓶
        http('GET', MOCK + '/__mock/setitem?acct=A1&char=c1&key=i2050004&qty=10')
        http('GET', MOCK + '/__mock/setitem?acct=A3&char=c4&key=i2000003&qty=30')
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        await wait(lambda: hub_ic('c1') and hub_ic('c3') and hub_ic('c4'), 40)
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4']}})

        print('1. 伺服器的戰前檢查（預設門檻）')
        j = prep()
        check(j['prep'] == {'mpMin': 100, 'hpMin': 100, 'cureMin': 5, 'mpPct': 40, 'hpPct': 50, 'autoCure': True, 'autoPotion': True}, f'預設門檻：藍藥 ≥ 100、萬能療傷藥 ≥ 5、MP 40%、autoCure 開（{j["prep"]}）')
        check([r['id'] for r in j['rows']] == ['c1', 'c3', 'c4'], '列出計畫裡的隊長＋隊員')
        r1 = row('c1')
        check(r1 and r1['tab'] == 'tab' and r1['slot'] == 1 and r1['mp']['name'] == '藍色藥水' and r1['mp']['qty'] == 200 and r1['mp']['pct'] == 20 and r1['cure'] == 10, f'c1：分頁、第 1 套、藍色藥水 200、MP 20%、萬能療傷藥 10（{r1 and r1["mp"]}）')
        check(iss(r1, 'autoCure') and iss(r1, 'autoCure')[0]['lv'] == 'bad', 'c1：自動解除異常沒勾 → 紅')
        check(iss(r1, 'mpPct') and iss(r1, 'mpPct')[0]['lv'] == 'warn' and not iss(r1, 'mpQty') and not iss(r1, 'cure'), 'c1：MP 20% → 黃；藍藥 200、萬能療傷藥 10 沒問題')
        # 技能 1＝主動技能（character.active），技能 2、3 選填；有主動技能就不算問題（game.js openAttackSlot）
        check(not iss(r1, 'attack') and r1['attack']['state'] == 'ok' and r1['attack']['txt'].startswith('1. '), f'c1：有主動技能 → 攻擊格沒問題（{r1 and r1["attack"]}）')
        check(r1['autoPotion'] is True and not iss(r1, 'autoPotion'), 'c1：自動喝水開著')
        r3, r4 = row('c3'), row('c4')
        check(iss(r3, 'cure') and iss(r3, 'cure')[0]['lv'] == 'bad', 'c3：沒有萬能療傷藥 → 紅')
        check(iss(r4, 'mpQty') and iss(r4, 'mpQty')[0]['lv'] == 'warn' and '30' in iss(r4, 'mpQty')[0]['txt'], f'c4：藍色藥水只有 30 → 黃（{iss(r4, "mpQty")}）')

        print('2. 改門檻（存 settings.raid.prep）')
        s, b = http('POST', HUB + '/api/raid/prep', {'prep': {'cureMin': 20, 'mpPct': 999}})
        p = (hub_json('GET', '/api/data')['settings'].get('raid') or {}).get('prep') or {}
        check(s == 200 and p.get('cureMin') == 20 and p.get('mpPct') == 40 and p.get('mpMin') == 100, f'萬能療傷藥改 20、不合理的 999% 不收（{p}）')
        check(iss(row('c1'), 'cure') and iss(row('c1'), 'cure')[0]['lv'] == 'warn', 'c1：10 個 < 20 → 黃')
        plan = hub_json('GET', '/api/data')['settings'].get('raid') or {}
        check(plan.get('leader') == 'c1' and plan.get('members') == ['c3', 'c4'], '改門檻不會動到副本計畫')

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(2500)

        print('3. 面板：每隻一列、紅黃標')
        txt = await d.inner_text('#rdPrep')
        check('本尊劍士' in txt and '弓箭分身' in txt and '倉庫分身' in txt and '本尊小號' not in txt, '列出計畫裡的 3 隻（不在計畫的不列）')
        check('自動解除異常沒勾' in txt and '沒有萬能療傷藥' in txt and '攻擊格沒設定' not in txt and '藍色藥水' in txt, '顯示問題：解除異常沒勾、沒有萬能療傷藥（攻擊格不再誤報）')
        check('lv-bad' in (await d.get_attribute('#rdPrep tr[data-rpsel="c3"]', 'class')), '有紅色問題的列標紅')
        check(await d.locator('#rdPrep [data-rpth="cureMin"]').input_value() == '20', '門檻輸入框顯示 20')

        print('4. 打字中不重畫')
        await d.click('#rdPrep [data-rpth="mpMin"]'); await d.fill('#rdPrep [data-rpth="mpMin"]', '12')
        await d.wait_for_timeout(2500)
        check(await d.locator('#rdPrep [data-rpth="mpMin"]').input_value() == '12', '打字中每秒更新不會把輸入框洗掉')
        await d.fill('#rdPrep [data-rpth="mpMin"]', '150'); await d.dispatch_event('#rdPrep [data-rpth="mpMin"]', 'change'); await d.wait_for_timeout(1500)
        check(prep()['prep']['mpMin'] == 150, '面板改 MP 藥水門檻 150 存起來')
        await d.fill('#rdPrep [data-rpth="mpPct"]', '45'); await d.dispatch_event('#rdPrep [data-rpth="mpPct"]', 'change'); await d.wait_for_timeout(2500)
        check(prep()['prep']['mpPct'] == 45, '面板改 MP 喝水建議值 45%')
        check('建議 ≥ 150' in await d.inner_text('#rdPrep tr[data-rpsel="c3"]'), '弓箭分身：藍藥 100 < 150 → 提醒')

        print('5. 一鍵套用：點整列選角色 → 列出要改的 → 確認')
        await d.click('#rdPrep tr[data-rpsel="c1"] td:nth-child(2)'); await d.wait_for_timeout(300)
        await d.click('#rdPrep tr[data-rpsel="c3"] td:nth-child(5)'); await d.wait_for_timeout(300)
        check('on' in (await d.get_attribute('#rdPrep tr[data-rpsel="c1"]', 'class')).split() and await d.locator('#rdPrep tr[data-rpsel="c3"] input').is_checked(), '點整列就能選取')
        await d.click('#rdPrep tr[data-rpsel="c3"] td:nth-child(2)'); await d.wait_for_timeout(300)
        check('on' not in (await d.get_attribute('#rdPrep tr[data-rpsel="c3"]', 'class')).split(), '再點一次取消')
        await d.click('#rdPrep tr[data-rpsel="c3"] td:nth-child(3)'); await d.wait_for_timeout(2200)
        check('已選 2 隻' in await d.inner_text('#rdPrep'), '每秒更新後勾選還在')
        n0 = len(msgs)
        await d.click('#rdPrep [data-rpgo]'); await d.wait_for_timeout(800)
        m = msgs[-1] if len(msgs) > n0 else ''
        check('本尊劍士' in m and '弓箭分身' in m and '自動解除異常 關→開' in m and 'MP 喝水 20%→45%' in m and 'HP 喝水' not in m and '不會花楓幣' in m, f'確認框列出每隻要改的（{m!r}）')
        c1 = await wait(lambda: (lambda c: c if c['supply']['autoCure'] and c['supply']['mpPct'] == 45 else None)(mock_char('A1', 'c1')), 50)
        check(c1 and c1['supply']['hpItem'] == 'i2000000' and c1['supply']['hpPct'] == 60 and c1['supply']['mpItem'] == 'i2000003' and c1['autoPotion'], f'本尊劍士：遊戲裡 autoCure 開、MP 45%，其他不變（{c1 and c1["supply"]}）')
        c3 = await wait(lambda: (lambda c: c if c['supply']['autoCure'] and c['supply']['mpPct'] == 45 else None)(mock_char('A2', 'c3')), 50)
        check(c3, '弓箭分身也套上了')
        c4 = mock_char('A3', 'c4')
        check(not c4['supply']['autoCure'] and c4['supply']['mpPct'] == 20, '沒選的倉庫分身不動')
        check(not any(mock_char(a, c)['autoBuy']['enabled'] for a, c in [('A1', 'c1'), ('A2', 'c3'), ('A3', 'c4')]), '自動買水（會花楓幣）都沒有被打開')
        await wait(lambda: not iss(row('c1'), 'autoCure') and not iss(row('c1'), 'mpPct'), 40)
        check(not iss(row('c1'), 'autoCure') and not iss(row('c1'), 'mpPct'), '中控重新讀到：本尊劍士的紅黃標消失')

        print('6. 自動喝水關著的角色：沒勾「自動喝水：開」就維持關閉')
        http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c4', 'action': 'cfg', 'cmd': {'type': 'setting', 'key': 'autoPotion', 'value': False}, 'label': '關自動喝水'}]})
        await wait(lambda: mock_char('A3', 'c4')['autoPotion'] is False, 30)
        r4 = await wait(lambda: (lambda r: r if r['autoPotion'] is False else None)(row('c4')), 40)
        check(r4 and iss(r4, 'autoPotion') and iss(r4, 'autoPotion')[0]['lv'] == 'bad', '倉庫分身：自動喝水沒開 → 紅')
        await d.wait_for_timeout(2500)
        await d.uncheck('#rdPrep [data-rpitem="autoPotion"]'); await d.wait_for_timeout(300)
        await d.click('#rdPrep tr[data-rpsel="c4"] td:nth-child(2)'); await d.wait_for_timeout(300)
        n0 = len(msgs)
        await d.click('#rdPrep [data-rpgo]'); await d.wait_for_timeout(800)
        m = msgs[-1] if len(msgs) > n0 else ''
        check('倉庫分身' in m and '自動解除異常 關→開' in m and '自動喝水' not in m.split('\n')[1], f'確認框只列補給的改動（{m!r}）')
        c4 = await wait(lambda: (lambda c: c if c['supply']['autoCure'] else None)(mock_char('A3', 'c4')), 50)
        await asyncio.sleep(3)
        c4 = mock_char('A3', 'c4')
        check(c4 and c4['supply']['autoCure'] and c4['autoPotion'] is False, f'倉庫分身：autoCure 開，自動喝水維持關閉（autoPotion={c4 and c4["autoPotion"]}）')
        await wait(lambda: row('c4')['autoCure'], 40); await d.wait_for_timeout(2500)
        await d.check('#rdPrep [data-rpitem="autoPotion"]'); await d.wait_for_timeout(300)
        await d.click('#rdPrep tr[data-rpsel="c4"] td:nth-child(2)'); await d.wait_for_timeout(300)
        n0 = len(msgs)
        await d.click('#rdPrep [data-rpgo]'); await d.wait_for_timeout(800)
        m = msgs[-1] if len(msgs) > n0 else ''
        check('自動喝水 關→開' in m, f'勾「自動喝水：開」→ 列出要打開（{m!r}）')
        c4 = await wait(lambda: (lambda c: c if c['autoPotion'] else None)(mock_char('A3', 'c4')), 50)
        check(c4, '倉庫分身：自動喝水打開了')

        print('7. 改副本計畫不會清掉門檻')
        await d.uncheck('[data-rdmem="c4"]'); await d.wait_for_timeout(1500)
        st = hub_json('GET', '/api/data')['settings'].get('raid') or {}
        check(st.get('members') == ['c3'] and (st.get('prep') or {}).get('mpPct') == 45 and (st.get('prep') or {}).get('mpMin') == 150, f'隊員改了、門檻還在（{st}）')
        await d.wait_for_timeout(2500)
        check('倉庫分身' not in await d.inner_text('#rdPrep'), '戰前檢查跟著計畫只列 2 隻')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
