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
        await d.screenshot(path='/tmp/dex.png')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-25:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
