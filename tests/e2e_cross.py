"""十字獵人（v0.82）：一鍵接取（等級不夠的不接、遊戲擋下來的錯誤原樣記下）、自動狩獵（移到目標地圖、_noboss 優先、mapPref 覆蓋）、
擊殺數到了自動領獎、換下一張、全部完成變 done；副本中的角色 blocked 不會被拉走；GET /api/cross 的欄位"""
import asyncio, json, os, sys, time, urllib.parse
import harness
from harness import Env, hub_json, http, HUB, MOCK

# 自動循環 3 秒一次（正式 30 秒）
os.environ['SZG_CROSS_TICK_MS'] = '3000'
# questAccept／questClaim 要 v0.82.0 以上的腳本（server.js NEW_CFG_082）；發佈前 version.json 可能還是舊版號，測試用的中控副本補到 0.82.0
_prep = harness.prepare_hub
def _prep_bump(fresh=True):
    _prep(fresh)
    p = os.path.join(harness.HUB_DIR, 'version.json'); v = json.load(open(p, encoding='utf-8'))
    if tuple(map(int, v['version'].split('.'))) < (0, 82, 0):
        v['version'] = '0.82.0'; json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
harness.prepare_hub = _prep_bump

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
ACC = {'c1': 'A1', 'c2': 'A1', 'c3': 'A2', 'c4': 'A3'}
def mock_char(c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][ACC[c]]['chars'][c]
def cross(): return hub_json('GET', '/api/cross')
def row(c): return next((x for x in cross()['chars'] if x['id'] == c), None)
def set_count(c, q, n): return http('GET', f'{MOCK}/__mock/quest?acct={ACC[c]}&char={c}&quest={q}&count={n}')
def cross_jobs(c): return [j for j in hub_json('GET', '/api/data')['jobs'] if j.get('cross') and any(t.get('charId') == c for t in (j['batches'][0].get('targets') or []))]
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        try: v = fn()
        except Exception: v = None
        if v: return v
        await asyncio.sleep(step)
    return None
Q20, Q30, Q40, Q120 = 'cross_m5200000', 'cross_m1210100', 'cross_m1210101', 'cross_m100100'

