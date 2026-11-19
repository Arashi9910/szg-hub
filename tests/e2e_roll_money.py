"""浮動判斷分部位／武器、背包條列＋依浮動選取賣出、公倉消耗分頁、公倉存楓幣與點數"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_state():
    return json.loads(http('GET', MOCK + '/__mock/state')[1])

EXT = {
    '1082002': {'n': '工地手套', 't': '裝備', 'lv': 10, 'c': '手套'},
    '1452002': {'n': '戰鬥弓', 't': '裝備', 'lv': 10, 'job': '弓箭手', 'c': '武器 · 弓'},
    '1372005': {'n': '木製短杖', 't': '裝備', 'lv': 8, 'job': '法師', 'c': '武器 · 短杖'},
    '2000001': {'n': '橘色藥水', 't': '消耗'},
}

async def wait_job(jid, sec=60):
    end = time.time() + sec
    while time.time() < end:
        j = next((x for x in hub_json('GET', '/api/data')['jobs'] if x['id'] == jid), None)
        if j and j['status'] in ('done', 'failed', 'cancelled'):
            return j
        await asyncio.sleep(1)
    raise AssertionError('工作沒做完：' + json.dumps(j, ensure_ascii=False)[:400])

async def main():
    async with Env(extdb=EXT) as env:
        # 指定浮動的武器：戰鬥弓標準物攻 28、木製短杖標準魔攻 29
        add = lambda key, clean: json.loads(http('GET', f'{MOCK}/__mock/addgear?acct=A1&char=c1&key={key}&clean={clean}')[1])['uid']
        bow_good = add('e1452002', 'incPAD:30')            # +2 → 達標
        bow_bad = add('e1452002', 'incPAD:27,incDEX:5')     # 物攻 −1（敏捷不算）→ 未達標
        wand_good = add('e1372005', 'incMAD:31')           # +2 → 達標
        wand_bad = add('e1372005', 'incMAD:28,incPAD:9')    # 魔攻 −1（物攻不算）→ 未達標
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        for pg in pages:
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(3)

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2000)

        print('1. 背包條列：每件一列、依部位判斷')
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(800)
        await d.click('[data-bview="list"]'); await d.wait_for_timeout(1200)
        row = lambda uid: d.locator(f'tr[data-bpick="c1|g:{uid}"]')
        txt = {u: (await row(u).inner_text()) for u in (bow_good, bow_bad, wand_good, wand_bad)}
        check('達標' in txt[bow_good] and '未達標' not in txt[bow_good], '戰鬥弓 物攻 +2 → 達標：' + ' '.join(txt[bow_good].split())[:80])
        check('未達標' in txt[bow_bad], '戰鬥弓 物攻 −1、敏捷 +5 → 未達標（物理武器只看物攻）')
        check('達標' in txt[wand_good] and '未達標' not in txt[wand_good], '短杖 魔攻 +2 → 達標')
        check('未達標' in txt[wand_bad], '短杖 魔攻 −1、物攻 +9 → 未達標（法杖只看魔攻）')
        check('弓' in txt[bow_good] and '短杖' in txt[wand_good], '類別欄顯示武器種類')

        print('2. 篩「浮動未達標」→ 一鍵選取 → 建立賣出工作')
        await d.select_option('#bJudge', 'no'); await d.wait_for_timeout(800)
        shown = await d.locator('#bagOut tr[data-bpick]').count()
        check(await row(bow_good).count() == 0 and await row(bow_bad).count() == 1, f'只列出未達標的（{shown} 列）')
        await d.click('[data-bquick="rollno"]'); await d.wait_for_timeout(600)
        bar = await d.inner_text('#bagBar')
        check(f'已選 {shown} 項' in bar, '選取畫面上未達標的全部：' + bar.split('\n')[0])
        await d.click('[data-bact="sell"]'); await d.wait_for_timeout(1500)
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'sell' and j['fromCharId'] == 'c1']
        uids = {g['uid'] for j in js for g in j['batches'][0]['gear']}
        check(bow_bad in uids and wand_bad in uids and bow_good not in uids and wand_good not in uids, f'賣出工作只含未達標的裝備（{len(uids)} 件），等確認')
        for j in js: http('POST', f"{HUB}/api/jobs/{j['id']}/cancel")
        await d.keyboard.press('Escape'); await d.wait_for_timeout(300)
        await d.select_option('#bJudge', 'all'); await d.wait_for_timeout(500)

        print('3. 改基準：手套加看物防，判斷跟著變，存到設定')
        await d.click('#bag details.rp-editor summary'); await d.wait_for_timeout(500)
        await d.click('#bag [data-rpstat="gloves|incPDD"]'); await d.wait_for_timeout(1200)
        prof = (hub_json('GET', '/api/data')['settings'].get('rollProfiles') or {}).get('gloves')
        check(prof and prof['stats'] == ['incSTR', 'incDEX', 'incINT', 'incLUK', 'incPDD'] and prof['min'] == 1, f'手套預設看四屬，加上物防後存檔：{prof}')
        st = mock_state()
        gl = [g for g in st['accounts']['A1']['chars']['c1']['equipmentBag'] if g['type'] == 'gloves']
        good = [g for g in gl if g['cleanStats'].get('incPDD', 0) - g['baseStats'].get('incPDD', 0) >= 1]
        if good:
            check('未達標' not in await row(good[0]['uid']).inner_text(), '物防浮動 ≥ 1 的手套變成達標')
        bad = [g for g in gl if g['cleanStats'].get('incPDD', 0) - g['baseStats'].get('incPDD', 0) < 1]
        if bad:
            check('未達標' in await row(bad[0]['uid']).inner_text(), '物防浮動 < 1 的手套仍是未達標')

        print('4. 公倉存入規則：依部位基準達標')
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(800)
        await d.click('[data-gdpreset="good"]'); await d.wait_for_timeout(1200)
        dep = hub_json('GET', '/api/data')['settings']['guildDep']
        check(dep['conds'] == [{'k': '_pass', 'min': ''}], f'快速套用改用部位基準：{dep["conds"]}')
        check('依部位基準達標' in await d.inner_text('#gdSummary'), '摘要寫出依部位基準達標')

        print('5. 公倉分頁：卷軸／消耗／其他')
        http('GET', f'{MOCK}/__mock/additem?acct=A1&char=c1&key=i2000001&qty=20'); await asyncio.sleep(5)
        r = hub_json('POST', '/api/jobs', {'kind': 'guildDeposit', 'fromCharId': 'c1', 'batches': [{'items': [{'key': 'i2000001', 'name': '橘色藥水', 'qty': 5}, {'key': 'i2040801', 'name': '手套攻擊卷軸', 'qty': 2}], 'gear': []}]})
        jid = r['jobs'][0]['id']; http('POST', f'{HUB}/api/jobs/{jid}/approve')
        j = await wait_job(jid)
        check(j['status'] == 'done', '存入藥水、卷軸：' + j['lastMsg'])
        await d.click('#gwRefresh'); await d.wait_for_timeout(5000)
        await d.click('#gwTabs button[data-gwtab=use]'); await d.wait_for_timeout(400)
        use = await d.inner_text('#gwOut')
        await d.click('#gwTabs button[data-gwtab=scroll]'); await d.wait_for_timeout(400)
        scr = await d.inner_text('#gwOut')
        check('橘色藥水' in use and '卷軸' not in use, '消耗分頁列出藥水：' + ' '.join(use.split())[:60])
        check('卷軸' in scr and '橘色藥水' not in scr, '卷軸分頁只有卷軸')

        print('6. 存楓幣、點數：建立後待確認，「全部確認」也可以確認')
        await d.fill('[data-gmm="c1"]', '1000000'); await d.fill('[data-gmc="c1"]', '300')
        check('楓幣 1,000,000' in await d.inner_text('#gmSum'), '合計即時更新')
        before_money = mock_state()['accounts']['A1']['chars']['c1']['money']
        await d.click('#gmCreate'); await d.wait_for_timeout(1200)
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildMoney']
        check(len(js) == 1 and js[0]['status'] == 'pending' and js[0]['batches'][0]['mesos'] == 1000000 and js[0]['batches'][0]['cash'] == 300, '建立 1 個待確認工作')
        await d.click('#jobBtn'); await d.wait_for_timeout(600)
        await d.click('[data-approve-all]'); await d.wait_for_timeout(800)
        await d.keyboard.press('Escape')
        j = await wait_job(js[0]['id'])
        st = mock_state()
        check(j['status'] == 'done', '執行完成：' + ' / '.join(x['msg'] for x in j['log'][-3:]))
        check(st['guild']['mesos'] == 1000000 and st['guild']['cashPoints'] == 300, f"公倉楓幣 {st['guild']['mesos']}、點數 {st['guild']['cashPoints']}")
        check(st['accounts']['A1']['chars']['c1']['money'] <= before_money - 1000000 + 5000, '角色楓幣扣掉存入的金額')
        check(st['accounts']['A1']['cashPoints'] == 4700, '帳號點數扣掉 300')
        check(any('公倉楓幣 0 → 1,000,000' in x['msg'] for x in j['log']), '紀錄寫出公倉餘額變化')

        print('7. 從公倉提領：扣稅、紀錄寫出實際拿到多少')
        await d.wait_for_timeout(3500)
        await d.click('[data-gmop="withdraw"]'); await d.wait_for_timeout(400)
        check('建立提領工作' in await d.inner_text('#gmCreate'), '切到提領模式')
        await d.fill('[data-gmm="c3"]', '200000'); await d.fill('[data-gmc="c3"]', '100')
        check('稅後約拿到楓幣 190,000' in await d.inner_text('#gmSum'), '預估稅後金額：' + await d.inner_text('#gmSum'))
        m3 = mock_state()['accounts']['A2']['chars']['c3']['money']
        await d.click('#gmCreate'); await d.wait_for_timeout(1200)
        wj = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildMoney' and j['status'] == 'pending']
        check(len(wj) == 1 and wj[0]['batches'][0]['op'] == 'withdraw' and wj[0]['fromCharId'] == 'c3', '建立 1 個提領工作（給弓箭分身）')
        http('POST', f"{HUB}/api/jobs/{wj[0]['id']}/approve")
        j = await wait_job(wj[0]['id']); st = mock_state()
        check(j['status'] == 'done', '提領完成：' + ' / '.join(x['msg'] for x in j['log'][-3:]))
        check(st['guild']['mesos'] == 800000 and st['guild']['cashPoints'] == 200, f"公倉楓幣 {st['guild']['mesos']}、點數 {st['guild']['cashPoints']}")
        check(abs(st['accounts']['A2']['chars']['c3']['money'] - m3 - 190000) < 5000 and st['accounts']['A2']['cashPoints'] == 5095, '角色拿到扣稅後的楓幣、帳號點數 +95')
        check(any('差額是公會稅' in x['msg'] for x in j['log']), '紀錄寫出稅金差額')
        r = hub_json('POST', '/api/jobs', {'kind': 'guildMoney', 'fromCharId': 'c3', 'batches': [{'op': 'withdraw', 'mesos': 99999999, 'cash': 0}]})
        http('POST', f"{HUB}/api/jobs/{r['jobs'][0]['id']}/approve")
        j = await wait_job(r['jobs'][0]['id'])
        check(j['status'] == 'failed' and '公倉楓幣不足' in j['lastMsg'] and mock_state()['guild']['mesos'] == 800000, '超過公倉餘額：失敗、公倉不變')

        print('8. 超過身上楓幣：不存、標示失敗')
        r = hub_json('POST', '/api/jobs', {'kind': 'guildMoney', 'fromCharId': 'c3', 'batches': [{'mesos': 999999999, 'cash': 0}]})
        http('POST', f"{HUB}/api/jobs/{r['jobs'][0]['id']}/approve")
        j = await wait_job(r['jobs'][0]['id'])
        check(j['status'] == 'failed' and '不足' in j['lastMsg'] and mock_state()['guild']['mesos'] == 800000, '楓幣不足時失敗、公倉不變：' + j['lastMsg'])

        for tab in ['overview', 'bag', 'guild', 'gear']:
            await d.click(f'nav button[data-tab={tab}]'); await d.wait_for_timeout(500)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
