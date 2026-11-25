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
  i2290001: { id: 2290001, name: '技能書：測試四轉技能', type: '技能書', sellPrice: 1 },
};
const scrolls = {
  i2040801: { id: 2040801, name: '手套攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'gloves', stats: { incPAD: 2 }, sellPrice: 500 },
  i2040805: { id: 2040805, name: '手套攻擊卷軸 10%', type: '卷軸', rate: 10, target: 'gloves', stats: { incPAD: 3 }, sellPrice: 500 },
  i2043001: { id: 2043001, name: '單手劍攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'oneHandedSword', stats: { incPAD: 2, incSTR: 1 }, sellPrice: 500 },
  i2044501: { id: 2044501, name: '弓攻擊卷軸 60%', type: '卷軸', rate: 60, target: 'bow', stats: { incPAD: 2, incACC: 1 }, sellPrice: 500 },
  i2040899: { id: 2040899, name: '手套攻擊詛咒卷軸 30%', type: '卷軸', rate: 30, cursed: 50, target: 'gloves', stats: { incPAD: 3 }, sellPrice: 1 },
};
for (const [k, s] of Object.entries(scrolls)) items[k] = { id: s.id, name: s.name, type: '卷軸', sellPrice: s.sellPrice };
const equipment = {
  e1082002: { itemId: 1082002, name: '工地手套', equipmentType: 'gloves', type: { category: 'Armor' }, meta: { reqLevel: 10, reqJob: 0 }, base: { incPDD: 2 }, slots: 5 },
  e1082149: { itemId: 1082149, name: '褐色工作手套', equipmentType: 'gloves', type: { category: 'Armor' }, meta: { reqLevel: 10, reqJob: 0 }, base: { incPDD: 5 }, slots: 7 },
  e1302000: { itemId: 1302000, name: '劍', equipmentType: 'oneHandedSword', type: { category: 'OneHandedWeapon' }, meta: { reqLevel: 0, reqJob: 1 }, base: { incPAD: 17 }, slots: 7 },
  e1452002: { itemId: 1452002, name: '戰鬥弓', equipmentType: 'bow', type: { category: 'TwoHandedWeapon' }, meta: { reqLevel: 10, reqJob: 4, reqDEX: 35 }, base: { incPAD: 28 }, slots: 7 },
  e1372005: { itemId: 1372005, name: '木製短杖', equipmentType: 'wand', type: { category: 'OneHandedWeapon' }, meta: { reqLevel: 8, reqJob: 2 }, base: { incMAD: 29 }, slots: 7 },
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
  // 野王（2026-11-20 對照真實遊戲：地圖的 bossSpawns、同步的 enemies／bossRespawns）
  { id: 'mBoss1', msId: 2220000, name: '紅寶王', lv: 20, hp: 3000, xp: 500, money: 500, defense: 10, isBoss: true },
  { id: 'mBoss2', msId: 6130101, name: '蘑菇王', lv: 60, hp: 900000000, xp: 5000, money: 5000, defense: 30, isBoss: true },
];
const maps = {
  gms100010000: { id: 'gms100010000', msId: 100010000, name: '弓箭手村北邊山丘', region: '維多利亞島', minLevel: 1, mobIds: ['m100100', 'm1210100'] },
  gms104040000: { id: 'gms104040000', msId: 104040000, name: '射手訓練場', region: '維多利亞島', minLevel: 10, mobIds: ['m1210101'] },
  gms104000400: { id: 'gms104000400', msId: 104000400, name: '海岸草叢3', region: '維多利亞島', minLevel: 1, mobIds: ['m1210101', 'mBoss1'], bossSpawns: [{ mobId: 'mBoss1', minSeconds: 1200, maxSeconds: 1200 }] },
  gms100000005: { id: 'gms100000005', msId: 100000005, name: '蘑菇王棲息地', region: '維多利亞島', minLevel: 1, mobIds: ['m100100', 'mBoss2'], bossSpawns: [{ mobId: 'mBoss2', minSeconds: 1800, maxSeconds: 1800 }] },
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
    id, name, job, lv, xp: 0, nextXp: 1000 * lv * lv, money: 500000, map, auto: false, until: null, hp: 500, maxhp: 500, mp: 300, maxmp: 300, kills: 0,
    stats: { incSTR: 40, incDEX: 40, incINT: 4, incLUK: 4 }, gear: {}, equipmentBag: [], warehouseGear: [], inventory: { i2000000: 200, i2000003: 100 },
    inventoryStacks: [], warehouse: {}, warehouseMesos: 0, supply: { hpItem: 'i2000000', mpItem: 'i2000003' }, autoSell: { maps: {} }, log: [], ...extra,
  };
}
const accounts = {};
function addAccount(acct, code, chars) {
  accounts[acct] = { acct, code, chars: Object.fromEntries(chars.map(c => [c.id, c])), active: chars[0].id, cashPoints: 5000 };
}
addAccount('A1', 'A1B2C3D4E5F6', [
  makeChar('c1', '本尊劍士', 'fighter', 45, 'gms104040000', { money: 30000000, gear: { weapon: makeGear('e1302000') },
    inventory: { i2000000: 300, i2000003: 200, i2040801: 12, i2040805: 5, i2043001: 4, i2044501: 5200, i2040899: 30, i2290001: 3 } }),
  makeChar('c2', '本尊小號', 'beginner', 12, 'gms100010000'),
]);
addAccount('A2', 'B2C3D4E5F6A1', [makeChar('c3', '弓箭分身', 'hunter', 32, 'gms104040000', { auto: true, until: Date.now() + 8 * 3600e3, gear: { weapon: makeGear('e1452002') } })]);
addAccount('A3', 'C3D4E5F6A1B2', [makeChar('c4', '倉庫分身', 'swordman', 20, 'gms100010000', { auto: true, until: Date.now() + 8 * 3600e3 })]);
if (process.env.MOCK_MORE_ACCTS) { // 4 人隊測試用：多兩個帳號
  addAccount('A4', 'D4E5F6A1B2C3', [makeChar('c5', '第四隻', 'swordman', 30, 'gms100010000', { auto: true, until: Date.now() + 8 * 3600e3 })]);
  addAccount('A5', 'E5F6A1B2C3D4', [makeChar('c6', '第五隻', 'swordman', 30, 'gms100010000', { auto: true, until: Date.now() + 8 * 3600e3 })]);
}
setTimeout(() => initParty(), 0); // 隊伍在帳號建好後才建
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
  const evs = bossTick(c, map, now - last);
  const normal = map.mobIds.filter(id => !(mobs.find(m => m.id === id) || {}).isBoss); if (!normal.length) return evs;
  const swings = Math.min(20, Math.max(1, Math.round((now - last) / 1000)));
  for (let i = 0; i < swings; i++) {
    const pickId = normal[rnd(normal.length)], mob = mobs.find(m => m.id === pickId);
    if (!mob) { console.error('[mock] 找不到怪物', JSON.stringify({ map: c.map, pickId, normal, n: normal.length })); continue; }
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

// ---------------- 野王 ----------------
// 每隻角色自己一份（真實遊戲：instanceId solo:角色:地圖；同隊的話是 party:…，這裡不模擬隊伍）
// c._boss[mob] = { hp, deadline }：deadline > 現在＝冷卻中；王的血量離開地圖後保留
const BOSS_DPS = () => Number(process.env.MOCK_BOSS_DPS || 600);
const bossMapOf = mob => Object.values(maps).find(m => (m.bossSpawns || []).some(b => b.mobId === mob));
// 隊伍（真實遊戲：partyCreate／partyJoin {code}／partyLeave；同步回應最上層 party = {code, leader, members}；最多 6 人；
// 同隊伍共用同一份王，instanceId party:隊伍代碼:地圖）。MOCK_PARTY=c3,c4 一開始就讓這幾隻同隊
const parties = {}; // code → { leader, members: [角色 id] }
let partySeq = 0;
const bossStore = {};
const instOf = (c, mapId) => c.partyCode && parties[c.partyCode] ? `party:${c.partyCode}:${mapId}` : `solo:${c.id}:${mapId}`;
function bossRec(c, mob) { const k = instOf(c, bossMapOf(mob).id) + '|' + mob; return bossStore[k] || (bossStore[k] = { hp: mobs.find(m => m.id === mob).hp, deadline: 0 }); }
function partyLeave(c) {
  const p = parties[c.partyCode]; c.partyCode = '';
  if (!p) return;
  p.members = p.members.filter(x => x !== c.id);
  if (!p.members.length) { for (const k of Object.keys(parties)) if (parties[k] === p) delete parties[k]; }
  else if (p.leader === c.id) p.leader = p.members[0];
}
function charById(id) { for (const a of Object.values(accounts)) if (a.chars[id]) return a.chars[id]; return null; }
function partyOf(c) {
  const p = parties[c.partyCode]; if (!p) return null;
  // 真實遊戲的隊伍會帶聊天紀錄（最多 40 則）和每個隊員一堆欄位；MOCK_PARTY_MSGS=40 模擬這個大小
  const nMsg = Number(process.env.MOCK_PARTY_MSGS) || 0;
  const messages = Array.from({ length: nMsg }, (_, i) => ({ id: 'm' + i, at: Date.now() - i * 60000, from: 'c3', name: '弓箭分身', text: '測試訊息'.repeat(8) + i, kind: 'chat', mapInstanceId: 'inst-' + i }));
  return { code: c.partyCode, leader: p.leader === c.id, notice: nMsg ? '公告'.repeat(30) : '', messages, members: p.members.map(charById).filter(Boolean).map(m => ({ id: m.id, name: m.name, lv: m.lv, job: m.job, map: m.map, auto: m.auto, hp: m.hp, maxhp: m.maxhp, leader: m.id === p.leader, self: m.id === c.id, ...(nMsg ? { mapInstanceId: 'inst-' + m.map, buffs: 'b'.repeat(500), equipSummary: 'e'.repeat(200) } : {}) })) };
}
// 一開始的隊伍（帳號建好之後）
function initParty() {
  const ids = (process.env.MOCK_PARTY || '').split(',').filter(Boolean); if (ids.length < 2) return;
  parties.PTEST00000AA = { leader: ids[0], members: ids.slice() };
  for (const id of ids) { const c = charById(id); if (c) c.partyCode = 'PTEST00000AA'; }
}
function bossTick(c, map, ms) {
  const evs = [];
  for (const sp of map.bossSpawns || []) {
    const b = bossRec(c, sp.mobId), now = Date.now();
    if (b.deadline > now) continue;
    const dmg = Math.round(BOSS_DPS() * Math.min(ms, 20000) / 1000); if (dmg <= 0) continue;
    b.hp = Math.max(0, b.hp - dmg);
    const killed = b.hp <= 0;
    evs.push({ eventId: 'ev' + (++eventSeq), actor: c.id, kind: 'attack', damage: dmg, effectiveDamage: dmg, lines: [{ damage: dmg }], skill: 1001004, mob: sp.mobId, killed, at: now, map: c.map });
    if (killed) {
      const mob = mobs.find(m => m.id === sp.mobId);
      b.deadline = now + Number(process.env.MOCK_BOSS_RESPAWN_MS || sp.minSeconds * 1000); b.hp = mob.hp;
      c.xp += mob.xp; c.money += mob.money; addLog(c, `擊敗首領：${mob.name}`);
    }
  }
  return evs;
}
function enemiesOf(c) {
  const map = maps[c.map]; if (!map) return [];
  const out = map.mobIds.filter(id => !(mobs.find(m => m.id === id) || {}).isBoss).map((id, i) => { const m = mobs.find(x => x.id === id); return { id, hp: m.hp, maxHp: m.hp, spawnId: 'sp' + i }; });
  for (const sp of map.bossSpawns || []) { const b = bossRec(c, sp.mobId); if (b.deadline <= Date.now()) out.push({ id: sp.mobId, hp: b.hp, maxHp: mobs.find(m => m.id === sp.mobId).hp, spawnId: 'boss-' + sp.mobId }); }
  return out;
}
function bossRespawnsOf(c) {
  const now = Date.now();
  return Object.values(maps).filter(m => (m.bossSpawns || []).length).map(m => {
    const mob = m.bossSpawns[0].mobId, b = bossStore[instOf(c, m.id) + '|' + mob], cd = !!(b && b.deadline > now);
    return { map: m.id, mapName: m.name, mob, name: mobs.find(x => x.id === mob).name, instanceId: instOf(c, m.id), roster: c.partyCode && parties[c.partyCode] ? parties[c.partyCode].members.join(',') : c.id, scopeVersion: 1, deadline: b ? b.deadline : 0, spawned: !cd && c.map === m.id, available: cd };
  });
}

// ---------------- 自由市場（攤位） ----------------
let listingSeq = 0;
function stallOf(c) { return c._stall || null; }
function marketView(a, c) {
  const st = stallOf(c);
  return { characterId: c.id, products: [], productsHasMore: false, stalls: [], selected: null,
    sellInventory: { inventory: { ...c.inventory } }, eligibleItems: tradeEligible(a, c.id).items, eligibleGear: c.equipmentBag.filter(g => !g.locked).map(g => g.uid),
    mine: st ? { id: 'stall-' + c.id, title: st.title, open: st.open, count: st.listings.length, listings: st.listings.map(({ gear, ...l }) => l), proceeds: st.proceeds, history: st.history.slice(-30) } : null };
}

// ---------------- 遊戲 API ----------------
const strip = c => { const { _simAt, _boss, _stall, pendingHits, ...rest } = c; return rest; };
// 回應裡的 character：請求指定的角色（同一個帳號開兩個分頁時，每個分頁拿到自己的角色）
function sessionView(a, cid) {
  const c = a.chars[cid] || a.chars[a.active];
  return { serverTime: Date.now(), cashPoints: a.cashPoints, character: strip(c), characters: Object.values(a.chars).map(x => ({ id: x.id, name: x.name, lv: x.lv, job: x.job, auto: x.auto })), party: partyOf(c), knowledge: { ready: false, remaining: 0 } };
}
function tradeEligible(a, cid) {
  const c = a.chars[cid] || a.chars[a.active];
  return { items: Object.keys(c.inventory).filter(k => !k.startsWith('i4031')), gear: c.equipmentBag.map(g => g.uid) };
}
const fail = msg => { const e = new Error(msg); e.game = true; throw e; };
function gearList(c) { return [...Object.values(c.gear).filter(Boolean), ...c.equipmentBag]; }
// 測試控制：/__mock/luck?seq=1,1,0 之後衝卷依序成功／失敗（用完回到隨機）
let scrollQueue = [];
function scrollOnce(c, g, key) {
  const sc = scrolls[key]; if (!sc) fail('不是卷軸');
  if (!(c.inventory[key] > 0)) fail('卷軸不足');
  if (g.slots <= 0) fail('沒有可衝次數');
  c.inventory[key]--; g.slots--;
  const ok = scrollQueue.length ? !!scrollQueue.shift() : rnd(100) < sc.rate;
  if (ok) { g.successes++; for (const [s, v] of Object.entries(sc.stats)) g.stats[s] = (g.stats[s] || 0) + v; }
  else if (sc.cursed && rnd(100) < sc.cursed) {  // 詛咒卷軸：失敗時有機率裝備消失
    c.equipmentBag = c.equipmentBag.filter(x => x !== g);
    for (const [k, x] of Object.entries(c.gear)) if (x === g) delete c.gear[k];
    g.destroyed = true;
  }
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
      // 真實遊戲：伺服器的「目前角色」跟著頁面同步的角色走
      if (body.characterId && a.chars[body.characterId]) a.active = body.characterId;
      let evs = [];
      for (const x of Object.values(a.chars)) evs = evs.concat(simulate(x, now));
      for (const x of Object.values(a.chars)) if (x.pendingHits && x.pendingHits.length) { evs = evs.concat(x.pendingHits); x.pendingHits = []; }
      const res = { ...sessionView(a, c.id), summary: { events: evs }, tradeEligible: tradeEligible(a, c.id), enemies: enemiesOf(c), bossTimers: {} };
      if (body.tradeOnly) res.trade = null;
      if (body.includeMarket) res.market = marketView(a, c);
      if (body.includeBossRespawns) res.bossRespawns = bossRespawnsOf(c);
      return res;
    }
    case 'start': c.auto = true; c.until = now + 24 * 3600e3; c._simAt = now; addLog(c, '開始掛機'); break;
    case 'stop': c.auto = false; addLog(c, '暫停掛機'); break;
    case 'map': if (!maps[body.map]) fail('沒有這張地圖'); c.map = body.map; addLog(c, '前往 ' + maps[body.map].name);
      // 真實遊戲（2026-11-20 實測）：換地圖會停止掛機（MOCK_MAP_STOPS_IDLE=1 模擬）
      if (process.env.MOCK_MAP_STOPS_IDLE === '1' && c.auto) { c.auto = false; c.until = now; }
      break;
    case 'autoSell':
      if (body.map !== c.map) fail('只能設定角色目前所在地圖的自動販售');
      c.autoSell.maps[body.map] = { enabled: !!(body.config && body.config.enabled), itemIds: ((body.config && body.config.itemIds) || []).map(Number) };
      break;
    // 掛機設定組合 1／2／3（真實遊戲：character.settingsSlot，沒設定過＝1）
    case 'settingsPreset': { const n = Number(body.slot); if (![1, 2, 3].includes(n)) fail('設定組合只有 1、2、3'); c.settingsSlot = n; (c.presetLog || (c.presetLog = [])).push({ n, map: c.map, auto: c.auto }); break; }
    // 死亡／原地復活（真實遊戲：死亡＝hp <= 0，{type:'revive'}；這裡復活後停止掛機，讓中控要再開始）
    case 'revive': if (c.hp > 0) fail('角色沒有死亡'); c.hp = c.maxhp; c.revives = (c.revives || 0) + 1; addLog(c, '原地復活'); break;
    case 'partyCreate': {
      if (c.partyCode) fail('已經在隊伍裡，請先離開');
      const code = ('P' + String(++partySeq).padStart(5, '0') + Math.random().toString(16).slice(2, 8)).toUpperCase().slice(0, 12);
      parties[code] = { leader: c.id, members: [c.id] }; c.partyCode = code; break;
    }
    case 'partyJoin': {
      if (c.partyCode) fail('已經在隊伍裡，請先離開');
      const code = String(body.code || '').toUpperCase(), p = parties[code]; if (!p) fail('找不到這個隊伍');
      if (p.members.length >= 6) fail('隊伍已滿');
      p.members.push(c.id); c.partyCode = code; break;
    }
    case 'partyLeave': if (!c.partyCode) fail('不在隊伍裡'); partyLeave(c); break;
    case 'partyKick': {
      const p = parties[c.partyCode]; if (!p) fail('不在隊伍裡'); if (p.leader !== c.id) fail('只有隊長可以踢人');
      const m = charById(body.memberId); if (!m || m.partyCode !== c.partyCode || m.id === c.id) fail('隊伍裡沒有這個人');
      partyLeave(m); break;
    }
    case 'marketConfig': c._stall = c._stall || { listings: [], proceeds: 0, history: [] }; c._stall.title = body.title || ''; c._stall.open = body.open !== false; break;
    case 'marketList': {
      const st = stallOf(c); if (!st) fail('還沒有攤位');
      if (st.listings.length >= 50) fail('攤位已滿');
      if (body.kind === 'gear') {
        const i = c.equipmentBag.findIndex(g => g.uid === body.uid); if (i < 0) fail('找不到裝備');
        const g = c.equipmentBag.splice(i, 1)[0];
        st.listings.push({ id: 'L' + (++listingSeq), kind: 'gear', key: g.key, name: g.name, qty: 1, price: body.price, gear: g });
      } else {
        const have = c.inventory[body.item] || 0, qty = Number(body.qty) || 0; if (qty <= 0 || have < qty) fail('數量不足');
        c.inventory[body.item] = have - qty;
        st.listings.push({ id: 'L' + (++listingSeq), kind: 'item', key: body.item, name: items[body.item].name, qty, price: body.price });
      }
      break;
    }
    case 'marketCancel': {
      // 真實遊戲：下架商品取回至「目前角色」背包（characterId）
      const st = stallOf(c); const i = st ? st.listings.findIndex(l => l.id === body.listingId) : -1; if (i < 0) fail('找不到這個商品');
      const l = st.listings.splice(i, 1)[0];
      if (l.kind === 'gear') c.equipmentBag.push(l.gear); else c.inventory[l.key] = (c.inventory[l.key] || 0) + l.qty;
      addLog(c, `下架：${l.name} × ${l.qty}`);
      break;
    }
    case 'marketClaim': { const st = stallOf(c); if (st) { c.money += st.proceeds; st.proceeds = 0; } break; }
    case 'switch': if (!a.chars[body.characterId]) fail('沒有這隻角色'); a.active = body.characterId; break;
    case 'inventoryLock': {
      const ids = new Set(body.ids || []);
      for (const s of c.inventoryStacks) if (ids.has(s.uid)) s.locked = !!body.locked;
      for (const g of c.equipmentBag) if (ids.has(g.uid)) g.locked = !!body.locked;
      break;
    }
    case 'inventoryQuote': {
      // 真實遊戲（2026-11-20 實測）：報價單存在 character.inventoryQuote，賣完也不清掉；rows 每列有 uid、kind、key
      // 送來的 id 都對不上時（背包剛好在變動）不產生新報價，回應裡還是上一張
      const ids = new Set(body.ids || []); const rows = [];
      if (body.category === 'equip') for (const g of c.equipmentBag) { if (ids.has(g.uid) && !g.locked) rows.push({ uid: g.uid, kind: 'gear', key: g.key, name: g.name, qty: 1, price: 100 }); }
      else for (const s of c.inventoryStacks) if (ids.has(s.uid) && !s.locked) rows.push({ uid: s.uid, kind: 'item', key: s.key, name: items[s.key].name, qty: s.qty, price: items[s.key].sellPrice * s.qty });
      if (!rows.length || rows.length < ids.size) return { ...sessionView(a, c.id), summary: { events: [] } };
      const q = { id: newUid('q'), characterId: c.id, category: body.category, rows, total: rows.reduce((t, r) => t + r.price, 0), expiresAt: Date.now() + 60000, charId: c.id };
      quotes[q.id] = q; c.inventoryQuote = { ...q }; return { ...sessionView(a, c.id), summary: { events: [] } };
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
      return { ...sessionView(a, c.id), summary: { events: [], scroll: { success: ok, uid: g.uid } } };
    }
    case 'artisanScroll': {
      // 真實遊戲：每衝 1 次扣 1 張卷軸＋10 萬楓幣；單件 {uid}，多件 {uids: 2～10，名稱與剩餘次數要相同}；expectedSlots = 選裝時的剩餘格數
      // 結果寫在 character.lastArtisan（多件：{multi, gear, selected, scroll, rate, items:[{attempts:[], successes, destroyed, slots, stop}], attempts, successes, lost, fee, stop}）
      const FEE = 100000;
      const multi = !!body.uids;
      const uids = body.uids || (body.uid ? [body.uid] : []);
      if (!uids.length || uids.length > 10 || (multi && uids.length < 2)) fail('單件用 uid，多選 2～10 件用 uids');
      const count = Math.min(10, Math.max(1, Number(body.count) || 1));
      const sc = scrolls[body.item]; if (!sc) fail('不是卷軸');
      const gs = uids.map(u => gearList(c).find(x => x.uid === u));
      if (gs.some(g => !g)) fail('找不到裝備');
      if (multi && gs.some(g => g.name !== gs[0].name || g.slots !== gs[0].slots || g.locked)) fail('多選的裝備要名稱、剩餘次數相同而且沒鎖定');
      if (gs.some(g => sc.target !== g.type)) fail('卷軸不適用這件裝備');
      if (body.expectedSlots != null && gs.some(g => g.slots !== body.expectedSlots)) fail('裝備狀態已變更，請重新開啟');
      if (c.money < FEE) fail('楓幣不足');
      const items = []; let stop = '';
      for (const g of gs) {
        const att = []; let ok = 0, st = '';
        while (true) {
          if (att.length >= count) { st = '次數到了'; break; }
          if (g.slots <= 0) { st = '格數用完'; break; }
          if ((c.inventory[body.item] || 0) <= 0) { st = stop = '卷軸用完'; break; }
          if (c.money < FEE) { st = stop = '楓幣不足'; break; }
          c.money -= FEE; const r = scrollOnce(c, g, body.item); att.push(r); if (r) ok++;
          if (g.destroyed) { st = '裝備消失'; break; }
          if (body.stopAfterSuccesses && ok >= body.stopAfterSuccesses) { st = '達到成功次數'; break; }
          if (body.stopOnFail && !r) { st = '失敗停止'; break; }
        }
        items.push({ uid: g.uid, attempts: att, successes: ok, destroyed: !!g.destroyed, slots: g.slots, stop: st });
        if (stop) break;
      }
      const all = items.flatMap(x => x.attempts);
      c.lastArtisan = multi
        ? { multi: true, gear: gs[0].name, selected: gs.length, scroll: sc.name, rate: sc.rate, items, attempts: all, successes: all.filter(Boolean).length, lost: items.filter(x => x.destroyed).length, fee: all.length * FEE, stop }
        : { uid: gs[0].uid, gear: gs[0].name, scroll: sc.name, rate: sc.rate, attempts: items[0].attempts, successes: items[0].successes, destroyed: items[0].destroyed, slots: items[0].slots, fee: all.length * FEE, stop: items[0].stop };
      rebuildStacks(c);
      addLog(c, `神匠之魂：衝了 ${all.length} 次`);
      return { ...sessionView(a, c.id), summary: { events: [] } };
    }
    case 'guildWarehouseView': return { ...sessionView(a, c.id), summary: { events: [], guildWarehouse: guildView() } };
    case 'guildWarehouseMesos': case 'guildWarehouseCash': {
      // 存入：從角色楓幣／帳號點數扣掉、加到公倉；提領：扣稅（模擬遊戲的 taxPercent）
      const amt = Math.floor(Number(body.amount) || 0); if (!(amt > 0)) fail('金額不正確');
      const isM = body.type === 'guildWarehouseMesos', gk = isM ? 'mesos' : 'cashPoints';
      const get = () => isM ? c.money : a.cashPoints, set = v => { if (isM) c.money = v; else a.cashPoints = v; };
      if (body.op === 'deposit') { if (get() < amt) fail(isM ? '楓幣不足' : '點數不足'); set(get() - amt); guild[gk] += amt; }
      else if (body.op === 'withdraw') { if (guild[gk] < amt) fail('公會倉庫餘額不足'); guild[gk] -= amt; set(get() + Math.floor(amt * (100 - guild.taxPercent) / 100)); }
      else fail('不明的操作');
      return { ...sessionView(a, c.id), summary: { events: [], guildWarehouse: guildView() } };
    }
    case 'guildWarehouseBatch': {
      const list = body.items || []; if (list.length > 100) fail('一次最多 100 項');
      // 真實遊戲另有單次請求上限（門檻不明），模擬成：總數量超過 3000 回「請求過大」
      if (list.reduce((t, it) => t + (it.qty || 1), 0) > Number(process.env.GUILD_QTY_MAX || 3000)) fail('請求過大');
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
          if (!tradeEligible(a, c.id).items.includes(it.item)) fail('不可交易的道具不能存入');
          c.inventory[it.item] = have - it.qty; guild.items[it.item] = (guild.items[it.item] || 0) + it.qty;
        } else if (body.op === 'withdraw') {
          if (it.kind === 'gear') { const i = guild.gear.findIndex(g => g.uid === it.uid); if (i < 0) fail('公會倉庫沒有這件'); c.equipmentBag.push(guild.gear.splice(i, 1)[0]); continue; }
          const have = guild.items[it.item] || 0; if (have < it.qty) fail('公會倉庫數量不足');
          guild.items[it.item] = have - it.qty; if (!guild.items[it.item]) delete guild.items[it.item];
          c.inventory[it.item] = (c.inventory[it.item] || 0) + it.qty;
        } else fail('不明的操作');
      }
      rebuildStacks(c);
      return { ...sessionView(a, c.id), summary: { events: [], guildWarehouse: guildView() } };
    }
    default: fail('模擬遊戲沒有實作：' + body.type);
  }
  rebuildStacks(c);
  return { ...sessionView(a, c.id), summary: { events: [] } };
}

