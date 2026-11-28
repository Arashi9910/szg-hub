"""副本戰況看板（照 2026-11-28 第一場實機拉圖斯補強）：王的 damageBy／回血估計／淨輸出／預估打完時間、
黑球（enemies 裡 maxHp 20000）剩幾顆＋沒清完全隊封印、只顯示還有效的異常（diseases 留過期紀錄）、0 傷害標紅、結束後的 raidReport"""
import asyncio, json, os, sys, time
os.environ.update({'MOCK_RAID_PREP_MS': '3000', 'MOCK_RAID_FEE': '100000', 'MOCK_RAID_NO_MAGE': '1',
                   'MOCK_RAID_DPS': '0.006', 'MOCK_RAID_REGEN': '0.001',              # 2M 血：總輸出 1.2 萬／秒、回血 2000／秒
                   'MOCK_RAID_ORB_MS': '600000', 'MOCK_RAID_ORB_LIFE_MS': '6000',      # 黑球由測試觸發；6 秒後自己消失
                   'MOCK_RAID_ORB_KILL': '0.5', 'MOCK_RAID_SEAL_MS': '8000', 'MOCK_RAID_ZERO': 'c4'})
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def raid(q=''): return hub_json('GET', '/api/raid' + q)
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
        print('0. 組隊（直接用 API）：拉圖斯，隊長 c1，隊員 c3、c4')
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4']}})
        act([{'charId': 'c1', 'cmd': {'type': 'raidCreate', 'raid': 'papulatus'}, 'label': '建立'}])
        team = await wait(lambda: (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        check(team and team.get('code'), f"建立隊伍 {team and team.get('code')}")
        act([{'charId': c, 'cmd': {'type': 'raidJoin', 'code': team['code']}, 'label': '加入'} for c in ['c3', 'c4']])
        await wait(lambda: all((raid()['views'].get(c) or {}).get('view', {}).get('team') for c in ['c3', 'c4']), 40)
        act([{'charId': c, 'cmd': {'type': 'raidReady', 'ready': True}, 'label': '準備'} for c in ['c3', 'c4']])
        await wait(lambda: all(m['ready'] or m['leader'] for m in ((raid()['views'].get('c4') or {}).get('view', {}).get('team') or {}).get('members', [{'ready': False, 'leader': False}])), 40)
        act([{'charId': 'c1', 'cmd': {'type': 'raidStart', 'memberIds': ['c1', 'c3', 'c4']}, 'label': '開始'}])
        b = await wait(lambda: live('c1').get('battle'), 40)
        check(b and b['raid'] == 'papulatus', '開打了')

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1100}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(1500)

        print('1. 回報者送王的 damageBy；異常只送還有效的')
        boss = await wait(lambda: (lambda e: e[0] if e and (e[0].get('damageBy') or {}).get('c3') else None)(live('c1').get('enemies')), 30)
        check(boss and boss['maxHp'] == 2000000 and boss['damageBy'].get('c1', 0) > boss['damageBy'].get('c3', 0) > 0, f"王的 damageBy（{boss and boss.get('damageBy')}）")
        check(boss and not boss['damageBy'].get('c4'), '倉庫分身（模擬 0 傷害）沒有傷害')
        st = json.loads(http('GET', MOCK + '/__mock/state')[1])
        c3 = st['accounts']['A2']['chars']['c3']
        check('stun' in (c3.get('diseases') or {}), '遊戲（mock）的 diseases 留著過期的 stun 紀錄')
        me = live('c3').get('me') or {}
        check('stun' not in (me.get('diseases') or {}), f"agent 只送還有效的異常（{me.get('diseases')}）")

        print('2. 時間序列：每秒一筆，?since= 只拿新的')
        s = await wait(lambda: (lambda x: x if x and len(x['points']) >= 8 else None)(raid()['series']), 30)
        check(s and s['code'] == b['code'] and s['maxHp'] == 2000000, f"series 有 {s and len(s['points'])} 筆")
        if s:
            ts = [p[0] for p in s['points']]
            check(ts == sorted(ts) and all(ts[i + 1] - ts[i] >= 800 for i in range(len(ts) - 1)), '時間遞增、大約一秒一筆')
            part = raid('?since=%d' % ts[-3])['series']
            check(part['since'] == ts[-3] and 1 <= len(part['points']) <= 4 and part['n'] >= len(s['points']), f"?since= 只回新的（{len(part['points'])} 筆，總共 {part['n']}）")
        await d.wait_for_timeout(8000)
        txt = await d.inner_text('#rdBattle')
        check('回血速度' in txt and '淨輸出' in txt and '總輸出' in txt, '面板顯示總輸出、回血速度、淨輸出')
        eta = await d.inner_text('#rdEta')
        check('時間內打得完' in eta, f'照這速度打得完（{eta!r}）')
        stat = await d.inner_text('#rdStat')
        check('／秒' in stat and '—' not in stat.split('回血速度')[1].split('淨輸出')[0], f'回血速度有估出來（{stat!r}）')
        row = d.locator('#rdBattle .rd-mem tr', has_text='倉庫分身')
        check(await row.locator('td.num.bad').count() >= 2 and '0.0%' in await row.inner_text(), '0 傷害的隊員標紅、占比 0.0%（攻擊紀錄欄的「沒出手」也是紅的）')
        row1 = d.locator('#rdBattle .rd-mem tr', has_text='本尊劍士')
        check(await row1.locator('td.num.bad').count() == 0 and '%' in await row1.inner_text(), '有傷害的隊員顯示累計傷害和占比')
        check('還沒出現過' in await d.inner_text('#rdOrbs'), '黑球：還沒出現過')

        print('3. 黑球：15 顆、無敵；沒清完自己消失 → 全隊封印')
        mock('?orbs=now')
        bb = await wait(lambda: (lambda x: x if x and x.get('invulnerable') and x.get('orbs') else None)(live('c1').get('battle')), 20)
        check(bb and 10 <= bb['orbs'] <= 15, f"黑球出現、王無敵（剩 {bb and bb['orbs']} 顆）")
        en = live('c1').get('enemies') or []
        orbs = [e for e in en if e.get('maxHp') == 20000]
        check(en and en[0]['maxHp'] == 2000000 and len(orbs) >= 10, f'enemies 有王＋黑球（黑球 {len(orbs)} 顆，maxHp 20000）')
        await d.wait_for_timeout(1500)
        ot = await d.inner_text('#rdOrbs')
        check('剩' in ot and '沒清完' in ot and '封印' in ot, f'面板：黑球剩幾顆＋提示沒清完會全隊封印')
        check(await d.locator('#rdOrbs .rd-orbs .rd-bar').count() >= 10, '每顆黑球的血條')
        sealed = await wait(lambda: all('seal' in ((live(c).get('me') or {}).get('diseases') or {}) for c in ['c1', 'c3', 'c4']), 25)
        check(sealed, '黑球沒清完 → 全隊封印')
        check(not live('c1').get('battle', {}).get('invulnerable'), '黑球消失後王不再無敵')
        sd = (live('c3').get('me') or {}).get('diseases', {}).get('seal') or {}
        check(sd.get('raid') and 0 < sd.get('left', 0) <= 8, f'封印附剩幾秒（{sd}）')
        await d.wait_for_timeout(1500)
        row = await d.locator('#rdBattle .rd-mem tr', has_text='弓箭分身').inner_text()
        check('封印' in row and '秒' in row, f'隊員列顯示封印剩幾秒（{row!r}）')
        ot = await d.inner_text('#rdOrbs')
        check('上次出現' in ot and '下一波約' in ot and '全隊封印過 1 次' in ot, f'記錄上次黑球時間、估下一波、封印次數（{ot!r}）')
        check(len(raid()['series']['orbWaves']) == 1, '伺服器記了 1 波黑球')
        gone = await wait(lambda: not any('seal' in ((live(c).get('me') or {}).get('diseases') or {}) for c in ['c1', 'c3', 'c4']), 20)
        check(gone, '封印時間過了就不再回報（遊戲留著過期紀錄也不算）')
        await d.wait_for_timeout(1500)
        check('封印' not in await d.locator('#rdBattle .rd-mem tr', has_text='弓箭分身').inner_text(), '面板上封印消失')

        print('4. 回血大於輸出 → 打不完標紅')
        mock('?regen=0.02')
        red = None
        for _ in range(45):
            if await d.locator('#rdEta.bad').count() and '打不完' in await d.inner_text('#rdEta'): red = True; break
            await d.wait_for_timeout(1000)
        check(red, '預估打不完時標紅')
        mock('?regen=')

        print('5. 結束：raidReport')
        mock('?end=fail')
        rep = await wait(lambda: (raid().get('report') or {}).get('report'), 30)
        check(rep and rep['result'] == 'fail' and len(rep['rows']) == 3 and rep['code'] == b['code'], f'中控存了結算（{rep}）')
        if rep:
            r4 = [r for r in rep['rows'] if r['name'] == '倉庫分身']
            check(r4 and r4[0]['damage'] == 0 and rep['total'] == sum(r['damage'] for r in rep['rows']) and rep['total'] > 0, '結算：總傷害、每人傷害（倉庫分身 0）')
        await wait(lambda: not live('c1').get('battle'), 20)
        await d.wait_for_timeout(2000)
        rt = await d.inner_text('#rdBattle')
        check('上一場結算' in rt and '失敗' in rt and '總傷害' in rt and '倉庫分身' in rt and '死亡' in rt, f'面板顯示結算（結果、總傷害、每人）')
        check(await d.locator('#rdReport tr', has_text='倉庫分身').locator('td.num.bad').count() == 2, '結算裡 0 傷害標紅')
        await d.wait_for_timeout(4000)
        check(raid()['report']['report']['at'] == rep['at'], '同一份結算不重複覆蓋')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