async def main():
    async with Env() as env:
        await env.open_account('A1'); await env.open_account('A1', 'c2'); await env.open_accounts(['A2', 'A3'])
        d = await wait(lambda: (lambda ch: ch if all((ch.get(c) or {}).get('char', {}).get('cross') is not None for c in ACC) else None)(hub_json('GET', '/api/data')['chars']), 60)
        check(d, '四隻角色都回報 char.cross')
        check(d and d['c1']['char']['cross'] == {'quests': {}, 'coins': 0, 'exchanged': 0}, f'char.cross 格式（{d and d["c1"]["char"]["cross"]}）')
        await wait(lambda: cross()['quests'], 40)

        print('1. GET /api/cross')
        v = cross()
        qs = {q['id']: q for q in v['quests']}
        check(sorted(qs) == sorted([Q20, Q30, Q40, Q120]), f'只列 group cross 的任務（{sorted(qs)}）')
        q = qs.get(Q20) or {}
        check(q.get('name') == '幼小石球懸賞標示牌' and q.get('level') == 20 and q.get('mob') == 'm5200000' and q.get('mobName') == '幼小石球' and q.get('count') == 20,
              f'任務欄位（{ {k: q.get(k) for k in ("name", "level", "mob", "mobName", "count")} }）')
        check(sorted(m['id'] for m in q.get('maps', [])) == ['gms101030404', 'gms101030404_noboss'] and any(m['noboss'] for m in q['maps']), f'怪物所在的地圖含 _noboss 版（{q.get("maps")}）')
        check(q.get('defaultMap') == 'gms101030404_noboss', f'預設地圖＝無 BOSS 版（{q.get("defaultMap")}）')
        check(qs.get(Q40, {}).get('defaultMap') == 'gms104040000', f'沒有無 BOSS 版＝第一張（{qs.get(Q40, {}).get("defaultMap")}）')
        check(v['cfg'] == {'enabled': False, 'ids': [], 'order': 'low', 'mapPref': {}, 'skip': []}, f'預設設定（{v["cfg"]}）')
        check(len(v['exchange']) == 4 and v['exchange'][1] == {'tier': 1, 'key': 'drop_1112677', 'price': 10}, f'十字硬幣兌換表（{v["exchange"][:2]}）')
        r1 = row('c1')
        need = {'id', 'name', 'lv', 'map', 'mapName', 'coins', 'exchanged', 'quests', 'target', 'state', 'why'}
        check(r1 and need <= set(r1), f'角色欄位（少了 {need - set(r1 or {})}）')
        check(r1 and r1['state'] == 'idle' and r1['canAccept'] == [Q20, Q30, Q40], f'c1 Lv45 能接 3 張（{r1 and (r1["state"], r1["canAccept"], r1["why"])}）')

        print('2. 遊戲擋下來的接取：錯誤原樣記下，不重試')
        http('GET', MOCK + '/__mock/quest?fail=' + urllib.parse.quote('同時進行的任務已達上限'))
        s, b = http('POST', HUB + '/api/cross/accept', {'ids': ['c3'], 'quests': [Q20]})
        check(s == 200 and json.loads(b)['chars'][0]['n'] == 1, f'送出（{s} {b[:160]}）')
        r3 = await wait(lambda: (lambda r: r if r['errors'].get(Q20) else None)(row('c3')), 40)
        check(r3 and '同時進行的任務已達上限' in r3['errors'][Q20], f'c3 的 errors 有遊戲的訊息（{r3 and r3["errors"]}）')
        check(any('同時進行的任務已達上限' in x['msg'] for x in cross()['log']), '紀錄有遊戲的訊息')
        check(not mock_char('c3')['quests'], '遊戲裡沒有接到')

        print('3. 一鍵接取：等級不夠的不接')
        s, b = http('POST', HUB + '/api/cross/accept', {'ids': ['c1', 'c2', 'c3']})
        res = {x['id']: x for x in json.loads(b)['chars']} if s == 200 else {}
        check(res.get('c1', {}).get('n') == 3 and res.get('c3', {}).get('n') == 2 and res.get('c2', {}).get('n') == 0, f'c1 接 3 張、c3（Lv32）2 張、c2（Lv12）不接（{res}）')
        jb = cross_jobs('c1')
        check(jb and jb[-1].get('minAgent') == '0.82.0' and [t['cmd'] for t in jb[-1]['batches'][0]['targets']][0] == {'type': 'questAccept', 'quest': Q20}, f'工作格式＋要求 v0.82.0（{jb and (jb[-1].get("minAgent"), jb[-1]["batches"][0]["targets"][0]["cmd"])}）')
        m1 = await wait(lambda: (lambda c: c if len(c['quests']) == 3 else None)(mock_char('c1')), 40)
        check(m1 and set(m1['quests']) == {Q20, Q30, Q40} and all(x == {'count': 0, 'claimed': False} for x in m1['quests'].values()), f'遊戲裡 c1 接了 3 張（{m1 and m1["quests"]}）')
        m3 = await wait(lambda: (lambda c: c if len(c['quests']) == 2 else None)(mock_char('c3')), 40)
        check(m3 and set(m3['quests']) == {Q20, Q30}, f'遊戲裡 c3 接了 Lv20、Lv30（{m3 and m3["quests"]}）')
        check(not mock_char('c2')['quests'], 'c2 沒有接')
        r1 = await wait(lambda: (lambda r: r if len(r['quests']) == 3 and not r['canAccept'] and '等遊戲回報' not in r['why'] else None)(row('c1')), 40)  # 接取的工作結果回來了
        check(r1 and r1['target'] and r1['target']['quest'] == Q20 and r1['target']['map'] == 'gms101030404_noboss', f'c1 的目標＝等級最低的那張、無 BOSS 地圖（{r1 and r1["target"]}）')
        s, b = http('POST', HUB + '/api/cross/accept', {'ids': ['c1']})
        check('沒有可以接的' in b, f'再按一次：沒有可以接的（{b[:120]}）')

        print('4. 啟用自動：移到目標地圖（無 BOSS 版）並掛機')
        # c4 先模擬「副本戰鬥中」
        live = lambda: http('POST', HUB + '/api/raid/live', {'charId': 'c4', 'inRaid': True, 'battle': {'code': 'T1', 'raid': 'papulatus', 'phase': 1}, 'team': {}, 'enemies': [], 'me': {}})
        live()
        s, b = http('POST', HUB + '/api/cross/cfg', {'enabled': True, 'ids': ['c1', 'c4'], 'order': 'low'})
        check(s == 200 and json.loads(b)['cfg']['enabled'] is True, f'存設定（{b[:160]}）')
        m1 = await wait(lambda: (lambda c: c if c['map'] == 'gms101030404_noboss' and c['auto'] else None)(mock_char('c1')), 50)
        check(m1, f'c1 被移到東方岩石山〈5〉（無BOSS）並開始掛機（{mock_char("c1")["map"]}）')
        r1 = await wait(lambda: (lambda r: r if r['state'] == 'hunting' else None)(row('c1')), 30)
        check(r1, f'c1 state hunting（{row("c1")["state"]} {row("c1")["why"]}）')

        print('5. 副本中的角色：blocked、不會被拉走')
        for _ in range(4):
            live(); await asyncio.sleep(2)
        r4 = row('c4')
        check(r4 and r4['state'] == 'blocked' and '副本' in r4['why'], f'c4 blocked（{r4 and (r4["state"], r4["why"])}）')
        check(not cross_jobs('c4') and not mock_char('c4')['quests'] and mock_char('c4')['map'] == 'gms100010000', 'c4 沒有被送任何工作')

        print('6. 擊殺數到了 → 自動領獎 → 換下一張')
        set_count('c1', Q20, 20)
        m1 = await wait(lambda: (lambda c: c if c['quests'][Q20]['claimed'] else None)(mock_char('c1')), 40)
        check(m1 and m1['inventory'].get('i4310029') == 1, f'遊戲裡領了、十字硬幣 1 個（{m1 and m1["inventory"].get("i4310029")}）')
        m1 = await wait(lambda: (lambda c: c if c['map'] == 'gms100010000' else None)(mock_char('c1')), 50)
        check(m1, f'換下一張：c1 移到弓箭手村北邊山丘（綠水靈）（{mock_char("c1")["map"]}）')
        r1 = await wait(lambda: (lambda r: r if r['coins'] == 1 and r['target'] and r['target']['quest'] == Q30 else None)(row('c1')), 30)
        check(r1, f'中控：硬幣 1、目標換成綠水靈（{row("c1")["coins"]}, {row("c1")["target"]}）')

        print('7. mapPref 覆蓋預設地圖；副本結束後 c4 自動接取、移過去')
        http('POST', HUB + '/api/cross/cfg', {'mapPref': {Q20: 'gms101030404'}})
        check(next(q for q in cross()['quests'] if q['id'] == Q20)['defaultMap'] == 'gms101030404', 'mapPref 改了預設地圖')
        m4 = await wait(lambda: (lambda c: c if c['quests'].get(Q20) and c['map'] == 'gms101030404' else None)(mock_char('c4')), 70)
        check(m4, f'c4（Lv20）自動接了幼小石球並移到東方岩石山〈5〉（{mock_char("c4")["quests"]}, {mock_char("c4")["map"]}）')

        print('8. 剩下的一起完成 → done')
        set_count('c1', Q30, 20); set_count('c1', Q40, 20)
        m1 = await wait(lambda: (lambda c: c if c['quests'][Q30]['claimed'] and c['quests'][Q40]['claimed'] else None)(mock_char('c1')), 50)
        check(m1 and m1['inventory'].get('i4310029') == 3, f'遊戲裡 3 張都領了、硬幣 3（{m1 and m1["inventory"].get("i4310029")}）')
        r1 = await wait(lambda: (lambda r: r if r['state'] == 'done' else None)(row('c1')), 40)
        check(r1 and '等級不夠' in r1['why'] and r1['target'] is None, f'c1 done（{r1 and r1["why"]}）')
        check(any('領取' in x['msg'] and x['charId'] == 'c1' for x in cross()['log']), '紀錄有領取')
        n = len(cross_jobs('c1')); await asyncio.sleep(8)
        check(len(cross_jobs('c1')) == n, 'done 之後不再送工作')

        print('9. 關閉自動、不合格的指令')
        http('POST', HUB + '/api/cross/cfg', {'enabled': False})
        check(cross()['cfg']['enabled'] is False and cross()['cfg']['mapPref'] == {Q20: 'gms101030404'}, '關閉自動，其他設定保留')
        s, _ = http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': {'type': 'questAccept', 'quest': 'q_mock_main'}}]})
        check(s >= 400, f'不是 cross_ 開頭的任務擋掉（{s}）')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
