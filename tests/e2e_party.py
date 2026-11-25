"""組隊分頁：從目前隊伍匯入、拖曳排隊、一鍵套用（離隊、隊長建隊、隊員加入、換圖、開掛機）、已就位、即時經驗；
5. 加人／減人時沿用原本的隊伍（不解散重組：隊長留著、新的人用代碼加入、不要的人被隊長踢出）"""
import asyncio, json, os, sys, time
os.environ['MOCK_PARTY'] = 'c3,c4'
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3'])
        await env.wait_chars(3)
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=party]'); await d.wait_for_timeout(1500)

        print('1. 從目前隊伍匯入')
        await wait(lambda: all(((hub_json('GET', '/api/data')['chars'].get(c) or {}).get('party') or {}).get('party') for c in ('c3', 'c4')), 30)
        await d.evaluate('poll(true)'); await d.wait_for_timeout(500)
        await d.click('#ptImport'); await d.wait_for_timeout(800)
        ps = hub_json('GET', '/api/data')['settings'].get('parties') or []
        check(len(ps) == 1 and set(ps[0]['members']) == {'c3', 'c4'} and ps[0]['members'][0] == 'c3', f"匯入 1 隊：{ps and ps[0]['members']}（隊長 c3）")
        check('已就位' in await d.inner_text('#ptCards'), '卡片顯示「✓ 已就位」')

        print('2. 拖曳：新隊伍、把角色拖進去')
        await d.click('#ptAdd'); await d.wait_for_timeout(500)
        ps = hub_json('GET', '/api/data')['settings']['parties']; pid = ps[-1]['id']
        await d.drag_and_drop('#ptPool [data-ptchar="c1"]', f'[data-ptdrop="{pid}"]'); await d.wait_for_timeout(600)
        await d.drag_and_drop('.pt-mem[data-ptchar="c4"]', f'[data-ptdrop="{pid}"]'); await d.wait_for_timeout(600)
        ps = hub_json('GET', '/api/data')['settings']['parties']
        p2 = next(p for p in ps if p['id'] == pid)
        check(p2['members'] == ['c1', 'c4'], f"拖曳後新隊伍：{p2['members']}（c1 隊長）")
        check(next(p for p in ps if p['id'] != pid)['members'] == ['c3'], '原隊伍剩 c3')
        await d.select_option(f'[data-ptmap="{pid}"]', 'gms104040000'); await d.wait_for_timeout(600)
        check(next(p for p in hub_json('GET', '/api/data')['settings']['parties'] if p['id'] == pid)['map'] == 'gms104040000', '選地圖：射手訓練場')

        print('3. 套用全部')
        await d.click('#ptApplyAll'); await d.wait_for_timeout(1500)
        jobs = await wait(lambda: (lambda js: js if js and all(j['status'] in ('done', 'failed') for j in js) else None)([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party']), 120)
        check(jobs and len(jobs) == 3 and all(j['status'] == 'done' for j in jobs), '3 個組隊工作都完成' + ('' if jobs and all(j['status'] == 'done' for j in jobs) else '：' + '；'.join(f"{j['fromName']} {j['status']} {j['lastMsg']}" for j in (jobs or []))))
        c1, c3, c4 = mock_char('A1', 'c1'), mock_char('A2', 'c3'), mock_char('A3', 'c4')
        check(c1.get('partyCode') and c1.get('partyCode') == c4.get('partyCode'), f"c1、c4 同一隊（{c1.get('partyCode')}）")
        check(not c3.get('partyCode'), 'c3 離開原本的隊伍（單人）')
        check(c4['map'] == 'gms104040000' and c4['auto'] and c1['auto'], 'c4 換到射手訓練場，兩隻都在掛機')
        st = await wait(lambda: None, 0)
        for _ in range(20):
            await d.evaluate('poll(true)'); await d.wait_for_timeout(1500)
            txt = await d.inner_text(f'[data-ptdrop="{pid}"]')
            if '已就位' in txt: break
        check('已就位' in txt, '新隊伍卡片顯示「✓ 已就位」')

        print('4. 即時經驗（最近 3 分鐘）')
        live = await wait(lambda: (lambda L: L if L.get('c4', {}).get('rate') is not None else None)(hub_json('GET', '/api/data').get('expLive') or {}), 100, 3)
        check(live and live['c4']['rate'] >= 0, f"c4 換圖後量到每小時經驗 {live and live['c4']['rate']:,}" if live else 'c4 換圖後量到每小時經驗')
        await d.evaluate('poll(true)'); await d.wait_for_timeout(800)
        txt = await d.inner_text(f'[data-ptdrop="{pid}"]')
        check('全隊每小時經驗' in txt and ('測量中' in txt or '最近 3 分鐘' in txt), '卡片顯示全隊經驗與量測狀態')
        await d.screenshot(path='/tmp/party.png')

        print('5. 加人、減人：沿用原本的隊伍，不解散重組')
        K = mock_char('A1', 'c1')['partyCode']
        def hp(cs, c): return (((cs.get(c) or {}).get('party') or {}).get('party') or {})
        seen = lambda: (lambda cs: cs if all(hp(cs, c).get('code') == K for c in ('c1', 'c4')) else None)(hub_json('GET', '/api/data')['chars'])
        check(await wait(seen, 30), '中控看到 c1、c4 的隊伍')
        def apply(members):
            r = hub_json('POST', '/api/party/apply', {'parties': [{'id': 'x', 'name': '測試隊', 'members': members, 'map': 'gms104040000'}]})
            return r
        n0 = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party'])
        apply(['c3', 'c1', 'c4'])  # 名單第一位是 c3，但遊戲裡的隊長 c1 在名單裡 → 沿用 c1 的隊伍
        js = await wait(lambda: (lambda js: js if len(js) == 3 and all(j['status'] in ('done', 'failed') for j in js) else None)([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party'][n0:]), 90)
        check(js and all(j['status'] == 'done' for j in js), '3 個工作都完成' + ('' if js and all(j['status'] == 'done' for j in js) else '：' + '；'.join(f"{j['fromName']} {j['status']} {j['lastMsg']}" for j in (js or []))))
        c1, c3, c4 = mock_char('A1', 'c1'), mock_char('A2', 'c3'), mock_char('A3', 'c4')
        check(c1['partyCode'] == K and c4['partyCode'] == K and c3['partyCode'] == K, f"隊伍代碼沒變（{K}），c3 加進來")
        logs = ' '.join(' '.join(l['msg'] if isinstance(l, dict) else str(l) for l in j.get('log', [])) for j in js or [])
        check('沿用隊伍' in logs and '用隊伍代碼加入' in logs and '建立隊伍' not in logs.replace('（隊長，建立隊伍）', ''), '紀錄寫沿用隊伍、用代碼加入，沒有重建')
        check(c3['map'] == 'gms104040000' and c3['auto'], 'c3 換到同一張圖並開始掛機')
        seen3 = lambda: (lambda cs: cs if hp(cs, 'c3').get('code') == K and len(hp(cs, 'c1').get('members') or []) == 3 else None)(hub_json('GET', '/api/data')['chars'])
        await wait(seen3, 30)
        n0 = len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party'])
        apply(['c1', 'c3'])  # 拿掉 c4 → 隊長踢出
        js = await wait(lambda: (lambda js: js if len(js) == 2 and all(j['status'] in ('done', 'failed') for j in js) else None)([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party'][n0:]), 90)
        check(js and all(j['status'] == 'done' for j in js), '減人：2 個工作都完成')
        c1, c3, c4 = mock_char('A1', 'c1'), mock_char('A2', 'c3'), mock_char('A3', 'c4')
        check(c1['partyCode'] == K and c3['partyCode'] == K and not c4.get('partyCode'), 'c4 被踢出，c1、c3 還在原本的隊伍')

        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