const MOCK_AVA_GIF = 'R0lGODlhKAAoAIEAAAAAAPrSqjx43CgoPCH5BAEAAAAALAAAAAAoACgAQAiuAAEIHEiwoMGDCBMeDMCwocOHDBVKLAjx4cSLAgVo3MixI0aJAgaIHBlypEgBHydWdJhS4cqXLQ92nMkxpkyaNG0eNCkSAM8BOiVaDIrwJUSiAo1WRApAKUumOHNCjepxKtWNTAFcrZn1p0+eWQV69Rq27EeYZp0GCKs2ItK2Dd/CXStXLVunZpuuNLsVq9WtWftqDCyYcF/DgP9eDTsWLGOwZLtCdizZ5FfLEwMCADs=';
// ---------------- 頁面 ----------------
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>上漲谷（模擬）</title></head><body>
<h3>上漲谷模擬遊戲</h3><img src="/game/res/test.png" width="1" height="1" alt=""><div id="who"></div><pre id="st"></pre>
<script>
// 模擬遊戲的 client-update.js：所有 /api/game 請求補上版本標頭
(function(){ const f = window.fetch; window.fetch = function(input, init){ init = init || {}; const u = String((input && input.url) || input);
  if (u.includes('/api/game')) { init.headers = Object.assign({}, init.headers || {}, { 'X-Game-Version': '${GAME_VERSION}' }); } return f.call(this, input, init); }; })();
