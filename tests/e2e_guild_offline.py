"""公倉自動存入遇到離線掛機（v0.74.4）：在離線的角色先按「繼續」、回到線上回報新資料後才存；在線的照常存；試跑不叫醒"""
import asyncio, json, os, sys, time
os.environ.update({'SZG_GUILD_TICK_MS': '3000', 'SZG_GUILD_WAKE_WAIT_MS': '3000'})
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def data(): return hub_json('GET', '/api/data')
def glog(): return [l['msg'] for l in hub_json('GET', '/api/guild')['log']]
def deps(cid): return [j for j in data()['jobs'] if j['kind'] == 'guildDeposit' and j['fromCharId'] == cid]
async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None
OFFLINE = """(() => { if (document.getElementById('idleOffline')) return; const d = document.createElement('div'); d.id = 'idleOffline'; d.textContent = '已離線掛機';
  const b = document.createElement('button'); b.id = 'idleOfflineResume'; b.textContent = '繼續'; b.onclick = () => { window.__resumed = (window.__resumed || 0) + 1; d.remove(); };
  d.appendChild(b); document.body.appendChild(d); })()"""

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages:
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2)
        for a, c in [('A1', 'c1'), ('A2', 'c3')]: http('GET', MOCK + f'/__mock/additem?acct={a}&char={c}&key=i2040805&qty=3')
        await asyncio.sleep(8)
        hub_json('POST', '/api/settings', {'guildDep': {'names': [], 'cats': ['卷軸'], 'conds': [], 'keep': 0}, 'guildAuto': {'mode': 'preview', 'everyMin': 30}})
        print('1. 本尊劍士進入離線掛機')
        await pages[0].evaluate(OFFLINE)
        check(await wait(lambda: data()['chars']['c1'].get('idleOffline')), '中控知道本尊劍士在離線掛機')

        print('2. 試跑：不叫醒，只記錄')
        hub_json('POST', '/api/guild/auto-run', {})
        await asyncio.sleep(2)
        check(any('試跑' in m and '離線掛機' in m for m in glog()), '試跑紀錄寫出離線的角色')
        check(await pages[0].evaluate("!!document.getElementById('idleOffline')"), '試跑不會按「繼續」')

        print('3. 自動存入：在線的照存、離線的先叫醒再存')
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'deposit', 'everyMin': 30}})
        hub_json('POST', '/api/guild/auto-run', {})
        await asyncio.sleep(1)
        check(not deps('c1'), '本尊劍士（離線）先不存')
        check(any('先按「繼續」' in m for m in glog()), '紀錄寫「先按繼續，回到線上後再存」')
        resumed = None
        for _ in range(30):
            resumed = await pages[0].evaluate("window.__resumed || 0")
            if resumed: break
            await asyncio.sleep(1)
        check(resumed == 1, '本尊劍士的分頁自動按了「繼續」')
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] == 'done' else None)(deps('c1')), 60)
        check(j is not None, '回到線上、回報新資料後自動存入完成')
        check(any('離線叫醒後' in m for m in glog()), '紀錄寫「離線叫醒後自動存入」')
        idl = [x for x in data().get('idleLog', []) if '公倉自動存入前' in (x.get('msg') or '')]
        check(idl, '掛機紀錄寫「公倉自動存入前，已按繼續」')
        print('4. 已經叫醒過、又離線：下一次到期才會再叫醒（不會一直按）')
        await pages[0].evaluate(OFFLINE)
        await asyncio.sleep(8)
        check(await pages[0].evaluate("window.__resumed || 0") == 1, '還沒到下一次自動存入，不會再按「繼續」')
        print('5. 保持在線（全部分頁）：一進入離線就自動按「繼續」，不寫掛機紀錄')
        p = hub_json('GET', '/api/idle-policy')['policy']
        check(p.get('keepOnline') == 'bg', '預設：只有背景執行的分頁保持在線')
        hub_json('POST', '/api/settings', {'idlePolicy': {**p, 'keepOnline': 'all'}})
        n0 = len(data().get('idleLog', []))
        r = None
        for _ in range(50):
            r = await pages[0].evaluate("window.__resumed || 0")
            if r >= 2: break
            await asyncio.sleep(1)
        check(r == 2 and not await pages[0].evaluate("!!document.getElementById('idleOffline')"), '本尊劍士一進入離線就被按「繼續」')
        check(len(data().get('idleLog', [])) == n0, '保持在線不寫掛機紀錄（不會洗版）')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
