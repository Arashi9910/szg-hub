"""輪流打野王：連續打（打完一隻直接去下一隻，全部打完才回練功圖）、隊伍各自分開打（同一隻不同時去）、隊伍一起連續打（同隊拿到同一個下一隻）"""
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

def boss_jobs():
    return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']

def summ():
    return {c['charId']: c for c in hub_json('GET', '/api/boss')['chars']}

def reset_bosses():
    for acct, cid in (('A2', 'c3'), ('A3', 'c4')):
        for mob in ('mBoss1', 'mBoss2'):
            http('GET', MOCK + f'/__mock/boss?acct={acct}&char={cid}&mob={mob}&cd=0&hp=2000')
    # 中控記的王狀態是分頁每 4 分鐘回報一次的：直接告訴中控「都已重生」（和遊戲現在的狀態一致）
    sm = summ()
    for cid in ('c3', 'c4'):
        rows = (sm.get(cid) or {}).get('rows') or []
        if rows: hub_json('POST', '/api/boss/state', {'charId': cid, 'serverTime': int(time.time() * 1000), 'list': [{'map': r['map'], 'mapName': r['mapName'], 'mob': r['mob'], 'name': r['name'], 'instanceId': r['instanceId'], 'deadline': 0, 'spawned': True, 'available': False} for r in rows]})

def done_all():
    js = boss_jobs()
    return js if js and all(j['status'] in ('done', 'failed') for j in js) else None

BASE = {'estMax': 100000, 'visitMax': 3}

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boss': {'mode': 'off', 'charMobs': {}, **BASE}})
        await env.open_accounts(['A2', 'A3'])
        await env.wait_chars(2)
        await wait(lambda: (lambda x: x if x.get('c3', {}).get('party') else None)(summ()), 60)
        homes = {'c3': mock_char('A2', 'c3')['map'], 'c4': mock_char('A3', 'c4')['map']}

        print('1. 隊伍各自分開打：同一隻王不會同時去')
        reset_bosses()
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'partyMode': 'split', 'chain': False, 'charMobs': {'c3': ['*'], 'c4': ['*']}, **BASE}})
        s = await wait(lambda: (lambda x: x if all(x.get(c, {}).get('at') for c in ('c3', 'c4')) else None)(summ()), 90)
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        mobs = sorted(j['batches'][0]['boss']['mob'] for j in js)
        check(len(js) == 2 and mobs == ['mBoss1', 'mBoss2'], f'兩隻各自出發、打不同的王（{[(j["fromName"], j["batches"][0]["boss"]["mob"]) for j in js]}）')
        await wait(done_all, 200, 2)
        check(all(j['status'] == 'done' for j in boss_jobs()), '兩個都完成')
        hub_json('POST', '/api/jobs/clear', {})

        print('2. 單隻連續打：打完一隻直接去下一隻，全部打完才回練功圖')
        reset_bosses()
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'partyMode': 'split', 'chain': True, 'charMobs': {'c3': ['*']}, **BASE}})
        await asyncio.sleep(3)
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        check(len(js) == 1 and js[0]['fromCharId'] == 'c3', '只有 c3 出發')
        await wait(done_all, 240, 2)
        j = boss_jobs()[0]
        logs = ' / '.join(l['msg'] for l in j['log'])
        check(j['status'] == 'done' and '接著去' in logs, f'工作紀錄有「接著去」（{j["status"]}）')
        blog = [l['msg'] for l in hub_json('GET', '/api/boss')['log']]
        check(sum('打死了' in m for m in blog) >= 2 and any('沒有下一隻了' in m for m in blog), '打死 2 隻、最後「沒有下一隻了，回練功圖」')
        c3 = mock_char('A2', 'c3')
        check(c3['map'] == homes['c3'] and c3['auto'], '回到原本的練功圖並在掛機')
        maps_visited = [x.get('map') for x in (c3.get('presetLog') or [])]
        hub_json('POST', '/api/jobs/clear', {})

        print('3. 隊伍一起連續打：同隊拿到同一個下一隻')
        reset_bosses()
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'partyMode': 'together', 'chain': True, 'charMobs': {'c3': ['*']}, **BASE}})
        await asyncio.sleep(3)
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        check(len(js) == 2 and len({j['batches'][0]['boss']['mob'] for j in js}) == 1, f'整隊 2 隻一起出發、同一隻王（{len(js)}）')
        await wait(done_all, 300, 2)
        js = boss_jobs()
        check(all(j['status'] == 'done' for j in js) and all(any('接著去' in l['msg'] for l in j['log']) for j in js), '兩隻都連續打到第二隻')
        check(len({j['batches'][0]['boss']['mob'] for j in js}) == 1, '第二隻也是同一隻')
        blog = [l['msg'] for l in hub_json('GET', '/api/boss')['log']]
        check(any('連續打：隊伍' in m and '一起' in m for m in blog), '紀錄：連續打：隊伍 … 一起接著去')
        check(mock_char('A2', 'c3')['map'] == homes['c3'] and mock_char('A3', 'c4')['map'] == homes['c4'], '兩隻都回到各自的練功圖')
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
