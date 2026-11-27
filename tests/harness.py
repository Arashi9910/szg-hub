"""上漲谷中控 e2e 測試工具
- 起模擬遊戲（mockgame.js）與測試用中控（把私人 repo 複製到 /tmp/hub，關掉自動更新）
- 每個帳號開一個 Playwright context（= 一個 Chrome 設定檔），模擬 Tampermonkey 載入 szg-hub.user.js + agent.js
用法（在其他 e2e*.py 裡）：
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(3)
"""
import asyncio, json, os, shutil, subprocess, sys, time, urllib.request
from playwright.async_api import async_playwright

os.environ.setdefault('SZG_LAUNCHER', 'test')  # 測試直接管中控程序（不要 Mac／Linux 的看門程序）  # 測試絕對不能連到真的組隊大廳
REPO = os.environ.get('SZG_REPO', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 預設：tests 的上一層
HUB_DIR = '/tmp/hub'
HERE = os.path.dirname(os.path.abspath(__file__))
HUB = 'http://127.0.0.1:8787'
MOCK = 'http://127.0.0.1:9900'


def http(method, url, body=None, headers=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def hub_json(method, path, body=None):
    s, t = http(method, HUB + path, body)
    return json.loads(t) if t else None


def game_sell(char, map_id):
    """遊戲（mock）裡這隻角色某張圖的自動販售，換成「會賣哪些」：{'enabled', 'itemIds'(排序)}。
    遊戲 2026-11-27 起 rule 2：itemIds 是保留清單，可販售的掉落沒保留的就賣"""
    x = ((char.get('autoSell') or {}).get('maps') or {}).get(map_id)
    if not x: return {}
    rows = (hub_json('GET', '/api/world') or {}).get('autoSellDrops', {}).get(map_id) or []
    keep = set(int(i) for i in x.get('itemIds') or [])
    sell = sorted(int(r[0]) for r in rows if r[4] and int(r[0]) not in keep)
    on = bool(x.get('enabled')) and bool(sell)
    return {'enabled': on, 'itemIds': sell if on else []}


def wait_url(url, sec=15):
    end = time.time() + sec
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1); return
        except urllib.error.HTTPError:
            return  # 有回應就代表伺服器起來了
        except Exception:
            time.sleep(0.3)
    raise RuntimeError('等不到 ' + url)


def prepare_hub(fresh=True):
    if fresh and os.path.exists(HUB_DIR):
        shutil.rmtree(HUB_DIR)
    shutil.copytree(REPO, HUB_DIR, ignore=shutil.ignore_patterns('.git', 'data', 'backup', '.update-tmp', 'tests', '__pycache__'), dirs_exist_ok=True)


class Env:
    def __init__(self, fresh=True, headless=True, busy_rate=0, extdb=None, sync_ms=3000):
        self.fresh, self.headless, self.busy_rate, self.extdb, self.sync_ms = fresh, headless, busy_rate, extdb, sync_ms
        self.procs, self.contexts, self.logs = [], [], []

    async def __aenter__(self):
        prepare_hub(self.fresh)
        if self.extdb is not None:  # 預先放一份冒險資料庫（測試環境連不到外網）
            os.makedirs(os.path.join(HUB_DIR, 'data'), exist_ok=True)
            json.dump({'source': 'test', 'fetchedAt': int(time.time() * 1000), 'meta': {}, 'items': self.extdb, 'mobs': {}, 'quiz': []},
                      open(os.path.join(HUB_DIR, 'data', 'extdb.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        env = {**os.environ, 'BUSY_RATE': str(self.busy_rate), 'MOCK_SYNC_MS': str(self.sync_ms)}
        self.procs.append(subprocess.Popen(['node', os.path.join(HERE, 'mockgame.js'), '9900'], env=env, stdout=open('/tmp/mockgame.log', 'w'), stderr=subprocess.STDOUT))
        # 測試絕對不能送到真的共享題庫：沒指定時指向一個不存在的本機位址
        self.procs.append(subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787', 'SZG_QUIZ_SHARE_URL': os.environ.get('SZG_QUIZ_SHARE_URL', 'http://127.0.0.1:9/'), 'SZG_LOBBY_URL': os.environ.get('SZG_LOBBY_URL', 'http://127.0.0.1:9')}, stdout=open('/tmp/hub.log', 'w'), stderr=subprocess.STDOUT))
        try:
            wait_url(MOCK + '/api/account'); wait_url(HUB + '/api/settings')
        except Exception:
            for p in self.procs: p.terminate()
            raise RuntimeError('啟動失敗，請看 /tmp/mockgame.log、/tmp/hub.log')
        hub_json('POST', '/api/settings', {'autoUpdate': False})  # 不然會被 GitHub 版本蓋掉
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=self.headless)
        _, self.userscript = http('GET', HUB + '/szg-hub.user.js')
        _, self.agent = http('GET', HUB + '/agent.js')
        return self

    async def __aexit__(self, *a):
        for c in self.contexts:
            await c.close()
        await self.browser.close(); await self.pw.stop()
        for p in self.procs:
            p.terminate()

    def init_script(self):
        body = self.userscript.split('// ==/UserScript==', 1)[1]
        shim = r"""
const unsafeWindow = window;
const GM_getValue = (k, d) => { try { const v = localStorage.getItem('__gm:' + k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } };
const GM_setValue = (k, v) => localStorage.setItem('__gm:' + k, JSON.stringify(v));
const GM_xmlhttpRequest = o => { window.__gmx({ method: o.method, url: o.url, headers: o.headers || {}, data: o.data || null, timeout: o.timeout || 8000 })
  .then(r => r.error ? (r.error === 'timeout' ? o.ontimeout && o.ontimeout() : o.onerror && o.onerror(r)) : o.onload && o.onload(r)); };
"""
        # Tampermonkey 只在 @match 的網址跑；Playwright 的 init script 每個頁面（含 about:blank）都會跑，所以自己擋
        return '(function(){\nif (location.hostname !== "play.szg08.com") return;\n' + shim + self.agent + '\n' + body + '\n})();'

    async def open_account(self, acct, char=None):
        """開一個帳號的遊戲分頁（每個帳號一個瀏覽器設定檔＝context）。char：用 ?szgChar= 固定顯示那隻（同帳號第二個分頁）"""
        self.acct_ctx = getattr(self, 'acct_ctx', {})
        if acct in self.acct_ctx:
            ctx = self.acct_ctx[acct]
            page = await ctx.new_page()
            page.on('console', lambda m: self.logs.append(f'[{acct}/{char}] {m.type}: {m.text}'))
            page.on('pageerror', lambda e: self.logs.append(f'[{acct}/{char}] pageerror: {e}'))
            await page.goto('https://play.szg08.com/game/' + (f'?szgChar={char}' if char else ''))
            return page
        ctx = await self.browser.new_context()
        self.contexts.append(ctx)
        self.acct_ctx[acct] = ctx

        async def gmx(source, o):
            def do():
                data = o['data'].encode() if o.get('data') else None
                req = urllib.request.Request(o['url'], data=data, method=o['method'], headers=o.get('headers') or {})
                try:
                    with urllib.request.urlopen(req, timeout=o['timeout'] / 1000) as r:
                        return {'status': r.status, 'responseText': r.read().decode('utf-8', 'replace')}
                except urllib.error.HTTPError as e:
                    return {'status': e.code, 'responseText': e.read().decode('utf-8', 'replace')}
                except Exception as e:
                    return {'error': 'timeout' if 'timed out' in str(e) else str(e)}
            return await asyncio.to_thread(do)
        await ctx.expose_binding('__gmx', gmx)

        async def route(r):
            req = r.request
            path = req.url.split('play.szg08.com', 1)[1]
            hdr = {k: v for k, v in req.headers.items() if k.lower() in ('content-type', 'x-game-version')}
            hdr['x-acct'] = acct
            if path.startswith('/api/appearance'):  # 二進位（站姿 GIF），不經過文字解碼
                def get_bytes():
                    try:
                        with urllib.request.urlopen(urllib.request.Request(MOCK + path, headers=hdr), timeout=10) as x: return x.status, x.read()
                    except urllib.error.HTTPError as e: return e.code, e.read()
                s, b = await asyncio.to_thread(get_bytes)
                return await r.fulfill(status=s, body=b, content_type='image/gif')
            s, t = await asyncio.to_thread(http, req.method, MOCK + path, None, hdr) if not req.post_data else \
                await asyncio.to_thread(lambda: http_raw(req.method, MOCK + path, req.post_data, hdr))
            await r.fulfill(status=s, body=t, content_type='text/html; charset=utf-8' if path.startswith('/game') else 'application/json; charset=utf-8')
        await ctx.route('https://play.szg08.com/**', route)
        await ctx.add_init_script(self.init_script())
        page = await ctx.new_page()
        page.on('console', lambda m: self.logs.append(f'[{acct}] {m.type}: {m.text}'))
        page.on('pageerror', lambda e: self.logs.append(f'[{acct}] pageerror: {e}'))
        await page.goto('https://play.szg08.com/game/' + (f'?szgChar={char}' if char else ''))
        return page

    async def open_accounts(self, accts):
        return [await self.open_account(a) for a in accts]

    async def wait_chars(self, n, sec=40):
        end = time.time() + sec
        while time.time() < end:
            d = hub_json('GET', '/api/data')
            if d and len(d.get('chars', {})) >= n:
                return d
            await asyncio.sleep(1)
        raise AssertionError(f'中控 {sec} 秒內沒收到 {n} 隻角色；最近的頁面紀錄：\n' + '\n'.join(self.logs[-20:]))


def http_raw(method, url, data, headers):
    req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
