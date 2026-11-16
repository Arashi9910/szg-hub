// 上漲谷中控 - 本機伺服器（不需要安裝任何套件，Node.js 18 以上即可）
// 啟動：node server.js   然後打開 http://127.0.0.1:8787
'use strict';

const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const updater = require('./update');

const PORT = Number(process.env.PORT) || 8787;
// REMOTE=1 時開放外部連線（例如 Tailscale）；外部連線一律要帶通行碼，本機連線不用。
const REMOTE = process.env.REMOTE === '1';
const HOST = REMOTE ? '0.0.0.0' : '127.0.0.1';
const DATA_DIR = path.join(__dirname, 'data');
const STATE_FILE = path.join(DATA_DIR, 'state.json');
const TOKEN_FILE = path.join(DATA_DIR, 'token.txt');
const DASHBOARD = path.join(__dirname, 'dashboard.html');
const USERSCRIPT = path.join(__dirname, 'szg-hub.user.js');

fs.mkdirSync(DATA_DIR, { recursive: true });

let TOKEN = '';
try { TOKEN = fs.readFileSync(TOKEN_FILE, 'utf8').trim(); } catch (_) {}
if (!TOKEN) {
  TOKEN = crypto.randomBytes(12).toString('hex');
  try { fs.writeFileSync(TOKEN_FILE, TOKEN); } catch (_) { console.warn('[警告] 通行碼無法存檔，重開伺服器後會換一組。'); }
}

let updateInfo = { current: updater.localVersion(), latest: null, hasUpdate: false, notes: '', checkedAt: 0, error: '' };
async function checkUpdate() {
  try {
    const r = await updater.check();
    updateInfo = { current: r.current, latest: r.latest, hasUpdate: r.hasUpdate, notes: r.notes, checkedAt: Date.now(), error: '' };
    if (r.hasUpdate) {
      const busy = db.jobs.some(j => ACTIVE.has(j.status));
      if (db.settings.autoUpdate !== false && !busy) return await applyUpdateAndRestart();
      console.log(`有新版本 ${r.latest}（目前 ${r.current}）${busy ? '，等工作結束後自動更新' : '，可在面板按「更新並重啟」'}。`);
    }
  } catch (e) {
    const c = e.cause && (e.cause.code || (e.cause.errors && e.cause.errors[0] && e.cause.errors[0].code) || e.cause.message);
    updateInfo.error = c ? `${e.message}（${c}）` : e.message;
    updateInfo.checkedAt = Date.now();
    console.log('檢查更新失敗：' + updateInfo.error);
  }
}

// 腳本裡 //== AGENT START == 到 //== AGENT END == 之間是實際功能，各設定檔每次載入都會來拿這一段
function agentSource() {
  const src = userscriptSource();
  const a = src.indexOf('//== AGENT START =='), b = src.indexOf('//== AGENT END ==');
  if (a < 0 || b < 0) throw new Error('腳本缺少 AGENT 區段');
  return src.slice(a, b);
}
async function applyUpdateAndRestart() {
  const r = await updater.apply();
  if (r.updated) {
    console.log(`已更新到 ${r.latest}，重新啟動中…`);
    clearTimeout(saveTimer);
    try { fs.writeFileSync(STATE_FILE, JSON.stringify(db)); } catch (_) {}
    setTimeout(() => process.exit(3), 300); // start.bat 看到代碼 3 會自動重開
  }
  return r;
}
// 版本號只有一個來源：version.json。提供給瀏覽器的腳本會把版本號換成它，
// 所以伺服器、面板、腳本、Tampermonkey 顯示的數字永遠一致；每次發新版，遊戲頁面都會自動重整一次。
function scriptVersion() { return updater.localVersion(); }
function stampVersion(src) {
  const v = scriptVersion();
  return src.replace(/const AGENT_VERSION = '[^']*'/, `const AGENT_VERSION = '${v}'`)
            .replace(/(\/\/ @version\s+)\S+/, `$1${v}`);
}
function userscriptSource() { return stampVersion(fs.readFileSync(USERSCRIPT, 'utf8')); }
function isLocal(req) {
  const a = req.socket.remoteAddress || '';
  return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1';
}
function tokenOk(req, url) {
  const t = req.headers['x-hub-token'] || url.searchParams.get('token') || '';
  const a = Buffer.from(String(t)), b = Buffer.from(TOKEN);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// 依連進來的位址，產生已填好連線位址與通行碼的遠端版腳本
function remoteUserscript(hostHeader) {
  const host = String(hostHeader || '').replace(/[^\w.:\-\[\]]/g, '');
  const hostname = host.replace(/:\d+$/, '').replace(/^\[|\]$/g, '');
  return userscriptSource()
    .replace(/(@name\s+.*)/, '$1（遠端）')
    .replace(/\/\/ @connect\s+127\.0\.0\.1/, `// @connect      ${hostname}`)
    .replace(/const HUB = '[^']*';/, `const HUB = 'http://${host}';`)
    .replace(/const TOKEN = '[^']*';/, `const TOKEN = '${TOKEN}';`)
    .replace(/(\/\/ @(?:updateURL|downloadURL)\s+).*/g, `$1http://${host}/remote.user.js?token=${TOKEN}`);
}

let db = { chars: {}, jobs: [], settings: { accountLabels: {}, mainCharId: null, presets: [], slotStats: {} } };
try {
  const loaded = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  db = { ...db, ...loaded, jobs: loaded.jobs || [], settings: { ...db.settings, ...(loaded.settings || {}) } };
} catch (_) { /* 第一次啟動 */ }

let saveTimer = null;
let saveFailed = false;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const tmp = STATE_FILE + '.tmp';
    try {
      fs.writeFileSync(tmp, JSON.stringify(db));
      fs.renameSync(tmp, STATE_FILE);
      if (saveFailed) { console.log('存檔恢復正常。'); saveFailed = false; }
    } catch (e) {
      try { fs.unlinkSync(tmp); } catch (_) {}
      if (!saveFailed) console.warn(`[警告] 資料存檔失敗（${e.code || e.message}）：面板照常運作，但關掉伺服器後資料不會保留。若是 ENOSPC，代表硬碟空間不足。`);
      saveFailed = true;
    }
  }, 1000);
}


