"""去處規則（dest.js）的計算：共用規則、王的掉落、地圖覆寫、公倉／強化、舊設定轉換（不用起模擬遊戲）"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(os.path.dirname(HERE), 'dest.js')
ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

JS = r"""
const D = require(process.argv[1]);
const world = {
  maps: [{ id: 'm1', msId: 1, boss: [] }, { id: 'bm', msId: 2, boss: ['boss1'] }],
  mobs: [{ id: 'boss1', msId: 9 }], drops: {}, mobDrops: { 9: [[4000016, 1, 1, 1000]] },
  names: { 2290001: ['技能書', '技能書'] },
  autoSellDrops: {
    m1: [[1082149, 'gear', '手套', 10, 1, '', []], [2040805, 'item', '卷軸', 5, 1, '', []], [4000016, 'item', '紅寶殼', 1, 1, '', []], [2290001, 'item', '技能書', 1, 1, '', []], [4031000, 'item', '不能賣', 0, 0, '', []]],
    bm: [[1082149, 'gear', '手套', 10, 1, '', ['m2']], [4000016, 'item', '紅寶殼', 1, 1, '', ['boss1']], [2040805, 'item', '卷軸', 5, 1, '', []]],
  },
};
const out = {};
const S0 = { dest: { board: true, boss: true } };
out.def = D.calc(world, S0, 'm1');
out.defSell = D.sellOf(world, S0, 'm1', 'board');
out.boss = D.sellOf(world, S0, 'bm', 'boss');
out.bossRule = D.sellOf(world, { dest: { board: true, boss: true, rule: { boss: 'rule', other: 'shop' } } }, 'bm', 'boss');
out.off = D.sellOf(world, { dest: { board: false, boss: true } }, 'm1', 'board');
out.game = D.sellOf(world, { dest: { board: true, over: { m1: { game: true } } } }, 'm1', 'board');
const S1 = { dest: { board: true, over: { m1: { items: { 1082149: 'keep', 2040805: 'shop' } } }, forge: [4000016] }, guildDep: { ids: [2290001], cats: [] } };
out.ov = D.calc(world, S1, 'm1');
out.ovSell = D.sellOf(world, S1, 'm1', 'board');
out.gcat = D.calc(world, { dest: { board: true }, guildDep: { cats: ['卷軸'] } }, 'm1');
out.rest = D.sellOf(world, { dest: { board: true, over: { m1: { items: { 4000016: 'shop' }, rest: 'keep' } } } }, 'm1', 'board');
out.mig = D.migrate({
  boss: { sell: { on: true, rule: { gear: 'sell', scroll: 'sell', other: 'keep', boss: 'rule' }, over: { bm: { itemIds: [1082149] } } } },
  board: { lanes: { train: ['m1', 'm9'], scroll: [], gear: [] }, sell: { m1: { enabled: true, itemIds: [4000016] } } },
  boards: { B: { lanes: { train: ['m8'] }, sell: { m8: { enabled: false, itemIds: [] } } } },
}, 1);
out.migEmpty = D.migrate({}, 1);
console.log(JSON.stringify(out));
"""

r = subprocess.run(['node', '-e', JS, DEST], capture_output=True, text=True)
if r.returncode:
    print(r.stderr); sys.exit(1)
o = json.loads(r.stdout)

print('1. 共用規則（預設：裝備、其他道具賣，卷軸、技能書留著）')
d = o['def']['dest']
check(d == {'1082149': 'shop', '2040805': 'bag', '4000016': 'shop', '2290001': 'bag', '4031000': 'bag'}, f'每樣的去處：{d}')
check(o['defSell'] == {'enabled': True, 'itemIds': [1082149, 4000016]}, f'送給遊戲的自動販售：{o["defSell"]}')
check(o['def']['cats']['2290001'] == 'book', '技能書分成自己一類')

print('2. 野王地圖：王會掉的東西一律留著（或照規則）')
check(o['boss'] == {'enabled': True, 'itemIds': [1082149]}, f'王會掉的紅寶殼留著：{o["boss"]}')
check(sorted(o['bossRule']['itemIds']) == [1082149, 4000016], f'改成照規則就一起賣：{o["bossRule"]}')

print('3. 沒開、沿用遊戲設定 → 不動遊戲')
check(o['off'] is None and o['game'] is None, '派工地圖沒開、或這張圖沿用遊戲設定 → null')

print('4. 地圖覆寫、公倉、強化')
d = o['ov']['dest']; f = o['ov']['from']
check(d['1082149'] == 'bag' and f['1082149'] == 'map', '這張圖把手套改成留著')
check(d['2040805'] == 'shop' and f['2040805'] == 'map', '這張圖把卷軸改成賣')
check(d['4000016'] == 'forge' and d['2290001'] == 'guild', '強化、公倉的指定（全部地圖共用）一律留著')
check(o['ovSell']['itemIds'] == [2040805], f'只賣卷軸：{o["ovSell"]}')
check(o['ov']['over'], '標成這張圖改過')
check(o['gcat']['dest']['2040805'] == 'guild', '公倉存入規則勾了整類卷軸 → 卷軸的去處是公倉')
check(o['rest']['itemIds'] == [4000016], f'舊版整張圖勾選（rest）：只有勾的賣，其他留著（{o["rest"]}）')

print('5. 舊設定轉換')
m = o['mig']
check(m['boss'] is True and m['board'] is True, '野王有開、派工有販售範本 → 兩邊都開')
check(m['rule'] == {'gear': 'shop', 'scroll': 'shop', 'book': 'keep', 'other': 'keep', 'boss': 'rule'}, f'共用規則照野王的轉：{m["rule"]}')
check(m['over']['bm'] == {'items': {'1082149': 'shop'}, 'rest': 'keep'}, '野王的個別調整 → 這張圖只賣原本勾的')
check(m['over']['m1'] == {'items': {'4000016': 'shop'}, 'rest': 'keep'}, '派工的販售範本 → 這張圖只賣原本勾的')
check(m['over']['m8'] == {'items': {}, 'rest': 'keep'}, '關掉的販售範本 → 全部留著（等於關掉自動販售）')
check(m['over']['m9'] == {'game': True}, '沒有販售範本的派工地圖 → 沿用遊戲設定（中控不會動）')
e = o['migEmpty']
check(e['board'] is False and e['boss'] is False and e['over'] == {}, '全新安裝：兩邊都關著')

print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)
