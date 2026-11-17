"""公會倉庫（私人版）：面板開存入選單→用掉落浮動篩選→存入；公倉內容→依職業建議／指定角色→領取"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_state():
    return json.loads(http('GET', MOCK + '/__mock/state')[1])

EXT = {  # 測試用冒險資料庫：手套全職業 Lv10、戰鬥弓限弓箭手 Lv10
    '1082002': {'n': '工地手套', 't': '裝備', 'lv': 10, 'c': '手套'},
    '1082149': {'n': '褐色工作手套', 't': '裝備', 'lv': 10, 'c': '手套'},
    '1452002': {'n': '戰鬥弓', 't': '裝備', 'lv': 10, 'job': '弓箭手', 'c': '武器 · 弓'},
    '2040801': {'n': '手套攻擊卷軸 60%', 't': '卷軸'},
}

async def wait_jobs(kind, sec=60):
    end = time.time() + sec
    while time.time() < end:
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == kind]
        if js and all(j['status'] in ('done', 'failed', 'cancelled') for j in js):
            return js
        await asyncio.sleep(1)
    raise AssertionError(f'{kind} 工作 {sec} 秒內沒做完：' + json.dumps([(j['fromName'], j['status'], j['lastMsg']) for j in js], ensure_ascii=False))

async def main():
    async with Env(extdb=EXT) as env:
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        # 掛機中的角色會一直撿到新手套，數量對不起來：測試期間先暫停掛機
        for pg in pages:
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        d = await env.wait_chars(3)
        check(all(g.get('baseStats') for s in d['chars'].values() for g in s['gear'] if g['loc'] == '背包'), '背包裝備都有回報標準值（baseStats）')

        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        dash.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await dash.goto(HUB + '/'); await dash.wait_for_timeout(1500)
        await dash.click('nav button[data-tab=guild]')

        print('1. 讀取公倉')
        await dash.click('#gwRefresh')
        await wait_jobs('guildView')
        await dash.wait_for_timeout(4500)
        check('測試公會' in await dash.inner_text('#gwInfo'), '面板顯示公會名稱與容量：' + (await dash.inner_text('#gwInfo'))[:60])

        print('2. 存入：工地手套（物防浮動 ≥ 0）＋手套攻擊卷軸，每隻保留 2 張')
        await dash.click('#gdOpen')
        await dash.fill('#gdQ', '工地手套'); await dash.wait_for_timeout(300)
        await dash.click('#gdPickShown')
        await dash.fill('#gdQ', '手套攻擊卷軸 60%'); await dash.wait_for_timeout(300)
        await dash.click('#gdPickShown'); await dash.fill('#gdQ', '')
        await dash.click('#gdAddCond'); await dash.wait_for_timeout(200)
        await dash.select_option('[data-gdck="0"]', 'incPDD')
        await dash.fill('[data-gdcmin="0"]', '0'); await dash.press('[data-gdcmin="0"]', 'Tab')
        await dash.fill('#gdKeep', '2'); await dash.press('#gdKeep', 'Tab'); await dash.wait_for_timeout(300)
        prev = await dash.inner_text('#gdPreview')
        print('   預覽：', prev.split('\n')[0])
        # 自己算一次應該存哪些
        st = mock_state()
        want_uids, want_scroll = set(), 0
        for a in st['accounts'].values():
            c = a['chars'][a['active']]
            for g in c['equipmentBag']:
                if g['name'] == '工地手套' and not g['locked'] and g['cleanStats'].get('incPDD', 0) - g['baseStats'].get('incPDD', 0) >= 0:
                    want_uids.add(g['uid'])
            want_scroll += max(0, c['inventory'].get('i2040801', 0) - 2)
        check(f'符合 {len(want_uids)} 件' in prev, f'預覽的符合件數正確（{len(want_uids)} 件）')
        await dash.click('#gdCreate'); await dash.wait_for_timeout(800)
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        check(jobs and all(j['status'] == 'pending' for j in jobs), f'建立 {len(jobs)} 個存入工作，等待確認')
        hub_json('POST', '/api/jobs/approve-all')
        await wait_jobs('guildDeposit')
        st = mock_state(); gw = st['guild']
        check({g['uid'] for g in gw['gear']} == want_uids, f"公倉裝備正好是符合條件的 {len(want_uids)} 件")
        check(gw['items'].get('i2040801', 0) == want_scroll, f"卷軸存入 {want_scroll} 張（每隻保留 2 張）")
        check(st['accounts']['A1']['chars']['c1']['inventory'].get('i2040801') == 2, '本尊身上留下 2 張')

        print('3. 領取：裝備依建議、卷軸全部給弓箭分身')
        await dash.wait_for_timeout(3500)
        await dash.click('#gwTabs button[data-gwtab=item]'); await dash.wait_for_timeout(300)
        await dash.check('[data-gwpick="i:i2040801"]'); await dash.wait_for_timeout(200)
        await dash.fill('[data-gwqty="i:i2040801"]', '3'); await dash.press('[data-gwqty="i:i2040801"]', 'Tab')
        await dash.select_option('#gwAll', 'c3')
        await dash.click('#gwTabs button[data-gwtab=gear]'); await dash.wait_for_timeout(300)
        first = await dash.get_attribute('[data-gwpick^="g:"]', 'data-gwpick')
        sugg = await dash.eval_on_selector(f'[data-gwto="{first}"]', 'e => e.value')
        check(sugg != '', f'裝備有預設建議的角色（{sugg}）')
        await dash.check(f'[data-gwpick="{first}"]'); await dash.wait_for_timeout(200)
        await dash.select_option(f'[data-gwto="{first}"]', 'c4'); await dash.wait_for_timeout(200)
        await dash.click('#gwCreate'); await dash.wait_for_timeout(800)
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildWithdraw']
        check(sorted(j['fromCharId'] for j in jobs) == ['c3', 'c4'], '建立 2 個領取工作（弓箭分身、倉庫分身）')
        before3 = mock_state()['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0)
        hub_json('POST', '/api/jobs/approve-all')
        await wait_jobs('guildWithdraw')
        st = mock_state()
        check(st['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0) - before3 == 3, '弓箭分身領到 3 張卷軸')
        check(any(g['uid'] == first[2:] for g in st['accounts']['A3']['chars']['c4']['equipmentBag']), '倉庫分身領到指定的那件裝備')
        check(st['guild']['items'].get('i2040801') == want_scroll - 3, '公倉卷軸數量扣掉 3')

        print('4. 防呆')
        r = hub_json('POST', '/api/jobs', {'kind': 'guildDeposit', 'fromCharId': 'c1', 'batches': [{'items': [{'key': 'i2040801', 'name': '手套攻擊卷軸 60%', 'qty': 999}], 'gear': []}]})
        hub_json('POST', '/api/jobs/approve-all')
        js = await wait_jobs('guildDeposit')
        last = js[-1]
        st = mock_state()
        check(last['status'] == 'done' and st['accounts']['A1']['chars']['c1']['inventory'].get('i2040801', 0) == 0, '要存 999 張只會存身上有的數量')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    pe = [l for l in env.logs if 'pageerror' in l]
    check(not pe, '遊戲頁沒有 JS 錯誤' + ('：' + pe[0] if pe else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == "__main__": asyncio.run(main())
