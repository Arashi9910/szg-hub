"""輪流打野王（隊伍）：同隊伍的角色以隊伍為單位一起出發打同一隻王，只勾其中一隻也會一起去；各自回原本的地圖；王共用（打死後兩隻都看到冷卻）"""
import asyncio, os, sys, time, json
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_PARTY'] = 'c3,c4'
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

def summ():
    return {c['charId']: c for c in hub_json('GET', '/api/boss')['chars']}

def boss_jobs():
    return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'chars': {'c3': True}, 'mobs': ['mBoss1'], 'estMax': 15, 'visitMax': 3}})
        await env.open_accounts(['A2', 'A3'])
        await env.wait_chars(2)
        print('1. 偵測隊伍')
        s = await wait(lambda: (lambda x: x if 'c4' in x and x['c4'].get('party') and x['c3'].get('at') else None)(summ()), 60)
        check(s and set(s['c3']['party']['ids']) == {'c3', 'c4'}, '中控認得 c3、c4 同一隊')
        check(s and s['c4']['on'] and not s['c4']['picked'], '只勾 c3，c4 也算進來（跟著隊友）')
        print('2. 試跑：寫出整隊一起去')
        b = hub_json('POST', '/api/boss/run-now')
        check(any('試跑' in l['msg'] and '隊伍' in l['msg'] and '一起' in l['msg'] for l in b['log']), '紀錄：' + next((l['msg'] for l in b['log'] if '試跑' in l['msg']), '（沒有）'))
        print('3. 自動：兩隻一起出發打同一隻王')
        homes = {'c3': mock_char('A2', 'c3')['map'], 'c4': mock_char('A3', 'c4')['map']}
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss1'], 'estMax': 15, 'visitMax': 3}})
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        check(len(js) == 2 and {j['fromCharId'] for j in js} == {'c3', 'c4'} and len({j['batches'][0]['boss']['mob'] for j in js}) == 1, f'建立 2 個工作、同一隻王（{len(js)}）')
        hub_json('POST', '/api/boss/run-now')
        check(len(boss_jobs()) == 2, '還在打時不會重複派')
        done = await wait(lambda: all(j['status'] in ('done', 'failed') for j in boss_jobs()) and boss_jobs(), 150)
        check(done and all(j['status'] == 'done' for j in boss_jobs()), '兩個工作都完成')
        log = hub_json('GET', '/api/boss')['log']
        check(sum(1 for l in log if '打死了' in l['msg']) >= 1, '紀錄有「打死了」')
        check(mock_char('A2', 'c3')['map'] == homes['c3'] and mock_char('A3', 'c4')['map'] == homes['c4'], '兩隻都回到各自原本的地圖')
        s = summ()
        check(all(next(r for r in s[c]['rows'] if r['mob'] == 'mBoss1')['cooling'] for c in ('c3', 'c4') if s[c]['rows']), '共用的王變成冷卻中')
        print('4. 面板')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto('http://127.0.0.1:8787/'); await dash.wait_for_timeout(1500)
        await dash.click('nav button[data-tab="maps"]'); await dash.wait_for_timeout(2500)
        txt = await dash.inner_text('#bossTable')
        check('隊伍（2 人一起出發' in txt and '跟著隊友' in txt, '面板把同隊的放在一起')
        await dash.screenshot(path='/tmp/boss_party.png')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
