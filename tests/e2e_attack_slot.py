"""攻擊格（設定技能 1、2、3）：中控送 attackSlot 進遊戲（技能 1＝active＋持續施放、技能 2、3＝attackSlots），讀回確認；
角色不在那張地圖要失敗；技能 2、3 設「無」會清掉；不合格的指令中控擋掉"""
import asyncio, json, os, sys, time
import harness
from harness import Env, hub_json, http, HUB, MOCK

# attackSlot 要 v0.81.0 以上的腳本（server.js NEW_CFG_081）；正式發佈前 version.json 可能還是舊版號，
# 測試用的中控副本把版本號補到 0.81.0，讓遊戲分頁的腳本夠新（只改 /tmp/hub 的副本）
_prep = harness.prepare_hub
def _prep_bump(fresh=True):
    _prep(fresh)
    p = os.path.join(harness.HUB_DIR, 'version.json'); v = json.load(open(p, encoding='utf-8'))
    if tuple(map(int, v['version'].split('.'))) < (0, 81, 0):
        v['version'] = '0.81.0'; json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
harness.prepare_hub = _prep_bump

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
def hub_char(c): return (hub_json('GET', '/api/data')['chars'].get(c) or {}).get('char') or {}
def idle_jobs(word): return [x for x in hub_json('GET', '/api/data')['jobs'] if x['kind'] == 'idle' and word in json.dumps(x, ensure_ascii=False)]
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        try: v = fn()
        except Exception: v = None
        if v: return v
        await asyncio.sleep(step)
    return None
def slot_cmd(slot, skill, targets=None, **kw): return {'type': 'attackSlot', 'slot': slot, 'skill': skill, 'targets': targets or [], **kw}
def idle(cmd, label): return http('POST', HUB + '/api/idle', {'targets': [{'charId': 'c1', 'action': 'cfg', 'cmd': cmd, 'label': label}]})

