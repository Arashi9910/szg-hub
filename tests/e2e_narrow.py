"""窄螢幕（直式螢幕、Windows 縮放 125%／150%）：每個分頁都不會把頁面撐出左右捲軸，頂端列不會被擠成直的"""
import asyncio, sys
from harness import Env, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
TABS = ['overview', 'gear', 'trade', 'bag', 'board', 'maps', 'market', 'quiz', 'forge', 'guild']

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2', 'A3']); await env.wait_chars(3); await asyncio.sleep(3)
        for w in [1080, 864, 720]:
            print(f'寬度 {w}')
            ctx = await env.browser.new_context(viewport={'width': w, 'height': 1200}); env.contexts.append(ctx)
            d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
            await d.goto(HUB + '/'); await d.wait_for_timeout(2500)
            over = []
            for t in TABS:
                await d.click(f'nav button[data-tab={t}]'); await d.wait_for_timeout(700)
                sw, iw = await d.evaluate('[document.documentElement.scrollWidth, innerWidth]')
                if sw > iw + 1: over.append(f'{t}({sw})')
            check(not over, '每個分頁都沒有左右撐破' + ('：' + '、'.join(over) if over else ''))
            hs = await d.evaluate("[document.querySelector('#status').offsetHeight, document.querySelector('#updBox').offsetHeight, document.querySelector('header').offsetHeight]")
            check(hs[0] <= 40 and hs[1] <= 40 and hs[2] <= 140, f'頂端列文字沒有被擠成直的（狀態 {hs[0]}px、更新 {hs[1]}px、整列 {hs[2]}px）')
            await d.click('nav button[data-tab=board]'); await d.wait_for_timeout(800)
            bh = await d.evaluate("(() => { const b = [...document.querySelectorAll('.fac-hud button')]; return b.length ? Math.max(...b.map(x => x.offsetHeight)) : 0; })()")
            check(bh <= 40, f'派工工具列的按鈕沒有被擠成直的（最高 {bh}px）')
            check(not errs, '沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
