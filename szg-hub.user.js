// ==UserScript==
// @name         上漲谷中控 - 資料回報
// @namespace    szg-hub
// @version      0.6.3
// @description  回報角色資料到中控面板；執行你在面板上確認過的工作（交易、背包）。每次載入都向中控伺服器取得最新程式。
// @match        https://play.szg08.com/game/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        unsafeWindow
// @connect      127.0.0.1
// @run-at       document-start
// @updateURL    http://127.0.0.1:8787/szg-hub.user.js
// @downloadURL  http://127.0.0.1:8787/szg-hub.user.js
// ==/UserScript==

// 結構：
//   1. 載入器（這個檔案外層）：攔截遊戲回應、向中控伺服器取得最新的 agent 程式並執行；
//      取不到或瀏覽器不允許動態執行時，改用下面內建的版本。
//   2. agentMain：真正的功能（回報資料、執行交易／背包工作）。伺服器會把這一段單獨提供成 /agent.js。

(function () {
  'use strict';

  const HUB = 'http://127.0.0.1:8787';
  const TOKEN = ''; // 只有遠端版需要；家裡本機用不到
  const W = (typeof unsafeWindow !== 'undefined' && unsafeWindow) || window;
  const shared = { eligible: null }; // 伺服器給的可交易清單 { items:Set, gear:Set }

  // ---------- 攔截遊戲自己的同步回應，取得「可交易清單」（要在 document-start 就裝好） ----------
  try {
    const origFetch = W.fetch;
    W.fetch = function (input, init) {
      const p = origFetch.apply(this, arguments);
      try {
        const u = String((input && input.url) || input);
        if (u.includes('/api/game')) {
          p.then(r => r.clone().json()).then(j => {
            if (j && j.tradeEligible && Array.isArray(j.tradeEligible.items)) {
              shared.eligible = { items: new Set(j.tradeEligible.items), gear: new Set(j.tradeEligible.gear || []), at: Date.now() };
            }
          }).catch(() => {});
        }
      } catch (_) {}
      return p;
    };
  } catch (e) { console.warn('[szg-hub] fetch hook failed', e); }

//== AGENT START ==
function agentMain(ctx) {
  'use strict';
  const AGENT_VERSION = '0.6.3';
  const { GM_xmlhttpRequest, GM_getValue, GM_setValue, W, HUB, TOKEN, shared } = ctx;
  const SCAN_MS = 10000;      // 資料回報間隔
  const HEARTBEAT_MS = 60000;
  const AGENT_MS = 3000;      // 工作輪詢間隔
  const STEP_TIMEOUT_MS = 3 * 60 * 1000; // 交易某一步卡超過 3 分鐘就取消
  const JOB_BITS = { '劍士': 1, '法師': 2, '弓箭手': 4, '盜賊': 8, '海盜': 16 };

  let catalog = null;
  let lastHash = '';
  let lastSent = 0;
  let account = null;          // { playerCode, activeCharacterId }
  let accountAt = 0;

    // ---------- 共用 ----------
    function hub(method, path, body) {
      return new Promise((resolve, reject) => {
        const headers = { 'Content-Type': 'application/json' };
        if (TOKEN) headers['X-Hub-Token'] = TOKEN;
        GM_xmlhttpRequest({
          method, url: HUB + path, headers, timeout: 8000,
          data: body ? JSON.stringify(body) : undefined,
          onload: r => {
            setBadge(r.status === 200 ? 'ok' : r.status === 401 ? 'auth' : 'err');
            if (r.status !== 200) return reject(new Error('hub ' + r.status));
            try { resolve(JSON.parse(r.responseText)); } catch (e) { reject(e); }
          },
          onerror: () => { setBadge('err'); reject(new Error('hub offline')); },
          ontimeout: () => { setBadge('err'); reject(new Error('hub timeout')); },
        });
      });
    }

    async function game(action) {
      const characterId = sessionStorage.getItem('mapleCharacter');
      const r = await fetch('/api/game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...action, characterId }),
      });
      let j = null;
      try { j = await r.json(); } catch (_) {}
      if (!r.ok || (j && j.error)) throw new Error((j && (j.error || j.message)) || ('HTTP ' + r.status));
      return j;
    }

    function readState() {
      const raw = sessionStorage.getItem('mapleSessionView');
      if (!raw) return null;
      const v = JSON.parse(raw);
      return v && v.state && v.state.character ? v.state : null;
    }

    async function loadAccount() {
      if (account && Date.now() - accountAt < 5 * 60 * 1000) return account;
      const r = await fetch('/api/account', { credentials: 'same-origin' });
      const a = await r.json();
      account = { playerCode: a.playerCode, activeCharacterId: a.activeCharacterId };
      accountAt = Date.now();
      return account;
    }

    // ---------- 目錄 ----------
    async function loadCatalog() {
      if (catalog) return catalog;
      const res = await fetch('/api/catalog', { credentials: 'same-origin' });
      const cat = await res.json();
      const mapsById = {};
      for (const m of Object.values(cat.maps || {})) {
        if (m && m.id != null) mapsById[String(m.id)] = m.name;
        if (m && m.msId != null) mapsById[String(m.msId)] = m.name;
      }
      catalog = { equipment: cat.equipment || {}, items: cat.items || {}, scrolls: cat.scrolls || {}, jobs: cat.jobs || {}, statNames: cat.statNames || {}, mapsById };
      return catalog;
    }
    function jobBranch(jobKey) {
      let j = catalog.jobs[jobKey], guard = 0;
      while (j && j.parent && j.tier > 1 && guard++ < 6) j = catalog.jobs[j.parent];
      return j ? j.name : '';
    }
    function itemInfo(key) {
      const it = catalog.items[key] || catalog.scrolls[key];
      if (!it) return { name: key, kind: '其他', cat: 'etc', sellPrice: 0, itemId: 0 };
      const kind = it.type || (catalog.scrolls[key] ? '卷軸' : '其他');
      return { name: it.name || key, kind, cat: bagCat(it.id, kind), sellPrice: it.sellPrice || 0, itemId: it.id || 0 };
    }
    // 遊戲背包分類：依物品編號開頭（2 消耗、3 裝飾、4 其他、5 點數）
    function bagCat(id, kind) {
      const head = Math.floor((Number(id) || 0) / 1000000);
      if (head === 2) return 'consume';
      if (head === 3) return 'setup';
      if (head === 4) return 'etc';
      if (head === 5) return 'cash';
      return kind === '消耗' || kind === '卷軸' ? 'consume' : 'etc';
    }

    // 補給中使用的道具（不收集）
    function supplyKeys(c) {
      const s = c.supply || {};
      const keys = new Set();
      for (const k of ['hpItem', 'mpItem']) if (s[k]) keys.add(s[k]);
      for (const k of ['buffPotion', 'buffPotion2', 'buffPotion3', 'extra']) if (s[k] && s[k].item) keys.add(s[k].item);
      if (c.selectedAmmo) keys.add(c.selectedAmmo);
      return keys;
    }
    // 每種道具被鎖定的數量
    function lockedQtyByKey(c) {
      const m = {};
      for (const st of c.inventoryStacks || []) if (st.locked) m[st.key] = (m[st.key] || 0) + (st.qty || 0);
      return m;
    }
    function itemTradableQty(c, key, locked) {
      const qty = (c.inventory || {})[key] || 0;
      if (shared.eligible && !shared.eligible.items.has(key)) return 0;
      return Math.max(0, qty - (locked[key] || 0));
    }
    function gearTradable(g) {
      if (g.locked) return false;
      if (shared.eligible && !shared.eligible.gear.has(g.uid)) return false;
      return true;
    }

    // ---------- 畫面補抓 ----------
    function scrapeDom(charId) {
      const metaKey = 'meta:' + charId;
      const meta = GM_getValue(metaKey, {});
      const text = document.body ? document.body.innerText : '';
      let m;
      if ((m = text.match(/EXP\s*([\d,]+)\s*\[([\d.]+)%\]/))) {
        const xp = Number(m[1].replace(/,/g, '')), pct = Number(m[2]);
        if (pct > 0) meta.expNeed = Math.round(xp / (pct / 100));
      }
      if ((m = text.match(/平均每小時經驗\s*([\d,]+)/))) meta.hourlyExp = Number(m[1].replace(/,/g, ''));
      GM_setValue(metaKey, meta);
      return meta;
    }

    // ---------- 快照 ----------
    function gearRow(g, loc, slotKey) {
      const e = catalog.equipment[g.key] || {};
      const meta = e.meta || {};
      const category = (e.type && e.type.category) || '';
      let slot = slotKey || g.type || e.equipmentType || '';
      if (/Weapon/.test(category)) slot = 'weapon';
      return {
        loc, slot, uid: g.uid,
        weaponType: /Weapon/.test(category) ? (g.type || e.equipmentType) : '',
        itemId: g.itemId, name: g.name, plus: g.successes || 0, slotsLeft: g.slots || 0, maxSlots: g.maxSlots || 0,
        locked: !!g.locked, tradable: loc === '背包' ? gearTradable(g) : false,
        stats: g.stats || {}, cleanStats: g.cleanStats || g.baseStats || {},
        reqLevel: meta.reqLevel || 0, reqJob: meta.reqJob || 0,
        reqSTR: meta.reqSTR || 0, reqDEX: meta.reqDEX || 0, reqINT: meta.reqINT || 0, reqLUK: meta.reqLUK || 0,
      };
    }

    function buildSnapshot(state) {
      const c = state.character;
      const meta = scrapeDom(c.id);
      const inv = c.inventory || {};
      const sup = c.supply || {};
      const branch = jobBranch(c.job);
      const supKeys = supplyKeys(c);
      const locked = lockedQtyByKey(c);

      const gear = [];
      for (const [slotKey, g] of Object.entries(c.gear || {})) if (g) gear.push(gearRow(g, '穿戴', slotKey));
      for (const g of c.equipmentBag || []) gear.push(gearRow(g, '背包'));
      for (const g of c.warehouseGear || []) gear.push(gearRow(g, '倉庫'));

      const stacksByKey = {};
      for (const st of c.inventoryStacks || []) (stacksByKey[st.key] || (stacksByKey[st.key] = [])).push({ uid: st.uid, qty: st.qty, locked: !!st.locked });
      const items = [];
      for (const [key, qty] of Object.entries(inv)) {
        if (!qty) continue;
        const info = itemInfo(key);
        items.push({ key, name: info.name, kind: info.kind, cat: info.cat, itemId: info.itemId, sellPrice: info.sellPrice, qty, loc: '背包',
          supply: supKeys.has(key), tradableQty: itemTradableQty(c, key, locked), lockedQty: locked[key] || 0, stacks: stacksByKey[key] || [] });
      }
      for (const [key, qty] of Object.entries(c.warehouse || {})) {
        if (!qty) continue;
        const info = itemInfo(key);
        items.push({ key, name: info.name, kind: info.kind, cat: info.cat, qty, loc: '倉庫', supply: false, tradableQty: 0, lockedQty: 0, stacks: [] });
      }

      const chars = (state.characters || []).map(x => ({ id: x.id, name: x.name, lv: x.lv, job: x.job, auto: x.auto }));
      const accountId = chars.length ? chars.map(x => x.id).sort()[0] : c.id;

      return {
        v: 3, at: Date.now(), serverTime: state.serverTime || Date.now(),
        scriptVersion: AGENT_VERSION,
        scriptMode: ctx.mode,
        accountId, accountChars: chars, statNames: catalog.statNames,
        playerCode: account && account.playerCode,
        activeCharId: account && account.activeCharacterId,
        eligibleKnown: !!shared.eligible,
        char: {
          id: c.id, name: c.name, job: c.job,
          jobName: (catalog.jobs[c.job] && catalog.jobs[c.job].name) || c.job,
          branch, branchBit: JOB_BITS[branch] || 0,
          lv: c.lv, xp: c.xp,
          expPct: meta.expNeed ? Math.min(100, (c.xp / meta.expNeed) * 100) : null,
          hourlyExp: meta.hourlyExp || null,
          tradeId: account && account.playerCode,
          money: c.money || 0, warehouseMesos: c.warehouseMesos || 0,
          map: c.map, mapName: catalog.mapsById[String(c.map)] || c.map,
          auto: !!c.auto, until: c.until || null,
          hp: c.hp, maxhp: c.maxhp, mp: c.mp, maxmp: c.maxmp, kills: c.kills || 0,
          hpItem: sup.hpItem ? itemInfo(sup.hpItem).name : null, hpQty: sup.hpItem ? (inv[sup.hpItem] || 0) : null,
          mpItem: sup.mpItem ? itemInfo(sup.mpItem).name : null, mpQty: sup.mpItem ? (inv[sup.mpItem] || 0) : null,
          stats: c.stats || {},
          gearBagCount: (c.equipmentBag || []).length,
          itemStackCount: (c.inventoryStacks || []).length,
        },
        gear, items,
      };
    }

    function setBadge(status, text) {
      if (!document.body) return;
      let el = document.getElementById('szg-hub-badge');
      if (!el) {
        el = document.createElement('div');
        el.id = 'szg-hub-badge';
        el.style.cssText = 'position:fixed;right:8px;bottom:8px;z-index:99999;font:12px sans-serif;padding:3px 8px;border-radius:10px;opacity:.9;pointer-events:none;color:#fff;max-width:340px';
        document.body.appendChild(el);
      }
      if (text) { el.textContent = text; el.style.background = '#7a5a12'; return; }
      if (agentBusy) return; // 交易進行中時保留交易狀態文字
      if (status === 'ok') { el.textContent = '中控：已連線'; el.style.background = '#1f7a3a'; }
      else if (status === 'auth') { el.textContent = '中控：通行碼錯誤，請重裝遠端腳本'; el.style.background = '#8a2b2b'; }
      else { el.textContent = '中控：連不到中控伺服器'; el.style.background = '#8a2b2b'; }
    }

    async function tick() {
      try {
        const state = readState();
        if (!state) return;
        await loadCatalog();
        try { await loadAccount(); } catch (_) {}
        const snap = buildSnapshot(state);
        const hash = JSON.stringify([snap.char, snap.playerCode, snap.eligibleKnown, snap.gear.map(g => g.uid + g.plus + g.loc + g.locked).join('|'), snap.items.map(i => i.key + i.qty + i.loc + i.tradableQty + i.lockedQty).join('|')]);
        const now = Date.now();
        if (hash !== lastHash || now - lastSent > HEARTBEAT_MS) {
          lastHash = hash; lastSent = now;
          await hub('POST', '/api/push', snap);
        }
      } catch (e) { console.warn('[szg-hub]', e); }
    }

    // =====================================================================
    // 交易執行（只做你在面板上按過「確認執行」的工作）
    // =====================================================================
    let agentBusy = false;
    let agentRunning = false;
    const local = {}; // jobId -> { batchIndex, tradeId, stepAt, invites }

    function offerKey(x) {
      if (!x) return '';
      if (x.kind === 'gear' || x.kind === 'cash') return 'g:' + (x.uid || (x.gear && x.gear.uid) || (x.cash && x.cash.uid));
      return 'i:' + (x.item || x.key);
    }

    // 依目前背包重新計算這一批要放的東西（第二次檢查：鎖定、可交易清單、補給品、數量）
    function buildOffer(batch, c) {
      const locked = lockedQtyByKey(c);
      const sup = supplyKeys(c);
      const bag = new Map((c.equipmentBag || []).map(g => [g.uid, g]));
      const items = [];
      const skipped = [];
      for (const it of batch.items || []) {
        if (it.excludeSupply !== false && sup.has(it.key) && it.qty === 'ALL') { skipped.push(it.name + '（補給中）'); continue; }
        const can = itemTradableQty(c, it.key, locked);
        const qty = it.qty === 'ALL' ? can : Math.min(Number(it.qty) || 0, can);
        if (qty > 0) items.push({ kind: 'item', item: it.key, qty });
        else skipped.push(it.name);
        if (it.qty !== 'ALL' && can < Number(it.qty)) skipped.push(`${it.name} 只剩 ${can}`);
      }
      for (const g of batch.gear || []) {
        const cur = bag.get(g.uid);
        if (!cur || !gearTradable(cur)) { skipped.push(g.name + (cur ? '（已鎖定）' : '（不在背包）')); continue; }
        items.push({ kind: 'gear', uid: g.uid, qty: 1 });
      }
      let money = 0;
      if (batch.money === 'ALL') money = Math.max(0, Math.floor((c.money || 0) / 1.05) - 1000); // 預留 5% 手續費
      else if (batch.money) money = Math.min(Number(batch.money) || 0, Math.floor((c.money || 0) / 1.05));
      return { offer: { money, points: 0, items: items.slice(0, 20) }, skipped };
    }

    // 收貨方核對：對方放的東西必須都在這一批的預期清單內
    function verifyIncoming(batch, theirOffer) {
      const allowed = new Map();
      for (const it of batch.items || []) allowed.set('i:' + it.key, it.qty === 'ALL' ? Infinity : Number(it.qty));
      for (const g of batch.gear || []) allowed.set('g:' + g.uid, 1);
      for (const x of (theirOffer && theirOffer.items) || []) {
        const k = offerKey(x);
        if (!allowed.has(k)) return '對方放了不在清單內的東西：' + (x.name || k);
        if ((x.qty || 1) > allowed.get(k)) return '數量超過預期：' + (x.name || k);
      }
      const m = (theirOffer && theirOffer.money) || 0;
      if (batch.money !== 'ALL' && m > (Number(batch.money) || 0)) return '楓幣超過預期';
      if ((theirOffer && theirOffer.points) > 0) return '對方放了點數，與清單不符';
      return null;
    }

    async function report(job, ev) {
      try { await hub('POST', '/api/agent/report', { jobId: job.id, batchIndex: job.batchIndex, ...ev }); } catch (_) {}
    }


    // ---------- 背包操作：賣出／鎖定／解鎖 ----------
    // 在回應裡找報價單（有 id 與 rows 的物件）
    function findQuote(o, depth = 0) {
      if (!o || typeof o !== 'object' || depth > 4) return null;
      if (o.id && Array.isArray(o.rows)) return o;
      for (const v of Object.values(o)) { const q = findQuote(v, depth + 1); if (q) return q; }
      return null;
    }
    async function runBagJob(job, state, charId) {
      if (charId !== job.fromCharId) {
        setBadge(null, `背包工作等待中：請切到「${job.fromName}」`);
        return report(job, { event: 'waiting', msg: `等待切換到 ${job.fromName}` });
      }
      const c = state.character;
      const stackOk = new Map((c.inventoryStacks || []).map(s => [s.uid, s]));
      const gearOk = new Map((c.equipmentBag || []).map(g => [g.uid, g]));
      const b = job.batches[0];
      const rid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
      if (job.kind === 'lock' || job.kind === 'unlock') {
        const want = job.kind === 'lock';
        const ids = [...(b.items || []).flatMap(i => i.uids || []).filter(u => stackOk.has(u)), ...(b.gear || []).map(g => g.uid).filter(u => gearOk.has(u))];
        if (!ids.length) { await report(job, { event: 'log', msg: '找不到要處理的物品（可能已經不在背包）' }); return report(job, { event: 'batchDone', skippedEmpty: true }); }
        setBadge(null, `${want ? '鎖定' : '解鎖'} ${ids.length} 項…`);
        await game({ type: 'inventoryLock', ids, locked: want, batch: true, requestId: rid() });
        await report(job, { event: 'log', msg: `已${want ? '鎖定' : '解鎖'} ${ids.length} 項` });
        return report(job, { event: 'batchDone' });
      }
      if (job.kind === 'sell') {
        // 第二次檢查：已鎖定、已不在背包、補給中的道具一律不賣
        const sup = supplyKeys(c);
        const groups = {};
        const skipped = [];
        for (const it of b.items || []) {
          if (sup.has(it.key)) { skipped.push(it.name + '（補給中）'); continue; }
          const uids = (it.uids || []).filter(u => stackOk.has(u) && !stackOk.get(u).locked);
          if (!uids.length) { skipped.push(it.name); continue; }
          (groups[it.cat || 'consume'] || (groups[it.cat || 'consume'] = [])).push(...uids);
        }
        for (const g of b.gear || []) {
          const cur = gearOk.get(g.uid);
          if (!cur || cur.locked) { skipped.push(g.name); continue; }
          (groups.equip || (groups.equip = [])).push(g.uid);
        }
        if (skipped.length) await report(job, { event: 'log', msg: '略過（已鎖定／不在背包／補給中）：' + skipped.join('、') });
        let total = 0, count = 0;
        for (const [category, ids] of Object.entries(groups)) {
          setBadge(null, `賣出 ${ids.length} 項（${category}）…`);
          const qr = await game({ type: 'inventoryQuote', category, ids });
          const q = findQuote(qr);
          if (!q) return report(job, { event: 'error', msg: `取得報價失敗（${category}），回應欄位：${Object.keys(qr || {}).join(',')}` });
          if (q.rows.length > ids.length) return report(job, { event: 'error', msg: `報價單有 ${q.rows.length} 項，比選擇的 ${ids.length} 項多，已停止` });
          await game({ type: 'inventorySell', quoteId: q.id, requestId: rid() });
          total += Number(q.total) || 0; count += q.rows.length;
        }
        await report(job, { event: 'log', msg: `已賣出 ${count} 項，共 ${total.toLocaleString()} 楓幣` });
        return report(job, { event: 'batchDone' });
      }
      return report(job, { event: 'error', msg: '未知的工作類型：' + job.kind });
    }

    async function agentTick() {
      if (agentRunning) return;
      agentRunning = true;
      try {
        await loadAccount().catch(() => null);
        const state = readState();
        if (!account || !state) return;
        const charId = sessionStorage.getItem('mapleCharacter');
        const res = await hub('GET', `/api/agent?code=${encodeURIComponent(account.playerCode)}&charId=${encodeURIComponent(charId)}`);
        const job = res && res.job;
        if (!job) { if (agentBusy) { agentBusy = false; setBadge('ok'); } return; }
        agentBusy = true;
        if (res.role === 'owner') return await runBagJob(job, state, charId);
        const role = res.role; // 'giver' | 'receiver'
        const batch = job.batches[job.batchIndex];
        const L = local[job.id] || (local[job.id] = { batchIndex: -1 });
        if (L.batchIndex !== job.batchIndex) Object.assign(L, { batchIndex: job.batchIndex, tradeId: null, stepAt: Date.now(), invites: 0, step: '' });

        const wantChar = role === 'giver' ? job.fromCharId : job.toCharId;
        if (job.strictChar && wantChar && charId !== wantChar) {
          setBadge(null, `交易等待中：請切到「${role === 'giver' ? job.fromName : job.toName}」`);
          return report(job, { event: 'waiting', msg: `等待切換到 ${role === 'giver' ? job.fromName : job.toName}` });
        }
        if (!res.peerReady) {
          setBadge(null, `交易等待中：對方（${role === 'giver' ? job.toName : job.fromName}）尚未上線`);
          return;
        }

        const sync = await game({ type: 'sync', tradeOnly: true });
        const t = sync && sync.trade;
        const peerCode = role === 'giver' ? job.toCode : job.fromCode;
        const mine = t && t.sides && t.sides[t.self];
        const theirs = t && t.sides && t.sides[1 - t.self];
        const isOurTrade = t && theirs && theirs.code === peerCode && t.status !== 'done' && t.status !== 'cancelled';

        const stepTimedOut = Date.now() - L.stepAt > STEP_TIMEOUT_MS;
        const step = s => { if (L.step !== s) { L.step = s; L.stepAt = Date.now(); } };
        const label = `交易 ${job.batchIndex + 1}/${job.batches.length}`;

        // 這一批已完成
        if (t && L.tradeId && t.id === L.tradeId && t.status === 'done') {
          setBadge(null, `${label}：完成`);
          await report(job, { event: 'batchDone', tradeId: t.id });
          return;
        }

        // 有其他人的交易卡著
        if (t && !isOurTrade && t.status !== 'done' && t.status !== 'cancelled' && theirs) {
          setBadge(null, `交易等待中：目前有和其他人的交易未結束`);
          return report(job, { event: 'waiting', msg: '有其他交易進行中，請先在遊戲裡取消或完成' });
        }

        if (stepTimedOut && L.step) {
          if (isOurTrade) { try { await game({ type: 'tradeCancel', tradeId: t.id }); } catch (_) {} }
          return report(job, { event: 'error', msg: `${label} 在「${L.step}」這一步卡超過 3 分鐘，已取消` });
        }

        if (role === 'giver') {
          if (!isOurTrade) {
            if (L.invites >= 3) return report(job, { event: 'error', msg: `${label}：邀請 3 次都沒有成立` });
            if (L.step === 'invited' && Date.now() - L.stepAt < 30000) return; // 剛邀請，等對方
            const c = state.character;
            const { offer, skipped } = buildOffer(batch, c);
            if (!offer.items.length && !offer.money) {
              await report(job, { event: 'log', msg: `${label}：沒有可交易的東西，略過。${skipped.length ? '略過：' + skipped.join('、') : ''}` });
              return report(job, { event: 'batchDone', tradeId: null, skippedEmpty: true });
            }
            L.invites++;
            step('invited');
            setBadge(null, `${label}：送出邀請給 ${job.toName}`);
            await game({ type: 'tradeInvite', code: job.toCode });
            return report(job, { event: 'log', msg: `${label}：已送出邀請` });
          }
          L.tradeId = t.id;
          if (t.status === 'invited') { step('invited'); setBadge(null, `${label}：等待 ${job.toName} 接受`); return; }
          if (t.status === 'open') {
            if (!mine.locked) {
              const { offer, skipped } = buildOffer(batch, state.character);
              if (skipped.length) await report(job, { event: 'log', msg: `${label}：略過 ${skipped.join('、')}` });
              step('lock');
              setBadge(null, `${label}：放入 ${offer.items.length} 格＋楓幣 ${offer.money.toLocaleString()}，鎖定`);
              await game({ type: 'tradeOffer', tradeId: t.id, revision: t.revision, offer });
              const s2 = await game({ type: 'sync', tradeOnly: true });
              const t2 = s2.trade;
              await game({ type: 'tradeLock', tradeId: t2.id, revision: t2.revision, offer });
              return report(job, { event: 'log', msg: `${label}：已放入 ${offer.items.length} 格、楓幣 ${offer.money.toLocaleString()} 並鎖定` });
            }
            if (!theirs.locked) { step('waitLock'); setBadge(null, `${label}：等待 ${job.toName} 鎖定`); return; }
            if ((theirs.offer && ((theirs.offer.items || []).length || theirs.offer.money || theirs.offer.points))) {
              await game({ type: 'tradeCancel', tradeId: t.id }).catch(() => {});
              return report(job, { event: 'error', msg: `${label}：收貨方竟然也放了東西，已取消` });
            }
            if (!mine.confirmed) {
              step('confirm');
              setBadge(null, `${label}：確認交易`);
              await game({ type: 'tradeConfirm', tradeId: t.id, revision: t.revision });
              return report(job, { event: 'log', msg: `${label}：已確認，等待對方確認${mine.fees && mine.fees.money ? `（手續費 ${mine.fees.money.toLocaleString()}）` : ''}` });
            }
            step('waitConfirm'); setBadge(null, `${label}：等待 ${job.toName} 確認`);
            return;
          }
          return;
        }

        // ---- 收貨方 ----
        if (!isOurTrade) { step(''); setBadge(null, `${label}：等待 ${job.fromName} 的邀請`); return; }
        L.tradeId = t.id;
        if (t.status === 'invited') {
          // 只接受工作清單上指定的對象
          step('accept');
          setBadge(null, `${label}：接受 ${job.fromName} 的邀請`);
          await game({ type: 'tradeAccept', tradeId: t.id });
          return report(job, { event: 'log', msg: `${label}：已接受邀請` });
        }
        if (t.status === 'open') {
          if (!theirs.locked) { step('waitGiver'); setBadge(null, `${label}：等待 ${job.fromName} 放東西`); return; }
          const bad = verifyIncoming(batch, theirs.offer);
          if (bad) {
            await game({ type: 'tradeCancel', tradeId: t.id }).catch(() => {});
            return report(job, { event: 'error', msg: `${label}：核對失敗，已取消。${bad}` });
          }
          if (!mine.locked) {
            step('lock');
            await game({ type: 'tradeLock', tradeId: t.id, revision: t.revision, offer: { money: 0, points: 0, items: [] } });
            return report(job, { event: 'log', msg: `${label}：核對通過（${(theirs.offer.items || []).length} 格、楓幣 ${(theirs.offer.money || 0).toLocaleString()}），已鎖定` });
          }
          if (!mine.confirmed) {
            step('confirm');
            setBadge(null, `${label}：確認交易`);
            await game({ type: 'tradeConfirm', tradeId: t.id, revision: t.revision });
            return report(job, { event: 'log', msg: `${label}：收貨方已確認` });
          }
          step('waitConfirm'); setBadge(null, `${label}：等待 ${job.fromName} 確認`);
        }
      } catch (e) {
        console.warn('[szg-hub agent]', e);
        setBadge(null, '交易錯誤：' + e.message);
        try {
          const res = await hub('GET', `/api/agent?code=${encodeURIComponent(account && account.playerCode || '')}&charId=`);
          if (res && res.job) await report(res.job, { event: 'log', msg: '遊戲回應錯誤：' + e.message });
        } catch (_) {}
      } finally {
        agentRunning = false;
      }
    }

    function start() {
      setTimeout(tick, 3000);
      setInterval(tick, SCAN_MS);
      setInterval(agentTick, AGENT_MS);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();

    return { version: AGENT_VERSION, isBusy: () => agentBusy || agentRunning };
}
//== AGENT END ==

  // ---------- 載入器 ----------
  const ctx = { GM_xmlhttpRequest, GM_getValue, GM_setValue, W, HUB, TOKEN, shared, mode: 'bundled' };
  const hdr = TOKEN ? { 'X-Hub-Token': TOKEN } : {};
  const verOf = text => (String(text).match(/const AGENT_VERSION = '([^']+)'/) || [])[1];
  const BUNDLED_VERSION = verOf(agentMain.toString());
  let running = null;
  let evalBlocked = false;

  function runBundled(mode) {
    if (running) return;
    running = agentMain({ ...ctx, mode });
  }
  function boot() {
    GM_xmlhttpRequest({
      method: 'GET', url: HUB + '/agent.js?t=' + Date.now(), headers: hdr, timeout: 6000,
      onload: r => {
        if (r.status !== 200) return runBundled('bundled');
        const ver = verOf(r.responseText);
        if (!ver || ver === BUNDLED_VERSION) return runBundled('bundled');
        try {
          const fn = new Function('ctx', r.responseText + '\nreturn agentMain(ctx);');
          running = fn({ ...ctx, mode: 'live' });
          console.log(`[szg-hub] 已載入伺服器上的新版程式 ${ver}（內建 ${BUNDLED_VERSION}）`);
        } catch (e) {
          evalBlocked = true;
          console.warn('[szg-hub] 瀏覽器不允許動態載入，改用內建版本', e);
          runBundled('blocked');
        }
      },
      onerror: () => runBundled('bundled'),
      ontimeout: () => runBundled('bundled'),
    });
  }
  boot();

  // 每 2 分鐘檢查伺服器上的版本；有新版而且沒有工作在跑，就重新整理頁面
  setInterval(() => {
    if (evalBlocked || !running) return;
    GM_xmlhttpRequest({
      method: 'GET', url: HUB + '/api/agent-version?t=' + Date.now(), headers: hdr, timeout: 5000,
      onload: r => {
        try {
          const v = JSON.parse(r.responseText).version;
          if (v && v !== running.version && !running.isBusy()) {
            console.log(`[szg-hub] 偵測到新版 ${v}，重新整理頁面`);
            location.reload();
          }
        } catch (_) {}
      },
    });
  }, 2 * 60 * 1000);
})();
