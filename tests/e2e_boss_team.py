"""隊伍打王（v0.69.3）：一起打要全員能出發（等隊友）→ 依隊伍看的卡片、每個隊伍各自的打法 → 一起打時倒下原地復活繼續、有人被停止整隊一起回"""
import asyncio, os, sys, time, json
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'
os.environ['MOCK_PARTY'] = 'c3,c4'
from harness import Env, hub_json, http, http_raw, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)
def mock_char(acct, cid): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]
def game(acct, body):
    body = {'requestId': str(time.time()), **body}
    s, t = http_raw('POST', MOCK + '/api/game', json.dumps(body), {'Content-Type': 'application/json', 'x-game-version': '1', 'x-acct': acct})
    return json.loads(t)
async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None
def boss_jobs(): return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']
def active(): return [j for j in boss_jobs() if j['status'] in ('approved', 'running')]
def l_char(b, msg): return next((l['charId'] for l in b['log'] if l['msg'] == msg), None)
def logs(j): return ' '.join(l['msg'] if isinstance(l, dict) else str(l) for l in j.get('log', []))

async def main():
    async with Env() as env:
        base = {'charMobs': {'c3': ['mBoss1']}, 'estMax': 100000, 'chain': False}
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', **base}})
        await env.open_accounts(['A2', 'A3'])
        await env.wait_chars(2)
        p = await wait(lambda: (lambda b: b['parties'][0] if b.get('parties') and any(c.get('at') for c in b['chars'] if c['charId'] == 'c3') else None)(hub_json('GET', '/api/boss')), 60)
        check(p and set(p['ids']) == {'c3', 'c4'} and p['mode'] == 'together', f"認得 c3、c4 同一隊（{p and p['ids']}，{p and p['mode']}）")

        print('1. 一起打：隊友沒在掛機 → 整隊等')
        game('A3', {'type': 'stop', 'characterId': 'c4'})
        await wait(lambda: not hub_json('GET', '/api/data')['chars']['c4']['char']['auto'], 30)
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', **base}})
        hub_json('POST', '/api/boss/run-now')
        check(not boss_jobs(), 'c4 沒在掛機：沒有人自己先去（以前 c3 會一個人去）')
        p = hub_json('GET', '/api/boss')['parties'][0]
        check(p['why'].get('c4') == '沒在掛機', f"隊伍卡片資料：等 c4（{p['why']}）")
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dg: asyncio.ensure_future(dg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab="maps"]'); await d.wait_for_timeout(1500)
        await d.click('#bossView [data-bview=party]'); await d.wait_for_timeout(1000)
        txt = await d.inner_text('#bossParties')
        check('等隊友' in txt and '倉庫分身（沒在掛機）' in txt, '依隊伍看：顯示等誰：' + txt.replace('\n', ' ')[:120])
        game('A3', {'type': 'start', 'characterId': 'c4'})
        await wait(lambda: hub_json('GET', '/api/data')['chars']['c4']['char']['auto'], 30)
        hub_json('POST', '/api/boss/run-now')
        js = boss_jobs()
        check(len(js) == 2 and {j['fromCharId'] for j in js} == {'c3', 'c4'}, f'c4 回來掛機後整隊一起出發（{len(js)} 個工作）')
        await wait(lambda: not active(), 120)
        check(all(j['status'] == 'done' for j in boss_jobs()), '一起打死紅寶王、都回去了' + ('' if all(j['status'] == 'done' for j in boss_jobs()) else '：' + '；'.join(f"{j['fromName']} {j['status']} {j['lastMsg']}" for j in boss_jobs())))

        print('2. 每個隊伍各自的打法')
        await d.evaluate('loadBoss(true).then(() => renderBoss(true))'); await d.wait_for_timeout(800)
        key = hub_json('GET', '/api/boss')['parties'][0]['key']
        await d.click(f'[data-pbmode="{key}|split"]'); await d.wait_for_timeout(1200)
        b = hub_json('GET', '/api/boss')
        check(b['cfg']['parties'].get(key, {}).get('mode') == 'split' and b['parties'][0]['mode'] == 'split' and b['parties'][0]['custom'], f"這隊改成各自分開打（{b['cfg']['parties']}）")
        hub_json('POST', '/api/settings', {'boss': {**hub_json('GET', '/api/data')['settings']['boss'], 'mode': 'preview', 'charMobs': {'c3': ['mBoss2']}}})
        b = hub_json('POST', '/api/boss/run-now')
        msg = next((l['msg'] for l in reversed(b['log']) if '試跑' in l['msg'] and '蘑菇王' in l['msg']), '')
        check(msg and '隊伍' not in msg and l_char(b, msg) == 'c3', f"各自打：試跑只有勾王的 c3 自己去（{msg}）")
        await d.evaluate('poll(true).then(() => loadBoss(true)).then(() => renderBoss(true))'); await d.wait_for_timeout(1200)
        await d.click(f'[data-pbreset="{key}"]'); await d.wait_for_timeout(1200)
        b = hub_json('GET', '/api/boss')
        check(key not in b['cfg']['parties'] and b['parties'][0]['mode'] == 'together', '改回預設（一起打）')

        print('3. 一起打：倒下原地復活繼續；有人被停止整隊一起回')
        hub_json('POST', '/api/settings', {'boss': {**hub_json('GET', '/api/data')['settings']['boss'], 'mode': 'auto'}})
        hub_json('POST', '/api/boss/run-now')
        js = active()
        check(len(js) == 2, f'整隊一起去打蘑菇王（{len(js)}）')
        await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None), None), 60)
        http('GET', MOCK + '/__mock/die?acct=A3&char=c4')
        j4 = await wait(lambda: (lambda j: j if j and '原地復活繼續' in logs(j) else None)(next((x for x in boss_jobs() if x['fromCharId'] == 'c4' and x['batches'][0]['boss']['mob'] == 'mBoss2'), None)), 40)
        check(j4 and j4['status'] in ('approved', 'running'), 'c4 倒下：原地復活、繼續跟隊友打')
        check(mock_char('A3', 'c4')['hp'] > 0 and mock_char('A3', 'c4')['map'] == 'gms100000005', 'c4 活著、還在王的地圖')
        hub_json('POST', '/api/boss/stop', {'charIds': ['c4']})
        await wait(lambda: not active(), 60)
        j3 = next(x for x in boss_jobs() if x['fromCharId'] == 'c3' and x['batches'][0]['boss']['mob'] == 'mBoss2')
        check(j3['status'] == 'done' and '隊友 倉庫分身 被停止' in logs(j3), '只停 c4 → c3 也跟著一起回去')
        b = hub_json('GET', '/api/boss')
        held = {c['charId']: bool(c['held']) for c in b['chars']}
        check(held.get('c4') and not held.get('c3'), f'只有被停的 c4 暫停打王（{held}）')
        c3, c4 = mock_char('A2', 'c3'), mock_char('A3', 'c4')
        check(c3['map'] != 'gms100000005' and c4['map'] != 'gms100000005' and c3['auto'] and c4['auto'], '兩隻都回練功圖在掛機')
        await d.screenshot(path='/tmp/boss_team.png', full_page=True)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
