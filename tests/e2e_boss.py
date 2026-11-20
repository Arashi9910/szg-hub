"""輪流打野王：回報王的狀態 → 試跑只記錄 → 自動出發打死王、回原本的地圖 → 打不死的王時間到先回去、血量保留、30 分鐘內不再去"""
import asyncio, os, sys, time
os.environ['MOCK_BOSS_DPS'] = '600'          # 紅寶王 3000 血，幾秒就打死
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
os.environ['MOCK_MAP_STOPS_IDLE'] = '1'   # 真實遊戲換地圖會停止掛機
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    import json
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

def boss_char(cid):
    b = hub_json('GET', '/api/boss')
    return next((c for c in b['chars'] if c['charId'] == cid), None), b

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'chars': {'c3': True}, 'mobs': None, 'estMax': 15, 'visitMax': 1}})
        await env.open_accounts(['A2'])
        await env.wait_chars(1)
        print('1. 遊戲分頁回報王的狀態')
        st = await wait(lambda: (boss_char('c3')[0] or {}).get('at'), 60)
        c3, _ = boss_char('c3')
        check(st and len(c3['rows']) == 2, f"收到 2 隻野王的狀態（{len(c3['rows']) if c3 else 0}）")
        r1 = next(r for r in c3['rows'] if r['mob'] == 'mBoss1')
        check(r1['ready'] and not r1['cooling'], '紅寶王已重生、可以打')

        print('2. 試跑：只記錄，不出發')
        b = hub_json('POST', '/api/boss/run-now')
        check(any('試跑' in l['msg'] and '紅寶王' in l['msg'] for l in b['log']), '紀錄有「試跑：會去 … 打 紅寶王」')
        check(not [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss'], '沒有建立打王工作')

        print('3. 自動：出發打死王，回原本的地圖')
        home = mock_char('A2', 'c3')['map']
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss1'], 'estMax': 15, 'visitMax': 1}})
        hub_json('POST', '/api/boss/run-now')
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']
        check(len(jobs) == 1 and jobs[0]['batches'][0]['boss']['mob'] == 'mBoss1', '建立 1 個打紅寶王的工作')
        done = await wait(lambda: next((j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss' and j['status'] in ('done', 'failed')), None), 90)
        check(done and done['status'] == 'done', '工作完成' + ('' if done and done['status'] == 'done' else f"：{done and done['lastMsg']}"))
        _, b = boss_char('c3')
        check(any('打死了' in l['msg'] for l in b['log']), '紀錄有「打死了」')
        c = mock_char('A2', 'c3')
        check(c['map'] == home, f'回到原本的地圖（{c["map"]}）')
        check(c['auto'], '回去後有重新開始掛機（真實遊戲換地圖會停止掛機）')
        c3, _ = boss_char('c3')
        r1 = next(r for r in c3['rows'] if r['mob'] == 'mBoss1')
        check(r1['cooling'] and r1['remainMs'] > 50 * 60 * 1000, '紅寶王變成冷卻中（約 60 分鐘後重生）')
        hub_json('POST', '/api/boss/run-now')
        check(len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']) == 1, '冷卻中不會再派')

        print('4. 打不死的王：時間到先回去，血量保留，30 分鐘內不再去')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss2'], 'estMax': 100000, 'visitMax': 1}})
        hub_json('POST', '/api/boss/run-now')
        lv = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None), None), 40)
        check(lv and lv['mob'] == 'mBoss2', '打王中：即時血量有回報' + (f"（{lv['hp']:,}）" if lv else ''))
        c = mock_char('A2', 'c3')
        check(c['map'] == 'gms100000005' and c['auto'], '到了首領地圖有開始掛機')
        lv2 = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None and g['hp'] < lv['hp']), None), 20)
        check(lv2, '血量持續更新（幾秒內就變少）')
        eta = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g.get('etaSec') is not None), None), 25)
        check(eta, '算得出預估還要多久' + (f"（{eta['etaSec']:,} 秒）" if eta else ''))
        await asyncio.sleep(1)
        done = await wait(lambda: next((j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss' and j['batches'][0]['boss']['mob'] == 'mBoss2' and j['status'] in ('done', 'failed')), None), 150)
        check(done and done['status'] == 'done', '工作結束')
        _, b = boss_char('c3')
        check(any('蘑菇王' in l['msg'] and '還沒打死' in l['msg'] for l in b['log']), '紀錄有「打了 1 分鐘還沒打死」')
        check(mock_char('A2', 'c3')['map'] == home and mock_char('A2', 'c3')['auto'], '回到原本的地圖並在掛機')
        c3, _ = boss_char('c3')
        r2 = next(r for r in c3['rows'] if r['mob'] == 'mBoss2')
        check(r2['hpKnown'] and r2['hp'] < r2['maxHp'], f"記住剩下的血量（{r2['hp']:,} / {r2['maxHp']:,}）")
        check('再試' in r2['skip'], '30 分鐘內不再去：' + r2['skip'])
        hub_json('POST', '/api/boss/run-now')
        check(len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']) == 2, '沒有馬上再派')

        print('5. 預估太久的王不去')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss2'], 'estMax': 15, 'visitMax': 1}})
        c3, _ = boss_char('c3')
        r2 = next(r for r in c3['rows'] if r['mob'] == 'mBoss2')
        if c3['dps']:
            check('預估' in r2['skip'] and '超過 15 分鐘' in r2['skip'], '有實戰 DPS：' + r2['skip'])
        else:
            print('  - 還沒有實戰 DPS，略過這項檢查')

        print('6. 面板')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto('http://127.0.0.1:8787/'); await dash.wait_for_timeout(1500)
        await dash.click('nav button[data-tab="maps"]'); await dash.wait_for_timeout(2500)
        txt = await dash.inner_text('#bossCard')
        tbl = await dash.inner_text('#bossGrid')
        check('蘑菇王' in tbl and ('稍後' in tbl or '太久' in tbl), '面板總表顯示王的狀態：' + tbl.replace('\n', ' ')[:80])
        check('蘑菇王' in txt, '面板列出勾選的王')
        await dash.screenshot(path='/tmp/boss.png', full_page=False)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
