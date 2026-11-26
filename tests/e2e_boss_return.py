"""打完王回原本的地圖（v0.69.2）
1. 練功圖本身也有野王（海岸草叢3 有紅寶王）：以前不會記成原本的地圖、打完留在王那邊；現在會回到海岸草叢3
2. 保險：打王工作結束後角色還停在王的地圖（回程失敗、分頁重新整理…）→ 約 1.5 分鐘後自動帶回原本的地圖並開始掛機"""
import asyncio, os, sys, time, json
os.environ['MOCK_BOSS_DPS'] = '600'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'
from harness import Env, hub_json, http, http_raw, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)
def mock_char(acct, cid): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]
def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)
async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None
def boss_jobs(): return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']

async def main():
    async with Env() as env:
        TRAIN, BOSSMAP = 'gms104000400', 'gms100000005'   # 海岸草叢3（有紅寶王）、蘑菇王棲息地
        game('A2', {'type': 'map', 'map': TRAIN, 'characterId': 'c3'}); game('A2', {'type': 'start', 'characterId': 'c3'})
        http('GET', MOCK + '/__mock/boss?acct=A2&char=c3&mob=mBoss1&cd=3600000')   # 紅寶王冷卻中，不相干
        http('GET', MOCK + '/__mock/boss?acct=A2&char=c3&mob=mBoss2&cd=0&hp=3000')  # 蘑菇王剩一點血，幾秒打死
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c3': ['mBoss2']}, 'estMax': 100000, 'chain': True}})
        await env.open_accounts(['A2'])
        await env.wait_chars(1)
        await wait(lambda: (lambda c: c if c and c.get('at') and c.get('map') == TRAIN else None)(next((c for c in hub_json('GET', '/api/boss')['chars'] if c['charId'] == 'c3'), None)), 60)
        print('1. 練功圖本身有野王：打完回到練功圖')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'charMobs': {'c3': ['mBoss2']}, 'estMax': 100000, 'chain': True}})
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        check(len(js) == 1 and js[0]['batches'][0]['boss']['back'] == TRAIN, f"工作記得原本的地圖是海岸草叢3（{js and js[0]['batches'][0]['boss'].get('back')}）")
        done = await wait(lambda: next((j for j in boss_jobs() if j['status'] in ('done', 'failed')), None), 90)
        check(done and done['status'] == 'done', '工作完成')
        c = mock_char('A2', 'c3')
        check(c['map'] == TRAIN and c['auto'], f"回到海岸草叢3 並在掛機（{c['map']}）")
        check(any('已回到 海岸草叢3' in l['msg'] for l in hub_json('GET', '/api/boss')['log']), '紀錄：已回到 海岸草叢3')

        print('2. 保險：打完王還停在王的地圖 → 自動帶回')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'off', 'charMobs': {'c3': ['mBoss2']}, 'estMax': 100000}})
        game('A2', {'type': 'map', 'map': BOSSMAP, 'characterId': 'c3'})   # 模擬回程失敗、留在蘑菇王棲息地
        back = await wait(lambda: (lambda c: c if c['map'] == TRAIN and c['auto'] else None)(mock_char('A2', 'c3')), 180, 3)
        check(back, '約 1.5 分鐘後自動帶回海岸草叢3、開始掛機')
        check(any('自動帶回' in l['msg'] for l in hub_json('GET', '/api/boss')['log']), '紀錄：打完王還停在…自動帶回')
        n = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party'])
        await asyncio.sleep(40)
        check(len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party']) == n, '只帶回一次，不會重複')
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
