"""背包分頁：選取道具／裝備 →「存進公倉」→ 直接執行（不用到工作確認）；補給中的略過；勾「含公倉」→ 選公倉的東西 →「從公倉領取」給別的角色"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        await pages[0].evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2); await asyncio.sleep(11)
        c0 = mock_state()['accounts']['A1']['chars']['c1']
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=bag]'); await d.wait_for_timeout(1000)
        if not await d.eval_on_selector('#bCharBox', 'e => e.open'): await d.click('#bCharBox summary')
        await d.click('.ccard[data-bchar="c1"]'); await d.wait_for_timeout(400)  # 只看本尊劍士
        await d.fill('#bSearch', '手套'); await d.wait_for_timeout(500)
        await d.click('[data-bquick="all"]'); await d.wait_for_timeout(300)
        await d.fill('#bSearch', '紅色藥水'); await d.wait_for_timeout(500)
        await d.locator('tr', has_text='紅色藥水').locator('[data-bpick]').first.click(); await d.wait_for_timeout(300)
        bar = await d.inner_text('#bagBar')
        check('存進公倉' in bar, '背包動作列有「🏦 存進公倉」')
        await d.click('[data-bact="guild"]'); await d.wait_for_timeout(1500)
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        check(jobs and all(j['status'] in ('approved', 'running', 'done') for j in jobs), '建立後直接執行，不用到「工作」確認')
        end = time.time() + 40
        while time.time() < end and not all(j['status'] in ('done', 'failed') for j in jobs):
            await asyncio.sleep(1); jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildDeposit']
        g = mock_state()['guild']
        gloves = [x for x in c0['equipmentBag'] if '手套' in x['name'] and not x['locked']]
        check(jobs[-1]['status'] == 'done' and {x['uid'] for x in g['gear']} == {x['uid'] for x in gloves}, f'{len(gloves)} 件手套存進公倉')
        check(g['items'].get('i2040801') == c0['inventory']['i2040801'] and g['items'].get('i2040899') == c0['inventory']['i2040899'], '搜尋「手套」選到的卷軸全部存進公倉')
        check('i2000000' not in g['items'] and mock_state()['accounts']['A1']['chars']['c1']['inventory']['i2000000'] == c0['inventory']['i2000000'], '補給中的紅色藥水沒有被存走')
        print('2. 含公倉 → 從公倉領取')
        await d.keyboard.press('Escape'); await d.wait_for_timeout(300)
        await d.fill('#bSearch', ''); await d.wait_for_timeout(300)
        await d.check('#bGuild'); await d.wait_for_timeout(2500)
        check('裝備' in await d.inner_text('#bGuildInfo'), '勾「含公倉」後顯示公倉摘要：' + (await d.inner_text('#bGuildInfo'))[:40])
        await d.click('.ccard[data-bchar="*"]'); await d.wait_for_timeout(300)
        await d.fill('#bSearch', '工地手套'); await d.wait_for_timeout(600)
        chip = d.locator('.holder.gl').first
        n_glove = len([x for x in gloves if x['name'] == '工地手套'])
        check(await chip.count() == 1 and f'×{n_glove}' in await chip.inner_text(), f'依道具：工地手套那列有「🏦 公倉 ×{n_glove}」')
        await chip.click(); await d.wait_for_timeout(400)
        bt = ' '.join((await d.inner_text('#bagBar')).split())
        check(f'公倉已選 {n_glove}' in bt, '動作列顯示「公倉已選」和「從公倉領取」')
        await d.select_option('#bGuildTo', 'c3'); await d.wait_for_timeout(300)
        await d.click('[data-bact="guildTake"]'); await d.wait_for_timeout(1500); await d.keyboard.press('Escape')
        end = time.time() + 40
        while time.time() < end:
            wj = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'guildWithdraw']
            if wj and wj[-1]['status'] in ('done', 'failed'): break
            await asyncio.sleep(1)
        st = mock_state(); c3 = st['accounts']['A2']['chars']['c3']
        want = {x['uid'] for x in gloves if x['name'] == '工地手套'}
        check(wj[-1]['status'] == 'done' and want <= {x['uid'] for x in c3['equipmentBag']} and not (want & {x['uid'] for x in st['guild']['gear']}), f'{n_glove} 件工地手套從公倉領到弓箭分身（不用到工作確認）')
        print('3. 依角色：公倉一格一格選')
        await d.fill('#bSearch', ''); await d.click('[data-bview="char"]'); await d.wait_for_timeout(2500)
        tile = d.locator('.bag-guild [data-bpick="G|i:i2040801"]')
        check(await tile.count() == 1, '依角色最後有「🏦 公會倉庫」一塊，每樣東西一格')
        await tile.click(); await d.wait_for_timeout(300)
        await d.select_option('#bGuildTo', 'c3'); await d.click('[data-bact="guildTake"]'); await d.wait_for_timeout(1500); await d.keyboard.press('Escape')
        q = st['guild']['items'].get('i2040801', 0)
        end = time.time() + 40
        while time.time() < end and mock_state()['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0) < q: await asyncio.sleep(1)
        st = mock_state()
        check(st['accounts']['A2']['chars']['c3']['inventory'].get('i2040801', 0) == q and 'i2040801' not in st['guild']['items'], f'手套攻擊卷軸 60% ×{q} 全部領到弓箭分身')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
