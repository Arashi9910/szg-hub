"""分流：強化結果的及格／不及格各自處理（鎖定、賣出、交給角色、存進公倉），標成已分流；工廠圖的分流節點"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def jobs(kind): return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == kind]

async def wait_done(ids, sec=60):
    end = time.time() + sec
    while time.time() < end:
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['id'] in ids]
        if js and all(j['status'] in ('done', 'failed') for j in js): return js
        await asyncio.sleep(1)
    raise AssertionError('工作沒做完')

async def forge(d, gear, item, count, minsucc):
    await d.click('nav button[data-tab=forge]'); await d.wait_for_timeout(800)
    await d.select_option('#fgChar', 'c1'); await d.wait_for_timeout(300)
    await d.select_option('#fgGear', gear); await d.wait_for_timeout(300)
    await d.select_option('#fgScroll', item); await d.wait_for_timeout(300)
    await d.select_option('#fgCount', count); await d.wait_for_timeout(300)
    await d.fill('#fgPass', str(minsucc)); await d.press('#fgPass', 'Tab'); await d.wait_for_timeout(300)
    await d.click('#fgCreate'); await d.wait_for_timeout(800); await d.keyboard.press('Escape')
    j = jobs('forge')[-1]; hub_json('POST', f"/api/jobs/{j['id']}/approve")
    await wait_done([j['id']])
    await asyncio.sleep(11)  # 等角色回報衝完的裝備
    return hub_json('GET', '/api/forge')['log'][-1]

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages: await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2)
        end = time.time() + 30
        while time.time() < end and 'scrolls' not in (hub_json('GET', '/api/world') or {}): await asyncio.sleep(1)
        hub_json('POST', '/api/settings', {'mainCharId': 'c1'})
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)

        print('1. 及格→鎖定、不及格→賣給商店')
        http('GET', MOCK + '/__mock/luck?seq=' + ','.join(['1'] * 5 + ['0'] * 40))  # 第一件全成功（及格），其他全失敗
        r = await forge(d, '工地手套', 'i2040801', 'all', 4)
        passed = [x['uid'] for x in r['results'] if x['pass'] and not x['destroyed']]; failed = [x['uid'] for x in r['results'] if not x['pass'] and not x['destroyed']]
        print(f'   衝了 {len(r["results"])} 件：及格 {len(passed)}、不及格 {len(failed)}')
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1200)
        check('等你分流' in await d.inner_text('.fnode[data-fn="forge"]'), '城鎮圖的強化建築顯示「等你分流」')
        await d.click('nav button[data-tab=forge]'); await d.wait_for_timeout(1000)
        box = d.locator('#fgLog details[open] .fg-split')
        check(await box.count() == 1, '最新一筆結果下面有分流區塊')
        await box.locator('select[data-fgsp="pass"]').select_option('lock'); await d.wait_for_timeout(200)
        await d.locator('#fgLog details[open] .fg-split select[data-fgsp="fail"]').select_option('sell'); await d.wait_for_timeout(200)
        money0 = mock_state()['accounts']['A1']['chars']['c1']['money']
        await d.locator('#fgLog details[open] [data-fgsprun]').click(); await d.wait_for_timeout(1500); await d.keyboard.press('Escape')
        new = [j for j in hub_json('GET', '/api/data')['jobs'] if j['status'] == 'pending']
        check({j['kind'] for j in new} == ({'lock'} if passed else set()) | ({'sell'} if failed else set()), f"建立工作：{[j['kind'] for j in new]}（待確認）")
        hub_json('POST', '/api/jobs/approve-all'); await wait_done([j['id'] for j in new])
        bag = {g['uid']: g for g in mock_state()['accounts']['A1']['chars']['c1']['equipmentBag']}
        check(all(bag[u]['locked'] for u in passed), f'及格的 {len(passed)} 件已鎖定')
        check(not any(u in bag for u in failed) and mock_state()['accounts']['A1']['chars']['c1']['money'] - money0 == len(failed) * 100, f'不及格的 {len(failed)} 件已賣掉')
        await d.wait_for_timeout(5500)
        check('已分流' in await d.inner_text('#fgLog'), '結果標成「已分流」')

        print('2. 及格→交給另一個帳號的角色、不及格→存進公倉')
        http('GET', MOCK + '/__mock/luck?seq=' + ','.join(['1'] * 2 + ['0'] * 40))
        r = await forge(d, '褐色工作手套', 'i2040805', '2', 1)
        passed = [x['uid'] for x in r['results'] if x['pass']]; failed = [x['uid'] for x in r['results'] if not x['pass'] and not x['destroyed']]
        print(f'   衝了 {len(r["results"])} 件：及格 {len(passed)}、不及格 {len(failed)}')
        await d.wait_for_timeout(1000)
        await d.locator('#fgLog details[open] .fg-split select[data-fgsp="pass"]').select_option('give'); await d.wait_for_timeout(300)
        opts = await d.locator('#fgLog details[open] select[data-fgspto] option').all_inner_texts()
        check(opts and '弓箭分身' in opts[0] and not any('本尊' in o for o in opts), f'交給誰：只列別的帳號、可以穿的角色（{opts}）')
        await d.locator('#fgLog details[open] .fg-split select[data-fgsp="fail"]').select_option('guild'); await d.wait_for_timeout(200)
        await d.locator('#fgLog details[open] [data-fgsprun]').click(); await d.wait_for_timeout(2000); await d.keyboard.press('Escape')
        gv = jobs('give'); dep = jobs('guildDeposit')
        if passed: check(gv and gv[-1]['toCharId'] == 'c3' and gv[-1]['status'] == 'pending', '建立交易工作：本尊劍士 → 弓箭分身（待確認）')
        if failed:
            await wait_done([dep[-1]['id']])
            check({g['uid'] for g in mock_state()['guild']['gear']} >= set(failed), f'不及格的 {len(failed)} 件自動存進公倉')
        for j in gv: hub_json('POST', f"/api/jobs/{j['id']}/cancel")
        check(S := ('已分流' in await d.inner_text('#fgLog')), '第二筆也標成已分流')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
