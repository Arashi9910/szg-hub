"""讀遊戲程式碼 /api/bg/gamesrc：用已登入的背景分頁 fetch 遊戲的 .js（只讀）
1. 沒有背景分頁 → 回錯誤
2. 背景分頁登入後：搜尋片段、識別字、切片、檔案清單；不准讀 .js／.json 以外或 .. 路徑
3. 沒登入的背景分頁不會被拿來用
"""
import asyncio, json, os, subprocess, time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    CHROMIUM = p.chromium.executable_path
from harness import Env, hub_json, http, HUB, MOCK

os.environ.update({'MOCK_REQUIRE_LOGIN': '1', 'SZG_BG_GAME': MOCK, 'SZG_BG_LOGIN_PATH': '/__mock/login?acct={name}',
                   'SZG_BG_LOGIN_HEADLESS': '1', 'SZG_CHROME': CHROMIUM, 'SZG_BG_TICK_MS': '2000'})
ok_all = True
def check(cond, msg):
    global ok_all
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    if not cond: ok_all = False
    return cond
def src(qs): return hub_json('GET', '/api/bg/gamesrc?' + qs)
def prof(pid): return next(x for x in hub_json('GET', '/api/bg')['profiles'] if x['id'] == pid)
async def until(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        print('1. 沒有背景分頁')
        r = src('file=/game/game.js')
        check('error' in r and '背景分頁' in r['error'], f"回錯誤（{r.get('error')}）")
        pid = hub_json('POST', '/api/bg/add', {'name': 'A1'})['id']
        hub_json('POST', '/api/bg/start', {'id': pid})
        await until(lambda: prof(pid)['needLogin'], 30)
        r = src('file=/game/game.js')
        check('error' in r, f"還沒登入的背景分頁不會被拿來用（{r.get('error')}）")

        print('2. 登入後讀程式碼')
        hub_json('POST', '/api/bg/login', {'id': pid}); await asyncio.sleep(4)
        hub_json('POST', '/api/bg/login-done', {'id': pid})
        ok = await until(lambda: (lambda x: x['state'] == 'running' and x['code'] and not x['needLogin'] and any(l['injected'] for l in x['live']))(prof(pid)), 60)
        check(ok, '背景分頁已登入、在跑')
        r = await until(lambda: (lambda r: r if r.get('status') == 200 else None)(src('file=/game/game.js&q=' + quote('mobAttack') + '&ctx=20')), 30)
        check(r and r['len'] > 50 and r['from'] == 'A1', f"讀到 game.js（{r and r['len']} 字，從 {r and r['from']}）")
        check(r and r['count'] == 2 and len(r['matches']) == 2 and 'kind' in r['matches'][1]['text'], f"搜尋回片段（{r and r['matches']}）")
        r = src('words=' + quote('^party'))
        check([w for w, _ in r.get('words', [])] and set(w for w, _ in r['words']) == {'partyCreate', 'partyJoin'}, f"識別字清單（{r.get('words')}）")
        r = src('from=0&len=20')
        check(r.get('slice', {}).get('text', '').startswith('function partyCreate'), '切片讀一段')
        r = src('list=1')
        check('files' in r and r['from'] == 'A1', f"列出頁面載入的程式檔（{r.get('files')}）")
        for bad in ['/game/../x.js', '/etc/passwd', '/game/a.png']:
            check('error' in src('file=' + quote(bad)), f'不准讀 {bad}')
        r = src('q=' + quote('('))
        check('error' in r, '正規表示式錯誤會回錯誤，不會讓中控當掉')
        check(hub_json('GET', '/api/bg')['profiles'], '中控照常運作')
        hub_json('POST', '/api/bg/stop', {'id': pid}); await asyncio.sleep(3)
    print('\n全部通過' if ok_all else '\n有失敗')

asyncio.run(main())
