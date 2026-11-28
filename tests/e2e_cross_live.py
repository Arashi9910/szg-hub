"""十字獵人分頁接真的 /api/cross（不攔截）：面板畫出 mock 遊戲的任務與角色，按「一鍵接取」真的在遊戲裡接到任務，自動狩獵把角色移到無 BOSS 地圖。"""
import asyncio, json, os, sys, time
import harness
from harness import Env, hub_json, http, HUB, MOCK

_prep = harness.prepare_hub
def _prep_bump(fresh=True):
    _prep(fresh)
    p = os.path.join(harness.HUB_DIR, 'version.json'); v = json.load(open(p, encoding='utf-8'))
    v['version'] = '0.82.0'; json.dump(v, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
harness.prepare_hub = _prep_bump
os.environ.setdefault('SZG_CROSS_TICK_MS', '3000')

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(acc, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acc]['chars'][c]
async def wait(fn, sec=30, step=1):
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
        await env.open_accounts(['A1'])
        await wait(lambda: (hub_json('GET', '/api/data')['chars'].get('c1') or {}).get('char', {}).get('cross') is not None, 60)
        await wait(lambda: hub_json('GET', '/api/cross')['quests'], 40)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        dialogs = []; d.on('dialog', lambda dl: (dialogs.append(dl.message), asyncio.ensure_future(dl.accept())))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=cross]')
        await d.wait_for_selector('#crChars tr[data-crsel="c1"]', timeout=15000)
        print('1. 真的 API 畫出來')
        txt = await d.inner_text('#cross')
        check('幼小石球懸賞標示牌' in txt or '幼小石球' in txt, '任務總表有 mock 的十字獵人任務')
        check(await d.locator('[data-crmap]').count() >= 1, '每張任務有地圖下拉')
        print('2. 勾 c1 → 一鍵接取 → 遊戲裡接到')
        if 'on' not in ((await d.get_attribute('#crChars tr[data-crsel="c1"]', 'class')) or '').split():
            await d.click('#crChars tr[data-crsel="c1"] td:nth-child(3)'); await d.wait_for_timeout(1000)
        check(hub_json('GET', '/api/cross')['cfg']['ids'] == ['c1'], 'cfg.ids=[c1] 存到伺服器')
        btn = d.locator('#crBar button', has_text='一鍵接取')
        check(await btn.count() == 1, '有一鍵接取按鈕')
        await btn.click(); await d.wait_for_timeout(1000)
        check(dialogs and '接' in dialogs[-1], f'先跳確認框（{dialogs[-1:]}）')
        m = await wait(lambda: (lambda q: q if len(q) >= 2 else None)(mock_char('A1', 'c1')['quests']), 40)
        check(m and all(k.startswith('cross_') for k in m), f'遊戲裡 c1 接到十字獵人任務（{m}）')
        print('3. 打開自動狩獵 → 移到目標地圖')
        await d.click('#crEnabled'); await d.wait_for_timeout(1000)
        check(hub_json('GET', '/api/cross')['cfg']['enabled'] is True, '自動狩獵已開')
        row = await wait(lambda: (lambda r: r if r.get('target') and r.get('onTarget') else None)(next(x for x in hub_json('GET', '/api/cross')['chars'] if x['id'] == 'c1')), 60)
        check(row and mock_char('A1', 'c1')['map'] == row['target']['map'], f'c1 到了目標地圖（{row and row["target"]}）')
        await d.wait_for_timeout(4000)
        c1 = await d.inner_text('#crChars tr[data-crsel="c1"]')
        check('打獵中' in c1 or '移動中' in c1, f'面板顯示狀態（{c1!r}）')
        check(not errs, f'沒有 JS 錯誤（{errs[:2]}）')
        print('4. 舊版腳本上傳舊格式世界資料（w7、沒有 crossQuests）不能把任務清單洗掉')
        n0 = len(hub_json('GET', '/api/cross')['quests'])
        s, b = http('POST', HUB + '/api/world', {'version': 'w7:old', 'maps': [{'id': 'x', 'name': 'x', 'mobIds': []}], 'mobs': []})
        check(s == 200 and 'ignored' in b, f'舊格式被忽略（{s} {b[:80]}）')
        await asyncio.sleep(2)
        check(n0 > 0 and len(hub_json('GET', '/api/cross')['quests']) == n0, f'任務清單還在（{n0} 張）')
        check(len(json.loads(http('GET', HUB + '/api/world')[1])['maps']) > 1, '地圖資料沒被蓋掉')
    print('\n全部通過' if ok else '\n有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
