"""腳本太舊的分頁不會拿到新種類的工作（排隊等、不會失敗）；換上新腳本後照常執行"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

def push(ver):
    snap = {'v': 3, 'at': int(time.time() * 1000), 'scriptVersion': ver, 'accountId': 'acc-x', 'accountChars': [{'id': 'cx', 'name': '舊腳本分身', 'lv': 30, 'job': 'thief'}],
            'playerCode': 'ABCDEFABCDEF', 'activeCharId': 'cx', 'char': {'id': 'cx', 'name': '舊腳本分身', 'lv': 30, 'money': 1000000, 'map': 'gms100010000'}, 'gear': [], 'items': []}
    return http('POST', HUB + '/api/push', snap)

async def main():
    async with Env() as env:
        cur = hub_json('GET', '/api/data')['scriptVersion']
        push('0.25.2')
        job = hub_json('POST', '/api/jobs', {'kind': 'guildSell', 'fromCharId': 'cx', 'batches': [{'items': [], 'gear': [{'uid': 'g1', 'name': '測試甲'}]}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{job['id']}/approve")
        r = hub_json('GET', '/api/agent?code=ABCDEFABCDEF&charId=cx')
        j = [x for x in hub_json('GET', '/api/data')['jobs'] if x['id'] == job['id']][0]
        check(r['job'] is None and r.get('needUpdate') == '0.28.0', '舊腳本（v0.25.2）拿不到「公倉賣出」工作，回覆要更新')
        check(j['status'] == 'approved' and '等待' in j['lastMsg'] and 'v0.25.2' in j['lastMsg'], '工作沒有失敗，顯示等待換新腳本：' + j['lastMsg'][:60])
        push(cur)
        r = hub_json('GET', '/api/agent?code=ABCDEFABCDEF&charId=cx')
        check(r['job'] and r['job']['id'] == job['id'], f'換上新腳本（v{cur}）後就拿到工作')
        job2 = hub_json('POST', '/api/jobs', {'kind': 'sell', 'fromCharId': 'cx', 'batches': [{'items': [{'key': 'x', 'name': 'x', 'uids': ['s1']}], 'gear': []}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{job['id']}/cancel"); hub_json('POST', f"/api/jobs/{job2['id']}/approve")
        push('0.25.2')
        r = hub_json('GET', '/api/agent?code=ABCDEFABCDEF&charId=cx')
        check(r['job'] and r['job']['id'] == job2['id'], '舊種類的工作（賣出）舊腳本照常拿得到')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