async def main():
    async with Env() as env:
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        c = await wait(lambda: (lambda x: x if x.get('idleCfg') and x.get('prog') else None)(hub_char('c1')), 40)
        check(c and c['map'] == 'gms104040000' and c['prog']['active'] == 's1001004' and c['idleCfg']['continuousAttack'] is False,
              f'中控收到角色目前地圖、技能 1（active）、持續施放（{c and (c["map"], c["prog"]["active"], c["idleCfg"]["continuousAttack"])}）')

        print('1. 中控擋掉不合格的攻擊格指令')
        for bad, why in [(slot_cmd(3, 's1001004'), '第 4 格'), (slot_cmd(0, None), '技能 1 設成無'), (slot_cmd(1, 's1001004', ['m%d' % i for i in range(31)]), '指定 31 隻怪'),
                         ({'type': 'attackSlot', 'slot': 1, 'skill': 's1001004', 'targets': 'm1210101'}, 'targets 不是陣列'), (slot_cmd(1, 's1001004', [5]), '怪物 id 不是字串'),
                         (slot_cmd(1, 's 1'), '技能 id 不合格'), (slot_cmd(1, 's1001004', map='a b'), '地圖 id 不合格')]:
            s, body = idle(bad, 'x')
            check(s >= 400, f'擋掉{why}（{s}）')

        print('2. 一次送技能 1、2、3')
        s, body = http('POST', HUB + '/api/idle', {'targets': [
            {'charId': 'c1', 'action': 'cfg', 'cmd': slot_cmd(0, 'basic', continuous=True), 'label': '技能 1：普通攻擊'},
            {'charId': 'c1', 'action': 'cfg', 'cmd': slot_cmd(1, 's1001004', ['m1210101'], map='gms104040000'), 'label': '技能 2：強力攻擊'},
            {'charId': 'c1', 'action': 'cfg', 'cmd': slot_cmd(2, 's1001004'), 'label': '技能 3：強力攻擊'}]})
        check(s == 200, f'送出（{s} {body[:120]}）')
        jb = [x for x in hub_json('GET', '/api/data')['jobs'] if x['kind'] == 'idle' and '技能 1：普通攻擊' in json.dumps(x, ensure_ascii=False)]
        check(jb and jb[-1].get('minAgent') == '0.81.0', f'工作要求 v0.81.0 以上的腳本（{jb and jb[-1].get("minAgent")}）')
        cmds = [t['cmd'] for t in (jb[-1]['batches'][0]['targets'] if jb else [])]
        check(cmds and cmds[0] == {'type': 'attackSlot', 'slot': 0, 'skill': 'basic', 'targets': [], 'continuous': True} and 'continuous' not in cmds[1] and cmds[1]['map'] == 'gms104040000',
              f'中控整理後的指令格式（{cmds}）')
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] in ('done', 'failed', 'error') else None)(idle_jobs('技能 1：普通攻擊')), 50)
        check(j and j['status'] == 'done', f'工作完成（{j and (j["status"], j.get("lastMsg"))}）')
        m = mock_char('A1', 'c1')
        check(m['active'] == 'basic' and m['continuousAttack'] is True, f'遊戲裡技能 1＝普通攻擊、持續施放開啟（{m["active"]}, {m["continuousAttack"]}）')
        check(m['attackSlots'][1] == {'skill': 's1001004', 'targets': ['m1210101'], 'map': 'gms104040000'}, f'遊戲裡技能 2＝強力攻擊、指定怪物 m1210101（{m["attackSlots"]}）')
        check(m['attackSlots'][2] == {'skill': 's1001004', 'targets': [], 'map': 'gms104040000'}, '遊戲裡技能 3：沒帶地圖 → 用角色目前的地圖、全部怪物')
        c = await wait(lambda: (lambda x: x if x.get('prog', {}).get('active') == 'basic' and len(x['idleCfg']['attackSlots']) >= 3 else None)(hub_char('c1')), 30)
        check(c and c['idleCfg']['continuousAttack'] is True and c['idleCfg']['attackSlots'][1]['targets'] == ['m1210101'] and c['idleCfg']['attackSlots'][2]['skill'] == 's1001004',
              f'中控讀回 active／continuousAttack／attackSlots（{c and c["idleCfg"]["attackSlots"]}）')

        print('3. 技能 3 設「無」→ 清掉')
        idle(slot_cmd(2, None, ['m1210101']), '技能 3：無')
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] in ('done', 'failed', 'error') else None)(idle_jobs('技能 3：無')), 50)
        m = mock_char('A1', 'c1')
        check(j and j['status'] == 'done' and m['attackSlots'][2] is None and m['attackSlots'][1]['skill'] == 's1001004', f'遊戲裡技能 3 清掉、技能 2 不動（{m["attackSlots"]}）')
        c = await wait(lambda: (lambda x: x if x['idleCfg']['attackSlots'][2] is None else None)(hub_char('c1')), 30)
        check(c, '中控讀回技能 3 是空的')

        print('4. 角色不在那張地圖 → 失敗、遊戲不變')
        idle(slot_cmd(1, 's1001004', ['m100100'], map='gms100010000'), '技能 2：別張圖')
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] in ('done', 'failed', 'error') else None)(idle_jobs('技能 2：別張圖')), 50)
        txt = json.dumps(j, ensure_ascii=False) if j else ''
        check(j and j['status'] != 'done' and '角色已不在那張地圖' in txt, f'工作回報失敗訊息（{j and (j["status"], j.get("lastMsg"))}）')
        check(mock_char('A1', 'c1')['attackSlots'][1]['targets'] == ['m1210101'], '遊戲裡技能 2 沒被改')

        print('5. 遊戲擋掉的（地圖沒有這隻怪）→ 失敗')
        idle(slot_cmd(1, 's1001004', ['m100100']), '技能 2：不在地圖的怪')
        j = await wait(lambda: (lambda js: js[-1] if js and js[-1]['status'] in ('done', 'failed', 'error') else None)(idle_jobs('技能 2：不在地圖的怪')), 50)
        check(j and j['status'] != 'done' and '這張地圖沒有這隻怪物' in json.dumps(j, ensure_ascii=False), f'回報遊戲的錯誤（{j and j.get("lastMsg")}）')
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
