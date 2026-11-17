// 上漲谷模擬遊戲（測試用）：模擬 play.szg08.com 的 /game/ 頁面與 /api/account、/api/catalog、/api/game
// 啟動：node mockgame.js [port=9900]
// 帳號由 cookie `acct`（A1、A2…）決定；e2e 用 Playwright 把 https://play.szg08.com/** 轉到這裡並設好 cookie。
// 2026-11-18 對照真實遊戲：回應是整份狀態放最上層＋summary；公會倉庫格式已核對（實際存取 1 張卷軸）；
// 神匠之魂的請求參數已核對（讀遊戲程式碼），回應格式還沒實際看過。
'use strict';
const http = require('http');
const PORT = Number(process.argv[2]) || 9900;
const GAME_VERSION = '1';

// ---------------- 目錄 ----------------
const items = {
  i2000000: { id: 2000000, name: '紅色藥水', type: '消耗', sellPrice: 25 },
  i2000001: { id: 2000001, name: '橘色藥水', type: '消耗', sellPrice: 80 },
  i2000003: { id: 2000003, name: '藍色藥水', type: '消耗', sellPrice: 100 },
  i4000000: { id: 4000000, name: '嫩寶殼', type: '其他', sellPrice: 6 },
  i4000001: { id: 4000001, name: '綠水靈珠', type: '其他', sellPrice: 8 },
  i4000016: { id: 4000016, name: '紅寶殼', type: '其他', sellPrice: 12 },
  i4031052: { id: 4031052, name: '任務道具', type: '其他', sellPrice: 0 },
};
const scrolls = {
  i2040801: { id: 2040801, name: '手套攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'glove', stats: { incPAD: 2 }, sellPrice: 500 },
  i2040805: { id: 2040805, name: '手套攻擊卷軸 10%', type: '卷軸', rate: 10, target: 'glove', stats: { incPAD: 3 }, sellPrice: 500 },
  i2043001: { id: 2043001, name: '單手劍攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'oneHandedSword', stats: { incPAD: 2, incSTR: 1 }, sellPrice: 500 },
  i2044501: { id: 2044501, name: '弓攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'bow', stats: { incPAD: 2, incACC: 1 }, sellPrice: 500 },
};
for (const [k, s] of Object.entries(scrolls)) items[k] = { id: s.id, name: s.name, type: '卷軸', sellPrice: s.sellPrice };
const equipment = {
  e1082002: { itemId: 1082002, name: '工地手套', equipmentType: 'glove', type: { category: 'Armor' }, meta: { reqLevel: 10, reqJob: 0 }, base: { incPDD: 2 }, slots: 5 },
  e1082149: { itemId: 1082149, name: '褐色工作手套', equipmentType: 'glove', type: { category: 'Armor' }, meta: { reqLevel: 10, reqJob: 0 }, base: { incPDD: 5 }, slots: 7 },
  e1302000: { itemId: 1302000, name: '劍', equipmentType: 'oneHandedSword', type: { category: 'OneHandedWeapon' }, meta: { reqLevel: 0, reqJob: 1 }, base: { incPAD: 17 }, slots: 7 },
  e1452002: { itemId: 1452002, name: '戰鬥弓', equipmentType: 'bow', type: { category: 'TwoHandedWeapon' }, meta: { reqLevel: 10, reqJob: 4, reqDEX: 35 }, base: { incPAD: 28 }, slots: 7 },
  e1040002: { itemId: 1040002, name: '白色背心', equipmentType: 'top', type: { category: 'Armor' }, meta: { reqLevel: 0, reqJob: 0 }, base: { incPDD: 3 }, slots: 7 },
};
const jobs = {
  beginner: { name: '初心者', tier: 0 }, swordman: { name: '劍士', tier: 1 }, fighter: { name: '狂戰士', tier: 2, parent: 'swordman' },
  archer: { name: '弓箭手', tier: 1 }, hunter: { name: '獵人', tier: 2, parent: 'archer' },
  magician: { name: '法師', tier: 1 }, thief: { name: '盜賊', tier: 1 },
};
const mobs = [
  { id: 'm100100', msId: 100100, name: '嫩寶', lv: 1, hp: 8, xp: 3, money: 5, defense: 0 },
  { id: 'm1210100', msId: 1210100, name: '綠水靈', lv: 6, hp: 50, xp: 12, money: 20, defense: 2 },
  { id: 'm1210101', msId: 1210101, name: '紅寶', lv: 12, hp: 150, xp: 30, money: 45, defense: 5 },
];
const maps = {
  gms100010000: { id: 'gms100010000', msId: 100010000, name: '弓箭手村北邊山丘', region: '維多利亞島', minLevel: 1, mobIds: ['m100100', 'm1210100'] },
  gms104040000: { id: 'gms104040000', msId: 104040000, name: '射手訓練場', region: '維多利亞島', minLevel: 10, mobIds: ['m1210101'] },
  gms990040001: { id: 'gms990040001', msId: 990040001, name: '傷害測試場 1', region: '測試', minLevel: 1, mobIds: [] },
};
const drops = {
  m100100: [{ itemId: 4000000, min: 1, max: 1, chance: 600000 }, { itemId: 2000000, min: 1, max: 1, chance: 100000 }],
  m1210100: [{ itemId: 4000001, min: 1, max: 1, chance: 600000 }, { itemId: 2040801, min: 1, max: 1, chance: 20000 }, { itemId: 1082002, min: 1, max: 1, chance: 30000 }],
  m1210101: [{ itemId: 4000016, min: 1, max: 1, chance: 600000 }, { itemId: 2040805, min: 1, max: 1, chance: 15000 }, { itemId: 1082149, min: 1, max: 1, chance: 30000 }, { itemId: 1452002, min: 1, max: 1, chance: 10000 }],
};
const keyById = {};
for (const [k, v] of Object.entries(items)) keyById[v.id] = k;
for (const [k, v] of Object.entries(equipment)) keyById[v.itemId] = k;
const nameOf = id => { const k = keyById[id]; return k ? (items[k] || equipment[k]).name : String(id); };
function autoSellDropsFor(map) {
  const out = [], seen = new Set();
  for (const mid of map.mobIds) for (const d of drops[mid] || []) {
    if (seen.has(d.itemId)) continue; seen.add(d.itemId);
    const k = keyById[d.itemId]; const eq = equipment[k]; const it = items[k];
    out.push({ itemId: d.itemId, kind: eq ? 'equip' : 'item', name: nameOf(d.itemId), price: eq ? 100 : it.sellPrice, sellable: !(it && it.sellPrice === 0), category: eq ? '裝備' : it.type, monsters: [{ id: mid }] });
  }
  return out;
}
const catalog = {
  version: 'mock-1', dropScale: 1000000, items, scrolls, equipment, jobs, mobs, maps, drops, mapDrops: {},
  statNames: { incPAD: '物攻', incMAD: '魔攻', incSTR: '力量', incDEX: '敏捷', incINT: '智力', incLUK: '幸運', incPDD: '物防', incACC: '命中' },
  skills: [{ msId: 1001004, name: '強力攻擊', job: 'swordman', tier: 1, levels: [{ damage: 260 }] }],
  autoSellDrops: Object.fromEntries(Object.values(maps).map(m => [m.id, autoSellDropsFor(m)])),
  fourth: {},
};

// ---------------- 世界狀態 ----------------
const rnd = n => Math.floor(Math.random() * n);
let uidSeq = 1000;
const newUid = p => p + (++uidSeq);
// 掉落浮動：每個素質在標準值上下浮動（約 ±10%，至少 ±1），跟真實遊戲一樣記在 baseStats（標準）／cleanStats（掉落時）
function rollStats(base) {
  const out = {};
  for (const [k, v] of Object.entries(base)) { const r = Math.max(1, Math.round(v * 0.1)); out[k] = Math.max(0, v + rnd(2 * r + 1) - r); }
  return out;
}
function makeGear(key, extra = {}) {
  const e = equipment[key];
  const clean = rollStats(e.base);
  return { uid: newUid('g'), key, itemId: e.itemId, name: e.name, type: e.equipmentType, successes: 0, slots: e.slots, maxSlots: e.slots, locked: false,
    stats: { ...clean }, baseStats: { ...e.base }, cleanStats: clean, rollVersion: 1, ...extra };
}
function makeChar(id, name, job, lv, map, extra = {}) {
  return {
    id, name, job, lv, xp: 0, money: 500000, map, auto: false, until: null, hp: 500, maxhp: 500, mp: 300, maxmp: 300, kills: 0,
    stats: { incSTR: 40, incDEX: 40, incINT: 4, incLUK: 4 }, gear: {}, equipmentBag: [], warehouseGear: [], inventory: { i2000000: 200, i2000003: 100 },
    inventoryStacks: [], warehouse: {}, warehouseMesos: 0, supply: { hpItem: 'i2000000', mpItem: 'i2000003' }, autoSell: { maps: {} }, log: [], ...extra,
  };
}
const accounts = {};
function addAccount(acct, code, chars) {
  accounts[acct] = { acct, code, chars: Object.fromEntries(chars.map(c => [c.id, c])), active: chars[0].id };
}
addAccount('A1', 'A1B2C3D4E5F6', [
  makeChar('c1', '本尊劍士', 'fighter', 45, 'gms104040000', { money: 30000000, gear: { weapon: makeGear('e1302000') },
    inventory: { i2000000: 300, i2000003: 200, i2040801: 12, i2040805: 5, i2043001: 4 } }),
  makeChar('c2', '本尊小號', 'beginner', 8, 'gms100010000'),
]);
addAccount('A2', 'B2C3D4E5F6A1', [makeChar('c3', '弓箭分身', 'hunter', 32, 'gms104040000', { auto: true, until: Date.now() + 8 * 3600e3, gear: { weapon: makeGear('e1452002') } })]);
addAccount('A3', 'C3D4E5F6A1B2', [makeChar('c4', '倉庫分身', 'swordman', 20, 'gms100010000', { auto: true, until: Date.now() + 8 * 3600e3 })]);
// 每隻角色背包放幾件裝備、幾疊道具
for (const a of Object.values(accounts)) for (const c of Object.values(a.chars)) {
  c.equipmentBag.push(makeGear('e1082002'), makeGear('e1082002'), makeGear('e1082002'), makeGear('e1082149'), makeGear('e1082149'), makeGear('e1040002'));
  rebuildStacks(c);
}
const guild = { guildName: '測試公會', mesos: 0, cashPoints: 0, items: {}, gear: [], capacity: { gear: 500, items: 500 }, taxPercent: 5 };
const quotes = {};

function rebuildStacks(c) {
  const old = new Map((c.inventoryStacks || []).map(s => [s.key, s]));
  c.inventoryStacks = Object.entries(c.inventory).filter(([, q]) => q > 0).map(([key, qty]) => {
    const o = old.get(key); return { uid: o ? o.uid : newUid('s'), key, qty, locked: o ? o.locked : false };
  });
}
function addLog(c, t) { c.log.push({ time: Date.now() + c.log.length % 7, t }); if (c.log.length > 60) c.log.splice(0, c.log.length - 60); }

// 掛機模擬：每次同步依經過時間打怪、撿東西、自動販售
const events = {}; // charId → 最近一次的戰鬥事件
let eventSeq = 0;
function simulate(c, now) {
  const last = c._simAt || now; c._simAt = now;
  if (!c.auto || (c.until && now > c.until)) { if (c.auto && c.until && now > c.until) c.auto = false; return []; }
  const map = maps[c.map]; if (!map || !map.mobIds.length) return [];
  const evs = [];
  const swings = Math.min(20, Math.max(1, Math.round((now - last) / 1000)));
  for (let i = 0; i < swings; i++) {
    const mob = mobs.find(m => m.id === map.mobIds[rnd(map.mobIds.length)]);
    const dmg = 50 + rnd(150) + c.lv * 3; const killed = Math.random() < 0.5;
    evs.push({ eventId: 'ev' + (++eventSeq), actor: c.id, kind: 'attack', damage: dmg, effectiveDamage: Math.min(dmg, mob.hp), lines: [{ damage: dmg, critical: Math.random() < 0.1 }], skill: 1001004, mob: mob.id, killed, at: now - (swings - i) * 1000, map: c.map });
    if (!killed) continue;
    c.kills++; c.xp += mob.xp; c.money += mob.money;
    for (const d of drops[mob.id] || []) {
      if (rnd(1000000) >= d.chance * 20) continue; // 測試用：掉率放大 20 倍
      const key = keyById[d.itemId]; const name = nameOf(d.itemId);
      addLog(c, `撿取：${name} × 1`);
      const as = c.autoSell.maps[c.map];
      if (as && as.enabled && as.itemIds.includes(d.itemId)) {
        const price = equipment[key] ? 100 : items[key].sellPrice; c.money += price;
        addLog(c, `自動販售：${name} × 1，獲得 ${price.toLocaleString()} 楓幣`); continue;
      }
      if (equipment[key]) c.equipmentBag.push(makeGear(key)); else c.inventory[key] = (c.inventory[key] || 0) + 1;
    }
  }
  rebuildStacks(c);
  return evs;
}

// ---------------- 遊戲 API ----------------
const strip = c => { const { _simAt, ...rest } = c; return rest; };
function sessionView(a) {
  const c = a.chars[a.active];
  return { serverTime: Date.now(), character: strip(c), characters: Object.values(a.chars).map(x => ({ id: x.id, name: x.name, lv: x.lv, job: x.job, auto: x.auto })), party: null, knowledge: { ready: false, remaining: 0 } };
}
function tradeEligible(a) {
  const c = a.chars[a.active];
  return { items: Object.keys(c.inventory).filter(k => !k.startsWith('i4031')), gear: c.equipmentBag.map(g => g.uid) };
}
const fail = msg => { const e = new Error(msg); e.game = true; throw e; };
function gearList(c) { return [...Object.values(c.gear).filter(Boolean), ...c.equipmentBag]; }
function scrollOnce(c, g, key) {
  const sc = scrolls[key]; if (!sc) fail('不是卷軸');
  if (!(c.inventory[key] > 0)) fail('卷軸不足');
  if (g.slots <= 0) fail('沒有可衝次數');
  c.inventory[key]--; g.slots--;
  const ok = rnd(100) < sc.rate;
  if (ok) { g.successes++; for (const [s, v] of Object.entries(sc.stats)) g.stats[s] = (g.stats[s] || 0) + v; }
  return ok;
}
function guildView() { return JSON.parse(JSON.stringify(guild)); }

function handle(a, body) {
  const c = a.chars[body.characterId] || a.chars[a.active];
  if (body.type !== 'sync' && !body.requestId) fail('缺少操作識別碼');
  if (Math.random() < Number(process.env.BUSY_RATE || 0)) fail('存檔忙碌，請稍後重試');
  const now = Date.now();
  switch (body.type) {
    case 'sync': {
      let evs = [];
      for (const x of Object.values(a.chars)) evs = evs.concat(simulate(x, now));
      const res = { ...sessionView(a), summary: { events: evs }, tradeEligible: tradeEligible(a) };
      if (body.tradeOnly) res.trade = null;
      if (body.includeMarket) res.market = { products: [], hasMore: false, stall: { products: [], pending: 0, history: [] } };
      return res;
    }
    case 'start': c.auto = true; c.until = now + 24 * 3600e3; c._simAt = now; addLog(c, '開始掛機'); break;
    case 'stop': c.auto = false; addLog(c, '暫停掛機'); break;
    case 'map': if (!maps[body.map]) fail('沒有這張地圖'); c.map = body.map; addLog(c, '前往 ' + maps[body.map].name); break;
    case 'autoSell':
      if (body.map !== c.map) fail('只能設定角色目前所在地圖的自動販售');
      c.autoSell.maps[body.map] = { enabled: !!(body.config && body.config.enabled), itemIds: ((body.config && body.config.itemIds) || []).map(Number) };
      break;
    case 'switch': if (!a.chars[body.characterId]) fail('沒有這隻角色'); a.active = body.characterId; break;
    case 'inventoryLock': {
      const ids = new Set(body.ids || []);
      for (const s of c.inventoryStacks) if (ids.has(s.uid)) s.locked = !!body.locked;
      for (const g of c.equipmentBag) if (ids.has(g.uid)) g.locked = !!body.locked;
      break;
    }
    case 'inventoryQuote': {
      const ids = new Set(body.ids || []); const rows = [];
      if (body.category === 'equip') for (const g of c.equipmentBag) { if (ids.has(g.uid) && !g.locked) rows.push({ uid: g.uid, name: g.name, qty: 1, price: 100 }); }
      else for (const s of c.inventoryStacks) if (ids.has(s.uid) && !s.locked) rows.push({ uid: s.uid, key: s.key, name: items[s.key].name, qty: s.qty, price: items[s.key].sellPrice * s.qty });
      const q = { id: newUid('q'), rows, total: rows.reduce((t, r) => t + r.price, 0), charId: c.id };
      quotes[q.id] = q; return { ...sessionView(a), quote: q };
    }
    case 'inventorySell': {
      const q = quotes[body.quoteId]; if (!q || q.charId !== c.id) fail('報價已過期');
      delete quotes[body.quoteId];
      const ids = new Set(q.rows.map(r => r.uid));
      c.equipmentBag = c.equipmentBag.filter(g => !ids.has(g.uid));
      for (const s of c.inventoryStacks) if (ids.has(s.uid)) delete c.inventory[s.key];
      c.money += q.total; rebuildStacks(c); break;
    }
    case 'scroll': {
      const g = gearList(c).find(x => x.uid === body.uid); if (!g) fail('找不到裝備');
      const ok = scrollOnce(c, g, body.item); rebuildStacks(c);
      return { ...sessionView(a), summary: { events: [], scroll: { success: ok, uid: g.uid } } };
    }
    case 'artisanScroll': {
      // 真實遊戲：每衝 1 次扣 1 張卷軸＋10 萬楓幣；單件 {uid}，多件 {uids: 2～10}；expectedSlots = 選裝時的剩餘格數
      // 回應格式未確認（沒有實際衝過），這裡把結果放在 summary.artisan
      const FEE = 100000;
      const uids = body.uids || (body.uid ? [body.uid] : []);
      if (!uids.length || uids.length > 10 || (body.uids && uids.length < 2)) fail('單件用 uid，多選 2～10 件用 uids');
      const count = Math.min(10, Math.max(1, Number(body.count) || 1));
      if (!scrolls[body.item]) fail('不是卷軸');
      const results = [];
      for (const uid of uids) {
        const g = gearList(c).find(x => x.uid === uid);
        if (!g) { results.push({ uid, error: '找不到裝備' }); continue; }
        if (scrolls[body.item].target !== g.type) { results.push({ uid, error: '卷軸不適用這件裝備' }); continue; }
        if (body.expectedSlots != null && body.expectedSlots !== g.slots) { results.push({ uid, error: '可衝次數和選裝時不同' }); continue; }
        let tries = 0, ok = 0;
        while (tries < count && g.slots > 0 && (c.inventory[body.item] || 0) > 0 && c.money >= FEE) {
          tries++; c.money -= FEE; const r = scrollOnce(c, g, body.item); if (r) ok++;
          if (body.stopAfterSuccesses && ok >= body.stopAfterSuccesses) break;
          if (body.stopOnFail && !r) break;
        }
        results.push({ uid, name: g.name, attempts: tries, successes: ok, slotsLeft: g.slots, stats: { ...g.stats } });
      }
      rebuildStacks(c);
      addLog(c, `神匠之魂：衝了 ${results.reduce((t, r) => t + (r.attempts || 0), 0)} 次`);
      return { ...sessionView(a), summary: { events: [], artisan: { results } } };
    }
    case 'guildWarehouseView': return { ...sessionView(a), summary: { events: [], guildWarehouse: guildView() } };
    case 'guildWarehouseMesos': case 'guildWarehouseCash': fail('測試不碰楓幣／點數');
    case 'guildWarehouseBatch': {
      const list = body.items || []; if (list.length > 100) fail('一次最多 100 項');
      for (const it of list) {
        if (body.op === 'deposit') {
          if (it.kind === 'gear') {
            const i = c.equipmentBag.findIndex(g => g.uid === it.uid); if (i < 0) fail('找不到裝備');
            if (c.equipmentBag[i].locked) fail('鎖定的裝備不能存入');
            if (guild.gear.length >= guild.capacity.gear) fail('公會倉庫裝備欄已滿');
            guild.gear.push(c.equipmentBag.splice(i, 1)[0]); continue;
          }
          const have = c.inventory[it.item] || 0; if (have < it.qty) fail('數量不足：' + it.item);
          if (!guild.items[it.item] && Object.keys(guild.items).length >= guild.capacity.items) fail('公會倉庫道具欄已滿');
          if (!tradeEligible(a).items.includes(it.item)) fail('不可交易的道具不能存入');
          c.inventory[it.item] = have - it.qty; guild.items[it.item] = (guild.items[it.item] || 0) + it.qty;
        } else if (body.op === 'withdraw') {
          if (it.kind === 'gear') { const i = guild.gear.findIndex(g => g.uid === it.uid); if (i < 0) fail('公會倉庫沒有這件'); c.equipmentBag.push(guild.gear.splice(i, 1)[0]); continue; }
          const have = guild.items[it.item] || 0; if (have < it.qty) fail('公會倉庫數量不足');
          guild.items[it.item] = have - it.qty; if (!guild.items[it.item]) delete guild.items[it.item];
          c.inventory[it.item] = (c.inventory[it.item] || 0) + it.qty;
        } else fail('不明的操作');
      }
      rebuildStacks(c);
      return { ...sessionView(a), summary: { events: [], guildWarehouse: guildView() } };
    }
    default: fail('模擬遊戲沒有實作：' + body.type);
  }
  rebuildStacks(c);
  return { ...sessionView(a), summary: { events: [] } };
}

// ---------------- 頁面 ----------------
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>上漲谷（模擬）</title></head><body>
<h3>上漲谷模擬遊戲</h3><div id="who"></div><pre id="st"></pre>
<script>
// 模擬遊戲的 client-update.js：所有 /api/game 請求補上版本標頭
(function(){ const f = window.fetch; window.fetch = function(input, init){ init = init || {}; const u = String((input && input.url) || input);
  if (u.includes('/api/game')) { init.headers = Object.assign({}, init.headers || {}, { 'X-Game-Version': '${GAME_VERSION}' }); } return f.call(this, input, init); }; })();
async function sync(){
  const r = await fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'sync', characterId: sessionStorage.getItem('mapleCharacter') }) });
  const j = await r.json(); if (!j.character) return;
  sessionStorage.setItem('mapleCharacter', j.character.id);
  sessionStorage.setItem('mapleSessionView', JSON.stringify({ state: j }));
  document.getElementById('who').textContent = j.character.name + ' Lv' + j.character.lv + ' 楓幣 ' + j.character.money.toLocaleString();
  document.getElementById('st').textContent = 'EXP ' + j.character.xp + ' [12.50%]\\n平均每小時經驗 120,000\\n你的遊戲 ID：' + (window.__code || '');
}
fetch('/api/account').then(r => r.json()).then(a => { window.__code = a.playerCode; if (!sessionStorage.getItem('mapleCharacter')) sessionStorage.setItem('mapleCharacter', a.activeCharacterId); sync(); setInterval(sync, 3000); });
</script></body></html>`;

function acctOf(req) {
  const m = /(?:^|;\s*)acct=([^;]+)/.exec(req.headers.cookie || '');
  return accounts[(m && m[1]) || req.headers['x-acct'] || 'A1'];
}
const send = (res, code, obj, type = 'application/json; charset=utf-8') => { res.writeHead(code, { 'Content-Type': type }); res.end(typeof obj === 'string' ? obj : JSON.stringify(obj)); };
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const a = acctOf(req);
  if (!a) return send(res, 404, { error: '沒有這個帳號' });
  if (url.pathname.startsWith('/game')) return send(res, 200, PAGE, 'text/html; charset=utf-8');
  if (url.pathname === '/api/account') return send(res, 200, { playerCode: a.code, activeCharacterId: a.active, status: 'ok' });
  if (url.pathname === '/api/catalog') return send(res, 200, catalog);
  // 測試控制：查看／重設狀態
  if (url.pathname === '/__mock/state') return send(res, 200, { accounts, guild });
  if (url.pathname === '/api/game' && req.method === 'POST') {
    let buf = ''; req.on('data', d => buf += d); req.on('end', () => {
      if (req.headers['x-game-version'] !== GAME_VERSION) return send(res, 409, { error: '遊戲已更新，請重新整理後再試' });
      let body; try { body = JSON.parse(buf); } catch (_) { return send(res, 400, { error: '格式錯誤' }); }
      try { send(res, 200, handle(a, body)); }
      catch (e) { if (!e.game) console.error(e); send(res, e.game ? 400 : 500, { error: e.message }); }
    });
    return;
  }
  send(res, 404, { error: 'not found' });
}).listen(PORT, '127.0.0.1', () => console.log('mockgame on http://127.0.0.1:' + PORT));
