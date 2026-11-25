"""裝備圖鑑：遊戲分頁上傳裝備目錄、職業（選職業不混全職業）、等級、部位、搜尋、只看我有的、浮動範圍"""
import asyncio, sys, time
from harness import Env, hub_json

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        w = await wait(lambda: (lambda x: x if x.get('equipment') else None)(hub_json('GET', '/api/world') or {}), 40, 2)
        eq = (w or {}).get('equipment') or []
        check(len(eq) >= 4, f'世界資料有裝備目錄 {len(eq)} 件')
        ctx = await env.browser.new_context(viewport={'width': 1300, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=dex]'); await d.wait_for_timeout(800)
        names = lambda: d.eval_on_selector_all('#dexGrid .dex-card .nm', 'els => els.map(e => e.childNodes[0].textContent.trim())')
        allN = await names()
        check(len(allN) == len(eq), f'全部：{len(allN)} 件')
        await d.click('[data-dexjob="4"]'); await d.wait_for_timeout(300)
        n = await names()
        check(n == ['戰鬥弓'], f'弓箭手：只有弓，不混全職業（{n}）')
        await d.click('[data-dexjob="common"]'); await d.wait_for_timeout(300)
        n = await names()
        check('工地手套' in n and '戰鬥弓' not in n and '劍' not in n, f'全職業：只有全職業裝備（{n}）')
        await d.click('[data-dexjob="all"]'); await d.click('[data-dexlv="0-9"]'); await d.wait_for_timeout(300)
        n = await names()
        check('劍' in n and '戰鬥弓' not in n, f'等級 0～9（{n}）')
        await d.fill('#dexLvMin', '10'); await d.fill('#dexLvMax', '10'); await d.wait_for_timeout(300)
        n = await names()
        check('戰鬥弓' in n and '劍' not in n, f'自訂等級 10～10（{n}）')
        await d.fill('#dexLvMin', ''); await d.fill('#dexLvMax', ''); await d.click('[data-dexlv="all"]')
        await d.click('[data-dexslot="weapon"]'); await d.wait_for_timeout(300)
        n = await names()
        check('戰鬥弓' in n and '工地手套' not in n, f'部位：武器（{n}）')
        txt = await d.inner_text('#dexGrid')
        check('（±3）' in txt, '戰鬥弓物攻 28 顯示浮動 ±3')
        await d.click('[data-dexslot=""]'); await d.fill('#dexQ', '手套'); await d.wait_for_timeout(300)
        n = await names()
        check(n and all('手套' in x for x in n), f'搜尋「手套」（{n}）')
        await d.fill('#dexQ', ''); await d.check('#dexOwned'); await d.wait_for_timeout(300)
        n = await names()
        check(0 < len(n) < len(eq), f'只看我有的：{n}')
        await d.uncheck('#dexOwned'); await d.fill('#dexQ', '戰鬥弓'); await d.wait_for_timeout(300)
        txt = await d.inner_text('#dexGrid')
        check('掉落' in txt and '30%' in txt, f'戰鬥弓顯示掉落處與最高機率（紅寶王 30%）')
        await d.click('[data-dexsrc]'); await d.wait_for_timeout(300)
        check(await d.locator('.dex-card .sr').count() >= 1, '展開掉落地點清單')
        await d.screenshot(path='/tmp/dex.png')
        mid = await d.get_attribute('.dex-card .sr [data-dexmap]', 'data-dexmap')
        await d.click('.dex-card .sr [data-dexmap]'); await d.wait_for_timeout(800)
        check(await d.evaluate("document.querySelector('nav button.on').dataset.tab") == 'dex' and await d.evaluate('ui.dexView') == 'maps', '按「地圖」→ 圖鑑的「地圖查詢」')
        check(await d.locator(f'#wMaps [data-wmap="{mid}"]').count() == 1 and await d.evaluate(f"ui.wOpen.has('{mid}')"), '地圖查詢列出並展開那張圖')
        await d.click('#dexView [data-dexview=items]'); await d.fill('#wItem', '戰鬥弓'); await d.wait_for_timeout(500)
        check('海岸草叢' in await d.inner_text('#wItemOut') or '射手訓練場' in await d.inner_text('#wItemOut'), '掉落物查詢：' + (await d.inner_text('#wItemOut')).replace('\n', ' ')[:60])
        await d.click('#dexView [data-dexview=equip]'); await d.wait_for_timeout(500)
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.accept()))
        await d.click('.dex-card .sr [data-dexboard]'); await d.wait_for_timeout(1200)
        check(await d.evaluate("document.querySelector('nav button.on').dataset.tab") == 'board', '按「派工」→ 跳到派工')
        bs = hub_json('GET', '/api/data')['settings'].get('boards') or {}
        b = [x for x in bs.values() if mid in ((x.get('lanes') or {}).get('gear') or [])]
        check(b and 1452002 in [int(i) for i in (b[0].get('goals') or {}).get(mid, [])], f'看板「打裝備」加入 {mid}，目標有戰鬥弓')
        await d.click('nav button[data-tab=dex]'); await d.wait_for_timeout(300)
        await d.fill('#dexQ', ''); await d.check('#dexDrop'); await d.wait_for_timeout(300)
        n = await names()
        check(set(n) == {'工地手套', '褐色工作手套', '戰鬥弓'}, f'只看有怪物掉的（{n}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
