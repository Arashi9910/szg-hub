"""輪流打野王：回報王的狀態 → 試跑只記錄 → 自動出發打死王、到王的地圖套用自動販售、回原本的地圖 →
打很久的王：血量有在掉就一直打（不會時間到被拉走），血量不降才先回去、血量保留、30 分鐘內不再去"""
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
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'chars': {'c3': True}, 'mobs': None, 'estMax': 15}})
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
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss1'], 'estMax': 15, 'presetBoss': 2, 'presetTrain': 0,
            'sell': {'on': True}, 'sellMaps': {'gms104000400': {'enabled': True, 'itemIds': [1082149]}}}})
        hub_json('POST', '/api/boss/run-now')
        jobs = [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']
        check(len(jobs) == 1 and jobs[0]['batches'][0]['boss']['mob'] == 'mBoss1', '建立 1 個打紅寶王的工作')
        done = await wait(lambda: next((j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss' and j['status'] in ('done', 'failed')), None), 90)
        check(done and done['status'] == 'done', '工作完成' + ('' if done and done['status'] == 'done' else f"：{done and done['lastMsg']}"))
        _, b = boss_char('c3')
        check(any('打死了' in l['msg'] for l in b['log']), '紀錄有「打死了」')
        c = mock_char('A2', 'c3')
        check(c['map'] == home, f'回到原本的地圖（{c["map"]}）')
        check(c['autoSell']['maps'].get('gms104000400') == {'enabled': True, 'itemIds': [1082149]}, f"到王的地圖套用了掉落篩選（{c['autoSell']['maps'].get('gms104000400')}）")
        check(any('自動販售 1 項' in (l['msg'] if isinstance(l, dict) else str(l)) for l in done['log']), '工作紀錄寫「自動販售 1 項」')
        check(c['auto'], '回去後有重新開始掛機（真實遊戲換地圖會停止掛機）')
        pl = [(x['n'], x['map']) for x in c.get('presetLog', [])]
        check(pl == [(2, 'gms104000400'), (1, home)], f'到首領地圖換掛機設定 2、回練功圖換回出發前的設定 1（{pl}）')
        check(c.get('settingsSlot') == 1, '最後是設定 1')
        c3, _ = boss_char('c3')
        r1 = next(r for r in c3['rows'] if r['mob'] == 'mBoss1')
        check(r1['cooling'] and r1['remainMs'] > 50 * 60 * 1000, '紅寶王變成冷卻中（約 60 分鐘後重生）')
        hub_json('POST', '/api/boss/run-now')
        check(len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']) == 1, '冷卻中不會再派')

        print('4. 打很久的王：血量有在掉就打下去（不會被時間到拉走），血量不降才先回去')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss2'], 'estMax': 100000, 'stuckMin': 1, 'maxMin': 30, 'sell': {'on': False}}})
        hub_json('POST', '/api/boss/run-now')
        lv = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None), None), 40)
        check(lv and lv['mob'] == 'mBoss2', '打王中：即時血量有回報' + (f"（{lv['hp']:,}）" if lv else ''))
        c = mock_char('A2', 'c3')
        check(c['map'] == 'gms100000005' and c['auto'], '到了首領地圖有開始掛機')
        lv2 = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g['hp'] is not None and g['hp'] < lv['hp']), None), 20)
        check(lv2, '血量持續更新（幾秒內就變少）')
        eta = await wait(lambda: next((g for g in hub_json('GET', '/api/boss')['live'] if g.get('etaSec') is not None), None), 25)
        check(eta, '算得出預估還要多久' + (f"（{eta['etaSec']:,} 秒）" if eta else ''))
        j0 = next(j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss' and j['batches'][0]['boss']['mob'] == 'mBoss2')
        check(j0['batches'][0]['boss'].get('stuckMin') == 1 and j0['batches'][0]['boss'].get('maxMin') == 30 and j0['batches'][0]['boss'].get('sell') is None, '工作帶著「血量沒降幾分鐘就離開」、安全上限；掉落篩選關著就不動遊戲設定')
        await asyncio.sleep(70)   # 超過舊版的「每次最多打 1 分鐘」
        d = hub_json('GET', '/api/data'); t = d['tabs'].get('c3')
        check(t and d['now'] - t['at'] < 25000, f"打王中分頁有報到，中控不會以為分頁不見（{round((d['now'] - t['at']) / 1000) if t else '無'} 秒前）")
        j1 = next(j for j in d['jobs'] if j['id'] == j0['id'])
        check(j1['status'] in ('approved', 'running') and mock_char('A2', 'c3')['map'] == 'gms100000005', '打了 1 分多鐘血量還在掉：繼續打，沒有離開')
        http('GET', MOCK + '/__mock/bossdps?v=0')   # 王打不動了
        done = await wait(lambda: next((j for j in hub_json('GET', '/api/data')['jobs'] if j['id'] == j0['id'] and j['status'] in ('done', 'failed')), None), 150)
        http('GET', MOCK + '/__mock/bossdps?v=')
        check(done and done['status'] == 'done', '血量 1 分鐘沒降 → 工作結束')
        _, b = boss_char('c3')
        check(any('蘑菇王' in l['msg'] and '血量都沒有下降' in l['msg'] for l in b['log']), '紀錄有「1 分鐘內血量都沒有下降，先放棄」')
        check(mock_char('A2', 'c3')['map'] == home and mock_char('A2', 'c3')['auto'], '回到原本的地圖並在掛機')
        c3, _ = boss_char('c3')
        r2 = next(r for r in c3['rows'] if r['mob'] == 'mBoss2')
        check(r2['hpKnown'] and r2['hp'] < r2['maxHp'], f"記住剩下的血量（{r2['hp']:,} / {r2['maxHp']:,}）")
        check('再試' in r2['skip'], '30 分鐘內不再去：' + r2['skip'])
        hub_json('POST', '/api/boss/run-now')
        check(len([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'boss']) == 2, '沒有馬上再派')

        print('5. 預估太久的王不去')
        hub_json('POST', '/api/settings', {'boss': {'mode': 'auto', 'chars': {'c3': True}, 'mobs': ['mBoss2'], 'estMax': 15}})
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
        check(await dash.inner_text('nav button[data-tab="maps"]') == '野王', '分頁名稱是「野王」')
        brd = await dash.inner_text('#bossBoard')
        check('蘑菇王' in brd and '紅寶王' in brd, '依王看：每隻王一張卡片')
        mush = await dash.inner_text('.bb[data-bbmob="mBoss2"]')
        check('弓箭分身' in mush and ('稍後' in mush or '太久' in mush or '暫不去' in mush), '蘑菇王卡片：誰打、狀態：' + mush.replace('\n', ' ')[:90])
        red = await dash.inner_text('.bb[data-bbmob="mBoss1"]')
        check('沒人打' in red and '＋ 加角色' in red, '紅寶王（沒勾）卡片顯示「沒人打」、可以加角色：' + red.replace('\n', ' ')[:80])
        await dash.click('#bossSetOpen'); await dash.wait_for_timeout(500)
        check(await dash.is_visible('#bossSetDrawer') and await dash.input_value('#bossStuck') == '3', '⚙ 設定抽屜：血量幾分鐘沒降就離開（預設 3）')
        await dash.keyboard.press('Escape'); await dash.wait_for_timeout(300)
        check(not await dash.is_visible('#bossSetDrawer'), 'Esc 關掉抽屜')
        await dash.screenshot(path='/tmp/boss.png', full_page=False)
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-30:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
