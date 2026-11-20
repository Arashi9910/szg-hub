"""角色全身照上傳＋組隊卡片顯示、組隊套用帶派工看板的自動販售範本、派工「流水線」3D 視圖載入與互動"""
import asyncio, json, os, sys, time
os.environ['MOCK_APPEARANCE'] = '1'
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

MAP = 'gms104040000'

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)

        print('1. 全身照上傳')
        av = await wait(lambda: (lambda a: a if {'c1', 'c3'} <= set(a) else None)(hub_json('GET', '/api/data').get('avatars') or {}), 60, 2)
        check(av, f"c1、c3 上傳全身照：{sorted((av or {}).keys())}")
        s, body = http('GET', 'http://127.0.0.1:8787/api/avatar/c1')
        check(s == 200 and body.startswith('GIF8'), 'GET /api/avatar/c1 回傳 GIF')
        s, _ = http('GET', 'http://127.0.0.1:8787/api/avatar/nobody')
        check(s == 404, '沒有的角色回 404')

        print('2. 組隊卡片顯示全身照、套用時帶自動販售範本')
        sell = {'enabled': True, 'itemIds': [2000000, 4000000]}
        hub_json('POST', '/api/settings', {'parties': [{'id': 'pA', 'name': '測試隊', 'members': ['c1', 'c3'], 'map': MAP}],
                                           'boards': {'A': {'lanes': {'train': [MAP], 'scroll': [], 'gear': []}, 'assign': {}, 'sell': {MAP: sell}, 'goals': {}}, 'B': {}}})
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=party]'); await d.wait_for_timeout(1200)
        n = await d.locator('#ptCards .pt-mem img.ava').count()
        check(n == 2, f'組隊卡片有 {n} 張全身照')
        await d.click('#ptApplyAll'); await d.wait_for_timeout(1500)
        jobs = await wait(lambda: (lambda js: js if js and all(j['status'] in ('done', 'failed') for j in js) else None)([j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'party']), 120)
        check(jobs and all(j['status'] == 'done' for j in jobs), '組隊工作完成' + ('' if jobs and all(j['status'] == 'done' for j in jobs) else '：' + '；'.join(f"{j['fromName']} {j['status']} {j['lastMsg']}" for j in (jobs or []))))
        for a, c in (('A1', 'c1'), ('A2', 'c3')):
            mc = mock_char(a, c); ms = (mc.get('autoSell') or {}).get('maps', {}).get(MAP)
            check(mc['map'] == MAP and ms and ms['enabled'] and sorted(ms['itemIds']) == sell['itemIds'], f'{c} 換到 {MAP} 並套用看板的自動販售（{ms}）')

        print('3. 派工「流水線」3D')
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(500)
        await d.click('#bdViewSeg [data-bview2=pipe]')
        frames = 0
        for _ in range(30):
            await d.wait_for_timeout(500)
            frames = await d.evaluate('window.__pipe ? window.__pipe.frames : -1')
            if frames > 10: break
        err = await d.evaluate('ui.pipe.err')
        check(frames > 10, f'3D 場景在跑（{frames} 格）' + (f'：{err}' if err else ''))
        await d.evaluate('poll(true)'); await d.wait_for_timeout(1500)
        lbl = await d.inner_text('#bdPipe3d')
        check('測試隊' in lbl and '經驗' in lbl and '商店' in lbl, '標籤有隊伍名稱、經驗、商店')
        check('隊伍 1' in (await d.inner_text('#bdPipeHud')).replace('\n', ' '), 'HUD 顯示隊伍數')
        r = await d.evaluate("window.__pipe.loot({map: '%s', name: '測試掉落', qty: 3, sold: true, goal: false})" % MAP)
        check(r is True, '掉落光球出現（沿著地圖→商店的管線飛）')
        seen = 0
        for _ in range(15):
            seen = await d.locator('.p3d-loot').count()
            if seen: break
            await d.wait_for_timeout(200)
        check(seen >= 1, '掉落圖示畫在畫面上')
        await d.screenshot(path='/tmp/pipe3d.png')
        await d.evaluate("pipePick({type: 'pod', key: 'pt:pA'})"); await d.wait_for_timeout(800)
        check(await d.evaluate("document.querySelector('nav button.on').dataset.tab") == 'party', '點隊伍平台 → 跳到組隊分頁')
        await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(500)
        await d.evaluate("pipePick({type: 'station', key: '%s'})" % MAP); await d.wait_for_timeout(500)
        check(await d.is_visible('#bdSell'), '點地圖站 → 打開自動販售設定')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
