"""副本每隻角色的攻擊紀錄（查傷害 0 的原因）：回報者從 sync 回應的 summary.events 收全隊的攻擊事件（eventId 去重）→ /api/raid/hits；
GET /api/raid 帶每隻的出手次數／未命中率；打完併進戰後紀錄（rows[].hits、diag），失敗原因分辨「沒出手／全未命中／有命中但扣血 0」；面板戰況表、戰後紀錄；重開中控還在"""
import asyncio, json, os, signal, subprocess, sys, time
os.environ.update({'MOCK_RAID_PREP_MS': '3000', 'MOCK_RAID_FEE': '100000', 'MOCK_RAID_NO_MAGE': '1', 'MOCK_MORE_ACCTS': '1',
                   'MOCK_RAID_DPS': '0.002', 'MOCK_RAID_REGEN': '0.001', 'MOCK_RAID_ORB_MS': '600000'})  # 王打不死、不出黑球，由測試結束
from harness import Env, hub_json, http, HUB, MOCK, HUB_DIR, wait_url

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def raid(q=''): return hub_json('GET', '/api/raid' + q)
def hist(): return hub_json('GET', '/api/raid/history')['list']
def mock(q): return json.loads(http('GET', MOCK + '/__mock/raid' + q)[1])
def live(cid): return (raid()['live'].get(cid) or {})
async def wait(fn, sec=40, step=0.5):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception:
            pass
        await asyncio.sleep(step)
    return None