// 跟真實遊戲一樣：同步用的是記憶體裡「畫面上的角色」，同步完再把它寫回 sessionStorage
let cur = null;
async function sync(){
  cur = cur || sessionStorage.getItem('mapleCharacter');
  const r = await fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'sync', characterId: cur }) });
  const j = await r.json(); if (!j.character) return;
  cur = j.character.id; sessionStorage.setItem('mapleCharacter', j.character.id);
  sessionStorage.setItem('mapleSessionView', JSON.stringify({ state: j }));
  document.getElementById('who').textContent = j.character.name + ' Lv' + j.character.lv + ' 楓幣 ' + j.character.money.toLocaleString();
  document.getElementById('st').textContent = 'EXP ' + j.character.xp + ' [12.50%]\\n平均每小時經驗 120,000\\n你的遊戲 ID：' + (window.__code || '');
}
// 模擬遊戲的 appearance.js（MOCK_APPEARANCE=1）：站姿 GIF 用一張 40×40 的小人代替
${process.env.MOCK_APPEARANCE ? "window.MapleAppearance = { key: c => 'id=' + c.id + '&lv=' + (c.lv || 0) + '&v=72', load: async c => ({ key: 'x', stand: 'blob:not-readable' }) };" : ''}
fetch('/api/account').then(r => r.json()).then(a => { window.__code = a.playerCode; if (!sessionStorage.getItem('mapleCharacter')) sessionStorage.setItem('mapleCharacter', a.activeCharacterId); sync(); setInterval(sync, ${Number(process.env.MOCK_SYNC_MS) || 3000}); });
</script></body></html>`;

function acctOf(req) {
  const m = /(?:^|;\s*)acct=([^;]+)/.exec(req.headers.cookie || '');
  return accounts[(m && m[1]) || req.headers['x-acct'] || 'A1'];
}
const send = (res, code, obj, type = 'application/json; charset=utf-8') => { res.writeHead(code, { 'Content-Type': type }); res.end(typeof obj === 'string' ? obj : JSON.stringify(obj)); };
let pngHits = 0;
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  // MOCK_REQUIRE_LOGIN=1：沒有 acct cookie（也沒有 harness 的 x-acct 標頭）＝還沒登入（給背景執行 e2e_bg 測登入流程）
  // /__mock/login?acct=A1 模擬「Google 登入完成」：設好 cookie 再導回 /game/
  // 圖片請求計數（背景執行省資源模式要擋掉）：只算不是 harness（沒有 x-acct 標頭）的＝背景 Chrome 的
  if (url.pathname.endsWith('.png') && !req.headers['x-acct']) { pngHits++; res.writeHead(200, { 'Content-Type': 'image/png' }); return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64')); }
  if (url.pathname === '/__mock/pnghits') return send(res, 200, { n: pngHits });
  if (url.pathname === '/__mock/login') { res.writeHead(302, { 'Set-Cookie': `acct=${encodeURIComponent(url.searchParams.get('acct') || 'A1')}; Path=/; Max-Age=2592000`, Location: '/game/' }); return res.end(); }
  if (process.env.MOCK_REQUIRE_LOGIN && !/(?:^|;\s*)acct=/.test(req.headers.cookie || '') && !req.headers['x-acct'] && !url.pathname.startsWith('/__mock/')) {
    if (url.pathname.startsWith('/game')) return send(res, 200, '<!doctype html><title>請登入</title><body>請先登入</body>', 'text/html; charset=utf-8');
    return send(res, 401, { error: '請先登入' });
  }
  const a = acctOf(req);
  if (!a) return send(res, 404, { error: '沒有這個帳號' });
  if (url.pathname.startsWith('/game')) return send(res, 200, PAGE, 'text/html; charset=utf-8');
  // 外觀圖（真實遊戲 appearance.js 的 fetchPart：/api/appearance?<外觀參數>&action=stand|attack…）
  if (url.pathname === '/api/appearance') { if (url.searchParams.get('action') !== 'stand') return send(res, 404, { error: 'mock only has stand' }); res.writeHead(200, { 'Content-Type': 'image/gif' }); return res.end(Buffer.from(MOCK_AVA_GIF, 'base64')); }
  if (url.pathname === '/api/account') return send(res, 200, { playerCode: a.code, activeCharacterId: a.active, characterIds: Object.keys(a.chars), status: 'ok' });
  if (url.pathname === '/api/catalog') return send(res, 200, catalog);
  // 測試控制：查看／重設狀態
  if (url.pathname === '/__mock/state') return send(res, 200, { accounts, guild });
  // 測試控制：/__mock/session?acct=A1&char=c1&money=120000&activeMs=7200000&earned=9000000 設定本次掛機報告與累計賺得
  if (url.pathname === '/__mock/session') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    const n = k => Number(url.searchParams.get(k) || 0);
    c.earned = n('earned'); c.sessionReport = { startedAt: new Date(Date.now() - n('activeMs')).toISOString(), money: n('money'), xp: 0, activeMs: n('activeMs') };
    return send(res, 200, { ok: true });
  }
  // 測試控制：/__mock/additem?acct=A1&char=c1&key=i2000001&qty=20
  if (url.pathname === '/__mock/additem') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    const k = url.searchParams.get('key'); c.inventory[k] = (c.inventory[k] || 0) + Number(url.searchParams.get('qty') || 1); rebuildStacks(c);
    return send(res, 200, { ok: true });
  }
  // 測試控制：/__mock/addgear?acct=A1&char=c1&key=e1452002&clean=incPAD:30,incDEX:2 放一件指定浮動的裝備到背包
  if (url.pathname === '/__mock/addgear') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    const clean = Object.fromEntries((url.searchParams.get('clean') || '').split(',').filter(Boolean).map(x => { const [k, v] = x.split(':'); return [k, Number(v)]; }));
    const g = makeGear(url.searchParams.get('key'), { stats: { ...clean }, cleanStats: clean });
    c.equipmentBag.push(g); return send(res, 200, { ok: true, uid: g.uid });
  }
  // 測試控制：/__mock/boss?acct=A1&char=c1&mob=mBoss1&cd=60000&hp=500 設定野王（cd＝幾毫秒後重生，0＝在場上）
  if (url.pathname === '/__mock/boss') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    const b = bossRec(c, url.searchParams.get('mob'));
    if (url.searchParams.has('cd')) b.deadline = Number(url.searchParams.get('cd')) > 0 ? Date.now() + Number(url.searchParams.get('cd')) : 0;
    if (url.searchParams.has('hp')) b.hp = Number(url.searchParams.get('hp'));
    return send(res, 200, { ok: true, boss: b });
  }
  // 測試控制：/__mock/stall?acct=A1&char=c1 開攤位；&sell=L1&qty=3 模擬別人買走 3 個
  if (url.pathname === '/__mock/stall') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    c._stall = c._stall || { title: c.name + '的小攤', open: true, listings: [], proceeds: 0, history: [] };
    const id = url.searchParams.get('sell');
    if (id) {
      const l = c._stall.listings.find(x => x.id === id); if (!l) return send(res, 404, { error: 'no listing' });
      const q = Math.min(l.qty, Number(url.searchParams.get('qty') || 1)); l.qty -= q; c._stall.proceeds += q * l.price;
      c._stall.history.push({ time: Date.now(), name: l.name, qty: q, price: l.price, buyer: '路人' });
      if (!l.qty) c._stall.listings = c._stall.listings.filter(x => x !== l);
    }
    return send(res, 200, { ok: true, listings: c._stall.listings.map(({ gear, ...l }) => l) });
  }
  // 測試控制：/__mock/restack?acct=A1&char=c1 模擬撿東西造成堆疊重排（每一疊換新的 uid）
  if (url.pathname === '/__mock/restack') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    c.inventoryStacks = c.inventoryStacks.map(s => ({ ...s, uid: newUid('s') }));
    return send(res, 200, { ok: true });
  }
  // 測試控制：/__mock/die?acct=A1&char=c1 讓角色死亡（hp 0、停止掛機）
  if (url.pathname === '/__mock/die') {
    const a = accounts[url.searchParams.get('acct')], c = a && a.chars[url.searchParams.get('char')];
    if (!c) return send(res, 404, { error: 'no char' });
    // by=怪物 id：死前被這隻怪打（下一次同步的 summary.events 會有打到角色的事件）；gamerevive=1：遊戲自己的自動復活（同一次同步就活過來）
    const by = url.searchParams.get('by'), now = Date.now();
    if (by) { const m = mobs.find(x => x.id === by); (c.pendingHits = c.pendingHits || []).push({ eventId: 'h' + now, actor: 'inst-' + by, kind: 'mobAttack', target: c.id, mob: by, damage: Number(url.searchParams.get('dmg')) || c.maxhp, at: now - 500 }); addLog(c, `被 ${m ? m.name : by} 擊倒了`); }
    else addLog(c, '角色死亡');
    c.deaths = (c.deaths || 0) + 1; c.deathAt = now;
    if (url.searchParams.get('gamerevive') === '1') { c.autoReviveUsed = (c.autoReviveUsed || 0) + 1; addLog(c, '自動復活'); return send(res, 200, { ok: true }); }
    c.hp = 0; c.auto = false; return send(res, 200, { ok: true });
  }
  if (url.pathname === '/__mock/luck') { scrollQueue = (url.searchParams.get('seq') || '').split(',').filter(x => x !== '').map(Number); return send(res, 200, { ok: true, n: scrollQueue.length }); }
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