// ================= 交易工作 =================
// 狀態：pending（等你確認）→ approved（排隊中）→ running → done / failed / cancelled
const ACTIVE = new Set(['approved', 'running']);
const ONLINE_MS = 90 * 1000; // 這段時間內有回報資料，才算對方在線

function codeOf(charId) { const s = db.chars[charId]; return s && s.playerCode; }
function onlineCode(code) {
  return Object.values(db.chars).some(s => s.playerCode === code && Date.now() - (s.receivedAt || 0) < ONLINE_MS);
}
// 某個帳號目前應該處理的工作：最早建立、還沒結束、而且牽涉到它的那一個
function currentJobFor(code) {
  return db.jobs.filter(j => ACTIVE.has(j.status) && (j.fromCode === code || j.toCode === code))
    .sort((a, b) => a.createdAt - b.createdAt)[0] || null;
}
function jobLog(job, msg) {
  const last = job.log[job.log.length - 1];
  if (last && last.msg === msg) { last.at = Date.now(); last.n = (last.n || 1) + 1; return; }
  job.log.push({ at: Date.now(), msg });
  if (job.log.length > 200) job.log.splice(0, job.log.length - 200);
}
function publicJob(j) { return j; }

const BAG_KINDS = new Set(['sell', 'lock', 'unlock']);
function createBagJob(body) {
  const owner = db.chars[body.fromCharId];
  if (!owner) throw new Error('找不到角色資料');
  if (!owner.playerCode) throw new Error('角色還沒回報 12 碼 ID，請先更新腳本並打開遊戲頁面');
  const b = (body.batches || [])[0] || {};
  if (!(b.items || []).length && !(b.gear || []).length) throw new Error('沒有選擇任何物品');
  const job = {
    id: crypto.randomBytes(6).toString('hex'), kind: body.kind, status: 'pending', createdAt: Date.now(),
    fromCharId: owner.char.id, fromName: owner.char.name, fromCode: owner.playerCode,
    toCharId: owner.char.id, toName: owner.char.name, toCode: owner.playerCode,
    batches: [{ items: b.items || [], gear: b.gear || [], money: 0 }], batchIndex: 0, log: [], lastMsg: '',
    estimate: Number(body.estimate) || 0,
  };
  db.jobs.push(job);
  save();
  return job;
}

function createJob(body) {
  if (BAG_KINDS.has(body.kind)) return createBagJob(body);
  const from = db.chars[body.fromCharId], to = db.chars[body.toCharId];
  if (!from || !to) throw new Error('找不到角色資料');
  if (!from.playerCode || !to.playerCode) throw new Error('角色還沒回報 12 碼 ID，請先更新腳本並打開遊戲頁面');
  if (from.playerCode === to.playerCode) throw new Error('同帳號角色請用倉庫轉移，不能交易');
  const batches = (body.batches || []).filter(b => (b.items && b.items.length) || (b.gear && b.gear.length) || b.money);
  if (!batches.length) throw new Error('沒有要交易的東西');
  const job = {
    id: crypto.randomBytes(6).toString('hex'),
    kind: body.kind === 'give' ? 'give' : 'collect',
    status: 'pending',
    createdAt: Date.now(),
    fromCharId: from.char.id, fromName: from.char.name, fromCode: from.playerCode,
    toCharId: to.char.id, toName: to.char.name, toCode: to.playerCode,
    strictChar: true,
    batches, batchIndex: 0,
    log: [], lastMsg: '',
  };
  db.jobs.push(job);
  save();
  return job;
}

