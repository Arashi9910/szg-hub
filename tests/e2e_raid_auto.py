"""副本戰中自動應對（settings.raid.auto）：黑球出現 → 伺服器排分配表 → 負責的角色各自的 agent 送 {type:'target', target:slot}
→ 黑球清完不封印 → 切回王；沒開時照舊沒清完全隊封印。另外：警告列（30 秒沒傷害、MP 低於 10%、封印）、target 失敗不重試轟炸。"""
import asyncio, json, os, sys, time
os.environ.update({'MOCK_RAID_PREP_MS': '3000', 'MOCK_RAID_FEE': '100000', 'MOCK_RAID_NO_MAGE': '1',
                   'MOCK_RAID_DPS': '0.002', 'MOCK_RAID_REGEN': '0.0005',             # 王 2M 血，整場打不完
                   'MOCK_RAID_ORB_MS': '600000', 'MOCK_RAID_ORB_LIFE_MS': '6000',      # 黑球由測試觸發
                   'MOCK_RAID_ORB_KILL': '0.02', 'MOCK_RAID_ORB_FOCUS': '2',          # 沒選目標幾乎打不動；選了黑球當目標的一隻每秒 4 萬（隊長 8 萬）
                   'MOCK_RAID_SEAL_MS': '6000', 'MOCK_RAID_ZERO': 'c4'})
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def raid(q=''): return hub_json('GET', '/api/raid' + q)
def mock(q): return json.loads(http('GET', MOCK + '/__mock/raid' + q)[1])
def live(cid): return (raid()['live'].get(cid) or {})
def targets(): t = mock('')['teams']; return (t[0] if t else {}).get('targets') or {}
def sealed(c): return 'seal' in ((live(c).get('me') or {}).get('diseases') or {})
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
        print('0. 組隊開打：拉圖斯，隊長 c1，隊員 c3、c4（c4 模擬 0 傷害）；自動應對預設關')
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3', 'c4']}})
        act([{'charId': 'c1', 'cmd': {'type': 'raidCreate', 'raid': 'papulatus'}, 'label': '建立'}])
        team = await wait(lambda: (raid()['views'].get('c1') or {}).get('view', {}).get('team'), 40)
        act([{'charId': c, 'cmd': {'type': 'raidJoin', 'code': team['code']}, 'label': '加入'} for c in ['c3', 'c4']])
        await wait(lambda: all((raid()['views'].get(c) or {}).get('view', {}).get('team') for c in ['c3', 'c4']), 40)
        act([{'charId': c, 'cmd': {'type': 'raidReady', 'ready': True}, 'label': '準備'} for c in ['c3', 'c4']])
        await wait(lambda: all(m['ready'] or m['leader'] for m in ((raid()['views'].get('c4') or {}).get('view', {}).get('team') or {}).get('members', [{'ready': False, 'leader': False}])), 40)
        act([{'charId': 'c1', 'cmd': {'type': 'raidStart', 'memberIds': ['c1', 'c3', 'c4']}, 'label': '開始'}])
        b = await wait(lambda: live('c1').get('battle'), 40)
        check(b, '開打了')
        cfg = raid()['auto']['cfg']
        check(cfg == {'orbs': False, 'back': False, 'orbChars': []}, f'自動應對預設全關（{cfg}）')
        en = await wait(lambda: (lambda e: e if e and all(isinstance(x.get('slot'), int) for x in e) else None)(live('c1').get('enemies')), 20)
        check(en and en[0]['slot'] == 0, f"回報者的 enemies 帶 slot（遊戲 enemies 的索引）：{en and [x.get('slot') for x in en]}")

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1100}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(2000)
        at = await d.inner_text('#rdAuto')
        check('黑球出現時自動集火' in at and '切回王' in at and '本尊劍士' in at and '弓箭分身' in at and '倉庫分身' in at, '面板：自動應對開關＋負責角色清單')

        print('1. 沒開自動集火：黑球沒清完 → 全隊封印，不送 target')
        mock('?clearTargets=1&orbLife=6000&orbs=now')
        await wait(lambda: live('c1').get('battle', {}).get('invulnerable'), 15)
        await d.wait_for_timeout(1500)
        wt = await d.inner_text('#rdWarn')
        check('黑球' in wt and '自動集火沒開' in wt, f'警告列：黑球出現、自動集火沒開（{wt!r}）')
        s = await wait(lambda: all(sealed(c) for c in ['c1', 'c3', 'c4']), 20)
        check(s, '沒清完 → 全隊封印')
        check(not mock('')['targetLog'], '沒開就不送 target')
        await d.wait_for_timeout(1500)
        wt = await d.inner_text('#rdWarn')
        check('被封印' in wt and '弓箭分身' in wt, f'警告列：誰被封印（{wt!r}）')
        await wait(lambda: not any(sealed(c) for c in ['c1', 'c3', 'c4']), 15)

        print('2. 面板開啟：自動集火＋切回王、負責角色 c1、c3（點整列）')
        await d.click('#rdAuto input[data-rdauto=orbs]'); await d.wait_for_timeout(400)
        await d.click('#rdAuto input[data-rdauto=back]'); await d.wait_for_timeout(400)
        await d.locator('#rdAutoChars label', has_text='本尊劍士').click(); await d.wait_for_timeout(400)
        await d.locator('#rdAutoChars label', has_text='弓箭分身').click(); await d.wait_for_timeout(800)
        cfg = raid()['auto']['cfg']
        check(cfg['orbs'] and cfg['back'] and sorted(cfg['orbChars']) == ['c1', 'c3'], f'存進 settings.raid.auto（{cfg}）')
        plan = raid()['plan']
        check(plan.get('leader') == 'c1' and plan.get('members') == ['c3', 'c4'], '隊伍計畫沒被蓋掉')
        await d.click('#rdLock'); await d.wait_for_timeout(800)
        check(raid()['auto']['cfg']['orbs'] and raid()['plan'].get('lock'), '面板改別的副本設定（上鎖）auto 還在')
        await d.click('#rdLock'); await d.wait_for_timeout(500)

        print('3. 開了：黑球出現 → 只指派 c1、c3 → 送 target → 清完不封印 → 切回王')
        mock('?clearTargets=1&orbLife=15000&orbs=now')
        asg = await wait(lambda: (lambda a: a if len(a) == 2 else None)(raid()['auto']['assign']), 15)
        check(asg and set(asg) == {'c1', 'c3'} and all(x['kind'] == 'orb' and x['slot'] >= 1 for x in asg.values()), f'分配表只有負責的 c1、c3，打黑球（{asg}）')
        await d.wait_for_timeout(1200)
        wt = await d.inner_text('#rdWarn')
        check('已指派 2 隻去打' in wt, f'警告列：已指派 2 隻去打（{wt!r}）')
        tg = await wait(lambda: (lambda t: t if all(isinstance(t.get(c), int) and t[c] >= 1 for c in ['c1', 'c3']) else None)(targets()), 10)
        check(tg and tg.get('c4') is None, f'c1、c3 的遊戲目標換成黑球，c4 沒動（{tg}）')
        cleared = await wait(lambda: not live('c1').get('battle', {}).get('invulnerable'), 15)
        check(cleared, '黑球清完（王不再無敵）')
        await asyncio.sleep(3)
        check(not any(sealed(c) for c in ['c1', 'c3', 'c4']), '清完就不封印')
        back = await wait(lambda: (lambda t: t if t.get('c1') == 0 and t.get('c3') == 0 else None)(targets()), 10)
        check(back, f'清完切回王（target 0）：{targets()}')
        logs = mock('')['targetLog']
        by = {}
        for x in logs: by.setdefault(x['char'], []).append(x)
        check('c4' not in by, '沒負責的 c4 一次都沒送')
        gaps = [b2['at'] - a2['at'] for v in by.values() for a2, b2 in zip(v, v[1:])]
        check(all(g >= 1900 for g in gaps) and all(len(v) <= 8 for v in by.values()), f'每隻最少隔 2 秒才換目標、次數不多（{ {k: len(v) for k, v in by.items()} }，間隔 {gaps}）')
        await asyncio.sleep(4)
        check(len(mock('')['targetLog']) == len(logs), '切回王之後同一個目標不重送')
        await d.wait_for_timeout(1200)
        lt = await d.inner_text('#rdAutoLog')
        check('本尊劍士 → 黑球 #' in lt and '→ 王' in lt and '✓' in lt, f'面板：自動動作紀錄（{lt[:120]!r}）')
        check('波黑球結束' in lt, '紀錄黑球一波結束')

        print('4. 警告：30 秒以上沒傷害、MP 低於 10%')
        idle = await wait(lambda: any(w['id'] == 'c4' and w['kind'] == 'idle' for w in raid()['auto']['warn']), 40)
        check(idle, '0 傷害的 c4 → 30 秒以上沒有傷害')
        check(not any(w['id'] in ('c1', 'c3') and w['kind'] == 'idle' for w in raid()['auto']['warn']), '有在打的不警告')
        mock('?setmp=c3:10')
        mp = await wait(lambda: any(w['id'] == 'c3' and w['kind'] == 'mp' for w in raid()['auto']['warn']), 20)
        check(mp, 'c3 MP 低於 10% → 警告')
        await d.wait_for_timeout(1500)
        wt = await d.inner_text('#rdWarn')
        check('倉庫分身' in wt and '沒有傷害' in wt and 'MP' in wt, f'警告列顯示（{wt!r}）')
        mock('?setmp=c3:300')

        print('5. target 失敗：記錄錯誤、不一直重送')
        mock('?clearTargets=1&targetFail=1&orbLife=8000&orbs=now')
        await wait(lambda: live('c1').get('battle', {}).get('invulnerable'), 15)
        await asyncio.sleep(7)
        fl = [x for x in raid()['auto']['log'] if x.get('kind') == 'orb' and not x.get('ok')]
        cnt = {}
        for x in fl: cnt[x['charId']] = cnt.get(x['charId'], 0) + 1
        check(cnt.get('c1') == 1 and cnt.get('c3') == 1 and '無法切換' in fl[-1].get('error', ''), f'失敗記下原因、每隻只試一次（{cnt}，{fl[-1:]}）')
        await d.wait_for_timeout(1200)
        check('✗' in await d.inner_text('#rdAutoLog'), '面板紀錄顯示失敗')
        mock('?targetFail=')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
