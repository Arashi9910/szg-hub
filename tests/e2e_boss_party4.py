"""輪流打野王：4 人隊（真實大小的隊伍資料：40 則聊天＋隊員一堆欄位）只勾一隻，整隊 4 隻一起出發（v0.54.1 修正：以前隊伍資料超過 8000 字被整包丟掉，只有勾的那隻去）"""
import asyncio, os, sys, time, json
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'
os.environ['MOCK_PARTY'] = 'c3,c4,c5,c6'
os.environ['MOCK_PARTY_MSGS'] = '40'
os.environ['MOCK_MORE_ACCTS'] = '1'
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
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c3': ['mBoss1']}, 'estMax': 15, 'visitMax': 3}})
        await env.open_accounts(['A2', 'A3', 'A4', 'A5'])
        await env.wait_chars(4)
        d = hub_json('GET', '/api/data')
        sizes = {cid: len(json.dumps(s.get('party') or {})) for cid, s in d['chars'].items()}
        check(all(((d['chars'][c].get('party') or {}).get('party') or {}).get('code') for c in ('c3', 'c4', 'c5', 'c6')), f'4 隻的快照都有隊伍代碼（大小 {sizes}）')
        s = await wait(lambda: (lambda x: x if all(x.get(c, {}).get('party') for c in ('c3', 'c4', 'c5', 'c6')) and x['c3'].get('at') else None)(summ()), 60)
        check(s and len(s['c3']['party']['ids']) == 4, '中控認得 4 人同一隊' + ('' if s else '（等不到）'))
        b = hub_json('POST', '/api/boss/run-now')
        msg = next((l['msg'] for l in b['log'] if '試跑' in l['msg']), '')
        check('隊伍' in msg and all(n in msg for n in ('弓箭分身', '倉庫分身', '第四隻', '第五隻')), f'試跑：{msg}')
        cfg = hub_json('GET', '/api/boss')['cfg']
        hub_json('POST', '/api/settings', {'boss': {**cfg, 'mode': 'auto'}})
        hub_json('POST', '/api/boss/run-now')
        js = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']
        check(len(js) == 4 and len({j['batches'][0]['boss']['mob'] for j in js}) == 1, f'自動：4 個打王工作、同一隻王（{len(js)}）')
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
