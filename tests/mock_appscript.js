// 測試用：在 Node 裡跑 tools/quiz-share.gs（假的 SpreadsheetApp、CacheService、LockService、ContentService），開成 HTTP 服務
// GET / → doGet()；POST / → doPost()；GET /__sheet → 試算表內容；GET /__disable?key=… → 在「停用」欄打 x
'use strict';
const http = require('http'), fs = require('fs'), path = require('path'), vm = require('vm');
const port = Number(process.argv[2] || 9911);
const rows = [];  // 試算表（第一列是表頭）
const sheet = {
  appendRow: r => rows.push(r.slice()), setFrozenRows() {}, setColumnWidth() {},
  getDataRange: () => ({ getValues: () => rows.map(r => r.slice()) }),
  getRange: (r, c, nr, nc) => ({ setValues: vals => { for (let i = 0; i < nr; i++) rows[r - 1 + i] = vals[i].slice(0, nc); } }),
};
let made = false;
const cache = new Map();
const ctx = {
  SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: () => (made ? sheet : null), insertSheet: () => { made = true; return sheet; } }) },
  CacheService: { getScriptCache: () => ({ get: k => (cache.has(k) ? cache.get(k) : null), put: (k, v) => cache.set(k, String(v)), putAll: o => { for (const [k, v] of Object.entries(o)) cache.set(k, String(v)); }, getAll: ks => Object.fromEntries(ks.filter(k => cache.has(k)).map(k => [k, cache.get(k)])), remove: k => cache.delete(k) }) },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  ContentService: { MimeType: { JSON: 'json' }, createTextOutput: t => ({ text: t, setMimeType() { return this; } }) },
  Date, JSON, Object, Array, String, Number, Math,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'tools', 'quiz-share.gs'), 'utf8'), ctx);
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const done = o => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(typeof o === 'string' ? o : JSON.stringify(o)); };
  if (url.pathname === '/__sheet') return done(rows);
  if (url.pathname === '/__disable') { const r = rows.find(x => x[0] === url.searchParams.get('key')); if (r) r[6] = 'x'; cache.clear(); return done({ ok: !!r }); }
  if (url.pathname === '/__rl') { cache.clear(); return done({ ok: true }); }
  if (req.method === 'POST') { let b = ''; req.on('data', d => (b += d)); req.on('end', () => done(ctx.doPost({ postData: { contents: b } }).text)); return; }
  done(ctx.doGet().text);
}).listen(port, () => console.log('mock appscript on', port));
