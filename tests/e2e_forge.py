"""強化工坊：試跑估算 → 建立工作（要確認）→ 神匠之魂批次衝 → 結果與及格；公倉（私人版）裡的卷軸／裝備先領出再衝；詛咒卷軸提醒"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def c1(): return mock_state()['accounts']['A1']['chars']['c1']

async def game(page, action):
    return await page.evaluate("""async a => { a.requestId = crypto.randomUUID(); a.characterId = a.characterId || sessionStorage.getItem('mapleCharacter');
      const r = await fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(a) }); return await r.json(); }""", action)

async def wait_job(kind, sec=60):
    end = time.time() + sec
    while time.time() < end:
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == kind]
        if js and js[-1]['status'] in ('done', 'failed'): return js[-1]
        await asyncio.sleep(1)
    raise AssertionError(kind + ' 沒做完')

async def pick(d, sel, value):
    await d.select_option(sel, value); await d.wait_for_timeout(300)

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1'])
        await game(pages[0], {'type': 'stop'})
        await env.wait_chars(1)
        end = time.time() + 30
        while time.time() < end and 'scrolls' not in (hub_json('GET', '/api/world') or {}): await asyncio.sleep(1)
        check('i2040801' in hub_json('GET', '/api/world').get('scrolls', {}), '卷軸目錄已上傳（含適用部位、成功率、詛咒）')
        hub_json('POST', '/api/settings', {'mainCharId': 'c1'})
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=forge]'); await d.wait_for_timeout(1000)

        print('1. 試跑：工地手套 ×3、手套攻擊卷軸 60%、衝到用完、成功 3 次及格')
        await pick(d, '#fgChar', 'c1'); await pick(d, '#fgGear', '工地手套'); await pick(d, '#fgScroll', 'i2040801')
        await d.fill('#fgPass', '3'); await d.press('#fgPass', 'Tab'); await d.wait_for_timeout(300)
        plan = await d.inner_text('#fgPlan')
        check('裝備 3 件' in plan and '最多 15' in plan, '3 件、最多衝 15 次')
        check('不夠全部衝滿' in plan, '卷軸只有 12 張，提示不夠全部衝滿')
        check('保證衝完 2 件' in plan and '最多能衝 12 次' in plan, '依卷軸 12 張算出：保證能衝完 2 件（每件 5 次）')
        check(plan.count('可能輪不到') >= 2, '第 3 件標「可能輪不到」')
        sel = lambda: d.inner_text('.fg-pickbar')
        await d.click('[data-fgsel="none"]'); await d.wait_for_timeout(300)
        check('已選 0 / 3' in await sel(), '全不選 → 已選 0 件')
        await d.locator('tr.pickrow').nth(1).click(); await d.wait_for_timeout(300)
        check('已選 1 / 3' in await sel(), '點一列 → 個別勾選 1 件')
        await d.fill('#fgTopN', '2'); await d.click('[data-fgsel="top"]'); await d.wait_for_timeout(300)
        check('已選 2 / 3' in await sel(), '只選前 2 件')
        await d.click('[data-fgsel="all"]'); await d.wait_for_timeout(300)
        await d.click('[data-fgsel="sure"]'); await d.wait_for_timeout(300)
        plan = await d.inner_text('#fgPlan')
        check('已選 2 / 3' in plan and '不夠全部衝滿' not in plan, '「只選保證的 2 件」→ 卷軸夠用，不再警告')
        await d.click('[data-fgsel="all"]'); await d.wait_for_timeout(300)
        boxes = d.locator('[data-fgpick]')
        await boxes.nth(2).uncheck(); await d.wait_for_timeout(300)
        plan = await d.inner_text('#fgPlan')
        check('裝備 2 件' in plan and '最多 10' in plan and '100 萬' in plan, '取消一件 → 2 件、最多 10 次、最多 100 萬楓幣')

        print('2. 建立工作 → 確認 → 執行')
        st0 = c1(); money0 = st0['money']; bag0 = {g['uid']: g for g in st0['equipmentBag']}
        await d.click('#fgCreate'); await d.wait_for_timeout(800)
        job = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'forge'][-1]
        check(job['status'] == 'pending' and job['estimate'] == 1000000, '工作待確認、最多花費 100 萬')
        hub_json('POST', f"/api/jobs/{job['id']}/approve")
        job = await wait_job('forge')
        check(job['status'] == 'done', '強化工作完成：' + job['lastMsg'][:80])
        log = hub_json('GET', '/api/forge')['log'][-1]
        st1 = c1(); att = sum(r['attempts'] for r in log['results'])
        check(len(log['results']) == 2 and money0 - st1['money'] == att * 100000 == log['fee'], f'衝 2 件共 {att} 次，扣 {att * 10} 萬楓幣，結果記錄正確')
        bag1 = {g['uid']: g for g in st1['equipmentBag']}
        check(all(bag1[r['uid']]['successes'] == r['plus'] and r['pass'] == (r['plus'] >= 3) for r in log['results']), '每件的強化次數、及格判定跟遊戲一致')
        for _ in range(15):
            await d.wait_for_timeout(1000)
            txt = await d.inner_text('#fgLog')
            if '×' in txt: break
        dist = {}
        for r in log['results']: dist[r['plus']] = dist.get(r['plus'], 0) + 1
        check(all(f"+{p} ×{n}" in txt for p, n in dist.items()), '結果標題直接顯示 +幾 的分布：' + '、'.join(f'+{p}×{n}' for p, n in sorted(dist.items(), reverse=True)))
        check(await d.locator('#fgLog details[open] tbody tr').count() == 2 and '物攻 +' in txt, '最新一筆預設展開，列出每件 +幾 與增加的素質')
        check('+' in job['lastMsg'] or any('×' in l['msg'] for l in job['log']), '工作紀錄也寫出分布')

        print('3. 公倉（私人版）：裝備和卷軸放在公倉，執行時先領出')
        browns = [g for g in st1['equipmentBag'] if g['name'] == '褐色工作手套'][:2]
        await game(pages[0], {'type': 'guildWarehouseBatch', 'op': 'deposit', 'items': [{'kind': 'gear', 'uid': g['uid']} for g in browns] + [{'kind': 'item', 'item': 'i2040805', 'qty': 5}]})
        hub_json('POST', '/api/guild/refresh', {}); await wait_job('guildView'); await asyncio.sleep(10)
        await d.reload(); await d.wait_for_timeout(2500); await d.click('nav button[data-tab=forge]'); await d.wait_for_timeout(800)
        await pick(d, '#fgGear', '褐色工作手套'); await pick(d, '#fgScroll', 'i2040805'); await pick(d, '#fgCount', '2')
        await d.wait_for_timeout(300)
        plan = await d.inner_text('#fgPlan')
        check('公倉' in plan and '卷軸 4 張' in plan, '試跑寫出要從公倉領出卷軸 4 張、裝備：' + plan.split('\n')[-1][:60] if False else '試跑寫出要從公倉領出卷軸 4 張')
        await d.click('#fgCreate'); await d.wait_for_timeout(800)
        job = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'forge'][-1]
        hub_json('POST', f"/api/jobs/{job['id']}/approve")
        job = await wait_job('forge')
        st = mock_state(); g = st['guild']
        check(job['status'] == 'done' and not g['gear'] and g['items'].get('i2040805') == 1, '從公倉領出 2 件裝備＋4 張卷軸後衝完，公倉剩 1 張')
        log = hub_json('GET', '/api/forge')['log'][-1]
        check(len(log['results']) == 2 and all(r['attempts'] == 2 for r in log['results']), '每件衝 2 次')

        print('4. 詛咒卷軸')
        await pick(d, '#fgGear', '工地手套'); await pick(d, '#fgScroll', 'i2040899')
        plan = await d.inner_text('#fgPlan')
        check('消失' in plan and '詛咒' in await d.inner_text('#fgScrollInfo'), '試跑顯示詛咒與預估消失件數')

        print('5. 工廠圖')
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(1500)
        check('及格' in await d.inner_text('.fnode[data-fn="forge"]'), '工廠圖的強化工坊節點顯示上次結果')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    pe = [l for l in env.logs if 'pageerror' in l]
    check(not pe, '遊戲頁沒有 JS 錯誤' + ('：' + pe[0] if pe else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
