"""副本（v0.77）：用自己的角色組副本隊（建立 → 加入 → 準備 → 開始），戰況每秒更新（王的血量、階段、準備時間、異常狀態），投降／結束"""
import asyncio, json, os, sys, time
os.environ.update({'MOCK_RAID_PREP_MS': '4000', 'MOCK_RAID_DPS': '0.04'})
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def raid(): return hub_json('GET', '/api/raid')
async def wait(fn, sec=40, step=0.5):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception:
            pass
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(1500)

        print('1. 選副本、隊長、隊員')
        await d.click('[data-rdkind="zakum"]'); await d.wait_for_timeout(500)
        await d.select_option('#rdLeader', 'c1'); await d.wait_for_timeout(800)
        await d.check('[data-rdmem="c3"]'); await d.wait_for_timeout(500)
        await d.check('[data-rdmem="c4"]'); await d.wait_for_timeout(800)
        plan = hub_json('GET', '/api/data')['settings'].get('raid') or {}
        check(plan.get('kind') == 'zakum' and plan.get('leader') == 'c1' and sorted(plan.get('members', [])) == ['c3', 'c4'], f'存好計畫：{plan}')

        print('2. 建立隊伍 → 加入 → 準備')
        await d.click('[data-rdact="create"]')
        v = await wait(lambda: (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        check(v and v['isLeader'] and v['code'], f"建立了殘暴炎魔副本隊伍（代碼 {v and v['code']}）")
        check(any('建立' in m for m in msgs), '建立前先確認')
        await d.wait_for_timeout(1500)
        await d.click('[data-rdact="join"]')
        t = await wait(lambda: (lambda tm: tm if tm and len(tm['members']) == 3 else None)((raid()['views'].get('c1') or {}).get('view', {}).get('team')) or (hub_json('POST', '/api/raid/act', {'targets': [{'charId': 'c1', 'cmd': {'type': 'sync'}}]}) and None), 60, 2)
        check(t, '弓箭分身、倉庫分身都加入了')
        await d.wait_for_timeout(1500)
        txt = await d.inner_text('#rdTeam')
        check('弓箭分身' in txt and '倉庫分身' in txt and '未準備' in txt and '本週剩' in txt, '隊伍表格列出隊員、未準備、本週剩幾場')
        await d.click('[data-rdact="ready"]')
        hub_json('POST', '/api/raid/act', {'targets': [{'charId': 'c1', 'cmd': {'type': 'sync'}}]})
        t = await wait(lambda: (lambda tm: tm if tm and all(m['leader'] or m['ready'] for m in tm['members']) else None)((raid()['views'].get('c1') or {}).get('view', {}).get('team')) or (hub_json('POST', '/api/raid/act', {'targets': [{'charId': 'c1', 'cmd': {'type': 'sync'}}]}) and None), 60, 3)
        check(t, '隊員都準備好了')

        print('3. 開始 → 戰況每秒更新')
        await d.wait_for_timeout(1500)
        msgs.clear()
        await d.click('[data-rdact="start"]')
        check(await wait(lambda: any('開始' in m for m in msgs), 5), '開始前先確認（列出隊員）')
        live = await wait(lambda: (raid()['live'].get('c1') or {}).get('battle'), 40)
        check(live and live['raid'] == 'zakum' and live['phase'] == 1, f'戰況：殘暴炎魔第 1 階段（{live}）')
        await d.wait_for_timeout(1500)
        txt = await d.inner_text('#rdBattle')
        check('準備時間' in txt and '第 1 階段' in txt and '剩餘' in txt, '面板顯示準備時間倒數、階段、剩餘時間')
        e = await wait(lambda: (raid()['live'].get('c1') or {}).get('enemies'), 20)
        check(e and e[0]['maxHp'] == 3000000, f'拿到王的血量（{e}）')
        hp0 = e[0]['hp']
        e2 = await wait(lambda: (lambda x: x if x and x[0]['hp'] < hp0 else None)((raid()['live'].get('c1') or {}).get('enemies')), 20)
        check(e2, f'準備時間過後王的血量往下掉（{hp0} → {e2 and e2[0]["hp"]}）')
        await d.wait_for_timeout(1200)
        check(await d.locator('#rdBattle .rd-en .rd-bar.boss').count() >= 1, '王的血條')
        check(await d.locator('#rdBattle .rd-mem tr').count() == 4, '三隻隊員的 HP／MP')
        p2 = await wait(lambda: (lambda b: b if b and b['phase'] == 2 else None)((raid()['live'].get('c1') or {}).get('battle')), 30)
        check(p2, '血量一半進入第 2 階段')
        await d.wait_for_timeout(1500)
        txt = await d.inner_text('#rdBattle')
        check('第 2 階段' in txt and '封印' in txt, f'面板顯示第 2 階段、隊員被封印的秒數')

        print('4. 打完：戰況收起來')
        gone = await wait(lambda: not any(v.get('battle') for v in raid()['live'].values()), 60, 1)
        check(gone, '王倒下後戰況結束')
        await d.wait_for_timeout(1500)
        check('還沒開打' in await d.inner_text('#rdBattle'), '面板回到「還沒開打」')
        print('5. 解散隊伍')
        await d.click('[data-rdact="leave"]')
        gone = await wait(lambda: not (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40, 2)
        check(gone, '隊伍解散了')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
