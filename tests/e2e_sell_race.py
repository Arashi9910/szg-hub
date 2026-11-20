"""賣出時背包剛好在變動：舊的報價單還留在角色身上、堆疊被重排（uid 全換）→ 仍然只賣選到的東西，不會拿舊報價單而失敗"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, http_raw, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def main():
    async with Env() as env:
        await env.open_accounts(['A1'])
        d = await env.wait_chars(1)
        c = mock_char('A1', 'c1')
        print('1. 角色身上留著一張舊的大報價單（例如遊戲裡按過一鍵全賣但沒賣）')
        allc = [s['uid'] for s in c['inventoryStacks'] if s['key'].startswith('i2')]
        game('A1', {'type': 'inventoryQuote', 'category': 'consume', 'ids': allc, 'characterId': 'c1'})
        old = mock_char('A1', 'c1').get('inventoryQuote') or {}
        check(len(old.get('rows', [])) == len(allc) and len(allc) > 3, f"舊報價單 {len(old.get('rows', []))} 項")
        print('2. 從中控賣「手套攻擊卷軸 60%」，送出前堆疊被重排（uid 全換）')
        stale = [s['uid'] for s in c['inventoryStacks'] if s['key'] == 'i2040801']
        http('GET', MOCK + '/__mock/restack?acct=A1&char=c1')
        stale = stale + [s['uid'] for s in mock_char('A1', 'c1')['inventoryStacks'] if s['key'] == 'i2040801']  # 一部分舊、一部分新的 uid
        before = mock_char('A1', 'c1')
        keep = {k: v for k, v in before['inventory'].items() if k != 'i2040801'}
        r = hub_json('POST', '/api/jobs', {'kind': 'sell', 'fromCharId': 'c1', 'toCharId': 'c1', 'estimate': 0,
            'batches': [{'items': [{'key': 'i2040801', 'name': '手套攻擊卷軸 60%', 'cat': 'consume', 'qty': before['inventory']['i2040801'], 'uids': stale}], 'gear': [], 'money': 0}]})
        hub_json('POST', '/api/jobs/approve-all', {})
        job = None
        for _ in range(60):
            job = next((j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'sell'), None)
            if job and job['status'] in ('done', 'failed'): break
            await asyncio.sleep(1)
        check(job and job['status'] == 'done', '工作完成' + ('' if job and job['status'] == 'done' else f"：{job and job['lastMsg']}"))
        after = mock_char('A1', 'c1')
        check(after['inventory'].get('i2040801', 0) == 0, '卷軸賣掉了')
        check(all(after['inventory'].get(k, 0) == v for k, v in keep.items()), '其他道具一個都沒少（沒有用到舊報價單）')
        check(after['money'] > before['money'], f"楓幣增加 {after['money'] - before['money']:,}")
    if not ok: print('\n'.join(env.logs[-20:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
