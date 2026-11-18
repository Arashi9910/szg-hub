"""切換角色：遊戲同步會把 mapleCharacter 寫回畫面上的角色，切換後頁面要穩定換成新角色（模擬遊戲每 0.4 秒同步一次，製造時間差）"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

def active():
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts']['A1']['active']

async def switch_to(cid, name):
    hub_json('POST', '/api/idle', {'targets': [{'charId': cid, 'action': 'switch'}]})
    end = time.time() + 40
    while time.time() < end:
        s = hub_json('GET', '/api/data')['chars'].get(cid)
        if s and time.time() * 1000 - s['receivedAt'] < 4000 and active() == cid:
            break
        await asyncio.sleep(1)
    await asyncio.sleep(8)  # 再觀察一陣子，確認沒有被改回去
    s = hub_json('GET', '/api/data')['chars'].get(cid)
    stable = active() == cid and s and time.time() * 1000 - s['receivedAt'] < 12000
    check(stable, f'切換到 {name} 後穩定停在 {name}（遊戲目前角色：{active()}）')

async def main():
    async with Env(sync_ms=400) as env:
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        for i in range(3):
            await switch_to('c2', '本尊小號')
            await switch_to('c1', '本尊劍士')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
