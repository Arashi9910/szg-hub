"""部位設定合一：撿到自動處理用「浮動達標」當保留條件、舊腳本拿不到這種規則、面板一鍵加條件、裝備頁加粗要看的素質"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def bag(acct='A1', cid='c1'):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]['equipmentBag']

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1'])
        await pages[0].evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(1)
        rule = {'on': True, 'name': '手套', 'slots': ['gloves'], 'jobs': [], 'nameInc': '', 'sellAll': False, 'conds': [{'join': 'and', 'stat': '_rollOk', 'op': '=', 'val': '1'}]}
        hub_json('POST', '/api/settings', {'autoSell': {'mode': 'sell', 'chars': {'c1': True}, 'rules': [rule]}})

        print('1. 舊腳本拿不到用浮動條件的規則')
        old = hub_json('GET', '/api/autosell'); new = hub_json('GET', '/api/autosell?v=0.36.0')
        check(old['rules'] == [] and len(new['rules']) == 1, '沒帶版本：規則被拿掉（避免舊腳本全部賣掉）；新版：照給')

        print('2. 撿到兩雙手套：浮動達標的留下、沒達標的賣掉')
        await asyncio.sleep(25)  # 等腳本第一次記住目前背包
        good = json.loads(http('GET', f'{MOCK}/__mock/addgear?acct=A1&char=c1&key=e1082002&clean=incPDD:2,incSTR:2')[1])['uid']  # 力量 +2 → 達標
        bad = json.loads(http('GET', f'{MOCK}/__mock/addgear?acct=A1&char=c1&key=e1082002&clean=incPDD:4')[1])['uid']             # 只有物防 +2 → 防具不看物防 → 沒達標
        end = time.time() + 70
        while time.time() < end:
            uids = {g['uid'] for g in bag()}
            if bad not in uids: break
            await asyncio.sleep(3)
        uids = {g['uid'] for g in bag()}
        check(bad not in uids, '物防浮動不算（手套看四屬）→ 賣掉')
        check(good in uids, '力量 +2 → 浮動達標 → 留下')
        log = ' / '.join(x['msg'] for x in hub_json('GET', '/api/data')['gearLog'][-3:])
        check('自動賣出 1 件' in log, '紀錄：' + log[:120])

        print('3. 面板：一鍵加「保留浮動達標的」、裝備頁加粗')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2000)
        hub_json('POST', '/api/settings', {'autoSell': {'mode': 'preview', 'chars': {'c1': True}, 'rules': [{**rule, 'conds': []}]}})
        await d.reload(); await d.wait_for_timeout(2000)
        await d.click('nav button[data-tab=gear]'); await d.click('#gViewSeg button[data-gv="auto"]'); await d.wait_for_timeout(600)
        await d.click('[data-raddroll="0"]'); await d.wait_for_timeout(1200)
        conds = hub_json('GET', '/api/data')['settings']['autoSell']['rules'][0]['conds']
        check(conds == [{'join': 'and', 'stat': '_rollOk', 'op': '=', 'val': '1'}], f'加上保留條件：{conds}')
        check(await d.locator('#asRules select.cs option[value="_rollScore"]').count() >= 1, '條件選單有「浮動分數」')
        await d.click('#gViewSeg button[data-gv="matrix"]'); await d.wait_for_timeout(600)
        line = await d.evaluate("statLineJ({ gtype: 'gloves' }, { incSTR: 3, incPDD: 2 }) + ' | ' + statLineJ({ gtype: 'bow' }, { incPAD: 30, incDEX: 2 })")
        check(line == '<b>力量 3</b> · 物防 2 | <b>物攻 30</b> · 敏捷 2', '素質全部列出、部位設定要看的加粗：' + line)
        check(await d.locator('#slotCfgBox .rp-body').count() == 1, '裝備頁「部位設定」就是共用的那一份')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
