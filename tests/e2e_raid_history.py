"""副本戰後紀錄與分析：每場打完（收到 raidReport）存一筆到 db.raidHistory（重開還在、同一場只存一次）；
分析黑球每波有沒有清完、封印、淨輸出／回血、每隻 MP 最低／倒下時間，規則式的失敗原因；面板列表展開、兩場比較、刪除"""
import asyncio, json, os, signal, subprocess, sys, time
os.environ.update({'MOCK_RAID_PREP_MS': '3000', 'MOCK_RAID_FEE': '100000', 'MOCK_RAID_NO_MAGE': '1',
                   'MOCK_RAID_DPS': '0.006', 'MOCK_RAID_REGEN': '0.001',              # 2M 血：總輸出 1.2 萬／秒、回血 2000／秒（20 分鐘打不完的速度要靠 regen 調）
                   'MOCK_RAID_ORB_MS': '600000', 'MOCK_RAID_ORB_LIFE_MS': '6000',      # 黑球由測試觸發；6 秒後自己消失（清不完）
                   'MOCK_RAID_ORB_KILL': '0.5', 'MOCK_RAID_SEAL_MS': '8000', 'MOCK_RAID_ZERO': 'c4'})
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

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        print('0. 組隊開打：拉圖斯，隊長 c1，隊員 c3、c4（c4 模擬 0 傷害）')
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4']}})
        check(hist() == [], '一開始沒有紀錄')
        act([{'charId': 'c1', 'cmd': {'type': 'raidCreate', 'raid': 'papulatus'}, 'label': '建立'}])
        team = await wait(lambda: (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        act([{'charId': c, 'cmd': {'type': 'raidJoin', 'code': team['code']}, 'label': '加入'} for c in ['c3', 'c4']])
        await wait(lambda: all((raid()['views'].get(c) or {}).get('view', {}).get('team') for c in ['c3', 'c4']), 40)
        act([{'charId': c, 'cmd': {'type': 'raidReady', 'ready': True}, 'label': '準備'} for c in ['c3', 'c4']])
        await wait(lambda: all(m['ready'] or m['leader'] for m in ((raid()['views'].get('c4') or {}).get('view', {}).get('team') or {}).get('members', [{'ready': False, 'leader': False}])), 40)
        act([{'charId': 'c1', 'cmd': {'type': 'raidStart', 'memberIds': ['c1', 'c3', 'c4']}, 'label': '開始'}])
        b = await wait(lambda: live('c1').get('battle'), 40)
        check(b and b['raid'] == 'papulatus', '開打了')
        code = b['code']
        await wait(lambda: (lambda x: x if x and len(x['points']) >= 8 else None)(raid()['series']), 30)

        mock('?regen=0.006')  # 回血 1.2 萬／秒 ≥ 輸出：平均淨輸出變成負的
        print('1. 戰鬥中：弓箭分身 MP 見底、黑球沒清完 → 全隊封印 → 倒下 2 隻')
        mock('?mp=c3:0')
        await wait(lambda: (live('c3').get('me') or {}).get('mp') == 0, 15)
        mock('?orbs=now')
        sealed = await wait(lambda: all('seal' in ((live(c).get('me') or {}).get('diseases') or {}) for c in ['c1', 'c3', 'c4']), 25)
        check(sealed, '黑球沒清完 → 全隊封印')
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3'); http('GET', MOCK + '/__mock/die?acct=A3&char=c4')
        dead = await wait(lambda: all((live(c).get('me') or {}).get('hp') == 0 for c in ['c3', 'c4']), 15)
        check(dead, '弓箭分身、倉庫分身倒下（中控有收到 hp 0）')
        await asyncio.sleep(2)
        check(hist() == [], '還沒打完不存紀錄')

        print('2. 打完：存一筆歷史＋分析')
        mock('?end=fail')
        hs = await wait(lambda: (lambda l: l if l else None)(hist()), 40)
        h = hs and hs[0]
        check(h and h['code'] == code and h['result'] == 'fail' and h['raid'] == 'papulatus' and len(h['rows']) == 3, f"存了這場（{h and (h['code'], h['result'], h['raid'])}）")
        if h:
            rows = {r['name']: r for r in h['rows']}
            check(h['rows'][0]['name'] == '本尊劍士' and h['rows'][0]['damage'] >= h['rows'][1]['damage'], '每隻照傷害排序（隊長第一）')
            check({rows[n]['charId'] for n in rows} == {'c1', 'c3', 'c4'}, f"名字對上角色 id（{[(n, rows[n]['charId']) for n in rows]}）")
            check(rows['倉庫分身']['damage'] == 0 and rows['倉庫分身']['pct'] == 0 and abs(sum(r['pct'] for r in h['rows']) - 100) < 0.5, '占比（0 傷害 0%、合計 100%）')
            check(h['durationSec'] and h['durationSec'] >= 15, f"打了幾秒（{h['durationSec']}）")
            check(h['boss']['maxHp'] == 2000000 and 0 < h['boss']['minHpPct'] < 100, f"王：maxHp、最低血量 {h['boss']['minHpPct']}%")
            check(h['grossDps'] and h['grossDps'] > 0 and h['regenDps'] is not None and h['netDps'] is not None and abs(h['grossDps'] - h['regenDps'] - h['netDps']) <= 2, f"總輸出 {h['grossDps']}／回血 {h['regenDps']}／淨輸出 {h['netDps']}（每秒）")
            w = h['orbWaves']
            check(len(w) == 1 and w[0]['sealed'] and not w[0]['cleared'] and w[0]['max'] >= 10 and w[0]['left'] > 0, f'黑球 1 波、沒清完、之後封印（{w}）')
            check(h['sealCount'] >= 1, f"全隊封印 {h['sealCount']} 次")
            check(rows['弓箭分身']['mpMinPct'] == 0 and rows['本尊劍士']['mpMinPct'] > 50, f"MP 最低（弓箭分身 {rows['弓箭分身']['mpMinPct']}%、本尊劍士 {rows['本尊劍士']['mpMinPct']}%）")
            check(len(rows['弓箭分身']['deathAt']) == 1 and len(rows['倉庫分身']['deathAt']) == 1 and not rows['本尊劍士']['deathAt'], f"倒下時間（{rows['弓箭分身']['deathAt']}）")
            why = '\n'.join(h['reasons']); print('    失敗原因：' + ' ／ '.join(h['reasons']))
            check('黑球第 1 波沒清完' in why and '全隊封印' in why, '原因：黑球第 1 波沒清完 → 全隊封印')
            check('封印後 40 秒內倒了 2 隻' in why, '原因：封印後倒了 2 隻')
            check('1 隻傷害 0：倉庫分身' in why, '原因：傷害 0 的角色')
            check('MP 見底：弓箭分身' in why, '原因：MP 見底')
            check(why.index('黑球') < why.index('傷害 0'), '黑球／封印排在前面')
            check('20 分鐘打完要淨輸出 1667／秒' in why and h['netDps'] < 1667, '原因：淨輸出不夠（20 分鐘要 200 萬／1200 秒）')
        rep = raid()['report']['report']
        hub_json('POST', '/api/raid/report', {'charId': 'c3', 'report': rep})
        await asyncio.sleep(1)
        check(len(hist()) == 1, '同一場（代碼＋時間）每隻都送也只存一次')

        print('3. 第二場（直接送結算，中控沒有戰況）')
        rep2 = {'result': 'clear', 'at': int(time.time() * 1000), 'total': 900000, 'code': 'RD9999',
                'rows': [{'name': '本尊劍士', 'damage': 600000, 'deaths': 0}, {'name': '弓箭分身', 'damage': 300000, 'deaths': 0}, {'name': '倉庫分身', 'damage': 0, 'deaths': 1}]}
        hub_json('POST', '/api/raid/report', {'charId': 'c1', 'report': rep2})
        hs = await wait(lambda: (lambda l: l if len(l) == 2 else None)(hist()), 10)
        check(hs and hs[0]['code'] == 'RD9999' and hs[0]['result'] == 'clear' and hs[0]['durationSec'] is None, '第二場存在最前面（沒有戰況就不亂算時間）')

        print('4. 面板：列表、點整列展開、每秒刷新不會收起來、兩場比較、刪除')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1100}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(2500)
        check(await d.locator('#rdHist tr.rh-row').count() == 2, '列出 2 場')
        r1 = d.locator('#rdHist tr.rh-row', has_text='失敗')
        t1 = await r1.inner_text()
        check('拉圖斯' in t1 and '失敗' in t1 and ':' in t1 and t1.split(chr(9))[-3] == '2', f'一列：時間、副本、結果、總傷、時間、死亡 2（中控看到倒下）（{t1!r}）')
        await r1.locator('td').nth(2).click(); await d.wait_for_timeout(500)
        det = d.locator('#rdHist tr.rh-det')
        dt = await det.inner_text() if await det.count() else ''
        check('失敗原因' in dt and '黑球第 1 波沒清完' in dt and '倉庫分身' in dt and 'MP 最低' in dt and '淨輸出' in dt, '點整列展開詳細（排名、占比、MP 最低、黑球、失敗原因）')
        check('沒清完' in (await det.locator('ul').nth(1).inner_text() if await det.locator('ul').count() > 1 else ''), '黑球每波的結果')
        await d.wait_for_timeout(3500)
        check(await d.locator('#rdHist tr.rh-det').count() == 1, '每秒刷新後展開狀態還在')
        h0 = await d.evaluate("document.querySelector('#rdHist table').outerHTML")
        await d.wait_for_timeout(2500)
        check(h0 == await d.evaluate("document.querySelector('#rdHist table').outerHTML"), '資料沒變就不重畫')
        await r1.locator('td').nth(1).click(); await d.wait_for_timeout(500)
        check(await d.locator('#rdHist tr.rh-det').count() == 0, '再點一次收起來')
        for cb in await d.locator('#rdHist input[data-rhcmp]').all(): await cb.check()
        await d.wait_for_timeout(500)
        cmp = await d.inner_text('#rdHistCmp') if await d.locator('#rdHistCmp').count() else ''
        check('比較' in cmp and '本尊劍士' in cmp and '倉庫分身' in cmp and '合計' in cmp and '+' in cmp, '勾兩場：每隻傷害差')
        await d.locator('#rdHist tr.rh-row', has_text='通關').locator('button[data-rhdel]').click()
        hs = await wait(lambda: (lambda l: l if len(l) == 1 else None)(hist()), 10)
        check(hs and hs[0]['code'] == code, '刪除一筆（API DELETE）')
        await d.wait_for_timeout(1500)
        check(await d.locator('#rdHist tr.rh-row').count() == 1 and await d.locator('#rdHistCmp').count() == 0, '面板跟著少一列、比較收起來')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))

        print('5. 中控重開：紀錄還在')
        await asyncio.sleep(2)  # 存檔有 1 秒延遲
        hub = env.procs[1]; hub.send_signal(signal.SIGKILL); hub.wait()
        newhub = subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787', 'SZG_QUIZ_SHARE_URL': 'http://127.0.0.1:9/', 'SZG_LOBBY_URL': 'http://127.0.0.1:9'},
                                  stdout=open('/tmp/hub2.log', 'w'), stderr=subprocess.STDOUT)
        env.procs[1] = newhub
        wait_url(HUB + '/api/settings')
        hs = hist()
        check(len(hs) == 1 and hs[0]['code'] == code and any('黑球第 1 波沒清完' in x for x in hs[0]['reasons']) and len(hs[0]['orbWaves']) == 1, '重開後紀錄（含分析）還在')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
