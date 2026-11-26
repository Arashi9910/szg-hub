"""打王強制停止：隊伍兩隻一起打很久的王 → 面板只停其中一隻（v0.69.3 整隊同進退：隊友也一起回去，只有被停的暫停打王）→
另一隻很久的王用卡片「全部停止」→ 兩隻都回去、30 分鐘內不再派 →「恢復」"""
import asyncio, os, sys, time, json
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'
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

def boss_jobs(): return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']
def job_of(cid): return next((j for j in boss_jobs() if j['fromCharId'] == cid), None)

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c3': ['mBoss2']}, 'estMax': 100000}})
        await env.open_accounts(['A2', 'A3'])
        await env.wait_chars(2)
        await wait(lambda: (lambda b: all(c.get('at') for c in b['chars'] if c['charId'] in ('c3', 'c4')) and len(b['chars']) >= 2)(hub_json('GET', '/api/boss')), 60)
        homes = {'c3': mock_char('A2', 'c3')['map'], 'c4': mock_char('A3', 'c4')['map']}
        print('1. 兩隻一起去打蘑菇王（很久）')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'charMobs': {'c3': ['mBoss2']}, 'estMax': 100000}})
        hub_json('POST', '/api/boss/run-now')
        check(len(boss_jobs()) == 2, f'兩個打王工作（{len(boss_jobs())}）')
        lv = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None and len(g.get('who', [])) == 2), None), 60)
        check(lv and {w['charId'] for w in lv['who']} == {'c3', 'c4'}, '正在打：列出兩隻（who）')

        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab="maps"]'); await d.wait_for_timeout(2500)

        print('2. 只停 c4')
        await d.click('#bossLive [data-bstop="c4"]'); await d.wait_for_timeout(1000)
        done4 = await wait(lambda: (lambda j: j if j and j['status'] in ('done', 'failed', 'cancelled') else None)(job_of('c4')), 40)
        check(done4 and done4['status'] == 'done', f"c4 的工作結束（{done4 and done4['status']}）")
        c4 = mock_char('A3', 'c4')
        check(c4['map'] == homes['c4'] and c4['auto'], 'c4 回到原本的地圖並開始掛機')
        done3 = await wait(lambda: (lambda j: j if j and j['status'] in ('done', 'failed', 'cancelled') else None)(job_of('c3')), 40)
        check(done3 and done3['status'] == 'done' and mock_char('A2', 'c3')['map'] == homes['c3'], '整隊同進退：c3 也跟著回原本的地圖')
        held = {c['charId']: bool(c['held']) for c in hub_json('GET', '/api/boss')['chars']}
        check(held.get('c4') and not held.get('c3'), f'只有被停的 c4 暫停打王（{held}）')
        log = hub_json('GET', '/api/boss')['log']
        check(any('強制停止' in l['msg'] and l['charId'] == 'c4' for l in log), '紀錄有 c4 強制停止')
        hub_json('POST', '/api/boss/unhold', {})
        http('GET', MOCK + '/__mock/boss?acct=A2&char=c3&mob=mBoss1&hp=900000000&cd=0')   # 紅寶王也打很久
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'charMobs': {'c3': ['mBoss1']}, 'estMax': 100000}})
        hub_json('POST', '/api/boss/run-now')
        check(len([j for j in boss_jobs() if j['status'] in ('approved', 'running')]) == 2, '兩隻一起去打紅寶王')
        await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['mob'] == 'mBoss1' and g['hp'] is not None), None), 60)

        print('3. 全部停止（卡片上的按鈕）')
        await d.evaluate('loadBoss(true).then(() => renderBoss(true))'); await d.wait_for_timeout(1500)
        await d.click('.bb[data-bbmob="mBoss1"] [data-bstopall]'); await d.wait_for_timeout(1000)
        done3 = await wait(lambda: (lambda j: j if j and j['status'] in ('done', 'failed', 'cancelled') else None)(next((x for x in reversed(boss_jobs()) if x['fromCharId'] == 'c3'), None)), 40)
        check(done3 and done3['status'] == 'done', f"c3 的工作結束（{done3 and done3['status']}）")
        c3 = mock_char('A2', 'c3')
        check(c3['map'] == homes['c3'] and c3['auto'], 'c3 回到原本的地圖並開始掛機')
        check(not any('接著去' in (l['msg'] if isinstance(l, dict) else str(l)) for l in done3['log']), '停止後沒有連續打去別的王')

        print('4. 30 分鐘內不再派、恢復')
        hub_json('POST', '/api/boss/run-now')
        check(len(boss_jobs()) == 4, '停止的角色不會馬上又被派去打王')
        b = hub_json('GET', '/api/boss')
        check(all(c['held'] > time.time() * 1000 for c in b['chars'] if c['charId'] in ('c3', 'c4')), '兩隻都標暫停打王')
        await d.evaluate('loadBoss(true).then(() => renderBoss(true))'); await d.wait_for_timeout(1000)
        check('暫停打王' in await d.inner_text('#bossSum'), '面板摘要顯示：' + await d.inner_text('#bossSum'))
        await d.click('[data-bunhold]'); await d.wait_for_timeout(1000)
        check(not any(c['held'] for c in hub_json('GET', '/api/boss')['chars']), '按「恢復」→ 不再暫停')
        await d.screenshot(path='/tmp/boss_stop.png')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