function send(res, code, body, type = 'application/json; charset=utf-8') {
  res.writeHead(code, {
    'Content-Type': type,
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, X-Hub-Token',
    'Cache-Control': 'no-store',
  });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
}

function readBody(req, limit = 5 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', c => {
      size += c.length;
      if (size > limit) { reject(new Error('too large')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${HOST}`);
    if (req.method === 'OPTIONS') return send(res, 204, '');
    if (!isLocal(req) && !tokenOk(req, url)) return send(res, 401, { error: '需要通行碼' });

    if (req.method === 'GET' && url.pathname === '/agent.js') {
      return send(res, 200, agentSource(), 'text/javascript; charset=utf-8');
    }
    if (req.method === 'GET' && url.pathname === '/api/agent-version') {
      return send(res, 200, { version: scriptVersion() });
    }
    if (req.method === 'GET' && url.pathname === '/szg-hub.user.js') {
      return send(res, 200, userscriptSource(), 'text/javascript; charset=utf-8');
    }
    if (req.method === 'GET' && url.pathname === '/remote.user.js') {
      return send(res, 200, remoteUserscript(req.headers.host), 'text/javascript; charset=utf-8');
    }

    if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
      return send(res, 200, fs.readFileSync(DASHBOARD, 'utf8'), 'text/html; charset=utf-8');
    }

    if (req.method === 'GET' && url.pathname === '/api/data') {
      return send(res, 200, { now: Date.now(), chars: db.chars, settings: db.settings, jobs: db.jobs.slice(-100), scriptVersion: scriptVersion(), update: updateInfo });
    }

    if (req.method === 'POST' && url.pathname === '/api/push') {
      const snap = JSON.parse(await readBody(req));
      if (!snap || !snap.char || !snap.char.id) return send(res, 400, { error: 'bad snapshot' });
      snap.receivedAt = Date.now();
      db.chars[snap.char.id] = snap;
      // 同帳號的另一隻角色：更新它在角色大廳看得到的基本資料（等級、是否掛機）
      for (const other of snap.accountChars || []) {
        const prev = db.chars[other.id];
        if (prev && other.id !== snap.char.id) {
          if (snap.playerCode) prev.playerCode = snap.playerCode;
          prev.char.lv = other.lv;
          prev.char.auto = !!other.auto;
          prev.accountId = snap.accountId;
        }
      }
      save();
      return send(res, 200, { ok: true });
    }

    if (req.method === 'POST' && url.pathname === '/api/settings') {
      const patch = JSON.parse(await readBody(req));
      db.settings = { ...db.settings, ...patch };
      save();
      return send(res, 200, { ok: true, settings: db.settings });
    }


    // ---- 自動更新 ----
    if (req.method === 'POST' && url.pathname === '/api/update/check') {
      await checkUpdate();
      return send(res, 200, updateInfo);
    }
    if (req.method === 'POST' && url.pathname === '/api/update/apply') {
      if (!isLocal(req)) return send(res, 403, { error: '只能在家裡電腦上更新' });
      if (db.jobs.some(j => ACTIVE.has(j.status))) return send(res, 409, { error: '有交易工作正在執行，請等它結束或取消後再更新' });
      const r = await applyUpdateAndRestart();
      return send(res, 200, { ok: true, updated: r.updated, latest: r.latest });
    }

    // ---- 交易工作 ----
    if (req.method === 'GET' && url.pathname === '/api/jobs') {
      return send(res, 200, { jobs: db.jobs.slice(-100).map(publicJob) });
    }
    if (req.method === 'POST' && url.pathname === '/api/jobs') {
      const body = JSON.parse(await readBody(req));
      const list = Array.isArray(body) ? body : [body];
      const created = [];
      for (const b of list) created.push(createJob(b));
      return send(res, 200, { ok: true, jobs: created });
    }
    let m;
    if (req.method === 'POST' && (m = url.pathname.match(/^\/api\/jobs\/(\w+)\/(approve|cancel|retry|delete)$/))) {
      const job = db.jobs.find(j => j.id === m[1]);
      if (!job) return send(res, 404, { error: 'no job' });
      if (m[2] === 'approve' && job.status === 'pending') { job.status = 'approved'; jobLog(job, '已確認，排隊等待執行'); }
      if (m[2] === 'cancel' && !['done', 'cancelled'].includes(job.status)) { job.status = 'cancelled'; jobLog(job, '已取消（若遊戲裡還有進行中的交易，請手動取消）'); }
      if (m[2] === 'retry' && job.status === 'failed') { job.status = 'approved'; jobLog(job, `從第 ${job.batchIndex + 1} 批重新開始`); }
      if (m[2] === 'delete' && !ACTIVE.has(job.status)) db.jobs = db.jobs.filter(j => j !== job);
      save();
      return send(res, 200, { ok: true });
    }
    if (req.method === 'POST' && url.pathname === '/api/jobs/approve-all') {
      for (const j of db.jobs) if (j.status === 'pending') { j.status = 'approved'; jobLog(j, '已確認，排隊等待執行'); }
      save();
      return send(res, 200, { ok: true });
    }

    // 腳本查詢：這個帳號現在要做什麼
    if (req.method === 'GET' && url.pathname === '/api/agent') {
      const code = url.searchParams.get('code') || '';
      const job = currentJobFor(code);
      if (!job) return send(res, 200, { job: null });
      if (BAG_KINDS.has(job.kind)) return send(res, 200, { job, role: 'owner', peerReady: true });
      const role = job.fromCode === code ? 'giver' : 'receiver';
      const peer = role === 'giver' ? job.toCode : job.fromCode;
      // 對方帳號也必須以這個工作為優先，才開始（避免同時跟兩個人交易）
      const peerJob = currentJobFor(peer);
      const peerReady = !!peerJob && peerJob.id === job.id && onlineCode(peer);
      return send(res, 200, { job, role, peerReady });
    }
    if (req.method === 'POST' && url.pathname === '/api/agent/report') {
      const ev = JSON.parse(await readBody(req));
      const job = db.jobs.find(j => j.id === ev.jobId);
      if (!job || !ACTIVE.has(job.status)) return send(res, 200, { ok: true, ignored: true });
      if (ev.batchIndex !== job.batchIndex) return send(res, 200, { ok: true, ignored: true });
      if (job.status === 'approved') job.status = 'running';
      if (ev.event === 'log' || ev.event === 'waiting') { jobLog(job, ev.msg); job.lastMsg = ev.msg; }
      if (ev.event === 'error') { job.status = 'failed'; jobLog(job, '失敗：' + ev.msg); job.lastMsg = ev.msg; }
      if (ev.event === 'batchDone') {
        jobLog(job, BAG_KINDS.has(job.kind) ? '完成' : ev.skippedEmpty ? `第 ${job.batchIndex + 1} 批沒有東西，略過` : `第 ${job.batchIndex + 1} 批交易完成`);
        job.batchIndex++;
        if (job.batchIndex >= job.batches.length) { job.status = 'done'; job.lastMsg = '全部完成'; jobLog(job, '全部完成'); }
      }
      job.updatedAt = Date.now();
      save();
      return send(res, 200, { ok: true });
    }

    if (req.method === 'POST' && url.pathname === '/api/forget') {
      const { charId } = JSON.parse(await readBody(req));
      delete db.chars[charId];
      save();
      return send(res, 200, { ok: true });
    }

    send(res, 404, { error: 'not found' });
  } catch (e) {
    send(res, 400, { error: String(e && e.message || e) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`上漲谷中控已啟動：http://127.0.0.1:${PORT}`);
  console.log(`版本 ${scriptVersion()}。各設定檔安裝網址：http://127.0.0.1:${PORT}/szg-hub.user.js`);
  if (REMOTE) {
    const ips = Object.values(os.networkInterfaces()).flat().filter(i => i && i.family === 'IPv4' && !i.internal).map(i => i.address);
    const ts = ips.filter(ip => /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(ip));
    console.log('');
    console.log('已開放遠端連線。在公司電腦（裝好 Tampermonkey 後）打開下面網址安裝遠端版腳本：');
    for (const ip of (ts.length ? ts : ips)) console.log(`  http://${ip}:${PORT}/remote.user.js?token=${TOKEN}`);
    if (!ts.length) console.log('  （沒偵測到 Tailscale 位址 100.x.x.x，請確認 Tailscale 已登入）');
    console.log(`遠端看面板：http://<上面的位址>:${PORT}/?token=${TOKEN}`);
    console.log('通行碼存在 data\\token.txt，刪掉它再重啟就會換一組（遠端腳本要重裝）。');
  }
  console.log('');
  console.log('保持這個視窗開著；關掉視窗就會停止。');
  checkUpdate();
  setInterval(checkUpdate, 2 * 60 * 1000);
});