def act(targets): return hub_json('POST', '/api/raid/act', {'targets': targets})
MEM = ['c3', 'c4', 'c5']

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3', 'A4'])
        await env.wait_chars(4)
        print('0. 組隊開打：隊長 c1；c3 全部未命中、c4 不出手、c5 有命中但扣血 0')
        mock('?miss=c3&idle=c4&noeff=c5')
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': MEM}})
        act([{'charId': 'c1', 'cmd': {'type': 'raidCreate', 'raid': 'papulatus'}, 'label': '建立'}])
        team = await wait(lambda: (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        act([{'charId': c, 'cmd': {'type': 'raidJoin', 'code': team['code']}, 'label': '加入'} for c in MEM])
        await wait(lambda: all((raid()['views'].get(c) or {}).get('view', {}).get('team') for c in MEM), 40)
        act([{'charId': c, 'cmd': {'type': 'raidReady', 'ready': True}, 'label': '準備'} for c in MEM])
        await wait(lambda: all(m['ready'] or m['leader'] for m in ((raid()['views'].get('c5') or {}).get('view', {}).get('team') or {}).get('members', [{'ready': False, 'leader': False}])), 40)
        act([{'charId': 'c1', 'cmd': {'type': 'raidStart', 'memberIds': ['c1'] + MEM}, 'label': '開始'}])
        b = await wait(lambda: live('c1').get('battle'), 40)
        check(b and b['raid'] == 'papulatus', '開打了')
        code = b['code']

        print('1. 戰鬥中：GET /api/raid 的 hits')
        H = await wait(lambda: (lambda h: h if h and h['code'] == code and (h['chars'].get('c1') or {}).get('atk', 0) >= 8 and (h['chars'].get('c3') or {}).get('atk', 0) >= 5 else None)(raid()['hits']), 50)
        check(H, f"收到這場的攻擊紀錄（{H and {k: v['atk'] for k, v in H['chars'].items()}}）")
        if H:
            C = H['chars']; c1, c3, c5 = C.get('c1') or {}, C.get('c3') or {}, C.get('c5') or {}
            check(c1.get('lines') == 3 * c1.get('atk', 0) and c1.get('miss') == 0 and c1.get('dmg', 0) > 0 and c1.get('eff', 0) > 0 and c1.get('missPct') == 0, f"隊長：出手 {c1.get('atk')} 次、{c1.get('lines')} 段、未命中 0、有扣血")
            check(len(c1.get('skills') or []) >= 2 and any('持續' in s['name'] for s in c1['skills']) and c1.get('dot', 0) > 0, f"隊長：技能分開算（含持續傷害）（{[(s['name'], s['n']) for s in c1.get('skills') or []]}）")
            check(c1.get('boss', {}).get('n', 0) > 0 and c1.get('orb', {}).get('n') == 0 and c1.get('first') is not None and c1['last'] >= c1['first'], f"隊長：打王 {c1.get('boss')}、第一次／最後一次出手 {c1.get('first')}～{c1.get('last')} 秒")
            check(c3.get('miss') == c3.get('lines') and c3.get('lines', 0) > 0 and c3.get('dmg') == 0 and c3.get('missPct') == 100, f"c3：出手 {c3.get('atk')} 次全未命中（{c3.get('missPct')}%）")
            check('c4' not in C, 'c4：沒有攻擊事件（沒出手）')
            check(c5.get('dmg', 0) > 0 and c5.get('eff') == 0 and c5.get('zeroEff') == c5.get('atk'), f"c5：有命中但扣血 0（扣血 0 {c5.get('zeroEff')}／{c5.get('atk')} 次）")
            check('c2' not in C, '同帳號沒進副本的 c2 在別張地圖打怪不算')
            hn = raid()['hits']['chars']
            mt = next(t for t in mock('')['teams'] if t['code'] == code)['battle']['hitN']
            check(all(0 <= mt[c] - hn[c]['atk'] <= 8 for c in ['c1', 'c3', 'c5']), f"eventId 去重：中控的出手次數跟遊戲一致（遊戲 {mt}、中控 {({c: hn[c]['atk'] for c in hn})}）")

        print('2. 面板戰況表：出手／未命中率欄')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1100}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(2500)
        tb = d.locator('#rdBattle table.rd-mem')
        hd = await tb.locator('tr').first.inner_text() if await tb.count() else ''
        check('出手／未命中率' in hd, '戰況表有「出手／未命中率」欄')
        row = lambda n: tb.locator('tr', has_text=n).first
        t3, t4, t5, t1 = [await row(n).inner_text() if await tb.count() else '' for n in ['弓箭分身', '倉庫分身', '第四隻', '本尊劍士']]
        check('100%' in t3, f'c3 未命中率 100%（{t3!r}）')
        check('沒出手' in t4, f'c4 顯示沒出手（{t4!r}）')
        check('扣血 0' in t5, f'c5 顯示扣血 0（{t5!r}）')
        check('／0%' in t1, f'隊長未命中 0%（{t1!r}）')

        print('3. 打完：戰後紀錄每隻有 hits、傷害 0 的有診斷')
        mock('?end=fail')
        h = await wait(lambda: (lambda l: l[0] if l and l[0]['code'] == code and l[0].get('hitsN') else None)(hist()), 40)
        check(h, '存了這場（含攻擊紀錄）')
        if h:
            await asyncio.sleep(4)  # 最後一批攻擊紀錄晚到也會更新那一筆
            h = hist()[0]
            rows = {r['name']: r for r in h['rows']}
            check(rows['本尊劍士']['damage'] > 0 and rows['本尊劍士']['hits']['atk'] > 0 and not rows['本尊劍士']['diag'], '隊長：有傷害、有出手紀錄、不用診斷')
            check('全未命中' in rows['弓箭分身']['diag'] and rows['弓箭分身']['damage'] == 0, f"c3 診斷：{rows['弓箭分身']['diag']}")
            check(rows['倉庫分身']['diag'] == '沒出手' and rows['倉庫分身']['hits'] is None, f"c4 診斷：{rows['倉庫分身']['diag']}")
            check('有命中但扣血 0' in rows['第四隻']['diag'], f"c5 診斷：{rows['第四隻']['diag']}")
            why = '\n'.join(h['reasons']); print('    失敗原因：' + ' ／ '.join(h['reasons']))
            check('3 隻傷害 0：' in why and '倉庫分身沒出手' in why and '全未命中（命中不足？）' in why and '第四隻有命中但扣血 0' in why, '失敗原因分辨三種情況')

        print('4. 面板戰後紀錄：出手、未命中率、主要技能、診斷文字')
        await d.wait_for_timeout(2500)
        await d.locator('#rdHist tr.rh-row').first.locator('td').nth(2).click(); await d.wait_for_timeout(600)
        det = d.locator('#rdHist tr.rh-det')
        dt = await det.inner_text() if await det.count() else ''
        check('出手' in dt and '未命中率' in dt and '主要技能' in dt, '展開的表格有出手、未命中率、主要技能')
        check('全未命中' in dt and '沒出手' in dt and '扣血 0' in dt, '傷害 0 的角色顯示診斷文字')
        d1 = await det.locator('table.rh-mem tr', has_text='本尊劍士').inner_text() if await det.count() else ''
        check('×' in d1 and '0%' in d1, f'隊長列：主要技能 ×次數、未命中 0%（{d1!r}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

        print('5. 中控重開：攻擊紀錄還在戰後紀錄裡')
        await asyncio.sleep(2)
        hub = env.procs[1]; hub.send_signal(signal.SIGKILL); hub.wait()
        newhub = subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787', 'SZG_QUIZ_SHARE_URL': 'http://127.0.0.1:9/', 'SZG_LOBBY_URL': 'http://127.0.0.1:9'},
                                  stdout=open('/tmp/hub2.log', 'w'), stderr=subprocess.STDOUT)
        env.procs[1] = newhub
        wait_url(HUB + '/api/settings')
        hs = hist(); rows = {r['name']: r for r in hs[0]['rows']} if hs else {}
        check(hs and hs[0]['code'] == code and rows['本尊劍士']['hits']['atk'] > 0 and rows['倉庫分身']['diag'] == '沒出手' and any('沒出手' in x for x in hs[0]['reasons']), '重開後 hits、診斷、原因都還在')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
