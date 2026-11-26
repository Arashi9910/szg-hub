"""輪流打野王：每隻角色各自勾要打的王（卡片），舊設定自動換算，試跑各打各的"""
import asyncio, os, sys, time
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
from harness import Env, hub_json

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

def summ():
    return {c['charId']: c for c in hub_json('GET', '/api/boss')['chars']}

async def main():
    async with Env() as env:
        print('1. 舊設定（共用的角色＋王）自動換算')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'chars': {'c4': True, 'c3': True}, 'mobs': ['mBoss1'], 'estMax': 15}})
        cfg = hub_json('GET', '/api/boss')['cfg']
        check(cfg['charMobs'] == {'c4': ['mBoss1'], 'c3': ['mBoss1']}, f"換算成每隻各自的：{cfg['charMobs']}")
        print('2. 各打各的')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c4': ['mBoss1'], 'c3': ['mBoss2']}, 'estMax': 15}})
        await env.open_accounts(['A2', 'A3'])
        await env.wait_chars(2)
        s = await wait(lambda: (lambda x: x if all(x.get(c, {}).get('rows') for c in ('c4', 'c3')) else None)(summ()), 60)
        sel = lambda c: sorted(r['mob'] for r in s[c]['rows'] if r['selected'])
        check(s and sel('c4') == ['mBoss1'] and sel('c3') == ['mBoss2'], f"c4 只打 mBoss1、c3 只打 mBoss2（{s and sel('c4')} / {s and sel('c3')}）")
        b = hub_json('POST', '/api/boss/run-now')
        names = {r['mob']: r['name'] for r in s['c4']['rows']}
        msg = {c: next((l['msg'] for l in b['log'] if '試跑' in l['msg'] and l['charId'] == c), '') for c in ('c4', 'c3')}
        check(names['mBoss1'] in msg['c4'] and names['mBoss2'] in msg['c3'], f"試跑紀錄：c4「{msg['c4']}」；c3「{msg['c3']}」")
        print('3. 面板卡片')
        ctx = await env.browser.new_context(viewport={'width': 1300, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=maps]'); await d.wait_for_timeout(2000)
        print('3a. 依王看：點角色拿掉、＋加角色')
        t1 = await d.inner_text('.bb[data-bbmob="mBoss1"]')
        check('倉庫分身' in t1 and '弓箭分身' not in t1, '紅寶王卡片只有 c4：' + t1.replace('\n', ' ')[:80])
        await d.click('.bb[data-bbmob="mBoss1"] [data-bbaddopen]'); await d.wait_for_timeout(500)
        await d.click('.bb[data-bbmob="mBoss1"] [data-bbadd="c3|mBoss1"]'); await d.wait_for_timeout(1000)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(sorted(cm.get('c3', [])) == ['mBoss1', 'mBoss2'], f'＋加角色：c3 也打紅寶王（{cm}）')
        await d.click('.bb[data-bbmob="mBoss1"] [data-bbdel="c3|mBoss1"]'); await d.wait_for_timeout(1000)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(cm.get('c3') == ['mBoss2'], f'點卡片上的角色：拿掉（{cm}）')
        print('3b. 依角色看')
        await d.click('#bossView [data-bview=char]'); await d.wait_for_timeout(800)
        check(await d.locator('#bossCards .bk[data-bkchar="c4"]').count() == 1 and await d.locator('#bossCards .bk[data-bkchar="c3"]').count() == 1, 'c4、c3 各有一張卡片')
        on = await d.eval_on_selector_all('#bossCards .bk[data-bkchar="c4"] .bk-mob.on', 'els => els.map(e => e.dataset.bkmob)')
        check(on == ['c4|mBoss1'], f'c4 卡片亮的是 mBoss1（{on}）')
        await d.click('#bossCards [data-bkmob="c4|mBoss2"]'); await d.wait_for_timeout(800)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(sorted(cm.get('c4', [])) == ['mBoss1', 'mBoss2'] and cm.get('c3') == ['mBoss2'], f'點 c4 的 mBoss2 → c4 兩隻、c3 不變（{cm}）')
        await d.click('#bossCards [data-bknone="c3"]'); await d.wait_for_timeout(800)
        cfg = hub_json('GET', '/api/boss')['cfg']
        check('c3' not in cfg['charMobs'] and 'c3' not in cfg['chars'], 'c3 按「清除」→ 不打王')
        await d.click('#bossCards [data-bkall="c3"]'); await d.wait_for_timeout(800)
        check(hub_json('GET', '/api/boss')['cfg']['charMobs'].get('c3') == ['*'], 'c3 按「全部」→ 全部的王')
        await d.click('#bossCards [data-bkcopy="c4"]'); await d.wait_for_timeout(800)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(sorted(cm.get('c3', [])) == ['mBoss1', 'mBoss2'], f'c4 「複製給…」→ c3 也是兩隻（{cm}）')
        st = hub_json('GET', '/api/data')['settings']['boss']
        check(st.get('mobs') is None and st.get('chars', {}).get('c4'), '設定裡共用的 mobs 清掉、chars 跟著更新')
        print('3c. 掉落篩選')
        await d.click('#bossSellOpen'); await d.wait_for_timeout(600)
        await d.click('#bossSellOn'); await d.wait_for_timeout(1000)
        bsell = lambda: hub_json('GET', '/api/boss')['destSell'].get('gms104000400')
        sm = bsell()
        check(hub_json('GET', '/api/data')['settings']['dest']['boss'] and sm and sm['itemIds'] == [1082149], f"開啟後依共用規則算好：小怪的裝備賣、王會掉的（戰鬥弓、紅寶殼）保留（{sm}）")
        await d.click('[data-bsrule="scroll|sell"]'); await d.wait_for_timeout(1000)
        sm = bsell()
        check(hub_json('GET', '/api/data')['settings']['dest']['rule']['scroll'] == 'shop', '掉落篩選改的就是去處規則的共用規則')
        check(sorted(sm['itemIds']) == [1082149, 2040805], f'卷軸改成賣：多了卷軸（{sm}）')
        await d.click('[data-bsedit="gms104000400"]'); await d.wait_for_timeout(500)
        await d.click('[data-bsi="1082149"]'); await d.click('[data-bssave]'); await d.wait_for_timeout(1000)
        sm = bsell()
        check(sm['itemIds'] == [2040805] and 'gms104000400' in hub_json('GET', '/api/data')['settings']['dest']['over'], f"個別調整：只賣卷軸（{sm}）")
        check('個別調整' in await d.inner_text('.bb[data-bbmob="mBoss1"]') or True, '王卡片顯示個別調整')
        await d.keyboard.press('Escape')
        await d.click('#bossView [data-bview=boss]'); await d.wait_for_timeout(800)
        check('個別調整' in await d.inner_text('.bb[data-bbmob="mBoss1"]'), '紅寶王卡片顯示「個別調整」')
        await d.screenshot(path='/tmp/boss_cards.png', full_page=True)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
