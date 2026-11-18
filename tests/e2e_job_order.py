"""同帳號：排在前面的工作要另一隻角色時，目前角色自己的背包工作先做，不會卡住"""
import asyncio, sys, time
from harness import Env, hub_json

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

def job(cid):
    j = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': cid, 'batches': [{'items': [{'key': 'i2000000', 'name': '紅色藥水', 'uids': ['nope']}], 'gear': []}]})['jobs'][0]
    hub_json('POST', f"/api/jobs/{j['id']}/approve"); return j['id']

async def main():
    async with Env() as env:
        await env.open_accounts(['A1']); await env.wait_chars(1)
        # 先切到 c2 再切回 c1，讓兩隻都有快照
        for cid in ('c2', 'c1'):
            hub_json('POST', '/api/idle', {'targets': [{'charId': cid, 'action': 'switch'}]})
            end = time.time() + 40
            while time.time() < end:
                s = hub_json('GET', '/api/data')['chars'].get(cid)
                if s and s.get('activeCharId') == cid and time.time() * 1000 - s['receivedAt'] < 4000: break
                await asyncio.sleep(1)
        await asyncio.sleep(3)
        # c2 是同帳號的另一隻（不是目前角色），先排它
        j2 = job('c2'); await asyncio.sleep(0.2); j1 = job('c1')
        end = time.time() + 30; st = {}
        while time.time() < end:
            st = {j['id']: j for j in hub_json('GET', '/api/data')['jobs']}
            if st[j1]['status'] == 'done': break
            await asyncio.sleep(1)
        check(st[j1]['status'] == 'done', f"目前角色（本尊劍士）的工作先完成：{st[j1]['status']}")
        for _ in range(15):
            st = {j['id']: j for j in hub_json('GET', '/api/data')['jobs']}
            if '等待' in (st[j2].get('lastMsg') or ''): break
            await asyncio.sleep(1)
        check(st[j2]['status'] in ('approved', 'running') and '等待' in (st[j2].get('lastMsg') or ''), f"另一隻的工作繼續等切換：{st[j2]['status']} {st[j2].get('lastMsg')}")
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
