"""死亡原因與復活次數＋新的野王提醒
1. 被怪打死 → 中控記下原因（打到角色的怪、遊戲紀錄）、中控自動復活 → 復活次數算「中控」
2. 遊戲自己的自動復活（同一次同步就活過來）→ 仍然記一次死亡，復活算「遊戲自動」
3. 關掉自動復活 → 記死亡、標「還沒復活」
4. 面板「死亡與復活」卡片顯示次數，歸零
5. 遊戲新增野王 → 野王卡片提醒，按「加到等級夠的角色」→ 逐一挑選的角色加上新王，「全部」的不動
"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

def deaths(): return hub_json('GET', '/api/deaths')

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'idlePolicy': {'autoRenew': False, 'autoRevive': True, 'reviveMaxPerHour': 60}})
        await env.open_accounts(['A2'])
        await env.wait_chars(1)
        await asyncio.sleep(4)

        print('1. 被紅寶打死 → 記原因、中控自動復活')
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3&by=m1210101&dmg=777')
        x = await wait(lambda: next((l for l in deaths()['log'] if l.get('revivedAt')), None), 80)
        check(x, '死亡紀錄有了，而且已復活')
        if x:
            check('紅寶' in x['cause'], f"原因：{x['cause']}")
            check(any(t['name'] == '紅寶' and t['dmg'] == 777 for t in x['top']), f"死前受到的傷害：{x['top']}")
            check('擊倒' in x['gameLine'], f"遊戲紀錄：{x['gameLine']}")
            check(x['revivedBy'] == 'hub', f"復活者＝中控（{x['revivedBy']}）")
            check(x['mapName'] == '射手訓練場', f"地點：{x['mapName']}")
        check(len(deaths()['log']) == 1, '同一次死亡只記一次')

        print('2. 遊戲自己的自動復活')
        await asyncio.sleep(3)
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3&by=m100100&dmg=50&gamerevive=1')
        y = await wait(lambda: (lambda l: l[0] if len(l) >= 2 and l[0].get('revivedAt') else None)(deaths()['log']), 30)
        check(y and '嫩寶' in y['cause'], '記到第二次死亡：' + (y['cause'] if y else '（沒有）'))
        check(y and y['revivedBy'] == 'game', f"復活者＝遊戲自動（{y and y['revivedBy']}）")

        print('3. 關掉自動復活 → 還沒復活')
        hub_json('POST', '/api/settings', {'idlePolicy': {'autoRenew': False, 'autoRevive': False, 'reviveMaxPerHour': 60}})
        await asyncio.sleep(3)
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3')
        z = await wait(lambda: (lambda l: l[0] if len(l) >= 3 else None)(deaths()['log']), 30)
        check(z and not z.get('revivedAt'), '第三次死亡記下，標還沒復活')
        await asyncio.sleep(8)
        check(mock_char('A2', 'c3')['hp'] == 0 and len(deaths()['log']) == 3, '沒有被復活、沒有重複記錄')
        s = deaths()['chars'][0]
        check(s['deaths'] == 3 and s['revives'] == 2 and s['rv']['hub'] == 1 and s['rv']['game'] == 1, f"統計：死亡 {s['deaths']}、復活 {s['revives']} {s['rv']}")

        print('4. 面板卡片')
        ctx = await env.browser.new_context(viewport={'width': 1300, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(2500)
        check('累計死亡 3 次、復活 2 次' in await d.inner_text('#deathSum'), '摘要：' + await d.inner_text('#deathSum'))
        await d.click('#deathCard summary'); await d.wait_for_timeout(1200)
        t = await d.inner_text('#deathOut')
        check('弓箭分身' in t and '中控 1' in t and '遊戲自動 1' in t and '還沒復活' in t, '表格：' + t.replace('\n', ' ')[:140])
        await d.click('[data-dreset="c3"]'); await d.wait_for_timeout(1000)
        check(not deaths()['log'], '歸零後紀錄清空')

        print('5. 遊戲新增野王')
        st = lambda mobs: hub_json('POST', '/api/boss/state', {'charId': 'c3', 'serverTime': int(time.time() * 1000), 'list': [
            {'map': m, 'mapName': n, 'mob': b, 'name': nm, 'instanceId': f'solo:c3:{m}', 'deadline': 0, 'spawned': False, 'available': False} for m, n, b, nm in mobs]})
        old = [('gms104000400', '海岸草叢3', 'mBoss1', '紅寶王'), ('gms100000005', '蘑菇王棲息地', 'mBoss2', '蘑菇王')]
        st(old)
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c3': ['mBoss1'], 'c1': ['*']}, 'chars': {'c3': True, 'c1': True}}})
        check(not hub_json('GET', '/api/boss')['newBosses'], '一開始的王都不算新的')
        st(old + [('gms240020401', '噴火龍棲息地', 'mBoss3', '噴火龍')])
        nb = hub_json('GET', '/api/boss')['newBosses']
        check([x['mob'] for x in nb] == ['mBoss3'], f'新的王：{nb}')
        await d.click('nav button[data-tab="maps"]'); await d.wait_for_timeout(2500)
        await d.wait_for_selector('#bossNew:has-text("遊戲新增了")', timeout=15000)
        check('噴火龍' in await d.inner_text('#bossNew'), '野王卡片提醒：' + (await d.inner_text('#bossNew')).replace('\n', ' ')[:90])
        await d.click('#bossNewAdd'); await d.wait_for_timeout(1500)
        cm = hub_json('GET', '/api/boss')['cfg']['charMobs']
        check(cm.get('c3') == ['mBoss1', 'mBoss3'], f"逐一挑選的角色加上新王：{cm.get('c3')}")
        check(cm.get('c1', ['*']) == ['*'], '選「全部」的角色不動')
        check(not hub_json('GET', '/api/boss')['newBosses'] and not (await d.inner_text('#bossNew')).strip(), '處理過就不再提醒')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
