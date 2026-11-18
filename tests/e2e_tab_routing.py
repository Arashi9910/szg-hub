"""伺服器的分頁派工（不開瀏覽器，直接模擬分頁輪詢）：同帳號兩個分頁時，工作交給對的那隻角色的分頁；交易只由對的分頁做、雙方分頁準備好才開始"""
import sys, time
from harness import Env, hub_json, http, HUB
import asyncio, json, urllib.parse

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

def push(cid, name, acc, code, sibs):
    hub_json('POST', '/api/push', {'v': 3, 'at': int(time.time() * 1000), 'accountId': acc, 'playerCode': code, 'scriptVersion': '0.6.3',
        'accountChars': [{'id': i, 'name': n, 'lv': 50} for i, n in sibs], 'activeCharId': cid,
        'char': {'id': cid, 'name': name, 'lv': 50, 'job': 'fighter', 'money': 1000}, 'gear': [], 'items': []})

def poll(code, cid, peek=False):
    q = urllib.parse.urlencode({'code': code, 'charId': cid, 'page': 'p-' + cid, 'hidden': 0, 'off': 0, **({'peek': 1} if peek else {})})
    return hub_json('GET', '/api/agent?' + q)

async def main():
    async with Env() as env:
        X, Y = 'AAAAAAAAAAAA', 'BBBBBBBBBBBB'
        push('xa', '甲A', 'accX', X, [('xa', '甲A'), ('xb', '甲B')])
        push('xb', '甲B', 'accX', X, [('xa', '甲A'), ('xb', '甲B')])
        push('ya', '乙A', 'accY', Y, [('ya', '乙A')])
        print('1. 背包工作：交給那隻角色自己的分頁')
        poll(X, 'xa'); poll(X, 'xb'); poll(Y, 'ya')
        tabs = hub_json('GET', '/api/data')['tabs']
        check(set(tabs) >= {'xa', 'xb', 'ya'} and tabs['xa']['code'] == X, f'/api/data 列出有分頁的角色：{sorted(tabs)}')
        jb = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': 'xb', 'batches': [{'items': [{'key': 'k', 'name': 'k', 'uids': ['u']}], 'gear': []}]})['jobs'][0]
        ja = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': 'xa', 'batches': [{'items': [{'key': 'k', 'name': 'k', 'uids': ['u']}], 'gear': []}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{jb['id']}/approve"); hub_json('POST', f"/api/jobs/{ja['id']}/approve")
        ra, rb = poll(X, 'xa'), poll(X, 'xb')
        check(ra['job'] and ra['job']['id'] == ja['id'], '甲A 的分頁拿到甲A 的工作')
        check(rb['job'] and rb['job']['id'] == jb['id'], '甲B 的分頁同時拿到甲B 的工作（兩個分頁各做各的）')
        hub_json('POST', '/api/agent/report', {'jobId': ja['id'], 'batchIndex': 0, 'event': 'batchDone'})
        hub_json('POST', '/api/agent/report', {'jobId': jb['id'], 'batchIndex': 0, 'event': 'batchDone'})

        print('2. 掛機指令：有分頁的交給自己，切換有分頁的角色會被擋下')
        r = hub_json('POST', '/api/idle', {'targets': [{'charId': 'xb', 'action': 'stop'}, {'charId': 'xa', 'action': 'stop'}]})
        own = {j['needChar'] for j in r['jobs']}
        check(len(r['jobs']) == 2 and own == {'xa', 'xb'}, f'兩隻各自一個指令，交給自己的分頁：{own}')
        ga, gb = poll(X, 'xa')['job'], poll(X, 'xb')['job']
        check(ga and gb and ga['needChar'] == 'xa' and gb['needChar'] == 'xb', '各自的分頁拿到自己的掛機指令')
        for j in r['jobs']: hub_json('POST', '/api/agent/report', {'jobId': j['id'], 'batchIndex': 0, 'event': 'batchDone'})
        s, t = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'xb', 'action': 'switch'}]})
        check(s != 200 and '已經有自己的分頁' in t, '切換到已經有分頁的角色：擋下並說明')

        print('3. 交易：甲B → 乙A，只交給甲B 的分頁')
        tj = hub_json('POST', '/api/jobs', {'kind': 'give', 'fromCharId': 'xb', 'toCharId': 'ya', 'batches': [{'items': [], 'gear': [], 'money': 100}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{tj['id']}/approve")
        ra, rb, ry = poll(X, 'xa'), poll(X, 'xb'), poll(Y, 'ya')
        check(not ra['job'], '甲A 的分頁不會拿到（避免同帳號兩個分頁同時交易）')
        check(rb['job'] and rb['job']['id'] == tj['id'] and rb['role'] == 'giver', '甲B 的分頁拿到，角色是送出方')
        check(ry['job'] and ry['role'] == 'receiver' and ry['peerReady'], '乙A 收貨方：雙方都準備好')
        rb = poll(X, 'xb')
        check(rb['peerReady'], '送出方也看到對方準備好')
        hub_json('POST', f"/api/jobs/{tj['id']}/cancel")

        print('4. 甲B 沒有分頁時：交給甲A 的分頁顯示等待，甲A 自己的工作優先')
        http('POST', HUB + '/api/agent/leave', {'code': X, 'charId': 'xb'})
        check('xb' not in hub_json('GET', '/api/data')['tabs'], '分頁離開（切換角色）後馬上不算有分頁')
        jb = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': 'xb', 'batches': [{'items': [{'key': 'k', 'name': 'k', 'uids': ['u']}], 'gear': []}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{jb['id']}/approve"); time.sleep(0.05)
        ja = hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': 'xa', 'batches': [{'items': [{'key': 'k', 'name': 'k', 'uids': ['u']}], 'gear': []}]})['jobs'][0]
        hub_json('POST', f"/api/jobs/{ja['id']}/approve")
        ra = poll(X, 'xa')
        check(ra['job'] and ra['job']['id'] == ja['id'], '甲A 先做自己的')
        hub_json('POST', '/api/agent/report', {'jobId': ja['id'], 'batchIndex': 0, 'event': 'batchDone'})
        ra = poll(X, 'xa')
        check(ra['job'] and ra['job']['id'] == jb['id'], '再拿到甲B 的工作（腳本會顯示「等待甲B 的遊戲分頁」）')
        rb = poll(X, 'xb')
        check(rb['job'] and rb['job']['id'] == jb['id'], '甲B 的分頁一開，工作就改交給它')
        check(not poll(X, 'xa')['job'], '甲A 不再拿到甲B 的工作')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
