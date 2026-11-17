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
    def __init__(self, fresh=True, headless=True, busy_rate=0):
        self.fresh, self.headless, self.busy_rate = fresh, headless, busy_rate
        self.procs, self.contexts, self.logs = [], [], []

    async def __aenter__(self):
        prepare_hub(self.fresh)
        env = {**os.environ, 'BUSY_RATE': str(self.busy_rate)}
        self.procs.append(subprocess.Popen(['node', os.path.join(HERE, 'mockgame.js'), '9900'], env=env, stdout=open('/tmp/mockgame.log', 'w'), stderr=subprocess.STDOUT))
        self.procs.append(subprocess.Popen(['node', 'server.js'], cwd=HUB_DIR, env={**os.environ, 'PORT': '8787'}, stdout=open('/tmp/hub.log', 'w'), stderr=subprocess.STDOUT))
        wait_url(MOCK + '/api/account'); wait_url(HUB + '/api/settings')
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
        return '(function(){\n' + shim + self.agent + '\n' + body + '\n})();'

    async def open_account(self, acct):
        ctx = await self.browser.new_context()
        self.contexts.append(ctx)

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
            s, t = await asyncio.to_thread(http, req.method, MOCK + path, None, hdr) if not req.post_data else \
                await asyncio.to_thread(lambda: http_raw(req.method, MOCK + path, req.post_data, hdr))
            await r.fulfill(status=s, body=t, content_type='text/html; charset=utf-8' if path.startswith('/game') else 'application/json; charset=utf-8')
        await ctx.route('https://play.szg08.com/**', route)
        await ctx.add_init_script(self.init_script())
        page = await ctx.new_page()
        page.on('console', lambda m: self.logs.append(f'[{acct}] {m.type}: {m.text}'))
        page.on('pageerror', lambda e: self.logs.append(f'[{acct}] pageerror: {e}'))
        await page.goto('https://play.szg08.com/game/')
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
